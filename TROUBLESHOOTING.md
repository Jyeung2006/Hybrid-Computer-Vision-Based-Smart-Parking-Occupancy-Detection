# Troubleshooting

> **22 September correction:** Final now requires definite Reference/MOG2 agreement or a qualifying YOLO vehicle. The separate empty-image override has been removed; all three unresolved can no longer produce vacant. Reviewed images remain available for calibration. See [DECISION_FIX.md](DECISION_FIX.md) for the rule and [FINAL_RESULTS.md](FINAL_RESULTS.md) for current results.


**Why did all three methods say unresolved but Final say vacant?** The 21 September implementation used a separate reviewed-empty-image heuristic after YOLO. It has now been removed. Final vacancy needs Reference + MOG2 agreement. Restart the old window to load the corrected code. The current vehicle-only YOLO cannot confirm vacancy from no detection; the [empty examples](EMPTY_REFERENCES.md) are retained for future calibration.

**Current status:** OpenCV and YOLOv8 work locally. All eight recordings were checked successfully; no Windows setting change or manual download is needed. Restart the old interface and run `main.py`. See [QUICK_START.md](QUICK_START.md).

**Preparation looks paused:** analysis happens before recorded playback. The latest cached check took about 73 seconds. Follow the bottom status; when ready choose Watch video and Play. First media retrieval/calibration on another computer may take longer.

**Only three overhead bays appear:** an old window or legacy mode is running. Close it, run current `main.py` normally, then select SITE → Overhead demo car park. The table scrolls through all 69 bays. `--terminal` intentionally retains its original three-bay CHAD comparison; `--check` only tests decoding and has no occupancy calculation.

**Many Reference/MOG2 cells are UNKNOWN:** 66 overhead bays do not have verified empty references plus enough examples of both states. They are mapped, counted and passed to YOLO; missing evidence is not hidden. Click a bay to read the reason. Stationary occupied cars are included.

**YOLO says SKIPPED:** both classic branches already agree on occupied or vacant, so their result is kept. YOLO may still run once for another bay in the same frame.

**YOLO/Final remains UNCERTAIN:** no sufficiently strong, uniquely associated vehicle was found. A missed car does not prove vacancy. The proposal's 0.80 vehicle threshold is retained, and normal Run no longer uses the old one-sided empty-image fallback. Therefore some previous CHAD vacancies now remain uncertain. More verified references and separate vacant/occupied calibration examples are needed; do not label uncertain bays free or lower thresholds to force a result.

**Camera 1 near row:** P009's SUV is detected directly. P008 remains uncertain under the stricter rule. Other selected clips are not time-synchronized and cannot provide a contemporaneous substitute result. Camera 2/3 far-row IDs are still view-local.

**Overhead drift:** the current recipe applies guarded registration and all ten analysis samples passed. A substantially changed view, featureless image, wrong resolution or warp padding inside a bay still fails. Use the recorded error reason and recalibrate a changed camera; references are never silently replaced.

**YOLO model integrity error:** normal Run expects both ONNX assets and `yolov8s-manifest.json` under `assets/models/`. Keep them together when copying the project. The optional rebuild recipe is in [YOLOV8-SOURCES.md](third_party/YOLOV8-SOURCES.md); it is not needed for the supplied copy. Model failure leaves unresolved evidence rather than fake vacancy. Check `source-status.json` through Open saved results.

**Live camera:** this tab is a viewer for an authorized endpoint, not live occupancy. The supplied videos and their mappings cannot establish current live vacancy. See [INTERFACE.md](INTERFACE.md).

The following historical Windows discussion is retained as a record of the earlier resolved issue. It is not a required setup action for the working version.

## Earlier Windows loading issue (resolved in the current run)

**Earlier diagnosis:** the files had downloaded successfully, but Windows refused to load the installed OpenCV `cv2.pyd` library before it could read video. A repeated download was not a verified remedy for that trust/signing failure.

That earlier popup was a separate Tkinter dashboard whose static preview could appear even when OpenCV failed. The user subsequently ran the basic check successfully. The current chart/video interface was later added at the user's request; it is expected to open on normal Run. The basic diagnostic remains available behind `--check`.

On **15 September 2026**, Python reported:

```text
ImportError: DLL load failed while importing cv2:
An Application Control policy has blocked this file.
```

Windows Code Integrity events identify `.venv/Lib/site-packages/cv2/cv2.pyd` as blocked. This happens before a video is processed. The same project environment passed earlier tests on 10 September; those historical results do not establish that OpenCV works now.

## Your personal computer: available choices

You confirmed that this is your own computer. Microsoft documents turning Smart App Control off as an available user setting. That can remove this particular loading restriction, but it removes this additional protection for **all apps**, not just OpenCV. Keep Microsoft Defender antivirus and real-time protection enabled. If you want Smart App Control to remain on, the alternative is a publisher-supported trusted/signed OpenCV build; no such replacement has been verified for this project. [Microsoft's FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions).

If you accept the security trade-off and choose to change the setting yourself:

1. Open **Start → Windows Security**.
2. Select **App & browser control → Smart App Control settings**.
3. Select **Off**. Read the confirmation carefully before accepting, especially any warning about turning it back on. Microsoft says recent Windows updates permit re-enabling without reinstalling, but this should not be assumed for an older installation. If Windows warns that restoring it requires a reset, pause before confirming; a PC reset is not needed to perform this project check.
4. Start a fresh Python run: reopen VS Code, open **main.py**, and click **Run Python File**.

The settings path is documented in [Microsoft's Windows Security guide](https://support.microsoft.com/en-us/windows/security/windows-security/app-browser-control-in-the-windows-security-app). This is manual guidance; the assistant has not changed any Windows setting. No additional video or OpenCV download is currently required.

The basic check should get past the diagnosed import block if that restriction is removed. Success is established only when its terminal messages show OpenCV loading and actual video frames being decoded/processed. If a different error appears, retain that exact error for diagnosis.

Smart App Control does not offer a per-app allow exception, according to [Microsoft's FAQ](https://support.microsoft.com/en-US/Windows/Security/threat-malware-protection/smart-app-control-frequently-asked-questions). Publisher code signing is described in [Microsoft's developer guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control). No Windows protection settings were changed, and no blocked library was relocated or loaded through a different runtime.

After the compatibility issue is resolved, open `main.py` and press Run again. To verify from the project terminal:

```powershell
.\.venv\Scripts\python.exe -c "import cv2; print(cv2.__version__)"
.\.venv\Scripts\python.exe main.py --headless --frames 3
```

Run `main.py --check` to see the numbered basic checks. Its report is `runs/opencv-check/result.json`. Run `main.py` without that flag for the three-second occupancy table. The original MP4s can also be watched in a video player independently of either mode.

## Other messages

- **Missing dependency:** run `setup.ps1` using Python 3.12. Reinstalling packages alone is not an established fix for the Application Control block.
- **Public archive unavailable / range rejected:** check the connection and retry. Cached, verified videos work offline. The program deliberately refuses a whole-archive download.
- **Unknown bays:** inspect the generated `calibration-report.json`. Reference samples, alignment or separated thresholds could not be validated.
- **Camera view changed / resolution changed:** results become unavailable. Review the setup and bay configuration; references are not automatically refreshed.
- **Different recording selected:** the Site / View / Recording selectors switch playback after preparation. During preparation, wait for the ready message. Use Analyze again to create a new analysis run.
- **Video finished:** the last frame is timestamped recorded history. Replay or select another clip to continue; it is not a live camera.
