import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { createHash } from "node:crypto";

const routes = [
  "/",
  "/sandbox/",
  "/lab/opsroute/",
  "/lab/opsroute/methods/",
  "/lab/opsroute/failures/",
  "/lab/opsroute/memo/",
  "/lab/opsroute/evidence/",
  "/run/opsroute-qwen-olmo/",
  "/run/local/",
];

function blockExternalRequests(page: Page): void {
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) {
      throw new Error(`unexpected runtime request: ${request.url()}`);
    }
  });
}

async function expectNoDocumentOverflow(page: Page): Promise<void> {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.innerWidth);
}

for (const route of routes) {
  test(`${route} loads directly and remains accessible`, async ({ page }) => {
    blockExternalRequests(page);
    const errors: string[] = [];
    page.on("console", (message) => message.type() === "error" && errors.push(message.text()));
    await page.goto(route);
    await expect(page.locator("h1").first()).toBeVisible();
    expect(errors).toEqual([]);
    if (route === "/") await page.waitForTimeout(600);
    const accessibility = await new AxeBuilder({ page }).analyze();
    expect(accessibility.violations).toEqual([]);
  });
}

test("judge routes never create document-level mobile overflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium-mobile", "required mobile viewport matrix");
  blockExternalRequests(page);
  for (const viewport of [
    { width: 320, height: 800 },
    { width: 360, height: 800 },
    { width: 375, height: 812 },
    { width: 390, height: 844 },
    { width: 430, height: 932 },
  ]) {
    await page.setViewportSize(viewport);
    for (const route of routes) {
      await page.goto(route);
      await expect(page.locator("h1").first()).toBeVisible();
      await expectNoDocumentOverflow(page);
    }
  }
});

