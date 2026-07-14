import os
from pathlib import Path

import pytest

from inheritbench.config import load_model_config
from inheritbench.models.loader import load_model, unload_model


@pytest.mark.model_smoke
def test_real_models_load_sequentially() -> None:
    if os.getenv("INHERITBENCH_RUN_MODEL_SMOKE") != "1":
        pytest.skip("set INHERITBENCH_RUN_MODEL_SMOKE=1 for real model loading")
    for path in (Path("configs/models/source.yaml"), Path("configs/models/target.yaml")):
        loaded = load_model(load_model_config(path), device_override="auto")
        assert type(loaded.model).__name__
        unload_model(loaded)
