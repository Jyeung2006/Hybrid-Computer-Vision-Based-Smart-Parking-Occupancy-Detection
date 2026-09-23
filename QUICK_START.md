# Run the parking test

1. In VS Code, open **main.py**, select this project's **.venv** Python interpreter, and click **Run Python File ▶** or press **F5**.
2. Wait for preparation to finish; allow **about 2–3 minutes**, especially when new references are prepared. Progress appears at the bottom.
3. Choose **SITE → Overhead demo car park**. All **69 visible bays** are mapped. CHAD's four camera angles remain available under its site.
4. Open **Occupancy overview** for the circle chart and **Reference / MOG2 / YOLOv8 / Final estimate** table. Scroll to see every bay; click a row for its reason. **Watch video** shows the outlines. **Areas & availability** splits overhead into west/middle/east: 24/22/23 bays.
5. Press **Play**, **Replay**, or move the slider. Results change every **3 video seconds**; **10-second summaries** shows completed windows. **Open saved results** opens the JSON/CSV output folder.

**What you need to do now:** run the updated `main.py` and select the overhead site. Videos and both YOLO models are already available on this computer; no manual URL, API key, download or additional installation is needed.

**Read Final estimate.** Matching definite Reference/MOG2 results stay immediate. Otherwise YOLO runs: a qualifying vehicle confirms occupied. An unresolved bay can become vacant only after three consecutive clean three-second samples, with a reviewed empty match if available. **VACANT (P)** means provisional vacancy based on repeated no detection, without a reviewed empty reference. Click a bay for its evidence.

The latest replay's overhead final sample is **48 occupied + 9 vacant + 12 uncertain = 69 bays**. No provisional vacancies occurred in that replay; all newly resolved vacancies matched reviewed empty evidence. Accuracy has not been established. See [GUARDED_VACANCY.md](GUARDED_VACANCY.md).

These are recorded estimates, not live availability. The **Live camera** tab is a viewer for an authorized endpoint. Earlier `--terminal` mode keeps the original three-bay Reference/MOG2 comparison; `--check` tests OpenCV without calculating occupancy. Use normal Run for all 69 bays and YOLO.

[Guarded vacancy and results](GUARDED_VACANCY.md) · [Empty examples](EMPTY_REFERENCES.md) · [Mapping](OVERHEAD_MAPPING.md) · [Full work record](WORK_LOG.md)
