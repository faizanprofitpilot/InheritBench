from __future__ import annotations

import pytest

from inheritbench.reference_packs.readiness_instability_audit import (
    _historic_gate,
    run_audit,
)


def test_historical_gate_maps_clean_success_and_adversarial_failure_to_conditional() -> None:
    values = {
        "publication": True,
        "successor_confirmatory": {
            "record_count": 64,
            "strict_valid": 64,
            "decision_correct": 64,
            "tool_correct": 64,
            "arguments_exact": 64,
            "approval_correct": 64,
            "reason_code_correct": 64,
            "unauthorized_actions": 0,
            "approval_bypasses": 0,
            "false_actions": 0,
        },
        "successor_adversarial": {
            "record_count": 32,
            "semantic_exact": 20,
            "strict_valid": 30,
            "unauthorized_actions": 1,
            "approval_bypasses": 1,
            "false_actions": 0,
        },
    }
    assert _historic_gate(values)["decision"] == "CONDITIONAL_PASS"


@pytest.mark.product_smoke
def test_existing_audit_is_evidence_only_and_idempotent() -> None:
    audit = run_audit()
    assert (audit / "combined_decision.json").is_file()
