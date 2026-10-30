"""CSV schemas and per-bin detector metadata shared by daily and period products."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from picomuon_common import log_message
from picomuon_metadata import SETTINGS_KEYS, Settings, data_lines, load_legacy_settings

DETECTOR_COLUMNS = ("detector_name", *SETTINGS_KEYS)
CPM_COLUMNS = ("DateTime", "Count_T", "Count_B", "Count_C", *DETECTOR_COLUMNS)
ADC_COLUMNS = ("ADC_Value", "Count_T", "Count_B", "Count_C", *DETECTOR_COLUMNS)
DAY_COLUMNS = (
    "DateTime", "CPM_T", "CPM_B", "CPM_C", "Mean_Temp", "Mean_Pres",
    *DETECTOR_COLUMNS, "neutrons", "station",
)
HOUR_COLUMNS = (
    "DateTime", "T", "B", "C", "live_seconds", "missing_events", "temp", "pres",
    *DETECTOR_COLUMNS, "neutrons", "station",
)


@dataclass
class BinMetadata:
    values: list[set[str]] = field(default_factory=lambda: [set() for _ in DETECTOR_COLUMNS])
    _last_columns: Optional[Tuple[str, ...]] = field(default=None, init=False, repr=False, compare=False)

    def add(self, values: Iterable[object]) -> None:
        self.add_columns(tuple(str(value) for value in values))

    def add_columns(self, items: Tuple[str, ...]) -> None:
        if len(items) != len(DETECTOR_COLUMNS):
            raise ValueError("Expected detector name and four settings")
        if items == self._last_columns:
            return
        for seen, value in zip(self.values, items):
            seen.add(value)
        self._last_columns = items

    def columns(self, fallback: Optional[BinMetadata] = None) -> Tuple[str, ...]:
        if not any(self.values) and fallback is not None:
            return fallback.columns()
        return tuple(
            next(iter(seen)) if len(seen) == 1 else ("mixed" if seen else "")
            for seen in self.values
        )


class HistoricalSettings:
    """Explicit user-authorised assumption, loaded only when source settings are absent."""

    def __init__(self, base: Path, label: Optional[str] = None):
        self.base = base
        self.label = label
        self.settings: Optional[Settings] = None
        self.assumed_rows = 0

    def resolve(self, settings: Optional[Settings]) -> Settings:
        if settings is not None:
            return settings
        if self.settings is None:
            self.settings = load_legacy_settings(self.base, self.label)
        self.assumed_rows += 1
        return self.settings

    def report(self, process: str) -> None:
        if self.assumed_rows:
            section = f"legacy:{self.label}" if self.label else "legacy"
            log_message(process, f"ASSUMPTION - used current [{section}] settings for "
                        f"{self.assumed_rows} historical rows without recorded settings")


def product_rows(path: Path) -> Iterable[Dict[str, str]]:
    """Read both headered CSV products and historical seven-column day files."""
    with path.open(encoding="utf-8", errors="replace") as source:
        reader = csv.reader(data_lines(source))
        columns = None
        for row in reader:
            if not row:
                continue
            if row[0] == "DateTime":
                columns = row
                continue
            names = columns or ("DateTime", "CPM_T", "CPM_B", "CPM_C", "Mean_Temp", "Mean_Pres", "Neutrons")
            if len(row) != len(names):
                raise ValueError(f"CSV row width does not match header in {path}: {len(row)} != {len(names)}")
            yield dict(zip(names, row))
