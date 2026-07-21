import { readdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  MAX_UPLOAD_BYTES,
  UploadParseError,
  createMutationController,
  createVerificationReceipt,
  deriveReadiness,
  evaluateOutput,
  executeScenario,
  executeUploadedPredictions,
  loadSandboxAssets,
  parsePredictionUpload,
  readinessReportSchema,
  verifyReceiptHash,
  type SandboxAssets,
  type SandboxFetch,
} from "@/lib/sandbox";

const assetRoot = resolve(process.cwd(), "public/data/reference-succession/sandbox");

function fileFetch(tamper?: string): SandboxFetch {
  return async (input) => {
    const url = String(input);
    const marker = "/sandbox/";
    const relative = url.includes(marker) ? url.slice(url.indexOf(marker) + marker.length) : url.split("/").at(-1)!;
    try {
      let bytes = new Uint8Array(await readFile(resolve(assetRoot, relative)));
      if (relative === tamper) {
        bytes = Uint8Array.from(bytes);
        bytes[0] ^= 1;
      }
      return new Response(bytes, { status: 200 });
    } catch {
      return new Response("", { status: 404 });
    }
  };
}

async function assets(): Promise<SandboxAssets> {
  const loaded = await loadSandboxAssets("/data/reference-succession/sandbox", {
    fetch: fileFetch(),
  });
  expect(loaded.integrity.verified).toBe(true);
  if (!loaded.assets) throw new Error(loaded.integrity.error ?? "assets unavailable");
  return loaded.assets;
}

describe("sandbox integrity", () => {
  it("verifies every projected asset", async () => {
    const loaded = await loadSandboxAssets("/data/reference-succession/sandbox", {
      fetch: fileFetch(),
    });
    expect(loaded.assets).not.toBeNull();
    expect(loaded.integrity).toMatchObject({
      verified: true,
      failed_asset: null,
    });
    expect(loaded.integrity.verified_assets).toHaveLength(loaded.assets!.manifest.assets.length);
  });

  it("reports the exact tampered asset and refuses verified status", async () => {
    const failedAsset = "evaluation-contract.json";
    const loaded = await loadSandboxAssets("/data/reference-succession/sandbox", {
      fetch: fileFetch(failedAsset),
    });
    expect(loaded.assets).toBeNull();
    expect(loaded.integrity).toMatchObject({
      verified: false,
      failed_asset: failedAsset,
      error: "asset byte hash mismatch",
    });
    expect(loaded.integrity.actual_hash).not.toBe(loaded.integrity.expected_hash);
  });
});

describe("projected parity", () => {
  it("matches adapted source and keeps untouched target diagnostic-only", async () => {
    const loaded = await assets();
    const result = await executeScenario(loaded, "untouched-target");
    expect(result.parity).toEqual({ verified: true, mismatches: [] });
    expect(result.readiness).toBeNull();
    expect(result.readiness_eligible).toBe(false);
    expect(result.summaries.adapted_source).toMatchObject(
      loaded.parityExpectations.scenarios["adapted-source"].summary as Record<string, unknown>,
    );
  });

  it("matches direct recovery summary and blocked readiness exactly", async () => {
    const loaded = await assets();
    const expected = loaded.parityExpectations.scenarios["direct-recovery"];
    const result = await executeScenario(loaded, "direct-recovery");
    expect(result.parity).toEqual({ verified: true, mismatches: [] });
    expect(result.readiness).toEqual(expected.readiness);
    expect(result.readiness?.status).toBe("MIGRATION_BLOCKED");
  });

  it("matches anchored successor summary and conditional readiness exactly", async () => {
    const loaded = await assets();
    const expected = loaded.parityExpectations.scenarios["anchored-successor"];
    const result = await executeScenario(loaded, "anchored-successor");
    expect(result.parity).toEqual({ verified: true, mismatches: [] });
    expect(result.readiness).toEqual(expected.readiness);
    expect(result.readiness?.status).toBe("CONDITIONAL_PASS");
  });
});

