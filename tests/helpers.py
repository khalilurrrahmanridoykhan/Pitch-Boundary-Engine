import copy

from pitch_engine.config import PipelineConfig

VALID_CONFIG = {
    "video_path": "feed.mp4",
    "target_fps": 30,
    "sample_interval_seconds": 1.0,
    "progress_every_samples": 10,
    "max_frame_coverage": 0.98,
    "max_consecutive_failures": 5,
    "confidence_threshold": 0.5,
    "field_detector": {"type": "sam_mask_v1", "sport": "football", "min_area": 1000},
    "crop_search": {"aspect_ratio": "16:9", "padding_px": 20},
    "debug_mode": True,
}


def config_dict(**overrides):
    data = copy.deepcopy(VALID_CONFIG)
    data.update(overrides)
    return data


def make_config(**overrides) -> PipelineConfig:
    return PipelineConfig.model_validate(config_dict(**overrides))
