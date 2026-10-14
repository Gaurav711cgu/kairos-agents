import currentCohort from "../lib/study007-cohort.json";
import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import cohort from '../lib/study004-cohort.json';
import followup from '../lib/followup006-cohort.json';
import followupResults from '../lib/followup006-results.json';
const repair = '8b03a42f-149e-4d44-937f-0d61636f6042';
const runtime = process.env.KAIROS_REVIEWER_RUNTIME || path.resolve('..', '.runtime/reviewer005');
async function capture(page: Page, name: string) {
  const output = path.join(runtime, 'screenshots');
  await fs.mkdir(output, { recursive: true });
  await page.screenshot({ path: path.join(output, name + '.png'), fullPage: name !== 'reviewer-home-desktop' });
}
async function downloadedJson(page: Page, label: string) {
  const pending = page.waitForEvent('download');
  await page.getByRole('link', { name: label, exact: true }).click();
  const download = await pending;
  const file = await download.path();
  expect(file).not.toBeNull();
  return JSON.parse(await fs.readFile(file!, 'utf8'));
}
test('recorded repair exposes genuine patch, verifier evidence and keyboard context', async ({ page }) => {
  const pageErrors: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.goto('/');
  await expect(page.getByText('10 recorded attempts', { exact: true })).toBeVisible();
  await expect(page.getByText('Evidence viewer · Original investigation captures', { exact: true })).toBeVisible();
  await capture(page, 'reviewer-home-desktop');
  await page.goto('/investigations/' + repair);
  await expect(page.getByText(/^Recorded investigation ·/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Verified repair', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Before changed lines' })).toContainText('FILE_UPLOAD_PERMISSIONS = None');
  await expect(page.getByRole('region', { name: 'After changed lines' })).toContainText('0o644');
  const patchPending = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download patch', exact: true }).click();
  const patchFile = await (await patchPending).path();
  expect(await fs.readFile(patchFile!, 'utf8')).toContain('+FILE_UPLOAD_PERMISSIONS = 0o644');
  const bundle = await downloadedJson(page, 'Download evidence');
  expect(bundle.id).toBe(repair);
  expect(bundle.integrity.verified).toBe(true);
  const check = bundle.steps.find((step: { name: string }) => step.name === 'run_checks');
  expect(check.result.body.passed).toBe(true);
  expect(check.result.body.stderr).toMatch(/Ran 110 tests/);
  expect(check.result.body.stderr).toMatch(/skipped=1/);
  const context = page.getByRole('button', { name: /Prepared the context/ }).first();
  await context.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Evidence selected for the next call' })).toBeVisible();
  await capture(page, 'reviewer-repair-desktop');
  expect(pageErrors).toEqual([]);
});
test('frozen comparison retains zero repairs, costs and incomplete timing', async ({ page }) => {
  expect(cohort.complete).toBe(true);
  expect(cohort.ids).toHaveLength(36);
  await page.goto('/investigations/' + cohort.ids[0]);
  const comparison = page.getByRole('region', { name: 'Strategy comparison' });
  for (const label of ['Single call', 'Tool loop', 'Independent drafts']) await expect(comparison).toContainText(label);
  await page.goto('/study');
  await expect(page.getByRole('heading', { name: '0 / 12 verified', exact: true })).toHaveCount(3);
  await expect(page.getByText('Captured tokens', { exact: true })).toHaveCount(3);
  await expect(page.getByText(/Target missed/)).toBeVisible();
  const comparisonJson = await downloadedJson(page, 'Download comparison');
  expect(comparisonJson.complete).toBe(true);
  expect(Object.values(comparisonJson.strategies).every(value => (value as { verified: number }).verified === 0)).toBe(true);
  const attempts = await downloadedJson(page, 'Download all attempts');
  expect(Array.isArray(attempts) ? attempts.length : attempts.attempts.length).toBe(78);
  await capture(page, 'reviewer-study-desktop');
  await page.goto('/investigations/' + cohort.incomplete_duration_ids[0]);
  await expect(page.getByText('Timing incomplete', { exact: true }).first()).toBeVisible();
});
test('recorded mode closes private commands and never simulates login', async ({ page }) => {
  await page.goto('/workbench');
  await expect(page.getByRole('heading', { name: 'Start a new investigation.', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Set up the live workbench', exact: true })).toHaveAttribute('href','/docs#fullstack');
  await expect(page.getByRole('link', { name: 'Workbench', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Sign in', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Queue investigation', exact: true })).toHaveCount(0);
  for (const method of ['get', 'post'] as const) {
    const response = await page.request[method]('/api/workbench/investigations');
    expect(response.status()).toBe(403);
    expect((await response.json()).error).toBe('Private execution is disabled in recorded mode.');
  }
  const fork = await page.request.post('/api/local-fork/' + repair);
  expect(fork.status()).toBe(403);
  const cookies = await page.context().cookies();
  expect(cookies.some(cookie => cookie.name === 'kairos_session')).toBe(false);
});
test('390px evidence, capacity history and unavailable records remain readable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [route, name] of [['/', 'reviewer-home-mobile'], ['/investigations/' + repair, 'reviewer-repair-mobile'], ['/study', 'reviewer-study-mobile'], ['/capacity', 'reviewer-capacity-mobile']]) {
    await page.goto(route);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await capture(page, name);
  }
  await expect(page.getByRole('heading', { name: /435,270 requests.*A complete 42-minute test/ })).toBeVisible();
  const capacity = await downloadedJson(page, 'Download measurements');
  expect(capacity.quiet_repeat.raw_requests).toBe(435270);
  expect(capacity.quiet_repeat.target_met).toBe(true);
  expect(capacity.original_sustained_capacity_accepted).toBe(false);
  await page.goto('/investigations/00000000-0000-4000-8000-000000000000');
  await expect(page.getByText('This investigation is not included in the recorded evidence package.', { exact: true })).toBeVisible();
  await page.goto('/investigations/not-an-identifier');
  await expect(page.getByText('Invalid investigation identifier.', { exact: true })).toBeVisible();
});

test('follow-up keeps fresh failures, paired development evidence and original bytes visible', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText(/Five fresh Python cases/)).toBeVisible();
  await expect(page.getByText(/five locked Python cases/)).toBeVisible();
  await expect(page.locator('.investigation-row')).toHaveCount(5);
  await page.getByRole('combobox', { name: /^Configuration/ }).selectOption('final');
  await expect(page.locator('.investigation-row')).toHaveCount(5);
  await page.getByRole('link', { name: 'Inspect an investigation', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(currentCohort.featured_id));
  await page.goto('/investigations/' + followup.featured_id);
  const comparison = page.getByRole('region', { name: 'Strategy comparison' });
  await expect(comparison).toContainText('Single call');
  await expect(comparison).toContainText('Tool loop');
  await expect(comparison).not.toContainText('Comparison unavailable');
  await expect(page.getByRole('region', { name: 'Before changed lines' })).toContainText("save(update_fields");
  await expect(page.getByRole('region', { name: 'After changed lines' })).toContainText("update_fields");
  const source = page.getByRole('button', { name: /Retained original source/ }).first();
  await source.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('region', { name: 'Retrieved source excerpt' })).toContainText('def _rename');
  const context = page.getByRole('button', { name: /Prepared the context/ }).first();
  await context.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Evidence selected for the next call' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Retrieved source excerpt' }).first()).toContainText('def _rename');
  const bundle = await downloadedJson(page, 'Download evidence');
  expect(bundle.id).toBe(followup.featured_id);
  expect(bundle.steps.find((step: { name: string }) => step.name === 'run_checks').result.body.passed).toBe(true);
  const original = JSON.parse(await fs.readFile(path.resolve('evidence/records', followup.featured_id + '.json'), 'utf8'));
  expect(bundle).toEqual(original);
  await capture(page, 'followup-repair-desktop');
  await page.goto('/follow-up');
  await expect(page.getByRole('heading', { name: '0 / 5 verified', exact: true })).toHaveCount(2);
  await expect(page.getByText(/Consumption for the unknown dispatch is unavailable/)).toBeVisible();
  await expect(page.getByText('Dispatch outcome unknown: 1', { exact: true })).toBeVisible();
  await expect(page.locator('.prose a[href^="/investigations/"]')).toHaveCount(28);
  const results = await downloadedJson(page, 'Download follow-up results');
  expect(results).toEqual(followupResults);
  expect(results.historical_study).toEqual({ verified: 0, attempts: 36, preserved: true });
  await capture(page, 'followup-results-desktop');
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [route, name] of [['/follow-up', 'followup-results-mobile'], ['/investigations/' + followup.featured_id, 'followup-repair-mobile']]) {
    await page.goto(route);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await capture(page, name);
  }
});

