import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { createHash } from "node:crypto";

const routes = [
  "/",
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

test("header highlights only the current lab section", async ({ page }) => {
  blockExternalRequests(page);
  const sections = [
    ["/lab/opsroute/", "Succession Case"],
    ["/lab/opsroute/methods/", "Recovery Paths"],
    ["/lab/opsroute/failures/", "Failure Explorer"],
    ["/lab/opsroute/memo/", "Recommendation"],
    ["/lab/opsroute/evidence/", "Evidence"],
    ["/run/opsroute-qwen-olmo/", "Run Replay"],
  ] as const;

  for (const [route, label] of sections) {
    await page.goto(route);
    const currentLinks = page.locator('header a[aria-current="page"]');
    await expect(currentLinks).toHaveCount(2);
    await expect(currentLinks.first()).toHaveText(label);
    await expect(currentLinks.last()).toHaveText(label);
  }
});

test("landing page presents the product workflow and frozen published case", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/");

  await expect(page.getByText("MODEL SUCCESSION LAB", { exact: true })).toBeVisible();
  await expect(page.getByText("PUBLISHED QWEN → OLMO CASE", { exact: true })).toBeVisible();
  await expect(page.getByText("VALIDATED GPT-5.6 ANALYSIS", { exact: true })).toBeVisible();
  const proofBadgeLayout = await page.getByTestId("hero-proof-badges").evaluate((row) => {
    const bounds = row.getBoundingClientRect();
    const badges = [...row.children].map((badge) => badge.getBoundingClientRect());
    return {
      row: { left: bounds.left, right: bounds.right },
      badges: badges.map((badge) => ({ left: badge.left, right: badge.right, top: badge.top })),
    };
  });
  expect(new Set(proofBadgeLayout.badges.map((badge) => Math.round(badge.top))).size).toBe(1);
  expect(proofBadgeLayout.badges[0].right).toBeLessThan(proofBadgeLayout.badges[1].left);
  expect(proofBadgeLayout.badges[1].right).toBeLessThan(proofBadgeLayout.badges[2].left);
  expect(proofBadgeLayout.badges[0].left).toBeGreaterThanOrEqual(proofBadgeLayout.row.left);
  expect(proofBadgeLayout.badges[2].right).toBeLessThanOrEqual(proofBadgeLayout.row.right);
  await expect(page.getByRole("heading", { name: "Your successor model does not inherit capability by default." })).toBeVisible();
  await expect(page.getByText(/evaluate a model-family replacement before production/)).toBeVisible();

  await expect(page.getByRole("link", { name: /Run verified succession replay/ })).toHaveAttribute(
    "href",
    "/run/opsroute-qwen-olmo/",
  );
  await expect(page.getByRole("link", { name: /Explore the published case/ })).toHaveAttribute(
    "href",
    "/lab/opsroute/",
  );

  for (const label of ["Run Replay", "Succession Case", "Recovery Paths", "Failure Explorer", "Recommendation", "Evidence"]) {
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
    "59 / 768 accepted",
    "5 / 16",
    "719 / 768 accepted",
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
  await expect(page.getByText("21 files checked · 21 hashes matched")).toBeVisible();
  await expect(page.getByText(/This verifies the deployed display bundle/)).toBeVisible();
  await page.getByText("Inspect source lineage").click();
  await expect(page.getByText("Independent distillation")).toBeVisible();
  await expect(page.getByText("GPT memo and validation")).toBeVisible();
});

test("verified succession replay derives and downloads a conditional outcome", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/run/opsroute-qwen-olmo/");
  await expect(page.getByTestId("succession-configuration")).toBeVisible();
  await expect(page.getByText("214 teacher outputs + 10 direct anchors")).toBeVisible();
  await page.getByRole("button", { name: "Review replay preflight" }).click();
  await expect(page.getByTestId("succession-preflight")).toBeVisible();
  await expect(page.getByText("No training, inference, GPU, model download, or API key is required.")).toBeVisible();
  await page.getByRole("button", { name: "Run verified succession replay" }).click();
  await expect(page.getByRole("heading", { name: "Verified succession replay completed" })).toBeVisible();
  await expect(page.getByText("55 / 64 — 85.9375%")).toBeVisible();
  await expect(page.getByText("20 / 32 — 62.5%")).toBeVisible();
  await expect(page.getByText("Recovered successor adapter verified")).toBeVisible();
  await expect(page.getByText("Conditional pass", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download JSON" })).toHaveCount(2);
  expect(await page.evaluate(() => document.body.innerText.toLowerCase().includes("succession completed\n"))).toBe(false);
});

test("direct result links rerun verification before rendering", async ({ page }) => {
  blockExternalRequests(page);
  await page.goto("/run/opsroute-qwen-olmo/?stage=result");
  await expect(page.getByRole("heading", { name: "Verified succession replay completed" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Verified succession replay completed" })).toBeVisible();
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
    .getByLabel("Choose a finalized run bundle")
    .setInputFiles({
      name: "web_bundle.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(payload)),
    });
  await expect(page.getByRole("heading", { name: "Final evaluation remained sealed" })).toBeVisible();
  await expect(page.getByText("BLOCKED BEFORE FINAL EVALUATION", { exact: true })).toBeVisible();
  await expect(page.getByText("Candidate 0", { exact: true })).toBeVisible();
  await expect(page.getByText("Candidate 3", { exact: true })).toBeVisible();
  await expect(page.getByText("None", { exact: true })).toBeVisible();
  await expect(page.getByText("No confirmatory or adversarial evidence influenced candidate ranking.")).toBeVisible();
});

test("succession replay fails closed on tampered compact records", async ({ page }) => {
  blockExternalRequests(page);
  await page.route("**/data/succession/replay_records.jsonl", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{\"tampered\":true}\n" });
  });
  await page.goto("/run/opsroute-qwen-olmo/?stage=result");
  await expect(page.getByRole("heading", { name: "Frozen evidence could not be verified." })).toBeVisible();
  await expect(page.getByText(/Compact replay-record verification failed|Served succession artifact verification failed/)).toBeVisible();
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
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
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
