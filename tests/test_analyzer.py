import itertools
import logging

import numpy as np
import pytest
from helpers import make_config
from shapely.geometry import Polygon, box

from pitch_engine.analyzer import FieldBoundaryAnalyzer
from pitch_engine.errors import NoValidDetectionsError, SustainedFailureError
from pitch_engine.models import SkipReason
from pitch_engine.video import VideoSource
from synthetic_generator import generate_synthetic_video

PITCH = box(100, 100, 1180, 620)
PITCH_AREA = 1080 * 520
WHOLE_FRAME = box(0, 0, 1280, 720)
BOWTIE = Polygon([(0, 0), (100, 100), (100, 0), (0, 100)])
OFF_SCREEN = box(2000, 2000, 2100, 2100)


class ScriptedDetector:
    """Returns the scripted results in order, then `default` forever. Exceptions are raised."""

    def __init__(self, script=(), default=PITCH):
        self._results = itertools.chain(script, itertools.repeat(default))
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        result = next(self._results)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def video(tmp_path):
    path = str(tmp_path / "feed.mp4")
    generate_synthetic_video(path, numFrames=90)
    return path


def run(video, detector, **config):
    config.setdefault("sample_interval_seconds", 0.0001)  # every frame
    return FieldBoundaryAnalyzer(make_config(**config), detector).process_video(video, "run1")


def test_detector_runs_only_on_sampled_frames(video):
    detector = ScriptedDetector()
    summary = run(video, detector, sample_interval_seconds=1.0)
    assert detector.calls == summary.sampled_frames == 3
    assert summary.total_frames == 90


def test_each_kind_of_bad_frame_is_counted_and_kept_out_of_the_metrics(video):
    detector = ScriptedDetector([None, BOWTIE, WHOLE_FRAME, OFF_SCREEN])
    summary = run(video, detector)

    assert summary.sampled_frames == 90
    assert summary.valid_detections == 86
    assert summary.skipped[SkipReason.NO_DETECTION] == 1
    assert summary.skipped[SkipReason.INVALID_GEOMETRY] == 2
    assert summary.skipped[SkipReason.IMPLAUSIBLE_COVERAGE] == 1
    assert summary.area_px.min_px == summary.area_px.max_px == PITCH_AREA


def test_area_is_measured_against_the_real_frame_size(tmp_path):
    path = str(tmp_path / "small.mp4")
    generate_synthetic_video(path, numFrames=3, imgWidth=640, imgHeight=360)
    huge = box(0, 0, 5000, 5000)
    summary = run(path, ScriptedDetector(default=huge), max_frame_coverage=1.0)
    assert summary.area_px.mean_px == 640 * 360


def test_isolated_failures_are_tolerated_but_counted_and_logged(video, caplog):
    boom = RuntimeError("model crashed")
    detector = ScriptedDetector([boom, PITCH, boom, PITCH, boom])

    with caplog.at_level(logging.ERROR):
        summary = run(video, detector, max_consecutive_failures=2)

    assert summary.skipped[SkipReason.PROCESSING_ERROR] == 3
    assert summary.valid_detections == 87
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 3
    assert errors[0].exc_info is not None


def test_sustained_failures_stop_the_run(video):
    detector = ScriptedDetector(default=RuntimeError("model crashed"))
    with pytest.raises(SustainedFailureError) as excinfo:
        run(video, detector, max_consecutive_failures=3)
    assert detector.calls == 3
    assert excinfo.value.summary.skipped[SkipReason.PROCESSING_ERROR] == 3


def test_no_boundary_frames_do_not_count_as_failures(video):
    with pytest.raises(NoValidDetectionsError):
        run(video, ScriptedDetector(default=None), max_consecutive_failures=2)


def test_a_run_with_no_valid_detection_fails_with_its_summary(video):
    with pytest.raises(NoValidDetectionsError) as excinfo:
        run(video, ScriptedDetector(default=WHOLE_FRAME))
    assert excinfo.value.summary.skipped[SkipReason.IMPLAUSIBLE_COVERAGE] == 90


def test_unreadable_frames_are_counted_as_read_failures(video, monkeypatch):
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    def fake_sample(self, interval_seconds):
        yield 0, None
        yield 1, frame
        yield 2, None

    monkeypatch.setattr(VideoSource, "sample", fake_sample)
    summary = run(video, ScriptedDetector())
    assert summary.skipped[SkipReason.READ_FAILURE] == 2
    assert summary.valid_detections == 1


def test_progress_is_logged_at_the_configured_cadence(video, caplog):
    with caplog.at_level(logging.INFO):
        run(video, ScriptedDetector(), progress_every_samples=30)
    progress = [r for r in caplog.records if r.getMessage() == "progress"]
    assert [r.sampled_frames for r in progress] == [30, 60, 90]
