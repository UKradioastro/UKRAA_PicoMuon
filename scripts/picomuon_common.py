"""Shared installation and date helpers for PicoMuon scripts."""

from __future__ import annotations

import configparser
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, Optional, Tuple

_VERSION_PATTERN = re.compile(r"^\d{4}\.(0[1-9]|1[0-2])\.\d+$")

# Column width for process name in aligned log format
LOG_PROCESS_WIDTH = 26


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


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def format_log_entry(timestamp: datetime, process_name: str, message: str) -> str:
    """Format log line conforming to: YYYY-MM-DD HH:MM:SS UTC : %-26s : message"""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)
    ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"{ts_str} : {process_name:<{LOG_PROCESS_WIDTH}} : {message}"


def log_message(process_name: str, message: str) -> None:
    """Print aligned informational log message to stdout."""
    print(format_log_entry(utc_now(), process_name, message), flush=True)


def log_error(process_name: str, message: str) -> None:
    """Print aligned error log message to stderr."""
    print(format_log_entry(utc_now(), process_name, message), file=sys.stderr, flush=True)


def _log_uncaught_exception(exc_type: Any, exc_value: Any, exc_traceback: Any) -> None:
    """Ensure unhandled Python exceptions produce a timestamped entry in log-error.txt."""
    script_name = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "python"
    log_error(script_name, f"ERROR - unhandled {exc_type.__name__}: {exc_value}")
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = _log_uncaught_exception


def build_usb_ini_path(base_path: Optional[Path] = None) -> Path:
    """Return path to config/USB.ini, respecting PICOMUON_USB_INI_PATH override."""
    override = os.environ.get("PICOMUON_USB_INI_PATH")
    if override:
        return Path(override).expanduser().resolve()
    base = base_path or get_base_path()
    return base / "config" / "USB.ini"


def get_usb_options(base_path: Optional[Path] = None) -> Dict[str, str]:
    """Read USB.ini or return safe defaults."""
    config_file = build_usb_ini_path(base_path)
    parser = configparser.ConfigParser(interpolation=None)
    if config_file.exists():
        with open(config_file, mode="r", encoding="utf-8-sig") as f:
            parser.read_file(f)

    return {
        "serial_port": parser.get("usb", "serial_port", fallback="/dev/ttyACM0").strip() or "/dev/ttyACM0",
        "id_serial": parser.get("usb", "id_serial", fallback="").strip(),
        "id_serial_short": parser.get("usb", "id_serial_short", fallback="").strip(),
        "label": parser.get("usb", "label", fallback="").strip(),
    }


def get_usb_identity(device_path: str) -> Dict[str, str]:
    """Query udev properties for a serial device path."""
    try:
        result = subprocess.run(
            ["udevadm", "info", "--query=property", f"--name={device_path}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Unable to read USB identity for {device_path}: {exc}") from exc

    return dict(
        line.split("=", 1)
        for line in result.stdout.splitlines()
        if "=" in line
    )


def verify_usb_identity(device_path: str, usb_options: Dict[str, str]) -> Dict[str, str]:
    """Verify udev properties against expected ID_SERIAL / ID_SERIAL_SHORT in USB.ini."""
    expected_values: Tuple[Tuple[str, str], ...] = (
        ("ID_SERIAL", usb_options.get("id_serial", "")),
        ("ID_SERIAL_SHORT", usb_options.get("id_serial_short", "")),
    )
    if not any(expected for _, expected in expected_values):
        return {}

    actual_values = get_usb_identity(device_path)
    for property_name, expected_value in expected_values:
        if expected_value and actual_values.get(property_name) != expected_value:
            actual_value = actual_values.get(property_name, "<missing>")
            raise RuntimeError(
                f"USB identity mismatch for {device_path}: expected "
                f"{property_name}={expected_value}, got {actual_value}"
            )
    return actual_values


def build_raw_day_path(base_path: Path, current_time: datetime, label: Optional[str] = None) -> Path:
    """Build L0 raw file path: data/raw/[<label>/]YYYY/YYYY-MM/YYYY-MM-DD.txt"""
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    else:
        current_time = current_time.astimezone(timezone.utc)

    if label:
        return (
            base_path
            / "data"
            / "raw"
            / label
            / current_time.strftime("%Y")
            / current_time.strftime("%Y-%m")
            / f"{current_time.strftime('%Y-%m-%d')}.txt"
        )
    return (
        base_path
        / "data"
        / "raw"
        / current_time.strftime("%Y")
        / current_time.strftime("%Y-%m")
        / f"{current_time.strftime('%Y-%m-%d')}.txt"
    )


def get_target_date(default_days_ago: int = 1) -> date:
    """Return target date for processing, honoring PICOMUON_TARGET_DATE override."""
    env_target = os.environ.get("PICOMUON_TARGET_DATE")
    if env_target:
        try:
            return datetime.strptime(env_target.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(
                f"PICOMUON_TARGET_DATE {env_target!r} is not a valid YYYY-MM-DD date"
            ) from None
    return utc_yesterday()


def build_processed_day_path(
    base_path: Path,
    category: str,
    target_date: date,
    detector_label: str = "ACM0",
    extension: str = "txt",
) -> Path:
    """Build standard processed file path: data/processed/<category>/<detector>/YYYY/YYYY-MM/YYYY-MM-DD.<ext>"""
    return (
        base_path
        / "data"
        / "processed"
        / category
        / detector_label
        / target_date.strftime("%Y")
        / target_date.strftime("%Y-%m")
        / f"{target_date.strftime('%Y-%m-%d')}.{extension}"
    )


def build_neutron_path(base_path: Path, target_date: date) -> Path:
    """Build path to scraped NMDB neutron file for target_date."""
    return (
        base_path
        / "data"
        / "NMDB"
        / "neutrons"
        / target_date.strftime("%Y")
        / target_date.strftime("%Y-%m")
        / f"{target_date.strftime('%Y-%m-%d')}.txt"
    )


def build_daily_summary_path(base_path: Path) -> Path:
    """Build path to data/daily/summary.csv."""
    return base_path / "data" / "daily" / "summary.csv"


