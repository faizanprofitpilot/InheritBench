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

## 2026-07-15 — Day 2 Foundation and Data Freeze

- Added strict Day 2 method, schedule, training, checkpoint, evaluation, gate, comparison, replay,
  and publication schemas without changing historical v0.1 artifacts.
- Froze all 224 train IDs, all 32 validation IDs, all 32 final-test IDs, and 24 deterministic
  limited-train IDs under `artifacts/day2/data/day2-data-01c2e470b9ccf379`.
- Measured source schedule: 896 exposures, 224 optimizer steps, 379,768 tokens.
- Measured full-target schedule: 672 exposures, 168 optimizer steps, 272,643 tokens.
- Measured limited-target schedule: 672 exposures, 168 optimizer steps, 272,634 tokens, nine-token
  residual, and 27–29 exposures per selected ID.
- Baseline validation: source base 0/32 semantic exact and 15/32 strict valid; untouched target 0/32
  semantic exact and 0/32 strict valid.

## 2026-07-15 — Source Training and Capability Gate

- Primary source run `day2-train-source_adapted_full-20260714T205718-88ddf6a1` hit the declared
  numerical-instability kill switch at step 150 after a gradient norm of 4,344,363.5. It finalized
  `FAILED`; no result was represented as zero or silently discarded.
- Applied the one allowed correction: restart from base at learning rate `1e-4`, with all other
  scientific settings and the 224-step schedule unchanged.
- Corrected source run `day2-train-source_adapted_full-20260714T210427-d8bcfeac` completed 224
  steps and 379,768 tokens in 437.86 seconds.
- Selected step 224 through decision `checkpoint-decision-source_adapted_full-80d431c7fdec` after
  fresh-base validation of all four checkpoints.
- Source gate `source-gate-e5260bac406148a8` is `SOURCE_CAPABILITY_CONFIRMED`: adapted validation
  reached 30/32 semantic exact, 32/32 strict valid, and passed every family, correctness, and safety
  criterion.

## 2026-07-15 — Target Training

- Full-target run `day2-train-target_full_retrain-20260715T054943-e8956f73` completed 168 steps and
  272,643 tokens in 617.31 seconds. Step 168 reached 32/32 semantic exact and strict valid on
  validation with zero safety violations.
- Limited-target run `day2-train-target_limited_retrain_10pct-20260715T060429-97a41daf` completed
  the frozen 272,634-token schedule in 635.43 seconds. Step 168 reached 27/32 semantic exact and
  30/32 strict valid on validation with zero safety violations.
- Selected decisions are `checkpoint-decision-target_full_retrain-537ccf64dfc3` and
  `checkpoint-decision-target_limited_retrain_10pct-3d89c02acba8`.

## 2026-07-15 — Final Test and Replay

- Ran the five frozen methods exactly once on all 32 test records after source confirmation and
  checkpoint freeze.
- Test semantic/strict results: source base 0.000%/40.625%; adapted source 96.875%/100.000%;
  untouched target 0.000%/0.000%; full target 100.000%/100.000%; limited target
  84.375%/93.750%.
- All five final runs replayed exactly under `artifacts/day2/replays`.
- Final comparison `day2-comparison-8d0e9e5ac1494449` reports semantic retention of 103.226% for
  full target and 87.097% for limited target relative to adapted source.

## 2026-07-15 — Day 2 Gates and Release Packaging

- Ruff lint and format checks passed; strict mypy passed for 41 source files.
- Offline pytest passed: 48 selected tests passed and one real-model smoke test was deselected.
- Dataset regeneration retained SHA-256
  `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`.
- Frozen `uv` sync checked all 76 locked packages.
- Pushed Day 2 code and scientific evidence at commit
  `78e616bdd852b95766936e7dba8966938c2fe760`.
- Packaged three deterministic adapter archives under publication
  `day2-publication-78674991ed2241c1`; ZIP files remain ignored by Git.
