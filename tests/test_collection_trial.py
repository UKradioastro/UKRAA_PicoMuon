from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import TrialUnit1Collection as runner


def event(stamp):
    return (f"{stamp:%Y-%m-%d %H:%M:%S.%f},T,1,250,1000,0,22,1000,Unit one,"
            "200,100,200,100\n").encode()


class ModelHost:
    def __init__(self, trial):
        self.trial = trial
        self.current = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
        self.elapsed = 0
        self.running = runner.OLD
        self.owner = 900000001
        self.calls = []
        self.cron = b"# unrelated\n" + runner.DAILY + b"\n0 0 * * 0 rotate\n"
        self.fail = None
        self.busy = False
        self.restarts = "0"
        self.stale = False
        self.freeze = False
        self.bad_rows = False
        self.emit()

    def now(self):
        return self.current

    def ticks(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds
        self.current += timedelta(seconds=seconds)
        self.emit()

    def holders(self, device):
        return {99} if self.busy else {self.owner} if self.running else set()

    def emit(self):
        if not self.running or self.freeze:
            return
        named = self.running == runner.NAMED
        raw, status, rejected = self.trial.files(named)
        raw.parent.mkdir(parents=True, exist_ok=True)
        status.parent.mkdir(parents=True, exist_ok=True)
        rejected.parent.mkdir(parents=True, exist_ok=True)
        with raw.open("ab") as handle:
            row = event(self.current)
            handle.write(row.replace(b",200,100,200,100", b",250,100,200,100") if self.bad_rows else row)
        stamp = self.current - timedelta(seconds=60) if self.stale else self.current
        status.write_text(json.dumps({
            "last_event_utc": stamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_events_today": 1,
        }))
        rejected.touch()
        logs = self.trial.base / ("logfiles/detectors/Unit_1" if named else "logfiles")
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "log-error.txt").touch()

    def props(self, unit):
        active = unit == self.running
        props = {key: "" for key in runner.PROPERTIES}
        props.update(
            MainPID=str(self.owner) if active else "0", ActiveState="active" if active else "inactive",
            SubState="running" if active else "dead", NRestarts=self.restarts if unit == runner.NAMED else "0",
            FragmentPath=str(self.trial.units / unit), WorkingDirectory=str(self.trial.base),
            User="pi", Group="pi", SupplementaryGroups="dialout",
            Environment=shlex.quote(f"PICOMUON_BASE_PATH={self.trial.base}") + " TERM=dumb",
            ExecStart="{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 "
                      + f"{self.trial.base}/scripts/GetDataRaw.py"
                      + (" --detector Unit_1" if unit == runner.NAMED else "")
                      + " ; ignore_errors=no ; }",
            UnitFileState="enabled" if unit == runner.OLD else "disabled",
        )
        return "\n".join(f"{key}={value}" for key, value in props.items()).encode()

    def run(self, *args, **kwargs):
        self.calls.append(args)
        cmd = args[2:] if args[:2] == ("sudo", "-n") else args
        if cmd[:2] == ("systemctl", "show"):
            return self.props(cmd[2])
        if cmd[:2] == ("crontab", "-l"):
            return self.cron
        if cmd[0] == "crontab":
            self.cron = Path(cmd[1]).read_bytes()
        elif cmd[:2] == ("systemctl", "stop"):
            if self.fail == ("stop", cmd[2]):
                raise RuntimeError("injected stop failure")
            if self.running == cmd[2]:
                self.running = None
        elif cmd[:2] == ("systemctl", "start"):
            self.running = cmd[2]
            self.owner += 1
            self.current += timedelta(seconds=1)
            self.emit()
            if self.fail == ("start", cmd[2]):
                self.fail = None
                raise RuntimeError("injected start timeout after process launch")
        elif cmd[0] == "udevadm":
            return (f"ID_SERIAL={runner.staging.IDENTITY}\n"
                    f"ID_SERIAL_SHORT={runner.staging.SHORT_ID}\n").encode()
        elif cmd[0] == "ps":
            return (f"{self.owner} /usr/bin/python3 {self.trial.base}/scripts/GetDataRaw.py\n"
                    if self.running else "").encode()
        elif cmd[:2] in (("systemctl", "list-units"), ("systemctl", "list-unit-files")):
            return b"PicoMuon.service enabled enabled\nPicoMuon@.service disabled enabled\n"
        elif cmd[:2] == ("systemctl", "is-enabled"):
            return b"disabled\n"
        elif cmd[0] == "install":
            Path(cmd[-1]).write_bytes(Path(cmd[-2]).read_bytes())
        elif cmd[0] == "ln":
            os.link(cmd[-2], cmd[-1])
        elif cmd[0] == "rm":
            Path(cmd[-1]).unlink()
        return b""


