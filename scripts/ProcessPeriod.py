#!/usr/bin/env python3
"""Period data aggregator for UKRAA PicoMuon.

Builds multi-day products from daily products (data/day and data/daily/summary.csv):
1. Week (7 days): 1008 lines (10-minute bins) for PlotDataWeekACM0.gp
   Format: YYYY-MM-DD HH:MM:00,cpm_T,cpm_B,cpm_M,avg_temp,avg_pres,neutrons
2. Month (31 days): 744 lines (1-hour bins) for PlotDataMonthACM0.gp
   Format: YYYY-MM-DD HH:MM:00,cpm_T,cpm_B,cpm_M,avg_temp,avg_pres,neutrons
3. 3-Month (90 days): 90 lines (24-hour daily bins)
   Format: YYYY-MM-DD HH:MM:00,cpm_T,cpm_B,cpm_M,avg_temp,avg_pres,neutrons
4. 6-Month (183 days) and Year (365 days): daily bins from summary.csv

Applies completeness rules (as in UKRAA_PicoMagnetometer):
Requires >= period_min_valid_days_percent (default 90%) of days to be available.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import math
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple
from picomuon_metadata import SETTINGS_KEYS, csv_line
from picomuon_products import DAY_COLUMNS, BinMetadata, HistoricalSettings, product_rows
from picomuon_neutrons import DEFAULT_STATION
from picomuon_processing import processing_label, processing_lock

from picomuon_common import (
    build_processed_day_path,
    get_base_path,
    get_target_date,
    log_error,
    log_message,
)

SCRIPT_NAME = "ProcessPeriod.py"

PERIOD_CONFIGS = {
    "week": {"days": 7, "step_minutes": 10, "bin_count": 1008},
    "month": {"days": 31, "step_minutes": 60, "bin_count": 744},
    "3month": {"days": 90, "step_minutes": 1440, "bin_count": 90},
    "6month": {"days": 183, "step_minutes": 1440, "bin_count": 183},
    "year": {"days": 365, "step_minutes": 1440, "bin_count": 365},
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PicoMuon multi-day period aggregator.")
    parser.add_argument("--detector", help="Registered detector label (required in named mode)")
    parser.add_argument(
        "--target-date",
        "--date",
        dest="target_date",
        type=lambda d: datetime.strptime(d, "%Y-%m-%d").date(),
        default=None,
        help="UTC target date (end date) for period processing (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--period",
        choices=["all", "week", "month", "3month", "6month", "year"],
        default="all",
        help="Specific period to process (default: all)",
    )
    parser.add_argument(
        "--min-percent",
        type=float,
        default=90.0,
        help="Minimum percentage of valid days required (default: 90.0)",
    )
    return parser.parse_args()


DayRow = Tuple[datetime, float, float, float, float, float, float, Tuple[str, ...], str]


def load_day_file(
    day_file: Path, base_path: Optional[Path] = None, detector: Optional[str] = None,
) -> List[DayRow]:
    """Read new or historical day rows, retaining detector fields and NMDB station."""
    rows: List[DayRow] = []
    if not day_file.exists():
        return rows

    legacy = HistoricalSettings(base_path or get_base_path(), detector)
    assumed_station = False
    for row in product_rows(day_file):
        dt_val = datetime.strptime(row["DateTime"], "%Y-%m-%d %H:%M:%S")
        counts = tuple(float(row[key])
                       for key in ("CPM_T", "CPM_B", "CPM_C"))
        temp = float(row["Mean_Temp"])
        pres = float(row["Mean_Pres"])
        neutron_text = row.get("neutrons", row.get("Neutrons", "nan"))
        neutrons = float(neutron_text) if neutron_text != "nan" else 0.0
        settings = tuple(row.get(key, "") for key in SETTINGS_KEYS)
        if not any(settings):
            settings = tuple(str(value) for value in legacy.resolve(None))
        metadata = (row.get("detector_name", ""), *settings)
        station = row.get("station", DEFAULT_STATION)
        assumed_station = assumed_station or "station" not in row
        rows.append((dt_val, *counts, temp, pres, neutrons, metadata, station))
    source = f"{SCRIPT_NAME}[{detector}]" if detector else SCRIPT_NAME
    legacy.report(source)
    if assumed_station:
        log_message(source, f"ASSUMPTION - station OULU for historical day file without station column: {day_file}")
    return rows


def process_period_data(
    period_name: str,
    target_date: date,
    base_path: Optional[Path] = None,
    min_percent: float = 90.0,
    detector: Optional[str] = None,
) -> int:
    base = base_path or get_base_path()
    label = processing_label(base, detector)
    with processing_lock(base, label):
        return _process_period_data(period_name, target_date, base, min_percent, label)


def _process_period_data(
    period_name: str, target_date: date, base: Path, min_percent: float, label: Optional[str],
) -> int:
    product_label = label or "ACM0"
    source = f"{SCRIPT_NAME}[{label}]" if label else SCRIPT_NAME
    cfg = PERIOD_CONFIGS[period_name]
    num_days = cfg["days"]
    step_mins = cfg["step_minutes"]
    total_bins = cfg["bin_count"]

    start_date = target_date - timedelta(days=num_days - 1)
    date_str = target_date.strftime("%Y-%m-%d")
    start_str = start_date.strftime("%Y-%m-%d")

    log_message(
        source,
        f"Started {product_label} {period_name} data processing from {start_str} to {date_str}",
    )

    # Check available days in date range
    available_days = 0
    day_files: Dict[date, Path] = {}
    for d_offset in range(num_days):
        cur_date = start_date + timedelta(days=d_offset)
        df = build_processed_day_path(base, "day", cur_date, product_label, named_detector=label is not None)
        if df.exists():
            available_days += 1
            day_files[cur_date] = df

    min_required_days = math.ceil(num_days * (min_percent / 100.0) - 1e-9)
    if available_days < min_required_days:
        if label is not None:
            stale = build_processed_day_path(base, period_name, target_date, product_label, named_detector=True)
            if stale.exists():
                stale.unlink()
                log_message(source, f"Removed stale {period_name} product for {date_str}")
        log_message(
            source,
            f"Insufficient history; skipping {product_label} {period_name} data "
            f"({available_days}/{num_days} days, {min_required_days} needed "
            f"at {min_percent:.0f}%)",
        )
        return 0

    # Load 5-minute entries across the available days
    all_5min_rows: List[DayRow] = []
    for d_offset in range(num_days):
        cur_date = start_date + timedelta(days=d_offset)
        if cur_date in day_files:
            all_5min_rows.extend(load_day_file(day_files[cur_date], base, label))
    all_metadata = BinMetadata()
    for row in all_5min_rows:
        if any(value > 0 for value in row[1:4]):
            all_metadata.add(row[7])

    # Set up output path
    period_out = build_processed_day_path(base, period_name, target_date, product_label, named_detector=label is not None)
    period_out.parent.mkdir(parents=True, exist_ok=True)
    temp_out = period_out.with_suffix(".tmp")

    # Time boundaries
    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
    step_delta = timedelta(minutes=step_mins)

    # Index rows by their step bin
    # Number of 5-min intervals per step bin:
    intervals_per_step = step_mins // 5

    with temp_out.open(mode="w", encoding="utf-8") as out:
        out.write(csv_line(DAY_COLUMNS) + "\n")
        cur_bin_time = start_dt
        row_idx = 0
        num_rows = len(all_5min_rows)

        for b in range(total_bins):
            bin_end_time = cur_bin_time + step_delta

            cnt_T = 0.0
            cnt_B = 0.0
            cnt_M = 0.0
            temp_sum = 0.0
            pres_sum = 0.0
            neutrons_sum = 0.0
            temp_count = 0
            pres_count = 0
            metadata = BinMetadata()
            stations = set()
            observed = [False, False, False]

            # Advance rows within [cur_bin_time, bin_end_time)
            while row_idx < num_rows and all_5min_rows[row_idx][0] < bin_end_time:
                r_dt, r_T, r_B, r_M, r_temp, r_pres, r_neut, r_metadata, r_station = all_5min_rows[row_idx]
                if r_dt >= cur_bin_time:
                    if any(value > 0 for value in (r_T, r_B, r_M)):
                        metadata.add(r_metadata)
                    if r_station:
                        stations.add(r_station)
                    for index, value in enumerate((r_T, r_B, r_M)):
                        observed[index] = observed[index] or not math.isnan(value)
                    cnt_T += r_T if not math.isnan(r_T) else 0.0
                    cnt_B += r_B if not math.isnan(r_B) else 0.0
                    cnt_M += r_M if not math.isnan(r_M) else 0.0
                    neutrons_sum += r_neut
                    if not math.isnan(r_temp):
                        temp_sum += r_temp
                        temp_count += 1
                    if not math.isnan(r_pres):
                        pres_sum += r_pres
                        pres_count += 1
                row_idx += 1

            # Format outputs matching legacy formatting
            c_T = f"{cnt_T:.0f}" if observed[0] else "nan"
            c_B = f"{cnt_B:.0f}" if observed[1] else "nan"
            c_M = f"{cnt_M:.0f}" if observed[2] else "nan"

            # Temperature and pressure averages:
            # Legacy divides by intervals_per_step if total counts > 0
            tot_counts = cnt_T + cnt_B + cnt_M
            if tot_counts > 0.0:
                avg_t = f"{temp_sum / intervals_per_step:.1f}" if temp_count > 0 else "nan"
                avg_p = f"{pres_sum / intervals_per_step:.1f}" if pres_count > 0 else "nan"
            else:
                avg_t = "nan"
                avg_p = "nan"

            # Neutron threshold: count_N > (400.0 * intervals_per_step)
            if neutrons_sum > (400.0 * intervals_per_step):
                c_N = f"{neutrons_sum:.3f}"
            else:
                c_N = "nan"

            ts_str = cur_bin_time.strftime("%Y-%m-%d %H:%M:%S")
            station = next(iter(stations)) if len(stations) == 1 else ("mixed" if stations else "")
            out.write(csv_line([ts_str, c_T, c_B, c_M, avg_t, avg_p,
                                *metadata.columns(all_metadata), c_N, station]) + "\n")

            cur_bin_time = bin_end_time

    temp_out.replace(period_out)

    log_message(
        source,
        f"Completed {product_label} {period_name} data processing from {start_str} to {date_str}",
    )
    return 0


def main() -> None:
    args = parse_arguments()
    target = args.target_date or get_target_date()
    periods_to_run = (
        ["week", "month", "3month"]
        if args.period == "all"
        else [args.period]
    )

    failures = 0
    for p in periods_to_run:
        try:
            res = process_period_data(p, target, min_percent=args.min_percent, detector=args.detector)
        except (OSError, ValueError, RuntimeError) as error:
            log_error(SCRIPT_NAME, f"FAILED [{args.detector or 'single'}] - {error}")
            sys.exit(1)
        if res != 0:
            failures += 1

    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
