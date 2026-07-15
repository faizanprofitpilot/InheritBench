# Judge Replay

## Phase 4

The Phase 4 protocol is committed before inference and then bound to that commit through Git-tree
attestation. After the six one-time adversarial runs complete, every remaining command is offline
except the bounded GPT memo request:

```bash
uv run inheritbench phase4 replay --artifact artifacts/phase4/evaluations/<run-id>
uv run inheritbench phase4 analyze
uv run inheritbench phase4 compute-profiles
uv run inheritbench phase4 select-cases
uv run inheritbench phase4 build-evidence-pack
uv run inheritbench phase4 build-fallback-memo
uv run inheritbench phase4 generate-gpt-memo
uv run inheritbench phase4 validate-memo --memo artifacts/phase4/memo-attempts/<repair-id>
uv run inheritbench phase4 build-showcase
uv run inheritbench phase4 replay-showcase
uv run inheritbench phase4 finalize
```

The bounded GPT workflow used one initial response and one repair. The exact repaired bytes passed
the deterministic evidence validator without a third request. No model runs were repeated.

Authoritative static bundle: `artifacts/showcase/inheritbench-v0.1-gpt`. Its replay validates all
file hashes, derived tables, evidence-backed memo claims, Markdown rendering, and the completed
Phase 4 decision without network, model weights, or an accelerator. The original
`artifacts/showcase/inheritbench-v0.1` readiness snapshot remains immutable for lineage review.

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
test is separately exploratory. Exact commit lineage is:

1. Historical reference: `7283bfe22903ffc554c1f5ab210dea105df68b2b`.
2. Preregistration: `cd873c5d87817f64ac2ecd04824ef1cfdb19b1ea`.
3. Scientific result: `9ced5d1704972b6c1d818fd0c79a6006d2820b1c`.
4. Packaging/tag: `2d7052f103ba29d56a0ecd4ce442c5dd1c4b44b2`.
5. Public-download verification: `8718ef670e2a5f79a068da554b40603a6d4979e2`.

The immutable tag `phase3b-anchored-v0.1.0` resolves to the packaging commit. Later `main` commits
contain post-release verification or documentation only; they do not alter the preregistered inputs,
scientific evidence, selected adapter, release archive, or hashes.

Public release verification is machine-readable under
`artifacts/phase3b/publication-verifications/phase3b-publication-verified-4137871051bd4cfa`, and the
independent distribution decision is under
`artifacts/phase3b/distribution-decisions/phase3b-publication-verified-4137871051bd4cfa`.
