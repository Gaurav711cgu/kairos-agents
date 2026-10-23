import report from "@/lib/benchmark025.json";
import "./benchmark.css";

export const metadata = { title: "Repair benchmark: real Django bugs, independently tested" };

interface Sample {
  sample: string;
  outcome: string;
  verified: boolean;
  calls: number;
  patch: string | null;
}

interface CaseResult {
  instance_id: string;
  fair_pick_verified: boolean;
  samples: Sample[];
}

interface Run {
  run: string;
  model: string;
  split: string;
  cases_total: number;
  cases_verified: number;
  attempts_total: number;
  attempts_verified: number;
  model_calls: number;
  cases: CaseResult[];
}

const outcomeText: Record<string, string> = {
  verified_repair: "Hidden tests pass",
  behavioral_mismatch: "Tests still fail",
  loop_call_cap: "No patch within 8 model calls",
  loop_repeated: "Repeated itself, no patch",
  loop_exhausted: "Corrections ran out",
  revalidation_rejected: "Patch did not reapply",
  candidate_execution_failure: "Patch broke the test run",
};

const runs = report.runs as Run[];
const byName = Object.fromEntries(runs.map((r) => [r.run, r]));
const fresh = byName["nemotron-ultra-fresh"];
const devColumns = ["nemotron-ultra-dev", "qwen14b-run4-dev", "qwen14b-run5-dev"].map((n) => byName[n]);
const columnName: Record<string, string> = {
  "qwen14b-run4-dev": "14B, run 4",
  "qwen14b-run5-dev": "14B, run 5",
  "nemotron-ultra-dev": "Nemotron",
};

function shortCase(id: string) {
  return id.replace("django__django-", "Django #");
}

function Marks({ samples }: { samples: Sample[] }) {
  return (
    <span className="bench-marks">
      {samples.map((s) => (
        <span
          key={s.sample}
          className={s.verified ? "bench-mark is-pass" : "bench-mark is-fail"}
          title={`Attempt ${Number(s.sample.replace("oracle-s", "")) + 1}: ${outcomeText[s.outcome] ?? s.outcome}`}
        >
          {s.verified ? "Pass" : "Fail"}
        </span>
      ))}
    </span>
  );
}

function PatchDisclosure({ item }: { item: CaseResult }) {
  return (
    <details className="bench-detail">
      <summary>
        <span className="bench-case">{shortCase(item.instance_id)}</span>
        <Marks samples={item.samples} />
      </summary>
      {item.samples.map((s) => (
        <div className="bench-sample" key={s.sample}>
          <p>
            Attempt {Number(s.sample.replace("oracle-s", "")) + 1}: {outcomeText[s.outcome] ?? s.outcome}
            {s.outcome === "loop_call_cap" ? "" : `, ${s.calls} model ${s.calls === 1 ? "call" : "calls"}`}
          </p>
          {s.patch ? <pre className="bench-patch">{s.patch}</pre> : <p className="bench-empty">No patch was produced.</p>}
        </div>
      ))}
    </details>
  );
}

export default function BenchmarkPage() {
  const devCases = devColumns[0].cases.map((c) => c.instance_id);
  return (
    <div className="page-shell reading-page">
      <header className="page-heading">
        <span className="eyebrow">Repair benchmark</span>
        <h1>
          Real Django bugs.
          <br />
          <em>Fixed and tested by machine.</em>
        </h1>
        <p>
          Each case is a real, merged bug report from SWE-bench Verified. The model reads the issue and the relevant
          code, may run a reproduction script in a sandbox, and proposes a patch. A patch counts only when the
          project&apos;s own hidden tests pass in a pinned Docker image.
        </p>
      </header>

      <section className="bench-lead" aria-labelledby="fresh-heading">
        <h2 id="fresh-heading">
          On {fresh.cases_total} bugs it had never seen, it fixed {fresh.cases_verified}.
        </h2>
        <p>
          The model was chosen on the development cases first, then run once on these fresh cases with no tuning.
          {" "}{fresh.attempts_verified} of {fresh.attempts_total} attempts passed, using {fresh.model_calls} calls to a
          free hosted model.
        </p>
        <ol className="bench-fresh">
          {fresh.cases.map((c) => (
            <li key={c.instance_id}>
              <PatchDisclosure item={c} />
            </li>
          ))}
        </ol>
      </section>

      <section className="bench-section" aria-labelledby="dev-heading">
        <h2 id="dev-heading">Same harness, two models</h2>
        <p className="bench-intro">
          Five development cases, identical prompts and code context. The 14-billion-parameter model ran 4-bit on a
          free Colab T4 with a 3,539-token budget; Nemotron 3 Ultra ran on NVIDIA&apos;s free API.
        </p>
        <div className="bench-table-wrap">
          <table className="bench-table">
            <thead>
              <tr>
                <th scope="col">Case</th>
                {devColumns.map((r) => (
                  <th scope="col" key={r.run}>
                    {columnName[r.run]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {devCases.map((id) => (
                <tr key={id}>
                  <th scope="row">{shortCase(id)}</th>
                  {devColumns.map((r) => {
                    const item = r.cases.find((c) => c.instance_id === id);
                    return <td key={r.run}>{item ? <Marks samples={item.samples} /> : "Not run"}</td>;
                  })}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">Cases fixed</th>
                {devColumns.map((r) => (
                  <td key={r.run}>
                    {r.cases_verified} of {r.cases_total}
                  </td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
        <h3 className="bench-subhead">Nemotron&apos;s patches on these cases</h3>
        <ol className="bench-fresh">
          {devColumns[0].cases.map((c) => (
            <li key={c.instance_id}>
              <PatchDisclosure item={c} />
            </li>
          ))}
        </ol>
      </section>

      <section className="bench-section" aria-labelledby="limits-heading">
        <h2 id="limits-heading">What this does and does not show</h2>
        <dl className="bench-limits">
          <dt>Independent scoring</dt>
          <dd>Patches are re-applied to a clean checkout and judged by the hidden tests the model never sees.</dd>
          <dt>Small sample</dt>
          <dd>Twelve cases in total. A difference of one case is within noise.</dd>
          <dt>Possible contamination</dt>
          <dd>These are public 2020 Django fixes; a large model may have seen them in training.</dd>
          <dt>Code context given</dt>
          <dd>The model receives the code regions the real fix touched, then may search and read more.</dd>
          <dt>Protected sets untouched</dt>
          <dd>The frozen validation and locked holdout cases have not been run.</dd>
        </dl>
        <p className="bench-reproduce">
          Every capture, receipt and score is in <code>evidence/benchmark025</code> with a hash manifest. Rerun with{" "}
          <code>python -m scripts.hosted_repair</code> and score with <code>scripts/f025_score.py</code>.
        </p>
      </section>
    </div>
  );
}
