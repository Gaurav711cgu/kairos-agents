import { cookies } from "next/headers";
import Link from "next/link";
import { apiBase } from "@/lib/kairos-api";
import { Workbench } from "@/components/Workbench";

export const dynamic = "force-dynamic";

export default async function Page(props: {
  searchParams?: Promise<{ demo?: string }>;
}) {
  const searchParams = props.searchParams ? await props.searchParams : {};
  const cookieStore = await cookies();
  const isDemo =
    cookieStore.get("kairos_demo")?.value === "1" || searchParams.demo === "1";

  let identity: { subject: string; tenant_id: string; role: string } | null =
    null;
  let unavailable = false;

  if (isDemo) {
    identity = {
      subject: "usr_auditor_reviewer",
      tenant_id: "tenant_empiric_demo",
      role: "operator",
    };
  } else {
    try {
      const r = await fetch(apiBase() + "/api/auth/me", {
        headers: { Cookie: cookieStore.toString() },
        cache: "no-store",
        signal: AbortSignal.timeout(3000),
      });
      if (r.ok) identity = await r.json();
      else if (r.status !== 401) unavailable = true;
    } catch {
      unavailable = true;
    }
  }

  const returnTo = process.env.KAIROS_WEB_ORIGIN || "http://127.0.0.1:3100";

  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">WORKBENCH / PRIVATE EXECUTION</span>
        <h1>
          Run it. Break it.
          <br />
          <em>Keep the evidence.</em>
        </h1>
        <p>
          Bounded agent jobs, exact model responses and independent policy
          checks. Every failed output stays in the record.
        </p>
      </div>
      {identity ? (
        <Workbench identity={identity} />
      ) : (
        <section className="workbench-login">
          <div>
            <span className="eyebrow">IDENTITY BEFORE COMPUTE</span>
            <h2>
              Your workspace,
              <br />
              <em>your authority.</em>
            </h2>
            <p>
              Sign in through the configured OIDC provider, or launch the
              standalone Reviewer Sandbox with pre-configured Operator
              privileges.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginTop: "24px" }}>
              <Link
                className="button primary"
                href="/workbench?demo=1"
                style={{ justifyContent: "center", fontWeight: 600 }}
              >
                Launch Reviewer Sandbox [Operator Access] ↗
              </Link>

              {!unavailable && (
                <a
                  className="button dark"
                  href={
                    (process.env.KAIROS_AUTH_LOGIN_URL ||
                      apiBase() + "/api/auth/login") +
                    "?return_to=" +
                    encodeURIComponent(returnTo + "/workbench")
                  }
                  style={{ justifyContent: "center" }}
                >
                  Sign in with OIDC / Keycloak ↗
                </a>
              )}
            </div>

            {unavailable && (
              <p style={{ marginTop: "16px", fontSize: "12px", color: "var(--muted)" }}>
                [NOTE] Local Keycloak identity cluster is offline in this standalone view.
                Use the Reviewer Sandbox above to inspect the job ledger, dispatch bounded
                executions, and calibrate statistical release gates.
              </p>
            )}
          </div>
          <aside>
            <span className="eyebrow">WHAT HAPPENS NEXT</span>
            <ol>
              <li>Choose a synthetic case and context policy.</li>
              <li>Submit a reference or actual model job.</li>
              <li>
                Inspect the durable request, raw response and independent grade.
              </li>
              <li>Compare a fresh fork; keep unknown outcomes explicit.</li>
            </ol>
            <small>
              No payment provider. No public unlimited model compute.
            </small>
          </aside>
        </section>
      )}
    </div>
  );
}

