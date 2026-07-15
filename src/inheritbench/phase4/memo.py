"""Evidence-constrained deterministic and GPT-5.6 Sol memo generation."""

from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import (
    canonical_json,
    canonical_json_bytes,
    content_sha256,
    sha256_bytes,
)
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.phase4.config import load_experiment_config, load_memo_config, resolve
from inheritbench.phase4.schemas import (
    EvidenceReferenceV0_1,
    MemoClaimV0_1,
    MemoRecommendationV0_1,
    Phase4EvidencePackV0_1,
    Phase4MemoAttemptV0_1,
    Phase4MemoDraftV0_1,
    Phase4MemoV0_1,
    Phase4MemoValidationV0_1,
    Phase4MigrationAnalysisV0_1,
    Phase4SystemId,
)

_MEMO_EXCLUSIONS = {"generated_at", "content_sha256"}
_ATTEMPT_EXCLUSIONS = {"attempt_id", "created_at", "content_sha256"}
_VALIDATION_EXCLUSIONS = {"validation_id", "created_at", "content_sha256"}
_NUMBER = re.compile(r"(?<![A-Za-z0-9_.-])[-+]?\d+(?:\.\d+)?%?")
_CAUSAL = re.compile(
    r"\b(?:because|caused|causes|proves|proof|resulted\s+from|therefore\s+resulted)\b",
    re.IGNORECASE,
)


