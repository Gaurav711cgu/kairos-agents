# Local identity validation

Kairos build002 uses a real Keycloak26.8.0 provider with OIDC authorization code,
S256 PKCE, nonce and confidential-client token exchange. This is a local provider
integration; it is not evidence of a hosted managed-identity deployment.

## Start and provision

Use locked API environment first. From repository root:

1. `KAIROS_IDENTITY_PREPARE_ONLY=1 PYTHONPATH=. .venv/bin/python scripts/setup_identity.py`
2. Start official `quay.io/keycloak/keycloak:26.8.0` with ignored
   `.runtime/keycloak-bootstrap.env`, loopback8088->8080, persistent data volume,
   and `start-dev --http-port=8080 --hostname=http://127.0.0.1:8088`.
3. `PYTHONPATH=. .venv/bin/python scripts/setup_identity.py`
4. Load `.env.kairos.local` and `.runtime/identity.env` into API process environment
   without printing either. Root application uses `KAIROS_IDENTITY_MODE=oidc`.
5. Open `/workbench` and follow sign-in. Synthetic credentials are local-only in
   `.runtime/identity.local.json`, mode0600. Never publish this file or seed public
   credentials into source. The provider permits no registration or password grant
   for the application client.

The idempotent provisioning script creates one confidential client and four
synthetic accounts. Three subjects receive explicit PostgreSQL membership:
admin/operator/viewer roles across two tenants. The fourth valid provider subject
has no membership and must receive403 from Kairos. Setup grants these known
synthetic memberships; it must not run against a real production identity realm.

## Identity contract and boundaries

`install_identity(app)` registers routes once without opening the database. During
application lifespan, set `app.state.identity = initialize_identity(database_url)`
to validate provider configuration and initialize tables. The optional
`install_identity(app, database_url, config)` form initializes immediately for
isolated tools and tests. The hook installs `/api/auth/login`, `/callback`,
`/me`, `/logout` and returns a FastAPI-compatible `principal(request)` dependency.
Principal returns `{subject, tenant_id, role}` after signature/issuer/audience/
expiry/authorized-party validation or an opaque server-session lookup. The
membership table, not browser input or token role claims, selects tenant and role.
Every request rechecks active membership; role/revocation changes take effect on
its next request. `require_identity_role(principal, "operator")` protects writes.

Session cookies are HttpOnly, SameSite=Lax, opaque, hashed at rest, expire after
one hour by default and rotate at login. Auth responses are no-store and
no-referrer. Browser mutations require an exact configured web Origin. Access
bearer tokens are validated separately, and API service responses expose no
provider tokens. PKCE/state/nonce material lives on the server. Login state is
one-use, expires after ten minutes and is additionally bound to a browser cookie.
Return destinations are restricted to configured-origin root/workbench paths.

Local logout revokes the Kairos session. It does not claim to terminate all
provider SSO sessions or previously issued provider access tokens. Provider logout
and central revocation/backchannel integration need explicit deployment policy.
Membership revocation blocks both active Kairos sessions and valid bearer tokens.

Production configuration must set `KAIROS_ENV=production`; identity configuration
then rejects non-HTTPS issuer/callback/web origin and sets Secure cookies. Root
application also rejects developer credential authentication in production. Deploy
Keycloak in production mode with external durable database, TLS, secret injection,
provider backup/rotation and controlled proxy headers; `start-dev` is local-only.
Sessions are not refreshed; users authenticate again after expiry. This deliberately
bounds session lifetime without storing refresh tokens. Use one configured issuer;
changing issuer requires invalidating sessions and remapping memberships.

## Checks

Run tests with `TEST_DATABASE_URL` set privately and
`KAIROS_TEST_IDENTITY_PROVIDER=1 .venv/bin/python -m pytest tests/test_identity.py tests/test_identity_provider.py tests/test_identity_app.py -q --tb=short`.
All PostgreSQL tests create and drop their own randomly named schema; they do not
truncate product tables. Provider tests perform actual username/password
interaction against Keycloak followed by authorization-code exchange, strict
nonce/signature validation, membership check, one-use callback, immediate
membership revocation and local logout. They use private synthetic accounts and
redacted diagnostic representations.

Keycloak marks cookies Secure even on trustworthy HTTP loopback. Real browsers
accept loopback Secure cookies; httpx does not. The protocol test explicitly
forwards only provider127.0.0.1 realm cookies to the same loopback endpoint. No
provider cookie-security setting is weakened. Root browser validation separately
checks the actual browser redirect/session flow.
