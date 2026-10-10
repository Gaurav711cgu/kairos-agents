"use client";
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
          <span className="eyebrow">AUTHENTICATED WORKSPACE</span>
          <strong>{identity.tenant_id}</strong>
          <small>
            {identity.role} · {identity.subject}
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
          Sign out ↗
        </button>
      </div>
      {error && (
        <div className="workbench-error" role="alert">
          {error}
        </div>
      )}
      <div className="workbench-grid">
        <section className="run-composer">
          <span className="eyebrow">01 / SUBMIT A BOUNDED JOB</span>
          <h2>
            Choose the
            <br />
            <em>conditions.</em>
          </h2>
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
            <option value="model">Actual configured model</option>
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
            {pending ? "Retry same command identity ↗" : "Queue execution ↗"}
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
            <span className="eyebrow">02 / DURABLE JOB LEDGER</span>
            <button className="text-button" onClick={() => void refresh()}>
              Refresh ↻
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
                  <strong>{job.scenario_id.replaceAll("-", " ")}</strong>
                  <small>
                    {job.runner} · {job.policy} · attempt {job.attempt}/
                    {job.max_attempts}
                  </small>
                </div>
                <span
                  className={
                    "status " +
                    (job.status === "succeeded" ? "good" : "attention")
                  }
                >
                  {job.status}
                </span>
              </button>
            ))
          ) : (
            <div className="empty-state">
              No jobs in this tenant. The first execution starts here.
            </div>
          )}
        </section>
      </div>
      {selected && (
        <section className="job-inspector">
          <div className="section-top">
            <div>
              <span className="eyebrow">03 / CAPTURED EXECUTION</span>
              <h2>
                {selected.status}
                <em> / {selected.runner}</em>
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
                    Fresh preserve fork ↗
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
              <span className="eyebrow">EXACT CONTEXT SELECTION</span>
              {selected.context_blocks.map((block) => (
                <article
                  key={block.id}
                  className={block.included ? "" : "omitted"}
                >
                  <strong>
                    {block.id}{" "}
                    <span>{block.included ? "included" : "omitted"}</span>
                  </strong>
                  <p>{block.content}</p>
                </article>
              ))}
            </div>
            <div>
              <span className="eyebrow">EVENT HISTORY</span>
              <ol className="job-events">
                {selected.events.map((event) => (
                  <li key={event.seq}>
                    <span className="mono">
                      {String(event.seq).padStart(2, "0")}
                    </span>
                    <div>
                      <strong>{event.event_type}</strong>
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
              Recorded playback JSON ↗
            </a>
            <a
              className="text-button"
              href={"/api/workbench/jobs/" + selected.id + "/verify"}
            >
              Independent re-verification JSON ↗
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
            Download execution evidence ↓
          </a>
        </section>
      )}
      <section className="release-workbench">
        <div>
          <span className="eyebrow">04 / CALIBRATE THE RELEASE RULE</span>
          <h2>
            Pass. Fail.
            <br />
            <em>Inconclusive.</em>
          </h2>
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
                  {mode.replaceAll("-", " ")} ↗
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
                <strong>{r.mode.replaceAll("-", " ")}</strong>
                <span
                  className={
                    "status " +
                    (r.gate.verdict === "pass" ? "good" : "attention")
                  }
                >
                  {r.gate.verdict}
                </span>
                <small>
                  {r.gate.n} paired tasks · {r.split} ↗
                </small>
              </Link>
            ))
          ) : (
            <p className="empty-state">No private evaluations yet.</p>
          )}
        </div>
      </section>
      <EffectWorkbench role={identity.role} />
    </>
  );
}
