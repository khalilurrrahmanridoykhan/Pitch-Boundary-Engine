import copy
import json

import pytest

from helpers import VALID_CONFIG as VALID
from pitch_engine.config import ConfigError, load_config


REPORTING = {
    "base_url": "http://mock_api:5000",
    "timeout_seconds": 2.0,
    "event_retries": 3,
    "suspend_progress_after_failures": 3,
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


def test_reporting_can_be_configured_or_switched_off(tmp_path):
    assert load_config(write(tmp_path, VALID)).reporting is None
    config = load_config(write(tmp_path, {**VALID, "reporting": REPORTING}))
    assert str(config.reporting.base_url).rstrip("/") == "http://mock_api:5000"


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
        (lambda d: d.update(progress_every_samples=0), "progress_every_samples"),
        (lambda d: d.update(max_frame_coverage=0), "max_frame_coverage"),
        (lambda d: d.update(max_frame_coverage=1.2), "max_frame_coverage"),
        (lambda d: d.update(max_consecutive_failures=0), "max_consecutive_failures"),
        (lambda d: d.pop("max_consecutive_failures"), "max_consecutive_failures"),
        (lambda d: d["field_detector"].update(min_area=-5), "field_detector.min_area"),
        (lambda d: d["field_detector"].update(type="unknown"), "field_detector.type"),
        (lambda d: d["crop_search"].update(aspect_ratio="wide"), "crop_search.aspect_ratio"),
        (lambda d: d["crop_search"].update(aspect_ratio="0:9"), "crop_search.aspect_ratio"),
        (lambda d: d.update(debug_mode="yes"), "debug_mode"),
        (lambda d: d.pop("reporting"), "reporting"),
        (lambda d: d.update(reporting={**REPORTING, "base_url": "not a url"}), "reporting.base_url"),
        (lambda d: d.update(reporting={**REPORTING, "base_url": "ftp://host"}), "reporting.base_url"),
        (lambda d: d.update(reporting={**REPORTING, "timeout_seconds": 0}), "reporting.timeout_seconds"),
        (lambda d: d.update(reporting={**REPORTING, "event_retries": -1}), "reporting.event_retries"),
        (lambda d: d.update(reporting={**REPORTING, "suspend_progress_after_failures": 0}), "reporting.suspend_progress_after_failures"),
        (lambda d: d.update(reporting={**REPORTING, "surprise": 1}), "reporting.surprise"),
    ],
)
def test_bad_config_names_the_offending_field(tmp_path, mutate, field):
    with pytest.raises(ConfigError) as excinfo:
        load_config(write(tmp_path, mutated(mutate)))
    assert field in str(excinfo.value)
