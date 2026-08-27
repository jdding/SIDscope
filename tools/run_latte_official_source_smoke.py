#!/usr/bin/env python3
"""Run a bounded CPU smoke against pinned official Latte/PSID class methods."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

import torch


PINNED_REVISION = "05e4e6d983225bcb7172f148a076890e80c524d1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _install_import_stubs() -> None:
    genrec_module = types.ModuleType("genrec")
    genrec_module.__path__ = []
    dataset_module = types.ModuleType("genrec.dataset")
    dataset_module.AbstractDataset = object
    tokenizer_module = types.ModuleType("genrec.tokenizer")
    tokenizer_module.AbstractTokenizer = object

    class AbstractModel(torch.nn.Module):
        pass

    model_module = types.ModuleType("genrec.model")
    model_module.AbstractModel = AbstractModel
    layers_module = types.ModuleType("genrec.layers")
    layers_module.RQVAEModel = object
    sentence_module = types.ModuleType("sentence_transformers")
    sentence_module.SentenceTransformer = object
    sys.modules.update(
        {
            "genrec": genrec_module,
            "genrec.dataset": dataset_module,
            "genrec.tokenizer": tokenizer_module,
            "genrec.model": model_module,
            "genrec.layers": layers_module,
            "sentence_transformers": sentence_module,
        }
    )


def run(upstream_root: Path) -> dict[str, object]:
    revision = subprocess.run(
        ["git", "-C", str(upstream_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if revision != PINNED_REVISION:
        raise RuntimeError(f"expected Latte revision {PINNED_REVISION}, got {revision}")

    psid_path = upstream_root / "genrec/models/PSID/tokenizer.py"
    latte_tokenizer_path = upstream_root / "genrec/models/Latte/tokenizer.py"
    latte_model_path = upstream_root / "genrec/models/Latte/model.py"
    _install_import_stubs()
    psid_module = _load_module("sidscope_smoke_psid_tokenizer", psid_path)
    latte_tokenizer_module = _load_module("sidscope_smoke_latte_tokenizer", latte_tokenizer_path)
    latte_model_module = _load_module("sidscope_smoke_latte_model", latte_model_path)

    config = {"vq_n_codebooks": 3, "vq_codebook_size": 4}
    raw_cache = {
        "fixture-asin-a": [0, 1, 2],
        "fixture-asin-b": [1, 1, 2],
        "fixture-asin-c": [2, 0, 3],
    }
    psid = psid_module.PSIDTokenizer.__new__(psid_module.PSIDTokenizer)
    psid.config = config
    psid_tokens = psid._sem_ids_to_tokens({key: list(value) for key, value in raw_cache.items()})

    latte_tokenizer = latte_tokenizer_module.LatteTokenizer.__new__(
        latte_tokenizer_module.LatteTokenizer
    )
    latte_tokenizer.config = config
    latte_tokenizer.n_latent_tokens = 3
    latte_tokens = latte_tokenizer._sem_ids_to_tokens_with_offset(raw_cache)
    latte_tokenizer.item2tokens = latte_tokens
    latte_tokenizer.tokens_to_item = latte_tokenizer._build_tokens_to_items()
    latte_tokenizer.base_latent_token = 1

    latte_model = latte_model_module.Latte.__new__(latte_model_module.Latte)
    torch.nn.Module.__init__(latte_model)
    latte_model.tokenizer = latte_tokenizer
    predicted = torch.tensor(
        [[[1, 4, 9, 14], [2, 4, 9, 14], [3, 5, 9, 14], [4, 6, 8, 15], [2, 4, 8, 12]]],
        dtype=torch.long,
    )
    scores = torch.tensor([[-0.2, -1.2, -0.1, -0.05, -0.4]], dtype=torch.float64)
    latte_model.aggregation_method = "agg_sum"
    aggregate_sum = latte_model._aggregate_predictions(predicted, scores, 2)
    latte_model.aggregation_method = "agg_max"
    aggregate_max = latte_model._aggregate_predictions(predicted, scores, 2)

    return {
        "schema": "sidscope.latte_psid_official_source_smoke.v1",
        "status": "pass",
        "source_revision": revision,
        "runtime": "cpu_official_class_methods_no_checkpoint_no_training",
        "source_sha256": {
            "psid_tokenizer": _sha256(psid_path),
            "latte_tokenizer": _sha256(latte_tokenizer_path),
            "latte_model": _sha256(latte_model_path),
        },
        "configuration": {
            "vq_n_codebooks": 3,
            "vq_codebook_size": 4,
            "n_latent_tokens": 3,
        },
        "outputs": {
            "psid_item_tokens": {key: list(value) for key, value in sorted(psid_tokens.items())},
            "latte_item_tokens": {key: list(value) for key, value in sorted(latte_tokens.items())},
            "latte_agg_sum_ranked_tokens": aggregate_sum.tolist(),
            "latte_agg_max_ranked_tokens": aggregate_max.tolist(),
        },
        "boundary": {
            "cache": "deidentified in-memory schema fixture; not official-code-derived Amazon cache",
            "checkpoint": "none",
            "training": "none",
            "model_smoke": "official aggregation method only; T5 weights were not instantiated",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run(args.upstream_root.resolve())
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
