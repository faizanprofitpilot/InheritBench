from inheritbench.blockers.diagnosis import classify_failure
from inheritbench.evaluation.parser import parse_action_contract


def test_diagnosis_distinguishes_schema_and_malformed_failures() -> None:
    wrong_schema = '{"decision":"cancel","tool":"cancel_subscription"}'
    parsed = parse_action_contract(wrong_schema)
    categories, value, repetition = classify_failure(wrong_schema, parsed.status, parsed.errors)
    assert value is not None
    assert "VALID_JSON_WRONG_SCHEMA" in categories
    assert "MISSING_REQUIRED_FIELDS" in categories
    assert "WRONG_ENUM_OR_TOOL" in categories
    assert repetition is False

    malformed = '{"decision":"execute"'
    parsed = parse_action_contract(malformed)
    categories, value, repetition = classify_failure(malformed, parsed.status, parsed.errors)
    assert value is None
    assert categories == ["MALFORMED_JSON"]
    assert repetition is False


def test_diagnosis_detects_key_repetition() -> None:
    raw = '{"a":1,"a":2,"a":3}'
    parsed = parse_action_contract(raw)
    categories, _, repetition = classify_failure(raw, parsed.status, parsed.errors)
    assert repetition is True
    assert "REPETITION_OR_DEGENERATION" in categories
