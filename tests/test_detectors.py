import typing

import numpy as np

from pitch_engine.config import FieldDetectorConfig
from pitch_engine.detectors import _FACTORIES, GreenThresholdDetector, build_detector

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
