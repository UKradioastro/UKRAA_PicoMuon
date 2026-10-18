"""Neutron file attribution, column headers and historical-file compatibility."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, TextIO, Tuple

from picomuon_common import log_message

NEUTRON_COLUMNS = (
    "DateTime", "Pressure_hPa", "Uncorrected", "PressureCorrected", "EfficiencyCorrected",
)
DEFAULT_STATION = "OULU"


def write_neutron_header(handle: TextIO, station: str, request: str) -> None:
    if any(char in station + request for char in "\r\n"):
        raise ValueError("Station and request must be single lines")
    handle.write("# Neutron monitor data from NMDB (Neutron Monitor Database)\n")
    handle.write("# https://www.nmdb.eu/ ; station information: https://www.nmdb.eu/station/\n")
    handle.write(f"# Station: {station.upper()}\n")
    handle.write("# Time basis: UTC; efficiency-corrected values used for processed neutron totals\n")
    handle.write(f"# Request: {request}\n")
    csv.writer(handle, lineterminator="\n").writerow(NEUTRON_COLUMNS)


def neutron_rows(path: Path) -> Iterable[Tuple[list[str], str]]:
    station = ""
    with path.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            if line.startswith("# Station:"):
                station = line.partition(":")[2].strip().upper()
                continue
            if line.startswith("#") or not line.strip():
                continue
            row = next(csv.reader([line]))
            if row[0] in ("DateTime", "start_date_time"):
                continue
            if len(row) != 5:
                raise ValueError(f"Expected five neutron columns in {path}: {row!r}")
            datetime.strptime(row[0].strip(), "%Y-%m-%d %H:%M:%S")
            if not station:
                station = DEFAULT_STATION
                log_message("Neutron data", f"ASSUMPTION - station OULU for historical file without station header: {path}")
            yield row, station


def load_neutrons(path: Path) -> Tuple[Dict[str, float], str]:
    counts: Dict[str, float] = {}
    stations = set()
    if not path.exists():
        return counts, ""
    for row, station in neutron_rows(path):
        counts[row[0][11:16]] = float(row[4])
        stations.add(station)
    return counts, (next(iter(stations)) if len(stations) == 1 else ("mixed" if stations else ""))
