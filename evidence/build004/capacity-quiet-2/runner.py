"""Bounded local HTTP capacity experiment. Real PG; isolated schema and fixture identity.
No model calls, no production rows. Every request is preserved as JSONL.
"""
import argparse, asyncio, collections, json, math, os, secrets, statistics, threading, time
from pathlib import Path
from uuid import uuid4
import httpx, psycopg, uvicorn
from psycopg import sql
from psycopg.conninfo import make_conninfo
from fastapi import FastAPI, Header, HTTPException
from kairos_api.investigations.registry import CaseRegistry
from kairos_api.investigations.repository import InvestigationRepository
from kairos_api.investigations.routes import create_investigation_router


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='evidence/build004/capacity');parser.add_argument('--stage-seconds',type=int,default=180);parser.add_argument('--soak-seconds',type=int,default=1800);args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    for line in Path('.env.kairos.local').read_text().splitlines():
        if line and not line.startswith('#'):
            key,value=line.split('=',1);os.environ[key]=value
    url=os.environ['TEST_DATABASE_URL'];schema='capacity_'+uuid4().hex
    runtime=Path('.runtime/capacity')/schema;runtime.mkdir(parents=True)
    manifest=runtime/'cases.json';manifest.write_text(json.dumps({'version':'repository-cases-v1','cases':[{'id':'capacity-fixture','title':'Control-plane fixture only','qualified':True}]}))
    token=secrets.token_urlsafe(24)
    def tenant(authorization:str=Header(''),x_workspace:str=Header('')):
        if authorization!='Bearer '+token or not x_workspace.startswith(schema): raise HTTPException(401)
        return x_workspace
    def key(idempotency_key:str=Header()): return idempotency_key
    with psycopg.connect(url,autocommit=True) as connection: connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    repo=InvestigationRepository(make_conninfo(url,options='-c search_path='+schema),runtime/'blobs',CaseRegistry(manifest,runtime),pooled=True);repo.initialize()
    app=FastAPI();app.include_router(create_investigation_router(tenant,key,tenant,lambda:repo))
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8194,access_log=False,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    raw=(output/'requests.jsonl').open('w');summary=[]
    async def stage(clients,seconds,label):
        latencies=collections.defaultdict(list);statuses=collections.Counter();total=0;start=time.monotonic();stop=start+seconds
        async def user(n):
            headers={'Authorization':'Bearer '+token,'X-Workspace':schema+'-'+str(n)}
            pending_identity=None;pending_record=None
            async with httpx.AsyncClient(base_url='http://127.0.0.1:8194',headers=headers,timeout=10,trust_env=False) as client:
                async def send(method,path,operation,**kwargs):
                    nonlocal total
                    began=time.monotonic();status=0
                    try:
                        response=await client.request(method,path,**kwargs);status=response.status_code
                        try:value=response.json()
                        except ValueError:value={'error':'NonJsonResponse'}
                    except httpx.HTTPError as error:value={'error':type(error).__name__}
                    item={'stage':label,'client':n,'operation':operation,'status':status,'ms':round((time.monotonic()-began)*1000,3),'at_seconds':round(time.monotonic()-start,3)}
                    total+=1;statuses[status]+=1
                    if status in (200,202):latencies[operation].append(item['ms'])
                    raw.write(json.dumps(item)+'\n')
                    return status,value
                while time.monotonic()<stop:
                    # An uncertain acknowledgement retains its identity and command.
                    # An uncertain cancellation retains its target until confirmed.
                    if pending_identity is None:pending_identity=uuid4().hex
                    if pending_record is None:
                        status,record=await send('POST','/api/investigations','durable_ack',json={'task_id':'capacity-fixture','configuration':'baseline-v3'},headers={'Idempotency-Key':pending_identity})
                        if status==202 and isinstance(record,dict) and record.get('id'):pending_record=record
                        elif status in (400,403,404,409,422):pending_identity=None
                    if pending_record is not None:
                        await send('GET','/api/investigations/'+pending_record['id']+'/progress','summary_read')
                        retry,retried=await send('POST','/api/investigations','retry_ack',json={'task_id':'capacity-fixture','configuration':'baseline-v3'},headers={'Idempotency-Key':pending_identity})
                        if retry==202 and retried.get('id')!=pending_record['id']:raise AssertionError('Duplicate durable command')
                        cancelled,_=await send('POST','/api/investigations/'+pending_record['id']+'/cancel','cancel',json={})
                        if cancelled==200:pending_identity=None;pending_record=None
                    await send('GET','/api/investigations?limit=25','summary_read')
                    await asyncio.sleep(.05)
        await asyncio.gather(*(user(i) for i in range(clients)))
        raw.flush();os.fsync(raw.fileno())
        report={'label':label,'clients':clients,'requested_seconds':seconds,'actual_seconds':round(time.monotonic()-start,2),'requests':total,'observed_quota_rejections':statuses[429],'unexpected_errors':sum(count for status,count in statuses.items() if status not in (200,202,429)),'non_success_rate':sum(count for status,count in statuses.items() if status not in (200,202))/max(1,total),'status_counts':dict(statuses),'operations':{}}
        for op,recorded in sorted(latencies.items()):
            values=sorted(recorded)
            report['operations'][op]={'n':len(values),'p50_ms':statistics.median(values) if values else None,'p95_ms':values[max(0,math.ceil(len(values)*.95)-1)] if values else None,'max_ms':max(values) if values else None}
        report['unexpected_error_rate']=report['unexpected_errors']/max(1,total);summary.append(report)
        (output/'summary.json').write_text(json.dumps({'scope':'Fixture identity and task; actual HTTP, PostgreSQL commits and integrity reads. No inference or OIDC throughput claim.','stages':summary,'complete':False},indent=2));print(json.dumps(report),flush=True)
    async def run():
        while not server.started: await asyncio.sleep(.1)
        for clients in (1,5,10,20): await stage(clients,args.stage_seconds,'load-'+str(clients))
        await stage(10,args.soak_seconds,'soak-10')
    try:
        asyncio.run(run())
        (output/'summary.json').write_text(json.dumps({'scope':'Fixture identity and task; actual HTTP and PostgreSQL. No inference or OIDC throughput claim.','stages':summary,'complete':True,'protocol':'capacity-v2-stable-commands','quota_expected':False,'host_policy':'No builds, browser checks or inference run concurrently during the quiet repeat.'},indent=2))
    finally:
        raw.close();server.should_exit=True;thread.join(timeout=5);repo.close()
        with psycopg.connect(url,autocommit=True) as connection: connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

if __name__=='__main__': main()
