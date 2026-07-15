# Anchored Behavioral Transfer

## Method Identity

- Method: `target_hybrid_anchored_distillation_10`
- Attempt: `phase3b_anchored_behavioral_transfer`
- Classification: hybrid synthetic plus targeted original anchors
- Seed: `20260714`
- Source teacher: pinned Qwen plus verified Day 2 adapter
- Target: fresh pinned OLMo with rank-8 Q/K/V/O LoRA
- Preregistration commit: `cd873c5d87817f64ac2ecd04824ef1cfdb19b1ea`

## Data Composition

The frozen matched teacher pool contains 719 accepted outputs. Fifteen family/archetype groups
contribute their lowest 14 SHA-256-ranked accepted records. Duplicate auto-refund contributes all
four accepted records plus the lowest ten SHA-256-ranked original train records. The ten-label count
is exactly the immutable deficit `14 - 4`; no output, validation score, latency, or target behavior
influences anchor selection.

The target directly consumes 214 exact teacher strict candidates and ten canonical original action
contracts. It also depends upstream on 224 labels used to train the teacher and 224 labeled records
used to design the matched distribution. The method is not label-free.

## Separation and Leakage

Confirmatory validation contains 32 new deterministic rows and confirmatory test contains 64. Inputs
and oracles are stored separately. Generation stays within train-supported facts and excludes the
frozen unseen boundaries. Surface, input-content, record, ID, and value-sensitive semantic hashes
all have zero cross-corpus collisions. Confirmatory test metrics were not inspected before the
selected checkpoint was frozen.

## Training and Selection

The whole-sequence schedule exposes every one of 224 records exactly three times: 642 teacher-label
exposures and 30 anchor exposures. It processes 272,568 tokens, leaving a 75-token residual against
the 272,643 cap. Training uses the Day 2 full-target optimizer, scheduler, clipping, rank, alpha,
dropout, accumulation, and checkpoint cadence unchanged.

Steps 56 and 112 were rejected by the frozen safety filter. Step 168 completed 32 validation
predictions with 84.375% semantic exactness, 100% strict validity, and zero unauthorized actions,
approval bypasses, or false actions. It reloaded into a fresh base before test.

## Confirmatory Result

The selected hybrid completed all 64 primary predictions with 85.9375% semantic exactness, 100%
strict validity, perfect decision/tool/approval/argument scores, and zero safety violations. Its nine
semantic misses are policy-code mismatches concentrated in three subscription archetypes; the
anchored duplicate-auto-refund group is 4/4 semantic exact. All six systems share one test hash and
replay exactly.

The later original 32-record test result is exploratory and scores 100% semantic/strict. It cannot
revise the confirmatory result.

## Status and Limits

`PHASE3B_SCIENTIFICALLY_COMPLETED / DAY4_UNBLOCKED` is independent of publication and does not start
Day 4 automatically. Results apply only to Qwen→OLMo, OpsRoute v0.1.0, parser/prompt `0.1.0`,
evaluator `v0`, and one deterministic seed. No repeated seed, adversarial evaluation, additional
anchor count, prompt revision, fallback model, or further Phase 3B variant is permitted.
