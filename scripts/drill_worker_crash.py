#!/usr/bin/env python3
"""Actual SIGKILL worker drills; controlled provider fixture, isolated PostgreSQL schema."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output",default="evidence/build002/worker-crash-drill.json")
    parser.add_argument("--child",choices=["dispatch","known-response"])
    parser.add_argument("--marker")
    parser.add_argument("--calls")
    args = parser.parse_args()
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from kairos_api.jobs_repository import JobsRepository
    from kairos_api.worker import JobWorker
    from fastapi import HTTPException
    valid = {"raw_response":'{"disposition":"zero","reason":"Already compensated","evidence_ids":["policy.exception","order.receipt"]}',"model":"controlled-crash-drill-fixture"}
    if args.child:
        repository = JobsRepository()
        def pause():
            Path(args.marker).write_text("committed-checkpoint")
            while True:
                time.sleep(1)
        def provider(_):
            with open(args.calls,"a") as target:
                target.write("dispatch\n")
                target.flush()
                os.fsync(target.fileno())
            if args.child == "dispatch":
                pause()
            return valid
        if args.child == "known-response":
            original = repository.capture_response
            def capture(job,response):
                original(job,response)
                pause()
            repository.capture_response = capture
        JobWorker(repository,provider).run_once()
        return
    url = os.environ["DATABASE_URL"]
    schema = "kairos_crash_drill_" + uuid4().hex
    output = Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with psycopg.connect(url,autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    report = {"method":"Actual subprocess SIGKILL at durable checkpoints; lease expiry advanced explicitly after process death.",
              "provider":"Controlled fixture; not model-quality evidence", "isolated_schema":schema,"drills":[]}
    try:
        with tempfile.TemporaryDirectory(prefix="kairos-crash-") as temporary:
            root = Path(temporary)
            scoped = make_conninfo(url,options=f"-c search_path={schema}")
            repository = JobsRepository(scoped,root/"blobs")
            repository.initialize()
            for phase in ("dispatch","known-response"):
                job = repository.enqueue("crash-drill",phase,{"scenario_id":"late-order-exception","policy":"preserve","runner":"model","publish":False})
                marker,calls = root/(phase+".ready"),root/(phase+".calls")
                environment = {**os.environ,"DATABASE_URL":scoped,"KAIROS_BLOB_DIR":str(root/"blobs")}
                process = subprocess.Popen([sys.executable,__file__,"--child",phase,"--marker",str(marker),"--calls",str(calls)],env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                try:
                    deadline = time.monotonic()+30
                    while not marker.exists():
                        if process.poll() is not None:
                            raise RuntimeError("Drill child exited before committed checkpoint")
                        if time.monotonic()>deadline:
                            raise RuntimeError("Drill checkpoint timeout")
                        time.sleep(.05)
                    before = repository.read(job["id"],"crash-drill")
                    process.send_signal(signal.SIGKILL)
                    process.wait(timeout=10)
                    assert process.returncode == -signal.SIGKILL
                    with repository.connect() as connection:
                        connection.execute("UPDATE kairos_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(job["id"],))
                    repository.reclaim_expired()
                    after = repository.read(job["id"],"crash-drill")
                    assert after["status"] == "unknown"
                    calls_before = len(calls.read_text().splitlines())
                    if phase == "known-response":
                        repository.recover(job["id"],"crash-drill")
                        def forbidden(_):
                            raise AssertionError("Known result dispatched twice")
                        resumed = JobWorker(repository,forbidden).run_once()
                        assert resumed["status"] == "succeeded" and resumed["model_calls"] == 1
                    else:
                        try:
                            repository.recover(job["id"],"crash-drill")
                        except HTTPException as error:
                            assert error.status_code == 409
                        else:
                            raise AssertionError("Unknown outcome continuation accepted")
                        assert JobWorker(repository).run_once() is None
                        resumed = repository.read(job["id"],"crash-drill")
                    calls_after = len(calls.read_text().splitlines())
                    assert calls_before == calls_after == 1
                    report["drills"].append({"phase":phase,"job_id":job["id"],"process_returncode":process.returncode,
                        "committed_stage_before_kill":before["stage"],"status_after_reclaim":after["status"],
                        "final_status":resumed["status"],"provider_dispatches":calls_after,
                        "redispatches":0,"captured_response":bool(resumed["response"]),
                        "integrity":resumed["integrity"],"events":resumed["events"]})
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=10)
                    process.stderr.close()
        report["passed"] = True
    finally:
        with psycopg.connect(url,autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
    output.write_text(json.dumps(report,indent=2)+"\n")
    print(f"Saved {len(report['drills'])} actual process-kill drills; passed={report['passed']}")


if __name__ == "__main__":
    main()
