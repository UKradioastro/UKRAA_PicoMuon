#!/usr/bin/env python3

import glob
import os
import re
import sys
import time
from typing import Dict, Optional, Tuple

import serial

from MergeConfig import set_config_values
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
                # Detector emits 8 fields before host timestamping:
                # Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp_C,Pres_hPa,DetectorName
                parts = line_str.split(",", 7)
                if len(parts) == 8 and parts[0] in ("T", "B", "C"):
                    try:
                        int(parts[1].strip())
                        float(parts[5].strip())
                        float(parts[6].strip())
                    except (ValueError, TypeError):
                        continue
                    detector_name = parts[7].strip()
                    return detector_name
    except (OSError, serial.SerialException):
        pass
    return None


def configure_usb(
    device_path: str,
    config_path: str,
    serial_port: Optional[str] = None,
    label: Optional[str] = None,
) -> Tuple[Dict[str, str], str]:
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


def main() -> int:
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

    config_path = str(build_usb_ini_path(get_base_path()))
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
