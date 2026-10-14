"""Measured local recovery/load drills. Never restore over the source database."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import statistics
import subprocess
import time
import tarfile
import tempfile
from uuid import uuid4

import httpx
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo, conninfo_to_dict
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

def _private_file(path):
    """Create backup files privately from their first byte, rather than chmod later."""
    return os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),"wb")


def _blob_bytes(root,key):
    if len(key)!=64 or any(character not in "0123456789abcdef" for character in key):
        raise ValueError("Invalid captured object name")
    data=(root/key).read_bytes()
    if hashlib.sha256(data).hexdigest()!=key:
        raise ValueError("Captured object digest mismatch")
    json.loads(data)
    return data


def _restore_blob_archive(archive,destination,expected):
    """Restore only regular digest-named objects; never extract archive paths."""
    destination.mkdir(mode=0o700,parents=True,exist_ok=False)
    seen=set()
    with tarfile.open(archive,"r:gz") as backup:
        for member in backup.getmembers():
            key=member.name
            if not member.isfile() or len(key)!=64 or any(c not in "0123456789abcdef" for c in key) or key in seen or key not in expected:
                raise ValueError("Unexpected object archive member")
            source=backup.extractfile(member)
            if source is None:
                raise ValueError("Object archive member unavailable")
            with source:
                data=source.read()
            if hashlib.sha256(data).hexdigest()!=key:
                raise ValueError("Restored object digest mismatch")
            json.loads(data)
            with _private_file(destination/key) as target:
                target.write(data)
                target.flush()
                os.fsync(target.fileno())
            seen.add(key)
    if seen!=set(expected):
        raise ValueError("Object archive misses captured references")
    descriptor=os.open(destination,os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return seen


def restore_with_blobs(env):
    """One exported database snapshot plus every object referenced by that snapshot."""
    from kairos_api.effects import EffectRepository
    from kairos_api.jobs_repository import JobsRepository
    from kairos_api.identity import IdentityRepository
    from kairos_api.evaluation import EvaluationRepository
    from kairos_api.investigations.repository import InvestigationRepository
    container=env.get("KAIROS_POSTGRES_CONTAINER","kairos-postgres-build001")
    parameters=conninfo_to_dict(env["DATABASE_URL"])
    username=parameters.get("user","kairos")
    database=parameters.get("dbname","kairos")
    target="kairos_blob_restore_"+uuid4().hex
    directory=ROOT/".runtime/backups"
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    directory.chmod(0o700)
    dump,archive=directory/(target+".dump"),directory/(target+".blobs.tar.gz")
    blob_root=Path(env.get("KAIROS_BLOB_DIR",str(ROOT/".runtime/blobs")))
    if not blob_root.is_absolute():
        blob_root=ROOT/blob_root
    started=time.perf_counter()
    with psycopg.connect(env["DATABASE_URL"]) as source:
        source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        source.execute("SET LOCAL lock_timeout='15s'")
        names=[row[0] for row in source.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'kairos_%' ORDER BY tablename")]
        if not names:
            raise RuntimeError("Source has no Kairos tables")
        # Existing writers finish before locks; subsequent writers wait for snapshot capture.
        source.execute(sql.SQL("LOCK TABLE {} IN SHARE MODE").format(sql.SQL(",").join(sql.Identifier("public",name) for name in names)))
        before={name:source.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))).fetchone()[0] for name in names}
        snapshot=source.execute("SELECT pg_export_snapshot()").fetchone()[0]
        captures=source.execute("SELECT request,response FROM kairos_jobs").fetchall()
        references=[]
        for request,response in captures:
            for capture in (request,response):
                if capture is not None:
                    references.append(capture["blob"]["sha256"])
        if 'kairos_investigation_artifacts' in names:
            references.extend(row[0] for row in source.execute('SELECT sha256 FROM kairos_investigation_artifacts').fetchall())
        objects=set(references)
        with _private_file(dump) as output:
            subprocess.run(["docker","exec",container,"pg_dump","-U",username,"-d",database,"-Fc","--snapshot",snapshot],stdout=output,check=True)
            output.flush()
            os.fsync(output.fileno())
        with _private_file(archive) as output:
            with tarfile.open(fileobj=output,mode="w:gz") as backup:
                for key in sorted(objects):
                    data=_blob_bytes(blob_root,key)
                    member=tarfile.TarInfo(key)
                    member.size=len(data)
                    member.mode=0o600
                    backup.addfile(member,io.BytesIO(data))
            output.flush()
            os.fsync(output.fileno())
        descriptor=os.open(directory,os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    # Locks and exported snapshot are released only after both backup files are complete.
    print("Consistent database/blob snapshot captured; source writers may resume.",flush=True)
    subprocess.run(["docker","exec",container,"createdb","-U",username,target],check=True)
    try:
        with dump.open("rb") as backup:
            subprocess.run(["docker","exec","-i",container,"pg_restore","-U",username,"-d",target,"--exit-on-error"],stdin=backup,check=True)
        restored=make_conninfo(env["DATABASE_URL"],dbname=target)
        after=counts(restored)
        with tempfile.TemporaryDirectory(prefix="kairos-restored-objects-") as temporary:
            restored_blobs=Path(temporary)/"blobs"
            restored_keys=_restore_blob_archive(archive,restored_blobs,objects)
            jobs=JobsRepository(restored,restored_blobs)
            runs=RunRepository(restored)
            investigations=InvestigationRepository(restored,restored_blobs)
            with psycopg.connect(restored) as connection:
                scoped_jobs=connection.execute("SELECT id,tenant_id FROM kairos_jobs ORDER BY id").fetchall()
                scoped_runs=connection.execute("SELECT id,tenant_id FROM kairos_runs ORDER BY id").fetchall()
                scoped_investigations=connection.execute("SELECT id,tenant_id FROM kairos_investigations ORDER BY id").fetchall()
            job_checks=[jobs.read(str(identifier),tenant)["integrity"]["verified"] for identifier,tenant in scoped_jobs]
            run_checks=[runs.read(str(identifier),tenant_id=tenant)["integrity"]["verified"] for identifier,tenant in scoped_runs]
            investigation_checks=[investigations.read(str(identifier),tenant)["integrity"]["verified"] for identifier,tenant in scoped_investigations]
            for _ in range(2):
                for repository in (runs,EffectRepository(restored),jobs,IdentityRepository(restored),EvaluationRepository(restored),investigations):
                    repository.initialize()
            migrated=counts(restored)
            job_after=[jobs.read(str(identifier),tenant)["integrity"]["verified"] for identifier,tenant in scoped_jobs]
            assert before==after==migrated and all(job_checks+run_checks+job_after+investigation_checks)
            assert restored_keys==objects
            # Check restored files independently of repository validation, for every reference.
            for key in references:
                _blob_bytes(restored_blobs,key)
            return {"kind":"consistent_postgresql_and_content_addressed_object_restore", "passed":True,
                "source":"Local PostgreSQL18 development database and referenced local model objects",
                "snapshot_method":"SHARE locks on existing public kairos_* tables; pg_export_snapshot supplied to pg_dump; referenced immutable objects copied before releasing locks",
                "target":"Fresh isolated database and fresh temporary object directory; both removed after verification",
                "backup_storage":"Ignored .runtime/backups; directory0700, database dump and object archive0600; private captures never published",
                "database_backup_sha256":hashlib.sha256(dump.read_bytes()).hexdigest(),"database_backup_bytes":dump.stat().st_size,
                "object_archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),"object_archive_bytes":archive.stat().st_size,
                "source_counts":before,"restored_counts":after,"after_two_schema_initializations":migrated,
                "jobs_verified":len(job_checks),"reference_runs_verified":len(run_checks),
                "captured_object_references_verified":len(references),"distinct_objects_restored":len(objects),
                "all_job_integrity_passed":all(job_checks+job_after),"all_reference_integrity_passed":all(run_checks),"investigation_records_verified":len(investigation_checks),"all_investigation_integrity_passed":all(investigation_checks),
                "object_inventory_sha256":hashlib.sha256(json.dumps(sorted(objects),separators=(",",":")).encode()).hexdigest(),
                "duration_seconds":round(time.perf_counter()-started,3),
                "limits":["Same host/container recovery; not regional disaster recovery or an immutable backup claim.",
                    "Includes every object referenced by this frozen database snapshot; unreferenced orphan objects are excluded.",
                    "Existing Kairos table writers wait during capture. Schema migration/DDL and blob deletion must remain stopped during this drill.",
                    "No production retention, offsite copy, encryption/key rotation or recovery-time objective is established."]}
    finally:
        subprocess.run(["docker","exec",container,"dropdb","-U",username,target],check=True)


def load(env):
    schema="load_"+uuid4().hex
    with psycopg.connect(env["DATABASE_URL"],autocommit=True) as c:c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    child=env.copy();child.update(DATABASE_URL=make_conninfo(env["DATABASE_URL"],options=f"-c search_path={schema}"),KAIROS_DEV_TOKEN=secrets.token_urlsafe(32),KAIROS_IDENTITY_MODE="development",KAIROS_ENV="development")
    from kairos_api.migrations import apply
    apply(child["DATABASE_URL"])
    process=subprocess.Popen([str(ROOT/".venv/bin/python"),"-m","uvicorn","kairos_api.app:app","--host","127.0.0.1","--port","8135","--log-level","error"],cwd=ROOT,env=child,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        with httpx.Client(timeout=10) as client:
            for _ in range(100):
                if process.poll() is not None:raise RuntimeError("Isolated load API failed startup")
                try:
                    if client.get("http://127.0.0.1:8135/api/health").status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise RuntimeError("Load API startup deadline exceeded")
        headers={"Authorization":"Bearer "+child["KAIROS_DEV_TOKEN"]}
        command={"scenario_id":"late-order-standard","policy":"preserve","publish":False}
        def request(i):
            started=time.perf_counter()
            with httpx.Client(timeout=30) as client:r=client.post("http://127.0.0.1:8135/api/runs",json=command,headers={**headers,"Idempotency-Key":"measured-"+str(i)})
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
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=["restore","restore-with-blobs","load"]);parser.add_argument("--output",required=True);args=parser.parse_args()
    result={"restore":restore,"restore-with-blobs":restore_with_blobs,"load":load}[args.mode](environment());result["recorded_at"]=datetime.now(timezone.utc).isoformat()
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in {"raw","source_counts","restored_counts","after_two_schema_initializations"}},indent=2))

if __name__=="__main__":main()
