"use client";
import { displayLabel } from "@/lib/display";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { jobSummary, jobDetail, Job, reportSummary } from "@/lib/workbench";
import { z } from "zod";
import { EffectWorkbench } from "@/components/EffectWorkbench";
async function command(path: string, body?: unknown, key?: string) {
  const r = await fetch("/api/workbench/" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(key ? { "Idempotency-Key": key } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : data.error || "Request rejected (" + r.status + ").",
    );
  return data;
}
function Raw({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="raw-record">
      <summary>{title}</summary>
      <textarea
        readOnly
        aria-label={title}
        value={JSON.stringify(value, null, 2)}
      />
    </details>
  );
}
export function Workbench({
  identity,
}: {
  identity: { subject: string; tenant_id: string; role: string };
}) {
  const [loaded, setLoaded] = useState(false);
  const [jobs, setJobs] = useState<z.infer<typeof jobSummary>[]>([]);
  const [selected, setSelected] = useState<Job | null>(null);
  const [reports, setReports] = useState<z.infer<typeof reportSummary>[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [scenario, setScenario] = useState("late-order-exception");
  const [policy, setPolicy] = useState("preserve");
  const [runner, setRunner] = useState("reference");
  const [pending, setPending] = useState<{ key: string; body: unknown } | null>(
    null,
  );
  const storageKey =
    "kairos-pending-job:" + identity.tenant_id + ":" + identity.subject;
  const canWrite = identity.role === "operator" || identity.role === "admin";
  const refresh = useCallback(async () => {
    try {
      const [j, r] = await Promise.all([
        command("jobs"),
        command("evaluations"),
      ]);
      setJobs(z.object({ jobs: z.array(jobSummary) }).parse(j).jobs);
      setReports(
        z.object({ reports: z.array(reportSummary) }).parse(r).reports,
      );
      setLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not refresh.");
    }
  }, []);
  useEffect(() => {
    const initial = setTimeout(() => {
      void refresh();
      try {
        const stored = sessionStorage.getItem(storageKey);
        if (stored) {
          const saved = z
            .object({
              key: z.string().uuid(),
              body: z.object({
                scenario_id: z.enum([
                  "late-order-exception",
                  "late-order-standard",
                  "insufficient-evidence",
                ]),
                policy: z.enum(["compact", "preserve"]),
                runner: z.enum(["model", "reference"]),
                publish: z.literal(false),
              }),
            })
            .parse(JSON.parse(stored));
          setPending(saved);
          setScenario(saved.body.scenario_id);
          setPolicy(saved.body.policy);
          setRunner(saved.body.runner);
        }
      } catch {
        setError(
          "Pending command storage unavailable or invalid. Submission fails closed until command identity can be saved.",
        );
      }
    }, 0);
    const timer = setInterval(() => void refresh(), 4000);
    return () => {
      clearTimeout(initial);
      clearInterval(timer);
    };
  }, [refresh, storageKey]);
  useEffect(() => {
    if (!selected || !["queued", "running"].includes(selected.status)) return;
    const timer = setInterval(async () => {
      try {
        setSelected(jobDetail.parse(await command("jobs/" + selected.id)));
      } catch (e) {
        setError(String(e));
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [selected]);
  async function act(operation: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await operation();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed.");
    } finally {
      setBusy(false);
    }
  }
  async function durableCommand(path: string, body: unknown) {
    const name = storageKey + ":" + path;
    const stored = sessionStorage.getItem(name);
    const intent = stored
      ? JSON.parse(stored)
      : { key: crypto.randomUUID(), body };
    if (JSON.stringify(intent.body) !== JSON.stringify(body))
      throw Error(
        "An unconfirmed operation with different parameters is pending. Inspect the ledger before changing it.",
      );
    sessionStorage.setItem(name, JSON.stringify(intent));
    const result = await command(path, intent.body, intent.key);
    sessionStorage.removeItem(name);
    return result;
  }
  async function submit() {
    await act(async () => {
      const intent = pending || {
        key: crypto.randomUUID(),
        body: { scenario_id: scenario, policy, runner, publish: false },
      };
      sessionStorage.setItem(storageKey, JSON.stringify(intent));
      setPending(intent);
      setSelected(
        jobDetail.parse(await command("jobs", intent.body, intent.key)),
      );
      sessionStorage.removeItem(storageKey);
      setPending(null);
    });
  }
  return (
    <>
      <div className="workspace-identity">
        <div>
          <span className="eyebrow">Authenticated workspace</span>
          <strong>{identity.tenant_id}</strong>
          <small>
            {displayLabel(identity.role)} · {identity.subject}
          </small>
        </div>
        <button
          className="text-button"
          onClick={() =>
            void act(async () => {
              await command("auth/logout", {});
              window.location.assign("/workbench");
            })
          }
        >
          Sign out
        </button>
      </div>
      {error && (
        <div className="workbench-error" role="alert">
          {error}
        </div>
      )}
      <div className="workbench-grid">
        <section className="run-composer">
          <span className="eyebrow">01 / Submit a bounded job</span>
          <h2>Configure a job.</h2>
          <label htmlFor="scenario">Synthetic case</label>
          <select
            id="scenario"
            value={scenario}
            disabled={!!pending}
            onChange={(e) => setScenario(e.target.value)}
          >
            <option value="late-order-exception">
              Prior compensation exception
            </option>
            <option value="late-order-standard">Standard late order</option>
            <option value="insufficient-evidence">Missing evidence</option>
          </select>
          <label htmlFor="policy">Context policy</label>
          <select
            id="policy"
            value={policy}
            disabled={!!pending}
            onChange={(e) => setPolicy(e.target.value)}
          >
            <option value="preserve">Preserve exception</option>
            <option value="compact">Compact: omit exception</option>
          </select>
          <label htmlFor="runner">Runner</label>
          <select
            id="runner"
            value={runner}
            disabled={!!pending}
            onChange={(e) => setRunner(e.target.value)}
          >
            <option value="reference">Deterministic reference</option>
            <option value="model">Configured model</option>
          </select>
          <p>
            {runner === "model"
              ? "One bounded model classification; money is calculated by deterministic code. Raw invalid JSON remains a failed result."
              : "Reference execution tests system behavior. It is not a model-quality experiment."}
          </p>
          <button
            className="button dark"
            disabled={busy || !canWrite}
            onClick={() => void submit()}
          >
            {pending ? "Retry this request" : "Queue execution"}
          </button>
          {pending && (
            <small>
              Unconfirmed request retained. Retry uses the same payload and
              identity to prevent duplicate jobs.
            </small>
          )}
          {!canWrite && (
            <small>
              Viewer role can inspect records. Operator membership required to
              execute.
            </small>
          )}
        </section>
        <section className="job-ledger">
          <div className="section-top">
            <span className="eyebrow">02 / Durable job ledger</span>
            <button className="text-button" onClick={() => void refresh()}>
              Refresh
            </button>
          </div>
          {jobs.length ? (
            jobs.map((job) => (
              <button
                className={
                  "job-row " + (selected?.id === job.id ? "selected" : "")
                }
                key={job.id}
                onClick={() =>
                  void act(async () =>
                    setSelected(
                      jobDetail.parse(await command("jobs/" + job.id)),
                    ),
                  )
                }
              >
                <div>
                  <strong>{displayLabel(job.scenario_id)}</strong>
                  <small>
                    {displayLabel(job.runner)} · {displayLabel(job.policy)} ·
                    attempt {job.attempt}/{job.max_attempts}
                  </small>
                </div>
                <span
                  className={
                    "status " +
                    (job.status === "succeeded" ? "good" : "attention")
                  }
                >
                  {displayLabel(job.status)}
                </span>
              </button>
            ))
          ) : (
            <div className="empty-state">
              {loaded
                ? "No jobs in this tenant. The first execution starts here."
                : error
                  ? "Workspace records unavailable."
                  : "Loading durable workspace records…"}
            </div>
          )}
        </section>
      </div>
      {selected && (
        <section className="job-inspector">
          <div className="section-top">
            <div>
              <span className="eyebrow">03 / Captured execution</span>
              <h2>
                {displayLabel(selected.status)}
                <em> / {displayLabel(selected.runner)}</em>
              </h2>
              <small className="mono">{selected.id}</small>
            </div>
            <div className="job-actions">
              {canWrite && (
                <>
                  <button
                    className="text-button"
                    disabled={
                      busy || !["queued", "running"].includes(selected.status)
                    }
                    onClick={() =>
                      void act(async () =>
                        setSelected(
                          jobDetail.parse(
                            await durableCommand(
                              "jobs/" + selected.id + "/cancel",
                              {},
                            ),
                          ),
                        ),
                      )
                    }
                  >
                    Cancel
                  </button>
                  <button
                    className="text-button"
                    disabled={busy || selected.status !== "unknown"}
                    onClick={() =>
                      void act(async () =>
                        setSelected(
                          jobDetail.parse(
                            await durableCommand(
                              "jobs/" + selected.id + "/recover",
                              { mode: "continue_known_result" },
                            ),
                          ),
                        ),
                      )
                    }
                  >
                    Continue captured result
                  </button>
                  <button
                    className="button"
                    disabled={busy}
                    onClick={() =>
                      void act(async () =>
                        setSelected(
                          jobDetail.parse(
                            await durableCommand(
                              "jobs/" + selected.id + "/fork",
                              { policy: "preserve", runner: selected.runner },
                            ),
                          ),
                        ),
                      )
                    }
                  >
                    Fork with preserved context
                  </button>
                </>
              )}
            </div>
          </div>
          <p className="scope-note">
            A fresh fork starts a new isolated scenario. Recovery only continues
            a durably captured provider response; unknown requests are never
            silently redispatched. Cancellation cannot undo completed model
            work.
          </p>
          <div className="job-context">
            <div>
              <span className="eyebrow">Exact context selection</span>
              {selected.context_blocks.map((block) => (
                <article
                  key={block.id}
                  className={block.included ? "" : "omitted"}
                >
                  <strong>
                    {block.id}{" "}
                    <span>{block.included ? "Included" : "Omitted"}</span>
                  </strong>
                  <p>{block.content}</p>
                </article>
              ))}
            </div>
            <div>
              <span className="eyebrow">Event history</span>
              <ol className="job-events">
                {selected.events.map((event) => (
                  <li key={event.seq}>
                    <span className="mono">
                      {String(event.seq).padStart(2, "0")}
                    </span>
                    <div>
                      <strong>{displayLabel(event.event_type)}</strong>
                      <Raw title="Event payload" value={event.payload} />
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
          <div className="job-actions">
            <a
              className="text-button"
              href={"/api/workbench/jobs/" + selected.id + "/replay"}
            >
              Recorded playback JSON
            </a>
            <a
              className="text-button"
              href={"/api/workbench/jobs/" + selected.id + "/verify"}
            >
              Independent re-verification JSON
            </a>
          </div>
          <Raw title="Recorded model request" value={selected.request} />
          <Raw title="Raw provider response" value={selected.response} />
          <Raw title="Decision and independent grade" value={selected.result} />
          <Raw
            title="Error and integrity checks"
            value={{
              error: selected.error,
              integrity: selected.integrity,
              deadline: selected.deadline_at,
              checkpoint_version: selected.checkpoint_version,
            }}
          />
          <a
            className="text-button"
            href={"/api/workbench/jobs/" + selected.id}
            download={"kairos-job-" + selected.id + ".json"}
          >
            Download execution evidence
          </a>
        </section>
      )}
      <section className="release-workbench">
        <div>
          <span className="eyebrow">04 / Calibrate the release rule</span>
          <h2>Test the release rule.</h2>
          <p>
            1,024 fixed synthetic task pairs. Conservative finite-sample bounds;
            hard schema violations block release. Calibration does not measure
            model quality.
          </p>
          {canWrite && (
            <div className="calibration-actions">
              {[
                "null-calibration",
                "planted-regression",
                "reference-repair",
              ].map((mode) => (
                <button
                  className="button"
                  key={mode}
                  disabled={busy}
                  onClick={() =>
                    void act(async () => {
                      await command("evaluations", { mode });
                    })
                  }
                >
                  {displayLabel(mode)}
                </button>
              ))}
            </div>
          )}
        </div>
        <div>
          {reports.length ? (
            reports.map((r) => (
              <Link
                className="report-row"
                key={r.id}
                href={"/reports/" + r.id + "?private=1"}
              >
                <strong>{displayLabel(r.mode)}</strong>
                <span
                  className={
                    "status " +
                    (r.gate.verdict === "pass" ? "good" : "attention")
                  }
                >
                  {displayLabel(r.gate.verdict)}
                </span>
                <small>
                  {r.gate.n} paired tasks · {displayLabel(r.split)}
                </small>
              </Link>
            ))
          ) : (
            <p className="empty-state">
              {loaded
                ? "No private evaluations yet."
                : error
                  ? "Evaluation records unavailable."
                  : "Loading evaluation records…"}
            </p>
          )}
        </div>
      </section>
      <EffectWorkbench
        role={identity.role}
        scope={identity.tenant_id + ":" + identity.subject}
      />
    </>
  );
}
