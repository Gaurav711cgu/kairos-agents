"""Bounded local database outage and real connection-pool saturation drills."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import hashlib
import psycopg
from psycopg.conninfo import make_conninfo
import httpx
from psycopg_pool import PoolTimeout,TooManyRequests
from kairos_api.investigations.repository import InvestigationRepository
from scripts.study007_runtime import ROOT,save


def study_fingerprint(database):
    with psycopg.connect(database) as connection:
        rows=connection.execute("SELECT id,command_digest,task_digest,config_digest,status,outcome,model_calls,patch_count,check_count FROM kairos_investigations WHERE tenant_id='study007' ORDER BY id").fetchall()
    return {'rows':len(rows),'sha256':hashlib.sha256(json.dumps(rows,default=str,separators=(',',':')).encode()).hexdigest()}


def saturation(database,blobs):
    repository=InvestigationRepository(database,blobs,pooled=True)
    repository.pool.wait(timeout=10)
    held=[]
    try:
        held=[repository.pool.getconn(timeout=10) for _ in range(8)]
        def borrow(_):
            started=time.monotonic()
            try:
                with repository.connect():return {'result':'unexpected_borrow','seconds':time.monotonic()-started}
            except (PoolTimeout,TooManyRequests) as error:
                return {'result':type(error).__name__,'seconds':time.monotonic()-started}
        with ThreadPoolExecutor(max_workers=40) as executor:results=list(executor.map(borrow,range(40)))
        assert all(row['result'] in {'PoolTimeout','TooManyRequests'} for row in results)
        assert max(row['seconds'] for row in results)<8
        for connection in held:repository.pool.putconn(connection)
        held=[]
        with repository.connect() as connection:assert connection.execute('SELECT 1 AS alive').fetchone()['alive']==1
        return {'passed':True,'connections_held':8,'contending_borrowers':40,'maximum_waiting':32,
                'outcomes':{name:sum(row['result']==name for row in results) for name in ('PoolTimeout','TooManyRequests')},
                'maximum_elapsed_seconds':max(row['seconds'] for row in results),'recovered_after_release':True,
                'scope':'Actual PostgreSQL pool saturation; this is not a throughput benchmark'}
    finally:
        for connection in held:repository.pool.putconn(connection)
        repository.close()


def outage(database,blobs,container):
    before=study_fingerprint(database)
    token=secrets.token_urlsafe(32)
    bounded_database=make_conninfo(database,options='-c lock_timeout=2s -c statement_timeout=15s -c idle_in_transaction_session_timeout=30s')
    env={**os.environ,'DATABASE_URL':bounded_database,'KAIROS_BLOB_DIR':str(blobs),'KAIROS_ENV':'development',
         'KAIROS_IDENTITY_MODE':'development','KAIROS_DEV_TOKEN':token,'KAIROS_DEV_TENANT':'operations007'}
    log=ROOT/'.runtime/study007/operations-api.log'
    with log.open('w') as output:
        process=subprocess.Popen([sys.executable,'-m','uvicorn','kairos_api.app:app','--host','127.0.0.1','--port','8330','--no-access-log'],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
        try:
            with httpx.Client(timeout=10,trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:raise RuntimeError('Operations API startup failed')
                    try:
                        if client.get('http://127.0.0.1:8330/api/health').status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.1)
                else:raise TimeoutError('Operations API startup deadline exceeded')
                headers={'Authorization':'Bearer '+token,'Idempotency-Key':'operations007-durable-command'}
                body={'task_id':'kairos-clock-lease','configuration':'baseline-v7'}
                first=client.post('http://127.0.0.1:8330/api/investigations',headers=headers,json=body)
                assert first.status_code==202
                identifier=first.json()['id']
                with psycopg.connect(database) as blocker:
                    blocker.execute('SELECT pg_advisory_xact_lock(796342193)')
                    locked_at=time.monotonic()
                    blocked=client.post('http://127.0.0.1:8330/api/investigations',headers=headers,json=body)
                    locked_seconds=time.monotonic()-locked_at
                    assert blocked.status_code==503 and 1.5<locked_seconds<4
                resumed=client.post('http://127.0.0.1:8330/api/investigations',headers=headers,json=body)
                assert resumed.status_code==202 and resumed.json()['id']==identifier
                held_lock={'status':blocked.status_code,'elapsed_seconds':locked_seconds,
                           'recovered_same_identity':True,'new_model_dispatches':0}
                started=time.monotonic()
                subprocess.run(['docker','stop','--time','2',container],capture_output=True,check=True)
                response=client.get('http://127.0.0.1:8330/api/investigations',headers=headers)
                observed=time.monotonic()-started
                assert response.status_code==503
                subprocess.run(['docker','start',container],capture_output=True,check=True)
                recovery=time.monotonic()
                for _ in range(100):
                    try:
                        retry=client.post('http://127.0.0.1:8330/api/investigations',headers=headers,json=body)
                        if retry.status_code==202:break
                    except httpx.HTTPError:pass
                    time.sleep(.2)
                else:raise TimeoutError('Database recovery deadline exceeded')
                assert retry.json()['id']==identifier and retry.json()['model_calls']==0
                cancelled=client.post('http://127.0.0.1:8330/api/investigations/'+identifier+'/cancel',headers=headers,json={})
                assert cancelled.status_code==200 and cancelled.json()['status']=='cancelled'
                after=study_fingerprint(database)
                assert before==after,'Preserved study rows changed during outage'
                return {'passed':True,'held_runtime_lock':held_lock,'outage_status':response.status_code,'detection_seconds_including_stop':observed,
                        'recovery_seconds_after_start':time.monotonic()-recovery,'same_durable_command_after_restart':True,
                        'model_calls':0,'source_data_preserved':before==after,'preserved_study_fingerprint':after,
                        'scope':'Intentional local PostgreSQL outage, developer auth; actual OIDC journeys are separate'}
        finally:
            subprocess.run(['docker','start',container],capture_output=True,check=True)
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--environment',required=True);parser.add_argument('--container',required=True)
    args=parser.parse_args();data=json.loads(Path(args.environment).read_text());blobs=ROOT/'.runtime/study007/blobs'
    information=json.loads(subprocess.check_output(['docker','container','inspect',args.container],text=True))[0]
    if information['Config'].get('Labels',{}).get('io.kairos.build007.owner')!='kairos-build007-study':
        raise ValueError('Preserve unrelated container: operations drill requires the owned study database')
    result={'release':'build007','pool':saturation(data['DATABASE_URL'],blobs),
            'outage':outage(data['DATABASE_URL'],blobs,args.container)}
    result['passed']=result['pool']['passed'] and result['outage']['passed']
    save(ROOT/'evidence/build007/operational-drills.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
