import { createHash } from "node:crypto";
import { Buffer } from "node:buffer";

const MAX_BYTES = 1024 * 1024;
const MAX_BASE64 = 4 * Math.ceil(MAX_BYTES / 3);
const FILES = new Set(["candidate.patch", "checks.json", "original-model-response.json"]);
const MEDIA_TYPES = new Set(["application/json", "text/x-diff", "text/plain"]);

function error(status: number, message: string): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function logicalPath(segments: unknown): string | null {
  if (!Array.isArray(segments)) return null;
  if (segments.length === 1 && segments[0] === "attempts.json") return "attempts.json";
  if (segments.length !== 2 || typeof segments[0] !== "string" ||
      !/^[a-z0-9][a-z0-9_-]{0,119}$/.test(segments[0]) ||
      typeof segments[1] !== "string" || !FILES.has(segments[1])) return null;
  return segments.join("/");
}

/** Serve only compiled captured bytes after checking their exact size and hash. */
export function repair010Download(entries: unknown, segments: unknown): Response {
  const logical = logicalPath(segments);
  if (logical === null) return error(404, "Evidence download not found.");
  if (!entries || typeof entries !== "object" || Array.isArray(entries)) {
    return error(409, "Evidence download failed integrity checks.");
  }
  if (!Object.prototype.hasOwnProperty.call(entries, logical)) {
    return error(404, "Evidence download not found.");
  }
  try {
    const entry = (entries as Record<string, unknown>)[logical];
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) throw new Error();
    const value = entry as Record<string, unknown>;
    const filename = logical.split("/").at(-1);
    if (typeof value.base64 !== "string" || value.base64.length > MAX_BASE64 ||
        value.base64.length % 4 !== 0 || !/^[A-Za-z0-9+/]*={0,2}$/.test(value.base64) ||
        typeof value.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(value.sha256) ||
        typeof value.bytes !== "number" || !Number.isSafeInteger(value.bytes) ||
        value.bytes < 0 || value.bytes > MAX_BYTES ||
        typeof value.media_type !== "string" || !MEDIA_TYPES.has(value.media_type) ||
        typeof value.filename !== "string" || value.filename !== filename ||
        !/^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/.test(value.filename)) throw new Error();
    const raw = Buffer.from(value.base64, "base64");
    if (raw.length !== value.bytes || raw.length > MAX_BYTES ||
        raw.toString("base64") !== value.base64 ||
        createHash("sha256").update(raw).digest("hex") !== value.sha256) throw new Error();
    return new Response(new Uint8Array(raw), {
      status: 200,
      headers: {
        "Content-Type": value.media_type + "; charset=utf-8",
        "Content-Disposition": 'attachment; filename="' + value.filename + '"',
        "Content-Length": String(raw.length),
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return error(409, "Evidence download failed integrity checks.");
  }
}
