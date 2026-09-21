"""Fatal run failures.

Anything that raises a PipelineError ends the run with a failure. Problems with a
single frame are not errors: they are counted in the run summary (see models.py) and
only become fatal when they persist.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pitch_engine.models import RunSummary


class PipelineError(Exception):
    """A run-ending failure. Carries the partial summary when one exists."""

    def __init__(self, message: str, summary: "RunSummary | None" = None):
        super().__init__(message)
        self.summary = summary


class VideoSourceError(PipelineError):
    """The video source could not be opened or does not describe itself usably."""


class SustainedFailureError(PipelineError):
    """Too many frames in a row failed to read or process."""


class NoValidDetectionsError(PipelineError):
    """The run finished without a single valid detection."""
