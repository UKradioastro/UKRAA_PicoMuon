"""Explicit, validated detector identities for the Phase 2a collection pilot."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Dict, Optional

LABEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,15}")
BY_ID_PREFIX = "/dev/serial/by-id/"


def validate_label(label: str) -> str:
    if not LABEL_PATTERN.fullmatch(label) or label.casefold() in ("rejected", "single"):
        raise ValueError(
            f"Invalid detector label {label!r}: use 1-16 letters/digits, '-' or '_', "
            "starting with a letter/digit; 'rejected' and 'single' are reserved"
        )
    return label


def read_usb_config(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    # Labels are user-chosen path components, so case must not be lost.
    parser.optionxform = str
    if path.exists():
        with path.open(encoding="utf-8-sig") as source:
            parser.read_file(source)
    return parser


@dataclass(frozen=True)
class DetectorConfig:
    label: str
    serial_port: str
    id_serial: str
    id_serial_short: str
    detector_name: str = ""

    def usb_options(self) -> Dict[str, str]:
        return {
            "label": self.label,
            "serial_port": self.serial_port,
            "id_serial": self.id_serial,
            "id_serial_short": self.id_serial_short,
        }


def detectors_from_config(parser: configparser.ConfigParser) -> Dict[str, DetectorConfig]:
    detectors: Dict[str, DetectorConfig] = {}
    labels = set()
    paths = set()
    serial_ids = set()
    short_ids = set()
    names = set()
    entries = parser.items("detectors") if parser.has_section("detectors") else []
    if entries and parser.defaults():
        raise ValueError("USB.ini [DEFAULT] values are not supported in multi-detector configuration")
    for label, port in entries:
        validate_label(label)
        if label.casefold() in labels:
            raise ValueError(f"Duplicate detector label (case-insensitive): {label}")
        labels.add(label.casefold())
        port = port.strip()
        suffix = port[len(BY_ID_PREFIX):]
        if not port.startswith(BY_ID_PREFIX) or not suffix or any(c in suffix for c in "/\\\r\n"):
            raise ValueError(f"{label}: a stable {BY_ID_PREFIX} path is required")
        resolved = os.path.normcase(os.path.realpath(port))
        if resolved in paths:
            raise ValueError(f"Duplicate physical device or serial alias: {port}")
        paths.add(resolved)
        section = f"detector:{label}"
        options = dict(parser.items(section)) if parser.has_section(section) else {}
        unknown = set(options) - {"id_serial", "id_serial_short", "detector_name"}
        if unknown:
            raise ValueError(f"Unknown options in [{section}]: {', '.join(sorted(unknown))}")
        identity = options.get("id_serial", "").strip()
        short = options.get("id_serial_short", "").strip()
        if not identity and not short:
            raise ValueError(f"[{section}] requires id_serial or id_serial_short")
        if (identity and identity in serial_ids) or (short and short in short_ids):
            raise ValueError(f"Duplicate USB identity for detector {label}")
        if identity:
            serial_ids.add(identity)
        if short:
            short_ids.add(short)
        name = options.get("detector_name", "").strip()
        if name and name in names:
            raise ValueError(f"Duplicate configured detector_name: {name!r}")
        if name:
            names.add(name)
        detectors[label] = DetectorConfig(label, port, identity, short, name)

    for section in parser.sections():
        if section.startswith("detector:") and section[len("detector:"):] not in detectors:
            raise ValueError(f"Orphan [{section}]: register its label in [detectors] or remove the section")
    return detectors


def get_detectors(base_path: Optional[Path] = None) -> Dict[str, DetectorConfig]:
    from picomuon_common import build_usb_ini_path

    return detectors_from_config(read_usb_config(build_usb_ini_path(base_path)))


def select_detector(base_path: Path, label: Optional[str]) -> Optional[DetectorConfig]:
    detectors = get_detectors(base_path)
    if label is None:
        if detectors:
            raise ValueError(
                "USB.ini contains [detectors]; select one explicitly with --detector LABEL. "
                "Multi-detector processing/installer activation is not ready in this collection pilot."
            )
        return None
    validate_label(label)
    if label not in detectors:
        raise ValueError(f"Detector {label!r} is not registered in USB.ini [detectors]")
    return detectors[label]


def check_detector_name(
    name: str, selected: DetectorConfig, detectors: Dict[str, DetectorConfig],
) -> None:
    for label, detector in detectors.items():
        if label != selected.label and name and name == detector.detector_name:
            raise RuntimeError(
                f"{selected.label}: received name {name!r} registered to {label}; refusing possible cable swap"
            )
