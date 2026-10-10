import Link from "next/link";
export const metadata = { title: "Reproduction and guarantees" };
export default function Docs() {
  return (
    <div className="page-shell reading-page">
      <div className="page-heading">
        <span className="eyebrow">DOCUMENTATION / BUILD 001</span>
        <h1>
          A small surface.
          <br />
          <em>Explicit contracts.</em>
        </h1>
        <p>
          Start with the read-only evidence. Run controlled mutations only in
          your local developer environment.
        </p>
      </div>
      <div className="article-layout">
        <aside className="article-index">
          <a href="#setup">Local setup</a>
          <a href="#api">API surface</a>
          <a href="#guarantees">Guarantees & limits</a>
        </aside>
        <article className="prose">
          <section id="setup">
            <h2>Inspect locally</h2>
            <p>
              The frontend expects the execution API on port 8100 and serves on
              port 3100. Configure PostgreSQL and follow the repository’s
              backend setup instructions before starting the web app.
            </p>
            <pre>
              {[
                "python3 -m venv .venv",
                ".venv/bin/python -m pip install -r requirements-api.lock",
                "python3 scripts/configure_local.py",
                "docker compose --env-file .env.kairos.local up -d --wait",
                "python3 scripts/run_local.py seed",
                "cd dashboard && npm ci && cd ..",
                "# Start each service in a separate shell:",
                "python3 scripts/run_local.py api",
                "python3 scripts/run_local.py web",
              ].join(String.fromCharCode(10))}
            </pre>
            <p>
              Without the API, pages show an explicit evidence-service error. No
              sample results replace missing records.
            </p>
            <h3>Controlled fork interaction</h3>
            <p>
              The configure_local.py script creates ignored local credentials
              once. For manual setup, set KAIROS_ENABLE_LOCAL_MUTATIONS=true and
              KAIROS_DEV_TOKEN to a configured backend developer credential in
              the frontend server environment. Use localhost or 127.0.0.1.
              Production builds keep this mutation proxy disabled.
            </p>
            <p>
              The credential stays on the server. The proxy verifies same-origin
              requests and forwards an idempotency key. It supports only
              preserve-context reruns. Do not publish a local developer
              credential.
            </p>
          </section>
          <section id="api">
            <h2>The public read surface</h2>
            <div className="endpoint-list">
              <code>GET /api/health</code>
              <p>Service and database readiness.</p>
              <code>GET /api/public/incidents</code>
              <p>Published sanitized execution summaries.</p>
              <code>GET /api/public/incidents/:id</code>
              <p>
                Captured context, ordered events, decision, checks, and lineage.
              </p>
              <code>GET /api/public/evidence</code>
              <p>Service-supplied evidence and provenance.</p>
            </div>
            <h3>Private commands</h3>
            <p>
              POST /api/runs and POST /api/runs/:id/fork require a
              server-verified credential and an Idempotency-Key. Private reads
              are tenant scoped. A browser-supplied tenant header does not
              confer authority.
            </p>
          </section>
          <section id="guarantees">
            <h2>What this version establishes</h2>
            <ul>
              <li>
                Controlled reference-policy executions against synthetic order
                data.
              </li>
              <li>
                Run and event persistence in PostgreSQL, with acknowledgement
                after commit.
              </li>
              <li>
                Context inclusion records, an independent deterministic grader,
                and fresh fork lineage.
              </li>
              <li>
                Sanitized public records and authenticated private commands.
              </li>
            </ul>
            <h3>What remains open</h3>
            <p>
              Actual language-model qualification, checkpoint resume, external
              payment effects, administrator-resistant immutable history,
              off-host recovery, statistical release gates, managed identity,
              and public deployment.
            </p>
            <p>
              A failed check is useful evidence. An unavailable record is
              unavailable evidence. Neither is a successful production claim.
            </p>
            <Link className="text-link" href="/engineering">
              Read the design rationale ↗
            </Link>
          </section>
        </article>
      </div>
    </div>
  );
}
