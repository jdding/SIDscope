#!/usr/bin/env python3
"""One local observed-input workflow: canonical admission, ranked diagnostics, HTML.

Consumes an existing authorized observation; never runs a model or reads keys.
No replication of observations into fictitious independent seeds.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'src'))
from sidinspector.contracts import load_json,with_content_sha256,canonical_sha256
from sidscope.workflows import evaluate,WorkflowError
from sidscope.diagnostic_review import write_review
from tools.build_sidscope_native_submission import build_submission,verify_submission
from tools.project_sidscope_native_export import project_export


def file_sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(source,metadata,output):
    source,metadata,output=Path(source),Path(metadata),Path(output)
    if output.exists() or output.is_symlink(): raise FileExistsError(output)
    if source.resolve() in output.resolve().parents:
        raise WorkflowError('review_output_inside_input','new separate output directory required')
    files={name:source/(name+'.json') for name in ('native','preflight','selection','observations')}
    files['metadata']=metadata
    before={k:file_sha(p) for k,p in files.items()}
    phases={}; started=time.perf_counter(); mark=started
    # The canonical builder validates full joins before admitting diagnostics.
    canonical=build_submission(source,metadata,output/'canonical')
    phases['canonical_and_mapping_seconds']=time.perf_counter()-mark; mark=time.perf_counter()
    verify_submission(source,metadata,output/'canonical/submission')
    phases['original_input_recheck_seconds']=time.perf_counter()-mark; mark=time.perf_counter()
    projection=project_export(source/'native.json',selection=source/'selection.json')
    # Existing public evaluate rejects duplicates. Never silently deduplicate a
    # native slot sequence just to fit this optional report consumer.
    if any(row['duplicate_slots'] for row in projection['records']):
        raise WorkflowError('review_duplicate_slots_unsupported','native evidence retained; ranked consumer does not support duplicate slots')
    rows=projection['records']
    report=evaluate([{'episode_id':r['episode_id'],'ranked_items':r['ranked_items']} for r in rows],
        [{'episode_id':r['episode_id'],'target_item_id':r['target_normalized_item_id'],'slice':r['slice']} for r in rows],
        dataset='native-'+canonical_sha256({key:projection['protocol'][key] for key in
            ('dataset_split','split_sha256','target_universe_sha256')}),cutoff=projection['protocol']['evaluation_cutoff'])
    phases['rank_evaluation_seconds']=time.perf_counter()-mark; mark=time.perf_counter()
    review=write_review(output/'review',report)
    phases['review_seconds']=time.perf_counter()-mark
    for name,doc in (('evaluation',report),('clusters',{r['episode_id']:r['cluster_id'] for r in rows})):
        with (output/(name+'.json')).open('x') as handle: handle.write(json.dumps(doc,sort_keys=True)+'\n')
    observed=load_json(source/'observations.json',max_bytes=None)
    preflight=load_json(source/'preflight.json',max_bytes=None)
    after={k:file_sha(p) for k,p in files.items()}
    if after!=before: raise WorkflowError('native_input_changed','inputs changed during review')
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result=with_content_sha256({'format':'sidscope.observed_review_completion.v1','status':'pass',
        'inputs_sha256':before,'bundle_sha256':canonical['bundle_sha256'],'evaluation_sha256':report['content_sha256'],
        'review_sha256':review['review_sha256'],'phase_seconds':phases,'elapsed_seconds':time.perf_counter()-started,
        'process_peak_rss_bytes':int(rss if sys.platform=='darwin' else rss*1024),
        'output_bytes_before_receipt':sum(p.stat().st_size for p in output.rglob('*') if p.is_file()),
        'shape':{'mapping_items':len(preflight['mapping']),'split_rows':len(preflight['splits']),'trace_episodes':len(rows)},
        'observed_nfe':[r['nfe'] for r in observed['measurements']],
        'nfe_definition':observed['nfe_definition'],'nfe_scope':'previous_native_observation_not_measured_by_this_postprocessing_run',
        'multi_run_status':'unavailable_single_native_observation','independent_user_acceptance':'not_established',
        'boundary':'Local diagnostic postprocessing only; no new inference, training, scale extrapolation or independent seeds.'})
    with (output/'complete.json').open('x') as handle: handle.write(json.dumps(result,sort_keys=True)+'\n')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--metadata',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try: result=run(args.input,args.metadata,args.output)
    except (ValueError,TypeError,KeyError,OSError) as error:
        print(json.dumps({'status':'fail','code':getattr(error,'code',type(error).__name__),'detail':str(error)})); return 2
    print(json.dumps(result,sort_keys=True)); return 0


if __name__=='__main__': raise SystemExit(main())
