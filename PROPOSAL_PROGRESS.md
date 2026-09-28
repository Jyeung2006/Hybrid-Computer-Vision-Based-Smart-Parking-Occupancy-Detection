# Proposal progress and remaining goals

Review date: 28 September 2026, Malaysia time.

## Assessment

The project has a working **recorded parking-analysis prototype and a connected Flutter web home page**. It has substantial implementation work in image processing, per-bay decision routing, selective YOLO verification, result provenance, and software testing. The proposal's full acquisition-to-confirmed-database-state-to-mobile workflow and its controlled research evaluation are not yet demonstrated.

This assessment compares the proposal's actual Chapters 1, 3 and 4 with the active outer workspace, source code, tests and saved implementation reports. The nested `Hybrid-Computer-Vision-Based-Smart-Parking-Occupancy-Detection` copy is not treated as the current application. No new inference, benchmark, production test, or remote-server inspection was performed for this review. Prior test counts are historical evidence, not newly rerun tests. Absence of deployment evidence locally means deployment is **not verified here**, rather than proof that nothing exists elsewhere.

Source: [NgJiYeung_23026479_proposal.docx](NgJiYeung_23026479_proposal.docx). SHA-256: `23eb3797f805394ddea5ef7af5a48b83f3f89291bb24eaaa73265031134b369e`.

The proposal schedules Capstone 2 implementation from 28 September 2026, with final evaluation and delivery in January 2027. These are remaining acceptance requirements; this assessment does not imply they are already overdue. Actual module deadlines take precedence over the draft schedule. No completion percentage is assigned because implementation volume and accepted research outcomes have different weights.

## What is already implemented

- Polygonal bay mapping, empty-reference comparison, stateful MOG2 analysis, image validation, alignment checks, branch provenance, and recorded chronological processing.
- Local MobileNet-SSD plus reviewed-empty evidence and the user-approved OpenCV-first decision policy. This is an additional method beyond the original proposal.
- Selective YOLOv8s vehicle verification, a bounded single-worker queue, one shared inference per requested frame, confidence/association checks, and handling of full queues, failures, timeouts and superseded responses.
- Saved per-bay Final states, decision reasons, JSON/CSV histories, annotated review output and ten-second summaries.
- A responsive Flutter web home page connected to actual recorded Final results through a local JSON API. It shows counts, provisional results, recording selection, analysis timestamps, retry states and a background analysis action.
- Automated tests for the existing implementation and a separate day-separated PKLot external experiment. These are valuable evidence, with the limitations below.

## Requirement comparison

