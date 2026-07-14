"""Strict configuration models and YAML loading."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

FullCommitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ScenarioFamily = Literal[
    "refund_policy_routing",
    "subscription_cancellation_retention",
]


class StrictModel(BaseModel):
    """Base model for immutable, non-coercing configuration."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SpecialTokensConfig(StrictModel):
    pad_strategy: Literal["tokenizer_default", "eos_if_missing"]
    use_default_bos: bool
    use_default_eos: bool
    add_new_tokens: Literal[False]


class ModelLicenseConfig(StrictModel):
    spdx: Literal["Apache-2.0"]
    review_status: Literal["reviewed", "pending", "blocked"]
    access: Literal["public", "gated", "private"]
    source_url: HttpUrl


class ModelConfig(StrictModel):
    schema_version: Literal["model-config-v0.1"]
    internal_name: str
    role: Literal["source", "target", "fallback_target"]
    selection_status: Literal["provisional", "accepted", "rejected"]
    model_id: str
    revision: FullCommitSha
    expected_architecture_class: str
    model_family: str
    tokenizer_id: str
    tokenizer_revision: FullCommitSha
    trust_remote_code: Literal[False]
    chat_template_strategy: Literal["native", "explicit"]
    explicit_chat_template_path: Path | None
    requested_dtype: Literal["auto", "float32", "float16", "bfloat16"]
    device_policy: Literal["auto", "cpu", "mps", "cuda"]
    quantization: Literal["none"]
    attention_implementation: Literal["eager"]
    maximum_sequence_length: Literal[1024]
    special_tokens: SpecialTokensConfig
    license: ModelLicenseConfig
    intended_lora_target_modules: list[str] = Field(min_length=1)
    lora_target_status: Literal["provisional", "inspected"]

    @model_validator(mode="after")
    def validate_template(self) -> ModelConfig:
        if self.chat_template_strategy == "native" and self.explicit_chat_template_path is not None:
            raise ValueError("native chat templates cannot declare an explicit template path")
        if self.chat_template_strategy == "explicit" and self.explicit_chat_template_path is None:
            raise ValueError("explicit chat templates require a template path")
        return self


class SplitCountsPerArchetype(StrictModel):
    train: Literal[14]
    validation: Literal[2]
    test: Literal[2]
    adversarial: Literal[2]


class OpsRouteTaskConfig(StrictModel):
    schema_version: Literal["task-config-v0.1"]
    task_id: Literal["opsroute"]
    task_version: Literal["0.1.0"]
    generator_version: Literal["0.1.0"]
    template_version: Literal["0.1.0"]
    prompt_template_version: Literal["0.1.0", "0.1.1"]
    output_contract_version: Literal["0.1.0"]
    seed: Literal[20260714]
    families: list[ScenarioFamily]
    variants_per_archetype: Literal[20]
    split_counts_per_archetype: SplitCountsPerArchetype
    currency: Literal["USD"]
    refund_auto_approval_limit_minor: Literal[5000]
    refund_window_days: Literal[30]
    cancellation_balance_approval_limit_minor: Literal[10000]
    allowed_pause_days: list[Literal[30, 60, 90]]
    retention_offer_code: Literal["SAVE10_3MO"]
    maximum_prompt_tokens: Literal[1024]
    maximum_new_tokens: Literal[256]

    @model_validator(mode="after")
    def validate_locked_collections(self) -> OpsRouteTaskConfig:
        expected_families = [
            "refund_policy_routing",
            "subscription_cancellation_retention",
        ]
        if self.families != expected_families:
            raise ValueError(f"families must be exactly {expected_families}")
        if self.allowed_pause_days != [30, 60, 90]:
            raise ValueError("allowed_pause_days must be exactly [30, 60, 90]")
        return self


def load_yaml(path: Path) -> object:
    """Load YAML without executable constructors."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except OSError as exc:
        raise ValueError(f"unable to read configuration {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc


def load_model_config(path: Path) -> ModelConfig:
    return ModelConfig.model_validate(load_yaml(path), strict=True)


def load_task_config(path: Path) -> OpsRouteTaskConfig:
    return OpsRouteTaskConfig.model_validate(load_yaml(path), strict=True)
