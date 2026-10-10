import Link from "next/link";
import { getIncident, date } from "@/lib/kairos-api";
import { ServiceError } from "@/components/IncidentRows";
import { IncidentInspector } from "@/components/IncidentInspector";
export const dynamic = "force-dynamic";
export default async function IncidentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await getIncident(id);
  if (!result.data)
    return (
      <div className="page-shell">
        <Link className="text-link" href="/incidents">
          ← Case files
        </Link>
        <ServiceError message={result.error} />
      </div>
    );
  const incident = result.data;
  return (
    <div className="page-shell incident-page">
      <Link className="text-link" href="/incidents">
        ← Case files
      </Link>
      <div className="page-heading">
        <span className="eyebrow">
          RECORDED EXECUTION / {date(incident.created_at)} /{" "}
          {incident.configuration.runner}
        </span>
        <h1>{incident.title}</h1>
        <p>{incident.summary}</p>
        <div className="detail-metadata">
          <span>{incident.policy} context</span>
          <span>{incident.event_count} captured events</span>
          <span>{incident.duration_ms.toFixed(1)} ms · local execution</span>
          <span>Synthetic order data</span>
        </div>
      </div>
      <IncidentInspector
        incident={incident}
        canFork={
          process.env.NODE_ENV === "development" &&
          process.env.KAIROS_ENABLE_LOCAL_MUTATIONS === "true" &&
          !!process.env.KAIROS_DEV_TOKEN
        }
      />
    </div>
  );
}
