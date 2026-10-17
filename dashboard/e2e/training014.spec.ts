import { expect, test } from '@playwright/test';
import fs from 'node:fs/promises';

test('training evidence connects task, measured comparison and exact head download', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/repair-investigation');
  await page.getByRole('link', { name: 'Retrieval training', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Train a smaller head/ })).toBeVisible();
  await expect(page.getByRole('table')).toContainText('0.9225');
  await expect(page.getByText(/It includes zero/)).toBeVisible();
  const link = page.getByRole('link', { name: 'Download trained head', exact: true });
  await link.focus();
  const pending = page.waitForEvent('download');
  await page.keyboard.press('Enter');
  const file = await (await pending).path();
  const head = JSON.parse(await fs.readFile(file!, 'utf8'));
  expect(head.dimension).toBe(768);
  expect(head.rank).toBe(16);
  expect(head.selected_step).toBe(100);
  const bad = await page.request.get('/api/training014/weights.safetensors');
  expect(bad.status()).toBe(404);
  expect(errors).toEqual([]);
  await page.screenshot({ path: test.info().outputPath("training-desktop.png"), fullPage: true });
});

test('training comparison remains readable at 390 px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/retrieval-training');
  await expect(page.getByRole('heading', { name: /Train a smaller head/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const comparison = page.getByRole('region', { name: 'Held-out retrieval results', exact: true });
  expect(await comparison.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  const download = page.getByRole('link', { name: 'Download all paired held-out outcomes', exact: true });
  await download.focus();
  await expect(download).toBeFocused();
  await page.screenshot({ path: test.info().outputPath('training-390.png'), fullPage: true });
});
