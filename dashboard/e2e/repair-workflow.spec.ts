import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import evidence from "../lib/repair010-results.json";

const runtime = process.env.KAIROS_REVIEWER_RUNTIME || path.resolve("..", ".runtime/reviewer005");

test("repair follow-up exposes captured patches, independent checks and original outcomes", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("link", { name: "Read the repair workflow follow-up", exact: true }).click();
  await expect(page).toHaveURL(/\/repair-workflow$/);
  await expect(page.getByRole("heading", { name: /A captured patch.*Checked independently/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Checks passed", exact: true })).toHaveCount(2);
  await expect(page.getByText(/no completed end-to-end repair success/)).toBeVisible();
  await expect(page.getByText(/stopped at the subscription usage limit/)).toBeVisible();
  for (const candidate of evidence.results) {
    const section = page.getByRole("region", { name: candidate.title, exact: true });
    await expect(section.getByRole("region", { name: "Before changed lines" }).first()).toBeVisible();
    await expect(section.getByRole("region", { name: "After changed lines" }).first()).toBeVisible();
    const pending = page.waitForEvent("download");
    await section.getByRole("link", { name: "Download candidate patch", exact: true }).click();
    const downloaded = await (await pending).path();
    expect(downloaded).not.toBeNull();
    expect(await fs.readFile(downloaded!, "utf8")).toBe(candidate.patch);
    const checks = await page.request.get(`/api/repair010/${candidate.case}/checks.json`);
    expect(checks.ok()).toBe(true);
    expect(await checks.json()).toEqual(candidate.checks);
    const original = await page.request.get(`/api/repair010/${candidate.case}/original-model-response.json`);
    expect(original.ok()).toBe(true);
    expect((await original.json()).action).toBe("propose_patch");
  }
  const absent = await page.request.get("/api/repair010/absent-case/candidate.patch");
  expect(absent.status()).toBe(404);
  const attachment = await page.request.get("/api/repair010/attempts.json");
  expect(attachment.headers()["x-content-type-options"]).toBe("nosniff");
  expect(attachment.headers()["cache-control"]).toBe("no-store");
  expect(attachment.headers()["content-disposition"]).toContain("attachment");
  const output = page.locator("summary").filter({ hasText: /^Read test output$/ }).first();
  await output.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: /Test (runner|standard) output/ }).first()).toBeVisible();
  const ledger = page.locator("summary").filter({ hasText: "Inspect every captured attempt" });
  await ledger.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Development attempt ledger" })).toBeVisible();
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(evidence.attempts.length + 1);
  const pending = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download complete attempt ledger", exact: true }).click();
  const downloaded = await (await pending).path();
  const ledgerData = JSON.parse(await fs.readFile(downloaded!, "utf8"));
  expect(ledgerData.attempts).toMatchObject(evidence.attempts);
  await fs.mkdir(path.join(runtime, "screenshots"), { recursive: true });
  await page.screenshot({ path: path.join(runtime, "screenshots/repair010-desktop.png"), fullPage: true });
  expect(errors).toEqual([]);
});

test("390px follow-up contains its evidence and explains the optional local task path", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/repair-workflow");
  await expect(page.getByRole("heading", { name: "Investigate another reviewed Python defect.", exact: true })).toBeVisible();
  await expect(page.getByText(/does not require a maintainer repair/)).toBeVisible();
  await expect(page.getByText(/frozen local-model v7 study, completed on 13 October 2026, remains 0\/10/i)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const commands = page.locator("summary").filter({ hasText: "Show the local commands" });
  await commands.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("pre").filter({ hasText: "scripts.study010 validate-task" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: /submit|queue|run investigation/i })).toHaveCount(0);
  await fs.mkdir(path.join(runtime, "screenshots"), { recursive: true });
  await page.screenshot({ path: path.join(runtime, "screenshots/repair010-mobile.png"), fullPage: true });
});
