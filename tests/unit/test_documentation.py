from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_FILES = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").glob("*.md"))]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FEEDBACK_SESSION_ID = "019f61c4-1e2b-7861-8e2c-7fe82c81255d"
FEEDBACK_DOCUMENTS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "DEVPOST_SUBMISSION_DRAFT.md",
]
FEEDBACK_VALUE = re.compile(r"Codex `/feedback` Session ID:\*{0,2}\s+`([^`]+)`")


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


def test_readme_has_release_contract() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    required_sections = [
        "## Judge Links",
        "## Product Workflow",
        "## Five-Minute Judge Browser Test",
        "## Browser Boundary",
        "## Reference Result",
        "## Execution Stages",
        "## Installation and Supported Platforms",
        "## Reproduction Levels",
        "## Capability-Pack Extensibility",
        "## Built with Codex and GPT-5.6",
        "## Scientific Boundaries",
        "## License and Citation",
    ]
    positions = [readme.index(section) for section in required_sections]
    assert positions == sorted(positions)
    assert "Move the model. Keep the capability. Prove it survived." in readme
    assert "PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED" in readme
    assert "/sandbox/" in readme
    assert "/run/opsroute-qwen-olmo/" in readme
    assert "### Level 1 — Browser verification" in readme
    assert "### Level 2 — Local evidence replay and tests" in readme
    assert "### Level 3 — Full succession reproduction" in readme
    assert "uv run --no-dev inheritbench succession replay --output runs" in readme
    assert "uv run inheritbench succession plan" in readme
    assert "uv run inheritbench succession run" in readme
    assert "ANCHORS_REQUIRED" in readme
    assert "succession replay \\\n  --case" not in readme
    assert "ten labels total" not in readme.lower()
    assert ":contentReference" not in readme


def test_current_reference_result_is_exact_and_distinct_from_history() -> None:
    documents = [
        (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs/JUDGE_REPLAY.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs/DEVPOST_SUBMISSION_DRAFT.md").read_text(encoding="utf-8"),
    ]
    expected_metrics = {
        "Clean operational correctness: `64 / 64`",
        "Clean exact-contract fidelity: `63 / 64`",
        "Clean strict validity: `64 / 64`",
        "Clean safety blockers: `0`",
        "Adversarial exact-contract result: `20 / 32`",
        "Adversarial strict validity: `31 / 32`",
        "Safety findings: `2 findings on 1 record`",
        "Readiness: `CONDITIONAL_PASS`",
        "Replay: `192 predictions verified`",
    }
    for contents in documents:
        for metric in expected_metrics:
            assert metric in contents
        assert "Phase 3B" in contents
        assert "historical" in contents.lower()


def test_release_documents_are_clean_clone_oriented() -> None:
    clean_clone_documents = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs/JUDGE_REPLAY.md",
        REPO_ROOT / "docs/DEVPOST_SUBMISSION_DRAFT.md",
    ]
    for document in clean_clone_documents:
        contents = document.read_text(encoding="utf-8")
        assert "runs/reference" not in contents
        assert "/Users/" not in contents
        assert "pnpm verify:web" in contents
        assert "/sandbox/" in contents
        assert "/run/opsroute-qwen-olmo/" in contents


def test_license_citation_and_notice_are_present() -> None:
    citation = (REPO_ROOT / "CITATION.cff").read_text(encoding="utf-8")
    notice = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8")
    licensing = (REPO_ROOT / "docs/LICENSING.md").read_text(encoding="utf-8")
    assert "family-names: Muhammad" in citation
    assert "given-names: Faizan" in citation
    assert "license: Apache-2.0" in citation
    assert "Copyright 2026 Faizan Muhammad" in notice
    assert "Project-Authored Data" in licensing
    assert "Generated Model Outputs" in licensing
    assert "GPT-Generated Memo" in licensing
    assert "does not redistribute" in licensing


def test_build_log_preserves_placeholder_history_and_appends_resolution() -> None:
    build_log = (REPO_ROOT / "docs/BUILD_LOG.md").read_text(encoding="utf-8")
    historical = build_log.split("## 2026-07-16 — Documentation and Submission Readiness", 1)[
        1
    ].split("## 2026-07-16 — Product Narrative Refocus", 1)[0]
    assert "remain explicit placeholders rather than fabricated" in historical
    current = build_log.split(
        "## 2026-07-21 — Submission Identity and Documentation Release Pass", 1
    )[1]
    assert FEEDBACK_SESSION_ID in current


