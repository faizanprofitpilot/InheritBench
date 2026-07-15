from __future__ import annotations

import pytest

from inheritbench.phase5.projection import (
    derive_evaluation_surface,
    projection_files,
    verify_web_projection,
)


def test_projection_is_deterministic_and_current_cases_are_surface_resolved() -> None:
    first = projection_files()
    second = projection_files()
    assert first == second
    manifest = verify_web_projection()
    assert manifest.historical_artifacts_modified is False
    case_bytes = first["case-details.json"]
    assert case_bytes.count(b'"status":"SELECTED"') == 6
    assert case_bytes.count(b'"status":"NO_ELIGIBLE_CASE"') == 2
    assert case_bytes.count(b'"evaluation_surface":"adversarial"') == 6


@pytest.mark.parametrize(
    ("parent_schema", "split", "expected"),
    [
        ("phase4-analysis-v0.1", "adversarial", "adversarial"),
        ("phase3b-comparison-v0.1", "confirmatory_test", "confirmatory"),
        ("phase3b-comparison-v0.1", "exploratory_legacy_test", "exploratory"),
    ],
)
def test_surface_is_derived_from_frozen_parent_runs(
    parent_schema: str, split: str, expected: str
) -> None:
    selection = {"cases": [{"status": "SELECTED"}]}
    parent = {"schema_version": parent_schema}
    assert derive_evaluation_surface(selection, parent, [split]) == expected


def test_surface_mismatch_fails_closed() -> None:
    selection = {"cases": [{"status": "SELECTED", "evaluation_surface": "confirmatory"}]}
    with pytest.raises(ValueError, match="disagrees"):
        derive_evaluation_surface(
            selection,
            {"schema_version": "phase4-analysis-v0.1"},
            ["adversarial"],
        )


def test_unknown_or_mixed_surface_fails_closed() -> None:
    with pytest.raises(ValueError, match="cannot derive"):
        derive_evaluation_surface(
            {"cases": [{"status": "SELECTED"}]},
            {"schema_version": "phase4-analysis-v0.1"},
            ["adversarial", "confirmatory_test"],
        )


def test_projection_does_not_claim_ten_labels_total() -> None:
    payload = b"".join(projection_files().values()).lower()
    assert b"ten labels total" not in payload