test("Assurance Lab interactive states remain contained at mobile widths", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium-mobile", "required mobile interaction matrix");
  test.setTimeout(120_000);
  blockExternalRequests(page);
  for (const viewport of [
    { width: 320, height: 800 },
    { width: 360, height: 800 },
    { width: 375, height: 812 },
    { width: 390, height: 844 },
    { width: 430, height: 932 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/sandbox/");
    for (const step of ["Choose", "Run", "Review"]) {
      await expect(page.getByRole("listitem").filter({ hasText: step })).toBeVisible();
    }
    await expect(page.getByRole("listitem").filter({ hasText: "Stress" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^Anchored successor / })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expectNoDocumentOverflow(page);

    await page.getByRole("button", { name: "Run assurance evaluation" }).click();
    await expect(page.getByRole("heading", { name: "CONDITIONAL_PASS" })).toBeVisible();
    const workflow = page.getByRole("navigation", { name: "Assurance Lab workflow" });
    for (const step of ["Stress", "Verify"]) {
      await expect(workflow.getByRole("listitem").filter({ hasText: step })).toBeVisible();
    }
    await expect(page.getByText("Local verification receipt", { exact: true })).toBeAttached();
    await expectNoDocumentOverflow(page);

    await page.getByText("Detailed record inspection").click();
    await expect(page.getByText("Showing 96 of 96 records")).toBeVisible();
    await expectNoDocumentOverflow(page);

    await page.getByRole("button", { name: /Approval bypass · apply and rerun/ }).click();
    await expect(page.getByText(/Controlled mutation result/)).toBeVisible();
    await expectNoDocumentOverflow(page);

    const advancedTools = page.locator("details").filter({ hasText: "Advanced tools" }).locator("summary");
    await advancedTools.scrollIntoViewIfNeeded();
    await advancedTools.click({ force: true });
    await expect(page.getByLabel("Prediction file")).toBeVisible();
    await expect(page.getByRole("button", { name: "Download sample" })).toBeVisible();
    await expectNoDocumentOverflow(page);
  }
});

test("surface metrics remain separate", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/lab/opsroute/");
  await expect(page.getByText("Confirmatory · n=64")).toBeVisible();
  await expect(page.getByText("Qwen base", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("54.7%", { exact: true }).first()).toBeVisible();
  await page.getByRole("tab", { name: "Adversarial · n=32" }).click();
  await expect(page.getByText("68.8%", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Separate frozen surfaces. No blended score.")).toBeVisible();
});

test("migration profiles explain when no trained method is viable", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/lab/opsroute/");
  await expect(page.getByText("No viable trained migration")).toBeVisible();
  await expect(page.getByText(/Pure synthetic transfer never produced a balanced trainable target/)).toBeVisible();
});

test("header and footer expose the product paths", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/");
  for (const label of ["Product", "CLI workflow", "Reference run", "Assurance Lab", "GitHub"]) {
    await expect(page.getByRole("link", { name: label, exact: true }).first()).toBeAttached();
  }
  await expect(page.getByRole("link", { name: "View workflow" })).toHaveAttribute(
    "href",
    "/#developer-workflow",
  );
  for (const [label, href] of [
    ["CLI workflow", "/#developer-workflow"],
    ["Reference run", "/run/opsroute-qwen-olmo/"],
    ["Assurance Lab", "/sandbox/"],
    ["Integrity", "/lab/opsroute/evidence/"],
    ["Repository", "https://github.com/faizanprofitpilot/InheritBench"],
  ] as const) {
    await expect(page.locator("footer").getByRole("link", { name: label, exact: true })).toHaveAttribute("href", href);
  }
  const referenceRunLinks = page.getByRole("link", { name: "Reference run", exact: true });
  await expect(referenceRunLinks).toHaveCount(2);
  for (const link of await referenceRunLinks.all()) {
    await expect(link).toHaveAttribute("href", "/run/opsroute-qwen-olmo/");
    await expect(link).not.toHaveAttribute("href", /#/);
  }
  const allReferenceRunLinks = page.locator('a[href="/run/opsroute-qwen-olmo/"]').filter({
    hasText: /^Reference run$/,
  });
  await expect(allReferenceRunLinks).toHaveCount(3);
  const visibleReferenceRunLink = page.locator("header a:visible").filter({ hasText: /^Reference run$/ });
  await expect(visibleReferenceRunLink).toHaveAttribute("href", "/run/opsroute-qwen-olmo/");
  await visibleReferenceRunLink.click();
  await expect(page).toHaveURL(/\/run\/opsroute-qwen-olmo\/$/);
  await expect(page.getByTestId("run-inspector")).toBeVisible();
});

test("landing reference result retains a distinct hash anchor", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/#reference-result");
  await expect(page).toHaveURL(/\/#reference-result$/);
  await expect(page.locator("#reference-result")).toBeVisible();
  await expect(page.locator("#reference-result").getByText("Proof of execution", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Reference run", exact: true }).first()).not.toHaveAttribute(
    "href",
    /#/,
  );
});

test("landing page presents the product workflow and completed reference result", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Move the model/ })).toBeVisible();
  await expect(page.getByText("Local model-succession CLI", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Define the capability. Freeze the plan. Execute the succession.",
    }),
  ).toBeVisible();
  for (const command of [
    "inheritbench capability validate",
    "inheritbench succession plan",
    "inheritbench succession run",
    "inheritbench succession inspect",
    "inheritbench succession replay",
    "inheritbench succession export-web",
  ]) {
    await expect(page.getByText(new RegExp(command))).toBeVisible();
  }
  await expect(page.getByText("Diagnose → Recover → Assure", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Try the Assurance Lab", exact: true }).first()).toHaveAttribute(
    "href",
    "/sandbox/",
  );
  await expect(page.getByRole("link", { name: "See the developer workflow" })).toHaveAttribute(
    "href",
    "#developer-workflow",
  );
  await expect(page.getByRole("link", { name: /Inspect the Qwen → OLMo succession/ }).first()).toHaveAttribute(
    "href",
    "/run/opsroute-qwen-olmo/",
  );
  for (const step of ["Diagnose", "Recover", "Assure"]) {
    await expect(page.getByRole("heading", { name: step, exact: true })).toBeVisible();
  }
  await expect(page.getByText("64 / 64", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("63 / 64", { exact: true })).toBeVisible();
  for (const label of [
    "Operational correctness",
    "Exact-contract fidelity",
    "Strict validity",
    "Clean safety blockers",
    "Adversarial exact result",
    "Adversarial strict validity",
    "Safety findings",
    "Readiness",
  ]) {
    await expect(page.getByText(label, { exact: true })).toBeVisible();
  }
  await expect(page.getByText("2 on 1 adversarial record", { exact: true })).toBeVisible();
  await expect(page.getByText("CONDITIONAL PASS", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Test the assurance layer in your browser." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Test the assurance result" })).toHaveAttribute("href", "/sandbox/");
  await expect(page.getByRole("link", { name: "Inspect the full succession" })).toHaveAttribute(
    "href",
    "/run/opsroute-qwen-olmo/",
  );
});

