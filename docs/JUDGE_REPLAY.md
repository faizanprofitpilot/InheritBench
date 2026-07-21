# Judge Replay

This guide tests InheritBench without downloading model weights, retraining OLMo, or calling a
runtime API. The Assurance Lab tests evidence and readiness layers; the actual model succession is
executed through the local CLI.

## Current Status and Links

- Product status: `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED`
- Public URL: **TODO BEFORE SUBMISSION: add verified deployment URL**
- Assurance Lab route: `/sandbox/`
- Completed succession route: `/run/opsroute-qwen-olmo/`
- Source: <https://github.com/faizanprofitpilot/InheritBench>
- Demo video: **TODO BEFORE SUBMISSION: add video URL**
- Expected current product decision: `CONDITIONAL_PASS`

## What a Developer Runs

A developer authors and validates a capability pack, freezes a supported model pair and recovery
strategy, and executes the succession locally:

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

An anchored run may pause at `ANCHORS_REQUIRED`. `succession add-anchors` records explicitly
authorized original examples, and `succession resume` continues the same frozen run without
regenerating completed teacher evidence.

## Five-Minute Browser Journey

After deployment:

1. Open the completed **Qwen → OLMo succession** and confirm that it is a projection of a local CLI
   run.
2. Open the **Assurance Lab**.
3. Select **Untouched OLMo** and run the diagnostic. Confirm that it receives no readiness verdict.
4. Select **Anchored successor** and run the evaluation. Confirm `CONDITIONAL_PASS`.
5. Apply **Approval bypass · apply and rerun**. Confirm the modified local result becomes
   `MIGRATION_BLOCKED`.
6. Reset the original predictions and confirm the verified reference result returns.
7. Expand record inspection and verification details.
8. Return to the completed succession to inspect model lineage, candidate ranking, final evaluation,
   adapter identity, replay, and raw evidence.

The browser performs real integrity verification, record evaluation, aggregation, safety checks,
readiness application, mutations, and local receipt generation. Progress is tied to those operations,
not simulated timers. It does not load Qwen or OLMo, train an adapter, create candidates, or select a
checkpoint from live model runs.

## Expected Current Product Result

The completed repaired multi-start reference must report:

- Clean operational correctness: `64 / 64`
- Clean exact-contract fidelity: `63 / 64`
- Clean strict validity: `64 / 64`
- Clean safety blockers: `0`
- Adversarial exact-contract result: `20 / 32`
- Adversarial strict validity: `31 / 32`
- Safety findings: `2 findings on 1 record`
- Readiness: `CONDITIONAL_PASS`
- Replay: `192 predictions verified`

The condition is substantive: one adversarial record produced both an unauthorized action and an
approval bypass. Clean capability recovery succeeded, but the evidence does not support an
unconditional migration or a claim of production safety.

## Browser Truth Boundary

### Runs in the browser

- integrity checks over committed product files;
- schema and contract validation;
- prediction evaluation and coverage aggregation;
- safety and readiness rules;
- controlled in-memory mutation and reset;
- local JSON/JSONL upload evaluation;
- replay/parity verification;
- unsigned local receipt generation.

### Remains precomputed

- Qwen and OLMo model loading;
- model inference;
- LoRA training and checkpoint production;
- four-seed candidate execution;
- final reference predictions.

The local receipt proves deterministic content and result hashing. It is not a signature,
notarization, identity proof, or external attestation.

## Clean-Clone Frontend Verification

Prerequisites:

- Git;
- Node `22.14.0`;
- pnpm `10.7.1` through Corepack;
- Chromium installed through Playwright.

```bash
git clone https://github.com/faizanprofitpilot/InheritBench.git
cd InheritBench
corepack enable
pnpm install --frozen-lockfile
pnpm --filter @inheritbench/web exec playwright install chromium
pnpm verify:web
```

The build ingests committed product data into the ignored `apps/web/public/data/` directory. No
ignored scientific `runs/` directory is required for the static product or browser tests.

## Clean-Clone Python Evidence Replay

Prerequisites:

- uv `0.11.28` or a compatible release;
- CPython `3.11.x`; `.python-version` pins `3.11.15`;
- no GPU, model weights, API key, or network after installation.

```bash
uv sync --frozen --no-dev
uv run --no-dev inheritbench succession replay --output runs
```

Expected console status:

```text
VERIFIED_REPLAY_COMPLETED runs/succession-replay-2b1798dad96176ff
```

The output directory contains:

```text
succession_run_manifest.json
readiness_report.json
replay_receipt.json
evaluation_summary.json
residual_failures.json
label_accounting.json
compute_accounting.json
adapter_reference.json
evidence_manifest.json
```

An identical replay returns the same byte-identical directory. A conflicting existing directory
fails instead of overwriting evidence. This command reconstructs the frozen Phase 3B product replay;
it is intentionally separate from the later repaired multi-start web projection.

## Historical Scientific Preflight

```bash
uv sync --frozen --extra model --group dev
uv run inheritbench succession preflight \
  --case opsroute-qwen-olmo \
  --mode full \
  --json -
```

This command checks prerequisites for the preregistered Phase 3B scientific workflow, not the
pack-driven `succession plan/run` sequence above. It verifies model dependencies, revisions, local
evidence, disk, memory, and accelerator availability. It requires at least 20 GiB free disk, warns
below 16 GiB RAM, and may fail on a machine without a supported execution environment. It does not
train.

Full execution requires the pinned Qwen and OLMo model downloads and ML dependencies. Apple MPS is
the only real training backend demonstrated by the reference work. CUDA and CPU device options are
not evidence of validated full reproduction.

## Evidence Tracks

The product deliberately preserves two distinct tracks:

1. **Historical Phase 3B evidence** — the frozen public adapter release and base-only Python replay.
2. **Current repaired multi-start product evidence** — the 64/64 operational result shown in the
   completed inspector and Assurance Lab.

The later product result does not rewrite the historical adapter, metrics, or readiness contract.
See [Pack-Driven Succession](PACK_DRIVEN_SUCCESSION.md) and the append-only
[Build Log](BUILD_LOG.md).

## Adapter Access

The historical release is a LoRA adapter for the pinned OLMo base, not a full checkpoint:

- Release: `phase3b-anchored-v0.1.0`
- Archive SHA-256: `f30fa5c814596a6c383be0390174275c893e1aba83d27df1dc8eec46c929f87f`
- [Download the verified adapter](https://github.com/faizanprofitpilot/InheritBench/releases/download/phase3b-anchored-v0.1.0/target_hybrid_anchored_distillation_10-7461072c83b4dcde.zip)

Users must obtain the pinned OLMo base separately and follow its model card and license.

## Verification Checklist

- [ ] Root page explains the capability-loss problem without requiring research context.
- [ ] Assurance Lab starts with Choose → Run → Review.
- [ ] Untouched OLMo remains diagnostic-only.
- [ ] Anchored successor returns the exact reference metrics above.
- [ ] Approval-bypass mutation changes the readiness result.
- [ ] Reset restores the verified reference result.
- [ ] Candidate selection states validation-only ranking and final evaluation exactly once.
- [ ] Evidence details expose hashes and record-level findings without changing the primary result.
- [ ] No browser action claims fresh training, inference, signature, or external attestation.
- [ ] No external runtime request, login, key, or backend is required.

**Codex `/feedback` Session ID:** `019f61c4-1e2b-7861-8e2c-7fe82c81255d`
