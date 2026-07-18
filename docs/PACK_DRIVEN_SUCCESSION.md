# Pack-Driven Succession v0.2

InheritBench v0.2 adds a task-neutral local succession engine beside the immutable Day 1–Phase 5
scientific workflows. Developer-owned capability packs now drive validation, planning, source and
target execution, supervision, LoRA training, checkpoint selection, clean and adversarial
evaluation, readiness, adapter export, replay, and browser inspection.

The published Qwen → OLMo Phase 3B result remains unchanged. v0.2 does not reinterpret or replace
that evidence.

## Supported Boundary

The product is generic across capability packs, not arbitrary model architectures.

- Capability profile: `structured-json-v0.1`.
- Strategies: `direct-target-lora-v0.1` and `anchored-behavioral-transfer-v0.1`.
- Real source registry: pinned Qwen2.5 0.5B Instruct plus an explicitly verified adapter.
- Real target registry: pinned OLMo-2 1B Instruct with explicit Q/K/V/O LoRA modules.
- Test registry: deterministic fake source and target adapters.
- Executed real backend: Apple MPS.

Unknown models, revisions, architectures, backends, LoRA mappings, pack fields, vocabulary values,
unsafe paths, tampered hashes, and unauthorized data access fail closed.

Generic packages under `inheritbench.capability`, `inheritbench.model_adapters`,
`inheritbench.strategies`, and `inheritbench.orchestration` cannot import OpsRoute or any historical
Day/Phase module. Reference projection code is isolated under `inheritbench.reference_packs`.

## Author a Pack

```bash
uv run inheritbench capability init purchase-routing \
  --template structured-json-v0.1 \
  --output capabilities/purchase-routing/v0.1.0

uv run inheritbench capability validate capabilities/purchase-routing/v0.1.0
uv run inheritbench capability inspect capabilities/purchase-routing/v0.1.0 --json -
```

`capability init` creates a complete validating `DRAFT` sample. Model execution accepts only
`READY` or `REFERENCE`; `FIXTURE_ONLY` execution is hidden and test-only.

Inputs, evaluator oracles, direct labels, and anchors remain separate. Teacher generation receives
transfer inputs without oracle objects. Target training receives only frozen labeled supervision.
Validation, confirmatory, and adversarial oracles are exposed only to their authorized stages.

## Plan and Execute

```bash
uv run inheritbench succession plan \
  --pack capabilities/opsroute/v0.2.0 \
  --source-config configs/models/source.yaml \
  --target-config configs/models/target.yaml \
  --strategy direct-target-lora-v0.1 \
  --output runs

uv run inheritbench succession run --plan runs/<run-id> --device mps
uv run inheritbench succession inspect --run runs/<run-id> --json -
uv run inheritbench succession replay --run runs/<run-id> --output runs/replays
uv run inheritbench succession export-web --run runs/<run-id> --output web_bundle.json
```

`succession plan` validates the pack, resolves exact registry entries, hashes every authorized input,
and freezes a content-addressed plan without loading a model. Execution persists immutable stage
bundles and a mutable active pointer. Reusing completed stages is idempotent; changing a planned
input, repeating a final surface, or overwriting an artifact is rejected.

`inheritbench succeed` combines planning and execution only when `--accept-plan` is explicit.

## Direct Target LoRA

`direct-target-lora-v0.1` performs:

1. source capability gate;
2. untouched-target baseline;
3. direct-label validation;
4. deterministic whole-sequence schedule;
5. fresh-target LoRA training;
6. validation-only safety-eligible checkpoint selection;
7. exactly-once confirmatory evaluation;
8. exactly-once adversarial evaluation;
9. deterministic readiness;
10. fresh-base adapter verification, export, and model-free replay.

Checkpoint ordering is fixed: semantic match, strict validity, minimum coverage-group semantic
score, mean declared-field correctness, lower supervised validation loss, then earlier step.

## Anchored Behavioral Transfer

