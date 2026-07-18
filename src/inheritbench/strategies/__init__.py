"""Task-neutral succession supervision strategies."""

from inheritbench.strategies.anchored import prepare_anchored_supervision
from inheritbench.strategies.direct_lora import prepare_direct_supervision

__all__ = ["prepare_anchored_supervision", "prepare_direct_supervision"]
