# InheritBench

**Move the model. Keep the capability.**

InheritBench is a model-succession developer tool for AI teams replacing one model family with
another. It measures what learned operational capability breaks, reconstructs the capability on the
successor, evaluates clean and adversarial readiness, exports the recovered adapter, and produces an
evidence-backed migration decision.

> **Product status:** `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED`
>
> **Live demo:** deployment pending
> **Published case:** Qwen → OLMo on OpsRoute `v0.1.0`

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
Configure succession
→ Verify capability break
→ Reconstruct successor
→ Evaluate clean and adversarial readiness
→ Export adapter and migration decision
```

The packaged benchmark is proof of the product, not a claim of universal transfer. InheritBench
currently supports one completed configuration and fails closed outside that scope.

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

## Result at a Glance

Clean confirmatory and adversarial evidence are separate evaluation surfaces and are never blended
into one score.

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

Codex accelerated repository implementation across experiment scaffolding, deterministic OpsRoute
generation, model loading and inference, LoRA training orchestration, strict schemas, atomic
no-overwrite artifacts, leakage checks, replay systems, Phase 3B protocol implementation, Phase 4
evidence construction, the memo validator, static projection, browser verification, the succession
replay engines, CLI, frontend workflow, tests, CI, and documentation.

The founder set the scientific and product agenda: choosing model succession as the problem,
separating exact contract fidelity from operational correctness, preserving negative experiments,
forbidding parser repair and result substitution, freezing bounded protocols, selecting anchored
transfer after the teacher blind spot was diagnosed, requiring direct and upstream label accounting,
separating clean and adversarial surfaces, retaining `CONDITIONAL_PASS`, rejecting fake browser
training, and turning the completed case into a verified developer workflow.

**TODO BEFORE SUBMISSION: Add primary Codex `/feedback` Session ID.**

### GPT-5.6 Sol

Deterministic evaluators produce metrics and safety facts. Deterministic readiness rules determine
eligibility. GPT-5.6 Sol explains the constraint-aware migration recommendation from a validated,
content-addressed evidence graph, and a claim validator checks the memo before publication.

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

## Scientific Case

The frozen OpsRoute case records the full succession path:

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

- One pinned Qwen → OLMo model pair and one OpsRoute capability pack are supported.
- One deterministic seed demonstrates reproducibility, not statistical significance.
- Hosted mode does not train or run inference.
- Arbitrary models, capability uploads, and generalized one-command training are unsupported.
- Exact full-contract fidelity differs from operational correctness.
- Adversarial robustness remains limited; the readiness decision is conditional.
- The method directly consumes 10 original anchors and depends upstream on a teacher trained with
  224 original labels and a distribution designed from that corpus.
- Confirmatory and adversarial surfaces are small and case-specific.
- Results do not establish universal capability transfer or production safety.

Long-term, InheritBench aims to provide a model-agnostic succession process: recover the capability
when possible, and condition or block migration when evidence is insufficient.

## Documentation

- [Five-minute judge replay](docs/JUDGE_REPLAY.md)
- [Product architecture](docs/PRODUCT_ARCHITECTURE.md)
- [Capability packs](docs/CAPABILITY_PACKS.md)
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
