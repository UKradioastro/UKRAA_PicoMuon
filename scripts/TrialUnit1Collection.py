#!/usr/bin/env python3
"""Fixed Unit_1 attended trial. Default: check only. No boot or processing changes."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Iterator

import StageUnit1Cutover as staging

STAGE_INDEX = "f157f77361977b7081c09870283740b38984af349acafeb4fde2a9600c0c1a73"
STAGE_REPORT = "8ff2a3699a34b8f07c3c1e34c91997af9bf4d5e0e2fe4bcbe3bf15a1d1ffd334"
OLD = "PicoMuon.service"
NAMED = "PicoMuon@Unit_1.service"
DAILY = (
    b"15 1 * * * /bin/bash /home/pi/UKRAA_PicoMuon/scripts/runCronJob.sh /bin/bash "
    b"/home/pi/UKRAA_PicoMuon/scripts/processData.sh >> /home/pi/UKRAA_PicoMuon/logfiles/log-PicoMuon.txt"
)
HOLD = b"# UNIT1 COLLECTION-ONLY HOLD: "
APPROVAL = "UNIT1-10MIN-TRIAL-THEN-RECOVER"
CONFIGS = ("USB.ini", "legacy.ini")
CONFIG_MODES = {"USB.ini": 0o644, "legacy.ini": 0o664}
PROPERTIES = (
    "MainPID", "ActiveState", "SubState", "NRestarts", "FragmentPath", "DropInPaths",
    "ExecStart", "Environment", "WorkingDirectory", "User", "Group", "SupplementaryGroups",
    "UnitFileState",
)


def require(condition: bool, message: str) -> None:
    staging.require(condition, message)


def checked_config_mode(name: str, mode: int) -> int:
    expected = CONFIG_MODES[name]
    require(mode == expected,
            f"Unexpected config mode: {name}: got {mode:04o}, reviewed mode is {expected:04o}")
    return mode


def data(path: Path) -> bytes:
    # Reject symlinked ancestors as well as symlinked leaf files.
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), f"Symlink is not allowed: {parent}")
    return staging.regular_bytes(path)


def safe_target(path: Path) -> None:
    for ancestor in (path, *path.parents):
        require(not ancestor.is_symlink(), f"Symlink is not allowed: {ancestor}")


def sync_directory(path: Path) -> None:
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def fingerprint(path: Path) -> str | None:
    if not path.exists() and not path.is_symlink():
        return None
    return staging.digest(data(path))


def save_json(path: Path, value: object) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".writing", dir=path.parent)
    temporary = Path(name)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    sync_directory(path.parent)


def held_cron(original: bytes) -> bytes:
    require(original.splitlines().count(DAILY) == 1 and HOLD not in original,
            "Expected exactly one reviewed daily job and no existing hold.")
    return original.replace(DAILY, HOLD + DAILY)


def parse_events(content: bytes, day: str, *, final: bool) -> dict[str, object]:
    if not content.endswith(b"\n"):
        require(not final, "Incomplete final raw row after collector stopped.")
        content = content[:content.rfind(b"\n") + 1]
    rows = csv.reader(io.StringIO(content.decode("utf-8")), strict=True)
    first = last = None
    count = 0
    for row in rows:
        if row and (row[0] == "RPiTimestamp" or row[0].startswith("#")):
            continue
        require(len(row) == 13, "Unexpected raw event column count.")
        stamp = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
        require(stamp.date().isoformat() == day and (last is None or stamp >= last),
                "Wrong-day or out-of-order named event.")
        require(row[1] in ("T", "B", "C"), "Unexpected event type.")
        require(all(int(row[i]) >= 0 for i in (2, 3, 4, 5)), "Negative event numeric field.")
        require(all(math.isfinite(float(row[i])) for i in (6, 7)), "Nonfinite environment field.")
        require(tuple(map(int, row[9:])) == (200, 100, 200, 100), "Named settings mismatch.")
        first = first or stamp
        last = stamp
        count += 1
    require(count > 0 and first is not None and last is not None, "No complete named events.")
    return {"events": count, "first": first.isoformat(), "last": last.isoformat()}


def last_event(path: Path) -> datetime:
    with path.open("rb") as handle:
        handle.seek(max(0, path.stat().st_size - 65536))
        lines = handle.read().splitlines()
    for line in reversed(lines):
        if line and not line.startswith((b"#", b"RPiTimestamp")):
            value = next(csv.reader([line.decode("utf-8")]))[0]
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
    raise RuntimeError(f"No recent event found in {path}")


class Host:
    def __init__(self, evidence: Path):
        self.evidence = evidence
        self.sequence = 0

    def run(self, *command: str, allowed: tuple[int, ...] = (0,), timeout: int = 60) -> bytes:
        self.sequence += 1
        prefix = self.evidence / f"command-{self.sequence:04d}"
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("PICOMUON_", "PYTHON", "SYSTEMD_", "SUDO_"))}
        environment.update(PATH="/usr/sbin:/usr/bin:/sbin:/bin", LC_ALL="C",
                           SYSTEMD_PAGER="", SYSTEMD_COLORS="0", PYTHONDONTWRITEBYTECODE="1")
        save_json(prefix.with_suffix(".argv.json"), list(command))
        try:
            result = subprocess.run(command, capture_output=True, env=environment,
                                    timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            save_json(prefix.with_suffix(".error.json"), {"error": str(exc)})
            raise RuntimeError(f"Command could not complete: {command}; inspect {prefix}") from exc
        prefix.with_suffix(".stdout").write_bytes(result.stdout)
        prefix.with_suffix(".stderr").write_bytes(result.stderr)
        prefix.with_suffix(".exit").write_text(f"{result.returncode}\n", encoding="ascii")
        require(result.returncode in allowed,
                f"Command failed ({result.returncode}): {command}; inspect {prefix}")
        return result.stdout

    def holders(self, device: str) -> set[int]:
        self.run("sudo", "-n", "test", "-c", device)
        output = self.run("sudo", "-n", "fuser", device, allowed=(0, 1))
        prefix = self.evidence / f"command-{self.sequence:04d}"
        code = int(prefix.with_suffix(".exit").read_text())
        stderr = prefix.with_suffix(".stderr").read_bytes().strip()
        require(code == 0 or (code == 1 and not output.strip() and not stderr),
                "fuser error is not proof of a free port.")
        if code == 1:
            return set()
        labels = {os.fsencode(device) + b":", os.fsencode(Path(device).resolve()) + b":"}
        require(output.strip() != b"" and stderr in labels,
                "Unrecognized fuser result; cannot establish port ownership.")
        require(all(word.isdigit() for word in output.split()), "Unrecognized fuser PID output.")
        pids = {int(word) for word in output.split()}
        require(all(pid > 0 for pid in pids), "Invalid fuser PID output.")
        return pids

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def sleep(self, seconds: int) -> None:
        time.sleep(seconds)

    def ticks(self) -> float:
        return time.monotonic()


class Trial:
    def __init__(self, home: Path, units: Path, evidence: Path, host: Host):
        self.home, self.units, self.evidence, self.host = home, units, evidence, host
        self.base = home / "UKRAA_PicoMuon"
        self.preflight = home / "unit1-cutover-preflight.YtqHwx"
        self.stage = home / "unit1-cutover-stage._u8vl_xk"
        self.rehearsal = home / "unit1-processing-rehearsal.yo2to17p"
        self.state: dict = {"status": "checking", "mutations": [], "completed": [], "history": [],
                            "day": host.now().date().isoformat()}
        self.backup: dict[str, bytes] = {}
        self.hashes: dict[str, str] = {}
        self.reconstruction = evidence / "reconstructed"

    def journal(self, status: str) -> None:
        self.state["status"] = status
        self.state["updated_utc"] = self.host.now().isoformat()
        self.state["history"].append({"status": status, "utc": self.state["updated_utc"]})
        save_json(self.evidence / "state.json", self.state)

    def intent(self, action: str) -> None:
        self.state["mutations"].append(action)
        self.journal(f"intent:{action}")

    def done(self, action: str) -> None:
        self.state["completed"].append(action)
        self.journal(f"done:{action}")

    def properties(self, unit: str) -> dict[str, str]:
        output = self.host.run("systemctl", "show", unit, "--no-pager",
                               *(f"--property={key}" for key in PROPERTIES))
        result = dict(line.split("=", 1) for line in output.decode().splitlines() if "=" in line)
        require(all(key in result for key in PROPERTIES), f"Incomplete systemd properties: {unit}")
        return result

    def device(self) -> None:
        output = self.host.run("udevadm", "info", "--query=property", f"--name={staging.DEVICE}")
        props = dict(line.split("=", 1) for line in output.decode().splitlines() if "=" in line)
        require(props.get("ID_SERIAL") == staging.IDENTITY
                and props.get("ID_SERIAL_SHORT") == staging.SHORT_ID, "USB identity mismatch.")
        require(Path(staging.DEVICE).resolve().as_posix() == self.state.get(
            "device_resolved", Path(staging.DEVICE).resolve().as_posix()), "Device alias changed.")

    def no_other_jobs(self) -> None:
        output = self.host.run("ps", "-eo", "pid=,args=", "--width", "500").decode()
        save_json(self.evidence / "process-review.json", output.splitlines())
        for line in output.splitlines():
            if re.search(r"(ProcessDaily|ProcessPeriod|ProcessDetectors|reprocessData|processData|"
                         r"processCPM|processADC|plots\.sh|GetDataRawACM0|GetDataNeutron|GetDataWeather)"
                         r"(\.py|\.sh|\s|$)", line):
                raise RuntimeError(f"Potential manual processing/collector job: {line.strip()}")
            if "GetDataRaw.py" in line:
                expected = self.state.get("live_pid")
                require(expected is not None and int(line.split()[0]) == expected,
                        f"Unexpected collector process: {line.strip()}")

    def cron(self) -> bytes:
        return self.host.run("sudo", "-n", "crontab", "-l")

    def probe(self, named: bool, base: Path | None = None) -> None:
        root = base or self.base
        source = (
            "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[2]); "
            "from picomuon_detectors import get_detectors; "
            "from picomuon_metadata import load_legacy_settings; "
            "from picomuon_processing import processing_label; "
            "from picomuon_common import get_usb_options; b=Path(sys.argv[1]); "
        )
        if named:
            source += (
                "assert list(get_detectors(b))==['Unit_1']; "
                "d=get_detectors(b)['Unit_1']; "
                f"assert d.serial_port=={staging.DEVICE!r} and d.id_serial=={staging.IDENTITY!r} "
                f"and d.id_serial_short=={staging.SHORT_ID!r}; "
                "assert processing_label(b,'Unit_1')=='Unit_1'; "
                "assert load_legacy_settings(b,'Unit_1')==(200,100,200,100)"
            )
        else:
            source += (
                "assert not get_detectors(b); "
                f"assert get_usb_options(b)['serial_port']=={staging.DEVICE!r}; "
                "assert load_legacy_settings(b)==(200,100,200,100)"
            )
        self.host.run("/usr/bin/python3", "-B", "-c", source, str(root), str(self.base / "scripts"))

    def manifest(self) -> None:
        output = self.host.run(
            "/usr/bin/python3", "-B", str(self.stage / "candidate/scripts/AdoptUnit1Archive.py"),
            "--source-base", str(self.base), "--destination-base", str(self.base), timeout=900)
        require(staging.digest(output) == staging.MANIFEST_SHA256,
                "Historical archive validation no longer matches the approved manifest.")

    def verify_package(self) -> None:
        require(staging.digest(data(self.stage / "SHA256SUMS")) == STAGE_INDEX
                and staging.digest(data(self.stage / "staging-report.json")) == STAGE_REPORT,
                "Reviewed staging pins changed.")
        index = staging.hash_index(data(self.stage / "SHA256SUMS"))
        actual = {path.relative_to(self.stage).as_posix()
                  for name in ("candidate", "units") for path in (self.stage / name).rglob("*")
                  if not path.is_dir()}
        require(len(index) == 45 and set(index) == actual, "Staging inventory changed.")
        for name, expected in index.items():
            require(staging.digest(data(self.stage / name)) == expected, f"Staging changed: {name}")
        scripts, self.backup = staging.verified_inputs(self.preflight, self.rehearsal)
        self.hashes = staging.production_hashes(self.preflight)
        require(set(self.backup) == set(self.hashes), "Recovery backup inventory mismatch.")
        for name, expected in self.hashes.items():
            require(staging.digest(self.backup[name]) == expected, f"Backup mismatch: {name}")
        reconstructed = Path(tempfile.mkdtemp(prefix="reconstructed-", dir=self.evidence))
        self.reconstruction = reconstructed
        staging.build_candidate(reconstructed, scripts, self.backup)
        for name in index:
            require(data(reconstructed / name) == data(self.stage / name),
                    f"Independent reconstruction differs: {name}")

    def files(self, named: bool) -> tuple[Path, Path, Path]:
        day = self.state["day"]
        raw = self.base / "data/raw"
        status_root = self.base / "data/status"
        if named:
            raw /= "Unit_1"
            status_root /= "Unit_1"
        return (raw / day[:4] / day[:7] / f"{day}.txt",
                status_root / "current.json", raw / "rejected" / f"{day}.txt")

    def signatures(self, paths: tuple[Path, ...]) -> dict[str, str | None]:
        return {str(path): fingerprint(path) for path in paths}

    def frozen(self, label: str) -> None:
        for path, expected in self.state[label].items():
            require(fingerprint(Path(path)) == expected, f"Frozen file changed: {path}")

    def sample(self, named: bool) -> dict:
        raw, status_path, rejected = self.files(named)
        content = data(raw)
        status_value = json.loads(data(status_path))
        timestamp = datetime.strptime(status_value["last_event_utc"], "%Y-%m-%d %H:%M:%S UTC")
        age = (self.host.now() - timestamp.replace(tzinfo=timezone.utc)).total_seconds()
        require(0 <= age <= 15, "Collector status is stale or in the future.")
        rejected_size = len(data(rejected)) if rejected.exists() else 0
        require(rejected_size == (0 if named else self.state.get("old_rejected_size", rejected_size)),
                "New rejected records present; acceptance stopped.")
        return {"raw_bytes": len(content), "last_event": status_value["last_event_utc"],
                "raw_last": last_event(raw).isoformat(), "status": status_value}

    def check_unit(self, unit: str, *, running: bool) -> dict[str, str]:
        props = self.properties(unit)
        require(props["DropInPaths"] == "", f"Unexpected drop-ins for {unit}")
        require(props["FragmentPath"] == str(self.units / unit), f"Unexpected fragment for {unit}")
        require(props["User"] == props["Group"] == "pi"
                and "dialout" in props["SupplementaryGroups"].split(),
                "Unexpected collector account or supplementary groups.")
        require(props["WorkingDirectory"] == str(self.base), "Incorrect working directory.")
        require(set(shlex.split(props["Environment"])) ==
                {f"PICOMUON_BASE_PATH={self.base}", "TERM=dumb"}, "Incorrect service environment.")
        expected_command = f"/usr/bin/python3 {self.base}/scripts/GetDataRaw.py"
        if unit == NAMED:
            expected_command += " --detector Unit_1"
        match = re.search(r"argv\[\]=(.*?) ;", props["ExecStart"])
        require(match is not None and match.group(1) == expected_command,
                "Incorrect collector command or extra arguments.")
        if running:
            require(props["ActiveState"] == "active" and props["SubState"] == "running"
                    and int(props["MainPID"]) > 0, f"{unit} not running.")
        return props

    def check(self) -> None:
        for tool in ("sudo", "systemctl", "systemd-analyze", "fuser", "udevadm", "crontab", "ps"):
            require(shutil.which(tool) is not None, f"Required tool missing: {tool}")
        self.host.run("sudo", "-n", "true")
        require(shutil.disk_usage(self.home).free >= 512 * 1024 * 1024, "Less than 512 MiB free.")
        require(8 <= self.host.now().hour <= 18, "Use an attended 08:00-18:59 UTC daytime window.")
        require(self.host.now().date().isoformat() == self.state["day"], "UTC day changed.")
        self.verify_package()
        staging.check_production(self.base, self.hashes)
        self.device()
        self.state["device_resolved"] = Path(staging.DEVICE).resolve().as_posix()
        for action in ("list-units", "list-unit-files"):
            output = self.host.run("systemctl", action, "--all", "--type=service", "--no-pager",
                                   "--no-legend", "--plain").decode()
            names = {line.split()[0] for line in output.splitlines() if line.strip()
                     and re.match(r"PicoMuon.*\.service", line.split()[0])}
            require(OLD in names and names <= {OLD, "PicoMuon@.service"},
                    f"Unexpected PicoMuon unit inventory: {names}")
        props = self.check_unit(OLD, running=True)
        require(props["UnitFileState"] == "enabled", "Original collector is not enabled as reviewed.")
        self.state["old_restarts"] = props["NRestarts"]
        require(props["NRestarts"] == "0", "Existing automatic restarts require review.")
        self.state["live_pid"] = int(props["MainPID"])
        require(self.host.holders(staging.DEVICE) == {self.state["live_pid"]},
                "Device not owned solely by the old collector.")
        self.no_other_jobs()
        original_cron = self.cron()
        require(original_cron == data(self.preflight / "root-crontab.txt"), "Root crontab drift.")
        held = held_cron(original_cron)
        (self.evidence / "root-crontab.original").write_bytes(original_cron)
        (self.evidence / "root-crontab.held").write_bytes(held)
        self.host.run("sh", "-c",
                      'crontab -l >"$1" 2>"$2"; s=$?; '
                      'test "$s" -eq 1 && grep -Fxq "no crontab for pi" "$2"',
                      "pi-cron-check", str(self.evidence / "pi-cron.txt"),
                      str(self.evidence / "pi-cron.stderr"))
        # Detect scheduling changes against the reviewed snapshot without running cron.
        for command, filename in (
            (("systemctl", "list-timers", "--all", "--no-pager"), "timers.current"),
            (("sudo", "-n", "find", "/etc/cron.d", "/etc/cron.hourly", "/etc/cron.daily",
              "/etc/cron.weekly", "/etc/cron.monthly", "-type", "f", "-exec", "sha256sum", "{}", "+"),
             "system-cron.current"),
        ):
            (self.evidence / filename).write_bytes(self.host.run(*command))
        self.verify_system_cron()
        target = self.units / NAMED
        safe_target(target)
        require(not target.exists() and not target.is_symlink(), "Concrete Unit_1 unit already exists.")
        for path in (*self.files(True), self.base / "logfiles/detectors/Unit_1"):
            safe_target(path)
            require(not path.exists() and not path.is_symlink(), f"Prior named trial target exists: {path}")
        # Reject runtime/transient or type-wide overrides before a concrete unit is installed.
        for root in (Path("/run/systemd/system"), Path("/run/systemd/transient"), self.units):
            for name in (NAMED, f"{NAMED}.d", "PicoMuon@.service.d", "service.d"):
                if root == self.units and name == NAMED:
                    continue
                require(not (root / name).exists() and not (root / name).is_symlink(),
                        f"Unexpected runtime unit or drop-in: {root / name}")
        for name in (OLD, "PicoMuon@.service"):
            require(data(self.units / name) == self.host_unit_backup(name),
                    f"Installed unit changed: {name}")
        self.host.run("systemd-analyze", "verify", "--man=no", str(self.stage / "units" / NAMED))
        self.probe(True, self.reconstruction / "candidate")
        recovery = self.evidence / "recovery"
        recovery.mkdir()
        modes = {}
        for name in CONFIGS:
            path = self.base / "config" / name
            payload = data(path)
            info = path.stat()
            require(info.st_uid == os.getuid() and info.st_gid == os.getgid(),
                    f"Unexpected config owner/group: {name}")
            mode = checked_config_mode(name, stat.S_IMODE(info.st_mode))
            (recovery / name).write_bytes(payload)
            require(payload == self.backup[f"config/{name}"], f"Recovery bytes differ: {name}")
            modes[name] = mode
        self.state["config_modes"] = modes
        self.state["original_config_hashes"] = {
            name: staging.digest(data(recovery / name)) for name in CONFIGS}
        first = self.sample(False)
        rejected = self.files(False)[2]
        self.state["old_rejected_size"] = len(data(rejected)) if rejected.exists() else 0
        self.host.sleep(10)
        second = self.sample(False)
        require(second["raw_bytes"] > first["raw_bytes"]
                and second["last_event"] > first["last_event"], "Single-mode collection not advancing.")
        self.state["precheck_samples"] = [first, second]
        self.state["old_error_size"] = (self.base / "logfiles/log-error.txt").stat().st_size
        self.state["candidate_config_hashes"] = {
            name: staging.digest(data(self.stage / "candidate/config" / name)) for name in CONFIGS}
        self.state["candidate_unit_hash"] = staging.digest(data(self.stage / "units" / NAMED))
        self.journal("READY_FOR_REVIEW_NOT_AUTHORIZED")

    def host_unit_backup(self, name: str) -> bytes:
        import tarfile
        with tarfile.open(self.preflight / "systemd-unit-files.tar.gz") as archive:
            source = archive.extractfile(f"etc/systemd/system/{name}")
            require(source is not None, f"Missing unit backup: {name}")
            if source is None:
                raise RuntimeError(f"Missing unit backup: {name}")
            return source.read()

    def verify_system_cron(self) -> None:
        import tarfile
        expected = {}
        with tarfile.open(self.preflight / "system-cron-files.tar.gz") as archive:
            for member in archive.getmembers():
                if member.isfile():
                    path = Path("/") / member.name
                    source = archive.extractfile(member)
                    if source is None:
                        raise RuntimeError(f"Unreadable cron backup member: {member.name}")
                    expected[str(path)] = staging.digest(source.read())
                    output = self.host.run("sudo", "-n", "sha256sum", str(path)).decode()
                    require(output.split()[0] == expected[str(path)], f"System cron changed: {path}")
        actual = {}
        for line in data(self.evidence / "system-cron.current").decode().splitlines():
            value, path = line.split("  ", 1)
            actual[path] = value
        require(actual == {path: value for path, value in expected.items() if path != "/etc/crontab"},
                "System cron inventory changed.")
        timers = data(self.evidence / "timers.current").decode()
        timer_units = lambda text: set(re.findall(r"\S+\.(?:timer|service)\b", text))
        require(timer_units(timers) == timer_units(data(self.preflight / "timers.txt").decode())
                and "picomuon" not in timers.lower(), "Timer inventory changed.")

    @contextmanager
    def lock(self) -> Iterator[None]:
        import fcntl
        path = self.base / "logfiles/.picomuon-cron.lock"
        require(path.exists(), "Existing cron-wrapper lock missing.")
        data(path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("PicoMuon cron lock busy; do not kill the job.") from exc
            yield
        finally:
            os.close(fd)

    def set_cron(self, held: bool) -> None:
        before = data(self.evidence / ("root-crontab.original" if held else "root-crontab.held"))
        after = self.evidence / ("root-crontab.held" if held else "root-crontab.original")
        require(self.cron() == before, "Crontab edited concurrently; refusing replacement.")
        self.intent("hold-cron" if held else "restore-cron")
        self.host.run("sudo", "-n", "crontab", str(after))
        require(self.cron() == data(after), "Installed crontab readback differs.")
        self.done("hold-cron" if held else "restore-cron")

    def publish_config(self, name: str, restore: bool = False) -> None:
        path = self.base / "config" / name
        mode = checked_config_mode(name, self.state["config_modes"][name])
        original = self.state["original_config_hashes"][name]
        candidate = self.state["candidate_config_hashes"][name]
        expected = (original, candidate) if restore else (original,)
        require(fingerprint(path) in expected, f"Concurrent config edit: {name}")
        source = (self.evidence / "recovery" / name if restore
                  else self.stage / "candidate/config" / name)
        payload = data(source)
        require(staging.digest(payload) == (original if restore else candidate),
                f"Publication source changed: {source}")
        action = f"{'restore' if restore else 'publish'}-{name}"
        self.intent(action)
        temporary = path.with_name(f".{name}.{self.evidence.name}.tmp")
        # An interrupted write may have left this run's exact temporary file.
        if restore and temporary.exists():
            require(fingerprint(temporary) in (original, candidate),
                    f"Unrecognized publication temporary file: {temporary}")
            temporary.unlink()
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fchmod(handle.fileno(), mode)
            os.fsync(handle.fileno())
        temporary.replace(path)
        sync_directory(path.parent)
        require(data(path) == payload, f"Published config differs: {name}")
        self.done(action)

    def stop(self, unit: str) -> None:
        pid = int(self.properties(unit)["MainPID"])
        self.intent(f"stop-{unit}")
        self.host.run("sudo", "-n", "systemctl", "stop", unit)
        props = self.properties(unit)
        require(props["ActiveState"] in ("inactive", "failed") and props["MainPID"] == "0",
                f"{unit} did not stop.")
        if pid:
            require(not Path(f"/proc/{pid}").exists(), f"Previous collector PID {pid} still exists.")
        require(not self.host.holders(staging.DEVICE), "Device still held after stop.")
        self.state["live_pid"] = None
        self.done(f"stop-{unit}")

    def healthy(self, named: bool, duration: int) -> None:
        unit = NAMED if named else OLD
        deadline = self.host.ticks() + 30
        while True:
            props = self.properties(unit)
            raw, status_path, _ = self.files(named)
            if props["ActiveState"] == "active" and raw.exists() and status_path.exists():
                self.sample(named)
                if last_event(raw) >= datetime.fromisoformat(self.state["start_utc"]):
                    break
            require(self.host.ticks() < deadline, "No new valid collection within 30 seconds.")
            require(props["ActiveState"] in ("activating", "active"), "Collector failed on startup.")
            self.host.sleep(1)
        baseline = self.check_unit(unit, running=True)
        pid, restarts = int(baseline["MainPID"]), baseline["NRestarts"]
        require(restarts == "0" if named else restarts == self.state["old_restarts"],
                "Collector restarted unexpectedly.")
        self.state["live_pid"] = pid
        require(self.host.holders(staging.DEVICE) == {pid}, "Unexpected device owner.")
        samples = []
        started = self.host.ticks()
        while True:
            require(self.host.now().date().isoformat() == self.state["day"], "UTC day changed.")
            self.device()
            props = self.check_unit(unit, running=True)
            require(props["MainPID"] == str(pid) and props["NRestarts"] == restarts,
                    "Collector PID changed or restarted.")
            require(self.host.holders(staging.DEVICE) == {pid}, "Device ownership changed.")
            current = self.sample(named)
            if samples:
                require(current["raw_bytes"] > samples[-1]["raw_bytes"]
                        and current["last_event"] > samples[-1]["last_event"],
                        "Collection stopped advancing between observations.")
            if named:
                event_summary = parse_events(data(self.files(True)[0]), self.state["day"], final=False)
                gap = (datetime.fromisoformat(str(event_summary["first"]))
                       - datetime.fromisoformat(self.state["last_old_event"])).total_seconds()
                require(0 <= gap <= 120, f"Event boundary interval {gap}s exceeds 120 seconds.")
                self.state["event_boundary_seconds"] = gap
                self.frozen("old_frozen")
                error = self.base / "logfiles/detectors/Unit_1/log-error.txt"
            else:
                self.frozen("named_frozen")
                error = self.base / "logfiles/log-error.txt"
            require(error.stat().st_size == (0 if named else self.state["old_error_size"]),
                    "New collector error log content.")
            self.no_other_jobs()
            samples.append(current)
            save_json(self.evidence / ("named-observation.json" if named else "recovery-observation.json"),
                      samples)
            if self.host.ticks() - started >= duration:
                break
            self.host.sleep(10)

    def start(self, unit: str) -> None:
        require(not self.host.holders(staging.DEVICE), "Device is not free before start.")
        self.device()
        self.state["start_utc"] = self.host.now().isoformat()
        self.intent(f"start-{unit}")
        self.host.run("sudo", "-n", "systemctl", "start", unit)
        self.done(f"start-{unit}")

    def deploy_and_observe(self) -> None:
        require(self.cron() == data(self.evidence / "root-crontab.held"), "Cron hold lost.")
        require(self.host.now().date().isoformat() == self.state["day"]
                and 8 <= self.host.now().hour <= 18, "Outside reviewed daytime window.")
        self.device()
        self.no_other_jobs()
        staging.check_production(self.base, self.hashes)
        for path in (*self.files(True), self.base / "logfiles/detectors/Unit_1"):
            safe_target(path)
            require(not path.exists(), f"Named target appeared after precheck: {path}")
        self.stop(OLD)
        self.state["last_old_event"] = last_event(self.files(False)[0]).isoformat()
        self.state["old_frozen"] = self.signatures(self.files(False))
        self.journal("old-files-frozen")
        logs = self.base / "logfiles/detectors/Unit_1"
        logs.parent.mkdir(exist_ok=True)
        self.intent("create-named-logs")
        logs.mkdir(mode=0o755)
        logs.chmod(0o755)
        self.done("create-named-logs")
        for name in CONFIGS:
            self.publish_config(name)
        target = self.units / NAMED
        require(not target.exists() and not target.is_symlink(), "Instance appeared concurrently.")
        self.intent("install-unit")
        # A hard link publishes a root-owned complete file without overwriting an existing unit.
        temporary = self.units / f".{NAMED}.{self.evidence.name}.tmp"
        self.host.run("sudo", "-n", "test", "!", "-e", str(temporary))
        self.host.run("sudo", "-n", "install", "-o", "root", "-g", "root", "-m", "0644",
                      str(self.stage / "units" / NAMED), str(temporary))
        self.host.run("sudo", "-n", "ln", "-T", str(temporary), str(target))
        self.host.run("sudo", "-n", "rm", "--", str(temporary))
        self.done("install-unit")
        require(fingerprint(target) == self.state["candidate_unit_hash"], "Installed unit mismatch.")
        self.host.run("sudo", "-n", "systemctl", "daemon-reload")
        self.host.run("systemd-analyze", "verify", "--man=no", str(target))
        self.check_unit(NAMED, running=False)
        self.probe(True)
        self.start(NAMED)
        self.healthy(True, 600)
        self.state["trial_passed"] = True
        self.journal("named-trial-passed-recovery-required")

    def recover(self) -> None:
        self.journal("recovering")
        mutations = self.state["mutations"]
        changed = f"stop-{OLD}" in mutations
        if changed:
            if "named_frozen" in self.state:
                self.frozen("named_frozen")
            old_props = self.properties(OLD)
            old_running = old_props["ActiveState"] == "active" and int(old_props["MainPID"]) > 0
            original_config = all(
                fingerprint(self.base / "config" / name) == self.state["original_config_hashes"][name]
                for name in CONFIGS)
            already_restored = (old_running and original_config
                                and not (self.units / NAMED).exists())
            if already_restored:
                require(self.host.holders(staging.DEVICE) == {int(old_props["MainPID"])},
                        "Unexpected device ownership during resumed recovery.")
                self.state["live_pid"] = int(old_props["MainPID"])
                if "named_frozen" not in self.state:
                    self.state["named_frozen"] = self.signatures(self.files(True))
                # Re-observe a recovered service; do not stop/restart it a second time.
                self.state["start_utc"] = self.host.now().isoformat()
                self.healthy(False, 120)
            else:
                self.restore_stopped_collection(mutations)
        if changed:
            for name in (OLD, "PicoMuon@.service"):
                require(data(self.units / name) == self.host_unit_backup(name), "Original unit changed.")
            require(self.properties(OLD)["UnitFileState"] == "enabled", "Old boot state changed.")
            require(not (self.units / NAMED).exists(), "Concrete named unit remains installed.")
            require(self.host.run("systemctl", "is-enabled", NAMED, allowed=(0, 1)).strip() == b"disabled",
                    "Unexpected named boot enablement; keep processing held for review.")
            staging.check_production(self.base, staging.production_hashes(self.preflight))
            self.manifest()
        if "hold-cron" in mutations:
            current = self.cron()
            original = data(self.evidence / "root-crontab.original")
            if current != original:
                self.set_cron(False)
        self.journal("TRIAL_PASSED_AND_SINGLE_RESTORED" if self.state.get("trial_passed")
                     else "TRIAL_NOT_ACCEPTED_SINGLE_RESTORED" if changed
                     else "NO_COLLECTION_CHANGE_CRON_RESTORED")

    def restore_stopped_collection(self, mutations: list[str]) -> None:
        # A recorded start intent can mean start succeeded even if the command timed out.
        if f"start-{NAMED}" in mutations:
            self.stop(NAMED)
        else:
            require(not self.host.holders(staging.DEVICE), "Port unexpectedly occupied during recovery.")
        self.state["named_frozen"] = self.signatures(self.files(True))
        self.journal("named-files-frozen")
        raw = self.files(True)[0]
        if raw.exists() and raw.stat().st_size:
            try:
                self.state["final_named_rows"] = parse_events(data(raw), self.state["day"], final=True)
            except (ValueError, RuntimeError, csv.Error) as exc:
                self.state["trial_passed"] = False
                self.state["final_row_error"] = str(exc)
                self.journal("trial-data-invalid-recovering")
        for name in CONFIGS:
            self.publish_config(name, restore=True)
        target = self.units / NAMED
        if target.exists() or target.is_symlink():
            require("install-unit" in mutations
                    and fingerprint(target) == self.state["candidate_unit_hash"],
                    "Cannot remove an unrecognized concrete unit.")
            self.intent("remove-unit")
            self.host.run("sudo", "-n", "rm", "--", str(target))
            self.done("remove-unit")
        self.host.run("sudo", "-n", "systemctl", "daemon-reload")
        for name in (OLD, "PicoMuon@.service"):
            require(data(self.units / name) == self.host_unit_backup(name),
                    f"Original unit changed before recovery start: {name}")
        staging.check_production(self.base, staging.production_hashes(self.preflight))
        self.check_unit(OLD, running=False)
        self.probe(False)
        self.start(OLD)
        self.healthy(False, 120)

    def execute(self) -> None:
        self.state["trial_passed"] = False
        try:
            self.set_cron(True)
            with self.lock():
                try:
                    self.deploy_and_observe()
                except (OSError, ValueError, RuntimeError, csv.Error, KeyboardInterrupt) as exc:
                    self.state["trial_error"] = str(exc)
                    self.journal("trial-failed-recovery-required")
                    print(f"Trial stopped: {exc}. Attempting approved recovery.", file=sys.stderr)
                self.recover()
        except (OSError, ValueError, RuntimeError, csv.Error, KeyboardInterrupt):
            # Before stop intent, cron restoration needs no collector/config recovery.
            if f"stop-{OLD}" not in self.state["mutations"]:
                self.recover()
            raise


def interrupted(signum: int, frame: object) -> None:
    raise KeyboardInterrupt(f"Received signal {signum}; recovery must be verified.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="Default: evidence/readiness only.")
    modes.add_argument("--trial", action="store_true", help="Mutating trial and planned recovery; requires approval.")
    modes.add_argument("--recover", type=Path, help="Recover an interrupted run, never restart a trial.")
    parser.add_argument("--approval", help="Exact separately approved trial/recovery phrase.")
    args = parser.parse_args()
    if sys.platform != "linux" or os.getuid() == 0 or Path.home() != Path("/home/pi"):
        parser.error("Run on the production Pi as pi, without sudo.")
    if (args.trial or args.recover) and args.approval != APPROVAL:
        parser.error("Trial/recovery not approved: require the separately reviewed approval phrase.")
    if args.recover and not (args.recover.parent == Path.home()
                             and args.recover.name.startswith("unit1-collection-trial.")
                             and args.recover.is_dir() and not args.recover.is_symlink()):
        parser.error("Invalid recovery directory; use this Pi account's existing trial evidence.")
    os.umask(0o077)
    import fcntl
    global_lock = os.open(Path.home() / ".unit1-collection-trial.lock",
                          os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(global_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(global_lock)
        parser.error("Another Unit_1 trial/check/recovery runner is already active.")
    evidence = (args.recover if args.recover else
                Path(tempfile.mkdtemp(prefix="unit1-collection-trial.", dir=Path.home())))
    print(f"EVIDENCE DIRECTORY: {evidence}", flush=True)
    if not args.trial and not args.recover:
        print("CHECK ONLY: no production edits or service changes. Archive checks may take several minutes.",
              flush=True)
    trial = Trial(Path.home(), Path("/etc/systemd/system"), evidence, Host(evidence))
    recovery_loaded = False
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    try:
        if args.recover:
            require(evidence.parent == Path.home() and evidence.name.startswith("unit1-collection-trial.")
                    and not evidence.is_symlink(), "Invalid recovery directory.")
            recovered_state = json.loads(data(evidence / "state.json"))
            require(isinstance(recovered_state, dict) and all(key in recovered_state for key in (
                "status", "day", "history", "mutations", "completed", "config_modes",
                "original_config_hashes", "candidate_config_hashes", "candidate_unit_hash")),
                "Incomplete recovery journal; manual evidence review required.")
            require(isinstance(recovered_state["mutations"], list) and recovered_state["mutations"],
                    "No recorded mutations: check-only runs have nothing to recover.")
            trial.state = recovered_state
            recovery_loaded = True
            trial.host.sequence = len(list(evidence.glob("command-*.argv.json")))
            require(trial.state["day"] == trial.host.now().date().isoformat(),
                    "Recovery across UTC rollover requires manual review.")
            require(trial.state["status"] not in (
                "TRIAL_PASSED_AND_SINGLE_RESTORED", "TRIAL_NOT_ACCEPTED_SINGLE_RESTORED",
                "NO_COLLECTION_CHANGE_CRON_RESTORED"), "Run is already recovered.")
            trial.verify_package()
            for name in CONFIGS:
                require(data(evidence / "recovery" / name) == trial.backup[f"config/{name}"],
                    f"Recovery copy changed: {name}")
                require(trial.state["original_config_hashes"][name] == staging.digest(
                trial.backup[f"config/{name}"]), "Journal original-config pin changed.")
                require(trial.state["candidate_config_hashes"][name] == staging.digest(
                data(trial.stage / "candidate/config" / name)), "Journal candidate pin changed.")
                checked_config_mode(name, trial.state["config_modes"][name])
            require(data(evidence / "root-crontab.original") == data(trial.preflight / "root-crontab.txt")
                and data(evidence / "root-crontab.held") == held_cron(
                    data(evidence / "root-crontab.original")), "Recovery cron copies changed.")
            require(trial.state["candidate_unit_hash"] == staging.digest(
                data(trial.stage / "units" / NAMED)), "Journal unit pin changed.")
            with trial.lock():
                trial.recover()
        else:
            trial.check()
            with trial.lock():
                trial.no_other_jobs()
            trial.manifest()
            if args.trial:
                trial.execute()
        print(trial.state["status"])
        print("Privately download the evidence. No boot-enable changes or data merging performed.")
        return 0 if not args.trial or trial.state.get("trial_passed") else 1
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt, csv.Error) as exc:
        trial.state["error"] = str(exc)
        if args.recover and not recovery_loaded:
            save_json(evidence / "recovery-validation-failure.json", {"error": str(exc)})
        else:
            trial.journal("FAILED_REVIEW_REQUIRED")
        print(f"FAILED: {exc}\nPreserve {evidence}; do not rerun a trial or start a collector blindly.",
              file=sys.stderr)
        return 1
    finally:
        os.close(global_lock)


if __name__ == "__main__":
    raise SystemExit(main())
