"""Result models. Detections are aggregated as they arrive, so memory stays flat on long feeds."""

from collections import Counter
from enum import Enum

from pydantic import BaseModel, ConfigDict


class SkipReason(str, Enum):
    # The frame was inspected and there is no usable boundary in it. Expected on real feeds.
    NO_DETECTION = "no_detection"
    INVALID_GEOMETRY = "invalid_geometry"
    IMPLAUSIBLE_COVERAGE = "implausible_coverage"
    # The frame could not be inspected. Tolerated when isolated, fatal when sustained.
    READ_FAILURE = "read_failure"
    PROCESSING_ERROR = "processing_error"


FAILURE_REASONS = frozenset({SkipReason.READ_FAILURE, SkipReason.PROCESSING_ERROR})


class AreaStats(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mean_px: float
    min_px: float
    max_px: float


class RunSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    video_path: str
    total_frames: int  # 0 when the source does not report a length
    sampled_frames: int
    valid_detections: int
    skipped: dict[SkipReason, int]
    area_px: AreaStats | None  # None when there were no valid detections


class RunStats:
    """Running totals for one run."""

    def __init__(self) -> None:
        self._skipped: Counter[SkipReason] = Counter()
        self._valid = 0
        self._area_sum = 0.0
        self._area_min = float("inf")
        self._area_max = 0.0

    @property
    def sampled(self) -> int:
        return self._valid + sum(self._skipped.values())

    def record_valid(self, area_px: float) -> None:
        self._valid += 1
        self._area_sum += area_px
        self._area_min = min(self._area_min, area_px)
        self._area_max = max(self._area_max, area_px)

    def record_skip(self, reason: SkipReason) -> None:
        self._skipped[reason] += 1

    def summary(self, run_id: str, video_path: str, total_frames: int) -> RunSummary:
        area = (
            AreaStats(
                mean_px=self._area_sum / self._valid,
                min_px=self._area_min,
                max_px=self._area_max,
            )
            if self._valid
            else None
        )
        return RunSummary(
            run_id=run_id,
            video_path=video_path,
            total_frames=total_frames,
            sampled_frames=self.sampled,
            valid_detections=self._valid,
            skipped={reason: self._skipped[reason] for reason in SkipReason},
            area_px=area,
        )
