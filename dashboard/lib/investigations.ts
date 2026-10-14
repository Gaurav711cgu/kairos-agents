import currentCohort from "./study007-cohort.json";
import cohort from "./investigation-cohort.json";
import studyCohort from "./study004-cohort.json";
import followupCohort from "./followup006-cohort.json";

import { type Investigation } from "./investigation-contract";
export { investigationSummary, investigationSchema } from "./investigation-contract";
export type { Investigation, InvestigationSummary } from "./investigation-contract";

export const outcomeLabel = (outcome: string | null, status = "") => ({
  verified_repair: "Verified repair", failed_checks: "Checks failed", invalid_patch: "Patch rejected",
  no_patch: "No patch proposed", invalid_response: "Invalid model response", unknown_dispatch: "Dispatch outcome unknown",
  environment_failure: "Environment failure", timeout: "Time limit reached", cancelled: "Cancelled",
  claim_budget_exhausted: "Recovery limit reached",
}[outcome ?? ""] || ({ queued: "Queued", running: "Running" }[status] ?? "Outcome pending"));
export const configurationLabel = (configuration: string) => configuration.startsWith("baseline-") ? "Single call" : configuration.startsWith("drafts-") ? "Independent drafts" : "Tool loop";

export const modelUsage = (record: Investigation) => record.steps.reduce((total, step) => {
  if (step.kind !== "model" || !step.result) return total;
  const usage = step.result.body.usage;
  if (typeof usage !== "object" || !usage) return total;
  const value = usage as Record<string, unknown>;
  return total + (typeof value.prompt_tokens === "number" ? value.prompt_tokens : 0) + (typeof value.completion_tokens === "number" ? value.completion_tokens : 0);
}, 0);
export const elapsed = (record: Investigation) => (studyCohort.incomplete_duration_ids as string[]).includes(record.id) ? null : record.started_at ? Math.max(0, Math.round((Date.parse(record.updated_at) - Date.parse(record.started_at)) / 1000)) : null;

// Editorial labels only; the captured issue and model input remain unchanged.
export const caseTitle = (id: string, fallback: string) => ({
  "kairos-clock-lease": "Clock skew breaks worker lease checks",
  "kairos-body-limit": "Oversized commands reach JSON parsing",
  "django__django-10554": "Ordering a union changes its selected columns",
  "django__django-10880": "Distinct counts generate invalid SQL",
  "django__django-10914": "Uploaded files receive inconsistent permissions",
  "django__django-10973": "Pass database shell credentials through a scoped environment",
  "django__django-11066": "Renaming a content type uses the wrong database",
  "django__django-11133": "HTTP responses mishandle memoryview content",
  "django__django-11141": "Migration discovery skips directories without package markers",
  "pytest-dev__pytest-6197": "Test collection imports unrelated package files",
  "pytest-dev__pytest-7324": "Marker expressions crash a debug Python interpreter",
  "pytest-dev__pytest-7432": "Running expected failures changes skip locations",
  "psf__requests-2317": "Byte-valued HTTP methods are converted incorrectly",
  "psf__requests-2931": "Binary request bodies fail during string conversion",
}[id] || fallback);

const frozenIds = new Set(cohort.ids);
export const isFrozenComparison = (record: { id: string }) => frozenIds.has(record.id);

export const activeStudyComplete=studyCohort.complete;

export const isPublishedComparison=(record:{id:string})=>isFrozenComparison(record)||(studyCohort.ids as string[]).includes(record.id)||(followupCohort.ids as string[]).includes(record.id)||(currentCohort.ids as string[]).includes(record.id);
