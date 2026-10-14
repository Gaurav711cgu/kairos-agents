"""Run `python -m kairos_api.worker`; one bounded provider dispatch per job."""
import argparse
import os
import time
from uuid import uuid4

from kairos_api.jobs_repository import JobsRepository, input_digest
from kairos_api.model_runtime import call_model, classify_and_grade, model_request
from kairos_api.runner import reference_decision
from kairos_api.grading import grade_decision
from kairos_api.scenarios import get_scenario


class JobWorker:
    def __init__(self, repository, provider=call_model, owner=None):
        self.repository = repository
        self.provider = provider
        self.owner = owner or "worker-" + uuid4().hex

    def run_once(self):
        job = self.repository.claim(self.owner)
        if not job:
            return None
        try:
            capture = self.repository.read(str(job["id"]),job["tenant_id"])
            if not capture["integrity"]["verified"]:
                return self.repository.finish(job,error={"code":"capture_integrity_mismatch"})
            if job["checkpoint_version"] != 1 or job["input_digest"] != input_digest(job["scenario_id"],job["policy"],job["context_blocks"]):
                return self.repository.finish(job,error={"code":"checkpoint_version_or_context_mismatch"})
            if job["cancel_requested"]:
                return self.repository.finish(job,error={"code":"cancelled_before_dispatch"})
            if job["runner"] == "reference":
                decision = reference_decision(job["context_blocks"], get_scenario(job["scenario_id"]))
                result = {"decision":decision,"grade":grade_decision(job["scenario_id"],decision),
                          "configuration":{"runner":"reference","model":None,"model_calls":0,"policy_version":"synthetic-policy-v1"},
                          "parse_error":None}
            else:
                # A known-result continuation never enters the dispatch path.
                if job["stage"] == "response_captured":
                    response = job["response"]["body"]
                    captured_body = self.repository.blobs.get(job["response"]["blob"]["sha256"])
                    if captured_body != response:
                        raise ValueError("Known response object differs from durable checkpoint")
                else:
                    request = model_request(job["context_blocks"])
                    if not self.repository.dispatch_intent(job,request):
                        return self.repository.finish(job,error={"code":"cancelled_or_deadline_before_dispatch"})
                    response = self.provider(request)
                    self.repository.capture_response(job,response)
                result = classify_and_grade(job["scenario_id"],job["context_blocks"],response)
                result["configuration"] = {"runner":"model","model":response.get("model"),
                    "model_revision":response.get("model_revision"),"model_calls":1,
                    "policy_version":"synthetic-policy-v1","contract_version":"classification-v1",
                    "arithmetic":"deterministic-verified-order-cents-divided-by-five"}
            return self.repository.finish(job,result=result)
        except Exception:
            # Provider/network exceptions after committed intent are ambiguous. No hidden retry.
            # Do not copy credential-bearing connection exceptions into public captures.
            try:
                current = self.repository.read(str(job["id"]),job["tenant_id"])
                uncertain = current["stage"] in {"dispatched","response_captured"}
                return self.repository.finish(job,error={"code":"dispatch_outcome_unknown" if uncertain else "worker_processing_error"},unknown=uncertain)
            except RuntimeError:
                # An expired/fenced worker may not mutate the winning owner's state.
                return {"id":str(job["id"]),"status":"fenced","error":{"code":"stale_lease_rejected"}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--poll-seconds",type=float,default=1)
    args = parser.parse_args()
    repository = JobsRepository()
    repository.initialize()
    worker = JobWorker(repository)
    while True:
        result = worker.run_once()
        if result:
            print(f"job={result['id']} status={result['status']}",flush=True)
        if args.once:
            break
        if not result:
            time.sleep(max(0.1,min(args.poll_seconds,30)))


if __name__ == "__main__":
    main()
