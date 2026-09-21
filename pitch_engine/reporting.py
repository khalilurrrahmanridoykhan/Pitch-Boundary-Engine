"""Delivery of progress and outcome to the platform's reporting service.

Contract: reporters never raise. A delivery problem is logged and returned as False,
so an outage of the reporting service cannot change the outcome of the video pipeline.
The runner decides what an undelivered outcome means (see runner.py).
"""

import logging
import time
from typing import Callable, Protocol

import requests
from pydantic import BaseModel

from pitch_engine.config import ReportingConfig
from pitch_engine.models import ProgressReport, RunEvent

logger = logging.getLogger(__name__)

PROGRESS_PATH = "/api/v1/jobs/progress"
EVENTS_PATH = "/api/v1/jobs/events"
_BACKOFF_SECONDS = 0.5


class Reporter(Protocol):
    def progress(self, report: ProgressReport) -> bool:
        """Best effort. Returns whether the update was delivered."""
        ...

    def event(self, event: RunEvent) -> bool:
        """Retried. Returns whether the event was delivered."""
        ...


class NullReporter:
    """Used when reporting is turned off. There is nothing to deliver, so nothing is undelivered."""

    def progress(self, report: ProgressReport) -> bool:
        return True

    def event(self, event: RunEvent) -> bool:
        return True


class HttpReporter:
    def __init__(
        self,
        config: ReportingConfig,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._base_url = str(config.base_url).rstrip("/")
        self._timeout = config.timeout_seconds
        self._event_retries = config.event_retries
        self._suspend_after = config.suspend_progress_after_failures
        self._session = session or requests.Session()
        self._sleep = sleep
        self._consecutive_failures = 0

    def progress(self, report: ProgressReport) -> bool:
        # Once the service looks down, stop paying a timeout on every update. Events keep
        # being attempted and the first one that gets through resumes progress updates.
        if self._consecutive_failures >= self._suspend_after:
            return False
        delivered = self._send(PROGRESS_PATH, report, retries=0)
        if self._consecutive_failures == self._suspend_after:
            logger.warning(
                "progress reporting suspended until the reporting service responds",
                extra={"consecutive_failures": self._consecutive_failures},
            )
        return delivered

    def event(self, event: RunEvent) -> bool:
        return self._send(EVENTS_PATH, event, retries=self._event_retries)

    def _send(self, path: str, payload: BaseModel, retries: int) -> bool:
        url = self._base_url + path
        body = payload.model_dump(mode="json")
        error = "not attempted"

        for attempt in range(retries + 1):
            delivered, retryable, error = self._post_once(url, body)
            if delivered:
                self._consecutive_failures = 0
                return True
            if not retryable:
                break
            if attempt < retries:
                self._sleep(_BACKOFF_SECONDS * 2**attempt)

        self._consecutive_failures += 1
        logger.warning("report not delivered", extra={"url": url, "error": error, "attempts": attempt + 1})
        return False

    def _post_once(self, url: str, body: dict) -> tuple[bool, bool, str]:
        """Return (delivered, worth retrying, error description)."""
        try:
            response = self._session.post(url, json=body, timeout=self._timeout)
        except requests.RequestException as exc:
            return False, True, f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # a reporting bug must not end the run
            logger.exception("unexpected error while reporting")
            return False, False, f"{type(exc).__name__}: {exc}"

        if response.ok:
            return True, False, ""
        # A 4xx means this payload was rejected, and sending it again will not change that.
        return False, response.status_code >= 500, f"HTTP {response.status_code}"


def build_reporter(config: ReportingConfig | None) -> Reporter:
    return NullReporter() if config is None else HttpReporter(config)
