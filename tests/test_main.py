import json

from helpers import config_dict

from run_pipeline import EXIT_BAD_CONFIG, EXIT_RUN_FAILED, main


def write_config(tmp_path, **overrides):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_dict(**overrides)))
    return str(path)


def test_bad_config_exits_before_doing_any_work(tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"video_path": "x.mp4"}))

    assert main(["--config", str(path)]) == EXIT_BAD_CONFIG
    assert "Configuration error" in capsys.readouterr().err


def test_unreadable_video_exits_with_a_failure_code(tmp_path, capsys):
    video = tmp_path / "corrupt.mp4"
    video.write_text("this is not a video")

    assert main(["--config", write_config(tmp_path, video_path=str(video))]) == EXIT_RUN_FAILED

    failure = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert failure["message"] == "run failed"
    assert "Could not open video source" in failure["error"]
