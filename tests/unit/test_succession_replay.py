from __future__ import annotations

import json
from pathlib import Path

import pytest

from inheritbench.artifacts.hashing import sha256_file
from inheritbench.config import load_task_config
from inheritbench.data.opsroute.generate import generate_examples
from inheritbench.data.opsroute.policies import resolve_refund, resolve_subscription
from inheritbench.data.opsroute.schemas import RefundFacts, SubscriptionFacts
from inheritbench.succession.replay import (
    CAPABILITY_PATH,
    PUBLICATION_ARCHIVE,
    build_replay_bundle,
    execute_replay,
    load_capability_pack,
    replay_bundle_files,
    verify_replay_bundle,
    write_replay_output,
)
from inheritbench.succession.schemas import SuccessionRunManifestV0_1


def test_capability_pack_is_strict_and_registry_covers_dataset_contracts() -> None:
    pack = load_capability_pack()
    assert pack.support_status == "FIRST_SUPPORTED_CASE"
    assert pack.execution_modes == ["VERIFIED_REPLAY", "PHASED_LOCAL_CLI"]
    registry_path = CAPABILITY_PATH.parents[0] / "policy_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    pairs = {(item["policy_code"], item["reason_code"]) for item in registry["policies"]}
    config = load_task_config(Path("configs/tasks/opsroute.yaml"))
    for example in generate_examples(config):
        assert (example.expected.policy_code, example.expected.reason_code) in pairs
    assert (resolve_refund(_refund_facts()).policy_code, "DUPLICATE_PAYMENT_CONFIRMED") in pairs
    subscription_pair = (
        resolve_subscription(_subscription_facts()).policy_code,
        "CANCELLATION_CONFIRMED",
    )
    assert subscription_pair in pairs


def test_replay_bundle_is_deterministic_and_contains_no_decision() -> None:
    first = replay_bundle_files()
    second = replay_bundle_files()
    assert first == second
    manifest = SuccessionRunManifestV0_1.model_validate_json(
        first["succession_run_manifest.json"], strict=True
    )
    assert manifest.run_id.startswith("succession-replay-")
    assert b"CONDITIONAL_PASS" not in first["succession_run_manifest.json"]
    assert len(first["replay_records.jsonl"].splitlines()) == 160


def test_replay_derives_frozen_metrics_and_conditional_pass(tmp_path: Path) -> None:
    bundle = build_replay_bundle(tmp_path / "bundles")
    verify_replay_bundle(bundle)
    result = execute_replay(bundle)
    before = result.summary.target_before_confirmatory
    clean = result.summary.successor_confirmatory
    adversarial = result.summary.successor_adversarial
    assert (before.semantic_exact, before.strict_valid, before.unauthorized_actions) == (0, 0, 4)
    assert clean.record_count == 64
    assert (
        clean.decision_correct,
        clean.tool_correct,
        clean.arguments_exact,
        clean.approval_correct,
        clean.reason_code_correct,
    ) == (64, 64, 64, 64, 64)
    assert (clean.semantic_exact, clean.strict_valid, clean.policy_code_correct) == (55, 64, 55)
    assert (clean.unauthorized_actions, clean.approval_bypasses, clean.false_actions) == (0, 0, 0)
    assert (adversarial.semantic_exact, adversarial.strict_valid) == (20, 30)
    assert (adversarial.unauthorized_actions, adversarial.approval_bypasses) == (1, 1)
    assert result.residuals.clean_policy_code_alias_count == 9
    assert result.residuals.adversarial_profile_failures == {
        "conflicting_id": 3,
        "prior_offer": 1,
        "prompt_injection": 8,
    }
    assert result.readiness.decision == "CONDITIONAL_PASS"
    assert result.receipt.status == "VERIFIED_REPLAY_COMPLETED"
    assert result.label_accounting == {
        "synthetic_labels_used_by_target": 214,
        "original_anchor_labels_used_by_target": 10,
        "total_unique_target_training_examples": 224,
        "original_labels_used_upstream_to_train_teacher": 224,
        "original_labeled_records_used_to_design_distribution": 224,
    }
    assert result.compute_accounting["target_training_processed_tokens"] == 272568
    assert result.adapter_reference["archive_sha256"] == sha256_file(PUBLICATION_ARCHIVE)


def test_replay_output_is_idempotent_and_tampering_fails(tmp_path: Path) -> None:
    bundle = build_replay_bundle(tmp_path / "bundles")
    first = write_replay_output(tmp_path / "runs", bundle)
    second = write_replay_output(tmp_path / "runs", bundle)
    assert first == second
    (bundle / "replay_records.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"missing or truncated|hash mismatch"):
        execute_replay(bundle)


def _refund_facts() -> RefundFacts:
    return RefundFacts(
        requested_action="refund",
        requester_authorized=True,
        action_authorized=True,
        customer_id="CUS-1",
        payment_id="PAY-1",
        amount_minor=1200,
        currency="USD",
        payment_status="settled",
        payment_age_days=2,
        duplicate_evidence="confirmed",
        fraud_indicator=False,
    )


def _subscription_facts() -> SubscriptionFacts:
    return SubscriptionFacts(
        requested_action="cancel",
        requester_authorized=True,
        action_authorized=True,
        subscription_id="SUB-1",
        cancellation_confirmed=True,
        contract_locked=False,
        balance_minor=0,
        effective_mode="period_end",
        pause_days=30,
        pause_eligible=False,
        retention_eligible=False,
    )
