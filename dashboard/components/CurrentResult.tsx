import Link from "next/link";
import report from "@/lib/benchmark025.json";
import "./current-result.css";

const fresh = report.runs.find((r) => r.run === "nemotron-ultra-fresh")!;
const dev = report.runs.find((r) => r.run === "nemotron-ultra-dev")!;

/** The current headline result, shown wherever older studies are discussed. Numbers come from scored evidence. */
export function CurrentResult({ historical = false, home = false }: { historical?: boolean; home?: boolean }) {
  return (
    <aside className={"scope-note current-result" + (home ? " on-home" : "")} aria-label="Current result">
      <p>
        {historical && "This page is a historical record from an earlier build. "}
        Current result: a free hosted model (Nemotron 3 Ultra) fixed {fresh.cases_verified} of {fresh.cases_total} never-seen
        SWE-bench Verified Django bugs and {dev.cases_verified} of {dev.cases_total} development bugs, judged by hidden tests
        in Docker. <Link className="text-link" href="/benchmark">See the benchmark</Link>
      </p>
    </aside>
  );
}
