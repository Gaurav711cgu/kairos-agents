"""HTTP boundary with managed identity and explicit local development mode."""
from contextlib import asynccontextmanager
import hmac
import re

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psycopg

from kairos_api import __version__
from kairos_api.models import ForkCommand, RunCommand
from kairos_api.http_boundary import BoundedBodyMiddleware
from kairos_api.repository import CorruptRun, IdempotencyConflict, MissingRun, RunRepository
from kairos_api.settings import Settings, cors_origins


def create_app(settings: Settings | None = None, repository: RunRepository | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configured = settings or Settings.from_environment()
        application.state.settings = configured
        application.state.repository = repository or RunRepository(configured.database_url)
        application.state.repository.initialize()
        from kairos_api.jobs_repository import JobsRepository
        from kairos_api.evaluation import EvaluationRepository
        from kairos_api.effects import EffectRepository
        jobs = JobsRepository(configured.database_url)
        jobs.initialize()
        application.state.jobs_repository = jobs
        effects = EffectRepository(configured.database_url)
        effects.initialize()
        application.state.effects_repository = effects
        evaluation = EvaluationRepository(configured.database_url)
        evaluation.initialize()
        application.state.evaluation_repository = evaluation
        from kairos_api.investigations.repository import InvestigationRepository
        investigations = InvestigationRepository(configured.database_url,pooled=True)
        investigations.initialize()
        application.state.investigation_repository = investigations
        if configured.identity_mode == "oidc":
            from kairos_api.identity import initialize_identity
            application.state.identity = initialize_identity(configured.database_url)
        try:
            yield
        finally:
            investigations.close()

    application = FastAPI(title="Kairos controlled incident API", version=__version__, lifespan=lifespan)
    # CORS remains narrow; authorization is required independently of browser origin.
    origins = settings.origins if settings else cors_origins()
    application.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                               allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])
    application.add_middleware(BoundedBodyMiddleware)

    def repo(request: Request) -> RunRepository:
        return request.app.state.repository

    def jobs_repo(request: Request):
        return request.app.state.jobs_repository

    def investigations_repo(request: Request):
        return request.app.state.investigation_repository

    def effects_repo(request: Request):
        return request.app.state.effects_repository

    def evaluation_repo(request: Request):
        return request.app.state.evaluation_repository

    def tenant(request: Request, authorization: str | None = Header(default=None)) -> str:
        if request.app.state.settings.identity_mode == "oidc":
            from kairos_api.identity import require_identity_role
            principal = request.app.state.principal(request)
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                require_identity_role(principal, "operator")
            request.state.identity_subject = principal["subject"]
            request.state.identity_principal = principal
            return principal["tenant_id"]
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Developer bearer credential required.")
        token = authorization[7:]
        for candidate, tenant_id in request.app.state.settings.credentials.items():
            if hmac.compare_digest(token.encode(), candidate.encode()):
                return tenant_id
        raise HTTPException(status_code=401, detail="Invalid developer credential.")

    def approver(request: Request, tenant_id: str = Depends(tenant)) -> str:
        if request.app.state.settings.identity_mode == "oidc":
            from kairos_api.identity import require_identity_role
            require_identity_role(request.state.identity_principal, "admin")
        return tenant_id

    def command_key(idempotency_key: str | None = Header(default=None)) -> str:
        if not idempotency_key or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key):
            raise HTTPException(status_code=400, detail="Idempotency-Key required (1–128 letters, numbers, dots, colons, underscores or hyphens).")
        return idempotency_key

    from kairos_api.effects import EffectConflict

    @application.exception_handler(EffectConflict)
    async def effect_conflict_handler(_request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @application.exception_handler(MissingRun)
    async def missing_handler(_request, _error):
        return JSONResponse(status_code=404, content={"detail": "Run not found."})

    @application.exception_handler(IdempotencyConflict)
    async def conflict_handler(_request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @application.exception_handler(CorruptRun)
    async def corruption_handler(_request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @application.exception_handler(psycopg.Error)
    async def database_handler(_request, _error):
        return JSONResponse(status_code=503, content={"detail": "Database operation unavailable; retry with the same idempotency key."})

    @application.get("/api/health")
    def health(repository: RunRepository = Depends(repo)):
        repository.health()
        return {"status": "ok", "database": "connected", "version": __version__}

    @application.get("/api/public/incidents")
    def incidents(repository: RunRepository = Depends(repo)):
        return {"incidents": repository.public_list()}

    @application.get("/api/public/incidents/{run_id}")
    def incident(run_id: str, repository: RunRepository = Depends(repo)):
        return repository.read(run_id, public=True)

    @application.get("/api/public/evidence")
    def evidence(repository: RunRepository = Depends(repo)):
        return repository.evidence()

    @application.post("/api/runs", status_code=201)
    def run(command: RunCommand, tenant_id: str = Depends(tenant), key: str = Depends(command_key),
            repository: RunRepository = Depends(repo)):
        return repository.create(tenant_id, key, command.model_dump())

    @application.get("/api/runs/{run_id}")
    def private_run(run_id: str, tenant_id: str = Depends(tenant), repository: RunRepository = Depends(repo)):
        return repository.read(run_id, tenant_id=tenant_id)

    @application.post("/api/runs/{run_id}/fork", status_code=201)
    def fork(run_id: str, command: ForkCommand, tenant_id: str = Depends(tenant), key: str = Depends(command_key),
             repository: RunRepository = Depends(repo)):
        return repository.create(tenant_id, key, command.model_dump(), parent_run_id=run_id)

    from kairos_api.jobs import create_jobs_router
    from kairos_api.evaluation import create_evaluation_router
    from kairos_api.effects import create_effects_router
    from kairos_api.identity import install_identity
    application.state.principal = install_identity(application)
    application.include_router(create_jobs_router(tenant, command_key, jobs_repo))
    application.include_router(create_evaluation_router(tenant, repository_dependency=evaluation_repo))
    application.include_router(create_effects_router(tenant, command_key, approval_dependency=approver, repository_dependency=effects_repo))
    from kairos_api.investigations.routes import create_investigation_router
    application.include_router(create_investigation_router(tenant, command_key, approver, investigations_repo))
    return application


app = create_app()
