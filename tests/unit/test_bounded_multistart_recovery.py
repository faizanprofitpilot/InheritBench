from __future__ import annotations

import json
from pathlib import Path

import pytest

from inheritbench.orchestration.schemas import EvaluationRecord
from inheritbench.reference_packs.multistart_execution import (
    _atomic_summary,
    _candidate_rank,
    _failed_candidate_progress,
    freeze_multistart_plan,
    verify_multistart_plan,
)
from inheritbench.reference_packs.multistart_protocol import (
    CANONICAL_ANCHORED_PLAN_SHA256,
    DEFAULT_AMENDMENT_PATH,
    DEFAULT_SEED_PATH,
    derive_candidate_seed,
    verify_bounded_multistart_amendment,
    verify_bounded_multistart_seeds,
)
from inheritbench.reference_packs.multistart_surfaces import (
    DEFAULT_OUTPUT,
    verify_final_surfaces,
)

ROOT = Path(__file__).resolve().parents[2]
ANCHORED_RUN = ROOT / (
    "runs/reference/succession-opsroute-anchored-behavioral-transfer-v0.1-00-ee7a07404b124c1b"
)


@pytest.mark.product_smoke
def test_bounded_multistart_amendment_and_seeds_replay() -> None:
    amendment = verify_bounded_multistart_amendment(DEFAULT_AMENDMENT_PATH)
    seeds = verify_bounded_multistart_seeds(DEFAULT_SEED_PATH)

    assert amendment["status"] == "PROSPECTIVE_CONTENT_FROZEN"
    assert amendment["candidate_count"] == 4
    assert amendment["only_varied_dimension"] == "lora_initialization_seed"
    assert [item["candidate_index"] for item in seeds["candidates"]] == [0, 1, 2, 3]
    assert len({item["initialization_seed"] for item in seeds["candidates"]}) == 4
    assert [
        derive_candidate_seed(amendment["content_sha256"], CANONICAL_ANCHORED_PLAN_SHA256, index)
        for index in range(4)
    ] == [item["initialization_seed"] for item in seeds["candidates"]]


def test_fresh_final_surfaces_are_balanced_and_sealed() -> None:
    manifest = verify_final_surfaces(DEFAULT_OUTPUT)

    assert manifest["decision"] == "FRESH_FINAL_SURFACES_FROZEN"
    assert manifest["confirmatory"]["records"] == 64
    assert manifest["adversarial"]["records"] == 32
    assert set(manifest["confirmatory"]["group_counts"].values()) == {4}
    assert set(manifest["adversarial"]["group_counts"].values()) == {2}
    assert manifest["candidate_ranking_access_to_final_inputs"] is False
    assert manifest["candidate_ranking_access_to_final_oracles"] is False


@pytest.mark.product_smoke
def test_canonical_multistart_plan_is_content_addressed() -> None:
    run_directory = freeze_multistart_plan()
    plan = verify_multistart_plan(run_directory)

    assert plan["candidate_count"] == 4
    assert plan["schedule"]["processed_tokens"] == 272568
    assert plan["schedule"]["optimizer_steps"] == 168
    assert plan["schedule"]["checkpoint_steps"] == [56, 112, 168]
    assert plan["final_surfaces"]["candidate_access"] == (
        "PROHIBITED_UNTIL_SELECTED_CANDIDATE_FROZEN"
    )


@pytest.mark.product_smoke
def test_operational_semantic_does_not_conflate_policy_code() -> None:
    stage = json.loads(
        (ANCHORED_RUN / "stages/13-confirmatory_completed/stage.json").read_text(encoding="utf-8")
    )
    records = [
        EvaluationRecord.model_validate(item, strict=True) for item in stage["payload"]["records"]
    ]

    summary = _atomic_summary("old_confirmatory", records)

    assert summary["operational_semantic_correct"] == 64
    assert summary["exact_full_contract"] == 53
    assert summary["policy_code_correct"] == 53
    assert summary["historical_strict_valid"] == 64


def test_candidate_ranking_prioritizes_safety_then_operational_score() -> None:
    base = {
        "validation_minimum_group_operational_semantic_rate": 0.5,
        "validation_historical_strict_valid": 32,
        "validation_mean_declared_field_correctness": 0.95,
        "validation_loss": 0.02,
        "selected_optimizer_step": 168,
    }
    unsafe = {
        **base,
        "candidate_index": 0,
        "safety_eligible": False,
        "validation_operational_semantic_correct": 32,
    }
    safe = {
        **base,
        "candidate_index": 1,
        "safety_eligible": True,
        "validation_operational_semantic_correct": 30,
    }
    stronger_safe = {
        **safe,
        "candidate_index": 2,
        "validation_operational_semantic_correct": 31,
    }

    assert _candidate_rank(safe) > _candidate_rank(unsafe)
    assert _candidate_rank(stronger_safe) > _candidate_rank(safe)


def test_failed_candidate_progress_uses_partial_checkpoint_lower_bound() -> None:
    progress = _failed_candidate_progress(
        {
            "checkpoints": [
                {"optimizer_step": 56, "processed_tokens": 90856},
                {"optimizer_step": 112, "processed_tokens": 181712},
            ]
        }
    )

    assert progress == {
        "optimizer_steps": 112,
        "processed_tokens": 181712,
        "checkpoint_count": 2,
    }


@pytest.mark.product_smoke
def test_guard_repair_preserves_frozen_protocol_dimensions() -> None:
    repair = json.loads(
        (
            ROOT / "artifacts/protocol-amendments/bounded-multistart-guard-repair-v0.1.json"
        ).read_text()
    )
    assert repair["classification"] == "IMPLEMENTATION_DEFECT_REPAIR"
    for field in (
        "scientific_protocol_changed",
        "candidate_seeds_changed",
        "supervision_changed",
        "schedule_changed",
        "optimizer_changed",
        "learning_rate_changed",
        "training_budget_changed",
        "ranking_policy_changed",
        "readiness_contract_changed",
        "final_surfaces_changed",
    ):
        assert repair[field] is False
