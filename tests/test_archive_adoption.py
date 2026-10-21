from contextlib import nullcontext
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import AdoptUnit1Archive as adoption
from picomuon_common import LEGACY_RAW_HEADER

SCRIPT = Path(adoption.__file__)


def event(day, second, counter=None):
    return (
        f"{day} 00:00:{second:02d}.000001,C,{counter or second},200,{second * 1000},0,"
        "22,1015,56/148/627\n"
    ).encode("ascii")


class ArchiveAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.target = self.root / "destination"
        self.source.mkdir()
        self.target.mkdir()
        self.run = self.root / "adoption-run"
        self.header = (LEGACY_RAW_HEADER + "\n").encode("ascii")
        self.hashes = {}
        for day in adoption.REVIEWED:
            data = self.header + event(day, 1)
            legacy = day < "2026-10-13"
            if day == "2026-10-13":
                legacy_data = self.header + event(day, 1)
                data = self.header + event(day, 3) + event(day, 2)
                self.write_day(day, legacy_data, legacy=True)
                self.oct13_hashes = (self.hash(legacy_data), self.hash(data))
                self.hashes[day] = self.hash(self.header + event(day, 1) + event(day, 2) + event(day, 3))
            else:
                self.hashes[day] = self.hash(data)
            self.write_day(day, data, legacy=legacy)
        for number in range(13, 21):
            self.write(f"data/raw/rejected/2026-10-{number}.txt", b"bad serial\n" if number == 13 else b"")
        self.write_day("2026-10-21", b"active partial")
        self.write_day("2026-10-09", b"unmapped", legacy=True)
        self.patches = [
            patch.object(adoption, "REVIEWED", self.hashes),
            patch.object(adoption, "OCT13_SOURCES", self.oct13_hashes),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.plan = adoption.manifest(self.source, self.target)
        self.manifest = self.root / "approved.json"
        self.manifest.write_text(json.dumps(self.plan, sort_keys=True, indent=2) + "\n")
        self.approval = self.hash(self.manifest.read_bytes())
        # Exercise real NTFS no-clobber hard links on Windows; Linux durability/locking
        # has a separate native integration test, never a production bypass flag.
        if not sys.platform.startswith("linux"):
            for item in (
                patch.object(adoption, "require_linux"),
                patch.object(adoption, "sync_directory"),
                patch.object(adoption, "check_owner"),
                patch.object(adoption, "run_lock", side_effect=lambda path: nullcontext()),
            ):
                item.start()
                self.addCleanup(item.stop)

    @staticmethod
    def hash(data):
        return hashlib.sha256(data).hexdigest()

    def write(self, relative, data):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def write_day(self, day, data, legacy=False):
        return self.write(f"data/raw/{'ACM0/' if legacy else ''}{day[:4]}/{day[:7]}/{day}.txt", data)

    def apply(self, **kwargs):
        return adoption.execute(self.manifest, self.approval, self.run,
                                backup_verified=True, writers_stopped=True, **kwargs)

    def first_target(self):
        return self.target / self.plan["entries"][0]["destination"]

    def source_snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.source.rglob("*") if p.is_file()}

    def test_read_only_manifest_shape_and_fixed_exclusions(self):
        before = self.source_snapshot()
        self.assertEqual(adoption.manifest(self.source, self.target), self.plan)
        self.assertEqual(len(self.plan["entries"]), 19)
        self.assertEqual(sum(e.get("events", 0) for e in self.plan["entries"]), 13)
        self.assertTrue(all("2026-10-21" not in e["destination"] for e in self.plan["entries"]))
        self.assertFalse(list(self.target.iterdir()))
        self.assertFalse(self.run.exists())
        self.assertEqual(before, self.source_snapshot())

    def test_full_apply_noops_resume_and_source_preservation(self):
        before = self.source_snapshot()
        result = self.apply()
        self.assertEqual(result["created_or_resumed"], 19)
        self.assertEqual(result["identical_noops"], 0)
        self.assertEqual(before, self.source_snapshot())
        for entry in self.plan["entries"]:
            data = (self.target / entry["destination"]).read_bytes()
            self.assertEqual(self.hash(data), entry["sha256"])
        self.assertEqual(self.apply()["created_or_resumed"], 19)
        # A second independent run must treat every file as a no-op.
        self.run = self.root / "second-run"
        self.assertEqual(self.apply()["identical_noops"], 19)
        self.assertEqual(self.apply(rollback=True)["files"], 0)
        self.assertEqual(len(list(self.target.rglob("*.txt"))), 19)

    def test_approval_and_confirmation_guards_before_writes(self):
        for backup, writers in ((False, True), (True, False)):
            with self.assertRaisesRegex(ValueError, "confirmations"):
                adoption.execute(self.manifest, self.approval, self.run,
                                 backup_verified=backup, writers_stopped=writers)
        with self.assertRaisesRegex(ValueError, "approval hash"):
            adoption.execute(self.manifest, "0" * 64, self.run,
                             backup_verified=True, writers_stopped=True)
        self.assertFalse(self.run.exists())
        self.assertFalse(list(self.target.iterdir()))

    def test_changed_source_and_tampered_manifest_block(self):
        source = self.source / self.plan["entries"][0]["sources"][0]["path"]
        source.write_bytes(source.read_bytes() + b"bad\n")
        with self.assertRaisesRegex(ValueError, "validation failed|reviewed batch"):
            self.apply()
        self.assertFalse(self.run.exists())
        source.write_bytes(self.header + event("2026-10-10", 1))
        plan = json.loads(self.manifest.read_text())
        plan["entries"][0]["destination"] = "../escape"
        self.manifest.write_text(json.dumps(plan))
        self.approval = self.hash(self.manifest.read_bytes())
        with self.assertRaisesRegex(ValueError, "freshly validated"):
            self.apply()
        self.assertFalse(self.run.exists())

    def test_conflict_parent_file_and_extra_segment_refuse(self):
        target = self.first_target()
        target.parent.mkdir(parents=True)
        target.write_bytes(b"existing unrelated data")
        with self.assertRaisesRegex(ValueError, "Destination conflict"):
            self.apply()
        self.assertEqual(target.read_bytes(), b"existing unrelated data")
        target.unlink()
        alternate = self.write_day("2026-10-10", self.header + event("2026-10-10", 1))
        with self.assertRaisesRegex(ValueError, "Unexpected extra"):
            self.apply()
        alternate.unlink()
        blocker = self.target / "data" / "raw" / "Unit_1" / "rejected"
        blocker.write_bytes(b"blocked")
        with self.assertRaisesRegex(ValueError, "Parent is not a directory"):
            self.apply()
        self.assertFalse(self.run.exists())

    def test_oct13_exception_refuses_different_pair_even_if_valid_events(self):
        path = self.source / "data" / "raw" / "2026" / "2026-10" / "2026-10-13.txt"
        path.write_bytes(self.header + event("2026-10-13", 4) + event("2026-10-13", 2))
        with self.assertRaisesRegex(ValueError, "exception source hashes"):
            self.apply()
        self.assertFalse(self.run.exists())

    def test_no_clobber_race_requires_manual_identity_review(self):
        actual_promote = adoption.promote

        def race(stage, target):
            target.write_bytes(stage.read_bytes())
            actual_promote(stage, target)

        with patch.object(adoption, "promote", race):
            with self.assertRaises(FileExistsError):
                self.apply()
        self.assertEqual(self.hash(self.first_target().read_bytes()), self.plan["entries"][0]["sha256"])
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.apply()

    def test_interruption_after_link_before_journal_resumes(self):
        actual = adoption.promote
        count = 0

        def interrupted(stage, target):
            nonlocal count
            actual(stage, target)
            count += 1
            if count == 2:
                raise OSError(errno.EIO, "simulated crash after promotion")

        with patch.object(adoption, "promote", interrupted):
            with self.assertRaisesRegex(OSError, "simulated crash"):
                self.apply()
        self.assertEqual(len(list(self.target.rglob("*.txt"))), 2)
        self.assertEqual(self.apply()["created_or_resumed"], 19)
        self.assertEqual(self.apply(rollback=True)["files"], 19)
        self.assertFalse(list(self.target.rglob("*.txt")))
        self.assertEqual(self.apply(rollback=True)["files"], 0)
        with self.assertRaisesRegex(ValueError, "rolled back"):
            self.apply()

    def test_rollback_preserves_preexisting_files_and_rejects_modified_destinations(self):
        existing = self.first_target()
        existing.parent.mkdir(parents=True)
        existing.write_bytes((self.source / self.plan["entries"][0]["sources"][0]["path"]).read_bytes())
        self.apply()
        target = self.target / self.plan["entries"][1]["destination"]
        target.write_bytes(b"new collector wrote here")
        with self.assertRaisesRegex(ValueError, "Destination conflict"):
            self.apply(rollback=True)
        self.assertEqual(len(list(self.target.rglob("*.txt"))), 19)
        # Modification is not automatically repaired or rolled back.
        self.assertEqual(target.read_bytes(), b"new collector wrote here")
        self.assertTrue(existing.is_file())

    def test_rollback_rejects_replaced_identical_inode(self):
        self.apply()
        target = self.first_target()
        data = target.read_bytes()
        target.unlink()
        target.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "identity"):
            self.apply(rollback=True)
        self.assertEqual(len(list(self.target.rglob("*.txt"))), 19)

    def test_space_permission_and_incomplete_stage_fail_without_promotions(self):
        usage = adoption.shutil.disk_usage(self.root)
        with patch.object(adoption.shutil, "disk_usage", return_value=type(usage)(usage.total, usage.used, 0)):
            with self.assertRaisesRegex(ValueError, "Insufficient"):
                self.apply()
        self.assertFalse(list(self.target.rglob("*.txt")))
        real_save = adoption.save_bytes

        def denied(path, data, mode=0o600):
            if path.suffix == ".bin":
                raise PermissionError("staging denied")
            real_save(path, data, mode)

        with patch.object(adoption, "save_bytes", denied):
            with self.assertRaisesRegex(PermissionError, "staging denied"):
                self.apply()
        self.assertFalse(list(self.target.rglob("*.txt")))
        (self.run / "0000.bin").write_bytes(b"partial stage")
        with self.assertRaisesRegex(ValueError, "Staged file differs"):
            self.apply()
        self.assertFalse(list(self.target.rglob("*.txt")))

    def test_source_change_during_staging_blocks_all_promotions(self):
        real_save = adoption.save_bytes

        def change(path, data, mode=0o600):
            real_save(path, data, mode)
            if path.name == "0018.bin":
                origin = self.source / self.plan["entries"][0]["sources"][0]["path"]
                origin.write_bytes(origin.read_bytes() + b"bad\n")

        with patch.object(adoption, "save_bytes", change):
            with self.assertRaisesRegex(ValueError, "Source validation"):
                self.apply()
        self.assertFalse(list(self.target.rglob("*.txt")))

    def test_private_run_binding_and_malformed_journal(self):
        self.run = self.source / "unsafe-run"
        with self.assertRaisesRegex(ValueError, "separate"):
            self.apply()
        self.run = self.root / "adoption-run"
        self.apply()
        with (self.run / "journal.jsonl").open("ab") as output:
            output.write(b'{"partial":')
        with self.assertRaisesRegex(ValueError, "Incomplete journal"):
            self.apply()

    def test_selective_rollback_quarantines_new_files_but_keeps_noops_and_unrelated(self):
        existing = self.first_target()
        existing.parent.mkdir(parents=True)
        existing.write_bytes((self.source / self.plan["entries"][0]["sources"][0]["path"]).read_bytes())
        unrelated = self.target / "data" / "raw" / "Unit_1" / "2026" / "2026-10" / "unrelated.txt"
        unrelated.write_bytes(b"unrelated")
        self.assertEqual(self.apply()["identical_noops"], 1)
        self.assertEqual(self.apply(rollback=True)["files"], 18)
        self.assertTrue(existing.exists())
        self.assertEqual(unrelated.read_bytes(), b"unrelated")
        self.assertEqual(len(list((self.run / "quarantine").glob("*.bin"))), 18)

    def test_run_manifest_binding_and_source_stability_during_read(self):
        self.apply()
        (self.run / "approved-manifest.json").write_bytes(b"other approval")
        with self.assertRaisesRegex(ValueError, "another manifest"):
            self.apply()
        source = self.source / self.plan["entries"][0]["sources"][0]["path"]
        actual_open = Path.open
        from contextlib import contextmanager

        @contextmanager
        def changing(path, *args, **kwargs):
            with actual_open(path, *args, **kwargs) as handle:
                yield handle
            if path == source:
                with actual_open(path, "ab") as handle:
                    handle.write(b"\n")

        with patch.object(Path, "open", changing):
            with self.assertRaisesRegex(ValueError, "changed while reading"):
                adoption.read_snapshot(source)

    def test_symlink_guard_without_platform_privileges(self):
        blocked = self.source / self.plan["entries"][0]["sources"][0]["path"]
        real = adoption.unsafe_link
        with patch.object(adoption, "unsafe_link", side_effect=lambda p: p == blocked or real(p)):
            with self.assertRaisesRegex(ValueError, "Symbolic link"):
                self.apply()
        self.assertFalse(self.run.exists())

    def test_destination_mount_boundary_refused_before_staging(self):
        mounted = self.target / "data"
        mounted.mkdir()
        real_stat = Path.stat

        def another_device(path, *args, **kwargs):
            result = real_stat(path, *args, **kwargs)
            if path == mounted:
                values = list(result)
                values[2] += 1  # st_dev
                return os.stat_result(values)
            return result

        with patch.object(Path, "stat", another_device):
            with self.assertRaisesRegex(ValueError, "filesystem boundary"):
                self.apply()
        self.assertFalse(self.run.exists())

    def test_directory_flush_failure_is_not_success_and_can_resume(self):
        real_sync = adoption.sync_directory
        calls = 0

        def interrupted(path):
            nonlocal calls
            real_sync(path)
            calls += 1
            if calls == 5:
                raise OSError(errno.EIO, "directory flush failed")

        with patch.object(adoption, "sync_directory", interrupted):
            with self.assertRaisesRegex(OSError, "directory flush failed"):
                self.apply()
        self.assertFalse(list(self.target.rglob("*.txt")))
        self.assertEqual(self.apply()["created_or_resumed"], 19)

    def test_cli_never_applies_without_all_gates(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--apply"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("require", result.stderr)
        if not sys.platform.startswith("linux"):
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--apply", "--manifest", str(self.manifest),
                 "--approve-manifest", self.approval, "--run-dir", str(self.run),
                 "--backup-verified", "--writers-stopped"], capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("require Linux", result.stderr)
            self.assertFalse(self.run.exists())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Native directory durability/flock acceptance requires Linux/RPi")
    def test_native_linux_fsync_and_flock_exclusion(self):
        self.run.mkdir(mode=0o700)
        with adoption.run_lock(self.run):
            with self.assertRaises(BlockingIOError):
                with adoption.run_lock(self.run):
                    self.fail("Second lock acquired")
        self.assertEqual(self.apply()["created_or_resumed"], 19)


if __name__ == "__main__":
    unittest.main()
