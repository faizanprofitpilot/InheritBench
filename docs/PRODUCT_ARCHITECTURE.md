# Product Architecture

InheritBench is a model-succession system with three responsibilities: define the capability that
must survive, rebuild it on a replacement model, and determine whether the recovered successor is
ready to migrate. The Qwen → OLMo implementation performs that full workflow through the scientific
layer and delivers a trained adapter plus a migration decision.

The static product exposes the assurance layer for judge testing. It does real integrity and
readiness work without pretending to train or run a model in the browser.

## Component Map

```text
Capability layer
  └── OpsRoute capability pack
      ├── capability.yaml
      ├── policy_registry.json
      └── safety_rules.yaml
            ↓
Succession layer
  └── pinned model and method configs
            ↓
Preregistered phased scientific workflow
            ↓
Raw predictions + deterministic parser/metrics
            ↓
Immutable artifacts + selected adapter + publication verification
            ↓
Assurance layer
            ↓
Phase 4 evidence graph + validated GPT-5.6 memo
            ↓
Compact succession replay bundle
            ↓
Python replay engine ↔ TypeScript replay engine
            ↓
CLI run bundle       Static web cockpit
```

## Scientific Layer

Python owns dataset generation, policies, model loading, training, checkpoint selection, evaluation,
artifact finalization, replay, and the Phase 5 display projection. Historical scientific artifacts
are immutable inputs to the product layer.

This is the execution path that transferred OpsRoute from adapted Qwen to a fresh OLMo base. It is
implemented as a preregistered phased workflow rather than a generalized one-command orchestrator.

The executed workflow uses:

- exact model revisions;
- native prompt `0.1.0`;
- parser `0.1.0`;
- evaluator `v0`;
- canonical JSON and JSONL;
- byte and content hashes;
- atomic no-overwrite storage;
- Git-tree preregistration before real training and evaluation.

## Capability Pack

`capabilities/opsroute/v0.1.0` declares the supported model pair, versions, scenario families,
execution modes, policy registry, safety rules, adapter identity, and product limitations. The pack is
strictly validated but does not make arbitrary capabilities plug-and-play. See
[Capability Packs](CAPABILITY_PACKS.md).

## Succession Replay Bundle

The committed bundle at `artifacts/phase5/succession-replay/inheritbench-succession-v0.1` contains:

- `succession_run_manifest.json` — identity, configuration, schemas, hashes, operations, readiness
  version, source references, and adapter publication identity;
- `replay_records.jsonl` — 160 compact atomic records covering untouched-target clean evidence,
  recovered-successor clean evidence, and recovered-successor adversarial evidence;
- `context.json` — label accounting, compute accounting, profile identity, and validated memo lineage.

The manifest does not store `CONDITIONAL_PASS`. Both replay engines derive it.

## Truth Hierarchy

```text
succession_run_manifest.json
        ↓
immutable referenced scientific artifacts
        ↓
compact deterministic replay records
        ↓
shared deterministic replay specification
        ↓
fresh readiness report + replay receipt
```

Generated reports are product outputs, not manually maintained scientific sources.

## Replay Engines

The Python and TypeScript implementations perform the same ordered operations:

1. validate the manifest;
2. enforce safe relative paths;
3. verify byte counts and SHA-256 hashes;
4. validate compact records;
5. aggregate atomic metrics by evaluation surface;
6. derive operational correctness;
7. classify policy-code-only clean residuals;
8. count adversarial failure profiles and safety events;
9. apply `succession-readiness-v0.1`;
10. validate the verified adapter publication identity;
11. generate the report and receipt.

Cross-language golden tests require matching summary, residual, readiness, and receipt hashes.

## Readiness Rules

The deterministic rule returns:

- `BLOCK` when integrity, adapter verification, clean strict validity, or clean safety gates fail;
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
- `artifacts/phase5/succession-replay/inheritbench-succession-v0.1`.

The deployment build requires no Python, uv, model weights, Hugging Face, OpenAI, or historical
artifact discovery. Runtime requires only static site delivery.

## Trust Boundaries

| Boundary | Allowed | Forbidden |
|---|---|---|
| Scientific execution | Frozen data, models, oracles, training, evaluator-owned labels | Post-test tuning, artifact overwrite, parser repair |
| Product projection | Read historical evidence and generate display-only committed data | Modify historical artifacts or introduce metrics |
| Static ingestion | Validate and copy committed web data | Discover scientific evidence or call external services |
| Browser replay | Verify compact records and derive a product decision | Claim fresh training, inference, or scientific parser replay |
| GPT analyst | Explain validated evidence | Determine benchmark values or safety eligibility |

## Pack-Driven Local Engine

v0.2 adds a second, isolated execution path for developer-owned packs:

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
