"""HTTP boundary. Local developer credentials are an interim auth mechanism."""
from contextlib import asynccontextmanager
import hmac
import re

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psycopg

from kairos_api import __version__
from kairos_api.models import ForkCommand, RunCommand
from kairos_api.repository import CorruptRun, IdempotencyConflict, MissingRun, RunRepository
from kairos_api.settings import Settings, cors_origins


def create_app(settings: Settings | None = None, repository: RunRepository | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configured = settings or Settings.from_environment()
        application.state.settings = configured
        application.state.repository = repository or RunRepository(configured.database_url)
        application.state.repository.initialize()
        yield

    application = FastAPI(title="Kairos controlled incident API", version=__version__, lifespan=lifespan)
    # CORS remains narrow; authorization is required independently of browser origin.
    origins = settings.origins if settings else cors_origins()
    application.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                               allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])

    def repo(request: Request) -> RunRepository:
        return request.app.state.repository

    def tenant(request: Request, authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Developer bearer credential required.")
        token = authorization[7:]
        for candidate, tenant_id in request.app.state.settings.credentials.items():
            if hmac.compare_digest(token.encode(), candidate.encode()):
                return tenant_id
        raise HTTPException(status_code=401, detail="Invalid developer credential.")

    def command_key(idempotency_key: str | None = Header(default=None)) -> str:
        if not idempotency_key or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key):
            raise HTTPException(status_code=400, detail="Idempotency-Key required (1–128 letters, numbers, dots, colons, underscores or hyphens).")
        return idempotency_key

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

    return application


app = create_app()