| Proposal requirement | Status | Current evidence | Remaining acceptance work |
| --- | --- | --- | --- |
| Permitted fixed-camera acquisition and ONVIF GetSnapshotUri (§3.2) | Partial | `sources.py` supports configured HTTP snapshots/streams, authentication, timestamps, timeouts and bounded retries. Local HTTP fixtures test acquisition. A legacy Reference-only online CLI exists. | Add ONVIF profile/snapshot-URI acquisition or formally document an approved change. Connect periodic acquisition to the complete current hybrid pipeline and Flutter. Validate a permitted camera or declared fallback test feed, with traceable timestamps and errors. |
| Representative target scope and all required references (§1, §3.2, §3.7) | Partial | CHAD and Overhead mappings and reviewed reference banks exist. | Establish the final study zone/views and unique physical bays. Proposal intends about 20–40 bays across up to four views; current website aggregates 9 CHAD and 69 Overhead bays from different recorded periods. This is not one simultaneous target zone. Complete or explicitly limit reference/calibration coverage. |
| Reference and MOG2 evidence extraction (§3.3) | Implemented foundation | `vision.py`, `mog2.py`, calibration code and chronology/failure tests. | Validate the selected final dataset and camera conditions. The implementation does not itself establish acceptable detection accuracy for every mapped bay. The proposal's parallel branch execution/join is not demonstrated as a separate deployed parallel stage. |
| Calibrated logistic occupancy probability (§3.3) | Not implemented; method changed | `opencv_first.py` selects discrete states using a priority rule. No fitted logistic occupancy model or probability calibration report was found in the active source. | Either implement fitting/calibration and probability-boundary tests, or revise the methodology to the approved OpenCV-first/MobileNet policy with supervisor agreement. Raw difference, foreground ratio and object confidence must not be called occupancy probability. |
| Selective YOLOv8s and bounded verifier (§3.4) | Largely implemented for recorded operation | `yolo.py` uses a single worker and a queue with one waiting frame; tests cover threshold, shared inference, ambiguity, saturation, failure and supersession. | Complete concurrent-camera/VPS load evidence, sustained queue monitoring and end-to-end publication tests. Record the current fallback policy differences rather than claiming exact adherence to the proposal. |
| General three-snapshot state confirmation (§3.5) | Not implemented as proposed | `vacancy_guard.py` requires a streak for one guarded-vacancy route; other definite Final routes can resolve immediately. | Add a per-bay state machine for both occupied and vacant candidates: startup unknown, pending candidate/count, interrupted sequence, stable confirmed state, stale age and restart recovery. The vacancy guard and ten-second summary do not satisfy this general requirement. |
| Transactional PostgreSQL persistence (§3.5) | Not implemented | Results are persisted as local JSON/JSONL/CSV; there is no PostgreSQL integration in active dependencies/source. | Schema/migrations for cameras, bays, jobs and status; unique snapshot-slot keys; atomic updates; ordering/idempotency; retry/restart recovery; publish only committed states. File persistence exists, but it is not the proposed transactional state service. |
| FastAPI REST and WebSocket delivery (§3.6) | Partial functional substitute | `web_server.py` serves a read API and analysis POST using Python's standard HTTP server; Flutter polls every three seconds. | Implement the specified FastAPI contract, WebSocket events and reconnect/current-state recovery, or formally revise the chosen transport/framework. The present API is not FastAPI and has no WebSocket push channel. |
| Zone and individual-slot Flutter presentation (§3.6) | Partial | Aggregate occupancy ring and area cards, recorded provenance, provisional labels, backend failure/retry, responsive layout and accessibility checks exist. Per-bay states are already in the API. | Add a usable area/slot view, confirmed versus candidate/provisional distinction, live observation age, explicit stale last-confirmed values and per-camera/service health. Validate the intended mobile delivery on a real device; a responsive web viewport alone is not a native mobile build or usability study. |
| Security and retention controls (§3.6, §3.9) | Partial foundation | Local-only host, origin/header guard for starting analysis, source secret support and restricted web-asset serving. Browser receives status metadata rather than camera images. Some file output is bounded. | Deployed authentication/authorization, TLS, database least privilege, controlled research-image retention and ordinary-frame cleanup, disk bounds/alerts, and access/recovery checks. Local origin checks are not user authentication. |
| Ground truth and frozen 60/20/20 partitions (§3.7) | Partial | PKLot UFPR04 has a day-separated frozen split and external metrics. CHAD/Overhead have reviewed setup/calibration evidence. | Prepare representative final-study occupied/vacant/ambiguous labels, second-review evidence, session-separated partitions and frozen current-policy settings. Previously inspected/tuned samples cannot be relabelled as untouched final-test data. |
| OpenCV-only versus YOLO-only versus hybrid experiment (§3.8) | Not completed for current system | Existing branch/replay and PKLot reports provide groundwork. PKLot's YOLO rows are selective verification, not a full-frame YOLO-only baseline on all test frames. | Run all three configurations on the same held-out observations and polygons. If MobileNet remains in the hybrid, disclose it and preferably add an ablation to isolate its contribution. Report accuracy, precision/recall/F1, confusion matrices, error rates and coverage with stated denominators. |
| Environmental, calibration and statistical evidence (§3.8) | Partial historical evidence | External PKLot weather-stratified results exist. A known B08 obstruction failure is documented. | Evaluate adequately represented target conditions and errors; report session-level uncertainty intervals. Brier score/reliability plots apply if a calibrated occupancy probability is implemented, not to arbitrary detector confidence or discrete priority rules. Box mAP is conditional on having box annotations. |
| CPU-only VPS and operational evaluation (§3.8–3.9) | Not verified/completed here | Desktop per-frame processing timings exist; no final deployment/load evidence for the proposal's Debian VPS was found. | Deploy the selected workflow on the stated 4-vCPU/3.8-GiB server and measure CPU/RAM/disk, queue depth, retrieval success, p50/p95 acquisition-to-display latency, stale duration and recovery. Benchmark the proposal's candidate runtimes or document a justified scope change. Test up to four cameras at the three-second capture interval. |
| Complete end-to-end reliability and mobile acceptance (§3.8) | Partial | Many model, acquisition, UI, API count, request-ordering and failure tests exist. Last integration report records 27 Flutter checks and 29 relevant Python checks passing. | Exercise camera → candidates → confirmed database transaction → REST/WebSocket → Flutter, with database outage, duplicate/late jobs, camera/client reconnect and stale expiry. Add the predefined user tasks. Participant testing is conditional on institutional approval/consent, as the proposal states. |
| Final configuration freeze and research delivery (§4) | Not demonstrated complete | Detailed work logs and implementation Markdown exist. | Freeze the final code/configuration/dataset baseline, finish comparative results and limitations, and complete the final report, poster, demonstration and required submissions. Proposal presentation/submission completion cannot be inferred solely from the local DOCX. |

