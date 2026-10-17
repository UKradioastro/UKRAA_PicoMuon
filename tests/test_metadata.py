import csv
from datetime import date, datetime, timedelta, timezone
import io
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from AddRawHeaders import add_header
from GetDataRaw import parse_and_validate_line
import GetDataRaw
import GetDataRawACM0
from ConfigureUSB import probe_detector_sample
from picomuon_common import (
    LEGACY_RAW_HEADER, RAW_HEADER, build_processed_day_path, build_raw_day_path,
    open_raw_file, raw_data_lines,
)
from picomuon_metadata import (
    METADATA_PREFIX, RawEventWriter, data_lines, load_legacy_settings,
    metadata_from_product, metadata_from_raw, read_metadata,
    load_observation, write_metadata,
)
from ProcessDaily import process_daily
from ProcessPeriod import process_period_data

PAYLOAD = "C,1,200,1000,0,22.0,1015.0,Detector"


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.config = self.base / "config"
        self.config.mkdir()
        self.set_legacy()
        (self.config / "user.ini").write_text(
            "[Observatory]\nstation_id = Test-01\nobservatory_latitude = 51.5\n"
            "[Observer]\nobserver_name = Test Observer\nobserver_email = private@example.org\n",
            encoding="utf-8",
        )
        self.day = date(2026, 10, 9)
        self.raw = build_raw_day_path(self.base, datetime(2026, 10, 9, tzinfo=timezone.utc))

    def set_legacy(self, top=200):
        (self.config / "legacy.ini").write_text(
            f"[legacy]\nthreshold_top = {top}\nreset_top = 100\n"
            "threshold_bottom = 201\nreset_bottom = 101\n", encoding="utf-8",
        )

    def capture(self, payloads):
        writer = RawEventWriter(self.base)
        with open_raw_file(self.raw) as handle:
            for i, payload in enumerate(payloads):
                writer.write(handle, f"2026-10-09 00:00:{i:02d}.000000", payload)

    def process(self):
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(process_daily(self.day, self.base), 0)

    def test_legacy_and_extended_records_have_exactly_thirteen_columns(self):
        self.capture([PAYLOAD, PAYLOAD + ",300,110,301,111", PAYLOAD])
        rows = list(csv.reader(raw_data_lines(self.raw.read_text().splitlines())))
        self.assertEqual([len(row) for row in rows], [13, 13, 13])
        self.assertEqual(rows[0][-4:], ["200", "100", "201", "101"])
        self.assertEqual(rows[1][-4:], ["300", "110", "301", "111"])
        self.assertEqual(rows[2][-4:], rows[0][-4:])
        history = metadata_from_raw(self.raw)["segments"]
        self.assertEqual([s["settings_source"] for s in history], ["legacy.ini", "detector", "legacy.ini"])
        self.assertNotIn("private@example.org", self.raw.read_text())

    def test_extended_firmware_needs_no_legacy_file(self):
        (self.config / "legacy.ini").unlink()
        self.capture([PAYLOAD + ",300,110,301,111"])
        self.assertEqual(metadata_from_raw(self.raw)["segments"][0]["settings_source"], "detector")

    def test_missing_or_invalid_legacy_is_not_silently_defaulted(self):
        (self.config / "legacy.ini").unlink()
        with self.assertRaises(FileNotFoundError):
            self.capture([PAYLOAD])
        for content in (
            "[legacy]\nthreshold_top = 1\n",
            "[legacy]\nthreshold_top = -1\nreset_top = 0\nthreshold_bottom = 1\nreset_bottom = 0\n",
            "[legacy]\nthreshold_top = bad\nreset_top = 0\nthreshold_bottom = 1\nreset_bottom = 0\n",
        ):
            (self.config / "legacy.ini").write_text(content)
            with self.assertRaises(ValueError):
                load_legacy_settings(self.base)

    def test_partial_and_invalid_extended_payloads_are_rejected(self):
        for suffix in (",200", ",200,100", ",200,100,201", ",200,100,201,",
                       ",200,bad,201,101", ",-1,100,201,101"):
            with self.subTest(suffix=suffix):
                self.assertIsNone(parse_and_validate_line(PAYLOAD + suffix))
        self.assertIsNotNone(parse_and_validate_line(PAYLOAD + ",300,110,301,111"))

    def test_invalid_coordinates_are_reported_not_published(self):
        for key, value in (("observatory_latitude", "91"), ("observatory_longitude", "-181"),
                           ("observatory_altitude", "nan"), ("observatory_latitude", "bad")):
            with self.subTest(key=key, value=value):
                (self.config / "user.ini").write_text(f"[Observatory]\n{key} = {value}\n")
                with self.assertRaisesRegex(ValueError, key):
                    load_observation(self.base)

    def test_modern_collector_records_both_formats_and_archives_invalid_rows(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.readline.side_effect = [
            b"discarded partial startup line\n",
            (PAYLOAD + "\n").encode(),
            (PAYLOAD + ",300,110,301,111\n").encode(),
            (PAYLOAD + ",300,110\n").encode(),
            KeyboardInterrupt,
        ]
        now = datetime(2026, 10, 9, tzinfo=timezone.utc)
        with patch.object(GetDataRaw, "get_base_path", return_value=self.base), \
                patch.object(GetDataRaw.serial, "Serial", return_value=connection), \
                patch.object(GetDataRaw, "utc_now", return_value=now), \
                patch("sys.stdout", new_callable=io.StringIO), \
                patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(KeyboardInterrupt):
                GetDataRaw.main()
        rows = list(csv.reader(raw_data_lines(self.raw.read_text().splitlines())))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][-4:], ["200", "100", "201", "101"])
        self.assertEqual(rows[1][-4:], ["300", "110", "301", "111"])
        rejected = self.base / "data" / "raw" / "rejected" / "2026-10-09.txt"
        self.assertIn(PAYLOAD + ",300,110", rejected.read_text())

    def test_legacy_collector_records_both_formats(self):
        now = datetime(2026, 10, 9, tzinfo=timezone.utc)
        with patch.object(GetDataRawACM0, "get_base_path", return_value=self.base), \
                patch.object(GetDataRawACM0.serial, "Serial", return_value=[
                    (PAYLOAD + "\n").encode(), (PAYLOAD + ",300,110,301,111\n").encode(),
                ]), patch.object(GetDataRawACM0, "datetime") as clock:
            clock.now.return_value = now
            GetDataRawACM0.main()
        path = build_raw_day_path(self.base, now, "ACM0")
        rows = list(csv.reader(raw_data_lines(path.read_text().splitlines())))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(len(row) == 13 for row in rows))

    def test_usb_probe_does_not_include_settings_in_detector_name(self):
        for payload in (PAYLOAD, PAYLOAD + ",300,110,301,111"):
            with self.subTest(payload=payload):
                connection = MagicMock()
                connection.__enter__.return_value = connection
                connection.readline.side_effect = [b"startup\n", (payload + "\n").encode()]
                with patch("ConfigureUSB.serial.Serial", return_value=connection):
                    self.assertEqual(probe_detector_sample("test-port"), "Detector")

    def test_comma_in_detector_name_round_trips_as_csv(self):
        for name in ("MyDetector,Unit1", '"MyDetector,Unit1"'):
            with self.subTest(name=name):
                payload = PAYLOAD.rsplit(",", 1)[0] + "," + name + ",300,110,301,111"
                self.assertEqual(parse_and_validate_line(payload)[8], "MyDetector,Unit1")
                self.capture([payload])
        self.assertEqual(metadata_from_raw(self.raw)["segments"][0]["detector_name"], "MyDetector,Unit1")
        self.process()
        with (self.base / "data" / "daily" / "summary.csv").open() as source:
            rows = list(csv.DictReader(data_lines(source)))
        self.assertEqual(rows[0]["DetectorName"], "MyDetector,Unit1")

    def test_capture_snapshot_survives_later_config_edits_in_every_product(self):
        self.capture([PAYLOAD, PAYLOAD + ",300,110,301,111"])
        self.set_legacy(999)
        (self.config / "user.ini").write_text("[Observer]\nobserver_name = Later observer\n")
        self.process()
        for category in ("cpm", "day", "adc"):
            product = build_processed_day_path(self.base, category, self.day)
            metadata = metadata_from_product(product)
            segments = metadata["segments"]
            self.assertEqual(len(segments), 2)
            self.assertEqual(segments[0]["settings"]["threshold_top"], 200)
            self.assertEqual(segments[1]["settings"]["threshold_top"], 300)
            self.assertEqual(segments[0]["observation"]["Observer"]["observer_name"], "Test Observer")
            self.assertNotIn("private@example.org", product.read_text())
        hour = self.base / "data" / "hour" / "2026" / "2026-10" / "2026-10-09.csv"
        self.assertEqual(metadata_from_product(hour)["segments"], segments)
        summary = self.base / "data" / "daily" / "summary.csv"
        snapshots = [read_metadata(line) for line in summary.read_text().splitlines()
                     if line.startswith(METADATA_PREFIX)]
        self.assertEqual(snapshots[0]["segments"], segments)

    def test_config_changes_and_midnight_are_captured(self):
        writer = RawEventWriter(self.base)
        with open_raw_file(self.raw) as handle:
            writer.write(handle, "2026-10-09 00:00:00.000000", PAYLOAD)
            self.set_legacy(250)
            writer.write(handle, "2026-10-09 00:00:01.000000", PAYLOAD)
            writer.write(handle, "2026-10-09 00:00:02.000000", PAYLOAD)
        next_raw = self.raw.with_name("2026-10-10.txt")
        with open_raw_file(next_raw) as handle:
            writer.write(handle, "2026-10-10 00:00:00.000000", PAYLOAD)
        segments = metadata_from_raw(self.raw)["segments"]
        self.assertEqual([s["event_count"] for s in segments], [1, 2])
        self.assertEqual(metadata_from_raw(next_raw)["segments"][0]["settings"]["threshold_top"], 250)

    def test_history_without_metadata_is_unknown_not_today_configuration(self):
        self.raw.parent.mkdir(parents=True)
        original = "2026-10-09 00:00:00.000000," + PAYLOAD + "\n"
        self.raw.write_text(LEGACY_RAW_HEADER + "\n" + original)
        self.process()
        segments = metadata_from_product(build_processed_day_path(self.base, "day", self.day))["segments"]
        self.assertIsNone(segments[0]["settings"])
        self.assertEqual(segments[0]["settings_source"], "unknown")
        self.assertEqual(segments[0]["observation"], {})
        self.capture([PAYLOAD])
        self.assertIn(original, self.raw.read_text())
        self.assertIn(RAW_HEADER, self.raw.read_text())
        self.process()
        rows = list(csv.DictReader(data_lines(
            build_processed_day_path(self.base, "cpm", self.day).read_text().splitlines())))
        self.assertEqual(rows[0]["Count_C"], "2")

    def test_reprocessing_preserves_other_days_summary_metadata(self):
        self.capture([PAYLOAD])
        self.process()
        second = self.day + timedelta(days=1)
        raw = build_raw_day_path(self.base, datetime(2026, 10, 10, tzinfo=timezone.utc))
        with open_raw_file(raw) as handle:
            RawEventWriter(self.base).write(handle, "2026-10-10 00:00:00.000000", PAYLOAD + ",400,100,400,100")
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(process_daily(second, self.base), 0)
        summary = self.base / "data" / "daily" / "summary.csv"
        before = summary.read_bytes()
        self.process()
        self.assertEqual(summary.read_bytes(), before)
        self.assertEqual(len(list(csv.DictReader(data_lines(summary.read_text().splitlines())))), 2)

    def test_period_preserves_daily_metadata_and_counts(self):
        self.capture([PAYLOAD])
        self.process()
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(process_period_data("week", self.day, self.base, min_percent=0), 0)
        product = build_processed_day_path(self.base, "week", self.day)
        meta = metadata_from_product(product)
        self.assertEqual(meta["daily_metadata"][0]["date"], "2026-10-09")
        self.assertEqual(meta["daily_metadata"][0]["metadata"]["segments"][0]["settings_source"], "legacy.ini")
        rows = list(csv.DictReader(data_lines(product.read_text().splitlines())))
        self.assertEqual(len(rows), 1008)
        self.assertEqual(rows[-144]["CPM_C"], "1")

    def test_old_and_extended_input_produce_identical_numeric_products(self):
        self.raw.parent.mkdir(parents=True)
        rows = [
            f"2026-10-09 00:00:0{i}.000000,{event},{i},200,{i * 1000},0,22.0,1015.0,Detector"
            for i, event in enumerate(("T", "B", "C"), 1)
        ]
        self.raw.write_text(LEGACY_RAW_HEADER + "\n" + "\n".join(rows) + "\n")
        self.process()
        before = {
            path: list(data_lines(path.read_text().splitlines()))
            for path in (self.base / "data").rglob("*")
            if path.is_file() and path != self.raw
        }
        self.raw.write_text(
            RAW_HEADER + "\n" + "\n".join(row + ",200,100,201,101" for row in rows) + "\n"
        )
        self.process()
        for path, numeric_rows in before.items():
            self.assertEqual(list(data_lines(path.read_text().splitlines())), numeric_rows, str(path))

    def test_legacy_period_scripts_accept_comments_and_preserve_metadata(self):
        yesterday = (datetime.now() - timedelta(days=1)).date()
        for offset in range(31):
            day = yesterday - timedelta(days=offset)
            path = build_processed_day_path(self.base, "day", day)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                write_metadata(handle, {"schema_version": 1, "time_basis": "UTC", "segments": [],
                                        "station_id": "Test-01"})
                handle.write("DateTime,CPM_T,CPM_B,CPM_C,Mean_Temp,Mean_Pres,Neutrons\n")
                handle.write(f"{day.isoformat()} 00:00:00,1,1,1,22.0,1015.0,500\n")
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        with patch.dict(os.environ, {"PICOMUON_BASE_PATH": str(self.base)}), \
                patch("sys.stdout", new_callable=io.StringIO):
            for category, days in (("week", 7), ("month", 31)):
                runpy.run_path(str(scripts / f"ProcessData{category.title()}ACM0.py"), run_name="__main__")
                path = build_processed_day_path(self.base, category, yesterday)
                meta = metadata_from_product(path)
                self.assertEqual(len(meta["daily_metadata"]), days)
                self.assertEqual(meta["daily_metadata"][0]["metadata"]["station_id"], "Test-01")

    def test_migration_uses_extended_header_for_headerless_extended_rows(self):
        self.raw.parent.mkdir(parents=True)
        original = ("2026-10-09 00:00:00.000000," + PAYLOAD + ",200,100,201,101\n").encode()
        self.raw.write_bytes(original)
        self.assertTrue(add_header(self.raw))
        self.assertEqual(self.raw.read_bytes(), (RAW_HEADER + "\n").encode() + original)
        self.assertFalse(add_header(self.raw))


if __name__ == "__main__":
    unittest.main()
