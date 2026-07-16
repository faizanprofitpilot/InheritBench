import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { FailureMatrixExplorer } from "@/components/failure-matrix-explorer";
import type { MatrixRow } from "@/lib/data-schema";

function row(systemId: string, group: string, semantic: number, strict: number, safety = 0): MatrixRow {
  return {
    system_id: systemId,
    group_key: `family_archetype:refund_policy_routing:${group}`,
    prediction_count: 2,
    semantic_exact: { denominator: 2, numerator: semantic * 2, rate: semantic },
    strict_valid: { denominator: 2, numerator: strict * 2, rate: strict },
    argument_f1: { denominator: 2, numerator: semantic * 2, rate: semantic },
    safety_known: 2,
    safety_unknown: 0,
    false_actions: safety,
    unauthorized_actions: 0,
    approval_bypasses: 0,
    primary_failures: {},
  };
}

const rows = [
  row("target_full_retrain", "fraud_review", 1, 1),
  row("target_hybrid_anchored_distillation_10", "fraud_review", 0.5, 1),
  row("target_full_retrain", "duplicate_auto_refund", 0, 1),
  row("target_hybrid_anchored_distillation_10", "duplicate_auto_refund", 0, 0.5, 1),
];

describe("FailureMatrixExplorer", () => {
  it("keeps the full matrix disclosed behind filters with live row counts", async () => {
    const user = userEvent.setup();
    render(<FailureMatrixExplorer rows={rows} />);
    expect(screen.getByText("View all archetype results")).toBeInTheDocument();
    await user.click(screen.getByText("View all archetype results"));
    expect(screen.getByText("Showing 4 of 4 rows")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Method"), "target_full_retrain");
    expect(screen.getByText("Showing 2 of 4 rows")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Semantic mismatch" }));
    expect(screen.getByText("Showing 1 of 4 rows")).toBeInTheDocument();
  });
});
