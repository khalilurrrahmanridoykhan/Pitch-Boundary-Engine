import typing

import cv2
import numpy as np

from pitch_engine.config import FieldDetectorConfig
from pitch_engine.detectors import _FACTORIES, WhiteOutlineDetector, build_detector

GREEN = (34, 139, 34)
WHITE = (255, 255, 255)
FRAME_AREA = 1280 * 720


def black_frame():
    return np.zeros((720, 1280, 3), dtype=np.uint8)


def green_frame():
    frame = black_frame()
    frame[:] = GREEN
    return frame


def pitch_frame():
    """The trapezoid outline the synthetic generator draws on a green frame."""
    frame = green_frame()
    pts = np.array([[100, 100], [1180, 100], [1230, 620], [50, 620]], np.int32)
    cv2.polylines(frame, [pts], True, WHITE, 5)
    return frame


def noise_frame():
    """The small white marker the generator injects as detection noise."""
    frame = green_frame()
    pts = np.array([[10, 10], [40, 10], [40, 30], [10, 30]], np.int32)
    cv2.polylines(frame, [pts], True, WHITE, 2)
    return frame


def detector():
    return WhiteOutlineDetector(min_area=1000)


def test_black_frame_has_no_boundary():
    assert detector().detect(black_frame()) is None


def test_close_up_without_pitch_has_no_boundary():
    assert detector().detect(green_frame()) is None


def test_small_white_marker_is_ignored_as_noise():
    assert detector().detect(noise_frame()) is None


def test_pitch_outline_is_found_and_is_not_the_whole_frame():
    poly = detector().detect(pitch_frame())
    assert poly is not None and poly.is_valid
    assert 0.55 < poly.area / FRAME_AREA < 0.75


def test_every_configurable_type_has_a_factory():
    configurable = set(typing.get_args(FieldDetectorConfig.model_fields["type"].annotation))
    assert configurable == set(_FACTORIES)


def test_build_detector_uses_the_configured_min_area():
    cfg = FieldDetectorConfig(type="sam_mask_v1", sport="football", min_area=42)
    assert build_detector(cfg).min_area == 42
