# Product Architecture

InheritBench is a local CLI and pack-driven engine for controlled model succession. Developers define
the fine-tuned capability that must survive; the engine plans and executes recovery on an explicitly
supported replacement model, applies readiness, exports the adapter, and preserves replayable
evidence.

The completed Qwen → OLMo inspector proves that this workflow executed end to end. The Assurance Lab
is a supporting browser surface for testing evaluation and readiness against generated predictions;
it does not load, train, or run the models.

## Component Map

```text
Capability-pack layer
  └── developer-owned structured-JSON contract
      ├── model-visible inputs
      ├── evaluator-only expected contracts
      ├── schemas and controlled vocabularies
      ├── safety and readiness rules
      └── optional authorized anchors
                    ↓
Succession engine / local CLI
  └── validate → freeze plan → verify source → diagnose target
      → recover → select on validation → open final records
      → readiness → adapter export/reload → replay
                    ↓
Browser evidence surfaces
  ├── completed-run inspector: proof of CLI execution
  ├── Assurance Lab: lightweight evaluation/readiness testing
  └── local bundle inspector: browser-only inspection
```

## Capability-Pack Layer

The pack at `capabilities/opsroute/v0.2.0` uses profile `structured-json-v0.1`. Its layout includes
`capability.yaml`, input/output/cross-field schemas, `evaluator.yaml`, prompts, controlled
vocabularies, safety and readiness rules, model-visible data, evaluator-only oracles, frozen teacher
outputs, schedules, and authorized anchors.

`capability init` scaffolds a `DRAFT` pack. `capability validate` and `capability inspect` are
read-only authoring tools. Planning accepts only validated `READY` or `REFERENCE` packs;
`FIXTURE_ONLY` execution is hidden and test-only. The stage broker prevents final records and
oracles from entering supervision or selection.

## Succession Engine and CLI

Python owns pack validation, planning, model loading, source verification, target diagnosis,
supervision preparation, LoRA training, validation-only checkpoint selection, final evaluation,
readiness, adapter export/reload, and replay.

```bash
uv run inheritbench capability validate capabilities/opsroute/v0.2.0
uv run inheritbench succession plan \
  --pack capabilities/opsroute/v0.2.0 \
  --source-config configs/models/source.yaml \
  --target-config configs/models/target.yaml \
  --strategy anchored-behavioral-transfer-v0.1 \
  --output runs
uv run inheritbench succession run --plan runs/<run-id> --device mps
uv run inheritbench succession inspect --run runs/<run-id> --json -
uv run inheritbench succession replay --run runs/<run-id> --output runs/replays
uv run inheritbench succession export-web --run runs/<run-id> --output web_bundle.json
```

An anchored run may persist `ANCHORS_REQUIRED`. After `succession add-anchors`, `succession resume`
reuses completed teacher evidence and continues the same content-addressed plan.

Real model execution is intentionally narrow: pinned Qwen2.5-0.5B Instruct as source, pinned
OLMo-2-0425-1B-Instruct as target, explicit LoRA module maps, and Apple MPS as the demonstrated
training backend. A capability pack cannot authorize an unknown model architecture.

## Current Product Evidence

The current product projection at `artifacts/product/reference-succession-v0.1/` represents the
repaired bounded four-seed Qwen → OLMo execution. It includes the completed browser bundle, canonical
plan, validation-only ranking, selected-adapter identity, final comparison, replay verification, and
compact Assurance Lab assets.

The product readiness contract is `opsroute-readiness-product-v0.1`. Candidate 0 was selected before
the 64-record confirmatory and 32-record adversarial surfaces opened. Replay verifies 96 direct and
96 anchored predictions.

## Historical Phase 3B Replay

The separate frozen bundle at
`artifacts/phase5/succession-replay/inheritbench-succession-v0.1` contains a manifest, 160 compact
atomic records, and replay context for the historical public adapter. The base-only command
`inheritbench succession replay --output runs` derives its own report under
`succession-readiness-v0.1`. It does not reconstruct the later 192-prediction product projection.

## Truth Hierarchy

```text
developer capability pack + supported model configs
        ↓
content-addressed CLI plan and stage evidence
        ↓
trained adapter + readiness + replay
        ↓
deterministic product projection
        ↓
browser inspection and assurance testing
```

Generated reports are product outputs, not manually maintained scientific sources.

## Replay Engines

The historical Python and TypeScript replay implementations perform the same ordered operations:

1. validate the manifest;
2. enforce safe relative paths;
3. verify byte counts and SHA-256 hashes;
4. validate compact records;
5. aggregate atomic metrics by evaluation surface;
6. derive operational correctness;
7. classify policy-code-only clean residuals;
8. count adversarial failure profiles and safety events;
9. apply the historical `succession-readiness-v0.1` contract;
10. validate the verified adapter publication identity;
11. generate the report and receipt.

Cross-language golden tests require matching summary, residual, readiness, and receipt hashes. The
Assurance Lab has a separate Python/TypeScript parity contract for the current product scenarios and
applies `opsroute-readiness-product-v0.1`.

## Readiness Rules

The deterministic product rule returns:

