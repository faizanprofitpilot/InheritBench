import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  loadArchetypeMatrix,
  loadCases,
  loadEvidence,
  loadMemo,
  loadMemoValidation,
  loadMigrationProfiles,
  loadSources,
  loadStory,
  loadSystems,
} from "@/lib/data";

describe("committed product data", () => {
  it("validates every normalized input used by the product", () => {
    expect(loadStory().facts.length).toBeGreaterThan(10);
    expect(loadCases().cases).toHaveLength(8);
    expect(loadSources().sources.length).toBeGreaterThan(10);
    expect(loadSystems()).toHaveLength(6);
    expect(loadMemo().memo_kind).toBe("GPT_5_6_SOL");
    expect(loadMemoValidation().status).toBe("PASSED");
    expect(loadMigrationProfiles().recommendations).toHaveLength(6);
    expect(loadEvidence().references.length).toBeGreaterThan(20);
    expect(loadArchetypeMatrix().length).toBeGreaterThan(80);
  });

  it("preserves six adversarial cases and two empty frozen slots", () => {
    const cases = loadCases();
    expect(cases.cases.filter((item) => item.status === "SELECTED")).toHaveLength(6);
    expect(cases.cases.filter((item) => item.status === "NO_ELIGIBLE_CASE")).toHaveLength(2);
    expect(
      cases.cases.filter((item) => item.status === "SELECTED").every((item) => item.evaluation_surface === "adversarial"),
    ).toBe(true);
  });

  it("rejects misleading anchored-label accounting", () => {
    const root = path.resolve(process.cwd(), "src");
    const files = collect(root);
    const phrase = ["ten", "labels", "total"].join(" ");
    for (const file of files) {
      expect(readFileSync(file, "utf8").toLowerCase()).not.toContain(phrase);
    }
  });
});

function collect(root: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) files.push(...collect(fullPath));
    else if (/\.(ts|tsx)$/.test(entry.name)) files.push(fullPath);
  }
  return files;
}
