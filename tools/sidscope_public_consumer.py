#!/usr/bin/env python3
"""Independent consumer: imports only documented sidscope surfaces.

Copy this file plus JSON inputs outside the checkout and run with python -I.
The signature contract is versioned separately; verification never regenerates it.
"""
import argparse
import hashlib
import inspect
import json
import re
import shutil
import tempfile
from pathlib import Path
import sidscope as api
from sidscope.workflows import LocalInputBudget, audit, evaluate, compare
from sidscope.mapping_check import preflight
from sidscope.pipeline import run as run_producer
from sidscope.regression import compare_runs
from sidscope.diagnostic_review import write_review
from sidscope.refresh import bind_evaluation, compare_snapshots, write_report as write_refresh_report


def signatures():
    result = {}
    for name in api.__all__:
        value = getattr(api, name)
        if callable(value):
            result[name] = [{"name": p.name, "kind": p.kind.name, "default": None if p.default is inspect.Parameter.empty else repr(p.default), "required": p.default is inspect.Parameter.empty} for p in inspect.signature(value).parameters.values()]
        else:
            result[name] = {"constant": value}
    return result


def verify(inputs: Path, contract: Path, *, installed: bool = False):
    if installed:
        assert "site-packages" in Path(api.__file__).resolve().parts
    expected = json.loads(contract.read_text())["signatures"]
    assert expected["__version__"] == {"constant": "1.7.0.dev0"}, "frozen consumer baseline drift"
    version = api.__version__
    assert version in {"1.7.0.dev0", "2.0.0"} or re.fullmatch(r"2\.0\.0rc[1-9][0-9]*", version), "unsupported consumer version"
    expected["__version__"] = {"constant": version}
    assert signatures() == expected, "public signature/default/constant drift"
    covered = {"ADAPTER_SDK_VERSION", "PLUGIN_API_VERSION", "__version__"}
    fixture = inputs / "canonical_pipeline_fixture"
    for name in api.__all__:
        if name.startswith("load_") and name not in {"load_native_payload", "load_evidence_bundle", "load_public_schema_catalog"}:
            path = fixture / (name[5:] + ".json")
            if name == "load_dataset_identity":
                path = inputs / "dataset_identity_fixture/dataset_identity.json"
            value = getattr(api, name)(path)
            assert api.verify_content_sha256(value.to_dict())
            api.validate_public_document(value.to_dict())
            covered.add(name)
    obj = api.with_content_sha256({"value": 1})
    assert api.verify_content_sha256(obj)
    assert api.canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
    assert api.canonical_sha256({"a": 1, "b": 2}) == hashlib.sha256(b'{"a":1,"b":2}').hexdigest()
    covered.update({"with_content_sha256", "verify_content_sha256", "canonical_json_bytes", "canonical_sha256", "validate_public_document"})
    for name in api.__all__:
        if name.endswith("Error"):
            error = getattr(api, name)("consumer_failure", "bounded detail")
            assert isinstance(error, ValueError) and error.code == "consumer_failure"
            covered.add(name)
    catalog = api.load_public_schema_catalog()
    assert catalog and isinstance(catalog[0], api.PublicSchemaDescriptor)
    assert api.get_public_schema_descriptor(catalog[0].schema_id).schema_id == catalog[0].schema_id
    covered.update({"load_public_schema_catalog", "PublicSchemaDescriptor", "get_public_schema_descriptor"})
    capabilities = api.load_adapter_capabilities(fixture / "adapter_capabilities.json")
    assert isinstance(api.validate_adapter_capabilities(capabilities.to_dict()), api.AdapterCapabilities)
    covered.update({"validate_adapter_capabilities", "AdapterCapabilities"})
    payload = api.load_native_payload(inputs / "native_trace_payload_fixtures/parallel_graph_token_set.json")
    assert api.validate_native_payload(payload.to_dict()).content_sha256 == payload.content_sha256
    covered.update({"load_native_payload", "validate_native_payload"})
    assert isinstance(api.discover_adapter_plugins(), tuple)
    try:
        api.preflight_adapter_plugin("consumer-nonexistent-plugin")
    except api.AdapterPluginError as error:
        assert error.code == "plugin_not_found"
    else:
        raise AssertionError("missing plugin accepted")
    assert hasattr(api.AdapterPlugin, "get_capabilities") and hasattr(api.AdapterPlugin, "get_payload_fixture")
    covered.update({"discover_adapter_plugins", "preflight_adapter_plugin", "AdapterPlugin"})
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        class Producer:
            def produce(self, contract_type, output_path):
                shutil.copyfile(fixture / "trace_envelope.json", output_path)
                return output_path
        harness = api.AdapterHarness(capabilities, Producer())
        assert harness.produce("trace-envelope", root / "trace.json").content_sha256
        try:
            harness.produce("undeclared", root / "unused.json")
        except api.AdapterSDKError as error:
            assert error.code == "undeclared_contract_capability"
        else:
            raise AssertionError("undeclared capability accepted")
        covered.add("AdapterHarness")
        evidence = inputs / "evidence_system_fixture"
        bundle = api.load_evidence_bundle(evidence / "baseline_bundle.json")
        assert api.validate_evidence_bundle(bundle.to_dict()).content_sha256 == bundle.content_sha256
        public = evidence / "public_conformance_summary.json"
        store = api.ObjectStore(root / "store")
        store.admit_bundle(bundle, {hashlib.sha256(public.read_bytes()).hexdigest(): public})
        registry = api.EvidenceRegistry(root / "registry.sqlite3")
        assert registry.add(bundle) == bundle.content_sha256
        assert registry.show(bundle.content_sha256)
        assert len(registry.list_bundles()) == 1
        assert api.compare_evidence_bundles(bundle, bundle)["status"] == "incompatible"
        covered.update({"load_evidence_bundle", "validate_evidence_bundle", "ObjectStore", "EvidenceRegistry", "compare_evidence_bundles"})
    result = api.check_submission(inputs / "conformance_ecosystem_fixture/submission/positive")
    assert result.status == "rejected" and result.failures[0]["code"] == "independent_gate_verification_required"
    covered.add("check_submission")
    assert covered == set(api.__all__), sorted(set(api.__all__) - covered)
    mapping = [{"item_id": 1, "sid": [0, 0]}, {"item_id": 2, "sid": [0, 0]}]
    assert audit(mapping)["findings"][0]["code"] == "sid_collision"
    result = evaluate([{"episode_id": "a", "ranked_items": [None, 2]}], [{"episode_id": "a", "target_item_id": 2, "slice": "cold"}], dataset="consumer", cutoff=2)
    assert result["records"][0]["rank"] == 2
    assert compare(result, result)["overall_delta"]["hit_at_cutoff"] == 0
    joined = preflight(mapping, dataset="installed-consumer",
        catalog=[{"item_id": 1}, {"item_id": 2}],
        splits=[{"episode_id": "a", "split": "test", "target_item_id": 2, "history_item_ids": [1]}],
        targets=[{"episode_id": "a", "split": "test", "target_item_id": 2, "sid": [0, 0]}],
        interactions=[{"normalized_user_id": 0, "item_id": i, "split": "train"} for i in (1, 2)])
    assert joined["checks"]["target_split"]["status"] == "pass"
    assert "D4_popularity" in joined["metrics"]
    # A synthetic installed producer exercises orchestration, not real adoption.
    with tempfile.TemporaryDirectory() as tmp:
        declared = inputs / "conformance_ecosystem_fixture/submission/positive"
        manifest = json.loads((declared / "submission.json").read_text())
        bundle_path = next(row["path"] for row in manifest["artifacts"] if row["role"] == "evidence_bundle")
        provenance = api.load_evidence_bundle(declared / bundle_path)
        class SyntheticInstalledProducer:
            calls = 0
            def get_capabilities(self):
                caps = capabilities.to_dict()
                caps["adapter_id"] = provenance.subject["adapter_id"]
                return api.with_content_sha256(caps)
            def produce(self, kind, output):
                assert kind == "trace-envelope"
                self.calls += 1
                document = json.loads((fixture / "trace_envelope.json").read_text())
                for binding, role in (("run_binding", "run"), ("checkpoint_binding", "checkpoint")):
                    document[binding]["content_sha256"] = next(row["content_sha256"] for row in provenance.artifacts if row["role"] == role)
                output.write_text(json.dumps(api.with_content_sha256(document)))
                return output
        producer = SyntheticInstalledProducer()
        first = Path(tmp) / "first"
        run_producer(producer, source=declared, selection=fixture / "episode_selection.json", output=first)
        completed = run_producer(producer, source=declared, selection=fixture / "episode_selection.json", baseline=first / "submission", output=Path(tmp) / "second")
        assert producer.calls == 2 and completed["comparison_kind"] == "baseline"
    # Exercise the new policy from installed distributions, outside the checkout.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "large-mapping.json"
        rows = [{"item_id": i, "sid": [i]} for i in range(10001)]
        path.write_text(json.dumps(rows) + " " * (8 * 1024 * 1024))
        expected = audit(rows)
        assert audit(path) == expected
        assert audit(path, budget=LocalInputBudget(max_rows=10001)) == expected
        for policy in (LocalInputBudget(max_rows=10000), LocalInputBudget(max_input_bytes=8 * 1024 * 1024)):
            try:
                audit(path, budget=policy)
            except ValueError as error:
                assert error.code in {"workflow_row_budget", "json_size_exceeded"}
            else:
                raise AssertionError("explicit local input budget ignored")
    labels=[{'episode_id':str(i),'target_item_id':i,'slice':'test'} for i in range(8)]
    arms=[]
    for arm in range(2):
        runs=[]
        for seed in range(4):
            report=evaluate([{'episode_id':str(i),'ranked_items':[i if not arm or (i+seed)%5==0 else None]} for i in range(8)],labels,dataset='installed-test',cutoff=1)
            runs.append({'run_id':f'{arm}-{seed}','pair_id':str(seed),'seed':seed,'controls':{'fixture':'synthetic-installed'},'report':report})
        arms.append(runs)
    spec={'left':arms[0],'right':arms[1],'clusters':{str(i):str(i) for i in range(8)},
        'degradation_budget':{'hit_at_cutoff':.05,'ndcg_at_cutoff':.05},'replicates':200}
    regression=compare_runs(**spec)
    assert regression['results'][0]['metrics']['hit_at_cutoff']['decision']=='regression'
    with tempfile.TemporaryDirectory() as tmp:
        review=Path(tmp)/'review'
        write_review(review,arms[1][0]['report'],baseline=arms[0][0]['report'],regression_spec=spec)
        assert (review/'index.html').is_file() and (review/'complete.json').is_file()
        old_snapshot={'dataset':'installed-test','item_namespace':'items','sid_namespace':'old','semantics':'ordered_prefix','mapping':[{'item_id':i,'sid':[i//2,i%2]} for i in range(8)]}
        new_snapshot={**old_snapshot,'sid_namespace':'new','mapping':[{'item_id':i,'sid':[10+i//2,20+i%2]} for i in range(8)]}
        binding=bind_evaluation(old_snapshot,arms[0][0]['report'])
        refresh=compare_snapshots(old_snapshot,new_snapshot,downstream={'old':binding,'new':bind_evaluation(new_snapshot,arms[1][0]['report'])})
        assert refresh['classification']['classification']=='consistent_with_namespace_relabel_on_common_items'
        refresh_output=Path(tmp)/'refresh'
        write_refresh_report(refresh_output,old_snapshot,new_snapshot)
        assert (refresh_output/'report.md').is_file() and (refresh_output/'complete.json').is_file()
    # The installable pure-data bridge runs without the evidence-full RPG
    # verifier resource; missing resources fail closed, never pass.
    import sidscope.native_bridge as native_bridge
    import sidscope.observed_review  # noqa: F401
    native_bridge.clear_native_verifier_provider()
    with tempfile.TemporaryDirectory() as tmp:
        rpg_like = Path(tmp) / 'rpg-like.json'
        rpg_like.write_text(json.dumps({'schema': 'sidscope.rpg_trained_trace_bundle.v1', 'method': 'RPG'}))
        try:
            native_bridge.project_export(rpg_like)
        except native_bridge.NativeBridgeError as error:
            assert error.code == 'native_verifier_unavailable', error.code
        else:
            raise AssertionError('missing evidence-full RPG verifier did not fail closed')
    return {"status": "pass", "curated_symbols_exercised": sorted(covered), "workflow_functions": ["audit", "evaluate", "compare", "compare_runs", "write_review", "compare_snapshots", "bind_evaluation", "write_refresh_report"], "native_bridge": ["sidscope.native_bridge", "sidscope.observed_review"], "installed": installed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.inputs, args.contract, installed=args.installed), sort_keys=True))


if __name__ == "__main__":
    main()
