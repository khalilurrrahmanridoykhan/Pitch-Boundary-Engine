"""
SYNTHETIC RESEARCH PROTOTYPE — FIELD BOUNDARY & CROP DERIVATION (v0.1)
----------------------------------------------------------------------
This is an unoptimized prototype script for detecting pitch boundaries and
computing camera crop layouts across video feeds.

DO NOT USE IN PRODUCTION.
"""

from shapely.geometry import box

from pitch_engine.config import PipelineConfig
from pitch_engine.detectors import FieldDetector
from pitch_engine.video import VideoSource


class FieldBoundaryAnalyzer:
    def __init__(self, config: PipelineConfig, detector: FieldDetector):
        self.config = config
        self.detector = detector

    def process_video(self, video_path: str):
        print(f"Starting processing for video: {video_path}")
        detected_polygons = []
        sampled = 0

        with VideoSource(video_path) as source:
            # Built once per run, from the real frame size.
            frame_area = box(0, 0, source.width, source.height)

            for frame_index, frame in source.sample(self.config.sample_interval_seconds):
                sampled += 1
                poly = self.detector.detect(frame)

                if poly and poly.is_valid:
                    intersection_area = poly.intersection(frame_area).area
                    detected_polygons.append((frame_index, poly, intersection_area))

            total = source.frame_count

        print(f"Inspected {sampled} of {total} frames. Found {len(detected_polygons)} boundaries.")
        return detected_polygons
