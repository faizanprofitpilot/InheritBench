# Devpost Submission Draft

Replace only the explicit placeholders after deployment, video upload, Codex feedback, and Devpost
publication. Do not alter scientific values during submission editing.

## Project Title

InheritBench — Model Succession Lab

## One-Line Description

Transfer a learned capability to a replacement model—then prove what survived, what failed, and
whether the successor is ready to ship.

**Tagline:** Move the model. Keep the capability.

## Short Description

InheritBench turns model replacement into a capability-succession workflow. It generates transfer
supervision, trains the replacement model, evaluates clean and adversarial readiness, exports the
recovered adapter, and produces an evidence-backed migration decision.

## Long Description

**Models are becoming fungible. Learned capabilities are not.**

A team can switch providers, move to open weights, self-host, or replace a model family—only to
discover that the successor has silently lost the operational behavior the old model was trained to
perform. General benchmarks rarely detect that break because they do not test the organization's
exact contract, policies, tools, and safety boundaries.

InheritBench performs model succession. A capability pack defines the behavior that must survive.
The system measures what the untouched replacement lost, generates source-derived transfer
supervision, trains the successor, evaluates clean and adversarial readiness, exports the recovered
adapter, and produces a decision to pass, condition, or block the migration.

The first supported succession moves OpsRoute—a strict refund and subscription action-routing
capability—from adapted Qwen2.5 0.5B Instruct to pinned OLMo-2 1B Instruct. Untouched OLMo produced
0/64 full-contract-exact and 0/64 strict-valid outputs on the clean confirmatory surface.

Anchored Behavioral Transfer trained a fresh OLMo base using 214 exact teacher-generated outputs and
ten hash-ranked original anchors. The source teacher itself had been trained on 224 original labels,
and the matched transfer distribution was designed from that same corpus.

The recovered successor made all 64 measured clean decisions, tool selections, arguments, approval
choices, and reason codes correctly. It achieved 100% strict validity and produced zero clean
unauthorized actions, approval bypasses, or false actions. Nine exact policy-code aliases reduced
full-contract fidelity to 55/64, or 85.9375%.

Clean recovery did not imply universal readiness. On a separate adversarial surface, the successor
reached 20/32 semantic exactness and produced one unauthorized action and one approval bypass.
InheritBench therefore issued `CONDITIONAL_PASS`, preserving the remaining deployment risk instead
of manufacturing a success claim.

Judges can run the supported succession through a deterministic browser replay. The application
validates manifests and hashes, derives clean and adversarial results from atomic prediction
evidence, applies versioned readiness rules, confirms the published adapter identity, and generates
a fresh readiness report and replay receipt. It does not pretend to retrain the model in the
browser. The actual supervision, training, checkpoint selection, evaluation, and adapter export
remain implemented in the preregistered phased CLI workflow.

## Inspiration

Models are increasingly replaceable, but the behavior organizations teach them is not portable by
default. InheritBench was built to make that lost-capability problem measurable, recoverable, and
safe enough to support an actual migration decision.

## What It Does

```text
Define the capability contract
→ Measure what the replacement lost
→ Generate source-derived supervision
→ Train and select the recovered successor
→ Evaluate clean and adversarial readiness
→ Export the adapter, evidence, and migration decision
```

The published v0.1 case delivers:

- one frozen OpsRoute capability pack;
- one published Qwen → OLMo succession;
- a recovered OLMo LoRA adapter;
- clean and adversarial evaluation surfaces;
- deterministic readiness rules;
- residual-failure and accounting reports;
- a validated GPT-5.6 Succession Memo;
- browser and CLI verified replay;
- content-addressed evidence and replay receipts.

The local v0.2 product engine additionally makes capability packs executable. It validates
developer-owned structured-JSON contracts, resolves exact model-registry entries, freezes
content-addressed plans, runs direct LoRA or anchored transfer, persists anchor deficits, resumes
without repeating teacher work, selects safety-eligible checkpoints, evaluates clean and
adversarial surfaces exactly once, derives readiness, exports adapters, and replays without model
weights.

This is not arbitrary-model support. The real registry is intentionally limited to the pinned Qwen
source and OLMo target. A materially different Purchase Approval pack proves genericity with fake
adapters, while a real OpsRoute direct-LoRA integration run exercised the complete model path and
honestly returned `MIGRATION_BLOCKED`.

