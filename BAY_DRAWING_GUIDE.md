# Drawing parking bays and handling a neighbour's car at the edge

## Why the current result becomes uncertain

The current YOLOv8s detector returns **vehicle bounding boxes**, not a pixel-by-pixel statement that a bay is empty. The existing vehicle-association step computes box/polygon overlap and an anchor point to decide whether a detection belongs to a particular bay. The guarded vacancy step is deliberately stricter: any raw vehicle box touching the polygon or a narrow band around it prevents a new vacant decision. A car protruding from the adjacent bay can therefore leave Final **uncertain** even when most of your bay looks clear. See `src/parking_probe/yolo.py` (`associate`) and `src/parking_probe/vacancy_guard.py` (`near_vehicle_box`). Ultralytics documents boxes and segmentation masks as different output types in its [prediction guide](https://docs.ultralytics.com/modes/predict/).

“70% looks like empty parking” is **not** a quantity this YOLOv8s box detector currently measures. A box covering 30% of a bay does not prove that the remaining area is vacant: the box may be imprecise, another car may be missed, and a person or shadow may hide evidence. A sensible experiment would calculate the actual vehicle-box overlap fraction **inside the bay polygon**, check whether the vehicle's ground-contact/anchor lies in the neighbouring bay, and compare against reviewed empty appearance across three consecutive observations. The 70% boundary would need testing on independently labelled empty, occupied and edge-overlap frames before changing Final. A pixel-level vehicle mask would require a segmentation model, which is a separate, untested model choice ([Ultralytics segmentation task](https://docs.ultralytics.com/tasks/segment/)). No detector setting or vacancy threshold was changed in this discussion.

## Draw one bay yourself on a built-in recording

The project already has an OpenCV mouse-based polygon tool. These steps let you practise without changing the built-in analysis. Use the **project root** as your VS Code terminal folder: `C:\Users\Ji Yeung\Downloads\Capstone Project Implementation`.

1. Pick the **local slot ID**, not just its displayed physical ID. For the overhead example, the displayed `OVER-EL11` uses local `EL11`. The existing slots and IDs are in `presets/overhead-all-bays.json`. CHAD Camera 1 uses local IDs `B01`–`B09` in `presets/chad-camera-1-expanded.json`.
2. In a PowerShell terminal, make a separate practice configuration. Do this once; keep the file for later bays:

   ```powershell
   Copy-Item .\config.example.json .\drawing-overhead.json
   ```

3. Open the actual **setup frame** in the drawing tool. This cached overhead frame exists on this computer and is already at the analysis resolution of 1100 × 720 pixels:

   ```powershell
   .\.venv\Scripts\python.exe -m parking_probe --config .\drawing-overhead.json configure --frame 'data/overhead-all/preset-6cf3e5ced65301e7/frames/overhead-1-000000.png' --slot EL11
   ```

   To practise on CHAD Camera 1 instead, start a **different** practice config copied from `config.example.json`, and use its 1280 × 720 setup frame:

   ```powershell
   .\.venv\Scripts\python.exe -m parking_probe --config .\drawing-chad1.json configure --frame 'data/chad-mapped/Camera-1/preset-36a2f03813a8db2c/frames/chad-1-000000.png' --slot B08
   ```

   For that second example, first copy `config.example.json` to `drawing-chad1.json`. Other camera views each need their own setup frame and config because their pixel coordinates differ.

4. In the window, **left-click** the visible corners of that bay in order around its outline. Usually four clicks make a quadrilateral. **Right-click** removes the last point. Press **Enter** to save; press **Esc** to cancel. The tool validates that points are inside the frame and the edges do not cross. It automatically converts clicks on the resized preview back to original image coordinates. OpenCV's mouse-event mechanism is described in its [mouse tutorial](https://docs.opencv.org/4.11.0/db/d5b/tutorial_py_mouse_handling.html).
5. Draw the **painted parking-space footprint** in the setup view, leaving only a modest margin from the shared painted line. Avoid swallowing a large part of the neighbouring space, roadway or hatched access zone. Keep enough of your own bay that a small or offset vehicle would still overlap it. Check the outline against frames where the bay is empty **and** occupied; a shape that looks good on only one frame may be misleading. If markings are hidden in the setup frame, use other frames as visual guides but keep the final coordinates aligned to this setup view.
6. Open `drawing-overhead.json` (or `drawing-chad1.json`) in VS Code. Find the slot's `polygon` array. It contains integer `[x, y]` corners in the analysis frame. Redraw the same slot ID with the same command if needed; changing its polygon removes the practice config's old reference/calibration. Use distinct local IDs for distinct bays.

**Important:** this practice config is **not** read by the normal `main.py` chart/video interface. Normal Run builds its mapped bays from `presets/overhead-all-bays.json` and the corresponding CHAD preset files. To use your drawing there, copy only the `polygon` array into the matching slot in the appropriate preset, preserving its `id`, `bay_id`, `area`, reference and example entries. Back up the preset first. A changed polygon changes what each old reference and calibration label measures, so review those examples again and rerun the analysis before trusting new counts. You can send me the practice JSON and the slot ID for that review and integration.

For your **own live camera**, the documented `configure`, `reference`, `label` and `calibrate` commands in [README.md](README.md) form a separate setup workflow. One camera/view needs its own polygons and verified empty examples; a polygon from the overhead video cannot be reused at a new camera angle.
