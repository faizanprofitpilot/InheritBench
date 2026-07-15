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
