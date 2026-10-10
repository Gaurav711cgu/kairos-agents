import { z } from "zod";
export const jobSummary = z.object({
  id: z.string(),
  scenario_id: z.string(),
  policy: z.string(),
  runner: z.string(),
  status: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  attempt: z.number(),
  max_attempts: z.number(),
  model_calls: z.number(),
  cancel_requested: z.boolean(),
  publish: z.boolean(),
  parent_job_id: z.string().nullable(),
});
export const jobDetail = jobSummary
  .extend({
    context_blocks: z
      .array(
        z
          .object({
            id: z.string(),
            content: z.string(),
            included: z.boolean(),
          })
          .passthrough(),
      )
      .default([]),
    events: z
      .array(
        z
          .object({
            seq: z.number(),
            event_type: z.string(),
            payload: z.unknown(),
            created_at: z.string(),
          })
          .passthrough(),
      )
      .default([]),
    request: z.unknown().nullable().optional(),
    response: z.unknown().nullable().optional(),
    result: z.unknown().nullable().optional(),
    error: z.unknown().nullable().optional(),
    integrity: z.unknown().optional(),
    checkpoint_version: z.string().or(z.number()).optional(),
    deadline_at: z.string().nullable().optional(),
  })
  .passthrough();
export type Job = z.infer<typeof jobDetail>;
export const reportSummary = z
  .object({
    id: z.string(),
    created_at: z.string(),
    mode: z.string(),
    split: z.string(),
    baseline_passes: z.number(),
    candidate_passes: z.number(),
    provider_failures: z.number(),
    task_set_digest: z.string(),
    report_digest: z.string(),
    gate: z.object({
      verdict: z.enum(["pass", "fail", "inconclusive"]),
      reason: z.string(),
      n: z.number(),
      paired_success_delta: z.number(),
      lower: z.number(),
      upper: z.number(),
      radius: z.number(),
      plan: z
        .object({
          noninferiority_margin: z.number(),
          minimum_independent_tasks: z.number(),
          method: z.string(),
          sampling: z.string(),
        })
        .passthrough(),
    }),
  })
  .passthrough();
export const reportDetail = reportSummary.extend({
  hard_checks: z.array(
    z.object({ name: z.string(), passed: z.boolean(), detail: z.string() }),
  ),
  rows: z.array(
    z
      .object({
        task_id: z.string(),
        baseline_passed: z.boolean(),
        candidate_passed: z.boolean(),
        provider_error: z.string().nullable(),
      })
      .passthrough(),
  ),
  limits: z.array(z.string()),
});
export type Report = z.infer<typeof reportDetail>;
