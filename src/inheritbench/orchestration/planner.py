"""Deterministic succession planning without model execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from inheritbench.artifacts.hashing import (
    canonical_json_bytes,
    content_sha256,
    sha256_file,
)
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.capability.loader import load_capability_pack
from inheritbench.config import load_model_config
from inheritbench.model_adapters.registry import default_registry
from inheritbench.orchestration.schemas import (
    AdapterBinding,
    AuthorizedAnchorPoolBinding,
    PlannedInput,
    ProtocolAmendmentBinding,
    SuccessionPlan,
)

_ORDER = [
    "PACK_VALIDATED",
    "MODELS_PREFLIGHTED",
    "PLAN_FROZEN",
    "SOURCE_GATE_COMPLETED",
    "TARGET_BASELINE_COMPLETED",
    "SUPERVISION_PREPARING",
    "SUPERVISION_FROZEN",
    "TRAINING",
    "CHECKPOINT_SELECTED",
    "CONFIRMATORY_COMPLETED",
    "ADVERSARIAL_COMPLETED",
    "READINESS_FINALIZED",
    "ADAPTER_EXPORTED",
    "COMPLETED",
]

_V03_ORDER = [
    "PACK_VALIDATED",
    "MODELS_PREFLIGHTED",
    "PLAN_FROZEN",
    "SOURCE_GATE_COMPLETED",
    "TARGET_BASELINE_COMPLETED",
    "SUPERVISION_PREPARING",
    "TEACHER_OUTPUTS_EVALUATED",
    "ANCHORS_REQUIRED",
    "ANCHORS_ADDED",
    "SUPERVISION_FROZEN",
    "TRAINING",
    "CHECKPOINT_SELECTED",
    "CANDIDATE_FROZEN",
    "CONFIRMATORY_COMPLETED",
    "ADVERSARIAL_COMPLETED",
    "READINESS_FINALIZED",
    "ADAPTER_EXPORTED",
    "RELOAD_VERIFIED",
    "REPLAY_VERIFIED",
    "COMPLETED",
]


def create_plan(
    *,
    pack_root: Path,
    source_config_path: Path,
    target_config_path: Path,
    strategy_id: str,
    output_root: Path,
    device: Literal["mps", "cpu", "cuda"],
    source_adapter_path: Path | None = None,
    product_run_kind: Literal[
        "STANDARD",
        "PRODUCT_INTEGRATION_RUN",
        "PRODUCT_PARITY_RUN",
        "PRODUCT_REFERENCE_SUCCESSION",
    ] = "STANDARD",
    allow_fixture: bool = False,
    protocol_amendment_path: Path | None = None,
    authorized_anchor_pool_path: Path | None = None,
    replication_group_id: str | None = None,
    replication_index: int = 0,
) -> Path:
    pack = load_capability_pack(
        pack_root,
        allow_fixture=allow_fixture,
        require_executable=True,
    )
    profile = next(
        (item for item in pack.config.strategies if item.strategy_id == strategy_id),
        None,
    )
    if profile is None:
        raise ValueError(f"strategy {strategy_id} is not declared by the pack")
    source_config = load_model_config(source_config_path)
    target_config = load_model_config(target_config_path)
    registry = default_registry()
    source_registry_id = registry.registry_id_for(source_config)
    target_registry_id = registry.registry_id_for(target_config)
    if source_registry_id not in pack.config.models.source_registry_ids:
        raise ValueError("source model is not allowed by the capability pack")
    if target_registry_id not in pack.config.models.target_registry_ids:
        raise ValueError("target model is not allowed by the capability pack")
    source_binding = None
    if source_adapter_path is None and pack.config.models.default_source_adapter_path is not None:
        source_adapter_path = (
            Path.cwd() / pack.config.models.default_source_adapter_path
        ).resolve()
    if source_adapter_path is not None:
        adapter_file = _adapter_file(source_adapter_path)
        expected_adapter_sha = pack.config.models.default_source_adapter_sha256
        actual_adapter_sha = sha256_file(adapter_file)
        if expected_adapter_sha is not None and actual_adapter_sha != expected_adapter_sha:
            raise ValueError("default source adapter hash does not match capability pack")
        source_binding = AdapterBinding(
            relative_path=str(source_adapter_path.resolve()),
            adapter_sha256=actual_adapter_sha,
        )
    planned_inputs = [
        PlannedInput(
            relative_path=str((pack.root / relative).resolve()),
            bytes=(pack.root / relative).stat().st_size,
            byte_sha256=digest,
        )
        for relative, digest in sorted(pack.file_sha256s.items())
    ]
    amendment = (
        _protocol_amendment_binding(protocol_amendment_path)
        if protocol_amendment_path is not None
        else None
    )
    anchor_pool = (
        _anchor_pool_binding(
            authorized_anchor_pool_path,
            ranking_namespace=profile.anchor_selection_namespace or profile.selection_namespace,
        )
        if authorized_anchor_pool_path is not None
        else None
    )
    if amendment is None and anchor_pool is not None:
        raise ValueError("authorized anchor pools require a protocol amendment")
    if (
        amendment is not None
        and strategy_id == "anchored-behavioral-transfer-v0.1"
        and anchor_pool is None
    ):
        raise ValueError("amendment-bound anchored plans require an anchor pool")
    schema_version = (
        "inheritbench.succession-plan.v0.3"
        if amendment is not None
        else "inheritbench.succession-plan.v0.2"
    )
    body: dict[str, Any] = {
        "schema_version": schema_version,
        "execution_engine_version": (
            "inheritbench-generic-succession-v0.3.0"
            if amendment is not None
            else "inheritbench-generic-succession-v0.2.2"
        ),
        "run_id": "pending",
        "product_run_kind": product_run_kind,
        "pack_root": str(pack.root),
        "pack_validation_sha256": pack.validation.content_sha256,
        "capability_id": pack.config.capability.id,
        "capability_version": pack.config.capability.version,
        "strategy_id": strategy_id,
        "source_config_path": str(source_config_path.resolve()),
        "source_config_sha256": sha256_file(source_config_path),
        "source_registry_id": source_registry_id,
        "source_adapter": source_binding,
        "target_config_path": str(target_config_path.resolve()),
        "target_config_sha256": sha256_file(target_config_path),
        "target_registry_id": target_registry_id,
        "device": device,
        "seed": pack.config.seed,
        "authorized_inputs": planned_inputs,
        "strategy_profile": profile.model_dump(mode="json"),
        "operation_order": _V03_ORDER if amendment is not None else _ORDER,
    }
    if amendment is not None:
        canonical_sha = canonical_training_plan_sha256(
            body,
            authorized_anchor_pool=anchor_pool,
        )
        group_id = replication_group_id or f"{pack.config.capability.id}-{strategy_id}-v0.1"
        execution_sha = content_sha256(
            {
                "canonical_plan_sha256": canonical_sha,
                "protocol_amendment_sha256": amendment.amendment_sha256,
                "replication_group_id": group_id,
                "replication_index": replication_index,
            }
        )
        execution_id = (
            f"succession-{pack.config.capability.id}-{strategy_id}-"
            f"{replication_index:02d}-{execution_sha[:16]}"
        )
        body.update(
            {
                "canonical_plan_id": (
                    f"canonical-{pack.config.capability.id}-{strategy_id}-{canonical_sha[:16]}"
                ),
                "canonical_plan_sha256": canonical_sha,
                "execution_id": execution_id,
                "replication_group_id": group_id,
                "replication_index": replication_index,
                "protocol_amendment": amendment,
                "authorized_anchor_pool": anchor_pool,
            }
        )
        body["run_id"] = execution_id
    else:
        plan_hash = content_sha256(body, excluded_keys={"run_id", "plan_sha256"})
        body["run_id"] = f"succession-{pack.config.capability.id}-{strategy_id}-{plan_hash[:16]}"
    body["plan_sha256"] = content_sha256(body, excluded_keys={"plan_sha256"})
    plan = SuccessionPlan.model_validate(body, strict=True)
    return write_atomic_bundle(
        output_root,
        plan.run_id,
        {
            "plan.json": canonical_json_bytes(plan) + b"\n",
            "plan.sha256": (plan.plan_sha256 + "\n").encode(),
            "input_manifest.json": canonical_json_bytes(
                {
                    "run_id": plan.run_id,
                    "canonical_plan_id": plan.canonical_plan_id,
                    "execution_id": plan.execution_id,
                    "inputs": plan.authorized_inputs,
                    "authorized_anchor_pool": plan.authorized_anchor_pool,
                }
            )
            + b"\n",
            **(
                {
                    "protocol_amendment_reference.json": canonical_json_bytes(
                        plan.protocol_amendment
                    )
                    + b"\n"
                }
                if plan.protocol_amendment is not None
                else {}
            ),
        },
    )


def replicate_plan(
    *,
    reference_run: Path,
    output_root: Path,
    protocol_amendment_path: Path,
    replication_group_id: str,
    replication_index: int,
) -> Path:
    from inheritbench.orchestration.storage import load_plan

    reference = load_plan(reference_run)
    if reference.strategy_id != "direct-target-lora-v0.1":
        raise ValueError("seeded replication currently supports direct-target-lora only")
    if reference.product_run_kind != "PRODUCT_PARITY_RUN":
        raise ValueError("reference run is not a direct product-parity run")
    return create_plan(
        pack_root=Path(reference.pack_root),
        source_config_path=Path(reference.source_config_path),
        target_config_path=Path(reference.target_config_path),
        strategy_id=reference.strategy_id,
        output_root=output_root,
        device=reference.device,
        source_adapter_path=(
            Path(reference.source_adapter.relative_path)
            if reference.source_adapter is not None
            else None
        ),
        product_run_kind="PRODUCT_PARITY_RUN",
        protocol_amendment_path=protocol_amendment_path,
        replication_group_id=replication_group_id,
        replication_index=replication_index,
    )


def canonical_training_plan_sha256(
    body: dict[str, Any],
    *,
    authorized_anchor_pool: AuthorizedAnchorPoolBinding | None,
) -> str:
    source_adapter = body.get("source_adapter")
    if isinstance(source_adapter, AdapterBinding):
        source_adapter = source_adapter.model_dump(mode="json")
    anchor_identity = None
    if authorized_anchor_pool is not None:
        anchor_identity = {
            "byte_sha256": authorized_anchor_pool.byte_sha256,
            "records": authorized_anchor_pool.records,
            "records_sha256": authorized_anchor_pool.records_sha256,
            "ranking_namespace": authorized_anchor_pool.ranking_namespace,
        }
    return content_sha256(
        {
            "protocol_version": "seeded-lora-reference-v0.1",
            "pack_validation_sha256": body["pack_validation_sha256"],
            "capability_id": body["capability_id"],
            "capability_version": body["capability_version"],
            "strategy_id": body["strategy_id"],
            "source_config_sha256": body["source_config_sha256"],
            "source_registry_id": body["source_registry_id"],
            "source_adapter": source_adapter,
            "target_config_sha256": body["target_config_sha256"],
            "target_registry_id": body["target_registry_id"],
            "device": body["device"],
            "seed": body["seed"],
            "authorized_inputs": body["authorized_inputs"],
            "strategy_profile": body["strategy_profile"],
            "authorized_anchor_pool": anchor_identity,
        }
    )


def verify_plan_inputs(plan: SuccessionPlan) -> None:
    for item in plan.authorized_inputs:
        path = Path(item.relative_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size != item.bytes or sha256_file(path) != item.byte_sha256:
            raise ValueError(f"planned input changed: {path}")
    if sha256_file(Path(plan.source_config_path)) != plan.source_config_sha256:
        raise ValueError("source model config changed after planning")
    if sha256_file(Path(plan.target_config_path)) != plan.target_config_sha256:
        raise ValueError("target model config changed after planning")
    if (
        plan.source_adapter is not None
        and sha256_file(_adapter_file(Path(plan.source_adapter.relative_path)))
        != plan.source_adapter.adapter_sha256
    ):
        raise ValueError("source adapter changed after planning")
    if plan.protocol_amendment is not None:
        amendment_path = Path(plan.protocol_amendment.relative_path)
        if sha256_file(amendment_path) != plan.protocol_amendment.byte_sha256:
            raise ValueError("protocol amendment changed after planning")
    if plan.authorized_anchor_pool is not None:
        pool_path = Path(plan.authorized_anchor_pool.relative_path)
        if pool_path.stat().st_size != plan.authorized_anchor_pool.bytes:
            raise ValueError("authorized anchor-pool byte count changed after planning")
        if sha256_file(pool_path) != plan.authorized_anchor_pool.byte_sha256:
            raise ValueError("authorized anchor pool changed after planning")


def _adapter_file(path: Path) -> Path:
    for name in ("adapter_model.safetensors", "adapter_model.fake"):
        candidate = path / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"adapter payload not found in {path}")


def _protocol_amendment_binding(path: Path) -> ProtocolAmendmentBinding:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    amendment_id = payload.get("amendment_id")
    amendment_sha256 = payload.get("amendment_sha256")
    if not isinstance(amendment_id, str) or not isinstance(amendment_sha256, str):
        raise ValueError("protocol amendment lacks identity fields")
    stored = dict(payload)
    stored.pop("amendment_sha256", None)
    if content_sha256(stored) != amendment_sha256:
        raise ValueError("protocol amendment content hash mismatch")
    return ProtocolAmendmentBinding(
        amendment_id=amendment_id,
        relative_path=str(path.resolve()),
        byte_sha256=sha256_file(path),
        amendment_sha256=amendment_sha256,
    )


def _anchor_pool_binding(
    path: Path,
    *,
    ranking_namespace: str,
) -> AuthorizedAnchorPoolBinding:
    import json

    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not records:
        raise ValueError("authorized anchor pool is empty")
    return AuthorizedAnchorPoolBinding(
        relative_path=str(path.resolve()),
        bytes=path.stat().st_size,
        byte_sha256=sha256_file(path),
        records=len(records),
        records_sha256=content_sha256(records),
        ranking_namespace=ranking_namespace,
    )
