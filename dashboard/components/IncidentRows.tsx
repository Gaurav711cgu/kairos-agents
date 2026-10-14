import { displayLabel } from "@/lib/display";
import Link from "next/link";
import { RetryEvidence } from "@/components/RetryEvidence";
import { date, type IncidentSummary } from "@/lib/kairos-api";
export const IncidentRows = ({
  incidents,
}: {
  incidents: IncidentSummary[];
}) => (
  <div className="incident-rows">
    {incidents.map((item, index) => (
      <Link
        className="incident-row"
        href={"/incidents/" + item.id}
        key={item.id}
      >
        <span className="row-number">{String(index + 1).padStart(2, "0")}</span>
        <div>
          <div className="eyebrow">
            {displayLabel(item.scenario_id)} · {displayLabel(item.policy)}
          </div>
          <h3>{item.title}</h3>
          <p>{item.summary}</p>
        </div>
        <div className="row-meta">
          <span
            className={item.grade_passed ? "status good" : "status attention"}
          >
            {item.grade_passed
              ? "Checks passed"
              : item.grade_passed === false
                ? "Failure captured"
                : "Unscored"}
          </span>
          <small>
            Reference policy · {item.event_count} events
            <br />
            {date(item.created_at)}
          </small>
        </div>
        <span className="row-arrow" aria-hidden="true"></span>
      </Link>
    ))}
  </div>
);
export const ServiceError = ({ message }: { message: string }) => (
  <div role="status" className="service-error">
    <span className="eyebrow">Evidence unavailable</span>
    <h3>Records are unavailable</h3>
    <p>{message}</p>
    <RetryEvidence />
  </div>
);
