from __future__ import annotations

import json
from pathlib import Path

from inheritbench.data.opsroute.schemas import EvaluationMetadata
from inheritbench.evaluation.contracts import ActionContract
from inheritbench.evaluation.metrics import score_prediction
from inheritbench.evaluation.parser import parse_action_contract


def test_evaluation_golden_cases() -> None:
    cases = json.loads(Path("tests/fixtures/evaluation_golden.json").read_text(encoding="utf-8"))
    for case in cases:
        expected = ActionContract.model_validate(case["expected"], strict=True)
        evaluation = EvaluationMetadata.model_validate(case["evaluation"], strict=True)
        parsed = parse_action_contract(case["raw_output"])
        metrics = score_prediction(parsed, expected, evaluation)
        assert parsed.classification == case["classification"], case["name"]
        for key, value in case["metrics"].items():
            assert getattr(metrics, key) == value, case["name"]
