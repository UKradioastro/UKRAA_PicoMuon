import io
import os
from datetime import date, datetime, timezone
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from picomuon_common import (
    build_daily_summary_path,
    build_processed_day_path,
    get_target_date,
)
from ProcessDaily import process_daily
from ProcessPeriod import process_period_data


class Phase2ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        self.target_date = date(2026, 10, 9)

        # Copy sample raw data into base_path/data/raw/2026/2026-10/2026-10-09.txt
        repo_root = Path(__file__).resolve().parents[1]
        sample_raw = (
            repo_root
            / "examples"
            / "UKRAA_PicoMuon"
            / "data"
            / "raw"
            / "ACM0"
            / "2026"
            / "2026-10"
            / "2026-10-09.txt"
        )
        sample_neutron = (
            repo_root
            / "examples"
            / "UKRAA_PicoMuon"
            / "data"
            / "NMDB"
            / "neutrons"
            / "2026"
            / "2026-10"
            / "2026-10-09.txt"
        )

        dest_raw = (
            self.base_path
            / "data"
            / "raw"
            / "2026"
            / "2026-10"
            / "2026-10-09.txt"
        )
        dest_raw.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sample_raw, dest_raw)

        dest_neutron = (
            self.base_path
            / "data"
            / "NMDB"
            / "neutrons"
            / "2026"
            / "2026-10"
            / "2026-10-09.txt"
        )
        dest_neutron.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sample_neutron, dest_neutron)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_process_daily_products_created(self):
        result = process_daily(self.target_date, self.base_path)
        self.assertEqual(result, 0)

        # Check CPM file (1440 lines)
        cpm_file = build_processed_day_path(self.base_path, "cpm", self.target_date, "ACM0", "txt")
        self.assertTrue(cpm_file.exists())
        lines = cpm_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1440)
        first_cpm = lines[0].split(",")
        self.assertEqual(first_cpm[0], "2026-10-09 00:00:00")
        self.assertEqual(first_cpm[1], "0")
        self.assertEqual(first_cpm[2], "0")
        self.assertEqual(first_cpm[3], "17")

        # Check Day file (288 lines)
        day_file = build_processed_day_path(self.base_path, "day", self.target_date, "ACM0", "txt")
        self.assertTrue(day_file.exists())
        day_lines = day_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(day_lines), 288)
        first_day = day_lines[0].split(",")
        self.assertEqual(first_day[0], "2026-10-09 00:00:00")
        self.assertEqual(first_day[1], "nan")
        self.assertEqual(first_day[2], "nan")
        self.assertEqual(first_day[3], "78")
        self.assertEqual(first_day[4], "22.9")
        self.assertEqual(first_day[5], "1015.5")
        self.assertEqual(first_day[6], "505.674")

        # Check ADC file (1024 lines)
        adc_file = build_processed_day_path(self.base_path, "adc", self.target_date, "ACM0", "txt")
        self.assertTrue(adc_file.exists())
        adc_lines = adc_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(adc_lines), 1024)
        bin_200 = adc_lines[200].split(",")
        self.assertEqual(bin_200[0], "200")
        self.assertEqual(bin_200[3], "14")

        # Check Hourly L2 file (24 data lines + 1 header)
        hour_file = (
            self.base_path
            / "data"
            / "hour"
            / "2026"
            / "2026-10"
            / "2026-10-09.csv"
        )
        self.assertTrue(hour_file.exists())
        hour_lines = hour_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(hour_lines), 25)

        # Check summary.csv
        summary_file = build_daily_summary_path(self.base_path)
        self.assertTrue(summary_file.exists())
        summary_lines = summary_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(summary_lines), 2)
        parts = summary_lines[1].split(",")
        self.assertEqual(parts[0], "2026-10-09 00:00:00")
        self.assertEqual(parts[3], "21177")
        self.assertEqual(parts[6], "24")
        self.assertEqual(parts[7], "100.0")

    def test_process_period_week(self):
        # Create 7 consecutive day files using sample day data
        repo_root = Path(__file__).resolve().parents[1]
        sample_day_dir = (
            repo_root
            / "examples"
            / "UKRAA_PicoMuon"
            / "data"
            / "processed"
            / "day"
            / "ACM0"
            / "2026"
            / "2026-10"
        )
        for day_num in range(3, 10):
            d = date(2026, 10, day_num)
            src_f = sample_day_dir / f"{d.strftime('%Y-%m-%d')}.txt"
            dest_f = build_processed_day_path(self.base_path, "day", d, "ACM0", "txt")
            dest_f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_f, dest_f)

        res = process_period_data("week", self.target_date, self.base_path, min_percent=90.0)
        self.assertEqual(res, 0)

        week_file = build_processed_day_path(self.base_path, "week", self.target_date, "ACM0", "txt")
        self.assertTrue(week_file.exists())
        lines = week_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1008)

        # Compare first line with legacy week file
        first_week = lines[0].split(",")
        self.assertEqual(first_week[0], "2026-10-03 00:00:00")
        self.assertEqual(first_week[3], "143")
        self.assertEqual(first_week[4], "27.5")
        self.assertEqual(first_week[5], "1028.2")
        self.assertEqual(first_week[6], "1036.100")


if __name__ == "__main__":
    unittest.main()
