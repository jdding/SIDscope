"""Stable ``sidscope`` command facade over versioned core contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib import metadata
from pathlib import Path
from typing import Any, Mapping, Sequence

from sidinspector.contracts import (
    ContractRegistryError,
    DatasetIdentityValidationError,
    PreparedDatasetValidationError,
    ReportContractValidationError,
    RuntimeContractValidationError,
    SIDSpaceIdentityValidationError,
    SourceIdentityValidationError,
    load_contract_registry,
    load_episode_selection,
    load_registered_contract,
)
from sidinspector.conformance_core import load_conformance_report
from sidinspector.conformance_core import (
    ProfileEngineError,
    ProfileCompositionError,
    composed_profile_document,
    load_dataset_profile_descriptor,
    load_profile_catalog,
    load_profile_conformance_report,
    load_profile_registry,
)
from sidinspector.adapters_core import (
    AdapterPluginError,
    discover_adapter_plugins,
    preflight_adapter_plugin,
)
from sidinspector.evaluation import diagnostic_report_document, validate_diagnostic_report
from sidinspector.evidence import (
    EvidenceBundleValidationError,
    EvidenceRegistry,
    EvidenceRegistryError,
    ObjectStore,
    build_evidence_bundle,
    build_evidence_index,
    compare_evidence_bundles,
    load_evidence_bundle,
)
from sidinspector.sdk import ADAPTER_SDK_VERSION, AdapterSDKError, load_adapter_capabilities
from sidinspector.submission import (
    SubmissionValidationError,
    canonical_index_bytes,
    check_submission,
    generate_submission_indexes,
    validate_submission_package,
)
from sidinspector.trace import (
    NativePayloadValidationError,
    load_native_payload,
    load_native_payload_registry,
    load_trace_envelope,
)


VALIDATION_REPORT_SCHEMA = "sidscope.contract_validation.v1"
REGISTRY_LISTING_SCHEMA = "sidscope.contract_registry_listing.v1"
REGISTRY_ENTRY_SCHEMA = "sidscope.contract_registry_entry.v1"


def package_version() -> str:
    try:
        return metadata.version("sidinspector")
    except metadata.PackageNotFoundError:
        return "1.5.0.dev0+source"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sidscope")
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    commands = parser.add_subparsers(dest="command", required=True)

    adapter = commands.add_parser("adapter", help="inspect adapter SDK declarations")
    adapter_commands = adapter.add_subparsers(dest="adapter_command", required=True)
    preflight = adapter_commands.add_parser("preflight", help="validate capabilities")
    preflight.add_argument("--descriptor", required=True, type=Path)
    preflight.add_argument("--result-json", type=Path, default=None)

    plugin = commands.add_parser("plugin", help="discover external adapter plugins")
    plugin_commands = plugin.add_subparsers(dest="plugin_command", required=True)
    plugin_list = plugin_commands.add_parser("list", help="list entry points without loading them")
    plugin_list.add_argument("--result-json", type=Path, default=None)
    plugin_preflight = plugin_commands.add_parser("preflight", help="load and validate one plugin")
    plugin_preflight.add_argument("--name", required=True)
    plugin_preflight.add_argument("--result-json", type=Path, default=None)

    contract = commands.add_parser("contract", help="inspect and validate canonical contracts")
    contract_commands = contract.add_subparsers(dest="contract_command", required=True)
    listing = contract_commands.add_parser("list", help="list registered contracts")
    listing.add_argument("--result-json", type=Path, default=None)
    show = contract_commands.add_parser("show", help="show one registered contract")
    show.add_argument("--type", required=True)
    show.add_argument("--result-json", type=Path, default=None)
    validate = contract_commands.add_parser("validate", help="validate one contract")
    validate.add_argument("--type", required=True)
    validate.add_argument("--input", required=True, type=Path)
    validate.add_argument("--result-json", type=Path, default=None)

    trace = commands.add_parser("trace", help="validate a canonical trace envelope")
    trace_commands = trace.add_subparsers(dest="trace_command", required=True)
    trace_validate = trace_commands.add_parser("validate")
    trace_validate.add_argument("--input", required=True, type=Path)
    trace_validate.add_argument("--result-json", type=Path, default=None)
    payload = trace_commands.add_parser("payload", help="inspect native payload contracts")
    payload_commands = payload.add_subparsers(dest="payload_command", required=True)
    payload_list = payload_commands.add_parser("list")
    payload_list.add_argument("--result-json", type=Path, default=None)
    payload_validate = payload_commands.add_parser("validate")
    payload_validate.add_argument("--input", required=True, type=Path)
    payload_validate.add_argument("--result-json", type=Path, default=None)

    evaluate = commands.add_parser("evaluate", help="derive a canonical diagnostic report")
    evaluate.add_argument("--trace", required=True, type=Path)
    evaluate.add_argument("--selection", required=True, type=Path)
    evaluate.add_argument("--evaluation-cutoff", type=int, default=10)
    evaluate.add_argument("--publication-depth", type=int, default=100)
    evaluate.add_argument("--output", required=True, type=Path)

    verify = commands.add_parser("verify", help="validate a canonical conformance report")
    verify.add_argument("--report", required=True, type=Path)
    verify.add_argument("--result-json", type=Path, default=None)

    evidence = commands.add_parser("evidence", help="build indexes and immutable bundles")
    evidence_commands = evidence.add_subparsers(dest="evidence_command", required=True)
    package = evidence_commands.add_parser("package", help="package artifact dependencies")
    package.add_argument("--artifact", action="append", required=True, type=Path)
    package.add_argument("--index-id", required=True)
    package.add_argument("--output", required=True, type=Path)
    bundle = evidence_commands.add_parser("bundle", help="build or verify EvidenceBundle v1")
    bundle_commands = bundle.add_subparsers(dest="bundle_command", required=True)
    bundle_build = bundle_commands.add_parser("build")
    bundle_build.add_argument("--spec", required=True, type=Path)
    bundle_build.add_argument("--output", required=True, type=Path)
    bundle_verify = bundle_commands.add_parser("verify")
    bundle_verify.add_argument("--input", required=True, type=Path)
    bundle_verify.add_argument("--result-json", type=Path, default=None)

    registry = commands.add_parser("registry", help="manage the derived evidence registry")
    registry_commands = registry.add_subparsers(dest="registry_command", required=True)
    for name in ("add", "import"):
        command = registry_commands.add_parser(name)
        command.add_argument("--store", required=True, type=Path)
        command.add_argument("--bundle", action="append", required=True, type=Path)
        command.add_argument(
            "--artifact",
            action="append",
            default=[],
            metavar="SHA256=PATH",
            help="supply one embedded public artifact",
        )
        command.add_argument("--result-json", type=Path, default=None)
    registry_list = registry_commands.add_parser("list")
    registry_list.add_argument("--store", required=True, type=Path)
    registry_list.add_argument("--result-json", type=Path, default=None)
    registry_show = registry_commands.add_parser("show")
    registry_show.add_argument("--store", required=True, type=Path)
    registry_show.add_argument("--sha256", required=True)
    registry_show.add_argument("--result-json", type=Path, default=None)
    registry_compare = registry_commands.add_parser("compare")
    registry_compare.add_argument("--store", required=True, type=Path)
    registry_compare.add_argument("--left", required=True)
    registry_compare.add_argument("--right", required=True)
    registry_compare.add_argument("--result-json", type=Path, default=None)
    registry_supersede = registry_commands.add_parser("supersede")
    registry_supersede.add_argument("--store", required=True, type=Path)
    registry_supersede.add_argument("--prior", required=True)
    registry_supersede.add_argument("--bundle", required=True, type=Path)
    registry_supersede.add_argument(
        "--artifact", action="append", default=[], metavar="SHA256=PATH"
    )
    registry_supersede.add_argument("--result-json", type=Path, default=None)
    registry_export = registry_commands.add_parser("export")
    registry_export.add_argument("--store", required=True, type=Path)
    registry_export.add_argument("--output", required=True, type=Path)
    registry_rebuild = registry_commands.add_parser("rebuild")
    registry_rebuild.add_argument("--store", required=True, type=Path)
    registry_rebuild.add_argument("--result-json", type=Path, default=None)
    registry_quarantine = registry_commands.add_parser("quarantine")
    registry_quarantine.add_argument("--store", required=True, type=Path)
    registry_quarantine.add_argument("--sha256", required=True)
    registry_quarantine.add_argument("--reason", required=True)
    registry_quarantine.add_argument("--result-json", type=Path, default=None)

    profile = commands.add_parser("profile", help="inspect and compose conformance profiles")
    profile_commands = profile.add_subparsers(dest="profile_command", required=True)
    profile_list = profile_commands.add_parser("list")
    profile_list.add_argument("--result-json", type=Path, default=None)
    profile_compose = profile_commands.add_parser("compose")
    profile_compose.add_argument("--profile", action="append", required=True)
    profile_compose.add_argument("--result-json", type=Path, default=None)
    profile_catalog = profile_commands.add_parser(
        "catalog", help="list governed 1.5 admission profiles"
    )
    profile_catalog.add_argument("--result-json", type=Path, default=None)
    profile_verify = profile_commands.add_parser(
        "verify", help="validate a dataset descriptor and profile report"
    )
    profile_verify.add_argument("--descriptor", required=True, type=Path)
    profile_verify.add_argument("--report", required=True, type=Path)
    profile_verify.add_argument("--result-json", type=Path, default=None)

    submission = commands.add_parser(
        "submission", help="check portable evidence submissions and derive views"
    )
    submission_commands = submission.add_subparsers(
        dest="submission_command", required=True
    )
    submission_check = submission_commands.add_parser("check")
    submission_check.add_argument("--root", required=True, type=Path)
    submission_check.add_argument("--manifest", default="submission.json")
    submission_check.add_argument("--result-json", type=Path, default=None)
    submission_indexes = submission_commands.add_parser("indexes")
    submission_indexes.add_argument("--root", action="append", required=True, type=Path)
    submission_indexes.add_argument("--manifest", default="submission.json")
    submission_indexes.add_argument("--status-output", required=True, type=Path)
    submission_indexes.add_argument("--result-output", required=True, type=Path)
    submission_indexes.add_argument("--result-json", type=Path, default=None)
    return parser


def _write_result(result: dict[str, object], result_json: Path | None) -> None:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if result_json is not None:
        result_json.parent.mkdir(parents=True, exist_ok=True)
        result_json.write_text(payload, encoding="utf-8")
    print(payload, end="")


def _failure_result(command: str, exc: Exception) -> dict[str, object]:
    return {
        "schema": VALIDATION_REPORT_SCHEMA,
        "status": "fail",
        "command": command,
        "failure": {
            "code": getattr(exc, "code", "input_error"),
            "detail": getattr(exc, "detail", f"{type(exc).__name__}: {exc}"),
        },
    }


def _write_artifact(document: Mapping[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _adapter_preflight(args: argparse.Namespace) -> int:
    try:
        capabilities = load_adapter_capabilities(args.descriptor)
        result = {
            "schema": "sidscope.adapter_preflight.v1",
            "status": "pass",
            "adapter_id": capabilities.adapter_id,
            "sdk_version": ADAPTER_SDK_VERSION,
            "method_family": capabilities.method_family,
            "contract_types": list(capabilities.contract_types),
            "failure": None,
        }
        code = 0
    except (AdapterSDKError, ContractRegistryError, OSError, json.JSONDecodeError) as exc:
        result = _failure_result("adapter preflight", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _plugin_command(args: argparse.Namespace) -> int:
    try:
        if args.plugin_command == "list":
            plugins = discover_adapter_plugins()
            result = {
                "schema": "sidscope.adapter_plugin_listing.v1",
                "status": "pass",
                "entry_point_group": "sidscope.adapters",
                "plugins": [
                    {"name": item.name, "value": item.value, "distribution": item.distribution}
                    for item in plugins
                ],
                "failure": None,
            }
        else:
            preflight = preflight_adapter_plugin(args.name)
            result = {
                "schema": "sidscope.adapter_plugin_preflight.v1",
                "status": "pass",
                "plugin": {
                    "name": preflight.plugin.name,
                    "value": preflight.plugin.value,
                    "distribution": preflight.plugin.distribution,
                },
                "adapter_id": preflight.capabilities.adapter_id,
                "method_family": preflight.capabilities.method_family,
                "payload_schema": preflight.payload.schema,
                "payload_sha256": preflight.payload.content_sha256,
                "failure": None,
            }
        code = 0
    except AdapterPluginError as exc:
        result = _failure_result(f"plugin {args.plugin_command}", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _trace_validate(args: argparse.Namespace) -> int:
    try:
        trace = load_trace_envelope(args.input)
        result = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "pass",
            "contract_type": "trace-envelope",
            "trace_envelope_id": trace.artifact_id,
            "content_sha256": trace.content_sha256,
            "input_file_sha256": _file_sha256(args.input),
            "failure": None,
        }
        code = 0
    except (RuntimeContractValidationError, OSError, json.JSONDecodeError) as exc:
        result = _failure_result("trace validate", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _trace_payload_command(args: argparse.Namespace) -> int:
    try:
        if args.payload_command == "list":
            descriptors = load_native_payload_registry()
            result = {
                "schema": "sidscope.trace_payload_registry_listing.v1",
                "status": "pass",
                "payload_contracts": [
                    {
                        "method_family": item.method_family,
                        "schema_id": item.schema_id,
                        "schema_revision": item.schema_revision,
                    }
                    for item in descriptors
                ],
                "failure": None,
            }
        else:
            payload = load_native_payload(args.input)
            result = {
                "schema": "sidscope.native_payload_validation.v1",
                "status": "pass",
                "payload_id": payload.payload_id,
                "payload_schema": payload.schema,
                "method_family": payload.method_family,
                "content_sha256": payload.content_sha256,
                "failure": None,
            }
        code = 0
    except (NativePayloadValidationError, OSError, json.JSONDecodeError) as exc:
        result = _failure_result("trace payload", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _profile_command(args: argparse.Namespace) -> int:
    try:
        if args.profile_command == "list":
            profiles = load_profile_registry()
            result = {
                "schema": "sidscope.conformance_profile_listing.v1",
                "status": "pass",
                "profiles": [
                    {
                        "profile_id": item.profile_id,
                        "revision": item.revision,
                        "extends": list(item.extends),
                        "method_family": item.method_family,
                    }
                    for item in profiles
                ],
                "failure": None,
            }
        elif args.profile_command == "compose":
            result = composed_profile_document(args.profile)
            result["failure"] = None
        elif args.profile_command == "catalog":
            profiles = load_profile_catalog()
            result = {
                "schema": "sidscope.conformance_profile_catalog_listing.v1",
                "status": "pass",
                "profiles": [
                    {
                        "profile_id": item.profile_id,
                        "revision": item.revision,
                        "profile_kind": item.profile_kind,
                        "owner": item.owner,
                        "lifecycle_status": item.lifecycle["status"],
                        "status_label_policy": dict(item.status_label_policy),
                    }
                    for item in profiles
                ],
                "failure": None,
            }
        elif args.profile_command == "verify":
            descriptor = load_dataset_profile_descriptor(args.descriptor)
            report = load_profile_conformance_report(args.report, descriptor=descriptor)
            result = {
                "schema": "sidscope.profile_conformance_validation.v1",
                "status": "pass",
                "descriptor_id": descriptor.descriptor_id,
                "descriptor_sha256": descriptor.content_sha256,
                "report_id": report.report_id,
                "report_sha256": report.content_sha256,
                "profile_id": report.profile_id,
                "profile_revision": report.profile_revision,
                "decision_status": report.decision_status,
                "status_label": report.status_label,
                "failure": None,
            }
        else:
            raise AssertionError("unreachable profile command")
        code = 0
    except (
        ProfileCompositionError,
        ProfileEngineError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        result = _failure_result(f"profile {args.profile_command}", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _submission_command(args: argparse.Namespace) -> int:
    if args.submission_command == "check":
        report = check_submission(args.root, manifest_path=args.manifest)
        result = report.to_dict()
        _write_result(result, args.result_json)
        return 0 if report.status == "accepted" else 2
    try:
        submissions = [
            validate_submission_package(root, manifest_path=args.manifest)
            for root in args.root
        ]
        status_index, result_index = generate_submission_indexes(submissions)
        args.status_output.parent.mkdir(parents=True, exist_ok=True)
        args.result_output.parent.mkdir(parents=True, exist_ok=True)
        args.status_output.write_bytes(canonical_index_bytes(status_index))
        args.result_output.write_bytes(canonical_index_bytes(result_index))
        result = {
            "schema": "sidscope.submission_index_export.v1",
            "status": "pass",
            "submission_count": len(submissions),
            "status_index_sha256": status_index["content_sha256"],
            "result_index_sha256": result_index["content_sha256"],
            "failure": None,
        }
        code = 0
    except (SubmissionValidationError, OSError, json.JSONDecodeError) as exc:
        result = _failure_result("submission indexes", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _evaluate(args: argparse.Namespace) -> int:
    try:
        trace = load_trace_envelope(args.trace)
        selection = load_episode_selection(args.selection)
        if trace.to_dict()["episode_selection_binding"]["content_sha256"] != selection.content_sha256:
            raise RuntimeContractValidationError(
                "trace_selection_binding_mismatch", selection.content_sha256
            )
        selected = [row["episode_id"] for row in selection.to_dict()["rows"]]
        observed = [row["episode_id"] for row in trace.to_dict()["observations"]]
        if selected != observed:
            raise RuntimeContractValidationError("trace_selection_episode_mismatch", str(observed))
        document = diagnostic_report_document(
            trace,
            selection,
            evaluation_cutoff=args.evaluation_cutoff,
            publication_depth=args.publication_depth,
        )
        validate_diagnostic_report(document)
        _write_artifact(document, args.output)
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0
    except (
        RuntimeContractValidationError,
        ReportContractValidationError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        _write_result(_failure_result("evaluate", exc), None)
        return 2


def _verify(args: argparse.Namespace) -> int:
    try:
        report = load_conformance_report(args.report)
        result = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "pass",
            "contract_type": "conformance-report",
            "conformance_report_id": report.artifact_id,
            "content_sha256": report.content_sha256,
            "input_file_sha256": _file_sha256(args.report),
            "failure": None,
        }
        code = 0
    except (ReportContractValidationError, OSError, json.JSONDecodeError) as exc:
        result = _failure_result("verify", exc)
        code = 2
    _write_result(result, args.result_json)
    return code


def _evidence_package(args: argparse.Namespace) -> int:
    try:
        document = build_evidence_index(args.artifact, index_id=args.index_id)
        _write_artifact(document, args.output)
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0
    except (
        ContractRegistryError,
        DatasetIdentityValidationError,
        PreparedDatasetValidationError,
        ReportContractValidationError,
        RuntimeContractValidationError,
        SIDSpaceIdentityValidationError,
        SourceIdentityValidationError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        _write_result(_failure_result("evidence package", exc), None)
        return 2


def _evidence_bundle(args: argparse.Namespace) -> int:
    try:
        if args.bundle_command == "build":
            spec = json.loads(args.spec.read_text(encoding="utf-8"))
            if not isinstance(spec, Mapping):
                raise EvidenceBundleValidationError("invalid_type", "bundle spec")
            document = build_evidence_bundle(**dict(spec)).to_dict()
            _write_artifact(document, args.output)
            print(json.dumps(document, indent=2, sort_keys=True))
            return 0
        bundle = load_evidence_bundle(args.input)
        result = {
            "schema": "sidscope.evidence_bundle_validation.v1",
            "status": "pass",
            "bundle_id": bundle.bundle_id,
            "content_sha256": bundle.content_sha256,
            "artifact_count": len(bundle.artifacts),
            "supersedes": list(bundle.supersedes),
            "failure": None,
        }
        _write_result(result, args.result_json)
        return 0
    except (EvidenceBundleValidationError, OSError, json.JSONDecodeError, TypeError) as exc:
        result = _failure_result(f"evidence bundle {args.bundle_command}", exc)
        _write_result(result, getattr(args, "result_json", None))
        return 2


def _public_artifacts(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        digest, separator, raw_path = value.partition("=")
        if not separator or not digest or not raw_path:
            raise EvidenceBundleValidationError(
                "invalid_artifact_argument", "expected SHA256=PATH"
            )
        if digest in result:
            raise EvidenceBundleValidationError("duplicate_artifact_argument", digest)
        result[digest] = Path(raw_path)
    return result


def _order_bundles_for_admission(store: ObjectStore, bundles: Sequence[Any]) -> list[Any]:
    available = {bundle.content_sha256 for bundle in store.iter_bundles()}
    remaining = {bundle.content_sha256: bundle for bundle in bundles}
    ordered: list[Any] = []
    while remaining:
        ready = sorted(
            digest
            for digest, bundle in remaining.items()
            if set(bundle.supersedes) <= available
        )
        if not ready:
            referenced = {
                predecessor
                for bundle in remaining.values()
                for predecessor in bundle.supersedes
            }
            missing = sorted(referenced - available - set(remaining))
            code = "missing_superseded_bundle" if missing else "supersession_cycle"
            raise EvidenceBundleValidationError(code, ",".join(missing or sorted(remaining)))
        for digest in ready:
            ordered.append(remaining.pop(digest))
            available.add(digest)
    return ordered


def _registry_command(args: argparse.Namespace) -> int:
    store = ObjectStore(args.store)
    registry = EvidenceRegistry(args.store / "registry.sqlite3")
    try:
        command = args.registry_command
        if command in {"add", "import"}:
            supplied = _public_artifacts(args.artifact)
            bundles = [load_evidence_bundle(path) for path in args.bundle]
            used_artifacts: set[str] = set()
            for bundle in _order_bundles_for_admission(store, bundles):
                embedded = {
                    str(row["object_sha256"])
                    for row in bundle.artifacts
                    if row["availability"] == "embedded_public"
                }
                selected = {digest: path for digest, path in supplied.items() if digest in embedded}
                used_artifacts.update(selected)
                store.admit_bundle(bundle, selected)
            unused = sorted(set(supplied) - used_artifacts)
            if unused:
                raise EvidenceBundleValidationError(
                    "unexpected_public_artifact", ",".join(unused)
                )
            if command == "import":
                registry.import_bundles(bundles)
            else:
                for bundle in bundles:
                    registry.add(bundle)
            result = {
                "schema": "sidscope.evidence_registry_operation.v1",
                "status": "pass",
                "operation": command,
                "bundle_sha256s": [bundle.content_sha256 for bundle in bundles],
                "failure": None,
            }
        elif command == "list":
            result = {
                "schema": "sidscope.evidence_registry_listing.v1",
                "status": "pass",
                "bundles": registry.list_bundles(),
                "failure": None,
            }
        elif command == "show":
            result = {
                "schema": "sidscope.evidence_registry_entry.v1",
                "status": "pass",
                "bundle": registry.show(args.sha256),
                "failure": None,
            }
        elif command == "compare":
            result = compare_evidence_bundles(
                registry.show(args.left), registry.show(args.right)
            )
        elif command == "supersede":
            bundle = load_evidence_bundle(args.bundle)
            if args.prior not in bundle.supersedes:
                raise EvidenceRegistryError(
                    "missing_supersession_declaration", args.prior
                )
            store.admit_bundle(bundle, _public_artifacts(args.artifact))
            registry.add(bundle)
            result = {
                "schema": "sidscope.evidence_registry_operation.v1",
                "status": "pass",
                "operation": "supersede",
                "prior_bundle_sha256": args.prior,
                "replacement_bundle_sha256": bundle.content_sha256,
                "failure": None,
            }
        elif command == "export":
            result = registry.export_static()
            _write_artifact(result, args.output)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        elif command == "rebuild":
            bundles = list(store.iter_bundles())
            quarantined = list(store.iter_quarantined_bundles())
            registry.rebuild([*bundles, *quarantined])
            for bundle in quarantined:
                registry.quarantine(bundle.content_sha256, reason="object_store_quarantine")
            result = {
                "schema": "sidscope.evidence_registry_operation.v1",
                "status": "pass",
                "operation": "rebuild",
                "bundle_count": len(bundles) + len(quarantined),
                "quarantined_bundle_count": len(quarantined),
                "failure": None,
            }
        elif command == "quarantine":
            registry.show(args.sha256)
            store.quarantine_bundle(args.sha256)
            registry.quarantine(args.sha256, reason=args.reason)
            result = {
                "schema": "sidscope.evidence_registry_operation.v1",
                "status": "pass",
                "operation": "quarantine",
                "bundle_sha256": args.sha256,
                "failure": None,
            }
        else:
            raise AssertionError("unreachable registry command")
        _write_result(result, getattr(args, "result_json", None))
        return 0
    except (
        EvidenceBundleValidationError,
        EvidenceRegistryError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        _write_result(
            _failure_result(f"registry {args.registry_command}", exc),
            getattr(args, "result_json", None),
        )
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "adapter":
        return _adapter_preflight(args)
    if args.command == "plugin":
        return _plugin_command(args)
    if args.command == "trace":
        if args.trace_command == "payload":
            return _trace_payload_command(args)
        return _trace_validate(args)
    if args.command == "evaluate":
        return _evaluate(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "evidence":
        if args.evidence_command == "bundle":
            return _evidence_bundle(args)
        return _evidence_package(args)
    if args.command == "registry":
        return _registry_command(args)
    if args.command == "profile":
        return _profile_command(args)
    if args.command == "submission":
        return _submission_command(args)
    if args.command != "contract":
        raise AssertionError("unreachable argparse command")

    try:
        registry = load_contract_registry()
        if args.contract_command == "list":
            result = {
                "schema": REGISTRY_LISTING_SCHEMA,
                "status": "pass",
                "registry_id": registry.registry_id,
                "registry_schema": registry.schema,
                "registry_content_sha256": registry.content_sha256,
                "contract_count": len(registry.contracts),
                "contracts": [
                    {
                        "contract_type": item.contract_type,
                        "schema_id": item.schema_id,
                        "schema_revision": item.schema_revision,
                        "owner": item.owner,
                    }
                    for item in registry.contracts
                ],
                "failure": None,
            }
            _write_result(result, args.result_json)
            return 0
        if args.contract_command == "show":
            descriptor = registry.by_type(args.type)
            result = {
                "schema": REGISTRY_ENTRY_SCHEMA,
                "status": "pass",
                "registry_id": registry.registry_id,
                "contract": descriptor.to_dict(),
                "failure": None,
            }
            _write_result(result, args.result_json)
            return 0
        if args.contract_command != "validate":
            raise AssertionError("unreachable argparse command")
    except ContractRegistryError as exc:
        result = {
            "schema": REGISTRY_ENTRY_SCHEMA,
            "status": "fail",
            "contract_type": getattr(args, "type", None),
            "failure": {"code": exc.code, "detail": exc.detail},
        }
        _write_result(result, getattr(args, "result_json", None))
        return 2

    try:
        descriptor, artifact = load_registered_contract(args.type, args.input)
        artifact_dict = artifact.to_dict()
        result: dict[str, object] = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "pass",
            "contract_type": args.type,
            "contract_schema": artifact.schema,
            "schema_revision": artifact.schema_revision,
            descriptor.result_id_field: artifact_dict[descriptor.result_id_field],
            "content_sha256": artifact.content_sha256,
            "input_file_sha256": _file_sha256(args.input),
            "failure": None,
        }
        exit_code = 0
    except (
        ContractRegistryError,
        DatasetIdentityValidationError,
        PreparedDatasetValidationError,
        ReportContractValidationError,
        RuntimeContractValidationError,
        SIDSpaceIdentityValidationError,
        SourceIdentityValidationError,
    ) as exc:
        code = getattr(exc, "code", "contract_validation_error")
        detail = getattr(exc, "detail", str(exc))
        result = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "fail",
            "contract_type": args.type,
            "failure": {"code": code, "detail": detail},
        }
        exit_code = 2
    except (OSError, json.JSONDecodeError) as exc:
        result = {
            "schema": VALIDATION_REPORT_SCHEMA,
            "status": "fail",
            "contract_type": args.type,
            "failure": {"code": "input_error", "detail": f"{type(exc).__name__}: {exc}"},
        }
        exit_code = 2

    _write_result(result, args.result_json)
    return exit_code
