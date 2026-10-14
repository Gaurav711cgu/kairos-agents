# Identity trust boundary

Kairos supports one configured, trusted OIDC issuer per database installation. The membership and session tables currently identify users by provider subject within that single issuer. JWT validation checks the configured issuer, audience, signature, expiry and authorized party. Login also checks server-held state, the browser binding, PKCE and nonce.

Treat the configured issuer as immutable for an existing installation. Replacing a realm or changing the issuer without migrating identity data can let an unrelated subject from the new provider inherit the old subject's membership. A provider migration must revoke all existing sessions and pending login states, then explicitly rebuild or migrate memberships from verified old `(issuer, subject)` identities to verified new identities. Multi-provider support requires a schema migration that namespaces memberships and sessions by `(issuer, subject)`; it is not currently supported.

Multiple-audience tokens require `azp` equal to the configured client identifier. A single-audience token may omit `azp`; any present `azp` must still match the client. These checks follow [OpenID Connect Core ID Token Validation](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation), with a fail-closed policy for multiple audiences.

Local Keycloak runs exercise the real protocol. They do not establish public deployment, enterprise SSO interoperability, provider outage tolerance or customer adoption.

Production web pages, login and callback must share one public HTTPS origin. The edge routes `/api/auth/*` to the API and `/api/workbench/*` to Next.js. Session cookies are host-only; separate API and web subdomains are rejected. The edge must preserve the public `Host`, overwrite forwarded protocol headers and enforce the request-body limit before buffering.
