import { readFileSync } from "node:fs";
import path from "node:path";
import { z } from "zod";

import {
  caseDetailsSchema,
  evidenceSchema,
  matrixRowSchema,
  memoSchema,
  memoValidationSchema,
  migrationSchema,
  sourceIndexSchema,
  storySchema,
  systemSummarySchema,
} from "@/lib/data-schema";

const dataRoot = path.join(process.cwd(), "public/data");

function json(relativePath: string): unknown {
  return JSON.parse(readFileSync(path.join(dataRoot, relativePath), "utf8"));
}

function jsonl(relativePath: string): unknown[] {
  return readFileSync(path.join(dataRoot, relativePath), "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as unknown);
}

export function loadStory() {
  return storySchema.parse(json("projection/story.json"));
}

export function loadCases() {
  return caseDetailsSchema.parse(json("projection/case-details.json"));
}

export function loadSources() {
  return sourceIndexSchema.parse(json("projection/source-index.json"));
}

export function loadSystems() {
  return z.array(systemSummarySchema).length(6).parse(json("showcase/system-summaries.json"));
}

export function loadMemo() {
  return memoSchema.parse(json("showcase/memo.json"));
}

export function loadMemoValidation() {
  return memoValidationSchema.parse(json("showcase/memo-validation.json"));
}

export function loadMigrationProfiles() {
  return migrationSchema.parse(json("showcase/migration-profiles.json"));
}

export function loadEvidence() {
  return evidenceSchema.parse(json("showcase/evidence.json"));
}

export function loadProvenance() {
  return z.record(z.string(), z.unknown()).parse(json("showcase/provenance.json"));
}

export function loadProtocol() {
  return z.record(z.string(), z.unknown()).parse(json("showcase/protocol.json"));
}

export function loadPhase4Decision() {
  return z.record(z.string(), z.unknown()).parse(json("showcase/phase4-decision.json"));
}

export function loadArchetypeMatrix() {
  return z.array(matrixRowSchema).parse(jsonl("showcase/archetype-matrix.jsonl"));
}

export function loadFailureMatrix() {
  return z.array(matrixRowSchema).parse(jsonl("showcase/failure-matrix.jsonl"));
}
