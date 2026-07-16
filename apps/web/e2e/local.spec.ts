import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const routes = [
  "/",
  "/lab/opsroute/",
  "/lab/opsroute/methods/",
  "/lab/opsroute/failures/",
  "/lab/opsroute/memo/",
  "/lab/opsroute/evidence/",
];

function blockExternalRequests(page: Page): void {
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) {
      throw new Error(`unexpected runtime request: ${request.url()}`);
    }
  });
}

for (const route of routes) {
  test(`${route} loads directly and remains accessible`, async ({ page }) => {
    blockExternalRequests(page);
    const errors: string[] = [];
    page.on("console", (message) => message.type() === "error" && errors.push(message.text()));
    await page.goto(route);
    await expect(page.locator("h1").first()).toBeVisible();
    expect(errors).toEqual([]);
    const accessibility = await new AxeBuilder({ page }).analyze();
    expect(accessibility.violations).toEqual([]);
  });
}

test("surface metrics remain separate", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/lab/opsroute/");
  await expect(page.getByText("Confirmatory · n=64")).toBeVisible();
  await page.getByRole("tab", { name: "Adversarial · n=32" }).click();
  await expect(page.getByText("Separate frozen surfaces. No blended score.")).toBeVisible();
});

test("landing page presents the product workflow and frozen published case", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/");

  await expect(page.getByText("MODEL SUCCESSION LAB", { exact: true })).toBeVisible();
  await expect(page.getByText("PUBLISHED QWEN → OLMO CASE", { exact: true })).toBeVisible();
  await expect(page.getByText("VALIDATED GPT-5.6 ANALYSIS", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your successor model does not inherit capability by default." })).toBeVisible();
  await expect(page.getByText(/evaluate a model-family replacement before production/)).toBeVisible();

  await expect(page.getByRole("link", { name: /Open the succession lab/ })).toHaveAttribute(
    "href",
    "/lab/opsroute/",
  );
  await expect(page.getByRole("link", { name: /View the migration recommendation/ }).first()).toHaveAttribute(
    "href",
    "/lab/opsroute/memo/",
  );

  for (const label of ["Succession Case", "Recovery Paths", "Failure Explorer", "Recommendation", "Evidence"]) {
    await expect(page.getByRole("link", { name: label, exact: true }).first()).toBeVisible();
  }
  for (const step of [
    "Measure the capability break",
    "Test recovery paths",
    "Stress-test the candidates",
    "Choose under constraints",
  ]) {
    await expect(page.getByRole("heading", { name: step })).toBeVisible();
  }

  for (const metric of [
    "54.688%",
    "0.000%",
    "59 / 768",
    "5 / 16",
    "719 / 768",
    "4 / 48",
    "85.938%",
  ]) {
    await expect(page.getByText(metric, { exact: true }).first()).toBeAttached();
  }
  await expect(page.getByText(/10 original labels directly in target training/).first()).toBeVisible();
  await expect(page.getByText(/214 teacher-generated labels/).first()).toBeVisible();
  await expect(page.getByText(/teacher trained with 224 original labels/).first()).toBeVisible();
  await expect(page.getByText(/designed from 224 labeled records/).first()).toBeVisible();

  await expect(page.getByText("Clean capability retention", { exact: true })).toBeVisible();
  await expect(page.getByText("Adversarial resilience", { exact: true })).toBeVisible();
  await expect(page.getByText("Semantic exactness · N=64", { exact: true })).toBeVisible();
  await expect(page.getByText("Semantic exactness · N=32", { exact: true })).toBeVisible();
});

test("raw outputs and memo evidence open without regeneration", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/lab/opsroute/failures/");
  await page.getByText("Inspect exact raw output").first().click();
  await expect(page.locator("pre").filter({ hasText: /decision|<empty output>/ }).first()).toBeVisible();
  await page.goto("/lab/opsroute/memo/");
  await page.getByRole("button", { name: /confirmatory_semantic/ }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Evidence reference");
});

test("browser integrity verification passes", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/lab/opsroute/evidence/");
  await page.getByRole("button", { name: "Verify served bytes" }).click();
  await expect(page.getByText(/committed files match their SHA-256 hashes/)).toBeVisible();
});

test("keyboard navigation and reduced motion remain usable", async ({ page }) => {
  blockExternalRequests(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
});
