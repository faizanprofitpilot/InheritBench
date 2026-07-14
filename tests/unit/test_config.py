from pathlib import Path

import pytest
from pydantic import ValidationError

from inheritbench.config import ModelConfig, load_model_config, load_task_config


def test_committed_configs_are_strict_and_valid() -> None:
    source = load_model_config(Path("configs/models/source.yaml"))
    target = load_model_config(Path("configs/models/target.yaml"))
    task = load_task_config(Path("configs/tasks/opsroute.yaml"))

    assert source.revision == "7ae557604adf67be50417f59c2c2f167def9a775"
    assert target.expected_architecture_class == "Olmo2ForCausalLM"
    assert task.families == [
        "refund_policy_routing",
        "subscription_cancellation_retention",
    ]


def test_extra_config_field_is_rejected() -> None:
    raw = load_model_config(Path("configs/models/source.yaml")).model_dump(mode="python")
    raw["unknown"] = True
    with pytest.raises(ValidationError):
        ModelConfig.model_validate(raw, strict=True)


def test_short_revision_is_rejected() -> None:
    raw = load_model_config(Path("configs/models/source.yaml")).model_dump(mode="python")
    raw["revision"] = "abc123"
    with pytest.raises(ValidationError):
        ModelConfig.model_validate(raw, strict=True)