def build_fallback_memo(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    if list((root / "memos/fallback").glob("*/memo.json")):
        raise ValueError("deterministic fallback memo already exists")
    evidence_path, evidence = _single_evidence(root)
    del evidence_path
    _, profiles = _single_profiles(root)
    draft = _fallback_draft(profiles)
    memo = _materialize_memo(draft, "DETERMINISTIC_FALLBACK", evidence.content_sha256)
    markdown = render_markdown(memo, evidence)
    memo_id = f"phase4-fallback-memo-{memo.content_sha256[:16]}"
    return write_atomic_bundle(
        root / "memos/fallback",
        memo_id,
        {
            "memo.json": canonical_json_bytes(memo) + b"\n",
            "memo.md": markdown.encode("utf-8"),
        },
    )


def generate_gpt_memo(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    if list((root / "memos/gpt").glob("*/memo.json")):
        raise ValueError("validated GPT-5.6 Sol memo already exists")
    _, evidence = _single_evidence(root)
    _, profiles = _single_profiles(root)
    memo_config = load_memo_config(resolve(experiment_path, experiment.memo_config_path))
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return _write_attempt(
            root,
            attempt_number=1,
            request_kind="INITIAL",
            status="CREDENTIALS_MISSING",
            evidence_sha256=evidence.content_sha256,
            error_code="OPENAI_API_KEY_ABSENT",
        )
    client = _openai_client(key)
    prompt = _memo_prompt(evidence, profiles)
    previous_response_id: str | None = None
    next_kind: Literal["INITIAL", "REPAIR", "TRANSIENT_RETRY"] = "INITIAL"
    provider_failures = 0
    validation_issues: list[str] = []
    last_attempt: Path | None = None
    for attempt_number in (1, 2):
        try:
            request_previous_response_id = previous_response_id
            inputs = [
                {
                    "role": "system",
                    "content": (
                        "You are the InheritBench evidence analyst. Use only supplied evidence. "
                        "Return the required structured memo. Do not invent numbers or "
                        "causal claims."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt
                    if next_kind != "REPAIR"
                    else "Repair the prior memo using only these validator findings:\n"
                    + canonical_json(validation_issues),
                },
            ]
            kwargs: dict[str, Any] = {
                "model": memo_config.model,
                "input": inputs,
                "text_format": Phase4MemoDraftV0_1,
                "reasoning": {"effort": memo_config.reasoning_effort},
                "max_output_tokens": memo_config.maximum_output_tokens,
            }
            if previous_response_id is not None:
                kwargs["previous_response_id"] = previous_response_id
            response = client.responses.parse(**kwargs)
            previous_response_id = str(response.id)
            draft = response.output_parsed
            if not isinstance(draft, Phase4MemoDraftV0_1):
                raise ValueError("structured response did not produce a Phase4MemoDraftV0_1")
            memo = _materialize_memo(draft, "GPT_5_6_SOL", evidence.content_sha256)
            markdown = render_markdown(memo, evidence)
            findings = validate_memo_value(memo, evidence, profiles, markdown)
            status: Literal["COMPLETED", "INVALID_RESPONSE"] = (
                "COMPLETED" if not any(findings.values()) else "INVALID_RESPONSE"
            )
            last_attempt = _write_attempt(
                root,
                attempt_number=attempt_number,
                request_kind=next_kind,
                status=status,
                evidence_sha256=evidence.content_sha256,
                previous_response_id=request_previous_response_id,
                response_id=str(response.id),
                memo=memo,
                markdown=markdown,
                findings=findings,
            )
            if status == "COMPLETED":
                memo_id = f"phase4-gpt-memo-{memo.content_sha256[:16]}"
                return write_atomic_bundle(
                    root / "memos/gpt",
                    memo_id,
                    {
                        "memo.json": canonical_json_bytes(memo) + b"\n",
                        "memo.md": markdown.encode("utf-8"),
                    },
                )
            validation_issues = [item for values in findings.values() for item in values]
            next_kind = "REPAIR"
        except Exception as exc:
            category = _api_error_category(exc)
            if category == "CREDENTIALS":
                return _write_attempt(
                    root,
                    attempt_number=attempt_number,
                    request_kind=next_kind,
                    status="CREDENTIALS_MISSING",
                    evidence_sha256=evidence.content_sha256,
                    error_code=type(exc).__name__,
                )
            if category != "TRANSIENT":
                raise
            provider_failures += 1
            last_attempt = _write_attempt(
                root,
                attempt_number=attempt_number,
                request_kind=next_kind,
                status="PROVIDER_FAILURE",
                evidence_sha256=evidence.content_sha256,
                error_code=type(exc).__name__,
            )
            next_kind = "TRANSIENT_RETRY"
    if last_attempt is None or (provider_failures < 2 and not validation_issues):
        raise RuntimeError("bounded GPT memo attempt ended without terminal evidence")
    return last_attempt


def validate_memo(experiment_path: Path, memo_directory: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root)
    _, evidence = _single_evidence(root)
    _, profiles = _single_profiles(root)
    memo = Phase4MemoV0_1.model_validate_json(
        (memo_directory / "memo.json").read_bytes(), strict=True
    )
    markdown = render_markdown(memo, evidence)
    stored_markdown = (memo_directory / "memo.md").read_text(encoding="utf-8")
    if markdown != stored_markdown:
        raise ValueError("memo Markdown does not match deterministic rendering")
    findings = validate_memo_value(memo, evidence, profiles, markdown)
    status: Literal["PASSED", "FAILED"] = "PASSED" if not any(findings.values()) else "FAILED"
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase4-memo-validation-v0.1",
        "validation_id": "pending",
        "status": status,
        "memo_sha256": memo.content_sha256,
        "evidence_pack_sha256": evidence.content_sha256,
        "unknown_evidence_ids": findings["unknown_evidence_ids"],
        "unsupported_numeric_claims": findings["unsupported_numeric_claims"],
        "unsupported_comparisons": findings["unsupported_comparisons"],
        "prohibited_causal_claims": findings["prohibited_causal_claims"],
        "accounting_complete": not findings["missing_accounting"],
        "markdown_sha256": sha256_bytes(markdown.encode("utf-8")),
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_VALIDATION_EXCLUSIONS)
    validation_id = f"phase4-memo-validation-{identity[:16]}"
    value = Phase4MemoValidationV0_1.model_validate(
        {**payload, "validation_id": validation_id, "content_sha256": identity}, strict=True
    )
    path = write_atomic_bundle(
        root / "memo-validations",
        validation_id,
        {"validation.json": canonical_json_bytes(value) + b"\n"},
    )
    if status == "FAILED":
        raise ValueError(f"Phase 4 memo validation failed; evidence preserved at {path}")
    if memo.memo_kind == "GPT_5_6_SOL":
        memo_id = f"phase4-gpt-memo-{memo.content_sha256[:16]}"
        existing = sorted((root / "memos/gpt").glob("*/memo.json"))
        if existing:
            selected = Phase4MemoV0_1.model_validate_json(existing[0].read_bytes(), strict=True)
            if len(existing) != 1 or selected.content_sha256 != memo.content_sha256:
                raise ValueError("a different validated GPT-5.6 Sol memo already exists")
        else:
            write_atomic_bundle(
                root / "memos/gpt",
                memo_id,
                {
                    "memo.json": canonical_json_bytes(memo) + b"\n",
                    "memo.md": markdown.encode("utf-8"),
                },
            )
    return path


def validate_memo_value(
    memo: Phase4MemoV0_1,
    evidence: Phase4EvidencePackV0_1,
    profiles: Phase4MigrationAnalysisV0_1,
    markdown: str,
) -> dict[str, list[str]]:
    del markdown
    references = {item.evidence_id: item for item in evidence.references}
    unknown: list[str] = []
    unsupported_numbers: list[str] = []
    unsupported_comparisons: list[str] = []
    prohibited_causal: list[str] = []
    used: set[str] = set()
    claims = [
        *memo.executive_summary,
        *memo.transfer_assessment,
        *memo.adversarial_weaknesses,
        *memo.tradeoffs,
    ]
    for claim in claims:
        used.update(claim.evidence_ids)
        missing = [item for item in claim.evidence_ids if item not in references]
        unknown.extend(f"{claim.claim_id}:{item}" for item in missing)
        allowed = _allowed_numeric_strings(
            [references[item] for item in claim.evidence_ids if item in references]
        )
        for token in _NUMBER.findall(claim.statement):
            if token not in allowed:
                unsupported_numbers.append(f"{claim.claim_id}:{token}")
        if _CAUSAL.search(claim.statement):
            prohibited_causal.append(claim.claim_id)
        if claim.comparison != "NONE" and not _comparison_supported(claim, references):
            unsupported_comparisons.append(claim.claim_id)
    profile_map = {item.profile_id: item for item in profiles.recommendations}
    for recommendation in memo.recommendations:
        used.update(recommendation.evidence_ids)
        missing = [item for item in recommendation.evidence_ids if item not in references]
        unknown.extend(f"{recommendation.profile_id}:{item}" for item in missing)
        expected = profile_map[recommendation.profile_id].recommendation
        if recommendation.recommended_system != expected:
            unsupported_comparisons.append(f"recommendation:{recommendation.profile_id}")
        if _CAUSAL.search(recommendation.rationale):
            prohibited_causal.append(f"recommendation:{recommendation.profile_id}")
    required_accounting = {
        "direct_original_labels:target_hybrid_anchored_distillation_10",
        "upstream_original_labels:target_hybrid_anchored_distillation_10",
        "hybrid_accounting:teacher_generation_processed_tokens",
        "hybrid_accounting:source_teacher_training_tokens",
        "hybrid_accounting:original_anchor_labels_used_by_target",
        "hybrid_accounting:synthetic_labels_used_by_target",
    }
    missing_accounting = sorted(required_accounting - used)
    return {
        "unknown_evidence_ids": sorted(set(unknown)),
        "unsupported_numeric_claims": sorted(set(unsupported_numbers)),
        "unsupported_comparisons": sorted(set(unsupported_comparisons)),
        "prohibited_causal_claims": sorted(set(prohibited_causal)),
        "missing_accounting": missing_accounting,
    }


def render_markdown(memo: Phase4MemoV0_1, evidence: Phase4EvidencePackV0_1) -> str:
    references = {item.evidence_id: item for item in evidence.references}
    lines = [f"# {memo.title}", ""]
    sections: list[tuple[str, list[MemoClaimV0_1]]] = [
        ("Executive Summary", memo.executive_summary),
        ("Transfer Assessment", memo.transfer_assessment),
        ("Adversarial Weaknesses", memo.adversarial_weaknesses),
        ("Tradeoffs", memo.tradeoffs),
    ]
    for title, claims in sections:
        lines.extend([f"## {title}", ""])
        for claim in claims:
            citations = ", ".join(f"`{item}`" for item in claim.evidence_ids)
            lines.append(f"- {claim.statement} Evidence: {citations}.")
        lines.append("")
    lines.extend(["## Migration Recommendations", ""])
    for recommendation in memo.recommendations:
        lines.append(
            f"- `{recommendation.profile_id}` → `{recommendation.recommended_system}`: "
            f"{recommendation.rationale} Evidence: "
            + ", ".join(f"`{item}`" for item in recommendation.evidence_ids)
            + "."
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in memo.limitations)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {item}" for item in memo.next_steps)
    lines.extend(["", "## Evidence Values", ""])
    used = sorted(
        {
            evidence_id
            for claim in [
                *memo.executive_summary,
                *memo.transfer_assessment,
                *memo.adversarial_weaknesses,
                *memo.tradeoffs,
            ]
            for evidence_id in claim.evidence_ids
        }
        | {item for recommendation in memo.recommendations for item in recommendation.evidence_ids}
    )
    for evidence_id in used:
        reference = references.get(evidence_id)
        if reference is not None:
            lines.append(
                f"- `{evidence_id}` = `{canonical_json(reference.value)}` "
                f"from `{reference.artifact_path}` `{reference.json_path}`"
            )
    return "\n".join(lines).rstrip() + "\n"


def _fallback_draft(profiles: Phase4MigrationAnalysisV0_1) -> Phase4MemoDraftV0_1:
    targets = [
        "target_untouched",
        "target_full_retrain",
        "target_limited_retrain_10pct",
        "target_hybrid_anchored_distillation_10",
    ]
    recommendations = [
        MemoRecommendationV0_1(
            profile_id=item.profile_id,
            recommended_system=item.recommendation,
            rationale=(
                "The frozen profile ordering determines this result without a weighted score."
            ),
            evidence_ids=[f"migration_profile:{item.profile_id}"],
        )
        for item in profiles.recommendations
    ]
    return Phase4MemoDraftV0_1(
        title="InheritBench Adversarial Transfer Evidence Memo",
        executive_summary=[
            MemoClaimV0_1(
                claim_id="executive-target-separation",
                statement=(
                    "The confirmatory evidence separates viable adapted targets from the "
                    "untouched target."
                ),
                evidence_ids=[f"confirmatory_strict:{item}" for item in targets],
                comparison="NONE",
                compared_systems=[],
            )
        ],
        transfer_assessment=[
            MemoClaimV0_1(
                claim_id="transfer-confirmatory-order",
                statement=(
                    "The anchored hybrid target leads the confirmatory semantic comparison "
                    "among target candidates."
                ),
                evidence_ids=[f"confirmatory_semantic:{item}" for item in targets],
                comparison="BEST",
                compared_systems=[
                    "target_hybrid_anchored_distillation_10",
                    "target_full_retrain",
                    "target_limited_retrain_10pct",
                    "target_untouched",
                ],
            )
        ],
        adversarial_weaknesses=[
            MemoClaimV0_1(
                claim_id="adversarial-visible-failures",
                statement=(
                    "Adversarial evaluation exposes system-specific contract and safety "
                    "failures that remain visible in the evidence matrices."
                ),
                evidence_ids=[f"adversarial_semantic:{item}" for item in targets],
                comparison="NONE",
                compared_systems=[],
            )
        ],
        recommendations=recommendations,
        tradeoffs=[
            MemoClaimV0_1(
                claim_id="hybrid-accounting",
                statement=(
                    "The hybrid condition uses both direct anchors and teacher labels and "
                    "also inherits upstream teacher cost."
                ),
                evidence_ids=[
                    "direct_original_labels:target_hybrid_anchored_distillation_10",
                    "upstream_original_labels:target_hybrid_anchored_distillation_10",
                    "hybrid_accounting:teacher_generation_processed_tokens",
                    "hybrid_accounting:source_teacher_training_tokens",
                    "hybrid_accounting:original_anchor_labels_used_by_target",
                    "hybrid_accounting:synthetic_labels_used_by_target",
                ],
                comparison="NONE",
                compared_systems=[],
            )
        ],
        limitations=[
            "Results apply only to the pinned Qwen and OLMo revisions, OpsRoute v0.1.0, "
            "and seed 20260714.",
            "One seed establishes replayability but does not establish statistical significance.",
            "The adversarial evaluation was not used for tuning or method selection.",
        ],
        next_steps=[
            "Use the validated evidence bundle as the input contract for Phase 5 without "
            "starting new scientific variants.",
            "Preserve the exact evaluation surfaces when presenting migration recommendations.",
        ],
    )


def _materialize_memo(
    draft: Phase4MemoDraftV0_1,
    kind: Literal["GPT_5_6_SOL", "DETERMINISTIC_FALLBACK"],
    evidence_sha256: str,
) -> Phase4MemoV0_1:
    generated_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase4-memo-v0.1",
        "memo_kind": kind,
        **draft.model_dump(mode="json"),
        "evidence_pack_sha256": evidence_sha256,
        "generated_at": generated_at,
    }
    return Phase4MemoV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_MEMO_EXCLUSIONS)},
        strict=True,
    )


