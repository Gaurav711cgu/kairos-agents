"use client";
import { useState } from "react";
import Link from "next/link";
import { isPublishedComparison, caseTitle, configurationLabel, outcomeLabel, type InvestigationSummary } from "@/lib/investigations";
export function InvestigationRows({ records }: { records: InvestigationSummary[] }) {
  const [query, setQuery] = useState("");
  const [cohort, setCohort] = useState("all");
  const [filter, setFilter] = useState("all");
  const visible = records.filter(record => (cohort === "all" || isPublishedComparison(record)) && (caseTitle(record.task_id, record.title) + " " + record.title + " " + record.task_id).toLowerCase().includes(query.toLowerCase()) &&
    (filter === "all" || (filter === "verified" ? record.outcome === "verified_repair" : record.configuration.startsWith(filter))));
  return <>
    <div className="investigation-filters">
      <label>Find a case<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Issue or repository" type="search" /></label>
      <label>Show<select value={filter} onChange={event => setFilter(event.target.value)}>
        <option value="all">All attempts</option><option value="verified">Verified repairs</option>
        <option value="baseline-">Single-call baseline</option><option value="loop-">Tool loop</option><option value="drafts-">Independent drafts</option>
      </select></label>
      <label>Configuration<select value={cohort} onChange={event=>setCohort(event.target.value)}><option value="final">Frozen comparisons</option><option value="all">All recorded versions</option></select></label>
      <p aria-live="polite">{visible.length} of {records.length} attempts on this page</p>
    </div>
    <div className="investigation-records">
      {visible.map(record => <Link prefetch={false} href={"/investigations/" + record.id} key={record.id} className="investigation-row">
        <div><span className="eyebrow">{record.task_id.replace("django__django-", "Django #")}</span><h3>{caseTitle(record.task_id, record.title)}</h3></div>
        <span>{configurationLabel(record.configuration)} · {record.configuration.split("-").at(-1)}</span>
        <span className={record.outcome === "verified_repair" ? "result-pass" : "result-muted"}>{outcomeLabel(record.outcome, record.status)}</span>
        <span>{record.model_calls} {record.model_calls === 1 ? "call" : "calls"}</span>
      </Link>)}
      {!visible.length && <p className="empty-state">No recorded attempts match these filters.</p>}
    </div>
  </>;
}
