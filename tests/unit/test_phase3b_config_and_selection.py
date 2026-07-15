from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from inheritbench.phase3b.config import (
    load_experiment_config,
    validate_isolated_root,
)
from inheritbench.phase3b.schemas import (
    HybridDatasetManifestV0_1,
    OriginalAnchorSelectionV0_1,
    SyntheticSelectionV0_1,
)

EXPERIMENT = Path("configs/experiments/phase3b.yaml")
EXPECTED_ANCHORS = [
    "opsroute_v010_refund_duplicate_auto_refund_09_0eee0b95",
    "opsroute_v010_refund_duplicate_auto_refund_13_72c027ba",
    "opsroute_v010_refund_duplicate_auto_refund_06_5c0cf7ae",
    "opsroute_v010_refund_duplicate_auto_refund_01_1bbef901",
    "opsroute_v010_refund_duplicate_auto_refund_12_29af0ec1",
    "opsroute_v010_refund_duplicate_auto_refund_07_74971263",
    "opsroute_v010_refund_duplicate_auto_refund_08_37aacfc9",
    "opsroute_v010_refund_duplicate_auto_refund_04_c242cc0e",
    "opsroute_v010_refund_duplicate_auto_refund_00_a3fc39fe",
    "opsroute_v010_refund_duplicate_auto_refund_03_43fefb45",
]


def _single(pattern: str) -> Path:
    paths = list(Path("artifacts/phase3b").glob(pattern))
    assert len(paths) == 1
    return paths[0]


def test_phase3b_configs_are_strict_and_isolated(tmp_path: Path) -> None:
    config = load_experiment_config(EXPERIMENT)
    assert config.method_id == "target_hybrid_anchored_distillation_10"
    assert config.artifact_root == "artifacts/phase3b"

    with pytest.raises(ValueError, match="historical artifact roots"):
        validate_isolated_root(Path("artifacts/day3-matched/new"), config)

    raw = yaml.safe_load(EXPERIMENT.read_text(encoding="utf-8"))
    raw["unexpected"] = True
    invalid = tmp_path / "phase3b.yaml"
    invalid.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_experiment_config(invalid)


def test_phase3b_anchor_selection_is_exact_hash_rank() -> None:
    path = _single("anchor-selections/*/selection.json")
    selection = OriginalAnchorSelectionV0_1.model_validate_json(path.read_bytes(), strict=True)
    expected = sorted(selection.eligible_ids, key=selection.ranks.__getitem__)[:10]
    assert selection.selected_ids == EXPECTED_ANCHORS
    assert selection.selected_ids == expected
    assert len(selection.unselected_ids) == 4


def test_phase3b_hybrid_selection_has_frozen_composition() -> None:
    synthetic_path = _single("synthetic-selections/*/selection.json")
    synthetic = SyntheticSelectionV0_1.model_validate_json(synthetic_path.read_bytes(), strict=True)
    manifest_path = _single("hybrid-data/*/manifest.json")
    manifest = HybridDatasetManifestV0_1.model_validate_json(
        manifest_path.read_bytes(), strict=True
    )
    records_path = manifest_path.parent / "records.jsonl"
    records = [json.loads(line) for line in records_path.read_text().splitlines()]

    assert len(synthetic.selected_ids) == 214
    assert len(synthetic.selected_by_group) == 16
    assert len(synthetic.blindspot_selected_ids) == 4
    assert manifest.synthetic_count == 214
    assert manifest.anchor_count == 10
    assert manifest.total_count == len(records) == 224
    assert set(manifest.group_counts.values()) == {14}
    assert manifest.family_counts == {
        "refund_policy_routing": 112,
        "subscription_cancellation_retention": 112,
    }
    assert sum(item["label_origin"] == "teacher_output" for item in records) == 214
    assert sum(item["label_origin"] == "original_anchor" for item in records) == 10