A later seeded reference audit independently reproduced that corrected direct protocol bit-for-bit,
then exercised the full generic anchored lifecycle with real OLMo training: 768 frozen teacher
outputs, 719 accepted, a derived ten-anchor deficit, `ANCHORS_REQUIRED`, deterministic selection
from a bound 14-record pool, resume, checkpoint selection, final evaluation, adapter export,
fresh-base reload, and replay. The anchored product run also honestly returned
`MIGRATION_BLOCKED` at 53/64 clean semantic exactness. This validates the product machinery while
preserving the stronger published Phase 3B scientific result and avoiding a quality-driven rerun.

We then prospectively froze a four-seed initialization-sensitivity test with new sealed final
surfaces. Every candidate used identical supervision and training-stream bytes; only the LoRA
initialization seed changed. All four trajectories crossed the frozen numerical-instability guard
before validation, so InheritBench selected no model, ran no final evaluation, exported no adapter,
and returned `BLOCKED_BEFORE_FINAL_EVALUATION`. The product preserves this negative evidence and
renders readiness as not run rather than displaying a fabricated zero score.

Each succession ends with one practical outcome: pass the successor, deploy it conditionally with
known safeguards, or block the migration.

## Why InheritBench Is Different

**Benchmarks** tell you which model scores higher in general.

**Distillation scripts** train a student from a teacher.

**InheritBench** begins with a learned operational capability and ends with a recovered successor
artifact, residual-risk evidence, complete accounting, and a migration decision.

## How It Works

### Capability layer

OpsRoute defines the operational contract, policy vocabulary, scenario families, evaluator, safety
conditions, and held-out surfaces that must survive the migration.

### Succession layer

InheritBench measures the untouched target, constructs transfer supervision from the adapted
source, trains a fresh successor, selects a safety-eligible checkpoint, and exports the resulting
LoRA adapter through a preregistered phased workflow.

### Assurance layer

Deterministic evaluators preserve raw outputs, compute clean and adversarial results, classify
residual failures, apply readiness rules, and bind every conclusion to content-addressed evidence.
GPT-5.6 explains migration tradeoffs but does not own scores or safety gates.

The static product exposes this assurance layer without pretending to rerun GPU work. It validates
the succession manifest and compact atomic records, derives the decision, confirms adapter identity,
and generates fresh reports. The Node-only build has no backend, database, authentication, runtime
API, model download, GPU, or secret.

## How Codex Was Used

Codex served as the primary implementation partner across both the scientific engine and the product
surface. The founder defined the problem, protocols, intervention boundaries, scientific claims,
and product decisions; Codex helped translate those decisions into tested code, immutable artifacts,
replay systems, and the final execution cockpit.

Implementation covered experiment and training infrastructure; integrity, leakage, and replay
machinery; the evidence graph and GPT-5.6 validator; the CLI and browser succession workflow; and
tests, CI, and documentation.

The founder chose the product problem and scientific agenda, including preserving negative results,
forbidding parser repair and test-driven substitution, freezing bounded protocols, requiring direct
and upstream label accounting, separating clean and adversarial surfaces, selecting anchored
transfer after the teacher blind spot, retaining `CONDITIONAL_PASS`, and refusing fake browser
training.

**TODO BEFORE SUBMISSION: Add primary Codex `/feedback` Session ID.**

## How GPT-5.6 Was Used

GPT-5.6 is not a decorative chatbot inside InheritBench. It is a constrained reasoning layer that
converts validated evidence into a human-readable, constraint-aware migration recommendation.

GPT-5.6 Sol consumed a validated, content-addressed evidence graph and produced a structured
Succession Memo. The run used one initial response and one permitted repair. A deterministic claim
validator checked numeric values, denominators, comparisons, evidence references, accounting, and
unsupported causal claims before the memo entered the showcase.

GPT-5.6 did not produce raw benchmark metrics, determine safety eligibility, alter evidence, or
independently prove safety. Deterministic evaluators own the facts. Deterministic gates own
eligibility. GPT-5.6 explains the decision.

## Challenges

1. **Transferring behavior without hiding failure.** Pure distillation collapsed on one
   safety-critical archetype, and the system preserved that negative result instead of retrying
   until it disappeared.
2. **Separating operational correctness from exact contract fidelity.** The successor could make
   the correct decision and action while emitting the wrong policy identifier.
