import csv
from datetime import date
import io
from pathlib import Path
import runpy
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from picomuon_common import RAW_HEADER, build_neutron_path, build_processed_day_path
from picomuon_metadata import RawEventWriter
from picomuon_neutrons import NEUTRON_COLUMNS, load_neutrons, write_neutron_header
from picomuon_products import ADC_COLUMNS, CPM_COLUMNS, DAY_COLUMNS, HOUR_COLUMNS, BinMetadata
from ProcessDaily import process_daily
from ProcessPeriod import PERIOD_CONFIGS, process_period_data


class BinMetadataTests(unittest.TestCase):
    def test_prepared_columns_match_generic_values_across_repeats_and_changes(self):
        generic = BinMetadata()
        prepared = BinMetadata()
        observations = (
            ("Detector", 200, 100, 200, 100),
            ("Detector", 200, 100, 200, 100),
            ("Detector", 250, 100, 200, 100),
            ("Other", 250, 100, 200, 200),
            ("Detector", 200, 100, 200, 100),
        )
        for observation in observations:
            generic.add(observation)
            prepared.add_columns(tuple(str(value) for value in observation))
            self.assertEqual(prepared.values, generic.values)
            self.assertEqual(prepared.columns(), generic.columns())
        self.assertEqual(prepared.columns(), ("mixed", "mixed", "100", "200", "mixed"))

    def test_prepared_columns_preserve_empty_fallback_and_validate_width(self):
        fallback = BinMetadata()
        fallback.add(("Detector", 200, 100, 200, 100))
        empty = BinMetadata()
        self.assertEqual(empty.columns(fallback), fallback.columns())
        for values in ((), ("Detector",), ("Detector", "200", "100", "200", "100", "extra")):
            with self.assertRaises(ValueError):
                empty.add_columns(values)
        self.assertEqual(empty.columns(fallback), fallback.columns())
        empty.add_columns(("Other", "250", "120", "250", "120"))
        self.assertEqual(fallback.columns(), ("Detector", "200", "100", "200", "100"))


class ProductColumnTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.day = date(2026, 10, 17)
        config = self.base / "config"
        config.mkdir()
        (config / "legacy.ini").write_text(
            "[legacy]\nthreshold_top=200\nreset_top=100\nthreshold_bottom=200\nreset_bottom=100\n"
        )
        self.raw = self.base / "data" / "raw" / "2026" / "2026-10" / "2026-10-17.txt"
        self.raw.parent.mkdir(parents=True)

    def write_raw(self, rows):
        self.raw.write_text(RAW_HEADER + "\n" + "\n".join(rows) + "\n")

    def process(self):
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(process_daily(self.day, self.base), 0)

    def rows(self, category):
        path = build_processed_day_path(self.base, category, self.day)
        if category == "hour":
            path = self.base / "data" / "hour" / "2026" / "2026-10" / "2026-10-17.csv"
        text = path.read_text()
        self.assertNotIn("# picomuon_metadata:", text)
        reader = csv.DictReader(text.splitlines())
        rows = list(reader)
        self.assertTrue(all(None not in row and None not in row.values() for row in rows))
        return reader.fieldnames, rows

    def test_exact_schemas_and_column_values(self):
        self.write_raw([
            "2026-10-17 00:00:01.000000,C,1,200,1000,0,22.9,1028.45,56/148/627,200,100,200,100",
            "2026-10-17 00:00:02.000000,T,2,201,2000,0,22.9,1028.45,56/148/627,200,100,200,100",
        ])
        neutron = build_neutron_path(self.base, self.day)
        neutron.parent.mkdir(parents=True, exist_ok=True)
        with neutron.open("w", newline="") as output:
            write_neutron_header(output, "OULU", "https://www.nmdb.eu/test-request")
            output.write("2026-10-17 00:00:00,1010.59,90.8,98.202,493.888\n")
        self.process()
        for category, schema, count in (
            ("adc", ADC_COLUMNS, 1024), ("cpm", CPM_COLUMNS, 1440),
            ("day", DAY_COLUMNS, 288), ("hour", HOUR_COLUMNS, 24),
        ):
            with self.subTest(category=category):
                fields, rows = self.rows(category)
                self.assertEqual(fields, list(schema))
                self.assertEqual(len(rows), count)
                for row in rows:
                    self.assertEqual(
                        [row[key] for key in ("detector_name", "threshold_top", "reset_top",
                                              "threshold_bottom", "reset_bottom")],
                        ["56/148/627", "200", "100", "200", "100"],
                    )
        self.assertEqual(self.rows("day")[1][0]["neutrons"], "493.888")
        self.assertEqual(self.rows("day")[1][0]["station"], "OULU")
        self.assertEqual(self.rows("hour")[1][0]["pres"], "1028.45")
        self.assertEqual(self.rows("hour")[1][0]["station"], "OULU")

    def test_mixed_fields_and_bins_use_only_their_contributing_events(self):
        self.write_raw([
            "2026-10-17 00:00:01.000000,T,1,200,1000,0,22,1000,Detector,200,100,200,100",
            "2026-10-17 00:00:02.000000,C,2,200,2000,0,22,1000,Detector,250,100,200,100",
            "2026-10-17 00:01:01.000000,C,3,201,3000,0,22,1000,Other,250,100,200,100",
        ])
        self.process()
        cpm = self.rows("cpm")[1]
        self.assertEqual(cpm[0]["threshold_top"], "mixed")
        self.assertEqual(cpm[0]["reset_top"], "100")
        self.assertEqual(cpm[0]["detector_name"], "Detector")
        self.assertEqual(cpm[0]["Count_T"], "1")
        self.assertEqual(cpm[0]["Count_C"], "1")
        self.assertEqual(cpm[1]["threshold_top"], "250")
        self.assertEqual(cpm[1]["detector_name"], "Other")
        adc = self.rows("adc")[1]
        self.assertEqual(adc[200]["threshold_top"], "mixed")
        self.assertEqual(adc[201]["threshold_top"], "250")
        self.assertEqual(self.rows("hour")[1][0]["detector_name"], "mixed")

    def test_partial_day_marks_unobserved_time_as_nan_but_keeps_observed_zero_counts(self):
        self.write_raw([
            "2026-10-17 10:30:01.000000,C,1,200,1000,0,22,1000,Detector,200,100,200,100",
        ])
        original = self.raw.read_bytes()
        self.process()
        cpm = self.rows("cpm")[1]
        for index, row in enumerate(cpm):
            expected = ("0", "0", "1") if index == 630 else ("nan",) * 3
            self.assertEqual(tuple(row[key] for key in ("Count_T", "Count_B", "Count_C")), expected)
        day = self.rows("day")[1]
        for index, row in enumerate(day):
            expected = ("0", "0", "1") if index == 126 else ("nan",) * 3
            self.assertEqual(tuple(row[key] for key in ("CPM_T", "CPM_B", "CPM_C")), expected)
        self.assertEqual(self.raw.read_bytes(), original)
        self.assertEqual(self.rows("adc")[1][200]["Count_C"], "1")

    def test_continuous_accounting_interval_preserves_zero_event_minutes(self):
        self.write_raw([
            "2026-10-17 10:00:01.000000,C,1,200,1000,0,22,1000,Detector,200,100,200,100",
            "2026-10-17 10:03:01.000000,C,2,200,181000,0,22,1000,Detector,200,100,200,100",
        ])
        self.process()
        cpm = self.rows("cpm")[1]
        self.assertEqual(cpm[599]["Count_C"], "nan")
        self.assertEqual([row["Count_C"] for row in cpm[600:604]], ["1", "0", "0", "1"])
        self.assertEqual(cpm[604]["Count_C"], "nan")

    def test_reset_and_long_gap_do_not_imply_observation_between_events(self):
        self.write_raw([
            "2026-10-17 10:00:01.000000,C,10,200,10000,0,22,1000,Detector,200,100,200,100",
            "2026-10-17 10:10:01.000000,C,1,200,1000,0,22,1000,Detector,200,100,200,100",
            "2026-10-17 12:10:01.000000,C,2,200,7201000,0,22,1000,Detector,200,100,200,100",
        ])
        self.process()
        cpm = self.rows("cpm")[1]
        self.assertEqual(cpm[605]["Count_C"], "nan")
        self.assertEqual(cpm[660]["Count_C"], "nan")
        self.assertEqual(self.rows("day")[1][121]["CPM_C"], "nan")

    def test_periods_preserve_observed_zero_and_missing_bins(self):
        self.write_raw([
            "2026-10-17 10:00:01.000000,C,1,200,1000,0,22,1000,Detector,200,100,200,100",
        ])
        self.process()
        for period in PERIOD_CONFIGS:
            with self.subTest(period=period), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(process_period_data(period, self.day, self.base, min_percent=0), 0)
                rows = self.rows(period)[1]
                populated = [row for row in rows if row["CPM_C"] != "nan"]
                self.assertEqual(len(populated), 1)
                self.assertEqual([populated[0][key] for key in ("CPM_T", "CPM_B", "CPM_C")], ["0", "0", "1"])
                self.assertTrue(all(row["CPM_T"] == "nan" for row in rows if row["CPM_C"] == "nan"))

    def test_history_assumption_is_logged_and_does_not_override_reported_settings(self):
        self.write_raw([
            "# picomuon_metadata: {\"observation\": {\"private\": \"not copied\"}}",
            "2026-10-17 00:00:01.000000,C,1,200,1000,0,22,1000,Detector",
            "2026-10-17 00:01:01.000000,C,2,200,2000,0,22,1000,Detector,300,150,300,150",
        ])
        with patch("sys.stdout", new_callable=io.StringIO) as log:
            self.assertEqual(process_daily(self.day, self.base), 0)
        self.assertIn("ASSUMPTION", log.getvalue())
        self.assertIn("1 historical rows", log.getvalue())
        cpm = self.rows("cpm")[1]
        self.assertEqual(cpm[0]["threshold_top"], "200")
        self.assertEqual(cpm[1]["threshold_top"], "300")
        self.assertNotIn("not copied", build_processed_day_path(self.base, "day", self.day).read_text())
        (self.base / "config" / "legacy.ini").unlink()
        with patch("sys.stdout", new_callable=io.StringIO), self.assertRaises(FileNotFoundError):
            process_daily(self.day, self.base)

    def test_new_raw_files_have_only_column_header_and_events(self):
        (self.base / "config" / "user.ini").write_text("invalid INI - not required by raw recording")
        with self.raw.open("w") as output:
            output.write(RAW_HEADER + "\n")
            RawEventWriter(self.base).write(
                output, "2026-10-17 00:00:01.000000", 'C,1,200,1000,0,22,1000,"Detector,Unit1"',
            )
        rows = list(csv.reader(self.raw.read_text().splitlines()))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[1]), 13)
        self.assertEqual(rows[1][8], "Detector,Unit1")
        self.assertNotIn("#", self.raw.read_text())

    def test_all_periods_share_schema_and_preserve_station_and_mixed_fields(self):
        day_path = build_processed_day_path(self.base, "day", self.day)
        day_path.parent.mkdir(parents=True)
        with day_path.open("w", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(DAY_COLUMNS)
            writer.writerow(["2026-10-17 00:00:00", 1, 0, 1, 22, 1000, "Detector",
                             200, 100, 200, 100, 500, "OULU"])
            writer.writerow(["2026-10-17 00:05:00", 1, 0, 1, 22, 1000, "Detector",
                             250, 100, 200, 100, 600, "JUNG"])
        for period in PERIOD_CONFIGS:
            with self.subTest(period=period), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(process_period_data(period, self.day, self.base, min_percent=0), 0)
                fields, rows = self.rows(period)
                self.assertEqual(fields, list(DAY_COLUMNS))
                populated = [row for row in rows if row["CPM_C"] != "nan"]
                self.assertEqual(len(populated), 1)
                self.assertEqual(populated[0]["threshold_top"], "mixed")
                self.assertEqual(populated[0]["reset_top"], "100")
                self.assertEqual(populated[0]["station"], "mixed")
                expected_neutrons = "1100.000" if period == "week" else "nan"
                self.assertEqual(populated[0]["neutrons"], expected_neutrons)

    def test_neutron_header_and_headerless_inputs_produce_identical_counts(self):
        path = self.base / "neutrons.txt"
        data = "2026-10-17 00:00:00,1010.59,90.8,98.202,98.388\n"
        path.write_text(data)
        with patch("sys.stdout", new_callable=io.StringIO):
            historic = load_neutrons(path)
        with path.open("w", newline="") as output:
            write_neutron_header(output, "OULU", "https://www.nmdb.eu/test")
            output.write(data)
        self.assertEqual(load_neutrons(path), historic)
        self.assertIn("# Station: OULU", path.read_text())
        self.assertIn(",".join(NEUTRON_COLUMNS), path.read_text())
        self.assertEqual(historic, ({"00:00": 98.388}, "OULU"))
        path.write_text(path.read_text().replace("# Station: OULU", "# Station: JUNG"))
        self.assertEqual(load_neutrons(path)[1], "JUNG")

    def test_neutron_scraper_writes_header_and_preserves_dataframe_rows(self):
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        self.addCleanup(socket.setdefaulttimeout, socket.getdefaulttimeout())
        def to_csv(output, **kwargs):
            csv.writer(output, lineterminator="\n").writerow(
                ["2026-10-17 00:00:00", 1010.59, 90.8, 98.202, 98.388]
            )
        pandas = SimpleNamespace(read_table=lambda *args, **kwargs: SimpleNamespace(to_csv=to_csv))
        with patch("picomuon_common.get_base_path", return_value=self.base), \
                patch("picomuon_common.utc_yesterday", return_value=self.day), \
                patch.dict(sys.modules, {"pandas": pandas}), \
                patch("sys.stdout", new_callable=io.StringIO):
            runpy.run_path(str(scripts / "GetDataNeutron.py"), run_name="__main__")
        path = build_neutron_path(self.base, self.day)
        self.assertIn("# Request: https://www.nmdb.eu/nest/", path.read_text())
        self.assertEqual(load_neutrons(path), ({"00:00": 98.388}, "OULU"))

    def run_failed_neutron_download(self, error):
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        self.addCleanup(socket.setdefaulttimeout, socket.getdefaulttimeout())
        observed = {}

        def read_table(*args, **kwargs):
            observed["timeout"] = socket.getdefaulttimeout()
            raise error

        pandas = SimpleNamespace(read_table=read_table)
        stderr = io.StringIO()
        with patch("picomuon_common.get_base_path", return_value=self.base), \
                patch("picomuon_common.utc_yesterday", return_value=self.day), \
                patch.dict(sys.modules, {"pandas": pandas}), \
                patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", stderr), \
                self.assertRaises(SystemExit) as stopped:
            runpy.run_path(str(scripts / "GetDataNeutron.py"), run_name="__main__")
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(observed["timeout"], 30)
        written = [path for path in (self.base / "data").rglob("*") if path.is_file()]
        self.assertEqual([path for path in written if "neutron" in str(path).lower()], [])
        return stderr.getvalue().splitlines()

    def test_unreachable_nmdb_times_out_with_one_line_error(self):
        lines = self.run_failed_neutron_download(URLError(TimeoutError(110, "Connection timed out")))
        self.assertEqual(len(lines), 1)
        self.assertIn("GetDataNeutron.py", lines[0])
        self.assertIn(f"FAILED - NMDB download for {self.day}: [Errno 110] Connection timed out", lines[0])

    def test_unparseable_nmdb_response_is_one_line_error(self):
        lines = self.run_failed_neutron_download(ValueError("No columns to parse from file"))
        self.assertEqual(len(lines), 1)
        self.assertIn(f"FAILED - NMDB download for {self.day}: No columns to parse from file", lines[0])


if __name__ == "__main__":
    unittest.main()