`anchored-behavioral-transfer-v0.1` accepts either model-generated transfer outputs or a
pack-authorized frozen-output artifact, evaluates them internally against separate oracles, and
selects strict, semantically exact, vocabulary-valid, safety-eligible labels by deterministic group
rank. The OpsRoute reference profile uses the verified frozen-output artifact and does not prove
live generic teacher generation.

If a group quota is incomplete, the run persists `ANCHORS_REQUIRED` with exact deficits. Added
anchors must:

- use `label_origin=anchor` and the dedicated `anchor` surface;
- conform to input/output schemas and controlled vocabularies;
- carry valid content and label hashes;
- match a declared deficit group;
- avoid ID, byte-content, and semantic collisions with evaluation surfaces.

Resume reuses the immutable teacher stage. It does not regenerate failed teacher outputs or repeat
completed work. Direct, anchor, teacher, candidate, acceptance, rejection, and upstream-label counts
remain explicit.

The generic strategy replayed the historical matched-teacher evidence without OpsRoute logic:

- 768 candidate outputs;
- 719 accepted teacher outputs;
- four accepted outputs in `refund_policy_routing:duplicate_auto_refund`;
- a deficit of ten;
- 214 selected teacher labels;
- ten required direct anchors;
- 224 final records after intervention.

The separate Purchase Approval fixture demonstrated the same generic intervention flow with a
different schema, vocabulary, tools, safety predicates, thresholds, and group counts.

## Real Product Integration Run

The required local `PRODUCT_INTEGRATION_RUN` executed the v0.2 OpsRoute reference pack with real
Qwen and OLMo models:

- run ID: `succession-opsroute-direct-target-lora-v0.1-87c29fead2628e49`;
- source gate: 32 real Qwen-adapter generations;
- target baseline: 32 untouched OLMo generations;
- training: 224 direct labels, 272,643 tokens, 168 optimizer steps;
- checkpoints: 56, 112, and 168;
- selected checkpoint: 112 after safety eligibility;
- fresh-base adapter reload: passed;
- confirmatory: one 64-record run;
- adversarial: one 32-record run;
- exported adapter SHA-256:
  `303339a221c616a585d07247896377a5b75c690f04c8a1b567edf3d45b6760a4`;
- model-free replay: passed.

The result is an honest product block:

- confirmatory semantic exactness: 36/64;
- confirmatory strict validity: 52/64;
- confirmatory blocker safety findings: zero;
- adversarial semantic exactness: 18/32;
- adversarial strict validity: 29/32;
- adversarial blocker safety findings: two;
- readiness: `MIGRATION_BLOCKED`.

This local integration run uses previously known evaluation surfaces and is not new benchmark
evidence. It proves that the pack-driven engine actually loaded, trained, selected, evaluated,
exported, and replayed a real successor while preserving the ability to reject it.

## Seeded Reproduction and Anchored Reference Execution

The repaired runtime adds plan-seeded initialization, Python/NumPy/Torch/CUDA/MPS RNG persistence,
exact frozen schedules, full encoding manifests, decomposed evaluator facts, and
strategy-configured checkpoint surfaces. The historical direct run remains unreconstructible
because its original LoRA initialization was not recorded. A prospective amendment therefore
required the corrected seeded protocol to reproduce itself before anchored execution.

Independent direct execution
`succession-opsroute-direct-target-lora-v0.1-03-8795423ea3013599` achieved:

- exact canonical plan, supervision, encoding, schedule, optimizer, and inference identity;
- bitwise equality for all 168 loss, gradient, and learning-rate telemetry points;
- exact checkpoints, selected step 168, raw outputs, evaluator facts, safety findings, readiness,
  and exported adapter payload;
- `SEEDED_PROTOCOL_REPRODUCIBILITY_CONFIRMED` and
  `BITWISE_REPRODUCIBILITY_CONFIRMED`.

One prior execution is preserved after an unstable pickle-based RNG observability hash caused a
false post-training stop. A second execution is preserved after an MPS gradient spike. Neither
changed training settings or scientific evidence.

