import { notFound } from "next/navigation";
import { getIncidents, getIncident } from "@/lib/kairos-api";
import { IncidentInspector } from "@/components/IncidentInspector";
export const dynamic = "force-dynamic";
export default async function TraceStress() {
  if (
    process.env.NODE_ENV !== "development" ||
    process.env.KAIROS_ENABLE_LOCAL_MUTATIONS !== "true"
  )
    notFound();
  const list = await getIncidents();
  const id = list.data?.incidents[0]?.id;
  if (!id) return <p>No source execution for development rendering test.</p>;
  const result = await getIncident(id);
  if (!result.data) return <p>Source unavailable.</p>;
  const original = result.data;
  const incident = {
    ...original,
    event_count: 1000,
    events: Array.from({ length: 1000 }, (_, i) => ({
      ...original.events[i % original.events.length],
      seq: i + 1,
      title: "Rendering fixture step " + (i + 1),
      summary:
        "Synthetic repeated event for UI rendering stress only; not an executed system benchmark.",
    })),
  };
  return (
    <div className="page-shell">
      <div className="page-heading">
        <span className="eyebrow">DEVELOPMENT ONLY / RENDERING FIXTURE</span>
        <h1>
          1,000 event
          <br />
          <em>interaction check.</em>
        </h1>
        <p>
          This is explicitly synthetic repeated source material for bounded DOM
          and keyboard testing. It is not execution evidence or a performance
          claim. At most 80 timeline buttons render.
        </p>
      </div>
      <IncidentInspector incident={incident} canFork={false} />
    </div>
  );
}
