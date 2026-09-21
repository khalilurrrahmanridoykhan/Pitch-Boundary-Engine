import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pitch_engine.config import ReportingConfig
from pitch_engine.models import EventType, ProgressReport, RunEvent, RunStats
from pitch_engine.reporting import EVENTS_PATH, PROGRESS_PATH, HttpReporter, NullReporter


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.received.append((self.path, body))
        status = self.server.statuses.pop(0) if self.server.statuses else 200
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.received = []
    httpd.statuses = []  # status codes to answer with, in order; 200 once exhausted
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def config(url, **overrides):
    values = {"base_url": url, "timeout_seconds": 1.0, "event_retries": 2, "suspend_progress_after_failures": 2}
    return ReportingConfig(**{**values, **overrides})


def reporter_for(server, sleeps=None, **overrides):
    url = f"http://127.0.0.1:{server.server_port}"
    return HttpReporter(config(url, **overrides), sleep=(sleeps.append if sleeps is not None else lambda s: None))


def dead_url():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{sock.getsockname()[1]}"


def progress():
    return ProgressReport(
        run_id="run1", frame_index=30, total_frames=90, sampled_frames=2,
        valid_detections=2, skipped_frames=0, percent=33.3,
    )


def started():
    return RunEvent(run_id="run1", event=EventType.STARTED, video_path="feed.mp4")


def finished():
    stats = RunStats()
    stats.record_valid(10.0)
    return RunEvent(
        run_id="run1", event=EventType.FINISHED, video_path="feed.mp4",
        summary=stats.summary("run1", "feed.mp4", 90),
    )


def test_progress_and_events_reach_their_endpoints_as_json(server):
    reporter = reporter_for(server)

    assert reporter.progress(progress()) is True
    assert reporter.event(finished()) is True

    (progress_path, progress_body), (event_path, event_body) = server.received
    assert progress_path == PROGRESS_PATH and progress_body["percent"] == 33.3
    assert event_path == EVENTS_PATH and event_body["event"] == "finished"
    assert event_body["summary"]["valid_detections"] == 1


def test_events_are_retried_on_server_errors_with_backoff(server):
    server.statuses = [503, 500]
    sleeps = []

    assert reporter_for(server, sleeps).event(started()) is True
    assert len(server.received) == 3
    assert sleeps == [0.5, 1.0]


def test_events_give_up_after_the_configured_retries(server):
    server.statuses = [500, 500, 500, 500]
    assert reporter_for(server).event(started()) is False
    assert len(server.received) == 3  # first attempt + 2 retries


def test_rejected_payloads_are_not_retried(server):
    server.statuses = [400]
    assert reporter_for(server).event(started()) is False
    assert len(server.received) == 1


def test_progress_is_not_retried(server):
    server.statuses = [500]
    assert reporter_for(server).progress(progress()) is False
    assert len(server.received) == 1


def test_an_unreachable_service_returns_false_instead_of_raising():
    reporter = HttpReporter(config(dead_url()), sleep=lambda s: None)
    assert reporter.event(started()) is False
    assert reporter.progress(progress()) is False


def test_progress_is_suspended_after_repeated_failures_and_resumes_after_an_event(server):
    server.statuses = [500, 500]
    reporter = reporter_for(server, suspend_progress_after_failures=2)

    assert reporter.progress(progress()) is False
    assert reporter.progress(progress()) is False
    assert len(server.received) == 2

    assert reporter.progress(progress()) is False  # suspended: nothing is sent
    assert len(server.received) == 2

    assert reporter.event(started()) is True  # events are always attempted
    assert reporter.progress(progress()) is True  # and one success resumes progress
    assert len(server.received) == 4


def test_null_reporter_has_nothing_to_deliver():
    reporter = NullReporter()
    assert reporter.progress(progress()) is True
    assert reporter.event(started()) is True
