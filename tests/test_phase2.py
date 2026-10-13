import io
import os
from datetime import date, datetime, timezone
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from picomuon_common import (
    build_daily_summary_path,
    build_processed_day_path,
    get_target_date,
)
from ProcessDaily import parse_arguments as parse_daily_args, process_daily
from ProcessPeriod import parse_arguments as parse_period_args, process_period_data


def generate_synthetic_raw_and_neutron(base_path: Path, target_date: date):
    """Generate self-contained synthetic raw and neutron data for testing without gitignored examples."""
    raw_path = base_path / "data" / "raw" / "2026" / "2026-10" / f"{target_date.strftime('%Y-%m-%d')}.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate synthetic raw lines
    lines = []
    # 2 events per minute across all 1440 minutes = 2880 events
    event_num = 1
    elapsed_ms = 1000
    dead_ms = 50
    for hour in range(24):
        for minute in range(60):
            for sec, evt_type in [(10, "T"), (40, "C")]:
                ts_str = f"{target_date.strftime('%Y-%m-%d')} {hour:02d}:{minute:02d}:{sec:02d}.123456"
                adc = 200 if evt_type == "C" else 150
                elapsed_ms += 30000
                dead_ms += 10
                temp = 22.5
                pres = 1015.0
                det = "56/148/627"
                lines.append(f"{ts_str},{evt_type},{event_num},{adc},{elapsed_ms},{dead_ms},{temp},{pres},{det}")
                event_num += 1

    raw_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Generate synthetic neutron file (1440 lines)
    neutron_path = base_path / "data" / "NMDB" / "neutrons" / "2026" / "2026-10" / f"{target_date.strftime('%Y-%m-%d')}.txt"
    neutron_path.parent.mkdir(parents=True, exist_ok=True)
    n_lines = []
    for hour in range(24):
        for minute in range(60):
            ts_str = f"{target_date.strftime('%Y-%m-%d')} {hour:02d}:{minute:02d}:00"
            n_lines.append(f"{ts_str},1015.0,100.0,102.0,102.0")
    neutron_path.write_text("\n".join(n_lines) + "\n", encoding="utf-8")


class Phase2ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        self.target_date = date(2026, 10, 9)

        # Check if local example files exist (local developer environment)
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

        if sample_raw.exists() and sample_neutron.exists():
            shutil.copy2(sample_raw, dest_raw)
            shutil.copy2(sample_neutron, dest_neutron)
            self.has_real_sample = True
        else:
            generate_synthetic_raw_and_neutron(self.base_path, self.target_date)
            self.has_real_sample = False

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
        if self.has_real_sample:
            self.assertEqual(first_cpm[1], "0")
            self.assertEqual(first_cpm[2], "0")
            self.assertEqual(first_cpm[3], "17")
        else:
            self.assertEqual(first_cpm[1], "1")
            self.assertEqual(first_cpm[2], "0")
            self.assertEqual(first_cpm[3], "1")

        # Check Day file (288 lines)
        day_file = build_processed_day_path(self.base_path, "day", self.target_date, "ACM0", "txt")
        self.assertTrue(day_file.exists())
        day_lines = day_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(day_lines), 288)
        first_day = day_lines[0].split(",")
        self.assertEqual(first_day[0], "2026-10-09 00:00:00")
        if self.has_real_sample:
            self.assertEqual(first_day[1], "nan")
            self.assertEqual(first_day[2], "nan")
            self.assertEqual(first_day[3], "78")
            self.assertEqual(first_day[4], "22.9")
            self.assertEqual(first_day[5], "1015.5")
            self.assertEqual(first_day[6], "505.674")
        else:
            self.assertEqual(first_day[3], "5")

        # Check ADC file (1024 lines)
        adc_file = build_processed_day_path(self.base_path, "adc", self.target_date, "ACM0", "txt")
        self.assertTrue(adc_file.exists())
        adc_lines = adc_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(adc_lines), 1024)
        bin_200 = adc_lines[200].split(",")
        self.assertEqual(bin_200[0], "200")
        if self.has_real_sample:
            self.assertEqual(bin_200[3], "14")
        else:
            self.assertEqual(bin_200[3], "1440")

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
        self.assertEqual(parts[6], "24")
        self.assertEqual(parts[7], "100.0")

    def test_process_period_week(self):
        # Create 7 consecutive day files
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
        if sample_day_dir.exists():
            for day_num in range(3, 10):
                d = date(2026, 10, day_num)
                src_f = sample_day_dir / f"{d.strftime('%Y-%m-%d')}.txt"
                dest_f = build_processed_day_path(self.base_path, "day", d, "ACM0", "txt")
                dest_f.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_f, dest_f)
        else:
            # Generate synthetic day files (288 lines each)
            for day_num in range(3, 10):
                d = date(2026, 10, day_num)
                dest_f = build_processed_day_path(self.base_path, "day", d, "ACM0", "txt")
                dest_f.parent.mkdir(parents=True, exist_ok=True)
                lines = []
                for hour in range(24):
                    for minute in range(0, 60, 5):
                        ts = f"{d.strftime('%Y-%m-%d')} {hour:02d}:{minute:02d}:00"
                        lines.append(f"{ts},0.0,0.0,75,22.0,1015.0,500.000")
                dest_f.write_text("\n".join(lines) + "\n", encoding="utf-8")

        res = process_period_data("week", self.target_date, self.base_path, min_percent=90.0)
        self.assertEqual(res, 0)

        week_file = build_processed_day_path(self.base_path, "week", self.target_date, "ACM0", "txt")
        self.assertTrue(week_file.exists())
        lines = week_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1008)

        first_week = lines[0].split(",")
        self.assertEqual(first_week[0], "2026-10-03 00:00:00")
        if sample_day_dir.exists():
            self.assertEqual(first_week[3], "143")
            self.assertEqual(first_week[4], "27.5")
            self.assertEqual(first_week[5], "1028.2")
            self.assertEqual(first_week[6], "1036.100")
        else:
            self.assertEqual(first_week[3], "150")

    def test_cli_arguments_date_alias(self):
        # Verify --date works as alias for --target-date in ProcessDaily
        with unittest.mock.patch("sys.argv", ["ProcessDaily.py", "--date", "2026-10-12"]):
            args = parse_daily_args()
            self.assertEqual(args.target_date, date(2026, 10, 12))

        # Verify --target-date works as before
        with unittest.mock.patch("sys.argv", ["ProcessDaily.py", "--target-date", "2026-10-12"]):
            args = parse_daily_args()
            self.assertEqual(args.target_date, date(2026, 10, 12))

        # Verify --date works as alias for --target-date in ProcessPeriod
        with unittest.mock.patch("sys.argv", ["ProcessPeriod.py", "--date", "2026-10-12"]):
            args = parse_period_args()
            self.assertEqual(args.target_date, date(2026, 10, 12))


if __name__ == "__main__":
    unittest.main()
