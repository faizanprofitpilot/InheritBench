# InheritBench

**Move the model. Keep the capability.**

InheritBench is a reproducible model-succession benchmark for measuring what happens to an
operational capability when an organization replaces one open-weight model family with another.
Day 1 establishes OpsRoute, a policy-aware enterprise action-routing capability spanning refund
routing and subscription cancellation/retention.

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
- Adversarial evaluation, distillation, repeated seeds, UI work, and Day 3 remain untouched.

The three selected LoRA adapters remain outside Git and are published as deterministic assets in
the [Day 2 v0.1.0 release](https://github.com/faizanprofitpilot/InheritBench/releases/tag/day2-v0.1.0).
All public downloads match their recorded SHA-256 hashes; immutable verification metadata lives
under `artifacts/day2/publications`.

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

See `docs/EVALUATION_PROTOCOL.md`, `docs/COMPUTE_PLAN.md`, and `docs/LICENSING.md` for the
scientific, compute, and licensing contracts.
