from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from inheritbench.artifacts.hashing import canonical_json, content_sha256, sha256_bytes
from inheritbench.artifacts.schemas import GenerationConfig
from inheritbench.day3.filtering import _filter_one, _read_jsonl
from inheritbench.day3.lifecycle import _write_scientific_decision
from inheritbench.day3.pool import load_candidates, load_oracles
from inheritbench.day3.publication import _deterministic_zip
from inheritbench.day3.schemas import (
    Day3DistributionDecisionV0_1,
    Day3ScientificDecisionV0_1,
    TeacherPredictionV0_1,
)
from inheritbench.day3.teacher import _validated_archive_files
from inheritbench.evaluation.parser import parse_action_contract


def _candidate_oracle():
    pool = next(Path("artifacts/day3/pools").glob("day3-pool-initial-*"))
    return load_candidates(pool)[0], load_oracles(pool)[0]


def _prediction(raw_output: str) -> TeacherPredictionV0_1:
    candidate, _ = _candidate_oracle()
    parser = parse_action_contract(raw_output)
    now = datetime.now(UTC)
    payload = {
        "schema_version": "teacher-prediction-v0.1",
        "prediction_id": "teacher-prediction-test",
        "run_id": "teacher-run-test",
        "status": "COMPLETED",
        "error_type": None,
        "candidate_id": candidate.candidate_id,
        "candidate_record_sha256": candidate.record_sha256,
        "pool_content_sha256": "a" * 64,
        "teacher_verification_sha256": "b" * 64,
        "model_id": "Qwen/Qwen2.5-0.5B-Instruct",
        "model_revision": "7ae557604adf67be50417f59c2c2f167def9a775",
        "adapter_id": "source_adapted_full-8242bcea6f327545",
        "resolved_device": "mps",
        "resolved_dtype": "float16",
        "prompt_sha256": "c" * 64,
        "input_ids_sha256": "d" * 64,
        "generation": GenerationConfig(
            do_sample=False, num_beams=1, max_new_tokens=256, seed=20260714
        ).model_dump(mode="json"),
        "prompt_token_count": 100,
        "generated_token_count": 20,
        "finish_condition": "EOS",
        "raw_output": raw_output,
        "parser_result": parser.model_dump(mode="json"),
        "started_at": now,
        "finished_at": now,
        "latency_ms": 1,
        "errors": [],
    }
    return TeacherPredictionV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def test_filter_preserves_exact_strict_teacher_label(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate, oracle = _candidate_oracle()
    label = canonical_json(oracle.expected_contract)
    monkeypatch.setattr("inheritbench.day3.filtering.training_sequence_length", lambda *_: 200)
    result = _filter_one(candidate, oracle, _prediction(f"  {label}\n"), object())
    assert result.accepted is True
    assert result.teacher_label == label


def test_filter_rejects_fenced_output(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate, oracle = _candidate_oracle()
    label = canonical_json(oracle.expected_contract)
    monkeypatch.setattr("inheritbench.day3.filtering.training_sequence_length", lambda *_: 200)
    result = _filter_one(candidate, oracle, _prediction(f"```json\n{label}\n```"), object())
    assert result.accepted is False
    assert result.primary_rejection_reason == "NORMALIZED_NOT_STRICT"


def test_teacher_prediction_jsonl_round_trips_strict_datetimes(tmp_path: Path) -> None:
    prediction = _prediction("not-json")
    path = tmp_path / "predictions.jsonl"
    path.write_text(canonical_json(prediction) + "\n", encoding="utf-8")

    assert _read_jsonl(path, TeacherPredictionV0_1) == [prediction]


def test_teacher_zip_rejects_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../adapter_config.json", b"{}")
    with pytest.raises(ValueError, match=r"unexpected files|unsafe"):
        _validated_archive_files(archive, {"adapter_config.json": sha256_bytes(b"{}")})


def test_day3_adapter_zip_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "adapter_config.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "adapter_model.safetensors").write_bytes(b"weights")
    first = _deterministic_zip(tmp_path)
    (tmp_path / "adapter_config.json").touch()
    assert first == _deterministic_zip(tmp_path)


def test_publication_blocked_does_not_block_day4() -> None:
    now = datetime.now(UTC)
    science = Day3ScientificDecisionV0_1(
        schema_version="day3-scientific-decision-v0.1",
        decision_id="science-test",
        scientific_status="SCIENTIFICALLY_COMPLETED",
        day4_gate="DAY4_UNBLOCKED",
        reason_code="ALL_SCIENTIFIC_GATES_PASSED",
        training_run_id="training",
        checkpoint_decision_id="checkpoint",
        test_run_id="test",
        replay_id="replay",
        failure_analysis_id="analysis",
        comparison_id="comparison",
        evidence_sha256s=["a" * 64],
        created_at=now,
        content_sha256="b" * 64,
    )
    distribution = Day3DistributionDecisionV0_1(
        schema_version="day3-distribution-decision-v0.1",
        decision_id="distribution-test",
        publication_status="PUBLICATION_BLOCKED",
        scientific_decision_sha256=science.content_sha256,
        publication_sha256="c" * 64,
        day4_gate=science.day4_gate,
        created_at=now,
        content_sha256="d" * 64,
    )
    assert distribution.publication_status == "PUBLICATION_BLOCKED"
    assert distribution.day4_gate == "DAY4_UNBLOCKED"


def test_insufficient_synthetic_data_blocks_day4(tmp_path: Path) -> None:
    path = _write_scientific_decision(
        tmp_path,
        scientific_status="SCIENTIFICALLY_FAILED",
        day4_gate="DAY4_BLOCKED",
        reason_code="INSUFFICIENT_ACCEPTED_SYNTHETIC_EXAMPLES",
        evidence_sha256s=["a" * 64],
    )
    decision = Day3ScientificDecisionV0_1.model_validate_json(
        (path / "decision.json").read_bytes(), strict=True
    )

    assert decision.scientific_status == "SCIENTIFICALLY_FAILED"
    assert decision.day4_gate == "DAY4_BLOCKED"
