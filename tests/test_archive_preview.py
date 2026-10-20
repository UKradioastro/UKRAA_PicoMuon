from datetime import date
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from PreviewArchiveMigration import preview
from picomuon_common import LEGACY_RAW_HEADER, RAW_HEADER

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "PreviewArchiveMigration.py"
TODAY = date(2026, 10, 20)


def event(time="00:00:01", *, day="2026-10-13", name="56/148/627", settings=""):
    return f"{day} {time},C,1,200,-2147288954,0,22,1015,{name}{settings}\n"


class ArchivePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / "production"
        self.destination = Path(self.temp.name) / "pilot"
        self.raw = self.base / "data" / "raw"
        self.raw.mkdir(parents=True)

    def write(self, relative, content):
        path = self.raw / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def day(self, content, *, legacy=False, day="2026-10-13"):
        return self.write(
            f"{'ACM0/' if legacy else ''}{day[:4]}/{day[:7]}/{day}.txt", content,
        )

    def report(self):
        return preview(self.base, self.destination, today=TODAY)

    def snapshot(self):
        return {
            str(path.relative_to(self.temp.name)): (
                hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns,
            ) if path.is_file() else None
            for path in Path(self.temp.name).rglob("*")
        }

    def test_explicit_mapping_split_day_order_and_no_writes(self):
        # Directory traversal order is deliberately opposite to timestamp order.
        current = self.day(RAW_HEADER + "\n" + event("10:38:10.456836", settings=",1,2,3,4"))
        legacy = self.day(LEGACY_RAW_HEADER + "\n" + event("10:38:16.454421"), legacy=True)
        self.day(event(day="2026-10-10"), legacy=True, day="2026-10-10")
        before = self.snapshot()
        report = self.report()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.destination.exists())
        self.assertEqual(report["mapping"]["detector_label"], "Unit_1")
        self.assertEqual(report["mapping"]["id_serial_short"], "E660D4A0A7598522")
        self.assertFalse(report["has_conflicts"])
        self.assertEqual(report["summary"]["valid_completed_files"], 3)
        plan = report["plans"][1]
        self.assertEqual(plan["action"], "concatenate_in_timestamp_order")
        self.assertEqual(plan["sources_in_order"], [str(current), str(legacy)])
        self.assertEqual(plan["event_count"], 2)
        self.assertEqual(Path(plan["destination"]), self.destination / "data" / "raw" / "Unit_1"
                         / "2026" / "2026-10" / "2026-10-13.txt")
        self.assertEqual(sum(item["legacy_rows"] for item in report["files"]), 2)
        self.assertEqual(sum(item["settings_rows"] for item in report["files"]), 1)

    def test_all_completed_files_and_interior_order_are_validated(self):
        self.day(event("00:00:01") + event("00:00:03") + event("00:00:02") + event("00:00:04"))
        self.day(event(day="2026-10-14"), day="2026-10-14")
        report = self.report()
        self.assertEqual(len(report["files"]), 2)
        invalid = next(item for item in report["files"] if item["day"] == "2026-10-13")
        self.assertEqual(invalid["issue_counts"]["timestamp_order"], 1)
        self.assertEqual(invalid["issue_samples"][0]["line"], 3)
        self.assertEqual(report["summary"]["valid_completed_files"], 1)
        self.assertEqual(report["plans"][0]["action"], "blocked")

    def test_overlap_duplicate_boundary_and_enclosing_segments_block(self):
        for times in (("00:00:02", "00:00:04"), ("00:00:03", "00:00:05"),
                      ("00:00:01", "00:00:03")):
            with self.subTest(times=times):
                self.day(event("00:00:01") + event("00:00:03"), legacy=True)
                self.day(event(times[0]) + event(times[1]))
                plan = self.report()["plans"][0]
                self.assertEqual(plan["action"], "blocked")
                self.assertTrue(any("Overlapping" in text for text in plan["conflicts"]))

    def test_rejected_files_remain_separate_even_if_event_shaped(self):
        self.day(event())
        self.write("rejected/2026-10-13.txt", "bad serial data\n" + event())
        self.write("ACM0/rejected/2026-10-13.txt", "different diagnostics\n")
        report = self.report()
        self.assertEqual(report["summary"]["event_files"], 1)
        self.assertEqual(report["plans"][0]["event_count"], 1)
        diagnostics = report["rejected_diagnostics"]
        self.assertEqual(len(diagnostics), 2)
        self.assertEqual(len({item["destination"] for item in diagnostics}), 2)
        self.assertTrue(all(item["action"] == "keep_separate" for item in diagnostics))
        self.assertTrue(all(item["event_count"] == 0 for item in diagnostics))
        self.assertFalse(report["has_conflicts"])

    def test_today_active_file_is_always_provisional_and_future_is_flagged(self):
        self.day(event(day="2026-10-20") + "unfinished", day="2026-10-20")
        self.day(event(day="2026-10-21"), day="2026-10-21")
        report = self.report()
        self.assertEqual(report["summary"]["completed_files"], 0)
        self.assertTrue(all(plan["action"] == "defer_provisional" for plan in report["plans"]))
        self.assertTrue(all(item["validation"] == "provisional" for item in report["files"]))
        future = next(item for item in report["files"] if item["day"] == "2026-10-21")
        self.assertIn("future_day", future["issue_counts"])

    def test_well_formed_today_file_is_provisional_without_conflicts(self):
        self.day(event(day="2026-10-20"), day="2026-10-20")
        report = self.report()
        self.assertFalse(report["has_conflicts"])
        self.assertEqual(report["plans"][0]["action"], "defer_provisional")
        self.assertEqual(report["summary"]["valid_completed_files"], 0)

    def test_error_samples_are_bounded_but_every_record_is_checked(self):
        self.day("bad\n" * 35 + event() + event())
        entry = self.report()["files"][0]
        self.assertEqual(entry["lines"], 37)
        self.assertEqual(entry["issue_counts"]["invalid_record"], 35)
        self.assertEqual(entry["issue_counts"]["timestamp_order"], 1)
        self.assertEqual(entry["event_count"], 2)
        self.assertEqual(len(entry["issue_samples"]), 20)

    def test_preview_never_opens_write_handles_or_creates_directories(self):
        self.day(event())
        self.write("rejected/2026-10-13.txt", "diagnostics\n")
        real_open = Path.open

        def read_only(path, mode="r", *args, **kwargs):
            self.assertIn(mode, ("r", "rb"))
            return real_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", read_only), patch.object(
            Path, "mkdir", side_effect=AssertionError("Preview tried to create a directory"),
        ):
            self.assertFalse(self.report()["has_conflicts"])

    def test_record_errors_are_reported_without_discarding_or_repairing(self):
        variants = [
            event(name="Unit-2"), event(day="2026-10-12"), event().replace(",C,", ",X,"),
            event().replace(",200,", ",bad,"), event().replace(",22,", ",nan,"),
            event().replace(",1015,", ",inf,"), event(settings=",1,2"),
            event(settings=",1,2,3,-1"), "not an event\n",
            '2026-10-13 00:00:01,C,1,200,0,0,22,1015,"unterminated\n',
        ]
        for content in variants:
            with self.subTest(content=content):
                source = self.day(content)
                before = source.read_bytes()
                report = self.report()
                self.assertTrue(report["has_conflicts"])
                self.assertEqual(report["plans"][0]["action"], "blocked")
                self.assertEqual(source.read_bytes(), before)

    def test_empty_misplaced_pre_mapping_and_bad_filename_are_not_ignored(self):
        self.day("")
        self.day(event(day="2026-10-09"), day="2026-10-09", legacy=True)
        self.write("ACM0/2026/2026-11/2026-10-14.txt", event(day="2026-10-14"))
        self.write("ACM0/2026/2026-10/bad.txt", event())
        report = self.report()
        self.assertEqual(report["summary"]["event_files"], 4)
        self.assertTrue(report["has_conflicts"])
        codes = {code for item in report["files"] for code in item["issue_counts"]}
        self.assertTrue({"no_events", "outside_mapping", "invalid_layout", "invalid_filename"} <= codes)
        self.assertTrue(report["blockers"])

    def test_destination_conflicts_and_byte_identical_noop(self):
        source = self.day(event())
        target = self.destination / "data" / "raw" / "Unit_1" / source.relative_to(self.raw)
        target.parent.mkdir(parents=True)
        target.write_bytes(source.read_bytes())
        before = self.snapshot()
        self.assertEqual(self.report()["plans"][0]["action"], "already_present")
        self.assertEqual(self.snapshot(), before)
        target.write_text("other data")
        self.assertEqual(self.report()["plans"][0]["action"], "blocked")
        target.write_bytes(source.read_bytes())
        self.day(event("00:00:02"), legacy=True)
        self.assertEqual(self.report()["plans"][0]["action"], "blocked")

    def test_destination_parent_file_and_unmapped_named_archives(self):
        self.day(event())
        self.write("Unit_2/2026/2026-10/2026-10-13.txt", event(name="Unit-2"))
        self.destination.mkdir()
        (self.destination / "data").write_text("not a directory")
        report = self.report()
        self.assertEqual(report["summary"]["event_files"], 1)
        self.assertEqual(report["plans"][0]["action"], "blocked")

    def test_changed_completed_file_and_read_error_are_explicit(self):
        source = self.day(event())
        real_open = Path.open

        @contextmanager
        def changed(path, *args, **kwargs):
            with real_open(path, *args, **kwargs) as handle:
                yield handle
            if path == source:
                with real_open(path, "ab") as writer:
                    writer.write(b"\n")

        with patch.object(Path, "open", changed):
            report = self.report()
        self.assertIn("changed_during_read", report["files"][0]["issue_counts"])

        def denied(path, *args, **kwargs):
            if path == source:
                raise PermissionError("test denied")
            return real_open(path, *args, **kwargs)

        with patch.object(Path, "open", denied):
            report = self.report()
        self.assertIn("read_error", report["files"][0]["issue_counts"])

    def test_cli_json_exit_codes_and_no_apply_option(self):
        self.day(event())
        command = [sys.executable, "-B", str(SCRIPT), "--source-base", str(self.base),
                   "--destination-base", str(self.destination)]
        before = self.snapshot()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["read_only"])
        self.assertEqual(self.snapshot(), before)
        self.day("bad\n")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(json.loads(result.stdout)["has_conflicts"])
        result = subprocess.run(command + ["--apply"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments", result.stderr)

    def test_no_sources_and_missing_source_fail_explicitly(self):
        self.assertTrue(self.report()["has_conflicts"])
        with self.assertRaisesRegex(ValueError, "Source raw directory"):
            preview(self.base / "missing", self.destination, today=TODAY)

    def test_symbolic_link_sources_and_destinations_are_blocked(self):
        source = self.day(event())
        link = self.raw / "ACM0" / "2026"
        link.parent.mkdir()
        try:
            link.symlink_to(source.parent.parent, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symbolic links unavailable: {error}")
        report = self.report()
        self.assertTrue(report["has_conflicts"])
        self.assertTrue(any("symbolic_link" in item["issue_counts"] for item in report["files"]))
        self.destination.symlink_to(self.base, target_is_directory=True)
        self.assertTrue(self.report()["has_conflicts"])


if __name__ == "__main__":
    unittest.main()
