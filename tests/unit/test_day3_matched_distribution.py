from __future__ import annotations

from collections import Counter
from pathlib import Path

from inheritbench.data.opsroute.schemas import OpsRouteInput
from inheritbench.day3.pool import semantic_leakage_sha256
from inheritbench.day3_matched.config import load_pool_config
from inheritbench.day3_matched.distribution import apportioned_assignments
from inheritbench.day3_matched.schemas import (
    DistributionFingerprintV0_1,
    DistributionStratumV0_1,
)


def _stratum(index: int, count: int) -> DistributionStratumV0_1:
    family = "refund_policy_routing"
    payload = {
        "stratum_sha256": f"{index:064x}",
        "scenario_family": family,
        "archetype": "duplicate_auto_refund",
        "template_family": f"refund.duplicate_auto_refund.{index}",
        "prompt_bucket": "prompt_368_375",
        "numeric_buckets": {"amount_minor": "amount_900_1999", "payment_age_days": "age_1_10"},
        "categorical_facts": {},
        "expected_decision": "execute",
        "expected_tool": "refund_payment",
        "expected_approval_required": False,
        "expected_policy_code": "FIN-REFUND-01",
        "expected_reason_code": "DUPLICATE_PAYMENT_CONFIRMED",
        "train_count": count,
    }
    return DistributionStratumV0_1.model_validate(payload, strict=True)


def test_pool_config_locks_unseen_boundaries() -> None:
    config = load_pool_config(Path("configs/synthetic/day3_matched_pool.yaml"))
    assert config.forbidden_boundary_values == {
        "amount_minor": [4999, 5000, 5001],
        "payment_age_days": [30, 31],
        "balance_minor": [9999, 10000, 10001],
    }


def test_hamilton_apportionment_preserves_exact_archetype_quota() -> None:
    base = [_stratum(0, 5), _stratum(1, 5), _stratum(2, 4)]
    strata = []
    archetypes = [
        "duplicate_auto_refund",
        "duplicate_approval",
        "incomplete_evidence",
        "expired_window",
        "fraud_review",
        "unauthorized_requester",
        "pending_payment",
        "no_refund_request",
    ]
    for family_index, family in enumerate(
        ("refund_policy_routing", "subscription_cancellation_retention")
    ):
        for archetype_index, archetype in enumerate(archetypes):
            for index, item in enumerate(base):
                payload = item.model_dump(mode="python")
                identity = family_index * 100 + archetype_index * 3 + index
                payload["stratum_sha256"] = f"{identity:064x}"
                payload["scenario_family"] = family
                payload["archetype"] = archetype
                strata.append(DistributionStratumV0_1.model_validate(payload, strict=True))
    fingerprint = DistributionFingerprintV0_1.model_construct(strata=strata)
    assignments = apportioned_assignments(fingerprint, "initial", 32)
    assert len(assignments) == 16
    assert {len(values) for values in assignments.values()} == {32}
    sample = Counter(assignments[("refund_policy_routing", "duplicate_auto_refund")])
    assert sorted(sample.values()) == [9, 11, 12]


def test_semantic_signature_is_value_sensitive_not_archetype_only() -> None:
    base = OpsRouteInput(
        request="Please refund the duplicate.",
        context={
            "requested_action": "refund",
            "requester_authorized": True,
            "action_authorized": True,
            "customer_id": "CUS-A",
            "payment_id": "PAY-A",
            "amount_minor": 1500,
            "currency": "USD",
            "payment_status": "settled",
            "payment_age_days": 10,
            "duplicate_evidence": "confirmed",
            "fraud_indicator": False,
        },
        available_tools=["refund_payment", "escalate_fraud_review"],
        policy={
            "refund_auto_approval_limit_minor": 5000,
            "refund_window_days": 30,
            "currency": "USD",
            "rules": [],
        },
    )
    changed = base.model_copy(update={"context": {**base.context, "amount_minor": 1501}})
    assert semantic_leakage_sha256("refund_policy_routing", base) != (
        semantic_leakage_sha256("refund_policy_routing", changed)
    )
