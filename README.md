# InheritBench

**Move the model. Keep the capability.**

InheritBench is a reproducible model-succession benchmark for measuring what happens to an
operational capability when an organization replaces one open-weight model family with another.
Day 1 establishes OpsRoute, a policy-aware enterprise action-routing capability spanning refund
routing and subscription cancellation/retention.

## Day 3 Synthetic Distillation

Day 3 adds `target_synthetic_distillation`: a fresh OLMo target trained only on independently
generated inputs and exact strict outputs from the verified Day 2 Qwen teacher. It preserves the
frozen OpsRoute splits, prompt/parser `0.1.0`, evaluator `v0`, model revisions, and seed `20260714`.

- The initial pool contains 512 balanced candidates, 32 per archetype. One fixed 256-candidate
  expansion is available only if strict filtering cannot supply 14 accepted examples per archetype.
- Leakage protection uses separate surface, full prompt-visible input, and value-sensitive typed
  semantic hashes. Opaque identifier values and request paraphrases do not conceal or create
  semantic collisions.
- The teacher never receives the evaluator-only oracle. Only strict JSON outputs exactly matching
  the deterministic policy contract can enter the 224-record synthetic training set.
- Scientific completion and public distribution are separate. A completed, replayed six-system
  comparison sets `DAY4_UNBLOCKED`; release failure can only set `PUBLICATION_BLOCKED`.
- Day 4 is never started automatically.

### Independent Day 3 Outcome

Day 3 stopped at its predeclared synthetic-data gate. The verified teacher completed all 768
candidates across the initial and single allowed expansion pools, but only 59 outputs were strict,
policy-exact, and safety-valid. Accepted outputs covered five of sixteen archetypes, so the required
224-record set with 14 examples per archetype could not be selected.

- Terminal dataset: `artifacts/day3/synthetic-data/day3-synthetic-dataset-9d186a0dde24549f`
- Result: `SCIENTIFICALLY_FAILED / DAY4_BLOCKED`
- Reason: `INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES`
- Distribution: `NOT_ATTEMPTED`; no target training, test evaluation, adapter, comparison, release,
  or Day 4 work was run.
- Both teacher runs and the 768-record filter replay exactly. Low teacher agreement remains visible;
  no parser repair, quality retry, prompt change, or label rewriting was used.

### Distribution-Matched Recovery Outcome

The final bounded recovery matched the frozen train distribution exactly and improved strict
teacher acceptance from 59/768 (`7.68%`) to 719/768 (`93.62%`). Fifteen archetypes met the quota,
but duplicate auto-refund reached only 4/48 accepted outputs, below the frozen minimum of 14.

- Terminal dataset: `artifacts/day3-matched/synthetic-data/day3-matched-synthetic-dataset-36eea02e066b021a`
- Result: `RECOVERY_TERMINAL_NEGATIVE / DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT`
- Reason: `INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES`
- Distribution: `NOT_ATTEMPTED`; no target training, held-out test, adapter, six-row comparison, or
  release exists.
- Fingerprint, both distribution/leakage audits, both teacher runs, filtering, failure analysis,
  attempt comparison, and recovery decision replay exactly.
- No third Day 3 attempt or automatic Day 4 work is permitted.

## Current Day 2 Outcome

Day 2 trains and evaluates the learned capability across five frozen systems on the same 32-record
test split. The source capability gate passed every criterion before any test evaluation.

| Method | Unique train records | Processed tokens | Semantic exact | Strict valid |
|---|---:|---:|---:|---:|
| `source_base_supporting` | 0 | 0 | 0.000% | 40.625% |
| `source_adapted_full` | 224 | 379,768 | 96.875% | 100.000% |
| `target_untouched` | 0 | 0 | 0.000% | 0.000% |
| `target_full_retrain` | 224 | 272,643 | 100.000% | 100.000% |
| `target_limited_retrain_10pct` | 24 | 272,634 | 84.375% | 93.750% |

- The limited condition uses 24/224 unique examples (`10.7142857%`) and matches the full-target
  processed-token budget to `99.996699%` without truncating an example.
- Selected source, full-target, and limited-target checkpoints have zero unauthorized actions,
  approval bypasses, or false actions on validation and final test.
- All five final runs replay exactly. The machine-readable comparison is under
  `artifacts/day2/comparisons/day2-comparison-8d0e9e5ac1494449`.
- Adversarial evaluation, repeated seeds, and UI work remain untouched. Day 3 is reported separately.

