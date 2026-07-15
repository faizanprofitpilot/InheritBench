from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from inheritbench.artifacts.hashing import canonical_json, content_sha256
from inheritbench.artifacts.schemas import GenerationConfig
from inheritbench.config import load_model_config
from inheritbench.data.opsroute.schemas import OpsRouteExample
from inheritbench.evaluation.metrics import score_prediction
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.phase4 import protocol
from inheritbench.phase4.analysis import _recommend, classify_failure
from inheritbench.phase4.config import load_experiment_config
from inheritbench.phase4.memo import _comparison_supported
from inheritbench.phase4.schemas import (
    EvidenceReferenceV0_1,
    MemoClaimV0_1,
    Phase4ExperimentConfigV0_1,
    Phase4LineageV0_1,
    Phase4PredictionRecordV0_1,
    Phase4ProtocolV0_1,
    SystemEvidenceRowV0_1,
    TargetSystemId,
)

EXPERIMENT = Path("configs/experiments/phase4.yaml")
ZERO_HASH = "0" * 64


def test_phase4_configs_are_strict_and_frozen() -> None:
    config = load_experiment_config(EXPERIMENT)
    assert config.artifact_root == "artifacts/phase4"
    assert config.repeated_seeds is False
    assert [item.system_id for item in config.systems] == [
        "source_base_supporting",
        "source_adapted_full",
        "target_untouched",
        "target_full_retrain",
        "target_limited_retrain_10pct",
        "target_hybrid_anchored_distillation_10",
    ]

    raw = yaml.safe_load(EXPERIMENT.read_text(encoding="utf-8"))
    raw["unexpected"] = True
    with pytest.raises(ValidationError):
        Phase4ExperimentConfigV0_1.model_validate(raw, strict=True)


def test_phase4_protocol_freeze_validates_real_historical_bytes() -> None:
    output, value = protocol.find_protocol(EXPERIMENT)

    assert output.is_file()
    assert Phase4ProtocolV0_1.model_validate_json(output.read_bytes(), strict=True) == value
    assert value.status == "FROZEN"
    assert len(value.systems) == 6
    assert value.adversarial_split_sha256 == (
        "38bf3f5c91dbae04cdd6a83de73cfe336f7cc6a9eb31fcf85559037c2ac7f85a"
    )
    assert value.memo_model == "gpt-5.6-sol"


def test_failure_precedence_keeps_specific_safety_failure_first() -> None:
    record = next(
        item for item in _adversarial_records() if item.expected.decision == "request_approval"
    )
    predicted = record.expected.model_copy(
        update={"decision": "execute", "approval_required": False}
    )
    prediction = _prediction(record, canonical_json(predicted))

    tags = classify_failure(prediction)

    assert tags[:2] == ["APPROVAL_BYPASS", "UNAUTHORIZED_ACTION"]
    assert tags.index("UNAUTHORIZED_ACTION") < tags.index("WRONG_DECISION")
    assert "STRICT_CONTRACT_INVALID" not in tags


def test_invalid_json_remains_multilabel_but_primary_specific() -> None:
    prediction = _prediction(_adversarial_records()[0], "not json")

    tags = classify_failure(prediction)

    assert tags == ["INVALID_JSON", "STRICT_CONTRACT_INVALID"]


def test_profile_filters_teacher_dependency_and_uses_frozen_tiebreakers() -> None:
    rows = {
        system: _system_row(system, direct, teacher, semantic)
        for system, direct, teacher, semantic in [
            ("target_untouched", 0, False, 0.4),
            ("target_full_retrain", 224, False, 0.8),
            ("target_limited_retrain_10pct", 24, False, 0.7),
            ("target_hybrid_anchored_distillation_10", 10, True, 0.9),
        ]
    }
    complexity = {
        "NO_TARGET_TRAINING": 0,
        "DIRECT_TARGET_LORA": 1,
        "TEACHER_HYBRID_LORA": 2,
    }

    no_teacher = _recommend("no_source_teacher", list(rows), rows, complexity)
    maximum = _recommend("maximum_confirmed_capability", list(rows), rows, complexity)

    assert no_teacher.recommendation == "target_full_retrain"
    assert "target_hybrid_anchored_distillation_10" not in no_teacher.eligible_systems
    assert maximum.recommendation == "target_hybrid_anchored_distillation_10"


