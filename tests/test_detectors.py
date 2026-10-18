from contextlib import contextmanager
import csv
from datetime import date, datetime, timezone
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import GetDataRaw
from ConfigureUSB import configure_detector, configure_usb
from picomuon_common import get_usb_options, raw_data_lines
from picomuon_detectors import (
    check_detector_name, get_detectors, read_usb_config, select_detector, validate_label,
)
from picomuon_metadata import RawEventWriter, load_legacy_settings, metadata_from_raw
from ProcessDaily import process_daily
from ProcessPeriod import process_period_data

PORT_EAST = "/dev/serial/by-id/usb-Pico_EAST-if00"
PORT_WEST = "/dev/serial/by-id/usb-Pico_WEST-if00"
PAYLOAD = "C,1,200,1000,0,22.0,1015.0,East detector"
BASE_CONFIG = (
    "[usb]\nserial_port = /dev/ttyACM0\nlabel = historic\n"
    "# Existing comments and configuration must survive registration.\n"
)
MULTI_CONFIG = (
    BASE_CONFIG
    + f"[detectors]\nEast = {PORT_EAST}\nWest = {PORT_WEST}\n"
    "[detector:East]\nid_serial_short = EAST\ndetector_name = East detector\n"
    "[detector:West]\nid_serial_short = WEST\ndetector_name = West detector\n"
)


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.config = self.base / "config"
        self.config.mkdir()
        self.usb = self.config / "USB.ini"
        self.usb.write_text(MULTI_CONFIG)
        (self.config / "legacy.ini").write_text(
            "[legacy]\nthreshold_top = 999\nreset_top = 999\nthreshold_bottom = 999\nreset_bottom = 999\n"
            "[legacy:East]\nthreshold_top = 200\nreset_top = 100\nthreshold_bottom = 201\nreset_bottom = 101\n"
            "[legacy:West]\nthreshold_top = 300\nreset_top = 110\nthreshold_bottom = 301\nreset_bottom = 111\n"
        )
        self.now = datetime(2026, 10, 17, 23, 59, 59, tzinfo=timezone.utc)

    @contextmanager
    def collector_context(self, serial_factory):
        with patch.object(GetDataRaw, "get_base_path", return_value=self.base), \
                patch.object(GetDataRaw.serial, "Serial", side_effect=serial_factory) as serial_mock, \
                patch.object(GetDataRaw, "utc_now", return_value=self.now), \
                patch.object(GetDataRaw.time, "monotonic", return_value=10), \
                patch.object(GetDataRaw, "verify_usb_identity", return_value={}), \
                patch("sys.stdout", new_callable=io.StringIO), \
                patch("sys.stderr", new_callable=io.StringIO):
            yield serial_mock

    def rows(self, label, day="2026-10-17"):
        path = self.base / "data" / "raw" / label / day[:4] / day[:7] / (day + ".txt")
        return list(csv.reader(raw_data_lines(path.read_text().splitlines())))

    def test_labels_keep_case_and_require_explicit_selection(self):
        detectors = get_detectors(self.base)
        self.assertEqual(list(detectors), ["East", "West"])
        self.assertEqual(select_detector(self.base, "East").serial_port, PORT_EAST)
        for label in (None, "east", "unknown"):
            with self.subTest(label=label), self.assertRaises(ValueError):
                select_detector(self.base, label)
        with self.assertRaises(ValueError):
            get_usb_options(self.base)

    def test_one_named_detector_still_requires_selection(self):
        self.usb.write_text(
            f"[detectors]\nEast = {PORT_EAST}\n[detector:East]\nid_serial_short = EAST\n"
        )
        with self.assertRaises(ValueError):
            select_detector(self.base, None)

    def test_single_configuration_and_defaults_remain_compatible(self):
        self.usb.write_text(BASE_CONFIG + "[detectors]\n")
        self.assertEqual(get_detectors(self.base), {})
        self.assertIsNone(select_detector(self.base, None))
        self.assertEqual(get_usb_options(self.base)["label"], "historic")
        self.usb.unlink()
        self.assertEqual(get_usb_options(self.base)["serial_port"], "/dev/ttyACM0")

    def test_label_validation(self):
        for label in ("", "../other", "two words", "x" * 17, "rejected", "Rejected", "single", "_unit"):
            with self.subTest(label=label), self.assertRaises(ValueError):
                validate_label(label)
        for label in ("unit_1", "Roof-East", "123"):
            self.assertEqual(validate_label(label), label)

    def test_invalid_configuration_is_rejected(self):
        cases = (
            MULTI_CONFIG.replace(PORT_WEST, PORT_EAST),
            MULTI_CONFIG.replace("id_serial_short = WEST", "id_serial_short = EAST"),
            MULTI_CONFIG.replace(PORT_WEST, "/dev/ttyACM1"),
            MULTI_CONFIG.replace("West = ", "east = "),
            MULTI_CONFIG.replace("id_serial_short = WEST", "id_serial_short = "),
            MULTI_CONFIG.replace("detector_name = West detector", "detector_name = East detector"),
            MULTI_CONFIG + "[detector:OldLabel]\nid_serial_short = OLD\n",
            MULTI_CONFIG.replace("id_serial_short = WEST", "id_serial_shrot = WEST"),
            MULTI_CONFIG + "[DEFAULT]\nid_serial_short = SHARED\n",
        )
        for config in cases:
            with self.subTest(config=config):
                self.usb.write_text(config)
                with self.assertRaises(ValueError):
                    get_detectors(self.base)

    def test_aliases_resolving_to_same_physical_device_are_rejected(self):
        with patch("picomuon_detectors.os.path.realpath", return_value="/dev/ttyACM7"):
            with self.assertRaisesRegex(ValueError, "Duplicate physical"):
                get_detectors(self.base)

    def test_named_settings_do_not_inherit_single_defaults(self):
        self.assertEqual(load_legacy_settings(self.base), (999, 999, 999, 999))
        self.assertEqual(load_legacy_settings(self.base, "East"), (200, 100, 201, 101))
        self.assertEqual(load_legacy_settings(self.base, "West"), (300, 110, 301, 111))
        with self.assertRaisesRegex(ValueError, "legacy:Missing"):
            load_legacy_settings(self.base, "Missing")
        text = (self.config / "legacy.ini").read_text()
        (self.config / "legacy.ini").write_text(text.replace("threshold_top = 200\n", ""))
        with self.assertRaises(ValueError):
            load_legacy_settings(self.base, "East")
        (self.config / "legacy.ini").write_text(text + "[DEFAULT]\nthreshold_top = 250\n")
        with self.assertRaisesRegex(ValueError, "DEFAULT"):
            load_legacy_settings(self.base, "East")

    def test_named_extended_firmware_never_needs_legacy_settings(self):
        (self.config / "legacy.ini").unlink()
        path = self.base / "named.txt"
        with path.open("w") as handle:
            RawEventWriter(self.base, detector_label="East").write(
                handle, "2026-10-17 00:00:00.000000", PAYLOAD + ",500,200,500,200",
            )
        meta = metadata_from_raw(path)["segments"][0]
        self.assertEqual(meta["settings_source"], "unknown")
        self.assertEqual(meta["settings"]["threshold_top"], 500)
        self.assertNotIn("# picomuon_metadata:", path.read_text())

    def test_registration_is_atomic_preserves_comments_and_other_units(self):
        self.usb.write_text(BASE_CONFIG)
        identities = {"ID_SERIAL_SHORT": "EAST"}
        exists = os.path.exists
        real_path = os.path.realpath
        with patch("ConfigureUSB.os.path.exists", side_effect=lambda path: str(path).startswith("/dev/") or exists(path)), \
                patch("ConfigureUSB.os.path.realpath", side_effect=lambda path: PORT_EAST if str(path).startswith("/dev/") else real_path(path)), \
                patch("ConfigureUSB.get_usb_identity", return_value=identities):
            configure_detector("/dev/ttyACM0", str(self.usb), "East", PORT_EAST, "East detector")
        identities = {"ID_SERIAL_SHORT": "WEST"}
        # Realpath is shared by ConfigureUSB and the config validator; preserve
        # distinct resolved ports while proving /dev/ttyACM1 aliases West.
        def realpath(path):
            return real_path(PORT_WEST) if path == "/dev/ttyACM1" else real_path(path)
        with patch("ConfigureUSB.os.path.exists", side_effect=lambda path: str(path).startswith("/dev/") or exists(path)), \
                patch("ConfigureUSB.os.path.realpath", side_effect=realpath), \
                patch("ConfigureUSB.get_usb_identity", return_value=identities):
            configure_detector("/dev/ttyACM1", str(self.usb), "West", PORT_WEST, "West detector")
        parser = read_usb_config(self.usb)
        self.assertEqual(list(get_detectors(self.base)), ["East", "West"])
        self.assertEqual(parser.get("usb", "label"), "historic")
        self.assertIn("# Existing comments", self.usb.read_text())
        before = self.usb.read_bytes()
        with patch("ConfigureUSB.os.path.exists", side_effect=lambda path: str(path).startswith("/dev/") or exists(path)), \
                patch("ConfigureUSB.os.path.realpath", side_effect=realpath), \
                patch("ConfigureUSB.get_usb_identity", return_value={"ID_SERIAL_SHORT": "EAST"}):
            with self.assertRaisesRegex(ValueError, "Duplicate USB"):
                configure_detector("/dev/ttyACM1", str(self.usb), "West", PORT_WEST)
        self.assertEqual(self.usb.read_bytes(), before)
        self.assertEqual({path.name for path in self.config.iterdir()}, {"USB.ini", "legacy.ini"})

    def test_registration_rejects_alias_pointing_at_wrong_device(self):
        before = self.usb.read_bytes()
        with patch("ConfigureUSB.os.path.exists", return_value=True):
            with self.assertRaisesRegex(ValueError, "does not resolve"):
                configure_detector("/dev/ttyACM0", str(self.usb), "East", PORT_WEST)
        self.assertEqual(self.usb.read_bytes(), before)

    def test_registration_cannot_rename_existing_identity_implicitly(self):
        before = self.usb.read_bytes()
        exists = os.path.exists
        with patch("ConfigureUSB.os.path.exists", side_effect=lambda path: str(path).startswith("/dev/") or exists(path)), \
                patch("ConfigureUSB.os.path.realpath", side_effect=lambda path: str(path)), \
                patch("ConfigureUSB.get_usb_identity", return_value={"ID_SERIAL_SHORT": "EAST"}):
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                configure_detector(PORT_EAST, str(self.usb), "NewName", PORT_EAST)
        self.assertEqual(self.usb.read_bytes(), before)

    def test_single_editor_does_not_overwrite_named_configuration(self):
        before = self.usb.read_bytes()
        with self.assertRaisesRegex(ValueError, "use --register"):
            configure_usb("/dev/ttyACM0", str(self.usb))
        self.assertEqual(self.usb.read_bytes(), before)

    def test_identity_mismatch_never_opens_a_serial_port(self):
        with self.collector_context(lambda **kwargs: None) as serial_mock, \
                patch.object(GetDataRaw, "verify_usb_identity", side_effect=RuntimeError("wrong USB")), \
                patch.object(GetDataRaw.time, "sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                GetDataRaw.main("East")
        serial_mock.assert_not_called()
        self.assertFalse((self.base / "data").exists())

    def test_missing_named_legacy_settings_do_not_block_another_unit(self):
        legacy = self.config / "legacy.ini"
        legacy.write_text(legacy.read_text().replace("[legacy:East]", "[legacy:OldEast]"))
        east = MagicMock()
        east.__enter__.return_value = east
        east.readline.side_effect = [b"startup\n", PAYLOAD.encode()]
        west = MagicMock()
        west.__enter__.return_value = west
        west.readline.side_effect = [
            b"startup\n", PAYLOAD.replace("East detector", "West detector").encode(), KeyboardInterrupt,
        ]
        with self.collector_context(lambda **kwargs: east if kwargs["port"] == PORT_EAST else west):
            with self.assertRaises(SystemExit):
                GetDataRaw.main("East")
            with self.assertRaises(KeyboardInterrupt):
                GetDataRaw.main("West")
        self.assertEqual(self.rows("East"), [])
        self.assertEqual(self.rows("West")[0][-4:], ["300", "110", "301", "111"])

    def test_cable_swap_name_is_rejected_but_metadata_rename_is_allowed(self):
        detectors = get_detectors(self.base)
        check_detector_name("Renamed detector", detectors["East"], detectors)
        with self.assertRaisesRegex(RuntimeError, "cable swap"):
            check_detector_name("West detector", detectors["East"], detectors)
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.readline.side_effect = [
            b"startup\n", PAYLOAD.replace("East detector", "West detector").encode(),
        ]
        with self.collector_context(lambda **kwargs: connection):
            with self.assertRaises(SystemExit):
                GetDataRaw.main("East")
        self.assertEqual(self.rows("East"), [])

    def test_two_streams_with_independent_reconnect_and_utc_rollover(self):
        disconnected = threading.Event()
        west_progress = threading.Event()
        east_resumed = threading.Event()
        failures = []
        sessions = {"East": 0, "West": 0}
        calls = []
        midnight = datetime(2026, 10, 18, 0, 0, 1, tzinfo=timezone.utc)
        times = {
            "East": iter([self.now, midnight, midnight]),
            "West": iter([self.now, self.now, self.now, midnight]),
        }

        def wait_for(event):
            if not event.wait(5):
                raise AssertionError("Concurrent collector test synchronization timed out")

        def factory(**kwargs):
            label = "East" if kwargs["port"] == PORT_EAST else "West"
            sessions[label] += 1
            calls.append(kwargs)
            connection = MagicMock()
            connection.__enter__.return_value = connection
            session = sessions[label]
            reads = iter(range(10))

            def readline():
                index = next(reads)
                if index == 0:
                    return b"startup\n"
                if label == "East":
                    if session == 1 and index == 2:
                        disconnected.set()
                        raise GetDataRaw.serial.SerialException("East unplugged")
                    if index == 1:
                        return PAYLOAD.encode()
                    east_resumed.set()
                    raise KeyboardInterrupt
                if index == 1:
                    wait_for(disconnected)
                elif index == 2:
                    west_progress.set()
                elif index == 3:
                    wait_for(east_resumed)
                    return b"malformed\n"
                else:
                    raise KeyboardInterrupt
                return PAYLOAD.replace("East detector", "West detector").encode()

            connection.readline.side_effect = readline
            return connection

        def sleep(delay):
            wait_for(west_progress)

        def worker(label):
            try:
                GetDataRaw.main(label)
            except KeyboardInterrupt:
                pass
            except BaseException as exc:
                failures.append(exc)

        with self.collector_context(factory), \
                patch.object(GetDataRaw, "utc_now", side_effect=lambda: next(times[threading.current_thread().name])), \
                patch.object(GetDataRaw.time, "sleep", side_effect=sleep):
            threads = [threading.Thread(target=worker, args=(label,), name=label, daemon=True)
                       for label in ("East", "West")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(failures, [])
        self.assertEqual(sessions, {"East": 2, "West": 1})
        self.assertTrue(all(call["exclusive"] for call in calls))
        for label, expected in (("East", ["200", "100", "201", "101"]),
                                ("West", ["300", "110", "301", "111"])):
            self.assertEqual(self.rows(label)[0][-4:], expected)
        self.assertEqual(self.rows("East", "2026-10-18")[0][-4:], ["200", "100", "201", "101"])
        self.assertEqual(len(self.rows("West")), 2)
        status_root = self.base / "data" / "status"
        self.assertEqual(json.loads((status_root / "East" / "current.json").read_text())["detector_name"], "East detector")
        self.assertEqual(json.loads((status_root / "West" / "current.json").read_text())["detector_name"], "West detector")
        self.assertFalse((status_root / "current.json").exists())
        rejected = self.base / "data" / "raw" / "West" / "rejected" / "2026-10-18.txt"
        self.assertIn("malformed", rejected.read_text())
        self.assertFalse((self.base / "data" / "raw" / "rejected").exists())

    def test_swapped_acm_numbers_do_not_change_selected_by_id_ports(self):
        # Enumeration is deliberately reversed: selection still uses the
        # configured aliases, never the order of /dev/ttyACM*.
        with patch("picomuon_detectors.os.path.realpath", side_effect=lambda port: {
            PORT_EAST: "/dev/ttyACM1", PORT_WEST: "/dev/ttyACM0",
        }.get(port, str(port))):
            self.assertEqual(select_detector(self.base, "East").serial_port, PORT_EAST)
            self.assertEqual(select_detector(self.base, "West").serial_port, PORT_WEST)

    @unittest.skipUnless(os.name == "posix", "POSIX pseudo-terminal/exclusive access check runs on the RPi")
    def test_exclusive_serial_access_rejects_second_collector(self):
        import serial

        master, slave = os.openpty()
        try:
            name = os.ttyname(slave)
            with serial.Serial(name, exclusive=True):
                with self.assertRaises(serial.SerialException):
                    with serial.Serial(name, exclusive=True):
                        self.fail("Second exclusive collector must not open the same serial device")
        finally:
            os.close(slave)
            os.close(master)

    def test_processing_fails_closed_until_multi_pipeline_is_ready(self):
        with patch("sys.stdout", new_callable=io.StringIO):
            for operation in (
                lambda: process_daily(date(2026, 10, 17), self.base),
                lambda: process_period_data("week", date(2026, 10, 17), self.base),
            ):
                with self.assertRaisesRegex(ValueError, "Multi-detector"):
                    operation()
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        with patch.dict(os.environ, {"PICOMUON_BASE_PATH": str(self.base)}):
            for name in ("Adc", "Cpm", "Day", "Week", "Month"):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Multi-detector"):
                    runpy.run_path(str(scripts / f"ProcessData{name}ACM0.py"), run_name="__main__")
        self.assertFalse((self.base / "data").exists())


if __name__ == "__main__":
    unittest.main()
