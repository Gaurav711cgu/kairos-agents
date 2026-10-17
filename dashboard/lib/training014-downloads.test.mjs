import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { Buffer } from 'node:buffer';
import { URL } from 'node:url';
import { repair010Download } from './repair010-downloads.ts';
const entries = JSON.parse(readFileSync(new URL('./training014-downloads.json', import.meta.url)));
const summary = JSON.parse(readFileSync(new URL('./training014-summary.json', import.meta.url)));

test('trained head and paired outcomes download exact reviewed bytes', async () => {
  for (const name of ['adapter.json', 'bundle.json', 'receipt.json', 'retrieval.json']) {
    const response = repair010Download(entries, [name]);
    assert.equal(response.status, 200);
    const raw = Buffer.from(await response.arrayBuffer());
    assert.equal(createHash('sha256').update(raw).digest('hex'), entries[name].sha256);
    const value = JSON.parse(raw);
    if (name === 'bundle.json') {
      assert.equal(value.paired.length, 113);
      assert.deepEqual(value.summary, summary.summary);
      assert.equal(value.inference_manifest_sha256, summary.adapter_manifest_sha256);
    }
    if (name === 'receipt.json') assert.equal(value.complete_state_bitwise_equal, true);
  }
});

test('training downloads reject changed head, traversal and unknown files', () => {
  const corrupt = globalThis.structuredClone(entries);
  corrupt['adapter.json'].sha256 = '0'.repeat(64);
  assert.equal(repair010Download(corrupt, ['adapter.json']).status, 409);
  for (const path of [['..', 'adapter.json'], ['weights.safetensors'], ['adapter.json', 'extra']]) {
    assert.equal(repair010Download(entries, path).status, 404);
  }
});
