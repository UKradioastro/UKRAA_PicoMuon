"""Shared installation and date helpers for PicoMuon scripts."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import re
from typing import Optional

_VERSION_PATTERN = re.compile(r"^\d{4}\.(0[1-9]|1[0-2])\.\d+$")


def get_base_path() -> Path:
    """Return the installation root, honoring the service/cron override."""
    configured_path = os.environ.get("PICOMUON_BASE_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def get_version() -> str:
    """Read and validate the project's CalVer version."""
    version_path = get_base_path() / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip()
    if not _VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid PicoMuon CalVer in {version_path}: {version!r}")
    return version


def utc_yesterday(now: Optional[datetime] = None) -> date:
    """Return yesterday's UTC date; reject naive injected datetimes."""
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc).date() - timedelta(days=1)
