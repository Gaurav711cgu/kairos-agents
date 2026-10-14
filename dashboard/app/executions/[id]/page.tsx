import { displayLabel } from "@/lib/display";
import Link from "next/link";
import { jobDetail, Job } from "@/lib/workbench";
import { apiBase } from "@/lib/kairos-api";
import { isRecordedEvidence, recordedHistoryError } from "@/lib/evidence-mode";
export const dynamic = "force-dynamic";
export default async function Execution({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let job: Job | null = null;
  let error = "";
  try {
    if (isRecordedEvidence()) throw new Error(recordedHistoryError);
    const r = await fetch(
      apiBase() + "/api/public/jobs/" + encodeURIComponent(id),
      { cache: "no-store", signal: AbortSignal.timeout(5000) },
    );
    if (!r.ok) throw Error("Execution unavailable (HTTP " + r.status + ").");
    job = jobDetail.parse(await r.json());
  } catch (e) {
    error = e instanceof Error ? e.message : "Execution unavailable.";
  }
  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">Captured model execution</span>
        <h1>
          {job ? displayLabel(job.status) : "Unavailable"}.<br />
          <em>Read the response.</em>
        </h1>
        <p>
          {job
            ? displayLabel(job.scenario_id) +
              " · " +
              displayLabel(job.policy) +
              " · " +
              displayLabel(job.runner)
            : error}
        </p>
      </div>
      {job && (
        <>
          <div className="job-context">
            <section>
              <span className="eyebrow">Exact context</span>
              {job.context_blocks.map((b) => (
                <article key={b.id} className={b.included ? "" : "omitted"}>
                  <strong>
                    {b.id} / {b.included ? "Included" : "Omitted"}
                  </strong>
                  <p>{b.content}</p>
                </article>
              ))}
            </section>
            <section>
              <span className="eyebrow">Ordered events</span>
              <ol className="job-events">
                {job.events.map((e) => (
                  <li key={e.seq}>
                    <span className="mono">{e.seq}</span>
                    <div>
                      <strong>{displayLabel(e.event_type)}</strong>
                      <details className="raw-record">
                        <summary>Captured payload</summary>
                        <textarea
                          readOnly
                          aria-label={"Event " + e.seq + " payload"}
                          value={JSON.stringify(e.payload, null, 2)}
                        />
                      </details>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          </div>
          {[
            ["Exact dispatched request", job.request],
            ["Raw provider response", job.response],
            ["Decision and independent grade", job.result],
            [
              "Error and local integrity",
              { error: job.error, integrity: job.integrity },
            ],
          ].map(([title, value]) => (
            <details
              className="raw-record"
              key={String(title)}
              open={
                title === "Raw provider response" ||
                title === "Decision and independent grade"
              }
            >
              <summary>{String(title)}</summary>
              <textarea
                readOnly
                aria-label={String(title)}
                value={JSON.stringify(value, null, 2)}
              />
            </details>
          ))}
          <aside className="scope-note">
            <strong>Execution evidence, not qualification</strong>
            <p>
              These are actual observations on controlled data. A successful
              HTTP call is not a correct task. Model identity and revision
              remain attached to the captured provider response. Hash
              consistency does not establish immutable history.
            </p>
          </aside>
        </>
      )}
      <Link className="text-link" href="/executions">
        All model executions
      </Link>
    </div>
  );
}
