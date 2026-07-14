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

## 2026-07-14 — Blocker-Resolution Diagnosis

- Diagnosed all 16 preserved OLMo and SmolLM2 target outputs at
  `artifacts/blocker-resolution/diagnosis/diagnosis-a617178ecb317ada`.
- Observed task-directed JSON in every output. Failure forms were malformed JSON, valid JSON with
  the wrong schema, missing required fields, wrong enums/tools, and one repetitive malformed output.
- Found no verified inference/runtime defect. Native templates accepted the supplied roles, prompt
  and input-ID hashes matched, prompt lengths stayed below 1,024, completion slicing was correct,
  and model/tokenizer revisions matched configs.
- Added backward-compatible prompt/output token counts, resolved EOS IDs, finish conditions, and
  completion-only decoding regression coverage for new predictions.

## 2026-07-14 — Controlled Validation Diagnostics

- Froze eight validation IDs and 32 train IDs at
  `artifacts/blocker-resolution/subsets/subsets-c0e0abb99d3f9e7d`.
- Untouched OLMo run `diagnostic-20260714T194526-544a6811` completed 8/8 generations, all ending
  on EOS after 23–28 generated tokens. It produced 8/8 valid JSON objects and 0/8 schema-valid
  contracts, ruling out max-token truncation for this diagnostic subset.
- Untouched Qwen run `diagnostic-20260714T195815-8d4219d2` produced 3/8 schema-valid and 0/8
  semantic-exact contracts on the same validation subset.
- Both diagnostic runs replayed exactly under `artifacts/blocker-resolution/replays`.

## 2026-07-14 — Micro-LoRA Trainability Gates

- Added locked `peft==0.19.1`; no Datasets, TRL, bitsandbytes, or full Day 2 matrix was added.
- Configuration 1: rank 8, alpha 16, dropout 0.05, AdamW, learning rate 0.0002, batch size 1,
  accumulation 4, two epochs, float32 MPS, fixed order, seed `20260714`, and attention targets
  `q_proj`, `k_proj`, `v_proj`, `o_proj`.
- Source run `micro-lora-source_micro_lora-20260714T195119-5b707d58`: loss 1.1359→0.6712,
  8/8 schema-valid and 0/8 semantic-exact validation contracts. A later duplicate run occurred
  because artifact finalization outlived polling; the immutable correction is
  `artifacts/blocker-resolution/corrections/correction-8f21fbaa169460c8`.
- OLMo configuration-1 run `micro-lora-target_micro_lora-20260714T195432-b12b2708`: loss
  1.4788→0.5775, 8/8 schema-valid and 0/8 semantic-exact contracts.
- Because configuration 1 established stable formatting but no semantic exactness, the one allowed
  second configuration changed only epochs from 2 to 6.
- OLMo configuration-2 run `micro-lora-target_micro_lora-20260714T195848-79e58f44`: loss
  1.4788→0.0428, 7/8 schema-valid and 2/8 semantic-exact contracts. Exact replay passed.
- Decision: `OLMO_TRAINABILITY_CONFIRMED`. SmolLM2 fallback training was not triggered.
- Final machine-readable decision:
  `artifacts/blocker-resolution/decision/decision-77a945960ddfdb7e/decision.json`.

## 2026-07-14 — Modal Blocker Classification

- Re-inspection confirms `artifacts/modal/modal-smoke-20260714T192115-de421316.json` records an
  interactive external data-export/Codex execution-permission block, not authentication, billing,
  profile, package, network, model, or benchmark failure.
- Attempts remain zero; the blocked invocation is not counted as a remote GPU attempt.
- Local MPS completed the bounded trainability work, so Modal remains an infrastructure limitation.

## 2026-07-14 — Blocker-Resolution Final Gates

- Ruff lint passed; all 53 files passed the format check.
- Strict mypy passed for 32 source files.
- Offline pytest passed: 35 selected tests passed and one real-model smoke test was deselected.
- Dataset regeneration verified the unchanged 320-record dataset SHA-256
  `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`.
- Frozen `uv` sync passed with 76 installed packages checked.
- All 24 pre-sprint artifact files captured by the diagnosis baseline retained their exact byte
  hashes. Parser behavior and every Day 1 artifact remain unchanged.
