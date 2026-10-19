"""Detector selection, archive discovery and locking for offline processing."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date
import os
from pathlib import Path
from typing import Iterator, Optional

from picomuon_common import get_base_path, get_usb_options, log_error
from picomuon_detectors import select_detector


def processing_label(base: Path, detector: Optional[str]) -> Optional[str]:
    if detector is None:
        get_usb_options(base)  # Preserve the explicit-selection guard in named mode.
        return None
    selected = select_detector(base, detector)
    if selected is None:
        raise ValueError("A registered detector is required")
    return selected.label


def raw_roots(base: Path, label: Optional[str]) -> list[Path]:
    root = base / "data" / "raw"
    if label is not None:
        return [root / label]
    legacy_label = get_usb_options(base).get("label", "").strip()
    roots = [root / legacy_label] if legacy_label else []
    return list(dict.fromkeys([*roots, root, root / "ACM0"]))


def raw_dates(base: Path, label: Optional[str], first: Optional[date], last: date) -> list[date]:
    dates = set()
    for root in raw_roots(base, label):
        for path in root.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9][0-9][0-9]-[0-9][0-9]/*.txt"):
            try:
                day = date.fromisoformat(path.stem)
            except ValueError:
                continue
            if path.is_file() and path.parent.name == day.strftime("%Y-%m") and path.parent.parent.name == str(day.year):
                if (first is None or day >= first) and day <= last:
                    dates.add(day)
    return sorted(dates)


@contextmanager
def processing_lock(base: Path, label: Optional[str]) -> Iterator[None]:
    """Serialize daily/period writers, including different dates sharing a summary."""
    directory = base / "logfiles"
    if label is not None:
        directory = directory / "detectors" / label
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".processing.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            if lock.tell() == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError(f"Could not acquire processing lock for {label or 'single'}: {error}") from error
        else:
            import fcntl

            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError(f"Could not acquire processing lock for {label or 'single'}: {error}") from error
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def main() -> int:
    parser = argparse.ArgumentParser(description="List only the selected detector's raw archive dates.")
    parser.add_argument("--detector")
    parser.add_argument("--from", dest="first", type=date.fromisoformat)
    parser.add_argument("--to", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    try:
        base = get_base_path()
        label = processing_label(base, args.detector)
        for day in raw_dates(base, label, args.first, args.to):
            print(day.isoformat())
    except (OSError, ValueError, RuntimeError) as error:
        log_error("picomuon_processing", f"FAILED - {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
