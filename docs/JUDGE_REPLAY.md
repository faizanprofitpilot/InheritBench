# Judge Replay

This guide tests the InheritBench developer product without rebuilding a dataset, downloading model
weights, retraining OLMo, or calling an API.

## Current Status

- Product: `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY`
- Deployment: `DEPLOYMENT_REQUIRED`
- Public URL: **TODO BEFORE SUBMISSION: add verified deployment URL**
- Supported case: `opsroute-qwen-olmo`
- Expected decision: `CONDITIONAL_PASS`
- Expected local replay time: typically under five seconds after installation
- Expected browser replay time: under two seconds on a typical laptop

Do not interpret the missing public URL as a product failure. The static export, Node-only build,
Python replay, frontend tests, and browser tests pass; hosted verification remains outstanding.

## Five-Minute Hosted Journey

After deployment:

1. Open the public root page in an incognito Chromium window.
2. Select **Run verified succession replay**.
3. Review the locked OpsRoute, Qwen, OLMo, and Anchored Behavioral Transfer configuration.
4. Confirm the preflight states that no training, inference, model download, GPU, or API key is used.
5. Run the replay and observe the real verification operations.
6. Confirm **Verified succession replay completed** and `CONDITIONAL_PASS`.
7. Download `readiness_report.json` and `replay_receipt.json`.
8. Open the recovered successor adapter, residual failures, GPT-5.6 memo, and evidence views.
9. Run **Showcase integrity verification** in the evidence page.

The browser session validates the committed manifest and compact replay records, verifies hashes,
derives clean and adversarial aggregates, classifies residuals, applies readiness rules, confirms
adapter identity, and generates fresh downloads. It does not rerun models.

## Clean-Clone Local Replay

Prerequisites:

- Git
- uv `0.11.28` or a compatible current uv release
- CPython `3.11.x`; `.python-version` pins `3.11.15`
- no GPU, model weights, API key, or network after installation

```bash
git clone https://github.com/faizanprofitpilot/InheritBench.git
cd InheritBench
uv sync --frozen --no-dev
uv run --no-dev inheritbench succession replay \
  --case opsroute-qwen-olmo \
  --profile maximum-confirmed-capability \
  --output runs
```

Expected console status:

```text
VERIFIED_REPLAY_COMPLETED runs/succession-replay-2b1798dad96176ff
```

The deterministic run contains:

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

An identical second command returns the existing byte-identical run. A conflicting directory fails
instead of overwriting evidence.

## Expected Result

`readiness_report.json` must report `CONDITIONAL_PASS` because:

- clean decision, tool, argument, approval, and reason-code correctness are all 64/64;
- clean strict validity is 64/64;
- clean unauthorized actions, approval bypasses, and false actions are zero;
- nine clean full-contract misses differ only in the exact `policy_code` literal;
- adversarial semantic exactness is 20/32;
- adversarial evidence contains one unauthorized action and one approval bypass.

The correct product interpretation is:

> Clean capability recovery succeeded, but adversarial robustness remains insufficient for an
> unconditional migration pass.

`label_accounting.json` must disclose 214 teacher outputs and 10 direct original anchors used by
the target, plus 224 upstream original labels used to train the teacher and the original 224-label
corpus used to design the matched distribution.

## Adapter Access

The delivered artifact is a LoRA adapter for the pinned OLMo base, not a full checkpoint.

- Adapter ID: `target_hybrid_anchored_distillation_10-7461072c83b4dcde`
- Release: `phase3b-anchored-v0.1.0`
- Archive SHA-256: `f30fa5c814596a6c383be0390174275c893e1aba83d27df1dc8eec46c929f87f`
- Adapter model SHA-256: `ebf598fcfce095f599ccec16621c5f31256ec6abdf17fc5b65b966c01f148d84`
- [Download the verified adapter](https://github.com/faizanprofitpilot/InheritBench/releases/download/phase3b-anchored-v0.1.0/target_hybrid_anchored_distillation_10-7461072c83b4dcde.zip)

The publication artifact records an anonymous byte verification against the release.

## Full-Workflow Preflight

To inspect prerequisites and the actual preregistered phased workflow:

```bash
uv sync --frozen --extra model --group dev
uv run inheritbench succession preflight \
  --case opsroute-qwen-olmo \
  --mode full \
  --json -
```

Preflight may honestly return `FAILED` on a machine without sufficient disk, model dependencies, or
an accelerator. It does not train. When ready, it prints the existing Phase 3B commands for data
freeze, leakage audit, preregistration, training, validation, checkpoint selection, held-out test,
replay, analysis, packaging, and release verification.

## Evidence Verification

Product-level replay:

```bash
uv run --no-dev inheritbench succession replay --output runs
```

Phase 5 projection verification:

```bash
uv sync --frozen --group dev
uv run inheritbench phase5 verify-web-projection
```

Complete local product gates:

```bash
pnpm install --frozen-lockfile
pnpm verify
```

The browser calls its check **Showcase integrity verification**. It verifies served committed files;
it is not a live scientific replay.

## Supported Platforms

- Hosted product: Chromium desktop and mobile emulation are verified.
- Local GPU-free replay: macOS Apple Silicon is verified locally; Linux is verified in CI.
- Full model workflow: Apple Silicon MPS is the executed and verified backend.
- Firefox, Safari, Windows, CUDA, and Linux GPU training are not claimed as verified.

## Troubleshooting

| Symptom | Meaning | Action |
|---|---|---|
| Replay reports a hash mismatch | Committed input or bundle bytes differ | Restore a clean checkout; do not repair the artifact manually |
| Existing output conflict | The deterministic run directory contains different bytes | Choose an empty output root or preserve the directory for investigation |
| Full preflight reports low disk | Real model workflow needs at least 20 GiB free | Free disk or use replay-only mode |
| Full preflight reports CPU-only | The executed training path expects MPS | Use replay-only mode or an explicitly supported future backend |
| Browser integrity check fails | A served static file is missing or changed | Stop judging that deployment and rebuild from committed data |
| Adapter link fails | Public distribution is unavailable | Preserve the replay result but treat adapter delivery as blocked |

## Truth Boundary

```text
succession_run_manifest.json
        ↓
immutable referenced scientific artifacts
        ↓
compact deterministic replay records
        ↓
browser or CLI replay engine
        ↓
fresh readiness report + replay receipt
```

For deeper scientific chronology, use [Evaluation Protocol](EVALUATION_PROTOCOL.md),
[Anchored Behavioral Transfer](METHOD_ANCHORED_TRANSFER.md), and the append-only
[Build Log](BUILD_LOG.md).
