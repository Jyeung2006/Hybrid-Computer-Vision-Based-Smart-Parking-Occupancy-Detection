# Spotlens — smart parking occupancy

Spotlens is a capstone project that estimates parking-bay occupancy from recorded camera footage using **Reference/MOG2 first, MobileNet + reviewed-empty evidence when both are unresolved, and selective YOLOv8 for unresolved bays or classic-method disagreements**. It includes a research visualization application and a Flutter website connected to a Python API.

**Project version:** Python `0.1.0`; Flutter `0.1.0+1`. Current inputs are recorded CHAD and Overhead footage. The website and replay are **recorded estimates/simulation, not live parking availability**.

## Choose which version to run

| Version | Launch from the full project folder | What opens |
| --- | --- | --- |
| **Visualization version — video and accuracy review** | Open **`main.py`** in VS Code and select **Run Python File**, or press **F5** | A separate desktop window with video, bay outlines, model-by-model results, charts and saved evidence |
| **Connected Flutter website** | Run **`./apps/parking_web/run-web.ps1`** in the IDE terminal | A local Python server; open **http://127.0.0.1:8765/** for the parking homepage and **/#/replay** for replay |
| **Uploaded Spotlens website package** | Inside the `spotlens` folder, run **`./start.ps1`** locally or **`python serve.py`** with its installed runtime | The same website/API from the package's `public` folder |

The website package contains the website/backend inputs. **`main.py` is an entry point of the full project checkout**, rather than the upload package. `apps/parking_web/lib/main.dart` is the Flutter source entry point; use the connected launch command above when you need actual backend data.

## Software to install

These are the versions verified on the development computer, not claims that every newer release is compatible.

