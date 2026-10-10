"use client";
import { useState } from "react";
import { Report } from "@/lib/workbench";
export function ReportPairs({ rows }: { rows: Report["rows"] }) {
  const [failedOnly, setFailedOnly] = useState(false);
  const [page, setPage] = useState(0);
  const filtered = rows.filter((r) => !failedOnly || !r.candidate_passed);
  const pages = Math.max(1, Math.ceil(filtered.length / 40));
  return (
    <section className="paired-tasks">
      <div className="section-top">
        <div>
          <span className="eyebrow">
            PER-TASK PAIRS / {filtered.length} RETAINED
          </span>
          <h2>
            Nothing silently
            <br />
            <em>disappears.</em>
          </h2>
        </div>
        <label>
          <input
            type="checkbox"
            checked={failedOnly}
            onChange={(e) => {
              setFailedOnly(e.target.checked);
              setPage(0);
            }}
          />{" "}
          Candidate failures only
        </label>
      </div>
      <div
        className="pair-table"
        role="table"
        aria-label="Paired task outcomes"
      >
        <div role="row" className="pair-head">
          <span role="columnheader">Task</span>
          <span role="columnheader">Baseline</span>
          <span role="columnheader">Candidate</span>
          <span role="columnheader">Provider</span>
        </div>
        {filtered.slice(page * 40, (page + 1) * 40).map((row) => (
          <details key={row.task_id}>
            <summary>
              <span>{row.task_id}</span>
              <span>{row.baseline_passed ? "pass" : "fail"}</span>
              <span>{row.candidate_passed ? "pass" : "fail"}</span>
              <span>{row.provider_error || "response retained"} ↓</span>
            </summary>
            <textarea
              readOnly
              aria-label={row.task_id + " raw evidence"}
              value={JSON.stringify(row, null, 2)}
            />
          </details>
        ))}
      </div>
      <div className="pair-pagination">
        <button
          className="text-button"
          disabled={page === 0}
          onClick={() => setPage(page - 1)}
        >
          ← Previous
        </button>
        <span>
          Page {page + 1} of {pages} · 40 rows per page
        </span>
        <button
          className="text-button"
          disabled={page + 1 >= pages}
          onClick={() => setPage(page + 1)}
        >
          Next →
        </button>
      </div>
    </section>
  );
}
