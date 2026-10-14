import Link from "next/link";
import { isRecordedEvidence } from "@/lib/evidence-mode";
import { cookies } from "next/headers";
import { apiBase } from "@/lib/kairos-api";
import { Workbench } from "@/components/Workbench";

import { InvestigationWorkbench } from "@/components/InvestigationWorkbench";

export const dynamic = "force-dynamic";

export default async function Page() {
  if (isRecordedEvidence()) return <div className="page-shell"><header className="page-heading"><span className="eyebrow">Workbench / Local setup</span><h1>Start a new investigation.</h1><p>Kairos supports live investigations in an authenticated local workbench. This site currently opens completed investigation captures.</p></header><section className="scope-note"><h2>Choose your next step.</h2><p>Explore published source, patches and checks here. To submit a registered case and follow live progress, start the local workbench using the setup guide. Sign-in and submissions are available there.</p><div className="investigation-actions"><Link className="button primary" href="/docs#fullstack">Set up the live workbench</Link><Link className="button dark" href="/investigations">Explore investigations</Link></div></section></div>;

  let identity: { subject: string; tenant_id: string; role: string } | null =
    null;
  let unavailable = false;
  try {
    const response = await fetch(apiBase() + "/api/auth/me", {
      headers: { Cookie: (await cookies()).toString() },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (response.ok) identity = await response.json();
    else if (response.status !== 401) unavailable = true;
  } catch {
    unavailable = true;
  }

  const returnTo = process.env.KAIROS_WEB_ORIGIN || "http://127.0.0.1:3100";

  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">Workbench / Private execution</span>
        <h1>
          Investigate a real case.
          <br />
          <em>Review the evidence.</em>
        </h1>
        <p>
          Registered repository defects, bounded model tools and independent checks. Every investigation keeps its captured steps and observed outcome.
        </p>
      </div>
      {identity ? (
        <>
          <InvestigationWorkbench role={identity.role} workspace={identity.tenant_id} />
          <details className="raw-record"><summary>Historical synthetic order workbench</summary><Workbench identity={identity} /></details>
        </>
      ) : (
        <section className="workbench-login">
          <div>
            <span className="eyebrow">Identity before compute</span>
            <h2>Sign in to your workspace.</h2>
            <p>
              Sign in through the configured OIDC provider. Workspace membership
              and role determine access.
            </p>
            {unavailable ? (
              <p role="alert">
                Identity service unavailable. Private execution is closed until
                it returns.
              </p>
            ) : (
              <a
                className="button dark"
                href={
                  (process.env.KAIROS_AUTH_LOGIN_URL ||
                    apiBase() + "/api/auth/login") +
                  "?return_to=" +
                  encodeURIComponent(returnTo + "/workbench")
                }
              >
                Sign in
              </a>
            )}
          </div>
          <aside>
            <span className="eyebrow">What happens next</span>
            <ol>
              <li>Choose a registered historical repository case.</li>
              <li>Queue a bounded local model investigation.</li>
              <li>
                Inspect captured source, proposed edits and independent checks.
              </li>
              <li>Create a fresh fork and compare its captured outcome.</li>
            </ol>
            <small>
              Workspace roles and bounded execution control access to local compute.
            </small>
          </aside>
        </section>
      )}
    </div>
  );
}
