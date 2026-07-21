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

## 2026-07-15 — Phase 4 Protocol Foundation

- Added isolated strict schemas, configs, CLI, exactly-once adversarial evaluation, deterministic
  replay/analysis, migration profiles, representative cases, typed evidence, bounded GPT-5.6 Sol
  memo handling, and static showcase replay.
- Added the locked `analyst` extra with the official OpenAI Python SDK; no dependency is imported by
  offline data/evaluation commands.
- Frozen protocol `phase4-protocol-95094c5782a1d987` after verifying the untouched adversarial
  split, all six model/adapter lineages, and Phase 3B comparison/science/publication hashes.
- Focused Phase 4 protocol, taxonomy, profile, CLI, and parser-golden tests passed before the
  protocol commit. No model inference or API request occurred during protocol freezing.
- Protocol commit `26acce08bb5cf74e842306b09bfee12d074a8b8b` was bound through Git-tree
  attestation `phase4-attestation-6063ecc2f3563c40` before inference.
- The adapted-source model completed all 32 outputs, then artifact finalization rejected the
  adapter verification timestamp because the nested model had been JSON-dumped before strict
  validation. The serializer was corrected without changing prompts, generation, outputs, parser,
  metrics, or system lineage; the 32 preserved active predictions were finalized without model
  regeneration.

## 2026-07-15 — Phase 4 Adversarial Execution

- Completed exactly one 32-record adversarial run for each of the six frozen systems on MPS. All
  192 predictions reached terminal records and all six evaluation replays passed.
- Full target retraining reached 68.75% semantic exactness and 93.75% strict validity; the anchored
  hybrid reached 62.5% semantic exactness and 93.75% strict validity. Each had one approval bypass
  and one unauthorized action under the unchanged evaluator.
- Replayed failure/archetype matrices, migration profiles, representative cases, and evidence pack.
  Full retraining is the maximum-adversarial-resilience recommendation; the hybrid is the
  minimum-direct-label and maximum-confirmed-capability recommendation.
- Built and validated the deterministic fallback and the self-contained showcase. No
  `OPENAI_API_KEY` was present, so zero API requests were made and status finalized as
  `READY_FOR_GPT_MEMO / DAY5_BLOCKED_PENDING_GPT_MEMO` with `automatic_phase5=false`.
- Final gates passed: frozen sync checked 83 packages; Ruff lint/format and strict mypy passed;
  offline pytest passed with 121 selected tests and one real-model smoke test deselected; OpsRoute
  v0.1.0 regenerated exactly at `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`.

## 2026-07-15 — Phase 4 Validated GPT Memo and Freeze

- Supplied credentials were loaded only from ignored `.env.local`; the key was never printed or
  committed. The bounded GPT-5.6 Sol workflow made one initial request and the single permitted
  repair request. No third request was made.
- The repaired memo initially exposed a deterministic validator limitation: grouped comparisons
  supported two systems but not three targets against one source reference. The validator was
  generalized and unit-tested; the exact repaired memo bytes were revalidated without another API
  request.
- Authoritative memo `6e5697c5c0b12b9245a4fd192517c187a46d4148672693aac294fa11ef4461d0`
  passed validation `2a14ba3b4241edd84a2c6dbfc5cb90425a95265363c395672bb52d1d4e01bc60`
  with complete accounting and no unsupported claims.
- Built immutable final showcase `artifacts/showcase/inheritbench-v0.1-gpt`; manifest
  `85f6c02dcc430992a277d0cb500373a1b491893915f450b4523699b7b7d3e5cc` replayed exactly.
- Final decision `2db9baa4cf266cbccaf8ff4ce8948973a6c8175e5212e3b7336f29d616d434af`
  is `PHASE4_COMPLETED_WITH_VALIDATED_GPT_MEMO / DAY5_UNBLOCKED` with
  `automatic_phase5=false`. Existing no-overwrite guards make the final evidence terminal.

## 2026-07-15 — Phase 5 Static Product

