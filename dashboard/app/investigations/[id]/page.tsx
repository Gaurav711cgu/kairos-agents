import Link from "next/link";
import { caseTitle, configurationLabel } from "@/lib/investigations";
import { getInvestigation, getComparisonPeers } from "@/lib/investigation-readers";
import { isRecordedEvidence } from "@/lib/evidence-mode";
import { InvestigationInspector } from "@/components/InvestigationInspector";
import { ServiceError } from "@/components/IncidentRows";
export const dynamic = "force-dynamic";
export default async function InvestigationPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ step?: string }> }) {
  const { id } = await params;
  const result = await getInvestigation(id);
  if (!result.data) return <div className="page-shell"><Link className="text-link" href="/investigations">All investigations</Link><ServiceError message={result.error} /></div>;
  const record = result.data;
  const comparisons = await getComparisonPeers(record);
  return <div className="page-shell"><Link className="text-link" href="/investigations">All investigations</Link>
    <header className="page-heading investigation-heading"><span className="eyebrow">{isRecordedEvidence() ? "Recorded investigation · " : ""}{record.task_snapshot.repository} / {configurationLabel(record.configuration)}</span><h1>{caseTitle(record.task_id, record.task_snapshot.title)}</h1><p>Historical source. Actual model attempt. Independent verification.</p></header>
    <InvestigationInspector record={record} comparison={comparisons[0] ?? null} comparisons={comparisons} initialStep={Number((await searchParams).step) || 0} />
  </div>;
}
