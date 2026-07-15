"""Frozen train distribution, matched pools, and zero-overlap audits."""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    content_sha256,
    sha256_file,
    sha256_text,
)
from inheritbench.artifacts.store import artifact_reference, write_atomic_bundle
from inheritbench.config import ScenarioFamily, load_model_config, load_task_config
from inheritbench.data.opsroute.generate import (
    REFUND_ARCHETYPES,
    SUBSCRIPTION_ARCHETYPES,
    _refund_request,
    _subscription_request,
)
from inheritbench.data.opsroute.policies import resolve_refund, resolve_subscription
from inheritbench.data.opsroute.schemas import (
    EvaluationMetadata,
    OpsRouteExample,
    OpsRouteInput,
    RefundFacts,
    SubscriptionFacts,
)
from inheritbench.day3.pool import semantic_leakage_sha256
from inheritbench.day3_matched.baseline import find_baseline
from inheritbench.day3_matched.config import (
    load_experiment_config,
    load_pool_config,
    resolve,
)
from inheritbench.day3_matched.schemas import (
    CorpusDigestV0_1,
    DistributionFingerprintV0_1,
    DistributionMatchAuditV0_1,
    DistributionStratumV0_1,
    IntegerBucket,
    MatchedCandidateInputV0_1,
    MatchedLeakageAuditV0_1,
    MatchedOracleRecordV0_1,
    MatchedPoolConfigV0_1,
    MatchedPoolManifestV0_1,
)
from inheritbench.evaluation.contracts import StrictJsonScalar
from inheritbench.models.prompts import render_prompt

_FAMILIES: tuple[tuple[ScenarioFamily, tuple[str, ...]], ...] = (
    ("refund_policy_routing", REFUND_ARCHETYPES),
    ("subscription_cancellation_retention", SUBSCRIPTION_ARCHETYPES),
)
_FINGERPRINT_EXCLUSIONS = {"fingerprint_id", "created_at", "content_sha256"}
_AUDIT_EXCLUSIONS = {"audit_id", "created_at", "content_sha256"}
_POOL_EXCLUSIONS = {"pool_id", "created_at", "content_sha256"}


