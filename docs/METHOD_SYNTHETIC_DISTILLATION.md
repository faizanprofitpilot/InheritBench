# Synthetic Distillation Methods

## Independent Attempt

The immutable `independent_pool_attempt` generated 768 independent procedural candidates. The
verified Qwen teacher produced only 59 strict, policy-exact accepted outputs across five of sixteen
archetypes. The frozen 14-per-archetype selection was therefore impossible, and no target training
or held-out evaluation occurred.

## Distribution-Matched Recovery

`distribution_matched_attempt` is the final bounded Day 3 recovery. It changes only the candidate
input distribution. Teacher identity, filtering, selection quota, OLMo training method, validation,
test, parser, metrics, model revisions, and seed remain frozen.

The method reconstructs all 224 committed training inputs and records a content-addressed
distribution fingerprint. Within each archetype, empirical joint strata are scaled to 32 initial or
16 expansion slots with Hamilton largest-remainder apportionment. The strata include categorical
facts, numeric buckets, policy outcome, tool, approval requirement, template family, and exact
Qwen prompt-length bucket. Ties use a domain-separated SHA-256 rank.

Candidate generation samples only train-observed support through the frozen OpsRoute rendering
recipe. It creates novel opaque IDs and surfaces but introduces no train-unseen threshold examples.
Each slot receives at most 64 deterministic collision retries. Exact distribution equality and zero
leakage are hard gates rather than quality scores.

## Leakage Contract

The recovery reuses the Day 3 semantic leakage function unchanged. Separate surface, full-input,
record, identifier, and semantic hashes detect distinct collision classes. The semantic payload
normalizes opaque identifier values while retaining identifier presence and every decision-relevant
numeric value, status, flag, requested action, available tool, and policy constant. It therefore
does not collapse records merely because they share a family or archetype.

Candidates are checked against all frozen splits, fixtures, smoke and diagnostic references, Day 2
manifests, both original Day 3 pools, and earlier matched candidates. Metadata-only manifests are
retained as provenance but are not falsely counted as compared examples.

## Label Access

Teacher generation can open candidate inputs, audits, pool manifests, and the verified adapter
reference only. It cannot open the separate deterministic oracle. Filtering compares terminal raw
teacher outputs with that oracle and accepts only `STRICT_VALID`, exactly policy-matching, safe
outputs. The assistant label is the teacher's trimmed strict candidate without rewriting.

Target training can open only the selected matched synthetic artifact. Frozen data, oracle,
validation, test, adversarial, fixture, and original Day 3 paths are rejected. Original labels used
directly by the target are always zero; the 224 labels used upstream to train the teacher remain
explicit in accounting.

## Outcomes

Exactly 224 accepted examples, 14 per archetype, permit fresh OLMo training up to 272,643
whole-sequence tokens. A safety-eligible checkpoint permits one 32-record held-out test. Poor test
quality is still a scientifically completed result when replay and comparison gates pass.

Insufficient accepted data after the single expansion, or no safety-eligible checkpoint, is a
replayed terminal negative that unblocks Day 4 with a negative distillation result. Integrity or
infrastructure failures remain blocked. No third Day 3 attempt is allowed, and Day 4 is never
started automatically.

Publication is a separate distribution gate. A release failure cannot revise a completed or
terminal-negative scientific recovery decision.

## Executed Matched Result

The matched teacher completed 768/768 outputs with zero model failures. Strict filtering accepted
719 (`93.6198%`), rejecting 49 policy-contract mismatches. Fifteen archetypes exceeded the frozen
14-example quota, while duplicate auto-refund accepted only 4/48. The balanced set therefore could
not be selected after the one allowed expansion.

The replayed final result is
`RECOVERY_TERMINAL_NEGATIVE / DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT`. No target schedule,
training, validation, test, adapter, six-row comparison, release, third attempt, or automatic Day 4
work exists.

Phase 3B does not change either pure-distillation result. It is a separately named hybrid condition
that explicitly consumes ten original labels to cover the immutable teacher blind spot. Its claims,
accounting, confirmatory surface, preregistration commit, and status live under `artifacts/phase3b`.