- Added a pnpm workspace and statically exported Next.js App Router application with six directly
  linkable routes, a self-directed information architecture, accessible charts/tables, frozen case
  inspection, validated memo citations, and in-browser showcase hash verification.
- Added deterministic Python projection `inheritbench-web-v0.1`. Its surface-aware resolver derives
  six adversarial selected cases and preserves two `NO_ELIGIBLE_CASE` slots without substitution.
- Added a Node-only ingestion and build path that verifies committed showcase/projection hashes and
  requires no Python, uv, API credential, model, accelerator, or runtime data service.
- Added local projection, frontend unit, static-build, Chromium desktop/mobile, accessibility,
  reduced-motion, deep-link, and no-external-request gates. Deployment remains intentionally out of
  scope.
- Projection `08d272c95d243a7d89736afe9e7eb448a3b94d23b2c3687d2dccd191663ecd05`
  and web-build manifest `4a0c6cc92fe008906717aa45f104d95ec03a9e989a68d13ca49ce30c3fc01735`
  reproduced exactly; 130 offline Python tests, four frontend unit tests, and 20 desktop/mobile
  browser tests passed.
- Final product status is `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED`; hosted
  completion remains guarded by a separate deployment-verification artifact. Local decision hash:
  `0b86720841e28d1a3da476fb1e491debe0ed9bf88466e6bf739b6ce635004d2d`.

## 2026-07-16 — Verified Succession Replay Product

- Added the supported `opsroute-qwen-olmo` workflow and made **Run verified succession replay** the
  primary product action. The browser performs real manifest, hash, record, aggregate, residual,
  readiness, and adapter-identity verification without model execution.
- Added a compact 160-record replay bundle and matching strict Python and TypeScript engines. Both
  derive clean 55/64 exact, 64/64 strict, nine policy-code aliases, adversarial 20/32 exact, and
  `CONDITIONAL_PASS`; the input manifest stores no readiness decision.
- Added deterministic `succession replay` and honest `succession preflight` CLI commands. A clean
  base-only uv environment completes replay without model dependencies or network access.
- Added locked configuration, no-training preflight, ordered verification progress, generated report
  and receipt downloads, adapter delivery, residual inspection, GPT rationale, and evidence links.
- Added portable static-export route checks and made adapter verification work from a clean clone by
  relying on the immutable anonymously verified publication record while optionally rechecking local
  archive bytes.
- Final local gates: 138 selected Python tests passed with one model smoke test deselected; ten
  frontend tests passed; 36 Chromium desktop/mobile browser tests passed; exact dataset and Phase 5
  projection replay passed; portable static export passed; both GitHub Actions jobs passed.
- Product commit `c39c79b8cfe0c8f1a40e3c31f614a6c2c813b98e` remains
  `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED`. Public deployment is the remaining
  external gate.

## 2026-07-16 — Documentation and Submission Readiness

- Reorganized the README around the developer-tool product, supported succession case, hosted
  verified replay, full phased workflow, exact outputs, trust boundaries, and five-minute judge
  path. Package metadata now describes InheritBench as a model-succession developer tool.
- Replaced the chronology-first judge guide and added product architecture, capability-pack,
  succession-output, deployment, demo, and Devpost submission documents. Submission-only URLs and
  the primary Codex `/feedback` Session ID remain explicit placeholders rather than fabricated
  claims.
- Verified a clean base-only install with 18 runtime packages. The documented replay command
  produced `succession-replay-2b1798dad96176ff`, derived `CONDITIONAL_PASS`, completed all nine
  replay operations, and wrote the nine documented output files.
- Added documentation integrity tests for internal links, required product/accounting language,
  exact replay filenames, and prohibited stale tokens. No scientific artifact, dataset, adapter,
  metric, readiness decision, or historical evidence file changed.
- Final local gates passed: Ruff lint/format, strict mypy across 88 source files, 141 selected
  offline Python tests with one model smoke test deselected, ten frontend tests, 36 Chromium
  desktop/mobile browser tests, exact Phase 5 projection replay, exact 320-record OpsRoute
  regeneration, and the portable Node-only static export contract.

## 2026-07-16 — Product Narrative Refocus

