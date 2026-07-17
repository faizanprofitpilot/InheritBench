// @vitest-environment node

import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  executeSuccessionReplay,
  validateSuccessionBundle,
} from "@/lib/succession-replay";

const root = path.resolve(
  process.cwd(),
  "../../artifacts/phase5/succession-replay/inheritbench-succession-v0.1",
);

async function bundle() {
  const manifest = JSON.parse(
    readFileSync(path.join(root, "succession_run_manifest.json"), "utf8"),
  ) as unknown;
  return validateSuccessionBundle(
    manifest,
    readFileSync(path.join(root, "replay_records.jsonl")),
    readFileSync(path.join(root, "context.json")),
  );
}

describe("shared succession replay", () => {
  it("derives the frozen Python golden result without a stored decision", async () => {
    const validated = await bundle();
    expect("decision" in validated.manifest).toBe(false);
    const result = await executeSuccessionReplay(validated);

    expect(result.summary.target_before_confirmatory).toMatchObject({
      record_count: 64,
      semantic_exact: 0,
      strict_valid: 0,
      unauthorized_actions: 4,
    });
    expect(result.summary.successor_confirmatory).toMatchObject({
      record_count: 64,
      semantic_exact: 55,
      strict_valid: 64,
      decision_correct: 64,
      tool_correct: 64,
      arguments_exact: 64,
      approval_correct: 64,
      reason_code_correct: 64,
      unauthorized_actions: 0,
      approval_bypasses: 0,
      false_actions: 0,
    });
    expect(result.summary.successor_adversarial).toMatchObject({
      record_count: 32,
      semantic_exact: 20,
      strict_valid: 30,
      unauthorized_actions: 1,
      approval_bypasses: 1,
    });
    expect(result.residuals.clean_policy_code_alias_count).toBe(9);
    expect(result.residuals.adversarial_profile_failures).toEqual({
      conflicting_id: 3,
      prior_offer: 1,
      prompt_injection: 8,
    });
    expect(result.readiness.decision).toBe("CONDITIONAL_PASS");
    expect(result.summary.content_sha256).toBe(
      "760e0ae4a7f24260de772137bb3fe7cf0cf45caf3a676705883afda5fe32f5c1",
    );
    expect(result.residuals.content_sha256).toBe(
      "78373963a813ef0020642bf110aa28fda6188497e269f96120f99334cf6778af",
    );
    expect(result.readiness.content_sha256).toBe(
      "80b44046532234525c1941b037e0346840e9770db9230b3d91e6be0ef324f550",
    );
    expect(result.receipt.content_sha256).toBe(
      "33e4f4beb1da6033175226338cab4f4c90b50406b78257d1de251e9fe302c418",
    );
  });

  it("fails closed when a compact record byte changes", async () => {
    const manifest = JSON.parse(
      readFileSync(path.join(root, "succession_run_manifest.json"), "utf8"),
    ) as unknown;
    const records = readFileSync(path.join(root, "replay_records.jsonl"));
    records[12] ^= 1;
    await expect(
      validateSuccessionBundle(
        manifest,
        records,
        readFileSync(path.join(root, "context.json")),
      ),
    ).rejects.toThrow("Compact replay-record verification failed");
  });
});
