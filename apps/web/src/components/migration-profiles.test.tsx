import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MigrationProfiles } from "@/components/migration-profiles";

describe("MigrationProfiles", () => {
  it("shows an explicit non-recommendation", () => {
    render(
      <MigrationProfiles
        profiles={[
          {
            profile_id: "original_labels_unavailable",
            eligible_systems: [],
            ranking: [],
            recommendation: "NO_VIABLE_TRAINED_MIGRATION",
            reason_code: "NO_ELIGIBLE_SYSTEM",
          },
        ]}
      />,
    );
    expect(screen.getByText("No viable trained migration")).toBeInTheDocument();
    expect(screen.getByText(/Pure synthetic transfer never produced a balanced trainable target/)).toBeInTheDocument();
    expect(screen.getByText(/Qwen remains a reference/)).toBeInTheDocument();
  });
});
