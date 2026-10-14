"use client";
import { CheckEvidence, PatchEvidence, StepEvidence } from "./InvestigationEvidence";
import { useState } from "react";
import Link from "next/link";
import { type Investigation, configurationLabel, elapsed, modelUsage, outcomeLabel } from "@/lib/investigations";
const readable = (value: unknown) => typeof value === "string" ? value : JSON.stringify(value, null, 2);
const stepLabel = (kind: string, name: string) => kind === "model" ? "Model chose a next step" : ({ selection: "Prepared the context", initial_source: "Retained original source", search: "Searched the source", read_file: "Read a file", propose_patch: "Reviewed the proposed change", run_checks: "Ran independent checks", draft_candidate: "Recorded an independent draft", draft_selection: "Selected the checked candidate" }[name] || name);
export function InvestigationInspector({ record, comparison, initialStep = 0, privateView = false, comparisons = [] }: { record: Investigation; comparison: Investigation | null; initialStep?: number; privateView?: boolean; comparisons?: Investigation[] }) {
  const [selected, setSelected] = useState(initialStep || record.steps[0]?.seq || 0);
  const step = record.steps.find(item => item.seq === selected);
  const patches = record.steps.filter(item => item.name === "propose_patch");
  const selection=record.steps.find(item=>item.name==="draft_selection")?.result?.body;
  const candidates=Array.isArray(selection?.candidates) ? selection.candidates as {draft_seq:number;patch_digest:string}[] : [];
  const winningDraft=candidates.find(item=>item.patch_digest===selection?.selected_patch_digest)?.draft_seq;
  const patch = [...patches].reverse().find(item => item.result && !item.result.body.error && (winningDraft===undefined || item.result.body.draft_seq===winningDraft));
  const checks = record.steps.filter(item => item.name === "run_checks");
  const latest = (selection?.selected_patch_digest ? checks.find(item=>item.result?.body.patch_digest===selection.selected_patch_digest) : checks.at(-1))?.result?.body;
  const select = (seq: number) => { setSelected(seq); if (privateView) return; const url = new URL(window.location.href); url.searchParams.set("step", String(seq)); window.history.replaceState(null, "", url); };
  const tokens = modelUsage(record);
  return <>
    <section className="investigation-verdict" aria-label={privateView ? "Investigation outcome" : "Recorded outcome"}>
      <div><span className="eyebrow">{privateView ? "Investigation outcome" : "Recorded outcome"}</span><h2 className={record.outcome === "verified_repair" ? "result-pass" : ""}>{record.integrity.verified ? outcomeLabel(record.outcome, record.status) : "Capture integrity failed"}</h2><p>{latest ? latest.passed ? "The candidate passed the registered regression and selected existing tests." : "The candidate did not pass independent verification." : record.outcome === "invalid_patch" ? "The proposed change was rejected before verification." : record.status === "queued" ? "Your command is saved and waiting for the worker." : record.status === "running" ? "Follow captured source, model actions and checks as this investigation runs." : "Inspect the saved steps to see where this attempt stopped."}</p><details className="raw-record"><summary>Read the stop reason and final summary</summary><p>{record.summary || "No final summary captured."}</p></details></div>
      <dl><div><dt>Model calls</dt><dd>{record.model_calls}</dd></div><div><dt>Captured tokens</dt><dd>{tokens || "Not captured"}</dd></div><div><dt>Elapsed</dt><dd>{elapsed(record) === null ? (record.started_at ? "Timing incomplete" : "Not started") : elapsed(record) + "s"}</dd></div><div><dt>Checks run</dt><dd>{record.check_count}</dd></div></dl>
    </section>
    {!record.integrity.verified && <p role="alert" className="error-state">Stored capture integrity failed. Do not rely on these results.</p>}
    <div className="investigation-actions"><a className="button dark" href={(privateView ? "/api/workbench/investigations/" : "/api/public-investigations/") + record.id + "/bundle"}>Download evidence</a>{patch && <a className="button dark" href={(privateView ? "/api/workbench/investigations/" : "/api/public-investigations/") + record.id + "/patch"}>Download patch</a>}<span>Local inference · $0 API spend</span></div>
    <section className="investigation-patch"><header><span className="eyebrow">Candidate change</span><h2>{patch ? "The proposed patch." : ["queued", "running"].includes(record.status) ? "Awaiting the proposed change." : "No accepted patch."}</h2></header>
      {patch ? <PatchEvidence patch={readable(patch.result?.body.patch ?? patch.request.body.patch)} /> : <p>{["queued", "running"].includes(record.status) ? "The proposed change appears here when the worker captures a candidate. Follow the execution phase above." : patches.length ? "The model proposed a patch that did not pass patch validation. Its exact response remains in the timeline." : "This attempt produced no patch. See the captured model response and stop reason below."}</p>}
      {latest && <CheckEvidence result={latest} />}
    </section>
    {!privateView && <section className="investigation-comparison" aria-label="Strategy comparison">
      <header><span className="eyebrow">Same source and verifier</span><h2>Compare the approach.</h2><p>Compare the observed outcome alongside calls, captured tokens and elapsed time. Each attempt has its own inference budget.</p></header>
      <div className="comparison-pair">{[record, ...(comparisons.length ? comparisons : [comparison])].map((item, index) => item ? <article key={item.id}>
        <span className="eyebrow">{configurationLabel(item.configuration)}{item.id === record.id ? " · Viewing" : ""}</span>
        <h3>{outcomeLabel(item.outcome, item.status)}</h3><p>{item.model_calls} {item.model_calls === 1 ? "call" : "calls"} · {modelUsage(item) || "Unreported"} tokens · {elapsed(item) === null ? (item.started_at ? "Timing incomplete" : "Not started") : elapsed(item) + "s"}</p>
        {item.id !== record.id && <Link className="text-link" href={"/investigations/" + item.id}>Inspect this attempt</Link>}
      </article> : <article key={"missing-" + index}><h3>Comparison unavailable</h3><p>No paired attempt has been published yet.</p></article>)}</div>
    </section>}
    <section className="investigation-source"><header><span className="eyebrow">Source record</span><h2>{record.task_snapshot.repository}</h2></header>
      <dl><div><dt>Revision</dt><dd className="mono">{record.task_snapshot.revision}</dd></div><div><dt>Evaluation split</dt><dd>{record.task_snapshot.split === "evaluation" ? "Locked evaluation" : record.task_snapshot.split === "validation" ? "Locked validation" : "Development"}</dd></div><div><dt>Verification command</dt><dd><code>{record.task_snapshot.command.join(" ")}</code></dd></div></dl>
      <p>{record.task_snapshot.provenance}</p><div className="investigation-actions">{record.task_snapshot.issue_url && <a className="text-link" href={record.task_snapshot.issue_url} target="_blank" rel="noreferrer">Original issue</a>}{record.task_snapshot.source_url.startsWith("https://github.com/") && <a className="text-link" href={record.task_snapshot.source_url} target="_blank" rel="noreferrer">Pinned source</a>}</div>
      <details className="raw-record"><summary>Read the issue</summary><pre role="region" aria-label="Captured evidence" tabIndex={0}>{record.task_snapshot.issue}</pre></details>
    </section>
    <section className="investigation-timeline"><header><span className="eyebrow">Captured execution</span><h2>Follow each step.</h2><p>Replay shows saved records. It does not call the model or execute tools.</p></header>
      <div className="timeline-layout"><ol aria-label="Investigation steps">{record.steps.map(item => <li key={item.seq}><button aria-pressed={selected === item.seq} onClick={() => select(item.seq)}><span className="mono">{String(item.seq).padStart(2, "0")}</span><span>{stepLabel(item.kind, item.name)}<small>{item.state === "captured" ? "Captured" : "Outcome unknown"}</small></span></button></li>)}</ol>
        <div className="timeline-detail" aria-live="polite">{step ? <><h3>{stepLabel(step.kind, step.name)}</h3><p>Step {step.seq} · {step.state}</p><StepEvidence step={step} /><details className="raw-record"><summary>Exact captured result</summary><pre role="region" aria-label="Captured evidence" tabIndex={0}>{step.result ? readable(step.result.body) : "No result captured. This step must not be assumed to have failed safely."}</pre></details><details className="raw-record"><summary>Exact request</summary><pre role="region" aria-label="Captured evidence" tabIndex={0}>{readable(step.request.body)}</pre></details><p className="capture-digest">Request SHA-256 <code>{step.request.sha256}</code></p></> : <p>No execution steps recorded.</p>}</div>
      </div>
    </section>
  </>;
}
