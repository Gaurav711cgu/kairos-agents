import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import summary from "../lib/pilot013-summary.json";

const runtime = process.env.KAIROS_REVIEWER_RUNTIME || path.resolve("..", ".runtime/reviewer005");

test("completed development investigation exposes source, patch, checks and exact downloads", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("link", { name: "Inspect the completed repair investigation", exact: true }).click();
  await expect(page.getByRole("heading", { name: /From selected source.*to a checked repair/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Checks passed", exact: true })).toBeVisible();
  await expect(page.getByText(/^22 tests run\./).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Before changed lines" })).toContainText("self._mount_obj_if_needed()");
  const region = page.locator("summary").filter({ hasText: /^Source region 1:/ });
  await region.focus(); await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Retrieved source excerpt" })).toBeVisible();
  const output = page.locator("summary").filter({ hasText: /^Read test output$/ }).first();
  await output.focus(); await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: /Test (runner|standard) output/ }).first()).toBeVisible();
  const pending = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download model patch", exact: true }).click();
  const downloaded = await (await pending).path();
  expect(await fs.readFile(downloaded!, "utf8")).toContain("-        self._mount_obj_if_needed()");
  const bundle = await page.request.get("/api/pilot013/bundle.json");
  const record = await bundle.json();
  expect(record.outcome).toBe("verified_repair");
  expect(record.model_calls).toBe(summary.calls);
  expect(record.steps.filter((step: { kind: string }) => step.kind === "model")).toHaveLength(5);
  expect(bundle.headers()["content-disposition"]).toContain("attachment");
  expect((await page.request.get("/api/pilot013/missing.json")).status()).toBe(404);
  await fs.mkdir(path.join(runtime, "screenshots"), { recursive: true });
  await page.screenshot({ path: path.join(runtime, "screenshots/pilot013-desktop.png"), fullPage: true });
  expect(errors).toEqual([]);
});

test("390px investigation preserves scope, keyboard controls and source bounds", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/repair-investigation");
  await expect(page.getByText(/previously exposed development issue/)).toBeVisible();
  await expect(page.getByText(/Earlier 0\/10 and 0\/36/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const provenance = page.locator("summary").filter({ hasText: "Model, inference cost and provenance" });
  await provenance.focus(); await page.keyboard.press("Enter");
  await expect(page.getByText(/66,744 captured input tokens/)).toBeVisible();
  await expect(page.getByRole("button", { name: /run|submit|queue/i })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await fs.mkdir(path.join(runtime, "screenshots"), { recursive: true });
  await page.screenshot({ path: path.join(runtime, "screenshots/pilot013-mobile.png"), fullPage: true });
});
