#!/usr/bin/env python3
"""Fixed October 10-20 Unit_1 adoption: read-only manifest by default."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
from typing import Any, Iterator

from picomuon_common import LEGACY_RAW_HEADER, get_base_path, log_error
from PreviewArchiveMigration import MAPPING, scan_file, unsafe_link

# This batch cannot silently expand as more production days become complete.
REVIEWED = {
    "2026-10-10": "fc4d86c2c9a76191ac88d68d2fa3d6937864bc0d4797c98ffd2acb9729943ebd",
    "2026-10-11": "b5c063fb45fede4dd6b46a84a5bf3d3f545b7866137cda150706e40c40e8f7e7",
    "2026-10-12": "2aa5ada8e0742394d4622ddba90aa274709507da15e46219a38e8dd1a3f6973c",
    "2026-10-13": "aa3a0f4eaa9909bc9a04fce20b29049312b9e76935c5882ab850522b1d182765",
    "2026-10-14": "6bbd94f9f6998c3b39d8a1c832457692ce3877ddf19fabf76bc8a584584439d1",
    "2026-10-15": "c7ed1c123c138ef9f6c168a180b9755dbde91089d6ae924718f59e302eaf0e93",
    "2026-10-16": "043b8099446bf003b95be97733a09fb5a57dc6c10396877490d08e0c4e7667d5",
    "2026-10-17": "14d588111db05b7351d249864c78f08f5418b24d4d1dd90d3480ca691cea2411",
    "2026-10-18": "4d3a890935ec4b9a6aec27dd109f88fcc43402a349c4f18e7c605bb8559df31f",
    "2026-10-19": "cfc942e409eece2d2b2c850d6be7249743272feca8b7a14e3ec18becabebb43d",
    "2026-10-20": "ed7163fcff7ebc42eb32cdb75b90a477d380f2367f11cf74975a45ba9155e12a",
}
OCT13_SOURCES = (
    "0bf38e6c64a856e3986b1a9a8f49f632fc1e555e85c10563f262cd27b543d8cd",
    "66b3c7ed1d732994c29aaa7b54d38b04e7ecf0bb882876f709da9785b015cc79",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def checked(path: Path) -> Path:
    require(".." not in path.parts, f"Parent traversal is not allowed: {path}")
    path = path.absolute()
    require(not unsafe_link(path), f"Symbolic link or linked ancestor: {path}")
    for parent in path.parents:
        require(not parent.exists() or parent.is_dir(), f"Parent is not a directory: {parent}")
    return path


def read_snapshot(path: Path) -> bytes:
    checked(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode), f"Not a regular file: {path}")
    with path.open("rb") as source:
        data = source.read(before.st_size + 1)
    after = path.stat()
    require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        and len(data) == before.st_size,
        f"File changed while reading: {path}",
    )
    return data


def fingerprint(data: bytes) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def event_lines(data: bytes) -> list[bytes]:
    return [
        line for line in data.splitlines(keepends=True)
        if line.strip() and not line.startswith((b"#", b"RPiTimestamp,"))
    ]


def ordered_oct13(parts: list[bytes]) -> bytes:
    require(tuple(fingerprint(part)["sha256"] for part in parts) == OCT13_SOURCES,
            "October 13 exception source hashes do not match the reviewed pair")
    header = (LEGACY_RAW_HEADER + "\n").encode("ascii")
    require(all(part.startswith(header) for part in parts), "October 13 headers differ")
    records = [line for part in parts for line in event_lines(part)]
    require(all(line.endswith(b"\n") for line in records), "Unterminated October 13 event")
    counts = Counter(records)
    require(all(number == 1 for number in counts.values()), "Duplicate October 13 event bytes")
    ranges = [(min(line.split(b",", 1)[0] for line in event_lines(part)),
               max(line.split(b",", 1)[0] for line in event_lines(part))) for part in parts]
    require(ranges[0][1] < ranges[1][0], "October 13 segments overlap")
    records.sort(key=lambda line: datetime.fromisoformat(line.split(b",", 1)[0].decode("ascii")))
    timestamps = [line.split(b",", 1)[0] for line in records]
    require(all(a < b for a, b in zip(timestamps, timestamps[1:])), "Duplicate October 13 timestamps")
    output = header + b"".join(records)
    require(Counter(event_lines(output)) == counts, "October 13 event multiplicity changed")
    require(fingerprint(output)["sha256"] == REVIEWED["2026-10-13"], "October 13 output hash differs")
    return output


def output_bytes(source: Path, entry: dict[str, Any]) -> bytes:
    parts = []
    for item in entry["sources"]:
        data = read_snapshot(source / item["path"])
        require(fingerprint(data) == {key: item[key] for key in ("sha256", "bytes")},
                f"Source no longer matches approved manifest: {item['path']}")
        parts.append(data)
    data = ordered_oct13(parts) if entry["operation"] == "oct13_ordered_copy" else parts[0]
    require(fingerprint(data) == {key: entry[key] for key in ("sha256", "bytes")},
            f"Candidate no longer matches approved manifest: {entry['destination']}")
    return data


def destination_state(destination: Path, entry: dict[str, Any]) -> str:
    path = checked(destination / entry["destination"])
    if not path.exists():
        return "absent"
    require(fingerprint(read_snapshot(path)) == {key: entry[key] for key in ("sha256", "bytes")},
            f"Destination conflict; never overwrite: {path}")
    return "identical"


def manifest(source: Path, destination: Path) -> dict[str, Any]:
    source, destination = checked(source), checked(destination)
    require(source.is_dir() and destination.is_dir(), "Source and destination installation roots must exist")
    require(date.fromisoformat(max(REVIEWED)) < datetime.now(timezone.utc).date(),
            "Batch includes an active/future UTC day")
    entries = []
    for day, expected in REVIEWED.items():
        suffix = f"{day[:4]}/{day[:7]}/{day}.txt"
        roots = ["data/raw/ACM0", "data/raw"] if day == "2026-10-13" else [
            "data/raw/ACM0" if day < "2026-10-13" else "data/raw"
        ]
        paths = [f"{root}/{suffix}" for root in roots]
        # Refuse an unexpected extra segment rather than silently excluding it.
        alternate = source / ("data/raw" if day < "2026-10-13" else "data/raw/ACM0") / suffix
        if day != "2026-10-13":
            require(not alternate.exists() and not alternate.is_symlink(), f"Unexpected extra source: {alternate}")
        parts, sources, events, types = [], [], 0, Counter()
        for index, relative in enumerate(paths):
            path = source / relative
            data = read_snapshot(path)
            validation = scan_file(path, datetime.now(timezone.utc).date())
            allowed = {"timestamp_order": 1} if day == "2026-10-13" and index == 1 else {}
            require(validation["issue_counts"] == allowed, f"Source validation failed: {path}")
            require(validation["sha256"] == fingerprint(data)["sha256"], f"Source changed: {path}")
            parts.append(data)
            sources.append({"path": relative, **fingerprint(data)})
            events += validation["event_count"]
            types.update(validation["event_types"])
        data = ordered_oct13(parts) if len(parts) == 2 else parts[0]
        require(fingerprint(data)["sha256"] == expected, f"Source differs from reviewed batch: {day}")
        entries.append({
            "kind": "events", "day": day, "sources": sources,
            "destination": f"data/raw/Unit_1/{suffix}",
            "operation": "oct13_ordered_copy" if len(parts) == 2 else "byte_exact_copy",
            **fingerprint(data), "events": events, "event_types": dict(sorted(types.items())),
        })
    for number in range(13, 21):
        day = f"2026-10-{number}"
        relative = f"data/raw/rejected/{day}.txt"
        data = read_snapshot(source / relative)
        entries.append({
            "kind": "diagnostic", "day": day, "sources": [{"path": relative, **fingerprint(data)}],
            "destination": f"data/raw/Unit_1/rejected/current/{day}.txt",
            "operation": "byte_exact_copy", **fingerprint(data),
        })
    for entry in entries:
        destination_state(destination, entry)
    return {
        "schema_version": 1, "batch": "Unit_1-2026-10-10_2026-10-20",
        "source_base": str(source), "destination_base": str(destination),
        "mapping": dict(MAPPING), "entries": entries,
        "qualifications": [
            "Copy only; originals, services, configuration and derived products remain untouched",
            "October 13 hash-bound ordered-copy exception only; no deduplication or invented events",
            "2943 skipped sequence numbers; cause unknown; no acquisition-completeness claim",
            "Missing raw settings remain absent; processing assumptions are not historical evidence",
            "Detector elapsed span includes short gaps and is not calibrated dead-time-corrected exposure",
            "Active-day, pre-October-10 and later completed files are excluded from this fixed batch",
            "Backup restore verification and control of all relevant writers are operator prerequisites",
        ],
    }


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def make_directory(path: Path, device: int) -> None:
    checked(path)
    if not path.exists():
        make_directory(path.parent, device)
        path.mkdir(mode=0o755)
        sync_directory(path.parent)
    require(path.is_dir() and path.stat().st_dev == device, f"Unexpected directory or filesystem: {path}")


def require_linux() -> None:
    require(sys.platform.startswith("linux"), "Apply/rollback require Linux directory fsync and flock; preview works elsewhere")


def check_owner(path: Path, *, private: bool = False) -> None:
    require(path.stat().st_uid == os.geteuid(), f"Run as the owner of {path}")
    if private:
        require(path.is_dir() and stat.S_IMODE(path.stat().st_mode) == 0o700,
                "Run directory must be private (mode 0700)")


@contextmanager
def run_lock(run: Path) -> Iterator[None]:
    import fcntl

    with (run / ".lock").open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def save_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    with path.open("xb") as output:
        os.chmod(path, mode)
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    sync_directory(path.parent)


def journal(run: Path, action: str, index: int) -> None:
    path = checked(run / "journal.jsonl")
    with path.open("ab") as output:
        output.write((json.dumps({"action": action, "index": index}) + "\n").encode("ascii"))
        output.flush()
        os.fsync(output.fileno())
    sync_directory(run)


def journal_records(run: Path) -> list[dict[str, Any]]:
    path = run / "journal.jsonl"
    if not path.exists():
        return []
    data = read_snapshot(path)
    require(not data or data.endswith(b"\n"), "Incomplete journal; preserve it and request manual recovery")
    records = [json.loads(line) for line in data.splitlines()]
    require(all(isinstance(item, dict) and set(item) == {"action", "index"}
                and item["action"] in ("intent", "promoted", "noop", "quarantined")
                and type(item["index"]) is int and item["index"] >= 0 for item in records),
            "Invalid journal")
    return records


def promote(stage: Path, target: Path) -> None:
    os.link(stage, target)  # Atomic no-clobber: FileExistsError is never converted into success.
    sync_directory(target.parent)


def execute(manifest_path: Path, approved_hash: str, run: Path, *,
            backup_verified: bool, writers_stopped: bool, rollback: bool = False) -> dict[str, Any]:
    require(backup_verified and writers_stopped, "Requires verified backup/restore and stopped-writers confirmations")
    require_linux()
    data = read_snapshot(manifest_path)
    require(hashlib.sha256(data).hexdigest() == approved_hash, "Manifest approval hash mismatch")
    plan = json.loads(data)
    require(isinstance(plan, dict) and isinstance(plan.get("source_base"), str)
            and isinstance(plan.get("destination_base"), str), "Invalid manifest roots")
    source, destination = checked(Path(plan["source_base"])), checked(Path(plan["destination_base"]))
    # Never trust manifest-supplied paths or operations without rebuilding the constrained plan.
    require(plan == manifest(source, destination), "Manifest differs from freshly validated fixed-batch plan")
    run = checked(run)
    require(not run.is_relative_to(source) and not run.is_relative_to(destination)
            and not source.is_relative_to(run) and not destination.is_relative_to(run),
            "Run directory must be separate from both installation trees")
    require(run.parent.is_dir(), "Run directory parent must already exist")
    device = destination.stat().st_dev
    require(run.parent.stat().st_dev == device, "Run directory must be on destination filesystem")
    check_owner(destination)
    for entry in plan["entries"]:
        for item in entry["sources"]:
            check_owner(source / item["path"])
        parent = (destination / entry["destination"]).parent
        while not parent.exists():
            parent = parent.parent
        require(parent.stat().st_dev == device, f"Destination crosses a filesystem boundary: {parent}")
    if not run.exists():
        require(not rollback, "Rollback requires an existing run")
        run.mkdir(mode=0o700)
        sync_directory(run.parent)
    check_owner(run, private=True)
    require(run.stat().st_dev == device, "Run directory crosses a filesystem boundary")
    require(not unsafe_link(run / ".lock"), "Linked lock file")
    with run_lock(run):
        saved = run / "approved-manifest.json"
        if not saved.exists():
            require(not rollback and not list(run.glob("*.bin")) and not journal_records(run),
                    "Run evidence incomplete; manual recovery required")
            save_bytes(saved, data)
        require(read_snapshot(saved) == data, "Run belongs to another manifest")
        records = journal_records(run)
        require(all(item["index"] < len(plan["entries"]) for item in records), "Journal index outside approved batch")
        if rollback:
            return quarantine(plan, run, records, device)
        require(not any(item["action"] == "quarantined" for item in records),
                "Run has been rolled back; use a separately approved new run")
        # Stage the entire batch before any final destination file is created.
        needed = 0
        for index, entry in enumerate(plan["entries"]):
            stage = checked(run / f"{index:04d}.bin")
            if stage.exists():
                require(fingerprint(read_snapshot(stage)) == {key: entry[key] for key in ("sha256", "bytes")},
                        f"Staged file differs; preserve evidence and recover manually: {stage}")
            else:
                needed += entry["bytes"]
        require(shutil.disk_usage(run).free >= needed + 1024 * 1024, "Insufficient staging space")
        for index, entry in enumerate(plan["entries"]):
            stage = checked(run / f"{index:04d}.bin")
            candidate = output_bytes(source, entry)
            if not stage.exists():
                save_bytes(stage, candidate, 0o644)
            require(read_snapshot(stage) == candidate, f"Stage verification failed: {stage}")
            with stage.open("r+b") as handle:
                os.fsync(handle.fileno())
            sync_directory(run)
            if entry["kind"] == "events":
                # Validator requires a dated path, while stages intentionally use inert names.
                require(len(event_lines(candidate)) == entry["events"], "Staged event count changed")
        # Recheck all approved sources and destinations immediately before promotion.
        require(plan == manifest(source, destination), "Batch changed during staging")
        created, noops = 0, 0
        for index, entry in enumerate(plan["entries"]):
            stage = checked(run / f"{index:04d}.bin")
            target = checked(destination / entry["destination"])
            output_bytes(source, entry)
            prior = [item["action"] for item in records if item["index"] == index]
            if destination_state(destination, entry) == "identical":
                if os.path.samefile(stage, target):
                    require("intent" in prior, "Linked destination without journal intent")
                    sync_directory(target.parent)
                    journal(run, "promoted", index)
                    created += 1
                else:
                    require("promoted" not in prior and "intent" not in prior,
                            "Run destination identity changed; manual recovery required")
                    journal(run, "noop", index)
                    noops += 1
                continue
            require("promoted" not in prior and "noop" not in prior,
                    "Previously accepted destination disappeared; manual recovery required")
            make_directory(target.parent, device)
            journal(run, "intent", index)
            promote(stage, target)
            journal(run, "promoted", index)
            created += 1
        require(plan == manifest(source, destination), "Final source/destination verification failed")
        for entry in plan["entries"]:
            require(destination_state(destination, entry) == "identical", "Final destination missing")
        return {"status": "batch_verified", "created_or_resumed": created, "identical_noops": noops,
                "manifest_sha256": approved_hash, "run_directory": str(run)}


def quarantine(plan: dict[str, Any], run: Path, records: list[dict[str, Any]], device: int) -> dict[str, Any]:
    destination = Path(plan["destination_base"])
    eligible = []
    for index, entry in enumerate(plan["entries"]):
        prior = [item["action"] for item in records if item["index"] == index]
        if "intent" not in prior:
            continue  # Pre-existing no-ops and unrelated files must never be rolled back.
        stage = checked(run / f"{index:04d}.bin")
        require(fingerprint(read_snapshot(stage)) == {key: entry[key] for key in ("sha256", "bytes")},
                "Rollback stage hash changed")
        target = checked(destination / entry["destination"])
        recovered = checked(run / "quarantine" / f"{index:04d}.bin")
        if target.exists():
            require(os.path.samefile(stage, target), "Rollback refuses changed destination identity")
            destination_state(destination, entry)
            eligible.append((index, stage, target, recovered))
        else:
            require(recovered.exists() and os.path.samefile(stage, recovered),
                    "Rollback destination missing without recovery evidence")
    for index, stage, target, recovered in eligible:
        make_directory(recovered.parent, device)
        if not recovered.exists():
            promote(stage, recovered)
        require(os.path.samefile(stage, recovered), "Quarantine collision")
        # Writers must remain stopped; recheck immediately before this exact unlink.
        require(read_snapshot(target) == read_snapshot(stage) and os.path.samefile(stage, target),
                "Destination changed during rollback")
        target.unlink()
        sync_directory(target.parent)
        journal(run, "quarantined", index)
    return {"status": "quarantined_run_created_files_only", "files": len(eligible)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-base", type=Path)
    parser.add_argument("--destination-base", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--rollback", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--approve-manifest", help="SHA-256 of the exact reviewed manifest bytes")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--backup-verified", action="store_true", help="Confirm backup AND isolated restore were verified")
    parser.add_argument("--writers-stopped", action="store_true", help="Confirm all relevant writers remain stopped")
    args = parser.parse_args()
    if args.apply or args.rollback:
        if args.source_base or args.destination_base:
            parser.error("Apply/rollback take installation paths only from the approved manifest")
        if not (args.manifest and args.approve_manifest and args.run_dir and args.backup_verified and args.writers_stopped):
            parser.error("Apply/rollback require --manifest, --approve-manifest, --run-dir, --backup-verified and --writers-stopped")
    elif any((args.manifest, args.approve_manifest, args.run_dir, args.backup_verified, args.writers_stopped)):
        parser.error("Approval and run options require explicit --apply or --rollback")
    try:
        if args.apply or args.rollback:
            result = execute(args.manifest, args.approve_manifest, args.run_dir,
                             backup_verified=args.backup_verified, writers_stopped=args.writers_stopped,
                             rollback=args.rollback)
        else:
            source = args.source_base or get_base_path()
            result = manifest(source, args.destination_base or source)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as error:
        log_error("AdoptUnit1Archive.py", f"FAILED - {error}. Preserve the run evidence; do not relax checks.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