test('current documentation uses the reviewer entry point and states verification limits', async ({ page }) => {
  await page.goto('/docs');
  await expect(page.getByRole('heading', { name: 'Open the evidence viewer.', exact: true })).toBeVisible();
  await expect(page.locator('article')).toContainText('python3 -m scripts.reviewer demo');
  await expect(page.locator('article')).toContainText('PostgreSQL 55434');
  await expect(page.locator('article')).toContainText('feedback-visible');
  await expect(page.locator('article')).not.toContainText('python3 scripts/configure_local.py');
  await page.goto('/engineering');
  await expect(page.locator('article')).toContainText('55 of 66');
  await expect(page.locator('article')).toContainText('Fresh v5 validation is 0/10');
  await expect(page.locator('article')).toContainText('adversarial test-forgery resistance is unproven');
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ['/docs', '/engineering']) {
    await page.goto(route);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});


test('first-time reviewer follows the interaction path and sees an earned outcome', async ({ page }) => {
  await page.goto('/how-it-works');
  await expect(page.getByRole('heading', { name: 'Inspect a saved result.', exact: true })).toBeVisible();
  const first = page.locator('summary').filter({ hasText: 'Choose a completed investigation' });
  await first.focus(); await page.keyboard.press('Enter');
  await expect(page.getByText('You receive an inspectable trace immediately, without local setup.', { exact: false })).toBeVisible();
  await page.getByRole('link', { name: 'Inspect the development repair', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Verified repair', exact: true }).first()).toBeVisible();
  const bundle = await downloadedJson(page, 'Download evidence');
  expect(bundle.outcome).toBe('verified_repair');
  expect(bundle.steps.some((step: { name: string; result: { body: { passed: boolean } } }) => step.name === 'run_checks' && step.result.body.passed)).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/how-it-works');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await capture(page, 'first-investigation-mobile');
});


test('current study exposes every fresh result and keeps development comparisons separate', async ({ page }) => {
  await page.goto('/advancement');
  await expect(page.getByRole('heading', { name: '0 / 5 verified', exact: true })).toHaveCount(2);
  const results = await downloadedJson(page, 'Download build007 results');
  expect(results.attempts).toHaveLength(46);
  expect(results.qualification.qualified).toBe(5);
  expect(results.qualification.complete).toBe(false);
  await page.goto('/investigations/' + currentCohort.featured_id);
  const comparison = page.getByRole('region', { name: 'Strategy comparison' });
  await expect(comparison).toContainText('Single call');
  await expect(comparison).toContainText('Tool loop');
  const context = page.getByRole('button', { name: /Prepared the context/ }).first();
  await context.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('region', { name: 'Retrieved source excerpt' }).first()).toContainText('def _rename');
  await capture(page, 'build007-inspector-desktop');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/advancement');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await capture(page, 'build007-results-mobile');
});
