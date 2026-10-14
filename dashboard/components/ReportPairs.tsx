"use client";
import { Fragment, useState } from "react";
import { Report } from "@/lib/workbench";
export function ReportPairs({ rows }: { rows: Report["rows"] }) {
  const [failedOnly, setFailedOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const filtered = rows.filter((r) => !failedOnly || !r.candidate_passed);
  const pages = Math.max(1, Math.ceil(filtered.length / 40));
  return (
    <section className="paired-tasks">
      <div className="section-top">
        <div>
          <span className="eyebrow">
            Per-task pairs / {filtered.length} retained
          </span>
          <h2>Individual task results</h2>
        </div>
        <label>
          <input
            type="checkbox"
            checked={failedOnly}
            onChange={(e) => {
              setFailedOnly(e.target.checked);
              setPage(0);
              setExpanded(null);
            }}
          />{" "}
          Candidate failures only
        </label>
      </div>
      <div
        className="pair-table-scroll"
        role="region"
        aria-label="Scrollable paired task outcomes"
      >
        <table className="pair-table" aria-label="Paired task outcomes">
          <thead>
            <tr>
              <th scope="col">Task</th>
              <th scope="col">Baseline</th>
              <th scope="col">Candidate</th>
              <th scope="col">Provider</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(page * 40, (page + 1) * 40).map((row) => {
              const open = expanded === row.task_id;
              const evidenceId = "task-evidence-" + row.task_id;
              return (
                <Fragment key={row.task_id}>
                  <tr>
                    <th scope="row">
                      <button
                        className="text-button"
                        aria-expanded={open}
                        aria-controls={open ? evidenceId : undefined}
                        onClick={() => setExpanded(open ? null : row.task_id)}
                      >
                        {row.task_id} {open ? "↑" : "↓"}
                      </button>
                    </th>
                    <td>{row.baseline_passed ? "Passed" : "Failed"}</td>
                    <td>{row.candidate_passed ? "Passed" : "Failed"}</td>
                    <td>{row.provider_error || "Response captured"}</td>
                  </tr>
                  {open && (
                    <tr id={evidenceId}>
                      <td colSpan={4}>
                        <textarea
                          readOnly
                          aria-label={row.task_id + " raw evidence"}
                          value={JSON.stringify(row, null, 2)}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="pair-pagination">
        <button
          className="text-button"
          disabled={page === 0}
          onClick={() => {
            setPage(page - 1);
            setExpanded(null);
          }}
        >
          ← Previous
        </button>
        <span>
          Page {page + 1} of {pages} · 40 rows per page
        </span>
        <button
          className="text-button"
          disabled={page + 1 >= pages}
          onClick={() => {
            setPage(page + 1);
            setExpanded(null);
          }}
        >
          Next
        </button>
      </div>
    </section>
  );
}
