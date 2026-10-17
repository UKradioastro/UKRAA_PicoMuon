import csv
from datetime import datetime, timedelta, timezone
import io
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from AddRawHeaders import add_header, main as migrate_main
from GetDataRaw import open_daily_file
from picomuon_common import LEGACY_RAW_HEADER, RAW_HEADER, raw_data_lines
from picomuon_metadata import data_lines
from ProcessDaily import process_daily


EVENT = b"2026-10-09 00:00:01.000000,C,1,200,1000,0,22.0,1015.0,Detector"
HEADER = (LEGACY_RAW_HEADER + "\n").encode("ascii")


class RawHeaderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.now = datetime(2026, 10, 9, tzinfo=timezone.utc)
        self.raw = self.base / "data" / "raw" / "2026" / "2026-10" / "2026-10-09.txt"
        self.raw.parent.mkdir(parents=True)

    def test_collector_new_empty_reopened_and_labelled_files(self):
        for label in (None, "ACM0", "East-01"):
            with self.subTest(label=label):
                handle, path = open_daily_file(self.base, self.now, label)
                with handle:
                    handle.write(EVENT.decode("ascii") + "\n")
                handle, same_path = open_daily_file(self.base, self.now, label)
                with handle:
                    handle.write(EVENT.decode("ascii") + "\n")
                self.assertEqual(same_path, path)
                self.assertEqual(
                    path.read_text(),
                    RAW_HEADER + "\n" + (EVENT.decode("ascii") + "\n") * 2,
                )

        self.raw.write_bytes(b"")
        handle, _ = open_daily_file(self.base, self.now, None)
        handle.close()
        self.assertEqual(self.raw.read_text(), RAW_HEADER + "\n")

    def test_collector_does_not_insert_header_into_existing_events(self):
        self.raw.write_bytes(EVENT + b"\n")
        handle, _ = open_daily_file(self.base, self.now, None)
        handle.close()
        self.assertEqual(self.raw.read_bytes(), EVENT + b"\n")

    def test_collector_utc_rollover_creates_new_header(self):
        for day in (self.now, self.now + timedelta(days=1)):
            handle, path = open_daily_file(self.base, day, None)
            handle.close()
            self.assertEqual(path.read_text(), RAW_HEADER + "\n")

    def test_migration_preserves_event_bytes_backup_and_timestamp(self):
        for events in (b"", EVENT, EVENT + b"\r\n" + EVENT + b"\r\n"):
            with self.subTest(events=events):
                self.raw.write_bytes(events)
                backup = self.raw.with_name(self.raw.name + ".pre-header.bak")
                if backup.exists():
                    backup.unlink()
                old_mtime = self.raw.stat().st_mtime_ns
                self.assertTrue(add_header(self.raw))
                self.assertEqual(self.raw.read_bytes(), HEADER + events)
                self.assertEqual(backup.read_bytes(), events)
                self.assertEqual(self.raw.stat().st_mtime_ns, old_mtime)
                self.assertFalse(add_header(self.raw))
                self.assertEqual(self.raw.read_bytes().count(HEADER), 1)

    def test_existing_crlf_header_is_not_duplicated(self):
        original = RAW_HEADER.encode() + b"\r\n" + EVENT + b"\r\n"
        self.raw.write_bytes(original)
        self.assertFalse(add_header(self.raw))
        self.assertEqual(self.raw.read_bytes(), original)

    def test_backup_collision_leaves_original_unchanged(self):
        self.raw.write_bytes(EVENT)
        backup = self.raw.with_name(self.raw.name + ".pre-header.bak")
        backup.write_bytes(b"existing backup")
        with self.assertRaises(FileExistsError):
            add_header(self.raw)
        self.assertEqual(self.raw.read_bytes(), EVENT)
        self.assertEqual(backup.read_bytes(), b"existing backup")

    def test_replacement_failure_keeps_original_and_cleans_temporary(self):
        self.raw.write_bytes(EVENT)
        with patch.object(Path, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                add_header(self.raw)
        self.assertEqual(self.raw.read_bytes(), EVENT)
        self.assertEqual(
            {p.name for p in self.raw.parent.iterdir()},
            {self.raw.name, self.raw.name + ".pre-header.bak"},
        )

    def test_legacy_csv_reader_keeps_first_event_with_and_without_header(self):
        fields = ["timestamp", "event", "count", "adc", "elapsed", "dead", "temp", "pres", "name"]
        for prefix in ("", RAW_HEADER + "\n"):
            rows = list(csv.DictReader(raw_data_lines(io.StringIO(
                prefix + EVENT.decode() + "\n"
            )), fields))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["adc"], "200")
            self.assertEqual(rows[0]["event"], "C")

    def test_legacy_adc_and_cpm_scripts_accept_headered_raw(self):
        yesterday = datetime.now() - timedelta(days=1)
        raw = (self.base / "data" / "raw" / "ACM0" / yesterday.strftime("%Y")
               / yesterday.strftime("%Y-%m") / (yesterday.strftime("%Y-%m-%d") + ".txt"))
        raw.parent.mkdir(parents=True)
        raw.write_text(RAW_HEADER + "\n" + yesterday.strftime("%Y-%m-%d")
                       + " 00:00:01.000000,C,1,200,1000,0,22.0,1015.0,Detector\n")
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        with patch.dict(os.environ, {"PICOMUON_BASE_PATH": str(self.base)}), \
                patch("sys.stdout", new_callable=io.StringIO):
            for name in ("ProcessDataAdcACM0.py", "ProcessDataCpmACM0.py"):
                runpy.run_path(str(scripts / name), run_name="__main__")
        for category, index in (("adc", 201), ("cpm", 1)):
            output = (self.base / "data" / category / "ACM0" / yesterday.strftime("%Y")
                      / yesterday.strftime("%Y-%m") / raw.name)
            self.assertEqual(list(data_lines(output.read_text().splitlines()))[index].split(",")[-1], "1")

    def test_daily_outputs_identical_before_and_after_raw_migration(self):
        self.raw.write_bytes(EVENT + b"\n")
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(process_daily(self.now.date(), self.base), 0)
            outputs = {
                p: p.read_bytes() for p in (self.base / "data").rglob("*")
                if p.is_file() and p != self.raw
            }
            add_header(self.raw)
            self.assertEqual(process_daily(self.now.date(), self.base), 0)
        for path, content in outputs.items():
            self.assertEqual(path.read_bytes(), content, str(path))

    def test_cli_preview_apply_and_rejected_exclusion(self):
        self.raw.write_bytes(EVENT)
        legacy = self.base / "data" / "raw" / "ACM0" / "2025" / "old.txt"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(EVENT)
        rejected = self.base / "data" / "raw" / "rejected" / "2026-10-09.txt"
        rejected.parent.mkdir()
        rejected.write_bytes(b"malformed serial input\n")
        with patch.dict(os.environ, {"PICOMUON_BASE_PATH": str(self.base)}):
            with patch("sys.argv", ["AddRawHeaders.py"]), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(migrate_main(), 0)
            self.assertEqual(self.raw.read_bytes(), EVENT)
            with patch("sys.argv", ["AddRawHeaders.py", "--apply"]), patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as error:
                    migrate_main()
                self.assertEqual(error.exception.code, 2)
            with patch("sys.argv", ["AddRawHeaders.py", "--apply", "--collectors-stopped"]), \
                    patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(migrate_main(), 0)
                self.assertEqual(migrate_main(), 0)
        self.assertEqual(self.raw.read_bytes(), HEADER + EVENT)
        self.assertEqual(legacy.read_bytes(), HEADER + EVENT)
        self.assertEqual(rejected.read_bytes(), b"malformed serial input\n")


if __name__ == "__main__":
    unittest.main()