- Archive hashes: source `8ee07058b71056bf7119582eb15f9fee4febf20b60f8942efa470be44b84a007`,
  full target `cf92573ba50db6cda9788ce5d43840609bed007092c70562581d60cb227b0894`, and
  limited target `0e23bffa48f11206da39ee988f9f4943eef415c2629d93a1637ec68b2f950118`.

## 2026-07-15 — Public Release Verification

- Published tag `day2-v0.1.0` at
  `https://github.com/faizanprofitpilot/InheritBench/releases/tag/day2-v0.1.0`.
- Changed repository visibility to public after explicit owner confirmation so deterministic release
  URLs are anonymously downloadable.
- Downloaded all three adapter archives through their public release URLs and matched every byte to
  its packaged SHA-256 hash.
- Immutable verification `day2-release-verification-5acbafb44fc44722` has status `VERIFIED` and
  content SHA-256 `860a912f2cc253260138a656cb9891ac16fb3e56aed65d8f4ed3d1b24e5675cc`.
- Commit lineage for judge review:
  - `78e616bdd852b95766936e7dba8966938c2fe760` contains the completed scientific execution and
    evidence.
  - Release tag `day2-v0.1.0` resolves to `d731dba292d13d3818deb78662ae27c6df459078`, which adds
    deterministic archive checksums and publication metadata without changing scientific results.
  - `33a9dc520eff5ae7f4e52e6a5d58be60d0b0e9d3` adds post-release anonymous-download verification,
    documentation, and its evidence-matrix assertion; no scientific artifact or adapter changed.
  - Any later `main` commits in this lineage are documentation-only clarity updates.

## 2026-07-15 — Day 3 Foundation and Initial Pool

- Added isolated Day 3 strict schemas, configs, CLI, verified-teacher runner, strict filtering,
  whole-sequence scheduling, resumable OLMo training, checkpoint selection, frozen-split evaluation,
  replay, failure analysis, six-row comparison, scientific/distribution decisions, and deterministic
  one-adapter publication.
- Generalized only the prompt-record type interface; rendered Day 1/2 prompts remain unchanged.
- Froze 512 initial candidates at
  `artifacts/day3/pools/day3-pool-initial-af5ae874b4e54637`: 32 per archetype, 512 unique semantic
  leakage signatures, and zero overlap with frozen splits, fixtures, smoke IDs, blocker subsets, or
  Day 2 manifests.
- Added regression tests proving decision-relevant values alter semantic signatures while request
  paraphrases and opaque identifier substitutions do not.
- The first anonymous teacher download returned 404 because the repository was private. After the
  owner made the repository public, anonymous archive and internal-file verification passed at
  `artifacts/day3/teacher-verifications/day3-teacher-verification-51f66637be7badc8`.
- Started the real initial 512-candidate teacher run on local float16 MPS. Final run/filter IDs and
  measured durations are appended only after immutable finalization.

## 2026-07-15 — Day 3 Teacher Execution and Terminal Gate

- Initial teacher run `day3-teacher-initial-20260715T110543-9be5df3c` completed all 512 candidates
  with zero infrastructure failures, 221,755 processed generation tokens, and 728.85 seconds of
  measured active duration.
- Strict filtering accepted 46 initial outputs, so the one allowed expansion was triggered.
- Expansion pool `day3-pool-expansion-7c12780f52bbe378` preserved 16 candidates per archetype and
  zero leakage collisions. Teacher run `day3-teacher-expansion-20260715T111958-735173bf` completed
  all 256 candidates with zero infrastructure failures, 108,723 processed generation tokens, and
  362.80 seconds of measured active duration.
- Terminal filter `day3-filter-9d186a0dde24549f` evaluated all 768 outputs. It accepted 59 and
  rejected 709: 485 policy-contract mismatches, 214 schema-invalid outputs, eight safety
  violations, and two invalid-JSON outputs.
- Accepted outputs covered five of sixteen archetypes; only `pending_payment`, refund unauthorized,
  eligible cancellation, ineligible retention, and subscription unauthorized had any accepted
  records. The exact 224-record, 14-per-archetype set was therefore impossible.
