import json
import pytest
from tests.test_native_canonical_submission import synthetic_inputs
from tools.run_sidscope_observed_review import run
from tools.benchmark_sidscope_observed_review import benchmark


def test_one_command_review_and_identity(synthetic_inputs,tmp_path):
    source,metadata=synthetic_inputs
    result=run(source,metadata,tmp_path/'review')
    assert result['status']=='pass'
    assert result['multi_run_status']=='unavailable_single_native_observation'
    assert result['shape']['trace_episodes']==5
    assert result['observed_nfe']==[4]*5
    assert (tmp_path/'review/review/index.html').is_file()
    with pytest.raises(FileExistsError): run(source,metadata,tmp_path/'review')
    with pytest.raises(ValueError,match='review_output_inside_input'): run(source,metadata,source/'bad-output')


def test_repeated_real_shape_benchmark_plumbing(synthetic_inputs,tmp_path):
    source,metadata=synthetic_inputs
    result=benchmark(source,metadata,tmp_path/'benchmark',repeats=3)
    assert result['status']=='pass'
    assert len(result['runs'])==3
    assert result['benchmark_guards']['timeout_seconds']==300
    assert result['summary']['process_peak_rss_bytes']['max']>0
    assert len({r['review_sha256'] for r in result['runs']})==1


def test_benchmark_timeout_and_invalid_policy(synthetic_inputs,tmp_path):
    source,metadata=synthetic_inputs
    with pytest.raises(ValueError): benchmark(source,metadata,tmp_path/'invalid',repeats=1)
    result=benchmark(source,metadata,tmp_path/'timeout',timeout=.00001)
    assert result['status']=='fail'
    assert result['runs'][0]['reason']=='timeout'
