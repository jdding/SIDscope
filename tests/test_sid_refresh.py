import copy
import json
from collections import defaultdict

import pytest

from sidscope.refresh import bind_evaluation, compare_snapshots, main, write_report
from sidscope.workflows import LocalInputBudget, WorkflowError, evaluate


def snapshot(mapping, *, semantics="ordered_prefix", sid_namespace="sid-old"):
    return {"dataset":"toy", "item_namespace":"items", "sid_namespace":sid_namespace,
        "semantics":semantics, "mapping":[{"item_id":item,"sid":sid} for item,sid in mapping]}


def naive_affected(old, new, depth=None):
    common=set(old)&set(new); result=set()
    def key(value): return tuple(value if depth is None else value[:depth])
    for item in common:
        if {other for other in common if key(old[other])==key(old[item])} != {other for other in common if key(new[other])==key(new[item])}:
            result.add(item)
    return result


def test_pure_renumbering_is_not_structural_change():
    old=snapshot([(1,[0,0]),(2,[0,0]),(3,[1,0])])
    new=snapshot([(1,[7,5]),(2,[7,5]),(3,[8,5])],sid_namespace="sid-new")
    report=compare_snapshots(old,new)
    assert report["classification"]["classification"]=="consistent_with_namespace_relabel_on_common_items"
    assert report["classification"]["literal_changed_items"]==3
    assert all(row["affected_items"]==0 for row in report["structural_change"])


def test_split_merge_add_remove_and_pseudonymous_examples():
    old=snapshot([(1,[0]),(2,[0]),(3,[1]),(5,[2])])
    new=snapshot([(1,[0]),(2,[2]),(3,[2]),(4,[3])])
    report=compare_snapshots(old,new,max_examples=1)
    full=report["structural_change"][-1]
    assert report["population"]=={"old_items":4,"new_items":4,"common_items":3,"added_items":1,"removed_items":1}
    assert full["affected_items"]==3 and full["split_groups"]==1 and full["merge_groups"]==1
    assert report["omitted_examples"]["structural_change"]==2
    assert "item_id" not in json.dumps(report["examples"])


def test_partition_algorithm_matches_naive_oracle():
    for seed in range(20):
        old={i:[(i*7+seed)%4,(i+seed)%3] for i in range(17)}
        new={i:[(i*5+seed)%4,(i+2*seed)%3] for i in range(17)}
        report=compare_snapshots(snapshot(list(old.items())),snapshot(list(new.items()),sid_namespace="new"))
        for row in report["structural_change"]:
            assert row["affected_items"]==len(naive_affected(old,new,row["depth"]))


def test_empty_disjoint_width_and_unordered_representation():
    empty=compare_snapshots(snapshot([]),snapshot([]))
    assert empty["raw_churn"]["status"]=="unavailable"
    assert empty["structural_change"][-1]["affected_rate_common"] is None
    disjoint=compare_snapshots(snapshot([(1,[0])]),snapshot([(2,[1])],sid_namespace="new"))
    assert disjoint["classification"]["classification"]=="unavailable_no_common_items"
    width=compare_snapshots(snapshot([(1,[0])]),snapshot([(1,[0,1])],sid_namespace="new"))
    assert width["classification"]["classification"]=="width_changed"
    unordered=compare_snapshots(snapshot([(1,[1,2]),(2,[3])],semantics="unordered_set"),
        snapshot([(1,[2,1]),(2,[3])],semantics="unordered_set",sid_namespace="new"))
    assert unordered["classification"]["classification"]=="representation_only"
    assert unordered["raw_churn"]["levels"][0]["representation_only_items"]==1


def test_parallel_positions_are_position_aware_without_prefix_inference():
    old=snapshot([(1,[0,0]),(2,[0,0]),(3,[1,0])],semantics="parallel_positions")
    new=snapshot([(1,[7,5]),(2,[7,5]),(3,[8,5])],semantics="parallel_positions",sid_namespace="new")
    report=compare_snapshots(old,new)
    assert [row["scope"] for row in report["structural_change"]]==["full_code"]
    assert report["raw_churn"]["status"]=="computed_parallel_full_code"
    assert report["classification"]["classification"]=="consistent_with_namespace_relabel_on_common_items"


