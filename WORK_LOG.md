# Parking prototype work log

Recorded on 9 September 2026, Malaysia time. This file documents the work completed in the planning and implementation conversation, the evidence collected, and the remaining dependencies. The operational instructions are in [README.md](README.md); measured verification results are in [VALIDATION.md](VALIDATION.md).

## Request and boundaries

The user requested a backend language recommendation, research into online parking camera input, and an OpenCV prototype that retrieves frames and estimates parking occupancy. The user intends to use Flutter later, does not want camera hardware installed, and excluded MOG2 and other application components from this stage.

The user also explained that the proposal was written for subject submission and does not represent every personal implementation decision. Accordingly, its contents were treated as project background, not additional instructions or authorization. The original `NgJiYeung_23026479_proposal.docx` was read and left unchanged.

During planning, the user selected:

1. Indoor or underground parking only.
2. A genuinely live camera rather than internet recordings.
3. An authorized existing indoor camera as the source route when no working public alternative was verified.
4. Camera access as an outstanding prerequisite; no authorized camera URL was available yet.

The plan was then explicitly approved for implementation. The later request to continue and document all work led to this work log in addition to the setup guide and validation report.

## Environment inspection

The project folder initially contained only the proposal and no application code. Relevant workspace and parent locations were checked for `AGENTS.md`; none was found. The Windows environment was inspected without altering the proposal.

The bundled Python 3.12.14 runtime was available. OpenCV, the selected HTTP client, and pytest were not initially available in the runtime checked. A separate `.venv` was created in the project and the required packages were installed there. Global Python packages and system security settings were not changed.

The document skill was used for read-only proposal extraction. The Computer Use guidance was read, and the requested browser capability was used to inspect the candidate webcam. No account creation, owner messages, hardware configuration, or credential acquisition was performed.

## Proposal findings used in the implementation

The relevant proposal sections described periodic snapshots, predefined polygonal parking spaces, confirmed-empty references, grayscale appearance comparison, traceable identifiers, timestamps, unknown/stale states, and calibration/evaluation separation.

These ideas were retained for the prototype:

- One camera view with manually defined bay polygons.
- A configurable initial interval of three seconds.
- Separate manually confirmed empty references for individual bays.
- Normalized grayscale mean absolute difference within each polygon.
- Explicit occupied, vacant, uncertain and unknown states.
- Source, frame, and bay identifiers; capture, retrieval and processing metadata.
- Handling for failed retrieval, stale evidence, changed view, and invalid configuration.
- Evaluation reporting that separates correctness from decision coverage.

The proposal's ONVIF installation/discovery, MOG2 branch, probability fusion, YOLO verification queue, three-frame confirmation state machine, PostgreSQL, FastAPI/REST/WebSocket services, Flutter interface, and VPS deployment were not implemented. No raw difference value is described as a calibrated occupancy probability.

## Online source research

The attached screenshot was used as a list of leads, not as verified evidence of source suitability. Research covered recorded-media APIs, labelled parking datasets, public webcams, and indoor/underground parking feeds. Searches in several languages also returned construction-site cameras and garage entrances, which would not establish visibility of indoor parking bays.

