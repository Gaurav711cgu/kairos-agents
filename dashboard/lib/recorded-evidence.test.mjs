import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { Buffer } from "node:buffer";
import { mkdtemp, mkdir, readFile, writeFile, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createRecordedEvidenceReader, RecordedEvidenceError } from "./recorded-evidence.ts";
const id = "00000000-0000-4000-8000-000000000001";
const other = "00000000-0000-4000-8000-000000000002";
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), "kairos-recorded-unit-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "records")); await mkdir(join(root, "blobs"));
  const manifest = { version: "published-evidence-v1", records: {}, blobs: {} };
  const put = async value => {
    const bytes = Buffer.from(typeof value === "string" ? value : JSON.stringify(value));
    const digest = sha(bytes); const path = `blobs/${digest}`;
    await writeFile(join(root, path), bytes);
    manifest.blobs[digest] = { path, sha256: digest, bytes: bytes.length };
    return digest;
  };
  const task = { title: "Regression fixture", issue: "Reproduce a regression.", repository: "fixture", revision: "source", issue_url: null, source_url: "https://github.com/example/repo", source_digest: "d".repeat(64), split: "validation", provenance: "Isolated unit fixture.", entry_files: ["source.py"], qualified: true, command: ["registered-check"], image: "registered-image" };
  const config = { version: "baseline-v3", budgets: { max_calls: 1, max_checks: 1, max_patches: 1 }, generation: { temperature: 1 } };
  // Raw Python-style 1.0 is preserved rather than reconstructed by JS hashing.
  const configDigest = await put('{"version":"baseline-v3","budgets":{"max_calls":1,"max_checks":1,"max_patches":1},"generation":{"temperature":1.0}}');
  const taskDigest = await put({ case: task, registry_version: "repository-cases-v1" });
  const request = { query: "original source" }, result = { matches: [] };
  const requestDigest = await put(request), resultDigest = await put(result);
  const record = { id, task_id: "fixture", configuration: "baseline-v3", status: "completed", outcome: "no_patch", summary: "No repair.", model_calls: 1, patch_count: 0, check_count: 0, created_at: "2026-10-13T00:00:00Z", updated_at: "2026-10-13T00:00:02Z", started_at: "2026-10-13T00:00:01Z", deadline_at: "2026-10-13T00:10:01Z", published: true, parent_id: null, task_digest: taskDigest, task_snapshot: task, config_snapshot: config, config_digest: configDigest, steps: [{ seq: 1, kind: "tool", name: "search", state: "captured", request: { sha256: requestDigest, body: request }, result: { sha256: resultDigest, body: result }, started_at: "2026-10-13T00:00:01Z", captured_at: "2026-10-13T00:00:02Z" }], artifacts: [requestDigest, resultDigest].map(digest => ({ sha256: digest, bytes: manifest.blobs[digest].bytes })), integrity: { verified: true, scope: "Unit fixture; not historical evidence." } };
  async function save() {
    const bytes = Buffer.from(JSON.stringify(record)); const path = `records/${id}.json`;
    await writeFile(join(root, path), bytes);
    manifest.records[id] = { path, sha256: sha(bytes), bytes: bytes.length, task_snapshot_blob: taskDigest, config_snapshot_blob: configDigest, registry_version: "repository-cases-v1" };
    await writeFile(join(root, "manifest.json"), JSON.stringify(manifest));
  }
  await save();
  return { root, manifest, record, save, requestDigest, resultDigest };
}
const rejected = reader => assert.rejects(reader.validate(), RecordedEvidenceError);
test("validated capture retains original bytes and Python-style float representation", async t => {
  const f = await fixture(t), reader = createRecordedEvidenceReader(f.root);
  assert.equal((await reader.read(id)).record.steps[0].request.body.query, "original source");
  const download = await reader.download(id, "bundle");
  assert.deepEqual(download.bytes, await readFile(join(f.root, `records/${id}.json`)));
  assert.equal((await reader.list()).investigations.length, 1);
  await assert.rejects(reader.download(id, "patch"), error => error.status === 404);
});
test("invalid and absent identifiers are rejected without request paths", async t => {
  const f = await fixture(t), reader = createRecordedEvidenceReader(f.root);
  for (const bad of ["../../secrets", "not-a-uuid", "a".repeat(36)]) await assert.rejects(reader.read(bad), error => error.status === 400);
  await assert.rejects(reader.read(other), error => error.status === 404);
  await assert.rejects(reader.list("bogus"), error => error.status === 400);
});
test("all package bytes are checked before the first display", async t => {
  const f = await fixture(t);
  await writeFile(join(f.root, `blobs/${f.resultDigest}`), '{"matches":["altered"]}');
  await rejected(createRecordedEvidenceReader(f.root));
});
test("a changed artifact after initialization cannot use cached bytes", async t => {
  const f = await fixture(t), reader = createRecordedEvidenceReader(f.root);
  await reader.validate();
  await writeFile(join(f.root, `blobs/${f.requestDigest}`), '{"query":"altered source"}');
  await assert.rejects(reader.read(id), RecordedEvidenceError);
});
test("missing declared blobs and missing artifact references fail closed", async t => {
  const f = await fixture(t);
  await rm(join(f.root, `blobs/${f.resultDigest}`));
  await rejected(createRecordedEvidenceReader(f.root));
  const g = await fixture(t); g.record.artifacts = []; await g.save();
  await rejected(createRecordedEvidenceReader(g.root));
});
test("schema violations and a mismatched record identity are rejected", async t => {
  const f = await fixture(t); delete f.record.task_snapshot.issue; await f.save();
  await rejected(createRecordedEvidenceReader(f.root));
  const g = await fixture(t); g.record.id = other; await g.save();
  await rejected(createRecordedEvidenceReader(g.root));
});
test("gaps, duplicate order, unfinished published execution and inflated counters are rejected", async t => {
  for (const change of [record => { record.steps[0].seq = 2; }, record => { record.steps.push(record.steps[0]); }, record => { record.status = "running"; }, record => { record.model_calls = 7; }, record => { record.patch_count = 3; }, record => { record.check_count = 3; }]) {
    const f = await fixture(t); change(f.record); await f.save(); await rejected(createRecordedEvidenceReader(f.root));
  }
});
test("capture body must equal the original content-addressed JSON", async t => {
  const f = await fixture(t); f.record.steps[0].request.body.query = "invented source"; await f.save();
  await rejected(createRecordedEvidenceReader(f.root));
});
test("case and configuration must equal raw fingerprinted snapshot blobs", async t => {
  const f = await fixture(t); f.record.config_snapshot.generation.temperature = 0.7; await f.save();
  await rejected(createRecordedEvidenceReader(f.root));
  const g = await fixture(t); g.record.task_snapshot.issue = "Rewritten issue."; await g.save();
  await rejected(createRecordedEvidenceReader(g.root));
});
test("manifest traversal, escaped symlinks and oversized entries are rejected", async t => {
  const f = await fixture(t); f.manifest.blobs[f.resultDigest].path = "../outside"; await f.save();
  await rejected(createRecordedEvidenceReader(f.root));
  const g = await fixture(t); const outside = join(g.root, "outside"); await writeFile(outside, "{}");
  const escaping = await mkdtemp(join(tmpdir(), "kairos-outside-")); t.after(() => rm(escaping, { recursive: true, force: true }));
  await writeFile(join(escaping, "object"), await readFile(join(g.root, `blobs/${g.resultDigest}`)));
  await rm(join(g.root, `blobs/${g.resultDigest}`)); await symlink(join(escaping, "object"), join(g.root, `blobs/${g.resultDigest}`));
  await rejected(createRecordedEvidenceReader(g.root));
  const h = await fixture(t); h.manifest.blobs[h.resultDigest].bytes = 33 * 1024 * 1024; await h.save();
  await rejected(createRecordedEvidenceReader(h.root));
});
test("genuine release package validates every published record and original capture", async () => {
  const reader = createRecordedEvidenceReader(resolve("evidence"));
  const manifest = await reader.validate();
  const followup = JSON.parse(await readFile(resolve("lib/followup006-results.json"), "utf8"));
  const historical = JSON.parse(await readFile(resolve("lib/investigation-cohort.json"), "utf8")).ids.concat(
    JSON.parse(await readFile(resolve("lib/study004-cohort.json"), "utf8")).ids);
  const current = JSON.parse(await readFile(resolve("lib/study007-results.json"), "utf8"));
  const expectedIds = historical.concat(followup.attempts.map(record => record.id), current.attempts.map(record => record.id));
  assert.equal(Object.keys(manifest.records).length, expectedIds.length);
  const all = []; let cursor;
  do {
    const page = await reader.list(cursor);
    assert.ok(page.investigations.length <= 25);
    all.push(...page.investigations); cursor = page.next_cursor;
  } while (cursor);
  assert.deepEqual(new Set(all.map(record => record.id)), new Set(expectedIds));
  const uncertain = all.find(record => record.outcome === "unknown_dispatch");
  assert.ok(uncertain, "The published unknown dispatch must not be dropped from the package.");
  const unknown = (await reader.read(uncertain.id)).record;
  assert.equal(unknown.status, "unknown");
  assert.ok(unknown.steps.some(step => step.state === "pending" && step.result === null));
  const original = all.filter(record => historical.includes(record.id));
  assert.equal(original.length, 48);
  assert.equal(original.filter(record => record.outcome === "verified_repair").length, 2);
  for (const attempted of followup.attempts) {
    const record = (await reader.read(attempted.id)).record;
    assert.equal(record.outcome, attempted.outcome);
    assert.equal(record.configuration, attempted.configuration);
  }

});
