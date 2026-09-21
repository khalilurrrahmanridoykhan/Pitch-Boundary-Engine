import pytest
from helpers import make_config

from pitch_engine.analyzer import FieldBoundaryAnalyzer
from pitch_engine.models import EventType
from pitch_engine.runner import EXIT_OK, EXIT_REPORTING_FAILED, EXIT_RUN_FAILED, run_job
from synthetic_generator import generate_synthetic_video


class RecordingReporter:
    def __init__(self, deliver=True):
        self.deliver = deliver
        self.events = []
        self.progress_reports = []

    def event(self, event):
        self.events.append(event)
        return self.deliver

    def progress(self, report):
        self.progress_reports.append(report)
        return self.deliver

    @property
    def event_types(self):
        return [e.event for e in self.events]


@pytest.fixture
def video(tmp_path):
    path = str(tmp_path / "feed.mp4")
    generate_synthetic_video(path, numFrames=90)
    return path


@pytest.fixture
def corrupt_video(tmp_path):
    path = tmp_path / "corrupt.mp4"
    path.write_text("not a video")
    return str(path)


def config_for(video, **overrides):
    overrides.setdefault("sample_interval_seconds", 0.0001)
    overrides.setdefault("progress_every_samples", 30)
    return make_config(video_path=video, **overrides)


def test_successful_run_reports_started_progress_and_finished(video):
    reporter = RecordingReporter()

    assert run_job(config_for(video), "run1", reporter) == EXIT_OK

    assert reporter.event_types == [EventType.STARTED, EventType.FINISHED]
    assert reporter.events[-1].summary.valid_detections > 0
    assert [p.sampled_frames for p in reporter.progress_reports] == [30, 60, 90]
    assert reporter.progress_reports[-1].percent == pytest.approx(98.9, abs=0.1)


def test_pipeline_failure_is_reported_as_failed_with_its_type(corrupt_video):
    reporter = RecordingReporter()

    assert run_job(config_for(corrupt_video), "run1", reporter) == EXIT_RUN_FAILED

    assert reporter.event_types == [EventType.STARTED, EventType.FAILED]
    failed = reporter.events[-1]
    assert failed.error_type == "VideoSourceError"
    assert "Could not open" in failed.error


def test_unexpected_crash_is_reported_as_failed(video, monkeypatch):
    def explode(self, *args, **kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr(FieldBoundaryAnalyzer, "process_video", explode)
    reporter = RecordingReporter()

    assert run_job(config_for(video), "run1", reporter) == EXIT_RUN_FAILED
    assert reporter.events[-1].event is EventType.FAILED
    assert reporter.events[-1].error_type == "RuntimeError"


def test_unreachable_platform_does_not_fail_a_successful_pipeline(video):
    reporter = RecordingReporter(deliver=False)
    assert run_job(config_for(video), "run1", reporter) == EXIT_REPORTING_FAILED


def test_unreachable_platform_does_not_hide_a_pipeline_failure(corrupt_video):
    reporter = RecordingReporter(deliver=False)
    assert run_job(config_for(corrupt_video), "run1", reporter) == EXIT_RUN_FAILED


def test_the_pipeline_finishes_even_if_started_and_progress_are_not_delivered(video):
    class OnlyOutcomeDelivered(RecordingReporter):
        def event(self, event):
            super().event(event)
            return event.event is not EventType.STARTED

        def progress(self, report):
            super().progress(report)
            return False

    assert run_job(config_for(video), "run1", OnlyOutcomeDelivered()) == EXIT_OK