def freeze_fingerprint(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    find_baseline(experiment_path)
    pool_config = load_pool_config(resolve(experiment_path, experiment.pool_config_path))
    source = load_model_config(resolve(experiment_path, experiment.source_model_config_path))
    from transformers import AutoTokenizer

    auto_tokenizer: Any = AutoTokenizer
    tokenizer: Any = auto_tokenizer.from_pretrained(
        _local_snapshot(source.tokenizer_id, source.tokenizer_revision),
        trust_remote_code=False,
        local_files_only=True,
    )
    fingerprint = build_fingerprint(experiment_path, pool_config, tokenizer)
    root = resolve(experiment_path, experiment.artifact_root) / "fingerprints"
    destination = root / fingerprint.fingerprint_id
    if destination.exists():
        stored = DistributionFingerprintV0_1.model_validate_json(
            (destination / "fingerprint.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != fingerprint.content_sha256:
            raise ValueError("existing train-distribution fingerprint differs")
        return destination
    return write_atomic_bundle(
        root,
        fingerprint.fingerprint_id,
        {"fingerprint.json": canonical_json_bytes(fingerprint) + b"\n"},
    )


def build_fingerprint(
    experiment_path: Path, pool_config: MatchedPoolConfigV0_1, tokenizer: Any
) -> DistributionFingerprintV0_1:
    experiment = load_experiment_config(experiment_path)
    dataset = resolve(experiment_path, experiment.dataset_directory)
    train_path = dataset / "train.jsonl"
    train = _read_jsonl(train_path, OpsRouteExample)
    if len(train) != 224 or any(item.split != "train" for item in train):
        raise ValueError("matched fingerprint requires exactly 224 frozen train records")
    dataset_manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    source = load_model_config(resolve(experiment_path, experiment.source_model_config_path))
    grouped: dict[str, tuple[dict[str, Any], int]] = {}
    marginals: dict[str, Counter[str]] = defaultdict(Counter)
    forbidden = Counter[str]()
    for example in sorted(train, key=lambda item: item.example_id):
        prompt_tokens = _prompt_tokens(tokenizer, example)
        stratum_payload = _stratum_payload(example, prompt_tokens, pool_config)
        stratum_sha256 = content_sha256(stratum_payload)
        current = grouped.get(stratum_sha256)
        grouped[stratum_sha256] = (stratum_payload, 1 if current is None else current[1] + 1)
        _update_marginals(marginals, example, stratum_payload)
        for field, values in pool_config.forbidden_boundary_values.items():
            if example.input.context.get(field) in values:
                forbidden[field] += 1
    if any(forbidden.values()):
        raise ValueError(
            f"frozen train data unexpectedly contains forbidden boundaries: {forbidden}"
        )
    strata = [
        DistributionStratumV0_1.model_validate(
            {"stratum_sha256": stratum_sha256, **payload, "train_count": count},
            strict=True,
        )
        for stratum_sha256, (payload, count) in sorted(grouped.items())
    ]
    _validate_strata(strata)
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "day3-train-distribution-v0.1",
        "fingerprint_id": "pending",
        "status": "FROZEN",
        "train_records": 224,
        "dataset_sha256": dataset_manifest["dataset_sha256"],
        "train_byte_sha256": sha256_file(train_path),
        "task_config_sha256": content_sha256(
            load_task_config(resolve(experiment_path, experiment.task_config_path))
        ),
        "generator_source_sha256": sha256_file(
            Path(__file__).parents[1] / "data" / "opsroute" / "generate.py"
        ),
        "tokenizer_id": source.tokenizer_id,
        "tokenizer_revision": source.tokenizer_revision,
        "prompt_template_version": "0.1.0",
        "prompt_bucket_width": pool_config.prompt_bucket_width,
        "strata": [item.model_dump(mode="json") for item in strata],
        "marginal_histograms": {
            name: dict(sorted(values.items())) for name, values in sorted(marginals.items())
        },
        "forbidden_boundary_counts": {
            field: forbidden[field] for field in sorted(pool_config.forbidden_boundary_values)
        },
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_FINGERPRINT_EXCLUSIONS)
    payload["fingerprint_id"] = f"day3-matched-fingerprint-{identity[:16]}"
    return DistributionFingerprintV0_1.model_validate(
        {
            **payload,
            "content_sha256": content_sha256(payload, excluded_keys=_FINGERPRINT_EXCLUSIONS),
        },
        strict=True,
    )


def find_fingerprint(experiment_path: Path) -> tuple[Path, DistributionFingerprintV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "fingerprints"
    matches = sorted(root.glob("day3-matched-fingerprint-*"))
    if len(matches) != 1:
        raise ValueError(f"expected one matched fingerprint, found {len(matches)}")
    value = DistributionFingerprintV0_1.model_validate_json(
        (matches[0] / "fingerprint.json").read_bytes(), strict=True
    )
    return matches[0], value


def freeze_pool(experiment_path: Path, phase: Literal["initial", "expansion"] = "initial") -> Path:
    experiment = load_experiment_config(experiment_path)
    pool_config = load_pool_config(resolve(experiment_path, experiment.pool_config_path))
    _, fingerprint = find_fingerprint(experiment_path)
    if phase == "expansion":
        find_pool(experiment_path, "initial")
    source = load_model_config(resolve(experiment_path, experiment.source_model_config_path))
    from transformers import AutoTokenizer

    auto_tokenizer: Any = AutoTokenizer
    tokenizer: Any = auto_tokenizer.from_pretrained(
        _local_snapshot(source.tokenizer_id, source.tokenizer_revision),
        trust_remote_code=False,
        local_files_only=True,
    )
    target_per_archetype = (
        pool_config.initial_per_archetype
        if phase == "initial"
        else pool_config.expansion_per_archetype
    )
    excluded, corpora = materialize_excluded_corpora(experiment_path, phase)
    collision_sets = _collision_sets(excluded)
    candidates: list[MatchedCandidateInputV0_1] = []
    oracles: list[MatchedOracleRecordV0_1] = []
    collision_rejections = 0
    strata = {item.stratum_sha256: item for item in fingerprint.strata}
    source_examples = _source_examples_by_stratum(experiment_path, pool_config, tokenizer)
    assignments = apportioned_assignments(fingerprint, phase, target_per_archetype)
    for family, archetypes in _FAMILIES:
        for archetype in archetypes:
            assigned = assignments[(family, archetype)]
            for slot, stratum_sha256 in enumerate(assigned):
                stratum = strata[stratum_sha256]
                representative = source_examples[stratum_sha256][
                    slot % len(source_examples[stratum_sha256])
                ]
                for attempt in range(pool_config.maximum_collision_attempts):
                    try:
                        candidate, oracle = _candidate(
                            experiment_path,
                            pool_config,
                            tokenizer,
                            phase,
                            family,
                            archetype,
                            slot,
                            attempt,
                            stratum,
                            representative,
                        )
                    except _CandidateCollision:
                        collision_rejections += 1
                        continue
                    if _collides(candidate, collision_sets):
                        collision_rejections += 1
                        continue
                    candidates.append(candidate)
                    oracles.append(oracle)
                    _add_collision_values(candidate, collision_sets)
                    break
                else:
                    raise ValueError(
                        "matched candidate collision retry limit exhausted for "
                        f"{family}:{archetype}:{slot}"
                    )
    candidates.sort(key=lambda item: item.candidate_id)
    oracles.sort(key=lambda item: item.candidate_id)
    expected_count = target_per_archetype * 16
    if len(candidates) != expected_count or len(oracles) != expected_count:
        raise ValueError("matched pool generation produced the wrong candidate count")
    distribution = build_distribution_audit(fingerprint, candidates, phase, target_per_archetype)
    leakage = build_leakage_audit(
        candidates,
        excluded,
        corpora,
        phase,
        collision_rejections,
    )
    if distribution.status != "PASS" or leakage.status != "PASS":
        raise ValueError("matched pool failed its mandatory distribution or leakage audit")
    audit_identity = content_sha256(
        {"distribution": distribution.content_sha256, "leakage": leakage.content_sha256}
    )
    audit_id = f"day3-matched-audits-{phase}-{audit_identity[:16]}"
    audit_root = resolve(experiment_path, experiment.artifact_root) / "audits"
    audit_destination = audit_root / audit_id
    if not audit_destination.exists():
        write_atomic_bundle(
            audit_root,
            audit_id,
            {
                "distribution.json": canonical_json_bytes(distribution) + b"\n",
                "leakage.json": canonical_json_bytes(leakage) + b"\n",
            },
        )
    candidate_bytes = canonical_jsonl_bytes(candidates, id_key="candidate_id")
    oracle_bytes = canonical_jsonl_bytes(oracles, id_key="candidate_id")
    created_at = datetime.now(UTC)
    identity = content_sha256(
        {
            "phase": phase,
            "fingerprint": fingerprint.content_sha256,
            "candidate_hashes": [item.record_sha256 for item in candidates],
            "oracle_hashes": [item.content_sha256 for item in oracles],
            "distribution": distribution.content_sha256,
            "leakage": leakage.content_sha256,
        }
    )
    pool_id = f"day3-matched-pool-{phase}-{identity[:16]}"
    payload = {
        "schema_version": "day3-matched-pool-v0.1",
        "pool_id": pool_id,
        "attempt_id": "distribution_matched_attempt",
        "phase": phase,
        "status": "FROZEN",
        "seed": 20260714,
        "generator_version": pool_config.generator_version,
        "candidate_count": len(candidates),
        "per_archetype": target_per_archetype,
        "fingerprint_sha256": fingerprint.content_sha256,
        "distribution_audit_sha256": distribution.content_sha256,
        "leakage_audit_sha256": leakage.content_sha256,
        "candidate_artifact": artifact_reference(
            "candidate_inputs.jsonl",
            candidate_bytes,
            content_sha256=content_sha256(candidates),
        ).model_dump(mode="json"),
        "oracle_artifact": artifact_reference(
            "candidate_oracle.jsonl",
            oracle_bytes,
            content_sha256=content_sha256(oracles),
        ).model_dump(mode="json"),
        "created_at": created_at,
    }
    manifest = MatchedPoolManifestV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_POOL_EXCLUSIONS)},
        strict=True,
    )
    root = resolve(experiment_path, experiment.artifact_root) / "pools"
    destination = root / pool_id
    if destination.exists():
        stored = MatchedPoolManifestV0_1.model_validate_json(
            (destination / "manifest.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != manifest.content_sha256:
            raise ValueError("existing matched pool differs")
        return destination
    return write_atomic_bundle(
        root,
        pool_id,
        {
            "candidate_inputs.jsonl": candidate_bytes,
            "candidate_oracle.jsonl": oracle_bytes,
            "distribution_audit.json": canonical_json_bytes(distribution) + b"\n",
            "leakage_audit.json": canonical_json_bytes(leakage) + b"\n",
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )


def audit_distribution(experiment_path: Path, phase: Literal["initial", "expansion"]) -> Path:
    pool = find_pool(experiment_path, phase)
    manifest = load_pool_manifest(pool)
    _, fingerprint = find_fingerprint(experiment_path)
    candidates = load_candidates(pool)
    rebuilt = build_distribution_audit(fingerprint, candidates, phase, manifest.per_archetype)
    stored = DistributionMatchAuditV0_1.model_validate_json(
        (pool / "distribution_audit.json").read_bytes(), strict=True
    )
    if rebuilt.content_sha256 != stored.content_sha256 or stored.status != "PASS":
        raise ValueError("matched distribution audit replay mismatch")
    return pool


def audit_leakage(experiment_path: Path, phase: Literal["initial", "expansion"]) -> Path:
    pool = find_pool(experiment_path, phase)
    candidates = load_candidates(pool)
    excluded, corpora = materialize_excluded_corpora(experiment_path, phase)
    stored = MatchedLeakageAuditV0_1.model_validate_json(
        (pool / "leakage_audit.json").read_bytes(), strict=True
    )
    rebuilt = build_leakage_audit(
        candidates,
        excluded,
        corpora,
        phase,
        stored.collision_rejections,
    )
    if rebuilt.content_sha256 != stored.content_sha256 or stored.status != "PASS":
        raise ValueError("matched leakage audit replay mismatch")
    return pool


def find_pool(experiment_path: Path, phase: Literal["initial", "expansion"]) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "pools"
    matches = sorted(root.glob(f"day3-matched-pool-{phase}-*"))
    if len(matches) != 1:
        raise ValueError(f"expected one matched {phase} pool, found {len(matches)}")
    return matches[0]


def load_pool_manifest(pool: Path) -> MatchedPoolManifestV0_1:
    return MatchedPoolManifestV0_1.model_validate_json(
        (pool / "manifest.json").read_bytes(), strict=True
    )


def load_candidates(pool: Path) -> list[MatchedCandidateInputV0_1]:
    return _read_jsonl(pool / "candidate_inputs.jsonl", MatchedCandidateInputV0_1)


def load_oracles(pool: Path) -> list[MatchedOracleRecordV0_1]:
    return _read_jsonl(pool / "candidate_oracle.jsonl", MatchedOracleRecordV0_1)


def apportioned_assignments(
    fingerprint: DistributionFingerprintV0_1,
    phase: Literal["initial", "expansion"],
    target_per_archetype: int,
) -> dict[tuple[ScenarioFamily, str], list[str]]:
    grouped: dict[tuple[ScenarioFamily, str], list[DistributionStratumV0_1]] = defaultdict(list)
    for stratum in fingerprint.strata:
        grouped[(stratum.scenario_family, stratum.archetype)].append(stratum)
    result: dict[tuple[ScenarioFamily, str], list[str]] = {}
    for key, values in sorted(grouped.items()):
        total = sum(item.train_count for item in values)
        if total != 14:
            raise ValueError(f"train stratum total is not 14 for {key}: {total}")
        floors = {
            item.stratum_sha256: target_per_archetype * item.train_count // total for item in values
        }
        remaining = target_per_archetype - sum(floors.values())
        ranked = sorted(
            values,
            key=lambda item: (
                -((target_per_archetype * item.train_count) % total),
                sha256_text(
                    "20260714:day3-matched-strata-v0.1:"
                    f"{phase}:{key[0]}:{key[1]}:{item.stratum_sha256}"
                ),
            ),
        )
        for item in ranked[:remaining]:
            floors[item.stratum_sha256] += 1
        assigned = [
            item.stratum_sha256
            for item in sorted(values, key=lambda value: value.stratum_sha256)
            for _ in range(floors[item.stratum_sha256])
        ]
        if len(assigned) != target_per_archetype:
            raise ValueError(f"Hamilton apportionment failed for {key}")
        result[key] = assigned
    if len(result) != 16:
        raise ValueError("fingerprint does not contain all 16 archetypes")
    return result


def build_distribution_audit(
    fingerprint: DistributionFingerprintV0_1,
    candidates: list[MatchedCandidateInputV0_1],
    phase: Literal["initial", "expansion"],
    target_per_archetype: int,
) -> DistributionMatchAuditV0_1:
    assignments = apportioned_assignments(fingerprint, phase, target_per_archetype)
    expected = Counter(item for values in assignments.values() for item in values)
    observed = Counter(item.source_stratum_sha256 for item in candidates)
    expected_marginals = _candidate_marginals_from_assignments(fingerprint, expected)
    observed_marginals = _candidate_marginals(candidates)
    support_violations: list[str] = []
    known_strata = {item.stratum_sha256 for item in fingerprint.strata}
    for candidate in candidates:
        if candidate.source_stratum_sha256 not in known_strata:
            support_violations.append(f"unknown stratum:{candidate.candidate_id}")
    prompt_violations = (
        []
        if expected_marginals.get("prompt_bucket") == observed_marginals.get("prompt_bucket")
        else ["prompt bucket histogram mismatch"]
    )
    boundary_violations = [
        f"{item.candidate_id}:{field}={item.input.context.get(field)}"
        for item in candidates
        for field, forbidden in {
            "amount_minor": {4999, 5000, 5001},
            "payment_age_days": {30, 31},
            "balance_minor": {9999, 10000, 10001},
        }.items()
        if item.input.context.get(field) in forbidden
    ]
    status = (
        "PASS"
        if expected == observed
        and expected_marginals == observed_marginals
        and not support_violations
        and not prompt_violations
        and not boundary_violations
        else "FAIL"
    )
    created_at = datetime.now(UTC)
    identity = content_sha256(
        {"fingerprint": fingerprint.content_sha256, "phase": phase, "observed": observed}
    )
    payload = {
        "schema_version": "day3-distribution-audit-v0.1",
        "audit_id": f"day3-matched-distribution-audit-{phase}-{identity[:16]}",
        "phase": phase,
        "status": status,
        "fingerprint_sha256": fingerprint.content_sha256,
        "candidate_count": len(candidates),
        "expected_strata": dict(sorted(expected.items())),
        "observed_strata": dict(sorted(observed.items())),
        "expected_marginals": expected_marginals,
        "observed_marginals": observed_marginals,
        "support_violations": sorted(support_violations),
        "prompt_bucket_violations": sorted(prompt_violations),
        "boundary_violations": sorted(boundary_violations),
        "created_at": created_at,
    }
    return DistributionMatchAuditV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_AUDIT_EXCLUSIONS)},
        strict=True,
    )


