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
        results=[];start=time.monotonic();stop=start+seconds
        async def user(n):
            headers={'Authorization':'Bearer '+token,'X-Workspace':schema+'-'+str(n)}
            async with httpx.AsyncClient(base_url='http://127.0.0.1:8194',headers=headers,timeout=10,trust_env=False) as client:
                async def send(method,path,operation,**kwargs):
                    began=time.monotonic()
                    try:
                        response=await client.request(method,path,**kwargs);status=response.status_code;value=response.json()
                    except Exception as error: status=0;value={'error':type(error).__name__}
                    item={'stage':label,'client':n,'operation':operation,'status':status,'ms':round((time.monotonic()-began)*1000,3),'at_seconds':round(time.monotonic()-start,3)}
                    results.append(item);raw.write(json.dumps(item)+'\n')
                    return status,value
                while time.monotonic()<stop:
                    identity=uuid4().hex
                    status,record=await send('POST','/api/investigations','durable_ack',json={'task_id':'capacity-fixture','configuration':'baseline-v3'},headers={'Idempotency-Key':identity})
                    if status==202:
                        await send('GET','/api/investigations/'+record['id']+'/progress','summary_read')
                        retry,retried=await send('POST','/api/investigations','retry_ack',json={'task_id':'capacity-fixture','configuration':'baseline-v3'},headers={'Idempotency-Key':identity})
                        if retry==202 and retried['id']!=record['id']: raise AssertionError('Duplicate durable command')
                        await send('POST','/api/investigations/'+record['id']+'/cancel','cancel',json={})
                    await send('GET','/api/investigations?limit=25','summary_read')
                    await asyncio.sleep(.05)
        await asyncio.gather(*(user(i) for i in range(clients)))
        raw.flush();os.fsync(raw.fileno())
        report={'label':label,'clients':clients,'requested_seconds':seconds,'actual_seconds':round(time.monotonic()-start,2),'requests':len(results),'expected_quota_rejections':sum(r['status']==429 for r in results),'unexpected_errors':sum(r['status'] not in (200,202,429) for r in results),'operations':{}}
        for op in sorted(set(r['operation'] for r in results)):
            values=sorted(r['ms'] for r in results if r['operation']==op and r['status'] in (200,202))
            report['operations'][op]={'n':len(values),'p50_ms':statistics.median(values) if values else None,'p95_ms':values[max(0,math.ceil(len(values)*.95)-1)] if values else None,'max_ms':max(values) if values else None}
        report['unexpected_error_rate']=report['unexpected_errors']/max(1,len(results));summary.append(report)
        (output/'summary.json').write_text(json.dumps({'scope':'Fixture identity and task; actual HTTP, PostgreSQL commits and integrity reads. No inference or OIDC throughput claim.','stages':summary,'complete':False},indent=2));print(json.dumps(report),flush=True)
    async def run():
        while not server.started: await asyncio.sleep(.1)
        for clients in (1,5,10,20): await stage(clients,args.stage_seconds,'load-'+str(clients))
        await stage(10,args.soak_seconds,'soak-10')
    try:
        asyncio.run(run())
        (output/'summary.json').write_text(json.dumps({'scope':'Fixture identity and task; actual HTTP and PostgreSQL. No inference or OIDC throughput claim.','stages':summary,'complete':True},indent=2))
    finally:
        raw.close();server.should_exit=True;thread.join(timeout=5);repo.close()
        with psycopg.connect(url,autocommit=True) as connection: connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

if __name__=='__main__': main()