- `MIGRATION_BLOCKED` when source or clean requirements fail;
- `PASS` when no observed clean or adversarial semantic, parser, or safety blocker remains;
- `CONDITIONAL_PASS` when clean gates pass but adversarial blockers remain.

GPT-5.6 does not set this status.

## GPT-5.6 Analyst

Phase 4 provides GPT-5.6 Sol with a content-addressed evidence graph, frozen profiles,
representative cases, and strict output schema. A deterministic validator rejects unsupported values,
comparisons, causal claims, references, or missing accounting. The validated memo is explanatory and
constraint-aware; metrics and safety gates remain deterministic.

## Static Web Build

The Next.js App Router application exports plain static assets. Build-time ingestion uses Node
`crypto` to validate and copy only:

- `artifacts/showcase/inheritbench-v0.1-gpt`;
- `artifacts/phase5/web-projection/inheritbench-web-v0.1`;
- `artifacts/phase5/succession-replay/inheritbench-succession-v0.1`;
- `artifacts/product/reference-succession-v0.1`.

The deployment build requires no Python, uv, model weights, Hugging Face, OpenAI, or historical
artifact discovery. Runtime requires only static site delivery.

Ingestion verifies committed hashes before copying files into the ignored
`apps/web/public/data/` directory.

## Interactive Assurance Lab

`/sandbox/` is not the succession engine. It runs browser-native assurance over committed or
user-selected predictions produced outside the browser:

```text
verified files
→ record evaluation
→ coverage aggregation
→ safety checks
→ readiness or diagnostic boundary
→ local result hash and receipt
```

The TypeScript implementation under `apps/web/src/lib/sandbox/` mirrors the deterministic Python
evaluation semantics used for the projected reference scenarios. Built-in scenarios cover the
untouched target, direct recovery, and validation-selected anchored successor. After the anchored
run, controlled in-memory mutations test whether the same rules detect an unsafe change.

Local JSON/JSONL uploads remain in browser memory. Complete compatible record sets may receive a
readiness decision; partial compatible sets receive record evaluation only. Receipts are unsigned
local content proofs, not identity or external attestations.

## Trust Boundaries

| Boundary | Allowed | Forbidden |
|---|---|---|
| Scientific execution | Frozen data, models, oracles, training, evaluator-owned labels | Post-test tuning, artifact overwrite, parser repair |
| Product projection | Read historical evidence and generate display-only committed data | Modify historical artifacts or introduce metrics |
| Static ingestion | Validate and copy committed web data | Discover scientific evidence or call external services |
| Assurance Lab | Evaluate committed or local predictions, mutate in memory, apply readiness, generate unsigned receipts | Claim fresh training, inference, signature, or external attestation |
| Browser replay | Verify compact records and derive a product decision | Claim fresh training, inference, or scientific parser replay |
| GPT analyst | Explain validated evidence | Determine benchmark values or safety eligibility |

## Pack-Driven Execution Detail

The primary developer workflow follows:

```text
capability pack
      ↓
strict generic loader + declarative evaluator
      ↓
exact model registry
      ↓
content-addressed plan
      ↓
stage-scoped data broker
      ↓
direct LoRA or anchored transfer
      ↓
validation-only checkpoint choice
      ↓
exactly-once confirmatory + adversarial evaluation
      ↓
derived readiness + adapter export
      ↓
model-free replay + local browser bundle
```

The generic implementation lives in:

- `inheritbench.capability`;
- `inheritbench.model_adapters`;
- `inheritbench.strategies`;
- `inheritbench.orchestration`.

An AST-based import-boundary test forbids these packages from importing OpsRoute, historical
evaluation contracts, Day 2, Day 3, matched Day 3, Phase 3B, Phase 4, or Phase 5. OpsRoute projection
is isolated in `inheritbench.reference_packs`, where historical types may be read but never changed.

The model registry permits only exact supported identities. It owns revision matching, native
tokenizer behavior, eager attention, sequence limits, dtype, and explicit LoRA module maps. A pack
cannot turn an unknown model into a supported architecture.

Mutable state is limited to `runs/.active/<run-id>`. Plans, stages, failures, interventions,
completed runs, checkpoints, adapters, and replays use atomic no-overwrite storage. Interrupted
training may resume only from a matching trainer-state checkpoint and immutable schedule.

## Local Browser Boundary

`/run/local/` accepts only a user-selected `web_bundle.json` of at most 5 MiB. Zod validates the
generic finalized or intervention schema, Web Crypto verifies the content hash, and React renders
stage history, readiness or `ANCHORS_REQUIRED`, residual evidence, accounting, and adapter lineage.

The file stays in browser memory. There is no upload, API route, persistence, model execution, or
external request. Raw outputs are escaped text. The existing published OpsRoute replay route remains
unchanged.

## Extension Seams

Future work may add tested model-registry entries, additional real capability packs, backend
decisions, and hosted execution. Those are explicit product extensions, not implied by the v0.2
pack abstraction. A new pack must still define schemas, vocabularies, safety rules, evidence
surfaces, readiness, model support, and reproducibility gates before real execution.
