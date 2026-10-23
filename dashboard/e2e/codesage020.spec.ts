import { test, expect } from '@playwright/test';

test('retrieval inspection distinguishes provenance from repair scores', async ({ page }, testInfo) => {
  await page.goto('/repair-comparison/batch-eval');
  await expect(page.getByRole('heading', { name: 'Repository retrieval investigation', exact: true })).toBeVisible();
  await expect(page.getByText('Not eligible: case revisions are unbound', { exact: true })).toBeVisible();
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByRole('row')).toHaveCount(16);
  await expect(page.getByText('Not executed by this retrieval diagnostic', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('retrieval-diagnostic-desktop.png'), fullPage: true });
});

test('context demonstration discloses handwritten patch and missing checks', async ({ page }) => {
  await page.goto('/repair-comparison/codesage-mcp');
  await expect(page.getByRole('heading', { name: 'CodeSage context demonstration', exact: true })).toBeVisible();
  await expect(page.getByText('Handwritten example', { exact: true })).toBeVisible();
  await expect(page.getByText('Not established by this capture', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Handwritten example patch')).toContainText('fixturedef.scope');
  await expect(page.locator('.badge-pass')).toHaveCount(0);
});

test('diagnostic table is keyboard reachable', async ({ page }) => {
  await page.goto('/repair-comparison/batch-eval');
  const region = page.getByRole('region', { name: 'Retrieval diagnostic cases' });
  for (let step = 0; step < 40 && !(await region.evaluate(el => el === document.activeElement)); step++) {
    await page.keyboard.press('Tab');
  }
  await expect(region).toBeFocused();
});

test('390px inspection keeps page and patch within viewport', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ['/repair-comparison/batch-eval', '/repair-comparison/codesage-mcp']) {
    await page.goto(route);
    await expect(page.locator('h1')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(route.split('/').pop() + '-390.png'), fullPage: true });
  }
});
