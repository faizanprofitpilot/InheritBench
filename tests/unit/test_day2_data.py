import json
from pathlib import Path

from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.day2.data import load_schedule, load_subset, select_limited_examples

_LIMITED_IDS = {
    "opsroute_v010_refund_duplicate_approval_01_bc3ef00f",
    "opsroute_v010_refund_duplicate_approval_05_1c10b058",
    "opsroute_v010_refund_duplicate_auto_refund_02_f8c83022",
    "opsroute_v010_refund_duplicate_auto_refund_09_0eee0b95",
    "opsroute_v010_refund_expired_window_04_2b0665f8",
    "opsroute_v010_refund_fraud_review_09_567c5ffc",
    "opsroute_v010_refund_incomplete_evidence_11_a7997a7c",
    "opsroute_v010_refund_no_refund_request_10_06541074",
    "opsroute_v010_refund_pending_payment_03_71bfdc9f",
    "opsroute_v010_refund_pending_payment_12_1f477361",
    "opsroute_v010_refund_unauthorized_requester_09_77a590a3",
    "opsroute_v010_refund_unauthorized_requester_13_f77f419f",
    "opsroute_v010_subscription_cancellation_approval_06_208a08d0",
    "opsroute_v010_subscription_cancellation_approval_13_b62562d8",
    "opsroute_v010_subscription_confirmation_required_07_7af8ac0a",
    "opsroute_v010_subscription_confirmation_required_11_179bc970",
    "opsroute_v010_subscription_eligible_cancellation_07_753fb65f",
    "opsroute_v010_subscription_eligible_cancellation_12_bb36e714",
    "opsroute_v010_subscription_eligible_pause_10_d2635d6d",
    "opsroute_v010_subscription_eligible_retention_13_2afda5e9",
    "opsroute_v010_subscription_ineligible_retention_02_b63a47ca",
    "opsroute_v010_subscription_ineligible_retention_06_08f12558",
    "opsroute_v010_subscription_no_subscription_request_08_b8dc961b",
    "opsroute_v010_subscription_unauthorized_requester_13_584cf1f0",
}


def _bundle() -> Path:
    matches = list(Path("artifacts/day2/data").glob("day2-data-*"))
    assert len(matches) == 1
    return matches[0]


def _train_records() -> list[OpsRouteExample]:
    with Path("data/opsroute/v0.1.0/train.jsonl").open(encoding="utf-8") as handle:
        return [OpsRouteExample.model_validate(json.loads(line), strict=True) for line in handle]


def test_limited_selection_is_exact_and_order_independent() -> None:
    records = _train_records()
    selected = select_limited_examples(records)
    reversed_selected = select_limited_examples(list(reversed(records)))
    assert {item.example_id for item in selected} == _LIMITED_IDS
    assert [item.example_id for item in selected] == [item.example_id for item in reversed_selected]


def test_frozen_subsets_are_split_safe() -> None:
    bundle = _bundle()
    full = load_subset(bundle, "full_train")
    limited = load_subset(bundle, "limited_train")
    validation = load_subset(bundle, "full_validation")
    test = load_subset(bundle, "final_test")
    assert (
        len(full.entries),
        len(limited.entries),
        len(validation.entries),
        len(test.entries),
    ) == (
        224,
        24,
        32,
        32,
    )
    assert set(full.example_ids).isdisjoint(validation.example_ids)
    assert set(full.example_ids).isdisjoint(test.example_ids)
    assert set(limited.example_ids) <= set(full.example_ids)
    assert not any(item.startswith("fixture_") for item in full.example_ids)


def test_locked_token_schedules_match_fairness_contract() -> None:
    bundle = _bundle()
    source = load_schedule(bundle, "source_primary")
    full = load_schedule(bundle, "target_primary")
    limited = load_schedule(bundle, "target_limited_primary")
    assert (source.processed_tokens, source.example_exposures, source.optimizer_steps) == (
        379768,
        896,
        224,
    )
    assert (full.processed_tokens, full.example_exposures, full.optimizer_steps) == (
        272643,
        672,
        168,
    )
    assert (limited.processed_tokens, limited.residual_tokens) == (272634, 9)
    assert limited.example_exposures == 672
    assert limited.optimizer_steps == 168
    assert set(limited.per_example_exposures.values()) <= {27, 28, 29}
    assert limited.budget_ratio == 272634 / 272643