The seeded gate permitted real generic anchored run
`succession-opsroute-anchored-behavioral-transfer-v0.1-00-ee7a07404b124c1b`:

- bound the complete 14-record authorized anchor pool before execution;
- loaded 768 frozen teacher outputs, accepted 719, and selected 214;
- derived `duplicate_auto_refund` at 4/14 and persisted a ten-record `ANCHORS_REQUIRED` deficit;
- selected the exact lowest-ranked ten anchors only after the deficit existed;
- resumed from immutable teacher and intervention manifests without re-filtering teacher output;
- trained fresh OLMo for 272,568 tokens and 168 optimizer steps;
- selected checkpoint 168, exported adapter
  `fe6cc74f9a4696c99f72a1a82572aa62fdd2092c1ac1a143844bd48777fba34c`, verified fresh-base
  reload, and passed model-free replay;
- produced 53/64 confirmatory semantic exactness, 64/64 historical strict validity, zero clean
  blocker safety findings, 19/32 adversarial semantic exactness, 30/32 adversarial historical
  strict validity, and two adversarial blocker safety findings.

The unchanged readiness contract returned `MIGRATION_BLOCKED` because one clean coverage group was
0/4. The primary classification is `GENERIC_ANCHORED_RECOVERY_FAILED`; no quality rerun or settings
search followed. Historical Phase 3B behavioral parity was also not confirmed and remains a
secondary comparison rather than the primary gate.

This run proves generic pack ingestion, frozen teacher-output filtering, deficit discovery,
`ANCHORS_REQUIRED`, deterministic anchor selection, resume, real training, evaluation, export,
reload, readiness, replay, and browser inspection. It does not prove live generic teacher
generation.

## Bounded Multi-Start Recovery

After confirming supervision and executable training-stream identity, a prospective amendment
tested whether the anchored result was sensitive to LoRA initialization. Four seeds were derived
from the frozen amendment and canonical anchored plan. All candidates used the same 214 teacher
labels, ten anchors, 672 exposures, 272,568-token schedule, optimizer, checkpoint cadence, recovery
validation, generation settings, and readiness contract.

All four MPS trajectories crossed the predeclared numerical-instability guard. Candidates 0 and 1
failed before checkpoint 56; candidates 2 and 3 preserved ineligible step-56 checkpoints after at
least 90,856 processed tokens. No candidate completed validation, so the engine produced:

```text
NO_SAFETY_ELIGIBLE_CANDIDATE
NO_CANDIDATE_SELECTED
BLOCKED_BEFORE_FINAL_EVALUATION
readiness: NOT_RUN
final evaluation calls: 0
```

The prospectively frozen 64-record confirmatory and 32-record adversarial surfaces remained sealed.
No direct or anchored score exists on those surfaces. The model-free replay verifies the terminal
candidate states, ranking, surface seal, and absence of final evaluation. The local inspector
renders this v0.4 bundle without converting absent evidence into zeros.

### Numerical-guard repair and authorized rerun

An evidence-only audit subsequently established that the terminal guard had classified finite
pre-clip gradient norms above 100 as instability even though clipping had already succeeded. The
implementation correction records pre- and post-clip norms independently and fails only on
non-finite loss, gradients, parameters, or optimizer state. It does not change supervision,
schedule, optimizer, checkpoints, seeds, selection, readiness, or either sealed final surface.

All four original seeds were restarted under new execution identities and completed 168 optimizer
steps. Validation-only ranking selected candidate 0 at step 168. Its adapter
`bbfd685856645bde4bb1d45e1da239d567fa412a65e433483325227f6129f3e7` passed fresh-base reload.
The selected candidate and direct control then received one logical evaluation on each frozen v0.3
surface:

| System | Clean operational | Clean exact | Clean strict | Adversarial operational | Adversarial exact | Adversarial strict | Blocker findings |
|---|---:|---:|---:|---:|---:|---:|---:|
| Direct control | 62/64 | 50/64 | 64/64 | 16/32 | 12/32 | 30/32 | 2 adversarial |
| Repaired anchored | 64/64 | 63/64 | 64/64 | 20/32 | 20/32 | 31/32 | 2 adversarial |

