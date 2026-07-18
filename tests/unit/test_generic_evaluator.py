from __future__ import annotations

import json
from pathlib import Path

from inheritbench.capability.evaluator import evaluate_output
from inheritbench.capability.loader import load_capability_pack

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_exact_semantic_and_safety_evaluation() -> None:
    pack = load_capability_pack(
        REPOSITORY_ROOT / "examples/capability-packs/purchase-approval",
        allow_fixture=True,
    )
    record = pack.inputs["confirmatory"][4]
    oracle = pack.oracle_map("confirmatory")[record.record_id]
    result = evaluate_output(
        record=record,
        oracle=oracle,
        raw_output=record.payload["trained_output_json"]
        if "trained_output_json" in record.payload
        else json.dumps(record.payload["trained_output"], separators=(",", ":")),
        config=pack.evaluator,
        output_schema=pack.output_schema,
        cross_field_schema=pack.cross_field_schema,
        vocabularies=pack.vocabularies,
        safety_rules=pack.safety_rules,
    )
    assert result.parser_classification == "STRICT_VALID"
    assert result.semantic_match is True
    assert result.structural_exact is True
    assert result.safety_findings == []


def test_fenced_output_is_normalized_but_not_strict() -> None:
    pack = load_capability_pack(REPOSITORY_ROOT / "capabilities/opsroute/v0.2.0")
    record = pack.inputs["source_gate"][0]
    oracle = pack.oracle_map("source_gate")[record.record_id]

    raw = f"```json\n{json.dumps(oracle.expected, separators=(',', ':'))}\n```"
    result = evaluate_output(
        record=record,
        oracle=oracle,
        raw_output=raw,
        config=pack.evaluator,
        output_schema=pack.output_schema,
        cross_field_schema=pack.cross_field_schema,
        vocabularies=pack.vocabularies,
        safety_rules=pack.safety_rules,
    )
    assert result.parser_classification == "NORMALIZED_VALID"
    assert result.strict_valid is False
    assert result.semantic_match is True


def test_strict_json_accepts_noncanonical_key_order() -> None:
    pack = load_capability_pack(
        REPOSITORY_ROOT / "examples/capability-packs/purchase-approval",
        allow_fixture=True,
    )
    record = pack.inputs["confirmatory"][0]
    oracle = pack.oracle_map("confirmatory")[record.record_id]
    reordered = dict(reversed(list(oracle.expected.items())))
    result = evaluate_output(
        record=record,
        oracle=oracle,
        raw_output=json.dumps(reordered, separators=(",", ":")),
        config=pack.evaluator,
        output_schema=pack.output_schema,
        cross_field_schema=pack.cross_field_schema,
        vocabularies=pack.vocabularies,
        safety_rules=pack.safety_rules,
    )
    assert result.parser_classification == "STRICT_VALID"
    assert result.semantic_match is True


def test_safety_rule_can_compare_against_oracle_pointer() -> None:
    pack = load_capability_pack(REPOSITORY_ROOT / "capabilities/opsroute/v0.2.0")
    record = pack.inputs["confirmatory"][0]
    oracle = pack.oracle_map("confirmatory")[record.record_id]
    unsafe = dict(oracle.expected)
    unsafe["decision"] = "execute"
    unsafe["tool"] = "refund_payment"
    result = evaluate_output(
        record=record,
        oracle=oracle,
        raw_output=json.dumps(unsafe, separators=(",", ":")),
        config=pack.evaluator,
        output_schema=pack.output_schema,
        cross_field_schema=pack.cross_field_schema,
        vocabularies=pack.vocabularies,
        safety_rules=pack.safety_rules,
    )
    assert any(finding.code == "UNAUTHORIZED_ACTION" for finding in result.safety_findings)
