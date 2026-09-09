#!/usr/bin/env python3
"""Observed RPG/PSID inputs -> canonical identities, trace, diagnostic admission.

Pure data bridge: no models, checkpoint loads, secrets, fixture provenance or
caller-written hashes. Full normalized inputs stay external to the submission.
Existing training records remain declarations, not independently verified facts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from sidinspector import contracts as c
from sidinspector.contracts.json_io import loads_json
from sidinspector.contracts.prepared_dataset import validate_prepared_dataset_bindings
from sidinspector.contracts.runtime_contracts import validate_runtime_bindings
from sidinspector.conformance_core.profile_engine import (build_dataset_profile_descriptor,
    build_profile_conformance_report, get_profile_definition)
from sidinspector.evidence.bundle import build_evidence_bundle, scan_evidence_content, REQUIRED_PROVENANCE_ROLES
from sidinspector.evidence.recomputation import result_card_from_diagnostic
from sidinspector.evidence.comparison import compare_evidence_bundles
from sidinspector.submission.checker import check_submission, validate_submission_package
from sidinspector.sdk import AdapterHarness, validate_adapter_capabilities
from sidscope.mapping_check import preflight
from tools.project_sidscope_native_export import project_export, fail
from tools.verify_sidscope_native_observation import validate_observed_inputs, DATASETS

PRODUCER = {"name": "sidscope.native_observation_bridge", "version": "1.7.0.dev0"}
ALIASES = {"short": "short", "30-90d": "30-90d", "90-180d": "90-180d",
    "180-365d": "180-365d", ">365d": "gt365d", "overall": "overall"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(doc):
    return c.canonical_json_bytes(doc) + b"\n"


def binding(doc):
    return {"schema_id": doc["schema"], "schema_revision": doc["schema_revision"], "content_sha256": doc["content_sha256"]}


def document(kind, id_field, identity, **fields):
    return c.with_content_sha256({"schema": "sidscope." + kind + ".v1", "schema_revision": "1.0.0",
        id_field: identity, "producer": PRODUCER, **fields})


def validate_metadata(meta, native, method):
    fields = {"format", "method", "checkpoint_sha256", "completed_epoch", "global_step",
        "training_run_completed_epochs", "training_run_completed_steps", "records_sha256", "records_kind", "verification_scope"}
    if not isinstance(meta, dict) or set(meta) != fields or meta["format"] != "sidscope.native_checkpoint_metadata.v1":
        fail("invalid_checkpoint_metadata", "explicit extracted metadata required")
    if meta["method"] != method or meta["checkpoint_sha256"] != native["evidence"]["checkpoint_sha256"]:
        fail("checkpoint_metadata_binding_mismatch", "method/checkpoint")
    for field in ("completed_epoch", "global_step", "training_run_completed_epochs", "training_run_completed_steps"):
        if type(meta[field]) is not int or meta[field] < 1:
            fail("invalid_checkpoint_metadata", field)
    if meta["completed_epoch"] > meta["training_run_completed_epochs"] or meta["global_step"] > meta["training_run_completed_steps"]:
        fail("invalid_checkpoint_metadata", "checkpoint progress exceeds run")
    if c.SHA256_PATTERN.fullmatch(str(meta["records_sha256"])) is None or meta["verification_scope"] != "existing_training_records_not_recomputed":
        fail("invalid_checkpoint_metadata", "records/scope")
    if meta["records_kind"] != {"rpg": "rpg_training_manifest", "psid": "psid_training_log"}[method]:
        fail("invalid_checkpoint_metadata", "records kind")
    if method == "rpg" and meta["records_sha256"] != native["evidence"]["training_manifest_sha256"]:
        fail("checkpoint_metadata_binding_mismatch", "RPG training manifest")
    scan_evidence_content(meta)


class NativeObservationProducer:
    """SDK exporter of an already observed native run, not a model executor.

    Use the supported legacy descriptor because these unchanged legacy payloads
    do not claim the newer family-payload schema. The stable runtime retains
    this historical descriptor reader while current plugins target SDK 1.0.
    """
    def __init__(self, trace):
        self.trace = trace
        self.calls = 0

    def get_capabilities(self):
        return c.with_content_sha256({"schema": "sidscope.adapter_capabilities.alpha.v1", "sdk_version": "0.1.0",
            "adapter_id": "observed-native-export", "producer": PRODUCER,
            "method_family": self.trace["method_family"], "contract_types": ["trace-envelope"],
            "telemetry": {"supported": ["compute", "target_state"], "unavailable": ["training_reproducibility"]},
            "execution_boundary": "external_runtime"})

    def produce(self, kind, path):
        if kind != "trace-envelope":
            fail("unsupported_observation_export", kind)
        self.calls += 1
        with Path(path).open("xb") as handle:
            handle.write(encode(self.trace))
        return Path(path)


def native_observations(native, selected, measured, projection):
    """Project only complete final native output, retaining published rank slots."""
    universe = {r["normalized_item_id"]: r for r in native["target_universe"]["rows"]}
    rpg = native["method"] == "RPG"
    observations = []
    for i, (ep, label, compute, ranked) in enumerate(zip(native["episodes"], selected, measured, projection["records"])):
        target = label["target_normalized_item_id"]
        if rpg:
            if native["target_universe"]["visibility"] != "external_complete" or not ep["propagation"]:
                fail("complete_native_frontier_required", "RPG")
            # RPG emits graph item nodes; do not reinterpret unordered tokens as
            # an AR prefix or drop a valid node merely because its SID collides.
            generated = target in ep["propagation"][-1]["frontier"]
            resolved = generated and target in universe
            termination, attempts = ep["termination_reason"], 1
        else:
            beams = [beam for attempt in ep["attempts"] for beam in attempt["final_beams"]]
            tokens = universe[target]["ordered_model_vocabulary_tokens"]
            generated = any(beam["ordered_model_vocabulary_tokens"] == tokens for beam in beams)
            resolved = any(beam["valid"] and beam["normalized_item_id"] == target for beam in beams)
            termination, attempts = "native_attempts_completed", len(ep["attempts"])
        rank = ranked["rank"]
        if rank is not None and not resolved:
            fail("native_rank_resolution_mismatch", ep["trace_id"])
        observations.append({"selection_order": i, "episode_id": ep["trace_id"], "attempt_count": attempts,
            "termination_state": termination, "failure_state": None,
            "target": {"catalog_reachable": target in universe, "generated": generated, "resolved": resolved,
                "rank_state": ranked["rank_state"], "exact_rank": rank,
                "rank_lower_bound": projection["protocol"]["publication_depth"] + 1 if rank is None else None},
            "compute": dict(compute)})
    return observations


def build_documents(source, metadata):
    source = Path(source)
    blobs = {name: (source / (name + ".json")).read_bytes() for name in ("native", "selection", "observations", "preflight")}
    hashes = {key: digest(value) for key, value in blobs.items()}
    native, selected, observed, inputs = [loads_json(blobs[k], max_bytes=None) for k in blobs]
    metadata_bytes = Path(metadata).read_bytes()
    meta = loads_json(metadata_bytes, max_bytes=None)
    projection = project_export(source / "native.json", selection=source / "selection.json")
    method = validate_observed_inputs(native, selected, observed, inputs,
        native_sha256=hashes["native"], preflight_sha256=hashes["preflight"])
    validate_metadata(meta, native, method)
    mapped = preflight(**{**inputs, "dataset": DATASETS[method]})
    rpg = method == "rpg"
    prefix = method + ":observed"
    docs = {}
    source_files = observed["source_files"]
    if not source_files or any(c.SHA256_PATTERN.fullmatch(str(v)) is None for v in source_files.values()):
        fail("invalid_source_snapshot", "nonempty file digest inventory required")
    docs["source"] = document("source_identity", "source_id", prefix,
        paper={"title": "RPG" if rpg else "PSID (Latte implementation)", "url": None},
        repository={"url": "https://github.com/facebookresearch/RPG_KDD2025" if rpg else native["evidence"]["source_url"],
            "revision_kind": "content_sha256", "revision": c.canonical_sha256(source_files)},
        license={"status": "restricted_source_license" if rpg else "licensed",
            "identifier": "CC-BY-NC-4.0" if rpg else native["evidence"]["source_license"],
            "notices": [], "redistribution_policy": "metadata_only_no_upstream_source_or_assets"},
        derivation="observed_runtime_module_snapshot_not_asserted_pristine_upstream_commit",
        artifact_name="observed-python-yaml-source-snapshot", patches=[])
    # Each canonical data hash identifies the normalized observed representation,
    # not unrelated upstream bytes or a fixture. Selected PSID test scope stays
    # selected; neither dataset is promoted to a full-population effectiveness run.
    splits = [{"role": role, "split_id": DATASETS[method] + ":" + role,
        "sha256": c.canonical_sha256([row for row in inputs["splits"] if row["split"] == key]),
        "row_count": sum(row["split"] == key for row in inputs["splits"])}
        for role, key in (("train", "train"), ("validation", "valid"), ("test", "test"))]
    catalog = {"scope": "full_dataset", "item_count": len(inputs["catalog"]), "sha256": c.canonical_sha256(sorted(inputs["catalog"], key=lambda r: r["item_id"]))}
    target_rows = sorted({row["target_item_id"] for row in inputs["splits"] if row["split"] != "train"})
    target_universe = {"scope": "evaluation_targets", "item_count": len(target_rows), "sha256": c.canonical_sha256(target_rows)}
    docs["data"] = document("dataset_identity", "dataset_id", prefix,
        dataset={"name": "AmazonReviews2014", "normalized_name": DATASETS[method], "category": "Beauty" if rpg else "VideoGames", "profile": "observed_train_validation_test_with_explicit_native_selection"},
        splits=splits, catalog=catalog, target_universe=target_universe,
        privacy={"item_identity": "pseudonymous_normalized_items", "contains_source_item_ids": False}, identity_status="fully_bound", unbound_fields=[])
    depth = native["configuration"]["n_codebooks"] if rpg else len(native["target_universe"]["rows"][0]["ordered_model_vocabulary_tokens"])
    size = native["configuration"]["codebook_size"] if rpg else 256
    vocab_size = depth * size + 1 if rpg else native["episodes"][0]["attempts"][0]["vocabulary_size"]
    cache_hash = c.canonical_sha256(sorted(inputs["mapping"], key=lambda r: r["item_id"]))
    tokenizer_config = {"depth": depth, "codebook_size": size, "vocabulary_size": vocab_size,
        "encoding": "position_offset_semantic_codes" if rpg else "ordered_model_vocabulary_tokens"}
    docs["sid"] = document("sid_space_identity", "sid_space_id", prefix,
        structure={"tuple_kind": "unordered_set" if rpg else "ordered", "length_kind": "fixed", "depth": depth, "hierarchy": "none" if rpg else "prefix"},
        vocabulary={"semantic_code_min": 0, "codebook_sizes": [size] * depth,
            "position_offsets": [1 + size*i for i in range(depth)], "position_disjoint": True,
            "model_vocabulary_size": vocab_size,
            "special_tokens": {"pad": 0, "bos": None, "eos": None if rpg else native["decoder_vocabulary"]["eos_token_id"], "mask": None, "unknown": None}},
        tokenizer={"kind": "observed_native_mapping", "tokenizer_factor": "OPQ32" if rpg else "PSID_RQ",
            "configuration_sha256": c.canonical_sha256(tokenizer_config), "artifact_sha256": cache_hash},
        resolution={"dedup_semantics": "preserve_all_item_collisions", "collision_semantics": "many_items_per_sid_allowed"}, identity_status="fully_bound", unbound_fields=[])
    docs["prepared"] = document("prepared_dataset", "prepared_dataset_id", prefix,
        dataset_binding=binding(docs["data"]), sid_space_binding=binding(docs["sid"]),
        normalization={"representation": "normalized_item_sequences", "item_identity": "pseudonymous_normalized_items", "episode_identity": "pseudonymous_episode_ids",
            "source_item_ids_exported": False, "source_user_ids_exported": False, "evaluator_labels_in_generator_input": False},
        splits=splits, artifacts=[{"role": "interaction_sequences", "sha256": c.canonical_sha256(inputs["splits"]), "row_count": len(inputs["splits"])},
            {"role": "item_mapping", "sha256": catalog["sha256"], "row_count": catalog["item_count"]},
            {"role": "semantic_id_cache", "sha256": cache_hash, "row_count": catalog["item_count"]}],
        catalog=catalog, target_universe=target_universe)
    rows = []
    for i, row in enumerate(observed["selection"]):
        if row["slice"] not in ALIASES:
            fail("unsupported_native_slice", row["slice"])
        labels = {"cluster_id": row["cluster_id"], "native_slice": row["slice"]}
        if row["slice"] != "overall":
            labels["dormancy_bucket"] = ALIASES[row["slice"]]
        rows.append({"order": i, "episode_id": row["episode_id"], "split_row_index": row["split_row_index"],
            "target_normalized_item_id": row["target_normalized_item_id"], "evaluator_labels": labels})
    docs["selection"] = document("episode_selection", "selection_id", prefix,
        prepared_dataset_binding=binding(docs["prepared"]), split={k: splits[2][k] for k in ("split_id", "sha256")},
        policies={k: "reject" for k in ("missing_row", "duplicate_row", "out_of_split", "target_mismatch", "catalog_unreachable")}, rows=rows)
    configuration = native.get("configuration", {"decoder_vocabulary": native.get("decoder_vocabulary"), "native_training_config_sha256": native["evidence"].get("training_config_sha256")})
    docs["run"] = document("run_identity", "run_id", prefix + ":" + hashes["native"][:12], run_kind="trace_export",
        source_binding=binding(docs["source"]), prepared_dataset_binding=binding(docs["prepared"]),
        configuration_sha256=c.canonical_sha256(configuration), seed=observed["seed"],
        command_sha256=c.canonical_sha256({"entrypoint": "tools/build_sidscope_native_submission.py",
            "input_sha256": hashes, "metadata_sha256": digest(metadata_bytes)}),
        environment_sha256=c.canonical_sha256(observed["environment"]), training_manifest_sha256=None)
    checkpoint_sha = meta["checkpoint_sha256"]
    docs["checkpoint"] = document("checkpoint_binding", "checkpoint_id", prefix + ":" + checkpoint_sha[:12],
        run_binding=binding(docs["run"]), checkpoint_sha256=checkpoint_sha, state_kind="inference_only",
        completed_epoch=meta["completed_epoch"], global_step=meta["global_step"],
        state_sha256={"model": checkpoint_sha, "optimizer": None, "scheduler": None, "rng": None},
        epoch_ledger_sha256=None, previous_checkpoint_sha256=None)
    docs["trace"] = document("trace_envelope", "trace_envelope_id", prefix + ":" + hashes["native"][:12],
        episode_selection_binding=binding(docs["selection"]), run_binding=binding(docs["run"]), checkpoint_binding=binding(docs["checkpoint"]),
        method_family="parallel_graph_token_set" if rpg else "autoregressive_prefix", payload_schema=native["schema"], payload_sha256=hashes["native"],
        observations=native_observations(native, observed["selection"], observed["measurements"], projection))
    validate_identities(docs)
    k, publication_depth = (projection["protocol"][key] for key in ("evaluation_cutoff", "publication_depth"))
    docs["diagnostics"] = c.diagnostic_report_document(c.validate_trace_envelope(docs["trace"]), c.validate_episode_selection(docs["selection"]), evaluation_cutoff=k, publication_depth=publication_depth)
    docs["evaluation_protocol"] = c.build_evaluation_protocol(dataset_identity_sha256=docs["data"]["content_sha256"],
        target_universe_sha256=target_universe["sha256"], evaluation_cutoff=k, publication_depth=publication_depth,
        rank_semantics="exact_with_censoring", episode_selection_sha256=docs["selection"]["content_sha256"])
    descriptor = build_dataset_profile_descriptor(descriptor_id=prefix, producer=PRODUCER,
        dataset_identity_sha256=docs["data"]["content_sha256"],
        split_bindings=[{"role": row["role"], "content_sha256": row["sha256"], "row_count": row["row_count"]} for row in splits],
        catalog={"scope": catalog["scope"], "item_count": catalog["item_count"], "content_sha256": catalog["sha256"]},
        target_universe={"scope": target_universe["scope"], "item_count": target_universe["item_count"], "content_sha256": target_universe["sha256"]},
        evaluation={"cutoff": k, "publication_depth": publication_depth,
            "slices": [{"slice_id": name, "definition_sha256": c.canonical_sha256({"aliases": ALIASES, "slice": name})}
                for name in sorted({row["slice_id"] for row in docs["diagnostics"]["slices"]})]},
        privacy={"policy_sha256": c.canonical_sha256("normalized_metadata_only_no_assets"), "source_user_ids_exported": False, "source_item_ids_exported": False, "absolute_private_paths_exported": False})
    profile = get_profile_definition("generator_g0_g5")
    # All named-adapter gates remain partial. Executable diagnostic admission is
    # separate, and must not inherit historical PASS declarations as new proof.
    docs["conformance"] = build_profile_conformance_report(report_id=prefix, producer=PRODUCER,
        profile_id=profile.profile_id, descriptor=descriptor,
        artifacts=[{"artifact_id": "descriptor", "role": "dataset_profile_descriptor", **binding(descriptor.to_dict())}],
        gate_results=[{"gate_id": gate.gate_id, "status": "partial", "failure": {"code": gate.failure_code,
            "detail": "Only supplied-observation diagnostic scope recomputed; full named-adapter gate not rerun"}} for gate in profile.gates]).to_dict()
    docs["origin"] = c.with_content_sha256({"format": "sidscope.native_canonical_origin.v1", "input_sha256": hashes,
        "checkpoint_metadata_sha256": digest(metadata_bytes), "checkpoint_metadata": meta,
        "source_files": source_files, "native_protocol": projection["protocol"], "slice_aliases": ALIASES,
        "mapping_report_sha256": mapped["content_sha256"], "unavailable_mapping_checks": mapped["unavailable"],
        "compute_definition": observed["nfe_definition"], "compute_scope": observed["compute_scope"],
        "environment": observed["environment"], "unverified": ["training_reproducibility", "native_execution_authenticity", "independent_user_adoption"]})
    for doc in docs.values():
        scan_evidence_content(doc)
    if any(digest((source / (name + ".json")).read_bytes()) != expected for name, expected in hashes.items()) or Path(metadata).read_bytes() != metadata_bytes:
        fail("native_input_changed", "input changed during build")
    return docs, descriptor.to_dict()


def validate_identities(docs):
    source = c.validate_source_identity(docs["source"])
    data = c.validate_dataset_identity(docs["data"])
    sid = c.validate_sid_space_identity(docs["sid"])
    prepared = c.validate_prepared_dataset(docs["prepared"])
    validate_prepared_dataset_bindings(prepared, data, sid)
    validate_runtime_bindings(c.validate_episode_selection(docs["selection"]), c.validate_run_identity(docs["run"]),
        c.validate_checkpoint_binding(docs["checkpoint"]), c.validate_trace_envelope(docs["trace"]),
        source_sha256=source.content_sha256, prepared_sha256=prepared.content_sha256)
    if docs["selection"]["split"] != {k: docs["prepared"]["splits"][2][k] for k in ("split_id", "sha256")}:
        fail("canonical_selection_split_mismatch", "prepared test split")


def write_package(docs, descriptor, output):
    artifacts, objects = [], {}
    for role, doc in docs.items():
        payload = encode(doc)
        row = {"artifact_id": role, "role": role, "schema_id": doc.get("schema", doc.get("format")), "schema_revision": doc.get("schema_revision", "1.0.0"),
            "content_sha256": doc["content_sha256"], "object_sha256": digest(payload), "size_bytes": len(payload), "media_type": "application/json", "availability": "embedded_public"}
        if role == "checkpoint":
            # Required checkpoint provenance is hash-only; a separately typed
            # identity object is metadata, not the forbidden weight payload.
            artifacts.append({**row, "availability": "hash_reference_only"})
            row = {**row, "artifact_id": "checkpoint_identity", "role": "checkpoint_identity"}
        artifacts.append(row)
        objects[digest(payload)] = payload
    protocol = docs["evaluation_protocol"]
    compatibility = {key: protocol[key] for key in ("dataset_identity_sha256", "target_universe_sha256", "evaluation_cutoff", "publication_depth", "rank_semantics")}
    bundle = build_evidence_bundle(bundle_id=docs["trace"]["trace_envelope_id"], producer=PRODUCER,
        profile_binding={"profile_id": "generator_g0_g5", "profile_revision": "1.0.0", "conformance_report_sha256": docs["conformance"]["content_sha256"]},
        subject={"adapter_id": "rpg-observed" if docs["trace"]["method_family"] == "parallel_graph_token_set" else "psid-observed", "method_family": docs["trace"]["method_family"]},
        compatibility=compatibility, artifacts=artifacts,
        provenance_edges=[{"from_artifact": a, "to_artifact": b, "relation": "observed_derivation"} for a,b in zip(REQUIRED_PROVENANCE_ROLES, REQUIRED_PROVENANCE_ROLES[1:])],
        result_card=result_card_from_diagnostic(docs["diagnostics"], docs["trace"], protocol["rank_semantics"]))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    files = {"dataset_profile_descriptor.json": encode(descriptor), "profile_conformance_report.json": encode(docs["conformance"]), "evidence_bundle.json": encode(bundle.to_dict())}
    rows = [{"artifact_id": role, "role": role, "path": role + ".json", "sha256": digest(files[role + ".json"])} for role in ("dataset_profile_descriptor", "profile_conformance_report", "evidence_bundle")]
    for sha, payload in objects.items():
        if any(row["sha256"] == sha for row in rows):
            continue
        path = "objects/" + sha + ".json"
        files[path] = payload
        rows.append({"artifact_id": "object:" + sha, "role": "evidence_object", "path": path, "sha256": sha})
    submission = document("evidence_submission", "submission_id", bundle.bundle_id,
        artifacts=sorted(rows, key=lambda r: r["artifact_id"]), claims={**compatibility, "profile_id": "generator_g0_g5", "profile_revision": "1.0.0", "exact_ranks": bundle.result_card["rank_observations"]["exact_ranks"]})
    files["submission.json"] = encode(submission)
    for relative, payload in files.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(payload)
    return bundle


def build_submission(source, metadata, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    if Path(source).resolve() == output.resolve() or Path(source).resolve() in output.resolve().parents:
        fail("canonical_output_inside_input", "new sibling output directory required")
    docs, descriptor = build_documents(source, metadata)
    with tempfile.TemporaryDirectory(prefix="sidscope-native-canonical-") as temporary:
        producer = NativeObservationProducer(docs["trace"])
        exported = AdapterHarness(validate_adapter_capabilities(producer.get_capabilities()), producer).produce("trace-envelope", Path(temporary) / "trace.json")
        if exported.to_dict() != docs["trace"]:
            fail("native_sdk_export_mismatch", "SDK export differs from canonical projection")
        package = Path(temporary) / "submission"
        bundle = write_package(docs, descriptor, package)
        admission = check_submission(package).to_dict()
        if admission["status"] != "accepted":
            fail("canonical_native_admission_failed", json.dumps(admission))
        current = validate_submission_package(package)
        comparison = compare_evidence_bundles(bundle, bundle, left_objects=current.objects, right_objects=current.objects)
        if comparison["status"] != "compatible":
            fail("canonical_native_comparison_failed", json.dumps(comparison))
        receipt = c.with_content_sha256({"format": "sidscope.native_canonical_completion.v1", "status": "pass",
            "admission": admission, "bundle_sha256": bundle.content_sha256, "origin_sha256": docs["origin"]["content_sha256"],
            "comparison_kind": "same_export_recomputation", "comparison": comparison,
            "conformance": docs["conformance"]["decision"], "verification_scope": "canonical_bindings_and_diagnostics_from_supplied_native_observation",
            "sdk_export_calls": producer.calls,
            "unverified": docs["origin"]["unverified"]})
        output.mkdir(parents=True, exist_ok=False)
        shutil.copytree(package, output / "submission")
        with (output / "complete.json").open("xb") as handle:
            handle.write(encode(receipt))
    return receipt


def verify_submission(source, metadata, package):
    """Rebuild from supplied originals; rehashing forged canonical JSON cannot pass."""
    actual = validate_submission_package(Path(package))
    docs, descriptor = build_documents(source, metadata)
    with tempfile.TemporaryDirectory(prefix="sidscope-native-recheck-") as temporary:
        expected_bundle = write_package(docs, descriptor, Path(temporary) / "expected")
        if actual.evidence_bundle.to_dict() != expected_bundle.to_dict():
            fail("native_canonical_projection_mismatch", "canonical bundle differs from original native inputs")
    result = check_submission(Path(package)).to_dict()
    if result["status"] != "accepted":
        fail("canonical_native_admission_failed", json.dumps(result))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", type=Path)
    destination.add_argument("--verify-submission", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.verify_submission:
            result = verify_submission(args.input, args.metadata, args.verify_submission)
            print(json.dumps(result, sort_keys=True))
            return 0
        receipt = build_submission(args.input, args.metadata, args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "fail", "code": getattr(error, "code", type(error).__name__), "detail": str(error)}))
        return 2
    print(json.dumps({"status": receipt["status"], "admission": receipt["admission"]["status"], "bundle_sha256": receipt["bundle_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
