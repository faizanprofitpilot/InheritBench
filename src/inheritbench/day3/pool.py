"""Deterministic, leakage-audited Day 3 candidate pools."""

from __future__ import annotations

import random
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
from inheritbench.config import OpsRouteTaskConfig, ScenarioFamily, load_task_config
from inheritbench.data.opsroute.generate import REFUND_ARCHETYPES, SUBSCRIPTION_ARCHETYPES
from inheritbench.data.opsroute.policies import resolve_refund, resolve_subscription
from inheritbench.data.opsroute.schemas import (
    EvaluationMetadata,
    OpsRouteExample,
    OpsRouteInput,
    RefundFacts,
    SubscriptionFacts,
)
from inheritbench.day3.config import load_experiment_config, load_pool_config, resolve
from inheritbench.day3.schemas import (
    CorpusDigest,
    LeakageAuditV0_1,
    SyntheticCandidateInputV0_1,
    SyntheticOracleRecordV0_1,
    SyntheticPoolManifestV0_1,
)
from inheritbench.evaluation.contracts import StrictJsonScalar, ToolName

_FAMILIES: tuple[tuple[ScenarioFamily, tuple[str, ...]], ...] = (
    ("refund_policy_routing", REFUND_ARCHETYPES),
    ("subscription_cancellation_retention", SUBSCRIPTION_ARCHETYPES),
)


