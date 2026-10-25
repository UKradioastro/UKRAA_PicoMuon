from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import RestoreUnit1Processing as runner

staging = runner.staging
NOW = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
HELD = b"# UNIT1 COLLECTION-ONLY HOLD: 15 1 * * * daily\n"
ORIGINAL = b"15 1 * * * daily\n"


def row(stamp: str, count: int = 1, settings: str = "200,100,200,100") -> str:
    return f"{stamp},T,{count},100,1,0,20.0,1000.0,Unit_1,{settings}\n"


def raw(*rows: str) -> bytes:
    return ("\n" + runner.RAW_HEADER + "\n" + "".join(rows)).encode()


class FakeCollection:
    def __init__(self, evidence: Path):
        self.evidence = evidence
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "root-crontab.held").write_bytes(HELD)
        (evidence / "root-crontab.original").write_bytes(ORIGINAL)
        self.crontab = HELD
        self.state = {"last_old_event": "2026-10-24T10:58:20.500000+00:00"}
        self.hashes: dict[str, str] = {}

    def cron(self) -> bytes:
        return self.crontab

    @contextmanager
    def lock(self):
        yield


class FakeHost:
    def __init__(self, restore=None):
        self.restore = restore
        self.sequence = 0
        self.commands: list[tuple[str, ...]] = []
        self.current = NOW
        self.on_run = None

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)

    def run(self, *command: str, allowed=(0,), timeout=60) -> bytes:
        self.commands.append(command)
        if command[:3] == ("sudo", "-n", "crontab") and len(command) == 4:
            self.restore.collection.crontab = Path(command[3]).read_bytes()
        if self.on_run:
            self.on_run(command)
        return b""


class Fixture:
    def __init__(self, root: Path):
        self.home = root / "home"
        self.base = self.home / "UKRAA_PicoMuon"
        self.pins = {}
        for day in runner.GAP_DAYS:
            stamp = day + " {}"
            if day == "2026-10-24":
                single = raw(row(stamp.format("00:00:01.000000")), row(stamp.format("10:58:20.000000")))
            else:
                single = raw(row(stamp.format("00:00:01.000000")), row(stamp.format("12:00:00.000000")),
                             row(stamp.format("23:59:59.000000")))
            self.write(f"data/raw/{day[:4]}/{day[:7]}/{day}.txt", single)
        named = {
            "2026-10-22": raw(row("2026-10-22 10:00:00.000000", 2), row("2026-10-22 10:05:00.000000", 3)),
            "2026-10-23": raw(row("2026-10-23 15:15:16.000000", 4), row("2026-10-23 15:25:17.000000", 5)),
            "2026-10-24": raw(row("2026-10-24 10:58:27.000000", 6), row("2026-10-24 23:59:58.000000", 7)),
        }
        for day, content in named.items():
            self.write(f"data/raw/Unit_1/2026/2026-10/{day}.txt", content)
        self.pins = {"2026-10-21": None, "2026-10-22": staging.digest(named["2026-10-22"]),
                     "2026-10-23": staging.digest(named["2026-10-23"])}
        day = runner.FIRST_DAY
        while day <= NOW.date() - timedelta(days=1):
            text = day.isoformat()
            if text not in runner.GAP_DAYS:
                self.write(f"data/raw/Unit_1/2026/2026-10/{text}.txt",
                           raw(row(f"{text} 01:00:00.000000")))
            day += timedelta(days=1)
        self.write("scripts/ProcessDaily.py", b"old daily\n")
        self.write("scripts/processData.sh", b"old shell\n")
        self.write("scripts/__pycache__/ProcessDaily.cpython-313.pyc", b"old pyc")
        os.utime(self.base / "scripts/ProcessDaily.py", ns=(1_700_000_000_000_000_000,) * 2)
        self.payload = {"scripts/ProcessDaily.py": b"new daily\n", "scripts/plot-annotations.gp": b"set label\n",
                        "scripts/processData.sh": b"new shell\n"}
        public = root / "www"
        public.mkdir()
        (public / "index.html").write_bytes(b"<html>legacy</html>")
        self.public = public

    def write(self, relative: str, content: bytes) -> None:
        path = self.base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def restore(self, name: str) -> runner.Restore:
        evidence = self.home / f"{runner.PREFIX}{name}"
        evidence.mkdir(parents=True, exist_ok=True)
        host = FakeHost()
        operation = runner.Restore(self.home, self.home / "units", evidence, host)
        host.restore = operation
        operation.public = self.public
        operation.collection = FakeCollection(evidence / "collection")
        operation.payload = dict(self.payload)
        return operation

    def ready(self, operation: runner.Restore) -> None:
        runner.save_json(operation.evidence / "merge-manifest.json", operation.merge_manifest())
        operation.state["merge_manifest_sha256"] = staging.digest(
            runner.data(operation.evidence / "merge-manifest.json"))
        operation.state["backfill_days"] = operation.backfill_days()
        operation.state["web_before"] = operation.web_state()
        operation.state["deploy"] = {name: staging.digest(content) for name, content in operation.payload.items()}
        operation.journal(runner.READY)


