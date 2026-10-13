import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from picomuon_common import (
    LOG_PROCESS_WIDTH,
    build_raw_day_path,
    build_usb_ini_path,
    format_log_entry,
    get_usb_options,
    log_error,
    log_message,
    utc_now,
    verify_usb_identity,
)
from GetDataRaw import parse_and_validate_line, write_status_json
from ConfigureUSB import sanitize_label


class Phase1HelpersTests(unittest.TestCase):
    def test_format_log_entry_alignment(self):
        ts = datetime(2026, 10, 13, 12, 34, 56, tzinfo=timezone.utc)
        line = format_log_entry(ts, "GetDataRaw.py", "Connected to port")
        expected_prefix = f"2026-10-13 12:34:56 UTC : {'GetDataRaw.py':<26} : Connected to port"
        self.assertEqual(line, expected_prefix)
        # Check alignment position of colon
        parts = line.split(" : ")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "2026-10-13 12:34:56 UTC")
        self.assertEqual(parts[1], "GetDataRaw.py".ljust(LOG_PROCESS_WIDTH))
        self.assertEqual(parts[2], "Connected to port")

    def test_log_message_and_error(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            log_message("test_proc", "info message")
            output = mock_stdout.getvalue()
            self.assertIn("UTC : test_proc", output)
            self.assertIn("info message", output)

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            log_error("test_proc", "error message")
            output = mock_stderr.getvalue()
            self.assertIn("UTC : test_proc", output)
            self.assertIn("error message", output)

    def test_build_raw_day_path(self):
        base = Path("/opt/picomuon")
        ts = datetime(2026, 10, 14, 15, 30, tzinfo=timezone.utc)

        # Single detector layout
        path_single = build_raw_day_path(base, ts)
        self.assertEqual(
            path_single.as_posix(),
            "/opt/picomuon/data/raw/2026/2026-10/2026-10-14.txt",
        )

        # Multi detector layout with label
        path_multi = build_raw_day_path(base, ts, label="V56-123")
        self.assertEqual(
            path_multi.as_posix(),
            "/opt/picomuon/data/raw/V56-123/2026/2026-10/2026-10-14.txt",
        )

    def test_get_usb_options_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            options = get_usb_options(temp_path)
            self.assertEqual(options["serial_port"], "/dev/ttyACM0")
            self.assertEqual(options["id_serial"], "")
            self.assertEqual(options["id_serial_short"], "")
            self.assertEqual(options["label"], "")

    def test_get_usb_options_from_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_dir = temp_path / "config"
            config_dir.mkdir()
            ini_file = config_dir / "USB.ini"
            ini_file.write_text(
                "[usb]\nserial_port = /dev/serial/by-id/test-dev\nid_serial = Raspberry_Pi_Pico_123\nlabel = East-01\n",
                encoding="utf-8",
            )
            options = get_usb_options(temp_path)
            self.assertEqual(options["serial_port"], "/dev/serial/by-id/test-dev")
            self.assertEqual(options["id_serial"], "Raspberry_Pi_Pico_123")
            self.assertEqual(options["label"], "East-01")

    def test_sanitize_label(self):
        self.assertEqual(sanitize_label("V53/D/09/034"), "V53-D-09-034")
        self.assertEqual(sanitize_label("Detector #1!"), "Detector-1")
        self.assertEqual(sanitize_label("A" * 30), "A" * 16)

    def test_parse_and_validate_line_valid(self):
        # 8-field serial payload from detector: Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp_C,Pres_hPa,DetectorName
        sample = "C,2551179,607,-2147288954,14107572,24.1,1011.0,V53/D/09/034"
        res = parse_and_validate_line(sample)
        self.assertIsNotNone(res)
        (
            line_str,
            event,
            event_count,
            adc,
            elapsed_ms,
            dead_ms,
            temp_c,
            pres_hpa,
            det_name,
        ) = res
        self.assertEqual(event, "C")
        self.assertEqual(event_count, 2551179)
        self.assertEqual(adc, 607)
        self.assertEqual(elapsed_ms, -2147288954)
        self.assertEqual(dead_ms, 14107572)
        self.assertEqual(temp_c, 24.1)
        self.assertEqual(pres_hpa, 1011.0)
        self.assertEqual(det_name, "V53/D/09/034")

    def test_parse_and_validate_line_with_comma_in_detector_name(self):
        # DetectorName might have a comma: "V53/D,09/034"
        sample = "T,100,500,12345,678,25.0,1013.2,MyDetector,Unit1"
        res = parse_and_validate_line(sample)
        self.assertIsNotNone(res)
        self.assertEqual(res[1], "T")
        self.assertEqual(res[8], "MyDetector,Unit1")

    def test_parse_and_validate_line_invalid(self):
        self.assertIsNone(parse_and_validate_line("invalid,data"))
        self.assertIsNone(parse_and_validate_line("X,100,500,12345,678,25.0,1013.2,Det"))
        self.assertIsNone(parse_and_validate_line("C,notanumber,500,12345,678,25.0,1013.2,Det"))

    def test_write_status_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "data" / "status" / "current.json"
            ts = datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)
            write_status_json(
                status_file,
                ts,
                "C",
                24.5,
                1012.3,
                "TestDet",
                12345,
            )
            self.assertTrue(status_file.exists())
            data = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(data["last_event_utc"], "2026-10-13 10:00:00 UTC")
            self.assertEqual(data["last_event_type"], "C")
            self.assertEqual(data["temperature_c"], 24.5)
            self.assertEqual(data["pressure_hpa"], 1012.3)
            self.assertEqual(data["detector_name"], "TestDet")
            self.assertEqual(data["total_events_today"], 12345)


if __name__ == "__main__":
    unittest.main()