def freeze_pool(experiment_path: Path, phase: Literal["initial", "expansion"] = "initial") -> Path:
    experiment = load_experiment_config(experiment_path)
    pool_config = load_pool_config(resolve(experiment_path, experiment.pool_config_path))
    root = resolve(experiment_path, experiment.artifact_root) / "pools"
    if phase == "expansion" and not list(root.glob("day3-pool-initial-*")):
        raise ValueError("the expansion pool requires a frozen initial pool")
    per_archetype = (
        pool_config.initial_per_archetype
        if phase == "initial"
        else pool_config.expansion_per_archetype
    )
    excluded, corpora = _excluded_records(experiment_path)
    existing_semantic = {
        semantic_leakage_sha256(item.scenario_family, item.input) for item in excluded
    }
    existing_surface = {item.surface_sha256 for item in excluded}
    existing_input = {content_sha256(item.input) for item in excluded}
    existing_ids = {item.example_id for item in excluded}
    if phase == "expansion":
        initial_path = next(iter(sorted(root.glob("day3-pool-initial-*/candidate_inputs.jsonl"))))
        initial_candidates = _load_all_candidates(root, "initial")
        corpora.append(
            CorpusDigest(
                path=str(initial_path),
                byte_sha256=sha256_file(initial_path),
                records=len(initial_candidates),
            )
        )
        for candidate in initial_candidates:
            existing_semantic.add(candidate.semantic_leakage_sha256)
            existing_surface.add(candidate.surface_sha256)
            existing_input.add(candidate.input_content_sha256)
            existing_ids.add(candidate.candidate_id)
    task = load_task_config(resolve(experiment_path, experiment.task_config_path))
    candidates: list[SyntheticCandidateInputV0_1] = []
    oracles: list[SyntheticOracleRecordV0_1] = []
    rejected_collisions = 0
    for family, archetypes in _FAMILIES:
        for archetype in archetypes:
            for slot in range(per_archetype):
                for attempt in range(pool_config.maximum_collision_attempts):
                    candidate, oracle = _candidate(task, phase, family, archetype, slot, attempt)
                    collision = (
                        candidate.candidate_id in existing_ids
                        or candidate.surface_sha256 in existing_surface
                        or candidate.input_content_sha256 in existing_input
                        or candidate.semantic_leakage_sha256 in existing_semantic
                    )
                    if collision:
                        rejected_collisions += 1
                        continue
                    candidates.append(candidate)
                    oracles.append(oracle)
                    existing_ids.add(candidate.candidate_id)
                    existing_surface.add(candidate.surface_sha256)
                    existing_input.add(candidate.input_content_sha256)
                    existing_semantic.add(candidate.semantic_leakage_sha256)
                    break
                else:
                    raise ValueError(
                        f"collision attempts exhausted: {phase}/{family}/{archetype}/{slot}"
                    )
    candidates.sort(key=lambda item: item.candidate_id)
    oracles.sort(key=lambda item: item.candidate_id)
    expected_count = per_archetype * 16
    if len(candidates) != expected_count or len(oracles) != expected_count:
        raise ValueError("candidate pool count mismatch")
    candidate_bytes = canonical_jsonl_bytes(candidates, id_key="candidate_id")
    oracle_bytes = canonical_jsonl_bytes(oracles, id_key="candidate_id")
    audit_payload = {
        "schema_version": "day3-leakage-audit-v0.1",
        "signature_version": pool_config.leakage_signature_version,
        "phase": phase,
        "compared_corpora": [item.model_dump(mode="json") for item in corpora],
        "candidate_count": len(candidates),
        "unique_id_count": len({item.candidate_id for item in candidates}),
        "unique_surface_count": len({item.surface_sha256 for item in candidates}),
        "unique_input_content_count": len({item.input_content_sha256 for item in candidates}),
        "unique_semantic_count": len({item.semantic_leakage_sha256 for item in candidates}),
        "collision_rejections": rejected_collisions,
        "zero_overlap": True,
    }
    audit = LeakageAuditV0_1.model_validate(
        {**audit_payload, "content_sha256": content_sha256(audit_payload)}, strict=True
    )
    audit_bytes = canonical_json_bytes(audit) + b"\n"
    identity = content_sha256(
        {
            "phase": phase,
            "candidate_hashes": [item.record_sha256 for item in candidates],
            "oracle_hashes": [item.content_sha256 for item in oracles],
            "audit": audit.content_sha256,
        }
    )
    pool_id = f"day3-pool-{phase}-{identity[:16]}"
    candidates_ref = artifact_reference(
        "candidate_inputs.jsonl", candidate_bytes, content_sha256=content_sha256(candidates)
    )
    oracle_ref = artifact_reference(
        "candidate_oracle.jsonl", oracle_bytes, content_sha256=content_sha256(oracles)
    )
    audit_ref = artifact_reference(
        "leakage_audit.json", audit_bytes, content_sha256=audit.content_sha256
    )
    from datetime import UTC, datetime

    created_at = datetime.now(UTC)
    manifest_payload = {
        "schema_version": "synthetic-pool-v0.1",
        "pool_id": pool_id,
        "phase": phase,
        "status": "FROZEN",
        "seed": pool_config.seed,
        "generator_version": pool_config.generator_version,
        "template_version": pool_config.template_version,
        "candidate_count": len(candidates),
        "per_archetype": per_archetype,
        "candidate_artifact": candidates_ref.model_dump(mode="json"),
        "oracle_artifact": oracle_ref.model_dump(mode="json"),
        "leakage_artifact": audit_ref.model_dump(mode="json"),
        "created_at": created_at,
    }
    manifest = SyntheticPoolManifestV0_1.model_validate(
        {
            **manifest_payload,
            "content_sha256": content_sha256(
                manifest_payload, excluded_keys={"pool_id", "created_at", "content_sha256"}
            ),
        },
        strict=True,
    )
    destination = root / pool_id
    if destination.exists():
        stored = SyntheticPoolManifestV0_1.model_validate_json(
            (destination / "manifest.json").read_bytes(), strict=True
        )
        if stored.content_sha256 != manifest.content_sha256:
            raise ValueError("existing pool content differs")
        return destination
    return write_atomic_bundle(
        root,
        pool_id,
        {
            "candidate_inputs.jsonl": candidate_bytes,
            "candidate_oracle.jsonl": oracle_bytes,
            "leakage_audit.json": audit_bytes,
            "manifest.json": canonical_json_bytes(manifest) + b"\n",
        },
    )


def find_pool(experiment_path: Path, phase: Literal["initial", "expansion"]) -> Path:
    experiment = load_experiment_config(experiment_path)
    root = resolve(experiment_path, experiment.artifact_root) / "pools"
    matches = sorted(root.glob(f"day3-pool-{phase}-*"))
    if len(matches) != 1:
        raise ValueError(f"expected one {phase} pool, found {len(matches)}")
    return matches[0]


def load_candidates(pool: Path) -> list[SyntheticCandidateInputV0_1]:
    return _read_jsonl(pool / "candidate_inputs.jsonl", SyntheticCandidateInputV0_1)


