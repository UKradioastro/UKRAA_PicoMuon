"""Capture-time metadata and backwards-compatible detector payload handling."""

from __future__ import annotations

import configparser
import csv
from dataclasses import dataclass
import io
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, TextIO, Tuple

from picomuon_common import RAW_HEADER, raw_data_lines

SETTINGS_KEYS = ("threshold_top", "reset_top", "threshold_bottom", "reset_bottom")
Settings = Tuple[int, int, int, int]
METADATA_PREFIX = "# picomuon_metadata: "


def parse_settings(values: Iterable[str]) -> Settings:
    items = tuple(int(value.strip()) for value in values)
    if len(items) != 4 or any(value < 0 for value in items):
        raise ValueError("Detector settings must be four non-negative integers")
    return items[0], items[1], items[2], items[3]


def load_legacy_settings(base: Path, detector_label: Optional[str] = None) -> Settings:
    path = base / "config" / "legacy.ini"
    parser = configparser.ConfigParser(interpolation=None)
    with path.open(encoding="utf-8-sig") as source:
        parser.read_file(source)
    section = "legacy"
    if detector_label is not None:
        from picomuon_detectors import validate_label

        section = f"legacy:{validate_label(detector_label)}"
    # A named unit must never inherit another detector's shared defaults.
    if detector_label is not None and parser.defaults():
        raise ValueError(f"Remove [DEFAULT] from {path}; [{section}] must explicitly contain all four settings")
    try:
        return parse_settings(parser.get(section, key) for key in SETTINGS_KEYS)
    except (ValueError, configparser.Error) as exc:
        raise ValueError(f"Invalid detector settings in {path}: {exc}") from exc


def load_observation(base: Path) -> Dict[str, Dict[str, str]]:
    """Only explicitly shareable fields are copied; email is always private."""
    path = base / "config" / "user.ini"
    if not path.exists():
        return {}
    parser = configparser.ConfigParser(interpolation=None)
    with path.open(encoding="utf-8-sig") as source:
        parser.read_file(source)
    for key, limit in (("observatory_latitude", 90), ("observatory_longitude", 180),
                       ("observatory_altitude", None)):
        value = parser.get("Observatory", key, fallback="").strip()
        if value:
            try:
                number = float(value)
            except ValueError as exc:
                raise ValueError(f"Invalid {key} in {path}: {value!r}") from exc
            if not math.isfinite(number) or (limit is not None and abs(number) > limit):
                raise ValueError(f"Invalid {key} in {path}: {value!r}")
    allowed = {
        "Observatory": (
            "observatory_name", "observatory_longitude", "observatory_latitude",
            "observatory_altitude", "observatory_location", "observatory_tz",
            "station_id", "coordinate_datum", "altitude_reference",
        ),
        "Observer": ("observer_name", "observer_id"),
        "Detector": (
            "detector_model", "firmware_version", "orientation",
            "scintillator_dimensions", "detector_separation", "shielding", "notes",
            "settings_units", "calibration_date", "calibration_reference",
        ),
    }
    return {
        section: {
            key: parser.get(section, key).strip()
            for key in keys if parser.has_option(section, key)
            and parser.get(section, key).strip()
        }
        for section, keys in allowed.items() if parser.has_section(section)
    }


def split_payload(payload: str) -> Tuple[list[str], Optional[Settings]]:
    parts = next(csv.reader([payload], strict=True))
    if len(parts) < 8:
        raise ValueError("Expected 8 or 12 detector fields")
    parts = [part.strip() for part in parts]
    if len(parts) == 8:
        return parts, None
    if len(parts) >= 12:
        settings = parse_settings(parts[-4:])
        return parts[:7] + [",".join(parts[7:-4])], settings
    # Historic firmware allowed unquoted commas in detector names.
    if any(part.lstrip("+-").isdigit() or not part for part in parts[8:]):
        raise ValueError("Incomplete detector settings; expected all four values")
    return parts[:7] + [",".join(parts[7:])], None


def csv_line(parts: Iterable[object]) -> str:
    output = io.StringIO()
    csv.writer(output, lineterminator="\n").writerow(parts)
    return output.getvalue().rstrip("\n")


