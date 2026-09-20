from pitch_engine.analyzer import CONFIG, FieldBoundaryAnalyzer
from synthetic_generator import generate_synthetic_video


def main():
    generate_synthetic_video(CONFIG["video_path"])
    results = FieldBoundaryAnalyzer(CONFIG).process_video(CONFIG["video_path"])
    print(f"Pipeline finished with {len(results) if results else 0} results.")


if __name__ == "__main__":
    main()
