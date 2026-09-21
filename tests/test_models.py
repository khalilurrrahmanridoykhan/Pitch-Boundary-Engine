import pytest
from pydantic import ValidationError

from pitch_engine.models import EventType, ProgressReport, RunEvent, RunStats, SkipReason


def test_summary_aggregates_without_keeping_detections():
    stats = RunStats()
    for area in (100.0, 300.0, 200.0):
        stats.record_valid(area)
    stats.record_skip(SkipReason.NO_DETECTION)
    stats.record_skip(SkipReason.NO_DETECTION)
    stats.record_skip(SkipReason.READ_FAILURE)

    summary = stats.summary("run1", "feed.mp4", total_frames=100)

    assert summary.sampled_frames == 6
    assert summary.valid_detections == 3
    assert summary.skipped[SkipReason.NO_DETECTION] == 2
    assert summary.skipped[SkipReason.READ_FAILURE] == 1
    assert summary.skipped[SkipReason.IMPLAUSIBLE_COVERAGE] == 0
    assert (summary.area_px.mean_px, summary.area_px.min_px, summary.area_px.max_px) == (200.0, 100.0, 300.0)


def test_summary_has_no_area_stats_without_valid_detections():
    stats = RunStats()
    stats.record_skip(SkipReason.NO_DETECTION)
    assert stats.summary("run1", "feed.mp4", total_frames=10).area_px is None


def test_summary_serialises_to_plain_json_types():
    stats = RunStats()
    stats.record_valid(50.0)
    dumped = stats.summary("run1", "feed.mp4", total_frames=10).model_dump(mode="json")
    assert dumped["skipped"]["no_detection"] == 0
    assert dumped["area_px"]["mean_px"] == 50.0


def finished_summary():
    stats = RunStats()
    stats.record_valid(50.0)
    return stats.summary("run1", "feed.mp4", total_frames=10)


def test_finished_event_serialises_with_summary_and_utc_timestamp():
    event = RunEvent(run_id="run1", event=EventType.FINISHED, video_path="feed.mp4", summary=finished_summary())
    dumped = event.model_dump(mode="json")
    assert dumped["event"] == "finished"
    assert dumped["summary"]["valid_detections"] == 1
    assert dumped["timestamp"].endswith("Z") or dumped["timestamp"].endswith("+00:00")


def test_a_finished_event_must_carry_its_summary():
    with pytest.raises(ValidationError, match="summary"):
        RunEvent(run_id="run1", event=EventType.FINISHED, video_path="feed.mp4")


def test_a_failed_event_must_carry_an_error():
    with pytest.raises(ValidationError, match="error"):
        RunEvent(run_id="run1", event=EventType.FAILED, video_path="feed.mp4")


def test_wire_models_reject_unknown_fields():
    with pytest.raises(ValidationError):
        RunEvent(run_id="run1", event=EventType.STARTED, video_path="feed.mp4", surprise=1)


def test_progress_percent_is_bounded():
    with pytest.raises(ValidationError):
        ProgressReport(
            run_id="r", frame_index=0, total_frames=10, sampled_frames=1,
            valid_detections=1, skipped_frames=0, percent=120.0,
        )
