import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  SandboxExperience,
  type SandboxDependencies,
} from "@/components/sandbox/sandbox-experience";
import {
  UploadParseError,
  type MutationController,
  type MutationEffect,
  type Receipt,
  type SandboxAssets,
  type ScenarioExecution,
  type UploadParseResult,
} from "@/lib/sandbox";

const hash = "a".repeat(64);
const presentation = {
  sourceGateRecords: 1,
  finalRecords: 2,
  selectedCandidate: 0,
};

afterEach(cleanup);

function execution(
  scenarioId = "anchored-successor",
  options: { diagnostic?: boolean; inputHash?: string; parity?: boolean } = {},
): ScenarioExecution {
  const summary = {
    surface: "final_confirmatory_v0.3",
    expected: 1,
    terminal: 1,
    semantic_correct: 1,
    strict_valid: 1,
    vocabulary_conformant: 1,
    cross_field_conformant: 1,
    structural_exact: 1,
    mean_field_correctness: 1,
    blocker_safety_findings: 0,
    unknown_safety: 0,
    minimum_group_semantic_rate: 1,
    group_semantic: { routine: { correct: 1, total: 1, rate: 1 } },
    operational: {
      fields: ["decision"],
      correct: 1,
      rate: 1,
      minimum_group_rate: 1,
      groups: { routine: { correct: 1, total: 1, rate: 1 } },
    },
  };
  const record = {
    surface: summary.surface,
    generation: { record_id: "record-1", raw_output: '{"decision":"execute"}', status: "COMPLETED" as const },
    evaluation: {
      schema_version: "inheritbench.generic-evaluation.v0.2" as const,
      record_id: "record-1",
      raw_output: '{"decision":"execute"}',
      strict_candidate: '{"decision":"execute"}',
      normalized_candidate: '{"decision":"execute"}',
      parser_classification: "STRICT_VALID" as const,
      parse_valid: true,
      valid_json: true,
      schema_valid: true,
      vocabulary_conformant: true,
      cross_field_conformant: true,
      historical_strict_valid: true,
      strict_valid: true,
      structural_exact: true,
      semantic_match: true,
      field_correctness: { decision: true },
      mean_field_correctness: 1,
      parsed_output: { decision: "execute" },
      expected: { decision: "execute" },
      parser_findings: [],
      safety_findings: [],
      coverage: { group: "routine" },
      content_sha256: hash,
    },
  };
  const diagnostic = options.diagnostic ?? scenarioId === "untouched-target";
  return {
    scenario_id: scenarioId,
    input_sha256: options.inputHash ?? hash,
    integrity: {
      verified: true,
      manifest_hash: hash,
      verified_assets: ["evaluation-contract.json", "records/final.json"],
      failed_asset: null,
      expected_hash: null,
      actual_hash: null,
      error: null,
    },
    records: { source_gate: [record], target_baseline: [record], selected: [record] },
    summaries: {
      adapted_source: { ...summary, surface: "source_gate" },
      target_baseline: { ...summary, surface: "source_gate" },
      selected: diagnostic
        ? { source_gate: { ...summary, surface: "source_gate" } }
        : {
            "final_confirmatory_v0.3": summary,
            "final_adversarial_v0.3": { ...summary, surface: "final_adversarial_v0.3" },
          },
    },
    readiness: diagnostic
      ? null
      : {
          schema_version: "inheritbench.readiness-report.v0.2",
          run_id: "local-test",
          rule_version: "test",
          status: "CONDITIONAL_PASS",
          reason_codes: ["ADVERSARIAL_SEMANTIC_BELOW_THRESHOLD"],
          source_gate: { ...summary, surface: "source_gate" },
          target_baseline: { ...summary, surface: "source_gate" },
          confirmatory: summary,
          adversarial: { ...summary, surface: "final_adversarial_v0.3" },
          supervision: {},
          selected_checkpoint_id: "candidate",
          adapter_sha256: hash,
          content_sha256: hash,
        },
    readiness_eligible: !diagnostic,
    readiness_reason_code: diagnostic ? "DIAGNOSTIC_SCENARIO_NOT_READINESS_ELIGIBLE" : null,
    parity: { verified: options.parity ?? true, mismatches: [] },
    stages: ["INTEGRITY_VERIFIED", "SOURCE_GATE_EVALUATED", "SCENARIO_EVALUATED", "PARITY_VALIDATED", "COMPLETED"],
    timing: {
      started_at: "2026-01-01T00:00:00.000Z",
      completed_at: "2026-01-01T00:00:00.010Z",
      duration_ms: 10,
    },
  };
}

