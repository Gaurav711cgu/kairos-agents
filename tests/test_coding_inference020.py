import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

from scripts import coding_inference020 as m


def inputs():
 package={'cases':[{'instance_id':'a'},{'instance_id':'b'}],'scope':'fixture only','generation':{'max_new_tokens':4,'context_tokens':12}}
 cases=[{'instance_id':x,'messages':[{'role':'user','content':x}],'input_token_ids':[1], 'input_tokens':1,'unavailable_reason':None} for x in ['a','b']]
 package['cases']=[{'instance_id':c['instance_id'],'messages':c['messages'],'context_available':True} for c in cases]
 return package,cases,{'version':'fixture','profile':'same'}


def test_counterbalanced_pairs_keep_raw_outputs_without_claiming_repairs(tmp_path):
 package,cases,binding=inputs();calls=[]
 def generate(case,arm):
  calls.append((case['instance_id'],arm));return {'text':'full output with indentation\n    return 3','output_token_ids':[10,20]}
 result=m.paired_run(package,cases,tmp_path,binding,generate)
 assert calls==[('a','base'),('a','adapter'),('b','adapter'),('b','base')]
 assert result['repair_verification_complete'] is False and result['training_runs']==0
 assert all(r['verified_repair'] is None for r in result['records'])
 assert all(r['text'].endswith('    return 3') for r in result['records'])


def test_completed_results_never_regenerate(tmp_path):
 p,c,b=inputs();m.paired_run(p,c,tmp_path,b,lambda *_:{'text':'x'})
 m.paired_run(p,c,tmp_path,b,lambda *_:pytest.fail('captured dispatch repeated'))


def test_uncertain_dispatch_stops_instead_of_retrying(tmp_path):
 p,c,b=inputs()
 with pytest.raises(SystemExit):m.paired_run(p,c,tmp_path,b,lambda *_:(_ for _ in ()).throw(SystemExit('process interrupted')))
 assert (tmp_path/'a.base.intent.json').exists() and not (tmp_path/'a.base.json').exists()
 with pytest.raises(RuntimeError,match='Unknown prior dispatch'):
  m.paired_run(p,c,tmp_path,b,lambda *_:pytest.fail('uncertain dispatch repeated'))


def test_inference_error_is_captured_once(tmp_path):
 p,c,b=inputs();seen=[]
 def fail(case,arm):
  seen.append((case['instance_id'],arm));raise MemoryError('fixture OOM')
 result=m.paired_run(p,c,tmp_path,b,fail)
 assert len(seen)==4 and all(r['status']=='inference_error' and r['error_type']=='MemoryError' for r in result['records'])
 m.paired_run(p,c,tmp_path,b,lambda *_:pytest.fail('errored dispatch retried'))


def test_missing_context_preserves_case_but_spends_no_inference(tmp_path):
 p,c,b=inputs();c[0]['unavailable_reason']='No source'
 result=m.paired_run(p,c,tmp_path,b,lambda *_:{'text':'other case'})
 assert len(result['records'])==4
 assert sum(r['model_calls'] for r in result['records'])==2
 assert result['records'][0]['status']=='unavailable'


def test_whole_prompt_budget_never_truncates_json():
 p,_,_=inputs();p['cases']=[{'instance_id':'a','context_available':True,'messages':[{'role':'user','content':'full issue'}]}]
 result=m.tokenize_cases(p,lambda _:[1]*9)
 assert result[0]['input_tokens']==9 and len(result[0]['input_token_ids'])==9
 assert 'exceeds' in result[0]['unavailable_reason']


def test_result_corruption_and_profile_drift_are_rejected(tmp_path):
 p,c,b=inputs();m.paired_run(p,c,tmp_path,b,lambda *_:{'text':'original'})
 path=tmp_path/'a.base.json';v=json.loads(path.read_text());v['text']='changed';path.write_text(json.dumps(v))
 with pytest.raises(ValueError):m.paired_run(p,c,tmp_path,b,lambda *_:pytest.fail('unexpected dispatch'))
 with pytest.raises(ValueError):m.paired_run(p,c,tmp_path,{**b,'profile':'changed'},lambda *_:pytest.fail('unexpected dispatch'))


