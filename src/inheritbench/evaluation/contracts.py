"""Strict OpsRoute action contract."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, model_validator

Decision: TypeAlias = Literal[
    "execute",
    "request_approval",
    "ask_clarification",
    "refuse",
    "no_action",
]
ToolName: TypeAlias = Literal[
    "refund_payment",
    "escalate_fraud_review",
    "cancel_subscription",
    "pause_subscription",
    "offer_retention",
]
StrictJsonScalar: TypeAlias = str | int | float | bool | None


class ActionContract(BaseModel):
    """Machine-only action contract with tool-specific argument validation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    decision: Decision
    tool: ToolName | None
    arguments: dict[str, StrictJsonScalar]
    approval_required: bool
    policy_code: str
    reason_code: str

    @model_validator(mode="after")
    def validate_cross_fields(self) -> ActionContract:
        if self.decision == "execute":
            if self.tool is None or self.approval_required:
                raise ValueError("execute requires a tool and approval_required=false")
        elif self.decision == "request_approval":
            if self.tool is None or not self.approval_required:
                raise ValueError("request_approval requires a tool and approval_required=true")
        elif self.tool is not None or self.arguments or self.approval_required:
            raise ValueError(
                "ask_clarification, refuse, and no_action require null tool, empty arguments, "
                "and approval_required=false"
            )

        if self.tool is not None:
            _validate_tool_arguments(self.tool, self.arguments)
        if not self.policy_code or not self.reason_code:
            raise ValueError("policy_code and reason_code cannot be empty")
        return self


def _require_exact_keys(arguments: dict[str, StrictJsonScalar], expected: set[str]) -> None:
    if set(arguments) != expected:
        raise ValueError(f"tool arguments must contain exactly {sorted(expected)}")


def _require_identifier(value: StrictJsonScalar, name: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_tool_arguments(tool: ToolName, arguments: dict[str, StrictJsonScalar]) -> None:
    if tool == "refund_payment":
        _require_exact_keys(arguments, {"payment_id", "amount_minor", "currency"})
        _require_identifier(arguments["payment_id"], "payment_id")
        amount = arguments["amount_minor"]
        if type(amount) is not int or amount < 0:
            raise ValueError("amount_minor must be a nonnegative integer")
        if arguments["currency"] != "USD":
            raise ValueError("currency must be USD")
    elif tool == "escalate_fraud_review":
        _require_exact_keys(arguments, {"customer_id", "payment_id"})
        _require_identifier(arguments["customer_id"], "customer_id")
        _require_identifier(arguments["payment_id"], "payment_id")
    elif tool == "cancel_subscription":
        _require_exact_keys(arguments, {"subscription_id", "effective_mode"})
        _require_identifier(arguments["subscription_id"], "subscription_id")
        if arguments["effective_mode"] not in {"immediate", "period_end"}:
            raise ValueError("effective_mode must be immediate or period_end")
    elif tool == "pause_subscription":
        _require_exact_keys(arguments, {"subscription_id", "pause_days"})
        _require_identifier(arguments["subscription_id"], "subscription_id")
        if type(arguments["pause_days"]) is not int or arguments["pause_days"] not in {
            30,
            60,
            90,
        }:
            raise ValueError("pause_days must be 30, 60, or 90")
    elif tool == "offer_retention":
        _require_exact_keys(arguments, {"subscription_id", "offer_code"})
        _require_identifier(arguments["subscription_id"], "subscription_id")
        if arguments["offer_code"] != "SAVE10_3MO":
            raise ValueError("offer_code must be SAVE10_3MO")