- Teacher replays `day3-replay-teacher-d86202f1df684f79` and
  `day3-replay-teacher-83fb428b6d4a4fa3`, plus filter replay
  `day3-replay-filter-afad3d01fa2b4bc9`, all passed exactly.
- Scientific decision `day3-scientific-decision-41735df24888461c` finalized
  `SCIENTIFICALLY_FAILED / DAY4_BLOCKED / INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES`.
- Distribution decision `day3-distribution-decision-a20ce4a5e30545e8` finalized `NOT_ATTEMPTED`.
  No target training, validation, held-out test, comparison, adapter packaging, release, or Day 4
  execution occurred.
- During filtering, strict JSONL replay exposed datetime strings being passed through Pydantic's
  Python-mode strict validator. Day 3 JSONL readers now use strict JSON-mode validation, with a
  regression test; immutable teacher outputs were unchanged.

## 2026-07-15 — Day 3 Final Quality Gates

- Frozen sync checked all 76 locked packages.
- Ruff lint and format checks passed across 82 files.
- Strict mypy passed across 51 source files.
- Offline pytest passed with 83 selected tests and one opt-in real-model smoke test deselected.
- OpsRoute v0.1.0 regenerated exactly at
  `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`.
- The real-evidence integration test validates both pools, teacher verification, 768 terminal
  predictions, the failed synthetic dataset, all three replays, scientific/distribution decisions,
  and the absence of training, test, comparison, publication, or target-adapter evidence.

## 2026-07-15 — Distribution-Matched Recovery Foundation

- Added isolated strict schemas, configs, CLI, and artifact roots for
  `target_synthetic_distillation_matched`; no original Day 3 artifact was rewritten.
- Frozen historical baseline `day3-matched-baseline-5a63f9c161e964fd` and train fingerprint
  `day3-matched-fingerprint-5aa5befc9ae1da92`.
- Frozen initial pool `day3-matched-pool-initial-e272e8a7b827bb01` with 512 candidates, exactly 32
  per archetype. Exact distribution audit `3b11ff...` and leakage audit `dda75b...` passed.
- Added fresh OLMo training, safety-first checkpoint selection, held-out evaluation, replay,
  comparison, terminal-negative recovery, deterministic packaging, and publication-independent
  distribution status paths.
- Targeted original/matched regression suite passed 45 tests before scientific execution.

## 2026-07-15 — Distribution-Matched Recovery Execution

- Initial teacher run `day3-matched-teacher-initial-20260715T123651-195bede8` completed all 512
  candidates with 215,713 processed generation tokens in 766.10 active seconds. The strict filter
  accepted 479; duplicate auto-refund accepted 3/32, triggering the single fixed expansion.
- Expansion pool `day3-matched-pool-expansion-dc0b0c265b3c3ed1` passed exact distribution and
  leakage audits. Teacher run `day3-matched-teacher-expansion-20260715T125036-8f3c1dc8` completed
  all 256 outputs with 107,888 processed generation tokens in 356.59 active seconds.
- Terminal matched dataset `day3-matched-synthetic-dataset-36eea02e066b021a` accepted 719/768 and
  rejected 49 policy-contract mismatches. Duplicate auto-refund reached only 4/48; every other
  archetype reached at least 44.
- All required fingerprint, audit, teacher, filter, analysis, attempt-comparison, and recovery
  replays passed. Attempt comparison `day3-matched-attempt-comparison-83288d60a73ff1c8` preserves
  both the independent 59/768 result and matched 719/768 result.
- Recovery decision `day3-recovery-decision-bcb9f968af3abfc1` finalized
  `RECOVERY_TERMINAL_NEGATIVE / DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT`.
- Distribution decision `day3-matched-distribution-decision-80a3eb687b86a952` finalized
  `NOT_ATTEMPTED`. No target training, validation, test, adapter, release, third attempt, or Day 4
  execution occurred.

## 2026-07-15 — Matched Recovery Final Gates

- Frozen offline sync checked all 76 locked packages.
- Ruff lint and format checks passed across 97 files.
- Strict mypy passed across 62 source files.
- Offline pytest passed with 100 selected tests and one opt-in real-model smoke test deselected.
- OpsRoute v0.1.0 regenerated exactly at
  `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`.
