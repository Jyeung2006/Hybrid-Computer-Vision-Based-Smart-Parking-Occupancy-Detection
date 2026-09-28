# Flutter parking home page

## Current status — 27 September 2026

The home page is now connected to actual Python **recorded** Final results. The default demo is replaced by an API client, a recording selector, background analysis action, provisional/unknown states and source timestamps. It remains explicitly **not live availability**. Use `./apps/parking_web/run-web.ps1` from the repository root to build and serve both frontend and API; add `-SkipBuild` to reuse the build. A standalone Flutter development/static server no longer supplies all required functionality. See [BACKEND_INTEGRATION.md](BACKEND_INTEGRATION.md) for the current commands, architecture, counts, verification and future live boundary.

The following sections preserve the original 26 September UI design and demo-stage record for the paper. Their standalone launch instructions and future-integration wording describe that earlier stage.

## Original purpose and scope

Implemented on 26 September 2026 in `apps/parking_web/` with Flutter 3.44.6 / Dart 3.12.2. This is a new driver-facing, responsive website, designed independently of the Python prototype's popup. It is a home-page preview with deterministic **demo data**, not a live occupancy system. Opening it does not start video analysis, load detection models, or read the PKLot dataset.

The design combines warm white surfaces, navy text, blue actions and occupancy arcs, and mint/green availability indicators. Locally bundled Manrope typography, rounded cards, subtle shadows, and decorative parking illustrations provide a consistent visual style. The illustrations are schematic decorations, not site maps or representations of individual bays. The Google Fonts Manrope source is distributed under the SIL Open Font License in `assets/fonts/OFL.txt`.

## Data and behavior

| Area | Total spaces | Occupied | Available |
| --- | ---: | ---: | ---: |
| CHAD | 9 | 7 | 2 |
| Overhead | 69 | 45 | 24 |
| **Combined demo** | **78** | **52** | **26** |

The circular chart, headline availability count, legend, and area cards derive from the same snapshot. The chart displays **52 / 78 occupied**, approximately **67% full**. Area cards display **2 spaces left | 7/9 occupied** and **24 spaces left | 45/69 occupied**. These are chosen example values, not measured results or synchronized camera observations.

The **Demo data** button explains the preview. **View parking areas** scrolls to the area section and transfers keyboard focus to its heading. There are no placeholder links, automatic count changes, or simulated live indicators. Empty and fully occupied examples render correctly; zero capacity uses a neutral ring and explicit configuration text.

## Layout, animation, and accessibility

- The main content is centered with a maximum outer width of 1,176 logical pixels. Cards sit side by side when the available content width is at least 680 pixels and stack on smaller screens or at large text sizes. The main overview changes to a vertical layout below 680 pixels of card width, placing the circular chart first on phones.
- The circular arc and numeric counters share a 650 ms entrance animation. Cards enter with a short stagger and respond subtly to pointer hover. The scroll action takes 450 ms.
- The operating system/browser reduced-motion preference is respected through Flutter's accessibility settings: entrance, hover, and scroll animation are disabled.
- The chart has a screen-reader summary; area labels express counts without relying on color. Buttons support keyboard focus and activation, and interactive targets are at least 48 logical pixels. The interface adapts to enlarged text.

## Run and build

From a PowerShell terminal in the project root:

```powershell
cd apps/parking_web
flutter pub get
flutter run -d web-server --web-hostname 127.0.0.1 --web-port 8765
```

Then open `http://127.0.0.1:8765` in a browser. Alternatively run `apps/parking_web/run-web.ps1`. If another preview already uses that port, stop that preview or pass another port to the script. The Python application's `main.py` continues to launch its existing popup; it does not launch this website.

```powershell
flutter analyze
flutter test
flutter build web --no-web-resources-cdn
```

The production website is in `apps/parking_web/build/web/`. Serve that directory over HTTP rather than opening `index.html` directly. The build bundles Flutter's web engine locally; Manrope is also a local asset. The Flutter SDK and package versions are recorded in the project metadata and lockfile. No production runtime dependency beyond Flutter was added.

## Implementation structure and future integration

- `lib/data/parking_snapshot.dart`: typed demo areas and aggregate calculations.
- `lib/home_page.dart`: responsive home page, navigation within the page, demo explanation, and entrance motion.
- `lib/widgets/occupancy_ring.dart` and `area_card.dart`: reusable visualization components and decorative illustrations.
- `lib/theme.dart`: shared colors, typeface, and button styling; `lib/main.dart`: application entry point.

Replace the demo snapshot with an explicit data service in a later integration. A live data model must account for unknown/stale frames, provisional occupancy, timestamps, and physical bay identity before combining camera results. The demo's `available = capacity - occupied` assumes every sample bay has a complete known state and must not be applied blindly to unresolved live bays. This first version makes no changes to Reference, MOG2, MobileNet, YOLOv8, Python dependencies, or existing replay results.

## Verification

The implementation includes 14 model/widget checks: derived totals, empty/full/zero capacity, chart/card agreement, layouts at 1,440 / 768 / 390 / 320 logical pixels, area scrolling and focus, keyboard dialog operation, reduced motion, 200% text at phone width, chart semantics, text contrast, and labelled 48-pixel tap targets. All 14 passed. Initial testing found an invalid textual progress-bar semantics value under Flutter 3.44; it was corrected to a numeric value before delivery.

Final validation: `flutter analyze --no-pub` reported no issues, all 14 tests passed, and `flutter build web --no-web-resources-cdn` succeeded. The build emitted an optional Cupertino font warning; the app uses Material icons, and its visible icons rendered correctly in the browser review.

Inspected the running production build at desktop (1,440 pixels), tablet (768 pixels), and phone (390 pixels) widths. Confirmed the keyboard-operated demo dialog, its Escape dismissal, the phone scroll action and destination focus, and the screen-reader counts in the browser accessibility tree. No browser warning/error logs were reported. Reduced motion and 200% text were checked in widget tests. Saved [desktop preview](runs/verification/flutter-ui/desktop.png) and [phone area cards](runs/verification/flutter-ui/phone-areas.png).
