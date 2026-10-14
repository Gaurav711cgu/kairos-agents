"""One bounded local study execution. No paid provider, replacement attempt or tuning on evaluation.
Run on the Mac after focused acceptance. Source files must remain frozen during this command.
"""
import hashlib,json,os,subprocess,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evidence/build004';PYTHON=ROOT/'.venv/bin/python'
profiles={'coder':OUT/'inference-coder-mac.json','qwen3':OUT/'inference-qwen3-mac.json'}
active=None

def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def stop():
 global active
 if active is not None:
  active.terminate()
  try:active.wait(timeout=20)
  except subprocess.TimeoutExpired:active.kill();active.wait(timeout=10)
  active=None

def start(label,log_path=None,receipt_path=None):
 global active
 stop()
 with httpx.Client(timeout=1,trust_env=False) as client:
  try:client.get('http://127.0.0.1:8130/health')
  except httpx.HTTPError:pass
  else:raise RuntimeError('An inference server already occupies port 8130; preserve it')
 profile=json.loads(profiles[label].read_text());runtime=ROOT/'.runtime/investigations'
 for item in profile['files']:
  path=runtime/item['path']
  with path.open('rb') as source:actual=hashlib.file_digest(source,'sha256').hexdigest()
  if path.stat().st_size!=item['bytes'] or actual!=item['sha256']:raise RuntimeError('Pinned file mismatch: '+item['path'])
 archive=__import__('tarfile').open(runtime/'runtime/llama.tar.gz')
 for member in archive.getmembers():
  if member.isfile():
   with (runtime/'runtime'/member.name).open('rb') as source:
    if hashlib.file_digest(source,'sha256').hexdigest()!=hashlib.file_digest(archive.extractfile(member),'sha256').hexdigest():raise RuntimeError('Extracted binary/library mismatch')
 archive.close()
 model=next(item['path'] for item in profile['files'] if item['path'].endswith('.gguf'))
 argv=[str(runtime/'runtime/llama-b11552/llama-server'),'--model',str(runtime/model),'--host','127.0.0.1','--port','8130','--ctx-size','4096','--parallel','1','--threads','4','--n-predict','1024','--jinja','--no-webui']
 log=Path(log_path) if log_path else OUT/('model-revision2-'+label+'.txt')
 with log.open('a') as output:active=subprocess.Popen(argv,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
 write(Path(receipt_path) if receipt_path else OUT/'active-runtime.json',{'label':label,'pid':active.pid,'argv':argv,'profile':str(profiles[label].relative_to(ROOT)),'local_only':True})
 with httpx.Client(timeout=2,trust_env=False) as client:
  for _ in range(90):
   if active.poll() is not None:raise RuntimeError('Pinned model server exited; inspect '+str(log))
   try:
    if client.get('http://127.0.0.1:8130/health').status_code==200:return
   except httpx.HTTPError:pass
   time.sleep(1)
 raise TimeoutError('Pinned inference startup failed')

def run(label,phase,strategy=None):
 args=[str(PYTHON),'-m','scripts.study004',phase,'--profile',str(profiles[label]),'--label',label,'--revision','2']
 if strategy:args+=['--strategy',strategy]
 name=phase+'-'+(strategy or 'all')+'-'+label+'-revision2.txt'
 with (OUT/name).open('a') as output:subprocess.run(args,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,check=True)
 print(json.dumps({'completed':phase,'strategy':strategy,'profile':label}),flush=True)

def main():
 scores=[]
 try:
  for label in profiles:
   start(label);run(label,'development','baseline-v4')
   attempts=json.loads((OUT/('study-'+label)/'development-2/attempts.json').read_text())
   baseline=[a for a in attempts if a['configuration']=='baseline-v4']
   if len(baseline)!=6:raise RuntimeError('Incomplete six-case model comparison')
   scores.append({'label':label,'verified':sum(a['outcome']=='verified_repair' for a in baseline),'invalid_responses':sum(a['outcome']=='invalid_response' for a in baseline),'invalid_patches':sum(a['outcome']=='invalid_patch' for a in baseline),'elapsed_seconds':sum(a['elapsed_seconds'] or 0 for a in baseline),'attempt_ids':[a['id'] for a in baseline]})
  chosen=sorted(scores,key=lambda row:(-row['verified'],row['invalid_responses'],row['elapsed_seconds'],row['label']))[0]['label']
  write(OUT/'profile-selection.json',{'selected':chosen,'rule':'Six development single-call attempts each; more verified repairs, fewer invalid responses, lower elapsed time; lexical label resolves exact ties. No evaluation results used.','scores':scores,'lenovo_tested':False,'api_spend_usd':0})
  if chosen!='qwen3':start(chosen)
  for strategy in ('loop-v4','drafts-v4'):run(chosen,'development',strategy)
  run(chosen,'freeze');run(chosen,'evaluation');run(chosen,'report')
  env=os.environ.copy();env['KAIROS_INVESTIGATION_MODEL_MANIFEST']=str(profiles[chosen]);env['KAIROS_TEST_INVESTIGATION_PROVIDER']='1';env['KAIROS_TEST_INVESTIGATION_DOCKER']='1'
  with (OUT/'crash-recovery-output.txt').open('a') as output:subprocess.run([str(PYTHON),'-m','scripts.verify_investigation_crashes','--release','004','--configuration','baseline-v4'],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,check=True)
  with (OUT/'real-provider-docker.txt').open('a') as output:subprocess.run([str(PYTHON),'-m','pytest','tests/test_investigations.py::test_real_model_enforces_nested_schema','tests/test_investigations.py::test_real_docker_verifier_is_nonroot_readonly_and_network_disabled','-q','--tb=short'],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,check=True)
  write(OUT/'study-execution.json',{'complete':True,'selected':chosen,'development_revision':2,'evaluation_tuned':False,'api_spend_usd':0})
 finally:stop()
if __name__=='__main__':main()
