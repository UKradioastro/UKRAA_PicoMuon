from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import VerifyUnit1Reboot as reboot

staging = reboot.staging
NAME = "56/148/627"
DAY = "2026-10-26"
START = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)
CRON = b"0 4 * * 0 rotate\n" + reboot.trial.DAILY + b"\n"


def log_line(stamp: datetime, message: str) -> str:
    return f"{stamp:%Y-%m-%d %H:%M:%S} UTC : GetDataRaw.py[Unit_1]      : {message}\n"


class FakeHost:
    def __init__(self, check_base: Path):
        self.base = check_base
        self.current = START
        self.boot = START - timedelta(days=2)
        self.identity = "boot-a"
        self.pid = 1716198
        self.old_state = ("disabled", "inactive", "0")
        self.cron = CRON
        self.synced = b"yes\n"
        self.commands = []

    def run(self, *command, allowed=(0,), timeout=60):
        self.commands.append(command)
        if command[:2] == ("systemctl", "show"):
            if command[2] == reboot.OLD:
                state, active, pid = self.old_state
                values = {"UnitFileState": state, "ActiveState": active, "SubState": "dead", "MainPID": pid}
            else:
                values = {"UnitFileState": "enabled", "ActiveState": "active", "SubState": "running",
                          "MainPID": str(self.pid)}
            values.setdefault("NRestarts", "0")
            return "".join(f"{key}={values.get(key, '')}\n" for key in reboot.trial.PROPERTIES).encode()
        if command[0] == "udevadm":
            return f"ID_SERIAL={staging.IDENTITY}\nID_SERIAL_SHORT={staging.SHORT_ID}\n".encode()
        if command[0] == "ps":
            return f"  1 /sbin/init\n{self.pid} /usr/bin/python3 GetDataRaw.py --detector Unit_1\n".encode()
        if command[:2] == ("sudo", "-n"):
            return self.cron
        if command[0] == "timedatectl":
            return self.synced
        raise AssertionError(f"Unexpected command: {command}")

    def holders(self, device):
        return {self.pid}

    def now(self):
        return self.current

    def sleep(self, seconds):
        self.current += timedelta(seconds=seconds)
        self.event()

    def event(self, stamp=None):
        stamp = stamp or self.current
        path = self.base / "data/raw/Unit_1/2026/2026-10" / f"{DAY}.txt"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{stamp:%Y-%m-%d %H:%M:%S.%f},T,1,100,1,0,23.0,1004.6,{NAME},200,100,200,100\n")
        status = {"updated_at": f"{stamp:%Y-%m-%d %H:%M:%S} UTC", "detector_name": NAME}
        (self.base / "data/status/Unit_1/current.json").write_text(json.dumps(status), encoding="utf-8")

    def boot_id(self):
        return self.identity

    def boot_time(self):
        return self.boot

    def resolve(self, path):
        return "/dev/ttyACM0"

    def local_hour(self):
        return self.current.hour


class RebootCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.base = self.home / "UKRAA_PicoMuon"
        self.evidence = self.home / "unit1-reboot-check.test"
        for folder in ("data/raw/Unit_1/2026/2026-10", "data/raw/Unit_1/rejected", "data/status/Unit_1",
                       "logfiles/detectors/Unit_1", "unit1-reboot-check.test"):
            (self.home / ("" if folder.startswith("unit1") else "UKRAA_PicoMuon") / folder).mkdir(parents=True)
        self.raw = self.base / "data/raw/Unit_1/2026/2026-10" / f"{DAY}.txt"
        self.raw.write_text("RPiTimestamp,Event\n", encoding="utf-8")
        self.log = self.base / "logfiles/detectors/Unit_1/log-PicoMuon.txt"
        self.errors = self.base / "logfiles/detectors/Unit_1/log-error.txt"
        self.log.write_text(log_line(START - timedelta(days=2), "Starting raw data collector"), encoding="utf-8")
        self.errors.write_text("", encoding="utf-8")
        self.host = FakeHost(self.base)
        self.host.event(START - timedelta(seconds=1))
        self.check = reboot.RebootCheck(self.home, self.evidence, self.host)

    def tearDown(self):
        self.temp.cleanup()

    def append(self, path: Path, text: str):
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def simulate_reboot(self, *, delay=40, start_offset=5, header=False):
        """Collector runs a minute after the baseline, then the Pi reboots and collection resumes."""
        self.host.event(self.host.current + timedelta(seconds=60))
        self.host.boot = self.host.current + timedelta(seconds=90)
        self.host.identity = "boot-b"
        self.host.pid = 812
        if header:
            self.append(self.raw, "RPiTimestamp,Event\n")
        self.append(self.log, log_line(self.host.boot + timedelta(seconds=start_offset), "Starting raw data collector"))
        self.append(self.errors, log_line(self.host.boot + timedelta(seconds=8),
                                          "USB identity check failed: Unable to read USB identity"))
        self.append(self.log, log_line(self.host.boot + timedelta(seconds=12), "Connected to serial port"))
        self.host.current = self.host.boot + timedelta(seconds=delay)
        self.host.event()
        self.host.current += timedelta(seconds=150)
        self.host.event()

    def baseline(self):
        return self.check.baseline()

    def test_baseline_records_state_without_mutating_commands(self):
        state = self.baseline()
        self.assertEqual(state["status"], reboot.RECORDED)
        self.assertEqual(state["pid"], 1716198)
        self.assertEqual(state["device"], "/dev/ttyACM0")
        self.assertTrue((self.evidence / "baseline.json").is_file())
        for command in self.host.commands:
            self.assertFalse(any(word in ("start", "stop", "restart", "enable", "disable", "reboot")
                                 for word in command), command)
            if command[0] == "sudo":
                self.assertEqual(command, ("sudo", "-n", "crontab", "-l"))

    def test_successful_reboot_is_accepted(self):
        before = self.baseline()
        self.simulate_reboot()
        result = self.check.verify(before)
        self.assertEqual(result["status"], reboot.PASSED)
        self.assertEqual((result["old_pid"], result["new_pid"]), (1716198, 812))
        self.assertEqual(result["first_event_after_boot_seconds"], 40)
        self.assertEqual(result["collection_gap_seconds"], 70)
        self.assertEqual(result["events_since_boot"], 3)
        self.assertEqual(len(result["collector_error_lines"]), 1)
        self.assertTrue((self.evidence / "verification.json").is_file())

    def assert_rejected(self, before, message):
        with self.assertRaisesRegex(RuntimeError, message):
            self.check.verify(before)

    def test_requires_an_actual_reboot(self):
        before = self.baseline()
        self.host.current += timedelta(minutes=5)
        self.host.event()
        self.assert_rejected(before, "No reboot")

    def test_old_service_enabled_after_boot_is_rejected(self):
        before = self.baseline()
        self.simulate_reboot()
        self.host.old_state = ("enabled", "inactive", "0")
        self.assert_rejected(before, "must be disabled")

    def test_changed_pre_reboot_raw_is_rejected(self):
        before = self.baseline()
        self.simulate_reboot()
        content = self.raw.read_bytes()
        self.raw.write_bytes(content.replace(b"1004.6", b"1004.7", 1))
        self.assert_rejected(before, "only be appended")

    def test_header_written_again_is_rejected(self):
        before = self.baseline()
        self.simulate_reboot(header=True)
        self.assert_rejected(before, "header")

    def test_slow_start_is_rejected(self):
        before = self.baseline()
        self.simulate_reboot(delay=reboot.MAX_START_SECONDS + 30)
        self.assert_rejected(before, "after boot")

    def test_collector_started_before_clock_sync_is_rejected(self):
        before = self.baseline()
        self.simulate_reboot(start_offset=-60)
        self.assert_rejected(before, "wrong timestamps")

    def test_new_rejected_rows_are_rejected(self):
        before = self.baseline()
        self.simulate_reboot()
        (self.base / "data/raw/Unit_1/rejected" / f"{DAY}.txt").write_text("junk\n", encoding="utf-8")
        self.assert_rejected(before, "rejected rows")

    def test_cable_swap_error_is_rejected(self):
        before = self.baseline()
        self.simulate_reboot()
        self.append(self.errors, log_line(self.host.current, "name registered to Unit_2; refusing possible cable swap"))
        self.assert_rejected(before, "cable swap")

    def test_held_or_changed_cron_is_rejected(self):
        before = self.baseline()
        self.simulate_reboot()
        self.host.cron = CRON.replace(reboot.trial.DAILY, reboot.trial.HOLD + reboot.trial.DAILY)
        self.assert_rejected(before, "missing or held")

    def test_unsynchronised_clock_is_rejected(self):
        before = self.baseline()
        self.simulate_reboot()
        self.host.synced = b"no\n"
        self.assert_rejected(before, "NTP")

    def test_verify_on_another_utc_day_is_rejected(self):
        before = self.baseline()
        self.simulate_reboot()
        self.host.current += timedelta(days=1)
        self.assert_rejected(before, "UTC day")

    def test_daily_processing_window_is_refused(self):
        self.host.current = START.replace(hour=1)
        with self.assertRaisesRegex(RuntimeError, "04:00"):
            self.baseline()


if __name__ == "__main__":
    unittest.main()