def test_publish_refuses_overwrite_and_has_no_partial_final(tmp_path):
 path=tmp_path/'receipt.json';m.publish(path,{'done':True});m.publish(path,{'done':True})
 with pytest.raises(ValueError):m.publish(path,{'done':False})
 assert list(tmp_path.glob('.capture-*'))==[]


def test_prompt_integrity_checked_before_gpu_or_download(tmp_path):
 p=tmp_path/'prompts.json';p.write_text('{}')
 with pytest.raises(ValueError,match='Frozen prompts differ'):m.run_gpu(p,tmp_path,tmp_path/'out','0'*64,tmp_path)
 assert not (tmp_path/'out').exists()


def test_completed_gpu_run_returns_captures_without_importing_model_packages(tmp_path, monkeypatch):
 p,c,b=inputs();b.update(prompts_sha256='frozen',runner_sha256=m.sha(m.__file__))
 original=m.paired_run(p,c,tmp_path,b,lambda *_:{'text':'captured'})
 monkeypatch.setattr(m,'verify_inputs',lambda *_:p)
 monkeypatch.delenv('KAIROS_EVALUATION_GPU',raising=False)
 assert m.run_gpu(tmp_path/'unused',tmp_path,tmp_path,'frozen',tmp_path)==original


def test_completed_gpu_run_with_missing_capture_never_regenerates(tmp_path, monkeypatch):
 p,c,b=inputs();b.update(prompts_sha256='frozen',runner_sha256=m.sha(m.__file__))
 m.paired_run(p,c,tmp_path,b,lambda *_:{'text':'captured'})
 (tmp_path/'a.base.json').unlink()
 monkeypatch.setattr(m,'verify_inputs',lambda *_:p)
 with pytest.raises(RuntimeError,match='Unknown prior dispatch'):
  m.run_gpu(tmp_path/'unused',tmp_path,tmp_path,'frozen',tmp_path)


def test_export_is_hash_verified_and_reuses_exact_archive(tmp_path):
 import zipfile
 p,c,b=inputs();output=tmp_path/'results';m.paired_run(p,c,output,b,lambda *_:{'text':'full raw generation'})
 first=m.export_results(output);second=m.export_results(output)
 assert first==second
 with zipfile.ZipFile(first['path']) as z:
  assert all(not name.endswith(('.safetensors','.pt')) for name in z.namelist())
  assert json.loads(z.read('manifest.json'))['repair_verification_complete'] is False


def test_export_refuses_unselected_data(tmp_path):
 p,c,b=inputs();output=tmp_path/'results';m.paired_run(p,c,output,b,lambda *_:{'text':'generation'})
 (output/'private.json').write_text('{"not":"selected"}')
 with pytest.raises(ValueError,match='membership'):m.export_results(output)
 assert not (tmp_path/'kairos-evaluation020.zip').exists()


def test_opted_in_errors_preserve_bounded_redacted_diagnostics_and_never_retry(tmp_path, monkeypatch):
 p,c,b=inputs();monkeypatch.setenv('EXAMPLE_API_KEY','private-test-key-123456')
 def fail(*_):raise RuntimeError('dtype mismatch private-test-key-123456 ' + 'x'*5000)
 result=m.paired_run(p,c,tmp_path,b,fail,capture_error_details=True)
 for record in result['records']:
  detail=record['error_details']
  assert 'dtype mismatch [redacted]' in detail['message']
  assert 'private-test-key-123456' not in json.dumps(detail)
  assert len(detail['message'])<=4096 and len(detail['frames'])<=12
  assert detail['frames'][-1]['function']=='fail'
  assert all('/' not in f['file'] and set(f)=={'file','line','function'} for f in detail['frames'])
 m.paired_run(p,c,tmp_path,b,lambda *_:pytest.fail('failed dispatch retried'),capture_error_details=True)


def test_legacy_error_capture_remains_without_diagnostics(tmp_path):
 p,c,b=inputs()
 result=m.paired_run(p,c,tmp_path,b,lambda *_:(_ for _ in ()).throw(RuntimeError('private detail')))
 assert all('error_details' not in r for r in result['records'])
