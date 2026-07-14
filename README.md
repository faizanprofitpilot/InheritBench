# InheritBench

**Move the model. Keep the capability.**

InheritBench is a reproducible model-succession benchmark for measuring what happens to an
operational capability when an organization replaces one open-weight model family with another.
Day 1 establishes OpsRoute, a policy-aware enterprise action-routing capability spanning refund
routing and subscription cancellation/retention.

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

## Quick Start

```bash
uv sync --frozen --extra model --extra modal --group dev
uv run inheritbench --version
uv run ruff check .
uv run mypy src
uv run pytest -m "not model_smoke and not modal"
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

See `docs/EVALUATION_PROTOCOL.md`, `docs/COMPUTE_PLAN.md`, and `docs/LICENSING.md` for the
scientific, compute, and licensing contracts.