class MergeTests(unittest.TestCase):
    def test_merge_interleaves_segments_and_normalises_header(self):
        single = raw(row("2026-10-22 09:00:00.000000"), row("2026-10-22 11:00:00.000000"))
        named = raw(row("2026-10-22 10:00:00.000000", 2))
        output, summary = runner.merge_day("2026-10-22", single, named)
        lines = output.decode().splitlines()
        self.assertEqual(lines[0], runner.RAW_HEADER)
        self.assertEqual([line[11:19] for line in lines[1:]], ["09:00:00", "10:00:00", "11:00:00"])
        self.assertEqual((summary["events"], summary["single_before"], summary["single_after"]),
                         (3, "2026-10-22 09:00:00", "2026-10-22 11:00:00"))
        self.assertEqual(summary["sha256"], staging.digest(output))

    def test_single_only_day(self):
        output, summary = runner.merge_day("2026-10-21", raw(row("2026-10-21 00:00:01.000000")), None)
        self.assertEqual((summary["events"], summary["named_events"]), (1, 0))
        self.assertTrue(output.startswith(runner.RAW_HEADER.encode()))

    def test_rejects_unsafe_inputs(self):
        day = "2026-10-22"
        cases = {
            "overlap": (raw(row(f"{day} 10:02:00.000000")),
                        raw(row(f"{day} 10:00:00.000000"), row(f"{day} 10:05:00.000000"))),
            # Identical events are necessarily inside the named range, so the overlap guard fires first.
            "segments overlap": (raw(row(f"{day} 09:00:00.000000")), raw(row(f"{day} 09:00:00.000000"))),
            "settings": (raw(row(f"{day} 09:00:00.000000", settings="300,100,200,100")), None),
            "Incomplete": (raw(row(f"{day} 09:00:00.000000"))[:-1], None),
            "Wrong-day": (raw(row("2026-10-23 09:00:00.000000")), None),
            "Out-of-order": (raw(row(f"{day} 09:00:00.000000"), row(f"{day} 08:00:00.000000")), None),
            "No events": (raw(), None),
        }
        for message, (single, named) in cases.items():
            with self.subTest(message), self.assertRaisesRegex(Exception, message):
                runner.merge_day(day, single, named)


