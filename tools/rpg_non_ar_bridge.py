#!/usr/bin/env python3
"""Dataset-neutral contracts and runtime adapter for trained RPG traces.

The contract deliberately contains only normalized item rows and pseudonymous
episode keys.  Source item/user identities, dormant labels, and evaluator-side
strata are not accepted generation inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
from typing import Any, Optional


PREPARED_SCHEMA = "sidscope.rpg_prepared_dataset.v1"
SELECTION_SCHEMA = "sidscope.rpg_episode_selection.v1"
TRACE_SCHEMA_V2 = "sidscope.rpg_trained_trace_bundle.v2"
HANDOFF_SCHEMA = "sidscope.rpg_downstream_handoff.v1"
SOURCE_REVISION = "7dcf95ce9e08601810efdd1c850ed6dada5f97c2"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class BridgeFailure(ValueError):
    """Typed fail-closed contract violation."""


def fail(label: str, detail: str) -> None:
    raise BridgeFailure(f"{label}: {detail}")


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash(value: Any, location: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        fail("invalid_hash", location)
    return value


def _positive_int(value: Any, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        fail("invalid_positive_integer", location)
    return value


def _relative_artifact(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("missing_artifact", location)
    path = value.get("path")
    if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
        fail("unsafe_artifact_path", location)
    _hash(value.get("sha256"), f"{location}.sha256")
    return value


def validate_prepared_dataset(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") != PREPARED_SCHEMA:
        fail("invalid_prepared_schema", str(value.get("schema")))
    contract_id = value.get("contract_id")
    if not isinstance(contract_id, str) or not contract_id:
        fail("invalid_contract_id", str(contract_id))
    dataset = value.get("dataset")
    if not isinstance(dataset, dict) or any(
        not isinstance(dataset.get(key), str) or not dataset[key]
        for key in ("name", "category", "profile")
    ):
        fail("invalid_dataset_identity", str(dataset))
    source = value.get("source")
    if not isinstance(source, dict) or source.get("revision") != SOURCE_REVISION:
        fail("source_revision_mismatch", str(source))
    if source.get("license") != "CC-BY-NC-4.0":
        fail("source_license_mismatch", str(source.get("license")))

    config = value.get("configuration")
    if not isinstance(config, dict):
        fail("missing_configuration", "configuration")
    for key in ("n_codebooks", "codebook_size", "num_beams", "n_edges", "propagation_steps"):
        _positive_int(config.get(key), f"configuration.{key}")
    if config["codebook_size"] & (config["codebook_size"] - 1):
        fail("codebook_size_not_power_of_two", str(config["codebook_size"]))
    rank_cutoff = _positive_int(config.get("rank_cutoff"), "configuration.rank_cutoff")
    if rank_cutoff > config["num_beams"]:
        fail("rank_cutoff_exceeds_beams", str(rank_cutoff))
    temperature = config.get("temperature")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or temperature <= 0:
        fail("invalid_temperature", str(temperature))
    seed = config.get("model_seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        fail("invalid_model_seed", str(seed))
    if value.get("configuration_sha256") != canonical_hash(config):
        fail("configuration_hash_mismatch", "configuration")

    splits = value.get("splits")
    if not isinstance(splits, dict):
        fail("missing_splits", "splits")
    split_ids: set[str] = set()
    for split_name in ("train", "validation", "test"):
        row = splits.get(split_name)
        if not isinstance(row, dict):
            fail("missing_split", split_name)
        split_id = row.get("split_id")
        if not isinstance(split_id, str) or not split_id or split_id in split_ids:
            fail("invalid_or_duplicate_split_id", f"{split_name}:{split_id}")
        split_ids.add(split_id)
        _positive_int(row.get("row_count"), f"splits.{split_name}.row_count")
        _relative_artifact(row, f"splits.{split_name}")

    catalog = value.get("catalog")
    if not isinstance(catalog, dict):
        fail("missing_catalog", "catalog")
    _positive_int(catalog.get("row_count"), "catalog.row_count")
    if config["num_beams"] > catalog["row_count"] or config["n_edges"] > catalog["row_count"]:
        fail("graph_width_exceeds_catalog", str(catalog["row_count"]))
    parallel_topk = _positive_int(config.get("parallel_topk"), "configuration.parallel_topk")
    if parallel_topk > config["codebook_size"]:
        fail("parallel_topk_exceeds_codebook", str(parallel_topk))
    _hash(catalog.get("target_universe_sha256"), "catalog.target_universe_sha256")

    artifacts = value.get("artifacts")
    if not isinstance(artifacts, dict):
        fail("missing_artifacts", "artifacts")
    for name in ("item_mapping", "interaction_sequences", "semantic_id_cache"):
        _relative_artifact(artifacts.get(name), f"artifacts.{name}")

    training = value.get("training")
    if not isinstance(training, dict) or training.get("model_seed") != seed:
        fail("training_seed_mismatch", str(training))
    training_status = training.get("status", "complete")
    if training_status == "complete":
        _hash(training.get("checkpoint_sha256"), "training.checkpoint_sha256")
        _hash(training.get("training_manifest_sha256"), "training.training_manifest_sha256")
    elif training_status == "pending":
        if training.get("checkpoint_sha256") is not None or training.get("training_manifest_sha256") is not None:
            fail("pending_training_has_output_hash", str(training))
    else:
        fail("invalid_training_status", str(training_status))
    return {
        "schema": PREPARED_SCHEMA,
        "status": "pass",
        "contract_id": contract_id,
        "contract_sha256": canonical_hash(value),
        "catalog_rows": catalog["row_count"],
        "test_split_id": splits["test"]["split_id"],
    }


def validate_episode_selection(
    value: dict[str, Any], prepared: dict[str, Any]
) -> dict[str, Any]:
    validate_prepared_dataset(prepared)
    if value.get("schema") != SELECTION_SCHEMA:
        fail("invalid_selection_schema", str(value.get("schema")))
    if value.get("prepared_dataset_contract_sha256") != canonical_hash(prepared):
        fail("prepared_contract_binding_mismatch", "episode selection")
    test = prepared["splits"]["test"]
    if value.get("test_split_id") != test["split_id"] or value.get("test_split_sha256") != test["sha256"]:
        fail("selection_split_binding_mismatch", str(value.get("test_split_id")))
    policies = value.get("policies")
    expected_policies = {
        "missing_row": "reject",
        "duplicate_row": "reject",
        "out_of_split": "reject",
        "target_mismatch": "reject",
        "catalog_unreachable": "reject",
    }
    if policies != expected_policies:
        fail("selection_policy_mismatch", str(policies))
    rows = value.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > 256:
        fail("invalid_selection_count", str(len(rows) if isinstance(rows, list) else None))
    seen_ids: set[str] = set()
    seen_indices: set[int] = set()
    catalog_rows = prepared["catalog"]["row_count"]
    for order, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("order") != order:
            fail("selection_order_mismatch", str(order))
        episode_id = row.get("episode_id")
        if not isinstance(episode_id, str) or not episode_id or episode_id in seen_ids:
            fail("duplicate_or_invalid_episode_id", str(episode_id))
        seen_ids.add(episode_id)
        split_index = row.get("split_row_index")
        if (
            not isinstance(split_index, int)
            or isinstance(split_index, bool)
            or split_index < 0
            or split_index >= test["row_count"]
        ):
            fail("selection_out_of_split", f"{episode_id}:{split_index}")
        if split_index in seen_indices:
            fail("duplicate_selection_row", str(split_index))
        seen_indices.add(split_index)
        target = row.get("expected_target_normalized_item_id")
        if (
            not isinstance(target, int)
            or isinstance(target, bool)
            or not 0 <= target < catalog_rows
        ):
            fail("selection_catalog_unreachable", f"{episode_id}:{target}")
        forbidden = {"dormant_gap_bucket", "gap_bucket", "target_label", "user_id"}.intersection(row)
        if forbidden:
            fail("evaluator_join_leak", f"{episode_id}:{sorted(forbidden)}")
    return {
        "schema": SELECTION_SCHEMA,
        "status": "pass",
        "selection_id": value.get("selection_id"),
        "selection_sha256": canonical_hash(value),
        "episode_count": len(rows),
    }


def verify_artifact_files(prepared: dict[str, Any], root: Path) -> dict[str, Path]:
    """Resolve and hash-check every prepared artifact without following unsafe paths."""
    validate_prepared_dataset(prepared)
    resolved_root = root.resolve()
    entries = dict(prepared["artifacts"])
    entries.update({f"split_{key}": value for key, value in prepared["splits"].items()})
    paths: dict[str, Path] = {}
    for name, entry in entries.items():
        path = (resolved_root / entry["path"]).resolve()
        if resolved_root not in path.parents or not path.is_file():
            fail("missing_or_escaped_artifact", name)
        if sha256_file(path) != entry["sha256"]:
            fail("artifact_hash_mismatch", name)
        paths[name] = path
    return paths


def verify_source_checkout(source: Path) -> str:
    resolved = source.resolve()
    if not (resolved / "genrec/models/RPG/model.py").is_file():
        fail("invalid_rpg_source", str(resolved))
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(resolved), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        fail("unverifiable_rpg_source_revision", type(exc).__name__)
    if revision != SOURCE_REVISION:
        fail("rpg_source_revision_mismatch", revision)
    return revision


def load_prepared_rows(prepared: dict[str, Any], root: Path) -> dict[str, Any]:
    paths = verify_artifact_files(prepared, root)
    mapping = json.loads(paths["item_mapping"].read_text(encoding="utf-8"))
    semantic = json.loads(paths["semantic_id_cache"].read_text(encoding="utf-8"))
    interaction_manifest = json.loads(
        paths["interaction_sequences"].read_text(encoding="utf-8")
    )
    splits = {
        key: json.loads(paths[f"split_{key}"].read_text(encoding="utf-8"))
        for key in ("train", "validation", "test")
    }
    catalog_rows = prepared["catalog"]["row_count"]
    expected_ids = list(range(catalog_rows))
    if not isinstance(mapping, list) or [row.get("normalized_item_id") for row in mapping] != expected_ids:
        fail("item_mapping_not_dense", "normalized_item_id")
    keys = [row.get("prepared_item_key") for row in mapping]
    if any(not isinstance(key, str) or not key for key in keys) or len(set(keys)) != catalog_rows:
        fail("invalid_prepared_item_keys", "item_mapping")
    if not isinstance(semantic, list) or [row.get("normalized_item_id") for row in semantic] != expected_ids:
        fail("semantic_id_cache_not_dense", "normalized_item_id")
    n_codebooks = prepared["configuration"]["n_codebooks"]
    codebook_size = prepared["configuration"]["codebook_size"]
    for row in semantic:
        codes = row.get("semantic_codes")
        if (
            not isinstance(codes, list)
            or len(codes) != n_codebooks
            or any(not isinstance(code, int) or isinstance(code, bool) or not 0 <= code < codebook_size for code in codes)
        ):
            fail("invalid_prepared_semantic_codes", str(row.get("normalized_item_id")))
    target_rows = []
    for row in semantic:
        codes = row["semantic_codes"]
        target_rows.append(
            {
                "normalized_item_id": row["normalized_item_id"],
                "semantic_codes": codes,
                "unordered_model_vocabulary_tokens": [
                    head * codebook_size + code + 1 for head, code in enumerate(codes)
                ],
            }
        )
    if canonical_hash(target_rows) != prepared["catalog"]["target_universe_sha256"]:
        fail("prepared_target_universe_hash_mismatch", "semantic_id_cache")
    expected_interaction_manifest = {
        "schema": "sidscope.rpg_interaction_sequences.v1",
        "representation": "normalized_item_sequences",
        "splits": {
            name: {
                "row_count": prepared["splits"][name]["row_count"],
                "sha256": prepared["splits"][name]["sha256"],
            }
            for name in ("train", "validation", "test")
        },
    }
    if interaction_manifest != expected_interaction_manifest:
        fail("interaction_split_binding_mismatch", "interaction_sequences")
    for split_name, rows in splits.items():
        if not isinstance(rows, list) or len(rows) != prepared["splits"][split_name]["row_count"]:
            fail("split_row_count_mismatch", split_name)
        seen_episode_ids: set[str] = set()
        for row in rows:
            episode_id = row.get("episode_id") if isinstance(row, dict) else None
            sequence = row.get("normalized_item_ids") if isinstance(row, dict) else None
            if not isinstance(episode_id, str) or not episode_id or episode_id in seen_episode_ids:
                fail("invalid_split_episode_id", f"{split_name}:{episode_id}")
            seen_episode_ids.add(episode_id)
            if (
                not isinstance(sequence, list)
                or len(sequence) < 2
                or any(not isinstance(item, int) or isinstance(item, bool) or not 0 <= item < catalog_rows for item in sequence)
            ):
                fail("invalid_split_sequence", f"{split_name}:{episode_id}")
    return {
        "mapping": mapping,
        "semantic": semantic,
        "splits": splits,
        "target_universe": target_rows,
        "paths": paths,
    }


def build_official_runtime(
    *,
    rpg_source: Path,
    prepared: dict[str, Any],
    prepared_root: Path,
    runtime_dir: Path,
    checkpoint: Optional[Path] = None,
) -> Any:
    """Build the official RPG tokenizer/model over a prepared normalized dataset.

    This bypasses the upstream ``Pipeline`` constructor because it calls a
    supplied dataset instance as if it were a class.  No upstream source file
    is modified or vendored.
    """
    import sys

    source = rpg_source.resolve()
    verify_source_checkout(source)
    sys.path.insert(0, str(source))
    from accelerate import Accelerator
    from datasets import Dataset
    import torch
    from genrec.dataset import AbstractDataset
    from genrec.models.RPG.model import RPG
    from genrec.models.RPG.tokenizer import RPGTokenizer
    from genrec.utils import get_config, init_device, init_seed

    loaded = load_prepared_rows(prepared, prepared_root)
    config_override = dict(prepared["configuration"])
    config_override.update(
        {
            "dataset": prepared["dataset"]["name"],
            "metadata": "none",
            "sent_emb_model": "prepared-semantic-ids",
            "sent_emb_dim": 0,
            "sent_emb_pca": 0,
            "n_codebook": config_override.pop("n_codebooks"),
            "rand_seed": config_override.pop("model_seed"),
            "cache_dir": str(runtime_dir / "cache") + "/",
            "log_dir": str(runtime_dir / "logs") + "/",
            "tensorboard_log_dir": str(runtime_dir / "tensorboard") + "/",
            "ckpt_dir": str(runtime_dir / "checkpoint") + "/",
            "run_id": prepared["contract_id"],
            "reproducibility": True,
        }
    )
    # These verifier/export fields are not upstream RPG model configuration.
    config_override.pop("rank_cutoff", None)
    config_override.pop("parallel_topk", None)
    config = get_config("RPG", object(), None, config_override)
    config["device"], config["use_ddp"] = init_device()
    accelerator = Accelerator(log_with="tensorboard", project_dir=config["tensorboard_log_dir"])
    config["accelerator"] = accelerator
    init_seed(config["rand_seed"], config["reproducibility"])

    runtime_cache = Path(config["cache_dir"]).resolve()
    processed = runtime_cache / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    mapping = loaded["mapping"]
    semantic = loaded["semantic"]
    key_by_id = {row["normalized_item_id"]: row["prepared_item_key"] for row in mapping}
    sem_by_key = {
        key_by_id[row["normalized_item_id"]]: row["semantic_codes"] for row in semantic
    }
    sem_name = (
        f"prepared-semantic-ids_OPQ{config['n_codebook']},IVF1,"
        f"PQ{config['n_codebook']}x{int(config['codebook_size']).bit_length() - 1}.sem_ids"
    )
    (processed / sem_name).write_text(json.dumps(sem_by_key, sort_keys=True), encoding="utf-8")

    class PreparedDataset(AbstractDataset):
        def __init__(self, runtime_config: dict[str, Any]):
            super().__init__(runtime_config)
            self.cache_dir = str(runtime_cache)
            self.id_mapping = {
                "user2id": {"[PAD]": 0},
                "id2user": ["[PAD]"],
                "item2id": {"[PAD]": 0},
                "id2item": ["[PAD]"],
            }
            for normalized_id in range(prepared["catalog"]["row_count"]):
                key = key_by_id[normalized_id]
                self.id_mapping["item2id"][key] = normalized_id + 1
                self.id_mapping["id2item"].append(key)
            self.all_item_seqs = {}
            split_data = {}
            for split_name, upstream_name in (("train", "train"), ("validation", "val"), ("test", "test")):
                users = []
                sequences = []
                for row in loaded["splits"][split_name]:
                    user_key = f"episode:{row['episode_id']}"
                    users.append(user_key)
                    sequence = [key_by_id[item] for item in row["normalized_item_ids"]]
                    sequences.append(sequence)
                    self.all_item_seqs[user_key] = sequence
                    if user_key not in self.id_mapping["user2id"]:
                        self.id_mapping["user2id"][user_key] = len(self.id_mapping["id2user"])
                        self.id_mapping["id2user"].append(user_key)
                split_data[upstream_name] = Dataset.from_dict({"user": users, "item_seq": sequences})
            self.split_data = split_data
            self.item2meta = None

        def _download_and_process_raw(self) -> None:
            raise RuntimeError("prepared dataset never downloads raw data")

    dataset = PreparedDataset(config)
    tokenizer = RPGTokenizer(config, dataset)
    tokenized = tokenizer.tokenize(dataset.split())
    model = RPG(config, dataset, tokenizer)
    if checkpoint is not None:
        state = torch.load(checkpoint.resolve(), map_location=config["device"], weights_only=False)
        model.load_state_dict(state)
    return SimpleNamespace(
        config=config,
        accelerator=accelerator,
        raw_dataset=dataset,
        tokenizer=tokenizer,
        tokenized_datasets=tokenized,
        model=model,
        prepared_rows=loaded,
    )


def build_downstream_handoff(
    bundle: dict[str, Any], prepared: dict[str, Any], selection: dict[str, Any]
) -> dict[str, Any]:
    """Return an evaluator-neutral per-episode table from a verified v2 bundle."""
    rows_by_id = {
        row["normalized_item_id"]: row for row in bundle["target_universe"]["rows"]
    }
    ranking_diagnostic = bundle.get("ranking_diagnostic")
    output_rows = []
    for episode, selected in zip(bundle["episodes"], selection["rows"]):
        target = episode["target_normalized_item_id"]
        target_row = rows_by_id.get(target)
        ranked = episode["ranked_items"]
        ranked_target_sets = [row for row in ranked if target_row and row["semantic_codes"] == target_row["semantic_codes"]]
        initial = episode["initial_item_nodes"]
        candidates = [candidate["normalized_item_id"] for step in episode["propagation"] for candidate in step["candidates"]]
        reached = target in set(initial).union(candidates)
        target_generated = bool(ranked_target_sets)
        target_rank = episode["target_rank"]
        candidate_count = len(candidates)
        unique_candidates = len(set(candidates))
        output_row = {
                "episode_id": episode["episode_id"],
                "selection_order": selected["order"],
                "catalog_reachable": 0 <= target < prepared["catalog"]["row_count"],
                "target_generated": target_generated,
                "target_reached": reached,
                "resolution_loss": bool(target_generated and target_rank is None),
                "target_rank": target_rank,
                "hit_at_10": target_rank is not None and target_rank <= 10,
                "ndcg_at_10": 0.0 if target_rank is None or target_rank > 10 else 1.0 / __import__("math").log2(target_rank + 1),
                "valid_candidate_count": candidate_count,
                "unique_candidate_count": unique_candidates,
                "candidate_duplication_count": candidate_count - unique_candidates,
                "visited_item_node_count": episode["visited_item_node_count"],
                "parallel_score_count": bundle["configuration"]["n_codebooks"] * bundle["configuration"]["codebook_size"],
                "graph_candidate_score_count": candidate_count,
            }
        if ranking_diagnostic is not None:
            output_row.update(
                {
                    "evaluation_cutoff": ranking_diagnostic["evaluation_cutoff"],
                    "published_rank_depth": ranking_diagnostic["published_rank_depth"],
                    "target_rank_state": episode["target_rank_state"],
                    "target_rank_lower_bound": episode["target_rank_lower_bound"],
                    "target_rank_right_censored": episode["target_rank_state"]
                    == "target_not_in_published_depth",
                }
            )
        output_rows.append(output_row)
    return {
        "schema": HANDOFF_SCHEMA,
        "bundle_id": bundle.get("bundle_id"),
        "prepared_dataset_contract_sha256": canonical_hash(prepared),
        "episode_selection_manifest_sha256": canonical_hash(selection),
        "episode_count": len(output_rows),
        "evaluator_side_join_fields": ["dormant_gap_bucket", "target_label"],
        "rows": output_rows,
    }