def build_leakage_audit(
    candidates: list[MatchedCandidateInputV0_1],
    excluded: list[tuple[str, str, str, str, str]],
    corpora: list[CorpusDigestV0_1],
    phase: Literal["initial", "expansion"],
    collision_rejections: int,
) -> MatchedLeakageAuditV0_1:
    excluded_sets = (
        [set(values) for values in zip(*excluded, strict=True)]
        if excluded
        else [
            set(),
            set(),
            set(),
            set(),
            set(),
        ]
    )
    candidate_columns = [
        [item.candidate_id for item in candidates],
        [item.surface_sha256 for item in candidates],
        [item.input_content_sha256 for item in candidates],
        [item.record_sha256 for item in candidates],
        [item.semantic_leakage_sha256 for item in candidates],
    ]
    collisions = [
        sorted(set(values) & excluded_values)
        for values, excluded_values in zip(candidate_columns, excluded_sets, strict=True)
    ]
    duplicates = [
        sorted(value for value, count in Counter(values).items() if count > 1)
        for values in candidate_columns
    ]
    combined = [
        sorted(set(first + second)) for first, second in zip(collisions, duplicates, strict=True)
    ]
    zero_overlap = not any(combined)
    created_at = datetime.now(UTC)
    identity = content_sha256(
        {
            "phase": phase,
            "candidates": [item.record_sha256 for item in candidates],
            "corpora": corpora,
        }
    )
    payload = {
        "schema_version": "day3-matched-leakage-audit-v0.1",
        "audit_id": f"day3-matched-leakage-audit-{phase}-{identity[:16]}",
        "signature_version": "day3-semantic-leakage-v0.1",
        "phase": phase,
        "status": "PASS" if zero_overlap else "FAIL",
        "compared_corpora": [item.model_dump(mode="json") for item in corpora],
        "candidate_count": len(candidates),
        "unique_id_count": len(set(candidate_columns[0])),
        "unique_surface_count": len(set(candidate_columns[1])),
        "unique_input_content_count": len(set(candidate_columns[2])),
        "unique_record_count": len(set(candidate_columns[3])),
        "unique_semantic_count": len(set(candidate_columns[4])),
        "id_collisions": combined[0],
        "surface_collisions": combined[1],
        "input_content_collisions": combined[2],
        "record_collisions": combined[3],
        "semantic_collisions": combined[4],
        "collision_rejections": collision_rejections,
        "zero_overlap": zero_overlap,
        "created_at": created_at,
    }
    return MatchedLeakageAuditV0_1.model_validate(
        {**payload, "content_sha256": content_sha256(payload, excluded_keys=_AUDIT_EXCLUSIONS)},
        strict=True,
    )