class ModelTrial(runner.Trial):
    busy_lock = False

    @contextmanager
    def lock(self):
        if self.busy_lock:
            raise RuntimeError("PicoMuon cron lock busy")
        yield

    def manifest(self):
        self.host.calls.append(("archive-validation",))

    def host_unit_backup(self, name):
        return self.saved_units[name]


class CollectionTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.units = self.root / "units"
        self.units.mkdir()
        self.trial = ModelTrial(self.root / "home", self.units, self.evidence, DummyClock())
        t = self.trial
        t.saved_units = {runner.OLD: b"original unit\n", "PicoMuon@.service": b"pilot template\n"}
        for name, payload in t.saved_units.items():
            (self.units / name).write_bytes(payload)
        for directory in ("config", "scripts", "logfiles"):
            (t.base / directory).mkdir(parents=True)
        (t.base / "logfiles/log-error.txt").touch()
        (t.stage / "candidate/config").mkdir(parents=True)
        (t.stage / "units").mkdir()
        (t.stage / "units" / runner.NAMED).write_bytes(b"production named unit\n")
        (self.evidence / "recovery").mkdir()
        self.original = {}
        for name in runner.CONFIGS:
            self.original[name] = f"original {name}\n".encode()
            (t.base / "config" / name).write_bytes(self.original[name])
            (self.evidence / "recovery" / name).write_bytes(self.original[name])
            (t.stage / "candidate/config" / name).write_bytes(f"candidate {name}\n".encode())
        t.hashes = {f"config/{name}": runner.staging.digest(payload)
                    for name, payload in self.original.items()}
        t.host = ModelHost(t)
        for name in ("original", "held"):
            payload = t.host.cron if name == "original" else runner.held_cron(t.host.cron)
            (self.evidence / f"root-crontab.{name}").write_bytes(payload)
        t.state.update(
            live_pid=t.host.owner, old_restarts="0", old_error_size=0,
            config_modes=dict(runner.CONFIG_MODES),
            original_config_hashes={name: runner.staging.digest(payload)
                                    for name, payload in self.original.items()},
            candidate_config_hashes={
                name: runner.staging.digest((t.stage / "candidate/config" / name).read_bytes())
                for name in runner.CONFIGS},
            candidate_unit_hash=runner.staging.digest((t.stage / "units" / runner.NAMED).read_bytes()),
        )
        self.addCleanup(patch.stopall)
        patch.object(runner.staging, "production_hashes", return_value=t.hashes).start()
        # Kernel durability syscalls are covered on Linux; Windows lacks fchmod/O_DIRECTORY.
        if os.name == "nt":
            patch.object(runner.os, "fchmod", create=True).start()

    def assert_restored(self):
        t = self.trial
        self.assertEqual(t.host.running, runner.OLD)
        self.assertEqual(t.host.cron, (self.evidence / "root-crontab.original").read_bytes())
        for name, payload in self.original.items():
            self.assertEqual((t.base / "config" / name).read_bytes(), payload)
        self.assertFalse((self.units / runner.NAMED).exists())
        self.assertEqual((self.units / "PicoMuon@.service").read_bytes(), b"pilot template\n")
        for command in t.host.calls:
            self.assertFalse(any(word in ("enable", "disable", "restart", "reboot") for word in command))

    def test_successful_ten_minute_trial_and_planned_recovery(self):
        self.trial.execute()
        self.assert_restored()
        self.assertEqual(self.trial.state["status"], "TRIAL_PASSED_AND_SINGLE_RESTORED")
        samples = json.loads((self.evidence / "named-observation.json").read_text())
        self.assertGreaterEqual(len(samples), 61)
        self.assertGreaterEqual(self.trial.host.elapsed, 720)
        named = self.trial.files(True)[0]
        self.assertTrue(named.exists())
        self.assertIn("final_named_rows", self.trial.state)
        calls = self.trial.host.calls
        stop_old = calls.index(("sudo", "-n", "systemctl", "stop", runner.OLD))
        start_named = calls.index(("sudo", "-n", "systemctl", "start", runner.NAMED))
        stop_named = calls.index(("sudo", "-n", "systemctl", "stop", runner.NAMED))
        start_old = calls.index(("sudo", "-n", "systemctl", "start", runner.OLD))
        self.assertLess(stop_old, start_named)
        self.assertLess(stop_named, start_old)

    def test_busy_lock_restores_only_cron(self):
        self.trial.busy_lock = True
        with self.assertRaisesRegex(RuntimeError, "lock busy"):
            self.trial.execute()
        self.assert_restored()
        self.assertNotIn(f"stop-{runner.OLD}", self.trial.state["mutations"])

    def test_partial_configuration_publication_recovers(self):
        original = self.trial.publish_config

        def interrupted_publish(name, restore=False):
            original(name, restore)
            if name == "USB.ini" and not restore:
                raise RuntimeError("injected crash after first config")
        self.trial.publish_config = interrupted_publish
        self.trial.execute()
        self.assert_restored()
        self.assertFalse(self.trial.state["trial_passed"])

    def test_start_timeout_after_launch_still_stops_named_before_recovery(self):
        self.trial.host.fail = ("start", runner.NAMED)
        self.trial.execute()
        self.assert_restored()
        self.assertIn(f"stop-{runner.NAMED}", self.trial.state["completed"])

    def test_named_stop_failure_never_starts_old_and_keeps_cron_held(self):
        self.trial.host.fail = ("stop", runner.NAMED)
        with self.assertRaisesRegex(RuntimeError, "stop failure"):
            self.trial.execute()
        self.assertEqual(self.trial.host.running, runner.NAMED)
        self.assertNotIn(("sudo", "-n", "systemctl", "start", runner.OLD), self.trial.host.calls)
        self.assertIn(runner.HOLD, self.trial.host.cron)

    def test_busy_device_after_stop_never_starts_either_collector(self):
        stop = self.trial.stop

        def busy_after_stop(unit):
            stop(unit)
            self.trial.host.busy = True
        self.trial.stop = busy_after_stop
        with self.assertRaisesRegex(RuntimeError, "occupied"):
            self.trial.execute()
        self.assertIsNone(self.trial.host.running)
        self.assertFalse(any("start" in command for command in self.trial.host.calls))
        self.assertIn(runner.HOLD, self.trial.host.cron)

    def test_concurrent_cron_edit_is_not_overwritten(self):
        recover = self.trial.recover

        def edited_cron():
            self.trial.host.cron += b"# admin edit\n"
            recover()
        self.trial.recover = edited_cron
        with self.assertRaisesRegex(RuntimeError, "Crontab edited concurrently"):
            self.trial.execute()
        self.assertIn(b"# admin edit", self.trial.host.cron)
        self.assertIn(runner.HOLD, self.trial.host.cron)

    def test_unrecognized_configuration_is_never_overwritten(self):
        publish = self.trial.publish_config

        def edit(name, restore=False):
            if restore:
                (self.trial.base / "config" / name).write_bytes(b"third party\n")
            publish(name, restore)
        self.trial.publish_config = edit
        with self.assertRaisesRegex(RuntimeError, "Concurrent config edit"):
            self.trial.execute()
        self.assertNotIn(("sudo", "-n", "systemctl", "start", runner.OLD), self.trial.host.calls)

    def test_interrupted_publication_can_be_recovered_from_intent(self):
        publish = self.trial.publish_config

        def crash(name, restore=False):
            publish(name, restore)
            if not restore:
                raise SystemExit("simulated power loss")
        self.trial.publish_config = crash
        with self.assertRaises(SystemExit):
            self.trial.execute()
        self.trial.publish_config = publish
        saved = json.loads((self.evidence / "state.json").read_text())
        self.assertIn("publish-USB.ini", saved["mutations"])
        self.trial.state = saved
        self.trial.recover()
        self.assert_restored()

    def test_resumed_recovery_does_not_restart_already_restored_single_service(self):
        self.trial.execute()
        self.trial.state["status"] = "interrupted-after-recovery-before-report"
        starts = sum(command == ("sudo", "-n", "systemctl", "start", runner.OLD)
                     for command in self.trial.host.calls)
        self.trial.recover()
        self.assert_restored()
        self.assertEqual(sum(command == ("sudo", "-n", "systemctl", "start", runner.OLD)
                             for command in self.trial.host.calls), starts)

    def test_raw_validation_thresholds_order_partial_rows_and_wrong_day(self):
        stamp = self.trial.host.now()
        valid = event(stamp)
        self.assertEqual(runner.parse_events(valid, "2026-10-22", final=True)["events"], 1)
        self.assertEqual(runner.parse_events(valid + b"partial", "2026-10-22", final=False)["events"], 1)
        cases = [
            valid + b"partial", valid.replace(b",200,100,200,100", b",250,100,200,100"),
            valid + event(stamp - timedelta(seconds=1)), valid.replace(b",22,1000,", b",nan,1000,"),
            valid.replace(b",T,", b",X,"),
        ]
        for content in cases:
            with self.subTest(content=content), self.assertRaises((ValueError, RuntimeError)):
                runner.parse_events(content, "2026-10-22", final=True)
        with self.assertRaisesRegex(RuntimeError, "Wrong-day"):
            runner.parse_events(valid, "2026-10-23", final=True)

    def test_cron_hold_requires_exactly_one_unheld_line(self):
        for payload in (b"", runner.DAILY + b"\n" + runner.DAILY, runner.HOLD + runner.DAILY):
            with self.subTest(payload=payload), self.assertRaises(RuntimeError):
                runner.held_cron(payload)
        original = self.trial.host.cron
        self.assertEqual(runner.held_cron(original).replace(runner.HOLD, b""), original)

    def test_status_staleness_and_no_advancement_fail_acceptance(self):
        for field in ("stale", "freeze"):
            with self.subTest(field=field):
                setattr(self.trial.host, field, True)
                self.trial.state["start_utc"] = self.trial.host.now().isoformat()
                if field == "stale":
                    self.trial.host.emit()
                    with self.assertRaisesRegex(RuntimeError, "stale"):
                        self.trial.sample(False)
                else:
                    self.trial.state["named_frozen"] = self.trial.signatures(self.trial.files(True))
                    with self.assertRaisesRegex(RuntimeError, "stopped advancing"):
                        self.trial.healthy(False, 120)
                setattr(self.trial.host, field, False)
                self.trial.host.emit()

    def test_fuser_errors_are_not_treated_as_free(self):
        host = runner.Host(self.evidence)

        def fake_run(*command, **kwargs):
            host.sequence += 1
            if "fuser" in command:
                prefix = self.evidence / f"command-{host.sequence:04d}"
                prefix.with_suffix(".exit").write_text("1")
                prefix.with_suffix(".stderr").write_bytes(b"permission denied")
            return b""
        with patch.object(host, "run", side_effect=fake_run), self.assertRaisesRegex(RuntimeError, "fuser error"):
            host.holders("/dev/example")

    def test_fuser_accepts_alias_or_resolved_label_and_rejects_ambiguous_output(self):
        device = runner.staging.DEVICE
        resolved = Path("/dev/ttyACM0")
        cases = [
            (0, b" 1215267", device.encode() + b":       \n", {1215267}),
            (0, b" 1215267", os.fsencode(resolved) + b":       \n", {1215267}),
            (0, b" 1215267 42", os.fsencode(resolved) + b":\n", {1215267, 42}),
            (1, b"", b"", set()),
            (1, b"", b"permission denied", None),
            (0, b"1215267", b"/dev/ttyACM1:", None),
            (0, b"1215267", os.fsencode(resolved) + b":\nwarning", None),
            (0, b"1215267", b"", None),
            (0, b"", os.fsencode(resolved) + b":", None),
            (0, b"1215267x", os.fsencode(resolved) + b":", None),
            (0, b"0", os.fsencode(resolved) + b":", None),
        ]
        for code, stdout, stderr, expected in cases:
            with self.subTest(code=code, stdout=stdout, stderr=stderr):
                host = runner.Host(self.evidence)

                def fake_run(*command, **kwargs):
                    host.sequence += 1
                    if "fuser" in command:
                        prefix = self.evidence / f"command-{host.sequence:04d}"
                        prefix.with_suffix(".exit").write_text(str(code))
                        prefix.with_suffix(".stderr").write_bytes(stderr)
                        return stdout
                    return b""
                with patch.object(host, "run", side_effect=fake_run), \
                        patch.object(runner.Path, "resolve", return_value=resolved):
                    if expected is None:
                        with self.assertRaises(RuntimeError):
                            host.holders(device)
                    else:
                        self.assertEqual(host.holders(device), expected)

    def test_extra_command_arguments_and_environment_are_rejected(self):
        original = self.trial.host.props
        for old, new in ((b" ; ignore", b" --unexpected ; ignore"),
                         (b"TERM=dumb", b"TERM=dumb PICOMUON_USB_INI_PATH=/wrong")):
            with self.subTest(extra=new), \
                    patch.object(self.trial.host, "props",
                                 side_effect=lambda unit: original(unit).replace(old, new)), \
                    self.assertRaisesRegex(RuntimeError, "Incorrect"):
                self.trial.check_unit(runner.OLD, running=True)

    def test_check_mode_records_readiness_without_mutation(self):
        t = self.trial
        t.preflight.mkdir(parents=True)
        (t.preflight / "root-crontab.txt").write_bytes(t.host.cron)
        for path in (self.evidence / "recovery").iterdir():
            path.unlink()
        (self.evidence / "recovery").rmdir()
        t.backup = {f"config/{name}": payload for name, payload in self.original.items()}
        with patch.object(t, "verify_package"), patch.object(t, "verify_system_cron"), \
                patch.object(runner.shutil, "which", return_value="/mock/tool"), \
                patch.object(runner.os, "getuid", return_value=0, create=True), \
                patch.object(runner.os, "getgid", return_value=0, create=True), \
                patch.object(runner.stat, "S_IMODE", side_effect=[0o644, 0o664]):
            t.check()
        self.assertEqual(t.state["status"], "READY_FOR_REVIEW_NOT_AUTHORIZED")
        self.assertEqual(t.state["mutations"], [])
        self.assert_restored()
        for command in t.host.calls:
            cmd = command[2:] if command[:2] == ("sudo", "-n") else command
            self.assertFalse(cmd[:2] in (("systemctl", "start"), ("systemctl", "stop")))
            self.assertFalse(cmd and cmd[0] in ("install", "ln", "rm"))
            if cmd and cmd[0] == "crontab":
                self.assertEqual(cmd, ("crontab", "-l"))

    def test_config_modes_match_reviewed_backup_and_reject_drift(self):
        self.assertEqual(runner.checked_config_mode("USB.ini", 0o644), 0o644)
        self.assertEqual(runner.checked_config_mode("legacy.ini", 0o664), 0o664)
        for name, mode in (("USB.ini", 0o664), ("legacy.ini", 0o644),
                           ("legacy.ini", 0o666), ("legacy.ini", 0o775),
                           ("USB.ini", 0o4644)):
            with self.subTest(name=name, mode=mode), \
                    self.assertRaisesRegex(RuntimeError, "reviewed mode"):
                runner.checked_config_mode(name, mode)

    def test_config_publication_and_restore_preserve_reviewed_modes(self):
        for name in runner.CONFIGS:
            for restore in (False, True):
                with self.subTest(name=name, restore=restore), \
                        patch.object(runner.os, "fchmod", create=True) as chmod:
                    self.trial.publish_config(name, restore=restore)
                self.assertEqual(chmod.call_args.args[1], runner.CONFIG_MODES[name])
        self.trial.state["config_modes"]["legacy.ini"] = 0o666
        with self.assertRaisesRegex(RuntimeError, "reviewed mode"):
            self.trial.publish_config("legacy.ini", restore=True)

    def test_automatic_restarts_reject_trial(self):
        self.trial.host.restarts = "1"
        self.trial.execute()
        self.assert_restored()
        self.assertFalse(self.trial.state["trial_passed"])
        self.assertIn("restarted", self.trial.state["trial_error"])

    def test_excessive_event_interval_rejects_trial(self):
        stop = self.trial.stop

        def long_stop(unit):
            stop(unit)
            if unit == runner.OLD:
                self.trial.host.sleep(121)
        self.trial.stop = long_stop
        self.trial.execute()
        self.assert_restored()
        self.assertFalse(self.trial.state["trial_passed"])
        self.assertIn("exceeds 120", self.trial.state["trial_error"])

    def test_journal_can_replace_state_after_orphaned_temporary_write(self):
        (self.evidence / ".state.json.orphan.writing").write_text("interrupted")
        self.trial.journal("first")
        self.trial.journal("second")
        self.assertEqual(json.loads((self.evidence / "state.json").read_text())["status"], "second")

    def test_mutating_modes_require_explicit_separate_approval_before_any_io(self):
        for arguments in (["--trial"], ["--recover", "/home/pi/unit1-collection-trial.example"]):
            with self.subTest(arguments=arguments), \
                    patch.object(sys, "argv", ["TrialUnit1Collection.py", *arguments]), \
                    patch.object(sys, "platform", "linux"), \
                    patch.object(runner.os, "getuid", return_value=1000, create=True), \
                    patch.object(runner.Path, "home", return_value=Path("/home/pi")), \
                    patch.object(runner.os, "open") as opened, \
                    patch("sys.stderr", new_callable=io.StringIO), \
                    self.assertRaises(SystemExit) as stopped:
                runner.main()
            self.assertEqual(stopped.exception.code, 2)
            opened.assert_not_called()

    def test_unit_publication_refuses_to_clobber_a_concurrent_unit(self):
        original = self.trial.host.run

        def create_concurrent_unit(*command, **kwargs):
            if command[:4] == ("sudo", "-n", "ln", "-T"):
                (self.units / runner.NAMED).write_bytes(b"third-party unit\n")
            return original(*command, **kwargs)
        with patch.object(self.trial.host, "run", side_effect=create_concurrent_unit), \
                self.assertRaisesRegex(RuntimeError, "unrecognized concrete unit"):
            self.trial.execute()
        self.assertEqual((self.units / runner.NAMED).read_bytes(), b"third-party unit\n")
        self.assertNotIn(("sudo", "-n", "systemctl", "start", runner.OLD), self.trial.host.calls)
        self.assertIn(runner.HOLD, self.trial.host.cron)

    def test_startup_without_events_times_out_at_thirty_seconds(self):
        self.trial.host.running = runner.NAMED
        self.trial.host.freeze = True
        self.trial.state["start_utc"] = self.trial.host.now().isoformat()
        with self.assertRaisesRegex(RuntimeError, "within 30 seconds"):
            self.trial.healthy(True, 600)
        self.assertEqual(self.trial.host.elapsed, 30)

    def test_recovery_waits_for_new_raw_and_status_instead_of_rejecting_old_status(self):
        t = self.trial
        t.host.current += timedelta(minutes=11)
        t.state["start_utc"] = t.host.now().isoformat()
        t.state["named_frozen"] = t.signatures(t.files(True))
        slept = t.host.sleep

        def delayed_status(seconds):
            slept(seconds)
            if t.host.elapsed < 5:
                # Simulate the collector's status-write cadence after fresh raw arrives.
                path = t.files(False)[1]
                value = json.loads(path.read_text())
                value["last_event_utc"] = "2026-10-22 10:00:00 UTC"
                path.write_text(json.dumps(value))
        with patch.object(t.host, "sleep", side_effect=delayed_status):
            t.healthy(False, 120)
        self.assertGreaterEqual(t.host.elapsed, 125)
        self.assertEqual(t.host.running, runner.OLD)
        self.assertFalse(any(command[:4] == ("sudo", "-n", "systemctl", "start")
                             for command in t.host.calls))

    @unittest.skipUnless(sys.platform == "linux", "Native flock requires Linux")
    def test_native_wrapper_lock_is_exclusive_and_does_not_replace_inode(self):
        path = self.trial.base / "logfiles/.picomuon-cron.lock"
        path.write_bytes(b"preserve lock bytes\n")
        path.chmod(0o444)
        inode = path.stat().st_ino
        with runner.Trial.lock(self.trial):
            with self.assertRaisesRegex(RuntimeError, "lock busy"):
                with runner.Trial.lock(self.trial):
                    self.fail("Second lock unexpectedly acquired")
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.read_bytes(), b"preserve lock bytes\n")
        with runner.Trial.lock(self.trial):
            pass

    def test_wrapper_lock_opens_existing_file_read_only_without_recreation(self):
        import types
        path = self.trial.base / "logfiles/.picomuon-cron.lock"
        path.write_bytes(b"preserve lock bytes\n")
        flock = unittest.mock.Mock()
        fake = types.SimpleNamespace(flock=flock, LOCK_EX=2, LOCK_NB=4)
        with patch.dict(sys.modules, {"fcntl": fake}), \
                patch.object(runner.os, "O_NOFOLLOW", 0x20000, create=True), \
                patch.object(runner.os, "open", return_value=123) as opened, \
                patch.object(runner.os, "close") as closed:
            with runner.Trial.lock(self.trial):
                pass
        opened.assert_called_once_with(path, os.O_RDONLY | 0x20000)
        flock.assert_called_once_with(123, 6)
        closed.assert_called_once_with(123)
        self.assertEqual(path.read_bytes(), b"preserve lock bytes\n")


class DummyClock:
    def now(self):
        return datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
