import { z } from "zod";
import { investigationSchema } from "./investigation-contract.ts";

/** Study snapshots omit optional issue URLs. Normalize only this display view. */
export const comparisonRecordSchema = investigationSchema.extend({
  task_snapshot: investigationSchema.shape.task_snapshot.extend({
    issue_url: z.string().nullable().optional().transform(value => value ?? null),
  }),
});
