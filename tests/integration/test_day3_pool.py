from collections import Counter
from pathlib import Path

from inheritbench.day3.pool import load_candidates, load_oracles
from inheritbench.day3.schemas import LeakageAuditV0_1, SyntheticPoolManifestV0_1


def test_frozen_day3_initial_pool_is_balanced_and_collision_free() -> None:
    paths = list(Path("artifacts/day3/pools").glob("day3-pool-initial-*"))
    assert len(paths) == 1
    pool = paths[0]
    manifest = SyntheticPoolManifestV0_1.model_validate_json(
        (pool / "manifest.json").read_bytes(), strict=True
    )
    audit = LeakageAuditV0_1.model_validate_json(
        (pool / "leakage_audit.json").read_bytes(), strict=True
    )
    candidates = load_candidates(pool)
    oracles = load_oracles(pool)
    counts = Counter((item.scenario_family, item.archetype) for item in candidates)
    assert manifest.candidate_count == 512
    assert len(counts) == 16
    assert set(counts.values()) == {32}
    assert len(oracles) == 512
    assert audit.zero_overlap is True
    assert audit.unique_semantic_count == 512
    assert audit.unique_input_content_count == 512


def test_frozen_day3_pool_covers_exact_boundaries() -> None:
    pool = next(Path("artifacts/day3/pools").glob("day3-pool-initial-*"))
    candidates = load_candidates(pool)
    refund_amounts = {
        item.input.context.get("amount_minor")
        for item in candidates
        if item.scenario_family == "refund_policy_routing"
    }
    refund_ages = {
        item.input.context.get("payment_age_days")
        for item in candidates
        if item.scenario_family == "refund_policy_routing"
    }
    balances = {
        item.input.context.get("balance_minor")
        for item in candidates
        if item.scenario_family == "subscription_cancellation_retention"
    }
    assert {4999, 5000, 5001} <= refund_amounts
    assert {30, 31} <= refund_ages
    assert {9999, 10000, 10001} <= balances
