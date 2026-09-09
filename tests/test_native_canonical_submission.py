"""Synthetic plumbing tests; actual external acceptance is recorded separately."""
import copy
import hashlib
import json
from pathlib import Path
import pytest
from sidinspector import contracts as c
from sidinspector.evidence.bundle import scan_evidence_content
from sidinspector.submission.checker import check_submission, validate_submission_package
from tools.build_sidscope_native_submission import (build_documents, build_submission, verify_submission,
    validate_identities, validate_metadata, native_observations, write_package)
from tools.observe_sidscope_native_runtime import checkpoint_metadata

ROOT = Path(__file__).resolve().parents[1]
PSID = ROOT / "examples/latte_psid_trained_trace_real_smoke/psid_amazon_vg_1_per_bucket_s2024.json"


@pytest.fixture(scope="module")
def synthetic_inputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("synthetic-native-canonical")
    source = root / "inputs"
    source.mkdir()
    native = json.loads(PSID.read_text())
    mapping = [{"item_id": r["normalized_item_id"], "sid": r["ordered_model_vocabulary_tokens"]} for r in native["target_universe"]["rows"]]
    by_item = {row["item_id"]: row["sid"] for row in mapping}
    labels = [{"episode_id": ep["trace_id"], "target_normalized_item_id": ep["evaluation_slots"][0]["normalized_item_id"], "slice": ep["gap_bucket"], "cluster_id": "synthetic-"+str(i)} for i,ep in enumerate(native["episodes"])]
    splits = [{"episode_id": "synthetic-"+split, "split": split, "target_item_id": 0, "history_item_ids": []} for split in ("train","valid")]
    splits.extend({"episode_id": r["episode_id"], "split": "test", "target_item_id": r["target_normalized_item_id"], "history_item_ids": []} for r in labels)
    inputs = {"dataset": "synthetic", "mapping": mapping, "catalog": [{"item_id": r["item_id"]} for r in mapping], "splits": splits,
        "targets": [{"episode_id": r["episode_id"], "split": "test", "target_item_id": r["target_normalized_item_id"], "sid": by_item[r["target_normalized_item_id"]]} for r in labels],
        "interactions": [{"normalized_user_id": 0, "item_id": 0, "split": "train"}]}
    (source / "native.json").write_bytes(PSID.read_bytes())
    (source / "preflight.json").write_text(json.dumps(inputs))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    selected = {"format": "sidscope.native_selection.v1", "native_sha256": sha(source/"native.json"), "checkpoint_sha256": native["evidence"]["checkpoint_sha256"],
        "split_id": native["evidence"]["split_id"], "target_universe_sha256": native["target_universe"]["sha256"], "rows": labels}
    observation = {"method": "psid", "native_sha256": selected["native_sha256"], "preflight_sha256": sha(source/"preflight.json"), "checkpoint_sha256": selected["checkpoint_sha256"],
        "native_execution": "cpu_frozen_checkpoint_no_training", "environment": {"device": "cpu", "purpose": "synthetic-unit-test"},
        "selection": [{**r, "split_row_index": i} for i,r in enumerate(labels)], "measurements": [{"forward_calls": 4, "nfe": 4, "candidate_count": 50, "latency_ms": 1.0} for _ in labels],
        "source_files": {"synthetic.py": "a"*64}, "seed": 2024, "nfe_definition": "synthetic-test-only", "compute_scope": "synthetic-test-only"}
    for name,doc in (("selection",selected),("observations",observation)):
        (source/(name+".json")).write_text(json.dumps(doc))
    meta = {"format": "sidscope.native_checkpoint_metadata.v1", "method": "psid", "checkpoint_sha256": selected["checkpoint_sha256"],
        "completed_epoch": 12, "global_step": 9372, "training_run_completed_epochs": 13, "training_run_completed_steps": 10000,
        "records_sha256": "b"*64, "records_kind": "psid_training_log", "verification_scope": "existing_training_records_not_recomputed"}
    path = root/"metadata.json"
    path.write_text(json.dumps(meta))
    return source,path


@pytest.fixture(scope="module")
def documents(synthetic_inputs):
    return build_documents(*synthetic_inputs)


def test_synthetic_full_chain_sdk_admission_and_recheck(synthetic_inputs,tmp_path):
    output=tmp_path/"canonical"
    result=build_submission(*synthetic_inputs,output)
    assert result["status"]=="pass" and result["sdk_export_calls"]==1
    assert result["admission"]["bindings"]["status_label"]=="diagnostics_verified"
    assert result["conformance"]["status"]=="partial"
    assert result["comparison_kind"]=="same_export_recomputation"
    assert verify_submission(*synthetic_inputs,output/"submission")["status"]=="accepted"
    with pytest.raises(FileExistsError): build_submission(*synthetic_inputs,output)


@pytest.mark.parametrize("role,key,code",[("run","source_binding","run_source_binding_mismatch"),
    ("selection","prepared_dataset_binding","selection_prepared_binding_mismatch"),
    ("checkpoint","run_binding","checkpoint_run_binding_mismatch"),
    ("trace","checkpoint_binding","trace_checkpoint_binding_mismatch")])
def test_rehashed_identity_substitution_rejected(documents,role,key,code):
    docs=copy.deepcopy(documents[0]);docs[role][key]["content_sha256"]="f"*64
    docs[role]=c.with_content_sha256(docs[role])
    with pytest.raises(ValueError,match=code): validate_identities(docs)


