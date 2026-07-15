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