test("raw outputs and memo evidence open without regeneration", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/lab/opsroute/failures/");
  await expect(page.getByText("Full retraining performs better")).toBeVisible();
  await page.getByText("View all archetype results").click();
  await page.getByLabel("Method").selectOption("target_full_retrain");
  await page.getByRole("button", { name: "Failures only" }).click();
  await expect(page.getByText(/Showing \d+ of 96 rows/)).toBeVisible();
  await page.getByText("Inspect exact raw output").first().click();
  await expect(page.locator("pre").filter({ hasText: /decision|<empty output>/ }).first()).toBeVisible();
  await page.goto("/lab/opsroute/memo/");
  await expect(page.getByRole("heading", { name: "Validated migration recommendation." })).toBeVisible();
  await expect(page.getByText("OLMo anchored transfer", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/85.9%/).first()).toBeVisible();
  await page.getByRole("button", { name: /View evidence confirmatory_semantic/ }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Evidence reference");
  await expect(page.getByRole("dialog")).toContainText("0.859375");
});

test("browser integrity verification passes", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/lab/opsroute/evidence/");
  await page.getByRole("button", { name: "Verify served bytes" }).click();
  await expect(page.getByText("Showcase bundle verified")).toBeVisible();
  await expect(page.getByText(/^(\d+) files checked · \1 hashes matched$/)).toBeVisible();
  await expect(page.getByText(/This verifies the deployed display bundle/)).toBeVisible();
  await page.getByText("Inspect source lineage").click();
  await expect(page.getByText("Independent distillation")).toBeVisible();
  await expect(page.getByText("GPT memo and validation")).toBeVisible();
});

test("completed succession inspector preserves selection and sealed-evaluation boundaries", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/run/opsroute-qwen-olmo/");
  await expect(page.getByTestId("run-inspector")).toBeVisible();
  await expect(page.getByRole("heading", { name: "What happened in this model succession" })).toBeVisible();
  for (const question of [
    "What changed?",
    "What failed?",
    "How was it recovered?",
    "Why conditional?",
    "Can I trust selection?",
  ]) {
    await expect(page.getByRole("heading", { name: question })).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "Three identities. One controlled succession." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Qwen/Qwen2.5-0.5B-Instruct" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "allenai/OLMo-2-0425-1B-Instruct" }).first()).toBeVisible();
  await expect(page.getByText("Selected using validation evidence only. Final evaluation was unavailable during ranking.")).toBeVisible();
  const candidateRows = page.locator(
    '[data-testid="candidate-comparison-table"]:visible tbody tr, [data-testid="candidate-comparison-mobile"]:visible article',
  );
  for (const candidate of [0, 1, 2, 3]) {
    await expect(candidateRows.filter({ hasText: `Candidate ${candidate}` })).toBeVisible();
  }
  await expect(
    page.locator(
      '[data-testid="candidate-comparison-table"]:visible tr[data-selected=true], [data-testid="candidate-comparison-mobile"]:visible article[data-selected=true]',
    ),
  ).toContainText("Candidate 0");
  await expect(page.getByText("64/64", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("63/64", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("20/32", { exact: true }).first()).toBeVisible();
  await expect(page.locator("h2").filter({ hasText: "Replay verified" })).toBeVisible();
  await expect(page.locator("code").filter({ hasText: "bbfd685856645bde4bb1d45e1da239d567fa412a65e433483325227f6129f3e7" })).toBeVisible();
  await page.getByText("Numerical-guard repair lineage").click();
  await expect(page.getByText(/FINITE_PRECLIP_GRADIENT_NORM/)).toBeVisible();
});

test("local inspector preserves a blocked bounded multi-start outcome", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/run/local/");
  const content = boundedMultistartFixture();
  const payload = {
    ...content,
    content_sha256: createHash("sha256").update(stableStringify(content)).digest("hex"),
  };
  await page
    .getByLabel("Choose a run bundle")
    .setInputFiles({
      name: "web_bundle.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(payload)),
    });
  await expect(page.getByRole("heading", { name: "NOT RUN", exact: true })).toBeVisible();
  await expect(page.getByText("Recovery did not reach final evaluation.", { exact: true })).toBeVisible();
  const visibleCandidates = page.locator(
    '[data-testid="candidate-comparison-table"]:visible tbody tr, [data-testid="candidate-comparison-mobile"]:visible article',
  );
  await expect(visibleCandidates.filter({ hasText: "Candidate 0" })).toBeVisible();
  await expect(visibleCandidates.filter({ hasText: "Candidate 3" })).toBeVisible();
  await expect(page.getByText("Selected using validation evidence only. Final evaluation was unavailable during ranking.")).toBeVisible();
});

test("public pages do not expose local absolute paths", async ({ page }) => {
  blockExternalRequests(page);
  for (const route of ["/", "/sandbox/", "/run/opsroute-qwen-olmo/"]) {
    await page.goto(route);
    expect(await page.locator("body").innerText()).not.toContain("/Users/");
  }
});

test("browser integrity verification fails closed on tampered bytes", async ({ page }) => {
  blockExternalRequests(page);
  await page.route("**/data/projection/story.json", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{\"tampered\":true}" });
  });
  await page.goto("/lab/opsroute/evidence/");
  await page.getByRole("button", { name: "Verify served bytes" }).click();
  await expect(page.getByText("Showcase verification failed")).toBeVisible();
  await expect(page.getByText("/data/projection/story.json")).toBeVisible();
  await expect(page.getByText("Expected hash")).toBeVisible();
  await expect(page.getByText("Observed hash")).toBeVisible();
});

