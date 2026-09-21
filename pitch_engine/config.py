"""Validated pipeline configuration.

Every field is required and unknown keys are rejected, so a typo or a missing
value fails at load time with a clear message instead of falling back to a
default partway through a run.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError


class ConfigError(Exception):
    """The configuration could not be read or is invalid."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class FieldDetectorConfig(_StrictModel):
    type: Literal["sam_mask_v1"]
    sport: str = Field(min_length=1)
    min_area: int = Field(gt=0)


class CropSearchConfig(_StrictModel):
    aspect_ratio: str = Field(pattern=r"^[1-9]\d*:[1-9]\d*$")
    padding_px: int = Field(ge=0)


class PipelineConfig(_StrictModel):
    video_path: str = Field(min_length=1)
    target_fps: int = Field(gt=0)
    sample_interval_seconds: float = Field(gt=0)
    progress_every_samples: int = Field(gt=0)
    # A boundary covering more of the frame than this is treated as "no pitch visible".
    max_frame_coverage: float = Field(gt=0, le=1)
    # The run aborts when this many inspected frames in a row fail to read or process.
    max_consecutive_failures: int = Field(gt=0)
    confidence_threshold: float = Field(ge=0, le=1)
    field_detector: FieldDetectorConfig
    crop_search: CropSearchConfig
    debug_mode: StrictBool


def load_config(path: str | Path) -> PipelineConfig:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file {path} is not valid JSON: {exc}") from exc

    try:
        return PipelineConfig.model_validate(data)
    except ValidationError as exc:
        problems = "\n".join(
            f"  - {'.'.join(str(part) for part in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors()
        )
        raise ConfigError(f"Invalid config {path}:\n{problems}") from exc
