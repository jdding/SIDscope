#!/usr/bin/env python3
"""Repeat real observed postprocessing in fresh CPU processes, not model inference.

Limits are benchmark guards, not input limits or an unapproved production SLO.
Do not label a five-episode trace a full-scale inference acceptance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'src'))
from sidinspector.contracts import load_json,with_content_sha256


def sources():
    files=list((ROOT/'src').rglob('*.py'))+[ROOT/'tools'/name for name in
        ('run_sidscope_observed_review.py','benchmark_sidscope_observed_review.py','build_sidscope_native_submission.py','project_sidscope_native_export.py','verify_sidscope_native_observation.py')]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def benchmark(source,metadata,output,*,repeats=3,timeout=300,rss_mib=2048):
    if type(repeats) is not int or repeats<3 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (timeout,rss_mib)):
        raise ValueError('at least three repeats and positive execution guards required')
    output=Path(output)
    if Path(source).resolve() in output.resolve().parents:
        raise ValueError('benchmark_output_inside_input')
    output.mkdir(parents=True,exist_ok=False)
    snapshot=sources(); rows=[]
    for repeat in range(repeats):
        target=output/f'run-{repeat}'
        command=[sys.executable,str(ROOT/'tools/run_sidscope_observed_review.py'),'--input',str(Path(source).resolve()),'--metadata',str(Path(metadata).resolve()),'--output',str(target.resolve())]
        try:
            completed=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
            (output/f'run-{repeat}.log').write_text(completed.stdout+completed.stderr)
            if completed.returncode:
                rows.append({'status':'fail','reason':'worker_failed','returncode':completed.returncode}); break
            row=load_json(target/'complete.json',max_bytes=None)
            if row['process_peak_rss_bytes']>rss_mib*1024*1024: row.update(status='fail',reason='rss_guard_exceeded')
            rows.append(row)
            if row['status']!='pass': break
        except subprocess.TimeoutExpired:
            rows.append({'status':'fail','reason':'timeout'}); break
    passed=len(rows)==repeats and all(r['status']=='pass' for r in rows) and snapshot==sources()
    if passed:
        for key in ('inputs_sha256','bundle_sha256','evaluation_sha256','review_sha256','shape','observed_nfe'):
            if any(row[key]!=rows[0][key] for row in rows): passed=False
    summary={}
    if passed:
        for key in ('elapsed_seconds','process_peak_rss_bytes','output_bytes_before_receipt'):
            values=[row[key] for row in rows]
            summary[key]={'median':statistics.median(values),'min':min(values),'max':max(values)}
        summary['phase_seconds']={key:{'median':statistics.median(row['phase_seconds'][key] for row in rows),
            'max':max(row['phase_seconds'][key] for row in rows)} for key in rows[0]['phase_seconds']}
    result=with_content_sha256({'format':'sidscope.observed_review_benchmark.v1','status':'pass' if passed else 'fail',
        'source_files':snapshot,'environment':{'python':platform.python_version(),'platform':platform.platform()},
        'benchmark_guards':{'repeats':repeats,'timeout_seconds':timeout,'post_run_rss_mib':rss_mib},
        'runs':rows,'summary':summary,'scale_acceptance':'only_recorded_mapping_split_and_trace_shapes',
        'boundary':'Repeated existing real-input postprocessing. No new native NFE, full-population trace, tail-latency SLO or independent user claim.'})
    (output/'result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True); parser.add_argument('--metadata',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--timeout',type=float,default=300); parser.add_argument('--rss-mib',type=float,default=2048)
    args=parser.parse_args()
    result=benchmark(args.input,args.metadata,args.output,repeats=args.repeats,timeout=args.timeout,rss_mib=args.rss_mib)
    print(json.dumps({'status':result['status'],'summary':result['summary']})); return 0 if result['status']=='pass' else 2


if __name__=='__main__': raise SystemExit(main())
