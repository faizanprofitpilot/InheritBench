from __future__ import annotations

from pathlib import Path

import pytest

from inheritbench.config import OpsRouteTaskConfig, load_task_config
from inheritbench.data.opsroute.schemas import EvaluationMetadata
from inheritbench.evaluation.contracts import ActionContract


@pytest.fixture
def task_config() -> OpsRouteTaskConfig:
    return load_task_config(Path("configs/tasks/opsroute.yaml"))


@pytest.fixture
def no_action_contract() -> ActionContract:
    return ActionContract(
        decision="no_action",
        tool=None,
        arguments={},
        approval_required=False,
        policy_code="FIN-NOACT-01",
        reason_code="NO_REFUND_ACTION_REQUESTED",
    )


@pytest.fixture
def empty_evaluation() -> EvaluationMetadata:
    return EvaluationMetadata(
        authorized_tools=[],
        allowed_argument_values={},
        tags=[],
    )
