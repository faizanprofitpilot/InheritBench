"""Stage-scoped access to pack data and evaluator-only oracles."""

from __future__ import annotations

from inheritbench.capability.loader import LoadedCapabilityPack
from inheritbench.capability.schemas import (
    CapabilityInputRecord,
    CapabilityLabeledRecord,
    CapabilityOracleRecord,
)

_ORACLE_STAGES = {
    "SOURCE_GATE_COMPLETED": {"source_gate"},
    "TARGET_BASELINE_COMPLETED": {"source_gate"},
    "SUPERVISION_PREPARING": {"transfer_pool"},
    "CHECKPOINT_SELECTED": {"source_gate", "validation"},
    "CONFIRMATORY_COMPLETED": {"confirmatory"},
    "ADVERSARIAL_COMPLETED": {"adversarial"},
}


class StageDataBroker:
    def __init__(self, pack: LoadedCapabilityPack, stage: str) -> None:
        self._pack = pack
        self._stage = stage

    def inputs(self, surface: str) -> list[CapabilityInputRecord]:
        if surface not in self._pack.inputs:
            raise ValueError(f"unknown surface {surface}")
        if self._stage in {"TRAINING", "SUPERVISION_FROZEN"} and surface in {
            "validation",
            "confirmatory",
            "adversarial",
        }:
            raise PermissionError(f"{self._stage} cannot access {surface} inputs")
        return self._pack.inputs[surface]

    def oracles(self, surface: str) -> list[CapabilityOracleRecord]:
        permitted = _ORACLE_STAGES.get(self._stage, set())
        if surface not in permitted:
            raise PermissionError(f"{self._stage} cannot access {surface} oracles")
        return self._pack.oracles[surface]

    def direct_training(self) -> list[CapabilityLabeledRecord]:
        if self._stage != "SUPERVISION_PREPARING":
            raise PermissionError(f"{self._stage} cannot access direct training labels")
        return self._pack.direct_train

    def anchors(self) -> list[CapabilityLabeledRecord]:
        if self._stage != "SUPERVISION_PREPARING":
            raise PermissionError(f"{self._stage} cannot access anchors")
        return self._pack.anchors
