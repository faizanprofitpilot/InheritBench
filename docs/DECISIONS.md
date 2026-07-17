# Day 1 Decisions

## 2026-07-14 — Reproducible Foundation

- Use CPython 3.11.15 with `requires-python >=3.11,<3.12`.
- Use `uv` and commit `uv.lock`; do not fall back to the system Python or another package manager.
- Use PEP 621, Hatchling, a `src/` package, Typer, Pydantic v2, PyYAML, Rich, and structlog.
- Install PyTorch/Transformers and Modal through separate extras. Defer PEFT, Datasets, TRL,
  scikit-learn, and bitsandbytes until work that requires them begins.
- Logs go to stderr; command JSON goes to stdout or an explicit artifact path.
- Environment variables are documented but never automatically loaded or committed.

## 2026-07-14 — Model Pair

- Source: `Qwen/Qwen2.5-0.5B-Instruct` at
  `7ae557604adf67be50417f59c2c2f167def9a775`.
- Target: `allenai/OLMo-2-0425-1B-Instruct` at
  `48d788eca847d4d7548f375ad03d3c9312f6139e`.
- Fallback target: `HuggingFaceTB/SmolLM2-1.7B-Instruct` at
  `31b70e2e869a7173562077fd711b654946d38674`.
- All are configured for `trust_remote_code=false`, native chat templates, no quantization, eager
  attention, and a 1,024-token prompt ceiling.
- Heterogeneity and direct adapter-reuse verdicts are separate. Structural mismatch does not imply
  that every heterogeneous transfer method is impossible.

## 2026-07-14 — OpsRoute v0.1

- Use exactly refund routing and subscription cancellation/retention.
- Use seed `20260714`; task, generator, template, prompt, and contract version `0.1.0`.
- Generate 320 examples: 224 train, 32 validation, 32 test, and 32 adversarial.
- Generate labels only through pure policy resolvers with the documented precedence rules.
- Use SHA-256-derived per-record sub-seeds and reject ID, surface, or semantic collisions.
- Fixture IDs begin with `fixture_`; fixture evidence cannot enter benchmark manifests or inference.

## 2026-07-14 — Parsing and Metrics

- Accept strict whole-output JSON and one whole-output Markdown JSON fence only.
- Forbid first-object extraction, trailing-comma repair, case/alias normalization, JSON5, field
  invention, prose reconstruction, and LLM repair.
- Report unweighted strict validity, exact semantic contract match, atomic correctness, and safety
  metrics. Do not introduce a weighted Operational Contract Score on Day 1.
- Treat parser-invalid generations as completed inference with zero correctness and explicit
  unknown safety values where no decision is observable.

## 2026-07-14 — Prompt Revision 0.1.1

- The original `0.1.0` smoke run produced no schema-valid OLMo target output.
- Use the one allowed simplified revision: an exact six-key JSON skeleton, explicit JSON-null
  instruction, family-specific policy/reason mappings, and exact tool argument names.
- The revision changes only the rendered prompt contract. It does not expose evaluator-owned labels,
  alter examples, or change split membership.
- OLMo produced no schema-valid output under either `0.1.0` or `0.1.1`; activate the predeclared
  SmolLM2 fallback. Preserve `configs/tasks/opsroute_prompt_v0.1.1.yaml` and use the original
  `0.1.0` prompt for the fallback attempt so source validity remains demonstrated.
- SmolLM2 also produced no schema-valid output under either prompt. Stop model-pair selection under
  the declared kill switch and mark Day 1 blocked rather than weakening the parser or selecting
  results post hoc.

## 2026-07-14 — Evidence and Compute

- Serialize canonical JSON with sorted keys, compact separators, UTF-8, and `allow_nan=false`.
- Finalize datasets and run bundles atomically and never overwrite them.
- Create new run/replay IDs for reruns even if nonvolatile content hashes match.
- Run models sequentially on local MPS first. Use one bounded Modal L4 metadata probe without model
  downloads; record honest `BLOCKED` evidence if it cannot run.
- The Modal invocation was rejected before execution by the external data-export approval gate. Do
  not circumvent that control; record zero attempts and no remote environment instead.

## 2026-07-14 — Blocker Reclassification

- Preserve the Day 1 zero-validity evidence and reclassify the scientific interpretation from
  `TARGET_MODEL_INVALID_FOR_BENCHMARK` to
  `UNTOUCHED_TARGET_HAS_ZERO_SCHEMA_VALIDITY; TARGET_TRAINABILITY_UNTESTED`.