def materialize_excluded_corpora(
    experiment_path: Path, phase: Literal["initial", "expansion"]
) -> tuple[list[tuple[str, str, str, str, str]], list[CorpusDigestV0_1]]:
    experiment = load_experiment_config(experiment_path)
    dataset = resolve(experiment_path, experiment.dataset_directory)
    all_examples: dict[str, OpsRouteExample] = {}
    excluded: list[tuple[str, str, str, str, str]] = []
    corpora: list[CorpusDigestV0_1] = []
    for split in ("train", "validation", "test", "adversarial"):
        path = dataset / f"{split}.jsonl"
        values = _read_jsonl(path, OpsRouteExample)
        all_examples.update({item.example_id: item for item in values})
        excluded.extend(_example_collision_tuple(item) for item in values)
        corpora.append(_corpus(path, f"opsroute_{split}", values))
    fixture = Path.cwd() / "tests" / "fixtures" / "opsroute_fixture.jsonl"
    fixture_values = _read_jsonl(fixture, OpsRouteExample)
    excluded.extend(_example_collision_tuple(item) for item in fixture_values)
    corpora.append(_corpus(fixture, "opsroute_fixtures", fixture_values))
    reference_paths = [dataset / "smoke_ids.json"]
    reference_paths.extend(
        sorted((Path.cwd() / "artifacts" / "blocker-resolution" / "subsets").glob("*/*.json"))
    )
    reference_paths.extend(sorted((Path.cwd() / "artifacts" / "day2" / "data").glob("*/*.json")))
    for path in reference_paths:
        if not path.is_file():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        ids = _extract_example_ids(raw)
        resolved_values = [all_examples[item] for item in ids if item in all_examples]
        excluded.extend(_example_collision_tuple(item) for item in resolved_values)
        corpora.append(
            CorpusDigestV0_1(
                corpus_id=f"reference:{path.relative_to(Path.cwd())}",
                path=str(path),
                byte_sha256=sha256_file(path),
                content_sha256=raw.get("content_sha256") if isinstance(raw, dict) else None,
                records_materialized=len(resolved_values),
                reference_only=True,
            )
        )
    original_pool_root = resolve(experiment_path, experiment.original_day3_artifact_root) / "pools"
    for path in sorted(original_pool_root.glob("*/candidate_inputs.jsonl")):
        values = _read_jsonl(path, Any)
        for raw in values:
            input_value = OpsRouteInput.model_validate(raw["input"], strict=True)
            excluded.append(
                (
                    raw["candidate_id"],
                    raw["surface_sha256"],
                    raw["input_content_sha256"],
                    raw["record_sha256"],
                    semantic_leakage_sha256(raw["scenario_family"], input_value),
                )
            )
        corpora.append(
            CorpusDigestV0_1(
                corpus_id=f"original_day3:{path.parent.name}",
                path=str(path),
                byte_sha256=sha256_file(path),
                content_sha256=content_sha256([item["record_sha256"] for item in values]),
                records_materialized=len(values),
                reference_only=False,
            )
        )
    if phase == "expansion":
        initial = find_pool(experiment_path, "initial")
        initial_values = load_candidates(initial)
        excluded.extend(_candidate_collision_tuple(item) for item in initial_values)
        path = initial / "candidate_inputs.jsonl"
        corpora.append(
            CorpusDigestV0_1(
                corpus_id="matched_initial_pool",
                path=str(path),
                byte_sha256=sha256_file(path),
                content_sha256=content_sha256([item.record_sha256 for item in initial_values]),
                records_materialized=len(initial_values),
                reference_only=False,
            )
        )
    return excluded, corpora


