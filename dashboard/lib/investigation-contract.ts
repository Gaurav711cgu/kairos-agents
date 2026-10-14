import { z } from "zod";

export const investigationSummary = z.object({
  id: z.string(), task_id: z.string(), title: z.string(), configuration: z.string(),
  status: z.string(), outcome: z.string().nullable(), summary: z.string().nullable(),
  created_at: z.string(), updated_at: z.string(), model_calls: z.number(),
  patch_count: z.number(), check_count: z.number(), parent_id: z.string().nullable(), published: z.boolean(),
});
const capture = z.object({ sha256: z.string(), body: z.record(z.string(), z.unknown()) });
export const investigationSchema = z.object({
  id: z.string(), task_id: z.string(), configuration: z.string(), status: z.string(),
  outcome: z.string().nullable(), summary: z.string().nullable(), model_calls: z.number(),
  patch_count: z.number(), check_count: z.number(), created_at: z.string(), updated_at: z.string(),
  started_at: z.string().nullable(), deadline_at: z.string().nullable(), published: z.boolean(),
  parent_id: z.string().nullable(), task_digest: z.string(),
  task_snapshot: z.object({ title: z.string(), issue: z.string(), repository: z.string(),
    revision: z.string(), issue_url: z.string().nullable(), source_url: z.string(),
    source_digest: z.string(), split: z.string(), provenance: z.string(), entry_files: z.array(z.string()),
    qualified: z.boolean(), command: z.array(z.string()), image: z.string(),
  }),
  config_snapshot: z.record(z.string(), z.unknown()),
  steps: z.array(z.object({ seq: z.number(), kind: z.string(), name: z.string(), state: z.string(),
    request: capture, result: capture.nullable(), started_at: z.string(), captured_at: z.string().nullable(),
  })),
  artifacts: z.array(z.object({ sha256: z.string(), bytes: z.number() })),
  integrity: z.object({ verified: z.boolean(), scope: z.string() }),
});
export type Investigation = z.infer<typeof investigationSchema>;
export type InvestigationSummary = z.infer<typeof investigationSummary>;
