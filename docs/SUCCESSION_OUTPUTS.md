# Succession Output Contract

The verified replay produces a fresh deterministic product run from a frozen succession manifest and
compact atomic records. It does not copy or rewrite scientific evidence.

## Run Directory

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

## Files

### `succession_run_manifest.json`

Defines run and case identity, locked configuration, schema versions, compact replay files, immutable
source references, ordered verification operations, readiness-rule version, and adapter publication
identity. It does not contain a precomputed readiness decision.

### `readiness_report.json`

Contains the newly derived `BLOCK`, `PASS`, or `CONDITIONAL_PASS` decision, reason code, clean gates,
adversarial blockers, and hashes of the derived summary and residual analysis.

### `replay_receipt.json`

Records `VERIFIED_REPLAY_COMPLETED`, the manifest and record hashes, each passed operation, and the
readiness report hash. The receipt proves what the product replay checked; it is not proof of fresh
model execution.

### `evaluation_summary.json`

Separates:

- untouched-target clean confirmatory metrics;
- recovered-successor clean confirmatory metrics;
- recovered-successor adversarial metrics.

No blended cross-surface score is produced.

### `residual_failures.json`

Lists the nine clean policy-code aliases and adversarial profile counts. Clean residual classification
requires correct decision, tool, arguments, approval, reason code, strict validity, and safety facts.

### `label_accounting.json`

Discloses 214 teacher labels, 10 direct original anchors, 224 target records, 224 upstream original
teacher labels, and the original 224-label distribution-design corpus.

### `compute_accounting.json`

Records source-teacher, teacher-generation, and target-training tokens and durations, target optimizer
steps, and trainable parameters. It distinguishes incremental target cost from upstream cost.

### `adapter_reference.json`

Identifies the recovered OLMo LoRA adapter, pinned base revision, release, archive SHA-256, archive
bytes, internal adapter file hashes, verified publication record, and public release URL.

### `evidence_manifest.json`

References immutable source artifacts by safe repository-relative path, byte hash, content hash, and
byte count. Scientific artifacts remain in their original content-addressed locations.

## Deterministic Identity

The run ID is derived from capability identity, compact-record identity, replay context, and readiness
rule version. Timestamps and local paths do not affect it.

## Idempotency and No Overwrite

- If the destination does not exist, the product writes it atomically.
- If an existing destination is byte-identical, replay returns it unchanged.
- If an existing destination differs, replay fails with an output conflict.

The downloadable browser report and receipt follow the same deterministic specification, but browser
downloads are session outputs rather than repository scientific artifacts.

## Verification Boundary

The product aggregates already validated atomic records. It does not claim to rerun the historical
model, tokenizer, prompt rendering, or scientific parser in the browser. The Python scientific
workflow and immutable raw predictions remain available for deeper replay.
