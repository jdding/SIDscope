#!/usr/bin/env python3
"""Build a pinned Latte/PSID rqkmeans cache from local official data files.

This intentionally runs outside the core package dependencies.  Supply the
pinned official Latte checkout, the three Amazon Reviews 2023 history CSVs,
and the matching raw metadata JSONL.  The script executes the official Latte
metadata-cleaning and RQ-kmeans/conflict-resolution class methods, then records
all input/output hashes without embedding machine-local paths in the report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import types
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA
import sklearn
import sentence_transformers
import torch


PINNED_LATTE_REVISION = "05e4e6d983225bcb7172f148a076890e80c524d1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def list_to_str(value: list[Any] | str, remove_blank: bool = False) -> str:
    result = ", ".join(map(str, value)) if isinstance(value, list) else value
    return result.replace(" ", "") if remove_blank else result


def clean_text(raw_text: list[Any] | str) -> str:
    """Byte-for-byte translation of the pinned upstream clean_text helper."""

    text = list_to_str(raw_text)
    text = html.unescape(text)
    text = text.strip()
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\n\t]", " ", text)
    text = re.sub(r" +", " ", text)
    return re.sub(r"[^\x00-\x7F]", " ", text)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_official_classes(upstream_root: Path):
    genrec_module = types.ModuleType("genrec")
    genrec_module.__path__ = []
    dataset_base_module = types.ModuleType("genrec.dataset")
    dataset_base_module.AbstractDataset = object
    tokenizer_base_module = types.ModuleType("genrec.tokenizer")
    tokenizer_base_module.AbstractTokenizer = object
    utils_module = types.ModuleType("genrec.utils")
    utils_module.clean_text = clean_text
    datasets_module = types.ModuleType("datasets")
    datasets_module.load_dataset = None
    datasets_module.Dataset = object
    sys.modules.update(
        {
            "genrec": genrec_module,
            "genrec.dataset": dataset_base_module,
            "genrec.tokenizer": tokenizer_base_module,
            "genrec.utils": utils_module,
            "datasets": datasets_module,
        }
    )
    dataset_module = load_module(
        "sidscope_latte_build_dataset",
        upstream_root / "genrec/datasets/AmazonReviews2023/dataset.py",
    )
    tokenizer_module = load_module(
        "sidscope_latte_build_tokenizer",
        upstream_root / "genrec/models/Latte/tokenizer.py",
    )
    return dataset_module.AmazonReviews2023, tokenizer_module.LatteTokenizer


def read_histories(csv_paths: list[Path]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    mapping: dict[str, Any] = {
        "user2id": {"[PAD]": 0},
        "item2id": {"[PAD]": 0},
        "id2user": ["[PAD]"],
        "id2item": ["[PAD]"],
    }
    retained_rows: list[dict[str, str]] = []
    for path in csv_paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if not row["history"]:
                    continue
                retained_rows.append(row)
                user = row["user_id"]
                target = row["parent_asin"]
                if user not in mapping["user2id"]:
                    mapping["user2id"][user] = len(mapping["user2id"])
                    mapping["id2user"].append(user)
                if target not in mapping["item2id"]:
                    mapping["item2id"][target] = len(mapping["item2id"])
                    mapping["id2item"].append(target)
                for item in row["history"].split(" "):
                    if item not in mapping["item2id"]:
                        mapping["item2id"][item] = len(mapping["item2id"])
                        mapping["id2item"].append(item)

    sequences: dict[str, list[str]] = {}
    for row in retained_rows:
        sequence = row["history"].split(" ") + [row["parent_asin"]]
        user = row["user_id"]
        if len(sequence) > len(sequences.get(user, [])):
            sequences[user] = sequence
    return mapping, sequences


def read_metadata(
    path: Path, wanted: set[str], official_dataset_class: type
) -> dict[str, str]:
    cleaner = official_dataset_class.__new__(official_dataset_class)
    metadata: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid metadata JSON at line {line_number}") from exc
            source_item_id = str(value["parent_asin"])
            if source_item_id in wanted:
                metadata[source_item_id] = official_dataset_class._clean_metadata(cleaner, value)[
                    "cleaned_metadata"
                ]
    missing = sorted(wanted - set(metadata))
    if missing:
        raise RuntimeError(f"{len(missing)} catalog items lack metadata; first={missing[:5]}")
    return metadata


def dump_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle)


def build(args: argparse.Namespace) -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "-C", str(args.upstream_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if revision != PINNED_LATTE_REVISION:
        raise RuntimeError(f"expected Latte revision {PINNED_LATTE_REVISION}, got {revision}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    official_dataset_class, official_tokenizer_class = load_official_classes(args.upstream_root)

    csv_paths = [args.train_csv, args.valid_csv, args.test_csv]
    mapping, sequences = read_histories(csv_paths)
    metadata = read_metadata(args.metadata_jsonl, set(mapping["item2id"]) - {"[PAD]"}, official_dataset_class)
    id_mapping_path = args.output_dir / "id_mapping.json"
    sequences_path = args.output_dir / "all_item_seqs.json"
    metadata_path = args.output_dir / "metadata.sentence.json"
    dump_json(id_mapping_path, mapping)
    dump_json(sequences_path, sequences)
    dump_json(metadata_path, metadata)

    sent_emb_path = args.output_dir / "sentence-t5-base.sent_emb"
    if args.reuse_sent_emb:
        if not sent_emb_path.is_file():
            raise FileNotFoundError(f"cannot reuse missing embeddings: {sent_emb_path}")
        sent_embs = np.fromfile(sent_emb_path, dtype=np.float32).reshape(-1, args.sent_emb_dim)
        if sent_embs.shape[0] != len(mapping["id2item"]) - 1:
            raise RuntimeError("reused embeddings do not match the rebuilt item mapping")
    else:
        ordered_sentences = [metadata[source_item_id] for source_item_id in mapping["id2item"][1:]]
        model = SentenceTransformer(
            args.sent_emb_model,
            revision=args.sent_emb_revision,
            cache_folder=str(args.model_cache_dir),
        ).to("cpu")
        torch.set_num_threads(args.torch_num_threads)
        sent_embs = model.encode(
            ordered_sentences,
            convert_to_numpy=True,
            batch_size=args.sent_emb_batch_size,
            show_progress_bar=True,
            device="cpu",
        )
        sent_embs.tofile(sent_emb_path)
    reduced = PCA(n_components=args.sent_emb_pca, whiten=True).fit_transform(sent_embs)

    # Import Faiss only after Torch encoding. Loading both OpenMP runtimes before
    # encoding can crash on macOS even though each dependency works in isolation.
    import faiss

    train_items = {item for sequence in sequences.values() for item in sequence[:-2]}
    train_mask = np.array(
        [source_item_id in train_items for source_item_id in mapping["id2item"][1:]], dtype=bool
    )
    tokenizer = official_tokenizer_class.__new__(official_tokenizer_class)
    tokenizer.config = {
        "vq_n_codebooks": args.vq_n_codebooks,
        "vq_codebook_size": args.vq_codebook_size,
        "faiss_omp_num_threads": args.faiss_omp_num_threads,
    }
    tokenizer.n_latent_tokens = args.n_latent_tokens
    tokenizer.id2item = mapping["id2item"]
    tokenizer.log = print
    sem_ids_path = args.output_dir / (
        f"sentence-t5-base_rqkmeans_{args.vq_n_codebooks}x{args.vq_codebook_size}_psid.sem_ids"
    )
    official_tokenizer_class._generate_semantic_id_rqkmeans(
        tokenizer, reduced, str(sem_ids_path), train_mask
    )

    output_paths = [id_mapping_path, sequences_path, metadata_path, sent_emb_path, sem_ids_path]
    source_paths = {
        "amazon_train_csv": args.train_csv,
        "amazon_valid_csv": args.valid_csv,
        "amazon_test_csv": args.test_csv,
        "amazon_metadata_jsonl": args.metadata_jsonl,
        "official_dataset_source": args.upstream_root
        / "genrec/datasets/AmazonReviews2023/dataset.py",
        "official_latte_tokenizer_source": args.upstream_root / "genrec/models/Latte/tokenizer.py",
    }
    return {
        "schema": "sidscope.latte_psid_cache_build.v1",
        "status": "pass",
        "source_revision": revision,
        "dataset_revision": args.dataset_revision,
        "sentence_transformer_revision": args.sent_emb_revision,
        "configuration": {
            "category": "Musical_Instruments",
            "kcore": "5core",
            "split": "last_out",
            "metadata": "sentence",
            "sent_emb_model": args.sent_emb_model,
            "sent_emb_dim": int(sent_embs.shape[1]),
            "sent_emb_batch_size": args.sent_emb_batch_size,
            "sent_emb_pca": args.sent_emb_pca,
            "vq_method": "rqkmeans",
            "vq_n_codebooks": args.vq_n_codebooks,
            "vq_codebook_size": args.vq_codebook_size,
            "faiss_omp_num_threads": args.faiss_omp_num_threads,
            "torch_num_threads": args.torch_num_threads,
            "sent_emb_reused": args.reuse_sent_emb,
            "rand_seed": args.rand_seed,
        },
        "counts": {
            "users": len(mapping["user2id"]) - 1,
            "items": len(mapping["item2id"]) - 1,
            "interactions": sum(len(sequence) for sequence in sequences.values()),
            "training_items": int(train_mask.sum()),
            "metadata_items": len(metadata),
        },
        "runtime": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "torch": torch.__version__,
            "sentence_transformers": sentence_transformers.__version__,
            "sklearn": sklearn.__version__,
            "faiss": getattr(faiss, "__version__", "1.12.0"),
            "platform": sys.platform,
        },
        "input_sha256": {name: sha256(path) for name, path in source_paths.items()},
        "output_sha256": {path.name: sha256(path) for path in output_paths},
        "output_bytes": {path.name: path.stat().st_size for path in output_paths},
        "redistribution": "raw data, metadata text, embeddings, and generated cache remain external pending dataset-license clarification",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--train-csv", type=Path, required=True)
    parser.add_argument("--valid-csv", type=Path, required=True)
    parser.add_argument("--test-csv", type=Path, required=True)
    parser.add_argument("--metadata-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-cache-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dataset-revision", required=True)
    parser.add_argument("--sent-emb-model", default="sentence-transformers/sentence-t5-base")
    parser.add_argument("--sent-emb-revision", required=True)
    parser.add_argument("--sent-emb-batch-size", type=int, default=128)
    parser.add_argument("--sent-emb-dim", type=int, default=768)
    parser.add_argument("--sent-emb-pca", type=int, default=192)
    parser.add_argument("--vq-n-codebooks", type=int, default=3)
    parser.add_argument("--vq-codebook-size", type=int, default=256)
    parser.add_argument("--n-latent-tokens", type=int, default=8)
    parser.add_argument("--faiss-omp-num-threads", type=int, default=1)
    parser.add_argument("--torch-num-threads", type=int, default=4)
    parser.add_argument("--rand-seed", type=int, default=2024)
    parser.add_argument("--reuse-sent-emb", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.rand_seed)
    np.random.seed(args.rand_seed)
    torch.manual_seed(args.rand_seed)
    result = build(args)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