- Untouched zero validity is a valid M0 baseline because migration measures whether target-side
  adaptation recovers a capability; it is not evidence that adaptation cannot work.
- The controlled OLMo diagnostic ended all eight generations on EOS and reproduced the same schema
  failure, so no prompt revision or parser change was scientifically justified.
- The bounded trainability decision is `OLMO_TRAINABILITY_CONFIRMED`: the six-epoch OLMo run
  produced 7/8 schema-valid and 2/8 semantic-exact validation contracts with finite decreasing
  loss and exact replay.
- This decision unblocks Day 2 experimentation with the original Qwen→OLMo pair. It does not claim
  benchmark readiness, final quality, or permission to start Day 2 automatically.

## 2026-07-14 — Trainability Gate Design

- Fit exactly variants 00 and 01 from every OpsRoute archetype: 32 train records total.
- Evaluate exactly eight fixed variant-14 validation records balanced across families and decision
  behavior. Never load test or adversarial records in the trainability process.
- Use the existing semantic prompts, exact expected ActionContract supervision, native chat
  templates, prompt-label masking, strict parser, metrics, canonical hashes, and replay path.
- Permit one conservative rank-8 LoRA configuration and one bounded epoch extension only after the
  first OLMo run proves stable optimization but no semantic-exact output.
- Keep adapters under `adapters/blocker-resolution` and result evidence under
  `artifacts/blocker-resolution`; neither location changes Day 1 artifacts.

## 2026-07-14 — Modal Classification

- Classify Modal as `EXTERNAL_DATA_EXPORT_APPROVAL_REQUIRED` with zero remote attempts.
- Do not bypass the environment control or redesign around Modal. Continue local MPS work where
  bounded experiments fit, while remote CUDA validation remains unavailable until explicit approval.

## 2026-07-15 — Day 2 Scientific Freeze

- Preserve OpsRoute v0.1.0, parser `0.1.0`, metrics `v0`, prompt `0.1.0`, model revisions, and seed
  `20260714`; do not reinterpret historical results.
- Compare five final rows: source base, adapted source, untouched target, full-data target, and
  24-example limited target.
- Define the limited condition as 24/224 unique records (`10.7142857%`) selected only through locked
  SHA-256 rankings with all 16 archetypes represented.
- Match target full and limited conditions by processed-token budget. Record the nine-token limited
  residual rather than truncate an example.
- Keep early stopping disabled. Select only among declared checkpoints after training, using safety
  eligibility followed by semantic, strict, abstention, approval, argument F1, validation loss, and
  earlier-step ordering.
- Require the balanced hard source gate before target benchmark claims or any test evaluation.
- Keep test results decision-inert and leave adversarial records untouched.

## 2026-07-15 — Source Numerical Correction

- Classify the primary source gradient-norm breach as numerical instability under the predeclared
  kill switch.
- Permit exactly one correction: restart from base at learning rate `1e-4`; preserve the same data,
  token budget, optimizer-step budget, warmup, checkpoints, LoRA shape, and seed.
- Preserve the primary failed run and both of its checkpoint directories as historical evidence.
  Do not resume from them because the corrected method config hash differs.

## 2026-07-15 — Day 2 Result and Publication

- Confirm source capability before test: adapted validation semantic 93.75%, strict 100%, with all
  gate criteria passing.
- Accept target full and limited step-168 checkpoints because each is the highest-ranked
  safety-eligible checkpoint under the frozen selection rule.
- Report raw uncapped retention relative to adapted source. Full target semantic retention exceeds
  one because it scores 100% versus 96.875% for the source.
- Publish only the three selected final LoRA adapters as deterministic GitHub Release assets under
  tag `day2-v0.1.0`; keep all weights ignored by Git.

## 2026-07-15 — Day 3 Synthetic Distillation Freeze

- Preserve OpsRoute v0.1.0, prompt/parser `0.1.0`, evaluator `v0`, both pinned model revisions, all
  four split memberships, and seed `20260714`.
- Generate 512 independent non-adversarial candidates balanced 32 per archetype. Permit exactly one
  separately seeded 256-candidate expansion only after an insufficient strict filter.
- Use value-sensitive typed semantic leakage facts rather than family/archetype labels. Normalize
  opaque identifier values while preserving identifier presence, every decision-relevant value,
  available tools, and policy constants.
- Keep candidate input and evaluator-only oracle artifacts separate. Teacher inference may open only
  prompt-visible candidate inputs.
