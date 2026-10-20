import csv
from datetime import date
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ProcessDaily import process_daily
from picomuon_common import build_daily_summary_path


class EventAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.day = date(2026, 10, 19)
        self.raw = self.base / "data" / "raw" / "2026" / "2026-10" / "2026-10-19.txt"
        self.raw.parent.mkdir(parents=True)

    def process(self, events):
        # All settings are recorded, so these tests do not use legacy assumptions.
        self.raw.write_text("".join(
            f"{self.day} {timestamp},{event},{count},200,{elapsed},0,22,1015,{name},200,100,200,100\n"
            for timestamp, event, count, elapsed, name in events
        ))
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(process_daily(self.day, self.base), 0)
        hour = self.base / "data" / "hour" / "2026" / "2026-10" / "2026-10-19.csv"
        with hour.open() as source:
            self.hours = list(csv.DictReader(source))
        with build_daily_summary_path(self.base).open() as source:
            self.summary = next(csv.DictReader(source))

    def assert_accounting(self, seconds, missing):
        self.assertAlmostEqual(sum(float(row["live_seconds"]) for row in self.hours), seconds)
        self.assertEqual(sum(int(row["missing_events"]) for row in self.hours), missing)
        self.assertEqual(int(self.summary["MissingEvents"]), missing)

    def test_interleaved_independent_counters_use_one_shared_elapsed_clock(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:01", "B", 800, 11000, "Detector"),
            ("00:00:02", "C", 5, 12000, "Detector"),
            ("00:00:03", "T", 101, 13000, "Detector"),
            ("00:00:04", "B", 801, 14000, "Detector"),
            ("00:00:05", "C", 6, 15000, "Detector"),
        ])
        self.assert_accounting(5, 0)
        self.assertEqual(tuple(self.summary[f"Count_{event}"] for event in "TBC"), ("2", "2", "2"))

    def test_missing_counts_compare_only_the_same_event_type(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:01", "B", 800, 11000, "Detector"),
            ("00:00:02", "C", 5, 12000, "Detector"),
            ("00:00:03", "T", 104, 13000, "Detector"),
            ("00:00:04", "B", 802, 14000, "Detector"),
            ("00:00:05", "C", 6, 15000, "Detector"),
        ])
        self.assert_accounting(5, 4)

    def test_reboot_clears_all_event_baselines_even_when_first_type_changes(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:01", "B", 800, 11000, "Detector"),
            ("00:00:02", "C", 5, 12000, "Detector"),
            ("00:03:00", "B", 1, 100, "Detector"),
            ("00:03:01", "T", 1, 1100, "Detector"),
            ("00:03:02", "C", 20, 2100, "Detector"),
            ("00:03:03", "B", 2, 3100, "Detector"),
        ])
        self.assert_accounting(5, 0)

    def test_counter_drop_starts_segment_even_with_forward_elapsed(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:01", "B", 800, 11000, "Detector"),
            ("00:00:02", "T", 1, 12000, "Detector"),
            ("00:00:03", "B", 900, 13000, "Detector"),
        ])
        self.assert_accounting(2, 0)

    def test_signed_elapsed_wrap_and_shared_ticks_are_not_resets(self):
        self.process([
            ("00:00:00", "T", 100, 2147483000, "Detector"),
            ("00:00:00", "B", 800, 2147483000, "Detector"),
            ("00:00:01", "C", 5, -2147483296, "Detector"),
            ("00:00:02", "T", 101, -2147482296, "Detector"),
        ])
        self.assert_accounting(2, 0)

    def test_unsigned_elapsed_wrap(self):
        self.process([
            ("00:00:00", "T", 100, 4294967000, "Detector"),
            ("00:00:01", "B", 800, 704, "Detector"),
            ("00:00:02", "T", 101, 1704, "Detector"),
        ])
        self.assert_accounting(2, 0)

    def test_name_change_starts_new_segment(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Old"),
            ("00:00:01", "B", 800, 11000, "Old"),
            ("00:00:02", "T", 104, 12000, "New"),
            ("00:00:03", "B", 900, 13000, "New"),
            ("00:00:04", "T", 105, 14000, "New"),
        ])
        self.assert_accounting(3, 0)

    def test_exposure_is_split_at_utc_hour_boundary(self):
        self.process([
            ("00:59:59", "T", 100, 10000, "Detector"),
            ("01:00:01", "B", 800, 12000, "Detector"),
            ("01:00:03", "T", 103, 14000, "Detector"),
        ])
        self.assert_accounting(4, 2)
        self.assertEqual(self.hours[0]["live_seconds"], "1.0")
        self.assertEqual(self.hours[1]["live_seconds"], "3.0")
        self.assertEqual(self.hours[0]["missing_events"], "0")
        self.assertEqual(self.hours[1]["missing_events"], "2")

    def test_long_elapsed_gap_discards_all_counter_baselines(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:01", "B", 800, 11000, "Detector"),
            ("01:00:02", "T", 105, 3612000, "Detector"),
            ("01:00:03", "B", 900, 3613000, "Detector"),
        ])
        self.assert_accounting(2, 0)

    def test_large_same_type_gaps_are_not_silently_discarded(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:01", "B", 800, 11000, "Detector"),
            ("00:00:02", "T", 2101, 12000, "Detector"),
        ])
        self.assert_accounting(2, 2000)

    def test_clock_gap_clears_baselines_when_first_type_has_not_been_seen(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:01", "B", 800, 11000, "Detector"),
            ("00:00:10", "C", 1, 100, "Detector"),
            ("00:00:11", "T", 200, 1100, "Detector"),
            ("00:00:12", "B", 900, 2100, "Detector"),
        ])
        self.assert_accounting(3, 0)

    def test_partial_day_does_not_invent_exposure_before_first_or_after_last_event(self):
        self.process([
            ("10:30:00", "T", 100, 100000, "Detector"),
            ("10:30:02", "B", 800, 102000, "Detector"),
        ])
        self.assert_accounting(2, 0)
        self.assertEqual(self.hours[10]["live_seconds"], "2.0")
        self.assertEqual(self.summary["ValidHours"], "1")

    def test_boundary_allocation_uses_device_duration_not_wall_duration(self):
        self.process([
            ("00:59:58", "T", 100, 10000, "Detector"),
            ("01:00:02", "B", 800, 12000, "Detector"),
        ])
        self.assert_accounting(2, 0)
        self.assertEqual(self.hours[0]["live_seconds"], "1.0")
        self.assertEqual(self.hours[1]["live_seconds"], "1.0")

    def test_exact_hour_boundary_keeps_preceding_exposure_in_previous_hour(self):
        self.process([
            ("00:59:59", "T", 100, 10000, "Detector"),
            ("01:00:00", "B", 800, 11000, "Detector"),
        ])
        self.assert_accounting(1, 0)
        self.assertEqual(self.hours[0]["live_seconds"], "1.0")
        self.assertEqual(self.hours[1]["live_seconds"], "0.0")

    def test_backwards_timestamp_discards_interval_and_all_baselines(self):
        self.process([
            ("00:00:01", "T", 100, 10000, "Detector"),
            ("00:00:02", "B", 800, 11000, "Detector"),
            ("00:00:01", "T", 104, 12000, "Detector"),
            ("00:00:02", "B", 900, 13000, "Detector"),
        ])
        self.assert_accounting(2, 0)

    def test_long_utc_gap_is_not_bridged_even_if_device_elapsed_is_short(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:01", "B", 800, 11000, "Detector"),
            ("02:00:02", "T", 105, 12000, "Detector"),
            ("02:00:03", "B", 900, 13000, "Detector"),
        ])
        self.assert_accounting(2, 0)

    def test_repeated_same_type_counter_does_not_invent_missing_events(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:01", "B", 800, 11000, "Detector"),
            ("00:00:02", "T", 100, 12000, "Detector"),
            ("00:00:03", "T", 101, 13000, "Detector"),
        ])
        self.assert_accounting(3, 0)

    def test_shared_receiver_timestamp_does_not_drop_elapsed_duration(self):
        self.process([
            ("00:00:00", "T", 100, 10000, "Detector"),
            ("00:00:00", "B", 800, 11000, "Detector"),
            ("00:00:01", "T", 101, 12000, "Detector"),
        ])
        self.assert_accounting(2, 0)

    def test_device_clock_duration_is_not_clamped_to_receiver_hour(self):
        self.process([
            ("00:00:00", "T", 100, 0, "Detector"),
            ("00:30:00", "B", 800, 1800500, "Detector"),
            ("00:59:59", "T", 101, 3600500, "Detector"),
        ])
        self.assert_accounting(3600.5, 0)


if __name__ == "__main__":
    unittest.main()
