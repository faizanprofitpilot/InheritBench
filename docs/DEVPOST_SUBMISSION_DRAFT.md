# Devpost Submission Draft

Replace only the explicit deployment, video, and publication placeholders after those assets exist.
Do not alter scientific values during submission editing.

## Project Title

InheritBench — Model Succession with Executable Assurance

## One-Line Description

Use a local CLI to move a fine-tuned capability to a supported replacement model and produce a
replayable migration-readiness decision.

**Tagline:** Move the model. Keep the capability. Prove it survived.

## Links

- Live product: **TODO BEFORE SUBMISSION: add verified public URL**
- Assurance Lab: `/sandbox/`
- Completed Qwen → OLMo succession: `/run/opsroute-qwen-olmo/`
- Source: <https://github.com/faizanprofitpilot/InheritBench>
- Video: **TODO BEFORE SUBMISSION: add video URL**
- Devpost: **TODO AFTER SUBMISSION: add publication URL**

## Inspiration

Teams switch models for cost, latency, licensing, infrastructure, or vendor reasons. General
benchmarks do not prove that a replacement preserves an organization's exact policies, tool calls,
approval boundaries, and safety behavior. A plausible answer can still break the production
contract.

InheritBench turns that fine-tuned capability-portability problem into an executable local workflow:
**Diagnose → Recover → Assure**.

## What It Does

InheritBench is a local CLI. A developer authors a capability pack, selects an explicitly supported
source and target, configures a recovery strategy, and freezes a content-addressed plan. The engine
then verifies the adapted source, measures target loss, prepares authorized supervision, trains the
target adapter, selects using validation only, opens final records after selection, applies
readiness, exports and reloads the adapter, and produces replayable evidence.

```text
Capability pack
→ immutable succession plan
→ source verification and target diagnosis
→ configured recovery strategy
→ validation-only selection
→ sealed clean and adversarial assurance
→ adapter export, fresh-load verification, and replay
```

An anchored run may stop at `ANCHORS_REQUIRED`, identify the deficient group and count, accept
explicitly authorized original examples, and resume without regenerating completed teacher
evidence. The engine can also stop honestly with `MIGRATION_BLOCKED`.

The static product exposes two supporting judge paths:

- **Completed succession:** proof that the CLI executed a real Qwen → OLMo migration, including
  recovery, validation-only selection, sealed evaluation, adapter identity, and replay.
- **Assurance Lab:** evaluate generated predictions, challenge them with controlled mutations, apply
  readiness, inspect findings, upload compatible local results, and download an unsigned receipt.

The browser performs real evaluation, integrity, aggregation, safety, readiness, mutation, and replay
logic. It is not the migration engine; model loading, training, inference, candidate generation, and
adapter export are offline CLI operations.

## Reference Succession

The demonstrated capability is OpsRoute, a strict refund and subscription action-routing contract,
not the product itself.
The source is adapted Qwen2.5 0.5B Instruct and the successor is pinned OLMo-2 1B Instruct.

Untouched OLMo failed the source-gate diagnostic. InheritBench used Anchored Behavioral Transfer,
including ten deterministic original anchors, then executed a bounded four-seed recovery. Candidate
0 was selected from validation evidence before final records were opened.

Current repaired product evidence:

- Clean operational correctness: `64 / 64`
- Clean exact-contract fidelity: `63 / 64`
- Clean strict validity: `64 / 64`
- Clean safety blockers: `0`
- Adversarial exact-contract result: `20 / 32`
- Adversarial strict validity: `31 / 32`
- Safety findings: `2 findings on 1 record`
- Readiness: `CONDITIONAL_PASS`
- Replay: `192 predictions verified`

The condition is not cosmetic. One adversarial record produced both an unauthorized action and an
approval bypass. InheritBench therefore refuses an unconditional migration claim.

This current repaired multi-start experience is distinct from the frozen Phase 3B public adapter and
its historical metrics. The later product result does not rewrite historical scientific evidence.

## Why It Is Different

Benchmarks compare general performance. Distillation scripts produce a student model. InheritBench
starts from a learned operational capability and ends with a successor artifact, selection evidence,
residual risk, accounting, a migration decision, and replay.

The product is designed to preserve negative evidence:

- untouched target measurement is diagnostic-only;
- candidate selection cannot inspect final records;
- unsafe candidates are ineligible;
- residual failures remain visible;
- browser mutations cannot overwrite the verified baseline;
- deterministic rules, not an LLM, own readiness.

## How We Built It

### Capability and succession engine

Python, Pydantic, Typer, PyTorch, Transformers, PEFT, safetensors, declarative capability packs,
content-addressed plans, phased execution, deterministic evaluation, adapter export, and evidence
replay.

