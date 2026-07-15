# Judge Replay

## Historical Anchor

```bash
uv run inheritbench day3-matched validate-configs
uv run inheritbench day3-matched freeze-baseline
uv run pytest -q tests/integration/test_day3_artifacts.py
```

The baseline command validates the immutable original Day 3 byte hashes and writes only under
`artifacts/day3-matched/historical-baselines`.

## Distribution Evidence

```bash
uv run inheritbench day3-matched replay \
  --kind fingerprint --artifact artifacts/day3-matched/fingerprints/<fingerprint-id>
uv run inheritbench day3-matched replay \
  --kind distribution --artifact artifacts/day3-matched/pools/<pool-id>
uv run inheritbench day3-matched replay \
  --kind leakage --artifact artifacts/day3-matched/pools/<pool-id>
```

These commands reconstruct the train fingerprint and verify exact Hamilton strata, prompt buckets,
numeric support, and zero cross-corpus collision evidence without modifying original artifacts.

## Scientific Evidence

Replay every materialized teacher run and the terminal filter dataset:

```bash
uv run inheritbench day3-matched replay --kind teacher --artifact <teacher-run>
uv run inheritbench day3-matched replay --kind filter --artifact <synthetic-dataset>
uv run inheritbench day3-matched replay --kind failure_analysis --artifact <analysis>
uv run inheritbench day3-matched replay --kind attempt_comparison --artifact <comparison>
```

When training and test evidence exist, also replay the schedule, training lineage, held-out
evaluation, and six-row method comparison. Finalization fails closed unless the replays required by
the observed outcome exist.

## Status Interpretation

- `RECOVERY_SCIENTIFICALLY_COMPLETED / DAY4_UNBLOCKED` means training, a safety-eligible checkpoint,
  one held-out test, analysis, comparisons, and exact replays passed.
- `RECOVERY_TERMINAL_NEGATIVE / DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT` means the bounded
  method produced valid negative evidence after filtering or checkpoint selection.
- `RECOVERY_BLOCKED / DAY4_BLOCKED` means an integrity or infrastructure prerequisite failed.

`PUBLISHED_VERIFIED`, `PUBLICATION_BLOCKED`, and `NOT_ATTEMPTED` are distribution-only statuses and
cannot change the recovery or Day 4 decision.

## Phase 3B Replay

The scientific inputs are frozen at preregistration commit
`cd873c5d87817f64ac2ecd04824ef1cfdb19b1ea`. Verify its Git-tree attestation and exact results:

```bash
uv run inheritbench phase3b validate-configs
uv run inheritbench phase3b replay --kind evaluation --artifact artifacts/phase3b/test/<run-id>
uv run inheritbench phase3b replay --kind analysis --artifact artifacts/phase3b/failure-analysis/<id>
uv run inheritbench phase3b replay --kind comparison --artifact artifacts/phase3b/comparisons/<id>
```

The primary comparison requires six completed rows with one confirmatory split hash. The original
test is separately exploratory. Commit lineage is historical reference `7283bfe`, preregistration
`cd873c5`, a later result commit, packaging/tag commit `phase3b-anchored-v0.1.0`, and optional
post-release verification commit. The tag may intentionally precede later documentation on `main`.