- Historical original Day 3 and matched terminal-evidence integration gates passed. No credentials,
  model weights, original-artifact writes, target training, held-out test, publication, third
  attempt, or automatic Day 4 work entered the change set.

## 2026-07-15 — Phase 3B Preregistration and Execution

- Baseline `phase3b-baseline-aebd48f484b9c63e` replayed 48 matched duplicate-auto-refund
  candidates: four accepted and 44 strict policy-contract mismatches.
- Hybrid dataset `phase3b-hybrid-dataset-3a77845a67e42af3` contains 214 exact teacher labels and ten
  hash-ranked original anchors, exactly 14 records per family/archetype group.
- Confirmatory bundle `phase3b-confirmatory-9ec80c83731795de` froze 32 validation and 64 test rows;
  leakage audit `phase3b-confirmatory-leakage-661099920c116c56` passed all five collision classes.
- Schedule `phase3b-hybrid-schedule-fef500c2ac61404e` froze 672 exposures, 168 optimizer steps,
  272,568 processed tokens, and a 75-token residual.
- Preregistration commit `cd873c5d87817f64ac2ecd04824ef1cfdb19b1ea` was bound by attestation
  `phase3b-preregistration-2b54c44c199115a2` using Git-tree bytes.
- The sandbox-only MPS attempt finalized failed with zero steps/tokens. The identical configuration
  then completed on local MPS in 504.76 seconds with no correction and checkpoints 56/112/168.
- Steps 56 and 112 failed the safety filter. Step 168 reached 84.375% validation semantic, 100%
  strict, zero unauthorized actions/bypasses/false actions, and was selected.
- Primary run `phase3b-target_hybrid_anchored_distillation_10-confirmatory_test-20260715T150725-33a99282`
  completed 64/64 predictions at 85.9375% semantic and 100% strict with no safety violations.
- All six primary runs share split hash `74697b45669d80301df2853ac0c535333407d5b5fededfc5e7eec7efe595f44a`
  and replay exactly. The later exploratory legacy run scored 100% semantic/strict on 32 rows.
- Decision `phase3b-scientific-decision-0482549a90414fc8` finalized
  `PHASE3B_SCIENTIFICALLY_COMPLETED / DAY4_UNBLOCKED`; Day 4 was not started.

## 2026-07-15 — Phase 3B Publication and Verification

- Scientific-result commit `9ced5d1704972b6c1d818fd0c79a6006d2820b1c` preserves training,
  evaluation, exact replays, comparisons, failure analysis, and the scientific decision.
- Packaging/tag commit `2d7052f103ba29d56a0ecd4ce442c5dd1c4b44b2` is the immutable target of
  `phase3b-anchored-v0.1.0`; it adds deterministic packaging metadata without changing science.
- Published `target_hybrid_anchored_distillation_10-7461072c83b4dcde.zip` with SHA-256
  `f30fa5c814596a6c383be0390174275c893e1aba83d27df1dc8eec46c929f87f` and `SHA256SUMS`.
- A fresh public download verified the archive and all four internal files in one attempt. Evidence
  commit `8718ef670e2a5f79a068da554b40603a6d4979e2` records `PUBLISHED_VERIFIED` and the
  independent distribution decision.
- Later `main` history contains only post-tag public verification and documentation updates. The
  release tag intentionally remains on the earlier packaging commit, so scientific and distribution
  lineage is not obscured by judge-facing documentation changes.

## 2026-07-15 — Phase 3B Final Gates

- Frozen sync verified all 76 locked packages.
- Ruff lint and format checks passed across 112 files; strict mypy passed across 72 source files.
- Offline pytest passed with 113 selected tests and one opt-in real-model smoke test deselected.
- OpsRoute v0.1.0 regenerated exactly at
  `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`.
- Phase 3B integration gates validate historical immutability, preregistration, real training,
  checkpoint selection, all six confirmatory runs, exact replays, scientific completion, public
  release verification, and the publication-independent distribution decision.
