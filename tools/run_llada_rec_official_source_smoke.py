#!/usr/bin/env python3
"""Run bounded method-level checks against a pinned LLaDA-Rec checkout.

The smoke dynamically loads the external official class with dependency stubs,
then exercises confidence-based position selection, all-mask beam
initialization, and position-valid beam expansion. It does not instantiate a
model, load weights, train, or vendor any upstream source.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types
from typing import Any


PINNED_REVISION = "83dbcd6061da9266adcd8f68b16d1de7cc2612f3"
PINNED_MODEL_SHA256 = "280b0332e1bef6ee3ae40011a9e481102f158a55e02118a492e8f1087f681133"
PINNED_TOKENIZER_SHA256 = "ff887fa391b6063c8bf4e777d295fdb8826d443dbb1aa7446d295b2d37c6e6e8"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_official_class(model_path: Path):
    import torch

    genrec = types.ModuleType("genrec")
    genrec.__path__ = []
    dataset_module = types.ModuleType("genrec.dataset")
    dataset_module.AbstractDataset = object
    model_module = types.ModuleType("genrec.model")
    model_module.AbstractModel = torch.nn.Module
    tokenizer_module = types.ModuleType("genrec.tokenizer")
    tokenizer_module.AbstractTokenizer = object
    utils_module = types.ModuleType("genrec.utils")
    utils_module.log = lambda *args, **kwargs: None
    llada_module = types.ModuleType("LLaDA")
    llada_module.__path__ = []
    llada_module.LLaDAConfig = object
    llada_module.LLaDAModelLM = object
    llada_modeling = types.ModuleType("LLaDA.modeling_llada")
    llada_modeling.CausalLMOutputWithPast = object
    llada_modeling.ModuleType = object
    llada_modeling.init_weights = lambda *args, **kwargs: None
    sys.modules.update(
        {
            "genrec": genrec,
            "genrec.dataset": dataset_module,
            "genrec.model": model_module,
            "genrec.tokenizer": tokenizer_module,
            "genrec.utils": utils_module,
            "LLaDA": llada_module,
            "LLaDA.modeling_llada": llada_modeling,
        }
    )
    spec = importlib.util.spec_from_file_location("sidscope_llada_rec_smoke", model_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {model_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.LLaDARec


def run_smoke(source: Path) -> dict[str, Any]:
    source = source.resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != PINNED_REVISION:
        raise RuntimeError(
            f"LLaDA-Rec checkout must be pinned at {PINNED_REVISION}, observed {revision}"
        )
    model_path = source / "genrec/models/LLaDARec/model.py"
    tokenizer_path = source / "genrec/models/LLaDARec/tokenizer.py"
    if _sha256(model_path) != PINNED_MODEL_SHA256:
        raise RuntimeError("pinned LLaDA-Rec model.py hash mismatch")
    if _sha256(tokenizer_path) != PINNED_TOKENIZER_SHA256:
        raise RuntimeError("pinned LLaDA-Rec tokenizer.py hash mismatch")

    import torch

    official_class = _load_official_class(model_path)
    instance = official_class.__new__(official_class)
    instance.mask_token_id = 18
    instance.config = {"device": "cpu"}
    instance.tokenizer = types.SimpleNamespace(n_digit=4)
    instance.posValidTokens = torch.tensor(
        [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
        dtype=torch.long,
    )

    logits = torch.full((2, 4, 19), -4.0)
    logits[0, 0, 1] = 5.0
    logits[0, 1, 5] = 4.0
    logits[0, 2, 9] = 8.0
    logits[0, 3, 13] = 3.0
    logits[1, 0, 2] = 4.0
    logits[1, 1, 6] = 5.0
    logits[1, 2, 10] = 6.0
    logits[1, 3, 14] = 8.0
    all_mask = torch.full((2, 4), 18, dtype=torch.long)
    first_positions = instance.get_transfer_index(all_mask, logits, 1).tolist()
    partially_filled = all_mask[:1].clone()
    partially_filled[0, 2] = 9
    next_position = instance.get_transfer_index(partially_filled, logits[:1], 1).tolist()
    if first_positions != [[2], [3]] or next_position != [[0]]:
        raise RuntimeError(
            f"unexpected confidence transfer order: first={first_positions}, next={next_position}"
        )

    history = torch.tensor([[1, 6, 9, 15]], dtype=torch.long)
    attention = torch.ones_like(history, dtype=torch.bool)
    prepared_ids, prepared_attention, initial_scores, offsets = (
        instance.prepare_beam_search_inputs(history, attention, 1, 2)
    )
    if prepared_ids[:, -4:].tolist() != [[18, 18, 18, 18], [18, 18, 18, 18]]:
        raise RuntimeError("official beam initialization is not all-mask")

    step_logits = torch.full((2, 8, 19), -20.0)
    step_logits[0, 6, 9] = 5.0
    step_logits[0, 6, 11] = 4.0
    step_logits[1, 6, 9] = 5.0
    step_logits[1, 6, 11] = 4.0
    expanded_ids, expanded_scores = instance.beam_search_step(
        step_logits,
        prepared_ids,
        torch.tensor([6, 6]),
        initial_scores,
        offsets,
        1,
        2,
    )
    expected_targets = [[18, 18, 9, 18], [18, 18, 11, 18]]
    if expanded_ids[:, -4:].tolist() != expected_targets:
        raise RuntimeError("official position-valid beam expansion mismatch")

    return {
        "schema": "sidscope.llada_rec_official_source_smoke.v1",
        "status": "pass",
        "source_url": "https://github.com/TengShi-RUC/LLaDA-Rec",
        "source_revision": revision,
        "source_sha256": {
            "model": _sha256(model_path),
            "tokenizer": _sha256(tokenizer_path),
        },
        "runtime": {
            "device": "cpu",
            "python": sys.version.split()[0],
            "torch": torch.__version__,
        },
        "configuration": {
            "n_digit": 4,
            "codebook_sizes": [4, 4, 4, 4],
            "mask_token_id": 18,
            "beam_size": 2,
        },
        "outputs": {
            "first_confidence_selected_positions": first_positions,
            "filled_position_excluded_next_selection": next_position,
            "initial_target_states": prepared_ids[:, -4:].tolist(),
            "initial_beam_scores": initial_scores.tolist(),
            "expanded_target_states": expanded_ids[:, -4:].tolist(),
            "expanded_beam_scores": expanded_scores.tolist(),
            "attention_shape": list(prepared_attention.shape),
        },
        "inference_semantics": {
            "initial_state": "all_mask",
            "position_order": "adaptive_argmax_softmax_confidence",
            "position_vocabulary": "codebook_disjoint",
            "filled_positions_remasked": False,
        },
        "boundary": "Pinned official class methods with handcrafted logits and no model instantiation, weights, training, dataset, or recommendation result.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llada-rec-source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_smoke(args.llada_rec_source)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
