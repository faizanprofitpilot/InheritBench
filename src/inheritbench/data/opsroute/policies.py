"""Pure deterministic OpsRoute policy resolvers."""

from __future__ import annotations

from inheritbench.data.opsroute.schemas import RefundFacts, SubscriptionFacts
from inheritbench.evaluation.contracts import ActionContract


def resolve_refund(facts: RefundFacts) -> ActionContract:
    if not facts.requester_authorized:
        return _no_tool("refuse", "FIN-AUTH-01", "REQUESTER_NOT_AUTHORIZED")
    if facts.requested_action == "refund" and (
        facts.payment_id is None or facts.duplicate_evidence == "incomplete"
    ):
        return _no_tool(
            "ask_clarification",
            "FIN-REFUND-04",
            "DUPLICATE_EVIDENCE_INCOMPLETE",
        )
    if facts.requested_action == "refund" and not facts.action_authorized:
        return _no_tool("no_action", "FIN-NOACT-01", "NO_REFUND_ACTION_REQUESTED")
    if facts.requested_action == "refund" and facts.fraud_indicator:
        assert facts.payment_id is not None
        return ActionContract(
            decision="request_approval",
            tool="escalate_fraud_review",
            arguments={"customer_id": facts.customer_id, "payment_id": facts.payment_id},
            approval_required=True,
            policy_code="FIN-FRAUD-01",
            reason_code="FRAUD_INDICATOR_PRESENT",
        )
    if (
        facts.requested_action == "refund"
        and facts.payment_status == "settled"
        and facts.payment_age_days > 30
    ):
        return _no_tool("refuse", "FIN-REFUND-03", "REFUND_WINDOW_EXPIRED")
    if facts.requested_action == "refund" and facts.payment_status != "settled":
        return _no_tool("no_action", "FIN-REFUND-05", "PAYMENT_NOT_SETTLED")
    if facts.requested_action == "refund" and facts.duplicate_evidence == "confirmed":
        assert facts.payment_id is not None
        approval_required = facts.amount_minor > 5000
        return ActionContract(
            decision="request_approval" if approval_required else "execute",
            tool="refund_payment",
            arguments={
                "payment_id": facts.payment_id,
                "amount_minor": facts.amount_minor,
                "currency": facts.currency,
            },
            approval_required=approval_required,
            policy_code="FIN-REFUND-02" if approval_required else "FIN-REFUND-01",
            reason_code=(
                "AMOUNT_EXCEEDS_AUTO_APPROVAL_LIMIT"
                if approval_required
                else "DUPLICATE_PAYMENT_CONFIRMED"
            ),
        )
    return _no_tool("no_action", "FIN-NOACT-01", "NO_REFUND_ACTION_REQUESTED")


def resolve_subscription(facts: SubscriptionFacts) -> ActionContract:
    if not facts.requester_authorized:
        return _no_tool("refuse", "SUB-AUTH-01", "REQUESTER_NOT_AUTHORIZED")
    if facts.requested_action != "none" and facts.subscription_id is None:
        return _no_tool(
            "ask_clarification",
            "SUB-CONFIRM-01",
            "CANCELLATION_CONFIRMATION_REQUIRED",
        )
    if facts.requested_action == "cancel":
        if not facts.cancellation_confirmed or not facts.action_authorized:
            return _no_tool(
                "ask_clarification",
                "SUB-CONFIRM-01",
                "CANCELLATION_CONFIRMATION_REQUIRED",
            )
        assert facts.subscription_id is not None
        approval_required = facts.contract_locked or facts.balance_minor > 10000
        return ActionContract(
            decision="request_approval" if approval_required else "execute",
            tool="cancel_subscription",
            arguments={
                "subscription_id": facts.subscription_id,
                "effective_mode": facts.effective_mode,
            },
            approval_required=approval_required,
            policy_code="SUB-CANCEL-02" if approval_required else "SUB-CANCEL-01",
            reason_code=(
                "CONTRACT_REVIEW_REQUIRED" if approval_required else "CANCELLATION_CONFIRMED"
            ),
        )
    if facts.requested_action == "pause":
        assert facts.subscription_id is not None
        if facts.pause_eligible and facts.action_authorized:
            return ActionContract(
                decision="execute",
                tool="pause_subscription",
                arguments={
                    "subscription_id": facts.subscription_id,
                    "pause_days": facts.pause_days,
                },
                approval_required=False,
                policy_code="SUB-PAUSE-01",
                reason_code="PAUSE_ELIGIBLE",
            )
        return _no_tool("refuse", "SUB-PAUSE-02", "PAUSE_INELIGIBLE")
    if facts.requested_action == "retention":
        assert facts.subscription_id is not None
        if facts.retention_eligible and facts.action_authorized:
            return ActionContract(
                decision="execute",
                tool="offer_retention",
                arguments={
                    "subscription_id": facts.subscription_id,
                    "offer_code": "SAVE10_3MO",
                },
                approval_required=False,
                policy_code="SUB-RETENTION-01",
                reason_code="RETENTION_OFFER_ELIGIBLE",
            )
        return _no_tool("refuse", "SUB-RETENTION-02", "RETENTION_OFFER_INELIGIBLE")
    return _no_tool("no_action", "SUB-NOACT-01", "NO_SUBSCRIPTION_ACTION_REQUESTED")


def _no_tool(decision: str, policy_code: str, reason_code: str) -> ActionContract:
    return ActionContract.model_validate(
        {
            "decision": decision,
            "tool": None,
            "arguments": {},
            "approval_required": False,
            "policy_code": policy_code,
            "reason_code": reason_code,
        },
        strict=True,
    )
