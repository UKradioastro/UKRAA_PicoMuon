from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_collection_trial as trial_tests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import PermanentUnit1Collection as runner

trial = runner.trial


class PermanentHost(trial_tests.ModelHost):
    def __init__(self, operation):
        super().__init__(operation)
        self.current = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)
        self.link_fault = None
        self.emit()

    def emit(self):
        invalid = self.bad_rows
        original_day = self.trial.state["day"]
        self.trial.state["day"] = self.current.date().isoformat()
        if self.running == runner.OLD:
            self.bad_rows = False
        try:
            super().emit()
        finally:
            self.bad_rows = invalid
            self.trial.state["day"] = original_day

    def props(self, unit):
        output = super().props(unit)
        link = self.trial.units / "multi-user.target.wants" / unit
        enabled = b"enabled" if link.is_symlink() else b"disabled"
        lines = [b"UnitFileState=" + enabled if line.startswith(b"UnitFileState=") else line
                 for line in output.splitlines()]
        return b"\n".join(lines)

    def run(self, *args, **kwargs):
        cmd = args[2:] if args[:2] == ("sudo", "-n") else args
        if cmd[:2] in (("systemctl", "enable"), ("systemctl", "disable")):
            self.calls.append(args)
            action, unit = cmd[1:]
            if self.fail == (action, unit):
                self.fail = None
                raise RuntimeError(f"injected {action} failure")
            link = self.trial.units / "multi-user.target.wants" / unit
            if action == "enable" and not link.is_symlink():
                link.symlink_to(self.trial.units / unit)
            elif action == "disable" and link.is_symlink():
                link.unlink()
            if self.link_fault == (action, unit):
                self.link_fault = None
                raise RuntimeError("injected timeout after boot mutation")
            return b""
        if cmd[:2] == ("systemctl", "is-enabled"):
            self.calls.append(args)
            link = self.trial.units / "multi-user.target.wants" / cmd[2]
            return b"enabled\n" if link.is_symlink() else b"disabled\n"
        return super().run(*args, **kwargs)


class ModelPermanent(runner.Permanent):
    def manifest(self):
        self.host.calls.append(("archive-validation",))

    def host_unit_backup(self, name):
        return self.saved_units[name]

    def lock(self):
        return self.fixture.lock()


