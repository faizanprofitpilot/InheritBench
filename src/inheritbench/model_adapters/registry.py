"""Explicit registry for supported source and target architectures."""

from __future__ import annotations

from dataclasses import dataclass

from inheritbench.config import ModelConfig
from inheritbench.model_adapters.base import ModelAdapter
from inheritbench.model_adapters.fake import FakeModelAdapter
from inheritbench.model_adapters.huggingface import HuggingFaceCausalLMAdapter


@dataclass(frozen=True)
class RegistryEntry:
    registry_id: str
    model_id: str
    revision: str
    adapter: ModelAdapter


class ModelRegistry:
    def __init__(self, entries: list[RegistryEntry]) -> None:
        self._entries = {entry.registry_id: entry for entry in entries}

    def resolve(self, registry_id: str, config: ModelConfig) -> ModelAdapter:
        try:
            entry = self._entries[registry_id]
        except KeyError:
            raise ValueError(f"UNSUPPORTED_MODEL_ARCHITECTURE: {registry_id}") from None
        if entry.model_id != config.model_id or entry.revision != config.revision:
            raise ValueError("model config does not match registered identity")
        return entry.adapter

    def registry_id_for(self, config: ModelConfig) -> str:
        matches = [
            entry.registry_id
            for entry in self._entries.values()
            if entry.model_id == config.model_id and entry.revision == config.revision
        ]
        if len(matches) != 1:
            raise ValueError(f"UNSUPPORTED_MODEL_ARCHITECTURE: {config.model_id}")
        return matches[0]


def default_registry() -> ModelRegistry:
    qwen = HuggingFaceCausalLMAdapter(
        "qwen2.5-0.5b-instruct-v0.1",
        expected_model_id="Qwen/Qwen2.5-0.5B-Instruct",
        expected_revision="7ae557604adf67be50417f59c2c2f167def9a775",
        architecture_class="Qwen2ForCausalLM",
        lora_targets=("q_proj", "k_proj", "v_proj", "o_proj"),
    )
    olmo = HuggingFaceCausalLMAdapter(
        "olmo2-1b-instruct-v0.1",
        expected_model_id="allenai/OLMo-2-0425-1B-Instruct",
        expected_revision="48d788eca847d4d7548f375ad03d3c9312f6139e",
        architecture_class="Olmo2ForCausalLM",
        lora_targets=("q_proj", "k_proj", "v_proj", "o_proj"),
    )
    return ModelRegistry(
        [
            RegistryEntry(
                "qwen2.5-0.5b-instruct-v0.1",
                qwen.expected_model_id,
                qwen.expected_revision,
                qwen,
            ),
            RegistryEntry(
                "olmo2-1b-instruct-v0.1",
                olmo.expected_model_id,
                olmo.expected_revision,
                olmo,
            ),
            RegistryEntry(
                "fake-source-v0.1",
                "inheritbench/fake-source",
                "0" * 40,
                FakeModelAdapter("fake-source-v0.1"),
            ),
            RegistryEntry(
                "fake-target-v0.1",
                "inheritbench/fake-target",
                "1" * 40,
                FakeModelAdapter("fake-target-v0.1"),
            ),
        ]
    )
