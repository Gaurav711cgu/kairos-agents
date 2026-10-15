import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { Buffer } from "node:buffer";
import test from "node:test";
import { repair010Download } from "./repair010-downloads.ts";

function captured(raw = Buffer.from("--- a/source.py\n+++ b/source.py\n+π\n")) {
  return {
    base64: raw.toString("base64"), sha256: createHash("sha256").update(raw).digest("hex"),
    bytes: raw.length, media_type: "text/x-diff", filename: "candidate.patch",
  };
}
const logical = "reviewed-defect/candidate.patch";
const segments = ["reviewed-defect", "candidate.patch"];

test("a known capture returns its exact bytes and safe download headers", async () => {
  const raw = Buffer.from("--- a/source.py\n+++ b/source.py\n+π\n");
  const response = repair010Download({ [logical]: captured(raw) }, segments);
  assert.equal(response.status, 200);
  assert.deepEqual(Buffer.from(await response.arrayBuffer()), raw);
  assert.equal(response.headers.get("content-type"), "text/x-diff; charset=utf-8");
  assert.equal(response.headers.get("content-disposition"), 'attachment; filename="candidate.patch"');
  assert.equal(response.headers.get("content-length"), String(raw.length));
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("cache-control"), "no-store");
  const ledger = Buffer.from('{"attempts":[]}\n');
  const ledgerEntry = { ...captured(ledger), media_type: "application/json", filename: "attempts.json" };
  assert.equal(repair010Download({ "attempts.json": ledgerEntry }, ["attempts.json"]).status, 200);
});

test("corrupt digests, lengths and base64 fail closed without replacement bytes", async () => {
  const good = captured();
  const broken = [
    { ...good, sha256: "0".repeat(64) },
    { ...good, bytes: good.bytes + 1 },
    { ...good, base64: good.base64 + "!" },
    { ...good, base64: "Zh==", bytes: 1 }, // Decodes like Zg== but is not canonical.
    { ...good, base64: "A".repeat(4 * Math.ceil(1024 * 1024 / 3) + 4) },
    { ...good, bytes: 1024 * 1024 + 1 },
    { ...good, bytes: 1.5 },
    null,
  ];
  for (const entry of broken) {
    const response = repair010Download({ [logical]: entry }, segments);
    assert.equal(response.status, 409);
    assert.deepEqual(await response.json(), { error: "Evidence download failed integrity checks." });
    assert.equal(response.headers.get("content-disposition"), null);
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
});

test("unknown, inherited or malformed logical paths never select an artifact", () => {
  const entries = { [logical]: captured() };
  for (const path of [[], null, "attempts.json", ["missing", "candidate.patch"],
    ["reviewed-defect", "missing.json"], ["..", "candidate.patch"],
    ["reviewed/defect", "candidate.patch"], ["%2e%2e", "candidate.patch"],
    ["reviewed-defect", ".."], ["reviewed-defect", "candidate.patch", "extra"],
    ["reviewed-defect", 1]]) {
    assert.equal(repair010Download(entries, path).status, 404);
  }
  assert.equal(repair010Download(Object.create(entries), segments).status, 404);
  assert.equal(repair010Download({}, ["attempts.json"]).status, 404);
});

test("untrusted filenames and media types cannot inject headers or active content", async () => {
  const good = captured();
  for (const metadata of [
    { filename: 'candidate.patch\r\nX-Injected: yes' },
    { filename: '../candidate.patch' },
    { filename: 'misleading.json' },
    { media_type: 'text/html' },
    { media_type: 'application/json\r\nX-Injected: yes' },
  ]) {
    const response = repair010Download({ [logical]: { ...good, ...metadata } }, segments);
    assert.equal(response.status, 409);
    assert.equal(response.headers.get("x-injected"), null);
    assert.equal(response.headers.get("content-type"), "application/json; charset=utf-8");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  }
});