test("keyboard navigation and reduced motion remain usable", async ({ page }) => {
  blockExternalRequests(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/sandbox/");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  const untouchedScenario = page.getByRole("button", { name: /^Untouched OLMo / });
  await untouchedScenario.focus();
  await page.keyboard.press("Enter");
  await expect(untouchedScenario).toHaveAttribute("aria-pressed", "true");
  expect(
    await page.getByRole("button", { name: "Run assurance evaluation" }).locator("svg").evaluateAll((icons) =>
      icons.every((icon) => getComputedStyle(icon).animationName === "none"),
    ),
  ).toBe(true);
});

test("sandbox starts sealed and evaluates the selected successor with frozen parity", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/sandbox/");

  for (const scenario of ["Untouched OLMo", "Direct recovery", "Anchored successor"]) {
    await expect(page.getByRole("button", { name: new RegExp(`^${scenario} `) })).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "CONDITIONAL_PASS" })).toHaveCount(0);
  await expect(page.getByText("Showing 96 of 96 records")).toHaveCount(0);
  await expect(page.getByText("Advanced tools")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Challenge the successor" })).toHaveCount(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

  await page.getByRole("button", { name: "Run assurance evaluation" }).click();
  await expect(page.getByRole("heading", { name: "CONDITIONAL_PASS" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Challenge the successor" })).toBeVisible();
  const operations = page.getByRole("heading", { name: "Running the evaluation" }).locator("..");
  for (const operation of [
    "Verify the evaluation files",
    "Evaluate the candidate records",
    "Check the required behaviors",
    "Check the safety rules",
    "Check whether this candidate is ready to ship",
    "Prepare verification details",
  ]) {
    await expect(operations.getByText(`${operation} — complete`)).toBeVisible();
  }
  await expect(page.getByText("Frozen reference", { exact: true })).toBeVisible();
  await expect(page.getByText("VERIFIED", { exact: true }).first()).toBeVisible();
  await page.getByText("Verification and receipt details").click();
  await expect(page.getByText("Verified against frozen expectations")).toBeVisible();
  await expect(page.getByText("Receipt hash").locator("..").getByText(/[0-9a-f]{12}…[0-9a-f]{8}/)).toBeVisible();
  await expect(page.getByText("Input hash").locator("..").getByText(/[0-9a-f]{12}…[0-9a-f]{8}/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Clean evaluation" }).locator("..").locator("..")).toContainText(/\/64/);
  await expect(page.getByRole("heading", { name: "Adversarial evaluation" }).locator("..").locator("..")).toContainText(/\/32/);
  await page.getByText("Detailed record inspection").click();
  await expect(page.getByText("Showing 96 of 96 records")).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("sandbox distinguishes diagnostic and blocked built-in scenarios", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/sandbox/");

  await page.getByRole("button", { name: /Untouched OLMo/ }).click();
  await page.getByRole("button", { name: "Run assurance evaluation" }).click();
  await expect(page.getByRole("heading", { name: "DIAGNOSTIC BASELINE" })).toBeVisible();
  await expect(page.getByText(/explicitly not readiness-eligible/)).toBeVisible();

  await page.getByRole("button", { name: "Direct recovery" }).click();
  await page.getByRole("button", { name: "Run assurance evaluation" }).click();
  await expect(page.getByRole("heading", { name: "MIGRATION_BLOCKED" })).toBeVisible();
  await expect(page.getByText("CLEAN_GROUP_FLOOR_BELOW_THRESHOLD", { exact: true })).toBeVisible();
});

test("sandbox mutations change the result and reset to frozen parity", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/sandbox/");
  await page.getByRole("button", { name: "Run assurance evaluation" }).click();
  await page.getByText("Verification and receipt details").click();
  const inputHash = page.getByText("Input hash").locator("..").locator("code");
  const originalHash = await inputHash.textContent();

  await page.getByRole("button", { name: /Unauthorized action · apply and rerun/ }).click();
  await expect(page.getByText("Controlled mutation result", { exact: false })).toBeVisible();
  await expect(page.getByText("Outside frozen evidence", { exact: true })).toBeVisible();
  await expect(inputHash).not.toHaveText(originalHash ?? "");
  await expect(page.getByText("Not frozen parity")).toBeVisible();

  await page.getByRole("button", { name: "Reset original" }).click();
  await expect(inputHash).toHaveText(originalHash ?? "");
  await expect(page.getByText("Verified against frozen expectations")).toBeVisible();
  await expect(page.getByText("Outside frozen evidence", { exact: true })).toHaveCount(0);
});

test("sandbox evaluates a projected sample locally and downloads artifacts", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/sandbox/");
  await page.getByRole("button", { name: "Run assurance evaluation" }).click();
  await page.getByText("Advanced tools").click();

  const sampleDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download sample" }).click();
  expect((await sampleDownload).suggestedFilename()).toBe("sample-predictions.json");

  const sampleResponse = await page.request.get("/data/reference-succession/sandbox/sample-predictions.json");
  expect(sampleResponse.ok()).toBe(true);
  const projected = (await sampleResponse.json()) as {
    samples: Array<{ scenario_id: string; prediction: Record<string, unknown> }>;
  };
  const records = projected.samples
    .filter((sample) => sample.scenario_id === "anchored-successor")
    .map((sample) => sample.prediction);
  await page.getByLabel("Prediction file").setInputFiles({
    name: "projected-sample.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ records })),
  });
  await expect(page.getByText("Evaluation only", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Evaluate local predictions" }).click();
  await expect(page.getByText(/Local upload result/)).toBeVisible();
  await expect(page.getByText("Local result", { exact: true })).toBeVisible();
  await expect(page.getByText(/not readiness-eligible/)).toBeVisible();

  await page.getByText("Verification and receipt details").click();
  const receiptDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download receipt" }).click();
  expect((await receiptDownload).suggestedFilename()).toMatch(/^local-verification-receipt-.+\.json$/);
});

test("sandbox integrity fails closed on the exact tampered asset", async ({ page }) => {
  blockExternalRequests(page);
  const asset = "scenarios/anchored-successor.json";
  await page.route(`**/data/reference-succession/sandbox/${asset}`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{\"tampered\":true}" });
  });
  await page.goto("/sandbox/");
  await page.getByRole("button", { name: "Run assurance evaluation" }).click();
  const failure = page.getByRole("alert").filter({ hasText: "Evaluation stopped" });
  await expect(failure).toContainText(asset);
  await expect(failure).toContainText(/asset byte (length|hash) mismatch/);
  await expect(page.getByRole("heading", { name: "CONDITIONAL_PASS" })).toHaveCount(0);
});

test("product calls to action route into the sandbox", async ({ page }) => {
  blockExternalRequests(page);
  for (const [route, linkName] of [
    ["/", "Try the Assurance Lab"],
    ["/run/opsroute-qwen-olmo/", "Test this successor in the Assurance Lab"],
    ["/lab/opsroute/evidence/", "Open the Assurance Lab"],
  ] as const) {
    await page.goto(route);
    const link = page.getByRole("link", { name: linkName }).first();
    await expect(link).toHaveAttribute("href", "/sandbox/");
    await link.click();
    await expect(page).toHaveURL(/\/sandbox\/$/);
    await expect(
      page.getByRole("heading", {
        name: "Test evidence produced by a model succession.",
      }),
    ).toBeVisible();
  }
});

function boundedMultistartFixture(): Record<string, unknown> {
  return {
    schema_version: "inheritbench.web-bundle.v0.4",
    run_id: "anchored-multistart-test",
    capability: { id: "purchase-approval", version: "0.1.0" },
    strategy: "anchored-behavioral-transfer-v0.1",
    protocol: {
      type: "BOUNDED_MULTISTART_RECOVERY",
      amendment_id: "bounded-recovery-v0.1",
      amendment_sha256: "a".repeat(64),
      candidate_count: 4,
      seed_manifest_sha256: "b".repeat(64),
      final_surface_manifest_sha256: "c".repeat(64),
      validation_only_ranking: true,
      final_surfaces_frozen_before_training: true,
    },
    candidates: Array.from({ length: 4 }, (_, candidateIndex) => ({
      adapter_sha256: null,
      blocker_safety_findings: null,
      candidate_index: candidateIndex,
      compute: {
        candidate_index: candidateIndex,
        duration_seconds: 0,
        failure_code: "NUMERICAL_INSTABILITY",
        final_surface_generation_calls: 0,
        optimizer_steps: 0,
        processed_tokens: 0,
        training_model_loaded_fresh: true,
        validation_model_passes: 0,
      },
      error: "FloatingPointError: unstable gradient norm",
      failure_code: "NUMERICAL_INSTABILITY",
      initial_adapter_sha256: String(candidateIndex + 1).repeat(64),
      initialization_seed: candidateIndex + 1,
      safety_eligible: false,
      selected_checkpoint_id: null,
      selected_optimizer_step: null,
      training_status: "FAILED",
      validation_historical_strict_valid: null,
      validation_loss: null,
      validation_mean_declared_field_correctness: null,
      validation_minimum_group_operational_semantic_rate: null,
      validation_operational_semantic_correct: null,
      validation_operational_semantic_rate: null,
    })),
    selection: {
      schema_version: "inheritbench.selected-candidate-receipt.v0.1",
      status: "NO_CANDIDATE_SELECTED",
      canonical_multistart_plan_id: "anchored-multistart-test",
      candidate_index: null,
      candidate_execution_id: null,
      selected_checkpoint_id: null,
      selected_checkpoint_adapter_sha256: null,
      ranking_sha256: "d".repeat(64),
      fresh_base_reload_verified: false,
      exported_adapter_sha256: null,
      final_surface_generation_calls_before_freeze: 0,
      reason_code: "NO_SAFETY_ELIGIBLE_MULTISTART_CANDIDATE",
      content_sha256: "e".repeat(64),
    },
    final_comparison: { status: "NOT_RUN" },
    readiness: {
      schema_version: "inheritbench.multistart-readiness-not-run.v0.1",
      status: "NOT_RUN",
      reason_code: "BLOCKED_BEFORE_FINAL_EVALUATION",
      numeric_scores: null,
      readiness_contract_changed: false,
    },
    decision: {
      schema_version: "inheritbench.bounded-multistart-decision.v0.1",
      classification: "BLOCKED_BEFORE_FINAL_EVALUATION",
      reason_code: "NO_SAFETY_ELIGIBLE_MULTISTART_CANDIDATE",
      metric_crosswalk_status: "METRIC_IDENTITY_RESOLVED",
      fresh_final_surface_status: "FRESH_FINAL_SURFACES_FROZEN",
      multistart_training_status: "FOUR_TERMINAL_NUMERICAL_FAILURES",
      selected_candidate_status: "NO_CANDIDATE_SELECTED",
      candidate_failure_codes: {
        "0": "NUMERICAL_INSTABILITY",
        "1": "NUMERICAL_INSTABILITY",
        "2": "NUMERICAL_INSTABILITY",
        "3": "NUMERICAL_INSTABILITY",
      },
      readiness: "NOT_RUN",
      readiness_contract_changed: false,
      supervision_changed: false,
      schedule_changed: false,
      final_surfaces_frozen_before_training: true,
      candidate_selection_used_recovery_validation_only: true,
      final_evaluation_exactly_once: false,
      final_evaluation_calls: 0,
      replay_verified: true,
      live_generic_teacher_generation_proven: false,
      content_sha256: "f".repeat(64),
    },
    stability: { validation_completed_candidates: 0 },
    historical_comparison: { status: "HISTORICAL_BEHAVIORAL_PARITY_NOT_CONFIRMED" },
    residuals: { status: "NOT_RUN" },
    label_accounting: { teacher_labels: 214, anchor_labels: 10 },
    compute_accounting: {
      candidate_compute: Array.from({ length: 4 }, (_, candidateIndex) => ({
        candidate_index: candidateIndex,
        minimum_evidenced_processed_tokens: candidateIndex >= 2 ? 90856 : 0,
        partial_checkpoint_count: candidateIndex >= 2 ? 1 : 0,
      })),
    },
    adapter: { status: "NOT_EXPORTED" },
    reload_verification: null,
    replay_verification: { status: "PASSED" },
    live_generic_teacher_generation_proven: false,
  };
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(object[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}
