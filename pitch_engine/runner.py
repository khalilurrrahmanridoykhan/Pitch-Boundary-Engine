"""Runs one job: analyse the video, report to the platform, and decide the exit code.

Exit codes let an orchestrator tell the situations apart without reading logs:
  0  the pipeline succeeded and the platform was told
  1  the pipeline failed (whether or not the platform could be told)
  2  the configuration was rejected before any work started
  3  the pipeline succeeded but the platform never received the outcome
"""

import logging

from pitch_engine.analyzer import FieldBoundaryAnalyzer
from pitch_engine.config import PipelineConfig
from pitch_engine.detectors import build_detector
from pitch_engine.errors import PipelineError
from pitch_engine.models import EventType, RunEvent, RunSummary
from pitch_engine.reporting import Reporter

EXIT_OK = 0
EXIT_RUN_FAILED = 1
EXIT_BAD_CONFIG = 2
EXIT_REPORTING_FAILED = 3

logger = logging.getLogger(__name__)


def run_job(config: PipelineConfig, run_id: str, reporter: Reporter) -> int:
    analyzer = FieldBoundaryAnalyzer(config, build_detector(config.field_detector))

    # A missed "started" event is logged by the reporter and otherwise ignored: the
    # outcome event carries everything the platform needs.
    reporter.event(RunEvent(run_id=run_id, event=EventType.STARTED, video_path=config.video_path))

    try:
        summary = analyzer.process_video(config.video_path, run_id, on_progress=reporter.progress)
    except PipelineError as exc:
        logger.error("run failed", extra={"error": str(exc), "error_type": type(exc).__name__})
        _report_failure(reporter, run_id, config.video_path, exc, exc.summary)
        return EXIT_RUN_FAILED
    except Exception as exc:
        logger.exception("run crashed with an unexpected error")
        _report_failure(reporter, run_id, config.video_path, exc, None)
        return EXIT_RUN_FAILED

    finished = RunEvent(run_id=run_id, event=EventType.FINISHED, video_path=config.video_path, summary=summary)
    if not reporter.event(finished):
        logger.error("run finished but its outcome could not be reported to the platform")
        return EXIT_REPORTING_FAILED
    return EXIT_OK


def _report_failure(
    reporter: Reporter, run_id: str, video_path: str, exc: Exception, summary: RunSummary | None
) -> None:
    failed = RunEvent(
        run_id=run_id,
        event=EventType.FAILED,
        video_path=video_path,
        summary=summary,
        error=str(exc) or type(exc).__name__,
        error_type=type(exc).__name__,
    )
    if not reporter.event(failed):
        logger.error("run failed and the failure could not be reported to the platform")
