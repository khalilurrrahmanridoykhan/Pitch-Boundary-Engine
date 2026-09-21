"""Video input that decodes only the frames the pipeline will inspect."""

import math
from typing import Iterator

import cv2
import numpy as np

from pitch_engine.errors import VideoSourceError


class VideoSource:
    def __init__(self, path: str):
        self.path = path
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            self._cap.release()
            raise VideoSourceError(f"Could not open video source {path!r}")

        self.fps = self._cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # 0 or negative means the total is unknown, as with a live stream.
        self.frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if not math.isfinite(self.fps) or self.fps <= 0:
            self.release()
            raise VideoSourceError(f"Video source {path!r} reports an invalid fps: {self.fps}")
        if self.width <= 0 or self.height <= 0:
            self.release()
            raise VideoSourceError(
                f"Video source {path!r} reports an invalid size: {self.width}x{self.height}"
            )

    def stride_for(self, interval_seconds: float) -> int:
        return max(1, round(interval_seconds * self.fps))

    def sample(self, interval_seconds: float) -> Iterator[tuple[int, np.ndarray | None]]:
        """Yield (0-based frame index, BGR frame) for one frame per interval.

        The frame is None when that sample could not be read, so the caller can count
        the failure instead of the run quietly ending early. Frames in between are never
        converted or handed to the detector. With a known frame count the source seeks
        straight to each sample; otherwise it advances with grab(), which works on
        streams that cannot seek.
        """
        stride = self.stride_for(interval_seconds)
        if self.frame_count > 0:
            yield from self._sample_by_seeking(stride)
        else:
            yield from self._sample_by_grabbing(stride)

    def _sample_by_seeking(self, stride: int) -> Iterator[tuple[int, np.ndarray | None]]:
        for index in range(0, self.frame_count, stride):
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = self._cap.read()
            yield index, frame if ok else None

    def _sample_by_grabbing(self, stride: int) -> Iterator[tuple[int, np.ndarray | None]]:
        # grab() returning False is the end of the stream; it cannot be told apart from a
        # dropped connection here, so a live source that dies simply ends the run.
        index = 0
        while self._cap.grab():
            if index % stride == 0:
                ok, frame = self._cap.retrieve()
                yield index, frame if ok else None
            index += 1

    def release(self) -> None:
        self._cap.release()

    def __enter__(self) -> "VideoSource":
        return self

    def __exit__(self, *exc_info) -> None:
        self.release()