function assets(): SandboxAssets {
  const scenario = {
    schema_version: "inheritbench.sandbox-scenario.v0.1",
    scenario_id: "anchored-successor",
    display_name: "Anchored successor",
    record_definitions: "records/final.json",
    predictions: {
      "record-1": { record_id: "record-1", raw_output: '{"decision":"execute"}', status: "COMPLETED" as const },
    },
    surfaces: ["final_confirmatory_v0.3", "final_adversarial_v0.3"],
    source_run: "test",
  };
  return {
    manifest: {
      schema_version: "inheritbench.sandbox-manifest.v0.1",
      sandbox_id: "test",
      assets: [],
      scenarios: ["anchored-successor"],
      content_sha256: hash,
      expected_result_content_hashes: {},
    },
    evaluationContract: {} as SandboxAssets["evaluationContract"],
    readinessContract: {} as SandboxAssets["readinessContract"],
    parityExpectations: { schema_version: "test", scenarios: {} },
    recordSets: {
      "records/final.json": {
        schema_version: "test",
        record_set_id: "final",
        records: [{
          record_id: "record-1",
          surface: "final_confirmatory_v0.3",
          input: {},
          expected: { decision: "execute" },
          safety_context: {},
          coverage: { group: "routine" },
        }],
      },
    },
    scenarios: { "anchored-successor": scenario },
    rawAssets: {
      "sample-predictions.json": {
        samples: [{ prediction: scenario.predictions["record-1"] }],
      },
    },
    integrity: {
      verified: true,
      manifest_hash: hash,
      verified_assets: ["records/final.json"],
      failed_asset: null,
      expected_hash: null,
      actual_hash: null,
      error: null,
    },
  };
}

function receipt(result: ScenarioExecution): Receipt {
  return {
    schema_version: "inheritbench.local-verification-receipt.v0.1",
    created_at: "2026-01-01T00:00:00.011Z",
    scenario_id: result.scenario_id,
    input_sha256: result.input_sha256,
    integrity: result.integrity,
    readiness_status: result.readiness?.status ?? null,
    parity_verified: result.parity.verified,
    result_sha256: hash,
    receipt_sha256: hash,
  };
}

function dependencies() {
  const loaded = assets();
  let mutated = false;
  const effect: MutationEffect = {
    kind: "policy_code",
    record_id: "record-1",
    before: '{"decision":"execute"}',
    after: '{"decision":"refuse"}',
    changed_fields: ["/decision"],
    before_input_sha256: hash,
    after_input_sha256: "b".repeat(64),
  };
  const controller = {
    get scenario() {
      return loaded.scenarios["anchored-successor"];
    },
    apply: vi.fn(async () => {
      mutated = true;
      return effect;
    }),
    reset: vi.fn(async () => {
      mutated = false;
      return { scenario: loaded.scenarios["anchored-successor"], input_sha256: hash };
    }),
  } as unknown as MutationController;
  const execute = vi.fn(async (_assets: SandboxAssets, target: string | object) => {
    const id = typeof target === "string" ? target : "anchored-successor";
    return execution(id, { inputHash: mutated ? "b".repeat(64) : hash });
  });
  const executeUpload = vi.fn(async () => execution("local-upload", { parity: false }));
  const createReceipt = vi.fn(async (result: ScenarioExecution) => receipt(result));
  const download = vi.fn(() => new Blob());
  const parseUpload = vi.fn((_input: string | Uint8Array, options: { fileName?: string }) => {
    if (options.fileName === "bad.json") throw new UploadParseError("invalid JSON: unexpected token", "INVALID_JSON");
    return {
      records: { "record-1": loaded.scenarios["anchored-successor"].predictions["record-1"] },
      provenance: {
        kind: "local-upload",
        file_name: options.fileName,
        format: "json",
        bytes: 10,
        imported_at: "2026-01-01T00:00:00.000Z",
      },
      compatible_ids: ["record-1"],
      missing_ids: [],
      unknown_ids: [],
      evaluation_eligible: true,
      readiness_eligible: true,
    } satisfies UploadParseResult;
  });
  return {
    dependencies: {
      loadAssets: vi.fn(async () => ({ assets: loaded, integrity: loaded.integrity })),
      execute,
      executeUpload,
      createReceipt,
      createController: vi.fn(() => controller),
      parseUpload,
      download,
    } as unknown as SandboxDependencies,
    controller,
    download,
    executeUpload,
  };
}

