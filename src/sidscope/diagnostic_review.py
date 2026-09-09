"""Offline, escaped and evidence-addressed ranked-diagnostic review (no service)."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path

from sidinspector.contracts import canonical_sha256, with_content_sha256, load_json
from sidinspector.evidence import scan_evidence_content
from sidscope.workflows import compare
from sidscope.regression import checked_report, compare_runs, fail


def diagnose(candidate, *, baseline=None, regression_spec=None, max_examples=20):
    """Recompute evidence, then describe observations and hypotheses separately.

    Examples export salted-by-source-hash pseudonyms and JSON pointers, never raw
    episode/user identifiers or ranked inputs. The original inputs remain external.
    max_examples bounds presentation only; all rows contribute to metrics/counts.
    """
    if type(max_examples) is not int or max_examples < 1:
        fail('invalid_example_budget','positive integer required')
    checked_report(candidate)
    difference=compare(baseline,candidate) if baseline is not None else None
    if baseline is not None and [r['publication_depth'] for r in baseline['records']] != [r['publication_depth'] for r in candidate['records']]:
        fail('evaluation_protocol_mismatch','review requires identical publication depths')
    uncertainty=compare_runs(**regression_spec) if regression_spec is not None else None
    if uncertainty is not None:
        if baseline is None or not any(r['report']==candidate for r in regression_spec['right']) or not any(r['report']==baseline for r in regression_spec['left']):
            fail('review_run_binding_mismatch','displayed reports must belong to the recomputed comparison arms')
    findings={}
    for i,row in enumerate(candidate['records']):
        old=baseline['records'][i] if baseline else None
        codes=[]
        if row['invalid_slots']:
            codes.append(('invalid_ranked_slots','Published slots contain unresolved/invalid entries.',
                'Inspect native resolution and validity flags at these exact slots; do not backfill ranks.'))
        if old and old['rank'] is not None and (row['rank'] is None or row['rank']>old['rank']):
            codes.append(('target_rank_regression','Target rank worsened or became right-censored.',
                'Compare the native candidate frontier and resolution decisions for this same episode.'))
        if not row['hit']:
            codes.append(('target_outside_topk','Target is absent from the published top-K.',
                'Check target/catalog alignment, native generation and resolution before assigning model blame.'))
        for code,observation,next_check in codes:
            key=(code,row['slice'])
            finding=findings.setdefault(key,{'code':code,'slice':row['slice'],'affected_episodes':0,
                'observation':observation,'hypothesis':'Several upstream causes remain possible; ranked slots alone do not identify the cause.',
                'confirmed_cause':None,'next_check':next_check,'examples':[]})
            finding['affected_episodes']+=1
            if len(finding['examples'])<max_examples:
                token=hashlib.sha256((candidate['content_sha256']+row['episode_id']).encode()).hexdigest()[:20]
                finding['examples'].append({'episode_alias':token,'candidate_pointer':f'/records/{i}',
                    'baseline_pointer':f'/records/{i}' if baseline else None,
                    'candidate_rank':row['rank'],'candidate_rank_state':row['rank_state'],
                    'baseline_rank':old['rank'] if old else None,'invalid_slots':row['invalid_slots']})
    rows=[]
    for (code,label),finding in sorted(findings.items()):
        finding['omitted_examples']=finding['affected_episodes']-len(finding['examples'])
        rows.append(finding)
    result=with_content_sha256({'format':'sidscope.diagnostic_review.v1',
        'verification_scope':'recomputed_ranked_item_diagnostics_not_native_or_training_authenticity',
        'candidate_sha256':candidate['content_sha256'],'baseline_sha256':baseline['content_sha256'] if baseline else None,
        'protocol':candidate['protocol'],'metrics':candidate['metrics'],
        'comparison':None if difference is None else {k:difference[k] for k in ('overall_delta','slice_deltas')},
        'uncertainty':uncertainty,'findings':rows,'max_examples_per_finding':max_examples,
        'supersession':{'automatic':False,'baseline_is_not_automatically_superseded':True},
        'limitations':['Evidence pointers require the original hash-bound evaluation report.',
            'No raw inputs, cluster IDs or raw episode IDs are embedded in this review.',
            'No observed finding is proof of an upstream causal mechanism.',
            'Missing baseline or multi-run evidence remains unavailable; no significance is inferred.']})
    scan_evidence_content(result)
    return result


def render_html(review):
    """No scripts, external requests, clickable input URLs or active raw markup."""
    escape=lambda value:html.escape(str(value),quote=True)
    parts=['<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
        '<title>SIDScope diagnostic review</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}td,th{border:1px solid #bbb;padding:8px}table{border-collapse:collapse}small{color:#555}</style>',
        '<h1>SIDScope diagnostic review</h1><p>'+escape(review['verification_scope'])+'</p>',
        '<p>Candidate: '+escape(review['candidate_sha256'])+'<br>Baseline: '+escape(review['baseline_sha256'])+'</p>',
        '<h2>Metrics and comparison</h2><pre>'+escape(json.dumps({'metrics':review['metrics'],'comparison':review['comparison'],'uncertainty':review['uncertainty']},indent=2))+'</pre>',
        '<h2>Evidence-addressed findings</h2>']
    for finding in review['findings']:
        parts.append('<section><h3>'+escape(finding['code'])+' — '+escape(finding['slice'])+'</h3>')
        for key in ('affected_episodes','observation','hypothesis','confirmed_cause','next_check','omitted_examples'):
            parts.append('<p><strong>'+escape(key)+':</strong> '+escape(finding[key])+'</p>')
        parts.append('<pre>'+escape(json.dumps(finding['examples'],indent=2))+'</pre></section>')
    parts.append('<h2>Limits and supersession</h2><pre>'+escape(json.dumps({'limitations':review['limitations'],'supersession':review['supersession']},indent=2))+'</pre></html>')
    return '\n'.join(parts)+'\n'


def write_review(output, candidate, **kwargs):
    output=Path(output)
    if output.exists() or output.is_symlink(): raise FileExistsError(output)
    review=diagnose(candidate,**kwargs)
    payload=render_html(review)
    output.mkdir(parents=True,exist_ok=False)
    with (output/'review.json').open('x') as handle: handle.write(json.dumps(review,sort_keys=True)+'\n')
    with (output/'index.html').open('x') as handle: handle.write(payload)
    receipt=with_content_sha256({'format':'sidscope.diagnostic_review_completion.v1','status':'pass',
        'review_sha256':review['content_sha256'],'html_sha256':hashlib.sha256(payload.encode()).hexdigest()})
    with (output/'complete.json').open('x') as handle: handle.write(json.dumps(receipt,sort_keys=True)+'\n')
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-examples',type=int,default=20)
    args=parser.parse_args(argv)
    try:
        result=write_review(args.output,load_json(args.candidate,max_bytes=None),
            baseline=load_json(args.baseline,max_bytes=None) if args.baseline else None,max_examples=args.max_examples)
    except (ValueError,TypeError,KeyError,OSError) as error:
        print(json.dumps({'status':'fail','code':getattr(error,'code',type(error).__name__),'detail':str(error)})); return 2
    print(json.dumps(result,sort_keys=True)); return 0


if __name__=='__main__':
    raise SystemExit(main())
