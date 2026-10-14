/** Server-owned published captures. This module never executes tools or calls an API. */
import { createHash } from "node:crypto";
import { readFile, realpath, stat } from "node:fs/promises";
import { isDeepStrictEqual } from "node:util";
import { resolve, sep } from "node:path";
import { z } from "zod";
import { investigationSchema, investigationSummary, type Investigation } from "./investigation-contract.ts";
import type { ApiResult } from "./kairos-api";

const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
const sha = /^[a-f0-9]{64}$/;
const entry = z.object({ path: z.string(), sha256: z.string().regex(sha), bytes: z.number().int().nonnegative() });
const recordEntry = entry.extend({ task_snapshot_blob: z.string().regex(sha), config_snapshot_blob: z.string().regex(sha), registry_version: z.string().min(1) });
const manifestSchema = z.object({ version: z.literal("published-evidence-v1"), records: z.record(z.string().regex(uuid), recordEntry), blobs: z.record(z.string().regex(sha), entry) });
type Manifest = z.infer<typeof manifestSchema>;
const integrityError = "Recorded evidence integrity check failed. No unverified data is shown.";
export class RecordedEvidenceError extends Error {
  readonly status: number;
  constructor(message = integrityError, status = 409) { super(message); this.name = "RecordedEvidenceError"; this.status = status; }
}
const hash = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const parse = (bytes: Uint8Array): unknown => JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
const finiteDate = (value: string) => Number.isFinite(Date.parse(value));
const object = (value: unknown) => z.record(z.string(), z.unknown()).parse(value);