Primary commands include `inheritbench capability init|validate|inspect`,
`inheritbench succession plan|run|resume|add-anchors|inspect|replay|export-web`, and
`inheritbench succeed`.

### Product and Assurance Lab

Next.js App Router, React, TypeScript, Tailwind CSS, Zod, browser Web Crypto, Vitest, Playwright,
axe, and static export. The build ingests only committed, hash-verified product data.

### GPT-5.6

GPT-5.6 Sol consumed a validated evidence graph and produced a structured Succession Memo. A
deterministic claim validator checked substantive numeric and causal claims. GPT-5.6 explains the
evidence; it does not produce raw scores, determine candidate eligibility, modify evidence, or
override safety gates.

### Codex

Codex was the primary implementation partner for architecture, experiment controls, orchestration,
evaluators, numerical investigation and repair, Python/TypeScript parity, evidence projections,
Assurance Lab UI, tests, CI, hostile audits, and documentation. The project owner defined the
problem, protocols, allowed interventions, scientific claims, readiness semantics, and release
decisions.

**Codex `/feedback` Session ID:** `019f61c4-1e2b-7861-8e2c-7fe82c81255d`

This ID comes from the official Codex interface and identifies the session where the majority of
core implementation work occurred. It is included for OpenAI Build Week submission compliance.

## Challenges

1. Preserving a failure instead of retrying until it disappeared.
2. Separating operational correctness from exact-contract fidelity.
3. Preventing final-test leakage during multi-candidate recovery.
4. Repairing finite-state numerical validation without changing supervision, optimizer, schedule,
   seeds, or evaluation surfaces.
5. Making the assurance behavior judge-testable without pretending to run browser training.
6. Keeping historical evidence distinct from the later repaired product reference.

## Accomplishments

- Diagnosed capability collapse after a Qwen → OLMo replacement.
- Recovered all 64 measured clean operational behaviors.
- Selected the successor using validation evidence only.
- Preserved an adversarial safety residual and issued `CONDITIONAL_PASS`.
- Verified 192 final predictions in replay.
- Built browser evaluation, integrity, mutation, readiness, upload, and receipt paths.
- Kept the application static: no backend, database, authentication, runtime model API, or secret.
- Added desktop/mobile, accessibility, parity, data-integrity, and clean-build verification.

## What We Learned

- Capability transfer is constrained by coverage, not only label count.
- Operational correctness and contract fidelity need separate names and metrics.
- Clean recovery and adversarial readiness are separate claims.
- Selection evidence and final evidence need mechanically enforced boundaries.
- A migration product must be able to block its own output.
- Interactive assurance can be real even when expensive model execution is precomputed.

## Limitations

- OpsRoute is the only demonstrated real capability pack.
- Real model execution supports the pinned Qwen source and OLMo target only.
- The Purchase Approval pack is fixture-only evidence for evaluator genericity.
- Full training was executed on Apple MPS; CUDA, CPU training, and Linux GPU training are unverified.
- Static product tests target Chromium desktop and mobile emulation; Firefox and Safari are
  unverified.
- Frozen teacher outputs are used by the current reference.
- Small clean and adversarial surfaces do not establish universal transfer or production safety.
- A local verification receipt is unsigned and is not external attestation.

## Testing Instructions

Developer CLI workflow:

```bash
uv sync --frozen --extra model --group dev
uv run inheritbench capability validate capabilities/opsroute/v0.2.0
uv run inheritbench succession plan \
  --pack capabilities/opsroute/v0.2.0 \
  --source-config configs/models/source.yaml \
  --target-config configs/models/target.yaml \
  --strategy anchored-behavioral-transfer-v0.1 \
  --output runs
uv run inheritbench succession run --plan runs/<run-id> --device mps
```

This path requires model downloads and accelerator-backed execution; Apple MPS is the only real
training backend demonstrated.

Judge browser verification:

```bash
git clone https://github.com/faizanprofitpilot/InheritBench.git
cd InheritBench
corepack enable
pnpm install --frozen-lockfile
pnpm --filter @inheritbench/web exec playwright install chromium
pnpm verify:web
```

Base-only evidence replay:

```bash
uv sync --frozen --no-dev
uv run --no-dev inheritbench succession replay --output runs
```

See [Judge Replay](JUDGE_REPLAY.md) for expected outputs and [Deployment
Checklist](DEPLOYMENT_CHECKLIST.md) for the publication gate.

## What Is Next

1. Publish and verify the static deployment.
2. Record the product video.
3. Execute the same lifecycle against a second target model family.
4. Add a second real capability pack.
5. Validate additional accelerators and browsers.
6. Expand adversarial surfaces and controlled identifier validation.