def _candidate(
    experiment_path: Path,
    pool_config: MatchedPoolConfigV0_1,
    tokenizer: Any,
    phase: Literal["initial", "expansion"],
    family: ScenarioFamily,
    archetype: str,
    slot: int,
    attempt: int,
    stratum: DistributionStratumV0_1,
    representative: OpsRouteExample,
) -> tuple[MatchedCandidateInputV0_1, MatchedOracleRecordV0_1]:
    task = load_task_config(
        resolve(
            experiment_path,
            load_experiment_config(experiment_path).task_config_path,
        )
    )
    seed_material = (
        f"{task.seed}:day3-matched-candidate-v0.1.0:{phase}:{family}:{archetype}:{slot}:{attempt}"
    )
    subseed = int(sha256_text(seed_material)[:16], 16)
    rng = random.Random(subseed)
    suffix = _matched_identifier_suffix(representative, family, seed_material)
    context = dict(representative.input.context)
    if family == "refund_policy_routing":
        context["customer_id"] = f"CUS-{suffix}"
        context["payment_id"] = (
            f"PAY-{suffix}" if representative.input.context.get("payment_id") is not None else None
        )
        context["amount_minor"] = _sample_bucket(
            pool_config.refund_amount_buckets,
            stratum.numeric_buckets["amount_minor"],
            rng,
        )
        context["payment_age_days"] = _sample_bucket(
            pool_config.refund_age_buckets,
            stratum.numeric_buckets["payment_age_days"],
            rng,
        )
        refund_facts = RefundFacts.model_validate(context, strict=True)
        expected = resolve_refund(refund_facts)
        variant_index = int(stratum.template_family.rsplit(".", 1)[1])
        request, template_id, _ = _refund_request(archetype, refund_facts, variant_index)
    else:
        context["subscription_id"] = (
            f"SUB-{suffix}"
            if representative.input.context.get("subscription_id") is not None
            else None
        )
        context["balance_minor"] = _sample_bucket(
            pool_config.subscription_balance_buckets,
            stratum.numeric_buckets["balance_minor"],
            rng,
        )
        subscription_facts = SubscriptionFacts.model_validate(context, strict=True)
        expected = resolve_subscription(subscription_facts)
        variant_index = int(stratum.template_family.rsplit(".", 1)[1])
        request, template_id, _ = _subscription_request(
            archetype, subscription_facts, variant_index
        )
    if (
        expected.decision != stratum.expected_decision
        or expected.tool != stratum.expected_tool
        or expected.approval_required != stratum.expected_approval_required
        or expected.policy_code != stratum.expected_policy_code
        or expected.reason_code != stratum.expected_reason_code
    ):
        raise ValueError("sampled matched candidate changed the frozen stratum outcome")
    input_value = OpsRouteInput(
        request=request,
        context=context,
        available_tools=list(representative.input.available_tools),
        policy=dict(representative.input.policy),
    )
    temporary = _PromptCandidate(family, input_value)
    prompt_tokens = _prompt_tokens(tokenizer, temporary)
    actual_prompt_bucket = _bucket_for(prompt_tokens, pool_config.prompt_buckets).name
    if actual_prompt_bucket != stratum.prompt_bucket:
        raise _CandidateCollision("prompt bucket mismatch")
    candidate_id = (
        "matched_synthetic_opsroute_v010_"
        f"{'refund' if family == 'refund_policy_routing' else 'subscription'}_"
        f"{archetype}_{phase}_{slot:02d}_{sha256_text(seed_material)[:10]}"
    )
    payload = {
        "schema_version": "day3-matched-candidate-v0.1",
        "candidate_id": candidate_id,
        "attempt_id": "distribution_matched_attempt",
        "phase": phase,
        "task_id": "opsroute",
        "task_version": "0.1.0",
        "scenario_family": family,
        "archetype": archetype,
        "source_stratum_sha256": stratum.stratum_sha256,
        "template_version": pool_config.template_version,
        "template_id": template_id,
        "prompt_bucket": actual_prompt_bucket,
        "numeric_buckets": dict(stratum.numeric_buckets),
        "seed": subseed,
        "generation_attempt": attempt,
        "input": input_value.model_dump(mode="json"),
        "surface_sha256": sha256_text(request),
        "input_content_sha256": content_sha256(input_value),
        "semantic_leakage_sha256": semantic_leakage_sha256(family, input_value),
    }
    candidate = MatchedCandidateInputV0_1.model_validate(
        {**payload, "record_sha256": content_sha256(payload)}, strict=True
    )
    evaluation = EvaluationMetadata(
        authorized_tools=(
            [expected.tool] if expected.decision == "execute" and expected.tool else []
        ),
        allowed_argument_values=_allowed_argument_values(input_value.context, task),
        tags=["synthetic", "distribution_matched_attempt", phase, archetype],
    )
    oracle_payload = {
        "schema_version": "day3-matched-oracle-v0.1",
        "candidate_id": candidate_id,
        "candidate_record_sha256": candidate.record_sha256,
        "expected_contract": expected.model_dump(mode="json"),
        "evaluation_metadata": evaluation.model_dump(mode="json"),
    }
    oracle = MatchedOracleRecordV0_1.model_validate(
        {**oracle_payload, "content_sha256": content_sha256(oracle_payload)}, strict=True
    )
    return candidate, oracle


