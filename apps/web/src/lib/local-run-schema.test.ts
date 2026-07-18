import { describe, expect, it } from "vitest";

import { localRunBundleSchema } from "@/lib/local-run-schema";

describe("local run bundle schema", () => {
  it("is task-neutral and rejects historical literal-only payloads", () => {
    expect(localRunBundleSchema.options).toHaveLength(4);
    expect(() =>
      localRunBundleSchema.parse({
        schema_version: "succession-web-v0.1",
        case_id: "opsroute-qwen-olmo",
      }),
    ).toThrow();
  });

  it("accepts a generic seeded anchored reference bundle", () => {
    const summary = {
      surface: "confirmatory",
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
      group_semantic: { group: { correct: 1, total: 1, rate: 1 } },
    };
    const parsed = localRunBundleSchema.parse({
      schema_version: "inheritbench.web-bundle.v0.3",
      run_id: "execution-1",
      canonical_plan_id: "canonical-plan-1",
      execution_id: "execution-1",
      capability: { id: "purchase-approval", version: "0.1.0" },
      strategy: "anchored-behavioral-transfer-v0.1",
      protocol_amendment: { amendment_sha256: "1".repeat(64) },
      intervention: { selected_ids: ["anchor-1"] },
      reproduction: {
        direct_seeded: "SEEDED_PROTOCOL_REPRODUCIBILITY_CONFIRMED",
        anchored_recovery: "GENERIC_ANCHORED_RECOVERY_CONFIRMED",
      },
      readiness: {
        schema_version: "inheritbench.readiness-report.v0.2",
        run_id: "execution-1",
        rule_version: "readiness-v1",
        status: "CONDITIONAL_PASS",
        reason_codes: ["ADVERSARIAL_RESIDUALS"],
        source_gate: { ...summary, surface: "source_gate" },
        target_baseline: { ...summary, surface: "target_baseline" },
        confirmatory: summary,
        adversarial: { ...summary, surface: "adversarial" },
        supervision: {
          direct_labels: 0,
          anchor_labels: 1,
          teacher_labels: 1,
          upstream_original_labels: 2,
          candidate_inputs: 2,
          accepted_teacher_outputs: 1,
          rejected_teacher_outputs: 1,
          selected_training_records: 2,
        },
        selected_checkpoint_id: "checkpoint-1",
        adapter_sha256: "2".repeat(64),
        content_sha256: "3".repeat(64),
      },
      summaries: {
        source_gate: { ...summary, surface: "source_gate" },
        target_baseline: { ...summary, surface: "target_baseline" },
        confirmatory: summary,
        adversarial: { ...summary, surface: "adversarial" },
      },
      residuals: [],
      label_accounting: {
        direct_labels: 0,
        anchor_labels: 1,
        teacher_labels: 1,
        upstream_original_labels: 2,
        candidate_inputs: 2,
        accepted_teacher_outputs: 1,
        rejected_teacher_outputs: 1,
        selected_training_records: 2,
      },
      compute_accounting: { processed_tokens: 10 },
      adapter: {
        adapter_directory: "successor",
        adapter_sha256: "2".repeat(64),
        checkpoint_id: "checkpoint-1",
        model: { registry_id: "fake-target" },
      },
      reload_verification: { fresh_base_reload_verified: true },
      replay_verification: { status: "PASSED" },
      stages: ["PACK_VALIDATED", "COMPLETED"],
      content_sha256: "4".repeat(64),
    });
    expect(parsed.schema_version).toBe("inheritbench.web-bundle.v0.3");
  });

  it("accepts a generic anchor intervention bundle", () => {
    const parsed = localRunBundleSchema.parse({
      schema_version: "inheritbench.intervention-web-bundle.v0.2",
      run_id: "run-1",
      capability: { id: "purchase-approval", version: "0.1.0" },
      strategy: "anchored-behavioral-transfer-v0.1",
      state: "ANCHORS_REQUIRED",
      intervention: { deficits: [{ group: "manager_approval", deficit: 2 }] },
      stages: ["PACK_VALIDATED", "ANCHORS_REQUIRED"],
      content_sha256: "0".repeat(64),
    });
    expect(parsed.schema_version).toBe("inheritbench.intervention-web-bundle.v0.2");
  });

  it("accepts a blocked bounded multi-start bundle without numeric readiness", () => {
    const candidates = Array.from({ length: 4 }, (_, candidateIndex) => ({
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
    }));
    const parsed = localRunBundleSchema.parse({
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
      candidates,
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
      historical_comparison: {
        status: "HISTORICAL_BEHAVIORAL_PARITY_NOT_CONFIRMED",
      },
      residuals: { status: "NOT_RUN" },
      label_accounting: { teacher_labels: 214, anchor_labels: 10 },
      compute_accounting: { candidate_compute: [] },
      adapter: { status: "NOT_EXPORTED" },
      reload_verification: null,
      replay_verification: { status: "PASSED" },
      live_generic_teacher_generation_proven: false,
      content_sha256: "0".repeat(64),
    });
    expect(parsed.schema_version).toBe("inheritbench.web-bundle.v0.4");
    if (parsed.schema_version !== "inheritbench.web-bundle.v0.4") {
      throw new Error("expected bounded multi-start bundle");
    }
    expect(parsed.readiness.status).toBe("NOT_RUN");
  });
});
