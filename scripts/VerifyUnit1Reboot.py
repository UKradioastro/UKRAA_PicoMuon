#!/usr/bin/env python3
"""Read-only Unit_1 reboot acceptance: --baseline before a Pi reboot, --verify DIR after it."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import sys
import tempfile

import TrialUnit1Collection as trial
from TrialUnit1Collection import data, require, save_json

staging = trial.staging
OLD, NAMED = trial.OLD, trial.NAMED
KIND = "unit1-reboot-check-v1"
PREFIX = "unit1-reboot-check."
LABEL = "Unit_1"
COLLECTOR = f"GetDataRaw.py[{LABEL}]".encode()
SAMPLE_SECONDS = 10
MAX_STATUS_AGE_SECONDS = 15
# Boot, udev by-id creation and the collector's reconnect backoff must finish within this.
MAX_START_SECONDS = 180
LOCAL_HOURS = (4, 23)  # Keep clear of the 01:15 local daily processing run.
FATAL_ERRORS = (b"refusing possible cable swap", b"Cannot record detector metadata", b"Traceback")
FAILURES = (OSError, ValueError, RuntimeError, KeyError, csv.Error, KeyboardInterrupt)
PASSED = "REBOOT_ACCEPTED"
RECORDED = "BASELINE_RECORDED"


def parse_stamp(value: str, pattern: str = "%Y-%m-%d %H:%M:%S.%f") -> datetime:
    return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)


def complete(content: bytes) -> bytes:
    return content[:content.rfind(b"\n") + 1]


def raw_rows(content: bytes, detector_name: str) -> list[datetime]:
    """Timestamps of complete appended rows; a header here means the file was recreated."""
    stamps: list[datetime] = []
    for line in complete(content).decode("utf-8").splitlines():
        require(not line.startswith(("#", "RPiTimestamp")),
                "A header was written into the existing raw file after the baseline.")
        row = next(csv.reader([line], strict=True))
        require(len(row) == 13, f"Unexpected raw column count after the baseline: {line[:80]!r}")
        require(row[8] == detector_name, f"Unexpected detector name in raw data: {row[8]!r}")
        stamp = parse_stamp(row[0])
        require(not stamps or stamp >= stamps[-1], f"Raw timestamps go backwards at {row[0]}.")
        stamps.append(stamp)
    return stamps


def collector_lines(content: bytes) -> list[tuple[datetime, bytes]]:
    result = []
    for line in content.splitlines():
        if COLLECTOR in line:
            result.append((parse_stamp(line[:23].decode("ascii"), "%Y-%m-%d %H:%M:%S UTC"), line))
    return result


class Host(trial.Host):
    def boot_id(self) -> str:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()

    def boot_time(self) -> datetime:
        for line in Path("/proc/stat").read_text(encoding="ascii").splitlines():
            if line.startswith("btime "):
                return datetime.fromtimestamp(int(line.split()[1]), timezone.utc)
        raise RuntimeError("Boot time is unavailable in /proc/stat.")

    def resolve(self, path: str) -> str:
        return os.path.realpath(path)

    def local_hour(self) -> int:
        return datetime.now().hour


class RebootCheck:
    def __init__(self, home: Path, evidence: Path, host: Host):
        self.base = home / "UKRAA_PicoMuon"
        self.evidence, self.host = evidence, host
        self.logs = self.base / "logfiles/detectors" / LABEL
        self.status = self.base / "data/status" / LABEL / "current.json"

    def raw(self, day: str) -> Path:
        return self.base / "data/raw" / LABEL / day[:4] / day[:7] / f"{day}.txt"

    def rejected(self, day: str) -> Path:
        return self.base / "data/raw" / LABEL / "rejected" / f"{day}.txt"

    def size(self, path: Path) -> int:
        return len(data(path)) if path.exists() else 0

    def properties(self, unit: str) -> dict[str, str]:
        output = self.host.run("systemctl", "show", unit, "--no-pager",
                               *(f"--property={key}" for key in trial.PROPERTIES))
        result = dict(line.split("=", 1) for line in output.decode().splitlines() if "=" in line)
        require(all(key in result for key in trial.PROPERTIES), f"Incomplete systemd properties: {unit}")
        return result

    def sample(self, day: str) -> dict:
        status = json.loads(data(self.status))
        age = (self.host.now() - parse_stamp(status["updated_at"], "%Y-%m-%d %H:%M:%S UTC")).total_seconds()
        require(0 <= age <= MAX_STATUS_AGE_SECONDS, f"{LABEL} status is stale ({age:.0f} s old).")
        return {"raw_bytes": len(complete(data(self.raw(day)))), "status": status}

    def live(self) -> dict:
        """Checks that must hold both before and after the reboot."""
        now = self.host.now()
        hour = self.host.local_hour()
        require(LOCAL_HOURS[0] <= hour < LOCAL_HOURS[1],
                "Run between 04:00 and 22:59 local time, away from the 01:15 daily processing.")
        day = now.date().isoformat()
        old, named = self.properties(OLD), self.properties(NAMED)
        require(old["UnitFileState"] == "disabled" and old["ActiveState"] == "inactive"
                and old["MainPID"] == "0", f"{OLD} must be disabled and stopped.")
        require(named["UnitFileState"] == "enabled", f"{NAMED} is not enabled at boot.")
        require(named["ActiveState"] == "active" and named["SubState"] == "running"
                and int(named["MainPID"]) > 0, f"{NAMED} is not running.")
        pid = int(named["MainPID"])
        output = self.host.run("udevadm", "info", "--query=property", f"--name={staging.DEVICE}")
        udev = dict(line.split("=", 1) for line in output.decode().splitlines() if "=" in line)
        require(udev.get("ID_SERIAL") == staging.IDENTITY and udev.get("ID_SERIAL_SHORT") == staging.SHORT_ID,
                "Unit_1 USB identity mismatch.")
        require(self.host.holders(staging.DEVICE) == {pid}, "Unit_1 serial port is not owned only by the collector.")
        processes = self.host.run("ps", "-eo", "pid=,args=", "--width", "500").decode().splitlines()
        collectors = [line.split()[0] for line in processes if "GetDataRaw" in line]
        require(collectors == [str(pid)], f"Unexpected collector processes: {collectors}")
        cron = self.host.run("sudo", "-n", "crontab", "-l")
        require(cron.splitlines().count(trial.DAILY) == 1 and trial.HOLD not in cron,
                "Daily processing cron entry is missing or held.")
        synced = self.host.run("timedatectl", "show", "--property=NTPSynchronized", "--value").strip()
        require(synced == b"yes", "System clock is not NTP-synchronised; event timestamps may be wrong.")
        first = self.sample(day)
        self.host.sleep(SAMPLE_SECONDS)
        second = self.sample(day)
        require(second["raw_bytes"] > first["raw_bytes"], f"{LABEL} raw data is not advancing.")
        return {
            "utc": now.isoformat(), "day": day, "pid": pid, "nrestarts": named["NRestarts"],
            "device": self.host.resolve(staging.DEVICE), "cron_sha256": staging.digest(cron),
            "detector_name": second["status"]["detector_name"],
            "boot_id": self.host.boot_id(), "boot_time": self.host.boot_time().isoformat(),
        }

    def baseline(self) -> dict:
        state = self.live()
        content = complete(data(self.raw(state["day"])))
        stamps = raw_rows(content[content.rfind(b"\n", 0, len(content) - 1) + 1:], state["detector_name"])
        state.update(
            kind=KIND, status=RECORDED, raw_bytes=len(content), raw_sha256=staging.digest(content),
            last_event=stamps[-1].isoformat(),
            rejected_bytes=self.size(self.rejected(state["day"])),
            log_bytes=self.size(self.logs / "log-PicoMuon.txt"),
            error_bytes=self.size(self.logs / "log-error.txt"),
        )
        save_json(self.evidence / "baseline.json", state)
        return state

    def verify(self, before: dict) -> dict:
        require(before.get("kind") == KIND and before.get("status") == RECORDED, "Not a reboot baseline.")
        booted = self.host.boot_time()
        require(self.host.boot_id() != before["boot_id"],
                "No reboot since the baseline (same boot ID). Reboot, then verify.")
        require(booted > datetime.fromisoformat(before["utc"]), "Boot time is not after the baseline.")
        require(self.host.now().date().isoformat() == before["day"],
                "Verify on the baseline's UTC day; otherwise take a new baseline and reboot again.")
        state = self.live()
        require(state["pid"] != before["pid"], "Collector PID unchanged across the reboot.")
        require(state["nrestarts"] == "0", f"{NAMED} restarted after boot; review its journal.")
        require(state["cron_sha256"] == before["cron_sha256"], "Root crontab changed since the baseline.")
        require(state["detector_name"] == before["detector_name"], "Detector name changed since the baseline.")

        content = complete(data(self.raw(before["day"])))
        require(staging.digest(content[:before["raw_bytes"]]) == before["raw_sha256"],
                "Pre-reboot raw data changed; it must only be appended to.")
        stamps = raw_rows(content[before["raw_bytes"]:], before["detector_name"])
        after = [stamp for stamp in stamps if stamp >= booted]
        require(after, "No events recorded after boot.")
        last_before = max([stamp for stamp in stamps if stamp < booted],
                          default=datetime.fromisoformat(before["last_event"]))
        start_delay = (after[0] - booted).total_seconds()
        require(start_delay <= MAX_START_SECONDS,
                f"First post-boot event {start_delay:.0f} s after boot (limit {MAX_START_SECONDS} s).")

        require(self.size(self.rejected(before["day"])) == before["rejected_bytes"],
                "New rejected rows since the baseline; review the rejected file.")
        added = {}
        for name, key in (("log-PicoMuon.txt", "log_bytes"), ("log-error.txt", "error_bytes")):
            current = data(self.logs / name) if (self.logs / name).exists() else b""
            require(len(current) >= before[key], f"{name} shrank (rotated?) since the baseline; review.")
            added[name] = current[before[key]:]
        fatal = [line for line in added["log-error.txt"].splitlines()
                 if any(marker in line for marker in FATAL_ERRORS)]
        if fatal:
            raise RuntimeError(f"Errors after the reboot: {fatal[0].decode(errors='replace')}")
        errors = [line for _, line in collector_lines(added["log-error.txt"])]
        logs = {"log-PicoMuon.txt": collector_lines(added["log-PicoMuon.txt"])}
        starts = [stamp for stamp, line in logs["log-PicoMuon.txt"] if b"Starting raw data collector" in line]
        connects = [stamp for stamp, line in logs["log-PicoMuon.txt"] if b"Connected to serial port" in line]
        require(starts and connects, "No collector start/connect lines logged since the baseline.")
        # Log times are truncated to whole seconds; an earlier start means the clock was not yet set.
        require(starts[-1] >= booted - timedelta(seconds=2),
                f"Collector started at {starts[-1]:%H:%M:%S} UTC by its own clock, before the boot time "
                f"{booted:%H:%M:%S}: early post-boot rows may carry wrong timestamps.")
        result = {
            "status": PASSED, "kind": KIND, "baseline_utc": before["utc"], "boot_time": booted.isoformat(),
            "old_pid": before["pid"], "new_pid": state["pid"],
            "device_before": before["device"], "device_after": state["device"],
            "last_event_before_reboot": last_before.isoformat(),
            "first_event_after_boot": after[0].isoformat(),
            "collection_gap_seconds": round((after[0] - last_before).total_seconds(), 1),
            "first_event_after_boot_seconds": round(start_delay, 1),
            "events_since_boot": len(after),
            "collector_start": starts[-1].isoformat(), "collector_connected": connects[-1].isoformat(),
            "collector_error_lines": [line.decode(errors="replace") for line in errors],
        }
        save_json(self.evidence / "verification.json", result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--baseline", action="store_true", help="Record the pre-reboot state (read-only).")
    modes.add_argument("--verify", type=Path, help="Compare the post-reboot state with this baseline directory.")
    args = parser.parse_args()
    if sys.platform != "linux" or os.getuid() == 0 or Path.home() != Path("/home/pi"):
        parser.error("Run on the production Pi as pi, without sudo.")
    if args.verify and not (args.verify.parent == Path.home() and args.verify.name.startswith(PREFIX)
                            and args.verify.is_dir() and not args.verify.is_symlink()
                            and (args.verify / "baseline.json").is_file()):
        parser.error("Invalid baseline directory; use the one printed by --baseline.")
    os.umask(0o077)
    import fcntl
    # Never run beside another Unit_1 runner.
    lock = os.open(Path.home() / ".unit1-collection-trial.lock", os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        parser.error("Another Unit_1 runner is active.")
    evidence = args.verify or Path(tempfile.mkdtemp(prefix=PREFIX, dir=Path.home()))
    host = Host(evidence)
    host.sequence = len(list(evidence.glob("command-*.argv.json")))
    check = RebootCheck(Path.home(), evidence, host)
    signal.signal(signal.SIGTERM, trial.interrupted)
    signal.signal(signal.SIGHUP, trial.interrupted)
    print(f"EVIDENCE DIRECTORY: {evidence}\nREAD-ONLY: no service, config, cron or data changes.", flush=True)
    try:
        if args.verify:
            result = check.verify(json.loads(data(evidence / "baseline.json")))
            print(f"{PASSED}: collector PID {result['old_pid']} -> {result['new_pid']}, "
                  f"first event {result['first_event_after_boot_seconds']} s after boot, "
                  f"collection gap {result['collection_gap_seconds']} s, "
                  f"{result['events_since_boot']} events since boot.")
            for line in result["collector_error_lines"]:
                print(f"  logged during reconnect: {line}")
        else:
            state = check.baseline()
            print(f"{RECORDED}: PID {state['pid']}, last event {state['last_event']}.\n"
                  f"Now run: sudo reboot\nAfter about 3 minutes, log in and run:\n"
                  f"  python3 -B \"$HOME/VerifyUnit1Reboot.py\" --verify {evidence}")
        return 0
    except FAILURES as exc:
        save_json(evidence / ("verify-failure.json" if args.verify else "baseline-failure.json"),
                  {"error": str(exc), "utc": host.now().isoformat()})
        print(f"FAILED: {exc}\nNo changes were made. Preserve {evidence} for review.", file=sys.stderr)
        return 1
    finally:
        os.close(lock)


if __name__ == "__main__":
    raise SystemExit(main())
