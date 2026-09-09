import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from sidscope.workflows import evaluate, WorkflowError
from sidscope.diagnostic_review import diagnose,render_html,write_review,main
from tests.test_paired_regression import example


class DiagnosticReviewTest(unittest.TestCase):
    def reports(self):
        targets=[{'episode_id':f'private-episode-{i}','target_item_id':i,'slice':'cold'} for i in range(3)]
        baseline=evaluate([{'episode_id':r['episode_id'],'ranked_items':[r['target_item_id'],99]} for r in targets],targets,dataset='test',cutoff=2)
        candidate=evaluate([{'episode_id':targets[i]['episode_id'],'ranked_items':slots} for i,slots in enumerate(([99,0],[None,99],[98,99]))],targets,dataset='test',cutoff=2)
        return baseline,candidate

    def test_three_degradations_point_to_evidence(self):
        old,new=self.reports(); result=diagnose(new,baseline=old)
        self.assertEqual({r['code'] for r in result['findings']},{'invalid_ranked_slots','target_rank_regression','target_outside_topk'})
        for finding in result['findings']:
            self.assertIsNone(finding['confirmed_cause'])
            self.assertTrue(finding['next_check'])
            for sample in finding['examples']:
                i=int(sample['candidate_pointer'].split('/')[-1])
                self.assertEqual(sample['candidate_rank'],new['records'][i]['rank'])
        self.assertNotIn('private-episode-',json.dumps(result))
        self.assertNotIn('private-episode-',render_html(result))

    def test_example_limit_does_not_change_counts(self):
        old,new=self.reports(); result=diagnose(new,baseline=old,max_examples=1)
        finding=next(r for r in result['findings'] if r['code']=='target_outside_topk')
        self.assertEqual(finding['affected_episodes'],2)
        self.assertEqual(finding['omitted_examples'],1)
        self.assertEqual(result['metrics'],new['metrics'])

    def test_html_escapes_labels_and_no_active_script(self):
        old,new=self.reports(); inputs=copy.deepcopy(new['inputs'])
        inputs['targets'][0]['slice']='<img onerror=alert(1)>'
        result=diagnose(evaluate(**inputs)); page=render_html(result)
        self.assertNotIn('<img ',page)
        self.assertNotIn('<script',page)
        self.assertIn('&lt;img',page)
        self.assertIn('default-src',page)

    def test_input_tamper_and_uncertainty_binding_rejected(self):
        _,new=self.reports(); broken=copy.deepcopy(new); broken['records'][0]['rank']=99
        with self.assertRaises(WorkflowError): diagnose(broken)
        spec=example()
        with self.assertRaises(WorkflowError): diagnose(new,regression_spec=spec)
        result=diagnose(spec['right'][0]['report'],baseline=spec['left'][0]['report'],regression_spec=spec)
        self.assertEqual(result['uncertainty']['paired_runs'],4)

    def test_cli_and_completion_no_overwrite(self):
        old,new=self.reports()
        with TemporaryDirectory() as d:
            root=Path(d); (root/'new.json').write_text(json.dumps(new)); (root/'old.json').write_text(json.dumps(old))
            args=['--candidate',str(root/'new.json'),'--baseline',str(root/'old.json'),'--output',str(root/'review')]
            self.assertEqual(main(args),0)
            self.assertEqual(json.loads((root/'review/review.json').read_text()),diagnose(new,baseline=old))
            self.assertTrue((root/'review/complete.json').is_file())
            self.assertEqual(main(args),2)
