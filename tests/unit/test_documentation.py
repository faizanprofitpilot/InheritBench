from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_FILES = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").glob("*.md"))]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def test_internal_documentation_links_resolve() -> None:
    failures: list[str] = []
    for document in MARKDOWN_FILES:
        for raw_target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            parsed = urlparse(target)
            if parsed.scheme or target.startswith("#"):
                continue
            relative = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not relative:
                continue
            resolved = (document.parent / relative).resolve()
            if not resolved.exists():
                failures.append(f"{document.relative_to(REPO_ROOT)} -> {target}")
    assert not failures, "broken internal documentation links:\n" + "\n".join(failures)


def test_readme_has_product_and_collaboration_contract() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "## What InheritBench Does" in readme
    assert "## Why InheritBench Is Different" in readme
    assert "## How InheritBench Works" in readme
    assert "## Built with Codex and GPT-5.6" in readme
    assert "Models are becoming fungible. Learned capabilities are not." in readme
    assert (
        "InheritBench transfers a learned operational capability from one model family to its "
        "successor" in readme
    )
    assert "A recovered successor adapter, residual-risk report" in readme
    assert "TODO BEFORE SUBMISSION: Add primary Codex `/feedback` Session ID." in readme
    assert "PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED" in readme
    assert "ten labels total" not in readme.lower()
    assert ":contentReference" not in readme


def test_succession_output_documentation_matches_implementation() -> None:
    documented = (REPO_ROOT / "docs/SUCCESSION_OUTPUTS.md").read_text(encoding="utf-8")
    expected = {
        "succession_run_manifest.json",
        "readiness_report.json",
        "replay_receipt.json",
        "evaluation_summary.json",
        "residual_failures.json",
        "label_accounting.json",
        "compute_accounting.json",
        "adapter_reference.json",
        "evidence_manifest.json",
    }
    for filename in expected:
        assert f"`{filename}`" in documented or filename in documented
    published_contract = documented.split("## Pack-Driven Execution Output", 1)[0]
    assert "run.json" not in published_contract
    assert "replay_manifest.json" not in published_contract
    assert "run.json" in documented
    assert "replay_manifest.json" in documented
