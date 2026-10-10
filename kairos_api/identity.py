"""OIDC code flow with server-held state, PKCE, nonce and revocable membership.

Provider tokens never enter browser JSON or local storage. Sessions are opaque,
hashed at rest and short-lived; membership is rechecked on every request.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse

from authlib.integrations.httpx_client import OAuth2Client
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
import httpx
import jwt
import psycopg
from psycopg.rows import dict_row

COOKIE = "kairos_session"
BINDING_COOKIE = "kairos_login_binding"
ROLE_LEVEL = {"viewer": 0, "operator": 1, "admin": 2}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class IdentityConfig:
    issuer: str
    client_id: str
    client_secret: str
    callback: str
    web_origin: str
    secure: bool = False
    session_seconds: int = 3600

    @classmethod
    def from_environment(cls):
        prod = os.environ.get("KAIROS_ENV", "development") == "production"
        config = cls(os.environ.get("KAIROS_OIDC_ISSUER", ""),
                     os.environ.get("KAIROS_OIDC_CLIENT_ID", "kairos-web"),
                     os.environ.get("KAIROS_OIDC_CLIENT_SECRET", ""),
                     os.environ.get("KAIROS_OIDC_CALLBACK", "http://127.0.0.1:8100/api/auth/callback"),
                     os.environ.get("KAIROS_WEB_ORIGIN", "http://127.0.0.1:3100"), prod,
                     int(os.environ.get("KAIROS_SESSION_SECONDS", "3600")))
        if not config.issuer or not config.client_secret or len(config.client_secret) < 24:
            raise ValueError("OIDC issuer and confidential client secret required.")
        if prod and any(urlparse(url).scheme != "https" for url in (config.issuer, config.callback, config.web_origin)):
            raise ValueError("Production identity requires HTTPS issuer, callback and web origin.")
        if not 60 <= config.session_seconds <= 86400:
            raise ValueError("Session lifetime outside allowed range.")
        return config


class IdentityRepository:
    def __init__(self, database_url):
        self.database_url = database_url

    def connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=5)

    def initialize(self):
        with self.connect() as connection:
            connection.execute(Path(__file__).with_name("schema_identity.sql").read_text())

    def membership(self, subject):
        with self.connect() as connection:
            row = connection.execute("SELECT subject, tenant_id, role FROM kairos_memberships WHERE subject=%s AND active", (subject,)).fetchone()
        if not row:
            raise HTTPException(403, "Active workspace membership required.")
        return dict(row)

    def save_state(self, state, verifier, nonce, binding, return_to):
        with self.connect() as connection:
            connection.execute("DELETE FROM kairos_login_states WHERE expires_at < now()")
            connection.execute("INSERT INTO kairos_login_states VALUES (%s,%s,%s,%s,%s,%s)",
                               (digest(state), verifier, nonce, digest(binding), return_to,
                                datetime.now(timezone.utc) + timedelta(minutes=10)))

    def consume_state(self, state, binding):
        if not binding:
            raise HTTPException(400, "Invalid or expired login state.")
        with self.connect() as connection:
            row = connection.execute("DELETE FROM kairos_login_states WHERE state_hash=%s AND binding_hash=%s AND expires_at>now() RETURNING *",
                                     (digest(state), digest(binding))).fetchone()
        if not row:
            raise HTTPException(400, "Invalid or expired login state.")
        return row

    def session(self, session_token):
        with self.connect() as connection:
            row = connection.execute("SELECT subject FROM kairos_sessions WHERE session_hash=%s AND expires_at>now()", (digest(session_token),)).fetchone()
        if not row:
            raise HTTPException(401, "Session expired or revoked.")
        return self.membership(row["subject"])

    def create_session(self, subject, seconds):
        session_token = secrets.token_urlsafe(48)
        with self.connect() as connection:
            connection.execute("DELETE FROM kairos_sessions WHERE expires_at < now()")
            connection.execute("INSERT INTO kairos_sessions(session_hash,subject,expires_at) VALUES (%s,%s,%s)",
                               (digest(session_token), subject, datetime.now(timezone.utc) + timedelta(seconds=seconds)))
        return session_token

    def revoke_session(self, token):
        with self.connect() as connection:
            connection.execute("DELETE FROM kairos_sessions WHERE session_hash=%s", (digest(token),))


class IdentityService:
    def __init__(self, config, repository):
        self.config, self.repository = config, repository
        self._metadata = None
        self._jwks = None

    def metadata(self):
        if self._metadata is None:
            with httpx.Client(timeout=10, follow_redirects=False) as client:
                response = client.get(self.config.issuer + "/.well-known/openid-configuration")
                response.raise_for_status()
                metadata = response.json()
            if metadata.get("issuer") != self.config.issuer:
                raise HTTPException(503, "Identity provider issuer mismatch.")
            # Discovery cannot redirect code/token material to a different origin.
            expected = urlparse(self.config.issuer)
            for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                endpoint = urlparse(metadata.get(key, ""))
                if (endpoint.scheme, endpoint.netloc) != (expected.scheme, expected.netloc):
                    raise HTTPException(503, "Identity provider endpoint mismatch.")
            self._metadata = metadata
        return self._metadata

    def validate_token(self, token, *, nonce=None, access=False):
        try:
            # Reject malformed or unsupported tokens before provider network access.
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                raise ValueError("algorithm")
            metadata = self.metadata()
            if self._jwks is None or not any(key.get("kid") == header.get("kid") for key in self._jwks["keys"]):
                with httpx.Client(timeout=10) as client:
                    response = client.get(metadata["jwks_uri"])
                    response.raise_for_status()
                    self._jwks = response.json()
            candidates = [key for key in self._jwks["keys"] if key.get("kid") == header.get("kid") and key.get("kty") == "RSA"]
            if len(candidates) != 1:
                raise ValueError("key")
            key = jwt.PyJWK.from_dict(candidates[0], algorithm="RS256").key
            claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self.config.issuer,
                                audience=self.config.client_id, leeway=5,
                                options={"require": ["exp", "iat", "iss", "aud", "sub"]})
            if not isinstance(claims["sub"], str) or not claims["sub"]:
                raise ValueError("subject")
            if access and claims.get("typ") != "Bearer":
                raise ValueError("access token required")
            if nonce is not None and (not isinstance(claims.get("nonce"), str) or not hmac.compare_digest(claims["nonce"], nonce)):
                raise ValueError("nonce")
            if claims.get("azp") not in (None, self.config.client_id):
                raise ValueError("authorized party")
            return claims
        except HTTPException:
            raise
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            raise HTTPException(401, "Identity token validation failed.") from None
        except httpx.HTTPError:
            raise HTTPException(503, "Identity provider unavailable.") from None

    def principal(self, request: Request):
        authorization = request.headers.get("authorization")
        if authorization:
            if not authorization.startswith("Bearer "):
                raise HTTPException(401, "Bearer token required.")
            claims = self.validate_token(authorization[7:], access=True)
            return self.repository.membership(claims["sub"])
        session_token = request.cookies.get(COOKIE)
        if not session_token:
            raise HTTPException(401, "Sign in required.")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.headers.get("origin") != self.config.web_origin:
            raise HTTPException(403, "Workspace origin required for cookie mutations.")
        return self.repository.session(session_token)


def require_identity_role(principal, minimum="operator"):
    if ROLE_LEVEL.get(principal.get("role"), -1) < ROLE_LEVEL[minimum]:
        raise HTTPException(403, f"{minimum.capitalize()} role required.")
    return principal


def initialize_identity(database_url, config=None):
    """Lifespan factory: validate configuration and initialize tables once."""
    configured = config or IdentityConfig.from_environment()
    repository = IdentityRepository(database_url)
    repository.initialize()
    return IdentityService(configured, repository)


def install_identity(application, database_url=None, config=None):
    """Register routes once, with lazy app.state.identity service lookup.

    Production app factory calls this without database_url, then installs the
    initialized service during lifespan. Supplying database_url is a convenience
    for isolated tests/tools and initializes immediately before app startup.
    """
    if database_url is not None:
        application.state.identity = initialize_identity(database_url, config)

    def get_service(request):
        service = getattr(request.app.state, "identity", None)
        if service is None:
            raise HTTPException(503, "Identity service not initialized.")
        return service

    def principal(request: Request):
        return get_service(request).principal(request)

    @application.get("/api/auth/me")
    def me(request: Request):
        return JSONResponse(principal(request), headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @application.get("/api/auth/login")
    def login(request: Request, return_to: str = "/workbench"):
        service = get_service(request)
        configured, repository = service.config, service.repository
        if return_to.startswith("/") and not return_to.startswith("//"):
            destination = configured.web_origin + return_to
        else:
            destination = return_to
        target, origin = urlparse(destination), urlparse(configured.web_origin)
        if (target.scheme, target.netloc) != (origin.scheme, origin.netloc) or target.path not in {"/workbench", "/workbench/", "/"}:
            raise HTTPException(400, "Return destination not allowed.")
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        verifier, binding = secrets.token_urlsafe(64), secrets.token_urlsafe(32)
        with OAuth2Client(configured.client_id, configured.client_secret, redirect_uri=configured.callback,
                          scope="openid profile", code_challenge_method="S256") as client:
            url, _ = client.create_authorization_url(service.metadata()["authorization_endpoint"],
                                                      state=state, nonce=nonce, code_verifier=verifier)
        repository.save_state(state, verifier, nonce, binding, destination)
        response = RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        response.set_cookie(BINDING_COOKIE, binding, httponly=True, secure=configured.secure,
                            samesite="lax", max_age=600, path="/api/auth")
        return response

    @application.get("/api/auth/callback")
    def callback(request: Request, state: str = "", code: str = "", error: str = ""):
        service = get_service(request)
        configured, repository = service.config, service.repository
        pending = repository.consume_state(state, request.cookies.get(BINDING_COOKIE))
        if error or not code:
            raise HTTPException(400, "Provider did not authorize login.")
        try:
            with OAuth2Client(configured.client_id, configured.client_secret, redirect_uri=configured.callback,
                              token_endpoint_auth_method="client_secret_basic", timeout=10) as client:
                token = client.fetch_token(service.metadata()["token_endpoint"], grant_type="authorization_code",
                                           code=code, code_verifier=pending["verifier"])
            claims = service.validate_token(token.get("id_token", ""), nonce=pending["nonce"])
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(401, "Identity authorization exchange failed.") from None
        repository.membership(claims["sub"])
        if request.cookies.get(COOKIE):
            repository.revoke_session(request.cookies[COOKIE])
        session_token = repository.create_session(claims["sub"], configured.session_seconds)
        response = RedirectResponse(pending["return_to"], status_code=302, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        response.delete_cookie(BINDING_COOKIE, path="/api/auth")
        response.set_cookie(COOKIE, session_token, httponly=True, secure=configured.secure,
                            samesite="lax", max_age=configured.session_seconds, path="/")
        return response

    @application.post("/api/auth/logout")
    def logout(request: Request):
        service = get_service(request)
        service.principal(request)
        service.repository.revoke_session(request.cookies.get(COOKIE, ""))
        response = JSONResponse({"status": "signed_out"}, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        response.delete_cookie(COOKIE, path="/", secure=service.config.secure, httponly=True, samesite="lax")
        return response

    return principal