@pytest.mark.parametrize("mutate,code",[
    (lambda s:s["mapping"].append({"item_id":1,"sid":[2]}),"duplicate_mapping_item"),
    (lambda s:s["mapping"][0].update(item_id=True),"normalized_item_required"),
    (lambda s:s["mapping"][0].update(sid=[0,-1]),"normalized_item_required"),
    (lambda s:s.update(semantics="invented"),"unsupported_sid_semantics"),
    (lambda s:s["mapping"][0].update(sid=[0,0]),"duplicate_unordered_sid_token"),
])
def test_typed_snapshot_failures(mutate,code):
    source=snapshot([(1,[0,1])],semantics="unordered_set"); mutate(source)
    with pytest.raises(WorkflowError) as caught: compare_snapshots(source,source)
    assert caught.value.code==code


def evaluation(mapping, changed=False):
    targets=[{"episode_id":"a","target_item_id":1,"slice":"cold"},{"episode_id":"b","target_item_id":2,"slice":"warm"}]
    predictions=[{"episode_id":"a","ranked_items":[1]},{"episode_id":"b","ranked_items":[None if changed else 2]}]
    return evaluate(predictions,targets,dataset=mapping["dataset"],cutoff=1)


def test_downstream_binding_and_category_effects():
    old=snapshot([(1,[0]),(2,[0]),(3,[1])]); new=snapshot([(1,[0]),(2,[1]),(3,[1])],sid_namespace="new")
    old_report,new_report=evaluation(old),evaluation(new,True)
    downstream={"old":bind_evaluation(old,old_report),"new":bind_evaluation(new,new_report)}
    report=compare_snapshots(old,new,downstream=downstream)
    assert report["downstream"]["overall_delta"]["hit_at_cutoff"]==-0.5
    assert report["downstream"]["target_lifecycle_groups"]["structural_change"]["status"]=="computed"
    assert "not a causal" in report["downstream"]["interpretation"]


def test_tampered_stale_and_protocol_bindings_fail():
    old=snapshot([(1,[0]),(2,[1])]); report=evaluation(old); binding=bind_evaluation(old,report)
    tampered=copy.deepcopy(binding); tampered["snapshot_sha256"]="0"*64
    for change,code in [({"old":tampered,"new":binding},"refresh_evaluation_binding_mismatch")]:
        with pytest.raises(WorkflowError) as caught: compare_snapshots(old,old,downstream=change)
        assert caught.value.code==code
    bad=copy.deepcopy(old); bad["mapping"].pop()
    with pytest.raises(WorkflowError) as caught: bind_evaluation(bad,report)
    assert caught.value.code=="refresh_evaluation_catalog_mismatch"
    other=evaluate(report["inputs"]["predictions"],report["inputs"]["targets"],dataset="other",cutoff=1)
    with pytest.raises(WorkflowError) as caught: bind_evaluation(old,other)
    assert caught.value.code=="refresh_evaluation_dataset_mismatch"


def test_purity_budget_write_and_cli_parity(tmp_path):
    old=snapshot([(1,[0]),(2,[1])]); new=snapshot([(1,[0]),(2,[2])],sid_namespace="new")
    before=json.dumps([old,new],sort_keys=True); expected=compare_snapshots(old,new)
    assert json.dumps([old,new],sort_keys=True)==before
    with pytest.raises(WorkflowError) as caught: compare_snapshots(old,new,budget=LocalInputBudget(max_rows=1))
    assert caught.value.code=="workflow_row_budget"
    output=tmp_path/"api"; write_report(output,old,new)
    assert (output/"complete.json").is_file() and json.loads((output/"report.json").read_text())==expected
    with pytest.raises(FileExistsError): write_report(output,old,new)
    old_path,new_path=tmp_path/"old.json",tmp_path/"new.json"
    old_path.write_text(json.dumps(old)); new_path.write_text(json.dumps(new))
    cli=tmp_path/"cli"; assert main(["compare","--old",str(old_path),"--new",str(new_path),"--output",str(cli)])==0
    assert json.loads((cli/"report.json").read_text())==expected
