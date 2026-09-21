# Decisions

## Where I stopped

Parts 1 to 4 are implemented, tested (78 tests) and verified end to end in Docker against `mock_api`.

Not done, in the order I would do it next:

1. **Graceful shutdown.** If the container is stopped mid-run (SIGTERM), no `failed` event is sent, so the platform
   sees a run that started and never ended. A signal handler that reports an `interrupted` outcome is the first thing I
   would add.
2. **The crop step.** The README of the prototype describes a downstream crop-layout step. The assignment does not ask
   for it and the run keeps no polygons, only aggregates (see below).
3. **A cap on inspected frames.** See the performance section: time still grows with video length at a fixed interval.
4. **A real detector.** The detector here is a colour-mask placeholder.
5. **CI and a container test.** Tests run locally. The Docker path was checked by hand, not automated.

## 1. Assumptions and open questions

### What I assumed

- **Video stability.** Constant frame rate and a fixed resolution for the whole file. Both are read once when the
  video is opened, and the frame rectangle used for measurements is built once from the real size. A resolution change
  mid-stream is not handled.
- **Camera cuts and close-ups are normal.** The feed contains black frames, close-ups with no pitch and momentary
  noise. A frame with no usable boundary is expected, not an error. It is counted by reason and kept out of the metrics.
- **Stream errors.** Files are seekable and report their length. For a source that does not, sampling falls back to
  reading forward. In that mode the end of the stream cannot be told apart from a dropped connection, so a live source
  that dies simply ends the run.
- **A missing boundary over a whole run is a failure.** I assumed every feed shows the pitch at some point. A run with
  zero valid detections fails, rather than reporting success with nothing in it.

### What I found in the prototype

The prototype's detector masks the green background. The whole frame is green, so its "boundary" was the whole frame on
every frame except black ones. Against the generator's own labels: 1727 normal frames, 15 close-ups, 34 noise frames
and 24 black cuts. The prototype reported 1776 boundaries, so 49 close-up and noise frames were counted as pitches, and
every one of the 1776 was just the frame border. The placeholder now masks the white pitch outline instead, and the
same run reports 1727 valid frames and 73 skipped. That change is its own commit so it can be reverted.

A boundary that covers nearly the whole frame is also rejected by the pipeline itself (`max_frame_coverage`),
independent of the detector, because a real model can flood its mask in the same way.

### What I would ask the product and ML team

- What does `target_fps` mean? It is in the prototype config and nothing uses it. I kept it validated and did not
  guess a meaning.
- What does `confidence_threshold` apply to? The placeholder detector produces no confidence, so it is also unused.
- Which sports and detector types exist? `sport` accepts any non-empty string, and `type` accepts one value.
- What does the real detector return: a polygon, a mask, a confidence?
- What does the crop step consume? If it needs a polygon per frame or a stable representative polygon, the run has to
  keep or persist them. Today it keeps aggregates only.
- Is 0.98 the right coverage limit? It is a guess and needs real footage.
- What is the real schema of the reporting API? `mock_api` accepts any JSON, so I designed the payloads.
- How should the orchestrator treat exit code 3, a run that succeeded but could not report?
- Should a run with no valid detection fail, or finish with a warning?
- Where does the job id come from? I accept `--job-id` and generate one if it is missing.

## 2. Validation strictness versus fallback

### Where it fails fast

- **Configuration.** Every field is required, unknown keys are rejected, numbers are range-checked and the reporting
  URL is validated. Nothing falls back to a default, and a problem exits with code 2 before any work starts, with every
  problem listed. The prototype defaulted the sport to `"soccer"` while its own config said `"football"`, which is the
  kind of silent mismatch this prevents.
- **The video source.** A file that cannot be opened, or reports an invalid frame rate or size, raises immediately.
  The prototype printed a message and carried on with zero results.
- **Sustained failures.** After `max_consecutive_failures` (5) frames in a row that could not be read or processed,
  the run stops. That pattern means a broken model or a corrupt file, not noise.
- **Wire models.** A `finished` event cannot be built without a summary, and a `failed` event cannot be built without
  an error.

### Where it falls back, and why

- **A single bad frame is skipped, not fatal.** It is counted under one of five reasons (`no_detection`,
  `invalid_geometry`, `implausible_coverage`, `read_failure`, `processing_error`), and the two failure reasons are
  logged with a traceback. Nothing is absorbed silently: every skipped frame appears in the final summary.
