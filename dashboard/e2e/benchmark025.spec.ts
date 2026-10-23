import { test, expect } from '@playwright/test';

test('benchmark shows independently tested results and the passing patch', async ({ page }) => {
  await page.goto('/benchmark');
  await expect(page.getByRole('heading', { name: 'On 7 bugs it had never seen, it fixed 3.' })).toBeVisible();
  const table = page.getByRole('table');
  await expect(table.getByRole('columnheader').nth(1)).toHaveText('Nemotron');
  await expect(table.locator('tfoot')).toContainText('4 of 5');
  const row = page.locator('details').filter({ hasText: 'Django #13516' });
  await row.locator('summary').focus();
  await page.keyboard.press('Enter');
  await expect(row.getByText('Attempt 1: Hidden tests pass')).toBeVisible();
  await expect(row.locator('pre').first()).toContainText('+++ b/django/');
});

test('benchmark stays readable at 390px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/benchmark');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
