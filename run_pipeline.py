import argparse
import sys

from pitch_engine.analyzer import FieldBoundaryAnalyzer
from pitch_engine.config import ConfigError, load_config
from pitch_engine.detectors import build_detector
from pitch_engine.video import VideoSourceError
from synthetic_generator import generate_synthetic_video


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Pitch boundary and crop engine")
    parser.add_argument("--config", default="config.json", help="path to the JSON config file")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    generate_synthetic_video(config.video_path)
    detector = build_detector(config.field_detector)
    try:
        results = FieldBoundaryAnalyzer(config, detector).process_video(config.video_path)
    except VideoSourceError as exc:
        print(f"Video error: {exc}", file=sys.stderr)
        return 1
    print(f"Pipeline finished with {len(results)} results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
