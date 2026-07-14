"""Metadata and loaded pair inspection with narrow compatibility verdicts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.artifacts.store import write_atomic_file
from inheritbench.config import ModelConfig, Sha256
from inheritbench.models.loader import load_model, unload_model


class InspectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class InspectedModel(InspectionModel):
    model_id: str
    revision: str
    expected_architecture_class: str
    architecture_class: str | None
    model_type: str | None
    parameter_count: int | None
    hidden_size: int | None
    num_hidden_layers: int | None
    num_attention_heads: int | None
    num_key_value_heads: int | None
    vocabulary_size: int | None
    maximum_position_embeddings: int | None
    tie_word_embeddings: bool | None
    tokenizer_class: str | None
    chat_template_available: bool | None
    special_token_ids: dict[str, int | None]
    linear_modules: dict[str, list[int]]
    target_module_shapes: dict[str, list[list[int]]]


class PairComparisons(InspectionModel):
    same_architecture_class: bool | None
    same_model_type: bool | None
    same_hidden_size: bool | None
    same_tokenizer_class: bool | None
    same_vocabulary_size: bool | None
    target_module_shape_matches: dict[str, bool | None]


class PairInspectionResult(InspectionModel):
    schema_version: Literal["pair-inspection-v0.1"]
    inspector_version: Literal["0.1.0"]
    inspection_mode: Literal["metadata", "loaded"]
    source: InspectedModel
    target: InspectedModel
    comparisons: PairComparisons
    heterogeneity_verdict: Literal[
        "CONFIRMED",
        "NOT_CONFIRMED",
        "INSUFFICIENT_EVIDENCE",
    ]
    direct_adapter_reuse: Literal[
        "STRUCTURALLY_INCOMPATIBLE",
        "NO_STRUCTURAL_MISMATCH_DETECTED",
        "NOT_ASSESSED",
    ]
    evidence: list[str]
    warnings: list[str]
    content_sha256: Sha256


def inspect_pair(
    source_config: ModelConfig,
    target_config: ModelConfig,
    *,
    mode: Literal["metadata", "loaded"],
    device_override: str | None = None,
) -> PairInspectionResult:
    if mode == "loaded":
        source = _inspect_loaded(source_config, device_override=device_override)
        target = _inspect_loaded(target_config, device_override=device_override)
    else:
        source = _inspect_metadata(source_config)
        target = _inspect_metadata(target_config)

    warnings: list[str] = []
    for name, config, inspected in (
        ("source", source_config, source),
        ("target", target_config, target),
    ):
        if inspected.architecture_class != config.expected_architecture_class:
            warnings.append(
                f"{name} expected {config.expected_architecture_class} but observed "
                f"{inspected.architecture_class}"
            )
        if not inspected.chat_template_available:
            warnings.append(f"{name} tokenizer has no native chat template")

    shape_matches = _shape_comparisons(source_config, source, target)
    comparisons = PairComparisons(
        same_architecture_class=_same(source.architecture_class, target.architecture_class),
        same_model_type=_same(source.model_type, target.model_type),
        same_hidden_size=_same(source.hidden_size, target.hidden_size),
        same_tokenizer_class=_same(source.tokenizer_class, target.tokenizer_class),
        same_vocabulary_size=_same(source.vocabulary_size, target.vocabulary_size),
        target_module_shape_matches=shape_matches,
    )
    structural_differences = [
        source.hidden_size != target.hidden_size,
        source.num_hidden_layers != target.num_hidden_layers,
        source.num_attention_heads != target.num_attention_heads,
        source.num_key_value_heads != target.num_key_value_heads,
        source.vocabulary_size != target.vocabulary_size,
    ]
    if source.architecture_class is None or target.architecture_class is None:
        heterogeneity = "INSUFFICIENT_EVIDENCE"
    elif (
        source.architecture_class != target.architecture_class
        and source.model_type != target.model_type
        and any(structural_differences)
    ):
        heterogeneity = "CONFIRMED"
    else:
        heterogeneity = "NOT_CONFIRMED"

    if mode == "metadata":
        adapter_verdict = "NOT_ASSESSED"
    elif any(value is False for value in shape_matches.values()):
        adapter_verdict = "STRUCTURALLY_INCOMPATIBLE"
    elif shape_matches and all(value is True for value in shape_matches.values()):
        adapter_verdict = "NO_STRUCTURAL_MISMATCH_DETECTED"
    else:
        adapter_verdict = "NOT_ASSESSED"

    evidence = [
        f"architecture: {source.architecture_class} -> {target.architecture_class}",
        f"model_type: {source.model_type} -> {target.model_type}",
        f"hidden_size: {source.hidden_size} -> {target.hidden_size}",
        f"layers: {source.num_hidden_layers} -> {target.num_hidden_layers}",
        f"attention_heads: {source.num_attention_heads} -> {target.num_attention_heads}",
        f"vocabulary_size: {source.vocabulary_size} -> {target.vocabulary_size}",
    ]
    payload = {
        "schema_version": "pair-inspection-v0.1",
        "inspector_version": "0.1.0",
        "inspection_mode": mode,
        "source": source.model_dump(mode="json"),
        "target": target.model_dump(mode="json"),
        "comparisons": comparisons.model_dump(mode="json"),
        "heterogeneity_verdict": heterogeneity,
        "direct_adapter_reuse": adapter_verdict,
        "evidence": evidence,
        "warnings": warnings,
    }
    return PairInspectionResult.model_validate(
        {**payload, "content_sha256": content_sha256(payload)}, strict=True
    )


def _inspect_metadata(config: ModelConfig) -> InspectedModel:
    from transformers import AutoConfig, AutoTokenizer

    model_config = AutoConfig.from_pretrained(
        config.model_id,
        revision=config.revision,
        trust_remote_code=False,
    )
    auto_tokenizer: Any = AutoTokenizer
    tokenizer = auto_tokenizer.from_pretrained(
        config.tokenizer_id,
        revision=config.tokenizer_revision,
        trust_remote_code=False,
    )
    return _build_inspected(config, model_config, tokenizer, model=None)


def _inspect_loaded(config: ModelConfig, *, device_override: str | None) -> InspectedModel:
    loaded = load_model(config, device_override=device_override)
    try:
        return _build_inspected(config, loaded.model.config, loaded.tokenizer, model=loaded.model)
    finally:
        unload_model(loaded)


def _build_inspected(
    config: ModelConfig, model_config: Any, tokenizer: Any, *, model: Any | None
) -> InspectedModel:
    architectures = getattr(model_config, "architectures", None)
    architecture_class = (
        type(model).__name__
        if model is not None
        else architectures[0]
        if isinstance(architectures, list) and architectures
        else None
    )
    linear_modules: dict[str, list[int]] = {}
    parameter_count: int | None = None
    if model is not None:
        import torch

        parameter_count = sum(parameter.numel() for parameter in model.parameters())
        for name, module in model.named_modules():
            if isinstance(module, torch.nn.Linear):
                linear_modules[name] = list(module.weight.shape)
    target_shapes = {
        suffix: sorted(
            {tuple(shape) for name, shape in linear_modules.items() if name.endswith(suffix)}
        )
        for suffix in config.intended_lora_target_modules
    }
    return InspectedModel(
        model_id=config.model_id,
        revision=config.revision,
        expected_architecture_class=config.expected_architecture_class,
        architecture_class=architecture_class,
        model_type=_optional_str(getattr(model_config, "model_type", None)),
        parameter_count=parameter_count,
        hidden_size=_optional_int(getattr(model_config, "hidden_size", None)),
        num_hidden_layers=_optional_int(getattr(model_config, "num_hidden_layers", None)),
        num_attention_heads=_optional_int(getattr(model_config, "num_attention_heads", None)),
        num_key_value_heads=_optional_int(getattr(model_config, "num_key_value_heads", None)),
        vocabulary_size=_optional_int(getattr(model_config, "vocab_size", None)),
        maximum_position_embeddings=_optional_int(
            getattr(model_config, "max_position_embeddings", None)
        ),
        tie_word_embeddings=_optional_bool(getattr(model_config, "tie_word_embeddings", None)),
        tokenizer_class=type(tokenizer).__name__,
        chat_template_available=bool(getattr(tokenizer, "chat_template", None)),
        special_token_ids={
            "bos_token_id": _optional_int(getattr(tokenizer, "bos_token_id", None)),
            "eos_token_id": _optional_int(getattr(tokenizer, "eos_token_id", None)),
            "pad_token_id": _optional_int(getattr(tokenizer, "pad_token_id", None)),
            "unk_token_id": _optional_int(getattr(tokenizer, "unk_token_id", None)),
        },
        linear_modules=linear_modules,
        target_module_shapes={
            suffix: [list(shape) for shape in shapes] for suffix, shapes in target_shapes.items()
        },
    )


def _shape_comparisons(
    source_config: ModelConfig, source: InspectedModel, target: InspectedModel
) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {}
    for suffix in source_config.intended_lora_target_modules:
        source_shapes = source.target_module_shapes.get(suffix, [])
        target_shapes = target.target_module_shapes.get(suffix, [])
        if not source_shapes and not target_shapes:
            result[suffix] = None
        elif not source_shapes or not target_shapes:
            result[suffix] = False
        else:
            result[suffix] = source_shapes == target_shapes
    return result


def _same(left: Any | None, right: Any | None) -> bool | None:
    return None if left is None or right is None else left == right


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, int) else None


def _optional_str(value: Any) -> str | None:
    return str(value) if isinstance(value, str) else None


def _optional_bool(value: Any) -> bool | None:
    return bool(value) if isinstance(value, bool) else None


def write_inspection(result: PairInspectionResult, output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"{result.content_sha256}.json"
    payload = canonical_json_bytes(result) + b"\n"
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"inspection hash collision at {path}")
        return path
    write_atomic_file(path, payload)
    return path
