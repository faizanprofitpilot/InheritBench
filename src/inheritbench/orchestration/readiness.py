"""Versioned task-neutral migration-readiness rules."""

from __future__ import annotations

from inheritbench.artifacts.hashing import content_sha256
from inheritbench.orchestration.schemas import ReadinessReport, SurfaceSummary
from inheritbench.strategies.schemas import SupervisionAccounting


def derive_readiness(
    *,
    run_id: str,
    rules: dict[str, object],
    source_gate: SurfaceSummary,
    target_baseline: SurfaceSummary,
    confirmatory: SurfaceSummary,
    adversarial: SurfaceSummary,
    supervision: SupervisionAccounting,
    selected_checkpoint_id: str,
    adapter_sha256: str,
) -> ReadinessReport:
    rule_version = str(rules.get("version", "unknown"))
    clean_rules = _mapping(rules, "clean")
    adversarial_rules = _mapping(rules, "adversarial")
    reasons: list[str] = []
    clean_blocked = _violations(confirmatory, clean_rules, "CLEAN")
    source_blocked = _violations(
        source_gate,
        _mapping(rules, "source_gate", fallback=clean_rules),
        "SOURCE_GATE",
    )
    adversarial_blocked = _violations(adversarial, adversarial_rules, "ADVERSARIAL")
    if source_blocked:
        status = "MIGRATION_BLOCKED"
        reasons.extend(source_blocked)
    elif clean_blocked:
        status = "MIGRATION_BLOCKED"
        reasons.extend(clean_blocked)
    elif adversarial_blocked:
        status = "CONDITIONAL_PASS"
        reasons.extend(adversarial_blocked)
    else:
        status = "PASS"
        reasons.append("ALL_DECLARED_READINESS_REQUIREMENTS_PASSED")
    payload = {
        "schema_version": "inheritbench.readiness-report.v0.2",
        "run_id": run_id,
        "rule_version": rule_version,
        "status": status,
        "reason_codes": reasons,
        "source_gate": source_gate,
        "target_baseline": target_baseline,
        "confirmatory": confirmatory,
        "adversarial": adversarial,
        "supervision": supervision,
        "selected_checkpoint_id": selected_checkpoint_id,
        "adapter_sha256": adapter_sha256,
    }
    payload["content_sha256"] = content_sha256(payload)
    return ReadinessReport.model_validate(payload, strict=True)


def _mapping(
    rules: dict[str, object],
    key: str,
    *,
    fallback: dict[str, object] | None = None,
) -> dict[str, object]:
    value = rules.get(key)
    if value is None and fallback is not None:
        return fallback
    if not isinstance(value, dict):
        raise ValueError(f"readiness rules lack {key}")
    return value


def _violations(
    summary: SurfaceSummary,
    rules: dict[str, object],
    prefix: str,
) -> list[str]:
    if summary.expected == 0 or summary.terminal != summary.expected:
        return [f"{prefix}_INCOMPLETE_EVIDENCE"]
    violations: list[str] = []
    semantic_rate = summary.semantic_correct / summary.expected
    strict_rate = summary.strict_valid / summary.expected
    if semantic_rate < _float_rule(rules, "minimum_semantic_rate"):
        violations.append(f"{prefix}_SEMANTIC_BELOW_THRESHOLD")
    if strict_rate < _float_rule(rules, "minimum_strict_rate"):
        violations.append(f"{prefix}_STRICT_BELOW_THRESHOLD")
    if summary.minimum_group_semantic_rate < _float_rule(rules, "minimum_group_semantic_rate"):
        violations.append(f"{prefix}_GROUP_FLOOR_BELOW_THRESHOLD")
    if summary.blocker_safety_findings > _int_rule(rules, "maximum_blocker_safety_findings"):
        violations.append(f"{prefix}_BLOCKER_SAFETY_FINDINGS")
    if summary.unknown_safety:
        violations.append(f"{prefix}_UNKNOWN_SAFETY")
    return violations


def _float_rule(rules: dict[str, object], key: str) -> float:
    value = rules.get(key, 0.0)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"readiness rule {key} must be numeric")
    return float(value)


def _int_rule(rules: dict[str, object], key: str) -> int:
    value = rules.get(key, 0)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"readiness rule {key} must be an integer")
    return value
