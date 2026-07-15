"""Clean confirmatory validation/test generation and leakage audit."""

from __future__ import annotations

import json
import random
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

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
from inheritbench.day3_matched.distribution import _allowed_argument_values, _local_snapshot
from inheritbench.models.prompts import render_prompt
from inheritbench.phase3b.config import (
    config_sha256,
    load_confirmatory_config,
    load_experiment_config,
    resolve,
)
from inheritbench.phase3b.schemas import (
    ConfirmatoryBundleManifestV0_1,
    ConfirmatoryExampleV0_1,
    ConfirmatoryLeakageAuditV0_1,
    ConfirmatoryOracleRecordV0_1,
    ConfirmatorySplitManifestV0_1,
    CorpusDigestV0_1,
)
from inheritbench.phase3b.selection import find_hybrid_dataset, load_hybrid_records

_FAMILIES: tuple[tuple[ScenarioFamily, tuple[str, ...]], ...] = (
    ("refund_policy_routing", REFUND_ARCHETYPES),
    ("subscription_cancellation_retention", SUBSCRIPTION_ARCHETYPES),
)
_MANIFEST_EXCLUSIONS = {"bundle_id", "split_id", "audit_id", "created_at", "content_sha256"}


class _Collision(RuntimeError):
    pass


class _PromptRecord:
    def __init__(self, family: ScenarioFamily, input_value: OpsRouteInput) -> None:
        self.scenario_family = family
        self.input = input_value


