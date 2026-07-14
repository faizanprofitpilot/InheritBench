"""Sequential pinned Transformers model loading."""

from __future__ import annotations

import gc
from dataclasses import dataclass
from typing import Any

from inheritbench.config import ModelConfig


@dataclass
class LoadedModel:
    model: Any
    tokenizer: Any
    device: str
    dtype: str


def resolve_device(requested: str) -> str:
    import torch

    if requested != "auto":
        if requested == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is unavailable")
        if requested == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS was requested but is unavailable")
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def resolve_dtype(requested: str, device: str) -> tuple[Any, str]:
    import torch

    if requested == "float32":
        return torch.float32, "float32"
    if requested == "float16":
        return torch.float16, "float16"
    if requested == "bfloat16":
        return torch.bfloat16, "bfloat16"
    if device == "cuda":
        if torch.cuda.is_bf16_supported():
            return torch.bfloat16, "bfloat16"
        return torch.float16, "float16"
    if device == "mps":
        return torch.float16, "float16"
    return torch.float32, "float32"


def load_model(config: ModelConfig, *, device_override: str | None = None) -> LoadedModel:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = resolve_device(device_override or config.device_policy)
    torch_dtype, dtype_name = resolve_dtype(config.requested_dtype, device)
    auto_tokenizer: Any = AutoTokenizer
    tokenizer = auto_tokenizer.from_pretrained(
        config.tokenizer_id,
        revision=config.tokenizer_revision,
        trust_remote_code=False,
    )
    if config.chat_template_strategy == "native" and not tokenizer.chat_template:
        raise RuntimeError(f"{config.model_id} tokenizer has no native chat template")
    if tokenizer.pad_token_id is None and config.special_tokens.pad_strategy == "eos_if_missing":
        if tokenizer.eos_token_id is None:
            raise RuntimeError("tokenizer has neither a pad token nor an EOS token")
        tokenizer.pad_token = tokenizer.eos_token

    auto_model: Any = AutoModelForCausalLM
    model: Any = auto_model.from_pretrained(
        config.model_id,
        revision=config.revision,
        trust_remote_code=False,
        dtype=torch_dtype,
        attn_implementation=config.attention_implementation,
        low_cpu_mem_usage=True,
    )
    model.to(device)
    model.eval()
    model.generation_config.do_sample = False
    model.generation_config.temperature = None
    model.generation_config.top_p = None
    model.generation_config.top_k = None
    return LoadedModel(model=model, tokenizer=tokenizer, device=device, dtype=dtype_name)


def unload_model(loaded: LoadedModel) -> None:
    import torch

    del loaded.model
    del loaded.tokenizer
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
