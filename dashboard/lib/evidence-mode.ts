/** Evidence mode is explicit server configuration; live never falls back to captures. */
export function evidenceMode(): "live" | "recorded" {
  const defaultMode = (process.env.VERCEL || process.env.NEXT_PUBLIC_VERCEL_ENV) ? "recorded" : "live";
  const value = process.env.KAIROS_EVIDENCE_MODE ?? defaultMode;
  if (value !== "live" && value !== "recorded") throw new Error("Unsupported KAIROS_EVIDENCE_MODE. Use live or recorded.");
  return value;
}
export const isRecordedEvidence = () => evidenceMode() === "recorded";
export const recordedPrivateError = "Private execution is disabled in recorded mode.";
export const recordedHistoryError = "This historical collection is not included in the recorded evidence package. Run fullstack mode to inspect its database records.";
