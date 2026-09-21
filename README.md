# Pitch Boundary Engine

Finds the playing-field boundary in match video, aggregates the valid detections into a run summary, and reports
progress and outcome to the platform's reporting service.

It is a production-shaped rework of a research prototype. The trade-offs, assumptions and open questions are in
[DECISIONS.md](DECISIONS.md).

## Layout

```
run_pipeline.py          thin entry point: parse args, load config, start logging, call the runner
pitch_engine/
  config.py              validated config models; any problem fails at load time
  detectors.py           FieldDetector protocol + the placeholder detector (the one swappable part)
  video.py               samples one frame per interval; only those frames are converted
  analyzer.py            classifies each sampled frame and aggregates valid detections
  models.py              run summary and the payloads sent to the platform
  reporting.py           HTTP reporter (retries, never raises) and a null reporter
  runner.py              runs one job, reports it, decides the exit code
  errors.py              the failures that end a run
  logging_setup.py       JSON-lines logging with the run id on every line
synthetic_generator.py   the input feed (untouched)
mock_api/                the reporting service (untouched)
tests/
```

## Run it

Locally, with reporting switched off:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_pipeline.py                 # uses config.json
python run_pipeline.py --job-id 42     # use the orchestrator's job id instead of a generated one
```

The synthetic feed is generated on first run and reused afterwards. Delete `synthetic_pitch_feed.mp4` to regenerate it.

In Docker, reporting to `mock_api` over the compose network:

```bash
docker compose up --build --abort-on-container-exit --exit-code-from runner
```

The runner uses `config.docker.json`. Inspect what the platform received with:

```bash
docker compose exec mock_api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5000/api/v1/jobs/events').read().decode())"
```

On macOS, port 5000 on the host is usually taken by AirPlay Receiver, so `curl localhost:5000` will not reach
`mock_api`. Use the command above, or turn AirPlay Receiver off.

Tests:

```bash
python -m pytest
```

## Configuration

`config.json` is validated when it is loaded. Every field is required, unknown keys are rejected, and there are no
silent defaults. A bad file exits with code 2 and lists every problem.

| Field | Meaning |
|---|---|
| `video_path` | Input video. |
| `sample_interval_seconds` | One frame is inspected per interval. This is the throughput/accuracy dial. |
| `progress_every_samples` | How often progress is logged and reported. |
| `max_frame_coverage` | A boundary covering more of the frame than this is treated as "no pitch visible". |
| `max_consecutive_failures` | The run aborts after this many read or processing failures in a row. |
| `field_detector.type` | Which detector implementation to use. |
| `field_detector.sport`, `.min_area` | Detector settings. |
| `reporting` | Reporting service settings, or `null` to switch reporting off. |
| `debug_mode` | `true` logs every skipped frame. |
| `target_fps`, `confidence_threshold`, `crop_search` | Carried over from the prototype. Validated but not used yet. See DECISIONS.md. |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | The pipeline succeeded and the platform was told. |
| 1 | The pipeline failed, whether or not the platform could be told. |
| 2 | The configuration was rejected before any work started. |
| 3 | The pipeline succeeded but the platform never received the outcome. |

## What the platform receives

`POST /api/v1/jobs/progress` while running:

```json
{"run_id": "13f34de0ca23", "frame_index": 270, "total_frames": 1800, "sampled_frames": 10,
 "valid_detections": 9, "skipped_frames": 1, "percent": 15.0}
```

`POST /api/v1/jobs/events` at start (`started`) and end (`finished` or `failed`). A `finished` event carries the run
summary. A `failed` event carries `error`, `error_type` and, when known, the partial summary.

## Logs

One JSON object per line on stdout, each with `ts`, `level`, `logger`, `run_id` and `message`. Follow a run with the
`progress` lines, and diagnose a failure from the `run failed` line and the `frame processing failed` lines above it,
which include the traceback.

## Adding a detector

Implement `detect(frame) -> Polygon | None` in `pitch_engine/detectors.py`, add a factory to `_FACTORIES`, and add its
name to the `type` Literal in `pitch_engine/config.py`. A test checks that the two lists cannot drift apart.
