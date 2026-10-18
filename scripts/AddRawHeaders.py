#!/usr/bin/env python3
"""Safely add raw column headers or remove obsolete JSON comments with collectors stopped."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import shutil
import tempfile
from typing import Optional

from picomuon_common import LEGACY_RAW_HEADER, RAW_HEADER, get_base_path, log_error, log_message

SCRIPT_NAME = "AddRawHeaders.py"


def needs_header(path: Path) -> bool:
    with path.open("rb") as source:
        return source.readline().rstrip(b"\r\n") not in (
            RAW_HEADER.encode("ascii"), LEGACY_RAW_HEADER.encode("ascii"),
        )


def has_metadata_comments(path: Path) -> bool:
    with path.open("rb") as source:
        return any(line.startswith(b"# picomuon_metadata:") for line in source)


def add_header(path: Path, remove_metadata: bool = False) -> bool:
    """Keep a byte-exact backup, then atomically apply one raw-file migration."""
    if path.is_symlink():
        raise ValueError(f"Refusing to modify symbolic link: {path}")
    if not (has_metadata_comments(path) if remove_metadata else needs_header(path)):
        return False

    original = path.stat()
    suffix = ".pre-metadata-removal.bak" if remove_metadata else ".pre-header.bak"
    backup = path.with_name(path.name + suffix)
    # Exclusive creation prevents overwriting an earlier backup.
    with path.open("rb") as source, backup.open("xb") as destination:
        shutil.copyfileobj(source, destination)
        destination.flush()
        os.fsync(destination.fileno())
    shutil.copystat(path, backup)

    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            if remove_metadata:
                with backup.open("rb") as source:
                    for line in source:
                        if not line.startswith(b"# picomuon_metadata:"):
                            output.write(line)
            else:
                with backup.open("r", encoding="utf-8") as source:
                    first = next((line for line in source if line.strip() and not line.startswith("#")), "")
                header = RAW_HEADER if len(next(csv.reader([first]))) >= 13 else LEGACY_RAW_HEADER
                output.write((header + "\n").encode("ascii"))
                with backup.open("rb") as source:
                    shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        shutil.copystat(path, temporary)
        if hasattr(os, "chown"):
            os.chown(temporary, original.st_uid, original.st_gid)
        current = path.stat()
        if (current.st_ino, current.st_size, current.st_mtime_ns) != (
            original.st_ino, original.st_size, original.st_mtime_ns
        ):
            raise RuntimeError(f"File changed during migration; stop all writers: {path}")
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Modify files (default: preview only)")
    parser.add_argument(
        "--remove-metadata", action="store_true",
        help="Remove only # picomuon_metadata: comments instead of adding column headers",
    )
    parser.add_argument(
        "--collectors-stopped", action="store_true",
        help="Confirm all raw-data collectors have been stopped before applying changes",
    )
    args = parser.parse_args()
    if args.apply and not args.collectors_stopped:
        parser.error("--apply requires --collectors-stopped; stop all collectors first")

    raw_root = get_base_path() / "data" / "raw"
    if not raw_root.is_dir():
        log_error(SCRIPT_NAME, f"Raw directory does not exist: {raw_root}")
        return 1

    changed = 0
    skipped = 0
    try:
        for path in sorted(raw_root.rglob("*.txt")):
            if "rejected" in path.relative_to(raw_root).parts:
                continue
            if path.is_symlink():
                raise ValueError(f"Refusing to modify symbolic link: {path}")
            required = has_metadata_comments(path) if args.remove_metadata else needs_header(path)
            if not required:
                skipped += 1
                continue
            if args.apply:
                add_header(path, remove_metadata=args.remove_metadata)
            action = "Remove metadata comments" if args.remove_metadata else "Add header"
            log_message(SCRIPT_NAME, f"{'Applied' if args.apply else 'Would apply'} {action}: {path}")
            changed += 1
    except (OSError, ValueError, RuntimeError) as exc:
        log_error(SCRIPT_NAME, f"Migration stopped: {exc}. Resolve the error before restarting collection.")
        return 1

    log_message(
        SCRIPT_NAME,
        f"{'Updated' if args.apply else 'Would update'} {changed} raw files; "
        f"{skipped} need no change. Rejected rows are unchanged.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
