import numpy as np
import pytest

from pitch_engine.video import VideoSource, VideoSourceError
from synthetic_generator import generate_synthetic_video


@pytest.fixture
def video_path(tmp_path):
    path = str(tmp_path / "feed.mp4")
    generate_synthetic_video(path, numFrames=90)
    return path


def test_unopenable_source_raises(tmp_path):
    with pytest.raises(VideoSourceError, match="Could not open"):
        VideoSource(str(tmp_path / "missing.mp4"))


def test_sampling_yields_one_frame_per_interval(video_path):
    with VideoSource(video_path) as source:
        indices = [i for i, _ in source.sample(interval_seconds=1.0)]
    assert indices == [0, 30, 60]


def test_stride_is_never_below_one_frame(video_path):
    with VideoSource(video_path) as source:
        assert source.stride_for(0.0001) == 1
        indices = [i for i, _ in source.sample(interval_seconds=0.0001)]
    assert indices == list(range(90))


def test_seeking_and_grabbing_return_the_same_frames(video_path):
    with VideoSource(video_path) as source:
        sought = list(source._sample_by_seeking(stride=15))
    with VideoSource(video_path) as source:
        grabbed = list(source._sample_by_grabbing(stride=15))
    assert [i for i, _ in sought] == [i for i, _ in grabbed] == [0, 15, 30, 45, 60, 75]
    for (_, a), (_, b) in zip(sought, grabbed):
        assert np.array_equal(a, b)


def test_source_reports_real_frame_size(tmp_path):
    path = str(tmp_path / "small.mp4")
    generate_synthetic_video(path, numFrames=3, imgWidth=640, imgHeight=360)
    with VideoSource(path) as source:
        assert (source.width, source.height) == (640, 360)
