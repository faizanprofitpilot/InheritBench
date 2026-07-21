# InheritBench

InheritBench helps teams replace an open-weight model without silently losing behavior their
application depends on. It diagnoses capability loss, compares recovery strategies, selects a
successor without final-test leakage, and issues a replayable readiness decision.

**Move the model. Keep the capability. Prove it survived.**

> **Status:** `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED`
>
> The static product, browser Assurance Lab, completed succession inspector, and local verification
> paths are implemented and tested. A public deployment URL and demo video will be added only after
> deployment verification and recording.

## Judge Links

- **Live product:** deployment pending
- **Assurance Lab:** `/sandbox/` in the static product
- **Completed Qwen → OLMo succession:** `/run/opsroute-qwen-olmo/`
- **Source repository:** <https://github.com/faizanprofitpilot/InheritBench>
- **Demo video:** pending
- **Five-minute guide:** [Judge Replay](docs/JUDGE_REPLAY.md)

## Five-Minute Judge Quickstart

In the deployed product:

1. Open the **Assurance Lab**.
2. Run the **Untouched OLMo** diagnostic.
3. Run the **Anchored successor**.
4. Inject an **Approval bypass** and rerun.
5. Open the completed succession evidence.

The browser evaluates committed predictions and recomputes the decision. It does not simulate
training or inference.

### Lightweight frontend verification

```bash
git clone https://github.com/faizanprofitpilot/InheritBench.git
cd InheritBench
corepack enable
pnpm install --frozen-lockfile
pnpm --filter @inheritbench/web exec playwright install chromium
pnpm verify:web
```

`pnpm verify:web` regenerates the ignored `apps/web/public/data/` directory from committed,
hash-verified product artifacts before linting, type-checking, testing, building, and running the
Chromium browser suite.

### Fastest evidence replay

```bash
uv sync --frozen --no-dev
uv run --no-dev inheritbench succession replay --output runs
```

This base-only Python path needs no model weights, accelerator, API key, or network after
installation. It reconstructs the published Phase 3B readiness evidence and writes nine
deterministic output files under `runs/succession-replay-2b1798dad96176ff/`.

## What Runs Live and What Is Precomputed

### Runs in the browser

- artifact and hash integrity checks;
- prediction parsing and evaluation;
- schema and contract validation;
- coverage-group aggregation;
- safety checks;
- readiness application;
- controlled in-memory mutations;
- local JSON or JSONL prediction uploads;
- deterministic replay/parity checks;
- unsigned local receipt generation.

### Precomputed

- Qwen and OLMo model loading;
- source and successor inference;
- LoRA training;
- multi-seed candidate generation and checkpoint production;
- final reference predictions.

Those operations require model weights, storage, ML dependencies, and accelerator compute. The
browser works from committed predictions and verified evidence; it never claims to train Qwen or
OLMo, run fresh inference, sign a receipt, or provide external attestation.

## Reference Result

The current product reference is the repaired, bounded four-seed Qwen → OLMo succession projected
under `artifacts/product/reference-succession-v0.1/`. Candidate 0 was selected from validation
evidence before either final evaluation set was opened.

- Clean operational correctness: `64 / 64`
- Clean exact-contract fidelity: `63 / 64`
- Clean strict validity: `64 / 64`
- Clean safety blockers: `0`
- Adversarial exact-contract result: `20 / 32`
- Adversarial strict validity: `31 / 32`
- Safety findings: `2 findings on 1 record`
- Readiness: `CONDITIONAL_PASS`
- Replay: `192 predictions verified`

The result is conditional because clean behavior recovered, while one adversarial record still
produced an unauthorized action and an approval bypass. The unchanged
`opsroute-readiness-product-v0.1` rules therefore allow neither an unconditional pass nor a claim of
production safety.

### Current product evidence versus historical public evidence

