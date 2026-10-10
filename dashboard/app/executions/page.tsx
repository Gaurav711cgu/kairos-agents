import Link from "next/link";
import { z } from "zod";
import { jobSummary } from "@/lib/workbench";
import { apiBase } from "@/lib/kairos-api";
import { CANONICAL_JOBS } from "@/lib/empirical-store";

export const dynamic = "force-dynamic";

export default async function Executions() {
  let jobs: z.infer<typeof jobSummary>[] = [];
  try {
    const r = await fetch(apiBase() + "/api/public/jobs", {
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    if (r.ok) {
      jobs = z.object({ jobs: z.array(jobSummary) }).parse(await r.json()).jobs;
    }
  } catch {
    // API offline; fall back to canonical empirical jobs
  }

  if (!jobs.length) {
    jobs = CANONICAL_JOBS.map((j) => ({
      id: j.id,
      scenario_id: j.scenario_id,
      policy: j.policy,
      runner: j.runner,
      status: j.status,
      created_at: j.created_at,
      updated_at: j.updated_at,
      attempt: j.attempt,
      max_attempts: j.max_attempts,
      model_calls: j.model_calls,
      cancel_requested: j.cancel_requested,
      publish: j.publish,
      parent_job_id: j.parent_job_id,
    }));
  }

  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">MODEL EXECUTIONS / RAW CAPTURE LEDGER</span>
        <h1>
          Failures are
          <br />
          <em>first-class records.</em>
        </h1>
        <p>
          Configured model calls on controlled synthetic scenarios.
          End-to-end failure can stem from schema violations, missing citations, or invalid
          policy classifications. Each raw request and response stays verifiable.
        </p>
      </div>

      <div className="report-index">
        {jobs.map((job) => (
          <Link
            className="report-row antigravity-card"
            key={job.id}
            href={"/executions/" + job.id}
          >
            <div>
              <strong>{job.scenario_id.replaceAll("-", " ").replaceAll("_", " ").toUpperCase()}</strong>
              <small>
                {job.runner} · {job.policy} · {job.model_calls} model call(s) · Attempt {job.attempt}/{job.max_attempts}
              </small>
            </div>
            <span
              className={
                "status " + (job.status === "SUCCEEDED" || job.status === "succeeded" ? "good" : "attention")
              }
            >
              {job.status.toUpperCase()}
            </span>
            <p className="mt-1 text-xs text-zinc-400 font-mono">
              Job ID: {job.id} [INSPECT CAPTURE]
            </p>
          </Link>
        ))}
      </div>

      <aside className="scope-note">
        <strong>Strict Runner Isolation</strong>
        <p>
          Reference-policy executions demonstrate deterministic behavior. Model runs capture live LLM inputs and outputs directly. A failed result remains immutable; zero fabricated passes or hidden rewrites.
        </p>
      </aside>
    </div>
  );
}
