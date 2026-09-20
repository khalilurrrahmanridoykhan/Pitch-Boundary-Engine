import typing

import numpy as np
from shapely.geometry import Polygon

from pitch_engine.analyzer import FieldBoundaryAnalyzer
from pitch_engine.config import FieldDetectorConfig, PipelineConfig
from pitch_engine.detectors import _FACTORIES, GreenThresholdDetector, build_detector
from synthetic_generator import generate_synthetic_video

GREEN = (34, 139, 34)


def test_black_frame_has_no_boundary():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    assert GreenThresholdDetector(min_area=1000).detect(frame) is None


def test_green_frame_gives_a_polygon():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:] = GREEN
    assert GreenThresholdDetector(min_area=1000).detect(frame) is not None


def test_green_area_below_min_area_is_ignored():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[10:20, 10:20] = GREEN
    assert GreenThresholdDetector(min_area=1000).detect(frame) is None


def test_every_configurable_type_has_a_factory():
    configurable = set(typing.get_args(FieldDetectorConfig.model_fields["type"].annotation))
    assert configurable == set(_FACTORIES)


def test_build_detector_uses_the_configured_min_area():
    cfg = FieldDetectorConfig(type="sam_mask_v1", sport="football", min_area=42)
    assert build_detector(cfg).min_area == 42


def test_analyzer_accepts_any_detector(tmp_path):
    class FixedDetector:
        def detect(self, frame):
            return Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])

    video = str(tmp_path / "feed.mp4")
    generate_synthetic_video(video, numFrames=5)
    config = PipelineConfig.model_validate(
        {
            "video_path": video,
            "target_fps": 30,
            "confidence_threshold": 0.5,
            "field_detector": {"type": "sam_mask_v1", "sport": "football", "min_area": 1000},
            "crop_search": {"aspect_ratio": "16:9", "padding_px": 20},
            "debug_mode": False,
        }
    )
    results = FieldBoundaryAnalyzer(config, FixedDetector()).process_video(video)
    assert len(results) == 5
    assert all(area == 10000 for _, _, area in results)