- Established the canonical product definition: InheritBench transfers a learned operational
  capability to a replacement model, delivers the recovered adapter, and determines whether the
  migration should pass, proceed conditionally, or be blocked.
- Reorganized the README and Devpost draft around the product workflow before the empirical proof:
  define the capability, measure the loss, generate supervision, train and select the successor,
  evaluate readiness, and export the adapter, evidence, and decision.
- Positioned the Qwen → OLMo OpsRoute result as the first completed proof of the system and retained
  the exact v0.1 boundary: one model pair, one capability pack, and a preregistered phased workflow.
- Reframed browser and CLI replay as the assurance interface rather than the central invention. No
  scientific artifact, metric, adapter, evaluation, or readiness decision changed.
- Revalidated Ruff lint/format, strict mypy, CLI help, and 141 selected offline Python tests with one
  model smoke test deselected.

## 2026-07-17 — Pack-Driven Succession v0.2

- Added strict `inheritbench.capability-pack.v0.2` loading, scaffolding, hash validation, JSON Schema
  validation, RFC 6901 field comparison, controlled vocabularies, typed safety AST rules, constrained
  readiness rules, generic leakage utilities, and trusted local evaluator entry-point verification.
- Added an explicit model registry for pinned Qwen2.5 0.5B Instruct, pinned OLMo-2 1B Instruct, and
  test-only fake adapters. Real adapters implement deterministic generation, masked supervised
  formatting, Q/K/V/O LoRA, checkpoint persistence/resume, telemetry, fresh-base reload, and export
  verification.
- Added content-addressed generic planning and immutable execution stages for direct target LoRA and
  anchored behavioral transfer. A stage-scoped broker separates model inputs, evaluator oracles,
  direct labels, anchors, validation, confirmatory, and adversarial data.
- Added `capability`, generic `succession`, and `succeed` CLI interfaces while preserving the
  published `succession replay --case opsroute-qwen-olmo` and `succession preflight` commands.
- Added a deterministic OpsRoute v0.2 reference projection and a materially different
  Purchase Approval fixture. Generic packages are protected by an AST import-boundary test.
- Replayed 768 historical matched teacher outputs through the generic strategy: 719 accepted,
  duplicate-auto-refund 4/48, deficit ten, 214 teacher labels selected, and ten anchors required.
- Completed the Purchase Approval model-free intervention flow: persisted `ANCHORS_REQUIRED`, added
  exactly two validated anchors, resumed without repeating teacher work, finalized, and replayed.
- Executed real product integration run
  `succession-opsroute-direct-target-lora-v0.1-87c29fead2628e49` on Apple MPS. It ran real Qwen source
  and untouched OLMo inference, trained OLMo for 272,643 tokens and 168 optimizer steps, persisted
  checkpoints 56/112/168, selected safety-eligible checkpoint 112, verified fresh-base reload, ran
  confirmatory and adversarial surfaces once, exported adapter
  `303339a221c616a585d07247896377a5b75c690f04c8a1b567edf3d45b6760a4`, and passed exact model-free
  replay.
- The real v0.2 run honestly returned `MIGRATION_BLOCKED`: confirmatory 36/64 semantic and 52/64
  strict with zero blocker safety findings; adversarial 18/32 semantic and 29/32 strict with two
  blocker safety findings. This is integration evidence on known surfaces, not new benchmark
  evidence and not a replacement for the immutable Phase 3B result.
- Added `/run/local/` for client-only verified rendering of generic finalized and
  `ANCHORS_REQUIRED` bundles with Zod, Web Crypto, a 5 MiB limit, escaped output, and no upload or
  runtime API.
- Final acceptance gates passed: frozen sync checked 80 packages; Ruff checked and formatting
  verified 172 files; strict mypy verified 122 source files; 155 offline Python tests and the
  separate real-product smoke test passed; 12 frontend unit tests and 36 Chromium desktop/mobile
  browser tests passed; the Node-only static export built all declared routes.