class PinTests(unittest.TestCase):
    def test_process_data_pin_matches_repository(self):
        content = (ROOT / "scripts/processData.sh").read_bytes()
        self.assertNotIn(b"\r", content)
        self.assertEqual(staging.digest(content), runner.PROCESS_DATA_SHA256)

    def test_rehearsed_scripts_match_accepted_report_and_repository(self):
        report = json.loads((ROOT / "examples/unit1-processing-rehearsal.yo2to17p/validation-recheck.json")
                            .read_bytes())
        for name in runner.REHEARSED:
            with self.subTest(name):
                self.assertEqual(report["script_hashes"][name],
                                 staging.digest((ROOT / "scripts" / name).read_bytes()))

    def test_deployed_files_are_pinned_in_production_except_new_annotation(self):
        hashes = staging.production_hashes(ROOT / "examples/unit1-cutover-preflight.YtqHwx")
        for name in (*runner.REHEARSED, "processData.sh"):
            relative = f"scripts/{name}"
            self.assertEqual(relative in hashes, relative not in runner.NEW_FILES, relative)
        self.assertTrue(set(runner.STALE_BYTECODE) <= set(hashes))

    def test_helpers_cover_runner_and_shell(self):
        self.assertEqual(set(runner.helper_hashes()), set(runner.HELPERS))


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.fixture = Fixture(Path(self.temporary.name))
        self.pins = patch.dict(runner.NAMED_PINS, self.fixture.pins)
        self.pins.start()

    def tearDown(self):
        self.pins.stop()
        self.temporary.cleanup()

    def approved(self):
        reviewed = self.fixture.restore("reviewed")
        self.fixture.ready(reviewed)
        operation = self.fixture.restore("apply")
        self.fixture.ready(operation)
        return reviewed, operation

    def test_manifest_and_backfill_plan(self):
        operation = self.fixture.restore("plan")
        manifest = operation.merge_manifest()
        self.assertEqual([entry["day"] for entry in manifest["entries"]], list(runner.GAP_DAYS))
        self.assertIsNone(manifest["entries"][0]["named"])
        days = operation.backfill_days()
        self.assertEqual((days[0], days[-1], len(days)), ("2026-10-10", "2026-10-25", 16))

    def test_named_october24_must_follow_frozen_single_mode(self):
        operation = self.fixture.restore("late")
        operation.collection.state["last_old_event"] = "2026-10-24T11:00:00+00:00"
        with self.assertRaisesRegex(Exception, "does not follow"):
            operation.merge_manifest()

    def test_unexpected_named_pin_rejected(self):
        self.fixture.write("data/raw/Unit_1/2026/2026-10/2026-10-21.txt", raw(row("2026-10-21 05:00:00.000000")))
        with self.assertRaisesRegex(Exception, "pre-restore named raw for 2026-10-21"):
            self.fixture.restore("pin").merge_manifest()

    def test_successful_apply_merges_deploys_commits_and_restores_cron(self):
        reviewed, operation = self.approved()
        with patch.object(runner.Restore, "backfill"), patch.object(runner.Restore, "final_run"), \
                patch.object(runner.Restore, "restored"):
            operation.apply(reviewed.evidence)
        self.assertEqual(operation.state["status"], runner.COMMITTED)
        self.assertEqual(operation.collection.crontab, ORIGINAL)
        merged = (self.fixture.base / "data/raw/Unit_1/2026/2026-10/2026-10-22.txt").read_text().splitlines()
        self.assertEqual(merged[0], runner.RAW_HEADER)
        self.assertEqual([line[11:19] for line in merged[1:]],
                         ["00:00:01", "10:00:00", "10:05:00", "12:00:00", "23:59:59"])
        self.assertTrue((self.fixture.base / "data/raw/Unit_1/2026/2026-10/2026-10-21.txt").is_file())
        for relative, content in self.fixture.payload.items():
            self.assertEqual((self.fixture.base / relative).read_bytes(), content)
        self.assertLess(operation.state["history"].index(
            next(item for item in operation.state["history"] if item["status"] == "COMMIT_READY")),
            len(operation.state["history"]) - 1)

    def test_failed_backfill_rolls_back_bytes_mtime_and_keeps_hold(self):
        reviewed, operation = self.approved()
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.fixture.base.rglob("*") if path.is_file()}
        pyc = self.fixture.base / "scripts/__pycache__/ProcessDaily.cpython-313.pyc"

        def fail(_):
            pyc.write_bytes(b"rewritten by python")
            raise RuntimeError("pipeline failed")

        with patch.object(runner.Restore, "backfill", fail):
            operation.apply(reviewed.evidence)
        self.assertEqual(operation.state["status"], runner.ROLLED_BACK)
        self.assertEqual(operation.collection.crontab, HELD)
        after = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in self.fixture.base.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_reviewed_manifest_mismatch_rejected_before_mutation(self):
        reviewed, operation = self.approved()
        manifest = json.loads((reviewed.evidence / "merge-manifest.json").read_bytes())
        manifest["entries"][0]["events"] += 1
        (reviewed.evidence / "merge-manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(Exception, "differs from the reviewed check"):
            operation.apply(reviewed.evidence)
        self.assertNotIn("backup", operation.state)

    def test_reviewed_plan_on_different_day_rejected(self):
        reviewed, operation = self.approved()
        operation.state["backfill_days"] = operation.state["backfill_days"][:-1]
        with self.assertRaisesRegex(Exception, "plan differs"):
            operation.apply(reviewed.evidence)

    def test_commit_ready_is_never_rolled_back(self):
        operation = self.fixture.restore("barrier")
        self.fixture.ready(operation)
        operation.journal("COMMIT_READY")
        with self.assertRaisesRegex(Exception, "never roll back"):
            operation.rollback()

    def test_recover_finishes_cron_restore_after_commit_ready(self):
        operation = self.fixture.restore("recover")
        self.fixture.ready(operation)
        operation.journal("COMMIT_READY")
        with patch.object(runner.Restore, "restored"):
            operation.recover()
        self.assertEqual((operation.state["status"], operation.collection.crontab), (runner.COMMITTED, ORIGINAL))

    def test_cron_restore_refuses_changed_hold(self):
        operation = self.fixture.restore("cron")
        operation.collection.crontab = b"edited\n"
        with self.assertRaisesRegex(Exception, "hold changed"):
            operation.restore_cron()

    def test_backfill_runs_each_day_offline_then_final_cron_path(self):
        operation = self.fixture.restore("backfill")
        self.fixture.ready(operation)
        base = self.fixture.base
        log = base / "logfiles/detectors/Unit_1/log-PicoMuon.txt"
        self.fixture.write("logfiles/detectors/Unit_1/log-PicoMuon.txt", b"")
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 32

        def pipeline(command):
            if "ProcessDetectors.py" in " ".join(command) or command[-1].endswith("processData.sh"):
                day = command[command.index("--date") + 1] if "--date" in command else "2026-10-25"
                self.fixture.write(f"data/day/detectors/Unit_1/{day[:4]}/{day[:7]}/{day}.txt", b"x")
                plots = [f"yesterday/Unit_1_{event}-{kind}.png" for kind in ("Cpm", "Freq", "Adc")
                         for event in "TBC"] + ["periods/Unit_1_day_plot.png"]
                for name in plots:
                    self.fixture.write(f"temp/detectors/Unit_1/{name}", png)
                    self.fixture.write(f"WWW/detectors/Unit_1/{day}/{Path(name).name}", png)
                pages = ("index.html", "Unit_1/index.html", "Unit_1/status.json")
                for page in pages:
                    self.fixture.write(f"WWW/detectors/{page}", f"{page} {day}".encode())
                if command[-1].endswith("processData.sh"):
                    for page in pages:
                        target = self.fixture.public / "detectors" / page
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(f"{page} {day}".encode())
                for name in plots:
                    if command[-1].endswith("processData.sh"):
                        target = self.fixture.public / "temp" / ("ACM0_" + Path(name).name[len("Unit_1_"):])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(png)
                        published = self.fixture.public / "detectors/Unit_1" / day / Path(name).name
                        published.parent.mkdir(parents=True, exist_ok=True)
                        published.write_bytes(png)
                with log.open("a") as handle:
                    handle.write(f"Completed run for {day}\n")

        operation.host.on_run = pipeline
        operation.backfill()
        operation.final_run()
        runs = [command for command in operation.host.commands if "ProcessDetectors.py" in " ".join(command)]
        self.assertEqual(len(runs), 15)
        self.assertTrue(all("--skip-downloads" in command and "TZ=UTC" in command for command in runs))
        self.assertEqual(operation.host.commands[-1][-1], str(base / "scripts/processData.sh"))
        self.assertEqual(operation.state["processed"], operation.state["backfill_days"])
        (self.fixture.public / "detectors/Unit_1/status.json").write_bytes(b"stale")
        with self.assertRaisesRegex(Exception, "site not current"):
            operation.require_published("2026-10-25")

    def test_backfill_requires_fresh_completion_message(self):
        operation = self.fixture.restore("incomplete")
        self.fixture.ready(operation)
        self.fixture.write("logfiles/detectors/Unit_1/log-PicoMuon.txt", b"Completed run for 2026-10-10\n")
        with self.assertRaisesRegex(Exception, "did not complete 2026-10-10"):
            operation.backfill()

    def test_root_owned_unit_log_blocks_check(self):
        operation = self.fixture.restore("owner")
        for relative in runner.LOGS[:4]:
            self.fixture.write(relative, b"")
        blocked = str(self.fixture.base / "logfiles/detectors/Unit_1/log-error.txt")
        real = os.access
        with patch.object(runner.os, "access", lambda path, mode: str(path) != blocked and real(path, mode)):
            with self.assertRaisesRegex(Exception, "log-error.txt"):
                operation.require_writable()
        operation.require_writable()

    def test_published_index_must_not_change(self):
        operation = self.fixture.restore("index")
        self.fixture.ready(operation)
        (self.fixture.public / "index.html").write_bytes(b"replaced")
        with self.assertRaisesRegex(Exception, "index.html"):
            operation.require_published("2026-10-25")


if __name__ == "__main__":
    unittest.main()