class _PromptCandidate:
    def __init__(self, scenario_family: ScenarioFamily, input_value: OpsRouteInput) -> None:
        self.scenario_family = scenario_family
        self.input = input_value


class _CandidateCollision(ValueError):
    pass


def _stratum_payload(
    example: OpsRouteExample,
    prompt_tokens: int,
    pool_config: MatchedPoolConfigV0_1,
) -> dict[str, Any]:
    context = example.input.context
    numeric_buckets: dict[str, str]
    if example.scenario_family == "refund_policy_routing":
        numeric_buckets = {
            "amount_minor": _bucket_for(
                cast(int, context["amount_minor"]), pool_config.refund_amount_buckets
            ).name,
            "payment_age_days": _bucket_for(
                cast(int, context["payment_age_days"]), pool_config.refund_age_buckets
            ).name,
        }
        categorical = {
            "requested_action": context["requested_action"],
            "requester_authorized": context["requester_authorized"],
            "action_authorized": context["action_authorized"],
            "customer_id_present": bool(context.get("customer_id")),
            "payment_id_present": context.get("payment_id") is not None,
            "currency": context["currency"],
            "payment_status": context["payment_status"],
            "duplicate_evidence": context["duplicate_evidence"],
            "fraud_indicator": context["fraud_indicator"],
            "available_tools": example.input.available_tools,
            "policy": example.input.policy,
        }
    else:
        numeric_buckets = {
            "balance_minor": _bucket_for(
                cast(int, context["balance_minor"]), pool_config.subscription_balance_buckets
            ).name,
        }
        categorical = {
            "requested_action": context["requested_action"],
            "requester_authorized": context["requester_authorized"],
            "action_authorized": context["action_authorized"],
            "subscription_id_present": context.get("subscription_id") is not None,
            "cancellation_confirmed": context["cancellation_confirmed"],
            "contract_locked": context["contract_locked"],
            "effective_mode": context["effective_mode"],
            "pause_days": context["pause_days"],
            "pause_eligible": context["pause_eligible"],
            "retention_eligible": context["retention_eligible"],
            "available_tools": example.input.available_tools,
            "policy": example.input.policy,
        }
    return {
        "scenario_family": example.scenario_family,
        "archetype": example.archetype,
        "template_family": example.template_id,
        "prompt_bucket": _bucket_for(prompt_tokens, pool_config.prompt_buckets).name,
        "numeric_buckets": numeric_buckets,
        "categorical_facts": categorical,
        "expected_decision": example.expected.decision,
        "expected_tool": example.expected.tool,
        "expected_approval_required": example.expected.approval_required,
        "expected_policy_code": example.expected.policy_code,
        "expected_reason_code": example.expected.reason_code,
    }