- Exact OpsRoute regeneration remained
  `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`; the Phase 5 web projection
  remained `08d272c95d243a7d89736afe9e7eb448a3b94d23b2c3687d2dccd191663ecd05`;
  frozen Day 1–Phase 5 evidence remained
  `e97e33202c361b52564c34ad5bc70008983eb2f55d5b6d5e38e14be2f6d4f4e1`; both capability-pack
  projections regenerated byte-identically.
- No commit, push, tag, release, or deployment was performed for v0.2. Generic run and adapter
  evidence remains local and ignored as required.

## 2026-07-17 — Reproducibility Repair and Generic Anchored Gate

- Added plan-seeded Python, NumPy, Torch, CUDA, and MPS initialization before model load and LoRA
  attachment. New checkpoints persist Python, NumPy, Torch, CUDA, and MPS RNG state; resume restores
  state without reinitialization.
- Added versioned deterministic-hash and frozen-record-order schedules. The OpsRoute projection now
  reproduces the direct 672-exposure/272,643-token schedule and anchored
  672-exposure/272,568-token schedule exactly.
- Split generic evaluation into parse, schema, historical strict, vocabulary, cross-field,
  semantic, structural, and safety facts. Historical strict and semantic behavior matched every
  frozen direct and anchored confirmatory/adversarial prediction in offline regression tests.
- Added pack-configured validation surfaces and checkpoint policies. Direct uses the original
  32-record Day 2 validation surface; anchored is configured for the 32-record Phase 3B
  confirmatory-validation surface.
- Projected and verified 768 frozen matched-teacher outputs. Generic filtering reproduced 719
  accepted outputs, 214 selected teacher labels, duplicate-auto-refund 4/48, and the ten-record
  deficit. The reference profile explicitly does not claim live generic teacher generation.
- Executed repaired direct run
  `succession-opsroute-direct-target-lora-v0.1-200d8ad795f4bb0f` on MPS: exact 224-record
  supervision, 272,643 tokens, 168 optimizer steps, checkpoints 56/112/168, selected step 168,
  fresh reload, one confirmatory run, one adversarial run, adapter export, and model-free replay.
- The no-tolerance direct parity gate failed. Generic confirmatory semantic exactness was 48/64
  versus historical 51/64. Historical strict validity matched 64/64, adversarial semantic matched
  22/32, adversarial historical strict matched 30/32, checkpoint step 168 matched, and all safety
  findings matched.
- Diagnosis artifact
  `f7580908a6f6ad23d04748e24fdb9a565e9a44c20a5f4dab46643c0e89e0230b`
  records `HISTORICAL_UNSEEDED_ADAPTER_INITIALIZATION_NOT_RECONSTRUCTIBLE`: the historical trainer
  attached random LoRA tensors before seeding and saved neither initial adapter state nor MPS RNG
  state.
- Applied the frozen stop rule: `BLOCKED_BEFORE_ANCHORED_RUN`. No real generic anchored training,
  evaluation, adapter export, or parity claim was performed.
- Final non-anchored gates passed: frozen dependency sync; Ruff and formatting over 174 files;
  strict mypy over 123 source files; 160 offline tests; one repaired real-product smoke test; 12
  frontend unit tests; 36 Chromium desktop/mobile tests; exact OpsRoute regeneration; deterministic
  Phase 5 projection verification; both capability-pack projection checks; and the Node-only static
  build. The requested anchored acceptance gate remains intentionally unmet because its direct
  prerequisite failed.
- Frozen historical evidence remained
  `e97e33202c361b52564c34ad5bc70008983eb2f55d5b6d5e38e14be2f6d4f4e1`; OpsRoute regeneration
  remained `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`.
- No commit, push, tag, release, or deployment was performed.

## 2026-07-17 — Seeded Reference Reproduction and Generic Anchored Result

- Froze prospective amendment `54eda241f1f194d5ca51872f3504fac12cf003516bdb99a0d55c86a54ea6ae5b`
  against `HEAD` `8295713e0c19551839b33630d3ace3c042d20f61` with
  `git_preregistered=false` as required by the no-commit execution boundary.
