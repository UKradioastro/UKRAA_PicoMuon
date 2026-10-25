#!/usr/bin/env python3
"""Guarded Unit_1 processing restore, 21-24 Oct gap merge and backfill; default is check only."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import sys
import tempfile

import PermanentUnit1Collection as permanent
import TrialUnit1Collection as trial
from TrialUnit1Collection import data, fingerprint, require, safe_target, save_json, sync_directory

staging = trial.staging
OLD, NAMED = trial.OLD, trial.NAMED
KIND = "restore-unit1-processing-v1"
APPROVAL = "UNIT1-RESTORE-PROCESSING"
PREFIX = "unit1-restore-processing."
COLLECTION = "unit1-permanent-collection.k_xuwdb1"
RAW_HEADER = ("RPiTimestamp,Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp_C,Pres_hPa,DetectorName,"
              "threshold_top,reset_top,threshold_bottom,reset_bottom")
SETTINGS = (200, 100, 200, 100)
GAP_DAYS = ("2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24")
# Named raw present before the restore. October 24 is pinned by the reviewed check manifest.
NAMED_PINS = {"2026-10-21": None, "2026-10-22": permanent.TRIAL_RAW_SHA256,
              "2026-10-23": permanent.PARTIAL_RAW_SHA256}
FIRST_DAY = date(2026, 10, 10)
REHEARSED = (
    "ProcessDaily.py", "ProcessPeriod.py", "plot-annotations.gp", "PlotDataCpmACM0.gp",
    "PlotDataFreqACM0.gp", "PlotDataAdcACM0.gp", "PlotDataDayACM0.gp", "PlotDataWeekACM0.gp",
    "PlotDataMonthACM0.gp",
)
NEW_FILES = ("scripts/plot-annotations.gp",)
PROCESS_DATA_SHA256 = "dd50bdfcbdf5570fd7521b2bc2c1912926122087e16edfe1a02f44ffddffb609"
# Four PlotDataDay warnings reviewed after the 25 October rolled-back restore.
REVIEWED_PROCESSING_ERRORS_SHA256 = "cbfd4f0534702884f6f67c4d9d0069f86dfab9c04111aadef49b3562bce2cb2d"
# Python rewrites these after the reviewed sources change; they are restored on rollback.
STALE_BYTECODE = ("scripts/__pycache__/ProcessDaily.cpython-313.pyc",
                  "scripts/__pycache__/ProcessPeriod.cpython-313.pyc")
HELPERS = ("RestoreUnit1Processing.py", *permanent.HELPERS, "processData.sh")


@contextmanager
def production_umask():
    # Evidence stays private (umask 077), but products and public pages need cron's 022.
    previous = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(previous)
PUBLIC = Path("/var/www/html")
LOGS = ("logfiles/log-PicoMuon.txt", "logfiles/log-error.txt",
        "logfiles/detectors/Unit_1/log-PicoMuon.txt", "logfiles/detectors/Unit_1/log-error.txt",
        "logfiles/.pipeline.lock", "logfiles/detectors/Unit_1/.pipeline.lock",
        "logfiles/detectors/Unit_1/.processing.lock")
ROTATED_LOGS = frozenset(f"{relative}-{generation}"
                         for relative in LOGS[2:4] for generation in range(4))
# Everything the pipeline (run as pi) writes; systemd-created files are the known risk.
OUTPUT_ROOTS = (
    "logfiles/detectors/Unit_1", "data/raw/Unit_1", "temp/detectors/Unit_1", "WWW",
    "data/weather", "data/neutron",
    *(f"data/{kind}/detectors/Unit_1" for kind in ("cpm", "adc", "day", "hour", "week", "month", "3month")),
)
WINDOW_HOURS = (3, 21)
PUBLISHED_AFTER_MINUTES = 150
READY = "RESTORE_READY_NOT_AUTHORIZED"
COMMITTED = "RESTORED_PROCESSING_COMMITTED"
ROLLED_BACK = "RESTORE_ROLLED_BACK_PROCESSING_HELD"
VERIFIED = "RESTORED_PROCESSING_VERIFIED"
FAILURES = (OSError, ValueError, RuntimeError, csv.Error, KeyboardInterrupt)


def helper_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    return {name: staging.digest(data(root / name)) for name in HELPERS}


def raw_events(content: bytes, day: str, source: str) -> list[tuple[datetime, bytes]]:
    require(content.endswith(b"\n"), f"Incomplete final raw row: {source}")
    events: list[tuple[datetime, bytes]] = []
    for line in content.splitlines(keepends=True):
        if not line.strip() or line.startswith((b"#", b"RPiTimestamp,")):
            continue
        row = next(csv.reader([line.decode("utf-8")], strict=True))
        require(len(row) == 13, f"Unexpected raw column count in {source}")
        stamp = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S.%f")
        require(stamp.date().isoformat() == day, f"Wrong-day event in {source}")
        require(row[1] in ("T", "B", "C"), f"Unexpected event type in {source}")
        require(tuple(int(value) for value in row[9:]) == SETTINGS, f"Unexpected settings in {source}")
        require(not events or stamp >= events[-1][0], f"Out-of-order event in {source}")
        events.append((stamp, line))
    require(bool(events), f"No events in {source}")
    return events


def merge_day(day: str, single: bytes, named: bytes | None) -> tuple[bytes, dict]:
    first = raw_events(single, day, f"single-mode {day}")
    second = raw_events(named, day, f"named {day}") if named is not None else []
    summary: dict = {"single_events": len(first), "named_events": len(second)}
    if second:
        low, high = second[0][0], second[-1][0]
        require(not any(low <= stamp <= high for stamp, _ in first),
                f"Single-mode and named segments overlap on {day}")
        require(not {line for _, line in first} & {line for _, line in second},
                f"Duplicate event bytes on {day}")
        before = [stamp for stamp, _ in first if stamp < low]
        after = [stamp for stamp, _ in first if stamp > high]
        summary.update(
            named_first=low.isoformat(sep=" "), named_last=high.isoformat(sep=" "),
            single_before=before[-1].isoformat(sep=" ") if before else None,
            single_after=after[0].isoformat(sep=" ") if after else None,
        )
    # Stable sort: each source is already ordered and the segments are disjoint.
    merged = sorted(first + second, key=lambda item: item[0])
    output = (RAW_HEADER + "\n").encode("ascii") + b"".join(line for _, line in merged)
    summary.update(events=len(merged), first=merged[0][0].isoformat(sep=" "),
                   last=merged[-1][0].isoformat(sep=" "), sha256=staging.digest(output), bytes=len(output))
    return output, summary


def replace_file(path: Path, payload: bytes, mode: int, tag: str, mtime_ns: int | None = None) -> None:
    safe_target(path)
    temporary = path.with_name(f".{path.name}.{tag}.tmp")
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    if mtime_ns is not None:
        os.utime(temporary, ns=(mtime_ns, mtime_ns))
    temporary.replace(path)
    sync_directory(path.parent)
    require(data(path) == payload, f"Replacement readback differs: {path}")


def is_png(path: Path) -> bool:
    return path.is_file() and data(path).startswith(b"\x89PNG\r\n\x1a\n")


def last_command(evidence: Path) -> int:
    return max((int(path.name.split("-")[1].split(".")[0])
                for path in evidence.glob("command-*.argv.json")), default=0)


class Restore:
    def __init__(self, home: Path, units: Path, evidence: Path, host: trial.Host):
        self.home, self.units, self.evidence, self.host = home, units, evidence, host
        self.base = home / "UKRAA_PicoMuon"
        self.public = PUBLIC
        self.collection: permanent.Permanent | None = None
        self.payload: dict[str, bytes] = {}
        self.state: dict = {
            "kind": KIND, "status": "checking", "helpers": helper_hashes(), "mutations": [],
            "completed": [], "history": [], "processed": [], "day": host.now().date().isoformat(),
        }

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

    def commit_barrier(self) -> bool:
        return bool(self.state.get("committed") or any(
            item["status"] in ("COMMIT_READY", COMMITTED) for item in self.state["history"]))

    def open_collection(self) -> permanent.Permanent:
        source = self.home / COLLECTION
        copy = self.evidence / "collection"
        if not copy.exists():
            require(source.is_dir(), f"Committed collection evidence missing: {source}")
            for path in (source, *source.rglob("*")):
                require(not path.is_symlink(), f"Symlink in committed evidence: {path}")
            shutil.copytree(source, copy)
        collection = permanent.Permanent(self.home, self.units, copy, self.host)
        sequence = self.host.sequence
        collection.load()
        # Commands are recorded in this evidence directory, never in the committed copy.
        self.host.sequence = max(sequence, self.host.sequence, last_command(self.evidence))
        require(collection.commit_barrier(), "Permanent Unit_1 collection is not committed.")
        self.collection = collection
        return collection

    def single_raw(self, day: str) -> Path:
        return self.base / "data/raw" / day[:4] / day[:7] / f"{day}.txt"

    def named_raw(self, day: str) -> Path:
        return self.base / "data/raw/Unit_1" / day[:4] / day[:7] / f"{day}.txt"

    def relative(self, path: Path) -> str:
        return path.relative_to(self.base).as_posix()

    def merged(self, day: str) -> tuple[bytes, dict]:
        single_path, named_path = self.single_raw(day), self.named_raw(day)
        single = data(single_path)
        named = data(named_path) if named_path.exists() or named_path.is_symlink() else None
        if day in NAMED_PINS:
            require((None if named is None else staging.digest(named)) == NAMED_PINS[day],
                    f"Unexpected pre-restore named raw for {day}.")
        else:
            require(named is not None, f"Named raw missing for {day}.")
        output, summary = merge_day(day, single, named)
        entry = {
            "day": day, "destination": self.relative(named_path),
            "single": {"path": self.relative(single_path), "sha256": staging.digest(single),
                       "bytes": len(single)},
            "named": None if named is None else {"path": self.relative(named_path),
                                                 "sha256": staging.digest(named), "bytes": len(named)},
            **summary,
        }
        return output, entry

    def merge_manifest(self) -> dict:
        entries = [self.merged(day)[1] for day in GAP_DAYS]
        last_old = self.collection.state["last_old_event"]
        last_old_naive = datetime.fromisoformat(last_old).replace(tzinfo=None)
        require(datetime.fromisoformat(entries[-1]["named_first"]) > last_old_naive,
                "Named October 24 data does not follow the frozen single-mode data.")
        return {"schema_version": 1, "batch": "Unit_1-2026-10-21_2026-10-24", "entries": entries}

    def manifest(self) -> dict:
        content = data(self.evidence / "merge-manifest.json")
        require(staging.digest(content) == self.state["merge_manifest_sha256"], "Merge manifest changed.")
        return json.loads(content)

    def deployment(self) -> dict[str, bytes]:
        collection = self.collection
        scripts, _ = staging.verified_inputs(collection.preflight, collection.rehearsal)
        payload = {f"scripts/{name}": scripts[name] for name in REHEARSED}
        process_data = data(Path(__file__).resolve().parent / "processData.sh")
        require(staging.digest(process_data) == PROCESS_DATA_SHA256 and b"\r" not in process_data,
                "Reviewed processData.sh missing or changed beside this runner.")
        payload["scripts/processData.sh"] = process_data
        return payload

    def backfill_days(self) -> list[str]:
        yesterday = date.fromisoformat(self.state["day"]) - timedelta(days=1)
        days = [(FIRST_DAY + timedelta(days=offset)).isoformat()
                for offset in range((yesterday - FIRST_DAY).days + 1)]
        for day in days:
            if day not in GAP_DAYS:
                require(self.named_raw(day).is_file(), f"Unit_1 raw missing for backfill day {day}.")
        return days

    def web_state(self) -> dict:
        require(self.public.is_dir() and not self.public.is_symlink(), "Public web root missing.")
        temp = self.public / "temp"
        legacy = {path.name: fingerprint(path) for path in sorted(temp.glob("ACM0_*.png"))} if temp.is_dir() else {}
        return {"index_sha256": fingerprint(self.public / "index.html"), "legacy_plots": legacy}

    def require_writable(self) -> None:
        blocked: list[str] = []
        for relative in LOGS[:4]:
            if not (self.base / relative).is_file():
                blocked.append(f"{relative} (missing)")
        for relative in LOGS:
            path = self.base / relative
            if path.exists() and not os.access(path, os.W_OK):
                blocked.append(relative)
        for relative in OUTPUT_ROOTS:
            root = self.base / relative
            if not root.exists():
                while not root.exists():
                    root = root.parent
                if not os.access(root, os.W_OK | os.X_OK):
                    blocked.append(f"{self.relative(root)} (cannot create {relative})")
                continue
            for directory, names, files in os.walk(root):
                if not os.access(directory, os.W_OK | os.X_OK):
                    blocked.append(self.relative(Path(directory)))
                for name in files:
                    path = Path(directory) / name
                    # Rotation preserves ownership; processing never writes these archives.
                    if (self.relative(path) in ROTATED_LOGS
                            and stat.S_ISREG(path.lstat().st_mode)):
                        continue
                    if not os.access(path, os.W_OK):
                        blocked.append(self.relative(path))
        self.state["unwritable"] = blocked
        require(not blocked, f"Not writable by {self.home.name} ({len(blocked)}): {', '.join(blocked[:8])}")

    def retained_state(self) -> dict[str, str]:
        collection = self.collection
        live = self.base / "logfiles/detectors/Unit_1/log-error.txt"
        baseline = data(collection.evidence / "prior-named/log-error.txt")
        if fingerprint(live) != REVIEWED_PROCESSING_ERRORS_SHA256:
            return collection.retained_state()
        require(baseline == b"", "Reviewed processing warnings require the original empty baseline.")
        # Mirrors Permanent.retained_state (whose code is pinned by the committed journal), except
        # the error log may be the exact reviewed warnings. Committed evidence is never edited.
        collection.protect_trial()
        collection.installed_hashes()
        collection.service_inventory()
        collection.boot_state(True)
        require(collection.cron() == data(collection.evidence / "root-crontab.held"),
                "Permanent processing hold lost.")
        old = collection.properties(OLD)
        require(old["MainPID"] == "0" and old["ActiveState"] == "inactive", "Old service is not stopped.")
        named = collection.check_unit(NAMED, running=True)
        require(named["NRestarts"] == "0", "Named collector has restarted; review required.")
        collection.state["live_pid"] = int(named["MainPID"])
        collection.device()
        require(self.host.holders(staging.DEVICE) == {collection.state["live_pid"]}, "Unexpected device owner.")
        collection.no_other_jobs()
        collection.frozen("old_frozen")
        require(fingerprint(live) == REVIEWED_PROCESSING_ERRORS_SHA256,
                "Named error log changed or rotated; inspect before accepting retained collection.")
        self.state["reviewed_processing_errors_sha256"] = REVIEWED_PROCESSING_ERRORS_SHA256
        save_json(self.evidence / "reviewed-processing-errors.json", {
            "committed_baseline_sha256": staging.digest(baseline),
            "accepted_live_sha256": REVIEWED_PROCESSING_ERRORS_SHA256,
            "reason": "Four PlotDataDayACM0.gp warnings from the rolled-back 25 October restore.",
        })
        return named

    def check(self) -> None:
        now = self.host.now()
        require(WINDOW_HOURS[0] <= now.hour < WINDOW_HOURS[1],
                "Run between 03:00 and 21:00 UTC, clear of log rotation and the 01:15 daily job.")
        collection = self.open_collection()
        for path in self.home.glob(PREFIX + "*"):
            state_file = path / "state.json"
            if path != self.evidence and path.is_dir() and state_file.exists():
                earlier = json.loads(data(state_file))
                require(not earlier.get("mutations") or earlier.get("status") == ROLLED_BACK,
                        f"Earlier restore needs recovery or is already committed: {path}")
        with collection.lock():
            named = self.retained_state()
        self.state["collector_pid"] = int(named["MainPID"])
        collection.manifest()
        self.payload = self.deployment()
        for relative in self.payload:
            path = self.base / relative
            if relative in NEW_FILES:
                require(not path.exists() and not path.is_symlink(), f"Unexpected existing file: {relative}")
            else:
                require(fingerprint(path) == collection.hashes[relative], f"Production changed: {relative}")
        self.host.run("bash", "-n", str(Path(__file__).resolve().parent / "processData.sh"))
        self.require_writable()
        save_json(self.evidence / "merge-manifest.json", self.merge_manifest())
        self.state["merge_manifest_sha256"] = staging.digest(data(self.evidence / "merge-manifest.json"))
        self.state["backfill_days"] = self.backfill_days()
        self.state["web_before"] = self.web_state()
        self.state["deploy"] = {name: staging.digest(content) for name, content in self.payload.items()}
        self.journal(READY)

    def backup(self) -> None:
        root = self.evidence / "backup"
        record: dict[str, dict | None] = {}
        targets = [entry["destination"] for entry in self.manifest()["entries"]]
        for relative in (*targets, *self.payload, *STALE_BYTECODE):
            path = self.base / relative
            if not path.exists() and not path.is_symlink():
                record[relative] = None
                continue
            content = data(path)
            info = path.stat()
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            require(data(target) == content, f"Backup readback differs: {relative}")
            record[relative] = {"sha256": staging.digest(content), "mode": stat.S_IMODE(info.st_mode),
                                "mtime_ns": info.st_mtime_ns}
        self.state["backup"] = record
        self.journal("backed-up")

    def promote(self, entry: dict, mode: int) -> None:
        output, fresh = self.merged(entry["day"])
        require(fresh == entry, f"Gap sources changed since the reviewed check: {entry['day']}")
        action = f"raw:{entry['destination']}"
        self.intent(action)
        replace_file(self.base / entry["destination"], output, mode, self.evidence.name)
        self.done(action)

    def deploy(self) -> None:
        for relative, content in self.payload.items():
            before = self.state["backup"][relative]
            action = f"deploy:{relative}"
            self.intent(action)
            replace_file(self.base / relative, content, before["mode"] if before else 0o644, self.evidence.name)
            self.done(action)

    def python(self, script: str, *arguments: str) -> tuple[str, ...]:
        return ("/usr/bin/env", f"PICOMUON_BASE_PATH={self.base}", f"PICOMUON_FILE_OWNER={self.home.name}",
                "TZ=UTC", "/usr/bin/python3", str(self.base / "scripts" / script), *arguments)

    def unit_log(self) -> Path:
        return self.base / "logfiles/detectors/Unit_1/log-PicoMuon.txt"

    def plots(self) -> list[Path]:
        root = self.base / "temp/detectors/Unit_1"
        return [*sorted((root / "yesterday").glob("Unit_1_*.png")), *sorted((root / "periods").glob("Unit_1_*.png"))]

    def require_outputs(self, day: str) -> None:
        product = self.base / "data/day/detectors/Unit_1" / day[:4] / day[:7] / f"{day}.txt"
        require(product.is_file(), f"Unit_1 day product missing for {day}.")
        page = self.base / "WWW/detectors/Unit_1" / day
        require(page.is_dir() and any(page.glob("*.png")), f"Unit_1 page missing for {day}.")

    def require_processed(self, day: str, mark: int) -> None:
        appended = data(self.unit_log())[mark:]
        require(f"Completed run for {day}".encode() in appended, f"Unit_1 pipeline did not complete {day}.")
        self.require_outputs(day)
        names = {path.name for path in self.plots()}
        expected = {f"Unit_1_{event}-{kind}.png" for kind in ("Cpm", "Freq", "Adc") for event in "TBC"}
        require(expected | {"Unit_1_day_plot.png"} <= names, f"Unit_1 plots incomplete for {day}.")
        require(all(is_png(path) for path in self.plots()), f"Invalid Unit_1 plot for {day}.")

    def require_published(self, day: str) -> None:
        for path in self.plots():
            legacy = self.public / "temp" / ("ACM0_" + path.name[len("Unit_1_"):])
            require(data(legacy) == data(path), f"Public legacy plot not current: {legacy}")
        local = self.base / "WWW/detectors"
        pages = [local / "index.html", local / "Unit_1/index.html", local / "Unit_1/status.json",
                 *sorted((local / "Unit_1" / day).glob("*.png"))]
        for path in pages:
            require(data(self.public / "detectors" / path.relative_to(local)) == data(path),
                    f"Public Unit_1 site not current for {day}: {path.relative_to(local).as_posix()}")
        require(fingerprint(self.public / "index.html") == self.state["web_before"]["index_sha256"],
                "Public index.html changed; it must never be replaced.")

    def backfill(self) -> None:
        for day in self.state["backfill_days"][:-1]:
            self.host.run("sudo", "-n", "-v")
            weather = self.base / "data/weather" / day[:4] / day[:7] / f"{day}.txt"
            mark = self.unit_log().stat().st_size
            with production_umask():
                if not weather.exists():
                    self.host.run(*self.python("GetDataWeather.py", "--date", day), allowed=(0, 1),
                                  timeout=600)
                self.host.run(*self.python("ProcessDetectors.py", "--detector", "Unit_1", "--date", day,
                                           "--skip-downloads"), timeout=1800)
            self.require_processed(day, mark)
            self.state["processed"].append(day)
            self.journal(f"processed:{day}")

    def final_run(self) -> None:
        # Exercise the restored root cron path once; NMDB outages make exit 1 expected.
        day = self.state["backfill_days"][-1]
        self.host.run("sudo", "-n", "-v")
        mark = self.unit_log().stat().st_size
        with production_umask():
            self.host.run("sudo", "-n", "/bin/bash", str(self.base / "scripts/processData.sh"),
                          allowed=(0, 1), timeout=3600)
        self.require_processed(day, mark)
        self.require_published(day)
        self.state["processed"].append(day)
        self.journal(f"processed-and-published:{day}")

    def collector_errors(self) -> None:
        baseline = set(data(self.collection.evidence / "prior-named/log-error.txt").splitlines())
        current = data(self.base / "logfiles/detectors/Unit_1/log-error.txt").splitlines()
        require(not [line for line in current if line not in baseline and b"GetDataRaw" in line],
                "New Unit_1 collector errors; review required.")

    def restored(self, *, pin_pid: bool) -> dict[str, str]:
        collection = self.collection
        expected = {name: value for name, value in collection.hashes.items() if name not in STALE_BYTECODE}
        for name in trial.CONFIGS:
            expected[f"config/{name}"] = collection.state["candidate_config_hashes"][name]
        expected.update(self.state["deploy"])
        staging.check_production(self.base, expected)
        require(fingerprint(self.units / NAMED) == collection.state["candidate_unit_hash"],
                "Concrete instance changed.")
        collection.unchanged_original_units()
        collection.service_inventory()
        collection.boot_state(True)
        old = collection.properties(OLD)
        require(old["MainPID"] == "0" and old["ActiveState"] == "inactive", "Old service is not stopped.")
        named = collection.check_unit(NAMED, running=True)
        require(named["NRestarts"] == "0", "Named collector has restarted; review required.")
        if pin_pid:
            require(int(named["MainPID"]) == self.state["collector_pid"], "Named collector PID changed.")
        collection.state["live_pid"] = int(named["MainPID"])
        collection.device()
        require(self.host.holders(staging.DEVICE) == {collection.state["live_pid"]}, "Unexpected device owner.")
        collection.no_other_jobs()
        collection.frozen("old_frozen")
        self.collector_errors()
        for entry in self.manifest()["entries"]:
            require(fingerprint(self.base / entry["destination"]) == entry["sha256"],
                    f"Merged Unit_1 raw changed: {entry['destination']}")
        return named

    def restore_cron(self) -> None:
        collection = self.collection
        original = collection.evidence / "root-crontab.original"
        require(collection.cron() == data(collection.evidence / "root-crontab.held"),
                "Processing hold changed; refusing cron restore.")
        self.intent("restore-cron")
        self.host.run("sudo", "-n", "crontab", str(original))
        require(collection.cron() == data(original), "Restored crontab readback differs.")
        self.done("restore-cron")

    def apply(self, reviewed: Path) -> None:
        saved = json.loads(data(reviewed / "state.json"))
        require(saved.get("kind") == KIND and saved.get("status") == READY
                and saved.get("helpers") == self.state["helpers"], "Reviewed directory is not a ready check.")
        require(data(reviewed / "merge-manifest.json") == data(self.evidence / "merge-manifest.json"),
                "Gap merge differs from the reviewed check; collect and review fresh evidence.")
        require(saved.get("deploy") == self.state["deploy"]
                and saved.get("backfill_days") == self.state["backfill_days"],
                "Deployment or backfill plan differs from the reviewed check.")
        self.state["reviewed"] = str(reviewed)
        self.journal("approved")
        entries = self.manifest()["entries"]
        try:
            with self.collection.lock():
                self.backup()
                mode = self.state["backup"][entries[-1]["destination"]]["mode"]
                for entry in entries:
                    before = self.state["backup"][entry["destination"]]
                    self.promote(entry, before["mode"] if before else mode)
                self.deploy()
                self.backfill()
                self.final_run()
                self.restored(pin_pid=True)
                now = self.host.now()
                require(now.date().isoformat() == self.state["day"] and now.hour < 23,
                        "UTC day ended during restore; not committing.")
                self.journal("COMMIT_READY")
                self.restore_cron()
                self.state["committed"] = True
                self.journal(COMMITTED)
        except FAILURES as exc:
            if self.commit_barrier():
                raise
            self.state["apply_error"] = str(exc)
            self.journal("apply-failed-rollback-required")
            print(f"Apply failed: {exc}. Rolling back; processing stays held.", file=sys.stderr)
            with self.collection.lock():
                self.rollback()

    def rollback(self) -> None:
        require(not self.commit_barrier(), "Commit-ready restore: use --recover to finish, never roll back.")
        self.journal("rolling-back")
        backup = self.state.get("backup", {})
        manifest = {entry["destination"]: entry["sha256"] for entry in self.manifest()["entries"]}
        tag = self.evidence.name
        for action in reversed(self.state["mutations"]):
            kind, _, relative = action.partition(":")
            if kind not in ("raw", "deploy"):
                continue
            path = self.base / relative
            before = backup[relative]
            after = manifest[relative] if kind == "raw" else self.state["deploy"][relative]
            require(fingerprint(path) in {after, before["sha256"] if before else None},
                    f"Unexpected content during rollback: {relative}")
            leftover = path.with_name(f".{path.name}.{tag}.tmp")
            if leftover.exists():
                leftover.unlink()
            if before is None:
                if path.exists():
                    path.unlink()
                    sync_directory(path.parent)
            elif fingerprint(path) != before["sha256"] or path.stat().st_mtime_ns != before["mtime_ns"]:
                replace_file(path, data(self.evidence / "backup" / relative), before["mode"], tag,
                             before["mtime_ns"])
        if any(action.startswith("deploy:") for action in self.state["mutations"]):
            for relative in STALE_BYTECODE:
                before = backup[relative]
                if before is not None:
                    replace_file(self.base / relative, data(self.evidence / "backup" / relative),
                                 before["mode"], tag, before["mtime_ns"])
        require(self.collection.cron() == data(self.collection.evidence / "root-crontab.held"),
                "Processing hold changed during rollback.")
        self.journal(ROLLED_BACK)

    def recover(self) -> None:
        require(self.state["status"] != ROLLED_BACK and not self.state.get("committed"),
                "Already finished; do not mutate again.")
        if not self.commit_barrier():
            self.rollback()
            return
        self.restored(pin_pid=False)
        cron = self.collection.cron()
        if cron == data(self.collection.evidence / "root-crontab.held"):
            self.restore_cron()
        require(self.collection.cron() == data(self.collection.evidence / "root-crontab.original"),
                "Unrecognized crontab after commit-ready restore.")
        self.state["committed"] = True
        self.journal(COMMITTED)

    def verify(self) -> dict:
        require(bool(self.state.get("committed")), "Only committed restores can be verified.")
        collection = self.collection
        named = self.restored(pin_pid=False)
        require(collection.cron() == data(collection.evidence / "root-crontab.original"),
                "Daily processing cron is not restored.")
        day = collection.state["day"]
        try:
            collection.state["day"] = self.host.now().date().isoformat()
            first = collection.sample(True)
            self.host.sleep(10)
            second = collection.sample(True)
            require(second["raw_bytes"] > first["raw_bytes"] and second["raw_last"] > first["raw_last"],
                    "Named collection is not advancing.")
        finally:
            collection.state["day"] = day
        now = self.host.now()
        # The latest published page, not the wall clock, shows which daily run last completed.
        dated = [path.name for path in (self.base / "WWW/detectors/Unit_1").iterdir()
                 if path.is_dir() and len(path.name) == 10 and path.name[4] == path.name[7] == "-"]
        latest = max(dated)
        yesterday = now.date() - timedelta(days=1)
        allowed = {yesterday.isoformat()} if now.hour * 60 + now.minute >= PUBLISHED_AFTER_MINUTES \
            else {yesterday.isoformat(), (yesterday - timedelta(days=1)).isoformat()}
        require(latest in allowed, f"Latest published Unit_1 day {latest} is stale.")
        self.require_outputs(latest)
        self.require_published(latest)
        return {"status": VERIFIED, "utc": now.isoformat(), "collector_pid": int(named["MainPID"]),
                "latest_processed_day": latest}

    def load(self) -> None:
        saved = json.loads(data(self.evidence / "state.json"))
        require(saved.get("kind") == KIND and saved.get("helpers") == helper_hashes(),
                "Wrong journal kind or changed runner/helper code; review required.")
        require(all(key in saved for key in ("day", "history", "mutations", "completed", "deploy",
                                              "merge_manifest_sha256", "backfill_days", "web_before")),
                "Incomplete restore journal.")
        self.state = saved
        self.open_collection()
        self.manifest()
        self.payload = self.deployment()
        require({name: staging.digest(content) for name, content in self.payload.items()} == saved["deploy"],
                "Deployment payload changed since the journal was written.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="Default: no production mutations.")
    modes.add_argument("--apply", action="store_true", help="Requires separate restore approval and --reviewed.")
    modes.add_argument("--recover", type=Path, help="Finish or roll back an interrupted restore.")
    modes.add_argument("--verify", type=Path, help="Verify a committed restore without changes.")
    parser.add_argument("--approval")
    parser.add_argument("--reviewed", type=Path, help="Ready check evidence directory reviewed before apply.")
    args = parser.parse_args()
    if sys.platform != "linux" or os.getuid() == 0 or Path.home() != Path("/home/pi"):
        parser.error("Run on the production Pi as pi, without sudo.")
    if (args.apply or args.recover) and args.approval != APPROVAL:
        parser.error("Separate processing restore approval is required; collection approvals are invalid.")

    def evidence_dir(path: Path | None) -> bool:
        return path is not None and path.parent == Path.home() and path.name.startswith(PREFIX) \
            and path.is_dir() and not path.is_symlink()

    existing = args.recover or args.verify
    if existing and not evidence_dir(existing):
        parser.error("Invalid restore evidence directory.")
    if args.apply and not evidence_dir(args.reviewed):
        parser.error("--apply requires --reviewed with the reviewed ready check directory.")
    os.umask(0o077)
    import fcntl
    # Share the collection runners' singleton lock: these tools must never race.
    lock = os.open(Path.home() / ".unit1-collection-trial.lock",
                   os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        parser.error("Another Unit_1 runner is active.")
    evidence = existing or Path(tempfile.mkdtemp(prefix=PREFIX, dir=Path.home()))
    operation = Restore(Path.home(), Path("/etc/systemd/system"), evidence, trial.Host(evidence))
    print(f"EVIDENCE DIRECTORY: {evidence}", flush=True)
    signal.signal(signal.SIGTERM, trial.interrupted)
    signal.signal(signal.SIGHUP, trial.interrupted)
    loaded = False
    try:
        if existing:
            operation.load()
            loaded = True
            if args.verify:
                with operation.collection.lock():
                    result = operation.verify()
                save_json(evidence / "restore-verification.json", result)
                print(f"{VERIFIED}: latest processed day {result['latest_processed_day']}")
                return 0
            with operation.collection.lock():
                operation.recover()
        else:
            print("Readiness checks only until separately approved apply; archive checks may take several minutes.",
                  flush=True)
            operation.check()
            if args.apply:
                print("Approved restore: merge, deploy and backfill may take over an hour; keep this session open.",
                      flush=True)
                operation.apply(args.reviewed)
        print(operation.state["status"])
        print("Privately download evidence. No reboot performed.")
        return 1 if (args.apply or args.recover) and not operation.state.get("committed") else 0
    except FAILURES as exc:
        save_json(evidence / "last-failure.json", {"error": str(exc), "utc": operation.host.now().isoformat()})
        if (not existing or loaded) and not operation.commit_barrier() and not args.verify:
            operation.state["error"] = str(exc)
            operation.journal("FAILED_REVIEW_REQUIRED")
        print(f"FAILED: {exc}\nPreserve {evidence}. Do not repeat apply; send the evidence for review.",
              file=sys.stderr)
        return 1
    finally:
        os.close(lock)


if __name__ == "__main__":
    raise SystemExit(main())
