import { test } from 'node:test';
import assert from 'node:assert/strict';
import { securityHeaders } from './security-headers.ts';

const policy = (dev) => Object.fromEntries(securityHeaders(dev).map(h => [h.key, h.value]));

test('production pages load code and data only from this site and cannot be framed', () => {
  const headers = policy(false);
  const csp = headers['Content-Security-Policy'];
  for (const rule of ["default-src 'self'", "connect-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'"])
    assert.ok(csp.includes(rule), rule);
  assert.ok(!csp.includes('unsafe-eval') && !csp.includes('ws:'), 'no eval or websockets in production');
  assert.equal(headers['X-Frame-Options'], 'DENY');
  assert.match(headers['Strict-Transport-Security'], /max-age=\d{8}/);
});

test('development adds only what hot reload needs', () => {
  const csp = policy(true)['Content-Security-Policy'];
  assert.ok(csp.includes("'unsafe-eval'") && csp.includes('ws:'));
});
