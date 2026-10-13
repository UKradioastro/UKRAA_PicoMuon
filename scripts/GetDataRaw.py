#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Optional, TextIO

import serial

from picomuon_common import (
    build_raw_day_path,
    get_base_path,
    get_usb_options,
    log_error,
    log_message,
    utc_now,
    verify_usb_identity,
)

PROCESS_NAME = "GetDataRaw.py"


def parse_and_validate_line(line_str: str) -> Optional[tuple[str, str, int, int, int, int, float, float, str]]:
    """Validate 8-field serial payload from detector:
    Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp_C,Pres_hPa,DetectorName
    The 8th element (DetectorName) can contain arbitrary characters; we split on up to 7 commas.
    """
    parts = line_str.split(",", 7)
    if len(parts) != 8:
        return None

    event, event_count_s, adc_s, elapsed_s, dead_s, temp_s, pres_s, detector_name = parts
    event = event.strip()
    if event not in ("T", "B", "C"):
        return None

    try:
        event_count = int(event_count_s.strip())
        adc = int(adc_s.strip())
        elapsed_ms = int(elapsed_s.strip())
        dead_ms = int(dead_s.strip())
        temp_c = float(temp_s.strip())
        pres_hpa = float(pres_s.strip())
    except (ValueError, TypeError):
        return None

    return (
        line_str,
        event,
        event_count,
        adc,
        elapsed_ms,
        dead_ms,
        temp_c,
        pres_hpa,
        detector_name.strip(),
    )


def write_status_json(
    status_path: Path,
    last_event_time: datetime,
    event: str,
    temp_c: float,
    pres_hpa: float,
    detector_name: str,
    total_events_today: int,
) -> None:
    """Atomic write of data/status/current.json for web dashboard and monitoring."""
    status_dir = status_path.parent
    status_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = status_path.with_suffix(".tmp")
    payload = {
        "last_event_utc": last_event_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "last_event_type": event,
        "temperature_c": temp_c,
        "pressure_hpa": pres_hpa,
        "detector_name": detector_name,
        "total_events_today": total_events_today,
        "updated_at": utc_now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    try:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(status_path)
    except OSError as err:
        log_error(PROCESS_NAME, f"Failed writing status JSON: {err}")


def open_daily_file(base_path: Path, current_time: datetime, label: Optional[str]) -> Tuple[TextIO, Path]:
    target_path = build_raw_day_path(base_path, current_time, label)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(target_path, mode="a", encoding="utf-8", buffering=1)
    return handle, target_path


def open_rejected_file(base_path: Path, current_time: datetime) -> TextIO:
    rejected_dir = base_path / "data" / "raw" / "rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    rej_path = rejected_dir / f"{current_time.strftime('%Y-%m-%d')}.txt"
    return open(rej_path, mode="a", encoding="utf-8", buffering=1)


def main() -> None:
    base_path = get_base_path()
    usb_options = get_usb_options(base_path)
    serial_port = usb_options["serial_port"]
    label = usb_options["label"] or None

    log_message(PROCESS_NAME, f"Starting raw data collector on {serial_port}")

    status_path = base_path / "data" / "status" / "current.json"
    reconnect_delay = 2.0
    max_reconnect_delay = 30.0

    current_day: Optional[str] = None
    file_handle: Optional[TextIO] = None
    rejected_handle: Optional[TextIO] = None
    last_status_write = 0.0
    known_detector_name: Optional[str] = None
    events_today = 0

    while True:
        try:
            # Verify udev identity if configured in USB.ini
            try:
                verify_usb_identity(serial_port, usb_options)
            except RuntimeError as err:
                log_error(PROCESS_NAME, f"USB identity check failed: {err}")

            with serial.Serial(
                port=serial_port,
                baudrate=115200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=5.0,
            ) as ser:
                # Discard any incomplete line captured mid-stream on port open
                ser.reset_input_buffer()
                ser.readline()

                log_message(PROCESS_NAME, f"Connected to serial port {serial_port}")
                reconnect_delay = 2.0  # Reset backoff on successful connection

                while True:
                    raw_bytes = ser.readline()
                    if not raw_bytes:
                        continue

                    now = utc_now()
                    now_day_str = now.strftime("%Y-%m-%d")

                    # Handle midnight UTC rollover
                    if now_day_str != current_day:
                        if file_handle:
                            file_handle.close()
                        if rejected_handle:
                            rejected_handle.close()
                        file_handle, _ = open_daily_file(base_path, now, label)
                        rejected_handle = open_rejected_file(base_path, now)
                        current_day = now_day_str
                        events_today = 0
                        log_message(
                            PROCESS_NAME,
                            f"Rolled raw log to {now_day_str}.txt (label={label or 'single'})",
                        )

                    line_str = raw_bytes.decode("utf-8", "ignore").strip()
                    if not line_str:
                        continue

                    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")
                    validated = parse_and_validate_line(line_str)

                    if validated is None:
                        # Log and record malformed/rejected row
                        log_error(
                            PROCESS_NAME,
                            f"Malformed raw row rejected ({len(line_str)} chars): {line_str[:80]!r}",
                        )
                        if rejected_handle:
                            print(f"{timestamp_str},{line_str}", file=rejected_handle, flush=True)
                        continue

                    (
                        _,
                        event,
                        event_count,
                        adc,
                        elapsed_ms,
                        dead_ms,
                        temp_c,
                        pres_hpa,
                        det_name,
                    ) = validated

                    # Track detector name changes
                    if known_detector_name is None:
                        known_detector_name = det_name
                        log_message(PROCESS_NAME, f"Detector identified as '{det_name}'")
                    elif det_name != known_detector_name:
                        log_message(
                            PROCESS_NAME,
                            f"Detector name changed: '{known_detector_name}' -> '{det_name}'",
                        )
                        known_detector_name = det_name

                    # Write valid 9-field row: RPiTimestamp,Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp_C,Pres_hPa,DetectorName
                    # buffering=1 and flush() ensure data is written immediately
                    if file_handle:
                        print(f"{timestamp_str},{line_str}", file=file_handle, flush=True)
                        events_today += 1

                    # Update status JSON periodically (at most once every 5 seconds)
                    now_mono = time.monotonic()
                    if now_mono - last_status_write >= 5.0:
                        write_status_json(
                            status_path,
                            now,
                            event,
                            temp_c,
                            pres_hpa,
                            det_name,
                            events_today,
                        )
                        last_status_write = now_mono

        except (serial.SerialException, OSError) as exc:
            log_error(
                PROCESS_NAME,
                f"Serial connection error on {serial_port}: {exc}. Reconnecting in {reconnect_delay:.1f}s",
            )
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
        except Exception as unhandled:
            log_error(PROCESS_NAME, f"Unexpected error in collector loop: {unhandled}")
            time.sleep(reconnect_delay)


if __name__ == "__main__":
    main()
