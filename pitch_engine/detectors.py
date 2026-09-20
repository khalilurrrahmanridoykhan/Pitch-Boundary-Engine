"""Field detection, the one part of the pipeline that varies by sport and deployment.

The pipeline only depends on the FieldDetector protocol. To add a detector,
implement `detect`, register a factory in `_FACTORIES`, and add its name to the
`type` Literal in `pitch_engine.config`.
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


class GreenThresholdDetector:
    """Colour-threshold placeholder standing in for a real segmentation model."""

    def __init__(self, min_area: int):
        self.min_area = min_area

    def detect(self, frame: np.ndarray) -> Polygon | None:
        return self._derive_polygon_from_mask(self._extract_mask(frame))

    def _extract_mask(self, frame: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        return cv2.inRange(hsv, lower_green, upper_green)

    def _derive_polygon_from_mask(self, mask: np.ndarray) -> Polygon | None:
        try:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest) > self.min_area:
                    pts = largest.reshape(-1, 2)
                    if len(pts) >= 3:
                        return Polygon(pts)
        except Exception:
            pass
        return None


_FACTORIES: dict[str, Callable[[FieldDetectorConfig], FieldDetector]] = {
    "sam_mask_v1": lambda cfg: GreenThresholdDetector(min_area=cfg.min_area),
}


def build_detector(config: FieldDetectorConfig) -> FieldDetector:
    try:
        factory = _FACTORIES[config.type]
    except KeyError:
        raise ValueError(f"No field detector registered for type {config.type!r}") from None
    return factory(config)
