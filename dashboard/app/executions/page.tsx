import { displayLabel } from "@/lib/display";
import Link from "next/link";
import { z } from "zod";
import { jobSummary } from "@/lib/workbench";
import { apiBase } from "@/lib/kairos-api";
import { isRecordedEvidence, recordedHistoryError } from "@/lib/evidence-mode";

export const dynamic = "force-dynamic";

export default async function Executions() {
  let jobs: z.infer<typeof jobSummary>[] = [];
  let error = "";
  try {
    if (isRecordedEvidence()) throw new Error(recordedHistoryError);
    const r = await fetch(apiBase() + "/api/public/jobs", {
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    if (!r.ok) throw Error("Source unavailable (HTTP " + r.status + ").");
    if (r.ok) {
      jobs = z.object({ jobs: z.array(jobSummary) }).parse(await r.json()).jobs;
    }
  } catch (failure) {
    error = failure instanceof Error ? failure.message : "Source unavailable.";
  }

  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">Model executions / Raw capture ledger</span>
        <h1>
          Model runs.
          <br />
          <em>Responses and checks.</em>
        </h1>
        <p>
          Configured model calls on controlled synthetic scenarios. End-to-end
          failure can stem from schema violations, missing citations, or invalid
          policy classifications. Each raw request and response stays
          verifiable.
        </p>
      </div>

      {error && (
        <p className="workbench-error" role="alert">
          {error}
        </p>
      )}
      {!error && !jobs.length && (
        <p className="empty-state">No published records yet.</p>
      )}
      <div className="report-index">
        {jobs.map((job) => (
          <Link
            className="report-row antigravity-card"
            key={job.id}
            href={"/executions/" + job.id}
          >
            <div>
              <strong>{displayLabel(job.scenario_id)}</strong>
              <small>
                {displayLabel(job.runner)} · {displayLabel(job.policy)} ·{" "}
                {job.model_calls} model call(s) · Attempt {job.attempt}/
                {job.max_attempts}
              </small>
            </div>
            <span
              className={
                "status " +
                (job.status === "SUCCEEDED" || job.status === "succeeded"
                  ? "good"
                  : "attention")
              }
            >
              {displayLabel(job.status)}
            </span>
            <p className="mt-1 text-xs text-zinc-400 font-mono">
              Job ID: {job.id}
            </p>
          </Link>
        ))}
      </div>

      <aside className="scope-note">
        <strong>About these runs</strong>
        <p>
          Reference-policy executions demonstrate deterministic behavior. Model
          runs capture live LLM inputs and outputs directly. Failed outputs
          remain captured. Local hashes check consistency; they do not establish
          immutable history.
        </p>
      </aside>
    </div>
  );
}