- Accept only `STRICT_VALID` outputs that exactly equal the policy oracle and have no safety flag.
  Preserve the teacher's trimmed strict candidate byte-for-byte as the assistant label.
- Select exactly 14 accepted examples per archetype using the frozen SHA-256 rank; never select by
  validation/test behavior, latency, or output style.
- Train untouched OLMo with the Day 2 full-target LoRA/optimizer settings up to 272,643 whole-sequence
  tokens. Permit only the declared numerical-instability restart at learning rate `1e-4`.
- Preserve Day 2 checkpoint safety eligibility and lexicographic selection unchanged. Test exactly
  once after a checkpoint is frozen; leave adversarial untouched.

## 2026-07-15 — Scientific and Distribution Status Separation

- Scientific completion requires completed training, a safety-eligible checkpoint, 32 terminal
  held-out test predictions, exact evaluation replay, deterministic failure analysis, and a valid
  replayed six-row comparison.
- `SCIENTIFICALLY_COMPLETED` always sets `DAY4_UNBLOCKED`, independent of publication.
- Publication is a separate distribution decision: `PUBLISHED_VERIFIED`, `PUBLICATION_BLOCKED`, or
  `NOT_ATTEMPTED`. A second identical-byte publication failure cannot change the scientific status
  or Day 4 gate.
- Day 4 becomes eligible but is never started automatically.

## 2026-07-15 — Day 3 Terminal Scientific Decision

- Invoke the one allowed expansion because the initial strict filter accepted only 46 candidates.
- Preserve the terminal 59/768 acceptance result without prompt revision, regeneration for quality,
  parser repair, oracle rewriting, or relaxed archetype balance.
- Classify Day 3 as `SCIENTIFICALLY_FAILED` with
  `INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES`; this is not a numeric zero result.
- Keep `DAY4_BLOCKED` because target training, checkpoint selection, held-out evaluation, failure
  analysis, and the six-row comparison were correctly not run.
- Record distribution as `NOT_ATTEMPTED`. The publication/science independence rule remains intact,
  but no publishable adapter exists in this failed branch.

## 2026-07-15 — Final Distribution-Matched Recovery

- Preserve the independent attempt as immutable control evidence and add one isolated final method,
  `target_synthetic_distillation_matched`, under `artifacts/day3-matched`.
- Change only the candidate-input distribution. Scale the frozen 224-row train distribution with
  Hamilton largest-remainder quotas across joint facts, numeric support, templates, and exact Qwen
  prompt-length buckets.
- Reuse the value-sensitive Day 3 semantic leakage signature unchanged; family or archetype alone
  never defines semantic identity.
- Permit one 512-candidate initial pool and one fixed 256-candidate expansion. A replayed insufficiency
  or lack of a safety-eligible checkpoint is a terminal negative that unblocks Day 4 with a negative
  distillation result.
- Keep publication independent. Release failure may set `PUBLICATION_BLOCKED` but cannot change the
  recovery status or Day 4 gate.
- Forbid a third Day 3 attempt and automatic Day 4 execution.

## 2026-07-15 — Matched Recovery Terminal Decision

- Preserve the final 719/768 acceptance result without relaxing the duplicate auto-refund quota,
  rewriting labels, changing prompts, or adding another pool. That archetype reached 4/48 accepted.
- Finalize `RECOVERY_TERMINAL_NEGATIVE` with
  `DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT` after all required replays and the immutable
  independent-versus-matched comparison pass.
- Record publication as `NOT_ATTEMPTED`; no adapter exists. Do not start Day 4 automatically.

## 2026-07-15 — Phase 3B Anchored Behavioral Transfer

- Add `target_hybrid_anchored_distillation_10` as a separate hybrid method; preserve both terminal
  pure-distillation attempts unchanged.
- Select 14 hash-ranked synthetic records in fifteen unaffected groups, all four accepted blind-spot
  records, and the lowest hash-ranked ten of fourteen original blind-spot train records.
- Define `preregistration_commit` as the clean commit containing configs, selections, hybrid data,
  confirmatory inputs/oracles, leakage audit, and schedule before real OLMo training.
- Bind preregistration through Git-tree attestation, avoiding a circular future-commit field.
- Preserve Day 2 full-target settings, whole-dataset exposure parity, parser `0.1.0`, evaluator `v0`,
  and safety-first checkpoint ordering.
- Use one 64-record confirmatory test for the primary six-system matrix. Run the original test only
  afterward as `EXPLORATORY_LEGACY_TEST`; it cannot revise the primary result.
