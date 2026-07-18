from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import torch

from inheritbench.capability.evaluator import evaluate_output
from inheritbench.capability.loader import load_capability_pack
from inheritbench.capability.schemas import CapabilityLabeledRecord
from inheritbench.evaluation.parser import parse_action_contract
from inheritbench.model_adapters.huggingface import (
    capture_rng_state,
    restore_rng_state,
    seed_all,
)
from inheritbench.model_adapters.schemas import GenerationOutput
from inheritbench.orchestration.schedule import resolve_schedule
from inheritbench.strategies.anchored import prepare_anchored_supervision

ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = ROOT / "capabilities/opsroute/v0.2.0"


def _seed_sample(seed: int) -> tuple[float, float, list[float]]:
    seed_all(seed, "cpu")
    return random.random(), float(np.random.random()), torch.rand(4).tolist()


def test_generic_initialization_seed_is_repeatable_and_value_sensitive() -> None:
    first = _seed_sample(20260714)
    assert first == _seed_sample(20260714)
    assert first != _seed_sample(20260715)


def test_generic_resume_restores_python_numpy_and_torch_rng() -> None:
    seed_all(20260714, "cpu")
    state = capture_rng_state("cpu")
    expected = (random.random(), float(np.random.random()), torch.rand(4).tolist())
    _seed_sample(20260715)
    restore_rng_state(state, "cpu")
    actual = (random.random(), float(np.random.random()), torch.rand(4).tolist())
    assert actual == expected


def test_opsroute_generic_schedule_matches_historical_direct_schedule() -> None:
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    historical = json.loads(
        (ROOT / "artifacts/day2/data/day2-data-01c2e470b9ccf379/target_primary.json").read_text(
            encoding="utf-8"
        )
    )
    token_counts = {
        record_id: int(tokens) for record_id, tokens in historical["token_counts"].items()
    }
    profile = next(
        item for item in pack.config.strategies if item.strategy_id == "direct-target-lora-v0.1"
    )
    schedule = resolve_schedule(
        records=pack.direct_train,
        sequence_lengths=token_counts,
        profile=profile,
        pack_root=pack.root,
        seed=pack.config.seed,
    )
    historical_ids = [item["example_id"] for item in historical["items"]]
    assert [item.record_id for item in schedule.items] == historical_ids
    assert [item.sequence_tokens for item in schedule.items] == [
        item["sequence_tokens"] for item in historical["items"]
    ]
    assert len(schedule.items) == 672
    assert schedule.processed_tokens == 272643
    assert schedule.optimizer_steps == 168
    assert schedule.checkpoint_steps == [56, 112, 168]


def test_opsroute_generic_schedule_matches_historical_anchored_schedule() -> None:
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    profile = next(
        item
        for item in pack.config.strategies
        if item.strategy_id == "anchored-behavioral-transfer-v0.1"
    )
    assert profile.teacher_outputs_artifact is not None
    outputs = [
        GenerationOutput.model_validate_json(line, strict=True)
        for line in (pack.root / profile.teacher_outputs_artifact)
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    anchors = [
        CapabilityLabeledRecord.model_validate_json(line, strict=True)
        for line in (pack.root / "anchors/available.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    supervision = prepare_anchored_supervision(
        pack,
        outputs,
        minimum_examples_per_group=profile.minimum_examples_per_group,
        teacher_selection_namespace=str(profile.teacher_selection_namespace),
        anchor_selection_namespace=str(profile.anchor_selection_namespace),
        teacher_stage_sha256="0" * 64,
        anchors=anchors,
    )
    assert supervision.status == "FROZEN"
    historical = json.loads(
        (
            ROOT / "artifacts/phase3b/schedules/"
            "phase3b-hybrid-schedule-fef500c2ac61404e/schedule.json"
        ).read_text(encoding="utf-8")
    )
    token_counts = {
        record_id.removeprefix("phase3b-teacher-").removeprefix("phase3b-anchor-"): int(tokens)
        for record_id, tokens in historical["token_counts"].items()
    }
    schedule = resolve_schedule(
        records=supervision.records,
        sequence_lengths=token_counts,
        profile=profile,
        pack_root=pack.root,
        seed=pack.config.seed,
    )
    historical_ids = [
        item["training_record_id"].removeprefix("phase3b-teacher-").removeprefix("phase3b-anchor-")
        for item in historical["items"]
    ]
    assert [item.record_id for item in schedule.items] == historical_ids
    assert len(schedule.items) == 672
    assert schedule.processed_tokens == 272568
    assert schedule.residual_tokens == 75
    assert schedule.optimizer_steps == 168
    assert schedule.checkpoint_steps == [56, 112, 168]


def test_opsroute_reference_strict_semantics_match_historical_parser() -> None:
    pack = load_capability_pack(PACK_ROOT, require_executable=True)
    sources = [
        (
            "confirmatory",
            ROOT / "artifacts/phase3b/test/"
            "phase3b-target_full_retrain-confirmatory_test-20260715T151431-5d04e6d4/"
            "predictions.jsonl",
        ),
        (
            "confirmatory",
            ROOT / "artifacts/phase3b/test/"
            "phase3b-target_hybrid_anchored_distillation_10-confirmatory_test-"
            "20260715T150725-33a99282/predictions.jsonl",
        ),
        (
            "adversarial",
            ROOT / "artifacts/phase4/evaluations/"
            "phase4-adversarial-target_full_retrain-95094c5782a1-attempt-1-cecfea0e/"
            "predictions.jsonl",
        ),
        (
            "adversarial",
            ROOT / "artifacts/phase4/evaluations/"
            "phase4-adversarial-target_hybrid_anchored_distillation_10-"
            "95094c5782a1-attempt-1-30f70c02/predictions.jsonl",
        ),
    ]
    for surface, path in sources:
        records = {item.record_id: item for item in pack.inputs[surface]}
        oracles = pack.oracle_map(surface)
        for line in path.read_text(encoding="utf-8").splitlines():
            historical_record = json.loads(line)
            record_id = str(historical_record["example_id"])
            raw = str(historical_record["raw_output"])
            generic = evaluate_output(
                record=records[record_id],
                oracle=oracles[record_id],
                raw_output=raw,
                config=pack.evaluator,
                output_schema=pack.output_schema,
                cross_field_schema=pack.cross_field_schema,
                vocabularies=pack.vocabularies,
                safety_rules=pack.safety_rules,
                trusted_plugin=pack.trusted_plugin,
            )
            historical = parse_action_contract(raw)
            assert generic.historical_strict_valid == (historical.classification == "STRICT_VALID")
            assert generic.semantic_match == bool(
                historical_record["metrics"]["semantic_decision_score_v0"]
            )
