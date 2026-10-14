"""Start the prepared local release without resetting data. Ctrl-C stops owned processes.
Use --without-inference for public evidence inspection on a smaller memory budget.
"""
import argparse,json,os,shutil,signal,subprocess,time
from pathlib import Path
import httpx
from scripts import advance004
ROOT=Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--without-inference',action='store_true');args=parser.parse_args()
 selection=json.loads((ROOT/'evidence/build004/profile-selection.json').read_text());selected=selection['selected']
 env=os.environ.copy()
 for path in (ROOT/'.env.kairos.local',ROOT/'.runtime/identity.env'):
  for line in path.read_text().splitlines():
   if line and not line.startswith('#'):
    key,value=line.split('=',1);env[key]=value
 env.update(KAIROS_INVESTIGATION_MODEL_MANIFEST=str(advance004.profiles[selected]),KAIROS_API_URL='http://127.0.0.1:8100',HOSTNAME='127.0.0.1',PORT='3100')
 build=ROOT/'dashboard/.next-build';web=build/'standalone'
 if not (web/'server.js').exists():raise RuntimeError('Production build missing; run KAIROS_NEXT_BUILD_DIR=.next-build npm --prefix dashboard run build')
 with httpx.Client(timeout=1,trust_env=False) as client:
  for port in (8100,3100):
   try:client.get('http://127.0.0.1:'+str(port))
   except httpx.HTTPError:pass
   else:raise RuntimeError('Existing service preserved on port '+str(port))
 shutil.copytree(build/'static',web/'.next-build/static',dirs_exist_ok=True)
 shutil.copytree(ROOT/'dashboard/public',web/'public',dirs_exist_ok=True)
 processes=[];logs=[]
 def launch(name,command,cwd=ROOT):
  log=(ROOT/'.runtime'/('build004-'+name+'.log')).open('a');logs.append(log)
  process=subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(process)
  return process
 def interrupted(*_):raise KeyboardInterrupt()
 signal.signal(signal.SIGTERM,interrupted)
 try:
  api=launch('api',[str(ROOT/'.venv/bin/python'),'-m','uvicorn','kairos_api.app:app','--host','127.0.0.1','--port','8100','--no-access-log'])
  with httpx.Client(timeout=2,trust_env=False) as client:
   for _ in range(60):
    if api.poll() is not None:raise RuntimeError('API exited; inspect private runtime log')
    try:
     if client.get('http://127.0.0.1:8100/api/health').status_code==200:break
    except httpx.HTTPError:pass
    time.sleep(1)
   else:raise TimeoutError('API startup deadline exceeded')
  if not args.without_inference:
   # Fail before model dispatch when a registered exact verification image is missing.
   # Saved-evidence inspection does not need these images or a model runtime.
   from kairos_api.investigations.registry import CaseRegistry
   for image in sorted({case['image'] for case in CaseRegistry().cases() if case.get('qualified')}):
    probe=subprocess.run(['docker','image','inspect',image,'--format','{{.Id}}'],capture_output=True,text=True)
    if probe.returncode or probe.stdout.strip()!=image:
     raise RuntimeError('Registered verification image unavailable: '+image+'; restore exact image before inference')
   advance004.start(selected,ROOT/'.runtime/model-active004.log',ROOT/'.runtime/active-runtime.json')
   launch('investigator',[str(ROOT/'.venv/bin/python'),'-m','kairos_api.investigations.worker'])
  launch('web',['node','server.js'],web)
  (ROOT/'.runtime/build004-services.json').write_text(json.dumps({'owned_pids':[p.pid for p in processes],'inference':not args.without_inference,'model_profile':selected,'api':'http://127.0.0.1:8100','web':'http://127.0.0.1:3100'},indent=2)+'\n')
  print('Kairos local release: http://127.0.0.1:3100. Public inspection uses saved evidence. Ctrl-C stops this launcher’s processes.',flush=True)
  while True:
   if any(p.poll() is not None for p in processes):raise RuntimeError('An owned service exited; inspect its runtime log')
   time.sleep(2)
 except KeyboardInterrupt:pass
 finally:
  for process in reversed(processes):process.terminate()
  for process in processes:
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
  advance004.stop()
  for log in logs:log.close()
if __name__=='__main__':main()