## Important methodology differences

These differences follow deliberate implementation choices and the user's later instructions. They should not be silently undone merely to match an earlier document.

1. **Probability fusion versus priority rules.** The proposal combines Reference and MOG2 scores into logistic `p(occupied)` and initially uses 0.40/0.60 boundaries. Current normal operation uses definite Reference/MOG2 first, then MobileNet plus reviewed-empty evidence, then selective YOLO. This is a valid experimental method to describe and evaluate, but is a different method.
2. **Unresolved fallback.** The proposal retains the previous confirmed state when YOLO is absent, weak or ambiguous. Current policy can use Reference after a conflict check, reviewed-empty guarded vacancy, or valid-frame **OCCUPIED (P)**. Provisional occupied is an availability assumption, not proof of a vehicle and not the proposal's confirmed-state rule.
3. **Temporal confirmation.** Three clean samples for one vacancy route do not mean every occupied/vacant transition is confirmed over three samples. If a confirmed-state service is added, keep raw model candidates and service-confirmed state distinct in the records and UI.
4. **Recorded delivery versus current live state.** Loading latest JSONL results and polling every three seconds updates the page, but does not capture a new real-world image every three seconds. Analysis time and recording position are not source capture freshness. The legacy online Reference command and Live viewer do not form the complete current hybrid-to-Flutter pipeline.
5. **Study scope.** The current 78-bay sum is drawn from two separate sites/periods. It demonstrates data aggregation, not the proposal's 20–40-bay synchronized university deployment. The proposal explicitly allows permitted prerecorded indoor footage and a fallback test feed when camera access is unavailable; that contingency still needs documented scope and operational limitations.

Recommendation: agree the final method and study scope with the supervisor before adding probability fusion or changing the now-preferred OpenCV-first behavior. A documented, evaluated change is clearer than presenting the implementation as if it still exactly follows the original five phases.

## Existing evaluation must be described accurately

The historical PKLot UFPR04 experiment reported 100% accuracy **among classified observations**, but only 25.26% decision coverage for its selected aerial profile, and no final vacant decisions. It is a separate outdoor experiment using an earlier policy. It does not establish 100% accuracy for the current CHAD/Overhead system, prove the current MobileNet/provisional fallback, or replace the complete three-way comparison.

