#!/usr/bin/env python3
"""Run a bounded CPU smoke against a pinned external RPG source checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PINNED_REVISION = "7dcf95ce9e08601810efdd1c850ed6dada5f97c2"
PINNED_MODEL_SHA256 = "8d70fa9fde44279b3d0da9409e8e877b46ca4388d79442a2659d615336de6abc"
SEED = 2024


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_smoke(source: Path) -> dict[str, Any]:
    source = source.resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != PINNED_REVISION:
        raise RuntimeError(f"RPG checkout must be pinned at {PINNED_REVISION}, observed {revision}")
    model_path = source / "genrec/models/RPG/model.py"
    model_sha256 = _sha256(model_path)
    if model_sha256 != PINNED_MODEL_SHA256:
        raise RuntimeError("pinned RPG model.py hash mismatch")

    sys.path.insert(0, str(source))
    import torch
    import transformers
    from genrec.models.RPG.model import RPG

    class FixtureDataset:
        item2id = {"fixture-a": 1, "fixture-b": 2, "fixture-c": 3, "fixture-d": 4}
        n_items = 5

    class FixtureTokenizer:
        n_digit = 3
        codebook_size = 4
        item2tokens = {
            "fixture-a": (1, 5, 9),
            "fixture-b": (1, 6, 9),
            "fixture-c": (4, 8, 12),
            "fixture-d": (1, 5, 9),
        }
        vocab_size = 14
        max_token_seq_len = 4
        ignored_label = -100
        eos_token = 13

        @staticmethod
        def log(message: str) -> None:
            del message

    config = {
        "device": "cpu",
        "n_embd": 12,
        "n_layer": 1,
        "n_head": 3,
        "n_inner": 24,
        "activation_function": "gelu_new",
        "resid_pdrop": 0.0,
        "embd_pdrop": 0.0,
        "attn_pdrop": 0.0,
        "layer_norm_epsilon": 1e-12,
        "initializer_range": 0.02,
        "temperature": 0.07,
        "chunk_size": 4,
        "num_beams": 2,
        "n_edges": 2,
        "propagation_steps": 2,
        "codebook_size": 4,
    }
    torch.manual_seed(SEED)
    model = RPG(config, FixtureDataset(), FixtureTokenizer()).eval()
    batch = {
        "input_ids": torch.tensor([[1, 2, 0, 0]]),
        "attention_mask": torch.tensor([[1, 1, 0, 0]]),
        "seq_lens": torch.tensor([2]),
    }
    with torch.no_grad():
        exhaustive = model.generate(batch, n_return_sequences=2).squeeze(-1).tolist()
        model.generate_w_decoding_graph = True
        graph_items, visited = model.generate(batch, n_return_sequences=2)
    graph_items = graph_items.squeeze(-1).tolist()
    adjacency = model.adjacency.tolist()
    if exhaustive != [[2, 1]] or graph_items != [[2, 1]]:
        raise RuntimeError(
            f"unexpected bounded RPG outputs: exhaustive={exhaustive}, graph={graph_items}"
        )
    if not all(item_id in {1, 2, 3, 4} for row in graph_items for item_id in row):
        raise RuntimeError("official RPG graph smoke returned a non-item node")

    return {
        "schema": "sidscope.rpg_official_source_smoke.v1",
        "status": "pass",
        "source_url": "https://github.com/facebookresearch/RPG_KDD2025",
        "source_revision": revision,
        "source_model_sha256": model_sha256,
        "runtime": {
            "device": "cpu",
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "transformers": transformers.__version__,
        },
        "seed": SEED,
        "configuration": config,
        "fixture": {
            "items": 4,
            "n_codebooks": 3,
            "codebook_size": 4,
            "duplicate_token_set_item_nodes": [1, 4],
        },
        "outputs": {
            "exhaustive_ranked_item_ids": exhaustive,
            "graph_ranked_item_ids": graph_items,
            "visited_item_counts": visited.tolist(),
            "adjacency_item_nodes": adjacency,
        },
        "boundary": "Official source class with deterministic random weights and dummy data; not a trained checkpoint or recommendation result.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpg-source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_smoke(args.rpg_source)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
