"""Scoped durable execution HTTP routes; caller supplies authenticated tenant."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from kairos_api.jobs_repository import JobsRepository
from kairos_api.model_runtime import classify_and_grade
from kairos_api.grading import grade_decision


class JobCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: Literal["late-order-exception","late-order-standard","insufficient-evidence"] = "late-order-exception"
    policy: Literal["compact","preserve"] = "preserve"
    runner: Literal["reference","model"] = "reference"
    publish: bool = False


class RecoverCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["continue_known_result"]


class JobForkCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: Literal["compact","preserve"] = "preserve"
    runner: Literal["reference","model"] = "model"


def create_jobs_router(tenant_dependency, key_dependency, repository_dependency=None):
    router = APIRouter()
    if repository_dependency is None:
        repository = JobsRepository()
        repository.initialize()
        repository_dependency = lambda: repository

    @router.get("/api/jobs")
    def jobs(tenant_id=Depends(tenant_dependency),repository=Depends(repository_dependency)):
        return {"jobs":repository.list(tenant_id)}

    @router.post("/api/jobs",status_code=202)
    def enqueue(command:JobCommand,tenant_id=Depends(tenant_dependency),key=Depends(key_dependency),repository=Depends(repository_dependency)):
        return repository.enqueue(tenant_id,key,command.model_dump())

    @router.get("/api/jobs/{job_id}")
    def read(job_id:str,tenant_id=Depends(tenant_dependency),repository=Depends(repository_dependency)):
        return repository.read(job_id,tenant_id)

    @router.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id:str,tenant_id=Depends(tenant_dependency),repository=Depends(repository_dependency)):
        return repository.cancel(job_id,tenant_id)

    @router.post("/api/jobs/{job_id}/recover")
    def recover(job_id:str,command:RecoverCommand,tenant_id=Depends(tenant_dependency),repository=Depends(repository_dependency)):
        return repository.recover(job_id,tenant_id)

    @router.post("/api/jobs/{job_id}/fork",status_code=202)
    def fork(job_id:str,command:JobForkCommand,tenant_id=Depends(tenant_dependency),key=Depends(key_dependency),repository=Depends(repository_dependency)):
        parent = repository.read(job_id,tenant_id)
        return repository.enqueue(tenant_id,key,{"scenario_id":parent["scenario_id"],"policy":command.policy,
                                  "runner":command.runner,"publish":parent["publish"]},parent_job_id=job_id)

    @router.get("/api/jobs/{job_id}/replay")
    def replay(job_id:str,tenant_id=Depends(tenant_dependency),repository=Depends(repository_dependency)):
        return repository.replay(job_id,tenant_id)

    @router.get("/api/jobs/{job_id}/verify")
    def verify(job_id:str,tenant_id=Depends(tenant_dependency),repository=Depends(repository_dependency)):
        job = repository.read(job_id,tenant_id)
        if not job["integrity"]["verified"]:
            raise HTTPException(409,"Capture integrity/version mismatch")
        if job["runner"] == "model" and job["response"]:
            derived = classify_and_grade(job["scenario_id"],job["context_blocks"],job["response"]["body"])
            grade = derived["grade"]
            equal = bool(job["result"]) and derived["decision"] == job["result"]["decision"] and grade == job["result"]["grade"]
        elif job["result"] and job["result"]["decision"]:
            grade = grade_decision(job["scenario_id"],job["result"]["decision"])
            equal = grade == job["result"]["grade"]
        else:
            grade,equal = None,False
        return {"job_id":job_id,"mode":"deterministic-verification","network_calls":0,"external_effects":0,
                "captured_result_matches":equal,"independent_grade":grade,"integrity":job["integrity"]}

    @router.get("/api/jobs/{job_id}/blobs/{object_digest}")
    def blob(job_id:str,object_digest:str,tenant_id=Depends(tenant_dependency),repository=Depends(repository_dependency)):
        return repository.blob(job_id,tenant_id,object_digest)

    @router.get("/api/public/jobs")
    def public_jobs(repository=Depends(repository_dependency)):
        return {"jobs":repository.list(public=True)}

    @router.get("/api/public/jobs/{job_id}")
    def public_job(job_id:str,repository=Depends(repository_dependency)):
        return repository.read(job_id,public=True)

    return router
