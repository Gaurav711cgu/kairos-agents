import process from 'node:process';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { evidenceMode } from './evidence-mode.ts';

test('hosting flags never silently change live mode or hide invalid configuration', () => {
  const keys = ['KAIROS_EVIDENCE_MODE', 'VERCEL', 'NEXT_PUBLIC_VERCEL_ENV'];
  const saved = Object.fromEntries(keys.map(key => [key, process.env[key]]));
  try {
    delete process.env.KAIROS_EVIDENCE_MODE;
    process.env.VERCEL = '1';
    process.env.NEXT_PUBLIC_VERCEL_ENV = 'production';
    assert.equal(evidenceMode(), 'live');
    process.env.KAIROS_EVIDENCE_MODE = 'recorded';
    assert.equal(evidenceMode(), 'recorded');
    process.env.KAIROS_EVIDENCE_MODE = 'invalid';
    assert.throws(() => evidenceMode(), /Unsupported KAIROS_EVIDENCE_MODE/);
  } finally {
    for (const key of keys) {
      if (saved[key] === undefined) delete process.env[key];
      else process.env[key] = saved[key];
    }
  }
});
