"""Create a new immutable diagnostic submission from existing declared provenance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sidinspector.contracts import canonical_json_bytes, with_content_sha256, validate_trace_envelope, validate_episode_selection, diagnostic_report_document
from sidinspector.contracts import build_evaluation_protocol
from sidinspector.evidence import result_card_from_diagnostic
from .checker import validate_submission_package, check_submission


def build_recomputed_submission(source: Path, output: Path, *, trace: dict, selection: dict, diagnostic: dict | None = None) -> dict:
    """Existing source/run/training declarations are preserved, not certified."""
    original = validate_submission_package(source)
    bundle = original.evidence_bundle.to_dict()
    k, depth = bundle["compatibility"]["evaluation_cutoff"], bundle["compatibility"]["publication_depth"]
    trace_contract, selection_contract = validate_trace_envelope(trace), validate_episode_selection(selection)
    diagnostic = diagnostic or diagnostic_report_document(trace_contract, selection_contract, evaluation_cutoff=k, publication_depth=depth)
    protocol = build_evaluation_protocol(**{key: bundle["compatibility"][key] for key in ("dataset_identity_sha256", "target_universe_sha256", "evaluation_cutoff", "publication_depth", "rank_semantics")}, episode_selection_sha256=selection_contract.content_sha256)
    documents = {"trace": trace, "selection": selection, "diagnostics": diagnostic, "evaluation_protocol": protocol}
    bundle["subject"]["method_family"] = trace["method_family"]
    bundle["result_card"] = result_card_from_diagnostic(diagnostic, trace, protocol["rank_semantics"])
    objects = dict(original.objects)
    for role, doc in documents.items():
        payload = canonical_json_bytes(doc) + b"\n"
        digest = hashlib.sha256(payload).hexdigest()
        objects[digest] = payload
        matches = [row for row in bundle["artifacts"] if row["role"] == role]
        artifact_id = matches[0]["artifact_id"] if matches else f"recomputed:{role}"
        bundle["artifacts"] = [row for row in bundle["artifacts"] if row["role"] != role]
        bundle["artifacts"].append({"artifact_id": artifact_id, "role": role, "schema_id": doc["schema"], "schema_revision": doc["schema_revision"], "content_sha256": doc["content_sha256"], "object_sha256": digest, "size_bytes": len(payload), "media_type": "application/json", "availability": "embedded_public"})
    bundle["artifacts"].sort(key=lambda row: row["artifact_id"])
    bundle = with_content_sha256(bundle)
    submission = original.submission.to_dict()
    submission["claims"]["exact_ranks"] = bundle["result_card"]["rank_observations"]["exact_ranks"]
    descriptor = dict(original.descriptor)
    available_slices = {"overall", *bundle["result_card"]["slice_metrics"]}
    descriptor["evaluation"]["slices"] = [{"slice_id": name, "definition_sha256": hashlib.sha256((protocol["slice_definition"] + ":" + name).encode()).hexdigest()} for name in sorted(available_slices)]
    descriptor = with_content_sha256(descriptor)
    report = json.loads(json.dumps(original.conformance_report))
    old_descriptor_hash = report["descriptor_binding"]["content_sha256"]
    report["descriptor_binding"]["content_sha256"] = descriptor["content_sha256"]
    # Update only descriptor bindings; the original gate declarations stay declared.
    def replace_binding(value):
        if isinstance(value, dict):
            return {key: replace_binding(child) for key, child in value.items()}
        if isinstance(value, list):
            return [replace_binding(child) for child in value]
        return descriptor["content_sha256"] if value == old_descriptor_hash else value
    report = with_content_sha256(replace_binding(report))
    report_bytes = canonical_json_bytes(report) + b"\n"
    report_object_hash = hashlib.sha256(report_bytes).hexdigest()
    objects[report_object_hash] = report_bytes
    bundle["profile_binding"]["conformance_report_sha256"] = report["content_sha256"]
    for row in bundle["artifacts"]:
        if row["role"] == "conformance" and row["content_sha256"] == original.conformance_report["content_sha256"]:
            row["content_sha256"] = report["content_sha256"]
            row["object_sha256"] = report_object_hash
            row["size_bytes"] = len(report_bytes)
    bundle = with_content_sha256(bundle)
    package_documents = {"dataset_profile_descriptor": descriptor, "profile_conformance_report": report, "evidence_bundle": bundle}
    files = {}
    rows = []
    for role, doc in package_documents.items():
        path = f"{role}.json"
        payload = canonical_json_bytes(doc) + b"\n"
        files[path] = payload
        rows.append({"artifact_id": role, "role": role, "path": path, "sha256": hashlib.sha256(payload).hexdigest()})
    for row in bundle["artifacts"]:
        if row["availability"] == "embedded_public":
            digest = row["object_sha256"]
            path = f"objects/{digest}.json"
            if any(existing["sha256"] == digest for existing in rows):
                continue
            files[path] = objects[digest]
            rows.append({"artifact_id": f"object:{digest}", "role": "evidence_object", "path": path, "sha256": digest})
    submission["artifacts"] = sorted(rows, key=lambda row: row["artifact_id"])
    files["submission.json"] = canonical_json_bytes(with_content_sha256(submission)) + b"\n"
    output.mkdir(parents=True, exist_ok=False)
    for relative, payload in files.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(payload)
    return check_submission(output).to_dict()


def main() -> int:
    import argparse
    from .checker import _bounded_read, _check_json_depth
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    def read_input(path, role):
        payload = _bounded_read(path, role)
        _check_json_depth(payload, role)
        return json.loads(payload)
    try:
        result = build_recomputed_submission(args.source, args.output,
            trace=read_input(args.trace, "trace"),
            selection=read_input(args.selection, "selection"))
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "rejected", "code": getattr(error, "code", type(error).__name__), "detail": str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "accepted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
