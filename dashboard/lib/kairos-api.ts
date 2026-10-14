import { z } from "zod";
import { isRecordedEvidence, recordedHistoryError } from "./evidence-mode";
const summarySchema = z.object({
  id: z.string(),
  slug: z.string(),
  title: z.string(),
  summary: z.string(),
  scenario_id: z.string(),
  policy: z.string(),
  status: z.string(),
  created_at: z.string(),
  event_count: z.number(),
  provenance: z.string(),
  parent_run_id: z.string().nullable(),
  grade_passed: z.boolean().nullable(),
});
export const incidentSchema = summarySchema.extend({
  task: z.string(),
  scenario: z.object({
    order_id: z.string(),
    order_total_cents: z.number().nullable(),
    delay_minutes: z.number().nullable(),
    policy_exception: z.boolean(),
  }),
  context_blocks: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
      content: z.string(),
      source: z.string(),
      included: z.boolean(),
    }),
  ),
  events: z.array(
    z.object({
      seq: z.number(),
      event_type: z.string(),
      title: z.string(),
      summary: z.string(),
      created_at: z.string(),
      payload: z.unknown(),
      event_hash: z.string(),
      prev_hash: z.string().nullable(),
    }),
  ),
  decision: z.object({
    refund_cents: z.number().nullable(),
    reason: z.string(),
    evidence_ids: z.array(z.string()),
  }),
  grade: z.object({
    passed: z.boolean(),
    expected_refund_cents: z.number().nullable(),
    actual_refund_cents: z.number().nullable(),
    checks: z.array(
      z.object({ name: z.string(), passed: z.boolean(), detail: z.string() }),
    ),
  }),
  duration_ms: z.number(),
  configuration: z.object({
    runner: z.string(),
    model: z.string().nullable(),
    policy_version: z.string(),
  }),
  lineage: z.object({
    parent_run_id: z.string().nullable(),
    fork_seq: z.number().nullable(),
  }),
  integrity: z.object({ verified: z.boolean(), scope: z.string() }),
});
export type IncidentSummary = z.infer<typeof summarySchema>;
export type Incident = z.infer<typeof incidentSchema>;
export type ApiResult<T> =
  { data: T; error: null } | { data: null; error: string };
export const apiBase = () =>
  process.env.KAIROS_API_URL || "http://127.0.0.1:8100";
const get = async <T>(
  path: string,
  schema: z.ZodType<T>,
): Promise<ApiResult<T>> => {
  if (isRecordedEvidence()) return { data: null, error: recordedHistoryError };
  try {
    const response = await fetch(apiBase() + path, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok)
      return {
        data: null,
        error: "Evidence service returned HTTP " + response.status + ".",
      };
    const parsed = schema.safeParse(await response.json());
    if (!parsed.success) {
      console.error("Kairos API contract mismatch", parsed.error.issues);
      return {
        data: null,
        error:
          "The evidence service returned an unsupported record. No unverified data is shown.",
      };
    }
    return { data: parsed.data, error: null };
  } catch {
    return {
      data: null,
      error:
        "The evidence service is unavailable. Start the API and refresh to inspect recorded executions.",
    };
  }
};
export const getIncidents = () =>
  get("/api/public/incidents", z.object({ incidents: z.array(summarySchema) }));
export const getIncident = (id: string) =>
  get("/api/public/incidents/" + encodeURIComponent(id), incidentSchema);
export const getEvidence = () =>
  get("/api/public/evidence", z.record(z.string(), z.unknown()));
export const money = (cents: number | null) =>
  cents === null
    ? "Abstain"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(cents / 100);
export const date = (value: string) =>
  new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
