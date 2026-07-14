import json

from inheritbench.evaluation.contracts import ActionContract
from inheritbench.evaluation.parser import parse_action_contract


def _valid_payload() -> dict[str, object]:
    return {
        "decision": "no_action",
        "tool": None,
        "arguments": {},
        "approval_required": False,
        "policy_code": "FIN-NOACT-01",
        "reason_code": "NO_REFUND_ACTION_REQUESTED",
    }


def test_strict_and_whole_fence_classifications() -> None:
    serialized = json.dumps(_valid_payload())
    assert parse_action_contract(serialized).classification == "STRICT_VALID"
    fenced = parse_action_contract(f"```json\n{serialized}\n```")
    assert fenced.classification == "NORMALIZED_VALID"
    assert isinstance(fenced.validated_contract, ActionContract)


def test_surrounding_prose_is_never_repaired() -> None:
    result = parse_action_contract(f"Here you go: {json.dumps(_valid_payload())}")
    assert result.classification == "UNPARSEABLE"
    assert result.errors[0].code == "PROSE_OR_MULTIPLE_OBJECTS"


def test_trailing_comma_casing_alias_and_missing_field_are_invalid() -> None:
    serialized = json.dumps(_valid_payload())
    assert parse_action_contract(serialized[:-1] + ",}").classification == "UNPARSEABLE"
    casing = _valid_payload() | {"decision": "NO_ACTION"}
    assert parse_action_contract(json.dumps(casing)).classification == "UNPARSEABLE"
    alias = _valid_payload() | {"decision": "abstain"}
    assert parse_action_contract(json.dumps(alias)).classification == "UNPARSEABLE"
    missing = _valid_payload()
    del missing["reason_code"]
    assert parse_action_contract(json.dumps(missing)).errors[0].code == "MISSING_REQUIRED_KEY"


def test_extra_field_and_multiple_objects_are_invalid() -> None:
    extra = _valid_payload() | {"explanation": "safe"}
    assert parse_action_contract(json.dumps(extra)).errors[0].code == "EXTRA_FIELD"
    multiple = json.dumps(_valid_payload()) + json.dumps(_valid_payload())
    assert parse_action_contract(multiple).errors[0].code == "PROSE_OR_MULTIPLE_OBJECTS"
