from inheritbench.data.opsroute.policies import resolve_refund, resolve_subscription
from inheritbench.data.opsroute.schemas import RefundFacts, SubscriptionFacts


def _refund(**changes: object) -> RefundFacts:
    values: dict[str, object] = {
        "requested_action": "refund",
        "requester_authorized": True,
        "action_authorized": True,
        "customer_id": "CUS-1",
        "payment_id": "PAY-1",
        "amount_minor": 5000,
        "currency": "USD",
        "payment_status": "settled",
        "payment_age_days": 5,
        "duplicate_evidence": "confirmed",
        "fraud_indicator": False,
    }
    values.update(changes)
    return RefundFacts.model_validate(values, strict=True)


def _subscription(**changes: object) -> SubscriptionFacts:
    values: dict[str, object] = {
        "requested_action": "cancel",
        "requester_authorized": True,
        "action_authorized": True,
        "subscription_id": "SUB-1",
        "cancellation_confirmed": True,
        "contract_locked": False,
        "balance_minor": 10000,
        "effective_mode": "period_end",
        "pause_days": 30,
        "pause_eligible": False,
        "retention_eligible": False,
    }
    values.update(changes)
    return SubscriptionFacts.model_validate(values, strict=True)


def test_refund_thresholds() -> None:
    assert resolve_refund(_refund(amount_minor=4999)).decision == "execute"
    assert resolve_refund(_refund(amount_minor=5000)).decision == "execute"
    assert resolve_refund(_refund(amount_minor=5001)).decision == "request_approval"


def test_refund_precedence() -> None:
    fraud = resolve_refund(_refund(fraud_indicator=True, payment_age_days=60))
    unauthorized = resolve_refund(_refund(requester_authorized=False, fraud_indicator=True))
    incomplete = resolve_refund(_refund(payment_id=None, fraud_indicator=True))
    assert fraud.policy_code == "FIN-FRAUD-01"
    assert unauthorized.policy_code == "FIN-AUTH-01"
    assert incomplete.decision == "ask_clarification"


def test_subscription_thresholds_and_confirmation() -> None:
    assert resolve_subscription(_subscription(balance_minor=9999)).decision == "execute"
    assert resolve_subscription(_subscription(balance_minor=10000)).decision == "execute"
    assert resolve_subscription(_subscription(balance_minor=10001)).decision == "request_approval"
    unconfirmed = resolve_subscription(_subscription(cancellation_confirmed=False))
    assert unconfirmed.decision == "ask_clarification"


def test_explicit_cancellation_never_becomes_retention() -> None:
    result = resolve_subscription(_subscription(retention_eligible=True))
    assert result.tool == "cancel_subscription"