| Source | Finding and decision |
| --- | --- |
| [Pexels API](https://www.pexels.com/api/) | Provides recorded media; does not satisfy the selected live-camera requirement. Its key process is per-account, not a shared public camera key. |
| [Pexels key documentation](https://help.pexels.com/hc/en-us/articles/900004904026-How-do-I-get-an-API-key) | Verified that users obtain personal keys. No account or key was created. |
| [PKLot](https://web.inf.ufpr.br/vri/databases/parking-lot-database/) | Labelled outdoor parking images with bay coordinates; useful as a research lead but does not meet live indoor constraints. Not downloaded or used as the test source. |
| [CNRPark](https://cnrpark.it/) | Investigated as a dataset lead. The attempted direct website fetch timed out. Not selected or presented as verified live input. |
| [Toronto underground webcam listing](https://camguide.net/canada/ontario/toronto/parking/) | Opened in the browser. The embedded Nest player displayed “This camera is missing in action” and said it might no longer be publicly available. Rejected as a usable source. |
| [Windy webcam API](https://api.windy.com/webcams) | Reviewed as a webcam catalogue alternative. No working indoor parking view satisfying the requirements was verified. No subscription or key was obtained. |

The result was **no verified suitable public live indoor endpoint**, not a claim that none exists anywhere. The agreed route remains an owner-authorized URL for an existing indoor camera. Recorded footage was not substituted for that requirement, and no shared/private key found on the web was used.

## Backend decision and project setup

Python 3.12 was selected to keep OpenCV image processing, array operations, HTTP acquisition, calibration and reporting in one small program. Python can support a future Flutter-facing backend, but the current deliverable is a local command-line experiment.

Created:

- `pyproject.toml`: package metadata, Python version range, dependencies, development dependencies, and command entry point.
- `.venv`: isolated installed environment.
- `requirements-tested.txt`: exact verified dependency versions.
- `setup.ps1`: repeatable setup using tested versions and preservation of an existing local configuration.
- `run.ps1`: Windows command wrapper.
- `config.example.json`: credential-free camera/settings template.
- `config.local.json`: initial local copy; intentionally still lacks a camera URL, setup image, polygons and references.
- `.gitignore`: exclusions for local credentials/configuration, captured data, generated runs and environment/cache files.

## Implemented behavior

| Area | Work completed |
| --- | --- |
| Configuration | Validates IDs, source type, environment-variable names, retry limits, timeouts, image-size limit, alignment parameters and parking polygons. Rejects invalid or self-crossing polygons. |
| HTTP input | Retrieves and decodes snapshots; supports environment-based headers and Basic authentication; rejects redirects and oversized/invalid responses; uses fixed safe error codes. |
| Stream input | Uses OpenCV/FFmpeg in a separate process, continuously reads frames, bounds the pending-frame queue, and terminates stalled workers. Local recording paths are rejected as live URLs. |
| Retrieval bounds | Configurable connect/read timeouts, bounded retries and backoff. Snapshot processes also enforce a total attempt deadline to handle trickling responses. |
| Capture metadata | Records source/frame IDs, optional provider capture timestamp, UTC retrieval time, source-time availability, session ID and decoded-image hash. No capture timestamp is invented from the download time. |
| Setup tooling | Captures setup frames; supports mouse-drawn polygons and JSON polygon import; stores a fixed setup view. |
| References | Requires explicit manual empty-bay confirmation. Saves references independently per bay and invalidates calibration on replacement. |
| Alignment | Matches background ORB features outside expanded parking masks, estimates a transform with RANSAC, checks feature spread and inliers, and rejects substantial displacement or changed resolution. |
| Appearance analysis | Applies grayscale conversion and 5×5 Gaussian smoothing, then calculates normalized masked mean absolute difference against the bay's empty reference. |
| Calibration | Requires five unique vacant and five occupied examples per bay; fits the agreed percentile boundaries; keeps overlapping distributions uncalibrated. |
| Configuration consistency | Associates calibration with reference-image content, setup-image content, polygon geometry and preprocessing version. Changed inputs cannot silently reuse old thresholds. |
| Occupancy calculation | Provides a single percentage only when all monitored bays are classified; otherwise reports bounds and unresolved count. Invalid frames make current occupancy unavailable. |
| Reporting | Provides optional OpenCV preview, annotated PNG, latest JSON, JSON Lines history, summary CSV and per-bay CSV. States use text as well as color. |
| Failure handling | Writes an unavailable/stale current result instead of reusing an old percentage; preserves earlier successful results as timestamped history. |
| Storage | Retains one latest annotated image; rotates each history file around 10 MiB with three backups. Explicit captures/references remain local for research. |
| Evaluation | Checks reference/calibration image reuse and session overlap; reports classified accuracy, coverage, false-vacant/false-occupied errors, ambiguous exclusions and latency. |

The source is organized into `config.py`, `sources.py`, `vision.py`, `output.py`, `evaluation.py` and `cli.py` under `src/parking_probe`, with package and module entry points.

Commands implemented: `check`, `capture`, `configure`, `reference`, `label`, `calibrate`, `run`, `evaluate`, and explicitly offline `analyze-image`. Full examples and output field meanings are in the README.

## Verification and fixes

The first full automated test run completed with 45 passes and one streaming failure. Investigation found that OpenCV 4.14.0 in this environment does not expose `cv2.setLogLevel`. The optional call was guarded, while native diagnostic suppression remains in place. The targeted streaming test then passed.

A subsequent full run passed 46 tests. During final review, an explicit null calibration value was found to need the same handling as an absent calibration. That edge case was fixed and covered with a regression test. An image-size-limit test was added, and the stream test was extended to read a second recent frame.

A full run then passed 48 tests. One final integration test was added to exercise the actual `run` command from a local HTTP simulator through analysis and report writing, then verify that a failed retrieval clears current occupancy while retaining successful history. The final recorded full run passed **49 tests in 15.56 seconds**. The XML result is in `runs/verification/tests.xml`. Dependency consistency and Python compilation checks also passed.

The installer was updated to prefer `requirements-tested.txt`, then rerun successfully in the existing environment. The Windows launcher displayed the complete command help. Existing local configuration was preserved. Fresh-machine installation has not been tested.

`scripts/verify_prototype.py` was added and executed to exercise the complete comparison/calibration/reporting path with deterministic generated patterns. It created 20 calibration frames and 30 held-out synthetic frames across two artificial bays. Of 60 bay observations, 55 were classified correctly and 5 remained unresolved, giving 91.67% decision coverage. Median detector processing time was 15.28 ms and p95 was 17.77 ms on this machine. These are controlled software checks, not real parking measurements.

The normal annotated synthetic output and the failure output were opened and visually inspected. Text was readable, occupancy/counts matched the generated example, timestamps were separated, and failure output showed unavailable occupancy. The image itself is labelled “SYNTHETIC SOFTWARE TEST — NOT PARKING FOOTAGE.”

No 30-frame manually labelled real-camera evaluation has been performed. The synthetic report explicitly marks the real evaluation requirement unmet. See the validation document for artifacts, exact package versions, metric definitions and untested areas.

## Documentation delivered

- `README.md`: installation, camera access, configuration, polygon/reference setup, labelling, calibration, running, evaluation, credentials, timing, output interpretation and limitations.
- `VALIDATION.md`: test evidence, synthetic measurements, visual inspection and remaining real-world checks.
- `WORK_LOG.md`: this end-to-end record of the research, decisions, changes, fixes and status.

## Status before the recorded-video request (superseded below)

The authorized software portion is implemented and verified with controlled inputs. The real camera-dependent portion remains blocked by the acknowledged absence of an authorized live indoor camera URL.

To complete real validation:

1. Obtain the operator's approved snapshot or direct live-stream URL and any required credentials, without installing new camera hardware.
2. Set the environment variables and permitted sample interval; run `check` and inspect captured frames for indoor bay visibility and source freshness.
3. Configure the actual visible parking polygons and manually confirm empty references.
4. Collect and label calibration frames with both states for each bay; calibrate and inspect unresolved distributions.
5. Collect at least 30 distinct, manually labelled real frames across at least two separate new recording periods and run evaluation.
6. Report the actual accuracy, coverage, error rates and timing, including any lighting, glare, occlusion or alignment failures.

No further app components, MOG2 work, hardware changes, camera-owner contact, account signup, or deployment were performed.

## 2026-09-10: recorded indoor video and short launch guide

### Updated authorization

The user explicitly accepted recorded parking footage when a live indoor source is unavailable, preferred indoor footage, requested that the URL be placed directly in code, and asked for a brief guide explaining what they need to do. This supersedes the earlier live-only restriction. The OpenCV-only scope is unchanged.

### Source research and visual inspection

Public source pages and repository metadata were checked, and candidates were downloaded for actual OpenCV inspection. Public video URLs were used without private API keys, accounts, camera discovery or access-control bypasses.

| Candidate | Finding and decision |
| --- | --- |
| [Pexels 8996215](https://www.pexels.com/video/time-lapse-footage-of-parked-vehicles-8996215/) | Despite its parking/time-lapse description, sampled frames showed a moving dashcam passing through a garage and outdoors. Rejected for fixed polygons. |
| [Pexels 4707190, Ricky Esquivel](https://www.pexels.com/video/a-car-stopping-in-a-parking-lot-4707190/) | Fixed low-angle indoor/covered garage view, with a car entering and stopping in a visible foreground area. Selected for a one-region demonstration. Painted bay boundaries are not clear enough to claim actual bay counts. |
| [8harath/Car-Parking-Detection](https://github.com/8harath/Car-Parking-Detection) | Clear aerial outdoor lot; inspected the public `carPark.mp4`, but camera drift makes it unsuitable as a reliable fixed-view preset. No repository detection code used. |
| [SherkhanAmandyk/Parkingspacecounter](https://github.com/SherkhanAmandyk/Parkingspacecounter) | Inspected `Parking_space_counter-main/input/parking.mp4`; aerial outdoor footage and a black opening frame. Not selected. |
| [DiegoFranDA/Car-Park-Counter-with-UI](https://github.com/DiegoFranDA/Car-Park-Counter-with-UI) | Inspected `carPark.mp4`; clear bays, but measured background displacement reached about 13.8 pixels against a middle setup frame, exceeding the existing 8-pixel guard. Rejected instead of relaxing or bypassing the guard. |

The initially considered extra outdoor demo was dropped after those alignment measurements. Downloaded research clips and inspection frames remain under the ignored `data/video-research` directory, separate from the runnable preset. They are not bundled as successful demos or used for reported accuracy.

Selected direct MP4 URL (also hardcoded as `VIDEO_URL` in `src/parking_probe/video_demo.py`):

```text
https://videos.pexels.com/video-files/4707190/4707190-hd_1920_1080_24fps.mp4
```

The verified clip is 16,132,001 bytes, 1920×1080, 543 frames, approximately 23.976 fps and 22.647625 seconds. SHA-256: `95844b91d16bea399a23ac2c4349e754dbf5f78b42c08b362c4da31bc705e2d7`. Attribution and the Pexels license link are included in code and documentation.

### Implementation

- Added `video_demo.py` with the public URL, byte/hash verification, cached downloads, two bounded retry attempts, size/inactivity/duration limits, partial-download cleanup, and explicit local recorded-video decoding.
- Added `demo` to the CLI. It needs no camera URL, key, local configuration or manual polygon setup. The default preview samples approximately every 0.5 video seconds; `--headless` saves results without opening a window.
- Added a generated preset at 960×540 with one region, `ZONE01`, using polygon `[[325,175],[690,175],[690,310],[325,310]]`. Frame 0 is the reviewed vacant reference. Five distinct empty frames at 0.5/1/1.5/2/2.5 seconds and five occupied frames at 14/15/16/17/18 seconds feed the existing calibration procedure. The full contact sheet was visually reviewed, and is saved for the user as `review-labels.png`.
- Retained Gaussian/grayscale masked difference, percentile boundaries, uncertainty and alignment guards. No automatic scene stabilization, MOG2, YOLO, model training or persistence stage was added.
- Added a `recorded_video` configuration type for generated/offline presets. The live camera source explicitly rejects it, so recorded files cannot accidentally become a live-camera test.
- Added recorded-input metadata and test-region terminology to reports. Capture time and source frame age remain unknown; the video position and local decode/processing times are separate. The demo reports one monitored region and zero verified marked bays.
- Added timestamped output directories and annotated MP4 playback. Existing JSON/PNG/CSV histories remain available. Normal EOF is reported as completion; an interrupted user preview is labelled stopped. An existing output directory cannot be reused and mixed with a new run.
- Added `test_video.cmd` for double-click launch from the correct working directory, without changing execution policy or requiring terminal commands.
- Added `QUICK_START.md` and placed its link and the demo command at the top of the longer README. The guide explains current user actions and the later work needed for real bay occupancy.

### Actual verification and measurements

The new built-in download path fetched the real clip successfully and verified its digest. Full headless playback processed 46 sampled frames through decoding, alignment, comparison, annotation, MP4 writing, JSON and CSV. All 46 passed alignment (maximum measured corner displacement approximately 0.154 pixels). Results were 5 vacant, 20 occupied and 21 uncertain observations, with zero unknown/unavailable frames. Classified coverage was 54.35%; this is not an accuracy claim. Median detector time was 18.66 ms and p95 was 21.40 ms. Original capture time was correctly left unknown.

The end-to-end run is saved at `runs/demo-indoor/20260909T195706_985660Z`. Its annotated video was reopened successfully: 46 frames, 1000×710, approximately 1.998 fps. The final PNG and complete ten-image calibration contact sheet were opened and visually inspected. The final frame shows the marked car region, occupied state, video position, separate wall-clock processing time and an explicit recorded/not-live label.

A three-frame run also executed the OpenCV preview code successfully and reused the verified cache, saved at `runs/demo-indoor/20260909T195926_397593Z`. This checks GUI creation/playback/cleanup; Q/Esc interaction was not automated.

The original 49 tests passed after the implementation. Ten additional cases then covered the public downloader/cache/corruption retry, network failure bounds and partial cleanup, real local video decoding/bounds, EOF versus decode failure, recorded metadata and CSV fields, output-directory reuse rejection, recorded input rejection by live camera code, and invalid sampling intervals. The combined suite passed **59 tests in 14.91 seconds**, with XML at `runs/verification/tests-video.xml`.

### Current result and remaining work

The user can now run the indoor video experiment immediately without entering a URL. This verifies online media retrieval and OpenCV processing on actual parking footage. It does not verify a live camera or measure whole-lot occupancy. Calibration and playback share one short clip; independently labelled multi-period accuracy, false-vacant and false-occupied error rates remain unmeasured. For those later measurements, a stable view of identifiable bays and separate capture periods are still needed. The proposal and existing camera configuration were left unchanged.

## 2026-09-15: elevated camera sources, VS Code Run and a three-second display

### User request and scope

The user asked for 3–4 videos with a fixed camera looking down over multiple parking bays, preferably from the same car park, and a clean display that runs from the VS Code Run button with updates every three seconds. They reiterated that all work must be recorded in Markdown. This follows the accepted recorded-video fallback; no new live-camera prerequisite was imposed. The original proposal was consulted as project context, not treated as instructions overriding the user's scope. Its three-second reporting intent was preserved.

The work remains Python 3.12 plus OpenCV appearance comparison. A small local Tkinter display was added for this requested test interaction. No Flutter, MOG2, YOLO, database, backend web service, deployment, hardware installation, external messaging, or model training was introduced.

### Source research and actual inspection

- Reviewed the previous indoor and aerial candidates. The old Pexels clip was too low to show clearly marked bays; it remains an optional historical CLI example, not the default.
- Inspected the official MEVA dataset's example videos, S3 listings, metadata archive and camera-view/site-map PDF. Ground cameras G424/G328 were too shallow/unmarked, G339 involved PTZ movement, and G336/G340 were not a better match for this setup. The PDF skill was used for camera-map inspection. Research artifacts are in the ignored data/source-research-20260915 directory.
- Considered VIRAT (user agreement required; no agreement accepted), CNRPark (images rather than the requested recordings), and a PNNL/UCF endpoint with certificate-chain failure (verification was not disabled). No private API keys or camera credentials were sought.
- Selected the author-published CHAD dataset: https://github.com/TeCSAR-UNCC/CHAD and https://arxiv.org/abs/2212.09258. Its four cameras cover the same commercial car park; camera 1 provides the clearest elevated view with painted bays. All four selected clips are from this one camera. They are outdoor, oblique downward CCTV recordings, not indoor or perfectly vertical aerial footage.
- The official Google Drive archive contains 412 videos and is 87,967,801,766 bytes. Verified HTTP byte-range support, read the ZIP central directory without fetching the full archive, and selected members 1_029_0.mp4, 1_038_0.mp4, 1_049_0.mp4 and 1_054_0.mp4. The production downloader successfully retrieved these four members only.
- Verified all MP4 sizes, CRC32 and SHA-256 digests, pinned them in catalog.py, and cached all four videos in data/chad. Their combined original size is 292,818,440 bytes. All four have 1920×1080 video at approximately 29.97 fps, with container durations 30.00, 33.00, 19.99 and 33.00 seconds.
- Installed imageio-ffmpeg 0.6.0 only into the ignored data/research-tools inspection directory. Its separately permitted FFmpeg 7.1 executable decoded the complete four clips without errors: 899, 989, 599 and 989 frames. This was for source inspection and does not establish that OpenCV works or bypass its blocked binary. It is not a new application dependency.
- Visually inspected the first/middle/end views of all four videos and 15 calibration candidate frames. Retained labelled static previews in assets/previews and a sample contact sheet in assets/calibration-review.jpg. Cyan outlines in the previews are setup labels, not inferred occupancy.
- Retained the publisher's license in third_party/CHAD-LICENSE.txt and added attribution, links, source details, frame counts and sample choices in VIDEO_SOURCES.md. Original videos are unmodified; preview images are resized/labelled derivatives.

### Three-bay setup and calibration recipe

The selected recordings provide both vacant and occupied examples for three adjacent far-row bays. The remaining visible bays and foreground SUV are outside this preset's total. This avoids treating permanently observed cars or uncalibrated empty spaces as known classifications.

Added presets/chad-camera-1.json with reviewed polygons at 1280×720:
- B01: gray SUV bay in Videos 1/2; empty reference Video 3 at 0 seconds.
- B02: red SUV bay in Videos 3/4; empty reference Video 1 at 0 seconds.
- B03: dark sedan bay in Video 1; empty reference Video 2 at 0 seconds.

Each bay has five vacant and five occupied sample times (seconds 1–5), separate from every 0-second reference. There are 30 labelled bay observations across 15 unique full frames. These nearby frames are correlated and are demonstration calibration examples, not an independent evaluation. The dark sedan exits B03 during Video 1, so departure observations may be uncertain.

The new code extracts reference/sample PNGs with OpenCV only when OpenCV can load, validates resolution before resizing, and invokes the existing alignment and percentile calibration. Cached preset directories are keyed by the recipe, source hashes and OpenCV version. A failed alignment or invalid calibration leaves unknown results and a report; it does not weaken guards or assign arbitrary thresholds. Numeric CHAD thresholds remain unmeasured on this host.

### Implementation changes

- Added src/parking_probe/catalog.py: public archive URL, four clip IDs/names, ZIP locations and pinned digests; bounded download-page parsing, verified small range requests, two range retries, size/time bounds, raw-deflate extraction, partial cleanup, cache checks and corruption recovery. A 200 response to a range request is rejected before reading a huge response body.
- Added root main.py. Running it from VS Code automatically uses the project's .venv when present, sets the project working directory, and starts Video 1. UPDATE_INTERVAL_SECONDS is 3.0; START_VIDEO selects the default clip. URLs remain directly embedded in catalog.py, with no user input prompt.
- Added .vscode settings, a Python/debugpy F5 launch configuration for main.py, and Microsoft Python/debugpy extension recommendations. No global VS Code settings were changed.
- Added src/parking_probe/desktop.py: local Tkinter window with a four-video dropdown, Run/Stop controls, static source previews, camera image, occupied/vacant/unresolved cards, monitored occupancy percentage/range, per-bay state and difference score, and separate processing/video timestamps. Network/analysis work runs in one worker thread; UI events are marshalled through a queue. Results from an old selection are ignored. An unavailable frame clears the current image and counts.
- Added src/parking_probe/monitor.py: automatic preset preparation, recorded-frame extraction, existing OpenCV analysis, annotated preview generation, and Reporter JSON/PNG/CSV output in a fresh timestamped runs/chad/<video-id> directory. EOF is completion; failures write unavailable/stale records rather than reusing a previous occupancy estimate. Run metadata distinguishes recorded input, source IDs, video IDs, decoder/processing times, unknown original capture time, skipped samples and unmeasured accuracy.
- Added display_model.py with pure formatting and a monotonic three-second replay schedule. Source indices use rounded absolute video times instead of adding a rounded stride. Overdue samples are dropped instead of replaying a backlog rapidly. Normal timing is a three-second target with processing/drawing jitter; no hard real-time guarantee is asserted.
- Extended recorded CSV fields in output.py with video ID/name and replay timing/skip metadata. Existing snapshot/live behavior and the original config.local.json remain untouched.
- Updated test_video.cmd to launch main.py and updated setup.ps1's final instruction. The older indoor example remains available via python -m parking_probe demo.
- Added scripts/verify_video_sources.py for reproducible separate FFmpeg media verification, and checks/test_desktop_support.py for checks that do not need the blocked OpenCV binary.
- Replaced QUICK_START.md with the brief VS Code steps and required user action. Updated README.md with the new default, commands, output interpretation and historical-demo distinction. Added VIDEO_SOURCES.md and TROUBLESHOOTING.md; updated VALIDATION.md with current evidence and explicit pending tests.

### Windows runtime issue and limits on verification

Importing the existing cv2 extension now fails with: “DLL load failed while importing cv2: An Application Control policy has blocked this file.” Read-only Windows Code Integrity logs identified the existing .venv/Lib/site-packages/cv2/cv2.pyd and signing-policy enforcement, with policy activation logged on 13 September and blocked imports on 15 September. The prior 10 September success is historical.

No Windows protection settings were changed. No blocked DLL was renamed, relocated, re-signed, or loaded through another runtime. The GUI reports the failure clearly and keeps static source previews available without inventing counts. Microsoft documentation was checked: Smart App Control has no per-app allow exception; TROUBLESHOOTING.md links the official FAQ and signing guidance and asks for a trusted, policy-compliant environment through device administration/university IT or publisher review.

The installed dependency versions were retained. An initial preview-generation helper failed because the inspection Python runtime did not contain requests; image preparation and the network license fetch were separated and then succeeded. No extra packages were added to the application's .venv for that helper.

### Checks, corrections and measured evidence

- Four production downloads succeeded, with verified size/CRC/SHA and reusable cache.
- Full separate FFmpeg decode of all four videos passed. An initial metadata parser mistakenly matched the codec's hexadecimal tag as a resolution; the parser was corrected to match actual pixel dimensions, rerun, and now reports 1920×1080 for all four. Evidence: runs/verification/chad-media-inspection.json.
- Added 21 non-OpenCV checks covering the downloader's success and failure paths, retry/range/expansion bounds, pinned catalog, cache corruption, cancellation, frame scheduling, late-sample handling, formatting, sample/reference separation, and real Tk widget construction/render/reset with explicitly synthetic result fixtures.
- The first test run exposed an incorrect test expectation: a 900-frame, 29.97-fps fixture includes frame 899 near 30 seconds. Corrected the expected endpoint, retaining absolute-time sampling. Updated the overdue-sample test after reviewing scheduler behavior. The final support suite passed; full log is runs/verification/desktop-support-tests.txt.
- The Tk test loaded actual source PNGs, updated metrics/table entries from a test dictionary, cleared unavailable data, and switched previews. It was not an OpenCV inference test or a screenshot-based visual QA run.
- The existing OpenCV pytest suite was attempted and stopped during conftest import with exit code 4. It did not execute its historical 59 tests. Log: runs/verification/opencv-suite-current.txt.
- main.py --headless --frames 2 returned exit code 2 and the readable Application Control error. No CHAD occupancy frames were processed. Log: runs/verification/desktop-headless-current.txt.
- Source compilation was checked independently; syntax compilation does not load the blocked extension.

### Remaining dependent work and user actions

The four sources, run entry point, GUI, automatic recipe, output path and documentation are implemented. This computer cannot currently complete OpenCV-dependent validation. The user needs a trusted, policy-compliant OpenCV environment before pressing Run can calculate occupancy.

Once available: run the existing suite, run all four recordings through OpenCV, inspect actual cross-recording alignment and calibration reports, check the three-second display/output behavior and measure processing latency. Then label at least 30 evaluation frames from at least two capture periods separate from calibration; report classified accuracy, decision coverage, false-vacant and false-occupied rates. Videos 1–3 currently supply calibration, so Video 4 alone does not fulfill the two-period evaluation requirement. Additional bays require their own verified empty and occupied samples.

No new CHAD accuracy, real-time timing or OpenCV latency is claimed. The user can already inspect the downloaded original videos, static previews, recipe and guide. The proposal document was not edited.

Final delivery checks: all 21 support tests passed again after the scheduler adjustment (0.216 seconds); Python compilation, JSON parsing and local Markdown link checks passed. The final labelled Video 1 preview was opened and inspected: B01–B03 labels and cyan polygons are readable and do not assert occupancy states. Opening QUICK_START.md in the Codex panel was requested; the app returned queued. Current proposal SHA-256 was recorded as 23eb3797f805394ddea5ef7af5a48b83f3f89291bb24eaaa73265031134b369e; this turn did not write to it.


## 2026-09-15: clarify the blocker and reduce the default to an OpenCV check

The user reported that the video looked frozen, no data appeared, and a separate app popped up. They clarified that the immediate requirement is only to establish whether OpenCV works. The assistant explained that the popup was the Tkinter display it had added, with static source previews independent of OpenCV. A dashboard opening was never evidence that OpenCV loaded; that distinction should have been clearer in the earlier delivery.

A fresh direct import using the project's Python 3.12.14 reproduced the Application Control failure before any video was opened. Read-only checks found the existing cv2.pyd file unsigned, VerifiedAndReputablePolicyState=1, and current Code Integrity event 3077 identifying that exact extension and signing-policy rejection. All four downloaded MP4s remain present with the previously verified sizes. This is an installed-library loading failure, not a missing video, camera URL, API key or manual download prerequisite. A manual download of the same package is not a verified remedy.

Rechecked [Microsoft's Smart App Control FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions), including its explanation of signatures and the absence of individual-app allow exceptions. No security settings or installed packages were changed, and no alternative runtime was used to load the blocked file.

Changes made for the narrowed scope:
- main.py now runs a basic OpenCV check by default. The previously implemented dashboard is retained only through the explicit --dashboard option. The F5 configuration was renamed Basic OpenCV check.
- Added src/parking_probe/opencv_check.py. It prints four stages: importing OpenCV, opening the supplied recorded video, decoding/grayscale conversion/Gaussian smoothing, and plain OpenCV playback. It does not calibrate parking bays, calculate occupancy or create a dashboard. If loading succeeds, a continuous OpenCV video preview shows a frame counter, with terminal information about every three seconds; Q/Esc closes it.
- The diagnostic saves the actual failed/successful stage, version, processed-frame counts and error to runs/opencv-check/result.json. A successful image-processing check would additionally save first-frame-grayscale.png. --headless --frames 3 checks decoding/processing without any window.
- Updated QUICK_START.md, the README's default entry point and optional dashboard commands, TROUBLESHOOTING.md and VALIDATION.md to remove ambiguity about what Run does.

Actual verification: main.py --headless --frames 3 returned exit code 2, stage opencv_import, status failed, zero decoded frames, zero processed frames and no saved grayscale image. The error was readable in the terminal and the JSON report matched it. Evidence was saved to runs/verification/basic-opencv-check.txt. Syntax checks passed. The import failure means video decode, grayscale/blur and playback remain untested by this new diagnostic; no successful OpenCV result was claimed.

The videos do not need another download. Further parking-dashboard work is deferred. The remaining prerequisite is resolving the Windows trust/signing block with an appropriately trusted OpenCV environment; the existing security settings were left intact.

## 2026-09-15: personal-computer guidance

The user confirmed this is their personal computer and asked what to do to make OpenCV work. Microsoft’s current Smart App Control FAQ and Windows Security settings guide were checked again. The troubleshooting document now explains the user-controlled option to turn Smart App Control off through Windows Security, the fact that this changes protection for all apps, and the need to keep Defender antivirus/real-time protection enabled. It also describes keeping Smart App Control on and seeking a publisher-supported trusted/signed build as the alternative; no such replacement has been verified here.

The guidance asks the user to read the on-screen re-enabling warning before confirming. Microsoft’s current FAQ says recent updates allow re-enabling without reinstalling, while its general settings article still contains older reset-related restrictions; reversibility is therefore not promised for this specific installation. No reset is recommended. After a user-chosen change, a fresh main.py run is the verification step, and any further error must be diagnosed separately.

No Windows security settings, packages or application code were changed in this turn. No new OpenCV success is claimed: the most recent actual check still failed during import, and the user has not yet reported making a setting change. No manual video download is needed. Sources: [Microsoft FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions) and [Windows Security settings](https://support.microsoft.com/en-us/windows/security/windows-security/app-browser-control-in-the-windows-security-app).


## 2026-09-15: working OpenCV and occupancy output every three seconds

### User clarification and verified starting point

The user supplied a successful basic-check log and asked whether it reported occupied parking, reiterating that they need an occupied/vacant report every three seconds. The basic log explicitly stated that occupancy was not tested. Its on-disk result confirms OpenCV 4.14.0, Python 3.12.14, 1920×1080 input, 899 decoded/processed/preview frames, status passed and occupancy_tested=false. The user was told this verifies the image-processing pipeline, not parking classification.

The previous Windows import block no longer reproduces in this session. The assistant did not change or reconfigure Windows security, reinstall packages, or attempt to load the old blocked file through a different runtime. Normal project OpenCV imports and execution now succeed.

### Default Run behavior

Added src/parking_probe/terminal.py and changed main.py so a normal VS Code Run/F5 performs parking analysis and prints a compact ASCII table. The table shows processing time, video time, B01/B02/B03 states, occupied/vacant/unresolved counts, monitored occupancy percentage or range and detector duration. Processing timestamps include milliseconds; video labels round the nearest source frame to the intended 00:00, 00:03, 00:06... positions. The precise source position is retained in JSON/CSV.

No dashboard opens by default. The user can change START_VIDEO in main.py or use --video chad-2/chad-3/chad-4 to select the other supplied recordings. The original basic check remains available through --check, and the optional Tkinter display through --dashboard. Those two flags are rejected if supplied together. The F5 configuration was renamed Parking occupancy - every 3 seconds. test_video.cmd follows main.py's new default.

The terminal uses the existing monitor.run_recording pipeline and output files. --frames limits observations; --fast is explicitly marked as accelerated verification and skips wall-clock waits. Ctrl+C records the run as stopped and retains history. Failed decoding records unavailable occupancy and never substitutes the prior estimate as current.

Added occupancy_table to display_model.py. Unknown/unavailable frames are displayed explicitly, with unavailable counts marked -- instead of an apparently empty lot. The console explains uncertainty and the three-bay scope. Difference scores remain in JSON/CSV and are not labelled as confidence.

### Calibration issue found during actual replay

The original five samples per state covered only seconds 1–5. The first full accelerated runs showed that later appearances frequently fell outside those narrow distributions, leaving many obvious static bays uncertain. Those diagnostic outputs are retained as runs/verification/occupancy-chad-1-fast.txt through occupancy-chad-4-fast.txt.

Thirty selected views spanning Videos 1–3 were extracted with OpenCV and visually reviewed in a contact sheet. The images covered the gray SUV, the red SUV, the sedan departure and later empty bays; some vacant-bay examples include pedestrians. Added reviewed samples through an optional additional_samples field in the recipe and extended preset preparation to read them. The complete recipe has 99 labelled bay examples across 39 distinct full frames, with no reference image reused as calibration and no duplicate frame/slot pair.

Final sample counts: B01 has 10 vacant and 25 occupied examples; B02 has 21 vacant and 11 occupied; B03 has 26 vacant and 6 occupied. All examples are from Videos 1–3; Video 4 is excluded from calibration. The exact timestamps are documented in VIDEO_SOURCES.md and presets/chad-camera-1.json. The expanded contact sheet is assets/calibration-review-expanded.jpg, and the full-resolution inspected images remain in runs/verification/calibration-review-expanded.

The polygons, setup frame, zero-second empty references, Gaussian/grayscale normalized pixel-difference method, alignment guard and percentile rules were unchanged. No MOG2, YOLO, arbitrary confidence value, forced binary classification or automatic empty-reference replacement was added. The recipe hash produces a new preset directory, data/chad/preset-608ae95f8e05c30d, retaining the earlier preset.

Actual vacant-max / occupied-min boundaries:
- B01: 0.0928724103 / 0.4275638460.
- B02: 0.0195616106 / 0.4484225195.
- B03: 0.0144162118 / 0.3318076261.

The calibration expansion was driven by observed limitations and uses demonstration recordings; improved replay results are not an independent accuracy evaluation.

### Actual occupancy results and timing

All four recordings completed through OpenCV decoding, alignment, per-bay scoring, annotation and file reporting. There were 39 sampled frames and 117 bay observations: 39 occupied, 68 vacant, 10 uncertain, zero unknown, and zero unavailable frames. Classified coverage was 107/117 = 91.45%; coverage is not accuracy.

Per-video observed coverage was 86.67%, 87.88%, 90.48% and 100.00%. Median detector times were 28.90, 29.74, 28.99 and 28.36 ms; p95 times were 33.17, 37.88, 30.44 and 39.90 ms. Maximum measured camera displacement was about 0.9824 pixels, below the existing 8-pixel limit.

Video 1 reported B01 occupied, B02 vacant, B03 occupied at 0 and 3 seconds (66.7%). B03 became uncertain during departure, then vacant from the 18-second sample onward (33.3%). Video 4 reported B01 vacant, B02 occupied and B03 vacant at all 11 sampled times. Final annotated outputs for Videos 1 and 4 were opened and visually inspected; the marked bays, states and scope were readable. The foreground SUV remains excluded.

A normal main.py --frames 5 run, without --fast, produced observations at source times 0.000, 3.003, 6.006, 9.009 and 12.012 seconds. Actual successive processing-start intervals were 2.9352, 3.0125, 3.0433 and 2.9523 seconds, with no skipped samples. This verifies the approximately three-second schedule; decoding, computation and OS scheduling introduce small jitter.

Evidence:
- runs/verification/chad-occupancy-measurements.json contains run directories, source metrics and calibration metadata.
- runs/verification/occupancy-chad-<1..4>-expanded.txt contains the complete accelerated terminal output.
- runs/verification/occupancy-three-second-run.txt and occupancy-timing.json contain the timed check.
- Each referenced runs/chad directory contains latest.png, latest.json, history.jsonl, summary.csv, slots.csv and run.json.
- The user's successful 899-frame basic-check result remains in runs/opencv-check/result.json.

### Software checks and documentation

The restored original suite passed 59 tests in 20.42 seconds. Four new tests then exercised explicit terminal states/ranges, unavailable values rather than false zero parked counts, actual lossless local-video replay through analysis/reporting, and a simulated later decode failure preserving prior history while clearing current occupancy. The full pytest suite passed 63 tests in 21.87 seconds; 21 support checks passed separately in 0.763 seconds. The recipe-support check was extended to reject duplicate/reference samples across additional groups and to ensure Video 4 is excluded from calibration. The video-clock check now covers 17.9846 seconds rounding to the intended 00:18 display.

Updated QUICK_START.md with Run instructions, actual state examples, selecting videos, state meanings and saved results. Rewrote the README's default instructions around terminal occupancy, preserving advanced camera setup and optional tools. Updated VIDEO_SOURCES.md with expanded calibration provenance and VALIDATION.md with current measured results. TROUBLESHOOTING.md now identifies the Windows failure as historical and explains the difference between normal Run and --check.

Remaining limit: this is per-observation experimental occupancy for B01–B03. Independent classified accuracy, false-vacant/false-occupied errors and the planned 30-frame/two-independent-period evaluation remain unmeasured. No application backend, Flutter work, web service, database, deployment or persistence-confirmation stage was added.

Final checks: the four terminal/replay tests passed again in 2.04 seconds after adding millisecond timestamps. Python syntax and local Markdown links passed validation, and the generated manifest was confirmed to contain 99 rows referencing 39 unique frames. A readable rendering of the measured timed run is saved to runs/verification/terminal-format-example.txt. Showing the short guide in the Codex panel was requested; the app returned queued.

## 2026-09-17: shared physical bay IDs and ten-second summaries

### Request and scope

The user requested continuation, recognition of the same parking bay across views, unique IDs, reconciliation of different view results, a per-bay occupancy rate/state and a clean summary of each preceding ten-second window. The previously working default already classified three marked bays every three seconds. The extension retains that sampling interval and adds the requested ten-second reports. All work remains local Python/OpenCV, with no MOG2, YOLO, Flutter, database, web service or deployment. No Windows settings, packages, original proposal, calibration labels, reference images, thresholds or source video files were changed.

The user suggested marking slots in each view and mapping their IDs. Implemented this explicit, manually verified correspondence. Automatic visual matching of unfamiliar viewpoints is not implemented. The same physical bay has one registry ID and any number of view-specific polygons; it contributes once to the site count. The current four CHAD clips are separate periods from camera 1, so they continue to run individually and are not misrepresented as simultaneous cameras.

### Identity and conflict policy

Added src/parking_probe/bay_fusion.py. It maps camera/local-slot pairs to physical bay IDs and preserves per-view states, raw appearance scores, frame IDs, timestamps, ages and failure reasons. Built-in local B01/B02/B03 map to CHAD-P001/CHAD-P002/CHAD-P003, with the same mapping for every selectable CHAD clip.

All usable views must agree for a definite occupied/vacant state. Occupied versus vacant produces uncertain; a usable uncertain observation also keeps the fused result uncertain. No raw-score averaging or majority voting is used because normalized pixel differences are neither probabilities nor directly comparable calibrated confidence values. A missing/stale view cannot vote. Remaining usable views may supply a fallback, explicitly marked degraded with usable/expected view counts. No usable view produces unknown. Usable views with frame times differing by more than 0.1 seconds produce uncertain. Stale/future observations are rejected. Correctness of the user's declared physical mapping and synchronization still requires visual/source verification.

### Window semantics and display

TimeWindow integrates each physical bay's fused state over time, holding each sampled decision until the next observation or explicit camera-end/failure event. It closes [0,10), [10,20), etc. A sample exactly on a boundary belongs to the next window. The final shorter window uses its actual duration and is labelled partial. This is sampled-state duration estimation, not continuous ground truth or the proposal's deferred confirmation stage.

The displayed per-bay rate is occupied seconds / window seconds. Uncertain/unknown time expands the upper bound rather than becoming vacant or an invented probability. Classified time is the share with a definite occupied/vacant state. The latest state is shown separately from the duration rate: a bay can now be vacant after being occupied earlier in the window. Site counts/occupancy below the table use the latest state before the boundary and count each physical bay once. All-unknown current site occupancy is unavailable.

Updated terminal.py and the main.py description/F5 label. Normal Run prints compact three-second state rows and aligned ten-second tables with ID, latest state, occupied-time range, coverage, view support and conflict/missing-view detail. It opens no dashboard. The existing --check diagnostic and optional older --dashboard remain separate. The earlier dashboard keeps its old single-camera reporting; the new feature is in normal terminal mode.

### Recording runner and configuration

Added src/parking_probe/site_replay.py. It reuses preset preparation, calibrated Analyzer, validated Recording decoding and per-camera Reporter. The runner samples all supplied recordings on a common relative timeline using explicit video offsets. Summary deadlines are independent of sampling deadlines. Overdue samples become unknown, with skipped-tick and summary-lateness metadata. Per-camera decode failures and resolution changes preserve unknown/stale results without stopping other usable views; a shorter recording becomes unavailable at its own EOF. Resolution-change reason codes are retained for reconfiguration.

Added site.example.json and --site site.local.json. The example maps camera-a/A01 and camera-b/B07 to P001 while other polygons map to separate physical bays. It contains no secrets and deliberately has unverified mapping/synchronization and placeholder paths. Multiple-camera input requires a verified mapping and a synchronization note; invalid IDs, duplicate cameras, duplicate per-view physical mappings, unregistered/unmapped bays, invalid resolutions/offsets and mismatched calibration IDs/polygons are rejected. The loader rejects the same local video supplied twice as different cameras. No live multistream ingestion or automatic synchronization is claimed. Added site.local.json to .gitignore.

Each run now saves runs/sites/<site-id>/<UTC-run-time>/ with site.json, fused latest/history, latest-window/windows.jsonl, summary.csv, bays.csv, per-camera annotated JSON/PNG/CSV folders and run.json. Per-camera slots carry both local slot_id and shared bay_id. Original capture timestamps remain explicitly unknown. EOF/stop/failure clears current fused occupancy and marks the run inactive; historical estimates stay timestamped. A missing source is never silently counted vacant. Old runs/chad outputs are retained.

Extended output.py annotations to show the shared ID. Visual inspection found that the longer IDs overlapped adjacent labels. Replaced the single label with two centered lines beneath the polygon, with a dark background. A second actual image inspection confirmed separated, readable labels for all three bays. The original annotation layout remains for outputs without shared IDs.

### Verification performed

Added tests/test_bay_fusion.py and tests/test_site_replay.py. Twenty-five initial new cases passed in 9.63 seconds, then the full suite passed 88 tests in 31.38 seconds. Two synthetic lossless videos are actually decoded through OpenCV and the calibrated comparison path. They exercise a deliberate initial camera disagreement, later agreement, one physical count for duplicate views, occupied-time uncertainty, exact boundaries, short final windows, failed decoding, unavailable-camera fallback and different recording lengths. Other tests reject ambiguous mappings and stale/future/unsynchronized evidence. An additional source-resolution regression test was added after preserving that specific failure reason. The final focused suite rechecks all new behavior plus the earlier terminal/replay tests after annotation changes. The separate 21 support checks passed in 1.022 seconds. Test files/results are listed in VALIDATION.md.

Ran main.py normally through all of Video 1: ten sampled ticks, no skipped ticks/errors, and three summaries. Relative to the replay scheduler start, the first summaries were emitted approximately at 10.015 and 20.000 seconds. The final partial window ended at source time 29.996633 seconds and was emitted about 18.4 ms late. Total replay/reporting elapsed time was 30.047 seconds. The preparation/download clock is separate.

Actual first window: P001 occupied, P002 vacant, P003 uncertain; occupied-time estimates 100%, 0%, and 60–100%. At the second window's end P003 was vacant, but its preceding-window rate remained 0–80% because its earlier observations were unresolved. Final partial window: P001 occupied, P002/P003 vacant; 33.3% site occupancy. This verifies that latest state and historical rate are not conflated.

Replayed Videos 2–4 in accelerated verification mode, preserving three-second source sampling while skipping wall-clock waits. All four clips completed: 39 total ticks, 13 summaries including partial windows, 117 bay observations, 39 occupied/68 vacant/10 uncertain/0 unknown camera observations. These match the previous detector outputs; the extension does not improve or assert independent accuracy. Median detector times were 31.32/41.03/48.10/28.81 ms for Videos 1–4, with concurrent testing affecting timings. All window state-duration sums were checked against their window durations; stopped/latest site results were checked as unavailable. Reports and annotated imagery were inspected.

Saved runs/verification/multiview-measurements.json with actual paths, count/rate/timing evidence; multiview-timed.txt with normal console output; multiview-chad-2/3/4.txt with accelerated output; tests-multiview.xml, tests-multiview-final.xml and multiview-support-tests.txt with software check results. The representative corrected annotated image is under the Video 4 run referenced by the measurements JSON.

### Documentation and remaining work

Rewrote QUICK_START.md as a short Run/F5 guide with actual output, meanings of the rate/state columns, changing clips, results locations and the extra inputs needed only for real multi-camera use. Added MULTICAMERA.md with mapping examples, conflict policy, synchronization/offset setup, formulas, output files and limitations. Updated README.md, TROUBLESHOOTING.md and VALIDATION.md to describe current defaults while retaining advanced camera instructions and historical measurements.

The current single-camera demo is runnable without new downloads, credentials or Windows changes. Real cross-camera validation still requires authorized synchronized recordings with shared bays, visibly verified mappings and separate calibrations. The four existing clips do not satisfy that requirement. Automatic visual correspondence, independent 30-frame/two-period accuracy, false-vacant/false-occupied rates and live indoor/multicamera validation remain unmeasured; synthetic tests are not substitutes. The normal run does calculate experimental occupancy, whereas --check remains only the basic OpenCV diagnostic.

Final focused check completed: **30 tests passed in 11.93 seconds**, including the resolution-change case and all new fusion/replay tests plus the previous terminal checks. This follows the 88-test full run and 21 separate support checks reported above.

Final static checks passed for Python syntax, example/launch JSON and local Markdown links. The proposal SHA-256 still matches the original recorded digest. Opening QUICK_START.md in the Codex panel was requested; the app returned queued.

## 2026-09-17–18: CHAD 1–4 together, MOG2 and final historical estimates

### Updated authorization and proposal review

The user asked to run CHAD 2, 3 and 4 together with CHAD 1, develop the proposal's MOG2 section, display both methods' occupied/vacant/uncertain states for each time and bay, and document the work. This explicitly superseded the earlier exclusion of MOG2. The subsequent continuation requested a final occupancy summary. The scope remained Python/OpenCV; no YOLO, logistic probability fusion, three-snapshot confirmation, Flutter, database, service or deployment was implemented.

Read the proposal's DOCX XML as project context without modifying it or executing document instructions. Sections 3.2–3.3 specify one chronological full-frame MOG2 model per camera, shadow exclusion, morphological opening/closing, and the per-polygon foreground proportion. The proposal's broader server and application stages did not expand the user's request. Verified MOG2 API behavior against official OpenCV documentation: [class reference](https://docs.opencv.org/4.x/d7/d7b/classcv_1_1BackgroundSubtractorMOG2.html) and [background subtraction tutorial](https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html). The installed OpenCV package already provides MOG2; no packages or Windows settings were changed.

### MOG2 branch and calibration

Added src/parking_probe/mog2.py. Each recording owns a separate MOG2 model, initialized with a full-frame mosaic containing the verified empty-reference pixels for each bay and stable setup pixels elsewhere. Empty references may come from different moments; the mosaic is an initialization artifact, not an observed simultaneously empty car park. Thirty repeated bootstrap applications stabilize initialization, not thirty independent labelled training examples.

Runtime settings: history 500, variance threshold 16, shadow detection on, explicit learning rate 0.001 per accepted three-second sample, BGR 5×5 Gaussian blur, foreground value 255 only, 3×3 elliptical opening then closing. Shadow label 127 is excluded and its proportion logged separately. The model updates exactly once per chronological frame, then every bay reads the same full-frame mask. Duplicate/backwards updates and mismatched identifiers are rejected. Full-frame resolution, alignment and freshness validation is shared with the existing reference pipeline.

Foreground fraction gets its own calibrated boundaries and state, independent of the reference-distance decision. Neither score is labelled a probability. Missing/invalid MOG2 calibration produces uncertain; unusable frame or reference produces unknown. Gaps over 15 video seconds reset the model, followed by two uncertain observations for restabilization. A MOG2-only processing failure preserves valid reference evidence and requests model reset before recovery. Decode failures clear both methods for the affected recording, retaining other recordings' processing. Stale foreground images are removed on failure.

Added src/parking_probe/mog2_calibration.py. It reuses the 99 visually reviewed labels across 39 frames from CHAD 1–3, rejecting reference reuse and duplicate per-bay image content. CHAD 4 is excluded. Each calibration recording gets a fresh model. State updates use the runtime three-second nearest-frame schedule; extra labelled timestamps use learningRate=0 probes that do not update the background. Labelled PNG content is checked against the source-decoded frame. A dedicated test confirms probes leave subsequent masks unchanged.

MOG2 thresholds use the same minimum-five-per-state / vacant 95th / occupied 5th percentile rule, applied to foreground fraction rather than distance. Measured vacant-max / occupied-min values: B01 0.3147566521 / 0.8357864601 (10 vacant, 25 occupied); B02 0.0004180602 / 0.7727006689 (21 / 11); B03 0.2386392010 / 0.8988764045 (26 / 6). All fitting distributions separated. The stored report is data/chad/preset-608ae95f8e05c30d/mog2-calibration-654b23fa5d5efa80.json, model signature a5f9bb4c13796c53bb84224d0b59ba9f970b60179bdbb05cb79de50c221bc182. Parameters, sampling interval, OpenCV version, setup/mosaic/reference hashes, polygons and labelled image content bind the calibration cache. The original MAD calibration/reference files remain unchanged.

Initialization and slow adaptation address first-frame parked cars for this short experiment; they do not solve all background-absorption or lighting problems. An adaptive MOG2 model may eventually learn a stationary vehicle as background. This 20–33-second footage and its fitting data do not validate long-duration occupancy retention, semantic vehicle recognition, or independent real accuracy.

### Combined runner, output and compatibility

Added src/parking_probe/comparison.py. Normal main.py now sets RUN_ALL_VIDEOS=True, preparing the preset once and advancing CHAD 1–4 together at relative times 0, 3, 6... seconds. Each clip has separate model state, window histories and output folders. These are different periods from one physical camera; they are never merged as synchronized viewpoints or summed into twelve physical spaces. Source capture dates remain unknown.

Every three-second table displays recording ID, shared bay ID, REFERENCE state/difference, MOG2 state/foreground percentage, and method agreement. Agree/disagree applies only to two binary decisions; otherwise the comparison says unresolved. Ten-second tables report each method's latest state and occupied-time bounds, with separate counts/occupancy per recording. The short final windows are labelled partial. A shorter recording ends without stopping the others or looping its model state. Both branches use the same decoded image and their source/frame/time/slot IDs are checked before joining. Processing within a tick is sequential, not a claimed parallel worker system.

Updated main.py, terminal.py and the F5 label. --video chad-1/chad-2/chad-3/chad-4 selects one recording; --video all selects all four. RUN_ALL_VIDEOS=False restores START_VIDEO selection via the Run button. --frames limits common sample ticks; --fast is accelerated verification. The older --dashboard and custom --site modes remain reference-only; this distinction is explicit in the terminal and documents. The original --check remains an import/decode/playback diagnostic. No new GUI is opened by normal Run.

New outputs live under runs/comparison/<UTC-time>: paired observations.csv and history.jsonl, windows.jsonl, per-method summary.csv, bay-windows.csv, copied MOG2 calibration, run metadata, and per-recording reference/ and mog2/ folders with annotated PNG and JSON/CSV histories. MOG2 also saves the cleaned foreground.png. Method-specific annotations identify MOG2 and describe foreground proportion. The images and foreground mask were visually inspected; an updated labelled example was saved to runs/verification/mog2-annotated-example.png. Existing outputs are retained.

### Measured verification

The first accelerated run completed all four recordings after actual calibration. The initial eleven added tests passed in 11.25 seconds. Added a further MOG2-only failure case to ensure valid reference evidence survives and model recovery restabilizes correctly. The full suite then passed **101 tests in 48.23 seconds**, including all earlier tests and twelve new MOG2/comparison cases. Evidence: runs/verification/tests-mog2-comparison.xml.

Tests exercise shadow/noise removal, first-frame parked-car handling, short static-car retention and departure, chronological/duplicate updates, calibration-probe non-mutation, stale/resized-frame rejection, missing references/calibration, signature binding, matching identifiers, actual decoding of four synthetic videos, separate model histories, different lengths, both-branch decode failure, and isolated MOG2 failure. Synthetic scenes verify software behavior, not parking accuracy.

The normal timed all-video run is runs/comparison/20260916T203413_449434Z. It completed **39 sampled frames, 117 paired bay observations and 13 per-recording window summaries**, with zero skipped ticks/errors and **33.062 seconds** of replay/reporting time excluding preparation. First ten-second summaries were approximately 78–94 ms late, and every measured window was within 0–94 ms of its source-time target. Evidence is preserved in runs/verification/mog2-all-timed.txt and mog2-comparison-measurements.json. Accelerated output is mog2-all-first.txt; --video chad-2 --fast --frames 2 was separately checked in mog2-single-chad2.txt.

Reference counts by recording (occupied/vacant/uncertain): CHAD 1 12/14/4, CHAD 2 10/19/4, CHAD 3 6/13/2, CHAD 4 11/22/0. MOG2 counts: 16/10/4, 10/19/4, 6/13/2, 0/22/11. Across 117 bay observations, reference coverage was 107/117 = 91.45%, MOG2 96/117 = 82.05%, with zero unknowns. There were 89 pairs with agreeing binary decisions and 28 with unresolved evidence. These values measure coverage/decision distribution, not accuracy or correctness of agreement. MOG2 leaves CHAD 4's red-SUV bay uncertain rather than adjusting thresholds to force agreement.

Reference median times for clips 1–4 were 32.16/32.25/31.74/32.80 ms; MOG2 incremental medians were 10.38/8.71/10.04/9.72 ms. Reference timing includes shared alignment/validation; MOG2 timing follows that shared check. Decode, reporting and waiting are excluded and concurrent tests affected timings, so this is not a standalone end-to-end method benchmark.

### Final occupancy summary requested on continuation

Added an end-of-run FINAL HISTORICAL ESTIMATE table and final-summary.json/csv. It uses each recording's last paired observation and preserves the exact frame time and both original states. Occupied/vacant requires both methods to agree. Disagreement, an uncertain method or one unavailable method gives uncertain; both unavailable stays unknown. This is an experimental conservative consensus, not logistic probability fusion or temporal confirmation. Historical results are produced for completed/limited/stopped runs; top-level latest.json still marks current/live occupancy unavailable after playback.

Added seven parameterized consensus cases and saved-summary assertions to the comparison integration test. The final focused MOG2/comparison suite passed **19 tests in 17.39 seconds**. A complete accelerated replay reproduced the final states and saved them in runs/comparison/20260917T161258_089149Z; its console output is runs/verification/mog2-final-summary.txt and test XML is tests-mog2-final-summary.xml.

Final three-bay estimates:

| Recording | P001 | P002 | P003 | Counts |
| --- | --- | --- | --- | --- |
| CHAD 1 | occupied | vacant | vacant | 1 occupied, 2 vacant |
| CHAD 2 | uncertain | vacant | vacant | 2 vacant, 1 uncertain |
| CHAD 3 | vacant | occupied | vacant | 1 occupied, 2 vacant |
| CHAD 4 | vacant | uncertain | vacant | 2 vacant, 1 uncertain |

These refer to video positions approximately 27, 30, 18 and 30 seconds respectively. CHAD 2 P001 and CHAD 4 P002 are occupied in reference comparison but uncertain in MOG2, explaining their final uncertainty. They are different recording periods from the same camera, not a live combined car-park state. Only the three marked bays are counted.

### Documentation and remaining limits

Added MOG2.md with the proposal mapping, initialization/chronology/morphology choices, parameters, separate calibration, source links, output semantics, launch commands and limitations. Updated README.md, QUICK_START.md, MULTICAMERA.md, TROUBLESHOOTING.md and VALIDATION.md for the new default and retained legacy modes. Added FINAL_RESULTS.md with the measured final table. This work log records both the original MOG2 request and the final-summary continuation.

No new footage, key, manual download, dependency installation or Windows setting change was needed. The original proposal remains unedited. Independent 30-frame/two-period labelled accuracy, false-vacant/false-occupied errors, long-duration MOG2 behavior, real synchronized-camera correspondence and live indoor validation remain unmeasured. No claim of calibrated probability or production-ready confirmed occupancy is made.

Final static checks passed: Python syntax, launch JSON, local Markdown links, proposal hash unchanged, and saved final-summary states matching FINAL_RESULTS.md. Opening FINAL_RESULTS.md in the Codex panel was requested.

## 18 September 2026 — Occupancy chart and video navigation

The user requested an interface with a circular occupied/total chart and navigation to video or live video. Added a native Tkinter interface using the existing environment; no dependency installation, Windows setting change, additional media download, external service or hardware setup was required. Normal Run/F5 now opens this interface. The previous requests for terminal-only output were superseded by this explicit interface request; `--terminal` retains that workflow.

### Implemented behavior

- Occupancy overview: colour-coded donut, occupied/3 centre, exact percentage or unresolved range, four count categories and per-bay Reference/MOG2/final states. The same conservative consensus rule is reused without changing the detectors or calibration.
- Four CHAD selectors: each recording retains its own three physical bay observations. Different recording periods are never combined into twelve spaces or a simultaneous-camera estimate.
- Watch video: actual local recording decoder, coloured bay outlines, count strip, Play/Pause, Replay and seeking. Chart and overlay follow the selected playback position. Missing/failed decode clears displayed occupancy rather than retaining a misleading current state.
- Ten-second summaries: separate tab shows the latest completed window, method counts and per-bay occupied-time estimates/ranges. The final short window is marked partial.
- Timing: prepare all four clips chronologically in a worker, preserving MOG2 state order; then play recorded media at normal elapsed-time speed with up to about 15 preview frames/s. Samples are selected at or before playback time, every three video seconds. Backward seeks cannot reveal future observations or mutate MOG2. Processed-at is actual preparation time, source capture time remains unknown, and EOF is explicitly historical.
- Live Camera: configuration picker, Connect/Disconnect and bounded background retrieval through existing CameraSource. HTTP snapshots honor the configured interval; direct streams use their latest decoded frame. Live frames are limited to 960×540 while preserving aspect ratio, and the queue holds at most two packets. Failed/stale/expired inputs clear the preview; disconnect generation IDs prevent late old frames from restoring it. Addresses and credentials remain in environment variables and are not printed or persisted. This is a live viewer only; no public authorized live parking URL is configured and CHAD occupancy settings are not applied to new cameras.
- Open saved results opens this run's folder. Analyze again creates another run. Preparation progress remains visible. The UI layout was corrected after screenshot inspection to fit the actual 1280×720 display with all controls visible.

### Files and compatibility

Added `src/parking_probe/interface.py`, `interface_model.py`, `tests/test_interface.py`, `checks/check_interface.py` and `INTERFACE.md`. Updated `main.py`, `.vscode/launch.json`, `QUICK_START.md`, `README.md`, `MOG2.md`, `FINAL_RESULTS.md`, `TROUBLESHOOTING.md` and `VALIDATION.md`. The original proposal, camera configuration, video files, polygon recipe, references and algorithm modules were not edited.

`--dashboard` aliases the new interface; `--legacy-dashboard` preserves the original reference-only window. `--check` preserves the basic OpenCV diagnostic. `--terminal`, or legacy automation flags `--fast`/`--frames`/`--site`/`--headless`, select console behavior. In the UI, `--video`/START_VIDEO selects the initial display while all four clips are analyzed; RUN_ALL_VIDEOS applies only to terminal mode. Existing JSON/CSV/annotated outputs remain in `runs/comparison/<UTC-time>/`.

### Validation and measured outcomes

The complete suite passed **120 tests in 48.52 seconds**, including 12 new interface tests. Tests cover chart arithmetic, preserving uncertainty/unknowns, selecting no future/wrong-recording observations, resetting windows after seek, clearing stale/error/disconnected previews, bounded queues, sanitized errors, missing camera URLs and actual synthetic local HTTP snapshot/MJPEG decoding. Test evidence: `runs/verification/tests-interface-full.xml`. An initial GUI-test run encountered a Tcl error after repeatedly creating/destroying independent Tk interpreters; the test fixture now shares one interpreter with isolated Toplevel windows, matching a single running application's lifecycle. Production startup uses one Tk root.

Three actual interface runs verified 39 sampled frames (10/11/7/11 per CHAD clip), all four recording decoders, seeking, pause/resume, tab navigation and final chart values. Preparation was 13.50, 12.95 and 13.58 seconds with existing media/calibration. The latest comparison is `runs/comparison/20260917T171824_811397Z`; `runs/verification/interface-check.json` records checks and zero callback errors. Screenshots `interface-overview.png`, `interface-watch.png` and `interface-live.png` capture only the test application's window and were visually inspected. The initial screenshot exposed clipped controls; the final screenshots show the corrected compact layout.

Final chart counts reproduced the previous results: CHAD 1 and 3 each have 1 occupied/2 vacant (33.3%); CHAD 2 and 4 each have 0 definite occupied/2 vacant/1 uncertain (0–33.3%). These are the last sampled frames of different recording periods, not current availability. Terminal compatibility also passed with `main.py --terminal --video chad-2 --fast --frames 1`, exit 0, output in `runs/comparison/20260917T171828_849038Z`.

The work does not establish independent detection accuracy, real synchronized-camera correspondence or an authorized external live parking source. The live tab provides viewing only; a new camera's occupancy still requires separate setup/calibration. The short usage guide explains exactly what the user can run immediately and what is required for optional live viewing.

Final verification: after tightening the live preview's aspect-preserving 960×540 limit, all **12 interface tests passed again in 2.36 seconds** (`runs/verification/tests-interface.xml`). Python syntax, launch JSON and updated local documentation links passed. `main.py --help` correctly describes the new interface. Rechecking the proposal's hash was unavailable because another process had the DOCX open; this task made no edits to it.

## 18 September 2026 — real camera views, nine CHAD bays and another parking site

### Request and source findings

The user noticed that the four CHAD videos showed the same angle, identified additional visible bays including two near the camera, and requested another car park plus availability by area. Continued implementation and documented the resulting behavior and limitations.

Verified the [CHAD publisher repository](https://github.com/TeCSAR-UNCC/CHAD): it does provide four actual camera views. The previous four selected files were all Camera 1 recordings at different times; their old CHAD 1–4 labels were ambiguous. Retrieved and visually inspected `2_036_0.mp4`, `3_073_0.mp4` and `4_075_0.mp4`, about 67.65 MB total, via the existing bounded ZIP-range downloader. Size/CRC/SHA checks passed. The full approximately 87.97 GB archive was not downloaded. These particular clips have not been synchronized or mapped to common bay IDs and remain view only.

Added `carPark.mp4` from [Harsh Bafna's repository](https://github.com/harshbafnaa/car-parking-detection), pinned to commit `a35ce5055beb2d50eac971254720892944e0f7fb`. It shows a different car park from overhead: 1100×720, 679 frames, 24 fps, 28.29 seconds, 10,607,736 bytes. The direct URL, size and SHA-256 are embedded in `areas.py`; the file is cached locally. Added bounded streaming download, deadline, byte cap, hash check and atomic replacement. Only media was used; no external detection code, models or pickled annotations were loaded. Source attribution and the unverified original-video license are recorded in `third_party/OVERHEAD-SOURCE.md`.

Also researched the Computer Vision Engineer tutorial's Drive folder and the DLP dataset. The former did not yield a verified accessible video in this attempt; its archive attempt timed out. DLP full raw footage needs an access request, and its sample link could not be retrieved here. Neither was integrated; no messages or access requests were sent. Research images/metadata are under `data/source-research-20260918/`. No API credential was needed for the selected recordings.

### Implemented changes

- Added `src/parking_probe/areas.py`: separate site/camera/recording metadata, pinned media, stable physical bay inventory and per-area reports. Site capacity is never inferred by adding overlapping camera views or different periods.
- Expanded CHAD Camera 1's interface inventory to **nine identifiable visible bays**: seven far-row and two near-row. Existing P001–P003 retain their calibration/meaning; P004–P009 have polygons but stay unknown pending references/examples. Near bays are partially clipped; unidentified edge slivers are excluded. The full car park's capacity is not claimed.
- Added `presets/overhead-demo.json` version 2: two calibrated bays, OVER-W01 and OVER-E01, and a third pending inventory bay OVER-W02. West/east area labels describe only this demonstration subset, not all visible spaces.
- Generalized `monitor.prepare_preset` for a supplied recipe/clip fetcher/cache/source ID, keeping its CHAD defaults. Generalized `comparison.run_comparison` to accept prepared inputs and a validated unique physical-bay map. Each site retains its own references, calibration and models.
- MOG2 calibration now routes invalid **unlabelled** chronological frames through the existing runtime validation guard without updating the model. Invalid **labelled** frames still abort calibration. Reference comparison, decision percentiles, MOG2 parameters and the 8-pixel alignment guard were not relaxed.
- Extended `interface_model.chart_data` to accept an explicit inventory and fill missing observations as unknown. Pending bays affect the denominator and unresolved range, never known-vacant counts.
- Replaced ambiguous recording buttons with **Site / View / Recording** selectors. Added the default **Areas & availability** tab with four rows: CHAD far/near and overhead west/east samples. Rows include recording/sample time; double-click opens the matching video. Separate periods are never presented as simultaneous live availability.
- Added actual playback for all eight recordings, resolution validation per source, nine-bay CHAD overlays, correctly sized overhead overlays, a scrolling bay table and explicit view-only displays with no borrowed counts. Fixed the video layout so its count strip stays visible on the 1280×720 screen.
- Preserved three-video-second estimates, chronological MOG2 preparation, seeking and ten-second windows. Method window tables cover the calibrated subset; the main chart/area inventory additionally includes pending bays as unknown. Terminal mode retains its original three-calibrated-bay CHAD comparison.
- Interface runs now save separate `chad/` and `overhead/` method outputs under `runs/areas/<UTC-time>/`, plus `bay-inventory.json`, `source-status.json` and the most recently displayed `area-summary.json` with `live_availability: false`. Preparation failures are isolated by source and do not erase another usable source's results.

### Calibration trials and actual results

The first overhead attempt used a third bay and later empty frames; it failed alignment. Research trials with alternate setup instants were not adopted. The final recipe uses a valid 12-second empty reference for each of two bays and five distinct vacant/five occupied examples per bay near the original setup view. All 20 labels come from one short clip, so they are a demonstration, not independent accuracy evidence. W02 remains pending instead of relaxing the guard to accept its later examples.

The overhead view drifts. Runtime samples at 15, 18, 21, 24 and 27 seconds fail `camera_view_changed` and both methods report unknown. At 12 seconds, the interface shows 0 occupied, 2 vacant and 1 unknown, or 0–33.3%; that instant is also the empty reference and is not an accuracy test. At the final sample all displayed overhead bays are unknown and occupancy is unavailable.

CHAD's three calibrated final states remain unchanged. In the expanded nine-bay interface, recordings 1/3 show 1 occupied, 2 vacant, 6 unknown, range 11.1–77.8%; recordings 2/4 show 0 occupied, 2 vacant, 1 uncertain, 6 unknown, range 0–77.8%. These are different recording periods and cannot be summed into one live result.

### Verification and documentation

The full suite passed **125 tests in 56.17 seconds**, saved in `runs/verification/tests-areas-full.xml`. Added inventory/area arithmetic, site separation, view-only clearing and overhead pending-bay tests. After adding two explicit MOG2 calibration guard cases and correcting the video count-strip layout, **19 focused tests passed in 4.87 seconds** (`tests-areas-final.xml`). The guard cases verify that shifted unlabelled frames do not update the model and shifted labelled frames cannot produce a calibration report.

Actual integration checks decoded all eight recordings, prepared **49 sampled frames / 137 paired bay observations** (39 CHAD frames plus 10 overhead), and exercised seeking, playback, final counts, site/view selection and alignment-failure clearing. Preparation measured 17.66 s and then 15.16 s with cached media/calibration. The latest run is `runs/areas/20260918T135145_877105Z`; `runs/verification/interface-check.json` records zero source issues and zero Tk callback errors. Screenshots `interface-areas.png`, `interface-overview.png`, `interface-watch.png`, `interface-overhead.png`, `interface-chad-camera-2.png` through `-4.png` and `interface-live.png` capture only the check's own window. Inspected the area/chart views and real video views; corrected the previously clipped video count strip.

Created detailed [PARKING_AREAS.md](PARKING_AREAS.md), shortened/updated [QUICK_START.md](QUICK_START.md), and updated INTERFACE, README, VIDEO_SOURCES, FINAL_RESULTS, VALIDATION and TROUBLESHOOTING to distinguish the current inventory from historical three-bay results. No new dependency, Windows setting change, user camera configuration edit or proposal edit was needed. This folder is not a Git repository, so no commit was created.

Remaining requirements for full-area results: valid references/calibration for pending bays, stable footage of all intended areas, verified correspondence and timing for cross-camera fusion, and independent labelled evaluation periods. External live parking access and independent accuracy/error rates remain unverified. The supplied recorded demo is runnable without a manual download or URL entry.


## 19 September 2026 — complete camera mappings and approved OpenCV vehicle supplement

### Request, authorization and source review

Continued the unfinished request to produce occupancy results for Cameras 2–4 and assess Camera 1's additional/near bays. The user explicitly approved a pretrained vehicle detector through OpenCV, with no YOLO, when missing empty/occupied examples prevent classic calibration. This approval extends the original no-detector scope; Reference and MOG2 remain individually visible.

Rechecked the CHAD publisher's four-camera layout and selected recordings. Saved the official `top_view.png`, start/middle/end contact sheets, detector trials and polygon inspections under `data/view-mapping-20260919/`. Camera indices identify distinct views; per-camera clip indices do not establish synchronized times. Cross-view SIFT/homography trials had only 8/5/4 tentative inliers and incorrect matches; they were rejected, with no automatic correspondence adopted.

Verified the storefront SUV bay manually as CHAD-P009 across four views. Camera 1's adjacent P008 is separate from Camera 4's P010/P011; do not substitute one for the other. Camera 1 can assess its near row directly, so no other recording's historical state is borrowed. Camera 2/3 far-row physical correspondence remains unverified; explicit view-local C2-Fxx/C3-Fxx IDs avoid falsely merging spaces or counting them as additional site capacity.

### Model and evidence implementation

Downloaded the MobileNet-SSD Caffe model and prototxt at pinned revision `bb17b6c3eef36d80be441ae8e5339be66e8e3b7a`; verified exact sizes and SHA-256 values. Added repository attribution and unchanged MIT license under `third_party/`. OpenCV `cv2.dnn` performs CPU inference; no external Python detector code, pickle data, YOLO package or new pip dependency was installed. Model/source metadata is cached under `data/models/mobilenet-ssd/`.

Added `vehicle.py`: bounded model retrieval, integrity checks, full-frame plus four-crop inference, car/bus/motorbike filtering, duplicate suppression, unique polygon association, weak-overlap handling and guarded empty-image matching. Absence of detection alone never marks a bay vacant. Opposing definite methods remain uncertain. Missing model/frame/reference provenance disables affected evidence. Additional checks prevent stale or unavailable frames with missing error text from producing estimates. Vehicle processing timestamps describe that branch; combined row/UI completion times use the final branch completion.

Added `view_presets.py` and four reviewed recipes. Camera 1 expanded recipe v4 covers nine bays; Camera 2 v1 covers five; Camera 3 v2 covers four; Camera 4 v1 covers three. Corrected Camera 3's first trial against painted boundaries and removed a clipped fourth far-row region. Camera 2 excludes the shrub from the last bay. All final polygons are convex and valid. Hatched access space and unidentified clipped regions are excluded.

Generalized preset preparation to allow genuinely missing references and extract manually selected supplemental empty-bank images. Camera 1 B04–B08 use reviewed empty images from all four periods and five distinct vacant examples per period. This is a capped vacant-only tolerance, not fabricated two-state calibration. B09 has no empty reference. Additional-bank images must pass setup alignment and pixel-hash checks. There is no automatic reference replacement and no relaxation of resolution/alignment guards. Camera 1 recording 4 is used in this expanded demonstration and is not held out for the new branch; the original three-bay terminal recipe is unchanged.

### Pipeline, interface and outputs

Extended `run_comparison` with an optional supplemental branch, leaving its legacy defaults intact. CHAD interface runs emit Reference/MOG2/Vehicle/Final per-sample results, annotated images, JSON/CSV histories, final summaries and ten-second per-bay occupied-time windows. Original capture times stay unknown; EOF results remain historical. The Final duration is the sum of branch processing times, excluding decoding/writing/UI overhead.

Enabled actual analysis for Cameras 2–4 in the interface worker, with each camera's own configuration/calibration and isolated failures. The approved shared detector supplies only within-frame object evidence; no asynchronous camera fusion occurs. Added Vehicle/Final columns, selectable evidence explanations, four-method scrolling window reports, mapped-inventory scope and explicit view-local identity notes. Chart, video overlays and area counts use the same Final state. Areas follow the selected view/recording; overlapping view capacities are not summed. Overhead and optional live viewer behavior remain separate.

### Verification and measured findings

The complete automated suite passed **142 tests in 108.31s** (`tests-mapped-full.xml`). After tightening stale/unavailable metadata guards, **25 focused tests passed in 29.51s** (`tests-mapped-final.xml`). New tests cover box deduplication, unique association, weak/ambiguous evidence, no-detection safeguards, provenance, method conflicts/fallback, four-branch serialization/windows and per-view inventory/results.

The real interface integration check passed with zero source issues and zero callback errors. It decoded all eight videos and analyzed 60 frames: 50 CHAD samples/398 bay observations, plus ten overhead frames/two analyzed bays and a third unknown inventory bay. Preparation took **119.45s** including cached setup checks and report generation. CHAD summed processing latency measured median **237.73ms**, p95 **313.44ms**, excluding decoder, writes and UI. Decision coverage was **92.71%**, not independently measured accuracy.

Final historical counts: Camera 1 recordings 1/2/4 each 2 occupied and 7 vacant; recording 3 has 2 occupied, 2 vacant and 5 uncertain. Its P004–P008 empty-bank differences exceed conservative tolerances; P008's final score is about 0.01447 versus limit 0.01409. They were not forced vacant. Camera 2 has 2 occupied/3 vacant, Camera 3 2/2, Camera 4 1/2. P009 is occupied in every sampled view. Overhead still fails alignment after 12s; no thresholds were relaxed.

Verified visual layout via own-window screenshots, inspecting the near-row table/reason, circle chart, Camera 2 video/count strip, scrolling summaries and corrected Camera 3 annotation. Actual UI checks also covered seeking, summaries resetting after backward seek, playback pause/resume, source switching, and live-tab pause. Final run: `runs/areas/20260918T185845_684414Z`; reports: `runs/verification/interface-mapped-check.json` and `mapped-measurements.json`. Earlier mapping trials remain historical artifacts, not the delivered measurement set.

Created [CAMERA_MAPPING.md](CAMERA_MAPPING.md), added model license/provenance documentation, and updated QUICK_START, README, INTERFACE, PARKING_AREAS, VIDEO_SOURCES, MULTICAMERA, MOG2, TROUBLESHOOTING, FINAL_RESULTS and VALIDATION. Historical work/results are retained under dated headings. No proposal file, Windows protection setting, user endpoint or credentials were changed. No Git commit was made because the workspace is not a Git repository.

Remaining limits: unknown synchronization; Camera 2/3 far-row correspondence pending; incomplete two-state examples; per-frame detector errors and ambiguous views; no independent accuracy/error-rate evaluation; no authorized external live occupancy test. Recorded source estimates should not be described as current free spaces.

Final checks after timestamp corrections: **42 focused tests passed in 34.32s** (`runs/verification/tests-mapped-timestamps.xml`). Python source syntax, preset JSON/convex polygons and all local Markdown links passed. Also visually inspected the Camera 4 video/count strip and area table. No further code changes followed these checks.

## 19–20 September 2026 — all 69 overhead bays and selective YOLOv8s

### Request and proposal interpretation

The user asked to include every overhead parking bay, including bays that never change, and to use YOLOv8 whenever either Reference/MOG2 branch is unresolved or they disagree. A repeated continuation request on 20 September asked to finish and retain detailed Markdown documentation. The proposal DOCX was read as project evidence, not as separate instructions. Its relevant phase-three design specifies YOLOv8s, full-frame 640 input/batch one, bounded worker, source/frame/slot provenance, score at least 0.80, unique polygon association and no false vacancy from a missed detection. The user's direct matching-definite rule determines the trigger. Later learned probability fusion, three-snapshot confirmation, persistence/database, Flutter and deployment were not added.

### Mapping, references and drift

- Inspected the existing `carPark.mp4` overhead view and the publisher's 69-coordinate `CarParkPos` inventory at commit `a35ce5055beb2d50eac971254720892944e0f7fb`. Parsed only data structure/integer pickle opcodes using `pickletools.genops`; no unpickling, serialized code or repository Python was executed. Saved the inspection/source-digest record in `data/yolo-overhead-review/publisher-coordinates-inspected.json`.
- Added `presets/overhead-all-bays.json` (final recipe version 3), all 69 explicit convex bay polygons and physical IDs. Areas are west 24, middle 22, east 23. Preserve W01, W02 and E01 as aliases for their existing physical bays; no duplicate capacity. Hatched loading/access and roadway are excluded. Stationary occupied/empty bays are included. Created and visually inspected `assets/previews/overhead-69-bays.jpg`.
- W01/E01 retain separately reviewed reference and five-per-state examples. W02 gains a late empty reference at 27 seconds and five empty examples after its pickup leaves, separate from occupied examples. The remaining 66 bays receive no invented empty reference or label. They remain uncalibrated in classic columns and receive YOLO verification. Full times and all identifiers are listed in OVERHEAD_MAPPING.md.
- Diagnosed the earlier post-12-second failure as small view drift. Added guarded ORB/RANSAC partial-affine registration in `registration.py`, explicitly enabled only by the overhead recipe. Setup/reference/calibration extraction, runtime comparison, MOG2 calibration and preview use the same coordinate system. Both geometric limits and the original post-registration alignment checks remain active; warped borders cannot overlap monitored polygons.
- The first 2-pixel RANSAC trial rejected a valid 25-second frame at approximately 59.1% consensus. The final 3-pixel reprojection setting passed it with approximately 82.2% consensus and 0.936-pixel median error, while retaining 60% consensus, 80 inliers, distributed matches, maximum 1.5-pixel median error, 35-pixel displacement, 3% scale and 2-degree rotation limits. Recipe versioning invalidates earlier calibration caches. The W02 empty calibration selections remain 24, 24.5, 25.5, 26, 26.5 seconds.
- Actual final registration check: 227 stride-three frames, zero failures, maximum median reprojection error 1.086 pixels. This correction is specific to the reviewed clip; it is not automatic recovery from arbitrary camera relocation.

### Model investigation and reproducible runtime

- Checked primary Ultralytics YOLOv8/export documentation and OpenCV DNN documentation. Exported official YOLOv8s COCO weights. Initial overhead tests produced no vehicle detection above 0.25, including additional rotation/size/crop development checks. A known bus control image yielded a strong bus result, separating view-domain failure from an OpenCV/Windows loading problem.
- Located the aerial-trained `dronefreak/visdrone-yolov8s` checkpoint, pinned Hugging Face revision `4475b4d86d5f4b120806d1b953be15cedaac9285`. It detects overhead vehicles without training on this clip or lowering the proposal's 0.80 criterion. The alternative ENOT model source was researched but not used. Publisher benchmark metrics were not copied as project accuracy.
- Added two fixed YOLOv8s profiles: official COCO for CHAD, VisDrone aerial for overhead. Each requested source frame uses one selected profile and one full-frame inference for all affected bays. Both models execute locally through OpenCV DNN CPU; there is no external inference API or GPU requirement.
- Installed CPU torch 2.7.1+cpu / torchvision 0.22.1+cpu, ultralytics 8.3.203, onnx 1.19.0 and conversion dependencies inside the existing project venv. Runtime still needs only the project's OpenCV/NumPy/requests dependencies. Added the optional `yolo-export` dependency group and `requirements-yolo-export-tested.txt` as the installed conversion-environment snapshot.
- Read checkpoints with PyTorch `weights_only=True` and an explicit allowlist of installed known neural-layer classes. Pinned input sizes/digests and complete source URLs are recorded in `assets/models/yolov8s-manifest.json`. Bundled `yolov8s-coco.onnx` and `yolov8s-aerial.onnx`, static FP32 640/batch one/opset 12, no simplification or embedded NMS; runtime verifies size/SHA-256.
- Added and successfully executed `scripts/export_yolov8_models.py` for both profiles. Bounded downloads verify input hashes; output hashes update after export because metadata may change. The final full interface run used these rebuilt assets. Copied the upstream v8.3.203 AGPL-3.0 license and documented both sources in `third_party/YOLOV8-SOURCES.md`. Default Ultralytics settings created by initial conversion experiments were left in place; subsequent settings use `data/models/yolo-settings/`. No personal settings were removed.

### Pipeline, UI and saved output

- Added `yolo.py`: preprocessing/output parsing, vehicle classes and NMS, unique polygon association, inclusive 0.80 threshold, selective trigger/final rule, full-frame inference and bounded verification service. One executing plus one queued frame maximum; five-second request wait timeout, camera/frame/slot identity checks, sanitized failures and superseded-response rejection. Runtime retains object confidence as a detector score, never an occupancy probability.
- Both classic branches agreeing on occupied/vacant bypass YOLO for that bay. Unknown, uncertain or conflicting branches request verification. Strong uniquely associated vehicle detection gives occupied; no/weak/ambiguous hit remains uncertain. Unavailable evidence stays unknown. Results from settled neighbouring bays cannot override their classic agreement or be assigned ambiguously. No detection is interpreted as proof of vacancy.
- Updated `comparison.py` to preserve Reference/MOG2 and add YOLO/Final results, timings, completion timestamps, profiles and per-slot reasons. Each method has JSON/CSV history, annotated images and window summaries. Source decode/capture status and frame identities remain explicit. Registration failures cannot train MOG2 or become fresh detector input.
- Updated `monitor.py` and `mog2_calibration.py` to use the recipe-specific recording factory; updated `view_presets.py` so the current interface skips building the unused former empty-evidence bank. `areas.py` now derives overhead inventory from the complete 69-bay recipe. Updated `interface_model.py`, `output.py` and `interface.py` for four-method data, all-bay counts, compact polygon labels and selective-YOLO reasons. Legacy SSD and the original three-bay terminal workflow remain available but are not normal Run's policy.
- Interface now shows Reference / MOG2 / YOLOv8 / Final estimate, SKIPPED for matching classic evidence, 69 overhead entries, circle chart, 24/22/23 area totals, video overlays and all-bay ten-second summaries. One clipped three-line area footer was reduced to one clear line and visually rechecked. Close/stop shuts down the verification service. Existing recorded precomputation/three-video-second review timing and independent source-period handling remain explicit.
- Added `checks/measure_yolo_run.py` to derive coverage/timing from saved observations without treating predictions as labels. Updated `checks/check_interface.py` to verify all eight sources, exact per-row routing, final counts, all overhead polygons, seek/window/pause behavior and own-window screenshots. It closes its own window after verification.

### Verification and measured results

- Initial focused suite: 56 passed in 29.71 seconds. A pytest parameter called `request` was renamed because pytest reserves that name.
- First full run: 159 passed, two fixture failures. The production factory refactor meant the old monkeypatch no longer intercepted recording creation. Fixed the test to patch `recording_for_recipe`, retaining its invalid-frame rejection/model-update assertions; removed the unused constructor import.
- Final full run: **161 passed in 102.61 seconds**, `runs/verification/tests-yolo-full.xml`. Covers new routing/threshold/association, stale identities, bounded queues, cancellation/timeout/worker errors, registration limits and prior source/calibration/MOG2/summary arithmetic regressions.
- First successful full UI run: `runs/areas/20260919T085143_971731Z`, 68.28 seconds cached preparation. Final UI recheck after export rebuild and footer correction: **`runs/areas/20260919T085852_114918Z`**, **73.19 seconds**. Zero source issues and Tk callback errors. The final run overlapped CPU tests; timings are observations rather than a controlled benchmark.
- All eight recordings yielded **60 frames / 1,088 bay observations**: CHAD 50 frames/398 observations and overhead 10/690. **60 full-frame YOLO inferences** served **987 requested bay observations**; **101 bay observations** bypassed YOLO because classic branches agreed. All requested inferences completed.
- Final overhead sample (27 seconds): **48 occupied, 2 vacant, 19 uncertain / 69**; occupancy range 69.6–97.1%. Area totals: west 17/1/6 of 24, middle 17/0/5 of 22, east 14/1/8 of 23 (occupied/vacant/uncertain). All ten samples remain usable, unlike the former drift-limited demo.
- Final CHAD Camera 1 periods each have 2 occupied/2 vacant/5 uncertain of 9. Camera 2: 2/0/3 of 5; Camera 3: 2/0/2 of 4; Camera 4: 1/0/2 of 3. P009 is occupied in each sampled view. P008 remains uncertain; the prior one-sided empty-bank vacancies no longer apply. Separate capture periods were not borrowed to fill gaps.
- Across all samples, decision coverage is **40.70% CHAD** and **71.01% overhead**. Branch-sum median/p95: CHAD **424.50/492.16 ms**, overhead **447.72/503.72 ms**. YOLO inference median/p95: CHAD **342.02/391.68 ms**, overhead **339.79/402.33 ms**. Decode/registration, writes and UI rendering are outside branch-sum timings. These figures are not a live throughput guarantee or accuracy.
- Evidence: `runs/verification/interface-yolo-check.json`, `yolo-measurements.json`, `registration-overhead-check.json`, `tests-yolo-full.xml`, and `yolo-*.png` own-window captures. Inspected the 69-bay map, overhead chart/table and corrected area footer.

### Documentation and remaining limits

Created **YOLOV8.md**, **OVERHEAD_MAPPING.md**, **third_party/YOLOV8-SOURCES.md** and the source license copy. Rewrote the short QUICK_START and current README/INTERFACE/TROUBLESHOOTING descriptions. Updated FINAL_RESULTS and VALIDATION from saved measurements. Added explicit current-version notices to CAMERA_MAPPING, PARKING_AREAS, VIDEO_SOURCES and MOG2 while preserving older measurements as history; updated MULTICAMERA and overhead annotation provenance. This detailed work record covers both implementation and the continuation/documentation work.

All 69 visible bays are included, but 19 final overhead states remain uncertain. No qualifying detector box is insufficient to call a bay vacant. Additional verified references plus separate examples of both states can improve classic coverage. Independent accuracy, false-vacant/false-occupied rates and the planned at-least-30-frame evaluation remain unmeasured because a separate labelled capture-period set is not supplied. No authorized live parking endpoint is configured. Automatic cross-camera identity and Camera 2/3 far-row correspondence remain unvalidated. No Windows security setting, credentials, proposal text, external account or deployment was changed. The workspace has no Git repository, so no commit was made.

Final delivery check on 20 September: parsed 50 Python files successfully, verified 69 unique physical/local bay IDs and convex positive-area polygons, checked both bundled model sizes/SHA-256, and checked all root/third-party Markdown local links. No errors. Report: [yolo-delivery-check.json](runs/verification/yolo-delivery-check.json). No implementation changes followed the passing full tests and final UI run; subsequent edits completed documentation and added the measurement summarizer.

## 20 September 2026 — quick diagnosis of unresolved vacancies/vehicles

The user reported long-stationary empty/occupied bays remaining unresolved and asked for a quick check. Read current selective YOLO, previous SSD/empty-bank evidence, classic branches and integration; inspected the user's newer completed run `20260919T161628_245646Z`. All 60 inference jobs completed with no inference/source errors. Compared 398 same-recording/frame/bay CHAD observations against previous SSD run `20260918T185845_684414Z`: classic Reference/MOG2 states changed zero times, but 207 formerly vacant final observations became uncertain; 100 occupied and 62 vacant remained definite, 29 remained uncertain. No matching definite classic agreement was overridden.

Added `checks/diagnose_unresolved.py` to reproduce this audit and save diagnostic JSON/images. Loaded both actual ONNX models with integrity checks and re-ran last CHAD-1/overhead frames at 27 seconds; saved per-bay verification states reproduced. Inspected all 19 highlighted overhead unresolved bays: six visibly occupied bays have uniquely assigned detections with scores 0.588–0.788 below the 0.80 cutoff; 13 appear empty but have no accepted vacancy decision. Twelve of those empty bays lack classic evidence; calibrated W01 falls between both classic thresholds (Reference 0.017694 versus vacant maximum 0.009008; MOG2 0.037587 versus vacant maximum 0.017920). Did not assume a specific physical cause for its appearance change.

Diagnosis: my YOLO integration disabled the former reviewed-empty-image fallback, so it lost a positive vacancy-evidence path; this is a policy regression, not a Windows/OpenCV loading fault. The detector operates, but weak detections plus the strict acceptance cutoff account for the occupied-looking unresolved subset. Repeated three-second samples and ten-second reports do not implement temporal confirmation, so duration does not resolve uncertainty. Recommended preserving selective routing while restoring verified empty-reference checking after YOLO; view-specific threshold evaluation requires labels. No production model, threshold, reference, calibration or classification rule changed in this diagnostic task.

Focused verification: 18 YOLO tests passed in 1.30 seconds (`runs/verification/tests-yolo-quick-check.xml`). Added detailed `UNRESOLVED_CHECK.md` with exact transitions, six scores, W01 boundaries, visual diagnostic, reproduction command and recommended correction. Raw evidence: `runs/verification/unresolved-audit/report.json` and per-source highlighted images. This is a small diagnostic review, not independent accuracy evaluation or a claim that the limitation has already been repaired.


## 21 September 2026 - reviewed empty examples (completed record; policy later retired)

The user asked for empty examples and assistance restoring vacancy recognition. Searched and visually inspected the existing same-camera recordings; no unrelated photograph or generated background was used. This entry completes the documentation of that preceding work before recording the user's 22 September correction below.

- Saved masked crop galleries/contact sheets and `assets/empty-review/manifest.json` with full-frame paths, hashes, bay polygons and source times. Empty evidence covers 30 bay/view entries: overhead 15; CHAD Camera 1 eight; Camera 2 three; Camera 3 two; Camera 4 two. These are not 30 distinct physical spaces across synchronized cameras.
- Overhead recipe version 4 added vacant-only references for WL07, ML03, ML11, MR05, MR08, MR10, EL07, EL09, EL11, ER02, ER09 and ER10. Eleven use time 0 references and separate 5/10/15/20/26-second examples; EL09 uses a 27-second reference and 24/24.5/25.5/26/26.5-second clear samples. W01 adds a reviewed 27-second bank image. Original W01/W02/E01 two-state calibration remains; the other 66 bays were not falsely marked fully calibrated.
- CHAD Camera 1 recipe versions 5-6 added recording 3 at 18 seconds for B05-B08 and 15 seconds for B05-B07 to cover visually reviewed lighting changes. Rejected B04 at 15/18 seconds and B08 recording 4 at 27 seconds because people obstruct the bay. Existing Camera 2-4 references were retained. No automatic predicted-empty labels were introduced.
- Factored `prepare_empty_evidence` in `view_presets.py`: cache aligned/preprocessed frame reads, exclude reference reuse and duplicate content, require at least five distinct aligned vacant examples, record reference/setup/polygon/additional-bank hashes, and reject an empty tolerance contradicted by supplied occupied examples. Tolerance was capped at 0.04 with a minimum 0.012, using `p95(empty_scores)*1.5+0.005` inside those limits. This is an empty-only heuristic, not probability or validated two-state classification.
- Added `empty_evidence.py` for integrity-checked appearance matching and per-recording three-sample streaks. Its candidate needed valid input, a successful no-hit YOLO result, no weak/ambiguous overlap and no opposing classic occupied result. Failed matches/evidence, large time gaps, backward time and duplicate frames revoked the streak. At 0/3/6 seconds three checks can complete at 6 seconds. No state was carried through bad evidence.
- Integrated that extra evidence after YOLO and exposed its score/limit/streak in row details and saved output, but left the three branch columns unchanged. This caused the user-visible mismatch addressed below. It was a fourth heuristic decision path, not a YOLO vacancy prediction.
- Added 18 tests and `checks/check_empty_replay.py`; 47 focused tests passed in 41.72 seconds and 179 full tests passed in 105.75 seconds (`tests-empty-first.xml`, `tests-empty-full.xml`). Added `checks/export_empty_examples.py` and exported actual reference crops and provenance.
- Earlier headless trials `20260920T170648_924359Z` and `20260920T171150_307823Z` took 132.83 and 172.32 seconds; adding the reviewed 15/18-second CHAD appearances resolved some later mismatches. Final actual UI replay `20260920T171708_941751Z` processed 60 frames/1,088 observations and 245 three-check fallback vacancies, with no source issues. Its overhead final was 48 occupied/14 vacant/7 uncertain; final CHAD1 periods were 2/7/0, 2/7/0, 2/6/1, 2/6/1; Cameras 2/3/4 were 2/2/1, 2/2/0, 1/0/2. Numbers are occupied/vacant/uncertain.
- That run's full-sequence coverage was 77.89% CHAD and 85.07% overhead; branch-sum median/p95 was 295.29/328.31 ms CHAD and 321.41/381.41 ms overhead. No independent accuracy or error-rate claim was made. Camera 4 had only two samples; EL09 was interrupted by early objects and cleared late; six overhead vehicles stayed below the 0.80 detector cutoff.
- Wrote `EMPTY_REFERENCES.md`; updated README, QUICK_START, INTERFACE, troubleshooting, mapping/source/model notices. Historical measurements remain in `empty-replay-check.json` and `empty-measurements.json`. Reviewed images remain useful calibration material after retirement of their final-state override.

## 22 September 2026 - fix final results unsupported by displayed methods

### User request and diagnosis

The user observed Reference/MOG2/YOLO unknown or uncertain while Final was vacant, and requested a model-confirmed answer across every camera view. Inspected the actual production pipeline, branch decision function, empty matcher, calibration/preparation, UI, outputs and tests. Found the explicit `empty_confirmed` branch in `yolo.final_decision` and the hidden fourth-stage call in `comparison.py`. This was my previous design choice, not a Windows problem or a YOLO inference failure. Repeated empty-image appearance matches do not change a vehicle detector into a vacant-bay classifier.

Audited 1,088 prior observations from `runs/areas/20260920T171708_941751Z`: 245 final vacancies lacked matching definite Reference/MOG2 evidence; 237 of these had all three displayed methods unresolved. Exact all-three-unresolved counts: CHAD1 periods 27/44/19/43; Camera 2 six; Camera 3 four; Camera 4 zero; overhead 94. Camera 4 shared the code path but its clip was too short to complete the old streak. These are observation counts, not unique bays or independently labelled classification errors.

### Implementation

- Removed `empty_confirmed` from the final-decision API and removed the empty score/streak override from normal Run entirely. Definite Reference/MOG2 agreement is retained; otherwise a qualifying YOLO vehicle confirms occupied; other usable unresolved evidence stays uncertain and wholly unavailable evidence stays unknown. Neither no detection nor a fabricated YOLO vacant state can establish vacancy.
- Every final vacancy now requires both displayed classic branches to say vacant. The original requested YOLO routing remains: any uncertain/unknown or disagreement requests verification; matching definite classic states bypass it. YOLO threshold 0.80, box association, models and failure safeguards are unchanged.
- Normal interface preparation skips fitting the unused heuristic bank. Preset versions, reference images, reviewed labels and polygons remain intact. `empty_evidence.py` and its tests remain a historical diagnostic utility; the legacy SSD path is not the normal interface policy.
- Added policy ID `definite_opencv_agreement_else_yolov8_vehicle_else_unresolved_v2` to current results and final summaries. JSON/CSV rows have `final_confirmed_by`, and final per-bay JSON has `confirmed_by`, with Reference+MOG2 / YOLOv8 / null provenance.
- Updated row details to say which displayed methods confirm the result or "No method confirmation". Updated ready/help text and annotated output caption. Chart, area counts, video and ten-second summaries all consume the same corrected final states. No second rendering-only state substitution was added.
- Added `checks/check_decisions.py`: all eight recordings, 60 frames and 1,088 observations; validates request routing, every definite result's branch support, final JSON/chart consistency, final-window vacancies and policy metadata. Supports `--existing-run` and a prior-run audit. `check_empty_replay.py` now delegates to this current checker; the old empty review report remains on disk for crop export provenance.
- Added 64 branch-state combinations and a real three-sample comparison regression with a valid empty bank and a no-detection verifier. It checks saved final summaries and windows cannot gain a hidden vacant result. Updated the previous matcher test to require unresolved Final despite a completed diagnostic streak.

### Validation and UI inspection

Full suite: **244 passed in 97.35 seconds**, `runs/verification/tests-decision-full.xml`. All prior calibration/source/threshold/association/MOG2/summary regressions pass.

Headless all-view replay: `runs/areas/20260921T161321_173938Z`, 112.23 seconds preparation/analysis/reporting, 60 frames/1,088 observations, no errors. Actual normal-interface replay: **`runs/areas/20260921T161408_115721Z`**, all eight recordings complete and source-status issues empty. Validated its actual saved results with `checks/check_decisions.py --existing-run ... --baseline ...`; 652 definite observations all supported by the displayed methods, zero unsupported decisions. Actual UI preparation time was not separately instrumented. Runs overlapped tests/each other, so timing is not a controlled benchmark.

Used the Computer Use skill and native `sky` APIs to inspect only the task's test window. Verified the all-area counts, overhead 48/69 chart with 2 vacant/19 uncertain, WL03 weak-detection uncertainty, formerly overridden WL07 unknown/uncertain/uncertain now final uncertain with "No method confirmation", final partial-window counts and video count strip. Closed the owned verification window; its process exited successfully. No screenshot payloads were saved. UI inspection metadata: `runs/verification/interface-decision-check.json`.

Final counts (occupied/vacant/uncertain): each Camera 1 period **2/2/5 of 9**; Camera 2 **2/0/3 of 5**; Camera 3 **2/0/2 of 4**; Camera 4 **1/0/2 of 3**; overhead **48/2/19 of 69**, range 69.6-97.1%. Overhead west/middle/east are 17/1/6, 17/0/5, 14/1/8. All final unknown counts are zero in these valid recorded frames.

Actual UI run full-sequence coverage: CHAD 40.70%, overhead 71.01%. Branch-sum median/p95: CHAD 432.80/533.98 ms, overhead 514.78/577.85 ms. These exclude decoding/registration, reports and rendering. No independent labelled accuracy/error rates or new live-camera availability claim.

Matched the prior and corrected runs by recording/frame/bay: **zero changes to any Reference, MOG2 or YOLO state**. Final transitions: 582 occupied retained, 70 vacant retained, 191 uncertain retained, 245 heuristic vacancies changed to uncertain. Saved `runs/verification/decision-before-after.json`. This proves the correction removes unsupported final decisions; it does not pretend to improve the models' vacant recognition.

### Documentation and remaining work

Created `DECISION_FIX.md` with the cause, exact current rule, all-camera prior audit, reproducible commands and data needed to improve recognition. Updated README, QUICK_START, INTERFACE, TROUBLESHOOTING, FINAL_RESULTS and VALIDATION. Replaced obsolete current-policy notices in YOLOV8, OVERHEAD_MAPPING, CAMERA_MAPPING, PARKING_AREAS, MOG2 and UNRESOLVED_CHECK. Marked the empty-fallback description in EMPTY_REFERENCES as retired while preserving the actual crops and historical evidence.

The user only needs to close the previous window and run `main.py` again. No new download/install is necessary. Recognition coverage remains limited: some bays lack occupied examples for two-state calibration; the current YOLO models recognize vehicles, not a positive vacant-bay class. A parking-specific classifier or representative per-bay vacant/occupied calibration plus independent evaluation is needed to confirm more bays. We do not force a definite answer when the implemented methods cannot support it. No reference/polygon/model threshold, proposal text, Windows setting, external account, credentials or deployment was changed in this correction.

Final delivery check: 57 Python files parsed, both ONNX sizes/SHA-256 verified, and 178 root/third-party Markdown local links resolved. No errors. Evidence: `runs/verification/decision-delivery-check.json`. No production logic changes followed the successful full suite and real UI run; remaining edits finalized documentation and labelled the historical empty matcher.


## 22 September 2026 - root-cause audit from original Reference/MOG2 through YOLO

Related consultation: [Q1 and Q5, with verification notes](AI_CONSULTATION_LOG.md).

The user asked whether omitted mappings/references explain uncertainty, which YOLOv8 variant runs and why it varies. Performed a diagnostic audit without modifying production polygons, reference images/labels, calibration, model assets, thresholds, decision rules or UI behavior.

Compared original run `runs/comparison/20260917T161258_089149Z` to current `runs/areas/20260921T161408_115721Z`: **117 matching B01/B02/B03 observations, zero Reference/MOG2 state changes**. Every original recipe field for these bays is unchanged. All 62 original vacant and 27 original occupied consensus states persist; 14 formerly uncertain observations become YOLO-supported occupied, and 14 remain uncertain. The initial working subset did not regress; the display was expanded to incompletely calibrated bays.

Audited all 90 bay/view entries (not distinct physical site capacity). Mapped / usable empty reference / both methods calibrated: Camera 1 **9/8/3**, Camera 2 **5/3/0**, Camera 3 **4/2/0**, Camera 4 **3/2/0**, overhead **69/15/3**. Total coverage is six calibrated, 24 empty-only and 60 without references. All configured reference files load at the proper resolution. Missing references are absent configuration fields, not broken paths. Camera 1 B04-B08 have 20 vacant and zero occupied examples each; Camera 2 F02-F04, Camera 3 F02-F03 and Camera 4 N10-N11 each have five vacant and zero occupied examples. These fail the planned five-per-state calibration. The enlarged mapped inventory was not fully calibrated before inclusion, a setup-completeness gap that needed clearer explanation.

Matched 398 CHAD observations from the SSD supplement run `runs/areas/20260918T185845_684414Z`: zero classic changes; 100 occupied retained, 62 vacant retained, 29 uncertain retained, **207 former heuristic vacancies now uncertain**. This distinguishes a final-policy change from corruption of Reference/MOG2. The earlier empty-match supplement supplied those vacancies; later removal/restoration/retirement changed apparent completeness without completing calibration.

Added `checks/audit_mapping_calibration.py`, writing only to `runs/verification/mapping-calibration-audit/`. It verifies unique IDs, valid polygons, exact runtime/recipe geometry and dimensions, reference availability/calibration validity, label counts, historical states, model hashes/class metadata, repeated inference and saved-state reproduction. Its initial run encountered KeyError because generated configs omit bay_id; corrected it to read the verified joined row's physical ID. The final utility and a repeat run after adding historical transitions/score timelines completed successfully. Saved report.json, per-bay.csv, five setup overlays and five last-frame overlays. Visually inspected every last-frame overlay and all five empty-reference crop galleries.

No widespread scale/shift error was found. CHAD analysis and overlays share 1280x720; overhead uses registered 1100x720. All 60 current frames have zero alignment failures and inference errors. One WR07/W02 overlap is a one-pixel-high strip, 2.28% of the smaller continuous polygon area. A diagnostic-only in-memory WR07 trim to bottom y=428 changes zero associated YOLO states across all ten overhead samples. Actual preset unchanged; this is not the source of widespread uncertainty. Camera 2 F02 has another limitation: its empty bay is touched by the axis-aligned box of the neighbouring F01 car, leading to conservative weak/ambiguous association. This is separate from missing calibration.

Verified **YOLOv8s (small)** for both profiles: official COCO weights for CHAD (80 classes), pinned dronefreak/visdrone-yolov8s for overhead (11 classes). ONNX SHA-256 and names metadata match the manifest and all vehicle class IDs. Runtime is OpenCV DNN CPU, static 640x640/batch one/FP32/opset12. The prior MobileNet-SSD is a legacy alternative, not stacked before current YOLO. Neither active detector has a vacant-bay class. Consulted primary Ultralytics model/prediction docs and the aerial model card; publisher benchmark metrics were not used as project accuracy.

Repeated the same final image three times for each of five views: detections exactly identical and every freshly derived YOLO state matches saved state. This proves repeatability on those inputs, not detection accuracy. Last overhead unresolved vehicle scores: WL03 0.6981, WL09 0.5883, WL11 0.6590, WR02 0.6652, ER05 0.7883, ER08 0.6456. They are detected but rejected by the application's 0.80 cutoff. The other 13 unresolved overhead bays have no qualifying vehicle and no accepted classic vacancy.

Saved nine overhead score timelines. ML05 at 0/3/6 seconds is 0.814/0.794/0.811, producing occupied/uncertain/occupied. EL05 is 0.828/0.798/0.820. This demonstrates inter-frame scores crossing the cutoff. Typical overhead polygons are about 60x25 pixels at model scale, so detail loss and viewpoint/training differences are plausible contributors; no controlled higher-resolution/larger-model comparison was performed. Ultralytics' confidence parameter is configurable (documented default 0.25), but neither that default nor a blind cutoff reduction is validated for this scene. Production remains at 0.80.

Created **MAPPING_CALIBRATION_AUDIT.md** with the full findings, model identities, annotated views, all-camera coverage, exact threshold examples, historical comparison and next steps. Added pointers in README, CAMERA_MAPPING and YOLOV8 and an audit entry in VALIDATION. The substantive next work is representative vacant/occupied calibration or an evaluated bay classifier, plus labelled detector/association evaluation. No new installation, download, credentials, Windows setting, proposal edit, model/polygon/threshold change, or live availability claim. No independent accuracy/error rates measured. Existing 244 production tests were not rerun because production behavior was unchanged.

Audit delivery checks passed: script syntax, updated Markdown local links, 117/398 paired-history assertions, all 90 bay/view entries and five-view detector repeatability assertions. Evidence: `runs/verification/mapping-calibration-audit/delivery-check.json`.


## 22 September 2026 - separate PKLot UFPR04 external validation

Related consultation: [Q2–Q5, preserved questions/reasoning and completed status](AI_CONSULTATION_LOG.md). The later post-hoc comparison is documented in [REFERENCE_PRIORITY.md](REFERENCE_PRIORITY.md).

### Request, source inspection and scope

Implemented the request in the pasted attachment, including the identical continuation attachment. Before editing, read the actual current `catalog.py`, `areas.py`, `view_presets.py`, `comparison.py`, `yolo.py`, `mog2.py`, `mog2_calibration.py`, `monitor.py`, `evaluation.py` and `output.py`; also checked config, vision, sources, registration and proposal sections 3.7–3.8. Reported that existing preparation/replay wrappers are MP4/frame-index based and the existing evaluator computes single-branch metrics inline. Added the closest compatible snapshot adapter and shared metric/calibration helpers rather than a parallel CV algorithm. Did not assume a large labelled dataset would prove accuracy.

This is a **checks-only external experiment**, using the existing Analyzer, MOG2Branch, YOLOBranch, needs_verification/final_decision and classic consensus. No PKLot area was added to the app. The earlier CHAD/overhead recipes, reference images, calibration files, thresholds, model assets, final-decision rule and `main.py` were preserved. Before edits, recorded hashes of 636 protected existing files; every hash still matches. Existing current-camera MOG2 calibration signatures also still match, recorded in `runs/verification/pklot-legacy-signatures.json`.

### Acquisition and conversion

Added `src/parking_probe/pklot.py`. The university domain failed DNS resolution locally. Located the original-archive mirror at Hugging Face `teenygrad/pklot`, pinned revision `9604b05ad6dfd5ab5817b5fa6600d375754562fb`. Downloaded **4,898,276,304 bytes**, verified against the mirror's published Git LFS SHA-256 **e89bbc1dc735298c478688d50c7a682fb3b0076a87b6634923132709f2d2fa9b**. No independent university-side checksum was available; this distinction is documented. Download has bounded retries, timeouts, size checks, resumable bytes and mandatory final integrity verification. Extraction only permits original UFPR04 JPEG/XML members and checks member types, paths and sizes.

Cached the archive and **3,791 full 1280×720 images plus 3,791 XML files** under `data/pklot/`; extracted member checksums are saved. Original images/XML are unchanged. Added `third_party/PKLOT-LICENSE.md` with CC BY 4.0, authors, paper, official source, mirror/version/hash and derived-artifact attribution. UFPR04/UFPR05 are two views of the same UFPR car park, not two separate physical sites.

The first converter attempt discovered original XML uses both `<point>` and `<Point>`. Fixed the parser to accept both and added regression coverage; did not alter the source annotations. Converted original numeric IDs to 28 stable `UFPR04-P01`–`UFPR04-P28` IDs and integer polygons. Missing occupancy labels are excluded from binary ground truth: **105,845 labelled observations, 303 unlabelled slot/frame pairs**. A metadata/count/hash pass parsed all XML for the saved manifests; held-out labels were never used to select references, thresholds, geometry or profiles. Test pixels were not decoded, visually inspected or inferred before the frozen test run.

### Day partitions and actual production processing

Seed **20260922**, sorted unique dates shuffled by Python random.Random, largest-remainder 60/20/20 day allocation. All weather folders for the same date stay together. There are **30 dates**: fitting **18 days / 2,341 images / 65,355 labelled observations**, calibration **6 / 709 / 19,817**, test **6 / 741 / 20,673**. Manifests preserve exact dates, timestamps, paths, labels, polygons and JPEG/XML hashes. Byte-level duplicates and decoded-content leakage/duplicates are rejected. No frame sampling or class balancing was applied.

Added `src/parking_probe/pklot_evaluation.py` and `checks/evaluate_pklot.py` with prepare/fit/calibrate/test/all phases. `SnapshotRecording` streams original-size images chronologically per day through the real CV branches. Dataset-local capture time has an unspecified timezone and is stored separately from fresh local decode timestamps; historical dates do not masquerade as live freshness. Models start anew each day from fitting-only empty reference patches; unsupervised MOG2 updates remain chronological and never use labels. The old video-specific preparers were not repurposed incompatibly.

Generalized `MOG2Branch` with explicit `expected_sample_interval`: PKLot passes 300 seconds, giving a reset threshold of **1,500 seconds**, five expected samples. An omitted keyword preserves the legacy 15-second behavior and byte-identical signature parameters, even for callers with other replay intervals. All other MOG2 settings remain unchanged. Tests cover regular 300-second spacing, exact boundary, larger gaps, invalid intervals and legacy signature equality. Snapshot cadence is explicitly not equivalent to continuous video: intervening motion is unseen and 0.001 learning remains per observation.

Factored `reference_boundaries` from the existing percentile/calibration metadata logic and `ClassificationMetrics` from the existing evaluator. Both evaluators now share the same metrics. Added occupied-positive precision, recall, F1, coverage, conditional/unconditional error rates, correct decisions over all truth, all-positive recall and a full 2×4 confusion matrix. Accuracy/P/R/F1 condition on definite decisions and always appear with coverage. Missing decisions are preserved, not silently counted as vacant or removed from the total. Per-branch, per-bay, per-weather and accepted/rejected-alignment strata are saved. YOLO requested-only denominators are distinguished from all labelled observations.

### Fitting findings and frozen calibration

Selected the first complete fitting frame as setup, **2012-12-08_07_30_02**; all 28 bays had an XML-labelled vacant reference in that fitting view. The one shared reference-source frame was excluded from every bay's threshold fitting. No missing reference files. Each bay retained **693–978 vacant and 592–881 occupied** valid fitting examples; the exact 28-row counts and percentiles appear in `EXTERNAL_VALIDATION.md` and the JSON report, with sample hashes and all raw fitting scores retained.

The fitting images exposed **three camera/polygon arrangements**, visually checked using fitting-only overlays. Retained a single fixed setup and the existing eight-pixel alignment guard instead of moving polygons using evaluation labels or bypassing validation. Fitting excluded 765 alignment-failed frames plus the reference-source frame. There were 1,576 actual MOG2 updates and nine gap resets. Threshold fitting calibrated **19/28 Reference bays and 0/28 MOG2 bays**: every MOG2 empty/occupied percentile pair overlapped despite abundant two-state examples. This is a real failure of separability under these settings, not a shortage of examples. Added fitting-only distribution plots and camera-position overlays with the optional `checks/plot_pklot_fit.py` script (Matplotlib already installed; not a core evaluation dependency).

Compared both existing **YOLOv8s small** COCO/aerial profiles on calibration data at their unchanged input size, 0.80 vehicle threshold and association rules. Selection criterion was declared before evaluation: maximize correctly decided observations over all labelled observations, then minimize false-vacant errors, then COCO as final tie-break. Calibration final COCO: **228 correct occupied / 19,817 (1.1505273250% coverage)**; aerial: **2,468 / 19,817 (12.4539536761%)**; both had zero errors among their definite decisions and zero vacant decisions. Selected **aerial** before test. Calibration had 341 rejected frames, 368 MOG2 updates and two actual gap resets.

Saved code, runtime, model-manifest, references, configs, partitions and protocol fingerprints to `runs/verification/pklot/frozen.json`. Freeze SHA-256 **bd4aed4bcd178a52cc27712ff770ff8674bae1ff8252c3c5547cab81b2d3a112**. The test-opening receipt locks fitting/calibration; completed day checkpoints are reused rather than reinferred. No frozen-pipeline implementation, threshold, model or profile changes followed opening the test partition. There were no interrupted test days or retries in the actual held-out run.

### Held-out measurements

Completed all **741 test frames / 20,673 labelled observations** (15,118 occupied truth, 5,555 vacant truth; 75 unlabelled pairs excluded). Both predetermined profiles were measured; the primary profile remains the calibration-selected aerial model. Test weather: sunny 431 frames, cloudy 276, rainy 34. Rainy observations all failed the alignment guard, so rainy accuracy is undefined, not evidence of robustness.

- **Reference:** 4,130 classified, 16,543 unresolved; TP 3,808, TN 210, false-vacant 106, false-occupied 6. Classified accuracy **97.2881355932%**, precision **99.8426848453%**, conditional recall **97.2917731221%**, conditional F1 **98.5507246377%**, coverage **19.9777487544%**. False-vacant rate over all occupied truth **0.7011509459%**; false-occupied over all vacant truth **0.1080108011%**. Corresponding classified-truth error rates **2.7082268779% / 2.7777777778%**.
- **MOG2 and classic consensus:** zero classified decisions, hence zero coverage and undefined conditional accuracy/P/R/F1. Zero error counts here do not mean a working classifier.
- **Final COCO:** 140 correct occupied, zero vacant, zero errors, coverage **0.6772118222%**; 20,533 unresolved.
- **Final aerial (selected):** **5,222 correct occupied, zero vacant, 15,451 unresolved** (1,285 uncertain / 14,166 unknown). Classified accuracy/precision/conditional recall/conditional F1 **100%**, coverage **25.2600009674%**. False-vacant/false-occupied counts **0/0**, unconditional rates **0%/0%**. Conditional false-occupied rate is undefined because no vacant-truth observation was classified. This does **not** demonstrate reliable vacancy detection.
- To expose the limitation behind conditional 100% recall/F1, algebraic postprocessing of the same frozen counts also reports occupied recall counting abstentions as missed positives: **34.5416060325%**, with corresponding F1 **51.3470993117%** for final aerial. Confusion states remain unchanged. This additional table is saved in `pklot-abstention-metrics.json`; it involved no inference or tuning. Reference equivalents are **25.1885169996% recall / 40.2281850835% F1**.

The alignment guard rejected **508/741 frames**: 188 camera_view_changed, 214 background_alignment_failed, 100 background_matches_too_concentrated, six insufficient_background_matches. The remaining **233 frames / 6,507 labelled observations** had final aerial coverage **80.2520362686%** with all classified decisions correct, but still no confirmed vacancies. MOG2 made 233 updates and zero gap resets on test; normal five-minute spacing did not disable its temporal updates. Propagated alignment failures are reported as YOLO skip/error reasons, not mislabeled as model inference crashes.

Measured final-aerial per-profile pipeline latency (decode/checksum + Reference + MOG2 + selective verifier), all frames: median **62.0672 ms**, P95 **712.9336 ms**, maximum **1,301.3700 ms**. The low overall median includes many rejected frames with no inference. Both profiles ran sequentially on Windows CPU, two OpenCV threads; this is not a controlled deployment throughput benchmark. Full branch timing, reason distributions, per-bay metrics, weather confusion matrices and observations are retained.

### Verification, delivery and limits

Full final suite: **254 passed in 64.16 seconds**, `runs/verification/pklot-tests-final.xml`. Added 10 PKLot tests covering original XML spelling/unknown labels, archive allowlists/checksum/bounded failure retries, day separation across weather, duplicate rejection, metric arithmetic, legacy MOG2 signatures and snapshot gaps, chronological adapter, profile selection, test locks and an integration exercising real Reference/MOG2/YOLO/final-policy paths with a test verifier. The integration checks completed-day reuse avoids repeated inference. Initial targeted checks and the intermediate full suite also passed; XML casing was discovered and corrected before calibration/test.

Added `checks/check_pklot_results.py`; it independently checks saved truth/frame identities, all/weather matrix counts and ratio arithmetic, no date/content leakage, final-decision routing, unusable-view abstention, frozen fingerprints and protected files. Passed **80,980 decision-policy checks** across calibration/test and verified **636 protected files unchanged**; evidence `runs/verification/pklot-delivery-check.json`. Ran the default evaluation command after completion: it verified the freeze/model assets and returned the saved test report without rerunning inference.

Created **EXTERNAL_VALIDATION.md** with quick commands, source-interface discrepancies, source/license/hash, exact dates/sizes, every bay's calibration counts, all measured metrics/matrices/weather results, fitting plots, MOG2 cadence and domain limits. `checks/render_pklot_report.py` regenerates it solely from saved numbers. Updated README to link the independent experiment and scope earlier unmeasured-accuracy statements to CHAD/overhead. Added this work log and the validation index entry. All new outputs stay in `data/pklot/` or `runs/verification/`.

This experiment does not prove that more labelled examples alone make the existing hybrid accurate and complete. It demonstrates a useful conservative occupied-vehicle verifier, poor whole-dataset coverage from changed camera geometry, and failure of the current MOG2 features to calibrate under periodic snapshots. A subsequent camera-position-aware/illumination-aware or parking-specific classifier experiment needs a separately designed evaluation with untouched test data. No retuning was performed on this holdout; no indoor/live/CHAD accuracy claim, UI change, deployment, database, Flutter work, hardware installation or proposal edit was made.

Final delivery checks: **71 local Markdown links resolve**, new source/check/test helper syntax parses, frozen fingerprints still match, and abstention-sensitive F1 arithmetic matches the saved confusion counts. Added these checks to `pklot-delivery-check.json`. The generated fitting histograms and three fitting-camera overlays were visually inspected. The complete report was queued for display in the Codex file panel. No production changes followed the final test suite or the frozen held-out evaluation.

## 22 September 2026 - MOG2 contribution and opt-in Reference priority

### Request verification and scope

Read both pasted requests and confirmed the later replacement attachments were text-identical. Before editing, inspected the actual `interface.py`, `comparison.py`, `yolo.py`, `mog2.py`, `output.py`, saved `runs/areas` schema, `interface_model.py`, `SiteReporter` and frozen PKLot artifacts. Confirmed `final_decision(reference, mog2, verified)` returns `(state, reason)` and `needs_verification` requests YOLO unless both classic branches agree definitely. `MOG2Branch` already accepts `expected_sample_interval`; no additional MOG2 change was needed. Saved paired observations use `rows[].final_state/final_confirmed_by` and a top-level `final` branch; export support follows that actual schema.

Flagged the wording discrepancy: the detailed alternate function must accept **both occupied and vacant** calibrated Reference results, even though the shorthand and example toggle mention only vacancy. Implemented that exact broader rule and named the toggle Reference priority. Also flagged that skipped YOLO cannot support a causal counterfactual; the diagnostic reports absence of an alternative **recorded** confirmation rather than guessing an unrun model's answer.

Before changes, matched all nine source hashes in the PKLot freeze, archived those exact files to `runs/verification/reference-priority/frozen-source/`, and recorded 759 protected-file hashes. Combined with the original protected set, the final audit checks 927 unique unchanged files. No MOG2 model/threshold, Reference calibration, CHAD/overhead recipe/polygon/reference, primary Final function, DECISION_FIX.md, source video, model weight, proposal or frozen prediction was changed.

### Implementation and measured diagnostic

Added [alternate_policy.py](src/parking_probe/alternate_policy.py), with `final_decision_reference_priority(..., reference_calibrated=False)` returning explicit state/reason/confirmation and experimental/non-primary metadata. A valid definite Reference result is labelled `reference_only_experimental`; every other case falls back to the unchanged original Final function. Added a copy-based paired-observation derivation and separate opt-in JSONL/CSV export. No absence-of-detection vacancy rule was introduced.

Added calibration provenance to new replay rows using the existing Analyzer hash/threshold validity check. `run_comparison` has an explicit default-False `alternate_policy` keyword for programmatic combined exports. GUI preparation retains normal primary-only exports; enabling its default-OFF toggle derives from already-computed observations and writes separate combined primary/alternate files to the run's `experimental-reference-priority/` directory. New samples refresh that export while enabled. Disabling hides the alternate and retains its timestamped historical export. Primary Final, confirmation sources, charts, areas, video and 10-second windows remain unchanged.

Added the experimental columns and selectable confirmation details, with EXP markers and a purple explanatory note that Reference priority applies to occupied AND vacant and may override YOLO. Added Reports → View external validation report, a read-only Tk text window with no inference, dataset playback or file editing. The Live camera tab remains a viewer only.

Added [checks/diagnose_mog2_contribution.py](checks/diagnose_mog2_contribution.py), reading only existing replay logs/configuration. Confirmed eligible sets: Camera 1 B01/B02/B03 and overhead W01/W02/E01. Camera 2/3/4 have zero eligible bays and are excluded. Input is `runs/areas/20260921T161408_115721Z`; checked saved model signatures, unique observation identities and the current primary rule before computing metrics. Per-camera/per-bay counts and exact input hashes are retained in [mog2-contribution.json](runs/verification/reference-priority/mog2-contribution.json), with paired [CSV](runs/verification/reference-priority/calibrated-bay-comparison.csv) and JSON.

- CHAD: 117 observations, 89/89 overlapping definite agreements; MOG2 alone definite 7/117 (5.98%); Reference alone definite 18/117 (15.38%); 89 primary classic confirmations without another recorded confirming route.
- Overhead: 30 observations, 12/12 agreements; MOG2 alone 3/30 (10.00%); Reference alone 4/30 (13.33%); 12 such classic confirmations.
- Combined: 147 observations; 101/101 overlapping definite agreements; 10/147 MOG2-only (6.80%) and 22/147 Reference-only (14.97%). All 101 classic confirmations skipped YOLO for that bay, so an alternative detector outcome is unknown. These are correlated repeated observations and branch agreement, not independent accuracy evidence.
- Alternate counts on the selected calibrated bays: CHAD 41 occupied / 62 vacant / 14 unresolved → 41 / 68 / 8 (88.03% → 93.16% coverage); overhead 7 / 8 / 15 → 9 / 9 / 12 (50.00% → 60.00%). Seven more vacant and two more occupied observations resolve. **CHAD/overhead have no independent labels beyond the calibration set; accuracy and false-vacant rate remain unmeasured.** Accepting one branch increases reliance on its lighting/appearance sensitivity and does not repair uncalibrated bays.

### Frozen PKLot post-hoc comparison

Added [checks/compare_reference_priority.py](checks/compare_reference_priority.py). It reads the already-saved calibration/test observations, checks exact frame/truth sets and checkpoint identities, verifies original archived code/calibration hashes, preserves the pre-test selected aerial profile, and requires primary metrics to match the original report exactly. It writes only new comparison artifacts outside the frozen directory. No new image inference, fitting, threshold changes, partition/profile selection or reopening of the freeze occurred. This policy was designed after the original holdout was seen: the new results are explicitly **post-hoc**, not a newly preregistered experiment.

Calibration: 19,817 observations. Primary coverage 12.4540%, classified accuracy 100%, no false-vacant/false-occupied errors. Alternate coverage 38.5679%, accuracy 94.0076%, 155 false-vacant and 303 false-occupied, conditional false-vacant 5.6985%. It overrides 152 correct YOLO occupied confirmations to vacant.

Test: 20,673 observations. Primary classified 5,222 (25.2600% coverage), 100% classified accuracy, no vacant confirmations or measured errors. Alternate classified 6,030 (29.1685% coverage), 98.1426% classified accuracy; TP 5,708, TN 210, false-vacant 106, false-occupied 6, uncertain 477 and unknown 14,166. It changes 84 correctly YOLO-confirmed occupied observations to vacant, 232 uncertain to vacant and 576 uncertain to occupied. Of 316 alternate vacant predictions, 106 (33.54%) are wrong. Conditional false-vacant is 106/5,814 = 1.8232%; Reference alone remains 106/3,914 = 2.7082%. The lower percentage comes from a larger occupied denominator, not fewer false-vacant errors. Both yield 106/15,118 = 0.7012% over all occupied labels.

Saved [metrics/input hashes](runs/verification/reference-priority/pklot-reference-priority.json), [per-observation CSV](runs/verification/reference-priority/pklot-observations.csv) and JSONL. Added calibration/test tables, full alternate test confusion matrix, conflict counts and denominator explanations to [EXTERNAL_VALIDATION.md](EXTERNAL_VALIDATION.md#post-hoc-experimental-reference-priority-comparison). Its renderer now preserves the marked post-hoc appendix and prominent compatibility note on regeneration.

The original freeze hashes whole `comparison.py`; adding provenance/optional export changes that current hash. The old strict frozen-run/evaluation audit commands will reject the modified current tree. They were not weakened or used to update the freeze. The new saved-prediction comparison verifies the archived original source and unchanged frozen artifacts; use it or the saved report for these historical results. This compatibility limit is explained prominently in the external report and guide.

### Verification and documentation

- Existing comparison/interface tests: 25 passed. Added five focused tests, including exhaustive policy-state combinations, calibration validity gating, fallback equivalence, conflict visibility, immutable primary/secondary exports, default-OFF GUI behavior, both confirmation sources, read-only report and real replay integration with an intentionally failing MOG2 branch. An initial UI test fixture omitted the real schema's `processed_at` field; corrected the fixture. No production workaround was added for that fixture error.
- Full final suite: **259 passed in 61.35 seconds**, [JUnit report](runs/verification/reference-priority/tests.xml). No additional dependency was installed.
- [checks/check_reference_priority_results.py](checks/check_reference_priority_results.py) independently checked **40,490 PKLot** selected-profile observation policies/matrices/rates, **147 calibrated replay** observations, all input hashes and **927 unchanged protected files**. [Delivery audit](runs/verification/reference-priority/delivery-check.json).
- [checks/check_reference_priority_interface.py](checks/check_reference_priority_interface.py) loaded saved results only, exercised all **8 recordings / 60 sample pairs / 1,088 bay observations**, toggled the comparison and verified unchanged primary samples/counts, and opened the read-only report. No new inference. [GUI check](runs/verification/reference-priority/interface/result.json).
- Captured only this check's own application windows. Visual review caught clipping of lower details at smaller sizes; added overview vertical scrolling alongside table horizontal/vertical scrolling and repeated inspection at 1220- and 1100-pixel widths. Checked the default-off view, alternate columns, selected confirmation details and read-only report. [Default](runs/verification/reference-priority/interface/default-off.png), [alternate](runs/verification/reference-priority/interface/alternate-1220.png), [small-window details](runs/verification/reference-priority/interface/alternate-details-1100.png), [report](runs/verification/reference-priority/interface/read-only-report.png).

Created [REFERENCE_PRIORITY.md](REFERENCE_PRIORITY.md) with concise usage, API/export behavior, exact measured findings, scope and reproduction commands; added short navigation guidance in [INTERFACE.md](INTERFACE.md). Created [AI_CONSULTATION_LOG.md](AI_CONSULTATION_LOG.md), preserving supplied reasoning verbatim except the requested results/status completions, with separate factual verification notes and a citation ledger. Cross-linked the relevant older log entries and external report.

Flagged rather than silently correcting the supplied consultation's inaccurate or overbroad claims: uncalibrated bays can still reach occupied via YOLO; PKLot has three views of two physical sites; ordered snapshots can feed MOG2; the fitting ranges are 693–978 vacant and 592–881 occupied; Reference did predict 316 vacant (210 correctly); Final/YOLO classification metrics match but raw records/timings are not byte-identical; domain/cadence and score-noise causality were not isolated; 6,189 is alignment-accepted occupied truth; and the new hybrid's false-vacant denominator differs from Reference alone. Historical 254-test/636-file/80,980-check figures were verified and explicitly distinguished from this addition's checks. The original 82.05% CHAD MOG2 coverage was recomputed as 96/117, not mistaken for accuracy. The claimed external consultation/search history is attributed to the supplied account where the repository cannot independently verify it.

Final export review moved the opt-in enriched observation before the runtime last-sample assignment, so programmatic alternate runs retain secondary fields in final-summary rows as well as per-frame JSON/CSV. The focused replay/export regression checks passed after this adjustment; primary behavior is unchanged. See `runs/verification/reference-priority/export-regression-tests.xml`.

Final documentation check: all 122 local Markdown links resolve; changed Python sources/helpers parse; Q1–Q5 supplied reasoning matches verbatim, with only the requested status/results substitutions. Direct JSON checks confirmed the disputed example ranges, Reference confusion counts and matching primary/YOLO classification metrics. Re-ran the external-report renderer and verified that it preserves the post-hoc appendix and compatibility note. Evidence: [documentation-check.json](runs/verification/reference-priority/documentation-check.json).

No further model, source-search, calibration or performance experiment was added beyond this request. The alternate remains optional and off by default; MOG2 and primary Final remain active.

