import { test, expect, type Page, type APIResponse } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const runtime = process.env.KAIROS_REVIEWER_RUNTIME || path.resolve('..', '.runtime/reviewer005');
const origin = process.env.KAIROS_REVIEWER_URL || 'http://127.0.0.1:3310';
type Account = { username: string; password: string; role?: string; tenant_id?: string; subject: string };
// Only the CLI-generated private credential file is read. No storageState, traces or credentials are exported.
const credentials = JSON.parse(fs.readFileSync(path.join(runtime, 'identity.local.json'), 'utf8')) as { accounts: Account[] };
const prefix = '/api/workbench/investigations';
async function login(page: Page, role: string) {
  const account = credentials.accounts.find(item => item.role === role);
  if (!account) throw new Error('Reviewer credential role is missing: ' + role);
  await page.goto('/workbench');
  await page.getByRole('link', { name: 'Sign in', exact: true }).click();
  await page.getByLabel('Username').fill(account.username);
  await page.getByLabel('Password', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Sign In', exact: true }).click();
  await page.waitForURL(origin + '/workbench');
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible();
  const identity = await page.request.get('/api/workbench/auth/me');
  expect(identity.status()).toBe(200);
  const actual = await identity.json();
  expect(actual.subject).toBe(account.subject);
  expect(actual.tenant_id).toBe(account.tenant_id);
  expect(actual.role).toBe(role);
}
async function accepted(response: Pick<APIResponse, 'status' | 'json'>, status = 202) {
  expect(response.status()).toBe(status);
  return response.json();
}
async function create(page: Page, key: string, configuration = 'loop-v5') {
  return page.request.post(prefix, { headers: { Origin: origin, 'Idempotency-Key': key }, data: { task_id: 'kairos-clock-lease', configuration } });
}
async function cancel(page: Page, id: string) {
  const response = await page.request.post(prefix + '/' + id + '/cancel', { headers: { Origin: origin }, data: {} });
  expect(response.status()).toBe(200);
  expect((await response.json()).status).toBe('cancelled');
}
test('fresh real OIDC supports queue, cancel, fork, replay, publication, download and logout', async ({ page }) => {
  await login(page, 'admin');
  await page.getByLabel('Historical case').selectOption('kairos-clock-lease');
  const queued = page.waitForResponse(response => response.url().endsWith(prefix) && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Queue investigation', exact: true }).click();
  const parent = await accepted(await queued);
  expect(parent.status).toBe('queued');
  expect(parent.model_calls).toBe(0);
  expect(parent.configuration).toBe('loop-v7');
  expect(parent.config_snapshot.generation.temperature).toBe(0);
  const progress = await page.request.get(prefix + '/' + parent.id + '/progress');
  expect(progress.status()).toBe(200);
  expect((await progress.json()).phase).toBe('queued');
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Cancelled', exact: true })).toBeVisible();
  const forked = page.waitForResponse(response => response.url().endsWith('/fork') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Create a fresh fork', exact: true }).click();
  const child = await accepted(await forked);
  expect(child.parent_id).toBe(parent.id);
  await expect(page.getByRole('button', { name: 'Cancel', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Cancelled', exact: true })).toBeVisible();
  const replayed = page.waitForResponse(response => response.url().endsWith('/replay'));
  await page.getByRole('button', { name: 'Replay saved steps', exact: true }).click();
  const replay = await accepted(await replayed, 200);
  expect(replay.network_calls).toBe(0);
  expect(replay.tool_executions).toBe(0);
  await expect(page.getByRole('status').filter({ hasText: 'Recorded playback' })).toBeVisible();
  await page.getByRole('button', { name: 'Publish evidence', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Publish evidence', exact: true })).toBeDisabled();
  const downloadPending = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download evidence', exact: true }).click();
  const download = await downloadPending;
  expect(download.suggestedFilename()).toBe('kairos-' + child.id + '.json');
  const captured = JSON.parse(fs.readFileSync((await download.path())!, 'utf8'));
  expect(captured.id).toBe(child.id);
  expect(captured.integrity.verified).toBe(true);
  expect(captured.model_calls).toBe(0);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Sign in', exact: true })).toBeVisible();
  expect((await page.request.get(prefix)).status()).toBe(401);
});
test('real session preserves command identity, rejects conflicts and paginates without duplicates', async ({ page }) => {
  await login(page, 'admin');
  const key = crypto.randomUUID();
  const first = await accepted(await create(page, key));
  const retry = await accepted(await create(page, key));
  expect(retry.id).toBe(first.id);
  expect((await create(page, key, 'baseline-v5')).status()).toBe(409);
  await cancel(page, first.id);
  const forkKey = crypto.randomUUID();
  const fork = async (configuration = 'loop-v5') => page.request.post(prefix + '/' + first.id + '/fork', {
    headers: { Origin: origin, 'Idempotency-Key': forkKey }, data: { configuration },
  });
  const child = await accepted(await fork());
  expect((await accepted(await fork())).id).toBe(child.id);
  expect((await fork('baseline-v5')).status()).toBe(409);
  await cancel(page, child.id);
  const extra = await accepted(await create(page, crypto.randomUUID()));
  await cancel(page, extra.id);
  const ids: string[] = [];
  let cursor: string | null = null;
  for (let count = 0; count < 100; count++) {
    const response = await page.request.get(prefix + '?limit=2' + (cursor ? '&cursor=' + encodeURIComponent(cursor) : ''));
    const body = await accepted(response, 200);
    expect(body.investigations.length).toBeLessThanOrEqual(2);
    ids.push(...body.investigations.map((item: { id: string }) => item.id));
    cursor = body.next_cursor;
    if (!cursor) break;
  }
  expect(cursor).toBeNull();
  expect(new Set(ids).size).toBe(ids.length);
  for (const id of [first.id, child.id, extra.id]) expect(ids.filter(value => value === id)).toHaveLength(1);
  expect((await page.request.get(prefix + '?limit=101')).status()).toBe(422);
  expect((await page.request.get(prefix + '?cursor=invalid')).status()).toBe(422);
  const replay = await accepted(await page.request.get(prefix + '/' + first.id + '/replay'), 200);
  expect(replay.network_calls).toBe(0);
  expect(replay.tool_executions).toBe(0);
  expect(replay.investigation.model_calls).toBe(0);
});
test('real viewer membership denies mutations in UI and server', async ({ page }) => {
  await login(page, 'viewer');
  await expect(page.getByRole('button', { name: 'Queue investigation', exact: true })).toBeDisabled();
  expect((await create(page, crypto.randomUUID())).status()).toBe(403);
  const records = await accepted(await page.request.get(prefix), 200);
  const id = records.investigations[0]?.id;
  expect(id).toBeDefined();
  expect((await page.request.post(prefix + '/' + id + '/publish', { headers: { Origin: origin }, data: {} })).status()).toBe(403);
});
test('real operator cannot access another tenant record, progress, downloads or cursor', async ({ page, browser }) => {
  const adminContext = await browser.newContext({ baseURL: origin });
  const adminPage = await adminContext.newPage();
  let privateId = '', cursor = '';
  try {
    await login(adminPage, 'admin');
    const record = await accepted(await create(adminPage, crypto.randomUUID()));
    privateId = record.id;
    await cancel(adminPage, privateId);
    const records = await accepted(await adminPage.request.get(prefix + '?limit=1'), 200);
    cursor = records.next_cursor;
    expect(cursor).not.toBeNull();
  } finally { await adminContext.close(); }
  await login(page, 'operator');
  for (const suffix of ['', '/progress', '/bundle', '/patch', '/replay']) {
    expect((await page.request.get(prefix + '/' + privateId + suffix)).status()).toBe(404);
  }
  expect((await page.request.get(prefix + '?cursor=' + encodeURIComponent(cursor))).status()).toBe(422);
  const records = await accepted(await page.request.get(prefix), 200);
  expect(records.investigations.some((record: { id: string }) => record.id === privateId)).toBe(false);
  expect((await page.request.post(prefix + '/' + privateId + '/publish', { headers: { Origin: origin }, data: {} })).status()).toBe(403);
});
