import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunInspector } from "@/components/run-inspector";
import { loadReferenceSuccession } from "@/lib/data";

describe("RunInspector", () => {
  it("renders the completed succession from bundle evidence", () => {
    const { bundle, audit } = loadReferenceSuccession();
    render(<RunInspector bundle={bundle} audit={audit} />);

    expect(screen.getByRole("heading", { name: "CONDITIONAL PASS" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Three identities. One controlled succession." })).toBeInTheDocument();
    expect(screen.getByText("Targeted supervision required")).toBeInTheDocument();
    expect(screen.getByText("Selected using validation evidence only. Final evaluation was unavailable during ranking.")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Replay verified" }).length).toBeGreaterThan(0);

    const selected = document.querySelector("tr[data-selected=true]");
    expect(selected).not.toBeNull();
    expect(within(selected as HTMLElement).getByText("Candidate 0", { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText(/Candidate [0-3]/).length).toBeGreaterThanOrEqual(4);
  });

  it("keeps optional audit evidence non-fatal", () => {
    const { bundle } = loadReferenceSuccession();
    render(<RunInspector bundle={bundle} />);
    expect(screen.getAllByRole("heading", { name: "Replay verified" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Not included in this bundle/).length).toBeGreaterThan(0);
  });
});
