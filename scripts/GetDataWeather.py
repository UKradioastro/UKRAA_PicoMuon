#!/usr/bin/env python3
"""Download modelled hourly 2 m air temperature for CPM plot overlays."""

from __future__ import annotations

import argparse
import configparser
from datetime import date, timedelta
import json
import math
from pathlib import Path
from typing import Any, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from picomuon_common import get_base_path, get_target_date, log_error, log_message, utc_now

SCRIPT_NAME = "GetDataWeather.py"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_API = "https://historical-forecast-api.open-meteo.com/v1/forecast"


def load_coordinates(base: Path) -> Optional[tuple[float, float]]:
    path = base / "config" / "user.ini"
    if not path.exists():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    with path.open(encoding="utf-8-sig") as source:
        parser.read_file(source)
    if not parser.getboolean("weather", "enabled", fallback=False):
        return None
    latitude = parser.getfloat("Observatory", "observatory_latitude")
    longitude = parser.getfloat("Observatory", "observatory_longitude")
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError(f"Invalid latitude in {path}: {latitude}")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError(f"Invalid longitude in {path}: {longitude}")
    return latitude, longitude


def build_weather_path(base: Path, target: date) -> Path:
    return base / "data" / "weather" / f"{target:%Y}" / f"{target:%Y-%m}" / f"{target}.txt"


def build_weather_url(target: date, latitude: float, longitude: float, today: date) -> str:
    endpoint = FORECAST_API if target >= today - timedelta(days=5) else HISTORICAL_API
    return endpoint + "?" + urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m",
        "temperature_unit": "celsius",
        "timezone": "GMT",
        "start_date": target.isoformat(),
        "end_date": target.isoformat(),
    })


def parse_hourly(payload: Any, target: date) -> list[tuple[str, Optional[float]]]:
    if not isinstance(payload, dict):
        raise ValueError("Open-Meteo response must be an object")
    if payload.get("error"):
        raise ValueError(f"Open-Meteo error: {payload.get('reason', 'unspecified')}")
    units = payload.get("hourly_units")
    if not isinstance(units, dict) or units.get("temperature_2m") != "\N{DEGREE SIGN}C":
        raise ValueError("Open-Meteo response must contain Celsius temperatures")
    if payload.get("utc_offset_seconds") != 0:
        raise ValueError("Open-Meteo response must use UTC")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("Open-Meteo response is missing hourly data")
    times = hourly.get("time")
    values = hourly.get("temperature_2m")
    expected = [f"{target}T{hour:02d}:00" for hour in range(24)]
    if times != expected or not isinstance(values, list) or len(values) != 24:
        raise ValueError(f"Expected exactly 24 ordered hourly UTC values for {target}")
    rows: list[tuple[str, Optional[float]]] = []
    for timestamp, value in zip(times, values):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"Invalid temperature at {timestamp}: {value!r}")
        rows.append((timestamp.replace("T", " ") + ":00", value))
    if all(value is None for _, value in rows):
        raise ValueError(f"No valid Open-Meteo temperatures for {target}")
    return rows


def download_weather(base: Path, target: date) -> Optional[Path]:
    coordinates = load_coordinates(base)
    if coordinates is None:
        log_message(SCRIPT_NAME, "Skipped weather download: not enabled in config/user.ini")
        return None
    today = utc_now().date()
    if target >= today:
        raise ValueError("Weather overlays require a completed UTC day")
    latitude, longitude = coordinates
    url = build_weather_url(target, latitude, longitude, today)
    log_message(SCRIPT_NAME, f"Started 2 m air-temperature download for {target} ({latitude}, {longitude})")
    with urlopen(url, timeout=30) as response:
        payload = json.load(response)
    rows = parse_hourly(payload, target)
    output = build_weather_path(base, target)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("# Weather data by Open-Meteo.com; CC BY 4.0; modelled 2 m air temperature\n")
            handle.write("# https://open-meteo.com/ ; https://creativecommons.org/licenses/by/4.0/\n")
            handle.write("# Request: " + url + "\n")
            handle.write("DateTime,Temperature_2m_C\n")
            for timestamp, value in rows:
                handle.write(f"{timestamp},{'nan' if value is None else str(value)}\n")
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    valid = sum(value is not None for _, value in rows)
    log_message(SCRIPT_NAME, f"Completed weather download for {target} ({valid}/24 hours; missing values remain gaps)")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", "--target-date", dest="target_date", type=date.fromisoformat)
    args = parser.parse_args()
    try:
        download_weather(get_base_path(), args.target_date or get_target_date())
    except (OSError, URLError, ValueError, configparser.Error) as exc:
        log_error(SCRIPT_NAME, f"ERROR: weather download failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
