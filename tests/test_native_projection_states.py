import itertools
import json
from pathlib import Path
import pytest
from sidinspector.contracts import validate_trace_envelope, with_content_sha256, RuntimeContractValidationError
from sidinspector.trace import validate_native_projection, NativePayloadValidationError

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("catalog,generated,resolved,rank_state,failure", list(itertools.product((False, True), (False, True), (False, True), ("exact", "right_censored", "not_applicable"), (None, "native_failure"))))
def test_complete_target_state_truth_table(catalog, generated, resolved, rank_state, failure):
    doc = json.loads((ROOT / "examples/canonical_pipeline_fixture/trace_envelope.json").read_text())
    row = doc["observations"][0]
    row["target"] = {"catalog_reachable": catalog, "generated": generated, "resolved": resolved, "rank_state": rank_state, "exact_rank": 1 if rank_state == "exact" else None, "rank_lower_bound": 11 if rank_state == "right_censored" else None}
    row["failure_state"] = failure
    invalid = (resolved and not (catalog and generated)) or (rank_state == "exact" and (not resolved or failure is not None))
    if invalid:
        with pytest.raises(RuntimeContractValidationError):
            validate_trace_envelope(with_content_sha256(doc))
    else:
        validate_trace_envelope(with_content_sha256(doc))


def test_explicit_native_rank_cannot_be_rehashed_into_other_observation():
    payload = json.loads((ROOT / "examples/native_trace_payload_fixtures/decoder_overlay.json").read_text())
    trace = json.loads((ROOT / "examples/canonical_pipeline_fixture/trace_envelope.json").read_text())
    selection = json.loads((ROOT / "examples/canonical_pipeline_fixture/episode_selection.json").read_text())
    selection["rows"] = [selection["rows"][0]]
    selection["rows"][0].update(episode_id="episode-0", target_normalized_item_id=8)
    selection = with_content_sha256(selection)
    trace["observations"] = [trace["observations"][0]]
    trace["observations"][0].update(episode_id="episode-0", termination_state="success", failure_state=None)
    trace["observations"][0]["target"].update(catalog_reachable=True, generated=True, resolved=True, rank_state="exact", exact_rank=1, rank_lower_bound=None)
    trace.update(method_family=payload["method_family"], payload_schema=payload["schema"], payload_sha256=payload["content_sha256"])
    trace["episode_selection_binding"]["content_sha256"] = selection["content_sha256"]
    trace = with_content_sha256(trace)
    assert "target_rank" in validate_native_projection(payload, trace, selection)["verified_fields"]
    trace["observations"][0]["target"]["exact_rank"] = 2
    with pytest.raises(NativePayloadValidationError) as caught:
        validate_native_projection(payload, with_content_sha256(trace), selection)
    assert caught.value.code == "native_projection_rank_mismatch"