def load_oracles(pool: Path) -> list[SyntheticOracleRecordV0_1]:
    return _read_jsonl(pool / "candidate_oracle.jsonl", SyntheticOracleRecordV0_1)


def semantic_leakage_sha256(family: ScenarioFamily, value: OpsRouteInput) -> str:
    context = value.context
    if family == "refund_policy_routing":
        refund_facts = RefundFacts.model_validate(context, strict=True)
        normalized: dict[str, Any] = {
            "scenario_family": family,
            "requested_action": refund_facts.requested_action,
            "requester_authorized": refund_facts.requester_authorized,
            "action_authorized": refund_facts.action_authorized,
            "customer_id_present": bool(refund_facts.customer_id),
            "payment_id_present": refund_facts.payment_id is not None,
            "amount_minor": refund_facts.amount_minor,
            "currency": refund_facts.currency,
            "payment_status": refund_facts.payment_status,
            "payment_age_days": refund_facts.payment_age_days,
            "duplicate_evidence": refund_facts.duplicate_evidence,
            "fraud_indicator": refund_facts.fraud_indicator,
            "available_tools": value.available_tools,
            "policy": {
                "refund_auto_approval_limit_minor": value.policy[
                    "refund_auto_approval_limit_minor"
                ],
                "refund_window_days": value.policy["refund_window_days"],
                "currency": value.policy["currency"],
            },
        }
    else:
        subscription_facts = SubscriptionFacts.model_validate(context, strict=True)
        normalized = {
            "scenario_family": family,
            "requested_action": subscription_facts.requested_action,
            "requester_authorized": subscription_facts.requester_authorized,
            "action_authorized": subscription_facts.action_authorized,
            "subscription_id_present": subscription_facts.subscription_id is not None,
            "cancellation_confirmed": subscription_facts.cancellation_confirmed,
            "contract_locked": subscription_facts.contract_locked,
            "balance_minor": subscription_facts.balance_minor,
            "effective_mode": subscription_facts.effective_mode,
            "pause_days": subscription_facts.pause_days,
            "pause_eligible": subscription_facts.pause_eligible,
            "retention_eligible": subscription_facts.retention_eligible,
            "available_tools": value.available_tools,
            "policy": {
                "cancellation_balance_approval_limit_minor": value.policy[
                    "cancellation_balance_approval_limit_minor"
                ],
                "allowed_pause_days": value.policy["allowed_pause_days"],
                "retention_offer_code": value.policy["retention_offer_code"],
                "currency": value.policy["currency"],
            },
        }
    return content_sha256(normalized)


def _candidate(
    task: OpsRouteTaskConfig,
    phase: Literal["initial", "expansion"],
    family: ScenarioFamily,
    archetype: str,
    slot: int,
    attempt: int,
) -> tuple[SyntheticCandidateInputV0_1, SyntheticOracleRecordV0_1]:
    seed_material = f"{task.seed}:day3:{phase}:{family}:{archetype}:{slot}:{attempt}"
    subseed = int(sha256_text(seed_material)[:16], 16)
    rng = random.Random(subseed)
    suffix = sha256_text(f"day3:{subseed}")[:12].upper()
    if family == "refund_policy_routing":
        refund_facts = _refund_facts(task, archetype, slot, rng, suffix)
        expected = resolve_refund(refund_facts)
        tools: list[ToolName] = ["refund_payment", "escalate_fraud_review"]
        policy = _refund_policy(task)
        request, template_id = _refund_request(archetype, refund_facts, phase, slot)
        context = refund_facts.model_dump(mode="json")
    else:
        subscription_facts = _subscription_facts(task, archetype, slot, rng, suffix)
        expected = resolve_subscription(subscription_facts)
        tools = ["cancel_subscription", "pause_subscription", "offer_retention"]
        policy = _subscription_policy(task)
        request, template_id = _subscription_request(archetype, subscription_facts, phase, slot)
        context = subscription_facts.model_dump(mode="json")
    input_value = OpsRouteInput(
        request=request,
        context=context,
        available_tools=tools,
        policy=policy,
    )
    candidate_id = (
        "synthetic_opsroute_v010_"
        f"{'refund' if family == 'refund_policy_routing' else 'subscription'}_"
        f"{archetype}_{phase}_{slot:02d}_{sha256_text(seed_material)[:10]}"
    )
    payload = {
        "schema_version": "synthetic-candidate-v0.1",
        "candidate_id": candidate_id,
        "phase": phase,
        "task_id": "opsroute",
        "task_version": "0.1.0",
        "scenario_family": family,
        "archetype": archetype,
        "template_version": "day3-synthetic-template-v0.1.0",
        "template_id": template_id,
        "seed": subseed,
        "generation_attempt": attempt,
        "input": input_value.model_dump(mode="json"),
        "surface_sha256": sha256_text(request),
        "input_content_sha256": content_sha256(input_value),
        "semantic_leakage_sha256": semantic_leakage_sha256(family, input_value),
    }
    candidate = SyntheticCandidateInputV0_1.model_validate(
        {**payload, "record_sha256": content_sha256(payload)}, strict=True
    )
    evaluation = EvaluationMetadata(
        authorized_tools=(
            [expected.tool] if expected.decision == "execute" and expected.tool else []
        ),
        allowed_argument_values=_allowed_argument_values(input_value.context, task),
        tags=["synthetic", phase, archetype],
    )
    oracle_payload = {
        "schema_version": "synthetic-oracle-v0.1",
        "candidate_id": candidate_id,
        "candidate_record_sha256": candidate.record_sha256,
        "expected_contract": expected.model_dump(mode="json"),
        "evaluation_metadata": evaluation.model_dump(mode="json"),
    }
    oracle = SyntheticOracleRecordV0_1.model_validate(
        {**oracle_payload, "content_sha256": content_sha256(oracle_payload)}, strict=True
    )
    return candidate, oracle


