from __future__ import annotations

from collections import Counter
from pathlib import Path

from inheritbench.day3.pool import semantic_leakage_sha256
from inheritbench.phase3b.schemas import (
    ConfirmatoryExampleV0_1,
    ConfirmatoryLeakageAuditV0_1,
    ConfirmatoryOracleRecordV0_1,
    ConfirmatorySplitManifestV0_1,
)


def _single(pattern: str) -> Path:
    paths = list(Path("artifacts/phase3b").glob(pattern))
    assert len(paths) == 1
    return paths[0]


def _records(path: Path, schema: type) -> list:
    return [schema.model_validate_json(line, strict=True) for line in path.read_text().splitlines()]


def test_confirmatory_splits_are_balanced_and_oracles_are_separate() -> None:
    root = _single("confirmatory-data/*/manifest.json").parent
    expected = {"validation": (32, 2), "test": (64, 4)}
    all_ids: set[str] = set()
    for directory, (count, per_group) in expected.items():
        split = root / directory
        manifest = ConfirmatorySplitManifestV0_1.model_validate_json(
            (split / "manifest.json").read_bytes(), strict=True
        )
        examples = _records(split / "inputs.jsonl", ConfirmatoryExampleV0_1)
        oracles = _records(split / "oracle.jsonl", ConfirmatoryOracleRecordV0_1)
        groups = Counter((item.scenario_family, item.archetype) for item in examples)

        assert manifest.example_count == count
        assert manifest.per_archetype_count == per_group
        assert len(examples) == len(oracles) == count
        assert set(groups.values()) == {per_group}
        assert all("expected_contract" not in item.model_dump() for item in examples)
        assert {item.example_id for item in examples} == {item.example_id for item in oracles}
        assert not all_ids.intersection(item.example_id for item in examples)
        all_ids.update(item.example_id for item in examples)


def test_confirmatory_audit_proves_value_sensitive_zero_leakage() -> None:
    path = _single("leakage-audits/*/audit.json")
    audit = ConfirmatoryLeakageAuditV0_1.model_validate_json(path.read_bytes(), strict=True)
    assert audit.status == "PASS"
    assert not audit.id_collisions
    assert not audit.surface_collisions
    assert not audit.input_content_collisions
    assert not audit.record_collisions
    assert not audit.semantic_collisions
    assert not audit.support_violations
    assert all(value > 0 for value in audit.boundary_coverage.values())

    root = _single("confirmatory-data/*/manifest.json").parent
    example = _records(root / "validation/inputs.jsonl", ConfirmatoryExampleV0_1)[0]
    changed = example.input.model_copy(
        update={
            "context": {
                **example.input.context,
                "requester_authorized": not example.input.context["requester_authorized"],
            }
        }
    )
    assert semantic_leakage_sha256(example.scenario_family, example.input) != (
        semantic_leakage_sha256(example.scenario_family, changed)
    )
