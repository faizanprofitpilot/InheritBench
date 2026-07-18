from __future__ import annotations

import pytest
import torch

from inheritbench.model_adapters.huggingface import (
    _clip_and_validate_gradients,
    _require_finite_optimizer_state,
    _require_finite_parameters,
)


def test_finite_large_preclip_norm_is_clipped_not_rejected() -> None:
    parameter = torch.nn.Parameter(torch.tensor([10_000.0]))
    parameter.grad = torch.tensor([10_000.0])

    pre_clip, post_clip = _clip_and_validate_gradients([parameter], 1.0)

    assert pre_clip == 10_000.0
    assert post_clip <= 1.0 + 1e-6


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_gradient_still_terminates(value: float) -> None:
    parameter = torch.nn.Parameter(torch.tensor([1.0]))
    parameter.grad = torch.tensor([value])
    with pytest.raises(FloatingPointError, match="non-finite pre-clip"):
        _clip_and_validate_gradients([parameter], 1.0)


def test_nonfinite_parameter_and_optimizer_state_terminate() -> None:
    parameter = torch.nn.Parameter(torch.tensor([float("nan")]))
    with pytest.raises(FloatingPointError, match="non-finite trainable parameter"):
        _require_finite_parameters([parameter], "test")

    clean = torch.nn.Parameter(torch.tensor([1.0]))
    optimizer = torch.optim.AdamW([clean])
    optimizer.state[clean]["bad"] = torch.tensor([float("inf")])
    with pytest.raises(FloatingPointError, match="non-finite optimizer state"):
        _require_finite_optimizer_state(optimizer, "test")