| Software | Required/tested version | Needed for | Download |
| --- | --- | --- | --- |
| **Python, 64-bit** | **3.12.x**; tested **3.12.14**. Project requires `>=3.12,<3.13` | Visualization and Python API | [Python for Windows](https://www.python.org/downloads/windows/) |
| **Flutter SDK** | Tested **3.44.6 stable**, with **Dart 3.12.2** bundled | Editing or rebuilding the website | [Flutter SDK archive](https://docs.flutter.dev/install/archive) |
| **Visual Studio Code** | Tested **1.138.0**; this exact editor version is not required | The IDE instructions below | [VS Code](https://code.visualstudio.com/download) |
| **VS Code Python extension** | `ms-python.python`; no extension version is pinned | Python interpreter selection and Run Python File | Install **Python**, published by Microsoft, in VS Code Extensions |
| **VS Code Flutter extension** | `Dart-Code.flutter`; no extension version is pinned | Flutter/Dart editing | Install **Flutter**, published by Dart Code; it uses the Dart extension |
| **Web browser** | Chrome or Edge; no browser version is pinned | Website preview | Use your installed browser |

Install Python with the **Python launcher** and **Tcl/Tk** support for the desktop window. A GPU, PyTorch and the `ultralytics` Python package are not needed for normal inference: the runtime uses OpenCV DNN on CPU with cached Caffe/ONNX models. Model export has separate optional dependencies.

The tested Python dependency list is [requirements-tested.txt](requirements-tested.txt): **NumPy 2.5.3**, **OpenCV 4.14.0.94**, **Requests 2.34.2**, and **pytest 9.1.1**, plus pinned supporting packages. `setup.ps1` installs these versions. The upload package uses `requirements-runtime.txt` without test/export dependencies.

Flutter is unnecessary if you only run `main.py`, or serve a website build that already exists. Docker Engine with **Compose v2** is an alternative for server deployment; it is not required for the IDE workflow. The private server's Docker version was not recorded.

## First-time setup in VS Code

1. Clone/download the repository and open its **top-level folder** in VS Code. You should see `main.py`, `pyproject.toml`, `src`, `apps`, and this README.
2. Open **Terminal → New Terminal**, using PowerShell on Windows.
3. Run:

```powershell
./setup.ps1
```

4. Open the command palette (**Ctrl+Shift+P**), choose **Python: Select Interpreter**, and select **`.venv/Scripts/python.exe`** from this project.

The setup script creates `.venv` with Python 3.12 and installs the tested dependencies. It does not change Windows execution policy. If PowerShell blocks `.ps1` scripts, the equivalent setup is:

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-tested.txt
./.venv/Scripts/python.exe -m pip install --no-deps -e .
```

Recorded source/model downloads are pinned in the application. Verified cached files are reused. An ordinary Git checkout does **not** include ignored `data`, `runs`, `.venv` or the generated upload package, so first preparation may need network access. The delivered working folder/package already contains the relevant inputs. If a source is unavailable, inspect the reported error and the [source/provenance records](PROJECT_DOCUMENTATION.md#doc-video-sources).

## Run `main.py`: visualization version

1. Open **`main.py`** in the full project folder.
2. Click **Run Python File** or press **F5**. The supplied `.vscode/launch.json` selects the project interpreter and root directory.
3. Wait for the status to finish loading models, preparing calibration, and analyzing the recordings. Playback is enabled after preparation; startup can take minutes.
4. Select a site/recording and inspect **Occupancy overview**, **Watch video**, **Areas & availability**, and **10-second summaries**.

**What you see in the IDE:** the terminal shows startup/progress/errors. A separate desktop window shows the actual visualization. It displays **Reference, MOG2, MobileNet + empty, YOLOv8, and Final** as separate method columns. Click a bay for its decision source and reason; inspect the video polygons and open saved JSON/CSV results for comparison.

This version supports **video/data inspection and accuracy management**. It does not automatically prove accuracy: independent labels, false-vacant/false-occupied evaluation and coverage still matter. `OCCUPIED (P)` counts as occupied but remains a provisional estimate.

Equivalent launch:

```powershell
./.venv/Scripts/python.exe main.py
```

## Run the connected Flutter website

For first setup, install the Flutter SDK above, add its `bin` directory to PATH, and confirm:

```powershell
flutter --version
flutter doctor
```

From the project root in the IDE terminal:

```powershell
cd apps/parking_web
flutter pub get
cd ../..
./apps/parking_web/run-web.ps1
```

Open **http://127.0.0.1:8765/**. Keep the terminal running. The script builds Flutter and starts the Python website/API host on the same address.

**What you see:** the browser shows a circular occupancy chart and CHAD/Overhead availability cards from recorded Python Final results. A recording selector, **Run new analysis**, and **Open replay demo** are available. The replay page shows individual bays, source time, decision source, and confirmed/provisional/stale states.

To reuse an existing web build:

```powershell
./apps/parking_web/run-web.ps1 -SkipBuild
```

If port 8765 is occupied, use `-Port 8766` and open `http://127.0.0.1:8766/`. If script execution is blocked, build Flutter inside `apps/parking_web`, return to the project root, and launch Python directly:

```powershell
./.venv/Scripts/python.exe -m parking_probe.web_server --port 8765
```

Open **`apps/parking_web/lib/main.dart`** to edit the Flutter application. A standalone `flutter run`/static server does not supply the Python `/api/` routes; use the connected launch command to show real recorded data.

## Results and project structure

| Path | Purpose |
| --- | --- |
| `main.py` | Visualization-version launcher |
| `src/parking_probe/` | Detection, bay mapping, recorded/replay processing, SQLite status and local API |
| `apps/parking_web/lib/` | Flutter homepage, replay page, API client and components |
| `presets/` | Bay geometry, reference examples and calibration recipes |
| `data/`, `assets/models/` | Cached videos/models and prepared inputs; most are not committed |
| `runs/areas/` | Recorded analysis history and JSON/CSV evidence |
| `runs/replay/` | Replay status/events and historical session evidence |
| `checks/`, `tests/` | Evaluation utilities and software checks |
| `scripts/package_spotlens.py` | Creates a portable website/backend upload folder; preserves an existing package |
| `scripts/spotlens/` | Server/runtime templates, Dockerfile and launch helpers |
| `README.md` | Installation and launch instructions |
| `PROJECT_DOCUMENTATION.md` | All implementation notes, experiments, work history, deployment steps and attribution |

Default website inventory is **9 CHAD Camera 1 bays plus 69 Overhead bays**. The recordings come from different periods; combined recorded counts do not represent simultaneous live occupancy. Invalid or stale replay frames are unavailable, and provisional states remain labelled.

The last public-host check on **2 October 2026** confirmed a working `/api/` connection at `spotlens.cc`, while a new-analysis job had failed. That is historical deployment evidence, not a claim that the server was rechecked today. See the [1Panel guide](PROJECT_DOCUMENTATION.md#doc-1panel-backend-connect-guide).

## Verification

From the project root:

```powershell
./.venv/Scripts/python.exe -m pytest -q
```

For Flutter, from `apps/parking_web`:

```powershell
flutter analyze
flutter test
flutter build web --no-web-resources-cdn
```

Recorded test outcomes and measured limitations are preserved in the [consolidated documentation](PROJECT_DOCUMENTATION.md). Software tests and replay counts are not an independent accuracy percentage.

## Troubleshooting and documentation

- **Desktop does not open:** verify Python 3.12, the project `.venv`, and Tcl/Tk support. Read [Windows/OpenCV troubleshooting](PROJECT_DOCUMENTATION.md#doc-troubleshooting).
- **Website cannot connect:** run the Python host as well as Flutter, and use the same-origin preview URL. Static hosting alone cannot run the detectors.
- **Server homepage works but `/api/` returns 404:** inspect the running backend and reverse proxy using the [1Panel connection guide](PROJECT_DOCUMENTATION.md#doc-1panel-backend-connect-guide).
- **New analysis reports failed:** read `runs/areas/<run-id>/web-analysis-error.txt`; saved homepage data can remain available while a new job fails.

The redundant **4.90 GB PKLot archive was removed on 5 October 2026**. Extracted research images, split/label/provenance manifests and evaluation results remain. The app does not need that archive. A clean rebuild of missing benchmark images would need the pinned download again.

Only two authoritative Markdown documents are maintained: **this README** and **[PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)**. The generated Spotlens package carries copies of those same two documents. Its source notices and the project's full work log are sections of the consolidated file; original `.txt` licenses remain intact.

## Data, licensing and scope

This is research software. Model, dataset, video and font attribution/license records are retained in [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md#attribution-and-licenses) and the original license text files. They do not constitute a blanket permission to redistribute every input or enable automated third-party live-camera ingestion. The existing public source material does not establish target-site live accuracy.
