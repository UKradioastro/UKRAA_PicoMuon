#!/usr/bin/env python3

import argparse
import configparser
import glob
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from typing import Dict, Optional, Tuple

import serial

from MergeConfig import set_config_values
from GetDataRaw import parse_and_validate_line
from picomuon_detectors import (
    detectors_from_config, get_detectors, read_usb_config, validate_label,
)
from picomuon_common import (
    build_usb_ini_path,
    get_base_path,
    get_usb_identity,
)


def find_by_id_alias(device_path: str) -> str:
    """Find corresponding /dev/serial/by-id/* alias for a device node."""
    try:
        device_target = os.path.realpath(device_path)
        for alias_path in sorted(glob.glob("/dev/serial/by-id/*")):
            if os.path.realpath(alias_path) == device_target:
                return alias_path
    except OSError:
        pass
    return ""


def sanitize_label(name: str) -> str:
    """Convert detector name to a file-safe label (alphanumeric, -, _), max 16 chars."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", name).strip("-")
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned[:16]


def probe_detector_sample(device_path: str, timeout_seconds: float = 8.0) -> Optional[str]:
    """Open port, read lines, and extract DetectorName from valid PicoMuon line if possible."""
    try:
        with serial.Serial(
            port=device_path,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
            exclusive=True,
        ) as ser:
            # Flush initial buffer so we don't start reading a partial line mid-transmission
            ser.reset_input_buffer()
            # Discard any partial first line
            ser.readline()
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                raw_line = ser.readline()
                if not raw_line:
                    continue
                line_str = raw_line.decode("utf-8", "ignore").strip()
                validated = parse_and_validate_line(line_str)
                if validated is not None:
                    return validated[8]
    except (OSError, serial.SerialException):
        pass
    return None


def configure_usb(
    device_path: str,
    config_path: str,
    serial_port: Optional[str] = None,
    label: Optional[str] = None,
) -> Tuple[Dict[str, str], str]:
    if detectors_from_config(read_usb_config(Path(config_path))):
        raise ValueError("Named detectors are registered; use --register LABEL instead of replacing [usb]")
    if not os.path.exists(device_path):
        raise ValueError(f"Device does not exist: {device_path}")

    identity = get_usb_identity(device_path)
    id_serial = identity.get("ID_SERIAL", "").strip()
    id_serial_short = identity.get("ID_SERIAL_SHORT", "").strip()
    if not id_serial and not id_serial_short:
        raise RuntimeError(
            f"No ID_SERIAL or ID_SERIAL_SHORT reported for {device_path}; "
            "USB.ini was not changed."
        )

    selected_port = serial_port or device_path
    if not os.path.exists(selected_port):
        raise ValueError(f"Selected serial path does not exist: {selected_port}")

    config_directory = os.path.dirname(config_path)
    os.makedirs(config_directory, exist_ok=True)
    if not os.path.exists(config_path):
        with open(config_path, mode="w", encoding="utf-8") as config_file:
            config_file.write("[usb]\n")

    options_to_set = {
        "serial_port": selected_port,
        "id_serial": id_serial,
        "id_serial_short": id_serial_short,
    }
    if label is not None:
        options_to_set["label"] = label

    set_config_values(config_path, "usb", options_to_set)
    return identity, selected_port


def configure_detector(
    device_path: str,
    config_path: str,
    label: str,
    serial_port: str,
    detector_name: Optional[str] = None,
) -> Tuple[Dict[str, str], str]:
    """Validate a staged update, then replace USB.ini once; retain all other units."""
    validate_label(label)
    if not os.path.exists(device_path) or not os.path.exists(serial_port):
        raise ValueError("Both the device and its stable by-id serial path must exist during registration")
    if os.path.realpath(device_path) != os.path.realpath(serial_port):
        raise ValueError("The selected serial path does not resolve to the supplied device")
    identity = get_usb_identity(serial_port)
    options = {
        "id_serial": identity.get("ID_SERIAL", "").strip(),
        "id_serial_short": identity.get("ID_SERIAL_SHORT", "").strip(),
    }
    if detector_name is not None:
        if "\n" in detector_name or "\r" in detector_name:
            raise ValueError("Detector name must be a single line")
        options["detector_name"] = detector_name.strip()
    path = Path(config_path)
    original = path.read_bytes() if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as staged:
            temporary = Path(staged.name)
            staged.write(original if original is not None else b"[usb]\n")
        if original is not None:
            shutil.copystat(path, temporary)
            if hasattr(os, "chown"):
                stat = path.stat()
                os.chown(temporary, stat.st_uid, stat.st_gid)
        set_config_values(str(temporary), "detectors", {label: serial_port})
        set_config_values(str(temporary), f"detector:{label}", options)
        detectors_from_config(read_usb_config(temporary))
        current = path.read_bytes() if path.exists() else None
        if current != original:
            raise RuntimeError("USB.ini changed during registration; retry without concurrent configuration edits")
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return identity, serial_port


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure single USB or register a Phase 2a pilot detector.")
    parser.add_argument("--register", metavar="LABEL", help="Register/edit one named detector without replacing others")
    parser.add_argument("--device", help="Device to register, e.g. /dev/ttyACM0")
    parser.add_argument("--serial-port", help="Stable /dev/serial/by-id/ alias (otherwise discovered)")
    parser.add_argument("--detector-name", help="Optional known name for cable-swap detection; not an identity key")
    args = parser.parse_args()
    config_path = str(build_usb_ini_path(get_base_path()))
    if args.register:
        if not args.device:
            parser.error("--register requires --device")
        try:
            port = args.serial_port or find_by_id_alias(args.device)
            if not port:
                raise ValueError("No stable by-id alias found; supply --serial-port")
            identity, port = configure_detector(args.device, config_path, args.register, port, args.detector_name)
        except (OSError, RuntimeError, ValueError, configparser.Error) as error:
            print(f"Detector registration failed: {error}", file=sys.stderr)
            return 1
        print(f"Registered {args.register} in {config_path}.")
        print(f"serial_port = {port}")
        print(f"id_serial = {identity.get('ID_SERIAL', '')}")
        print(f"id_serial_short = {identity.get('ID_SERIAL_SHORT', '')}")
        print("Development pilot: named daily/plot/web runs are opt-in; production service activation and archive migration remain pending.")
        return 0
    if args.device or args.serial_port or args.detector_name:
        parser.error("--device, --serial-port and --detector-name require --register")
    if get_detectors(get_base_path()):
        print("Named detectors are configured; use --register LABEL --device PATH to edit them.", file=sys.stderr)
        return 1
    default_dev = "/dev/ttyACM0"
    device_input = input(f"PicoMuon device path [{default_dev}]: ").strip()
    device_path = device_input or default_dev

    selected_port = device_path
    by_id_alias = find_by_id_alias(device_path)
    if by_id_alias:
        print(f"Stable by-id path found: {by_id_alias}")
        use_alias = input("Use this path in USB.ini? [Y/n]: ").strip().lower()
        if use_alias in ("", "y", "yes"):
            selected_port = by_id_alias

    print("Probing detector for name and signal...")
    detected_name = probe_detector_sample(device_path, timeout_seconds=5.0)
    proposed_label = ""
    if detected_name:
        proposed_label = sanitize_label(detected_name)
        print(f"Detected detector name: {detected_name} (proposed label: {proposed_label})")
    else:
        print("No immediate data stream seen; detector may be idle or unplugged.")

    label_prompt = "Detector label (leave blank for single-detector mode): "
    final_label = input(label_prompt).strip()

    try:
        identity, selected_port = configure_usb(
            device_path, config_path, selected_port, final_label
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"USB configuration failed: {error}", file=sys.stderr)
        return 1

    print(f"Updated {config_path}")
    print(f"serial_port = {selected_port}")
    print(f"id_serial = {identity.get('ID_SERIAL', '')}")
    print(f"id_serial_short = {identity.get('ID_SERIAL_SHORT', '')}")
    print(f"label = {final_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
