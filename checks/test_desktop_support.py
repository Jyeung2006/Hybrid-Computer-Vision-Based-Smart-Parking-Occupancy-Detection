"""Checks that can run without loading the Windows-blocked OpenCV binary.

GUI observations below are explicit test fixtures, never parking measurements.
"""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import tkinter as tk
import unittest
from unittest.mock import Mock, patch
import zipfile
import zlib

import requests

from parking_probe import catalog
from parking_probe.display_model import occupancy_text, replay_delay, runtime_error, sample_indices, video_clock


class DisplayTests(unittest.TestCase):
    def test_source_frame_grid_has_no_accumulated_rounding_drift(self):
        self.assertEqual([x[1] for x in sample_indices(900, 30000 / 1001, 3)],
                         [0, 90, 180, 270, 360, 450, 539, 629, 719, 809, 899])

    def test_invalid_timing(self):
        for args in ((0, 30, 3), (10, 0, 3), (10, float("nan"), 3), (10, 30, 0), (10, 1, .1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                list(sample_indices(*args))

    def test_normal_scheduler_subtracts_processing_time(self):
        self.assertAlmostEqual(replay_delay(100, 1, 3, 100.4, 100), 2.6)

    def test_slow_processing_skips_deadlines_without_bursts(self):
        self.assertIsNone(replay_delay(100, 1, 3, 107, 100))
        self.assertIsNone(replay_delay(100, 2, 3, 107, 106.5))
        self.assertEqual(replay_delay(100, 3, 3, 107, 106.5), 2)

    def test_exact_range_and_unavailable_display(self):
        self.assertEqual(occupancy_text({"occupancy_min_pct": 50, "occupancy_pct": 50}), "50.0%")
        self.assertEqual(occupancy_text({"occupancy_min_pct": 25, "occupancy_max_pct": 75}), "25.0 - 75.0%")
        self.assertEqual(occupancy_text({"occupancy_min_pct": None, "occupancy_pct": None}), "Unavailable")

    def test_timestamp_clock(self):
        self.assertEqual(video_clock(189.9), "03:10")
        self.assertEqual(video_clock(17.9846), "00:18")
        self.assertEqual(video_clock(-1), "00:00")

    def test_dependency_failure_is_not_misreported_as_security_block(self):
        self.assertIn("missing", runtime_error(ModuleNotFoundError("No module named cv2")))
        self.assertIn("Application Control", runtime_error(ImportError("An Application Control policy has blocked this file")))
        self.assertIn("required DLL", runtime_error(ImportError("DLL load failed")))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        content = b"public test MP4 placeholder; not playable video" * 100
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("test.mp4", content)
            info = archive.getinfo("test.mp4")
        self.blob = buffer.getvalue()
        self.content = content
        self.clip = catalog.Clip("test", "test.mp4", len(content), info.compress_size, info.header_offset,
                                 zlib.crc32(content), hashlib.sha256(content).hexdigest())
        self.reader = Mock()
        self.reader.read.side_effect = lambda start, size: self.blob[start:start + size]

    def tearDown(self):
        self.temp.cleanup()

    def test_range_member_is_decompressed_and_verified(self):
        with patch.object(catalog, "ArchiveReader", return_value=self.reader):
            path = catalog.fetch_clip(self.clip, directory=self.directory)
        self.assertEqual(path.read_bytes(), self.content)
        self.assertFalse(path.with_suffix(".mp4.part").exists())
        self.reader.close.assert_called_once()

    def test_verified_cache_needs_no_network(self):
        (self.directory / self.clip.member).write_bytes(self.content)
        with patch.object(catalog, "ArchiveReader") as reader:
            catalog.fetch_clip(self.clip, directory=self.directory)
        reader.assert_not_called()

    def test_corrupted_cache_is_refetched(self):
        (self.directory / self.clip.member).write_bytes(b"x" * len(self.content))
        with patch.object(catalog, "ArchiveReader", return_value=self.reader):
            path = catalog.fetch_clip(self.clip, directory=self.directory)
        self.assertEqual(path.read_bytes(), self.content)

    def test_checksum_failure_removes_partial(self):
        with patch.object(catalog, "ArchiveReader", return_value=self.reader), self.assertRaises(catalog.DownloadError):
            catalog.fetch_clip(replace(self.clip, sha256="0" * 64), directory=self.directory)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_cancel_does_not_publish_partial_file(self):
        with patch.object(catalog, "ArchiveReader", return_value=self.reader), self.assertRaises(catalog.DownloadError):
            catalog.fetch_clip(self.clip, cancelled=lambda: True, directory=self.directory)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_expansion_limit(self):
        with patch.object(catalog, "ArchiveReader", return_value=self.reader), self.assertRaises(catalog.DownloadError):
            catalog.fetch_clip(replace(self.clip, size=5), directory=self.directory)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_changed_archive_member_is_rejected(self):
        with patch.object(catalog, "ArchiveReader", return_value=self.reader), self.assertRaises(catalog.DownloadError):
            catalog.fetch_clip(replace(self.clip, member="other.mp4"), directory=self.directory)

    def response(self, status, content_range, chunks):
        response = Mock(status_code=status, headers={"Content-Range": content_range})
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = iter(chunks)
        reader = catalog.ArchiveReader()
        reader.session = Mock()
        reader.url = "https://public.example.invalid/archive"
        reader.session.get.return_value = response
        return reader, response

    def test_ignored_range_is_rejected_before_reading_huge_body(self):
        reader, response = self.response(200, "", [b"too big"])
        with self.assertRaises(catalog.DownloadError):
            reader.read(10, 5)
        response.iter_content.assert_not_called()

    def test_correct_range(self):
        reader, _ = self.response(206, f"bytes 10-14/{catalog.ARCHIVE_BYTES}", [b"123", b"45"])
        self.assertEqual(reader.read(10, 5), b"12345")

    def test_short_or_excess_body_rejected(self):
        for body in (b"1", b"123456"):
            reader, _ = self.response(206, f"bytes 10-14/{catalog.ARCHIVE_BYTES}", [body])
            with self.subTest(body=body), self.assertRaises(catalog.DownloadError):
                reader.read(10, 5)

    def test_network_retries_are_bounded(self):
        reader, _ = self.response(206, "", [])
        reader.session.get.side_effect = requests.Timeout()
        with patch.object(catalog.time, "sleep"), self.assertRaises(catalog.DownloadError):
            reader.read(10, 5)
        self.assertEqual(reader.session.get.call_count, 2)

    def test_pinned_catalog(self):
        self.assertEqual(len(catalog.CLIPS), 4)
        self.assertEqual(len({c.member for c in catalog.CLIPS}), 4)
        self.assertTrue(all(c.member.startswith("1_") and len(c.sha256) == 64 for c in catalog.CLIPS))


class RecipeTests(unittest.TestCase):
    def test_labels_are_separate_from_references_and_have_both_states(self):
        recipe = json.loads((catalog.PROJECT_ROOT / "presets/chad-camera-1.json").read_text())
        refs = {tuple(s["reference"]) for s in recipe["slots"]}
        self.assertEqual(len(recipe["slots"]), 3)
        for slot in recipe["slots"]:
            seen = set()
            for state in ("vacant", "occupied"):
                groups = [slot[state], *slot.get("additional_samples", {}).get(state, [])]
                count = 0
                for examples in groups:
                    for second in examples["seconds"]:
                        key = examples["clip"], second
                        self.assertNotIn(key, refs)
                        self.assertNotIn(key, seen)
                        self.assertNotEqual(examples["clip"], "chad-4")
                        seen.add(key)
                        count += 1
                self.assertGreaterEqual(count, 5)
            self.assertTrue(all(0 <= x < 1280 and 0 <= y < 720 for x, y in slot["polygon"]))


class WindowTests(unittest.TestCase):
    def test_fixture_display_updates_and_clears_unavailable_counts(self):
        from parking_probe.desktop import ParkingWindow
        root = tk.Tk()
        root.withdraw()
        try:
            app = ParkingWindow(root, autostart=False)
            now = datetime.now(timezone.utc).isoformat()
            result = {"analysis_status": "estimated", "processed_at": now, "processing_duration_ms": 12,
                      "video_position_seconds": 3, "video_duration_seconds": 30,
                      "summary": {"occupied": 1, "vacant": 1, "unresolved": 1, "total_monitored_bays": 3,
                                  "occupancy_pct": None, "occupancy_min_pct": 100/3, "occupancy_max_pct": 200/3},
                      "slots": [{"slot_id": "TEST", "state": "uncertain", "difference_score": .12}]}
            png = (catalog.PROJECT_ROOT / "assets/previews/chad-1.png").read_bytes()
            app.render(result, png)
            self.assertEqual(app.metrics["occupied"].get(), "1")
            self.assertEqual(app.metrics["occupancy"].get(), "33.3 - 66.7%")
            self.assertEqual(len(app.table.get_children()), 1)
            result["analysis_status"] = "unavailable"
            result["summary"].update(occupancy_min_pct=None, occupancy_max_pct=None)
            app.render(result, None)
            self.assertEqual(app.metrics["occupied"].get(), "—")
            self.assertEqual(app.metrics["occupancy"].get(), "Unavailable")
            self.assertIsNone(app.photo)
            app.selected.set(catalog.CLIPS[1].title)
            app.selection_changed()
            self.assertEqual(len(app.table.get_children()), 0)
            self.assertIsNotNone(app.photo)
            root.update_idletasks()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
