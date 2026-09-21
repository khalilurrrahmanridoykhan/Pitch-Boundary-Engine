from shapely.geometry import Polygon

from pitch_engine.analyzer import FieldBoundaryAnalyzer
from pitch_engine.config import PipelineConfig
from synthetic_generator import generate_synthetic_video


class HugeDetector:
    """Always reports a polygon much larger than any test frame."""

    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return Polygon([(0, 0), (5000, 0), (5000, 5000), (0, 5000)])


def make_config(video_path, interval):
    return PipelineConfig.model_validate(
        {
            "video_path": video_path,
            "target_fps": 30,
            "sample_interval_seconds": interval,
            "confidence_threshold": 0.5,
            "field_detector": {"type": "sam_mask_v1", "sport": "football", "min_area": 1000},
            "crop_search": {"aspect_ratio": "16:9", "padding_px": 20},
            "debug_mode": False,
        }
    )


def test_detector_runs_only_on_sampled_frames(tmp_path):
    path = str(tmp_path / "feed.mp4")
    generate_synthetic_video(path, numFrames=90)
    detector = HugeDetector()

    results = FieldBoundaryAnalyzer(make_config(path, 1.0), detector).process_video(path)

    assert detector.calls == 3
    assert [index for index, _, _ in results] == [0, 30, 60]


def test_area_is_measured_against_the_real_frame_size(tmp_path):
    path = str(tmp_path / "small.mp4")
    generate_synthetic_video(path, numFrames=3, imgWidth=640, imgHeight=360)

    results = FieldBoundaryAnalyzer(make_config(path, 0.0001), HugeDetector()).process_video(path)

    assert len(results) == 3
    assert all(area == 640 * 360 for _, _, area in results)
