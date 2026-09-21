import copy
import json

import pytest

from pitch_engine.config import ConfigError, load_config

VALID = {
    "video_path": "feed.mp4",
    "target_fps": 30,
    "sample_interval_seconds": 1.0,
    "confidence_threshold": 0.5,
    "field_detector": {"type": "sam_mask_v1", "sport": "football", "min_area": 1000},
    "crop_search": {"aspect_ratio": "16:9", "padding_px": 20},
    "debug_mode": True,
}


def write(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


def mutated(mutate):
    data = copy.deepcopy(VALID)
    mutate(data)
    return data


def test_valid_config_loads(tmp_path):
    config = load_config(write(tmp_path, VALID))
    assert config.field_detector.min_area == 1000
    assert config.crop_search.aspect_ratio == "16:9"


def test_missing_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="Cannot read config file"):
        load_config(tmp_path / "nope.json")


def test_invalid_json_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_config(write(tmp_path, "{not json"))


@pytest.mark.parametrize(
    "mutate, field",
    [
        (lambda d: d.pop("video_path"), "video_path"),
        (lambda d: d["field_detector"].pop("min_area"), "field_detector.min_area"),
        (lambda d: d.update(unexpected=1), "unexpected"),
        (lambda d: d["crop_search"].update(extra=1), "crop_search.extra"),
        (lambda d: d.update(target_fps=0), "target_fps"),
        (lambda d: d.update(target_fps="fast"), "target_fps"),
        (lambda d: d.update(sample_interval_seconds=0), "sample_interval_seconds"),
        (lambda d: d.update(sample_interval_seconds=-1), "sample_interval_seconds"),
        (lambda d: d.pop("sample_interval_seconds"), "sample_interval_seconds"),
        (lambda d: d.update(confidence_threshold=1.5), "confidence_threshold"),
        (lambda d: d["field_detector"].update(min_area=-5), "field_detector.min_area"),
        (lambda d: d["field_detector"].update(type="unknown"), "field_detector.type"),
        (lambda d: d["crop_search"].update(aspect_ratio="wide"), "crop_search.aspect_ratio"),
        (lambda d: d["crop_search"].update(aspect_ratio="0:9"), "crop_search.aspect_ratio"),
        (lambda d: d.update(debug_mode="yes"), "debug_mode"),
    ],
)
def test_bad_config_names_the_offending_field(tmp_path, mutate, field):
    with pytest.raises(ConfigError) as excinfo:
        load_config(write(tmp_path, mutated(mutate)))
    assert field in str(excinfo.value)
