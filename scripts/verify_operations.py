"""Measured local recovery/load drills. Never restore over the source database."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import statistics
import subprocess
import time
from uuid import uuid4

import httpx
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from kairos_api.repository import RunRepository

ROOT=Path(__file__).resolve().parents[1]

def environment():
    env=os.environ.copy()
    for line in (ROOT/".env.kairos.local").read_text().splitlines():
        if line and not line.startswith("#"):
            key,value=line.split("=",1);env[key]=value
    return env

def counts(database):
    with psycopg.connect(database) as c:
        names=[r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'kairos_%' ORDER BY tablename")]
        return {name:c.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))).fetchone()[0] for name in names}

def restore(env):
    container=os.environ.get("KAIROS_POSTGRES_CONTAINER","kairos-postgres-build001")
    target="kairos_restore_"+uuid4().hex
    directory=ROOT/".runtime/backups";directory.mkdir(parents=True,exist_ok=True)
    dump=directory/(target+".dump")
    started=time.perf_counter()
    before=counts(env["DATABASE_URL"])
    with dump.open("wb") as output:
        subprocess.run(["docker","exec",container,"pg_dump","-U","kairos","-d","kairos","-Fc"],stdout=output,check=True)
    dump.chmod(0o600)
    subprocess.run(["docker","exec",container,"createdb","-U","kairos",target],check=True)
    try:
        with dump.open("rb") as source:
            subprocess.run(["docker","exec","-i",container,"pg_restore","-U","kairos","-d",target,"--exit-on-error"],stdin=source,check=True)
        restored=make_conninfo(env["DATABASE_URL"],dbname=target)
        after=counts(restored)
        repo=RunRepository(restored)
        public=repo.public_list()
        checks=[repo.read(row["id"],public=True)["integrity"]["verified"] for row in public]
        # Initialize current additive schemas twice against restored data; no rows may disappear.
        from kairos_api.effects import EffectRepository
        from kairos_api.jobs_repository import JobsRepository
        from kairos_api.identity import IdentityRepository
        from kairos_api.evaluation import EvaluationRepository
        for _ in range(2):
            for cls in (RunRepository,EffectRepository,JobsRepository,IdentityRepository,EvaluationRepository):cls(restored).initialize()
        migrated=counts(restored)
        assert before==after==migrated and all(checks)
        return {"kind":"pg_dump_restore_additive_schema_drill","source":"local PostgreSQL18 development database","target":"fresh isolated database, dropped after verification","backup_sha256":hashlib.sha256(dump.read_bytes()).hexdigest(),"backup_bytes":dump.stat().st_size,"backup_storage":"ignored mode0600 local file; not published","source_counts":before,"restored_counts":after,"after_two_schema_initializations":migrated,"public_runs_verified":len(checks),"integrity_passed":all(checks),"duration_seconds":round(time.perf_counter()-started,3),"limits":["Same host/container; not regional disaster recovery.","Filesystem model blobs require separate backup; this drill covers PostgreSQL only.","No concurrent writers during snapshot count comparison."]}
    finally:
        subprocess.run(["docker","exec",container,"dropdb","-U","kairos",target],check=True)

def load(env):
    schema="load_"+uuid4().hex
    with psycopg.connect(env["DATABASE_URL"],autocommit=True) as c:c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    child=env.copy();child.update(DATABASE_URL=make_conninfo(env["DATABASE_URL"],options=f"-c search_path={schema}"),KAIROS_DEV_TOKEN=secrets.token_urlsafe(32),KAIROS_IDENTITY_MODE="development",KAIROS_ENV="development")
    process=subprocess.Popen([str(ROOT/".venv/bin/python"),"-m","uvicorn","kairos_api.app:app","--host","127.0.0.1","--port","8130","--log-level","error"],cwd=ROOT,env=child,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        with httpx.Client(timeout=10) as client:
            for _ in range(100):
                if process.poll() is not None:raise RuntimeError("Isolated load API failed startup")
                try:
                    if client.get("http://127.0.0.1:8130/api/health").status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise RuntimeError("Load API startup deadline exceeded")
        headers={"Authorization":"Bearer "+child["KAIROS_DEV_TOKEN"]}
        command={"scenario_id":"late-order-standard","policy":"preserve","publish":False}
        def request(i):
            started=time.perf_counter()
            with httpx.Client(timeout=30) as client:r=client.post("http://127.0.0.1:8130/api/runs",json=command,headers={**headers,"Idempotency-Key":"measured-"+str(i)})
            return {"latency_ms":(time.perf_counter()-started)*1000,"status":r.status_code,"id":r.json().get("id")}
        started=time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(request,range(120)))
        elapsed=time.perf_counter()-started
        with ThreadPoolExecutor(max_workers=8) as pool:duplicates=list(pool.map(request,[999]*8))
        with psycopg.connect(child["DATABASE_URL"]) as c:
            run_count=c.execute("SELECT count(*) FROM kairos_runs").fetchone()[0]
            events=c.execute("SELECT count(*) FROM kairos_events").fetchone()[0]
        assert all(r["status"]==201 for r in rows+duplicates) and run_count==121 and len({r["id"] for r in duplicates})==1
        latency=sorted(r["latency_ms"] for r in rows)
        return {"kind":"local_http_reference_load","requests":120,"concurrency":8,"duplicate_requests":8,"duplicate_run_count":1,"committed_runs":run_count,"committed_events":events,"errors":0,"seconds":round(elapsed,3),"requests_per_second":round(120/elapsed,3),"latency_ms":{"p50":round(statistics.median(latency),3),"p95":round(latency[int(.95*len(latency))-1],3),"max":round(max(latency),3)},"raw":rows,"limits":["Local CPU, local Docker PostgreSQL, no model/network provider and no production traffic claim.","Includes one HTTP client connection setup per request.","120 requests are a smoke load, not a capacity limit or SLO proof."]}
    finally:
        process.terminate()
        try:process.communicate(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.communicate()
        with psycopg.connect(env["DATABASE_URL"],autocommit=True) as c:c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))

def main():
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=["restore","load"]);parser.add_argument("--output",required=True);args=parser.parse_args()
    result=(restore if args.mode=="restore" else load)(environment());result["recorded_at"]=datetime.now(timezone.utc).isoformat()
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in {"raw","source_counts","restored_counts","after_two_schema_initializations"}},indent=2))

if __name__=="__main__":main()
