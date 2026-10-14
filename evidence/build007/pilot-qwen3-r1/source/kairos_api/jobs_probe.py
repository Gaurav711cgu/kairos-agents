"""Reproducible six-cell durable local-model development probe; no quality gate."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from kairos_api.jobs_repository import JobsRepository
from kairos_api.worker import JobWorker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output",default="evidence/build002/model-jobs.json")
    parser.add_argument("--publish",action="store_true",help="Explicitly expose synthetic probe records; default private")
    parser.add_argument("--tenant",default="local-studio")
    parser.add_argument("--key-prefix",default="build002-model-development")
    args = parser.parse_args()
    repository = JobsRepository()
    repository.initialize()
    worker = JobWorker(repository)
    observations = []
    for scenario in ("late-order-exception","late-order-standard","insufficient-evidence"):
        for policy in ("compact","preserve"):
            job = repository.enqueue(args.tenant,f"{args.key_prefix}:{scenario}:{policy}",
                {"scenario_id":scenario,"policy":policy,"runner":"model","publish":args.publish})
            while job["status"] in {"queued","running"}:
                processed = worker.run_once()
                job = repository.read(job["id"],args.tenant)
                if processed is None and job["status"] == "running":
                    raise RuntimeError("Another worker owns the probe job; await it explicitly")
            observations.append(job)
            print(f"{scenario}/{policy}: {job['status']}; model_calls={job['model_calls']}",flush=True)
    report = {"created_at":datetime.now(timezone.utc).isoformat(),"task_set_version":"synthetic-orders-v1",
        "method":"Three synthetic development scenarios crossed with two context policies, one generation each. Not independent holdout samples or a release qualification.",
        "model_contract":"classification-v1 with deterministic amount tool and strict unmodified JSON parsing",
        "observations":observations,"count":len(observations),
        "grade_passed":sum(bool(j["result"] and j["result"]["grade"]["passed"]) for j in observations),
        "actual_model_calls":sum(j["model_calls"] for j in observations)}
    output = Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n")
    print(f"Saved {len(observations)} real durable model observations",flush=True)


if __name__ == "__main__":
    main()
