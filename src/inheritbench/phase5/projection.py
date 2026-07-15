"""Deterministic Phase 5 display projection from frozen evidence."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal, cast

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    content_sha256,
    sha256_bytes,
    sha256_file,
)
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.phase5 import (
    PHASE4_DECISION_CONTENT_SHA256,
    PHASE5_PROJECTION_ID,
    PHASE5_SHOWCASE_CONTENT_SHA256,
)
from inheritbench.phase5.schemas import (
    EvaluationSurface,
    Phase5CaseDetailsV0_1,
    Phase5CasePredictionV0_1,
    Phase5ProjectionFileV0_1,
    Phase5RepresentativeCaseDetailV0_1,
    Phase5SourceIndexV0_1,
    Phase5SourceReferenceV0_1,
    Phase5StoryFactV0_1,
    Phase5StoryStageV0_1,
    Phase5StoryV0_1,
    Phase5WebProjectionManifestV0_1,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SHOWCASE_ROOT = REPO_ROOT / "artifacts/showcase/inheritbench-v0.1-gpt"
PROJECTION_ROOT = REPO_ROOT / "artifacts/phase5/web-projection"

INDEPENDENT_DATASET = REPO_ROOT / (
    "artifacts/day3/synthetic-data/day3-synthetic-dataset-9d186a0dde24549f/manifest.json"
)
MATCHED_DATASET = REPO_ROOT / (
    "artifacts/day3-matched/synthetic-data/"
    "day3-matched-synthetic-dataset-36eea02e066b021a/manifest.json"
)
PHASE3B_BASELINE = REPO_ROOT / (
    "artifacts/phase3b/historical-baselines/phase3b-baseline-aebd48f484b9c63e/baseline.json"
)
PHASE3B_COMPOSITION = REPO_ROOT / (
    "artifacts/phase3b/comparisons/phase3b-comparison-data_composition-023dbcb95320/comparison.json"
)
PHASE4_EVALUATIONS = REPO_ROOT / "artifacts/phase4/evaluations"
PHASE4_CLASSIFICATIONS = REPO_ROOT / (
    "artifacts/phase4/analysis/phase4-analysis-98cdc9db978646e7/classifications.jsonl"
)
ADVERSARIAL_DATA = REPO_ROOT / "data/opsroute/v0.1.0/adversarial.jsonl"

_CONTENT_EXCLUSIONS = {"content_sha256", "created_at", "finished_at"}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], value)


def _json_value(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(cast(dict[str, Any], value))
    return rows


def _content(value: Any) -> str:
    return content_sha256(value, excluded_keys=_CONTENT_EXCLUSIONS)


def _validate_content(path: Path, value: dict[str, Any]) -> None:
    expected = value.get("content_sha256")
    if isinstance(expected, str) and _content(value) != expected:
        raise ValueError(f"content hash mismatch: {path}")


def _reference(
    source_id: str,
    path: Path,
    *,
    json_path: str,
    surface: EvaluationSurface | Literal["cross_surface", "not_applicable"],
    content_hash: str | None = None,
) -> Phase5SourceReferenceV0_1:
    if not path.is_file():
        raise FileNotFoundError(path)
    return Phase5SourceReferenceV0_1(
        schema_version="phase5-source-reference-v0.1",
        source_id=source_id,
        relative_path=str(path.relative_to(REPO_ROOT)),
        byte_sha256=sha256_file(path),
        content_sha256=content_hash,
        json_path=json_path,
        evaluation_surface=surface,
    )


def verify_showcase() -> dict[str, Any]:
    manifest_path = SHOWCASE_ROOT / "manifest.json"
    manifest = _json(manifest_path)
    _validate_content(manifest_path, manifest)
    if manifest.get("content_sha256") != PHASE5_SHOWCASE_CONTENT_SHA256:
        raise ValueError("unexpected Phase 4 showcase content hash")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("showcase manifest has no file list")
    loaded: dict[str, Any] = {"manifest.json": manifest}
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str):
            raise ValueError("invalid showcase file entry")
        relative_path = cast(str, item["relative_path"])
        path = SHOWCASE_ROOT / relative_path
        if not path.is_file() or sha256_file(path) != item.get("byte_sha256"):
            raise ValueError(f"showcase file hash mismatch: {relative_path}")
        if path.stat().st_size != item.get("bytes"):
            raise ValueError(f"showcase file byte count mismatch: {relative_path}")
        if path.suffix == ".json":
            loaded[relative_path] = _json_value(path)
    decision = cast(dict[str, Any], loaded["phase4-decision.json"])
    if decision.get("content_sha256") != PHASE4_DECISION_CONTENT_SHA256:
        raise ValueError("unexpected Phase 4 decision hash")
    return loaded


def derive_evaluation_surface(
    selection: dict[str, Any], parent: dict[str, Any], run_splits: Iterable[str]
) -> EvaluationSurface:
    explicit = {
        item.get("evaluation_surface")
        for item in cast(list[dict[str, Any]], selection.get("cases", []))
        if item.get("status") == "SELECTED" and item.get("evaluation_surface") is not None
    }
    if len(explicit) > 1:
        raise ValueError("representative selection spans multiple implicit surfaces")
    splits = set(run_splits)
    inferred: EvaluationSurface
    if splits == {"adversarial"}:
        inferred = "adversarial"
    elif splits == {"confirmatory_test"}:
        inferred = "confirmatory"
    elif splits == {"exploratory_legacy_test"}:
        inferred = "exploratory"
    else:
        raise ValueError(f"cannot derive representative evaluation surface from {splits}")
    if explicit and next(iter(explicit)) != inferred:
        raise ValueError("recorded representative surface disagrees with parent artifacts")
    parent_schema = parent.get("schema_version")
    if inferred == "adversarial" and parent_schema != "phase4-analysis-v0.1":
        raise ValueError("adversarial cases must derive from the frozen Phase 4 analysis")
    return inferred


def _phase4_run_index(analysis: dict[str, Any]) -> dict[str, tuple[Path, dict[str, Any]]]:
    expected = analysis.get("evaluation_run_sha256s")
    if not isinstance(expected, dict) or len(expected) != 6:
        raise ValueError("Phase 4 analysis does not reference six evaluation runs")
    found: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(PHASE4_EVALUATIONS.glob("*/manifest.json")):
        manifest = _json(path)
        if manifest.get("content_sha256") == expected.get(manifest.get("system_id")):
            found[cast(str, manifest["system_id"])] = (path, manifest)
    if set(found) != set(expected):
        raise ValueError("representative cases are missing a Phase 4 system run")
    for system_id, (_, manifest) in found.items():
        if manifest.get("content_sha256") != expected[system_id]:
            raise ValueError(f"run lineage mismatch for {system_id}")
    return found


def _phase4_case_details(
    selection: dict[str, Any], analysis: dict[str, Any]
) -> tuple[list[Phase5RepresentativeCaseDetailV0_1], list[Phase5SourceReferenceV0_1]]:
    runs = _phase4_run_index(analysis)
    surface = derive_evaluation_surface(
        selection, analysis, (manifest["split"] for _, manifest in runs.values())
    )
    if surface != "adversarial":
        raise ValueError("current frozen selection is not Phase 4 adversarial evidence")
    input_rows = {row["example_id"]: row for row in _jsonl(ADVERSARIAL_DATA)}
    classification_rows = _jsonl(PHASE4_CLASSIFICATIONS)
    classifications = {(row["system_id"], row["example_id"]): row for row in classification_rows}
    predictions: dict[str, dict[str, dict[str, Any]]] = {}
    references: list[Phase5SourceReferenceV0_1] = []
    split_hashes: set[str] = set()
    oracle_hashes: set[str] = set()
    for system_id, (manifest_path, manifest) in sorted(runs.items()):
        prediction_ref = manifest.get("prediction_artifact")
        if not isinstance(prediction_ref, dict):
            raise ValueError(f"missing prediction artifact for {system_id}")
        predictions_path = manifest_path.parent / cast(str, prediction_ref["relative_path"])
        if sha256_file(predictions_path) != prediction_ref.get("byte_sha256"):
            raise ValueError(f"tampered prediction artifact for {system_id}")
        rows = _jsonl(predictions_path)
        predictions[system_id] = {row["example_id"]: row for row in rows}
        split_hashes.add(cast(str, manifest["split_sha256"]))
        oracle_hashes.add(cast(str, manifest["oracle_sha256"]))
        references.extend(
            [
                _reference(
                    f"phase4-run-{system_id}",
                    manifest_path,
                    json_path="$",
                    surface="adversarial",
                    content_hash=cast(str, manifest["content_sha256"]),
                ),
                _reference(
                    f"phase4-predictions-{system_id}",
                    predictions_path,
                    json_path="$[*]",
                    surface="adversarial",
                    content_hash=cast(str, prediction_ref.get("content_sha256")),
                ),
            ]
        )
    if len(split_hashes) != 1 or len(oracle_hashes) != 1:
        raise ValueError("representative system runs do not share one frozen surface")

    details: list[Phase5RepresentativeCaseDetailV0_1] = []
    parent_sha = cast(str, selection["analysis_sha256"])
    cases = selection.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError("representative selection must contain eight frozen slots")
    for selected in cases:
        if selected["status"] == "NO_ELIGIBLE_CASE":
            payload: dict[str, Any] = {
                "schema_version": "phase5-representative-case-v0.1",
                "slot": selected["slot"],
                "status": "NO_ELIGIBLE_CASE",
                "eligibility_reason": selected["eligibility_reason"],
                "selection_rank": None,
                "evaluation_surface": None,
                "example_id": None,
                "scenario_family": None,
                "archetype": None,
                "input": None,
                "expected_contract": None,
                "system_predictions": [],
                "selection_parent_sha256": parent_sha,
            }
            payload["content_sha256"] = _content(payload)
            details.append(Phase5RepresentativeCaseDetailV0_1.model_validate(payload))
            continue
        example_id = cast(str, selected["example_id"])
        input_row = input_rows.get(example_id)
        if input_row is None:
            raise ValueError(f"selected case is absent from the adversarial split: {example_id}")
        expected_contract = input_row["expected"]
        system_outputs: list[Phase5CasePredictionV0_1] = []
        selected_failures = cast(dict[str, str], selected["system_primary_failures"])
        if set(selected_failures) != set(runs):
            raise ValueError(f"selected case has incomplete system lineage: {example_id}")
        for system_id, (manifest_path, manifest) in sorted(runs.items()):
            prediction = predictions[system_id].get(example_id)
            if prediction is None:
                raise ValueError(f"missing {system_id} prediction for {example_id}")
            if prediction.get("split") != "adversarial":
                raise ValueError(f"surface mismatch for {system_id}/{example_id}")
            if prediction.get("expected_contract") != expected_contract:
                raise ValueError(f"expected-contract mismatch for {system_id}/{example_id}")
            classification = classifications.get((system_id, example_id))
            if classification is None:
                raise ValueError(f"missing failure classification for {system_id}/{example_id}")
            if classification["primary_failure"] != selected_failures[system_id]:
                raise ValueError(f"selection-parent failure mismatch for {system_id}/{example_id}")
            prediction_ref = cast(dict[str, Any], manifest["prediction_artifact"])
            system_outputs.append(
                Phase5CasePredictionV0_1(
                    system_id=system_id,
                    split=cast(str, prediction["split"]),
                    run_id=cast(str, prediction["run_id"]),
                    prediction_id=cast(str, prediction["prediction_id"]),
                    raw_output=cast(str, prediction["raw_output"]),
                    parser_result=cast(dict[str, Any], prediction["parser_result"]),
                    expected_contract=cast(dict[str, Any], prediction["expected_contract"]),
                    metrics=cast(dict[str, Any], prediction["metrics"]),
                    primary_failure=cast(str, classification["primary_failure"]),
                    failure_tags=cast(list[str], classification["tags"]),
                    prediction_content_sha256=cast(str, prediction["content_sha256"]),
                    run_content_sha256=cast(str, manifest["content_sha256"]),
                    split_sha256=cast(str, manifest["split_sha256"]),
                    oracle_sha256=cast(str, manifest["oracle_sha256"]),
                    prediction_artifact_byte_sha256=cast(str, prediction_ref["byte_sha256"]),
                )
            )
            if manifest_path.parent.name != prediction["run_id"]:
                raise ValueError(f"prediction run directory mismatch for {system_id}")
        payload = {
            "schema_version": "phase5-representative-case-v0.1",
            "slot": selected["slot"],
            "status": "SELECTED",
            "eligibility_reason": selected["eligibility_reason"],
            "selection_rank": selected["selection_rank"],
            "evaluation_surface": surface,
            "example_id": example_id,
            "scenario_family": input_row["scenario_family"],
            "archetype": input_row["archetype"],
            "input": input_row["input"],
            "expected_contract": expected_contract,
            "system_predictions": system_outputs,
            "selection_parent_sha256": parent_sha,
        }
        payload["content_sha256"] = _content(payload)
        details.append(Phase5RepresentativeCaseDetailV0_1.model_validate(payload))
    references.extend(
        [
            _reference(
                "opsroute-adversarial-inputs",
                ADVERSARIAL_DATA,
                json_path="$[*]",
                surface="adversarial",
                content_hash=None,
            ),
            _reference(
                "phase4-failure-classifications",
                PHASE4_CLASSIFICATIONS,
                json_path="$[*]",
                surface="adversarial",
                content_hash=None,
            ),
        ]
    )
    return details, references


def _story_and_sources(
    showcase: dict[str, Any], case_sources: list[Phase5SourceReferenceV0_1]
) -> tuple[Phase5StoryV0_1, Phase5SourceIndexV0_1]:
    independent = _json(INDEPENDENT_DATASET)
    matched = _json(MATCHED_DATASET)
    baseline = _json(PHASE3B_BASELINE)
    composition = _json(PHASE3B_COMPOSITION)
    frozen_content_hashes = {
        INDEPENDENT_DATASET: "c9e6c149b03ebf08d17a6c7bf11bca9cda1b10dcc184a8ab3414399ea0029148",
        MATCHED_DATASET: "cdcb330e7e9fcb0189e0bf0a841ab452cfdceffd5f2b971a53419812d4fe8ce5",
        PHASE3B_BASELINE: "aebd48f484b9c63ec7e164e42513a13c4f8c3961b36ed9014f623042fc5090b0",
        PHASE3B_COMPOSITION: "41aeac26bf40329d773e991b1b5f88204e7658738ec65ccbfb6718b82b6cd6ba",
    }
    for path, value in (
        (INDEPENDENT_DATASET, independent),
        (MATCHED_DATASET, matched),
        (PHASE3B_BASELINE, baseline),
        (PHASE3B_COMPOSITION, composition),
    ):
        if value.get("content_sha256") != frozen_content_hashes[path]:
            raise ValueError(f"frozen historical content hash changed: {path}")

    independent_accepted_path = INDEPENDENT_DATASET.parent / cast(
        str, independent["accepted_artifact"]["relative_path"]
    )
    accepted_ids = {
        row["candidate_id"] for row in _jsonl(independent_accepted_path) if row.get("accepted")
    }
    candidate_rows: dict[str, dict[str, Any]] = {}
    for pool_id in cast(list[str], independent["pool_ids"]):
        for row in _jsonl(REPO_ROOT / f"artifacts/day3/pools/{pool_id}/candidate_inputs.jsonl"):
            candidate_rows[cast(str, row["candidate_id"])] = row
    accepted_archetypes = {
        (
            cast(str, candidate_rows[candidate_id]["scenario_family"]),
            cast(str, candidate_rows[candidate_id]["archetype"]),
        )
        for candidate_id in accepted_ids
    }
    if len(accepted_archetypes) != 5:
        raise ValueError("independent Day 3 accepted-archetype count changed")

    system_summaries = cast(list[dict[str, Any]], showcase["system-summaries.json"])
    rows = system_summaries
    summary_index = {row["system_id"]: row for row in rows}
    source_adapted = summary_index["source_adapted_full"]
    target_untouched = summary_index["target_untouched"]
    composition_accounting = cast(list[dict[str, Any]], composition["rows"])[0]

    facts_data: list[tuple[str, str, Any, str, tuple[str, ...]]] = [
        (
            "confirmatory-source-semantic",
            "Adapted Qwen semantic exactness",
            source_adapted["confirmatory_semantic"],
            "54.688%",
            ("showcase-system-summaries",),
        ),
        (
            "confirmatory-target-semantic",
            "Untouched OLMo semantic exactness",
            target_untouched["confirmatory_semantic"],
            "0.000%",
            ("showcase-system-summaries",),
        ),
        (
            "confirmatory-source-strict",
            "Adapted Qwen strict validity",
            source_adapted["confirmatory_strict"],
            "87.500%",
            ("showcase-system-summaries",),
        ),
        (
            "confirmatory-target-strict",
            "Untouched OLMo strict validity",
            target_untouched["confirmatory_strict"],
            "0.000%",
            ("showcase-system-summaries",),
        ),
        (
            "independent-candidates",
            "Independent synthetic candidates",
            independent["candidate_count"],
            "768",
            ("day3-independent-dataset",),
        ),
        (
            "independent-accepted",
            "Independent strict teacher outputs accepted",
            independent["accepted_count"],
            "59",
            ("day3-independent-dataset",),
        ),
        (
            "independent-archetypes",
            "Archetypes represented after strict filtering",
            len(accepted_archetypes),
            "5 of 16",
            ("day3-independent-accepted",),
        ),
        (
            "matched-accepted",
            "Distribution-matched outputs accepted",
            matched["accepted_count"],
            "719 of 768",
            ("day3-matched-dataset",),
        ),
        (
            "blindspot-accepted",
            "Duplicate auto-refund outputs accepted",
            baseline["duplicate_auto_accepted_count"],
            "4 of 48",
            ("phase3b-blindspot-baseline",),
        ),
        (
            "blindspot-mismatches",
            "Duplicate auto-refund policy mismatches",
            baseline["duplicate_auto_policy_mismatch_count"],
            "44",
            ("phase3b-blindspot-baseline",),
        ),
        (
            "hybrid-teacher-labels",
            "Teacher labels used by anchored target",
            composition_accounting["synthetic_labels_used_by_target"],
            "214",
            ("phase3b-data-composition",),
        ),
        (
            "hybrid-anchor-labels",
            "Original anchors used directly by target",
            composition_accounting["original_anchor_labels_used_by_target"],
            "10",
            ("phase3b-data-composition",),
        ),
        (
            "hybrid-total",
            "Unique anchored target training examples",
            composition_accounting["total_unique_target_training_examples"],
            "224",
            ("phase3b-data-composition",),
        ),
        (
            "hybrid-tokens",
            "Anchored target processed tokens",
            composition_accounting["target_training_processed_tokens"],
            "272,568",
            ("phase3b-data-composition",),
        ),
        (
            "upstream-teacher-labels",
            "Original labels used upstream to train the teacher",
            composition_accounting["original_labels_used_upstream_to_train_teacher"],
            "224",
            ("phase3b-data-composition",),
        ),
        (
            "distribution-design-labels",
            "Labeled records used to design the matched distribution",
            composition_accounting["original_labeled_records_used_to_design_distribution"],
            "224",
            ("phase3b-data-composition",),
        ),
    ]
    facts = [
        Phase5StoryFactV0_1(
            fact_id=fact_id,
            label=label,
            value=value,
            display_value=display,
            source_ids=list(source_ids),
        )
        for fact_id, label, value, display, source_ids in facts_data
    ]
    stages = [
        Phase5StoryStageV0_1(
            stage_id="capability-break",
            eyebrow="Capability break",
            title="A capable source does not make an untouched successor capable.",
            summary="The same frozen contract collapses when the architecture changes.",
            fact_ids=[
                "confirmatory-source-semantic",
                "confirmatory-target-semantic",
                "confirmatory-source-strict",
                "confirmatory-target-strict",
            ],
        ),
        Phase5StoryStageV0_1(
            stage_id="independent-distillation",
            eyebrow="Independent distillation",
            title="Strict filtering exposed a coverage failure.",
            summary="Only five archetypes survived the independent teacher pipeline.",
            fact_ids=[
                "independent-candidates",
                "independent-accepted",
                "independent-archetypes",
            ],
        ),
        Phase5StoryStageV0_1(
            stage_id="distribution-matching",
            eyebrow="Distribution matching",
            title="Matching the training distribution solved most acceptance failures.",
            summary="The remaining deficit localized to a reproducible policy blind spot.",
            fact_ids=["matched-accepted", "blindspot-accepted", "blindspot-mismatches"],
        ),
        Phase5StoryStageV0_1(
            stage_id="anchored-transfer",
            eyebrow="Anchored transfer",
            title="Ten original anchors completed a 224-example target curriculum.",
            summary="The hybrid condition preserves exact teacher labels and explicit provenance.",
            fact_ids=[
                "hybrid-teacher-labels",
                "hybrid-anchor-labels",
                "hybrid-total",
                "hybrid-tokens",
            ],
        ),
        Phase5StoryStageV0_1(
            stage_id="honest-accounting",
            eyebrow="Full accounting",
            title="Direct target labels are only one part of the method cost.",
            summary="Upstream teacher supervision and distribution-design labels remain visible.",
            fact_ids=["upstream-teacher-labels", "distribution-design-labels"],
        ),
    ]
    story_payload: dict[str, Any] = {
        "schema_version": "phase5-story-v0.1",
        "projection_id": PHASE5_PROJECTION_ID,
        "thesis": (
            "Model succession is an evidence problem: capabilities must be measured, "
            "transferred, stress-tested, and traced across architectures."
        ),
        "product_labels": [
            "Published experiment",
            "No live model execution",
            "Results reproduced from validated artifacts",
        ],
        "confirmatory_denominator": 64,
        "adversarial_denominator": 32,
        "stages": stages,
        "facts": facts,
        "prohibited_blended_score": True,
    }
    story_payload["content_sha256"] = _content(story_payload)
    story = Phase5StoryV0_1.model_validate(story_payload)

    sources = [
        _reference(
            "showcase-manifest",
            SHOWCASE_ROOT / "manifest.json",
            json_path="$",
            surface="cross_surface",
            content_hash=PHASE5_SHOWCASE_CONTENT_SHA256,
        ),
        _reference(
            "showcase-system-summaries",
            SHOWCASE_ROOT / "system-summaries.json",
            json_path="$.systems",
            surface="cross_surface",
            content_hash=None,
        ),
        _reference(
            "showcase-memo",
            SHOWCASE_ROOT / "memo.json",
            json_path="$",
            surface="cross_surface",
            content_hash=cast(str, showcase["memo.json"]["content_sha256"]),
        ),
        _reference(
            "showcase-memo-validation",
            SHOWCASE_ROOT / "memo-validation.json",
            json_path="$",
            surface="cross_surface",
            content_hash=cast(str, showcase["memo-validation.json"]["content_sha256"]),
        ),
        _reference(
            "showcase-migration-profiles",
            SHOWCASE_ROOT / "migration-profiles.json",
            json_path="$",
            surface="cross_surface",
            content_hash=cast(str, showcase["migration-profiles.json"]["content_sha256"]),
        ),
        _reference(
            "showcase-evidence",
            SHOWCASE_ROOT / "evidence.json",
            json_path="$",
            surface="cross_surface",
            content_hash=cast(str, showcase["evidence.json"]["content_sha256"]),
        ),
        _reference(
            "showcase-case-selection",
            SHOWCASE_ROOT / "representative-cases.json",
            json_path="$.cases",
            surface="adversarial",
            content_hash=cast(str, showcase["representative-cases.json"]["content_sha256"]),
        ),
        _reference(
            "showcase-analysis",
            SHOWCASE_ROOT / "analysis.json",
            json_path="$",
            surface="adversarial",
            content_hash=cast(str, showcase["analysis.json"]["content_sha256"]),
        ),
        _reference(
            "day3-independent-dataset",
            INDEPENDENT_DATASET,
            json_path="$",
            surface="not_applicable",
            content_hash=cast(str, independent["content_sha256"]),
        ),
        _reference(
            "day3-independent-accepted",
            independent_accepted_path,
            json_path="$[*]",
            surface="not_applicable",
            content_hash=cast(str, independent["accepted_artifact"]["content_sha256"]),
        ),
        _reference(
            "day3-matched-dataset",
            MATCHED_DATASET,
            json_path="$",
            surface="not_applicable",
            content_hash=cast(str, matched["content_sha256"]),
        ),
        _reference(
            "phase3b-blindspot-baseline",
            PHASE3B_BASELINE,
            json_path="$",
            surface="not_applicable",
            content_hash=cast(str, baseline["content_sha256"]),
        ),
        _reference(
            "phase3b-data-composition",
            PHASE3B_COMPOSITION,
            json_path="$.accounting",
            surface="confirmatory",
            content_hash=cast(str, composition["content_sha256"]),
        ),
        *case_sources,
    ]
    by_id: dict[str, Phase5SourceReferenceV0_1] = {}
    for source in sources:
        prior = by_id.get(source.source_id)
        if prior is not None and prior != source:
            raise ValueError(f"source ID collision: {source.source_id}")
        by_id[source.source_id] = source
    source_payload: dict[str, Any] = {
        "schema_version": "phase5-source-index-v0.1",
        "projection_id": PHASE5_PROJECTION_ID,
        "sources": [by_id[key] for key in sorted(by_id)],
    }
    source_payload["content_sha256"] = _content(source_payload)
    return story, Phase5SourceIndexV0_1.model_validate(source_payload)


def projection_files() -> dict[str, bytes]:
    showcase = verify_showcase()
    selection = cast(dict[str, Any], showcase["representative-cases.json"])
    analysis = cast(dict[str, Any], showcase["analysis.json"])
    if selection.get("analysis_sha256") != analysis.get("content_sha256"):
        raise ValueError("representative selection parent does not match showcase analysis")
    case_rows, case_sources = _phase4_case_details(selection, analysis)
    case_payload: dict[str, Any] = {
        "schema_version": "phase5-case-details-v0.1",
        "projection_id": PHASE5_PROJECTION_ID,
        "case_selection_sha256": selection["content_sha256"],
        "selection_parent_sha256": selection["analysis_sha256"],
        "cases": case_rows,
        "selected_count": sum(row.status == "SELECTED" for row in case_rows),
        "no_eligible_count": sum(row.status == "NO_ELIGIBLE_CASE" for row in case_rows),
    }
    case_payload["content_sha256"] = _content(case_payload)
    case_details = Phase5CaseDetailsV0_1.model_validate(case_payload)
    story, source_index = _story_and_sources(showcase, case_sources)
    return {
        "story.json": canonical_json_bytes(story) + b"\n",
        "case-details.json": canonical_json_bytes(case_details) + b"\n",
        "source-index.json": canonical_json_bytes(source_index) + b"\n",
    }


def _with_manifest(files: dict[str, bytes]) -> dict[str, bytes]:
    references: list[Phase5ProjectionFileV0_1] = []
    for relative_path, payload in sorted(files.items()):
        parsed = json.loads(payload)
        references.append(
            Phase5ProjectionFileV0_1(
                relative_path=relative_path,
                byte_sha256=sha256_bytes(payload),
                content_sha256=cast(str, parsed["content_sha256"]),
                bytes=len(payload),
            )
        )
    manifest_payload: dict[str, Any] = {
        "schema_version": "phase5-web-projection-manifest-v0.1",
        "projection_id": PHASE5_PROJECTION_ID,
        "status": "FROZEN",
        "source_showcase_content_sha256": PHASE5_SHOWCASE_CONTENT_SHA256,
        "phase4_decision_content_sha256": PHASE4_DECISION_CONTENT_SHA256,
        "files": references,
        "historical_artifacts_modified": False,
        "display_only": True,
    }
    manifest_payload["content_sha256"] = _content(manifest_payload)
    manifest = Phase5WebProjectionManifestV0_1.model_validate(manifest_payload)
    return {**files, "manifest.json": canonical_json_bytes(manifest) + b"\n"}


def build_web_projection(output_root: Path = PROJECTION_ROOT) -> Path:
    files = _with_manifest(projection_files())
    return write_atomic_bundle(output_root, PHASE5_PROJECTION_ID, files)


def verify_web_projection(
    bundle: Path = PROJECTION_ROOT / PHASE5_PROJECTION_ID,
) -> Phase5WebProjectionManifestV0_1:
    expected = _with_manifest(projection_files())
    if not bundle.is_dir():
        raise FileNotFoundError(bundle)
    actual_names = {str(path.relative_to(bundle)) for path in bundle.rglob("*") if path.is_file()}
    if actual_names != set(expected):
        raise ValueError("projection file set differs from deterministic regeneration")
    for relative_path, payload in expected.items():
        if (bundle / relative_path).read_bytes() != payload:
            raise ValueError(f"projection replay mismatch: {relative_path}")
    manifest = Phase5WebProjectionManifestV0_1.model_validate(json.loads(expected["manifest.json"]))
    with tempfile.TemporaryDirectory(prefix="inheritbench-phase5-verify-") as directory:
        temporary = Path(directory) / PHASE5_PROJECTION_ID
        temporary.mkdir()
        for relative_path, payload in expected.items():
            (temporary / relative_path).write_bytes(payload)
        if sha256_file(temporary / "manifest.json") != sha256_file(bundle / "manifest.json"):
            raise ValueError("projection manifest byte hash differs")
    return manifest