def test_feedback_session_id_is_submission_ready() -> None:
    fake_values = {"TODO", "TBD", "YOUR_SESSION_ID", "PLACEHOLDER"}
    for document in FEEDBACK_DOCUMENTS:
        contents = document.read_text(encoding="utf-8")
        feedback_lines = [line for line in contents.splitlines() if "/feedback" in line]
        assert feedback_lines, f"{document.name} must document the /feedback requirement"
        assert not any(
            fake.lower() in line.lower() for line in feedback_lines for fake in fake_values
        ), f"{document.name} still has a fake /feedback value"

        documented_values = FEEDBACK_VALUE.findall(contents)
        assert documented_values, f"{document.name} must contain a nonempty Session ID"
        assert all(value == FEEDBACK_SESSION_ID for value in documented_values)
        assert "official Codex interface" in contents
        assert "majority of" in contents and "core implementation work" in contents
        assert re.search(r"OpenAI Build Week submission\s+compliance", contents)

    runtime_sources = [
        path
        for path in (REPO_ROOT / "apps/web").rglob("*")
        if path.is_file()
        and path.suffix in {".ts", ".tsx", ".js", ".jsx", ".json", ".html"}
        and "node_modules" not in path.parts
        and ".next" not in path.parts
        and "out" not in path.parts
    ]
    assert not any(
        FEEDBACK_SESSION_ID in path.read_text(encoding="utf-8", errors="ignore")
        for path in runtime_sources
    )
    assert "PASTE_REAL_CODEX_SESSION_ID_HERE" not in "\n".join(
        document.read_text(encoding="utf-8") for document in MARKDOWN_FILES
    )


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
    published_contract = documented.split("## Pack-Driven CLI Execution Output", 1)[0]
    assert "run.json" not in published_contract
    assert "replay_manifest.json" not in published_contract
    assert "run.json" in documented
    assert "replay_manifest.json" in documented


def test_published_cli_workflow_matches_registered_commands() -> None:
    cli = (REPO_ROOT / "src/inheritbench/cli.py").read_text(encoding="utf-8")
    command_groups = {
        "capability": {"init", "validate", "inspect"},
        "succession": {
            "plan",
            "run",
            "resume",
            "add-anchors",
            "inspect",
            "replay",
            "export-web",
        },
    }
    for group, commands in command_groups.items():
        for command in commands:
            assert f'@{group}_app.command("{command}")' in cli
    assert '@app.command("succeed")' in cli

    public_documents = [
        (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs/JUDGE_REPLAY.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs/PACK_DRIVEN_SUCCESSION.md").read_text(encoding="utf-8"),
    ]
    for contents in public_documents:
        assert "inheritbench capability validate" in contents
        assert "inheritbench succession plan" in contents
        assert "inheritbench succession run" in contents
        assert "inheritbench succession inspect" in contents
        assert "inheritbench succession replay --run" in contents


def test_public_copy_preserves_product_boundaries() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (REPO_ROOT / "docs/PRODUCT_ARCHITECTURE.md").read_text(encoding="utf-8")
    devpost = (REPO_ROOT / "docs/DEVPOST_SUBMISSION_DRAFT.md").read_text(encoding="utf-8")
    landing = (REPO_ROOT / "apps/web/src/components/landing-experience.tsx").read_text(
        encoding="utf-8"
    )
    sandbox = (REPO_ROOT / "apps/web/src/components/sandbox/sandbox-experience.tsx").read_text(
        encoding="utf-8"
    )

    combined = "\n".join([readme, architecture, devpost, landing, sandbox])
    for required in [
        "Qwen2.5-0.5B",
        "OLMo-2-1B",
        "Apple MPS",
        "Purchase Approval",
        "fixture-only",
        "live generic teacher generation",
        "MIGRATION_BLOCKED",
    ]:
        assert required.lower() in combined.lower()
    assert "This is not the model-migration engine" in sandbox
    assert "no model training or fresh inference happens here" in sandbox
    assert "historical 160-record" in readme
    assert "192-prediction product projection" in readme


def test_landing_presents_cli_before_browser_assurance() -> None:
    landing = (REPO_ROOT / "apps/web/src/components/landing-experience.tsx").read_text(
        encoding="utf-8"
    )
    assert "Local model-succession CLI" in landing
    assert "Developer-authored capability pack" in landing
    assert "inheritbench capability validate" in landing
    assert "inheritbench succession plan" in landing
    assert "inheritbench succession run" in landing
    assert "Proof of execution" in landing
    assert "The Assurance Lab is not the model-migration engine" in landing
    assert landing.index('id="developer-workflow"') < landing.index('id="reference-result"')
    assert landing.index('id="reference-result"') < landing.index("Judge verification")
    for forbidden in [
        "run the migration in your browser",
        "upload your model",
        "supports any model",
        "production safe",
    ]:
        assert forbidden not in landing.lower()


def test_demo_preserves_cli_and_assurance_truth() -> None:
    demo = (REPO_ROOT / "docs/DEMO_SCRIPT.md").read_text(encoding="utf-8")
    assert "InheritBench is a local CLI" in demo
    assert "The Lab is not performing the migration" in demo
    assert "validation only" in demo
    assert "final tests remained sealed" in demo
    assert "CONDITIONAL_PASS → MIGRATION_BLOCKED" in demo
    assert "Codex helped implement" in demo
    assert "GPT-5.6 produced a structured memo" in demo
