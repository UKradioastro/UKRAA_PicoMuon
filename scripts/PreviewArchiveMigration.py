#!/usr/bin/env python3
"""Read-only preview of the explicitly confirmed production archive -> Unit_1."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Optional

from picomuon_common import LEGACY_RAW_HEADER, RAW_HEADER, get_base_path, log_error
from picomuon_metadata import read_metadata, split_payload

MAPPING = {
    "detector_label": "Unit_1",
    "detector_name": "56/148/627",
    "id_serial_short": "E660D4A0A7598522",
    "first_day": "2026-10-10",
    "source_layouts": ["data/raw/ACM0", "data/raw"],
    "basis": "User-confirmed physical detector continuity; not inferred from DetectorName",
}
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{1,6})?")


def issue(entry: dict[str, Any], code: str, detail: str, line: Optional[int] = None) -> None:
    entry["issue_counts"][code] = entry["issue_counts"].get(code, 0) + 1
    if len(entry["issue_samples"]) < 20:
        entry["issue_samples"].append({"code": code, "line": line, "detail": detail})


def unsafe_link(path: Path) -> bool:
    return any(part.is_symlink() for part in (path, *path.absolute().parents))


def scan_file(path: Path, today: date, *, rejected: bool = False) -> dict[str, Any]:
    """Read a bounded byte snapshot; never acquire writer locks or open for writing."""
    entry: dict[str, Any] = {
        "source": str(path), "day": None, "provisional": False,
        "issue_counts": {}, "issue_samples": [], "lines": 0, "event_count": 0,
        "event_types": {}, "settings_rows": 0, "legacy_rows": 0,
        "first_timestamp": None, "last_timestamp": None,
        "min_timestamp": None, "max_timestamp": None,
    }
    try:
        day = date.fromisoformat(path.stem)
        if path.stem != day.isoformat():
            raise ValueError("Expected YYYY-MM-DD.txt")
        entry["day"] = day.isoformat()
        entry["provisional"] = day >= today
        if day > today:
            issue(entry, "future_day", "File is dated after today UTC")
        if not rejected:
            if path.parent.name != day.strftime("%Y-%m") or path.parent.parent.name != str(day.year):
                issue(entry, "invalid_layout", "Expected YYYY/YYYY-MM/YYYY-MM-DD.txt")
            if day < date.fromisoformat(MAPPING["first_day"]):
                issue(entry, "outside_mapping", "Predates confirmed physical identity history")
    except ValueError as error:
        issue(entry, "invalid_filename", str(error))

    if unsafe_link(path):
        issue(entry, "symbolic_link", "Refusing to follow a source or ancestor symbolic link")
        return entry
    previous: Optional[datetime] = None
    minimum: Optional[datetime] = None
    maximum: Optional[datetime] = None
    types: Counter[str] = Counter()
    digest = hashlib.sha256()
    try:
        before = path.stat()
        if not stat.S_ISREG(before.st_mode):
            issue(entry, "not_regular_file", "Source is not a regular file")
            return entry
        with path.open("rb") as source:
            remaining = before.st_size
            while remaining:
                raw = source.readline(remaining)
                if not raw:
                    issue(entry, "truncated_during_read", "File shrank while reading")
                    break
                remaining -= len(raw)
                digest.update(raw)
                entry["lines"] += 1
                number = entry["lines"]
                if rejected:
                    continue
                try:
                    line = raw.decode("utf-8").rstrip("\r\n")
                    if not line.strip() or line in (RAW_HEADER, LEGACY_RAW_HEADER):
                        continue
                    if line.startswith("#"):
                        read_metadata(line)
                        continue
                    row = next(csv.reader([line], strict=True))
                    if not row or not TIMESTAMP.fullmatch(row[0]):
                        raise ValueError("Expected UTC timestamp YYYY-MM-DD HH:MM:SS[.ffffff]")
                    timestamp = datetime.fromisoformat(row[0])
                    stamp = timestamp.isoformat(sep=" ")
                    if entry["first_timestamp"] is None:
                        entry["first_timestamp"] = stamp
                    entry["last_timestamp"] = stamp
                    minimum = timestamp if minimum is None else min(minimum, timestamp)
                    maximum = timestamp if maximum is None else max(maximum, timestamp)
                    if previous is not None and timestamp <= previous:
                        issue(
                            entry, "timestamp_order",
                            f"Timestamp {stamp} is not later than {previous.isoformat(sep=' ')}", number,
                        )
                    previous = timestamp
                    if timestamp.date().isoformat() != entry["day"]:
                        issue(entry, "wrong_day", "Event UTC date does not match filename", number)
                    if len(row) not in (9, 13):
                        raise ValueError("Expected 9 legacy or 13 extended CSV fields")
                    payload, settings = split_payload(line.split(",", 1)[1])
                    event, count, adc, elapsed, dead, temp, pressure, name = payload
                    if event not in ("T", "B", "C"):
                        raise ValueError("Event must be T, B or C")
                    # Counter resets and signed elapsed/dead-time wrap are legitimate.
                    for value in (count, adc, elapsed, dead):
                        int(value)
                    if not all(math.isfinite(float(value)) for value in (temp, pressure)):
                        raise ValueError("Temperature and pressure must be finite")
                    if name != MAPPING["detector_name"]:
                        issue(entry, "identity_mismatch", f"Unexpected DetectorName {name!r}", number)
                    entry["event_count"] += 1
                    types[event] += 1
                    entry["legacy_rows" if settings is None else "settings_rows"] += 1
                except (UnicodeError, ValueError, csv.Error) as error:
                    issue(entry, "invalid_record", str(error), number)
        after = path.stat()
        entry["bytes"] = before.st_size
        entry["sha256"] = digest.hexdigest()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns,
        ):
            issue(entry, "changed_during_read", "Snapshot changed; rerun before considering adoption")
    except OSError as error:
        issue(entry, "read_error", str(error))
    entry["event_types"] = dict(types)
    entry["min_timestamp"] = minimum.isoformat(sep=" ") if minimum is not None else None
    entry["max_timestamp"] = maximum.isoformat(sep=" ") if maximum is not None else None
    if not rejected and not entry["event_count"]:
        issue(entry, "no_events", "No valid event-shaped records")
    return entry


def discover(raw: Path) -> tuple[list[Path], list[Path]]:
    """Only the two explicit production layouts; named pilot archives are not sources."""
    events: list[Path] = []
    rejected: list[Path] = []

    def walk(root: Path) -> None:
        def fail(error: OSError) -> None:
            raise error

        for directory, directories, filenames in os.walk(root, followlinks=False, onerror=fail):
            parent = Path(directory)
            for name in list(directories):
                child = parent / name
                if child.is_symlink():
                    (rejected if "rejected" in child.relative_to(raw).parts else events).append(child)
                    directories.remove(name)
            for name in sorted(filenames):
                if name.endswith(".txt"):
                    child = parent / name
                    (rejected if "rejected" in child.relative_to(raw).parts else events).append(child)

    for root in (raw / "ACM0", raw / "rejected"):
        if root.is_dir() and not unsafe_link(root):
            walk(root)
        elif root.exists() or root.is_symlink():
            (rejected if root.name == "rejected" else events).append(root)
    for path in sorted(raw.iterdir()):
        if path.name in ("ACM0", "rejected"):
            continue
        if path.suffix == ".txt":
            events.append(path)  # Misplaced files must not silently disappear.
        elif re.fullmatch(r"\d{4}", path.name):
            if unsafe_link(path):
                events.append(path)
            elif path.is_dir():
                walk(path)
    return events, rejected


def destination_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"path": str(path), "exists": False, "conflicts": []}
    if unsafe_link(path):
        info["conflicts"].append("Destination or ancestor is a symbolic link")
        return info
    try:
        for parent in path.parents:
            if parent.exists() and not parent.is_dir():
                info["conflicts"].append(f"Destination parent is not a directory: {parent}")
                return info
        info["exists"] = path.exists()
        if path.exists():
            if not path.is_file():
                info["conflicts"].append("Destination is not a regular file")
                return info
            before = path.stat()
            digest = hashlib.sha256()
            with path.open("rb") as source:
                remaining = before.st_size
                while remaining:
                    block = source.read(min(remaining, 1024 * 1024))
                    if not block:
                        info["conflicts"].append("Destination shrank during read")
                        break
                    remaining -= len(block)
                    digest.update(block)
            after = path.stat()
            info["sha256"] = digest.hexdigest()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_ino, after.st_size, after.st_mtime_ns,
            ):
                info["conflicts"].append("Destination changed during read")
    except OSError as error:
        info["conflicts"].append(f"Cannot inspect destination: {error}")
    return info


def preview(source_base: Path, destination_base: Path, *, today: Optional[date] = None) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    raw = source_base.absolute() / "data" / "raw"
    target = destination_base.absolute() / "data" / "raw" / MAPPING["detector_label"]
    if unsafe_link(raw) or not raw.is_dir():
        raise ValueError(f"Source raw directory must exist without symbolic-link ancestors: {raw}")
    paths, rejected_paths = discover(raw)
    files = [scan_file(path, today) for path in paths]
    rejected = [scan_file(path, today, rejected=True) for path in rejected_paths]
    plans: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in files:
        entry["validation"] = (
            "provisional" if entry["provisional"] else "invalid" if entry["issue_counts"] else "valid"
        )
        if entry["day"] is not None:
            groups[entry["day"]].append(entry)
    for day, segments in sorted(groups.items()):
        segments.sort(key=lambda item: (item["min_timestamp"] or "", item["source"]))
        destination = target / day[:4] / day[:7] / f"{day}.txt"
        info = destination_info(destination)
        conflicts = list(info["conflicts"])
        if any(item["issue_counts"] for item in segments):
            conflicts.append("Source validation failed; no records may be silently discarded")
        for index, left in enumerate(segments):
            for right in segments[index + 1:]:
                if left["max_timestamp"] is not None and right["min_timestamp"] is not None:
                    if right["min_timestamp"] <= left["max_timestamp"]:
                        conflicts.append(f"Overlapping timestamp ranges: {left['source']} and {right['source']}")
        identical = (
            len(segments) == 1 and info.get("sha256") is not None
            and info["sha256"] == segments[0].get("sha256")
        )
        if info["exists"] and not identical:
            conflicts.append("Destination already exists; never overwrite or implicitly merge")
        provisional = any(item["provisional"] for item in segments)
        action = (
            "defer_provisional" if provisional else "blocked" if conflicts
            else "already_present" if identical else "copy" if len(segments) == 1
            else "concatenate_in_timestamp_order"
        )
        plans.append({
            "day": day, "destination": str(destination), "destination_state": info,
            "sources_in_order": [item["source"] for item in segments],
            "event_count": sum(item["event_count"] for item in segments),
            "action": action, "provisional": provisional, "conflicts": conflicts,
        })
    diagnostics = []
    for entry in rejected:
        relative = Path(entry["source"]).relative_to(raw)
        # Preserve layout provenance to avoid collisions between diagnostic files.
        destination = target / "rejected" / ("legacy_ACM0" if relative.parts[0] == "ACM0" else "current")
        tail = relative.parts[1:] if relative.parts[0] in ("ACM0", "rejected") else relative.parts
        if tail and tail[0] == "rejected":
            tail = tail[1:]
        info = destination_info(destination.joinpath(*tail))
        conflicts = list(info["conflicts"])
        if entry["issue_counts"]:
            conflicts.append("Diagnostic snapshot has validation/read issues")
        if info["exists"]:
            conflicts.append("Diagnostic destination exists; no automatic merge or overwrite")
        diagnostics.append({
            **entry, "destination": info["path"], "conflicts": conflicts,
            "action": "defer_provisional" if entry["provisional"] else "blocked" if conflicts else "keep_separate",
        })
    blockers = []
    if not files:
        blockers.append("No production event files found in the explicitly mapped layouts")
    if any(entry["day"] is None for entry in files):
        blockers.append("Some event files have no valid day/destination")
    blocked = bool(
        blockers or any(plan["conflicts"] for plan in plans)
        or any(entry["conflicts"] for entry in diagnostics)
    )
    return {
        "schema_version": 1, "read_only": True, "today_utc": today.isoformat(),
        "source_base": str(source_base.absolute()), "destination_base": str(destination_base.absolute()),
        "mapping": dict(MAPPING),
        "notes": [
            "Proposals only: no archive/configuration/service/log/lock files are written.",
            "Today UTC and future files are provisional and excluded from completed-day adoption.",
            "Legacy settings are not invented; recorded names/settings and all source bytes remain unchanged.",
            "Concatenation is a future operation, requiring header handling without dropping event records.",
            "Timestamp intersections are conflicts even if rows might be duplicates; no automatic deduplication.",
            "Rejected files are diagnostics only; invalid event rows remain in their original source.",
            "Source/destination snapshots are not a cutover authorization; rerun with collectors stopped before adoption.",
        ],
        "files": files, "plans": plans, "rejected_diagnostics": diagnostics,
        "blockers": blockers, "has_conflicts": blocked,
        "summary": {
            "event_files": len(files),
            "completed_files": sum(not item["provisional"] for item in files),
            "valid_completed_files": sum(item["validation"] == "valid" for item in files),
            "provisional_files": sum(item["provisional"] for item in files),
            "rejected_files": len(rejected),
            "proposed_days": len(plans),
            "conflicting_days": sum(bool(plan["conflicts"]) for plan in plans),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-base", type=Path, default=get_base_path(), help="Production installation root")
    parser.add_argument("--destination-base", type=Path, help="Proposed installation root (default: source root)")
    args = parser.parse_args()
    try:
        report = preview(args.source_base, args.destination_base or args.source_base)
    except (OSError, ValueError) as error:
        log_error("PreviewArchiveMigration.py", f"Preview failed: {error}")
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["has_conflicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