def test_grouped_comparison_supports_targets_against_one_reference() -> None:
    systems = [
        "target_full_retrain",
        "target_hybrid_anchored_distillation_10",
        "target_limited_retrain_10pct",
        "source_adapted_full",
    ]
    references = {
        f"safety:{system}": EvidenceReferenceV0_1(
            evidence_id=f"safety:{system}",
            artifact_path="fixture.json",
            artifact_byte_sha256=ZERO_HASH,
            artifact_content_sha256=ZERO_HASH,
            json_path=f"$.{system}",
            value=value,
            numerator=value,
            denominator=32,
            evaluation_surface="adversarial",
            system_id=system,
        )
        for system, value in zip(systems, [1, 1, 1, 4], strict=True)
    }
    claim = MemoClaimV0_1(
        claim_id="grouped-safety",
        statement="The three targets are lower than the adapted source.",
        evidence_ids=list(references),
        comparison="LOWER",
        compared_systems=systems,
    )

    assert _comparison_supported(claim, references)


def _adversarial_records() -> list[OpsRouteExample]:
    with Path("data/opsroute/v0.1.0/adversarial.jsonl").open(encoding="utf-8") as handle:
        return [OpsRouteExample.model_validate_json(line, strict=True) for line in handle]


def _prediction(record: OpsRouteExample, raw_output: str) -> Phase4PredictionRecordV0_1:
    parsed = parse_action_contract(raw_output)
    metrics = score_prediction(parsed, record.expected, record.evaluation)
    model = load_model_config(Path("configs/models/target.yaml"))
    now = datetime.now(UTC)
    payload = {
        "schema_version": "phase4-prediction-v0.1",
        "prediction_id": "fixture-prediction",
        "run_id": "fixture-run",
        "status": "COMPLETED",
        "error_type": None,
        "system_id": "target_untouched",
        "split": "adversarial",
        "adapter_id": None,
        "example_id": record.example_id,
        "scenario_family": record.scenario_family,
        "archetype": record.archetype,
        "adversarial_profiles": record.evaluation.tags,
        "model_id": model.model_id,
        "model_revision": model.revision,
        "resolved_device": "mps",
        "resolved_dtype": "float16",
        "prompt_sha256": ZERO_HASH,
        "input_ids_sha256": ZERO_HASH,
        "prompt_token_count": 1,
        "generated_token_count": 1,
        "generation": GenerationConfig(
            do_sample=False, num_beams=1, max_new_tokens=256, seed=20260714
        ),
        "raw_output": raw_output,
        "parser_result": parsed,
        "expected_contract": record.expected,
        "evaluation_metadata": record.evaluation,
        "metrics": metrics,
        "started_at": now,
        "finished_at": now,
        "latency_ms": 0,
        "errors": [],
        "lineage": _lineage(),
    }
    return Phase4PredictionRecordV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _lineage() -> Phase4LineageV0_1:
    return Phase4LineageV0_1(
        historical_reference_commit="1" * 40,
        phase4_protocol_commit="2" * 40,
        protocol_attestation_sha256=ZERO_HASH,
        protocol_sha256=ZERO_HASH,
        adversarial_split_sha256=ZERO_HASH,
        adversarial_oracle_sha256=ZERO_HASH,
        phase3b_confirmatory_comparison_sha256=ZERO_HASH,
        phase3b_science_sha256=ZERO_HASH,
        phase3b_publication_verification_sha256=ZERO_HASH,
        prompt_version="0.1.0",
        parser_version="0.1.0",
        evaluator_version="v0",
    )


def _system_row(
    system: TargetSystemId,
    direct_labels: int,
    teacher_required: bool,
    semantic: float,
) -> SystemEvidenceRowV0_1:
    complexity = (
        "NO_TARGET_TRAINING"
        if system == "target_untouched"
        else "TEACHER_HYBRID_LORA"
        if teacher_required
        else "DIRECT_TARGET_LORA"
    )
    return SystemEvidenceRowV0_1(
        system_id=system,
        comparison_role="TARGET_MIGRATION_CANDIDATE",
        viable=True,
        viability_reasons=[],
        confirmatory_semantic=semantic,
        confirmatory_strict=1.0,
        confirmatory_unauthorized_actions=0,
        confirmatory_approval_bypasses=0,
        adversarial_semantic=semantic,
        adversarial_strict=1.0,
        adversarial_argument_f1=semantic,
        adversarial_safety_failures=0,
        direct_original_labels=direct_labels,
        upstream_original_labels=224 if teacher_required else 0,
        complexity=complexity,
        source_teacher_required=teacher_required,
        pareto_dominated=False,
        dominated_by=[],
    )