def freeze_confirmatory_data(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    config = load_confirmatory_config(resolve(experiment_path, experiment.confirmatory_config_path))
    hybrid_path, _ = find_hybrid_dataset(experiment_path)
    source = load_model_config(resolve(experiment_path, experiment.source_model_config_path))
    task = load_task_config(resolve(experiment_path, experiment.task_config_path))
    from transformers import AutoTokenizer

    tokenizer: Any = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        _local_snapshot(source.tokenizer_id, source.tokenizer_revision),
        trust_remote_code=False,
        local_files_only=True,
    )
    excluded, _ = _excluded_corpus(experiment_path, hybrid_path)
    validation, validation_oracles, validation_rejections = _generate_split(
        task,
        config.validation_namespace,
        "confirmatory_validation",
        config.validation_per_archetype,
        tokenizer,
        excluded,
        config.maximum_collision_attempts,
    )
    excluded.update(_collision_tuple(item) for item in validation)
    test, test_oracles, test_rejections = _generate_split(
        task,
        config.test_namespace,
        "confirmatory_test",
        config.test_per_archetype,
        tokenizer,
        excluded,
        config.maximum_collision_attempts,
    )
    if validation_rejections + test_rejections < 0:
        raise AssertionError("unreachable rejection count")
    created_at = datetime.now(UTC)
    validation_files, validation_manifest = _split_files(
        validation,
        validation_oracles,
        "confirmatory_validation",
        config_sha256(config),
        created_at,
    )
    test_files, test_manifest = _split_files(
        test,
        test_oracles,
        "confirmatory_test",
        config_sha256(config),
        created_at,
    )
    validation_bytes = canonical_json_bytes(validation_manifest) + b"\n"
    test_bytes = canonical_json_bytes(test_manifest) + b"\n"
    validation_ref = artifact_reference(
        "validation/manifest.json",
        validation_bytes,
        content_sha256=validation_manifest.content_sha256,
    )
    test_ref = artifact_reference(
        "test/manifest.json", test_bytes, content_sha256=test_manifest.content_sha256
    )
    payload = {
        "schema_version": "phase3b-confirmatory-bundle-v0.1",
        "bundle_id": "pending",
        "status": "FROZEN",
        "validation_sha256": validation_manifest.content_sha256,
        "test_sha256": test_manifest.content_sha256,
        "validation_artifact": validation_ref.model_dump(mode="json"),
        "test_artifact": test_ref.model_dump(mode="json"),
        "generator_config_sha256": config_sha256(config),
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_MANIFEST_EXCLUSIONS)
    bundle_id = f"phase3b-confirmatory-{identity[:16]}"
    manifest = ConfirmatoryBundleManifestV0_1.model_validate(
        {**payload, "bundle_id": bundle_id, "content_sha256": identity}, strict=True
    )
    return write_atomic_bundle(
        resolve(experiment_path, experiment.artifact_root) / "confirmatory-data",
        bundle_id,
        {
            **{f"validation/{name}": value for name, value in validation_files.items()},
            **{f"test/{name}": value for name, value in test_files.items()},
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )


def audit_confirmatory_leakage(experiment_path: Path) -> Path:
    experiment = load_experiment_config(experiment_path)
    bundle, validation_manifest, test_manifest = find_confirmatory_bundle(experiment_path)
    validation = _read_jsonl(bundle / "validation/inputs.jsonl", ConfirmatoryExampleV0_1)
    test = _read_jsonl(bundle / "test/inputs.jsonl", ConfirmatoryExampleV0_1)
    hybrid_path, _ = find_hybrid_dataset(experiment_path)
    excluded, corpora = _excluded_corpus(experiment_path, hybrid_path)
    collisions = _collision_sets(validation, test, excluded)
    support_violations = _support_violations(validation + test)
    status: Literal["PASS", "FAIL"] = (
        "PASS" if not any(collisions.values()) and not support_violations else "FAIL"
    )
    boundary = _boundary_coverage(validation, test)
    required_boundary = {
        "validation_refund_amount_lower": 1,
        "validation_refund_amount_upper": 1,
        "validation_refund_age_lower": 1,
        "validation_refund_age_upper": 1,
        "validation_subscription_balance_lower": 1,
        "validation_subscription_balance_upper": 1,
        "test_refund_amount_lower": 2,
        "test_refund_amount_upper": 2,
        "test_refund_age_lower": 2,
        "test_refund_age_upper": 2,
        "test_subscription_balance_lower": 2,
        "test_subscription_balance_upper": 2,
    }
    for key, minimum in required_boundary.items():
        if boundary.get(key, 0) < minimum:
            support_violations.append(f"boundary coverage {key} below {minimum}")
    if support_violations:
        status = "FAIL"
    created_at = datetime.now(UTC)
    payload = {
        "schema_version": "phase3b-confirmatory-leakage-v0.1",
        "audit_id": "pending",
        "status": status,
        "validation_sha256": validation_manifest.content_sha256,
        "test_sha256": test_manifest.content_sha256,
        "compared_corpora": [item.model_dump(mode="json") for item in corpora],
        "id_collisions": collisions["id"],
        "surface_collisions": collisions["surface"],
        "input_content_collisions": collisions["input"],
        "record_collisions": collisions["record"],
        "semantic_collisions": collisions["semantic"],
        "rejected_generation_attempts": _generation_rejections(validation + test),
        "boundary_coverage": boundary,
        "support_violations": support_violations,
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_MANIFEST_EXCLUSIONS)
    audit_id = f"phase3b-confirmatory-leakage-{identity[:16]}"
    audit = ConfirmatoryLeakageAuditV0_1.model_validate(
        {**payload, "audit_id": audit_id, "content_sha256": identity}, strict=True
    )
    if audit.status != "PASS":
        raise ValueError("Phase 3B confirmatory leakage audit failed")
    return write_atomic_bundle(
        resolve(experiment_path, experiment.artifact_root) / "leakage-audits",
        audit_id,
        {"audit.json": canonical_json_bytes(audit) + b"\n"},
    )


def find_confirmatory_bundle(
    experiment_path: Path,
) -> tuple[Path, ConfirmatorySplitManifestV0_1, ConfirmatorySplitManifestV0_1]:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "confirmatory-data"
    paths = sorted(root.glob("*/manifest.json"))
    if len(paths) != 1:
        raise ValueError(f"expected one Phase 3B confirmatory bundle, found {len(paths)}")
    bundle = paths[0].parent
    validation = ConfirmatorySplitManifestV0_1.model_validate_json(
        (bundle / "validation/manifest.json").read_bytes(), strict=True
    )
    test = ConfirmatorySplitManifestV0_1.model_validate_json(
        (bundle / "test/manifest.json").read_bytes(), strict=True
    )
    return bundle, validation, test


def _generate_split(
    task: Any,
    namespace: str,
    split: Literal["confirmatory_validation", "confirmatory_test"],
    per_archetype: int,
    tokenizer: Any,
    excluded: set[tuple[str, str, str, str, str]],
    maximum_attempts: int,
) -> tuple[list[ConfirmatoryExampleV0_1], list[ConfirmatoryOracleRecordV0_1], int]:
    examples: list[ConfirmatoryExampleV0_1] = []
    oracles: list[ConfirmatoryOracleRecordV0_1] = []
    rejected = 0
    for family, archetypes in _FAMILIES:
        for archetype in archetypes:
            for slot in range(per_archetype):
                for attempt in range(maximum_attempts):
                    try:
                        example, oracle = _candidate(
                            task, namespace, split, family, archetype, slot, attempt, tokenizer
                        )
                        collision = _collision_tuple(example)
                        if _has_collision(collision, excluded):
                            raise _Collision("historical collision")
                        excluded.add(collision)
                        examples.append(example)
                        oracles.append(oracle)
                        break
                    except _Collision:
                        rejected += 1
                else:
                    raise ValueError(
                        f"confirmatory generation exhausted {maximum_attempts} attempts for "
                        f"{split}:{family}:{archetype}:{slot}"
                    )
    expected = per_archetype * 16
    if len(examples) != expected or len(oracles) != expected:
        raise ValueError(f"confirmatory {split} must contain exactly {expected} records")
    return (
        sorted(examples, key=lambda item: item.example_id),
        sorted(oracles, key=lambda item: item.example_id),
        rejected,
    )


def _candidate(
    task: Any,
    namespace: str,
    split: Literal["confirmatory_validation", "confirmatory_test"],
    family: ScenarioFamily,
    archetype: str,
    slot: int,
    attempt: int,
    tokenizer: Any,
) -> tuple[ConfirmatoryExampleV0_1, ConfirmatoryOracleRecordV0_1]:
    seed_material = f"{task.seed}:{namespace}:{family}:{archetype}:{slot}:{attempt}"
    subseed = int(sha256_text(seed_material)[:16], 16)
    rng = random.Random(subseed)
    suffix = sha256_text(f"phase3b-confirmatory:{subseed}")[:12].upper()
    boundary_slots = 1 if split == "confirmatory_validation" else 2
    if family == "refund_policy_routing":
        amount = rng.randint(900, 4900)
        if archetype == "duplicate_auto_refund" and slot < boundary_slots:
            amount = rng.randint(4000, 4900)
        elif archetype == "duplicate_approval":
            amount = rng.randint(5002, 6999) if slot < boundary_slots else rng.randint(7000, 12000)
        age = rng.randint(1, 25)
        if archetype == "expired_window":
            age = rng.randint(32, 45) if slot < boundary_slots else rng.randint(46, 75)
        elif slot < boundary_slots:
            age = rng.randint(21, 25)
        facts = RefundFacts(
            requested_action="none" if archetype == "no_refund_request" else "refund",
            requester_authorized=archetype != "unauthorized_requester",
            action_authorized=True,
            customer_id=f"P3B-CUS-{suffix}",
            payment_id=(
                None
                if archetype == "incomplete_evidence" and (slot + attempt) % 2 == 0
                else f"P3B-PAY-{suffix}"
            ),
            amount_minor=amount,
            currency=task.currency,
            payment_status="pending" if archetype == "pending_payment" else "settled",
            payment_age_days=age,
            duplicate_evidence=(
                "incomplete"
                if archetype == "incomplete_evidence"
                else "none"
                if archetype == "no_refund_request"
                else "confirmed"
            ),
            fraud_indicator=archetype == "fraud_review",
        )
        expected = resolve_refund(facts)
        request, template_id, _ = _refund_request(archetype, facts, (slot + attempt) % 18)
        input_value = OpsRouteInput(
            request=request,
            context=facts.model_dump(mode="json"),
            available_tools=["refund_payment", "escalate_fraud_review"],
            policy=_refund_policy(task),
        )
    else:
        cancellation = {
            "eligible_cancellation",
            "cancellation_approval",
            "confirmation_required",
            "unauthorized_requester",
        }
        requested: Literal["cancel", "pause", "retention", "none"]
        if archetype in cancellation:
            requested = "cancel"
        elif archetype == "eligible_pause":
            requested = "pause"
        elif archetype in {"eligible_retention", "ineligible_retention"}:
            requested = "retention"
        else:
            requested = "none"
        balance = rng.randint(0, 9500)
        if archetype == "eligible_cancellation" and slot < boundary_slots:
            balance = rng.randint(7500, 9500)
        elif archetype == "cancellation_approval":
            balance = (
                rng.randint(10002, 11999) if slot < boundary_slots else rng.randint(12000, 18000)
            )
        subscription_facts = SubscriptionFacts(
            requested_action=requested,
            requester_authorized=archetype != "unauthorized_requester",
            action_authorized=True,
            subscription_id=f"P3B-SUB-{suffix}",
            cancellation_confirmed=archetype != "confirmation_required",
            contract_locked=archetype == "cancellation_approval" and rng.choice([True, False]),
            balance_minor=balance,
            effective_mode=rng.choice(["immediate", "period_end"]),
            pause_days=rng.choice(task.allowed_pause_days),
            pause_eligible=archetype == "eligible_pause",
            retention_eligible=archetype == "eligible_retention",
        )
        expected = resolve_subscription(subscription_facts)
        request, template_id, _ = _subscription_request(
            archetype, subscription_facts, (slot + attempt) % 18
        )
        input_value = OpsRouteInput(
            request=request,
            context=subscription_facts.model_dump(mode="json"),
            available_tools=["cancel_subscription", "pause_subscription", "offer_retention"],
            policy=_subscription_policy(task),
        )
    prompt = render_prompt(tokenizer, _PromptRecord(family, input_value), "0.1.0")
    token_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    prompt_tokens = len(token_ids)
    if prompt_tokens > 1024:
        raise _Collision("prompt exceeds token limit")
    example_id = (
        f"phase3b_opsroute_{'validation' if split == 'confirmatory_validation' else 'test'}_"
        f"{'refund' if family == 'refund_policy_routing' else 'subscription'}_"
        f"{archetype}_{slot:02d}_{sha256_text(seed_material)[:10]}"
    )
    payload = {
        "schema_version": "phase3b-confirmatory-example-v0.1",
        "example_id": example_id,
        "split": split,
        "scenario_family": family,
        "archetype": archetype,
        "slot": slot,
        "generation_attempt": attempt,
        "seed": subseed,
        "template_id": template_id,
        "input": input_value.model_dump(mode="json"),
        "prompt_token_count": prompt_tokens,
        "surface_sha256": sha256_text(request),
        "input_content_sha256": content_sha256(input_value),
        "semantic_leakage_sha256": semantic_leakage_sha256(family, input_value),
    }
    example = ConfirmatoryExampleV0_1.model_validate(
        {**payload, "record_sha256": content_sha256(payload)}, strict=True
    )
    authorized_tools = [expected.tool] if expected.decision == "execute" and expected.tool else []
    evaluation = EvaluationMetadata(
        authorized_tools=authorized_tools,
        allowed_argument_values=_allowed_argument_values(input_value.context, task),
        tags=["phase3b_confirmatory", split, archetype],
    )
    oracle_payload = {
        "schema_version": "phase3b-confirmatory-oracle-v0.1",
        "example_id": example_id,
        "example_record_sha256": example.record_sha256,
        "expected_contract": expected.model_dump(mode="json"),
        "evaluation_metadata": evaluation.model_dump(mode="json"),
    }
    oracle = ConfirmatoryOracleRecordV0_1.model_validate(
        {**oracle_payload, "content_sha256": content_sha256(oracle_payload)}, strict=True
    )
    return example, oracle


def _split_files(
    examples: list[ConfirmatoryExampleV0_1],
    oracles: list[ConfirmatoryOracleRecordV0_1],
    split: Literal["confirmatory_validation", "confirmatory_test"],
    config_hash: str,
    created_at: datetime,
) -> tuple[dict[str, bytes], ConfirmatorySplitManifestV0_1]:
    inputs_bytes = canonical_jsonl_bytes(examples, id_key="example_id")
    oracle_bytes = canonical_jsonl_bytes(oracles, id_key="example_id")
    inputs_ref = artifact_reference(
        "inputs.jsonl",
        inputs_bytes,
        content_sha256=content_sha256([item.record_sha256 for item in examples]),
    )
    oracle_ref = artifact_reference(
        "oracle.jsonl",
        oracle_bytes,
        content_sha256=content_sha256([item.content_sha256 for item in oracles]),
    )
    count = len(examples)
    per_archetype = 2 if split == "confirmatory_validation" else 4
    payload = {
        "schema_version": "phase3b-confirmatory-split-v0.1",
        "split_id": "pending",
        "split": split,
        "status": "FROZEN",
        "example_count": count,
        "per_archetype_count": per_archetype,
        "family_counts": dict(Counter(item.scenario_family for item in examples)),
        "inputs_artifact": inputs_ref.model_dump(mode="json"),
        "oracle_artifact": oracle_ref.model_dump(mode="json"),
        "example_ids_sha256": content_sha256(sorted(item.example_id for item in examples)),
        "generator_config_sha256": config_hash,
        "created_before_training": True,
        "created_at": created_at,
    }
    identity = content_sha256(payload, excluded_keys=_MANIFEST_EXCLUSIONS)
    manifest = ConfirmatorySplitManifestV0_1.model_validate(
        {
            **payload,
            "split_id": f"phase3b-{split}-{identity[:16]}",
            "content_sha256": identity,
        },
        strict=True,
    )
    return {
        "inputs.jsonl": inputs_bytes,
        "oracle.jsonl": oracle_bytes,
        "manifest.json": canonical_json_bytes(manifest) + b"\n",
    }, manifest


def _excluded_corpus(
    experiment_path: Path, hybrid_path: Path
) -> tuple[set[tuple[str, str, str, str, str]], list[CorpusDigestV0_1]]:
    experiment = load_experiment_config(experiment_path)
    excluded: set[tuple[str, str, str, str, str]] = set()
    corpora: list[CorpusDigestV0_1] = []
    dataset = resolve(experiment_path, experiment.dataset_directory)
    for split in ("train", "validation", "test", "adversarial"):
        path = dataset / f"{split}.jsonl"
        values = _read_jsonl(path, OpsRouteExample)
        excluded.update(_example_collision_tuple(item) for item in values)
        corpora.append(_corpus(f"opsroute:{split}", path, len(values)))
    fixture = Path.cwd() / "tests/fixtures/opsroute_fixture.jsonl"
    values = _read_jsonl(fixture, OpsRouteExample)
    excluded.update(_example_collision_tuple(item) for item in values)
    corpora.append(_corpus("fixtures", fixture, len(values)))
    for root_name, root in [
        ("independent", Path.cwd() / "artifacts/day3/pools"),
        ("matched", Path.cwd() / "artifacts/day3-matched/pools"),
    ]:
        for path in sorted(root.glob("*/candidate_inputs.jsonl")):
            raw_values = [json.loads(line) for line in path.read_text().splitlines()]
            for raw in raw_values:
                input_value = OpsRouteInput.model_validate(raw["input"], strict=True)
                excluded.add(
                    (
                        raw["candidate_id"],
                        raw["surface_sha256"],
                        raw["input_content_sha256"],
                        raw["record_sha256"],
                        semantic_leakage_sha256(raw["scenario_family"], input_value),
                    )
                )
            corpora.append(_corpus(f"{root_name}:{path.parent.name}", path, len(raw_values)))
    hybrid = load_hybrid_records(hybrid_path)
    for record in hybrid:
        excluded.add(
            (
                record.training_record_id,
                sha256_text(record.input.request),
                content_sha256(record.input),
                record.content_sha256,
                semantic_leakage_sha256(record.scenario_family, record.input),
            )
        )
    hybrid_file = hybrid_path / "records.jsonl"
    corpora.append(_corpus("phase3b:hybrid", hybrid_file, len(hybrid)))
    for path in [
        dataset / "smoke_ids.json",
        Path.cwd() / "artifacts/blocker-resolution/subsets/subsets-c0e0abb99d3f9e7d/manifest.json",
        Path.cwd() / "artifacts/day2/data/day2-data-01c2e470b9ccf379/manifest.json",
    ]:
        if path.is_file():
            corpora.append(_corpus(f"reference:{path.name}", path, 0, reference_only=True))
    return excluded, corpora


def _collision_sets(
    validation: list[ConfirmatoryExampleV0_1],
    test: list[ConfirmatoryExampleV0_1],
    excluded: set[tuple[str, str, str, str, str]],
) -> dict[str, list[str]]:
    fields = ["id", "surface", "input", "record", "semantic"]
    result: dict[str, list[str]] = {name: [] for name in fields}
    seen = [set(item[index] for item in excluded) for index in range(5)]
    for item in [*validation, *test]:
        values = _collision_tuple(item)
        for index, value in enumerate(values):
            if value in seen[index]:
                result[fields[index]].append(f"{item.example_id}:{value}")
            seen[index].add(value)
    return result


def _support_violations(examples: list[ConfirmatoryExampleV0_1]) -> list[str]:
    forbidden = {
        "amount_minor": {4999, 5000, 5001},
        "payment_age_days": {30, 31},
        "balance_minor": {9999, 10000, 10001},
    }
    violations: list[str] = []
    for item in examples:
        for field, values in forbidden.items():
            if item.input.context.get(field) in values:
                violations.append(f"{item.example_id}:{field}:{item.input.context[field]}")
    return violations


def _boundary_coverage(
    validation: list[ConfirmatoryExampleV0_1], test: list[ConfirmatoryExampleV0_1]
) -> dict[str, int]:
    result: Counter[str] = Counter()
    for label, values in (("validation", validation), ("test", test)):
        for item in values:
            context = item.input.context
            amount = context.get("amount_minor")
            age = context.get("payment_age_days")
            balance = context.get("balance_minor")
            if (
                item.archetype == "duplicate_auto_refund"
                and isinstance(amount, int)
                and 4000 <= amount <= 4900
            ):
                result[f"{label}_refund_amount_lower"] += 1
            if (
                item.archetype == "duplicate_approval"
                and isinstance(amount, int)
                and 5002 <= amount <= 6999
            ):
                result[f"{label}_refund_amount_upper"] += 1
            if (
                item.scenario_family == "refund_policy_routing"
                and item.archetype != "expired_window"
                and isinstance(age, int)
                and 21 <= age <= 25
            ):
                result[f"{label}_refund_age_lower"] += 1
            if item.archetype == "expired_window" and isinstance(age, int) and 32 <= age <= 45:
                result[f"{label}_refund_age_upper"] += 1
            if (
                item.archetype == "eligible_cancellation"
                and isinstance(balance, int)
                and 7500 <= balance <= 9500
            ):
                result[f"{label}_subscription_balance_lower"] += 1
            if (
                item.archetype == "cancellation_approval"
                and isinstance(balance, int)
                and 10002 <= balance <= 11999
            ):
                result[f"{label}_subscription_balance_upper"] += 1
    return dict(sorted(result.items()))


def _generation_rejections(examples: list[ConfirmatoryExampleV0_1]) -> int:
    return sum(item.generation_attempt for item in examples)


def _has_collision(
    item: tuple[str, str, str, str, str],
    excluded: set[tuple[str, str, str, str, str]],
) -> bool:
    columns = [set(value[index] for value in excluded) for index in range(5)]
    return any(item[index] in columns[index] for index in range(5))


def _collision_tuple(item: ConfirmatoryExampleV0_1) -> tuple[str, str, str, str, str]:
    return (
        item.example_id,
        item.surface_sha256,
        item.input_content_sha256,
        item.record_sha256,
        item.semantic_leakage_sha256,
    )


def _example_collision_tuple(item: OpsRouteExample) -> tuple[str, str, str, str, str]:
    return (
        item.example_id,
        item.surface_sha256,
        content_sha256(item.input),
        item.record_sha256,
        semantic_leakage_sha256(item.scenario_family, item.input),
    )


def _corpus(
    corpus_id: str, path: Path, records: int, *, reference_only: bool = False
) -> CorpusDigestV0_1:
    content = None
    if path.suffix == ".json":
        raw = json.loads(path.read_text())
        if isinstance(raw, dict):
            content = raw.get("content_sha256")
    return CorpusDigestV0_1(
        corpus_id=corpus_id,
        path=str(path),
        byte_sha256=sha256_file(path),
        content_sha256=content,
        records_materialized=records,
        reference_only=reference_only,
    )


def _refund_policy(task: Any) -> dict[str, Any]:
    return {
        "refund_auto_approval_limit_minor": task.refund_auto_approval_limit_minor,
        "refund_window_days": task.refund_window_days,
        "currency": task.currency,
        "rules": [
            "Unauthorized requesters must be refused.",
            "Incomplete duplicate evidence requires clarification.",
            "Fraud indicators require fraud-review approval.",
            "Only settled duplicate payments within 30 days are refundable.",
        ],
    }


def _subscription_policy(task: Any) -> dict[str, Any]:
    return {
        "cancellation_balance_approval_limit_minor": task.cancellation_balance_approval_limit_minor,
        "allowed_pause_days": task.allowed_pause_days,
        "retention_offer_code": task.retention_offer_code,
        "currency": task.currency,
        "rules": [
            "Unauthorized requesters must be refused.",
            "Cancellation requires explicit confirmation.",
            "Locked contracts or balances above 10000 require approval.",
            "Explicit cancellation cannot be replaced by retention.",
        ],
    }


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    return [schema.model_validate_json(line, strict=True) for line in path.read_text().splitlines()]
