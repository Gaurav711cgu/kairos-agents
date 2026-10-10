import { getIncidents } from "@/lib/kairos-api";
import { IncidentRows, ServiceError } from "@/components/IncidentRows";
export const dynamic = "force-dynamic";
export default async function Incidents() {
  const result = await getIncidents();
  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">THE CASE FILES / CONTROLLED EXECUTIONS</span>
        <h1>Follow the evidence.</h1>
        <p>
          Failures, healthy controls, and isolated policy reruns. Every row
          comes from a persisted execution against synthetic order data.
        </p>
      </div>
      {result.error ? (
        <ServiceError message={result.error} />
      ) : result.data?.incidents.length ? (
        <IncidentRows incidents={result.data.incidents} />
      ) : (
        <p className="empty-state">
          No published executions yet. Execute and publish a controlled scenario
          to populate this collection.
        </p>
      )}
      <aside className="scope-note">
        <strong>What you are inspecting</strong>
        <p>
          The current runner is a deterministic reference policy. These records
          demonstrate context capture, durable storage, independent grading, and
          fork lineage. They do not establish language-model quality or
          statistical release confidence.
        </p>
      </aside>
    </div>
  );
}
