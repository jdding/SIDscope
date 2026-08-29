#!/usr/bin/env python3
"""Fail-closed verifier for real LLaDA-Rec prepared/selection/trace bundles."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

try:
    from tools.export_llada_rec_trained_trace import BUCKETS, canonical_hash
    from tools.run_diffgrm_resumable_training import sha256_file
    from tools.run_llada_rec_resumable_training import SOURCE_REVISION
except ModuleNotFoundError:
    from export_llada_rec_trained_trace import BUCKETS, canonical_hash
    from run_diffgrm_resumable_training import sha256_file
    from run_llada_rec_resumable_training import SOURCE_REVISION


class VerificationFailure(ValueError):
    def __init__(self, label: str, message: str):
        super().__init__(message)
        self.label = label


def fail(label: str, message: str) -> None:
    raise VerificationFailure(label, message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail("invalid_json_root", f"{path} must contain an object")
    return value


def _walk(value: Any) -> list[tuple[str, Any]]:
    result: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            result.append((str(key), child))
            result.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_walk(child))
    return result


def verify(
    *, prepared_path: Path, selection_path: Path, bundle_path: Path,
    training_manifest_path: Path, expected_failure_mutation: str | None = None,
) -> dict[str, Any]:
    prepared = load(prepared_path)
    selection = load(selection_path)
    bundle = load(bundle_path)
    if expected_failure_mutation is not None:
        bundle = copy.deepcopy(bundle)
        if expected_failure_mutation == "unknown_parent_beam":
            bundle["episodes"][0]["steps"][1]["transitions"][0][
                "parent_beam_id"
            ] = "missing-parent"
        elif expected_failure_mutation == "prepared_binding_mismatch":
            bundle["prepared_dataset_contract_sha256"] = "0" * 64
        else:
            fail("unknown_expected_failure_mutation", expected_failure_mutation)
    training = load(training_manifest_path)
    if prepared.get("schema") != "sidscope.llada_rec_prepared_dataset.v1":
        fail("prepared_schema_mismatch", "unexpected prepared schema")
    if selection.get("schema") != "sidscope.llada_rec_episode_selection.v1":
        fail("selection_schema_mismatch", "unexpected selection schema")
    prepared_hash = canonical_hash(prepared)
    selection_hash = canonical_hash(selection)
    if selection.get("prepared_dataset_contract_sha256") != prepared_hash:
        fail("selection_prepared_binding_mismatch", "selection does not bind prepared")
    if bundle.get("schema") != "sidscope.llada_rec_trained_trace.v2":
        fail("bundle_schema_mismatch", "unexpected trained-trace schema")
    if bundle.get("source_revision") != SOURCE_REVISION:
        fail("source_revision_mismatch", "trained trace source revision differs")
    if bundle.get("decode_state_kind") != "masked_parallel_adaptive_unmasking":
        fail("decode_state_mismatch", "trained trace lost native masked state")
    if bundle.get("remasking_supported_by_pinned_source") is not False:
        fail("unsupported_remasking_claim", "pinned source does not support remasking")
    if bundle.get("prepared_dataset_contract_sha256") != prepared_hash:
        fail("prepared_binding_mismatch", "bundle does not bind prepared")
    if bundle.get("episode_selection_manifest_sha256") != selection_hash:
        fail("selection_binding_mismatch", "bundle does not bind selection")
    if bundle.get("training_manifest_sha256") != sha256_file(training_manifest_path):
        fail("training_binding_mismatch", "bundle does not bind training manifest")
    if int(bundle.get("evaluation_cutoff", -1)) != 10:
        fail("evaluation_cutoff_mismatch", "Hit/NDCG cutoff must remain ten")
    beam_size = int(bundle.get("published_rank_depth", -1))
    if beam_size <= 0:
        fail("invalid_publication_depth", "published rank depth must be positive")

    training_bindings = training.get("bindings", {})
    if training.get("status") not in {"checkpointed", "pass"}:
        fail("training_status_mismatch", "training manifest is not checkpointed/pass")
    if training_bindings.get("source_revision") != SOURCE_REVISION:
        fail("training_source_mismatch", "training manifest source differs")
    if training_bindings.get("prepared_dataset_sha256") != sha256_file(prepared_path):
        fail("training_prepared_mismatch", "training manifest prepared file differs")

    forbidden_keys = {"source_item_id", "source_user_id", "raw_user_id", "checkpoint_payload"}
    for key, value in _walk(bundle):
        if key in forbidden_keys:
            fail("forbidden_identity_field", f"forbidden field {key}")
        if isinstance(value, str) and Path(value).is_absolute():
            fail("private_path_exposure", "bundle contains an absolute private path")

    selected = selection.get("episodes", [])
    episodes = bundle.get("episodes", [])
    if len(episodes) != len(selected):
        fail("episode_count_mismatch", "bundle/selection episode count differs")
    initial_active = {"root"} | {f"inactive-root-{index}" for index in range(1, beam_size)}
    exact = 0
    censored = 0
    hits = 0
    ndcg_sum = 0.0
    invalid = 0
    duplicates = 0
    for expected, episode in zip(selected, episodes):
        if str(episode.get("episode_id")) != str(expected.get("episode_id")):
            fail("episode_order_mismatch", "bundle does not preserve selection order")
        if str(episode.get("target_normalized_item_id")) != str(
            expected.get("target_normalized_item_id")
        ):
            fail("target_mismatch", "bundle target differs from selection")
        if episode.get("gap_bucket") != expected.get("gap_bucket"):
            fail("bucket_mismatch", "bundle evaluator bucket differs")
        initial = episode.get("initial_mask_state")
        if initial != [1026, 1026, 1026, 1026]:
            fail("initial_mask_state_mismatch", "target must start all-mask")
        steps = episode.get("steps", [])
        if len(steps) != 4:
            fail("refinement_step_count_mismatch", "expected four unmasking actions")
        active = set(initial_active)
        for expected_step, step in enumerate(steps, start=1):
            if int(step.get("refinement_step", -1)) != expected_step:
                fail("noncontiguous_refinement_step", "refinement steps are not contiguous")
            transitions = step.get("transitions", [])
            if len(transitions) != beam_size:
                fail("beam_count_mismatch", "each action must retain the configured beams")
            next_active: set[str] = set()
            for transition in transitions:
                beam_id = str(transition.get("beam_id"))
                parent = str(transition.get("parent_beam_id"))
                if beam_id in next_active:
                    fail("duplicate_beam_id", "duplicate retained beam identity")
                if parent not in active:
                    fail("unknown_parent_beam", f"unknown parent beam {parent}")
                pre = transition.get("pre_tokens")
                post = transition.get("post_tokens")
                positions = transition.get("selected_positions")
                predicted = transition.get("predicted_tokens")
                if not isinstance(pre, list) or not isinstance(post, list) or len(pre) != 4 or len(post) != 4:
                    fail("state_width_mismatch", "beam state width must be four")
                if not isinstance(positions, list) or len(positions) != 1:
                    fail("unmask_action_width_mismatch", "pinned route fills one position per action")
                if not isinstance(predicted, list) or len(predicted) != 1:
                    fail("predicted_token_width_mismatch", "each action selects one token")
                position = int(positions[0])
                token = int(predicted[0])
                if position < 0 or position >= 4 or pre[position] != 1026:
                    fail("selected_position_not_masked", "selected position was not masked")
                lower = position * 256 + 1
                if token < lower or token >= lower + 256:
                    fail("token_outside_position_vocabulary", "selected token violates offset")
                expected_post = list(pre)
                expected_post[position] = token
                if post != expected_post:
                    fail("state_transition_mismatch", "post state differs from one-position action")
                if transition.get("remasked_positions") != []:
                    fail("unsupported_remasking_transition", "pinned source never remasks")
                if not math.isfinite(float(transition.get("beam_score_log_probability"))):
                    fail("invalid_beam_score", "beam score is not finite")
                next_active.add(beam_id)
            active = next_active

        ranked = episode.get("ranked_items", [])
        if [int(row.get("rank", -1)) for row in ranked] != list(range(1, len(ranked) + 1)):
            fail("noncontiguous_dense_ranks", "ranked items must be dense and contiguous")
        if len({str(row.get("normalized_item_id")) for row in ranked}) != len(ranked):
            fail("duplicate_ranked_item", "ranked normalized items must be unique")
        target = str(episode["target_normalized_item_id"])
        observed_rank = next(
            (int(row["rank"]) for row in ranked if str(row["normalized_item_id"]) == target),
            None,
        )
        if episode.get("target_rank") != observed_rank:
            fail("target_rank_mismatch", "declared target rank differs from dense ranking")
        if observed_rank is None:
            censored += 1
            if episode.get("target_rank_state") != "right_censored_beyond_beam_frontier":
                fail("unsupported_exact_rank_claim", "absent target must be right-censored")
        else:
            exact += 1
            if episode.get("target_rank_state") != "exact":
                fail("exact_rank_state_mismatch", "observed target rank must be exact")
        expected_hit = observed_rank is not None and observed_rank <= 10
        expected_ndcg = 1.0 / math.log2(observed_rank + 1) if expected_hit else 0.0
        if bool(episode.get("hit_at_10")) != expected_hit:
            fail("hit_at_10_mismatch", "episode Hit@10 is inconsistent")
        if not math.isclose(float(episode.get("ndcg_at_10")), expected_ndcg, abs_tol=1e-12):
            fail("ndcg_at_10_mismatch", "episode NDCG@10 is inconsistent")
        hits += int(expected_hit)
        ndcg_sum += expected_ndcg
        candidate_summary = episode.get("candidate_summary", {})
        invalid += int(candidate_summary.get("invalid_raw_tuple_count", -1))
        duplicates += int(candidate_summary.get("duplicate_raw_tuple_count", -1))

    count = len(episodes)
    summary = bundle.get("summary", {})
    if not math.isclose(float(summary.get("hit_at_10")), hits / count, abs_tol=1e-12):
        fail("summary_hit_mismatch", "summary Hit@10 differs from episodes")
    if not math.isclose(float(summary.get("ndcg_at_10")), ndcg_sum / count, abs_tol=1e-12):
        fail("summary_ndcg_mismatch", "summary NDCG@10 differs from episodes")
    if int(summary.get("exact_target_rank_count", -1)) != exact:
        fail("summary_exact_rank_mismatch", "summary exact-rank count differs")
    if int(summary.get("right_censored_target_rank_count", -1)) != censored:
        fail("summary_censored_rank_mismatch", "summary censored count differs")
    five_bucket = {bucket: sum(row["gap_bucket"] == bucket for row in episodes) for bucket in BUCKETS}
    if summary.get("five_bucket_counts") != five_bucket:
        fail("summary_bucket_mismatch", "summary bucket counts differ")
    return {
        "schema": "sidscope.llada_rec_trained_trace_verification.v1",
        "status": "pass",
        "route_id": "llada_rec",
        "source_revision": SOURCE_REVISION,
        "input_file_sha256": {
            "prepared": sha256_file(prepared_path),
            "selection": sha256_file(selection_path),
            "bundle": sha256_file(bundle_path),
            "training_manifest": sha256_file(training_manifest_path),
        },
        "canonical_sha256": {
            "prepared": prepared_hash,
            "selection": selection_hash,
            "bundle": canonical_hash(bundle),
        },
        "episode_count": count,
        "five_bucket_counts": five_bucket,
        "hit_at_10": hits / count,
        "ndcg_at_10": ndcg_sum / count,
        "exact_target_rank_count": exact,
        "right_censored_target_rank_count": censored,
        "invalid_raw_tuple_count": invalid,
        "duplicate_raw_tuple_count": duplicates,
        "compute": summary.get("compute"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--training-manifest", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument(
        "--expected-failure-mutation",
        choices=("unknown_parent_beam", "prepared_binding_mismatch"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = verify(
            prepared_path=args.prepared,
            selection_path=args.selection,
            bundle_path=args.bundle,
            training_manifest_path=args.training_manifest,
            expected_failure_mutation=args.expected_failure_mutation,
        )
    except VerificationFailure as exc:
        if args.expected_failure_mutation == exc.label:
            result = {
                "schema": "sidscope.llada_rec_trained_trace_expected_failure.v1",
                "status": "pass",
                "expected_failure_label": exc.label,
            }
        else:
            result = {
                "schema": "sidscope.llada_rec_trained_trace_verification.v1",
                "status": "fail",
                "failure": {"label": exc.label, "message": str(exc)},
            }
    else:
        if args.expected_failure_mutation is not None:
            result = {
                "schema": "sidscope.llada_rec_trained_trace_expected_failure.v1",
                "status": "fail",
                "failure": {
                    "label": "expected_failure_not_observed",
                    "message": args.expected_failure_mutation,
                },
            }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
