"""Paired run/user-cluster regression over recomputed local evaluation reports.

An additive local API, not a new evidence admission level. Run/control/cluster
labels are supplied declarations; this module cannot authenticate experiments.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

from sidinspector.contracts import canonical_sha256, with_content_sha256, load_json
from sidinspector.evidence import scan_evidence_content
from sidscope.workflows import WorkflowError, evaluate, _name


def fail(code, detail):
    raise WorkflowError(code, detail)


def checked_report(report, *, budget=None):
    if not isinstance(report, dict) or report.get('kind') != 'evaluate':
        fail('evaluation_report_required', 'recomputable evaluate report required')
    try:
        rebuilt = evaluate(**report['inputs'], budget=budget)
    except (KeyError, TypeError) as error:
        fail('invalid_regression_report', str(error))
    if rebuilt != report:
        fail('workflow_report_recomputation_mismatch', 'report differs from inputs')
    return rebuilt


def _runs(values):
    if not isinstance(values, list) or not values:
        fail('missing_run', 'nonempty run list required')
    pairs, run_ids, seeds = {}, set(), set()
    for row in values:
        if not isinstance(row, dict) or set(row) != {'run_id', 'pair_id', 'seed', 'controls', 'report'}:
            fail('invalid_run_fields', 'run_id/pair_id/seed/controls/report required')
        run, pair = _name(row['run_id']), _name(row['pair_id'])
        if run in run_ids or pair in pairs:
            fail('duplicate_run', 'run and pair IDs must be unique within each arm')
        if type(row['seed']) is not int or row['seed'] < 0:
            fail('invalid_run_seed', 'nonnegative integer required')
        if row['seed'] in seeds:
            fail('duplicate_seed', 'one independent run per seed per arm required')
        if not isinstance(row['controls'], dict) or not row['controls']:
            fail('missing_experimental_controls', 'explicit frozen control declarations required')
        scan_evidence_content(row['controls'])
        canonical_sha256(row['controls'])
        checked_report(row['report'])
        pairs[pair] = row
        run_ids.add(run)
        seeds.add(row['seed'])
    return pairs


def _bootstrap(left, right, counts, *, replicates, rng, confidence):
    """Multinomial product bootstrap of a complete run x user-cluster array.

    Each cell contains sums, not user means: preserves episode-macro estimand
    even with unequal cluster sizes. The same weights pair both arms.
    """
    import numpy as np
    runs, users = left.shape
    values = np.empty(replicates)
    for i in range(replicates):
        rw = rng.multinomial(runs, np.full(runs, 1 / runs))
        uw = rng.multinomial(users, np.full(users, 1 / users))
        values[i] = (rw @ (right-left) @ uw) / (runs * (counts @ uw))
    alpha = (1-confidence)/2
    return [float(x) for x in np.quantile(values, [alpha, 1-alpha], method='linear')]


def compare_runs(left, right, *, clusters, degradation_budget, replicates=2000,
                 confidence=0.95, random_seed=0):
    """Return paired episode-macro Hit/NDCG effects and pointwise intervals.

    Complete matching is mandatory; never intersect cohorts or drop missing runs.
    Small/degenerate cells remain inconclusive, not a regression-budget PASS.
    """
    import numpy as np
    if type(replicates) is not int or replicates < 200:
        fail('invalid_bootstrap_replicates', 'at least 200 replicates required')
    if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 < confidence < 1:
        fail('invalid_confidence', 'finite value strictly between zero and one required')
    if type(random_seed) is not int or random_seed < 0:
        fail('invalid_bootstrap_seed', 'nonnegative integer required')
    metrics = ('hit_at_cutoff', 'ndcg_at_cutoff')
    if not isinstance(degradation_budget, dict) or set(degradation_budget) != set(metrics):
        fail('invalid_degradation_budget', 'explicit absolute budgets for Hit and NDCG required')
    for value in degradation_budget.values():
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            fail('invalid_degradation_budget', 'finite nonnegative absolute budgets required')
    a, b = _runs(left), _runs(right)
    if set(a) != set(b):
        fail('missing_paired_run', 'both arms must contain exactly the same pair IDs')
    if {v['run_id'] for v in a.values()} & {v['run_id'] for v in b.values()}:
        fail('reused_run_across_arms', 'same run cannot be two independent observations')
    pairs = sorted(a)
    prototype = a[pairs[0]]['report']
    protocol = prototype['protocol']
    records = prototype['records']
    if not isinstance(clusters, dict) or set(clusters) != {r['episode_id'] for r in records}:
        fail('cluster_population_mismatch', 'one cluster identity for every selected episode required')
    for value in clusters.values():
        _name(value)
    controls = a[pairs[0]]['controls']
    depths = [r['publication_depth'] for r in records]
    for pair in pairs:
        if a[pair]['seed'] != b[pair]['seed']:
            fail('paired_seed_mismatch', pair)
        for run in (a[pair], b[pair]):
            if run['controls'] != controls:
                fail('experimental_controls_mismatch', pair)
            report = run['report']
            if report['protocol'] != protocol or [r['publication_depth'] for r in report['records']] != depths:
                fail('evaluation_protocol_mismatch', 'cohort/labels/K/depth/definitions must match')
    groups = [('overall', None)] + [('slice', label) for label in sorted({r['slice'] for r in records})]
    results = []
    for scope, label in groups:
        indices = [i for i,r in enumerate(records) if scope == 'overall' or r['slice'] == label]
        users = sorted({clusters[records[i]['episode_id']] for i in indices})
        user_index = {u:i for i,u in enumerate(users)}
        counts = np.zeros(len(users))
        matrices = {m: [np.zeros((len(pairs), len(users))) for _ in range(2)] for m in metrics}
        for i in indices:
            user = user_index[clusters[records[i]['episode_id']]]
            counts[user] += 1
            for p,pair in enumerate(pairs):
                for arm,runs in enumerate((a,b)):
                    row = runs[pair]['report']['records'][i]
                    hit = float(row['hit'])
                    matrices[metrics[0]][arm][p,user] += hit
                    matrices[metrics[1]][arm][p,user] += 1/math.log2(row['rank']+1) if hit else 0
        estimates = {}
        for metric in metrics:
            x,y = matrices[metric]
            denominator = len(pairs)*len(indices)
            baseline, candidate = float(x.sum()/denominator), float(y.sum()/denominator)
            delta = candidate-baseline
            # Minimum identifiable dimensions are not a sufficient-power claim.
            reason = 'insufficient_paired_runs' if len(pairs)<2 else 'insufficient_user_clusters' if len(users)<2 else None
            if reason is None and np.ptp((y-x)/counts) == 0:
                reason = 'degenerate_observed_effects'
            interval = None if reason else _bootstrap(x,y,counts,replicates=replicates,
                rng=np.random.default_rng(random_seed),confidence=confidence)
            budget = degradation_budget[metric]
            decision = ('inconclusive' if interval is None else 'regression' if interval[1] < -budget
                else 'within_budget' if interval[0] >= -budget else 'inconclusive')
            estimates[metric] = {'baseline':baseline,'candidate':candidate,'absolute_effect':delta,
                'relative_effect':delta/baseline if baseline else None,'confidence_interval':interval,
                'interval_unavailable':reason,'absolute_degradation_budget':budget,'decision':decision}
        results.append({'scope':scope,'slice':label,'episodes_per_run':len(indices),'user_clusters':len(users),'metrics':estimates})
    declarations = [{k:run[k] for k in ('run_id','pair_id','seed','controls')} | {'report_sha256':run['report']['content_sha256']}
        for arm in (a,b) for _,run in sorted(arm.items())]
    return with_content_sha256({'format':'sidscope.paired_regression.v1','status':'computed',
        'protocol':protocol,'publication_depth_sha256':canonical_sha256(depths),
        'run_binding_sha256':canonical_sha256(declarations),'cluster_binding_sha256':canonical_sha256(clusters),
        'paired_runs':len(pairs),'results':results,
        'method':{'name':'paired_run_user_product_bootstrap','replicates':replicates,'confidence':confidence,'random_seed':random_seed,
            'estimand':'equal_run_weight_episode_macro','intervals':'pointwise_percentile_not_simultaneous',
            'reference':'https://arxiv.org/abs/0712.1111'},
        'limitations':['Approximate intervals require independent exchangeable run pairs and user clusters; small counts may be unreliable.',
            'Control, seed and cluster declarations are bound but not independently authenticated.',
            'No familywise PASS, causal claim, training verification or generalization beyond the frozen protocol.']})


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True,help='JSON arguments; run reports may be paths relative to this file')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        spec=load_json(args.input,max_bytes=None)
        for arm in ('left','right'):
            for run in spec[arm]:
                if isinstance(run.get('report'),str):
                    run['report']=load_json(args.input.parent/run['report'],max_bytes=None)
        result=compare_runs(**spec)
        with args.output.open('x') as handle:
            handle.write(json.dumps(result,sort_keys=True,allow_nan=False)+'\n')
    except (ValueError,TypeError,KeyError,OSError) as error:
        print(json.dumps({'status':'fail','code':getattr(error,'code',type(error).__name__),'detail':str(error)}))
        return 2
    print(json.dumps({'status':'computed','content_sha256':result['content_sha256']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
