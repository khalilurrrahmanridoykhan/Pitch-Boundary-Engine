"""Runs a field detector over sampled frames and aggregates the valid detections."""

import logging
from typing import Callable

import numpy as np
from shapely.geometry import Polygon, box

from pitch_engine.config import PipelineConfig
from pitch_engine.detectors import FieldDetector
from pitch_engine.errors import NoValidDetectionsError, SustainedFailureError
from pitch_engine.models import FAILURE_REASONS, ProgressReport, RunStats, RunSummary, SkipReason
from pitch_engine.video import VideoSource

logger = logging.getLogger(__name__)


class FieldBoundaryAnalyzer:
    def __init__(self, config: PipelineConfig, detector: FieldDetector):
        self.config = config
        self.detector = detector

    def process_video(
        self,
        video_path: str,
        run_id: str,
        on_progress: Callable[[ProgressReport], object] | None = None,
    ) -> RunSummary:
        """Inspect sampled frames and return the aggregated result.

        Frames with no usable boundary are counted by reason and kept out of the metrics.
        `on_progress` is called at the configured cadence and must not raise.
        Raises PipelineError subclasses for failures that end the run.
        """
        stats = RunStats()
        consecutive_failures = 0

        with VideoSource(video_path) as source:
            total_frames = source.frame_count
            # Built once per run, from the real frame size.
            frame_area = box(0, 0, source.width, source.height)
            logger.info(
                "run started",
                extra={
                    "video_path": video_path,
                    "fps": source.fps,
                    "total_frames": total_frames,
                    "frame_size": [source.width, source.height],
                    "stride_frames": source.stride_for(self.config.sample_interval_seconds),
                },
            )

            for frame_index, frame in source.sample(self.config.sample_interval_seconds):
                area, skip = self._inspect_frame(frame_index, frame, frame_area)

                if skip is None:
                    stats.record_valid(area)
                    consecutive_failures = 0
                else:
                    stats.record_skip(skip)
                    logger.debug("frame skipped", extra={"frame_index": frame_index, "reason": skip})
                    consecutive_failures = consecutive_failures + 1 if skip in FAILURE_REASONS else 0

                if consecutive_failures >= self.config.max_consecutive_failures:
                    summary = stats.summary(run_id, video_path, total_frames)
                    raise SustainedFailureError(
                        f"{consecutive_failures} frames in a row failed "
                        f"(limit {self.config.max_consecutive_failures}), last at frame {frame_index}: "
                        f"{skip.value}",
                        summary,
                    )

                if stats.sampled % self.config.progress_every_samples == 0:
                    progress = stats.summary(run_id, video_path, total_frames)
                    logger.info(
                        "progress",
                        extra={
                            "frame_index": frame_index,
                            "total_frames": total_frames,
                            "sampled_frames": stats.sampled,
                            "summary": progress.model_dump(mode="json"),
                        },
                    )
                    if on_progress is not None:
                        on_progress(
                            ProgressReport(
                                run_id=run_id,
                                frame_index=frame_index,
                                total_frames=total_frames,
                                sampled_frames=stats.sampled,
                                valid_detections=stats.valid,
                                skipped_frames=stats.sampled - stats.valid,
                                percent=(
                                    min(100.0, round(100 * frame_index / total_frames, 1))
                                    if total_frames > 0
                                    else None
                                ),
                            )
                        )

        summary = stats.summary(run_id, video_path, total_frames)
        if summary.valid_detections == 0:
            raise NoValidDetectionsError(
                f"No valid detection in {summary.sampled_frames} inspected frames", summary
            )

        logger.info("run finished", extra={"summary": summary.model_dump(mode="json")})
        return summary

    def _inspect_frame(
        self, frame_index: int, frame: np.ndarray | None, frame_area: Polygon
    ) -> tuple[float | None, SkipReason | None]:
        """Return (area_px, None) for a valid detection, or (None, reason) for a skipped frame."""
        if frame is None:
            logger.warning("frame read failed", extra={"frame_index": frame_index})
            return None, SkipReason.READ_FAILURE

        try:
            poly = self.detector.detect(frame)
            if poly is None:
                return None, SkipReason.NO_DETECTION
            if poly.is_empty or not poly.is_valid:
                return None, SkipReason.INVALID_GEOMETRY
            area = poly.intersection(frame_area).area
        except Exception:
            logger.exception("frame processing failed", extra={"frame_index": frame_index})
            return None, SkipReason.PROCESSING_ERROR

        if area <= 0:
            return None, SkipReason.INVALID_GEOMETRY
        if area / frame_area.area > self.config.max_frame_coverage:
            return None, SkipReason.IMPLAUSIBLE_COVERAGE
        return area, None