- Preserved execution `...-01-ce164572f906c70e` after a report-time pickle RNG-hash equality
  defect caused a false stop after all 168 training steps. Froze implementation correction
  `753400e1210da6b0d18a3c9e948090b686e6c3ba9dbab61db9e96fd7f750b369`; training semantics did not
  change. Preserved execution `...-02-cb065a44ac4f29e6` after an MPS gradient spike at step 112.
- Independent execution `succession-opsroute-direct-target-lora-v0.1-03-8795423ea3013599`
  reproduced the corrected direct protocol bit-for-bit: 168 telemetry steps, all checkpoint
  adapters, selected step 168, all raw outputs and evaluator facts, readiness, and exported adapter
  hash `15ccc59e43707ad4f14dc3d24798ddb05b29000dc7ac4612da14e35b305be841`.
- Real generic anchored run
  `succession-opsroute-anchored-behavioral-transfer-v0.1-00-ee7a07404b124c1b` independently loaded
  768 frozen outputs, accepted 719, selected 214, derived a ten-record deficit, selected ten from
  the bound 14-record anchor pool, resumed without repeating teacher filtering, trained 272,568
  tokens over 168 steps, selected checkpoint 168, exported adapter
  `fe6cc74f9a4696c99f72a1a82572aa62fdd2092c1ac1a143844bd48777fba34c`, reloaded it into fresh
  OLMo, and passed model-free replay.
- The anchored result was 53/64 confirmatory semantic, 64/64 historical strict, zero clean blocker
  safety findings, 19/32 adversarial semantic, 30/32 adversarial historical strict, and two
  adversarial blocker safety findings. An unchanged clean group floor returned
  `MIGRATION_BLOCKED / GENERIC_ANCHORED_RECOVERY_FAILED`; no quality rerun followed.
- The reference proof consumes verified frozen teacher outputs and does not prove live generic
  teacher generation. Historical Phase 3B evidence and the published adapter remain authoritative
  and unchanged.

## 2026-07-17 — Bounded Multi-Start Recovery

- Resolved metric nomenclature from atomic records before execution. Historical and generic
  `semantic_match` values are exact six-field contract matches; the new operational semantic view
  checks decision, tool, arguments, approval, and reason while reporting policy code separately.
  Crosswalk status: `METRIC_IDENTITY_RESOLVED`, hash
  `f7a9880787150b852af194d71c0d919f967976d0383a145cc8ee78813d220f2e`.
- Content-froze amendment `bounded-multistart-recovery-v0.1` at
  `08a706d2b2332150fbe711cbdbddb9175bde1ce92678c27faa826837c27ffc6c` with
  `git_preregistered=false`. Four seeds were derived before training:
  `239647975`, `3558287218`, `1260805304`, and `47745490`.
- Generated and sealed fresh balanced OpsRoute v0.3 surfaces before model execution: 64
  confirmatory and 32 adversarial records, zero ID/surface/input/record/semantic collisions,
  manifest `70ea20a3fc94dbbcca7081628c2900239597cf5e4ed759458c28d9be22043a2d`.
- Froze canonical plan `anchored-multistart-b0b3b78e5354a40b`. Every candidate shared the same
  supervision, encoding hash, schedule, optimizer, checkpoints, validation surface, generation
  configuration, and readiness contract; only the LoRA seed and initial adapter hash differed.
- All four real MPS candidates terminated under the unchanged numerical-instability guard:
  gradient norms `14909.123046875`, `465762.40625`, `587452.25`, and `606600.5625`.
  Candidates 2 and 3 preserved ineligible step-56 partial checkpoints at 90,856 processed tokens;
  candidates 0 and 1 failed before the first declared checkpoint.
- No candidate completed recovery validation, no candidate was selected, no adapter was exported,
  and no final confirmatory or adversarial generation occurred. Readiness remains `NOT_RUN`;
  terminal classification is `BLOCKED_BEFORE_FINAL_EVALUATION`.
- Model-free blocked-run replay passed and proved four terminal candidate records, a validation-only
  no-candidate ranking, unchanged final-surface hashes, and zero final-evaluation calls.
