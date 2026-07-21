# Succession Output Contract

InheritBench has two output contracts. A pack-driven CLI succession writes the model-execution,
selection, readiness, adapter, and replay evidence under `runs/<run-id>/`. The separate base-only
historical replay reconstructs a nine-file Phase 3B report from a frozen manifest and compact atomic
records. Neither path copies or rewrites scientific evidence.

## Historical Phase 3B Replay Directory

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

## Pack-Driven CLI Execution Output

The v0.2 local engine writes a separate task-neutral run:

```text
runs/<run-id>/
├── plan.json
├── plan.sha256
├── input_manifest.json
├── run.json
├── execution_log.jsonl
├── evaluation_summary.json
├── readiness_report.json
├── residual_failures.json
├── label_accounting.json
├── compute_accounting.json
├── adapter_reference.json
├── evidence_manifest.json
├── web_bundle.json
├── stages/
├── checkpoints/
├── successor/
└── replays/<replay-id>/
    ├── replay_manifest.json
    └── replay_receipt.json
```

`plan.json` binds the exact pack validation hash, every authorized pack file, source and target
config hashes, registry identities, optional source-adapter hash, strategy profile, device, seed,
operation order, and deterministic run ID.

Each immutable `stages/<sequence>-<stage>/stage.json` stores its parent hash and normalized payload.
The only mutable pointer is `runs/.active/<run-id>/state.json`; it is removed after finalization.

For anchored transfer, `ANCHORS_REQUIRED` is a valid persisted intervention. `export-web` can
produce an intervention bundle before training. Added anchors are immutable under `interventions/`,
and resume reuses completed teacher work.

`succession replay --run` validates planned input and adapter hashes, rebuilds summaries, residuals,
and readiness from saved atomic records, compares the result with stored files, and writes a fresh
receipt without loading model weights.

`succession export-web` writes `web_bundle.json`. The local inspector at `/run/local/` validates and
renders that bundle in browser memory; the browser does not train, infer, select, export an adapter,
or mutate the CLI run.

The committed current product projection is a third presentation artifact generated from the
repaired reference execution. It verifies 192 direct and anchored predictions and must not be
confused with the 160-record historical Phase 3B replay described above.

## Verification Boundary

The product aggregates already validated atomic records. It does not claim to rerun the historical
model, tokenizer, prompt rendering, or scientific parser in the browser. The Python scientific
workflow and immutable raw predictions remain available for deeper replay.
