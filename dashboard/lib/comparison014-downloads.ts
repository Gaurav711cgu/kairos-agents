import { repair010Download } from "./repair010-downloads.ts";

/** Select a compiled capture; no caller-controlled filesystem access is used. */
export function comparisonDownload(entries: unknown, segments: unknown): Response {
  const missing = () => repair010Download({}, ["bundle.json"]);
  if (!Array.isArray(segments) || !entries || typeof entries !== "object" || Array.isArray(entries)) return missing();
  const catalog = entries as Record<string, unknown>;
  if (segments.length === 1 && ["attempts.json", "receipt.json"].includes(segments[0])) {
    return repair010Download(catalog.root, segments);
  }
  if (segments.length !== 2 || typeof segments[0] !== "string" ||
      !/^(django__django|pytest-dev__pytest)-[0-9]+-(baseline|loop|drafts)$/.test(segments[0]) ||
      !["bundle.json", "receipt.json", "candidate.patch", "checks.json"].includes(segments[1]) ||
      !Object.prototype.hasOwnProperty.call(catalog, segments[0])) return missing();
  return repair010Download(catalog[segments[0]], [segments[1]]);
}