- Added task-neutral browser support for `inheritbench.web-bundle.v0.4`, including protocol
  lineage, four candidate seeds, partial-checkpoint lower bounds, selection status, sealing,
  readiness-not-run, and replay evidence. Legacy v0.2/v0.3 bundles remain readable.
- Final gates passed: frozen sync checked 80 packages; Ruff and formatting verified 183 files;
  strict mypy verified 129 source files; 174 offline tests and two product-smoke tests passed; exact
  OpsRoute regeneration remained
  `9202ecdf200a86cf3899a9ff3eb71722effe9421c04f353fd575d62c6c7d492b`; both capability-pack
  projections and the Phase 5 projection replayed exactly; 14 frontend unit tests and 40 Chromium
  desktop/mobile browser tests passed; the Node-only static export and portable build report passed.
- Frozen historical evidence remained
  `e97e33202c361b52564c34ad5bc70008983eb2f55d5b6d5e38e14be2f6d4f4e1`.
- No scientific settings, supervision, schedule, thresholds, historical artifacts, prior runs,
  commits, tags, releases, or deployments were changed.

## 2026-07-18 — Evidence-Only Readiness and Numerical-Guard Audit

- Wrote immutable forensic bundle `runs/audits/readiness-and-instability` without model training,
  inference, or fresh-final-surface access. It records the complete frozen-input inventory,
  readiness traces, counterfactuals, candidate timelines, checkpoint integrity, and combined
  decision.
- Readiness classification is `READINESS_CONTRACT_VERSION_DRIFT_CONFIRMED`: the historical
  `succession-readiness-v0.1` contract has no clean coverage-group floor and maps remaining
  adversarial risk to `CONDITIONAL_PASS`; the generic `opsroute-readiness-product-v0.1` contract
  blocks first on the frozen clean group floor of `0.5`. Neither stored decision is rewritten.
- Numerical classification is `NUMERICAL_INSTABILITY_GUARD_DEFECT_CONFIRMED`: all four reported
  terminal norms were finite pre-clip values. The prior generic trainer clipped first, then treated
  its pre-clip return value above `100` as instability. Candidates 2 and 3 have readable, finite
  step-56 LoRA tensors and finite optimizer state.
- Narrow generic implementation repair: telemetry now distinguishes pre/post clipping norms and
  the guard rejects only non-finite loss, gradients, parameters, or optimizer state. No candidate
  was resumed or rerun. The permitted next action is
  `ORIGINAL_MULTISTART_PROTOCOL_RERUN_ALLOWED_AFTER_REPAIR`, pending explicit authorization.

## 2026-07-18 — Repaired Bounded Multi-Start Execution

- Content-froze implementation repair
  `artifacts/protocol-amendments/bounded-multistart-guard-repair-v0.1.json`. It changes only
  numerical telemetry and finite-state validation: supervision, 672-exposure schedule, optimizer,
  checkpoints, candidate seeds, recovery validation, readiness contract, and sealed v0.3 final
  surfaces remain unchanged.
- Restarted all four prospectively frozen seeds from step zero under new execution identities.
  Candidates 2 and 3 were not resumed from their old step-56 checkpoints because those checkpoints
  predated the repaired terminal-step and accumulation-boundary receipt. All four candidates
  completed 272,568 tokens and 168 optimizer steps.
- Recorded pre-clip and post-clip gradient norms separately. Candidate 1 continued safely through a
  finite pre-clip norm of `563354.8125`; its maximum post-clip norm was `0.9999999403953552`.
- Recovery-validation operational scores were `32/32`, `31/32`, `32/32`, and `32/32`. All four
  candidates were safety eligible. The frozen validation-only ranking selected candidate 0 at
  checkpoint 168.
- Fresh-base reload verified selected adapter
  `bbfd685856645bde4bb1d45e1da239d567fa412a65e433483325227f6129f3e7`.
  No candidate accessed either final surface before selection.
- Ran exactly one logical v0.3 final evaluation for the direct control and selected anchored
  candidate. Rejected candidates received zero final evaluations.