The three selected LoRA adapters remain outside Git and are published as deterministic assets in
the [Day 2 v0.1.0 release](https://github.com/faizanprofitpilot/InheritBench/releases/tag/day2-v0.1.0).
All public downloads match their recorded SHA-256 hashes; immutable verification metadata lives
under `artifacts/day2/publications`.

Release lineage is intentionally immutable: scientific execution is captured at `78e616b`, the
`day2-v0.1.0` tag resolves to `d731dba` after adding deterministic release checksums, and post-tag
`main` history beginning at `33a9dc5` contains only public-download verification and documentation.
No scientific run, adapter, prediction, metric, or release archive changed after `78e616b`.

## Day 1 Scope

The implemented vertical slice is:

```text
validated configuration
→ deterministic OpsRoute v0.1 data
→ pinned Qwen source-base and OLMo target-base inference
→ strict parsing
→ deterministic atomic scoring
→ immutable run artifacts
→ exact metric replay
```

Training, PEFT, distillation, synthetic data, UI work, provider abstractions, and a weighted
composite score are deliberately excluded.

## Current Day 1 Outcome

- The 320-record dataset is frozen and byte-reproducible at
  `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`.
- Qwen→OLMo and Qwen→SmolLM2 both load on MPS, confirm architecture heterogeneity, and confirm
  incompatible configured projection shapes.
- All real runs finalized eight terminal predictions and replayed exactly.
- Qwen produced schema-valid outputs under prompt `0.1.0`; neither OLMo nor the fallback SmolLM2
  produced a schema-valid output under the original or one simplified prompt contract.
- Day 1 is therefore **blocked at the target structured-output quality gate**. Invalid outputs remain
  visible and score zero; no parser repair or result substitution was used.
- The Modal L4 invocation was rejected before execution by the environment's external data-export
  approval gate. A local `BLOCKED` artifact records zero remote attempts and no GPU allocation.

The strongest completed fallback run is
`artifacts/runs/day1-20260714T191408-b65f0439`; its exact replay is
`artifacts/replays/replay-20260714T192011-50b1712a`.

## Blocker-Resolution Outcome

- Preserved target failures were schema-compliance failures; no inference/runtime defect was found.
- Untouched OLMo remained 0/8 schema-valid on a fixed validation diagnostic, with every generation
  ending on EOS. The correct baseline classification is
  `UNTOUCHED_TARGET_HAS_ZERO_SCHEMA_VALIDITY; TARGET_TRAINABILITY_UNTESTED`.
- A bounded 32-example LoRA gate improved Qwen from 3/8 to 8/8 schema-valid on the validation subset.
- The successful OLMo run `micro-lora-target_micro_lora-20260714T195848-79e58f44` produced 7/8
  schema-valid and 2/8 semantic-exact contracts with finite decreasing loss and exact replay.
- Final decision: `OLMO_TRAINABILITY_CONFIRMED`. SmolLM2 fallback training was not triggered.
- Machine-readable decision: `artifacts/blocker-resolution/decision/decision-77a945960ddfdb7e`.
- This blocker-resolution sprint scientifically unblocked the later Qwen→OLMo Day 2 execution.
  Modal remained unavailable because external workspace-export approval was not granted.

Blocker evidence lives under `artifacts/blocker-resolution`; adapters are separate under
`adapters/blocker-resolution`. Existing Day 1 artifacts remain unchanged.

## Quick Start

```bash
uv sync --frozen --extra model --extra modal --group dev
uv run inheritbench --version
uv run ruff check .
uv run mypy src
uv run pytest -m "not model_smoke and not modal"
```

Verify Day 2 configuration and frozen schedules:

```bash
uv run inheritbench day2 validate-configs
uv run inheritbench day2 freeze-data
```

The production Day 2 command group also provides `train`, `recover`, `evaluate`, `source-gate`,
`replay`, `compare`, `package-adapters`, and `verify-release`. Every finalization refuses overwrite.

Run the guarded Day 3 sequence:

```bash
uv run inheritbench day3 validate-configs
uv run inheritbench day3 freeze-pool
uv run inheritbench day3 verify-teacher
uv run inheritbench day3 run-teacher --pool initial --device mps
uv run inheritbench day3 filter
# Only when the filter reports NEEDS_EXPANSION:
uv run inheritbench day3 expand-pool
uv run inheritbench day3 run-teacher --pool expansion --device mps
uv run inheritbench day3 filter
# Stop when the terminal filter reports FAILED. Continue only after COMPLETED:
uv run inheritbench day3 freeze-schedule
uv run inheritbench day3 train --device mps
uv run inheritbench day3 evaluate --split test --device mps
```

The remaining Day 3 commands provide replay, failure analysis, six-row comparison, separate
scientific/distribution finalization, deterministic adapter packaging, and public release
verification. Every command fails closed on missing or mismatched lineage.

Replay the final matched recovery:

```bash
uv run inheritbench day3-matched validate-configs
uv run inheritbench day3-matched freeze-baseline
uv run pytest -q tests/integration/test_day3_matched_artifacts.py
```

Generate or verify the committed dataset:

```bash
uv run inheritbench data generate \
  --config configs/tasks/opsroute.yaml \
  --output data/opsroute/v0.1.0

uv run inheritbench data generate \
  --config configs/tasks/opsroute.yaml \
  --output data/opsroute/v0.1.0 \
  --check
```

Run the real Day 1 path:

```bash
uv run inheritbench doctor \
  --source configs/models/source.yaml \
  --target configs/models/target.yaml \
  --task configs/tasks/opsroute.yaml \
  --check-hub \
  --json artifacts/day1/doctor.json

uv run inheritbench inspect-pair \
  --source configs/models/source.yaml \
  --target configs/models/target_fallback.yaml \
  --mode loaded

uv run inheritbench infer \
  --source configs/models/source.yaml \
  --target configs/models/target_fallback.yaml \
  --task configs/tasks/opsroute.yaml \
  --examples data/opsroute/v0.1.0/smoke_ids.json \
  --device auto \
  --output-root artifacts/runs

uv run inheritbench evaluate \
  --run artifacts/runs/<run-id> \
  --verify-stored \
  --output-root artifacts/replays
```

## Architecture

- `configs/` contains validated, pinned manual identity and policy choices.
- `src/inheritbench/data/` owns deterministic examples and evaluator-owned labels.
- `src/inheritbench/evaluation/` owns parsing and all scores.
- `src/inheritbench/models/` owns pinned loading, native chat prompts, and inspection.
- `src/inheritbench/inference/` owns sequential inference and replay.
- `src/inheritbench/day2/` owns learned-method configs, schedules, training, checkpoint selection,
  source gating, final comparison, replay, and release packaging.
- `src/inheritbench/day3/` owns independent candidate generation, value-sensitive leakage audits,
  verified teacher inference, strict synthetic filtering, target training, replay, status decisions,
  and one-adapter publication.
- `src/inheritbench/day3_matched/` owns the isolated final distribution-matched recovery, exact
  train-fingerprint audits, terminal-negative status, replay, and independent publication lineage.
- `src/inheritbench/artifacts/` owns canonical hashes and no-overwrite finalization.
- `artifacts/` contains run evidence; no UI or prose document is scoring truth.

## Artifact Truth Hierarchy

1. Raw prediction records and exact expected contracts.
2. Deterministically recomputed parser results and atomic metrics.
3. Immutable run summaries and manifests with verified byte hashes.
4. Documentation that cites those artifacts.

Fixture IDs always begin with `fixture_` and are rejected as benchmark evidence. Failed model work
is recorded as `FAILED`; parser invalidity remains a completed inference with an explicit invalid
parser result. Unrun work is never represented as a zero score.

## Limitations

- Day 1 evaluates four held-out smoke examples per base model, not full benchmark quality.
- A single deterministic generation seed does not establish statistical significance.
- Exact model output identity is not claimed across hardware backends.
- LoRA targets are structural observations only and remain provisional.
- Modal is a bounded preflight, not a training or orchestration platform.
- The blocker-resolution trainability gate uses 32 train and eight validation examples; it is not a
  full benchmark result, and its semantic exactness remains limited.
- Day 2 uses one deterministic seed and one model pair; it does not establish statistical
  significance or generalize beyond OpsRoute v0.1.0.
- `semantic_decision_score_v0` remains exact full ActionContract equality, not a broader
  normalized decision-only score.
- MPS memory values are allocation snapshots, not peak-memory measurements.
- Day 3 synthetic examples still depend upstream on 224 original labels used to train the source
  teacher; the method is not described as label-free.
- Public adapter distribution is not evidence of scientific validity, and publication failure does
  not revise a completed scientific decision.
- The frozen Day 3 teacher produced only 59 accepted outputs across five archetypes, so no synthetic
  target was trained and no six-row comparison exists. This is a failed scientific gate, not a zero
  benchmark score.
- The matched recovery is a distinct final attempt. It preserves the independent failure and permits
  either a replayed completed result or a replayed terminal negative to unblock Day 4; it never starts
  Day 4 automatically.

See `docs/METHOD_SYNTHETIC_DISTILLATION.md`, `docs/JUDGE_REPLAY.md`,
`docs/EVALUATION_PROTOCOL.md`, `docs/COMPUTE_PLAN.md`, and `docs/LICENSING.md` for the scientific,
compute, replay, and licensing contracts.
