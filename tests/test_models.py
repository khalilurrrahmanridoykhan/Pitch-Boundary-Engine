from pitch_engine.models import RunStats, SkipReason


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
