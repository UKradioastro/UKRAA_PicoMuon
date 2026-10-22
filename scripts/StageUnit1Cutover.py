#!/usr/bin/env python3
"""Prepare the fixed Unit_1 candidate outside production; never install or start it."""

from __future__ import annotations

import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile
import tempfile

PREFLIGHT_INDEX_SHA256 = "1e03a8e0e685c15fad2973f7ff142d3a33bfeb6e3af17603b195056a58e3890a"
REHEARSAL_REPORT_SHA256 = "b4a2ae656e66b08ce0bafbb8d5892b68f786f91ed20d4dfc1eac63d33ce40437"
MANIFEST_SHA256 = "b59b5608aa489ba0c288b0c0222bde95c011f27c2bca08d8c5a062514b6452fd"
PRODUCTION = "/home/pi/UKRAA_PicoMuon"
DEVICE = "/dev/serial/by-id/usb-Raspberry_Pi_Pico_E660D4A0A7598522-if00"
IDENTITY = "Raspberry_Pi_Pico_E660D4A0A7598522"
SHORT_ID = "E660D4A0A7598522"
SETTINGS = ("threshold_top", "reset_top", "threshold_bottom", "reset_bottom")

CONFIG_PROBE = r"""
import json, sys
from pathlib import Path
from picomuon_detectors import get_detectors, select_detector
from picomuon_metadata import load_legacy_settings
from picomuon_processing import processing_label
base = Path(sys.argv[1])
detectors = get_detectors(base)
assert list(detectors) == ["Unit_1"], detectors
unit = detectors["Unit_1"]
assert unit.serial_port == sys.argv[2]
assert unit.id_serial == sys.argv[3] and unit.id_serial_short == sys.argv[4]
assert processing_label(base, "Unit_1") == "Unit_1"
try:
    select_detector(base, None)
except ValueError:
    pass
else:
    raise AssertionError("Named configuration allowed implicit single selection")
assert load_legacy_settings(base, "Unit_1") == (200, 100, 200, 100)
print(json.dumps({"detectors": ["Unit_1"], "legacy_settings": [200, 100, 200, 100],
                  "implicit_selection_rejected": True}))
"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular_bytes(path: Path) -> bytes:
    require(stat.S_ISREG(path.lstat().st_mode), f"Expected regular, non-symlink file: {path}")
    return path.read_bytes()


def hash_index(data: bytes) -> dict[str, str]:
    result = {}
    for line in data.decode("utf-8").splitlines():
        value, name = line.split("  ", 1)
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in name,
                f"Unsafe hash-index path: {name}")
        require(name not in result and len(value) == 64
                and all(c in "0123456789abcdef" for c in value), f"Invalid hash entry: {name}")
        result[name] = value
    return result


def verified_inputs(preflight: Path, rehearsal: Path) -> tuple[dict[str, bytes], dict[str, bytes]]:
    index = regular_bytes(preflight / "SHA256SUMS")
    require(digest(index) == PREFLIGHT_INDEX_SHA256, "Preflight index differs from reviewed YtqHwx.")
    for name, expected in hash_index(index).items():
        require(digest(regular_bytes(preflight / name)) == expected, f"Preflight hash mismatch: {name}")
    require(digest(regular_bytes(preflight / "fresh-adoption-manifest.json")) == MANIFEST_SHA256,
            "Historical manifest differs from the approved batch.")
    report_bytes = regular_bytes(rehearsal / "validation-recheck.json")
    require(digest(report_bytes) == REHEARSAL_REPORT_SHA256,
            "Rehearsal report differs from the accepted validation recheck.")
    report = json.loads(report_bytes)
    require(report["status"] == "PASS" and report["approved_manifest_sha256"] == MANIFEST_SHA256,
            "Rehearsal was not accepted for this batch.")
    scripts = {}
    for name, expected in report["script_hashes"].items():
        require(PurePosixPath(name).name == name and "\\" not in name, f"Unsafe script name: {name}")
        data = regular_bytes(rehearsal / "scripts" / name)
        require(digest(data) == expected, f"Accepted rehearsal script changed: {name}")
        if name.endswith(".sh"):
            require(b"\r" not in data, f"Shell script must be LF-only: {name}")
        if name.endswith(".py"):
            compile(data, name, "exec")
        scripts[name] = data
    require(len(scripts) == 40, "Expected the complete 40-file accepted code baseline.")
    backup = {}
    with tarfile.open(fileobj=io.BytesIO(regular_bytes(
            preflight / "production-config-code-backup.tar.gz")), mode="r:gz") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in member.name,
                    f"Unsafe backup member: {member.name}")
            if member.isdir():
                continue
            require(member.isfile() and member.name not in backup,
                    f"Unsupported or duplicate backup member: {member.name}")
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"Cannot read backup member: {member.name}")
            backup[member.name] = source.read()
    return scripts, backup


def production_hashes(preflight: Path) -> dict[str, str]:
    text = regular_bytes(preflight / "production-config-code.sha256").decode("utf-8")
    prefix = PRODUCTION + "/"
    lines = []
    for line in text.splitlines():
        value, name = line.split("  ", 1)
        require(name.startswith(prefix), f"Unexpected production hash path: {name}")
        lines.append(f"{value}  {name[len(prefix):]}")
    return hash_index("\n".join(lines).encode())


def check_production(base: Path, hashes: dict[str, str]) -> None:
    for name, expected in hashes.items():
        require(digest(regular_bytes(base / name)) == expected,
                f"Production changed since preflight: {name}. Collect/review fresh evidence; do not override.")


def write_text(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def write_parser(path: Path, parser: configparser.ConfigParser) -> None:
    text = io.StringIO()
    parser.write(text)
    write_text(path, text.getvalue())


def build_candidate(stage: Path, scripts: dict[str, bytes], backup: dict[str, bytes]) -> dict[str, object]:
    candidate = stage / "candidate"
    candidate.mkdir()
    (candidate / "scripts").mkdir()
    (candidate / "config").mkdir()
    for name, data in scripts.items():
        (candidate / "scripts" / name).write_bytes(data)
    for name in ("config/USB.ini", "config/legacy.ini", "config/user.ini", "VERSION"):
        (candidate / name).write_bytes(backup[name])

    usb = configparser.ConfigParser(interpolation=None)
    usb.optionxform = str
    usb.read_string(backup["config/USB.ini"].decode("utf-8-sig"))
    require(usb.sections() == ["usb"] and not usb.defaults(), "Expected reviewed single-mode USB.ini.")
    require(usb.get("usb", "serial_port") == DEVICE
            and usb.get("usb", "id_serial") == IDENTITY
            and usb.get("usb", "id_serial_short") == SHORT_ID, "Unexpected production USB identity.")
    usb["detectors"] = {"Unit_1": DEVICE}
    usb["detector:Unit_1"] = {"id_serial": IDENTITY, "id_serial_short": SHORT_ID}
    write_parser(candidate / "config" / "USB.ini", usb)

    legacy = configparser.ConfigParser(interpolation=None)
    legacy.read_string(backup["config/legacy.ini"].decode("utf-8-sig"))
    require(not legacy.defaults() and legacy.sections() == ["legacy"],
            "Expected reviewed single-mode legacy.ini.")
    values = [legacy.getint("legacy", key) for key in SETTINGS]
    require(values == [200, 100, 200, 100], "Configured fallback differs from reviewed values.")
    legacy["legacy:Unit_1"] = {key: str(value) for key, value in zip(SETTINGS, values)}
    write_parser(candidate / "config" / "legacy.ini", legacy)

    units = stage / "units"
    units.mkdir()
    template = backup["install/PicoMuon@.service"].decode("utf-8").replace("\r\n", "\n")
    template = template.replace(
        "Description=UKRAA PicoMuon detector %i (Phase 2a collection pilot)",
        "Description=UKRAA PicoMuon detector %i collector",
    )
    for token, value in (("@PICOMUON_USER@", "pi"), ("@PICOMUON_GROUP@", "pi"),
                         ("@PICOMUON_BASE_PATH@", PRODUCTION)):
        template = template.replace(token, value)
    require("@PICOMUON_" not in template and "-pilot" not in template,
            "Unrendered or pilot service path.")
    require(f'ExecStart=/usr/bin/python3 "{PRODUCTION}/scripts/GetDataRaw.py" --detector %i' in template,
            "Unexpected named ExecStart.")
    write_text(units / "PicoMuon@Unit_1.service", template)
    return {
        "status": "candidate_built_not_authorized",
        "production_base": PRODUCTION,
        "script_count": len(scripts),
        "settings_basis": "Copied current configured fallback; hardware confirmation still required",
        "proposed_legacy_settings": dict(zip(SETTINGS, values)),
        "remaining_gates": [
            "Confirm actual hardware settings before approving named fallback",
            "Explicitly resolve existing daily cron named-processing/publication behavior",
            "Approve exact code/config/unit deployment and tested recovery procedure",
            "Fresh service/device-ownership and raw/status advancement checks at cutover",
        ],
        "scope": "Staging only: no production writes, serial access, service or cron changes",
    }


def native_checks(stage: Path) -> None:
    candidate = stage / "candidate"
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PICOMUON_", "PYTHON"))}
    environment.update(PICOMUON_BASE_PATH=str(candidate),
                       PYTHONPATH=str(candidate / "scripts"), PYTHONDONTWRITEBYTECODE="1")
    commands = [
        ("config-probe", [sys.executable, "-B", "-c", CONFIG_PROBE, str(candidate),
                          DEVICE, IDENTITY, SHORT_ID]),
        ("systemd-verify", ["systemd-analyze", "verify", "--man=no",
                           str(stage / "units" / "PicoMuon@Unit_1.service")]),
    ]
    commands.extend((f"syntax-{path.name}", ["bash", "-n", str(path)])
                    for path in sorted((candidate / "scripts").glob("*.sh")))
    for label, command in commands:
        result = subprocess.run(command, cwd=candidate, env=environment,
                                capture_output=True, text=True, check=False)
        write_text(stage / f"{label}.stdout", result.stdout)
        write_text(stage / f"{label}.stderr", result.stderr)
        write_text(stage / f"{label}.exit", f"{result.returncode}\n")
        require(result.returncode == 0, f"{label} failed; inspect its saved exit/stderr in {stage}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, default=Path.home() / "unit1-cutover-preflight.YtqHwx")
    parser.add_argument("--rehearsal", type=Path,
                        default=Path.home() / "unit1-processing-rehearsal.yo2to17p")
    args = parser.parse_args()
    if sys.platform != "linux" or os.getuid() == 0 or Path.home() != Path("/home/pi"):
        parser.error("Run on the production Pi as pi, without sudo; this helper only stages files.")
    os.umask(0o077)
    stage = Path(tempfile.mkdtemp(prefix="unit1-cutover-stage.", dir=Path.home()))
    print(f"STAGING DIRECTORY: {stage}", flush=True)
    report: dict[str, object] = {"status": "failed", "started_utc": datetime.now(timezone.utc).isoformat()}
    try:
        scripts, backup = verified_inputs(args.preflight.resolve(), args.rehearsal.resolve())
        hashes = production_hashes(args.preflight)
        require(set(backup) == set(hashes), "Backup inventory differs from captured production hashes.")
        for name, expected in hashes.items():
            require(digest(backup[name]) == expected, f"Backup hash mismatch: {name}")
        check_production(Path(PRODUCTION), hashes)
        report.update(build_candidate(stage, scripts, backup))
        report.update(
            preflight_directory=str(args.preflight.resolve()),
            preflight_index_sha256=PREFLIGHT_INDEX_SHA256,
            rehearsal_directory=str(args.rehearsal.resolve()),
            rehearsal_report_sha256=REHEARSAL_REPORT_SHA256,
            approved_manifest_sha256=MANIFEST_SHA256,
            script_changes=[
                {"path": f"scripts/{name}",
                 "action": "add" if f"scripts/{name}" not in backup else "replace"}
                for name, data in scripts.items() if backup.get(f"scripts/{name}") != data
            ],
        )
        report["status"] = "native_validation_pending"
        native_checks(stage)
        check_production(Path(PRODUCTION), hashes)
        report.update(status="STAGED_NOT_AUTHORIZED", production_files_unchanged=len(hashes))
        write_text(stage / "SHA256SUMS", "".join(
            f"{digest(path.read_bytes())}  {path.relative_to(stage).as_posix()}\n"
            for directory in ("candidate", "units")
            for path in sorted((stage / directory).rglob("*")) if path.is_file()
        ))
    except (OSError, ValueError, RuntimeError, configparser.Error, tarfile.TarError) as exc:
        report.update(status="failed", error=str(exc))
        print(f"STAGING FAILED: {exc}\nEvidence retained: {stage}", file=sys.stderr)
        return 1
    finally:
        report["completed_utc"] = datetime.now(timezone.utc).isoformat()
        write_text(stage / "staging-report.json", json.dumps(report, indent=2) + "\n")
    print(f"STAGING COMPLETE (NOT CUTOVER APPROVAL): {stage}")
    print("No production files, services, cron, serial device or archive were changed.")
    print("Privately download this staging folder for review. Do not install or start the candidate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
