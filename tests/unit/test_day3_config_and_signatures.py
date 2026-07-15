from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from inheritbench.config import load_yaml
from inheritbench.data.opsroute.schemas import OpsRouteInput
from inheritbench.day3.config import load_experiment_config
from inheritbench.day3.pool import load_candidates, semantic_leakage_sha256
from inheritbench.day3.schemas import Day3MethodConfigV0_1


def _candidate(family: str):
    pool = next(Path("artifacts/day3/pools").glob("day3-pool-initial-*"))
    return next(item for item in load_candidates(pool) if item.scenario_family == family)


def _input_with(value: OpsRouteInput, **changes: object) -> OpsRouteInput:
    payload = value.model_dump(mode="python")
    payload.update(changes)
    return OpsRouteInput.model_validate(payload, strict=True)


def test_day3_configs_are_strict_and_locked() -> None:
    experiment = load_experiment_config(Path("configs/experiments/day3.yaml"))
    assert experiment.automatic_day4 is False
    raw = load_yaml(Path("configs/methods/target_synthetic_distillation.yaml"))
    assert isinstance(raw, dict)
    raw["surprise"] = True
    with pytest.raises(ValidationError):
        Day3MethodConfigV0_1.model_validate(raw, strict=True)


@pytest.mark.parametrize(
    ("family", "changes"),
    [
        ("refund_policy_routing", {"requested_action": "none"}),
        ("refund_policy_routing", {"requester_authorized": False}),
        ("refund_policy_routing", {"action_authorized": False}),
        ("refund_policy_routing", {"payment_id": None}),
        ("refund_policy_routing", {"amount_minor": 5001}),
        ("refund_policy_routing", {"payment_status": "pending"}),
        ("refund_policy_routing", {"payment_age_days": 31}),
        ("refund_policy_routing", {"duplicate_evidence": "incomplete"}),
        ("refund_policy_routing", {"fraud_indicator": True}),
        ("subscription_cancellation_retention", {"requested_action": "retention"}),
        ("subscription_cancellation_retention", {"requester_authorized": False}),
        ("subscription_cancellation_retention", {"action_authorized": False}),
        ("subscription_cancellation_retention", {"subscription_id": None}),
        ("subscription_cancellation_retention", {"cancellation_confirmed": False}),
        ("subscription_cancellation_retention", {"contract_locked": True}),
        ("subscription_cancellation_retention", {"balance_minor": 10001}),
        ("subscription_cancellation_retention", {"effective_mode": "immediate"}),
        ("subscription_cancellation_retention", {"pause_days": 90}),
        ("subscription_cancellation_retention", {"pause_eligible": True}),
        ("subscription_cancellation_retention", {"retention_eligible": True}),
    ],
)
def test_each_decision_relevant_fact_changes_signature(
    family: str, changes: dict[str, object]
) -> None:
    candidate = _candidate(family)
    context = dict(candidate.input.context)
    for name, value in changes.items():
        if context.get(name) == value:
            if isinstance(value, bool):
                value = not value
            elif name == "pause_days":
                value = 30 if value != 30 else 60
            elif isinstance(value, int):
                value += 1
            elif name == "effective_mode":
                value = "period_end"
            elif name == "requested_action":
                value = "refund" if family == "refund_policy_routing" else "cancel"
        context[name] = value
    changed = _input_with(candidate.input, context=context)
    assert semantic_leakage_sha256(family, changed) != candidate.semantic_leakage_sha256


def test_paraphrase_and_opaque_identifiers_preserve_signature() -> None:
    for family in ("refund_policy_routing", "subscription_cancellation_retention"):
        candidate = _candidate(family)
        context = dict(candidate.input.context)
        for key in ("customer_id", "payment_id", "subscription_id"):
            if context.get(key) is not None:
                context[key] = f"OPAQUE-{key}"
        changed = _input_with(
            candidate.input,
            request="A completely different but policy-equivalent request paraphrase.",
            context=context,
        )
        assert semantic_leakage_sha256(family, changed) == candidate.semantic_leakage_sha256


def test_tool_policy_and_field_order_are_signature_sensitive() -> None:
    candidate = _candidate("refund_policy_routing")
    fewer_tools = _input_with(candidate.input, available_tools=["refund_payment"])
    assert semantic_leakage_sha256(candidate.scenario_family, fewer_tools) != (
        candidate.semantic_leakage_sha256
    )
    policy = dict(candidate.input.policy)
    policy["refund_auto_approval_limit_minor"] = 5001
    changed_policy = _input_with(candidate.input, policy=policy)
    assert semantic_leakage_sha256(candidate.scenario_family, changed_policy) != (
        candidate.semantic_leakage_sha256
    )
    reversed_context = dict(reversed(list(candidate.input.context.items())))
    reordered = _input_with(candidate.input, context=reversed_context)
    assert semantic_leakage_sha256(candidate.scenario_family, reordered) == (
        candidate.semantic_leakage_sha256
    )


def test_pool_records_are_canonical_json() -> None:
    pool = next(Path("artifacts/day3/pools").glob("day3-pool-initial-*"))
    first = json.loads((pool / "candidate_inputs.jsonl").read_text().splitlines()[0])
    assert first["candidate_id"].startswith("synthetic_opsroute_v010_")
