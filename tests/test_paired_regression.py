import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from sidscope.workflows import evaluate, WorkflowError
from sidscope.regression import compare_runs, _bootstrap, main


def example(pairs=4, users=8):
    targets=[{'episode_id':f'e{i}', 'target_item_id':i,'slice':'cold' if i%2 else 'warm'} for i in range(users)]
    arms=[]
    for arm in range(2):
        runs=[]
        for pair in range(pairs):
            predictions=[{'episode_id':f'e{i}', 'ranked_items':[i if not arm or (i+pair)%5==0 else None]} for i in range(users)]
            runs.append({'run_id':f'a{arm}-r{pair}','pair_id':f'p{pair}','seed':pair,
                'controls':{'dataset_snapshot':'frozen-test','training_recipe':'matched-test'},
                'report':evaluate(predictions,targets,dataset='synthetic',cutoff=1)})
        arms.append(runs)
    return {'left':arms[0],'right':arms[1],'clusters':{f'e{i}':f'u{i}' for i in range(users)},
        'degradation_budget':{'hit_at_cutoff':.05,'ndcg_at_cutoff':.05},'replicates':200}


class PairedRegressionTest(unittest.TestCase):
    def test_effect_and_determinism_and_permutation(self):
        spec=example(); result=compare_runs(**spec)
        metric=result['results'][0]['metrics']['hit_at_cutoff']
        self.assertEqual(metric['baseline'],1)
        self.assertLess(metric['absolute_effect'],-.5)
        self.assertEqual(metric['decision'],'regression')
        self.assertEqual(result,compare_runs(**spec))
        spec['left'].reverse(); spec['right'].reverse()
        self.assertEqual(result,compare_runs(**spec))

    def test_exact_resampling_matches_independent_expanded_reference(self):
        x=np.array([[1.,0.],[2.,1.],[0.,1.]])
        y=np.array([[0.,1.],[1.,0.],[1.,1.]])
        counts=np.array([2.,1.])
        rng=np.random.default_rng(71); sampled=[]
        for _ in range(200):
            rw=rng.multinomial(3,[1/3]*3); uw=rng.multinomial(2,[.5,.5])
            numerator=sum(rw[r]*uw[u]*(y[r,u]-x[r,u]) for r in range(3) for u in range(2))
            denominator=sum(rw[r]*uw[u]*counts[u] for r in range(3) for u in range(2))
            sampled.append(numerator/denominator)
        expected=np.quantile(sampled,[.025,.975])
        actual=_bootstrap(x,y,counts,replicates=200,rng=np.random.default_rng(71),confidence=.95)
        np.testing.assert_allclose(actual,expected)

    def test_cluster_duplication_preserves_effect_and_interval(self):
        spec=example(); original=compare_runs(**spec)
        for arm in ('left','right'):
            for run in spec[arm]:
                data=copy.deepcopy(run['report']['inputs'])
                for key in ('predictions','targets'):
                    additions=copy.deepcopy(data[key])
                    for row in additions: row['episode_id']+='x'
                    data[key]+=additions
                run['report']=evaluate(**data)
        spec['clusters'].update({k+'x':v for k,v in list(spec['clusters'].items())})
        new=compare_runs(**spec)
        for old,row in zip(original['results'],new['results']):
            self.assertEqual(old['metrics'],row['metrics'])
            self.assertEqual(old['user_clusters'],row['user_clusters'])

    def test_unequal_user_sizes_preserve_episode_macro(self):
        spec=example(); spec['clusters']={f'e{i}':'large' if i<7 else 'small' for i in range(8)}
        out=compare_runs(**spec)['results'][0]
        expected=sum(r['report']['metrics']['overall']['hit_at_cutoff'] for r in spec['right'])/4-1
        self.assertEqual(out['metrics']['hit_at_cutoff']['absolute_effect'],expected)
        self.assertEqual(out['user_clusters'],2)

    def test_seeded_crossed_effect_coverage_sanity_not_nominal_guarantee(self):
        # Independent known-zero crossed run/user effects, NOT IID episodes.
        # This bounded deterministic calibration catches gross undercoverage;
        # it does not certify 95 percent coverage for real small-sample inputs.
        rng=np.random.default_rng(914); covered=0
        for index in range(40):
            x=np.full((24,48),.5)
            y=x+rng.normal(0,.03,(24,1))+rng.normal(0,.04,(1,48))+rng.normal(0,.01,(24,48))
            lo,hi=_bootstrap(x,y,np.ones(48),replicates=300,rng=np.random.default_rng(index),confidence=.95)
            covered+=lo<=0<=hi
        self.assertGreaterEqual(covered,34)

    def test_zero_baseline_relative_effect_unavailable(self):
        spec=example()
        for run in spec['left']:
            data=copy.deepcopy(run['report']['inputs'])
            for row in data['predictions']: row['ranked_items']=[None]
            run['report']=evaluate(**data)
        metric=compare_runs(**spec)['results'][0]['metrics']['hit_at_cutoff']
        self.assertIsNone(metric['relative_effect'])

    def test_insufficient_runs_clusters_and_degenerate_do_not_pass(self):
        for kind in ('runs','clusters','degenerate'):
            spec=example(pairs=1 if kind=='runs' else 4)
            if kind=='clusters': spec['clusters']={k:'one' for k in spec['clusters']}
            if kind=='degenerate':
                for a,b in zip(spec['left'],spec['right']): b['report']=copy.deepcopy(a['report'])
            result=compare_runs(**spec)
            metric=result['results'][0]['metrics']['hit_at_cutoff']
            self.assertIsNone(metric['confidence_interval'])
            self.assertEqual(metric['decision'],'inconclusive')

    def test_protocol_control_pairing_negative_cases(self):
        mutations=[('missing_paired_run',lambda s:s['right'].pop()),
            ('duplicate_run',lambda s:s['right'].append(copy.deepcopy(s['right'][0]))),
            ('paired_seed_mismatch',lambda s:s['right'][0].update(seed=100)),
            ('duplicate_seed',lambda s:s['right'][1].update(seed=0)),
            ('experimental_controls_mismatch',lambda s:s['right'][0].update(controls={'dataset_snapshot':'other'})),
            ('cluster_population_mismatch',lambda s:s['clusters'].pop('e0')),
            ('reused_run_across_arms',lambda s:s['right'][0].update(run_id=s['left'][0]['run_id'])),
            ('workflow_report_recomputation_mismatch',lambda s:s['right'][0]['report']['metrics']['overall'].update(hit_at_cutoff=99))]
        for code,mutate in mutations:
            with self.subTest(code=code):
                spec=example(); mutate(spec)
                with self.assertRaises(WorkflowError) as error: compare_runs(**spec)
                self.assertEqual(error.exception.code,code)

    def test_rehashed_cohort_and_depth_change_rejected(self):
        for field in ('dataset','depth','slice'):
            spec=example(); data=copy.deepcopy(spec['right'][0]['report']['inputs'])
            if field=='dataset': data['dataset']='other'
            elif field=='depth':
                for row in data['predictions']: row['ranked_items'].append(999)
            else: data['targets'][0]['slice']='other'
            spec['right'][0]['report']=evaluate(**data)
            with self.assertRaises(WorkflowError) as error: compare_runs(**spec)
            self.assertEqual(error.exception.code,'evaluation_protocol_mismatch')

    def test_bad_statistical_configuration(self):
        for kwargs in ({'replicates':True},{'confidence':float('nan')},{'random_seed':-1},
                       {'degradation_budget':{'hit_at_cutoff':True,'ndcg_at_cutoff':0}}):
            spec=example(); spec.update(kwargs)
            with self.assertRaises(WorkflowError): compare_runs(**spec)

    def test_cli_api_parity_and_no_overwrite(self):
        with TemporaryDirectory() as d:
            root=Path(d); spec=example(); expected=compare_runs(**spec)
            for arm in ('left','right'):
                for i,run in enumerate(spec[arm]):
                    name=f'{arm}-{i}.json'; (root/name).write_text(json.dumps(run['report'])); run['report']=name
            (root/'spec.json').write_text(json.dumps(spec))
            args=['--input',str(root/'spec.json'),'--output',str(root/'result.json')]
            self.assertEqual(main(args),0)
            self.assertEqual(json.loads((root/'result.json').read_text()),expected)
            self.assertEqual(main(args),2)