- **Reporting problems never change the pipeline's outcome.** Events are retried with backoff on connection errors
  and server errors. A rejected payload (4xx) is not retried. Progress updates are best effort and pause after three
  failures in a row, so an unreachable service cannot stall the run.
- **Reporting can be switched off explicitly** with `"reporting": null`. The key is still required, so this is a
  visible choice and not a missing value.

### The two kinds of failure stay separate

| Pipeline | Platform told | Exit code |
|---|---|---|
| OK | yes | 0 |
| Failed | yes or no | 1 |
| Bad config | not applicable | 2 |
| OK | no | 3 |

I checked the last row in Docker with `mock_api` stopped. The pipeline finished, the log says the outcome could not be
reported, and the container exited 3.

### Aggregation

Valid detections are combined as they arrive into a count and the mean, minimum and maximum area in pixels. No
per-frame results are kept, so memory does not grow with the length of the feed. The area is the part of the boundary
inside the frame, measured against the real frame size.

## 3. Performance trade-offs

- **Time-based sampling.** One frame per `sample_interval_seconds` is inspected. With a known frame count the source
  seeks straight to each sample. Otherwise it reads forward. I measured both skipping strategies on the 1800-frame feed:

  | Strategy | 1 s interval | 5 s interval |
  |---|---|---|
  | Read every frame | 0.69 s | 0.69 s |
  | Skip with `grab()` | 0.17 s | 0.16 s |
  | Seek | 0.18 s | 0.04 s |

  Seeking wins for long intervals and ties for short ones, which is why it is used when the length is known.
- **Against the prototype.** The prototype's `sleep` alone cost at least 9 s for 1800 frames. The analysis now takes
  about 0.26 s at a 1 s interval. The `sleep` was a stand-in for model latency, so it is gone, and the real cost is
  whatever the detector takes per sampled frame.
- **The limit of this approach.** A video twice as long, at the same interval, has twice the samples. I measured 0.26 s
  for 1800 frames and 0.44 s for 3600. Time scales with what is inspected, not with the file length, but a longer video
  at a fixed interval is still more work. A cap on samples or a time window would bound it, and I did not build one.
- **Accuracy given up.** Anything shorter than the interval can be missed. The interval is one number in the config
  and is the dial between throughput and accuracy. It is also subject to aliasing: the generator's trapezoid repeats
  every 30 frames, so a 1.0 s interval at 30 fps always samples the same phase. I did not add jitter.
- **Other repeated work.** The frame rectangle is built once per run, not once per frame. Aggregates are running
  totals, not lists.
- **Not verified.** I only tested seeking on the generator's MPEG-4 output. Seeking on other codecs, especially
  long-GOP H.264, can be inexact or slow, and would need checking on real footage. When a file reports more frames than
  it holds, the trailing samples fail to read and are counted as read failures instead of ending the run quietly.

## 4. AI/LLM disclosure

> **To complete before submitting.** The assignment PDF and `ASSIGNMENT.md` disagree: the PDF says AI tools are
> "strictly prohibited unless explicitly stated", while `ASSIGNMENT.md` asks for disclosure of LLM use. I have not
> resolved that with the reviewer. The text below states what happened, and the bracketed parts are for the author to
> fill in.

I used **Claude Code (Claude Sonnet 5)** in the editor for this exercise, in a single long conversation.

**What Claude did.** Most of the code, tests and documents in this repository: the package layout, the pydantic config
and payload models, the detector interface, the sampling reader, the frame classification and failure policy, the JSON
logging, the HTTP reporter, the runner and exit codes, the Dockerfile and compose changes, and these two documents. It
also ran the prototype and the Docker stack, and produced the measurements quoted above. The design choices in this file
were proposed by Claude, including the decision to change the placeholder detector.

**What I prompted for.** I asked for a summary of the assignment, for the repo structure and Git setup, and then asked
for each next part in turn. My prompts were short and mostly of the form "do the next". [Describe anything more specific
that you asked for or changed direction on.]

**What I did by hand.** I created the private repository and invited the reviewer, ran the prototype and the commands
I was given, and made every commit and push myself, with my own commit messages. [Add anything you edited, rewrote,
tested or decided yourself, and how you checked that you understand the code.]

**Caveats.** The 78 tests were also written by Claude, and Claude ran them and the Docker end-to-end check. [Confirm
that you have run them yourself.] They check Claude's own reading of the assignment, so they are evidence that the code
does what it was designed to do, not that the design is what the reviewer wants.
