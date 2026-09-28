# Parking home page

A responsive Flutter web preview for drivers. The chart and area cards share deterministic demo data: 52 of 78 spaces occupied, with 2 available at CHAD and 24 at Overhead. Live detection is not connected.

Run `flutter run -d web-server --web-hostname 127.0.0.1 --web-port 8765`, then open the displayed URL. On Windows, `./run-web.ps1` runs the same command.

Use `flutter analyze`, `flutter test`, and `flutter build web --no-web-resources-cdn` for verification and production output. See [FLUTTER_UI.md](../../FLUTTER_UI.md) for design choices, demo values, architecture, accessibility, and integration limitations.
