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

from picomuon_common import (
    build_daily_summary_path,
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


def load_day_file(day_file: Path) -> List[Tuple[datetime, float, float, float, float, float, float]]:
    """Read a 288-row 5-minute day file.
    Returns list of (dt, cnt_T, cnt_B, cnt_C, temp, pres, neutrons).
    """
    rows: List[Tuple[datetime, float, float, float, float, float, float]] = []
    if not day_file.exists():
        return rows

    with day_file.open(mode="r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 7:
                continue
            try:
                dt_val = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
                c_T = float(parts[1]) if parts[1] != "nan" else 0.0
                c_B = float(parts[2]) if parts[2] != "nan" else 0.0
                c_C = float(parts[3]) if parts[3] != "nan" else 0.0
                temp = float(parts[4]) if parts[4] != "nan" else math.nan
                pres = float(parts[5]) if parts[5] != "nan" else math.nan
                neutrons = float(parts[6]) if parts[6] != "nan" else 0.0
                rows.append((dt_val, c_T, c_B, c_C, temp, pres, neutrons))
            except (ValueError, IndexError):
                continue
    return rows


def process_period_data(
    period_name: str,
    target_date: date,
    base_path: Optional[Path] = None,
    min_percent: float = 90.0,
) -> int:
    base = base_path or get_base_path()
    cfg = PERIOD_CONFIGS[period_name]
    num_days = cfg["days"]
    step_mins = cfg["step_minutes"]
    total_bins = cfg["bin_count"]

    start_date = target_date - timedelta(days=num_days - 1)
    date_str = target_date.strftime("%Y-%m-%d")
    start_str = start_date.strftime("%Y-%m-%d")

    log_message(
        SCRIPT_NAME,
        f"Started ACM0 {period_name} data processing from {start_str} to {date_str}",
    )

    # Check available days in date range
    available_days = 0
    day_files: Dict[date, Path] = {}
    for d_offset in range(num_days):
        cur_date = start_date + timedelta(days=d_offset)
        df = build_processed_day_path(base, "day", cur_date, "ACM0", "txt")
        if df.exists():
            available_days += 1
            day_files[cur_date] = df

    min_required_days = math.ceil(num_days * (min_percent / 100.0) - 1e-9)
    if available_days < min_required_days:
        log_message(
            SCRIPT_NAME,
            f"Insufficient history; skipping ACM0 {period_name} data "
            f"({available_days}/{num_days} days, {min_required_days} needed "
            f"at {min_percent:.0f}%)",
        )
        return 0

    # Load 5-minute entries across the available days
    all_5min_rows: List[Tuple[datetime, float, float, float, float, float, float]] = []
    for d_offset in range(num_days):
        cur_date = start_date + timedelta(days=d_offset)
        if cur_date in day_files:
            all_5min_rows.extend(load_day_file(day_files[cur_date]))

    # Set up output path
    period_out = build_processed_day_path(base, period_name, target_date, "ACM0", "txt")
    period_out.parent.mkdir(parents=True, exist_ok=True)
    temp_out = period_out.with_suffix(".tmp")

    # Time boundaries
    start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
    step_delta = timedelta(minutes=step_mins)

    # Index rows by their step bin
    # Number of 5-min intervals per step bin:
    intervals_per_step = step_mins // 5

    with temp_out.open(mode="w", encoding="utf-8") as out:
        out.write("DateTime,CPM_T,CPM_B,CPM_C,Mean_Temp,Mean_Pres,Neutrons\n")
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

            # Advance rows within [cur_bin_time, bin_end_time)
            while row_idx < num_rows and all_5min_rows[row_idx][0] < bin_end_time:
                r_dt, r_T, r_B, r_M, r_temp, r_pres, r_neut = all_5min_rows[row_idx]
                if r_dt >= cur_bin_time:
                    cnt_T += r_T
                    cnt_B += r_B
                    cnt_M += r_M
                    neutrons_sum += r_neut
                    if not math.isnan(r_temp):
                        temp_sum += r_temp
                        temp_count += 1
                    if not math.isnan(r_pres):
                        pres_sum += r_pres
                        pres_count += 1
                row_idx += 1

            # Format outputs matching legacy formatting
            c_T = f"{cnt_T:.0f}" if cnt_T > 0.0 else "nan"
            c_B = f"{cnt_B:.0f}" if cnt_B > 0.0 else "nan"
            c_M = f"{cnt_M:.0f}" if cnt_M > 0.0 else "nan"

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
            out.write(f"{ts_str},{c_T},{c_B},{c_M},{avg_t},{avg_p},{c_N}\n")

            cur_bin_time = bin_end_time

    temp_out.replace(period_out)

    log_message(
        SCRIPT_NAME,
        f"Completed ACM0 {period_name} data processing from {start_str} to {date_str}",
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
        res = process_period_data(p, target, min_percent=args.min_percent)
        if res != 0:
            failures += 1

    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