def _memo_prompt(evidence: Phase4EvidencePackV0_1, profiles: Phase4MigrationAnalysisV0_1) -> str:
    return "\n".join(
        [
            "Create the final InheritBench evidence memo from the following canonical JSON.",
            "Cite evidence IDs on every claim. Put systems in structured fields rather than prose.",
            "Do not use causal language. Include all six frozen migration profiles.",
            "Include hybrid direct labels, upstream labels, teacher-generation tokens, "
            "source-teacher tokens, anchor labels, and synthetic labels in the tradeoff evidence.",
            "EVIDENCE_PACK:",
            canonical_json(evidence),
            "MIGRATION_PROFILES:",
            canonical_json(profiles),
        ]
    )


def _write_attempt(
    root: Path,
    *,
    attempt_number: Literal[1, 2],
    request_kind: Literal["INITIAL", "REPAIR", "TRANSIENT_RETRY"],
    status: Literal["COMPLETED", "PROVIDER_FAILURE", "INVALID_RESPONSE", "CREDENTIALS_MISSING"],
    evidence_sha256: str,
    error_code: str | None = None,
    previous_response_id: str | None = None,
    response_id: str | None = None,
    memo: Phase4MemoV0_1 | None = None,
    markdown: str | None = None,
    findings: dict[str, list[str]] | None = None,
) -> Path:
    created_at = datetime.now(UTC)
    attempt_id = f"phase4-memo-attempt-{uuid.uuid4().hex[:16]}"
    payload = {
        "schema_version": "phase4-memo-attempt-v0.1",
        "attempt_id": attempt_id,
        "attempt_number": attempt_number,
        "request_kind": request_kind,
        "model": "gpt-5.6-sol",
        "previous_response_id": previous_response_id,
        "response_id": response_id,
        "status": status,
        "error_code": error_code,
        "evidence_pack_sha256": evidence_sha256,
        "memo_sha256": memo.content_sha256 if memo else None,
        "created_at": created_at,
    }
    attempt = Phase4MemoAttemptV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_ATTEMPT_EXCLUSIONS)},
        strict=True,
    )
    files = {"attempt.json": canonical_json_bytes(attempt) + b"\n"}
    if memo is not None and markdown is not None:
        files["memo.json"] = canonical_json_bytes(memo) + b"\n"
        files["memo.md"] = markdown.encode("utf-8")
        files["validator_findings.json"] = canonical_json_bytes(findings or {}) + b"\n"
    return write_atomic_bundle(root / "memo-attempts", attempt_id, files)