def test_forged_consistent_trace_requires_native_recheck(documents,synthetic_inputs,tmp_path):
    docs,descriptor=copy.deepcopy(documents)
    docs["trace"]["observations"][0]["compute"]["latency_ms"]+=1
    docs["trace"]=c.with_content_sha256(docs["trace"])
    docs["diagnostics"]=c.diagnostic_report_document(c.validate_trace_envelope(docs["trace"]),c.validate_episode_selection(docs["selection"]),evaluation_cutoff=10,publication_depth=10)
    write_package(docs,descriptor,tmp_path/"forged")
    # Generic diagnostic verification does not claim native authenticity.
    assert check_submission(tmp_path/"forged").status=="accepted"
    with pytest.raises(ValueError,match="native_canonical_projection_mismatch"):
        verify_submission(*synthetic_inputs,tmp_path/"forged")


def test_protocol_and_unavailable_claims(documents):
    docs,_=documents
    assert docs["checkpoint"]["global_step"]==9372
    assert docs["checkpoint"]["global_step"]!=docs["origin"]["checkpoint_metadata"]["training_run_completed_steps"]
    assert docs["sid"]["structure"]["tuple_kind"]=="ordered"
    assert docs["trace"]["payload_schema"]=="sidscope.latte_psid_trained_trace_bundle.v2"
    assert docs["diagnostics"]["evaluation"]["hit_at_cutoff"]==1
    assert "gt365d" in {r["slice_id"] for r in docs["diagnostics"]["slices"]}
    assert docs["run"]["training_manifest_sha256"] is None


@pytest.mark.parametrize("value",[True,0,-1,"9372",None])
def test_invalid_checkpoint_progress(documents,value):
    docs,_=documents
    meta=copy.deepcopy(docs["origin"]["checkpoint_metadata"]);meta["global_step"]=value
    native=json.loads(PSID.read_text())
    with pytest.raises(ValueError,match="invalid_checkpoint_metadata"): validate_metadata(meta,native,"psid")


def test_prepared_privacy_exception_is_schema_validated(documents):
    prepared=documents[0]["prepared"]
    scan_evidence_content(prepared)
    with pytest.raises(ValueError): scan_evidence_content({"normalization":{"source_item_ids_exported":False}})
    for mutation in (lambda d:d["normalization"].update(source_item_ids_exported=True),
        lambda d:d["normalization"].update(source_item_ids_exported=0),
        lambda d:d["normalization"].update(raw_user_id="private")):
        bad=copy.deepcopy(prepared);mutation(bad);bad=c.with_content_sha256(bad)
        with pytest.raises(ValueError):scan_evidence_content(bad)


def test_metadata_uses_best_not_final_progress(tmp_path):
    checkpoint=tmp_path/"checkpoint.pth";checkpoint.write_bytes(b"synthetic bytes")
    logs=tmp_path/"logs/DormantVideoGames/PSID";logs.mkdir(parents=True)
    (logs/"checkpoint.log").write_text('[Epoch 12] Train Loss: 2.2; completed steps: 9372/10000\n[Epoch 12] Saved model checkpoint to ckpt/checkpoint.pth\n[Epoch 13] Train Loss: 2.1; completed steps: 10000/10000\nBest epoch: 12, Best val score: 0.1\n')
    spec={"method":"psid","source":str(tmp_path),"checkpoint":str(checkpoint),"checkpoint_sha256":hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
    result=checkpoint_metadata(spec)
    assert result["global_step"]==9372 and result["training_run_completed_steps"]==10000
    checkpoint.write_bytes(b"changed")
    with pytest.raises(ValueError,match="checkpoint identity mismatch"):checkpoint_metadata(spec)


@pytest.mark.parametrize("frontier,rank,generated",[([2],None,True),([3],None,False),([2],1,True)])
def test_rpg_final_item_nodes_preserve_censoring(frontier,rank,generated):
    native={"method":"RPG","target_universe":{"visibility":"external_complete","rows":[{"normalized_item_id":2}]},
        "episodes":[{"trace_id":"ep","propagation":[{"frontier":frontier}],"termination_reason":"completed_configured_graph_propagation"}]}
    projection={"records":[{"rank":rank,"rank_state":"exact" if rank else "right_censored"}],"protocol":{"publication_depth":10}}
    row=native_observations(native,[{"target_normalized_item_id":2}],[{"nfe":1,"forward_calls":1,"candidate_count":2,"latency_ms":1}],projection)[0]
    assert row["target"]["generated"] is generated
    assert row["target"]["resolved"] is generated
    assert row["target"]["rank_lower_bound"]==(11 if rank is None else None)


def test_psid_generated_invalid_code_is_resolution_loss_not_generation_miss():
    native={"method":"PSID","target_universe":{"rows":[{"normalized_item_id":2,"ordered_model_vocabulary_tokens":[1,257,513]}]},
        "episodes":[{"trace_id":"ep","attempts":[{"final_beams":[{"ordered_model_vocabulary_tokens":[1,257,513],"valid":False,"normalized_item_id":None}]}]}]}
    projection={"records":[{"rank":None,"rank_state":"right_censored"}],"protocol":{"publication_depth":10}}
    row=native_observations(native,[{"target_normalized_item_id":2}],[{"nfe":4}],projection)[0]
    assert row["target"]["generated"] is True and row["target"]["resolved"] is False


def test_metadata_missing_log_does_not_invent_progress(tmp_path):
    checkpoint=tmp_path/"checkpoint.pth";checkpoint.write_bytes(b"synthetic")
    spec={"method":"psid","source":str(tmp_path),"checkpoint":str(checkpoint),"checkpoint_sha256":hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
    with pytest.raises(FileNotFoundError):checkpoint_metadata(spec)