The product experience above presents the later repaired multi-start execution and its committed
web projection. The separately published
[Phase 3B adapter](https://github.com/faizanprofitpilot/InheritBench/releases/tag/phase3b-anchored-v0.1.0)
and `succession-readiness-v0.1` replay remain frozen historical scientific evidence. Their metrics,
adapter identity, and readiness record are not rewritten to match the later product execution.
See [Pack-Driven Succession](docs/PACK_DRIVEN_SUCCESSION.md) for the full relationship between these
tracks.

## Product Workflow

```text
Validate capability pack
→ verify the adapted source
→ diagnose target capability loss
→ choose a configured recovery strategy
→ train bounded candidates
→ select using validation evidence only
→ open final evaluation records
→ apply the versioned readiness contract
→ export and verify the adapter
→ replay the decision
```

The capability pack, model registry, strategies, thresholds, record roles, and candidate budget are
configured. Pack validation, evidence separation, deterministic evaluation, readiness application,
hash verification, and replay are automated. The current reference still uses an explicitly
supported Qwen/OLMo model pair and an OpsRoute-specific capability pack; it is not an arbitrary-model
autotuning system.

## Installation and Supported Platforms

### Browser deployment

The Next.js application is a static export. Deployment requires Node `22.14.0`, pnpm `10.7.1`, and
the committed product artifacts. It requires no Python, backend, database, API key, model weights,
or runtime model service.

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm build
```

### Frontend development

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm ingest
pnpm dev
```

`pnpm dev` also runs ingestion. The explicit `pnpm ingest` step makes the clean-clone data
dependency visible.

### Evidence replay

- CPython `3.11.15` (`>=3.11,<3.12` is enforced);
- uv `0.11.28` is the CI-pinned version;
- CPU-only after dependency installation;
- verified on macOS Apple Silicon and Linux CI;
- no model download or accelerator required.

### Full ML workflow

```bash
uv sync --frozen --extra model --group dev
uv run inheritbench succession preflight \
  --case opsroute-qwen-olmo \
  --mode full \
  --json -
```

Preflight does not train. It checks the phased workflow prerequisites and may fail honestly. The
implemented checks require at least 20 GiB free disk, warn below 16 GiB RAM, verify model
dependencies and pinned revisions, and report accelerator availability. The executed reference
workflow used macOS Apple Silicon MPS on an Apple M2 Pro with 32 GB unified memory. CUDA, CPU
training, Linux GPU training, Windows, Firefox, and Safari are not claimed as verified platforms.

Model downloads are required for full reproduction. Individual historical training executions took
minutes on the recorded M2 Pro environment, but InheritBench does not publish a portable runtime
SLA; hardware, cache state, and model access materially affect duration.

## Reproduction Levels

### Level 1 — Browser verification

No installation, credentials, model weights, backend, or accelerator. Use the Assurance Lab to
evaluate scenarios, mutate predictions, apply readiness, inspect records, and download an unsigned
local receipt.

### Level 2 — Local evidence replay and tests

Clone the repository and use either `pnpm verify:web` for the static product or the base-only Python
replay command for deterministic evidence reconstruction. Full ML dependencies are not required.

To run the root web/projection gate, prepare both toolchains first:

```bash
uv sync --frozen --no-dev
corepack enable
pnpm install --frozen-lockfile
pnpm --filter @inheritbench/web exec playwright install chromium
pnpm verify
```

`pnpm verify` verifies the Python web projection and executes the complete frontend verification
chain. CI additionally runs Python formatting, linting, mypy, pytest, and deterministic data
regeneration.

### Level 3 — Full succession reproduction

Requires the model extra, pinned Qwen and OLMo downloads, sufficient storage and memory, and an
accelerator. Follow the preregistered phased commands emitted by preflight. Do not treat preflight as
training or the availability of a CLI device flag as proof that a backend was validated.

## Capability-Pack Extensibility

A developer-authored capability pack supplies:

- model-visible records and evaluator-only expected contracts;
- input and output JSON Schemas;
- prompts and controlled vocabularies;
- coverage-group declarations;
- safety rules;
- readiness thresholds;
- direct labels and optional intervention anchors;
- source and target model configuration through the supported registry.

The pack loader, declarative evaluator, data separation, safety AST, readiness application, replay,
and browser bundle are task-neutral. Real model execution has been demonstrated only with OpsRoute
and the pinned Qwen → OLMo pair. The Purchase Approval pack is fixture-only test evidence and makes
no transfer claim. See [Capability Packs](docs/CAPABILITY_PACKS.md).

## Built with Codex and GPT-5.6

Codex and GPT-5.6 helped build InheritBench. They are not the source or successor models in the
reference succession.

Their work included:

- architecture and workflow implementation;
- evaluator and readiness design;
- Python/TypeScript parity;
- experimental controls and evidence boundaries;
- numerical-failure investigation and guard repair;
- deterministic evidence projection;
- landing page, inspector, and Assurance Lab implementation;
- test generation, hostile audits, and documentation review.

The project owner defined the problem, scientific protocol, allowed interventions, readiness
semantics, and product claims. Deterministic evaluators own metrics and safety facts. Deterministic
rules own readiness. GPT-5.6 explains validated evidence but does not create scores, alter evidence,
or override gates.

**Codex `/feedback` Session ID:** `019f61c4-1e2b-7861-8e2c-7fe82c81255d`

This ID comes from the official Codex interface and identifies the session where the majority of
core implementation work occurred. It is included for OpenAI Build Week submission compliance.

## Scientific Boundaries

- Final evaluation records are sealed before candidate training.
- Candidate selection uses recovery-validation evidence only.
- Untouched OLMo is a diagnostic baseline and receives no readiness verdict.
- The numerical-guard repair changed finite-state validation and telemetry, not supervision,
  optimizer, schedule, candidate seeds, evaluation records, or readiness thresholds.
- Current product readiness uses `opsroute-readiness-product-v0.1`; historical Phase 3B replay uses
  its frozen `succession-readiness-v0.1` contract.
- Known adversarial residuals remain visible and produce `CONDITIONAL_PASS`.
- OpsRoute is the only demonstrated real capability pack.
- Frozen teacher outputs are used by the current reference; live generic teacher generation is not
  proven.
- InheritBench does not claim universal transfer success, arbitrary-model support, statistical
  significance, or production safety.

See [Evaluation Protocol](docs/EVALUATION_PROTOCOL.md), [Clean-Room Statement](docs/CLEAN_ROOM.md),
[Decision Record](docs/DECISIONS.md), and the append-only [Build Log](docs/BUILD_LOG.md).

## License and Citation

InheritBench source and project-authored OpsRoute materials are provided under Apache-2.0. Base model
weights are not redistributed; model use remains subject to the pinned upstream model cards and
licenses. Generated teacher outputs, adapters, and GPT-authored memos have additional provenance
notes in [Licensing](docs/LICENSING.md).

Citation metadata is provided in [CITATION.cff](CITATION.cff). A plain-text citation is:

```text
Faizan Muhammad. InheritBench: Model Succession with Executable Assurance. 2026.
https://github.com/faizanprofitpilot/InheritBench
```

## Documentation

- [Judge Replay](docs/JUDGE_REPLAY.md)
- [Product Architecture](docs/PRODUCT_ARCHITECTURE.md)
- [Capability Packs](docs/CAPABILITY_PACKS.md)
- [Pack-Driven Succession](docs/PACK_DRIVEN_SUCCESSION.md)
- [Succession Output Contract](docs/SUCCESSION_OUTPUTS.md)
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)
- [Demo Script](docs/DEMO_SCRIPT.md)
- [Devpost Submission Draft](docs/DEVPOST_SUBMISSION_DRAFT.md)
- [Licensing](docs/LICENSING.md)
- [Append-Only Build Log](docs/BUILD_LOG.md)