def _refund_facts(
    task: OpsRouteTaskConfig, archetype: str, slot: int, rng: random.Random, suffix: str
) -> RefundFacts:
    amount = rng.randint(700, 4900)
    if archetype == "duplicate_auto_refund" and slot % 16 in {0, 1}:
        amount = 4999 if slot % 16 == 0 else 5000
    elif archetype == "duplicate_approval":
        amount = 5001 if slot % 16 == 0 else rng.randint(5002, 15000)
    age = rng.randint(1, 29)
    if archetype == "duplicate_auto_refund" and slot % 16 == 2:
        age = 30
    elif archetype == "expired_window":
        age = 31 if slot % 16 == 0 else rng.randint(32, 90)
    return RefundFacts(
        requested_action="none" if archetype == "no_refund_request" else "refund",
        requester_authorized=archetype != "unauthorized_requester",
        action_authorized=True,
        customer_id=f"D3-CUS-{suffix}",
        payment_id=(
            None if archetype == "incomplete_evidence" and slot % 2 == 0 else f"D3-PAY-{suffix}"
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


def _subscription_facts(
    task: OpsRouteTaskConfig, archetype: str, slot: int, rng: random.Random, suffix: str
) -> SubscriptionFacts:
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
    if archetype == "eligible_cancellation" and slot % 16 in {0, 1}:
        balance = 9999 if slot % 16 == 0 else 10000
    elif archetype == "cancellation_approval":
        balance = 10001 if slot % 16 == 0 else rng.randint(10002, 20000)
    return SubscriptionFacts(
        requested_action=requested,
        requester_authorized=archetype != "unauthorized_requester",
        action_authorized=True,
        subscription_id=f"D3-SUB-{suffix}",
        cancellation_confirmed=archetype != "confirmation_required",
        contract_locked=archetype == "cancellation_approval" and rng.choice([True, False]),
        balance_minor=balance,
        effective_mode=rng.choice(["immediate", "period_end"]),
        pause_days=rng.choice(task.allowed_pause_days),
        pause_eligible=archetype == "eligible_pause",
        retention_eligible=archetype == "eligible_retention",
    )


def _refund_request(archetype: str, facts: RefundFacts, phase: str, slot: int) -> tuple[str, str]:
    payment = facts.payment_id or (
        f"the duplicate payment with the missing identifier for {facts.customer_id}"
    )
    templates = (
        "Route this duplicate-payment request for {payment} under the supplied policy.",
        "Please handle the requested refund concerning {payment} using only verified "
        "account facts.",
        "Determine the permitted refund action for {payment}; preserve all approval controls.",
        "Apply the refund workflow to {payment} and return only the operational contract.",
        "Assess the correct policy route for refund case {payment}.",
        "Resolve the requested payment action for {payment} without adding unsupported facts.",
    )
    if archetype == "no_refund_request":
        templates = (
            "Provide payment status for {payment}; do not initiate a refund or other action.",
            "This is an information-only inquiry about {payment}, not a request to act.",
            "Route the status inquiry for {payment} without executing any payment operation.",
            "Return the operational contract for this non-actionable inquiry about {payment}.",
            "Assess {payment} as a status question only; no refund is requested.",
            "Resolve the informational inquiry for {payment} without taking action.",
        )
    template_index = slot % (4 if phase == "initial" else 2) + (0 if phase == "initial" else 4)
    return (
        templates[template_index].format(payment=payment),
        f"day3.refund.{archetype}.{template_index}",
    )


def _subscription_request(
    archetype: str, facts: SubscriptionFacts, phase: str, slot: int
) -> tuple[str, str]:
    subscription = facts.subscription_id or "the subscription with the missing identifier"
    action = facts.requested_action
    templates = (
        "Route the {action} request for {subscription} under the supplied subscription policy.",
        "Determine the permitted {action} action for {subscription} using only verified facts.",
        "Apply the subscription workflow to {subscription} for this {action} request.",
        "Return the operational contract for the {action} case involving {subscription}.",
        "Assess the correct policy route for {subscription} and the requested {action} action.",
        "Resolve the {action} request for {subscription} without inventing account details.",
    )
    if archetype == "no_subscription_action":
        templates = (
            "Provide subscription status for {subscription}; no account action is requested.",
            "This is an information-only inquiry about {subscription}, not a request to act.",
            "Route the status inquiry for {subscription} without changing the subscription.",
            "Return the operational contract for this non-actionable subscription inquiry.",
            "Assess {subscription} as a status question only; do not modify the account.",
            "Resolve the informational inquiry for {subscription} without taking action.",
        )
    template_index = slot % (4 if phase == "initial" else 2) + (0 if phase == "initial" else 4)
    return (
        templates[template_index].format(action=action, subscription=subscription),
        f"day3.subscription.{archetype}.{template_index}",
    )


def _refund_policy(task: OpsRouteTaskConfig) -> dict[str, Any]:
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


def _subscription_policy(task: OpsRouteTaskConfig) -> dict[str, Any]:
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


def _allowed_argument_values(
    context: dict[str, Any], task: OpsRouteTaskConfig
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


def _excluded_records(experiment_path: Path) -> tuple[list[OpsRouteExample], list[CorpusDigest]]:
    experiment = load_experiment_config(experiment_path)
    dataset = resolve(experiment_path, experiment.dataset_directory)
    paths = [dataset / f"{split}.jsonl" for split in ("train", "validation", "test", "adversarial")]
    fixture = Path.cwd() / "tests/fixtures/opsroute_fixture.jsonl"
    paths.append(fixture)
    records: list[OpsRouteExample] = []
    corpora: list[CorpusDigest] = []
    for path in paths:
        values = _read_jsonl(path, OpsRouteExample)
        records.extend(values)
        corpora.append(
            CorpusDigest(path=str(path), byte_sha256=sha256_file(path), records=len(values))
        )
    metadata_paths = [
        dataset / "smoke_ids.json",
        Path.cwd() / "artifacts/blocker-resolution/subsets/subsets-c0e0abb99d3f9e7d/manifest.json",
        Path.cwd() / "artifacts/day2/data/day2-data-01c2e470b9ccf379/manifest.json",
    ]
    for path in metadata_paths:
        if path.is_file():
            corpora.append(CorpusDigest(path=str(path), byte_sha256=sha256_file(path), records=0))
    return records, corpora


def _load_all_candidates(root: Path, phase: str) -> list[SyntheticCandidateInputV0_1]:
    matches = sorted(root.glob(f"day3-pool-{phase}-*/candidate_inputs.jsonl"))
    if len(matches) != 1:
        raise ValueError(f"expected one frozen {phase} candidate file")
    return _read_jsonl(matches[0], SyntheticCandidateInputV0_1)


def _read_jsonl(path: Path, schema: Any) -> list[Any]:
    with path.open(encoding="utf-8") as handle:
        return [schema.model_validate_json(line, strict=True) for line in handle]