def _source_examples_by_stratum(
    experiment_path: Path, pool_config: MatchedPoolConfigV0_1, tokenizer: Any
) -> dict[str, list[OpsRouteExample]]:
    experiment = load_experiment_config(experiment_path)
    train = _read_jsonl(
        resolve(experiment_path, experiment.dataset_directory) / "train.jsonl",
        OpsRouteExample,
    )
    grouped: dict[str, list[OpsRouteExample]] = defaultdict(list)
    for example in train:
        payload = _stratum_payload(example, _prompt_tokens(tokenizer, example), pool_config)
        grouped[content_sha256(payload)].append(example)
    return {
        key: sorted(values, key=lambda item: item.example_id) for key, values in grouped.items()
    }


def _candidate_marginals_from_assignments(
    fingerprint: DistributionFingerprintV0_1, counts: Counter[str]
) -> dict[str, dict[str, int]]:
    strata = {item.stratum_sha256: item for item in fingerprint.strata}
    result: dict[str, Counter[str]] = defaultdict(Counter)
    for stratum_sha256, count in counts.items():
        stratum = strata[stratum_sha256]
        _add_stratum_marginals(result, stratum, count)
    return {name: dict(sorted(values.items())) for name, values in sorted(result.items())}


def _candidate_marginals(
    candidates: list[MatchedCandidateInputV0_1],
) -> dict[str, dict[str, int]]:
    result: dict[str, Counter[str]] = defaultdict(Counter)
    for item in candidates:
        result["family"][item.scenario_family] += 1
        result["archetype"][f"{item.scenario_family}:{item.archetype}"] += 1
        result["template_family"][item.template_id] += 1
        result["prompt_bucket"][item.prompt_bucket] += 1
        for name, value in item.numeric_buckets.items():
            result[f"numeric:{name}"][value] += 1
    return {name: dict(sorted(values.items())) for name, values in sorted(result.items())}


def _add_stratum_marginals(
    result: dict[str, Counter[str]], stratum: DistributionStratumV0_1, count: int
) -> None:
    result["family"][stratum.scenario_family] += count
    result["archetype"][f"{stratum.scenario_family}:{stratum.archetype}"] += count
    result["template_family"][stratum.template_family] += count
    result["prompt_bucket"][stratum.prompt_bucket] += count
    for name, value in stratum.numeric_buckets.items():
        result[f"numeric:{name}"][value] += count


def _update_marginals(
    marginals: dict[str, Counter[str]], example: OpsRouteExample, payload: dict[str, Any]
) -> None:
    marginals["family"][example.scenario_family] += 1
    marginals["archetype"][f"{example.scenario_family}:{example.archetype}"] += 1
    marginals["decision"][example.expected.decision] += 1
    marginals["tool"][str(example.expected.tool)] += 1
    marginals["template_family"][example.template_id] += 1
    marginals["prompt_bucket"][payload["prompt_bucket"]] += 1
    for name, value in payload["numeric_buckets"].items():
        marginals[f"numeric:{name}"][value] += 1


