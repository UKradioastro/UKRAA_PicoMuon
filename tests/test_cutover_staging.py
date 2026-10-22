import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import StageUnit1Cutover as staging


class CutoverStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.preflight = self.root / "preflight"
        self.rehearsal = self.root / "rehearsal"
        self.live = self.root / "production"
        self.preflight.mkdir()
        (self.rehearsal / "scripts").mkdir(parents=True)
        self.live.mkdir()
        self.backup = {
            "config/USB.ini": (
                f"[usb]\nserial_port = {staging.DEVICE}\nid_serial = {staging.IDENTITY}\n"
                f"id_serial_short = {staging.SHORT_ID}\nlabel =\n"
            ).encode(),
            "config/legacy.ini": (
                "[legacy]\nthreshold_top = 200\nreset_top = 100\n"
                "threshold_bottom = 200\nreset_bottom = 100\n"
            ).encode(),
            "config/user.ini": b"[Observatory]\nobservatory_location = private test site\n",
            "VERSION": b"2026.10.0\n",
            "install/PicoMuon@.service": (
                Path(__file__).resolve().parents[1] / "install" / "PicoMuon@.service"
            ).read_bytes(),
        }
        scripts = {f"example{n}.py": b"value = 1\n" for n in range(39)}
        scripts["example0.py"] = b"value = 1\r\n"
        scripts["example.sh"] = b"#!/bin/bash\nset -euo pipefail\n"
        for name, data in scripts.items():
            (self.rehearsal / "scripts" / name).write_bytes(data)
        report = {
            "status": "PASS", "approved_manifest_sha256": staging.MANIFEST_SHA256,
            "script_hashes": {name: staging.digest(data) for name, data in scripts.items()},
        }
        self.addCleanup(patch.stopall)
        with tarfile.open(self.preflight / "production-config-code-backup.tar.gz", "w:gz") as archive:
            for name, data in self.backup.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
                live_file = self.live / name
                live_file.parent.mkdir(parents=True, exist_ok=True)
                live_file.write_bytes(data)
        hashes = "".join(f"{staging.digest(data)}  {staging.PRODUCTION}/{name}\n"
                         for name, data in self.backup.items())
        (self.preflight / "production-config-code.sha256").write_bytes(hashes.encode())
        manifest = b'{"test": "fixed batch"}'
        (self.preflight / "fresh-adoption-manifest.json").write_bytes(manifest)
        patch.object(staging, "MANIFEST_SHA256", staging.digest(manifest)).start()
        report["approved_manifest_sha256"] = staging.MANIFEST_SHA256
        report_bytes = json.dumps(report).encode()
        (self.rehearsal / "validation-recheck.json").write_bytes(report_bytes)
        patch.object(staging, "REHEARSAL_REPORT_SHA256", staging.digest(report_bytes)).start()
        self.refresh_preflight_index()

    def refresh_preflight_index(self):
        data = "".join(
            f"{staging.digest(path.read_bytes())}  ./{path.name}\n"
            for path in sorted(self.preflight.iterdir()) if path.name != "SHA256SUMS"
        ).encode()
        (self.preflight / "SHA256SUMS").write_bytes(data)
        patch.object(staging, "PREFLIGHT_INDEX_SHA256", staging.digest(data)).start()

    def test_complete_candidate_is_separate_and_no_clobber(self):
        scripts, backup = staging.verified_inputs(self.preflight, self.rehearsal)
        hashes = staging.production_hashes(self.preflight)
        staging.check_production(self.live, hashes)
        stage = self.root / "stage"
        stage.mkdir()
        report = staging.build_candidate(stage, scripts, backup)
        self.assertEqual(report["script_count"], 40)
        self.assertIn("hardware confirmation", report["settings_basis"])
        candidate = stage / "candidate"
        self.assertIn("[legacy:Unit_1]", (candidate / "config" / "legacy.ini").read_text())
        self.assertIn("[detectors]", (candidate / "config" / "USB.ini").read_text())
        self.assertEqual((candidate / "config" / "user.ini").read_bytes(), backup["config/user.ini"])
        self.assertEqual((candidate / "scripts" / "example0.py").read_bytes(), scripts["example0.py"])
        unit = (stage / "units" / "PicoMuon@Unit_1.service").read_text()
        self.assertIn(staging.PRODUCTION, unit)
        self.assertNotIn("@PICOMUON_", unit)
        self.assertNotIn("-pilot", unit)
        self.assertFalse((candidate / "data").exists())
        staging.check_production(self.live, hashes)
        with self.assertRaises(FileExistsError):
            staging.build_candidate(stage, scripts, backup)

    def test_evidence_and_script_tampering_rejected(self):
        for target in (self.preflight / "SHA256SUMS",
                       self.preflight / "production-config-code-backup.tar.gz",
                       self.rehearsal / "validation-recheck.json",
                       self.rehearsal / "scripts" / "example0.py"):
            original = target.read_bytes()
            with self.subTest(target=target):
                target.write_bytes(original + b"\n")
                with self.assertRaisesRegex(RuntimeError, "differs|mismatch|changed"):
                    staging.verified_inputs(self.preflight, self.rehearsal)
                target.write_bytes(original)

    def test_production_drift_is_blocking(self):
        hashes = staging.production_hashes(self.preflight)
        (self.live / "VERSION").write_bytes(b"changed\n")
        with self.assertRaisesRegex(RuntimeError, "Production changed since preflight"):
            staging.check_production(self.live, hashes)

    def test_unsafe_hash_paths_rejected(self):
        for name in ("../outside", "/absolute", "config/../../outside", "config\\outside"):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "Unsafe"):
                staging.hash_index(f'{"a" * 64}  {name}\n'.encode())

    def test_native_failure_is_saved_and_not_ignored(self):
        stage = self.root / "stage"
        stage.mkdir()
        scripts, backup = staging.verified_inputs(self.preflight, self.rehearsal)
        staging.build_candidate(stage, scripts, backup)
        for failed_label, failed_command in (("config-probe", sys.executable),
                                             ("systemd-verify", "systemd-analyze"),
                                             ("syntax-example.sh", "bash")):
            def run(command, **kwargs):
                self.assertNotIn("PICOMUON_USB_INI_PATH", kwargs["env"])
                self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
                return subprocess.CompletedProcess(
                    command, 7 if command[0] == failed_command else 0, "", "injected failure",
                )
            with self.subTest(label=failed_label), \
                    patch.dict("os.environ", {"PICOMUON_USB_INI_PATH": "/wrong/config"}), \
                    patch.object(staging.subprocess, "run", side_effect=run), \
                    self.assertRaisesRegex(RuntimeError, f"{failed_label} failed"):
                staging.native_checks(stage)
            self.assertEqual((stage / f"{failed_label}.exit").read_text().strip(), "7")

    def test_changed_settings_are_not_silently_accepted(self):
        scripts, backup = staging.verified_inputs(self.preflight, self.rehearsal)
        backup["config/legacy.ini"] = backup["config/legacy.ini"].replace(b"200", b"250")
        stage = self.root / "stage"
        stage.mkdir()
        with self.assertRaisesRegex(RuntimeError, "fallback differs"):
            staging.build_candidate(stage, scripts, backup)

    def test_real_configuration_probe_and_missing_settings_guard(self):
        scripts, backup = staging.verified_inputs(self.preflight, self.rehearsal)
        repo_scripts = Path(__file__).resolve().parents[1] / "scripts"
        for name in ("picomuon_common.py", "picomuon_detectors.py", "picomuon_metadata.py",
                     "picomuon_processing.py"):
            scripts[name] = (repo_scripts / name).read_bytes()
        stage = self.root / "probe-stage"
        stage.mkdir()
        staging.build_candidate(stage, scripts, backup)
        candidate = stage / "candidate"
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("PICOMUON_", "PYTHON"))}
        environment.update(PICOMUON_BASE_PATH=str(candidate),
                           PYTHONPATH=str(candidate / "scripts"), PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, "-B", "-c", staging.CONFIG_PROBE, str(candidate),
                   staging.DEVICE, staging.IDENTITY, staging.SHORT_ID]
        result = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["detectors"], ["Unit_1"])
        path = candidate / "config" / "legacy.ini"
        text = path.read_text()
        head, named = text.split("[legacy:Unit_1]", 1)
        path.write_text(head + "[legacy:Unit_1]" + named.replace("threshold_top = 200\n", ""))
        result = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("legacy:Unit_1", result.stderr)
        self.assertFalse((candidate / "data").exists())

    def test_main_retains_report_and_never_applies_candidate(self):
        stage = self.root / "stage"
        stage.mkdir()
        check = staging.check_production
        calls = []

        def check_live(base, hashes):
            self.assertEqual(base, Path(staging.PRODUCTION))
            check(self.live, hashes)
            calls.append(base)

        with patch.object(sys, "argv", ["StageUnit1Cutover.py", "--preflight", str(self.preflight),
                                       "--rehearsal", str(self.rehearsal)]), \
                patch.object(sys, "platform", "linux"), \
                patch.object(staging.os, "getuid", return_value=1000, create=True), \
                patch.object(staging.os, "umask"), \
                patch.object(staging.Path, "home", return_value=Path("/home/pi")), \
                patch.object(staging.tempfile, "mkdtemp", return_value=str(stage)), \
                patch.object(staging, "check_production", side_effect=check_live), \
                patch.object(staging, "native_checks") as native, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(staging.main(), 0)
        native.assert_called_once_with(stage)
        self.assertEqual(len(calls), 2)
        report = json.loads((stage / "staging-report.json").read_text())
        self.assertEqual(report["status"], "STAGED_NOT_AUTHORIZED")
        self.assertEqual(report["production_files_unchanged"], len(self.backup))
        self.assertEqual(len(staging.hash_index((stage / "SHA256SUMS").read_bytes())), 45)
        staging.check_production(self.live, staging.production_hashes(self.preflight))

    def test_main_preserves_failed_stage(self):
        stage = self.root / "failed-stage"
        stage.mkdir()
        with patch.object(sys, "argv", ["StageUnit1Cutover.py", "--preflight", str(self.preflight),
                                       "--rehearsal", str(self.rehearsal)]), \
                patch.object(sys, "platform", "linux"), \
                patch.object(staging.os, "getuid", return_value=1000, create=True), \
                patch.object(staging.os, "umask"), \
                patch.object(staging.Path, "home", return_value=Path("/home/pi")), \
                patch.object(staging.tempfile, "mkdtemp", return_value=str(stage)), \
                patch.object(staging, "check_production"), \
                patch.object(staging, "native_checks", side_effect=RuntimeError("native check failed")), \
                patch("sys.stdout", new_callable=io.StringIO), \
                patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(staging.main(), 1)
        report = json.loads((stage / "staging-report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertIn("native check failed", report["error"])
        self.assertTrue((stage / "candidate").is_dir())
        self.assertFalse((stage / "SHA256SUMS").exists())


if __name__ == "__main__":
    unittest.main()
