from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from inheritbench.day3_matched import teacher
from inheritbench.day3_matched.filtering import _validate_training_path
from inheritbench.day3_matched.publication import _deterministic_zip
from inheritbench.day3_matched.schemas import (
    Day3RecoveryDecisionV0_1,
    MatchedDistributionDecisionV0_1,
)


def _recovery(status: str, gate: str) -> Day3RecoveryDecisionV0_1:
    return Day3RecoveryDecisionV0_1.model_validate(
        {
            "schema_version": "day3-recovery-decision-v0.1",
            "decision_id": "matched-recovery-test",
            "recovery_status": status,
            "day4_gate": gate,
            "reason_code": "TEST",
            "dataset_id": "dataset",
            "training_run_id": None,
            "checkpoint_decision_id": None,
            "test_run_id": None,
            "attempt_comparison_id": "attempt-comparison",
            "method_comparison_id": None,
            "evidence_sha256s": ["a" * 64],
            "further_day3_attempts_allowed": False,
            "automatic_day4_started": False,
            "created_at": datetime.now(UTC),
            "content_sha256": "b" * 64,
        },
        strict=True,
    )


def test_terminal_negative_unblocks_day4_with_negative_result() -> None:
    decision = _recovery(
        "RECOVERY_TERMINAL_NEGATIVE",
        "DAY4_UNBLOCKED_WITH_NEGATIVE_DISTILLATION_RESULT",
    )
    assert decision.further_day3_attempts_allowed is False
    assert decision.automatic_day4_started is False


def test_scientific_completion_unblocks_day4() -> None:
    decision = _recovery("RECOVERY_SCIENTIFICALLY_COMPLETED", "DAY4_UNBLOCKED")
    assert decision.day4_gate == "DAY4_UNBLOCKED"


def test_recovery_status_rejects_inconsistent_day4_gate() -> None:
    with pytest.raises(ValidationError, match="recovery status and Day 4 gate disagree"):
        _recovery("RECOVERY_BLOCKED", "DAY4_UNBLOCKED")


def test_publication_status_cannot_change_recovery_gate() -> None:
    recovery = _recovery("RECOVERY_SCIENTIFICALLY_COMPLETED", "DAY4_UNBLOCKED")
    distribution = MatchedDistributionDecisionV0_1(
        schema_version="day3-matched-distribution-decision-v0.1",
        decision_id="matched-distribution-test",
        publication_status="PUBLICATION_BLOCKED",
        recovery_decision_sha256=recovery.content_sha256,
        publication_sha256="c" * 64,
        day4_gate=recovery.day4_gate,
        created_at=datetime.now(UTC),
        content_sha256="d" * 64,
    )
    assert distribution.publication_status == "PUBLICATION_BLOCKED"
    assert distribution.day4_gate == "DAY4_UNBLOCKED"


def test_matched_adapter_archive_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "adapter_config.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "adapter_model.safetensors").write_bytes(b"weights")
    first = _deterministic_zip(tmp_path)
    (tmp_path / "adapter_config.json").touch()
    assert first == _deterministic_zip(tmp_path)


def test_teacher_runtime_has_no_oracle_loader_dependency() -> None:
    source = inspect.getsource(teacher)
    assert "load_oracles" not in source
    assert "oracle.jsonl" not in source


@pytest.mark.parametrize(
    "path",
    [
        Path("data/opsroute/v0.1.0"),
        Path("artifacts/day3/pools"),
        Path("artifacts/day3-matched/pools"),
    ],
)
def test_target_training_rejects_non_synthetic_paths(path: Path) -> None:
    with pytest.raises(ValueError, match="only matched synthetic-data"):
        _validate_training_path(path)
