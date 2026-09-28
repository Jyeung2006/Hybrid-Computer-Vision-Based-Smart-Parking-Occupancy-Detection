# Run the parking test

1. In VS Code, open **main.py**, select this project's **.venv** Python interpreter, and click **Run Python File ▶** or press **F5**.
2. Wait for preparation to finish; allow **about 2–3 minutes**, especially when new references are prepared. Progress appears at the bottom.
3. Choose **SITE → Overhead demo car park**. All **69 visible bays** are mapped. CHAD's four camera angles remain available under its site.
4. Open **Occupancy overview** for the circle chart and **Reference / MOG2 / MobileNet + empty / YOLOv8 / Final estimate** table. Scroll to see every bay; click a row for its method source and reason. **Watch video** shows the outlines. **Areas & availability** splits overhead into west/middle/east: 24/22/23 bays.
5. Press **Play**, **Replay**, or move the slider. Results change every **3 video seconds**; **10-second summaries** shows completed windows. **Open saved results** opens the JSON/CSV output folder.

**What you need to do now:** run the updated `main.py` and select the overhead site. Videos, the local MobileNet-SSD model and both YOLO models are already available on this computer; no manual URL, API key, download or additional installation is needed.

**Why video appears after a wait:** opening the popup automatically starts a fresh analysis of all mapped CHAD and overhead recordings before playback is enabled. The app loads MobileNet and YOLO locally, prepares/validates references and MOG2 calibration, samples the recordings every three video seconds, computes each method and Final for every mapped bay, then writes new summaries and report files. Existing MOG2 calibration may be reused, but the recording analysis is run again on each launch. Once the status says **Ready**, the selected local video opens and its first frame is decoded; switching recordings may add a smaller opening/decoding delay. The PKLot archive is unrelated to this startup. This wait is expected when the status says **Preparing** or **Analyzing**; an error or a long stall at one status should be investigated separately.

**Read Final estimate.** A definite Reference or MOG2 result is used before MobileNet. MobileNet's vehicle and reviewed-empty check handles bays where both classic methods are unresolved. YOLO runs only for still-unresolved bays or a definite Reference/MOG2 conflict. **OCCUPIED (P)** is a provisional guess when a valid frame has no definite method result; it counts as occupied but is not model-confirmed. Click a bay to see which method supplied the result.

The current replay has zero uncertain observations across the eight recordings, but includes provisional occupied guesses and a known pedestrian-obscured false vacancy at B08. Accuracy has not been established. See [OPENCV_FIRST.md](OPENCV_FIRST.md) and [the replay report](runs/verification/opencv-first/report.json).

These are recorded estimates, not live availability. The **Live camera** tab is a viewer for an authorized endpoint. Earlier `--terminal` mode keeps the original three-bay Reference/MOG2 comparison; `--check` tests OpenCV without calculating occupancy. Use normal Run for all 69 bays and YOLO.

[Guarded vacancy and results](GUARDED_VACANCY.md) · [Empty examples](EMPTY_REFERENCES.md) · [Mapping](OVERHEAD_MAPPING.md) · [Full work record](WORK_LOG.md)

To draw or adjust a bay yourself, follow the mouse controls and safe practice-config steps in [BAY_DRAWING_GUIDE.md](BAY_DRAWING_GUIDE.md). The normal interface uses the built-in presets, so a practice drawing does not change its results until the matching preset is reviewed and updated.
