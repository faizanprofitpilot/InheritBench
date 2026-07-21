import { createHash } from "node:crypto";
import { writeFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const url = process.env.DEPLOYMENT_URL;
const report = process.env.PHASE5_DEPLOYMENT_REPORT;
if (!url || !report) throw new Error("deployment verification environment is incomplete");

test("public deployment satisfies the complete product gate", async ({ browser }) => {
  const consoleErrors: string[] = [];
  const hydrationErrors: string[] = [];
  const accessibilityErrors: string[] = [];
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
        if (/hydration/i.test(message.text())) hydrationErrors.push(message.text());
      }
    });
    for (const route of [
      "/",
      "/sandbox/",
      "/lab/opsroute/",
      "/lab/opsroute/methods/",
      "/lab/opsroute/failures/",
      "/lab/opsroute/memo/",
      "/lab/opsroute/evidence/",
      "/run/opsroute-qwen-olmo/",
      "/run/local/",
    ]) {
      const response = await page.goto(`${url}${route}`);
      expect(response?.ok()).toBe(true);
      await expect(page.locator("h1").first()).toBeVisible();
    }
    await page.goto(`${url}/sandbox/`);
    const sandboxBefore = await new AxeBuilder({ page }).analyze();
    accessibilityErrors.push(...sandboxBefore.violations.map((item) => item.id));
    await page.getByRole("button", { name: "Run assurance evaluation" }).click();
    await expect(page.getByRole("heading", { name: "CONDITIONAL_PASS" })).toBeVisible();
    await expect(page.getByText("Matches frozen expectations")).toBeVisible();
    await expect(
      page.getByText("Evidence integrity", { exact: true }).locator(".."),
    ).toContainText("VERIFIED");
    const sandboxAfter = await new AxeBuilder({ page }).analyze();
    accessibilityErrors.push(...sandboxAfter.violations.map((item) => item.id));
    await page.goto(`${url}/lab/opsroute/evidence/`);
    await page.getByRole("button", { name: "Verify served bytes" }).click();
    await expect(page.getByText("Showcase bundle verified")).toBeVisible();
    await context.close();
  }
  expect(consoleErrors).toEqual([]);
  expect(hydrationErrors).toEqual([]);
  expect(accessibilityErrors).toEqual([]);
  const payload: Record<string, unknown> = {
    schema_version: "phase5-deployment-verification-v0.1",
    verification_id: `phase5-deployment-${hash(url).slice(0, 16)}`,
    public_url: url,
    stable_public_url: true,
    incognito_access_passed: true,
    deep_links_passed: true,
    no_auth_or_secret_required: true,
    browser_integrity_passed: true,
    core_flow_passed: true,
    desktop_passed: true,
    mobile_passed: true,
    console_errors: consoleErrors,
    hydration_errors: hydrationErrors,
    accessibility_errors: accessibilityErrors,
  };
  payload.content_sha256 = hash(canonical(payload));
  await writeFile(report, `${canonical(payload)}\n`, { flag: "wx" });
});

function hash(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}
