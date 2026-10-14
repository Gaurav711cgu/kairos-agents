import type { Investigation } from "@/lib/investigations";

type Body = Record<string, unknown>;
const object = (value: unknown): Body => value && typeof value === "object" && !Array.isArray(value) ? value as Body : {};
const text = (value: unknown) => typeof value === "string" ? value : "";
type ChangedLine = { number: number; code: string };
type FileChange = { path: string; before: ChangedLine[]; after: ChangedLine[] };

// These are display coordinates from the recorded unified diff, never reconstructed source.
function changedFiles(patch: string): FileChange[] {
  const files: FileChange[] = [];
  let file: FileChange | undefined;
  let before = 0;
  let after = 0;
  for (const line of patch.split("\n")) {
    if (line.startsWith("+++ b/")) { file = { path: line.slice(6), before: [], after: [] };files.push(file);continue; }
    if (line.startsWith("--- a/")) continue;
    const hunk = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
    if (hunk) { before = Number(hunk[1]);after = Number(hunk[2]);continue; }
    if (!file) continue;
    if (line.startsWith("-")) file.before.push({ number: before++, code: line.slice(1) });
    else if (line.startsWith("+")) file.after.push({ number: after++, code: line.slice(1) });
    else if (line.startsWith(" ")) { before++;after++; }
  }
  return files;
}
function ChangeSide({ label, lines }: { label: "Before" | "After"; lines: ChangedLine[] }) {
  return <div className={"change-side " + label.toLowerCase()}><h4>{label}</h4><pre role="region" aria-label={label + " changed lines"} tabIndex={0}>{lines.length ? lines.map((line, i) => <span className="change-line" key={i}><span className="change-number" aria-label={"Line " + line.number}>{line.number}</span><code>{line.code || " "}</code>{"\n"}</span>) : <span className="change-empty">No lines {label === "Before" ? "removed" : "added"}.</span>}</pre></div>;
}
export function PatchEvidence({ patch }: { patch: string }) {
  const files = changedFiles(patch);
  const removed = files.reduce((n, file) => n + file.before.length, 0);
  const added = files.reduce((n, file) => n + file.after.length, 0);
  return <div className="patch-evidence">
    <p className="evidence-explainer">{files.length} {files.length === 1 ? "file" : "files"} changed. {removed} {removed === 1 ? "line" : "lines"} removed; {added} {added === 1 ? "line" : "lines"} added.</p>
    {files.map((file, i) => <article className="file-change" key={i}><header><span>Source file</span><h3><code>{file.path}</code></h3></header><div className="change-pair"><ChangeSide label="Before" lines={file.before} /><ChangeSide label="After" lines={file.after} /></div></article>)}
    <details className="raw-record"><summary>View complete diff and surrounding code</summary><pre role="region" className="patch-diff" tabIndex={0} aria-label="Unified patch diff">{patch.split("\n").map((line, i) => <span key={i} className={line.startsWith("+") ? "diff-add" : line.startsWith("-") ? "diff-remove" : ""}>{line + "\n"}</span>)}</pre></details>
  </div>;
}
export function CheckEvidence({ result }: { result: Body }) {
  const output = text(result.stderr) + "\n" + text(result.stdout);
  const count = typeof result.tests_run === "number" ? String(result.tests_run) : /Ran (\d+) tests? in/.exec(output)?.[1];
  const skips = /skipped=(\d+)/.exec(output)?.[1];
  const error = output.split("\n").reverse().find(line => /^(AssertionError|ModuleNotFoundError|ImportError|FAILED|ERROR)/.test(line));
  const label = result.environment_error ? "Checks could not run" : result.passed ? "Checks passed" : "Checks failed";
  return <div className="check-evidence"><h3 className={result.passed ? "result-pass" : ""}>{label}</h3>
    <p>{count ? `${count} tests run.${skips ? ` ${skips} skipped.` : ""}` : result.passed ? "The registered verification command completed successfully." : "The candidate did not pass the registered verification command."} {typeof result.seconds === "number" ? `${result.seconds.toFixed(1)} seconds.` : ""}</p>
    {!result.passed && <p className="check-reason">{error || `Command exit status: ${String(result.returncode ?? "unavailable")}.`}</p>}
    {result.output_truncated === true && <p>Output reached its capture limit. The saved tail is available below.</p>}
    <details className="raw-record"><summary>Read test output</summary>{text(result.stdout) && <><h4>Standard output</h4><pre role="region" aria-label="Test standard output" tabIndex={0}>{text(result.stdout)}</pre></>}{text(result.stderr) && <><h4>Test runner output</h4><pre role="region" aria-label="Test runner output" tabIndex={0}>{text(result.stderr)}</pre></>}</details>
  </div>;
}
function SourceEvidence({ result }: { result: Body }) {
  return <div className="source-evidence"><p><code>{text(result.path)}</code>{typeof result.start_line === "number" ? ` · From line ${result.start_line}` : ""}</p><pre role="region" aria-label="Retrieved source excerpt" tabIndex={0}>{text(result.text)}</pre>{result.truncated === true && <p>This excerpt was shortened to fit the retrieval limit.</p>}</div>;
}
export function StepEvidence({ step }: { step: Investigation["steps"][number] }) {
  if (!step.result) return <p>No result was captured. The dispatch outcome remains unknown.</p>;
  const result = step.result.body;
  if (step.name === "draft_candidate") return <div className="step-explanation"><h4>{result.error ? "Draft rejected" : result.selected ? "Draft selected before checks" : "Valid draft outside the two-candidate limit"}</h4><p>{typeof result.error === "string" ? result.error : "All six fresh-context drafts are recorded before either selected candidate is checked."}</p>{typeof result.patch === "string" && <PatchEvidence patch={result.patch}/>}</div>;
  if (step.name === "draft_selection") return <div className="step-explanation"><h4>Independent drafts completed</h4><p>The first two structurally valid drafts were selected before verification. The displayed patch follows the saved verification decision.</p><p>{Array.isArray(result.candidates) ? result.candidates.length : 0} candidates checked. Exact patch identity remains in the capture.</p></div>;
  if (typeof result.error === "string") return <div className="step-explanation"><h4>Request rejected</h4><p>{result.error}</p><p>The rejected request remains in the exact capture below.</p></div>;
  if (step.name === "run_checks") return <CheckEvidence result={result} />;
  if (step.name === "propose_patch") return <div className="step-explanation"><h4>Patch accepted for checking</h4><p>Source replacements passed path and patch validation. Acceptance here does not mean the repair works.</p>{typeof result.patch === "string" && <PatchEvidence patch={result.patch} />}</div>;
  if (step.name === "read_file" || step.name === "initial_source") return <><p>{typeof result.selection_reason === "string" ? result.selection_reason : "Original source retained before model execution."}</p><SourceEvidence result={result} /></>;
  if (step.name === "search") {
    const matches = Array.isArray(result.matches) ? result.matches.map(object) : [];
    return <div className="step-explanation"><p>{matches.length} source matches for <code>{text(step.request.body.query)}</code>.</p>{matches.map((match, i) => <p key={i}><code>{text(match.path)}{typeof match.line === "number" ? ":" + match.line : ""}</code><br />{text(match.text)}</p>)}</div>;
  }
  if (step.name === "selection") {
    const selection = object(result.selection);
    const budgets = object(selection.budgets);
    const omissions = Array.isArray(result.omissions) ? result.omissions.map(object) : [];
    const omitted = omissions.length || (Array.isArray(result.omitted_observation_indices) ? result.omitted_observation_indices.length : 0);
    const observations = Array.isArray(selection.observations) ? selection.observations.map(object) : [];
    const sourceBlocks = Array.isArray(selection.source_blocks) ? selection.source_blocks.map(object) : [];
    return <div className="step-explanation"><h4>Evidence selected for the next call</h4><p>The issue, remaining budget and latest verification result stay in context.</p><dl className="context-budget"><div><dt>Calls left</dt><dd>{String(budgets.calls_remaining ?? "Unreported")}</dd></div><div><dt>Patches left</dt><dd>{String(budgets.patches_remaining ?? "Unreported")}</dd></div><div><dt>Checks left</dt><dd>{String(budgets.checks_remaining ?? "Unreported")}</dd></div></dl><p>{typeof result.rendered_input_tokens === "number" ? `${result.rendered_input_tokens} input tokens after the chat template. ` : typeof result.input_tokens_before_chat_template === "number" ? `${result.input_tokens_before_chat_template} input tokens before the chat template. ` : ""}{omitted ? `${omitted} evidence ${omitted === 1 ? "region" : "regions"} omitted or shortened; inspect the capture for exact selection details.` : "No observation omissions recorded."}</p>{omissions.length>0 && <details className="raw-record"><summary>Why evidence was omitted</summary><ul>{omissions.map((omission,i)=><li key={i}>{String(omission.reason || "Unreported reason")}{typeof omission.observation_index === "number" ? ` · Observation ${omission.observation_index+1}` : ""}</li>)}</ul></details>}{sourceBlocks.map((source, i)=><SourceEvidence key={"v5-"+i} result={{path:source.path,start_line:source.start_line,text:source.numbered_original_source ?? source.original_source}}/>)}{observations.map((observation, i) => {
      let source = object(observation.result);
      if (Array.isArray(source.lines)) source={...source,text:source.lines.map(line=>Array.isArray(line)?`${String(line[0])}: ${String(line[1])}`:"").join("\n")};
      if (typeof observation.excerpt === "string") { try { source = object(object(JSON.parse(observation.excerpt)).result); } catch { return <p key={i}>Source observation {i + 1} was shortened. Its exact captured excerpt is available below.</p>; } }
      return typeof source.text === "string" ? <SourceEvidence key={i} result={source} /> : null;
    })}</div>;
  }
  if (step.kind === "model") {
    const choice = object(Array.isArray(result.choices) ? result.choices[0] : null);
    const content = text(object(choice.message).content);
    let action: Body = {};
    try { action = object(JSON.parse(content)); } catch { /* The raw invalid response remains inspectable. */ }
    const labels: Record<string, string> = { propose_patch: "Proposed source replacements", search: "Requested a source search", read_file: "Requested a file excerpt", run_checks: "Requested independent checks", final_result: "Submitted a final summary" };
    return <div className="step-explanation"><h4>{labels[text(action.action)] || "Response captured"}</h4>{action.action === "propose_patch" && <p>The proposed replacements are inspected in the following patch step. This model response does not approve the change.</p>}{typeof action.query === "string" && <p>Search for <code>{action.query}</code>.</p>}{typeof action.path === "string" && <p><code>{action.path}</code>{typeof action.start_line === "number" ? ` · From line ${action.start_line}` : ""}</p>}{typeof action.summary === "string" && <p>Model statement, unverified: {action.summary}</p>}{!action.action && <p>No supported structured action is shown. Open the exact capture to inspect the response.</p>}</div>;
  }
  return <p>Saved evidence is available in the exact capture below.</p>;
}
