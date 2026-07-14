import json
from pathlib import Path

from inheritbench.artifacts.hashing import sha256_file
from inheritbench.blockers.decision import BlockerResolutionDecision
from inheritbench.blockers.runtime import DiagnosticManifest
from inheritbench.blockers.trainability import TrainabilityManifest

ROOT = Path("artifacts/blocker-resolution")
SUBSETS = ROOT / "subsets/subsets-c0e0abb99d3f9e7d"
TARGET_RUN = ROOT / "trainability/micro-lora-target_micro_lora-20260714T195848-79e58f44"


def test_training_provenance_contains_only_train_records() -> None:
    training = json.loads((SUBSETS / "micro-lora-train.json").read_text(encoding="utf-8"))
    validation = json.loads((SUBSETS / "validation-diagnostic.json").read_text(encoding="utf-8"))

    assert training["source_split"] == "train"
    assert validation["source_split"] == "validation"
    assert not set(training["example_ids"]) & set(validation["example_ids"])
    assert all("_16_" not in item and "_17_" not in item for item in training["example_ids"])
    assert all("_18_" not in item and "_19_" not in item for item in training["example_ids"])


def test_completed_target_artifact_hashes_and_gate_result() -> None:
    manifest = TrainabilityManifest.model_validate_json(
        (TARGET_RUN / "manifest.json").read_bytes(), strict=True
    )

    assert manifest.status == "COMPLETED"
    assert manifest.schema_valid_predictions == 7
    assert manifest.semantic_exact_predictions == 2
    assert sha256_file(TARGET_RUN / "predictions.jsonl") == manifest.predictions_byte_sha256
    assert sha256_file(TARGET_RUN / "summary.json") == manifest.summary_byte_sha256


def test_diagnostic_artifact_references_exact_bytes() -> None:
    run = ROOT / "diagnostics/diagnostic-20260714T194526-544a6811"
    manifest = DiagnosticManifest.model_validate_json(
        (run / "manifest.json").read_bytes(), strict=True
    )

    assert manifest.status == "COMPLETED"
    assert sha256_file(run / "predictions.jsonl") == manifest.prediction_artifact.byte_sha256
    assert sha256_file(run / "summary.json") == manifest.summary_artifact.byte_sha256


def test_final_decision_is_backed_by_thresholds() -> None:
    decision_path = next((ROOT / "decision").glob("decision-*/decision.json"))
    decision = BlockerResolutionDecision.model_validate_json(
        decision_path.read_bytes(), strict=True
    )

    assert decision.trainability_decision == "OLMO_TRAINABILITY_CONFIRMED"
    assert decision.observed_schema_valid >= decision.schema_valid_threshold
    assert decision.observed_semantic_exact >= decision.semantic_exact_threshold
    assert decision.modal_remote_attempts == 0
