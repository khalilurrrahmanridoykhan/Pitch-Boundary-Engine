import json
import logging

from pitch_engine.logging_setup import configure_logging


def test_records_are_json_lines_with_run_id_and_extra_fields(capsys):
    configure_logging("abc123", debug=False)
    logging.getLogger("pitch_engine.test").info("hello", extra={"frame_index": 7})

    line = json.loads(capsys.readouterr().out.strip())
    assert line["message"] == "hello"
    assert line["run_id"] == "abc123"
    assert line["level"] == "INFO"
    assert line["frame_index"] == 7


def test_exceptions_are_included_as_a_traceback(capsys):
    configure_logging("abc123", debug=False)
    try:
        raise ValueError("bad frame")
    except ValueError:
        logging.getLogger("pitch_engine.test").exception("failed")

    line = json.loads(capsys.readouterr().out.strip())
    assert "ValueError: bad frame" in line["exception"]


def test_debug_mode_controls_verbosity(capsys):
    logger = logging.getLogger("pitch_engine.test")

    configure_logging("abc123", debug=False)
    logger.debug("hidden")
    assert capsys.readouterr().out == ""

    configure_logging("abc123", debug=True)
    logger.debug("shown")
    assert "shown" in capsys.readouterr().out
