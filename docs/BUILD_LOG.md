# Build Log

This file is append-only. Results are recorded only after the corresponding command completes.

## 2026-07-14 — Repository Assessment

- Confirmed branch `main` at starting commit `d5e7ea243435a42875eb3cb6e96e4b34fe253706`.
- Confirmed the only starting project file was `INHERITBENCH_HACKATHON_IDEA_AND_PROJECT_PLAN.md`.
- Confirmed macOS arm64, Apple M2 Pro, 32 GB unified memory, and a local MPS path.
- Confirmed `uv 0.11.28` and uv-managed CPython 3.11.15; system Python 3.14 is unsupported.
- Confirmed no Hugging Face token and an existing local Modal credential profile.

## 2026-07-14 — Day 1 Implementation

- Added a Python 3.11/Hatchling/uv package with a Typer CLI and lazy optional-model imports.
- Added strict model/task configs, deterministic OpsRoute generation, and frozen policy resolvers.
- Added strict/fenced-only parsing, atomic metrics, canonical hashing, and atomic no-overwrite stores.
- Added doctor, pair inspection, sequential inference, replay, and bounded Modal smoke paths.
- Added offline unit/golden/integration tests and opt-in real-model/Modal markers.

## 2026-07-14 — Locked Environment and Offline Gates

- `uv lock` resolved 96 packages and created `uv.lock` under CPython 3.11.15.
- `uv sync --extra model --extra modal --group dev` installed the exact locked environment.
- Ruff lint and format checks passed.
- Strict mypy passed for 26 source files.
- Offline pytest passed: 26 tests selected after final updates, with real-model and Modal tests
  excluded by markers.

## 2026-07-14 — Dataset and Doctor

- Generated and exact-byte regenerated 320 records at `data/opsroute/v0.1.0`.
- Dataset SHA-256:
  `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`.
- Split counts: 224 train, 32 validation, 32 test, 32 adversarial.
- Generated 16 `fixture_`-prefixed records at `tests/fixtures/opsroute_fixture.jsonl`.
- Qwen/OLMo doctor artifact `artifacts/day1/doctor.json`: `PASS`.
- Qwen/SmolLM2 doctor artifact `artifacts/day1/doctor-fallback.json`: `PASS`.

## 2026-07-14 — Loaded Pair Inspection

- Qwen→OLMo artifact:
  `artifacts/inspections/4b0ee6c845f4b5037798f514069ef00d57fe3ea91b3f63b924472f2452beef94.json`.
- Observed 494,032,768 Qwen parameters and 1,484,916,736 OLMo parameters.
- Verdicts: `CONFIRMED` heterogeneity and `STRUCTURALLY_INCOMPATIBLE` direct adapter reuse.
- Qwen→SmolLM2 artifact:
  `artifacts/inspections/ab803018319e505431a9dd07962e102456f7dc25ee44a1b81bcce563d93b8527.json`.
- Observed 1,711,376,384 SmolLM2 parameters.
- Verdicts: `CONFIRMED` heterogeneity and `STRUCTURALLY_INCOMPATIBLE` direct adapter reuse.

## 2026-07-14 — Real MPS Runs

- `day1-20260714T190135-509b1711`: Qwen→OLMo, prompt `0.1.0`, eight completed
  predictions; source valid 2/4, target valid 0/4.
- `day1-20260714T190338-73d05f81`: Qwen→OLMo, prompt `0.1.1`, eight completed
  predictions; source valid 0/4, target valid 0/4.
- Activated the predeclared fallback after OLMo failed both prompt quality checks.
- `day1-20260714T191408-b65f0439`: Qwen→SmolLM2, prompt `0.1.0`, eight completed
  predictions; source valid 2/4, target valid 0/4.
- `day1-20260714T191535-73a725e2`: Qwen→SmolLM2, prompt `0.1.1`, eight completed
  predictions; source valid 0/4, target valid 0/4.
- No infrastructure failures were hidden. All invalid raw outputs and parser errors are preserved.

## 2026-07-14 — Replay and Modal

- Exact replay passed at `artifacts/replays/replay-20260714T192011-50b1712a` for run
  `day1-20260714T191408-b65f0439`.
- The final frozen-gate replay also passed at
  `artifacts/replays/replay-20260714T192223-df6d0a36`.
- Original prediction and summary byte hashes, every parser result, every metric, and the aggregate
  summary matched.
- The Modal L4 invocation was rejected before execution by the external data-export approval gate.
- Recorded `BLOCKED` with zero remote attempts at
  `artifacts/modal/modal-smoke-20260714T192115-de421316.json`; no GPU was allocated.

## 2026-07-14 — Day 1 Gate Status

- Foundation, dataset, loading, inspection, inference traversal, immutability, and replay gates pass.
- Day 2 is blocked because neither target candidate produced a strict or fenced-schema-valid output
  after the original and one simplified prompt contract. The kill switch stops further pair search.
