import argparse
import sys
import uuid
from pathlib import Path

from pitch_engine.config import ConfigError, load_config
from pitch_engine.logging_setup import configure_logging
from pitch_engine.reporting import build_reporter
from pitch_engine.runner import EXIT_BAD_CONFIG, run_job
from synthetic_generator import generate_synthetic_video


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Pitch boundary and crop engine")
    parser.add_argument("--config", default="config.json", help="path to the JSON config file")
    parser.add_argument("--job-id", default=None, help="job id from the orchestrator (default: generated)")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_BAD_CONFIG

    run_id = args.job_id or uuid.uuid4().hex[:12]
    configure_logging(run_id, debug=config.debug_mode)

    if not Path(config.video_path).exists():
        generate_synthetic_video(config.video_path)

    return run_job(config, run_id, build_reporter(config.reporting))


if __name__ == "__main__":
    sys.exit(main())
