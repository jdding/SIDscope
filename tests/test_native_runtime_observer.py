import pytest

from tools.observe_sidscope_native_runtime import rpg_observation_anchors, finish_measurement
from tools.observe_sidscope_native_runtime import episode_selection, validate_episode_counts


@pytest.mark.parametrize("episodes", [5, 100])
def test_explicit_episode_selection_preserves_frozen_policy(episodes):
    assert episode_selection("rpg", episodes) == {"--episodes": episodes}
    assert episode_selection("psid", episodes) == {
        "--eval-per-bucket-limit": episodes // 5,
        "--trained-trace-split-id": f"amazon_vg/rigor_original_test/{episodes // 5}_per_bucket/s2024"}
    native = {"episodes": [{"trace_id": str(i)} for i in range(episodes)]}
    validate_episode_counts([object()], [None] * episodes, native, episodes)


@pytest.mark.parametrize("episodes", [0, -1, True, 1.5])
def test_invalid_episode_counts_fail_closed(episodes):
    with pytest.raises(ValueError, match="positive_integer"):
        episode_selection("rpg", episodes)


def test_unbalanced_psid_selection_is_rejected():
    with pytest.raises(ValueError, match="five_equal_buckets"):
        episode_selection("psid", 99)


@pytest.mark.parametrize("measurements,ids", [(99, list(range(100))), (100, list(range(99))),
    (100, [0] * 100)])
def test_incomplete_or_duplicate_observation_is_rejected(measurements, ids):
    with pytest.raises(ValueError, match="incomplete_or_duplicate"):
        validate_episode_counts([object()], [None] * measurements,
            {"episodes": [{"trace_id": str(i)} for i in ids]}, 100)


@pytest.mark.parametrize("stop", ["episodes.append(", "episodes.append(episode_row)"])
def test_frozen_and_current_exporter_anchors(stop):
    source = "  batch = {key: value.to(device) for key, value in raw_batch.items()}\n  propagation = []\n  " + stop
    assert rpg_observation_anchors(source) == (1, 3)


@pytest.mark.parametrize("source", ["", "episodes.append(episode_row)",
    "batch = {key: value.to(device) for key, value in raw_batch.items()}\nepisodes.append(\nepisodes.append(episode_row)"])
def test_unknown_or_ambiguous_exporter_fails(source):
    with pytest.raises(ValueError, match="anchors"):
        rpg_observation_anchors(source)


def test_multiline_stop_consumes_one_episode():
    import time
    timing = {"start": time.perf_counter(), "calls": 3}
    row = finish_measurement(timing, 4, [{"candidate_count": 8}, {"candidate_count": 9}])
    assert row["nfe"] == row["forward_calls"] == 1
    assert row["candidate_count"] == 17
    assert row["latency_ms"] >= 0
    assert finish_measurement(timing, 4, []) is None


def small_observed_inputs():
    """Synthetic plumbing case; never represented as actual model execution."""
    native = {"method": "PSID", "evidence": {"checkpoint_sha256": "a" * 64},
        "target_universe": {"rows": [{"normalized_item_id": 0, "ordered_model_vocabulary_tokens": [1, 2]}]},
        "episodes": [{"trace_id": "episode", "attempts": [{"final_beams": [{}]}]}]}
    selected = {"rows": [{"episode_id": "episode", "target_normalized_item_id": 0, "cluster_id": "cluster", "slice": "short"}]}
    observation = {"method": "psid", "native_sha256": "b" * 64, "preflight_sha256": "c" * 64,
        "checkpoint_sha256": "a" * 64, "native_execution": "cpu_frozen_checkpoint_no_training", "environment": {"device": "cpu"},
        "selection": [{**selected["rows"][0], "split_row_index": 0}],
        "measurements": [{"nfe": 4, "forward_calls": 4, "candidate_count": 1, "latency_ms": 20}]}
    inputs = {"mapping": [{"item_id": 0, "sid": [1, 2]}], "splits": [{"episode_id": "episode", "split": "test", "target_item_id": 0}],
        "targets": [{"episode_id": "episode", "split": "test", "target_item_id": 0}]}
    return native, selected, observation, inputs


def check_observed(docs):
    from tools.verify_sidscope_native_observation import validate_observed_inputs
    return validate_observed_inputs(*docs, native_sha256="b" * 64, preflight_sha256="c" * 64)


def test_observation_consistency_not_authenticity():
    assert check_observed(small_observed_inputs()) == "psid"


@pytest.mark.parametrize("mutate,code", [
    (lambda d: d[2].update(native_sha256="d" * 64), "native_observation_binding_mismatch"),
    (lambda d: d[2].update(preflight_sha256="d" * 64), "native_observation_binding_mismatch"),
    (lambda d: d[2].update(checkpoint_sha256="d" * 64), "native_observation_binding_mismatch"),
    (lambda d: d[2]["environment"].update(device="cuda"), "native_observation_execution_scope"),
    (lambda d: d[2]["measurements"].clear(), "native_observation_population_mismatch"),
    (lambda d: d[2]["measurements"][0].update(nfe=True), "invalid_native_measurement"),
    (lambda d: d[2]["measurements"][0].update(latency_ms=float("nan")), "invalid_native_measurement"),
    (lambda d: d[2]["measurements"][0].update(candidate_count=5), "native_candidate_count_mismatch"),
    (lambda d: d[2]["selection"][0].update(split_row_index=True), "native_observation_split_mismatch"),
    (lambda d: d[2]["selection"][0].update(cluster_id="other"), "native_observation_selection_mismatch"),
    (lambda d: d[3]["targets"][0].update(target_item_id=1), "native_observation_target_mismatch"),
    (lambda d: d[3]["splits"][0].update(episode_id="other"), "native_observation_target_mismatch"),
    (lambda d: d[3]["mapping"][0].update(sid=[7, 8]), "native_observation_mapping_mismatch"),
])
def test_observation_typed_negatives(mutate, code):
    docs = small_observed_inputs()
    mutate(docs)
    with pytest.raises(ValueError, match=code):
        check_observed(docs)
