import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { Buffer } from 'node:buffer';
import { URL } from 'node:url';
import { comparisonDownload } from './comparison014-downloads.ts';

const catalog = JSON.parse(readFileSync(new URL('./comparison014-downloads.json', import.meta.url)));
const report = JSON.parse(readFileSync(new URL('./comparison014-report.json', import.meta.url)));

test('comparison report and qualification receipts download exact verified bytes', async () => {
  for (const name of ['attempts.json', 'receipt.json']) {
    const response = comparisonDownload(catalog, [name]);
    assert.equal(response.status, 200);
    const raw = Buffer.from(await response.arrayBuffer());
    assert.equal(createHash('sha256').update(raw).digest('hex'), catalog.root[name].sha256);
    if (name === 'attempts.json') {
      const data = JSON.parse(raw);
      assert.equal(data.attempts, report.attempts);
      assert.equal(data.cases.length, report.cases.length);
    }
  }
});

test('per-arm captured investigations and patches download exact verified bytes', async () => {
  const caseKey = 'django__django-14752-loop';
  for (const file of ['bundle.json', 'candidate.patch', 'receipt.json', 'checks.json']) {
    const response = comparisonDownload(catalog, [caseKey, file]);
    assert.equal(response.status, 200);
    const raw = Buffer.from(await response.arrayBuffer());
    assert.equal(createHash('sha256').update(raw).digest('hex'), catalog[caseKey][file].sha256);
    if (file === 'candidate.patch') {
      assert.match(response.headers.get('content-type'), /^text\/x-diff/);
      assert.match(raw.toString('utf-8'), /autocomplete\.py/);
    }
  }
});

test('comparison downloads reject invalid keys, traversal and non-existent artifacts', () => {
  const badPaths = [
    ['attempts.json', 'extra'],
    ['..', 'attempts.json'],
    ['unsafe_case-loop', 'candidate.patch'],
    ['django__django-14752-loop', 'evil.sh'],
    ['django__django-14752-loop', '..', 'bundle.json'],
    ['nonexistent-loop', 'bundle.json'],
  ];
  for (const path of badPaths) {
    assert.equal(comparisonDownload(catalog, path).status, 404);
  }
});