describe("SandboxExperience", () => {
  it("hides metrics initially, then runs and renders verified results and receipt actions", async () => {
    const user = userEvent.setup();
    const fixture = dependencies();
    render(<SandboxExperience presentation={presentation} dependencies={fixture.dependencies} />);

    expect(screen.queryByRole("heading", { name: "CONDITIONAL_PASS" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Test evidence produced by a model succession." }),
    ).toBeInTheDocument();
    expect(screen.getByText(/This is not the model-migration engine/i)).toBeInTheDocument();
    expect(screen.getByText(/no model training or fresh inference happens here/i)).toBeInTheDocument();
    expect(screen.getByText("Results remain hidden until evaluation.")).toBeInTheDocument();
    expect(screen.getByText("Advanced tools")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Challenge the successor" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Run assurance evaluation" }));
    expect(await screen.findByRole("heading", { name: "CONDITIONAL_PASS" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Challenge the successor" })).toBeInTheDocument();
    expect(screen.getAllByText(/Verified against frozen expectations/).length).toBeGreaterThan(0);
    expect(screen.getByText("Detailed record inspection")).toBeInTheDocument();

    await user.click(screen.getByText("Verification and receipt details"));
    await user.click(screen.getByRole("button", { name: "Download receipt" }));
    await user.click(screen.getByText("Advanced tools"));
    await user.click(screen.getByRole("button", { name: "Download sample" }));
    expect(fixture.download).toHaveBeenCalledTimes(2);
  });

  it("shows explicit diagnostic wording for the untouched target", async () => {
    const user = userEvent.setup();
    const fixture = dependencies();
    render(<SandboxExperience presentation={presentation} dependencies={fixture.dependencies} />);

    await user.click(screen.getByRole("button", { name: /Untouched OLMo/i }));
    await user.click(screen.getByRole("button", { name: "Run assurance evaluation" }));

    expect(await screen.findByText(/explicitly not readiness-eligible/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "DIAGNOSTIC BASELINE" })).toBeInTheDocument();
  });

  it("re-evaluates a controlled mutation and reset restores the original result", async () => {
    const user = userEvent.setup();
    const fixture = dependencies();
    render(<SandboxExperience presentation={presentation} dependencies={fixture.dependencies} />);
    await user.click(screen.getByRole("button", { name: "Run assurance evaluation" }));

    await user.click(await screen.findByRole("button", { name: /Policy code · apply and rerun/ }));
    expect(await screen.findByText("Outside frozen evidence")).toBeInTheDocument();
    expect(screen.getByText("Readiness transition").nextElementSibling).toHaveTextContent("→");
    expect(fixture.controller.apply).toHaveBeenCalledWith("policy_code");

    await user.click(screen.getByRole("button", { name: /Reset original/i }));
    await waitFor(() => expect(fixture.controller.reset).toHaveBeenCalled());
    expect(screen.queryByText("Outside frozen evidence")).not.toBeInTheDocument();
    expect(screen.getAllByText(/Verified against frozen expectations/).length).toBeGreaterThan(0);
  });

  it("reports exact upload errors and evaluates a compatible local file", async () => {
    const user = userEvent.setup();
    const fixture = dependencies();
    const { container } = render(
      <SandboxExperience presentation={presentation} dependencies={fixture.dependencies} />,
    );
    await user.click(screen.getByText("Advanced tools"));
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, new File(["{"], "bad.json", { type: "application/json" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("[INVALID_JSON] invalid JSON: unexpected token");

    await user.upload(input, new File(["{}"], "good.json", { type: "application/json" }));
    expect((await screen.findAllByText("Readiness eligible")).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Evaluate local predictions" }));

    expect(await screen.findByText(/Local upload result/)).toBeInTheDocument();
    expect(fixture.executeUpload).toHaveBeenCalled();
  });
});