- Keep scientific completion score-independent after integrity/replay gates and independent from
  publication. Do not start Day 4 automatically or permit another Phase 3B variant.

## 2026-07-15 — Phase 3B Distribution Lineage

- Publish the selected adapter under immutable tag `phase3b-anchored-v0.1.0`, resolving to packaging
  commit `2d7052f103ba29d56a0ecd4ce442c5dd1c4b44b2`.
- Preserve preregistration commit `cd873c5d87817f64ac2ecd04824ef1cfdb19b1ea` and scientific-result
  commit `9ced5d1704972b6c1d818fd0c79a6006d2820b1c` as separate lineage events.
- Record anonymous public-download verification in later commit
  `8718ef670e2a5f79a068da554b40603a6d4979e2`; later documentation on `main` cannot move the tag or
  alter released bytes, scientific artifacts, metrics, or the Day 4 gate.
- Finalize distribution as `PUBLISHED_VERIFIED` after one successful byte-identical verification.
  Scientific status remains `PHASE3B_SCIENTIFICALLY_COMPLETED / DAY4_UNBLOCKED` independently.

## 2026-07-15 — Phase 4 Adversarial Protocol

- Freeze all six existing systems on the untouched 32-record adversarial split before inference.
- Preserve prompt/parser `0.1.0`, evaluator `v0`, seed `20260714`, greedy MPS generation, and one
  logical run per system with one missing-record-only resume.
- Use deterministic multi-label failure tags with specific safety and semantic failures preceding
  generic strict-contract invalidity.
- Restrict migration recommendations to the six declared lexicographic profiles and report an
  explicit no-recommendation state when exclusions leave no viable target method.
- Make the validated `gpt-5.6-sol` structured memo the intended submission path. Missing credentials
  produce `READY_FOR_GPT_MEMO`; deterministic fallback completion is reserved for a genuine bounded
  API failure.
- Omit repeated seeds, new methods, new data, releases, UI implementation, and automatic Phase 5.

## 2026-07-15 — Phase 4 GPT Memo Finalization

- Accept the single repaired GPT-5.6 Sol response as authoritative only after deterministic
  revalidation against the immutable evidence graph; make no additional API request.
- Treat a many-to-one comparison as supported when every listed subject system is strictly higher
  or lower than the final reference system on the same typed evidence metric. Preserve the original
  invalid-attempt records as audit evidence.
- Preserve `artifacts/showcase/inheritbench-v0.1` as the readiness snapshot and store the validated
  GPT state separately at `artifacts/showcase/inheritbench-v0.1-gpt`.
- Freeze Phase 4 after the completed decision. Phase 5 is unblocked but never starts automatically.

## 2026-07-15 — Phase 5 Product Boundary

- Build a self-directed model-succession lab rather than a guided walkthrough, judge mode, tour,
  spotlight, or auto-advancing presentation.
- Preserve scientific/product separation: Python deterministically projects and verifies frozen
  evidence; the deployed web build consumes only committed hashed data through Node.
- Resolve every representative case from its recorded evaluation surface and fail closed rather
  than substitute, regenerate, or manually replace evidence.
- Keep confirmatory and adversarial surfaces separate with explicit denominators and no blended
  score. Render the validated GPT-5.6 Sol structured memo without regeneration or rewriting.
- Stop at `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED`. Public completion requires a
  stable unauthenticated URL and all immutable hosted-browser checks; no deployment occurs here.

## 2026-07-16 — Verified Succession Replay Product

- Make the replay engine the product core, the browser the primary judge-facing interface, and the
  CLI a thin wrapper over the same deterministic specification.
- Support only `opsroute-qwen-olmo` and `maximum-confirmed-capability` in v0.1; do not expose fake
  arbitrary-model or capability controls.
- Use one truth hierarchy: succession manifest, immutable scientific references, compact atomic
  records, replay engine, then fresh report and receipt.
- Derive `CONDITIONAL_PASS` from versioned readiness rules. Never store it as a display-only value in
  the input manifest, and never delegate readiness to GPT-5.6.
- Describe hosted mode as verified replay, not live training, inference, model rerun, or full
  scientific replay.
- Keep the actual supervision, training, checkpoint selection, held-out evaluation, replay, and
  adapter export as the existing preregistered Phase 3B command sequence. Full-workflow preflight
  reports prerequisites and commands but does not execute training.
- Preserve `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED` until a stable public URL,
  incognito deep-link access, browser integrity verification, product-flow smoke test, and desktop
  and mobile checks produce an immutable deployment-verification artifact.
