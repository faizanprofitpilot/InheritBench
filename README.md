# InheritBench

**Models are becoming fungible. Learned capabilities are not.**

**Move the model. Keep the capability.**

InheritBench transfers a learned operational capability from one model family to its successor,
then verifies what was recovered, what still fails, and whether the migration is ready to ship.

> **Product status:** `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED`
>
> **Live demo:** deployment pending
> **Published case:** Qwen → OLMo on OpsRoute `v0.1.0`
> **Local engine:** pack-driven succession `v0.2`

**Start here:** [five-minute judge guide](docs/JUDGE_REPLAY.md) ·
[recovered successor adapter](https://github.com/faizanprofitpilot/InheritBench/releases/download/phase3b-anchored-v0.1.0/target_hybrid_anchored_distillation_10-7461072c83b4dcde.zip) ·
[product architecture](docs/PRODUCT_ARCHITECTURE.md) ·
[scientific protocol](docs/EVALUATION_PROTOCOL.md) · demo video pending

## What InheritBench Does

InheritBench helps ML platform, applied AI, model infrastructure, safety, and evaluation teams answer
one operational question:

> Can a replacement model safely assume an existing learned capability, and if not, can that
> capability be recovered with a deliverable successor artifact and auditable migration guidance?

```text
Define the capability contract
→ Measure what the untouched successor lost
→ Generate source-derived transfer supervision
→ Train and select the recovered successor
→ Evaluate clean and adversarial readiness
→ Export the adapter, evidence, and migration decision
```

A succession run ends with one practical outcome: pass the successor, deploy it conditionally with
known safeguards, or block the migration. InheritBench is not a leaderboard or a generic
distillation script. It begins with a learned operational capability and ends with a trained
successor artifact, residual-risk evidence, complete data and compute accounting, and an explicit
migration decision.

The Qwen → OLMo case is proof that the system has performed this job once, not a claim of universal
transfer. The published hosted case remains frozen at v0.1. The local v0.2 engine now executes
developer-owned structured-JSON capability packs against an explicit Qwen/OLMo model registry and
fails closed outside that supported architecture boundary.

The latest v0.2 audit now separates historical reconstruction from prospective reproducibility.
The historical Day 2 initialization remains unreconstructible, but an independently executed
seeded direct protocol reproduced all 168 telemetry steps, checkpoints, raw predictions, evaluator
facts, readiness, and adapter bytes exactly. That permitted one real generic anchored execution.
The engine independently derived the ten-anchor deficit from 768 frozen teacher outputs, selected
ten anchors from the bound 14-record pool, resumed without repeating teacher filtering, trained,
evaluated, exported, reloaded, and replayed the successor. It honestly remained
`MIGRATION_BLOCKED`; the published Phase 3B successor and all historical evidence remain unchanged.

A later evidence-only audit proved that the four-seed recovery test had treated finite pre-clip
gradient norms as numerical failures after clipping. The implementation guard was corrected without
changing supervision, schedule, optimizer, checkpoints, validation rules, readiness rules, or the
sealed final surfaces. All four frozen seeds were restarted under the repaired guard and completed.
Validation-only ranking selected candidate 0; its fresh OLMo reload then ran the sealed final
surfaces exactly once.

That repaired local product proof reached 64/64 clean operational correctness, 63/64 exact
full-contract fidelity, 64/64 historical strict validity, and zero clean blocker safety findings.
It reached 20/32 adversarial operational and exact correctness with one unauthorized action and one
approval bypass on the same record, producing
`GENERIC_ANCHORED_RECOVERY_CONFIRMED / CONDITIONAL_PASS`. The proof consumes verified frozen teacher
outputs and does not prove live generic teacher generation. It is local integration evidence; the
immutable Phase 3B result and published adapter remain the authoritative public scientific result.

## Why InheritBench Is Different

| System | Starts with | Ends with |
|---|---|---|
| General benchmark | A broad model comparison | Aggregate model scores |
| Distillation script | A teacher and student | A trained student checkpoint |
| InheritBench | A learned operational capability that must survive replacement | A recovered successor adapter, residual-risk report, and pass/condition/block decision |

## First Supported Succession

| Product input | Frozen v0.1 value |
|---|---|
| Capability pack | OpsRoute `v0.1.0` |
| Learned capability | Refund routing and subscription cancellation/retention |
| Source | Adapted `Qwen/Qwen2.5-0.5B-Instruct` |
| Successor base | Pinned `allenai/OLMo-2-0425-1B-Instruct` |
| Transfer strategy | Anchored Behavioral Transfer |
| Target supervision | 214 exact teacher outputs + 10 original anchors |
| Target training | 224 records, 272,568 processed tokens, checkpoint step 168 |
| Delivered artifact | Verified OLMo LoRA adapter |
| Readiness decision | `CONDITIONAL_PASS` |

The upstream source teacher was trained on 224 original labels, and the matched candidate
distribution was designed from that same 224-label corpus. This is not ten-shot, label-free, or
purely synthetic transfer. See [Anchored Behavioral Transfer](docs/METHOD_ANCHORED_TRANSFER.md) for
the complete accounting.

## How InheritBench Works

### Capability layer

The capability pack defines the operational contract, policy vocabulary, scenario families,
evaluator, safety conditions, and held-out surfaces that must survive the migration.

### Succession layer

InheritBench measures the untouched target, constructs transfer supervision from the adapted
source, trains a fresh successor, selects a safety-eligible checkpoint, and exports the resulting
LoRA adapter. The published v0.1 path remains a preregistered phased workflow. The isolated v0.2
product engine adds deterministic planning, direct LoRA and anchored transfer strategies,
intervention/resume, model-free replay, and local browser inspection without importing historical
OpsRoute implementation code.

### Assurance layer

Deterministic evaluators preserve raw outputs, compute clean and adversarial results, classify
residual failures, apply readiness rules, and bind conclusions to content-addressed evidence.
GPT-5.6 explains the resulting migration tradeoffs but does not own scores or safety gates.

## Result at a Glance

Clean confirmatory and adversarial evidence are separate evaluation surfaces and are never blended
into one score.

Untouched OLMo could not perform the capability. After succession, the recovered OLMo made every
measured clean operational decision and action correctly, with 100% strict contract validity and
zero clean safety violations. Nine policy-code aliases reduced exact full-contract fidelity to
85.9%.

| Surface and system | Semantic exactness | Strict validity | Operational or safety result |
|---|---:|---:|---|
| Clean · untouched OLMo | 0 / 64 | 0 / 64 | 4 unauthorized actions |
| Clean · recovered successor | 55 / 64 (85.9375%) | 64 / 64 (100%) | 64/64 decision, tool, arguments, approval, and reason code; zero unauthorized actions, bypasses, or false actions |
| Adversarial · recovered successor | 20 / 32 (62.5%) | 30 / 32 | 8 prompt-injection failures, 3 conflicting-identifier failures, 1 unauthorized action, 1 approval bypass |

> **The recovered successor made every measured clean operational decision and action correctly.
> Its nine remaining clean errors were exact policy-code aliases, reducing full-contract exactness
> to 85.9%.**

Clean capability recovery succeeded, but adversarial robustness remains insufficient for an
unconditional migration pass. Deterministic readiness rules therefore produce `CONDITIONAL_PASS`,
not “production ready” or “fully safe.”

## Try the Product

### Hosted route after deployment

The static product route will be:

```text
/run/opsroute-qwen-olmo/
```

It is available after public deployment. No live URL is claimed yet.

### GPU-free local replay

The smallest verified installation uses only base dependencies:

```bash
uv sync --frozen --no-dev
uv run --no-dev inheritbench succession replay \
  --case opsroute-qwen-olmo \
  --profile maximum-confirmed-capability \
  --output runs
```

The replay is CPU-only, offline, deterministic, and idempotent. It verifies immutable evidence,
derives metrics and residuals, applies `succession-readiness-v0.1`, confirms the published adapter
identity, and writes a fresh product run bundle.

### Full-workflow preflight

```bash
uv run inheritbench succession preflight \
  --case opsroute-qwen-olmo \
  --mode full \
  --json -
```

Preflight checks local model dependencies, pinned revisions, accelerator, disk, frozen capability
data, and preregistration evidence. It prints the real phased command sequence; it does **not** train
a model or present a generalized one-command executor.

### Pack-driven local execution

```bash
uv run inheritbench capability validate capabilities/opsroute/v0.2.0
uv run inheritbench succession plan \
  --pack capabilities/opsroute/v0.2.0 \
  --source-config configs/models/source.yaml \
  --target-config configs/models/target.yaml \
  --strategy direct-target-lora-v0.1 \
  --output runs
uv run inheritbench succession run --plan runs/<run-id> --device mps
```

The exact model registry, capability contract, stage graph, anchor intervention, output bundle, and
real integration evidence are documented in
[Pack-Driven Succession v0.2](docs/PACK_DRIVEN_SUCCESSION.md).

## Product Modes

| Mode | What it does | Hardware | Network | Output |
|---|---|---|---|---|
| Hosted verified replay | Verifies frozen succession evidence and derives a fresh readiness decision | Modern Chromium browser | Static site delivery only; no runtime API, model, or external data service | Readiness report and replay receipt |
| Local replay | Runs the equivalent deterministic product replay through Python | CPU | Offline after installation | Product run bundle |
| Full phased workflow | Performs real supervision preparation, training, evaluation, selection, replay, and export | Apple Silicon MPS in the executed case | Model downloads required | Trained adapter and scientific evidence |

The hosted product verifies and replays a completed succession from immutable evidence. Full
source-to-successor training remains the real preregistered phased CLI workflow.

## Delivered Output

The local replay writes one deterministic, no-overwrite directory:

```text
runs/succession-replay-<content-hash>/
├── succession_run_manifest.json
├── readiness_report.json
├── replay_receipt.json
├── evaluation_summary.json
├── residual_failures.json
├── label_accounting.json
├── compute_accounting.json
├── adapter_reference.json
└── evidence_manifest.json
```

The run manifest references rather than copies scientific artifacts. Repeating an identical replay
returns the byte-identical run; a conflicting existing directory fails closed. The complete contract
is documented in [Succession Outputs](docs/SUCCESSION_OUTPUTS.md).

## Built with Codex and GPT-5.6

### Codex collaboration

Codex served as the primary implementation partner across the scientific engine and product
surface. The founder defined the problem, protocols, intervention boundaries, scientific claims,
and product decisions; Codex helped translate those decisions into tested code, immutable artifacts,
replay systems, and the final execution cockpit.

That implementation work covered experiment and training infrastructure; integrity, leakage, and
replay machinery; the evidence graph and GPT-5.6 validator; the CLI and browser succession workflow;
and tests, CI, and documentation.

The founder set the scientific and product agenda: choosing model succession as the problem,
separating exact contract fidelity from operational correctness, preserving negative experiments,
forbidding parser repair and result substitution, freezing bounded protocols, selecting anchored
transfer after the teacher blind spot was diagnosed, requiring direct and upstream label accounting,
separating clean and adversarial surfaces, retaining `CONDITIONAL_PASS`, rejecting fake browser
training, and turning the completed case into a testable succession workflow.

**TODO BEFORE SUBMISSION: Add primary Codex `/feedback` Session ID.**

### GPT-5.6 Sol

GPT-5.6 is not a decorative chatbot inside InheritBench. It is a constrained reasoning layer that
converts validated evidence into a human-readable, constraint-aware migration recommendation.

Deterministic evaluators produce metrics and safety facts. Deterministic readiness rules determine
eligibility. GPT-5.6 Sol explains the constraint-aware migration recommendation from a validated,
content-addressed evidence graph, and a claim validator checks the memo before publication.

**Deterministic evaluators own the facts. Deterministic gates own eligibility. GPT-5.6 explains the
decision.**

The authoritative memo used one initial structured-output request and one permitted repair. GPT-5.6
did not calculate benchmark metrics, replace safety gates, alter evidence, or independently prove
model safety. Read the validated memo in the static product or inspect the frozen bundle under
`artifacts/showcase/inheritbench-v0.1-gpt`.

## Architecture

```text
Capability pack + pinned model configs
                    ↓
Preregistered supervision and training workflow
                    ↓
Raw predictions → deterministic parser and metrics
                    ↓
Content-addressed scientific artifacts + verified adapter
                    ↓
Evidence graph → GPT-5.6 memo → deterministic claim validation
                    ↓
Succession run manifest + compact replay records
                    ↓
Shared Python / TypeScript replay specification
                    ↓
Readiness report + replay receipt + static web cockpit
```

The product has no backend, database, authentication, runtime model service, or secret. The deployed
build uses Node and committed web data only; Python remains the scientific projection and local
verification layer. See [Product Architecture](docs/PRODUCT_ARCHITECTURE.md) and
[Capability Packs](docs/CAPABILITY_PACKS.md).

## Proof: Qwen → OLMo

The frozen OpsRoute case proves the system has completed the full succession job:

1. **Capability break:** untouched OLMo produced 0/64 semantic-exact and 0/64 strict-valid outputs
   on the clean confirmatory surface.
2. **Independent distillation failed:** only 59/768 teacher outputs met the frozen acceptance rules.
3. **Distribution matching exposed a blind spot:** acceptance rose to 719/768, but duplicate
   auto-refund supplied only 4/48 accepted examples against a quota of 14.
4. **Anchored Behavioral Transfer succeeded cleanly:** 214 teacher labels plus 10 hash-ranked
   original anchors trained a fresh pinned OLMo base.
5. **Adversarial audit limited readiness:** 62.5% semantic exactness and two observed safety events
   required a conditional rather than unconditional migration recommendation.
6. **Adapter publication:** the selected step-168 LoRA adapter was packaged, released, downloaded
   anonymously, and byte-verified.

Negative attempts remain immutable and visible. Detailed chronology lives in the
[Build Log](docs/BUILD_LOG.md), [Decision Record](docs/DECISIONS.md),
[Synthetic Distillation Methods](docs/METHOD_SYNTHETIC_DISTILLATION.md), and
[Anchored Behavioral Transfer](docs/METHOD_ANCHORED_TRANSFER.md).

## Reproducibility and Trust

- Frozen protocols and Git-tree preregistration bind scientific choices before execution.
- Canonical JSON, byte hashes, content hashes, atomic rename, and no-overwrite storage protect
  evidence integrity.
- Raw model outputs remain preserved; parser failures remain visible.
- Metrics and readiness decisions are deterministic code outputs, not memo judgments.
- Replay reconstructs results from saved atomic records without model weights or network access.
- The released adapter archive and internal files have verified SHA-256 identities.
- Browser replay verifies the compact product bundle; it is not model inference or full scientific
  parser replay.
- The Python scientific replay remains the canonical deeper verification path.

## Supported Platforms

| Use | Verified platform |
|---|---|
| Hosted/static product | Chromium desktop and Pixel 7 mobile emulation |
| GPU-free replay | CPython 3.11.15 on macOS Apple Silicon; CI also verifies Linux execution |
| Full model workflow | macOS Apple Silicon with MPS, executed on an Apple M2 Pro with 32 GB unified memory |
| Frontend toolchain | Node 22.14.0 and pnpm 10.7.1 |
| Python environment | uv 0.11.28 with committed `uv.lock` |

Firefox, Safari, Windows, CUDA, and Linux GPU training are not claimed as verified execution
platforms. The application is a static export and may work more broadly, but those environments
remain unvalidated.

## Installation

### Product replay only

```bash
git clone https://github.com/faizanprofitpilot/InheritBench.git
cd InheritBench
uv sync --frozen --no-dev
uv run --no-dev inheritbench succession replay --output runs
```

No model weights, API key, accelerator, or network connection are required after installation.

### Frontend development

```bash
pnpm install --frozen-lockfile
pnpm ingest
pnpm dev
```

The production export is Node-only:

```bash
pnpm build
```

### Full scientific workflow

```bash
uv sync --frozen --extra model --group dev
uv run inheritbench succession preflight --case opsroute-qwen-olmo --mode full --json -
```

The executed local workflow requires model downloads, sufficient disk, and Apple MPS. Follow the
phased commands emitted by preflight; do not interpret preflight itself as training.

## Five-Minute Judge Test

Before public deployment, use the local equivalent:

1. Run the base-only installation and `succession replay` command above.
2. Open `readiness_report.json` and confirm `CONDITIONAL_PASS`.
3. Open `replay_receipt.json` and confirm all nine verification operations passed.
4. Inspect `residual_failures.json` for nine clean policy-code aliases and the adversarial profile
   counts.
5. Open the [recovered successor adapter](https://github.com/faizanprofitpilot/InheritBench/releases/download/phase3b-anchored-v0.1.0/target_hybrid_anchored_distillation_10-7461072c83b4dcde.zip).
6. Read the GPT-5.6 recommendation and evidence references in the static showcase bundle.

After deployment, judges can perform the same journey at `/run/opsroute-qwen-olmo/`: review the
no-training preflight, run verified replay, download the fresh report and receipt, inspect the
adapter, open the validated memo, and verify evidence. The final public URL will replace the single
placeholder in [Judge Replay](docs/JUDGE_REPLAY.md).

## Limitations

- Real execution supports only the explicit pinned Qwen → OLMo registry; arbitrary Transformers
  architectures remain unsupported.
- OpsRoute is the only real reference pack. Purchase Approval is fixture-only and carries no model
  transfer claim.
- One deterministic seed demonstrates reproducibility, not statistical significance.
- Hosted mode does not train or run inference.
- Hosted capability uploads and hosted training are unsupported.
- Exact full-contract fidelity differs from operational correctness.
- Adversarial robustness remains limited; the readiness decision is conditional.
- The method directly consumes 10 original anchors and depends upstream on a teacher trained with
  224 original labels and a distribution designed from that corpus.
- Confirmatory and adversarial surfaces are small and case-specific.
- Results do not establish universal capability transfer or production safety.

## Where It Goes Next

The next milestone is broader executed evidence, not more orchestration scaffolding:

1. run the same OpsRoute succession against a second target model family with minimal pair-specific
   changes;
2. promote a second, materially different capability pack from fixture-only to real execution;
3. extend the explicit model registry with another tested architecture;
4. test repeated seeds, larger held-out surfaces, and additional accelerator backends;
5. deploy and verify the static product publicly.

The long-term goal is a model-agnostic succession process: recover the capability when possible,
and condition or block migration when evidence is insufficient.

## Documentation

- [Five-minute judge replay](docs/JUDGE_REPLAY.md)
- [Product architecture](docs/PRODUCT_ARCHITECTURE.md)
- [Capability packs](docs/CAPABILITY_PACKS.md)
- [Pack-driven succession v0.2](docs/PACK_DRIVEN_SUCCESSION.md)
- [Succession output contract](docs/SUCCESSION_OUTPUTS.md)
- [Deployment checklist](docs/DEPLOYMENT_CHECKLIST.md)
- [Demo script](docs/DEMO_SCRIPT.md)
- [Devpost submission draft](docs/DEVPOST_SUBMISSION_DRAFT.md)
- [Evaluation protocol](docs/EVALUATION_PROTOCOL.md)
- [Anchored Behavioral Transfer](docs/METHOD_ANCHORED_TRANSFER.md)
- [Synthetic distillation attempts](docs/METHOD_SYNTHETIC_DISTILLATION.md)
- [Compute and accounting](docs/COMPUTE_PLAN.md)
- [Licensing](docs/LICENSING.md)
- [Clean-room statement](docs/CLEAN_ROOM.md)
- [Decision record](docs/DECISIONS.md)
- [Append-only build log](docs/BUILD_LOG.md)
