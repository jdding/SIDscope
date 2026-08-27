#!/usr/bin/env python3
"""Build an RPG Amazon Reviews 2014 OPQ cache with pinned official classes.

Run this in an optional environment containing the official RPG dependencies.
Raw data, text, embeddings, and semantic IDs stay outside the SIDScope package;
the JSON report records only hashes, counts, versions, and configuration.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any


PINNED_RPG_REVISION = "7dcf95ce9e08601810efdd1c850ed6dada5f97c2"


class LocalAccelerator:
    """Minimum single-process accelerator surface used by the official dataset."""

    is_main_process = True
    device = "cpu"

    @staticmethod
    def wait_for_everyone() -> None:
        return None

    @staticmethod
    @contextmanager
    def main_process_first():
        yield


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def directory_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    if not files:
        raise RuntimeError(f"model snapshot directory is empty: {path}")
    for candidate in files:
        digest.update(candidate.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with candidate.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--reviews-gz", type=Path, required=True)
    parser.add_argument("--metadata-gz", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--category", default="Beauty")
    parser.add_argument("--sent-emb-model", required=True)
    parser.add_argument("--sent-emb-revision", required=True)
    parser.add_argument("--sent-emb-dim", type=int, default=768)
    parser.add_argument("--sent-emb-pca", type=int, default=128)
    parser.add_argument("--sent-emb-batch-size", type=int, default=64)
    parser.add_argument("--n-codebook", type=int, default=32)
    parser.add_argument("--codebook-size", type=int, default=256)
    parser.add_argument("--faiss-omp-num-threads", type=int, default=4)
    return parser.parse_args()


def build(args: argparse.Namespace) -> dict[str, Any]:
    if args.codebook_size <= 0 or args.codebook_size & (args.codebook_size - 1):
        raise RuntimeError("--codebook-size must be a positive power of two")
    revision = subprocess.run(
        ["git", "-C", str(args.upstream_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if revision != PINNED_RPG_REVISION:
        raise RuntimeError(f"expected RPG revision {PINNED_RPG_REVISION}, got {revision}")
    if not Path(args.sent_emb_model).is_dir():
        raise RuntimeError(
            "--sent-emb-model must be a local pinned snapshot directory; "
            "the official tokenizer API does not accept a revision argument"
        )
    expected_reviews_name = f"reviews_{args.category}_5.json.gz"
    expected_metadata_name = f"meta_{args.category}.json.gz"
    if args.reviews_gz.name != expected_reviews_name or args.metadata_gz.name != expected_metadata_name:
        raise RuntimeError("raw filenames do not match the official AmazonReviews2014 route")

    raw_dir = args.cache_root / "AmazonReviews2014" / args.category / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for source in (args.reviews_gz, args.metadata_gz):
        destination = raw_dir / source.name
        if not destination.exists():
            shutil.copy2(source, destination)
        if sha256(destination) != sha256(source):
            raise RuntimeError(f"copied raw input hash mismatch for {source.name}")

    sys.path.insert(0, str(args.upstream_root))
    from genrec.datasets.AmazonReviews2014.dataset import AmazonReviews2014
    from sentence_transformers import SentenceTransformer

    config = {
        "accelerator": LocalAccelerator(),
        "cache_dir": str(args.cache_root),
        "category": args.category,
        "metadata": "sentence",
        "split": "leave_one_out",
        "sent_emb_model": args.sent_emb_model,
        "sent_emb_dim": args.sent_emb_dim,
        "sent_emb_pca": args.sent_emb_pca,
        "sent_emb_batch_size": args.sent_emb_batch_size,
        "device": "cpu",
        "n_codebook": args.n_codebook,
        "codebook_size": args.codebook_size,
        "opq_use_gpu": False,
        "opq_gpu_id": 0,
        "faiss_omp_num_threads": args.faiss_omp_num_threads,
        "max_item_seq_len": 50,
    }
    dataset = AmazonReviews2014(config)
    dataset.split()
    processed = args.cache_root / "AmazonReviews2014" / args.category / "processed"
    sent_emb_path = processed / f"{Path(args.sent_emb_model).name}.sent_emb"
    sent_emb_reused = sent_emb_path.is_file()
    if not sent_emb_reused:
        sentences = [dataset.item2meta[item] for item in dataset.id_mapping["id2item"][1:]]
        model = SentenceTransformer(args.sent_emb_model).to("cpu")
        embeddings = model.encode(
            sentences,
            convert_to_numpy=True,
            batch_size=args.sent_emb_batch_size,
            show_progress_bar=True,
            device="cpu",
        )
        embeddings.tofile(sent_emb_path)
    sem_name = (
        f"{Path(args.sent_emb_model).name}_"
        f"OPQ{args.n_codebook},IVF1,PQ{args.n_codebook}x{args.codebook_size.bit_length() - 1}.sem_ids"
    )
    sem_ids_path = processed / sem_name
    sem_ids_reused = sem_ids_path.is_file()
    if not sem_ids_reused:
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("generate_rpg_opq_from_embeddings.py")),
                "--upstream-root",
                str(args.upstream_root),
                "--processed-dir",
                str(processed),
                "--sent-emb-filename",
                sent_emb_path.name,
                "--output-filename",
                sem_name,
                "--sent-emb-dim",
                str(args.sent_emb_dim),
                "--sent-emb-pca",
                str(args.sent_emb_pca),
                "--n-codebook",
                str(args.n_codebook),
                "--codebook-size",
                str(args.codebook_size),
                "--faiss-omp-num-threads",
                str(args.faiss_omp_num_threads),
            ],
            check=True,
        )
    outputs = [
        processed / "id_mapping.json",
        processed / "all_item_seqs.json",
        processed / "metadata.sentence.json",
        sent_emb_path,
        sem_ids_path,
    ]
    for path in outputs:
        if not path.is_file():
            raise RuntimeError(f"official cache output is missing: {path.name}")
    import faiss
    import numpy
    import sentence_transformers
    import sklearn

    return {
        "schema": "sidscope.rpg_opq_cache_build.v1",
        "status": "pass",
        "source_revision": revision,
        "sentence_transformer_revision": args.sent_emb_revision,
        "configuration": {
            "category": args.category,
            "dataset": "AmazonReviews2014",
            "split": "leave_one_out",
            "metadata": "sentence",
            "sent_emb_model": "sentence-transformers/sentence-t5-base",
            "sent_emb_dim": args.sent_emb_dim,
            "sent_emb_pca": args.sent_emb_pca,
            "sent_emb_batch_size": args.sent_emb_batch_size,
            "n_codebook": args.n_codebook,
            "codebook_size": args.codebook_size,
            "index_factory": f"OPQ{args.n_codebook},IVF1,PQ{args.n_codebook}x{args.codebook_size.bit_length() - 1}",
            "device": "cpu",
            "faiss_omp_num_threads": args.faiss_omp_num_threads,
            "sent_emb_reused": sent_emb_reused,
            "semantic_ids_reused": sem_ids_reused,
        },
        "counts": {
            "users": dataset.n_users - 1,
            "items": dataset.n_items - 1,
            "interactions": dataset.n_interactions,
            "training_items": len(
                {
                    item
                    for sequence in dataset.split_data["train"]["item_seq"]
                    for item in sequence
                }
            ),
            "metadata_items": len(dataset.item2meta),
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": numpy.__version__,
            "sentence_transformers": sentence_transformers.__version__,
            "sklearn": sklearn.__version__,
            "faiss": getattr(faiss, "__version__", "unknown"),
            "platform": sys.platform,
        },
        "input_sha256": {
            expected_reviews_name: sha256(args.reviews_gz),
            expected_metadata_name: sha256(args.metadata_gz),
            "official_dataset_source": sha256(
                args.upstream_root / "genrec/datasets/AmazonReviews2014/dataset.py"
            ),
            "official_rpg_tokenizer_source": sha256(
                args.upstream_root / "genrec/models/RPG/tokenizer.py"
            ),
            "sentence_transformer_snapshot": directory_sha256(Path(args.sent_emb_model)),
        },
        "output_sha256": {path.name: sha256(path) for path in outputs},
        "output_bytes": {path.name: path.stat().st_size for path in outputs},
        "redistribution": "raw data, metadata text, embeddings, and generated semantic IDs remain external; publish summary only",
    }


def main() -> None:
    args = parse_args()
    result = build(args)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