def write_metadata(handle: TextIO, metadata: Dict[str, Any]) -> None:
    handle.write(METADATA_PREFIX + json.dumps(metadata, sort_keys=True, ensure_ascii=True) + "\n")


def read_metadata(line: str) -> Optional[Dict[str, Any]]:
    if not line.startswith(METADATA_PREFIX):
        return None
    metadata = json.loads(line[len(METADATA_PREFIX):])
    if not isinstance(metadata, dict):
        raise ValueError("PicoMuon metadata must be a JSON object")
    return metadata


def data_lines(lines: Iterable[str]) -> Iterable[str]:
    """CSV readers must ignore metadata comments, but retain the column header."""
    return (line for line in lines if not line.startswith("#"))


@dataclass
class RawEventWriter:
    base: Path
    detector_label: Optional[str] = None
    previous_metadata: Optional[Dict[str, Any]] = None
    previous_handle: Optional[TextIO] = None

    def write(self, handle: TextIO, timestamp: str, payload: str) -> None:
        parts, settings = split_payload(payload)
        source = "detector"
        if settings is None:
            settings = load_legacy_settings(self.base, self.detector_label)
            source = "legacy.ini"
        metadata = {
            "observation": load_observation(self.base),
            "detector_name": parts[7],
            "settings": dict(zip(SETTINGS_KEYS, settings)),
            "settings_source": source,
        }
        if self.detector_label is not None:
            metadata["detector_label"] = self.detector_label
        if (
            metadata != self.previous_metadata or self.previous_handle is None
            or handle.name != self.previous_handle.name
        ):
            if self.previous_handle is None or handle.name != self.previous_handle.name:
                with Path(handle.name).open(encoding="utf-8") as existing:
                    first_line = existing.readline().rstrip("\r\n")
                if first_line != RAW_HEADER:
                    handle.write("\n" + RAW_HEADER + "\n")
            write_metadata(handle, metadata)
            self.previous_metadata = metadata
            self.previous_handle = handle
        handle.write(csv_line([timestamp, *parts, *settings]) + "\n")
        handle.flush()


class MetadataHistory:
    """Keep consecutive configuration segments, never one misleading daily value."""

    def __init__(self) -> None:
        self.context: Dict[str, Any] = {}
        self.segments: list[Dict[str, Any]] = []

    def consume_comment(self, line: str) -> bool:
        if not line.startswith("#"):
            return False
        metadata = read_metadata(line)
        if metadata is not None:
            self.context = metadata
        return True

    def add(self, timestamp: str, name: str, settings: Optional[Settings]) -> None:
        values = dict(zip(SETTINGS_KEYS, settings)) if settings is not None else None
        matched = (
            values is not None and self.context.get("settings") == values
            and self.context.get("detector_name") == name
        )
        segment = {
            "detector_name": name,
            "settings": values,
            "settings_source": self.context.get("settings_source", "unknown") if matched else "unknown",
            "observation": self.context.get("observation", {}),
        }
        if "detector_label" in self.context:
            segment["detector_label"] = self.context["detector_label"]
        if self.segments and all(self.segments[-1][key] == value for key, value in segment.items()):
            self.segments[-1]["last_event_utc"] = timestamp
            self.segments[-1]["event_count"] += 1
        else:
            self.segments.append({
                **segment, "first_event_utc": timestamp,
                "last_event_utc": timestamp, "event_count": 1,
            })

    def metadata(self) -> Dict[str, Any]:
        return {"schema_version": 1, "time_basis": "UTC", "segments": self.segments}


def metadata_from_raw(path: Path) -> Dict[str, Any]:
    history = MetadataHistory()
    with path.open(encoding="utf-8") as source:
        for line in source:
            if history.consume_comment(line) or not list(raw_data_lines([line])) or not line.strip():
                continue
            timestamp, payload = line.rstrip("\r\n").split(",", 1)
            parts, settings = split_payload(payload)
            history.add(timestamp, parts[7], settings)
    return history.metadata()


def metadata_from_product(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        for line in source:
            metadata = read_metadata(line)
            if metadata is not None:
                return metadata
            if not line.startswith("#"):
                break
    return {"schema_version": 1, "time_basis": "UTC", "segments": [], "metadata_status": "unknown"}
