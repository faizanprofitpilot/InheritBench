import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricChart } from "@/components/metric-chart";
import type { SystemSummary } from "@/lib/data-schema";

const system = {
  system_id: "target_hybrid_anchored_distillation_10",
  comparison_role: "TARGET_MIGRATION_CANDIDATE",
  confirmatory_semantic: 0.859375,
  confirmatory_strict: 1,
  confirmatory_unauthorized_actions: 0,
  confirmatory_approval_bypasses: 0,
  adversarial_semantic: 0.625,
  adversarial_strict: 0.9375,
  adversarial_argument_f1: 0.6875,
  adversarial_safety_failures: 0,
  direct_original_labels: 10,
  upstream_original_labels: 224,
  complexity: "TEACHER_HYBRID_LORA",
  source_teacher_required: true,
  viable: true,
  viability_reasons: [],
  pareto_dominated: false,
  dominated_by: [],
} satisfies SystemSummary;

describe("MetricChart", () => {
  it("renders readable horizontal values and an accessible precision table", () => {
    const { container } = render(<MetricChart systems={[system]} surface="confirmatory" />);
    expect(screen.getAllByText("OLMo anchored transfer").length).toBeGreaterThan(0);
    expect(screen.getAllByText("85.9%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("100.0%").length).toBeGreaterThan(0);
    expect(screen.getByText("Accessible confirmatory metric table")).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeInTheDocument();
  });
});
