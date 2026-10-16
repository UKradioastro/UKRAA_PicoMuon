#!/usr/bin/env python3
"""Prepend column headers to existing raw files while all collectors are stopped."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import tempfile
from typing import Optional

from picomuon_common import RAW_HEADER, get_base_path, log_error, log_message

SCRIPT_NAME = "AddRawHeaders.py"
HEADER_BYTES = (RAW_HEADER + "\n").encode("ascii")


def needs_header(path: Path) -> bool:
    with path.open("rb") as source:
        return source.readline().rstrip(b"\r\n") != RAW_HEADER.encode("ascii")


def add_header(path: Path) -> bool:
    """Keep a byte-exact backup, then atomically prepend the header once."""
    if path.is_symlink():
        raise ValueError(f"Refusing to modify symbolic link: {path}")
    if not needs_header(path):
        return False

    original = path.stat()
    backup = path.with_name(path.name + ".pre-header.bak")
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
            output.write(HEADER_BYTES)
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
            if not needs_header(path):
                skipped += 1
                continue
            if args.apply:
                add_header(path)
            log_message(SCRIPT_NAME, f"{'Added header' if args.apply else 'Would add header'}: {path}")
            changed += 1
    except (OSError, ValueError, RuntimeError) as exc:
        log_error(SCRIPT_NAME, f"Migration stopped: {exc}. Resolve the error before restarting collection.")
        return 1

    log_message(
        SCRIPT_NAME,
        f"{'Updated' if args.apply else 'Would update'} {changed} raw files; "
        f"{skipped} already have headers. Rejected rows are unchanged.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