The current policy's zero uncertain counts are also not an accuracy measurement. The known pedestrian-obstructed B08 in `chad-4` at 15 seconds still returns vacant through `mobilenet_reviewed_empty`. Its reviewed failure category and any ambiguous-ground-truth treatment must be explicit in the final study. Count provisional outcomes separately when evaluating the availability policy and do not use them to manufacture a higher confirmed decision coverage.

## Suggested order of remaining work

1. **Re-baseline the research method and scope.** Record the OpenCV-first/MobileNet and provisional-state deviations, the intended deployment/test feed, mapped inventory and what constitutes confirmed availability.
2. **Start the final dataset work immediately.** Collect and review independent occupied/vacant/ambiguous sessions and reserve the final test partition. Data access and condition coverage take time; do this alongside the service work.
3. **Build confirmed state and persistence.** Implement the generic per-bay temporal state machine and PostgreSQL transactions before calling displayed values confirmed.
4. **Connect continuous acquisition and publication.** Route periodic camera/test-feed snapshots through the hybrid worker, persist accepted state, and publish through the agreed API/WebSocket transport. Include freshness and recovery from the outset.
5. **Finish the driver-facing slot view.** Expose the already available bay-level identity/state with observation age, camera health and clear unknown/stale/provisional explanations; validate the intended phone platform.
6. **Freeze and evaluate.** Run the three-way held-out comparison, the resource/latency and failure experiments on the target server, and the mobile tasks. Use those results for the report and demonstration.

No payment, reservation, face recognition, licence-plate recognition, driver profiling, MQTT, edge deployment or full-campus scaling is needed to satisfy the stated baseline. Those are exclusions or optional future alternatives. YOLO fine-tuning/YOLO Medium and participant usability studies are conditional, not automatic missing features.

## How to run the connected Flutter preview in the IDE

Open the outer project folder in VS Code (or use another IDE's integrated PowerShell terminal). The existing VS Code F5 launch configuration starts `main.py`, the Python popup; it is not the Flutter launch command.

From the integrated terminal:

```powershell
cd "C:\Users\Ji Yeung\Downloads\Capstone Project Implementation"
.\apps\parking_web\run-web.ps1 -SkipBuild
```

Open `http://127.0.0.1:8765/`. Keep the terminal open; Ctrl+C stops the host. This uses the last built Flutter files and starts the Python API on the same origin.

After changing Flutter code, rebuild and launch:

```powershell
.\apps\parking_web\run-web.ps1
```

If the current preview already occupies 8765, reuse it, stop its own running terminal, or use a different port:

```powershell
.\apps\parking_web\run-web.ps1 -SkipBuild -Port 8766
```

Then open `http://127.0.0.1:8766/`. This workflow serves a compiled preview; it does not provide Flutter hot reload. A plain `flutter run -d web-server` alone lacks the connected API under the current same-origin configuration. If `flutter` is not on the IDE terminal's PATH, restart the IDE after SDK setup; this machine's SDK is `C:\src\flutter`.

## Evidence inspected

- [Proposal](NgJiYeung_23026479_proposal.docx), especially §§3.2–3.9 and Chapter 4 acceptance tables.
- [Current decision policy](OPENCV_FIRST.md), [mapping/calibration audit](MAPPING_CALIBRATION_AUDIT.md), [external validation](EXTERNAL_VALIDATION.md), and [validation history](VALIDATION.md).
- [Backend integration](BACKEND_INTEGRATION.md), [Flutter design/history](FLUTTER_UI.md), [work log](WORK_LOG.md).
- `src/parking_probe/{sources,cli,vision,mog2,opencv_first,vacancy_guard,yolo,bay_fusion,web_server}.py` and source/MOG2/YOLO tests.
- Flutter `lib/`, `run-web.ps1`, `.vscode/launch.json` and active `pyproject.toml`.

Only this assessment, the IDE launch guidance and the work-log entry were added for this review. The proposal and application behavior were not changed.
