# Product Architecture

InheritBench separates scientific execution from judge-facing verified replay. The static product
does real integrity and readiness work without pretending to train or run a model in the browser.

## Component Map

```text
OpsRoute capability pack
  ├── capability.yaml
  ├── policy_registry.json
  └── safety_rules.yaml
            ↓
Pinned model and method configs
            ↓
Preregistered phased scientific workflow
            ↓
Raw predictions + deterministic parser/metrics
            ↓
Immutable artifacts + selected adapter + publication verification
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

## Extension Seams

Future work may add capability packs, method registries, backend decisions, and generalized workflow
orchestration. Those are explicit product extensions, not features of v0.1. An additional pack must
define its own policy registry, safety rules, evidence surfaces, readiness contract, model support,
and reproducibility gates before it can enter hosted replay.
