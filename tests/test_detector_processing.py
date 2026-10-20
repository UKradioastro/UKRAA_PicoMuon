import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ProcessDaily import process_daily
from ProcessPeriod import PERIOD_CONFIGS, load_day_file, process_period_data
from picomuon_common import build_daily_summary_path, build_processed_day_path, build_raw_day_path
from picomuon_processing import processing_lock, raw_dates


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class DetectorProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.day = date(2026, 10, 17)
        self.labels = ("East", "West", "Third")
        config = self.base / "config"
        config.mkdir()
        (config / "USB.ini").write_text(
            "[usb]\nlabel = Old\n[detectors]\n"
            + "".join(f"{label} = /dev/serial/by-id/usb-{label}\n" for label in self.labels)
            + "".join(f"[detector:{label}]\nid_serial_short = {label}\n" for label in self.labels)
        )
        (config / "legacy.ini").write_text(
            "[legacy]\nthreshold_top=999\nreset_top=999\nthreshold_bottom=999\nreset_bottom=999\n"
            + "".join(
                f"[legacy:{label}]\nthreshold_top={100 + index}\nreset_top={50 + index}\n"
                f"threshold_bottom={200 + index}\nreset_bottom={60 + index}\n"
                for index, label in enumerate(self.labels)
            )
        )
        self.environment = patch.dict(os.environ, {"PICOMUON_BASE_PATH": str(self.base)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.output = patch("sys.stdout", new_callable=io.StringIO)
        self.output.start()
        self.addCleanup(self.output.stop)

    def raw(self, label, count=2, day=None, settings=""):
        day = day or self.day
        timestamp = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        path = build_raw_day_path(self.base, timestamp, label)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(
            f"{day} 00:00:{index:02d},C,{index + 1},200,{1000 * (index + 1)},0,22,1015,"
            f"{label or 'Unlabelled'}{settings}\n"
            for index in range(count)
        ))
        return path

    def product(self, category, label, day=None, extension="txt"):
        return build_processed_day_path(
            self.base, category, day or self.day, label, extension, named_detector=True,
        )

    def rows(self, path):
        with path.open() as source:
            return list(csv.DictReader(source))

    def test_three_daily_streams_keep_counts_exposure_settings_and_summary_separate(self):
        originals = {}
        for index, label in enumerate(self.labels):
            raw = self.raw(label, index + 2)
            originals[raw] = raw.read_bytes()
        with ThreadPoolExecutor(max_workers=3) as workers:
            results = list(workers.map(lambda label: process_daily(self.day, self.base, label), self.labels))
        self.assertEqual(results, [0, 0, 0])
        for index, label in enumerate(self.labels):
            cpm = self.rows(self.product("cpm", label))
            self.assertEqual(len(cpm), 1440)
            self.assertEqual(sum(int(row["Count_C"]) for row in cpm), index + 2)
            self.assertEqual(cpm[0]["detector_name"], label)
            self.assertEqual(cpm[0]["threshold_top"], str(100 + index))
            self.assertEqual(len(self.rows(self.product("day", label))), 288)
            self.assertEqual(len(self.rows(self.product("adc", label))), 1024)
            hour = self.rows(self.product("hour", label, extension="csv"))
            self.assertEqual(len(hour), 24)
            self.assertEqual(hour[0]["live_seconds"], f"{index + 1:.1f}")
            self.assertEqual(hour[0]["missing_events"], "0")
            summary = self.rows(build_daily_summary_path(self.base, label))
            self.assertEqual(len(summary), 1)
            self.assertEqual(summary[0]["Count_C"], str(index + 2))
        self.assertEqual(process_daily(self.day, self.base, "East"), 0)
        self.assertEqual(len(self.rows(build_daily_summary_path(self.base, "East"))), 1)
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertFalse(build_daily_summary_path(self.base).exists())
        self.assertFalse((self.base / "data" / "cpm" / "ACM0").exists())
        self.assertEqual(list((self.base / "data").rglob("*.tmp")), [])

    def test_missing_named_input_never_uses_other_or_legacy_raw(self):
        for label in (None, "ACM0", "Old", "West"):
            self.raw(label)
        with patch("sys.stderr", new_callable=io.StringIO) as errors:
            self.assertEqual(process_daily(self.day, self.base, "East"), 1)
        self.assertIn("ProcessDaily.py[East]", errors.getvalue())
        self.assertIn("Raw data file missing", errors.getvalue())
        self.assertFalse(self.product("cpm", "East").exists())
        self.assertFalse(build_daily_summary_path(self.base, "East").exists())

    def test_missing_named_settings_never_fall_back_to_shared_settings(self):
        legacy = self.base / "config" / "legacy.ini"
        legacy.write_text(legacy.read_text().replace("[legacy:East]", "[legacy:OldEast]"))
        self.raw("East")
        self.raw("West")
        with self.assertRaisesRegex(ValueError, "legacy:East"):
            process_daily(self.day, self.base, "East")
        self.assertFalse(self.product("cpm", "East").exists())
        self.assertEqual(process_daily(self.day, self.base, "West"), 0)
        # Recorded settings do not require any legacy section.
        self.raw("East", settings=",10,20,30,40")
        self.assertEqual(process_daily(self.day, self.base, "East"), 0)
        self.assertEqual(self.rows(self.product("cpm", "East"))[0]["threshold_top"], "10")

    def test_periods_keep_all_three_detectors_separate(self):
        for index, label in enumerate(self.labels):
            self.raw(label, index + 2)
            self.assertEqual(process_daily(self.day, self.base, label), 0)
            for period, cfg in PERIOD_CONFIGS.items():
                self.assertEqual(process_period_data(period, self.day, self.base, 0.1, label), 0)
                rows = self.rows(self.product(period, label))
                self.assertEqual(len(rows), cfg["bin_count"])
                self.assertEqual(sum(float(row["CPM_C"]) for row in rows if row["CPM_C"] != "nan"), index + 2)
                self.assertEqual(rows[-1]["detector_name"], label)
                self.assertEqual(rows[-1]["threshold_top"], str(100 + index))

    def test_period_missing_input_does_not_use_legacy_or_other_detector(self):
        self.raw("West")
        process_daily(self.day, self.base, "West")
        legacy = build_processed_day_path(self.base, "day", self.day)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.product("day", "West"), legacy)
        self.assertEqual(process_period_data("week", self.day, self.base, 10, "East"), 0)
        self.assertFalse(self.product("week", "East").exists())

    def test_historical_period_settings_use_only_selected_label(self):
        path = self.product("day", "Third")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{self.day} 00:00:00,1,2,3,22,1015,100\n")
        rows = load_day_file(path, self.base, "Third")
        self.assertEqual(rows[0][7][1:], ("102", "52", "202", "62"))

    def test_reprocessing_discovery_ignores_other_units_rejected_and_out_of_range(self):
        self.raw("East")
        self.raw("East", day=self.day - timedelta(days=1))
        self.raw("East", day=self.day + timedelta(days=1))
        self.raw("West", day=self.day - timedelta(days=2))
        self.raw(None, day=self.day - timedelta(days=3))
        rejected = self.base / "data" / "raw" / "East" / "rejected" / "2026-10-01.txt"
        rejected.parent.mkdir()
        rejected.write_text("malformed")
        self.assertEqual(raw_dates(self.base, "East", None, self.day), [self.day - timedelta(days=1), self.day])
        self.assertEqual(raw_dates(self.base, "East", self.day, self.day), [self.day])

    def test_single_archive_discovery_does_not_scan_named_or_rejected_folders(self):
        (self.base / "config" / "USB.ini").write_text("[usb]\nlabel=Old\n")
        for label in (None, "ACM0", "Old", "East", "rejected"):
            self.raw(label)
        self.raw("East", day=self.day - timedelta(days=1))
        self.assertEqual(raw_dates(self.base, None, None, self.day), [self.day])
        self.assertEqual(process_daily(self.day, self.base), 0)
        self.assertEqual(self.rows(build_processed_day_path(self.base, "cpm", self.day))[0]["detector_name"], "Old")

    def test_processing_lock_blocks_same_detector_but_not_other_detectors_and_releases(self):
        self.raw("East")
        self.raw("West")
        with processing_lock(self.base, "East"):
            for operation in (
                lambda: process_daily(self.day, self.base, "East"),
                lambda: process_period_data("week", self.day, self.base, detector="East"),
            ):
                with self.assertRaisesRegex(RuntimeError, "processing lock for East"):
                    operation()
            self.assertEqual(process_daily(self.day, self.base, "West"), 0)
        self.assertEqual(process_daily(self.day, self.base, "East"), 0)
        with self.assertRaisesRegex(ValueError, "test failure"):
            with processing_lock(self.base, "East"):
                raise ValueError("test failure")
        with processing_lock(self.base, "East"):
            pass

    def test_cli_requires_selection_and_logs_invalid_labels(self):
        for script in ("ProcessDaily.py", "ProcessPeriod.py"):
            for args in ([], ["--detector", "Unknown"], ["--detector", "../East"]):
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / script), "--date", str(self.day), *args],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("FAILED", result.stderr)
        self.assertFalse((self.base / "data").exists())

    def test_named_processing_cli_and_cross_process_lock_contention(self):
        self.raw("East", 3)
        daily = [sys.executable, str(SCRIPTS / "ProcessDaily.py"),
                 "--detector", "East", "--date", str(self.day)]
        with processing_lock(self.base, "East"):
            busy = subprocess.run(daily, capture_output=True, text=True)
            self.assertEqual(busy.returncode, 1)
            self.assertIn("processing lock for East", busy.stderr)
            self.assertFalse(self.product("cpm", "East").exists())
        run = subprocess.run(daily, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        period = subprocess.run(
            [sys.executable, str(SCRIPTS / "ProcessPeriod.py"), "--detector", "East",
             "--date", str(self.day), "--period", "week", "--min-percent", "10"],
            capture_output=True, text=True,
        )
        self.assertEqual(period.returncode, 0, period.stderr)
        self.assertEqual(self.rows(self.product("week", "East"))[-1]["detector_name"], "East")

    def test_named_acm0_does_not_overwrite_legacy_processed_products(self):
        usb = self.base / "config" / "USB.ini"
        usb.write_text(usb.read_text().replace("Third", "ACM0"))
        self.raw("ACM0", settings=",1,2,3,4")
        legacy = build_processed_day_path(self.base, "cpm", self.day)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("legacy product")
        self.assertEqual(process_daily(self.day, self.base, "ACM0"), 0)
        self.assertEqual(legacy.read_text(), "legacy product")
        self.assertTrue(self.product("cpm", "ACM0").exists())

    def test_archive_discovery_cli_is_read_only(self):
        self.raw("East")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "picomuon_processing.py"),
             "--detector", "East", "--to", str(self.day)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.day))
        self.assertFalse((self.base / "logfiles").exists())
        self.assertFalse((self.base / "data" / "cpm").exists())

    @unittest.skipUnless(os.name == "posix", "Bash reprocessing integration runs on Linux/RPi")
    def test_shell_dry_run_selection_processing_and_batch_lock(self):
        shutil.copytree(SCRIPTS, self.base / "scripts")
        self.raw("East")
        self.raw("West", day=self.day - timedelta(days=1))
        command = ["bash", str(self.base / "scripts" / "reprocessData.sh"),
                   "--detector", "East", "--to", str(self.day)]
        dry = subprocess.run([*command, "--dry-run"], capture_output=True, text=True)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn(str(self.day), dry.stdout)
        self.assertNotIn(str(self.day - timedelta(days=1)), dry.stdout)
        self.assertFalse((self.base / "logfiles").exists())
        run = subprocess.run([*command, "--skip-period"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(self.product("cpm", "East").exists())
        self.assertFalse(self.product("cpm", "West").exists())
        log = self.base / "logfiles" / "detectors" / "East" / "log-PicoMuon.txt"
        self.assertIn("Completed reprocessing with 0 failure(s)", log.read_text())
        with (log.parent / ".reprocess.lock").open("a+b") as lock:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            blocked = subprocess.run([*command, "--skip-period"], capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 1)
        self.assertIn("another reprocessing job is running", (log.parent / "log-error.txt").read_text())
        invalid = subprocess.run(
            ["bash", str(self.base / "scripts" / "reprocessData.sh"), "--dry-run",
             "--detector", "Unknown", "--to", str(self.day)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("not registered", invalid.stderr)


if __name__ == "__main__":
    unittest.main()
