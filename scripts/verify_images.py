"""Smoke actual non-root images against an isolated schema; never publish test runs."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from scripts.verify_operations import environment

ROOT=Path(__file__).resolve().parents[1]

def docker(*arguments):
    return subprocess.check_output(["docker",*arguments],stderr=subprocess.DEVNULL,text=True).strip()

def ready(client,url):
    for _ in range(100):
        try:
            if client.get(url).status_code==200:return
        except httpx.HTTPError:pass
        time.sleep(.2)
    raise RuntimeError("Container HTTP startup deadline exceeded")

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--build',choices=['002','003','004','005','006','007'],default='002');args=parser.parse_args()
    if args.build in {'005','006','007'}:
        from scripts.reviewer import environment as reviewer_environment
        env=reviewer_environment(ROOT/'.runtime/reviewer005','live',include_setup=True)
        if args.build=='007': env['DATABASE_URL']=env['KAIROS_MIGRATION_DATABASE_URL']
    else:
        env=environment()
    schema="image_smoke_"+uuid4().hex
    names=[]
    report={"method":"Actual built Docker images; isolated temporary PostgreSQL schema and private synthetic commands","checks":{}}
    with psycopg.connect(env['DATABASE_URL'],autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        from kairos_api.migrations import apply
        apply(make_conninfo(env['DATABASE_URL'],options=f'-c search_path={schema}'))
        runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime,prefix='image-smoke-') as temporary:
            token=secrets.token_urlsafe(32)
            settings=Path(temporary)/'api.env'
            settings.write_text('DATABASE_URL='+make_conninfo(env['DATABASE_URL'],host='host.docker.internal',options=f'-c search_path={schema}')+'\nKAIROS_DEV_TOKEN='+token+'\nKAIROS_DEV_TENANT=image-smoke\nKAIROS_ENV=development\nKAIROS_IDENTITY_MODE=development\n')
            settings.chmod(0o600)
            api='kairos-image-api-'+uuid4().hex[:12];names.append(api)
            docker('run','-d','--name',api,'--env-file',str(settings),'-p','127.0.0.1:8131:8100','kairos-api:build'+args.build)
            report['api_image_id']=docker('image','inspect','--format','{{.Id}}','kairos-api:build'+args.build)
            report['api_uid']=int(docker('exec',api,'id','-u'))
            with httpx.Client(timeout=15) as client:
                ready(client,'http://127.0.0.1:8131/api/health')
                headers={'Authorization':'Bearer '+token,'Idempotency-Key':'private-image-smoke'}
                command={'scenario_id':'late-order-standard','policy':'preserve','publish':False}
                first=client.post('http://127.0.0.1:8131/api/runs',headers=headers,json=command)
                repeat=client.post('http://127.0.0.1:8131/api/runs',headers=headers,json=command)
                conflict=client.post('http://127.0.0.1:8131/api/runs',headers=headers,json={**command,'policy':'compact'})
                checks=report['checks']
                if args.build in {'004','005','006','007'}:
                    command_headers={'Authorization':'Bearer '+token,'Idempotency-Key':'investigation-image-smoke'}
                    queued=client.post('http://127.0.0.1:8131/api/investigations',headers=command_headers,json={'task_id':'kairos-clock-lease','configuration':'baseline-v5' if args.build in {'006','007'} else 'baseline-v4'})
                    assert queued.status_code==202,queued.text
                    identifier=queued.json()['id'];base='http://127.0.0.1:8131/api/investigations/'+identifier
                    progress=client.get(base+'/progress',headers=command_headers)
                    checks['investigation_progress_without_bodies']=progress.status_code==200 and progress.json()['phase']=='queued' and 'steps' not in progress.json()
                    bundle=client.get(base+'/bundle',headers=command_headers)
                    checks['private_integrity_download']=bundle.status_code==200 and bundle.json()['integrity']['verified']
                    fork_headers={**command_headers,'Idempotency-Key':'investigation-fork-smoke'}
                    fork=client.post(base+'/fork',headers=fork_headers,json={})
                    repeated=client.post(base+'/fork',headers=fork_headers,json={})
                    checks['fork_retry_same_identity']=fork.status_code==repeated.status_code==202 and fork.json()['id']==repeated.json()['id']
                    page=client.get('http://127.0.0.1:8131/api/investigations?limit=1',headers=command_headers)
                    checks['investigation_cursor_page']=page.status_code==200 and len(page.json()['investigations'])==1 and bool(page.json()['next_cursor'])
                    for target in (identifier,fork.json()['id']):
                        assert client.post('http://127.0.0.1:8131/api/investigations/'+target+'/cancel',headers=command_headers,json={}).status_code==200
                    replay=client.get(base+'/replay',headers=command_headers)
                    checks['investigation_replay_no_execution']=replay.status_code==200 and replay.json()['network_calls']==replay.json()['tool_executions']==0
                checks['durable_private_idempotency']=first.status_code==repeat.status_code==201 and first.json()['id']==repeat.json()['id'] and first.json()['integrity']['verified']
                checks['payload_conflict']=conflict.status_code==409
                checks['private_not_published']=client.get('http://127.0.0.1:8131/api/public/incidents/'+first.json()['id']).status_code==404
                oversized=client.post('http://127.0.0.1:8131/api/runs',content=b'x'*32769)
                checks['body_limit_before_auth']=oversized.status_code==413
                web='kairos-image-web-'+uuid4().hex[:12];names.append(web)
                docker('run','-d','--name',web,'-e','KAIROS_API_URL=http://host.docker.internal:8131','-e','KAIROS_AUTH_LOGIN_URL=http://127.0.0.1:8131/api/auth/login','-p','127.0.0.1:3131:3100','kairos-web:build'+args.build)
                report['web_image_id']=docker('image','inspect','--format','{{.Id}}','kairos-web:build'+args.build)
                report['web_uid']=int(docker('exec',web,'id','-u'))
                ready(client,'http://127.0.0.1:3131/')
                checks['public_web_served']=client.get('http://127.0.0.1:3131/').status_code==200
                checks['production_local_mutation_denied']=client.post('http://127.0.0.1:3131/api/local-fork/'+first.json()['id'],json={'policy':'preserve'},headers={'Origin':'http://127.0.0.1:3131','Idempotency-Key':str(uuid4())}).status_code==403
                checks['private_proxy_anonymous_denied']=client.get('http://127.0.0.1:3131/api/workbench/jobs').status_code==401
                checks['unknown_public_report_not_fabricated']=client.get('http://127.0.0.1:3131/api/public-evaluations/'+str(uuid4())).status_code==404
                checks['investigation_schema_initialized']=client.get('http://127.0.0.1:8131/api/public/investigations').status_code==200
                checks['private_investigation_anonymous_denied']=client.get('http://127.0.0.1:3131/api/workbench/investigations').status_code==401
                checks['nonroot_images']=report['api_uid']>0 and report['web_uid']>0
                docker('stop',api)
                checks['outage_proxy_returns_unavailable']=client.get('http://127.0.0.1:3131/api/public-incidents').status_code==503
                checks['outage_home_never_fabricates_records']='Records are unavailable' in client.get('http://127.0.0.1:3131/').text
                if args.build in {'005','006','007'}:
                    docker('rm','-f',web)
                    recorded='kairos-image-recorded-'+uuid4().hex[:12];names.append(recorded)
                    docker('run','-d','--name',recorded,'-e','KAIROS_EVIDENCE_MODE=recorded','-e','KAIROS_API_URL=http://127.0.0.1:1','-p','127.0.0.1:3131:3100','kairos-web:build'+args.build)
                    ready(client,'http://127.0.0.1:3131/')
                    home=client.get('http://127.0.0.1:3131/').text
                    checks['recorded_image_genuine_cohort_no_api']=('10 recorded attempts' if args.build in {'006','007'} else '36 recorded attempts') in home and 'Recorded investigations. No live execution.' in home
                    repair=json.loads((ROOT/'dashboard/lib/followup006-cohort.json').read_text())['featured_id'] if args.build in {'006','007'} else '8b03a42f-149e-4d44-937f-0d61636f6042'
                    package=client.get('http://127.0.0.1:3131/api/public-investigations/'+repair+'/bundle')
                    checks['recorded_image_original_download']=package.status_code==200 and package.json()['id']==repair and package.json()['integrity']['verified']
                    denied=client.post('http://127.0.0.1:3131/api/workbench/investigations',json={})
                    checks['recorded_image_private_mutations_closed']=denied.status_code==403
                if not all(checks.values()): print(json.dumps(report,indent=2),flush=True)
                assert all(checks.values()),'Image smoke check failed'
                report['passed']=True
        report['limits']=['Development API auth used only inside isolated local smoke schema. Production OIDC has separate protocol/configuration tests.','No TLS edge or public hosting exercised.','All smoke runs private; temporary containers/schema removed.']
        output=ROOT/('evidence/build'+args.build+'/docker-smoke.json')
        output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        for name in reversed(names):
            subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        with psycopg.connect(env['DATABASE_URL'],autocommit=True) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

if __name__=='__main__':main()
