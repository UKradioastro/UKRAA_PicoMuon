#!/usr/bin/env python3
"""Fixed permanent Unit_1 collection-only cutover; default is readiness only."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import sys
import tempfile

import TrialUnit1Collection as trial
from TrialUnit1Collection import data, fingerprint, require, safe_target, save_json

staging = trial.staging
OLD, NAMED = trial.OLD, trial.NAMED
APPROVAL = "UNIT1-PERMANENT-COLLECTION-ONLY"
PREFIX = "unit1-permanent-collection."
TRIAL_DAY = "2026-10-22"
TRIAL_RAW_SHA256 = "03d4ac6915bc8a6215394a6f5839f79cf47dac8af0c8c2b4b7850b0e95a91a6b"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
TRIAL_STATUS_SHA256 = "afd95017061e7f632986fa71cffda426304c36dd907b4114feb5ceb700fa6b05"
TERMINAL_RECOVERY = "SINGLE_RESTORED_CRON_RESTORED"
COMMITTED = "PERMANENT_NAMED_COMMITTED_PROCESSING_HELD"
HELPERS = ("PermanentUnit1Collection.py", "TrialUnit1Collection.py", "StageUnit1Cutover.py")


def helper_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    return {name: staging.digest(data(root / name)) for name in HELPERS}


class Permanent(trial.Trial):
    def __init__(self, home: Path, units: Path, evidence: Path, host: trial.Host):
        super().__init__(home, units, evidence, host)
        self.systemd_roots = (units, Path("/run/systemd/system"), Path("/run/systemd/transient"))
        self.state.update(kind="permanent-unit1-v1", helpers=helper_hashes())

    def protect_trial(self) -> None:
        root = self.base / "data/raw/Unit_1"
        require(fingerprint(root / "2026/2026-10/2026-10-22.txt") == TRIAL_RAW_SHA256,
                "October 22 trial raw changed or missing.")
        require(fingerprint(root / "rejected/2026-10-22.txt") == EMPTY_SHA256,
                "October 22 trial rejected data changed or missing.")

    def check_named_targets(self) -> None:
        require(self.state["day"] > TRIAL_DAY, "Permanent cutover requires a later UTC day than October 22.")
        raw, _, rejected = self.files(True)
        for path in (raw, rejected):
            safe_target(path)
            require(not path.exists(), f"Cutover-day named target already exists: {path}")
        self.protect_trial()
        # Status and logs intentionally survive the accepted trial.
        paths = [self.files(True)[1]]
        logs = self.base / "logfiles/detectors/Unit_1"
        safe_target(logs)
        require(logs.is_dir(), "Reviewed named log directory missing.")
        info = logs.stat()
        require(info.st_uid == os.getuid() and info.st_gid == os.getgid()
                and not stat.S_IMODE(info.st_mode) & 0o022, "Unexpected named log directory permissions.")
        paths += [logs / "log-PicoMuon.txt", logs / "log-error.txt"]
        for path in paths:
            data(path)
            info = path.stat()
            require(info.st_uid == os.getuid() and info.st_gid == os.getgid()
                    and not stat.S_IMODE(info.st_mode) & 0o022,
                    f"Unexpected named status/log permissions: {path}")
        require(fingerprint(paths[0]) == TRIAL_STATUS_SHA256, "Pre-cutover trial status changed.")
        snapshot = self.evidence / "prior-named"
        if not snapshot.exists():
            snapshot.mkdir()
            for path, name in zip(paths, ("status.json", "log-PicoMuon.txt", "log-error.txt")):
                (snapshot / name).write_bytes(data(path))
            self.state["named_error_size"] = paths[-1].stat().st_size
            self.state["prior_named_hashes"] = {str(path): fingerprint(path) for path in paths}
            self.state["prior_named_metadata"] = {
                str(path): {"uid": path.stat().st_uid, "gid": path.stat().st_gid,
                            "mode": stat.S_IMODE(path.stat().st_mode), "bytes": path.stat().st_size}
                for path in paths}
            self.journal("prior-named-preserved")
        else:
            for path in paths:
                require(fingerprint(path) == self.state["prior_named_hashes"][str(path)],
                        f"Named status/log changed after precheck: {path}")

    def error_baseline(self, named: bool) -> int:
        return self.state["named_error_size"] if named else super().error_baseline(False)

    def record_unit_temporary(self, temporary: Path) -> None:
        require(fingerprint(temporary) == self.state["candidate_unit_hash"], "Staged unit changed.")
        info = temporary.stat()
        self.state["unit_identity"] = [info.st_dev, info.st_ino]
        self.journal("unit-staged")

    def owned_unit(self, path: Path) -> None:
        require("install-unit" in self.state["mutations"]
                and fingerprint(path) == self.state["candidate_unit_hash"],
                "Unrecognized concrete unit; refusing removal.")
        info = path.stat()
        require([info.st_dev, info.st_ino] == self.state.get("unit_identity"),
                "Unit inode is not this operation's publication; refusing removal.")

    def boot_links(self) -> dict[str, str]:
        result = {}
        for root in self.systemd_roots:
            safe_target(root)
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_symlink() and (path.name.startswith("PicoMuon")
                                          or path.resolve() in {
                                              self.units / OLD, self.units / NAMED,
                                              self.units / "PicoMuon@.service"}):
                    result[str(path)] = os.readlink(path)
                    require(path.name in (OLD, NAMED)
                            and path.parent.name == "multi-user.target.wants"
                            and path.parent.parent == self.units
                            and path.resolve() == (self.units / path.name).resolve(),
                            f"Unexpected boot link or alias: {path}")
        return result

    def expected_links(self, named: bool) -> dict[str, str]:
        if not named:
            return self.state["original_boot_links"]
        return {str(self.units / "multi-user.target.wants" / NAMED): str(self.units / NAMED)}

    def boot_state(self, named: bool) -> None:
        actual = self.boot_links()
        require(actual == self.expected_links(named), "Boot link state differs from the reviewed target.")
        for unit, expected in ((OLD, "disabled" if named else "enabled"),
                               (NAMED, "enabled" if named else "disabled")):
            output = self.host.run("systemctl", "is-enabled", unit, allowed=(0, 1)).strip()
            require(output.decode() == expected, f"Unexpected enabled state for {unit}: {output!r}")

    def set_boot(self, unit: str, enabled: bool) -> None:
        require(unit in (OLD, NAMED), "Invalid boot unit.")
        self.boot_links()  # Fail on unexpected links before modifying anything.
        action = f"{'enable' if enabled else 'disable'}-{unit}"
        self.intent(action)
        self.host.run("sudo", "-n", "systemctl", "enable" if enabled else "disable", unit)
        self.done(action)

    def check(self) -> None:
        require(self.host.now().date().isoformat() > TRIAL_DAY,
                "Readiness/apply must run on a later UTC day; preserve today's trial.")
        # Reject a new operation while an earlier mutation needs recovery or is committed.
        for path in self.home.glob(PREFIX + "*"):
            if path == self.evidence or not path.is_dir():
                continue
            state_file = path / "state.json"
            if state_file.exists():
                state = json.loads(data(state_file))
                require(not state.get("mutations") or state.get("status") == TERMINAL_RECOVERY,
                        f"Existing permanent operation requires verification/recovery: {path}")
        super().check()
        for tool in ("install", "ln", "rm"):
            require(shutil.which(tool) is not None, f"Required deployment tool missing: {tool}")
        links = self.boot_links()
        expected_path = str(self.units / "multi-user.target.wants" / OLD)
        require(links == {expected_path: str(self.units / OLD)},
                "Expected only the canonical original old-service boot link.")
        self.state["original_boot_links"] = links
        self.boot_state(False)
        self.probe(False)
        self.manifest()
        with self.lock():
            self.no_other_jobs()
        self.journal("PERMANENT_READY_NOT_AUTHORIZED")

    def unchanged_original_units(self) -> None:
        for name in (OLD, "PicoMuon@.service"):
            require(data(self.units / name) == self.host_unit_backup(name),
                    f"Original unit changed: {name}")

    def installed_hashes(self) -> None:
        expected = dict(self.hashes)
        for name in trial.CONFIGS:
            expected[f"config/{name}"] = self.state["candidate_config_hashes"][name]
        staging.check_production(self.base, expected)
        require(fingerprint(self.units / NAMED) == self.state["candidate_unit_hash"],
                "Concrete instance changed.")
        self.unchanged_original_units()

    def service_inventory(self) -> None:
        for action in ("list-units", "list-unit-files"):
            output = self.host.run("systemctl", action, "--all", "--type=service", "--no-pager",
                                   "--no-legend", "--plain").decode()
            names = {line.split()[0] for line in output.splitlines() if line.strip()
                     and line.split()[0].startswith("PicoMuon")}
            require(OLD in names and names <= {OLD, NAMED, "PicoMuon@.service"},
                    f"Unexpected permanent PicoMuon service inventory: {names}")

    def deploy(self) -> None:
        require(self.host.now().date().isoformat() == self.state["day"]
                and 8 <= self.host.now().hour <= 18, "Outside reviewed daytime window.")
        self.boot_state(False)
        self.check_named_targets()
        staging.check_production(self.base, self.hashes)
        self.unchanged_original_units()
        require(self.cron() == data(self.evidence / "root-crontab.held"), "Processing hold lost.")
        old = self.check_unit(OLD, running=True)
        self.state["live_pid"] = int(old["MainPID"])
        self.no_other_jobs()
        self.device()
        require(self.host.holders(staging.DEVICE) == {self.state["live_pid"]},
                "Old collector is not sole device owner.")
        self.set_boot(OLD, False)
        require(self.boot_links() == {}, "Old boot enablement was not removed.")
        self.check_unit(OLD, running=True)
        self.stop(OLD)
        self.state["last_old_event"] = trial.last_event(self.files(False)[0]).isoformat()
        self.state["old_frozen"] = self.signatures(self.files(False))
        self.journal("old-files-frozen")
        for name in trial.CONFIGS:
            self.publish_config(name)
        self.install_named_unit()
        self.set_boot(NAMED, True)
        self.boot_state(True)
        self.start(NAMED)
        self.healthy(True, 600)
        self.verify_retained(observe=False)
        # A durable commit barrier prevents a reporting failure from triggering rollback.
        self.journal("COMMIT_READY")
        self.state["committed"] = True
        self.journal(COMMITTED)

    def commit_barrier(self) -> bool:
        return bool(self.state.get("committed") or any(
            item["status"] in ("COMMIT_READY", COMMITTED) for item in self.state["history"]))

    def retained_state(self) -> dict[str, str]:
        self.protect_trial()
        self.installed_hashes()
        self.service_inventory()
        self.boot_state(True)
        require(self.cron() == data(self.evidence / "root-crontab.held"), "Permanent processing hold lost.")
        old = self.properties(OLD)
        require(old["MainPID"] == "0" and old["ActiveState"] == "inactive", "Old service is not stopped.")
        named = self.check_unit(NAMED, running=True)
        require(named["NRestarts"] == "0", "Named collector has restarted; review required.")
        self.state["live_pid"] = int(named["MainPID"])
        self.device()
        require(self.host.holders(staging.DEVICE) == {self.state["live_pid"]}, "Unexpected device owner.")
        self.no_other_jobs()
        self.frozen("old_frozen")
        require(fingerprint(self.base / "logfiles/detectors/Unit_1/log-error.txt")
                == staging.digest(data(self.evidence / "prior-named/log-error.txt")),
                "Named error log changed or rotated; inspect before accepting retained collection.")
        return named

    def verify_retained(self, *, observe: bool) -> None:
        named = self.retained_state()
        if observe:
            # Verification after commit may occur on a later UTC day; never restart/redeploy.
            day = self.state["day"]
            try:
                self.state["day"] = self.host.now().date().isoformat()
                first = self.sample(True)
                self.host.sleep(10)
                second = self.sample(True)
                require(second["raw_bytes"] > first["raw_bytes"]
                        and second["last_event"] > first["last_event"]
                        and second["raw_last"] > first["raw_last"], "Named collection is not advancing.")
                trial.parse_events(data(self.files(True)[0]), self.state["day"], final=False)
                current = self.retained_state()
                require(current["MainPID"] == named["MainPID"] and current["NRestarts"] == "0",
                        "Named process changed during committed verification.")
                save_json(self.evidence / "committed-observation.json", [first, second])
            finally:
                self.state["day"] = day
        summary = trial.parse_events(data(self.files(True)[0]), self.state["day"], final=False)
        save_json(self.evidence / "cutover-rows.json", summary)
        self.manifest()

    def recover(self) -> None:
        require(not self.commit_barrier(), "Committed/commit-ready run: use --verify; rollback needs separate approval.")
        self.journal("recovering")
        mutations = self.state["mutations"]
        self.protect_trial()
        self.boot_links()
        if f"stop-{OLD}" in mutations:
            old = self.properties(OLD)
            original = all(fingerprint(self.base / "config" / name)
                           == self.state["original_config_hashes"][name] for name in trial.CONFIGS)
            restored = old["ActiveState"] == "active" and original and not (self.units / NAMED).exists()
            if restored:
                require(self.host.holders(staging.DEVICE) == {int(old["MainPID"])},
                        "Unknown owner during resumed recovery.")
                self.state["live_pid"] = int(old["MainPID"])
                if "named_frozen" not in self.state:
                    self.state["named_frozen"] = self.signatures(self.files(True))
            else:
                if f"start-{NAMED}" in mutations:
                    self.stop(NAMED)
                else:
                    require(not self.host.holders(staging.DEVICE), "Device occupied during recovery.")
                if "named_frozen" in self.state:
                    self.frozen("named_frozen")
                self.state["named_frozen"] = self.signatures(self.files(True))
                self.journal("named-files-frozen")
                raw = self.files(True)[0]
                if raw.exists() and raw.stat().st_size:
                    try:
                        summary = trial.parse_events(data(raw), self.state["day"], final=True)
                        save_json(self.evidence / "failed-cutover-rows.json", summary)
                        self.state["rollback_last_named_event"] = summary["last"]
                    except (ValueError, RuntimeError, csv.Error) as exc:
                        self.state["data_validation_error"] = str(exc)
                        self.journal("invalid-partial-data-preserved")
                if f"enable-{NAMED}" in mutations:
                    self.set_boot(NAMED, False)
                for name in trial.CONFIGS:
                    self.publish_config(name, restore=True)
                target = self.units / NAMED
                if target.exists() or target.is_symlink():
                    self.owned_unit(target)
                    self.intent("remove-unit")
                    self.host.run("sudo", "-n", "rm", "--", str(target))
                    self.done("remove-unit")
                temporary = self.units / f".{NAMED}.{self.evidence.name}.tmp"
                if temporary.exists() or temporary.is_symlink():
                    self.owned_unit(temporary)
                    self.intent("remove-unit-temporary")
                    self.host.run("sudo", "-n", "rm", "--", str(temporary))
                    self.done("remove-unit-temporary")
                self.host.run("sudo", "-n", "systemctl", "daemon-reload")
            self.unchanged_original_units()
            staging.check_production(self.base, self.hashes)
            self.probe(False)
            self.check_unit(OLD, running=restored)
            self.restore_boot()
            if not restored:
                self.state["recovery_raw_offset"] = self.files(False)[0].stat().st_size
                self.start(OLD)
            else:
                self.state["start_utc"] = self.host.now().isoformat()
            self.healthy(False, 120)
            if "recovery_raw_offset" in self.state:
                with self.files(False)[0].open("rb") as handle:
                    handle.seek(self.state["recovery_raw_offset"])
                    recovery_rows = trial.parse_events(handle.read(), self.state["day"], final=False)
                self.state["recovery_first_event"] = recovery_rows["first"]
                if "rollback_last_named_event" in self.state:
                    interval = (datetime.fromisoformat(str(recovery_rows["first"]))
                                - datetime.fromisoformat(self.state["rollback_last_named_event"]))
                    self.state["rollback_event_boundary_seconds"] = interval.total_seconds()
            self.manifest()
        else:
            old = self.check_unit(OLD, running=True)
            self.state["live_pid"] = int(old["MainPID"])
            self.device()
            require(self.host.holders(staging.DEVICE) == {self.state["live_pid"]},
                    "Unexpected device owner before collection changes; hold retained for review.")
            self.no_other_jobs()
            self.unchanged_original_units()
            staging.check_production(self.base, self.hashes)
            self.probe(False)
            self.restore_boot()
        self.protect_trial()
        self.boot_state(False)
        self.service_inventory()
        if "hold-cron" in mutations:
            if self.cron() != data(self.evidence / "root-crontab.original"):
                self.set_cron(False)
        self.journal(TERMINAL_RECOVERY)

    def restore_boot(self) -> None:
        if f"disable-{OLD}" in self.state["mutations"]:
            self.set_boot(OLD, True)
        self.boot_state(False)

    def execute(self) -> None:
        recovery_attempted = False
        try:
            self.set_cron(True)
            with self.lock():
                try:
                    self.deploy()
                except (OSError, ValueError, RuntimeError, csv.Error, KeyboardInterrupt) as exc:
                    if self.commit_barrier():
                        raise
                    self.state["apply_error"] = str(exc)
                    self.journal("apply-failed-recovery-required")
                    print(f"Apply failed: {exc}. Attempting guarded recovery.", file=sys.stderr)
                    recovery_attempted = True
                    self.recover()
        except (OSError, ValueError, RuntimeError, csv.Error, KeyboardInterrupt):
            if not recovery_attempted and not self.commit_barrier() \
                    and f"disable-{OLD}" not in self.state["mutations"]:
                self.recover()
            raise

    def load(self) -> None:
        saved = json.loads(data(self.evidence / "state.json"))
        require(saved.get("kind") == "permanent-unit1-v1" and saved.get("helpers") == helper_hashes(),
                "Wrong journal kind or changed runner/helper code; review required.")
        require(all(key in saved for key in ("day", "history", "mutations", "completed",
                "config_modes", "original_boot_links", "original_config_hashes",
                "candidate_config_hashes", "candidate_unit_hash")),
                "Incomplete permanent journal.")
        self.state = saved
        self.host.sequence = max(
            (int(path.name.split("-")[1].split(".")[0])
             for path in self.evidence.glob("command-*.argv.json")), default=0)
        self.verify_package()
        for name in trial.CONFIGS:
            require(data(self.evidence / "recovery" / name) == self.backup[f"config/{name}"],
                    f"Recovery config changed: {name}")
            require(self.state["original_config_hashes"][name] == staging.digest(self.backup[f"config/{name}"])
                    and self.state["candidate_config_hashes"][name] == staging.digest(
                        data(self.stage / "candidate/config" / name)), "Journal config pin changed.")
            trial.checked_config_mode(name, self.state["config_modes"][name])
        require(data(self.evidence / "root-crontab.original") == data(self.preflight / "root-crontab.txt")
                and data(self.evidence / "root-crontab.held") == trial.held_cron(
                    data(self.evidence / "root-crontab.original")), "Recovery cron changed.")
        require(self.state["candidate_unit_hash"] == staging.digest(data(self.stage / "units" / NAMED)),
                "Journal unit pin changed.")
        links = self.state["original_boot_links"]
        require(links == {str(self.units / "multi-user.target.wants" / OLD): str(self.units / OLD)},
                "Unrecognized original boot links.")
        require(self.state["day"] > TRIAL_DAY, "Invalid cutover day in journal.")
        require(date.fromisoformat(self.state["day"]).isoformat() == self.state["day"],
                "Noncanonical cutover date.")
        error_backup = self.evidence / "prior-named/log-error.txt"
        require(self.state.get("named_error_size") == len(data(error_backup)),
                "Named error baseline changed.")
        expected_paths = set(map(str, self.files(False)))
        require(not self.state.get("old_frozen") or set(self.state["old_frozen"]) == expected_paths,
                "Unexpected old frozen-file paths.")
        require(not self.state.get("named_frozen")
                or set(self.state["named_frozen"]) == set(map(str, self.files(True))),
                "Unexpected named frozen-file paths.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="Default: no production mutations.")
    modes.add_argument("--apply", action="store_true", help="Requires separate permanent execution approval.")
    modes.add_argument("--recover", type=Path, help="Recover an uncommitted interrupted operation.")
    modes.add_argument("--verify", type=Path, help="Verify retained committed operation without service changes.")
    parser.add_argument("--approval")
    args = parser.parse_args()
    if sys.platform != "linux" or os.getuid() == 0 or Path.home() != Path("/home/pi"):
        parser.error("Run on the production Pi as pi, without sudo.")
    if (args.apply or args.recover) and args.approval != APPROVAL:
        parser.error("Separate permanent apply/recovery approval is required; trial approval is invalid.")
    existing = args.recover or args.verify
    if existing and not (existing.parent == Path.home() and existing.name.startswith(PREFIX)
                         and existing.is_dir() and not existing.is_symlink()):
        parser.error("Invalid permanent evidence directory.")
    os.umask(0o077)
    import fcntl
    # Share the trial runner's singleton lock: the two tools must never race.
    lock = os.open(Path.home() / ".unit1-collection-trial.lock",
                   os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        parser.error("Another Unit_1 runner is active.")
    evidence = existing or Path(tempfile.mkdtemp(prefix=PREFIX, dir=Path.home()))
    operation = Permanent(Path.home(), Path("/etc/systemd/system"), evidence, trial.Host(evidence))
    print(f"EVIDENCE DIRECTORY: {evidence}", flush=True)
    signal.signal(signal.SIGTERM, trial.interrupted)
    signal.signal(signal.SIGHUP, trial.interrupted)
    loaded = False
    try:
        if existing:
            operation.load()
            loaded = True
            if args.verify:
                require(operation.commit_barrier(), "Only committed/commit-ready runs can be verified.")
                with operation.lock():
                    operation.verify_retained(observe=True)
                save_json(evidence / "retained-verification.json",
                          {"status": "RETAINED_NAMED_VERIFIED_PROCESSING_HELD",
                           "utc": operation.host.now().isoformat()})
                print("RETAINED_NAMED_VERIFIED_PROCESSING_HELD")
                return 0
            require(operation.state["day"] == operation.host.now().date().isoformat(),
                    "Recovery across UTC rollover requires manual review.")
            require(operation.state["status"] != TERMINAL_RECOVERY, "Already recovered; do not mutate again.")
            with operation.lock():
                operation.recover()
        else:
            print("Readiness checks only until separately approved apply; archive checks may take several minutes.",
                  flush=True)
            operation.check()
            if args.apply:
                operation.execute()
        print(operation.state["status"])
        print("Privately download evidence. Processing remains held after committed success; no reboot performed.")
        return 1 if args.apply and not operation.commit_barrier() else 0
    except (OSError, ValueError, RuntimeError, csv.Error, KeyboardInterrupt) as exc:
        # Preserve committed state and interrupted journals; a verifier failure must not roll back.
        save_json(evidence / "last-failure.json", {"error": str(exc), "utc": operation.host.now().isoformat()})
        if not existing or loaded:
            if not operation.commit_barrier() and not args.verify:
                operation.state["error"] = str(exc)
                operation.journal("FAILED_REVIEW_REQUIRED")
        print(f"FAILED: {exc}\nPreserve {evidence}. Do not repeat apply or start another collector.",
              file=sys.stderr)
        return 1
    finally:
        os.close(lock)


if __name__ == "__main__":
    raise SystemExit(main())