- Selected anchored result: clean operational `64/64`, exact full contract `63/64`, historical
  strict `64/64`, zero clean blocker safety findings; adversarial operational and exact `20/32`,
  historical strict `31/32`, with one unauthorized action and one approval bypass on the same
  record.
- The direct control reached clean operational `62/64` and exact full contract `50/64`; adversarial
  operational `16/32` and exact full contract `12/32`.
- Final classification:
  `GENERIC_ANCHORED_RECOVERY_CONFIRMED / CONDITIONAL_PASS /
  ADVERSARIAL_BLOCKER_SAFETY_FINDINGS`. Model-free replay passed with 96 direct and 96 anchored
  records. The reference path still consumes frozen teacher outputs and does not prove live generic
  teacher generation.

## 2026-07-21 — Interactive Assurance Lab

- Added `/sandbox/` as a browser-native judge path over the committed repaired reference projection.
  It verifies asset hashes, evaluates records, aggregates coverage groups, detects safety findings,
  applies the unchanged readiness contract, checks replay parity, and generates an unsigned local
  receipt.
- Added three built-in scenarios for the untouched target, direct recovery, and validation-selected
  anchored successor. Results are withheld until evaluation completes; untouched-target output
  remains diagnostic-only.
- Added controlled in-memory safety mutations, reset behavior, compatible local JSON/JSONL uploads,
  record-level findings, and receipt export. Training, model inference, candidate generation, and
  final reference predictions remain precomputed.
- Added Python/TypeScript parity, integrity, readiness, mutation, upload, source-neutrality,
  accessibility, and browser interaction guards without modifying the evaluator contract, readiness
  semantics, or frozen scientific artifacts.

## 2026-07-21 — Judge Narrative, Navigation, and Mobile Pass

- Reorganized the landing page around one model-replacement problem, Diagnose → Recover → Assure,
  the current Qwen → OLMo result, an Assurance Lab invitation, and two primary judge paths.
- Simplified the Lab initial state to Choose → Run → Review, moved stress and detailed tools behind
  progressive disclosure, elevated the readiness decision, improved typography and contrast, and
  removed implementation-heavy primary copy.
- Standardized every **Reference run** destination on `/run/opsroute-qwen-olmo/`, added Lab links to
  the completed inspector and evidence page, and kept historical evidence visually separate from
  current product assurance.
- Eliminated document-level mobile overflow at 320, 360, 375, 390, and 430 CSS-pixel widths by
  making the stepper responsive and rendering candidate comparison as mobile cards while preserving
  the desktop table.

## 2026-07-21 — Submission Identity and Documentation Release Pass

- Recorded the real Codex `/feedback` Session ID
  `019f61c4-1e2b-7861-8e2c-7fe82c81255d` in current submission documentation. The 2026-07-16
  historical placeholder statement remains unchanged as originally recorded.
- Rewrote the README and judge guide around the current product, exact repaired reference metrics,
  live-versus-precomputed boundary, three reproduction levels, code-backed commands, supported
  platforms, capability-pack inputs, scientific limits, and Codex/GPT-5.6 roles.
- Synchronized architecture, deployment, demo, Devpost, capability-pack, and licensing guidance
  with the Lab-first product. Kept public deployment and video links explicitly pending.
- Added `CITATION.cff`, `NOTICE`, and provenance guidance for project-authored synthetic data,
  generated model outputs, the GPT-authored memo, base models, adapters, and third-party software.
- Documentation guards passed Ruff format/lint and eight focused pytest checks covering section
  order, exact current metrics, routes, clean-clone commands, internal links, citation/provenance,
  append-only history, and the real session ID.
- Final `pnpm verify` passed: the Phase 5 projection replay retained
  `08d272c95d243a7d89736afe9e7eb448a3b94d23b2c3687d2dccd191663ecd05`; ingestion validated 40
  committed files; ESLint and TypeScript passed; all 36 frontend unit tests passed; all 12 static
  routes built; 56 Playwright/Axe desktop/mobile tests passed with two expected project skips; and
  the portable immutable build report verified.
