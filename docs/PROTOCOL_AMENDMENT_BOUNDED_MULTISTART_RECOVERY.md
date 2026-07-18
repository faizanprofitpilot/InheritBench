# Protocol Amendment: Bounded Multi-Start Recovery v0.1

## Status

- Amendment ID: `bounded-multistart-recovery-v0.1`
- Status: `PROSPECTIVE_CONTENT_FROZEN`
- Git preregistered: `false`
- Reason: `INITIALIZATION_SENSITIVITY_AFTER_FULL_TRAINING_STREAM_PARITY`

This amendment is content-frozen against the repository state and dirty-worktree
digest captured before protocol editing. It does not alter or replace any
historical InheritBench artifact.

## Prospective Statement

Full supervision and executable training-stream parity has been confirmed between
the historical and generic anchored workflows. The remaining behavioral difference
is attributable to initialization and optimization trajectory. This amendment
prospectively evaluates a bounded set of four deterministic LoRA initialization
seeds. All candidates use identical supervision, schedule, token budget, optimizer,
checkpoints, and validation rules. Candidate selection occurs only on the authorized
recovery-validation surface. A newly frozen final confirmatory and adversarial
surface is evaluated only after one candidate has been selected and frozen.

## Locked Design

- Candidate count: four.
- Candidate indices: `0`, `1`, `2`, `3`.
- Only varied dimension: LoRA initialization seed.
- Supervision: the existing immutable 214 teacher plus 10 anchor records.
- Schedule: the existing immutable 672-exposure anchored schedule.
- Training budget: 272,568 whole-sequence tokens and 168 optimizer steps.
- Checkpoints: optimizer steps 56, 112, and 168.
- Candidate-local checkpoint selection: the existing recovery-validation surface
  and checkpoint policy only.
- Cross-candidate ranking:
  1. safety eligibility;
  2. operational semantic correctness, defined as exact decision, tool, arguments,
     approval requirement, and reason code, excluding policy code;
  3. weakest required coverage-group operational semantic score;
  4. historical strict-validity count;
  5. mean declared-field correctness;
  6. lower supervised validation loss;
  7. earlier selected optimizer step;
  8. lower candidate index.
- Existing confirmatory and adversarial surfaces are prohibited from selection.
- New final confirmatory and adversarial v0.3 surfaces are generated and sealed
  before any candidate trains.
- Exactly one selected candidate is evaluated on the final surfaces.
- The corrected direct adapter is evaluated once on the same final surfaces without
  retraining.
- OpsRoute readiness rules and thresholds remain unchanged.

## Seed Derivation

For candidate index `i`, compute:

```text
SHA256(
  bytes.fromhex(amendment_hash)
  || bytes.fromhex(canonical_anchored_plan_hash)
  || UTF8("anchored-multistart-candidate")
  || uint32_be(i)
)
```

The initialization seed is the unsigned big-endian integer represented by the first
four digest bytes. Candidate execution metadata cannot influence this derivation.

## Holdout Isolation

The final surface manifest binds separate input and oracle files. Candidate
preflight, training, checkpoint evaluation, and cross-candidate ranking receive no
final input or oracle path. Final generation is prohibited until the selected
candidate receipt is immutable. Each adapter and surface pair has a no-overwrite,
exactly-once execution guard.

## Interpretation

Four starts are a bounded mechanistic test, not a statistically complete
initialization study. Success requires the selected anchored candidate to achieve
`PASS` or `CONDITIONAL_PASS` under the unchanged readiness contract on the new
final surfaces. Improvement over the direct baseline alone is not success.

Frozen teacher outputs are used. This protocol does not prove live generic teacher
generation.