def _allowed_numeric_strings(references: list[EvidenceReferenceV0_1]) -> set[str]:
    result: set[str] = set()
    for reference in references:
        values = [reference.value, reference.numerator, reference.denominator]
        for value in values:
            if isinstance(value, bool) or value is None or not isinstance(value, int | float):
                continue
            result.add(str(value))
            if isinstance(value, float):
                result.add(f"{value:.2f}")
                result.add(f"{value:.3f}")
                if 0 <= value <= 1:
                    result.add(f"{value * 100:.1f}%")
                    result.add(f"{value * 100:.2f}%")
                    result.add(f"{value * 100:.3f}%")
    return result


def _comparison_supported(
    claim: MemoClaimV0_1, references: dict[str, EvidenceReferenceV0_1]
) -> bool:
    if len(claim.compared_systems) < 2:
        return False
    candidates: dict[str, dict[Phase4SystemId, float]] = {}
    for evidence_id in claim.evidence_ids:
        reference = references.get(evidence_id)
        if (
            reference is None
            or reference.system_id is None
            or not isinstance(reference.value, int | float)
        ):
            continue
        prefix = evidence_id.rsplit(":", 1)[0]
        candidates.setdefault(prefix, {})[reference.system_id] = float(reference.value)
    for values in candidates.values():
        if not all(system in values for system in claim.compared_systems):
            continue
        ordered = [values[system] for system in claim.compared_systems]
        if claim.comparison == "HIGHER" and (
            ordered[0] > max(ordered[1:]) or min(ordered[:-1]) > ordered[-1]
        ):
            return True
        if claim.comparison == "LOWER" and (
            ordered[0] < min(ordered[1:]) or max(ordered[:-1]) < ordered[-1]
        ):
            return True
        if claim.comparison == "BEST" and ordered[0] == max(ordered):
            return True
        if claim.comparison == "WORST" and ordered[0] == min(ordered):
            return True
        if claim.comparison == "TIE" and len(set(ordered)) == 1:
            return True
    return False


def _openai_client(api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "install the locked analyst extra before generating the GPT memo"
        ) from exc
    return OpenAI(api_key=api_key)


def _api_error_category(error: Exception) -> str:
    name = type(error).__name__
    if name in {"AuthenticationError", "PermissionDeniedError"}:
        return "CREDENTIALS"
    if name in {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
    }:
        return "TRANSIENT"
    return "IMPLEMENTATION"


def _single_evidence(root: Path) -> tuple[Path, Phase4EvidencePackV0_1]:
    matches = sorted((root / "evidence-packs").glob("*/evidence.json"))
    if len(matches) != 1:
        raise ValueError("expected exactly one validated Phase 4 evidence pack")
    return matches[0].parent, Phase4EvidencePackV0_1.model_validate_json(
        matches[0].read_bytes(), strict=True
    )


def _single_profiles(root: Path) -> tuple[Path, Phase4MigrationAnalysisV0_1]:
    matches = sorted((root / "migration-profiles").glob("*/profiles.json"))
    if len(matches) != 1:
        raise ValueError("expected exactly one Phase 4 migration analysis")
    return matches[0].parent, Phase4MigrationAnalysisV0_1.model_validate_json(
        matches[0].read_bytes(), strict=True
    )