describe("readiness precedence", () => {
  it("reports source blockers before clean and adversarial blockers", async () => {
    const loaded = await assets();
    const expected = readinessReportSchema.parse(
      loaded.parityExpectations.scenarios["anchored-successor"].readiness,
    );
    const base = expected.source_gate;
    const incomplete = { ...base, terminal: base.expected - 1 };
    const readiness = await deriveReadiness({
      rules: loaded.readinessContract,
      sourceGate: incomplete,
      targetBaseline: expected.target_baseline,
      confirmatory: { ...expected.confirmatory, terminal: 0 },
      adversarial: expected.adversarial,
      metadata: {
        run_id: String(expected.run_id),
        supervision: expected.supervision,
        selected_checkpoint_id: expected.selected_checkpoint_id,
        adapter_sha256: expected.adapter_sha256,
      },
    });
    expect(readiness.status).toBe("MIGRATION_BLOCKED");
    expect(readiness.reason_codes).toEqual(["SOURCE_GATE_INCOMPLETE_EVIDENCE"]);
  });
});

describe("controlled mutations", () => {
  it("changes real raw outputs, exposes evaluator effects, and resets the input hash", async () => {
    const loaded = await assets();
    const scenario = loaded.scenarios["direct-recovery"];
    const records = loaded.recordSets[scenario.record_definitions];
    const original = createMutationController(scenario, records, loaded.evaluationContract);
    const originalHash = await original.inputHash();

    const safetyController = createMutationController(scenario, records, loaded.evaluationContract);
    const safetyEffect = await safetyController.apply("unauthorized_action");
    const safetyRun = await executeScenario(loaded, safetyController.scenario);
    expect(safetyEffect.after).not.toBe(safetyEffect.before);
    expect(safetyEffect.after_input_sha256).not.toBe(safetyEffect.before_input_sha256);
    expect(
      safetyRun.records.selected
        .flatMap((record) => record.evaluation.safety_findings)
        .some((finding) => finding.code === "UNAUTHORIZED_ACTION"),
    ).toBe(true);

    for (const kind of [
      "approval_bypass",
      "policy_code",
      "reason_code",
      "required_argument_corruption",
      "malformed_contract",
    ] as const) {
      const controller = createMutationController(scenario, records, loaded.evaluationContract);
      const effect = await controller.apply(kind);
      expect(effect.after).not.toBe(effect.before);
      expect(effect.changed_fields.length).toBeGreaterThan(0);
      const prediction = controller.scenario.predictions[effect.record_id];
      const record = records.records.find((item) => item.record_id === effect.record_id)!;
      const evaluation = await evaluateOutput({
        record,
        prediction,
        contract: loaded.evaluationContract,
      });
      if (kind === "approval_bypass") {
        expect(evaluation.safety_findings.map((finding) => finding.code)).toContain("APPROVAL_BYPASS");
      } else if (kind === "policy_code") {
        expect(evaluation.field_correctness.policy_code).toBe(false);
      } else if (kind === "reason_code") {
        expect(evaluation.field_correctness.reason_code).toBe(false);
      } else if (kind === "required_argument_corruption") {
        expect(evaluation.structural_exact).toBe(false);
      } else {
        expect(evaluation.parse_valid).toBe(false);
      }
      const reset = await controller.reset();
      expect(reset.input_sha256).toBe(originalHash);
    }
  });
});

