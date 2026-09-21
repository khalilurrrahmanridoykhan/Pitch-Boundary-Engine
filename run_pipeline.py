import argparse
import logging
import sys
import uuid
from pathlib import Path

from pitch_engine.analyzer import FieldBoundaryAnalyzer
from pitch_engine.config import ConfigError, load_config
from pitch_engine.detectors import build_detector
from pitch_engine.errors import PipelineError
from pitch_engine.logging_setup import configure_logging
from synthetic_generator import generate_synthetic_video

EXIT_OK = 0
EXIT_RUN_FAILED = 1
EXIT_BAD_CONFIG = 2

logger = logging.getLogger("pitch_engine.run")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Pitch boundary and crop engine")
    parser.add_argument("--config", default="config.json", help="path to the JSON config file")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_BAD_CONFIG

    run_id = uuid.uuid4().hex[:12]
    configure_logging(run_id, debug=config.debug_mode)

    if not Path(config.video_path).exists():
        generate_synthetic_video(config.video_path)

    detector = build_detector(config.field_detector)
    try:
        FieldBoundaryAnalyzer(config, detector).process_video(config.video_path, run_id)
    except PipelineError as exc:
        summary = exc.summary.model_dump(mode="json") if exc.summary else None
        logger.error("run failed", extra={"error": str(exc), "summary": summary})
        return EXIT_RUN_FAILED
    except Exception:
        logger.exception("run crashed with an unexpected error")
        return EXIT_RUN_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