export function createRecordedEvidenceReader(directory: string) {
  const root = resolve(directory);
  let initialization: Promise<Manifest> | undefined;
  async function bytes(path: string, expected?: z.infer<typeof entry>): Promise<Buffer> {
    const base = await realpath(root);
    const target = await realpath(resolve(base, path));
    if (!target.startsWith(base + sep)) throw new RecordedEvidenceError();
    const info = await stat(target);
    const maximum = path === "manifest.json" ? 4 * 1024 * 1024 : 32 * 1024 * 1024;
    if (!info.isFile() || info.size > maximum || (expected && info.size !== expected.bytes)) throw new RecordedEvidenceError();
    const value = await readFile(target);
    if (value.byteLength > maximum || (expected && (value.byteLength !== expected.bytes || hash(value) !== expected.sha256))) throw new RecordedEvidenceError();
    return value;
  }
  async function readRecord(manifest: Manifest, id: string, cache?: Map<string, Buffer>) {
    const descriptor = manifest.records[id];
    if (!descriptor) throw new RecordedEvidenceError("This investigation is not included in the recorded evidence package.", 404);
    const recordBytes = await bytes(descriptor.path, descriptor);
    const raw = object(parse(recordBytes));
    const record = investigationSchema.parse(raw);
    if (record.id !== id || !record.published || !record.integrity.verified || !uuid.test(record.id) || !sha.test(record.task_digest)) throw new RecordedEvidenceError();
    if (record.parent_id && !uuid.test(record.parent_id)) throw new RecordedEvidenceError();
    if (!["completed", "failed", "timed_out", "unknown", "cancelled"].includes(record.status) || record.model_calls > 6 || record.patch_count > 2 || record.check_count > 2) throw new RecordedEvidenceError();
    if (![record.created_at, record.updated_at, ...(record.started_at ? [record.started_at] : []), ...(record.deadline_at ? [record.deadline_at] : [])].every(finiteDate)) throw new RecordedEvidenceError();
    if (![record.model_calls, record.patch_count, record.check_count].every(value => Number.isSafeInteger(value) && value >= 0)) throw new RecordedEvidenceError();
    if (record.steps.length > 100 || record.artifacts.length > 1000) throw new RecordedEvidenceError();
    const referenced = new Map(record.artifacts.map(item => [item.sha256, item.bytes]));
    if (referenced.size !== record.artifacts.length) throw new RecordedEvidenceError();
    async function blob(digest: string, expectedBytes?: number) {
      const file = manifest.blobs[digest];
      if (!sha.test(digest) || !file || file.sha256 !== digest || (expectedBytes !== undefined && expectedBytes !== file.bytes)) throw new RecordedEvidenceError();
      const value = cache?.get(digest) ?? await bytes(file.path, file);
      cache?.set(digest, value);
      return value;
    }
    for (const artifact of record.artifacts) await blob(artifact.sha256, artifact.bytes);
    for (const [index, step] of record.steps.entries()) {
      if (step.seq !== index + 1 || !finiteDate(step.started_at) || (step.captured_at !== null && !finiteDate(step.captured_at))) throw new RecordedEvidenceError();
      if (!((step.state === "captured" && step.result !== null && step.captured_at !== null) || (step.state === "pending" && step.result === null && step.captured_at === null))) throw new RecordedEvidenceError();
      for (const capture of [step.request, step.result]) {
        if (!capture) continue;
        if (!referenced.has(capture.sha256)) throw new RecordedEvidenceError();
        if (!isDeepStrictEqual(parse(await blob(capture.sha256, referenced.get(capture.sha256))), capture.body)) throw new RecordedEvidenceError();
      }
    }
    if (descriptor.task_snapshot_blob !== record.task_digest || descriptor.config_snapshot_blob !== raw.config_digest) throw new RecordedEvidenceError();
    if (!isDeepStrictEqual(parse(await blob(descriptor.task_snapshot_blob)), { case: raw.task_snapshot, registry_version: descriptor.registry_version })) throw new RecordedEvidenceError();
    if (!isDeepStrictEqual(parse(await blob(descriptor.config_snapshot_blob)), raw.config_snapshot)) throw new RecordedEvidenceError();
    return { record, recordBytes };
  }
  async function initialize() {
    if (!initialization) initialization = (async () => {
      const manifest = manifestSchema.parse(parse(await bytes("manifest.json")));
      if (!Object.keys(manifest.records).length || Object.keys(manifest.records).length > 1000 || Object.keys(manifest.blobs).length > 10000) throw new RecordedEvidenceError();
      for (const [id, file] of Object.entries(manifest.records)) if (file.path !== `records/${id}.json`) throw new RecordedEvidenceError();
      for (const [digest, file] of Object.entries(manifest.blobs)) if (file.path !== `blobs/${digest}` || file.sha256 !== digest) throw new RecordedEvidenceError();
      if ([...Object.values(manifest.records), ...Object.values(manifest.blobs)].reduce((size, file) => size + file.bytes, 0) > 512 * 1024 * 1024) throw new RecordedEvidenceError();
      const cache = new Map<string, Buffer>();
      // Validate every manifest entry before any record is shown. Request reads
      // recheck their own bytes so an edited artifact cannot use a stale cache.
      for (const file of Object.values(manifest.blobs)) cache.set(file.sha256, await bytes(file.path, file));
      for (const id of Object.keys(manifest.records)) await readRecord(manifest, id, cache);
      return manifest;
    })();
    try { return await initialization; } catch { initialization = undefined; throw new RecordedEvidenceError(); }
  }
  async function read(id: string) {
    if (!uuid.test(id)) throw new RecordedEvidenceError("Invalid investigation identifier.", 400);
    return readRecord(await initialize(), id);
  }
  async function list(cursor?: string) {
    const manifest = await initialize();
    const records = [];
    for (const id of Object.keys(manifest.records)) records.push((await readRecord(manifest, id)).record);
    records.sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id.localeCompare(a.id));
    let start = 0;
    if (cursor) {
      if (cursor.length > 512 || !/^[A-Za-z0-9_-]+$/.test(cursor)) throw new RecordedEvidenceError("Invalid recorded evidence cursor.", 400);
      let anchor: unknown;
      try { anchor = JSON.parse(Buffer.from(cursor, "base64url").toString("utf8")); } catch { throw new RecordedEvidenceError("Invalid recorded evidence cursor.", 400); }
      if (!Array.isArray(anchor) || anchor.length !== 2 || !anchor.every(value => typeof value === "string")) throw new RecordedEvidenceError("Invalid recorded evidence cursor.", 400);
      const index = records.findIndex(record => record.created_at === anchor[0] && record.id === anchor[1]);
      if (index < 0) throw new RecordedEvidenceError("Invalid recorded evidence cursor.", 400);
      start = index + 1;
    }
    const selected = records.slice(start, start + 25);
    const last = selected.at(-1);
    return { investigations: selected.map(record => investigationSummary.parse({ ...record, title: record.task_snapshot.title })), next_cursor: start + selected.length < records.length && last ? Buffer.from(JSON.stringify([last.created_at, last.id])).toString("base64url") : null };
  }
  async function download(id: string, kind: "bundle" | "patch") {
    const { record, recordBytes } = await read(id);
    if (kind === "bundle") return { bytes: recordBytes, contentType: "application/json", filename: `kairos-${id}.json` };
    let patches = record.steps.filter(step => step.name === "propose_patch" && step.state === "captured" && step.result && !("error" in step.result.body));
    const selection = [...record.steps].reverse().find(step => step.name === "draft_selection" && step.state === "captured")?.result?.body.selected_patch_digest;
    if (typeof selection === "string") patches = patches.filter(step => hash(Buffer.from(JSON.stringify(step.result!.body.patch ?? ""))) === selection);
    const selected = patches.at(-1);
    const patch = selected?.result?.body.patch ?? selected?.request.body.patch;
    if (typeof patch !== "string") throw new RecordedEvidenceError("No accepted patch in this investigation.", 404);
    return { bytes: Buffer.from(patch), contentType: "text/plain; charset=utf-8", filename: `kairos-${id}.patch` };
  }
  return { read, list, download, validate: initialize };
}
let defaultReader: ReturnType<typeof createRecordedEvidenceReader> | undefined;
function reader() { return defaultReader ??= createRecordedEvidenceReader(process.env.KAIROS_EVIDENCE_DIR || resolve(process.cwd(), "evidence")); }
export function recordedFailure(error: unknown) { return error instanceof RecordedEvidenceError ? error : new RecordedEvidenceError(); }
export async function getRecordedInvestigation(id: string): Promise<ApiResult<Investigation>> {
  try { return { data: (await reader().read(id)).record, error: null }; } catch (error) { return { data: null, error: recordedFailure(error).message }; }
}
export async function listRecordedInvestigations(cursor?: string) {
  try { return { data: await reader().list(cursor), error: null }; } catch (error) { return { data: null, error: recordedFailure(error).message }; }
}
export const downloadRecordedInvestigation = (id: string, kind: "bundle" | "patch") => reader().download(id, kind);
export const validateRecordedPackage = () => reader().validate();
