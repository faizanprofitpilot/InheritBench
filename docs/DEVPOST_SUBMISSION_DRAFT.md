# Devpost Submission Draft

Replace only the explicit placeholders after deployment, video upload, Codex feedback, and Devpost
publication. Do not alter scientific values during submission editing.

## Project Title

InheritBench — Model Succession Lab

## One-Line Description

Move the model. Keep the capability.

## Short Description

InheritBench is a developer tool for AI teams replacing one model family with another. It measures
what learned operational capability breaks, reconstructs the successor, evaluates clean and
adversarial readiness, exports the recovered adapter, and produces an evidence-backed migration
decision.

## Long Description

Model replacement is usually evaluated as a broad quality or cost tradeoff. That misses a harder
operational question: what happens to a capability a team already taught the old model?

InheritBench packages model replacement as a succession workflow. The first supported case transfers
OpsRoute—strict refund and subscription action routing—from adapted Qwen2.5 0.5B Instruct to pinned
OLMo-2 1B Instruct.

Untouched OLMo produced 0/64 semantic-exact and 0/64 strict-valid outputs on the clean confirmatory
surface. Anchored Behavioral Transfer trained a fresh OLMo base with 214 exact teacher outputs and 10
hash-ranked original anchors. Upstream, the source teacher was trained on 224 original labels and the
matched distribution was designed from that same 224-label corpus. The recovered successor made
every measured clean decision, tool call, argument, approval, and reason code correctly, with 100%
strict validity and zero clean safety failures. Nine exact policy-code aliases reduced full-contract
exactness to 55/64, or 85.9375%.

A separate adversarial audit reached 20/32 semantic exactness and observed one unauthorized action
and one approval bypass. InheritBench therefore returns `CONDITIONAL_PASS`, not an unconditional
migration claim.

The product lets judges run a deterministic verified succession replay in the browser. It validates
committed manifests and hashes, recomputes metrics, classifies residuals, applies readiness rules,
confirms the published adapter, and generates a fresh readiness report and replay receipt. It does
not simulate training. The real source-to-successor workflow remains a preregistered phased CLI.

## Inspiration

Teams change model providers, move to open weights, self-host, or diversify infrastructure. Existing
benchmarks compare general capability, but they rarely answer whether a replacement can assume one
specific learned operational contract. InheritBench was built to make that migration measurable,
recoverable, and auditable.

## What It Does

```text
Configure succession
→ Verify capability break
→ Reconstruct successor
→ Evaluate clean and adversarial readiness
→ Export adapter and migration decision
```

v0.1 delivers:

- one frozen OpsRoute capability pack;
- one published Qwen → OLMo succession;
- a recovered OLMo LoRA adapter;
- clean and adversarial evaluation surfaces;
- deterministic readiness rules;
- residual-failure and accounting reports;
- a validated GPT-5.6 Succession Memo;
- browser and CLI verified replay;
- content-addressed evidence and replay receipts.

## How It Works

The scientific layer pins model revisions, data, prompts, parser, evaluator, seed, training settings,
and leakage rules. It preserves raw outputs and finalizes artifacts atomically without overwrite.

The product layer consumes a frozen succession manifest and compact atomic records. Shared Python
and TypeScript replay engines validate hashes, aggregate surface-specific metrics, classify clean
policy-code aliases, count adversarial failures, apply `succession-readiness-v0.1`, verify the public
adapter identity, and generate fresh product outputs.

The static web build uses committed data and Node only. It has no backend, database, authentication,
runtime API, GPU, model download, or secret.

## How Codex Was Used

Codex accelerated experiment scaffolding, deterministic dataset generation, model-loading and
inference paths, LoRA training orchestration, strict artifact schemas, atomic finalization, leakage
checks, replay systems, Phase 3B protocol implementation, Phase 4 evidence construction, the memo
validator, static projection, browser verification, the succession replay engines, CLI, frontend
workflow, tests, CI, and documentation.

The founder chose the product problem and scientific agenda, including preserving negative results,
forbidding parser repair and test-driven substitution, freezing bounded protocols, requiring direct
and upstream label accounting, separating clean and adversarial surfaces, selecting anchored
transfer after the teacher blind spot, retaining `CONDITIONAL_PASS`, and refusing fake browser
training.

**TODO BEFORE SUBMISSION: Add primary Codex `/feedback` Session ID.**

## How GPT-5.6 Was Used

GPT-5.6 Sol consumed a validated, content-addressed evidence graph and produced a structured
Succession Memo. The run used one initial response and one permitted repair. A deterministic claim
validator checked numeric values, denominators, comparisons, evidence references, accounting, and
unsupported causal claims before the memo entered the showcase.

GPT-5.6 did not produce raw benchmark metrics, determine safety eligibility, alter evidence, or
independently prove safety. Deterministic evaluators and readiness rules own those decisions.

## Challenges

- Preserving strict evaluator behavior without score-inflating parser repair.
- Preventing leakage across generated, train, validation, test, adversarial, and diagnostic data.
- Separating exact contract fidelity from operational correctness.
- Diagnosing why high teacher acceptance still missed one critical archetype.
- Recovering the blind spot with a bounded, preregistered hybrid intervention.
- Presenting a completed scientific workflow as a real browser action without pretending to train.
- Keeping the deployment build Node-only while retaining Python scientific verification.

## Accomplishments

- Demonstrated a complete capability break from adapted Qwen to untouched OLMo.
- Preserved two terminal negative pure-distillation attempts.
- Recovered clean operational behavior with Anchored Behavioral Transfer.
- Exported and anonymously byte-verified the successor adapter.
- Ran six-system adversarial analysis without tuning on the adversarial results.
- Produced a validated GPT-5.6 evidence memo.
- Built cross-language deterministic replay with matching golden hashes.
- Built a self-directed static product with unit, integration, accessibility, and browser tests.

## What We Learned

- High overall synthetic acceptance can hide a concentrated teacher capability blind spot.
- A small targeted anchor set can repair a mechanically diagnosed quota deficit, but upstream label
  dependence must remain explicit.
- Operationally correct outputs can still fail exact contract scoring through controlled-vocabulary
  aliases.
- Clean capability recovery does not imply adversarial readiness.
- A migration product must be willing to condition or block a successor, not optimize for a pass.

## What Is Next

- Verify and publish the static deployment.
- Add capability-pack authoring and validation without weakening evidence requirements.
- Enforce registry-backed policy vocabularies in future evaluator versions.
- Test additional model pairs, capabilities, seeds, and accelerator backends.
- Extend succession orchestration only after the first product path remains reproducible.

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