def _validate_strata(strata: list[DistributionStratumV0_1]) -> None:
    counts = Counter(
        (item.scenario_family, item.archetype) for item in strata for _ in range(item.train_count)
    )
    if len(counts) != 16 or set(counts.values()) != {14}:
        raise ValueError("distribution strata do not reconstruct 14 train rows per archetype")


def _prompt_tokens(tokenizer: Any, example: Any) -> int:
    prompt = render_prompt(tokenizer, example, "0.1.0")
    return len(tokenizer(prompt, add_special_tokens=False)["input_ids"])


def _bucket_for(value: int, buckets: list[IntegerBucket]) -> IntegerBucket:
    matches = [item for item in buckets if item.minimum <= value <= item.maximum]
    if len(matches) != 1:
        raise ValueError(f"value {value} maps to {len(matches)} configured buckets")
    return matches[0]


def _sample_bucket(buckets: list[IntegerBucket], name: str, rng: random.Random) -> int:
    matches = [item for item in buckets if item.name == name]
    if len(matches) != 1:
        raise ValueError(f"unknown or ambiguous numeric bucket: {name}")
    return rng.randint(matches[0].minimum, matches[0].maximum)


def _matched_identifier_suffix(
    representative: OpsRouteExample,
    family: ScenarioFamily,
    seed_material: str,
) -> str:
    context = representative.input.context
    source = (
        context.get("customer_id")
        if family == "refund_policy_routing"
        else context.get("subscription_id")
    )
    if not isinstance(source, str) or "-" not in source:
        raise ValueError("frozen train identifier cannot seed a matched opaque identifier")
    suffix = list(source.rsplit("-", 1)[1])
    digest = sha256_text(seed_material).upper()
    alphabet = "0123456789ABCDEF"
    for offset in range(2):
        position = (int(digest[offset * 2 : offset * 2 + 2], 16) + offset * 3) % len(suffix)
        replacement = alphabet[int(digest[8 + offset], 16)]
        if replacement == suffix[position]:
            replacement = alphabet[(alphabet.index(replacement) + 1) % len(alphabet)]
        suffix[position] = replacement
    return "".join(suffix)


def _allowed_argument_values(
    context: dict[str, Any], task: Any
) -> dict[str, list[StrictJsonScalar]]:
    values: dict[str, list[StrictJsonScalar]] = {
        "currency": [task.currency],
        "offer_code": [task.retention_offer_code],
        "pause_days": list(task.allowed_pause_days),
        "effective_mode": ["immediate", "period_end"],
    }
    for name in ("payment_id", "customer_id", "subscription_id", "amount_minor"):
        value = context.get(name)
        if value is not None and type(value) in {str, int, float, bool}:
            values[name] = [cast(StrictJsonScalar, value)]
    return values


def _extract_example_ids(value: Any) -> list[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "example_id" and isinstance(item, str):
                found.add(item)
            elif key == "example_ids" and isinstance(item, list):
                found.update(entry for entry in item if isinstance(entry, str))
            else:
                found.update(_extract_example_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_extract_example_ids(item))
    return sorted(found)


def _example_collision_tuple(example: OpsRouteExample) -> tuple[str, str, str, str, str]:
    return (
        example.example_id,
        example.surface_sha256,
        content_sha256(example.input),
        example.record_sha256,
        semantic_leakage_sha256(example.scenario_family, example.input),
    )


def _candidate_collision_tuple(
    candidate: MatchedCandidateInputV0_1,
) -> tuple[str, str, str, str, str]:
    return (
        candidate.candidate_id,
        candidate.surface_sha256,
        candidate.input_content_sha256,
        candidate.record_sha256,
        candidate.semantic_leakage_sha256,
    )


def _corpus(path: Path, corpus_id: str, values: list[OpsRouteExample]) -> CorpusDigestV0_1:
    return CorpusDigestV0_1(
        corpus_id=corpus_id,
        path=str(path),
        byte_sha256=sha256_file(path),
        content_sha256=content_sha256([item.record_sha256 for item in values]),
        records_materialized=len(values),
        reference_only=False,
    )


def _collision_sets(
    values: list[tuple[str, str, str, str, str]],
) -> list[set[str]]:
    if not values:
        return [set(), set(), set(), set(), set()]
    return [set(items) for items in zip(*values, strict=True)]


def _collides(candidate: MatchedCandidateInputV0_1, sets: list[set[str]]) -> bool:
    values = _candidate_collision_tuple(candidate)
    return any(value in existing for value, existing in zip(values, sets, strict=True))


def _add_collision_values(candidate: MatchedCandidateInputV0_1, sets: list[set[str]]) -> None:
    for value, existing in zip(_candidate_collision_tuple(candidate), sets, strict=True):
        existing.add(value)


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    with path.open(encoding="utf-8") as handle:
        if schema is Any:
            return [json.loads(line) for line in handle]
        return [schema.model_validate_json(line, strict=True) for line in handle]


def _local_snapshot(model_id: str, revision: str) -> str:
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        return snapshot_download(
            repo_id=model_id,
            revision=revision,
            local_files_only=True,
        )
    except (FileNotFoundError, LocalEntryNotFoundError) as exc:
        raise FileNotFoundError(
            f"pinned tokenizer snapshot is not cached locally: {model_id}@{revision}"
        ) from exc
