from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from inheritbench.capability.leakage import leakage_collisions
from inheritbench.capability.loader import load_capability_pack
from inheritbench.capability.plugins import load_trusted_plugin
from inheritbench.capability.scaffold import scaffold_capability
from inheritbench.capability.schemas import TrustedEvaluatorPluginConfig
from inheritbench.reference_packs.integrity import verify_frozen_root_manifest
from inheritbench.reference_packs.opsroute import verify_opsroute_pack
from inheritbench.reference_packs.purchase_approval import verify_purchase_approval_pack

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GENERIC_ROOTS = (
    REPOSITORY_ROOT / "src/inheritbench/capability",
    REPOSITORY_ROOT / "src/inheritbench/model_adapters",
    REPOSITORY_ROOT / "src/inheritbench/strategies",
    REPOSITORY_ROOT / "src/inheritbench/orchestration",
)
FORBIDDEN = (
    "inheritbench.data.opsroute",
    "inheritbench.evaluation.contracts",
    "inheritbench.day2",
    "inheritbench.day3",
    "inheritbench.day3_matched",
    "inheritbench.phase3b",
    "inheritbench.phase4",
    "inheritbench.phase5",
)


def test_scaffold_round_trip_is_strict_draft(tmp_path: Path) -> None:
    root = scaffold_capability("expense routing", tmp_path / "pack")
    pack = load_capability_pack(root)
    assert pack.config.capability.id == "expense-routing"
    assert pack.config.capability.status == "DRAFT"
    assert pack.validation.status == "PASS"
    with pytest.raises(ValueError, match="not executable"):
        load_capability_pack(root, require_executable=True)


def test_reference_and_fixture_use_same_loader() -> None:
    opsroute = load_capability_pack(
        REPOSITORY_ROOT / "capabilities/opsroute/v0.2.0",
        require_executable=True,
    )
    fixture = load_capability_pack(
        REPOSITORY_ROOT / "examples/capability-packs/purchase-approval",
        allow_fixture=True,
        require_executable=True,
    )
    assert opsroute.validation.status == fixture.validation.status == "PASS"
    assert opsroute.config.capability.id == "opsroute"
    assert fixture.config.capability.id == "purchase-approval"
    assert opsroute.input_schema != fixture.input_schema
    assert opsroute.vocabularies != fixture.vocabularies


def test_generic_packages_do_not_import_historical_workflows() -> None:
    violations: list[str] = []
    for root in GENERIC_ROOTS:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                for module in modules:
                    if any(module == item or module.startswith(f"{item}.") for item in FORBIDDEN):
                        violations.append(f"{path.relative_to(REPOSITORY_ROOT)}:{module}")
    assert violations == []


def test_reference_projection_and_frozen_roots_replay_exactly() -> None:
    verify_opsroute_pack()
    verify_purchase_approval_pack()
    manifest = verify_frozen_root_manifest()
    assert manifest["roots"]["artifacts/phase3b"]["file_count"] == 90


def test_pack_tampering_and_untrusted_plugins_fail_closed(tmp_path: Path) -> None:
    root = scaffold_capability("tamper check", tmp_path / "pack")
    direct_path = root / "data/direct_train.jsonl"
    record = json.loads(direct_path.read_text(encoding="utf-8"))
    record["assistant_label"] = '{"decision":"refuse"}'
    direct_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ASSISTANT_LABEL_HASH_MISMATCH"):
        load_capability_pack(root)

    plugin = TrustedEvaluatorPluginConfig(
        entry_point_group="inheritbench.evaluators",
        entry_point_name="not-installed",
        distribution="not-installed",
        version="0.1.0",
        code_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="missing or ambiguous"):
        load_trusted_plugin(plugin)


def test_generic_leakage_detects_semantic_collisions() -> None:
    pack = load_capability_pack(
        REPOSITORY_ROOT / "examples/capability-packs/purchase-approval",
        allow_fixture=True,
    )
    record = pack.inputs["source_gate"][0]
    collisions = leakage_collisions({"first": [record], "second": [record]})
    assert collisions["record_id"]
    assert collisions["content"]
    assert collisions["semantic"]
