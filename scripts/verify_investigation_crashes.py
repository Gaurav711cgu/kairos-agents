"""Actual SIGKILL drills at durable boundaries; records stay outside evaluation cohorts."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from uuid import uuid4
from kairos_api.investigations.model import LocalInvestigator
from kairos_api.investigations.repository import InvestigationRepository
from kairos_api.investigations.sandbox import Workspace
from kairos_api.investigations.worker import ENTRY_LINES, InvestigationWorker

ROOT=Path(__file__).resolve().parents[1]


def environment():
    for line in (ROOT/'.env.kairos.local').read_text().splitlines():
        if line and not line.startswith('#'):
            key,value=line.split('=',1);os.environ[key]=value


def child(identifier,phase,marker):
    repository=InvestigationRepository();job=repository.claim('kill-drill-'+uuid4().hex)
    if not job or str(job['id'])!=identifier: raise RuntimeError('Unexpected queue order')
    case=repository.registry.get(job['task_id']);workspace=Workspace(repository.registry,case)
    provider=LocalInvestigator()
    if job['configuration'].endswith('-v4'):provider.verify_profile()
    observations=[{'action':'initial_source','result':(workspace.read_original if job['configuration'].endswith('-v4') else workspace.read)(p,ENTRY_LINES.get(p,1))} for p in case['entry_files']]
    request,context=provider.prepare(case,job['configuration'],observations,{'calls_remaining':1,'patches_remaining':1,'checks_remaining':1})
    seq=repository.begin(job,'context','selection',{});repository.capture(job,seq,context)
    seq=repository.begin(job,'model','dispatch',request)
    if phase=='captured': repository.capture(job,seq,provider(request))
    Path(marker).write_text(json.dumps({'id':identifier,'phase':phase,'model_calls':1}))
    os.kill(os.getpid(),signal.SIGSTOP)
    # Parent must terminate us. There is no normal continuation past the boundary.
    raise RuntimeError('Drill child unexpectedly resumed')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',choices=['003','004'],default='003');parser.add_argument('--configuration',default='baseline-v3');parser.add_argument('--child');parser.add_argument('--phase',choices=['intent','captured']);parser.add_argument('--marker');args=parser.parse_args()
    environment()
    if args.child: return child(args.child,args.phase,args.marker)
    repository=InvestigationRepository();repository.initialize();receipts=[]
    directory=ROOT/('evidence/build'+args.release+'/crash-drills');directory.mkdir(parents=True,exist_ok=True)
    for phase in ['intent','captured']:
        record=repository.enqueue('crash-drill','kill-'+uuid4().hex,'kairos-clock-lease',args.configuration)
        marker=ROOT/'.runtime/investigations'/('kill-'+record['id']+'.json')
        process=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','scripts.verify_investigation_crashes','--child',record['id'],'--phase',phase,'--marker',str(marker)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        deadline=time.monotonic()+150
        try:
            while not marker.exists():
                if process.poll() is not None: raise RuntimeError(process.stderr.read().decode()[-1500:])
                if time.monotonic()>deadline: raise TimeoutError('Crash boundary was not reached')
                time.sleep(.1)
            os.kill(process.pid,signal.SIGKILL);process.wait(timeout=10)
            before=repository.read(record['id'],'crash-drill')
            # Fault injection advances eligibility, not the recovery implementation's clock.
            with repository.connect() as connection:
                connection.execute("UPDATE kairos_investigations SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(record['id'],))
            class NoRedispatch(LocalInvestigator):
                calls=0
                def __call__(self,*args):
                    self.calls+=1
                    raise AssertionError('Recovered boundary must never dispatch another model call')
            provider=NoRedispatch();InvestigationWorker(repository,provider).run_once()
            after=repository.read(record['id'],'crash-drill')
            assert provider.calls==0 and after['model_calls']==1 and after['integrity']['verified']
            if phase=='intent': assert after['outcome']=='unknown_dispatch'
            else: assert after['status'] not in {'queued','running','unknown'}
            (directory/(phase+'.json')).write_text(json.dumps(after,indent=2)+'\n')
            receipts.append({'phase':phase,'record_id':record['id'],'signal':'SIGKILL','exit_code':process.returncode,
                             'before_status':before['status'],'after_status':after['status'],'after_outcome':after['outcome'],
                             'model_calls':after['model_calls'],'recovery_model_dispatches':provider.calls,
                             'captured_real_model_response':phase=='captured','integrity_verified':after['integrity']['verified'],
                             'fault_injection':'Lease expiry set to database clock minus one second after process death.',
                             'scope':'Intent drill dies before HTTP send; captured drill uses an actual local model response. No external side effects.'})
        finally:
            if process.poll() is None: process.kill();process.wait(timeout=10)
    (ROOT/('evidence/build'+args.release+'/crash-recovery.json')).write_text(json.dumps({'passed':True,'drills':receipts},indent=2)+'\n')
    print(json.dumps(receipts,indent=2))

if __name__=='__main__': main()