3. **Preventing scientific contamination.** Training, generated data, confirmatory evaluation, and
   adversarial evaluation required frozen boundaries and leakage checks.
4. **Turning a completed GPU workflow into a judge-testable product.** The browser needed to perform
   real verification without pretending to rerun training.

## Accomplishments

- Transferred OpsRoute from Qwen to a previously incapable OLMo successor.
- Recovered every measured clean operational decision and action.
- Exported and anonymously byte-verified the successor adapter.
- Preserved the failed pure-distillation paths and diagnosed the exact teacher blind spot.
- Issued an evidence-backed `CONDITIONAL_PASS` after adversarial testing exposed remaining risk.
- Built deterministic browser and CLI replay that derive the result instead of reading a stored
  verdict.
- Validated the GPT-5.6 memo against the evidence graph.
- Passed 141 offline Python tests, 10 frontend tests, and 36 desktop/mobile browser tests, plus
  static export and exact data/projection replay.

## What We Learned

- Capability transfer is limited by coverage, not just label volume. A teacher can perform well
  overall while systematically failing one crucial branch.
- A small anchor set is powerful only when mechanically targeted. The ten anchors repaired a
  diagnosed quota deficit; they were not an arbitrary few-shot trick.
- Structural validity and operational correctness are different. A contract may accept a string
  that is syntactically valid but operationally outside the approved vocabulary.
- Clean success and adversarial readiness are separate claims.
- A trustworthy succession system must be willing to block its own output.

## What Is Next

1. Verify and publish the static deployment.
2. Run the same OpsRoute succession pipeline against a second target model family with minimal
   pair-specific changes.
3. Add a second, materially different capability pack.
4. Introduce registry-backed contract validation for controlled operational identifiers.
5. Test repeated seeds, larger held-out surfaces, and additional accelerator backends.
6. Generalize the phased workflow into a configurable succession orchestrator.

## Technology Stack

- Python 3.11, uv, Pydantic, Typer, structlog
- PyTorch, Transformers, PEFT, safetensors
- Next.js App Router, TypeScript, React, Tailwind CSS
- Recharts, Motion, Zod
- Vitest, pytest, Ruff, mypy, Playwright, axe
- GPT-5.6 Sol structured outputs
- GitHub Actions and Vercel-ready static export

## Testing Instructions

GPU-free replay:

```bash
git clone https://github.com/faizanprofitpilot/InheritBench.git
cd InheritBench
uv sync --frozen --no-dev
uv run --no-dev inheritbench succession replay \
  --case opsroute-qwen-olmo \
  --profile maximum-confirmed-capability \
  --output runs
```

Expected status: `VERIFIED_REPLAY_COMPLETED`. Open `readiness_report.json` for
`CONDITIONAL_PASS` and `replay_receipt.json` for the nine passed replay operations.

## Supported Platforms

- Verified static product: Chromium desktop and Pixel 7 mobile emulation.
- Verified local replay: macOS Apple Silicon and Linux CI.
- Executed full workflow: macOS Apple Silicon MPS.
- Python: 3.11.15; Node: 22.14.0; pnpm: 10.7.1; uv: 0.11.28.
- Firefox, Safari, Windows, CUDA, and Linux GPU training are not claimed as verified.

## Limitations

- One model pair and one capability pack.
- One deterministic seed.
- No arbitrary uploads or hosted training.
- Browser replay is not model inference.
- Exact full-contract fidelity differs from operational correctness.
- Adversarial robustness remains limited.
- The method uses 10 direct original anchors and depends upstream on 224 original teacher labels and
  a distribution designed from that corpus.
- Small confirmatory and adversarial surfaces do not establish universal transfer.

## Links

- Repository: https://github.com/faizanprofitpilot/InheritBench
- Adapter: https://github.com/faizanprofitpilot/InheritBench/releases/download/phase3b-anchored-v0.1.0/target_hybrid_anchored_distillation_10-7461072c83b4dcde.zip
- Live demo: **TODO BEFORE SUBMISSION: add verified public URL**
- YouTube demo: **TODO BEFORE SUBMISSION: add video URL**
- Devpost submission: **TODO AFTER SUBMISSION: add Devpost URL**
- Codex `/feedback` Session ID: **TODO BEFORE SUBMISSION: add ID**
