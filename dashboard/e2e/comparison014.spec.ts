import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";

test("repair comparison overview displays summary, matrix and downloads", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("/repair-comparison");
  await expect(page.getByRole("heading", { name: /Three repair strategies/ })).toBeVisible();
  await expect(page.getByRole("table", { name: /Strategy summary table/ })).toContainText("7 / 12");
  await expect(page.getByRole("table", { name: /19 cases comparison matrix/ })).toBeVisible();

  // Test downloading attempts.json report
  const reportDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: /Download full comparison report/ }).click();
  const reportPath = await (await reportDownload).path();
  const reportData = JSON.parse(await fs.readFile(reportPath!, "utf8"));
  expect(reportData.attempts).toBe(57);
  expect(reportData.cases.length).toBe(24);

  // Test drilldown to verified repair case
  await page.goto("/repair-comparison/django__django-14752/loop");
  await expect(page.getByRole("heading", { name: /django__django-14752/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Strategy: loop/ })).toBeVisible();
  await expect(page.getByText("Verified repair")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Proposed model patch" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Independent verification checks" })).toBeVisible();

  // Test downloading candidate.patch
  const patchDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download candidate.patch" }).click();
  const patchPath = await (await patchDownload).path();
  const patchContent = await fs.readFile(patchPath!, "utf8");
  expect(patchContent).toContain("--- a/django/contrib/admin/views/autocomplete.py");

  // Verify disallowed path fails with 404
  const bad = await page.request.get("/api/comparison014/unsafe/file.txt");
  expect(bad.status()).toBe(404);

  expect(errors).toEqual([]);
  await page.screenshot({ path: test.info().outputPath("comparison-desktop.png"), fullPage: true });
});

test("repair comparison remains responsive and accessible at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/repair-comparison");
  await expect(page.getByRole("heading", { name: /Three repair strategies/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.goto("/repair-comparison/django__django-14752/loop");
  await expect(page.getByRole("heading", { name: /django__django-14752/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  const downloadLink = page.getByRole("link", { name: "Download candidate.patch" });
  await downloadLink.focus();
  await expect(downloadLink).toBeFocused();
  await page.screenshot({ path: test.info().outputPath("comparison-390.png"), fullPage: true });
});
