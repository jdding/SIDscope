#!/usr/bin/env python3
"""Run RPG's pinned OPQ method from a frozen sentence-embedding file.

The official tokenizer imports Torch/SentenceTransformers at module import.
This runner supplies inert base-class stubs because embedding is already done,
then invokes the exact pinned ``_generate_semantic_id_opq`` implementation.
That isolation avoids the multiple-OpenMP deadlock observed on macOS.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np
from sklearn.decomposition import PCA


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--sent-emb-filename", default="sentence-t5-base.sent_emb")
    parser.add_argument("--output-filename", default="sentence-t5-base_OPQ32,IVF1,PQ32x8.sem_ids")
    parser.add_argument("--sent-emb-dim", type=int, default=768)
    parser.add_argument("--sent-emb-pca", type=int, default=128)
    parser.add_argument("--n-codebook", type=int, default=32)
    parser.add_argument("--codebook-size", type=int, default=256)
    parser.add_argument("--faiss-omp-num-threads", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.codebook_size <= 0 or args.codebook_size & (args.codebook_size - 1):
        raise RuntimeError("--codebook-size must be a positive power of two")
    embeddings = np.fromfile(
        args.processed_dir / args.sent_emb_filename, dtype=np.float32
    ).reshape(-1, args.sent_emb_dim)
    reduced = PCA(n_components=args.sent_emb_pca, whiten=True).fit_transform(embeddings)
    del embeddings

    genrec = types.ModuleType("genrec")
    genrec.__path__ = []
    dataset_module = types.ModuleType("genrec.dataset")
    dataset_module.AbstractDataset = object
    tokenizer_module = types.ModuleType("genrec.tokenizer")
    tokenizer_module.AbstractTokenizer = object
    sentence_transformers_stub = types.ModuleType("sentence_transformers")
    sentence_transformers_stub.SentenceTransformer = object
    sys.modules.update(
        {
            "genrec": genrec,
            "genrec.dataset": dataset_module,
            "genrec.tokenizer": tokenizer_module,
            "sentence_transformers": sentence_transformers_stub,
        }
    )
    source = args.upstream_root / "genrec/models/RPG/tokenizer.py"
    spec = importlib.util.spec_from_file_location("sidscope_pinned_rpg_tokenizer", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load pinned tokenizer source: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    mapping = json.loads((args.processed_dir / "id_mapping.json").read_text(encoding="utf-8"))
    sequences = json.loads(
        (args.processed_dir / "all_item_seqs.json").read_text(encoding="utf-8")
    )
    training_items = {item for sequence in sequences.values() for item in sequence[:-2]}
    train_mask = np.array(
        [item in training_items for item in mapping["id2item"][1:]], dtype=bool
    )
    tokenizer = module.RPGTokenizer.__new__(module.RPGTokenizer)
    tokenizer.config = {
        "n_codebook": args.n_codebook,
        "codebook_size": args.codebook_size,
        "opq_use_gpu": False,
        "opq_gpu_id": 0,
        "faiss_omp_num_threads": args.faiss_omp_num_threads,
    }
    tokenizer.n_codebook_bits = args.codebook_size.bit_length() - 1
    tokenizer.index_factory = (
        f"OPQ{args.n_codebook},IVF1,"
        f"PQ{args.n_codebook}x{tokenizer.n_codebook_bits}"
    )
    tokenizer.id2item = mapping["id2item"]
    tokenizer.log = print
    output = args.processed_dir / args.output_filename
    module.RPGTokenizer._generate_semantic_id_opq(
        tokenizer, reduced, str(output), train_mask
    )
    print(
        json.dumps(
            {
                "items": len(mapping["id2item"]) - 1,
                "training_items": int(train_mask.sum()),
                "reduced_shape": list(reduced.shape),
                "output": output.name,
                "official_method": "RPGTokenizer._generate_semantic_id_opq",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