class PermanentCollectionTests(unittest.TestCase):
    def setUp(self):
        # Reuse the tested disposable host fixture, not its trial implementation.
        fixture = trial_tests.CollectionTrialTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.evidence = fixture.evidence
        self.units = fixture.units
        operation = ModelPermanent(fixture.trial.home, self.units, self.evidence,
                                   fixture.trial.host)
        operation.fixture = fixture.trial
        operation.state = dict(fixture.trial.state)
        operation.state.update(day="2026-10-23", kind="permanent-unit1-v1",
                               helpers=runner.helper_hashes())
        operation.saved_units = fixture.trial.saved_units
        operation.hashes = fixture.trial.hashes
        operation.backup = {f"config/{name}": value for name, value in fixture.original.items()}
        operation.systemd_roots = (self.units,)
        operation.host = PermanentHost(operation)
        self.operation = operation
        self.original = fixture.original
        if os.name == "nt":
            # Windows cannot create symlinks without privileges. Model only boot links;
            # actual regular config/unit files and all validation code remain in use.
            links = {}
            real_is_link, real_resolve = Path.is_symlink, Path.resolve
            real_unlink, real_readlink = Path.unlink, os.readlink

            def symlink(path, target, target_is_directory=False):
                path.write_bytes(b"")
                links[path] = str(target)

            def unlink(path, *args, **kwargs):
                links.pop(path, None)
                return real_unlink(path, *args, **kwargs)

            patch.object(Path, "symlink_to", symlink).start()
            patch.object(Path, "is_symlink", lambda path: path in links or real_is_link(path)).start()
            patch.object(Path, "resolve", lambda path, **kwargs:
                         real_resolve(Path(links[path]), **kwargs) if path in links
                         else real_resolve(path, **kwargs)).start()
            patch.object(Path, "unlink", unlink).start()
            patch.object(os, "readlink", lambda path, **kwargs:
                         links[path] if path in links else real_readlink(path, **kwargs)).start()
        wants = self.units / "multi-user.target.wants"
        wants.mkdir()
        (wants / runner.OLD).symlink_to(self.units / runner.OLD)
        operation.state["original_boot_links"] = operation.boot_links()
        # October 22 raw/rejected evidence is immutable; status/log paths are reusable.
        root = operation.base / "data/raw/Unit_1"
        raw = root / "2026/2026-10/2026-10-22.txt"
        raw.parent.mkdir(parents=True)
        raw.write_bytes(b"trial raw preserved\n")
        rejected = root / "rejected/2026-10-22.txt"
        rejected.parent.mkdir(parents=True)
        rejected.write_bytes(b"")
        status = operation.files(True)[1]
        status.parent.mkdir(parents=True)
        status.write_text('{"last_event_utc": "2026-10-22 11:40:51 UTC"}')
        logs = operation.base / "logfiles/detectors/Unit_1"
        logs.mkdir(parents=True, mode=0o755)
        (logs / "log-PicoMuon.txt").write_bytes(b"old trial info\n")
        (logs / "log-error.txt").write_bytes(b"old trial error retained\n")
        self.addCleanup(patch.stopall)
        patch.object(runner, "TRIAL_RAW_SHA256", trial.staging.digest(raw.read_bytes())).start()
        patch.object(runner, "TRIAL_STATUS_SHA256", trial.staging.digest(status.read_bytes())).start()
        if os.name == "nt":
            # Only POSIX mode extraction is mocked; checks and publications run normally.
            patch.object(runner.stat, "S_IMODE", return_value=0o644).start()
        # Windows stat uid/gid are zero; Linux fixture files belong to the current process.
        if not hasattr(os, "getuid"):
            patch.object(runner.os, "getuid", return_value=0, create=True).start()
            patch.object(runner.os, "getgid", return_value=0, create=True).start()
        operation.check_named_targets()

    def assert_retained(self):
        op = self.operation
        self.assertEqual(op.host.running, runner.NAMED)
        op.boot_state(True)
        self.assertEqual(op.state["status"], runner.COMMITTED)
        self.assertEqual(op.host.cron, trial.held_cron(
            (self.evidence / "root-crontab.original").read_bytes()))
        self.assertTrue((self.units / runner.NAMED).is_file())
        for name in trial.CONFIGS:
            self.assertEqual((op.base / "config" / name).read_bytes(),
                             (op.stage / "candidate/config" / name).read_bytes())
        op.protect_trial()

    def assert_restored(self):
        op = self.operation
        self.assertEqual(op.host.running, runner.OLD)
        op.boot_state(False)
        self.assertEqual(op.host.cron, (self.evidence / "root-crontab.original").read_bytes())
        self.assertFalse((self.units / runner.NAMED).exists())
        self.assertEqual(op.state["status"], runner.TERMINAL_RECOVERY)
        for name, payload in self.original.items():
            self.assertEqual((op.base / "config" / name).read_bytes(), payload)
        op.protect_trial()

    def test_success_retains_named_boot_and_hold_without_recovery(self):
        self.operation.execute()
        self.assert_retained()
        samples = json.loads((self.evidence / "named-observation.json").read_text())
        self.assertGreaterEqual(len(samples), 61)
        self.assertGreaterEqual(self.operation.host.elapsed, 600)
        self.assertFalse(any(command[-2:] == ("stop", runner.NAMED)
                             for command in self.operation.host.calls))
        self.assertFalse(any(command[-2:] == ("start", runner.OLD)
                             for command in self.operation.host.calls))

    def test_disable_old_failure_recovers_boot_and_cron_without_stop(self):
        self.operation.host.fail = ("disable", runner.OLD)
        self.operation.execute()
        self.assert_restored()
        self.assertFalse(any(command[-2:] == ("stop", runner.OLD)
                             for command in self.operation.host.calls))

    def test_enable_named_failure_rolls_back_configs_boot_and_cron(self):
        self.operation.host.fail = ("enable", runner.NAMED)
        self.operation.execute()
        self.assert_restored()

    def test_timeout_after_named_enable_uses_intent_to_disable_link(self):
        self.operation.host.link_fault = ("enable", runner.NAMED)
        self.operation.execute()
        self.assert_restored()

    def test_partial_config_publication_recovers(self):
        publish = self.operation.publish_config

        def fail(name, restore=False):
            publish(name, restore)
            if name == "USB.ini" and not restore:
                raise RuntimeError("injected config failure")
        with patch.object(self.operation, "publish_config", side_effect=fail):
            self.operation.execute()
        self.assert_restored()

    def test_unknown_config_edit_halts_recovery_and_preserves_hold(self):
        publish = self.operation.publish_config

        def fail(name, restore=False):
            if name == "legacy.ini" and not restore:
                (self.operation.base / "config/USB.ini").write_bytes(b"admin edit")
                raise RuntimeError("injected concurrent edit")
            publish(name, restore)
        with patch.object(self.operation, "publish_config", side_effect=fail), \
                self.assertRaisesRegex(RuntimeError, "Concurrent config edit"):
            self.operation.execute()
        self.assertIsNone(self.operation.host.running)
        self.assertIn(trial.HOLD, self.operation.host.cron)
        self.assertEqual((self.operation.base / "config/USB.ini").read_bytes(), b"admin edit")

    def test_named_stop_failure_never_starts_old(self):
        self.operation.host.fail = ("start", runner.NAMED)
        original = self.operation.host.run

        def failing_stop(*args, **kwargs):
            if args[-2:] == ("stop", runner.NAMED):
                raise RuntimeError("named stop failed")
            return original(*args, **kwargs)
        with patch.object(self.operation.host, "run", side_effect=failing_stop), \
                self.assertRaisesRegex(RuntimeError, "named stop failed"):
            self.operation.execute()
        self.assertEqual(self.operation.host.running, runner.NAMED)
        self.assertIn(trial.HOLD, self.operation.host.cron)
        self.assertFalse(any(command[-2:] == ("start", runner.OLD)
                             for command in self.operation.host.calls))

    def test_busy_lock_changes_no_service_and_restores_cron(self):
        self.fixture.trial.busy_lock = True
        with self.assertRaisesRegex(RuntimeError, "lock busy"):
            self.operation.execute()
        self.assert_restored()
        self.assertFalse(any("stop" in command for command in self.operation.host.calls))

    def test_interrupted_after_enable_can_resume_recovery(self):
        original = self.operation.set_boot

        def power_loss(unit, enabled):
            original(unit, enabled)
            if unit == runner.NAMED and enabled:
                raise SystemExit("power loss")
        with patch.object(self.operation, "set_boot", side_effect=power_loss), self.assertRaises(SystemExit):
            self.operation.execute()
        self.operation.state = json.loads((self.evidence / "state.json").read_text())
        self.operation.recover()
        self.assert_restored()

    def test_interrupted_after_commit_barrier_must_not_auto_rollback(self):
        original = self.operation.journal

        def interruption(status):
            original(status)
            if status == "COMMIT_READY":
                raise RuntimeError("reporting interrupted")
        with patch.object(self.operation, "journal", side_effect=interruption), \
                self.assertRaisesRegex(RuntimeError, "reporting interrupted"):
            self.operation.execute()
        self.assertEqual(self.operation.host.running, runner.NAMED)
        self.operation.state = json.loads((self.evidence / "state.json").read_text())
        with self.assertRaisesRegex(RuntimeError, "use --verify"):
            self.operation.recover()
        self.operation.verify_retained(observe=True)
        self.assertEqual(self.operation.host.running, runner.NAMED)

    def test_committed_verification_is_idempotent_and_does_not_restart(self):
        self.operation.execute()
        before = len(self.operation.host.calls)
        self.operation.verify_retained(observe=True)
        self.operation.verify_retained(observe=True)
        for command in self.operation.host.calls[before:]:
            self.assertFalse(any(action in command for action in
                                 ("start", "stop", "enable", "disable", "install", "rm", "ln")))
        self.assert_retained()

    def test_committed_hold_drift_is_not_restored_or_rolled_back(self):
        self.operation.execute()
        self.operation.host.cron += b"# concurrent admin\n"
        with self.assertRaisesRegex(RuntimeError, "processing hold lost"):
            self.operation.verify_retained(observe=True)
        self.assertEqual(self.operation.host.running, runner.NAMED)
        self.assertIn(b"# concurrent admin", self.operation.host.cron)
        with self.assertRaisesRegex(RuntimeError, "use --verify"):
            self.operation.recover()

    def test_later_day_gate_and_existing_named_file_refuse_deployment(self):
        self.operation.state["day"] = "2026-10-22"
        with self.assertRaisesRegex(RuntimeError, "later UTC day"):
            self.operation.check_named_targets()
        self.operation.state["day"] = "2026-10-23"
        raw = self.operation.files(True)[0]
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(b"existing scientific data\n")
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            self.operation.check_named_targets()
        self.assertEqual(raw.read_bytes(), b"existing scientific data\n")

    def test_trial_and_status_drift_refuse_apply(self):
        self.operation.files(True)[1].write_bytes(b"unexpected status")
        with self.assertRaisesRegex(RuntimeError, "trial status changed"):
            self.operation.check_named_targets()
        raw = self.operation.base / "data/raw/Unit_1/2026/2026-10/2026-10-22.txt"
        raw.write_bytes(b"changed trial")
        with self.assertRaisesRegex(RuntimeError, "trial raw changed"):
            self.operation.protect_trial()

    def test_boot_link_to_wrong_target_is_never_followed_or_rewritten(self):
        link = self.units / "multi-user.target.wants" / runner.OLD
        link.unlink()
        link.symlink_to(self.units / "unrelated.service")
        with self.assertRaisesRegex(RuntimeError, "Unexpected boot link"):
            self.operation.execute()
        self.assertEqual(os.readlink(link), str(self.units / "unrelated.service"))
        self.assertEqual(self.operation.host.running, runner.OLD)

    def test_wrong_trial_approval_cannot_open_locks_or_mutate(self):
        for mode in ("--apply", "--recover"):
            args = ["PermanentUnit1Collection.py", mode]
            if mode == "--recover":
                args.append("/home/pi/unit1-permanent-collection.example")
            args += ["--approval", trial.APPROVAL]
            with self.subTest(mode=mode), patch.object(sys, "argv", args), \
                    patch.object(sys, "platform", "linux"), \
                    patch.object(runner.os, "getuid", return_value=1000, create=True), \
                    patch.object(runner.Path, "home", return_value=Path("/home/pi")), \
                    patch.object(runner.os, "open") as opened, \
                    patch("sys.stderr", new_callable=io.StringIO), \
                    self.assertRaises(SystemExit) as stopped:
                runner.main()
            self.assertEqual(stopped.exception.code, 2)
            opened.assert_not_called()

    def test_preserved_trial_status_waits_for_fresh_post_start_update(self):
        original = self.operation.host.run
        preserved = self.operation.files(True)[1].read_bytes()

        def delayed(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[-2:] == ("start", runner.NAMED):
                self.operation.files(True)[1].write_bytes(preserved)
            return result
        with patch.object(self.operation.host, "run", side_effect=delayed):
            self.operation.execute()
        self.assert_retained()

    def test_header_only_startup_raw_waits_while_trial_status_is_preserved(self):
        original = self.operation.host.run
        preserved = self.operation.files(True)[1].read_bytes()

        def delayed(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[-2:] == ("start", runner.NAMED):
                self.operation.files(True)[0].write_bytes(b"RPiTimestamp,Event\n")
                self.operation.files(True)[1].write_bytes(preserved)
            return result
        with patch.object(self.operation.host, "run", side_effect=delayed):
            self.operation.execute()
        self.assert_retained()

    def test_slow_startup_observation_cannot_pass_after_thirty_second_deadline(self):
        original = self.operation.host.run
        delayed = False

        def slow(*args, **kwargs):
            nonlocal delayed
            if not delayed and self.operation.host.running == runner.NAMED \
                    and args[:3] == ("systemctl", "show", runner.NAMED):
                delayed = True
                self.operation.host.sleep(31)
            return original(*args, **kwargs)
        with patch.object(self.operation.host, "run", side_effect=slow):
            self.operation.execute()
        self.assert_restored()
        self.assertIn("within 30 seconds", self.operation.state["apply_error"])

    def test_new_error_rolls_back_but_keeps_error_and_partial_raw(self):
        original = self.operation.start

        def new_error(unit):
            original(unit)
            if unit == runner.NAMED:
                with (self.operation.base / "logfiles/detectors/Unit_1/log-error.txt").open("ab") as log:
                    log.write(b"new error\n")
        with patch.object(self.operation, "start", side_effect=new_error):
            self.operation.execute()
        self.assert_restored()
        self.assertTrue(self.operation.files(True)[0].exists())
        self.assertTrue((self.operation.base / "logfiles/detectors/Unit_1/log-error.txt")
                        .read_bytes().endswith(b"new error\n"))
        self.assertEqual((self.evidence / "prior-named/log-error.txt").read_bytes(),
                         b"old trial error retained\n")

    def test_invalid_rows_trigger_rollback_and_explicit_validation_evidence(self):
        self.operation.host.bad_rows = True
        self.operation.execute()
        self.assert_restored()
        self.assertIn("Named settings mismatch", self.operation.state["data_validation_error"])
        self.assertTrue(self.operation.files(True)[0].exists())

    def test_resume_already_recovered_single_service_without_second_start(self):
        self.operation.host.fail = ("start", runner.NAMED)
        healthy = self.operation.healthy
        failed = False

        def interrupted(named, duration):
            nonlocal failed
            if not named and not failed:
                failed = True
                raise RuntimeError("recovery observation interrupted")
            healthy(named, duration)
        with patch.object(self.operation, "healthy", side_effect=interrupted), \
                self.assertRaisesRegex(RuntimeError, "observation interrupted"):
            self.operation.execute()
        starts = self.operation.host.calls.count(("sudo", "-n", "systemctl", "start", runner.OLD))
        self.operation.recover()
        self.assert_restored()
        self.assertEqual(self.operation.host.calls.count(
            ("sudo", "-n", "systemctl", "start", runner.OLD)), starts)

    def test_busy_port_refuses_stop_and_restores_hold(self):
        self.operation.host.busy = True
        with self.assertRaisesRegex(RuntimeError, "Unexpected device owner|sole device owner"):
            self.operation.execute()
        self.assertEqual(self.operation.host.running, runner.OLD)
        self.assertFalse(any("stop" in command for command in self.operation.host.calls))

    def test_concurrent_unit_collision_is_not_removed_even_with_identical_bytes(self):
        original = self.operation.host.run

        def collision(*args, **kwargs):
            if args[2:4] == ("ln", "-T"):
                (self.units / runner.NAMED).write_bytes((self.operation.stage / "units" / runner.NAMED).read_bytes())
            return original(*args, **kwargs)
        with patch.object(self.operation.host, "run", side_effect=collision), \
                self.assertRaisesRegex(RuntimeError, "inode is not this operation"):
            self.operation.execute()
        self.assertTrue((self.units / runner.NAMED).exists())
        self.assertIn(trial.HOLD, self.operation.host.cron)
        self.assertIsNone(self.operation.host.running)

    def test_unit_publish_timeout_recovers_only_owned_inode_and_temporary(self):
        original = self.operation.host.run

        def interrupted(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[2:4] == ("ln", "-T"):
                raise RuntimeError("timeout after unit publication")
            return result
        with patch.object(self.operation.host, "run", side_effect=interrupted):
            self.operation.execute()
        self.assert_restored()
        self.assertFalse((self.units / f".{runner.NAMED}.{self.evidence.name}.tmp").exists())

    def load_fixture(self):
        self.operation.preflight.mkdir(parents=True, exist_ok=True)
        (self.operation.preflight / "root-crontab.txt").write_bytes(
            (self.evidence / "root-crontab.original").read_bytes())
        self.operation.journal("ready-for-load-test")

    def test_load_checks_helpers_configs_cron_and_command_sequence(self):
        self.load_fixture()
        (self.evidence / "command-0042.argv.json").write_text("[]")
        with patch.object(self.operation, "verify_package"):
            self.operation.load()
        self.assertEqual(self.operation.host.sequence, 42)
        for target, message in (
            (self.evidence / "recovery/USB.ini", "Recovery config changed"),
            (self.evidence / "root-crontab.held", "Recovery cron changed"),
        ):
            with self.subTest(target=target):
                original = target.read_bytes()
                target.write_bytes(b"unreviewed edit")
                with patch.object(self.operation, "verify_package"), self.assertRaisesRegex(RuntimeError, message):
                    self.operation.load()
                target.write_bytes(original)

    def test_load_refuses_changed_helpers_before_package_or_mutation(self):
        self.load_fixture()
        saved = json.loads((self.evidence / "state.json").read_text())
        saved["helpers"]["TrialUnit1Collection.py"] = "changed"
        trial.save_json(self.evidence / "state.json", saved)
        with patch.object(self.operation, "verify_package") as package, \
                self.assertRaisesRegex(RuntimeError, "changed runner/helper"):
            self.operation.load()
        package.assert_not_called()

    def test_check_only_runs_inherited_checks_and_never_changes_services_or_config(self):
        op = self.operation
        self.load_fixture()
        for name in trial.CONFIGS:
            (self.evidence / "recovery" / name).unlink()
        (self.evidence / "recovery").rmdir()
        with patch.object(op, "verify_package"), patch.object(op, "verify_system_cron"), \
                patch.object(trial.shutil, "which", return_value="/usr/bin/tool"), \
                patch.object(trial, "checked_config_mode", side_effect=lambda name, mode: trial.CONFIG_MODES[name]):
            op.check()
        self.assertEqual(op.state["status"], "PERMANENT_READY_NOT_AUTHORIZED")
        self.assertEqual(op.state["mutations"], [])
        self.assertEqual(op.host.running, runner.OLD)
        self.assertEqual(op.host.cron, (self.evidence / "root-crontab.original").read_bytes())
        for name, payload in self.original.items():
            self.assertEqual((op.base / "config" / name).read_bytes(), payload)
        self.assertFalse((self.units / runner.NAMED).exists())
        for command in op.host.calls:
            self.assertFalse(any(action in command for action in
                                 ("start", "stop", "enable", "disable", "install", "rm", "ln")))

    def test_check_rejects_prior_unresolved_operation_before_host_changes(self):
        previous = self.operation.home / (runner.PREFIX + "interrupted")
        previous.mkdir()
        trial.save_json(previous / "state.json", {"mutations": ["disable-old"], "status": "interrupted"})
        with self.assertRaisesRegex(RuntimeError, "Existing permanent operation"):
            self.operation.check()
        self.assertEqual(self.operation.host.calls, [])

    def test_missing_sudo_fails_without_any_mutation(self):
        with patch.object(trial.shutil, "which", side_effect=lambda name: None if name == "sudo" else "/usr/bin/tool"), \
                self.assertRaisesRegex(RuntimeError, "Required tool missing: sudo"):
            self.operation.check()
        self.assertEqual(self.operation.state["mutations"], [])
        self.assertEqual(self.operation.host.calls, [])

    def test_boot_alias_and_other_detector_enablement_are_rejected(self):
        alias = self.units / "multi-user.target.wants/another-name.service"
        alias.symlink_to(self.units / runner.OLD)
        with self.assertRaisesRegex(RuntimeError, "Unexpected boot link"):
            self.operation.boot_links()
        alias.unlink()
        other = self.units / "multi-user.target.wants/PicoMuon@Unit_2.service"
        other.symlink_to(self.units / "PicoMuon@.service")
        with self.assertRaisesRegex(RuntimeError, "Unexpected boot link"):
            self.operation.boot_links()

    def test_new_errors_after_commit_fail_verification_without_rollback(self):
        self.operation.execute()
        error = self.operation.base / "logfiles/detectors/Unit_1/log-error.txt"
        with error.open("ab") as handle:
            handle.write(b"new collector error\n")
        with self.assertRaisesRegex(RuntimeError, "error log changed"):
            self.operation.verify_retained(observe=True)
        self.assertEqual(self.operation.host.running, runner.NAMED)
        self.operation.boot_state(True)
        self.assertIn(trial.HOLD, self.operation.host.cron)

    def test_outside_daytime_does_not_stop_or_change_boot_enablement(self):
        self.operation.host.current = self.operation.host.current.replace(hour=19)
        self.operation.host.emit()
        self.operation.execute()
        self.assert_restored()
        self.assertFalse(any(action in command for command in self.operation.host.calls
                             for action in ("stop", "disable", "enable")))

    def test_journal_resume_rejects_wrong_day_and_boot_link_pins(self):
        self.load_fixture()
        original = (self.evidence / "state.json").read_bytes()
        for key, value, message in (
            ("day", "2026-10-22", "Invalid cutover day"),
            ("original_boot_links", {}, "Unrecognized original boot"),
        ):
            with self.subTest(key=key):
                saved = json.loads(original)
                saved[key] = value
                trial.save_json(self.evidence / "state.json", saved)
                with patch.object(self.operation, "verify_package"), self.assertRaisesRegex(RuntimeError, message):
                    self.operation.load()
        (self.evidence / "state.json").write_bytes(original)

    def test_committed_verification_after_rollover_reads_new_day_without_mutations(self):
        self.operation.execute()
        cutover = self.operation.files(True)[0].read_bytes()
        self.operation.host.current = self.operation.host.current.replace(day=24)
        self.operation.host.emit()
        before = len(self.operation.host.calls)
        self.operation.verify_retained(observe=True)
        self.assertEqual(self.operation.state["day"], "2026-10-23")
        self.assertEqual(self.operation.files(True)[0].read_bytes(), cutover)
        self.assertTrue((self.operation.base / "data/raw/Unit_1/2026/2026-10/2026-10-24.txt").exists())
        for command in self.operation.host.calls[before:]:
            self.assertFalse(any(action in command for action in
                                 ("start", "stop", "enable", "disable", "install", "rm", "ln")))


if __name__ == "__main__":
    unittest.main()