describe("prediction uploads", () => {
  it("parses JSON and JSONL with local provenance and readiness eligibility", () => {
    const rows = [
      { record_id: "a", raw_output: "{}", status: "COMPLETED" },
      { record_id: "b", raw_output: "{}", status: "FAILED" },
    ];
    const json = parsePredictionUpload(JSON.stringify({ records: rows, metadata: { label: "local" } }), {
      compatibleIds: ["a", "b"],
      completeFinalIds: ["a", "b"],
      fileName: "predictions.json",
    });
    const jsonl = parsePredictionUpload(rows.map((row) => JSON.stringify(row)).join("\n"), {
      format: "jsonl",
      compatibleIds: ["a", "b", "c"],
      completeFinalIds: ["a", "b", "c"],
    });
    expect(json).toMatchObject({
      evaluation_eligible: true,
      readiness_eligible: true,
      metadata: { label: "local" },
      provenance: { kind: "local-upload", format: "json" },
    });
    expect(jsonl).toMatchObject({
      evaluation_eligible: true,
      readiness_eligible: false,
      missing_ids: ["c"],
    });
  });

  it("rejects duplicate, missing, malformed, and oversized inputs", () => {
    const duplicate = [
      { record_id: "same", raw_output: "{}", status: "COMPLETED" },
      { record_id: "same", raw_output: "{}", status: "COMPLETED" },
    ];
    expect(() => parsePredictionUpload(JSON.stringify(duplicate))).toThrowError(
      expect.objectContaining<Partial<UploadParseError>>({ code: "DUPLICATE_ID" }),
    );
    expect(() => parsePredictionUpload(JSON.stringify([{ raw_output: "{}" }]))).toThrowError(
      expect.objectContaining<Partial<UploadParseError>>({ code: "MISSING_ID" }),
    );
    expect(() => parsePredictionUpload("{")).toThrowError(
      expect.objectContaining<Partial<UploadParseError>>({ code: "INVALID_JSON" }),
    );
    expect(() => parsePredictionUpload(new Uint8Array(MAX_UPLOAD_BYTES + 1))).toThrowError(
      expect.objectContaining<Partial<UploadParseError>>({ code: "FILE_TOO_LARGE" }),
    );
  });

  it("evaluates a partial projected sample without readiness or frozen parity", async () => {
    const loaded = await assets();
    const finalRecords = loaded.recordSets["records/final.json"];
    const finalIds = finalRecords.records.map((record) => record.record_id);
    const rawSamples = loaded.rawAssets?.["sample-predictions.json"] as {
      samples: Array<{ prediction: { record_id: string; raw_output: string; status: "COMPLETED" | "FAILED" } }>;
    };
    const sample = rawSamples.samples.find(({ prediction }) => finalIds.includes(prediction.record_id));
    if (!sample) throw new Error("projected sample lacks a compatible final prediction");
    const unknown = { record_id: "unknown-local-id", raw_output: "{}", status: "COMPLETED" as const };
    const upload = parsePredictionUpload(JSON.stringify([sample.prediction, unknown]), {
      compatibleIds: finalIds,
      completeFinalIds: finalIds,
      fileName: "sample-predictions.json",
    });
    const execution = await executeUploadedPredictions(loaded, upload);

    expect(upload.unknown_ids).toEqual([unknown.record_id]);
    expect(execution.records.selected).toHaveLength(1);
    expect(Object.keys(execution.summaries.selected)).toEqual([
      execution.records.selected[0].surface,
    ]);
    expect(execution.readiness).toBeNull();
    expect(execution.readiness_eligible).toBe(false);
    expect(execution.readiness_reason_code).toBe("INCOMPATIBLE_FINAL_SURFACE_EVIDENCE");
    expect(execution.parity).toEqual({
      verified: false,
      mismatches: ["$.upload.provenance:local-input-not-frozen-parity"],
    });
  });

  it("derives readiness for a complete built-in final prediction set", async () => {
    const loaded = await assets();
    const finalRecords = loaded.recordSets["records/final.json"];
    const finalIds = finalRecords.records.map((record) => record.record_id);
    const scenario = loaded.scenarios["direct-recovery"];
    const upload = parsePredictionUpload(JSON.stringify(Object.values(scenario.predictions)), {
      compatibleIds: finalIds,
      completeFinalIds: finalIds,
      fileName: "complete-final.json",
    });
    const execution = await executeUploadedPredictions(loaded, upload, {
      scenarioId: "uploaded-complete-final",
    });
    const receipt = await createVerificationReceipt(execution);

    expect(execution.records.selected).toHaveLength(finalIds.length);
    expect(execution.readiness_eligible).toBe(true);
    expect(execution.readiness).not.toBeNull();
    expect(execution.readiness_reason_code).toBeNull();
    expect(execution.parity.verified).toBe(false);
    expect(execution.stages).toContain("READINESS_DERIVED");
    expect(await verifyReceiptHash(receipt)).toBe(true);
  });
});

describe("verification receipts", () => {
  it("creates a stable canonical receipt hash", async () => {
    const loaded = await assets();
    const execution = await executeScenario(loaded, "untouched-target");
    const now = () => new Date("2026-01-01T00:00:00.000Z");
    const first = await createVerificationReceipt(execution, { now });
    const second = await createVerificationReceipt(execution, { now });
    expect(first).toEqual(second);
    expect(await verifyReceiptHash(first)).toBe(true);
    expect(await verifyReceiptHash({ ...first, scenario_id: "changed" })).toBe(false);
  });
});

describe("shared source guard", () => {
  it("contains no product or model literals", async () => {
    const sourceDir = resolve(process.cwd(), "src/lib/sandbox");
    const files = (await readdir(sourceDir)).filter((file) => file.endsWith(".ts"));
    const terms = ["Ops" + "Route", "ops" + "route", "re" + "fund", "sub" + "scription", "Q" + "wen", "OL" + "Mo"];
    for (const file of files) {
      const source = await readFile(resolve(sourceDir, file), "utf8");
      for (const term of terms) expect(source, `${file} contains ${term}`).not.toContain(term);
    }
  });
});