The anchored candidate had zero clean blocker findings. Its one adversarial unauthorized action and
one approval bypass occurred on the same record. The engine therefore finalized
`GENERIC_ANCHORED_RECOVERY_CONFIRMED / CONDITIONAL_PASS`, and model-free replay passed over all 192
saved predictions. This result proves the generic pack, frozen-output filtering, intervention,
training, selection, evaluation, export, reload, readiness, and replay path. It still does not
prove live generic source-teacher generation.

The earlier repaired direct baseline remains:

- run ID: `succession-opsroute-direct-target-lora-v0.1-200d8ad795f4bb0f`;
- engine: `inheritbench-generic-succession-v0.2.2`;
- exact supervision: 224 records;
- exact frozen schedule: 672 exposures, 272,643 tokens, 168 optimizer steps;
- selected checkpoint: 168;
- confirmatory: 48/64 semantic, 64/64 historical strict, zero blocker safety findings;
- adversarial: 22/32 semantic, 30/32 historical strict, two blocker safety findings;
- model-free replay: passed.

The historical training/inference parity gate did not pass. It matched the schedule, supervision,
encoding, optimizer contract, selected checkpoint, historical strict validity, and safety findings,
but the historical direct adapter produced 51/64 confirmatory semantic matches. The loss streams
share the exact first loss but diverge immediately in first-step gradient norm
(`3.032052516937256` generic versus `3.040402889251709` historical).

Source and artifact inspection confirmed that the historical Day 2 trainer attached randomly
initialized LoRA tensors before applying the declared seed. It did not record an initial-adapter
hash or MPS RNG state. Exact historical initialization is therefore not reconstructible from the
immutable evidence. The resulting classification is:

```text
GENERIC_DIRECT_TRAINING_INFERENCE_PARITY_FAILED
BLOCKED_BEFORE_ANCHORED_RUN
HISTORICAL_UNSEEDED_ADAPTER_INITIALIZATION_NOT_RECONSTRUCTIBLE
```

That failed historical reconstruction is preserved. It no longer substitutes for the independent
seeded self-reproduction gate described above.

## Local Browser Inspection

Export `web_bundle.json`, open `/run/local/`, and select the file. Browser verification:

- accepts at most 5 MiB;
- validates a task-neutral Zod schema;
- verifies the embedded SHA-256 with Web Crypto;
- renders PASS, CONDITIONAL_PASS, MIGRATION_BLOCKED, and ANCHORS_REQUIRED states;
- escapes raw JSON;
- makes no upload, runtime API call, or external request.

The browser validates a local product bundle. Offline Python replay remains the authoritative
model-free execution verification.

## Output and Replay

Completed runs contain the frozen plan, input manifest, immutable stage history, raw generations,
normalized evaluations, schedule and training telemetry, checkpoint decision, readiness report,
residual failures, label and compute accounting, adapter identity, evidence manifest, replay
receipt, and browser bundle.

Replay verifies planned inputs and adapter bytes, rebuilds all surface aggregates and readiness from
saved atomic records, compares them with stored values, and writes a fresh receipt without loading
models.

## Limitations

- Only the explicit Qwen and OLMo registry entries are supported for real execution.
- Purchase Approval is model-free test evidence, not a transfer claim.
- The v0.2 real integration run ended `MIGRATION_BLOCKED`.
- The first generic anchored reference run completed but remained `MIGRATION_BLOCKED`. The repaired
  prospectively frozen multi-start run later reached `CONDITIONAL_PASS`; both remain local product
  evidence, not replacements for the published Phase 3B result.
- The OpsRoute anchored reference path consumes verified frozen teacher outputs; live generic
  source-teacher generation is not proven.
- No hosted training, arbitrary upload, model guessing, prompt search, or automatic architecture
  support is claimed.
- The immutable Phase 3B anchored adapter remains the published scientific successor.
