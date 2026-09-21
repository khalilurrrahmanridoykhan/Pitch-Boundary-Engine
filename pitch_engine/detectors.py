"""Field detection, the one part of the pipeline that varies by sport and deployment.

The pipeline only depends on the FieldDetector protocol. To add a detector,
implement `detect`, register a factory in `_FACTORIES`, and add its name to the
`type` Literal in `pitch_engine.config`.

A detector returns None when it finds no boundary. It should let unexpected errors
propagate: the pipeline counts and logs them per frame, and stops if they persist.
"""

from typing import Callable, Protocol

import cv2
import numpy as np
from shapely.geometry import Polygon

from pitch_engine.config import FieldDetectorConfig


class FieldDetector(Protocol):
    def detect(self, frame: np.ndarray) -> Polygon | None:
        """Return the playing-field boundary in a BGR frame, or None if there is none."""
        ...


class WhiteOutlineDetector:
    """Colour-mask placeholder standing in for a real segmentation model.

    Masks the white pitch outline and returns its outer contour. A green-surface mask
    covers the whole frame whether or not a pitch is visible, so it cannot tell a
    pitch from a close-up.
    """

    _LOWER_WHITE = np.array([200, 200, 200], dtype=np.uint8)
    _UPPER_WHITE = np.array([255, 255, 255], dtype=np.uint8)

    def __init__(self, min_area: int):
        self.min_area = min_area

    def detect(self, frame: np.ndarray) -> Polygon | None:
        return self._derive_polygon_from_mask(self._extract_mask(frame))

    def _extract_mask(self, frame: np.ndarray) -> np.ndarray:
        return cv2.inRange(frame, self._LOWER_WHITE, self._UPPER_WHITE)

    def _derive_polygon_from_mask(self, mask: np.ndarray) -> Polygon | None:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) <= self.min_area:
            return None
        pts = largest.reshape(-1, 2)
        if len(pts) < 3:
            return None
        return Polygon(pts)


_FACTORIES: dict[str, Callable[[FieldDetectorConfig], FieldDetector]] = {
    "sam_mask_v1": lambda cfg: WhiteOutlineDetector(min_area=cfg.min_area),
}


def build_detector(config: FieldDetectorConfig) -> FieldDetector:
    try:
        factory = _FACTORIES[config.type]
    except KeyError:
        raise ValueError(f"No field detector registered for type {config.type!r}") from None
    return factory(config)
