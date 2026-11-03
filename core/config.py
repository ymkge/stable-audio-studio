"""Application configuration for Stable Audio Studio."""

from dataclasses import dataclass, field
from pathlib import Path
import os
import torch


def get_default_device() -> str:
    """Return the optimal device: mps if available on macOS, otherwise cpu."""
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@dataclass
class AppConfig:
    # Model configuration
    model_id: str = "stabilityai/stable-audio-3-medium"
    available_models: list[str] = field(
        default_factory=lambda: [
            "stabilityai/stable-audio-3-medium",
            "stabilityai/stable-audio-open-1.0",
        ]
    )
    device: str = field(default_factory=get_default_device)

    # Audio synthesis defaults
    sample_rate: int = 44100
    default_bpm: int = 120
    min_bpm: int = 40
    max_bpm: int = 240

    default_duration: int = 30
    min_duration: int = 5
    max_duration: int = 180

    default_steps: int = 100
    min_steps: int = 10
    max_steps: int = 250

    default_cfg_scale: float = 7.0
    min_cfg_scale: float = 1.0
    max_cfg_scale: float = 15.0

    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    output_dir: Path = field(init=False)

    def __post_init__(self):
        self.output_dir = self.base_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Global default instance
config = AppConfig()
