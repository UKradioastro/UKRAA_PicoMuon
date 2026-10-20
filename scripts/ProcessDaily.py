#!/usr/bin/env python3
"""Single-pass daily processor for UKRAA PicoMuon.

Reads yesterday's L0 raw file exactly once and generates:
1. Minute CPM (1440 rows): utc,cpm_T,cpm_B,cpm_C
2. 5-minute Day (288 rows): utc,cpm_T,cpm_B,cpm_M,avg_temp,avg_pres,neutrons
3. ADC spectrum (1024 bins): adc_bin,count_T,count_B,count_C
4. Hourly summary (24 rows): utc,T,B,C,live_s,missing_events,temp,pres,neutrons
5. Appends to data/daily/summary.csv for multi-day period analysis and health checks.

Backward compatibility:
Writes processed products to data/cpm/ACM0, data/day/ACM0, and data/adc/ACM0.
Named mode requires --detector LABEL and isolates all products under that label.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
import math
from pathlib import Path
import sys
from typing import Dict, Optional
from picomuon_metadata import csv_line, split_payload
from picomuon_products import (
    ADC_COLUMNS, CPM_COLUMNS, DAY_COLUMNS, HOUR_COLUMNS, BinMetadata, HistoricalSettings,
)
from picomuon_neutrons import load_neutrons
from picomuon_processing import processing_label, processing_lock, raw_roots

from picomuon_common import (
    build_daily_summary_path,
    build_neutron_path,
    build_processed_day_path,
    raw_data_lines,
    get_base_path,
    get_target_date,
    log_error,
    log_message,
)

SCRIPT_NAME = "ProcessDaily.py"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-pass PicoMuon daily processor.")
    parser.add_argument("--detector", help="Registered detector label (required in named mode)")
    parser.add_argument(
        "--target-date",
        "--date",
        dest="target_date",
        type=lambda d: datetime.strptime(d, "%Y-%m-%d").date(),
        default=None,
        help="UTC target date to process (YYYY-MM-DD, defaults to PICOMUON_TARGET_DATE or yesterday)",
    )
    return parser.parse_args()


def load_neutron_data(neutron_file: Path) -> Dict[str, float]:
    """Compatibility helper for callers needing only neutron counts."""
    return load_neutrons(neutron_file)[0]


def find_raw_file(base_path: Path, target_date: date, label: Optional[str]) -> Optional[Path]:
    """Named mode never falls back to unlabelled or legacy input."""
    for root in raw_roots(base_path, label):
        candidate = root / target_date.strftime("%Y") / target_date.strftime("%Y-%m") / f"{target_date:%Y-%m-%d}.txt"
        if candidate.is_file():
            return candidate
    return None


def process_daily(
    target_date: date, base_path: Optional[Path] = None, detector: Optional[str] = None,
) -> int:
    base = base_path or get_base_path()
    label = processing_label(base, detector)
    with processing_lock(base, label):
        return _process_daily(target_date, base, label)


def _process_daily(target_date: date, base: Path, detector_label: Optional[str]) -> int:
    date_str = target_date.strftime("%Y-%m-%d")
    source = f"{SCRIPT_NAME}[{detector_label}]" if detector_label else SCRIPT_NAME
    product_label = detector_label or "ACM0"

    log_message(source, f"Started fast daily data processing for {date_str}")

    raw_file = find_raw_file(base, target_date, detector_label)
    if raw_file is None or not raw_file.exists():
        log_error(source, f"Raw data file missing for {date_str}")
        return 1

    # Load neutron data for the day
    neutron_file = build_neutron_path(base, target_date)
    neutron_by_minute, neutron_station = load_neutrons(neutron_file)

    # 1. 1440 1-minute bins: count_T, count_B, count_C
    cpm_bins = [[0, 0, 0] for _ in range(1440)]

    # 2. 288 5-minute bins: count_T, count_B, count_C, sum_temp, sum_pres
    day_bins = [[0, 0, 0, 0.0, 0.0] for _ in range(288)]

    # 3. 1024 ADC bins: count_T, count_B, count_C
    adc_bins = [[0, 0, 0] for _ in range(1024)]

    # 4. 24 hourly bins: count_T, count_B, count_C, live_ms, missing_events, sum_temp, sum_pres
    hour_bins = [[0, 0, 0, 0, 0, 0.0, 0.0] for _ in range(24)]

    # Tracking run segments, elapsed wrap, missing events
    total_events = 0
    detector_name = ""
    event_counts: Dict[str, int] = {}
    prev_elapsed_ms: Optional[int] = None
    prev_time: Optional[datetime] = None
    prev_det_name: Optional[str] = None
    legacy = HistoricalSettings(base, detector_label)
    all_metadata = BinMetadata()
    minute_metadata = [BinMetadata() for _ in cpm_bins]
    day_metadata = [BinMetadata() for _ in day_bins]
    adc_metadata = [BinMetadata() for _ in adc_bins]
    hour_metadata = [BinMetadata() for _ in hour_bins]

    with raw_file.open(mode="r", encoding="utf-8", errors="replace") as rf:
        for line in raw_data_lines(rf):
            line = line.strip()
            if not line:
                continue

            parts = [part.strip() for part in next(csv.reader([line]))]
            if len(parts) < 8:
                continue
            settings = None
            if len(parts) >= 9:
                try:
                    payload, settings = split_payload(line.split(",", 1)[1])
                except (ValueError, csv.Error) as exc:
                    log_error(source, f"Invalid raw metadata in {raw_file}: {exc}")
                    continue
                parts = [parts[0], *payload]

            # Parse datetime: YYYY-MM-DD HH:MM:SS.ffffff
            dt_str = parts[0]
            try:
                dt_val = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    dt_val = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue

            # Ensure event belongs to the target UTC date
            if dt_val.date() != target_date:
                continue

            pos = parts[1]
            if pos not in ("T", "B", "C"):
                continue

            try:
                event_count = int(parts[2])
                adc_val = int(parts[3])
                elapsed_ms = int(parts[4])
                temp_val = float(parts[6])
                pres_val = float(parts[7])
            except (ValueError, IndexError):
                continue

            det_name = parts[8] if len(parts) >= 9 else ""
            if det_name and not detector_name:
                detector_name = det_name
            metadata = (det_name, *legacy.resolve(settings))
            all_metadata.add(metadata)

            total_events += 1
            pos_idx = 0 if pos == "T" else (1 if pos == "B" else 2)

            min_idx = dt_val.hour * 60 + dt_val.minute
            day_idx = min_idx // 5
            hour_idx = dt_val.hour
            minute_metadata[min_idx].add(metadata)
            day_metadata[day_idx].add(metadata)
            hour_metadata[hour_idx].add(metadata)

            # Bins accumulation
            cpm_bins[min_idx][pos_idx] += 1

            day_bins[day_idx][pos_idx] += 1
            day_bins[day_idx][3] += temp_val
            day_bins[day_idx][4] += pres_val

            if 0 <= adc_val < 1024:
                adc_bins[adc_val][pos_idx] += 1
                adc_metadata[adc_val].add(metadata)

            hour_bins[hour_idx][pos_idx] += 1
            hour_bins[hour_idx][5] += temp_val
            hour_bins[hour_idx][6] += pres_val

            # EventCount is per T/B/C; Elapsed_ms is shared by the whole detector.
            previous_count = event_counts.get(pos)
            if prev_elapsed_ms is not None and prev_time is not None:
                delta_ms = (elapsed_ms - prev_elapsed_ms) % (2**32)
                wall_seconds = (dt_val - prev_time).total_seconds()
                reason = None
                if det_name and prev_det_name and det_name != prev_det_name:
                    reason = "detector name changed"
                elif previous_count is not None and event_count < previous_count:
                    reason = f"{pos} counter reset"
                elif delta_ms >= 3600000 or wall_seconds >= 3600:
                    reason = "elapsed clock reset or gap of at least one hour"
                elif wall_seconds < 0:
                    reason = "UTC timestamp moved backwards"

                if reason is not None:
                    event_counts.clear()
                    log_message(source, f"Started new accounting segment at {dt_val}: {reason}")
                else:
                    if previous_count is not None:
                        hour_bins[hour_idx][4] += max(0, event_count - previous_count - 1)
                    # Apportion shared elapsed time over the UTC interval, not
                    # entirely to the hour containing its final event.
                    if prev_time.hour == hour_idx:
                        hour_bins[hour_idx][3] += delta_ms
                    else:
                        interval_start = prev_time
                        while interval_start < dt_val:
                            next_hour = interval_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                            interval_end = min(next_hour, dt_val)
                            fraction = (interval_end - interval_start).total_seconds() / wall_seconds
                            hour_bins[interval_start.hour][3] += delta_ms * fraction
                            interval_start = interval_end

            event_counts[pos] = event_count
            prev_elapsed_ms = elapsed_ms
            prev_time = dt_val
            prev_det_name = det_name

    legacy.report(source)
    # Output 1: Minute CPM file (1440 lines)
    # Compatible format: YYYY-MM-DD HH:MM:00,cpm_T,cpm_B,cpm_M
    cpm_out = build_processed_day_path(base, "cpm", target_date, product_label, named_detector=detector_label is not None)
    cpm_out.parent.mkdir(parents=True, exist_ok=True)
    temp_cpm = cpm_out.with_suffix(".tmp")

    with temp_cpm.open(mode="w", encoding="utf-8") as out:
        out.write(csv_line(CPM_COLUMNS) + "\n")
        for m in range(1440):
            hh = m // 60
            mm = m % 60
            ts_str = f"{date_str} {hh:02d}:{mm:02d}:00"
            cnt_T, cnt_B, cnt_C = cpm_bins[m]
            out.write(csv_line([ts_str, cnt_T, cnt_B, cnt_C,
                                *minute_metadata[m].columns(all_metadata)]) + "\n")
    temp_cpm.replace(cpm_out)

    # Output 2: 5-minute Day file (288 lines)
    # Compatible format: YYYY-MM-DD HH:MM:00,cpm_T,cpm_B,cpm_M,avg_temp,avg_pres,neutrons
    day_out = build_processed_day_path(base, "day", target_date, product_label, named_detector=detector_label is not None)
    day_out.parent.mkdir(parents=True, exist_ok=True)
    temp_day = day_out.with_suffix(".tmp")

    with temp_day.open(mode="w", encoding="utf-8") as out:
        out.write(csv_line(DAY_COLUMNS) + "\n")
        for b in range(288):
            min_start = b * 5
            hh = min_start // 60
            mm = min_start % 60
            ts_str = f"{date_str} {hh:02d}:{mm:02d}:00"
            cnt_T, cnt_B, cnt_C, sum_t, sum_p = day_bins[b]
            tot_counts = cnt_T + cnt_B + cnt_C

            c_T = str(cnt_T) if cnt_T > 0 else "nan"
            c_B = str(cnt_B) if cnt_B > 0 else "nan"
            c_C = str(cnt_C) if cnt_C > 0 else "nan"
            avg_t = f"{sum_t / tot_counts:.1f}" if tot_counts > 0 else "nan"
            avg_p = f"{sum_p / tot_counts:.1f}" if tot_counts > 0 else "nan"

            # Sum 5 minutes of neutrons for this 5-min bin
            neutron_sum = 0.0
            neutron_count = 0
            for min_offset in range(5):
                m_total = min_start + min_offset
                m_hh = m_total // 60
                m_mm = m_total % 60
                key = f"{m_hh:02d}:{m_mm:02d}"
                if key in neutron_by_minute:
                    neutron_sum += neutron_by_minute[key]
                    neutron_count += 1

            # Legacy threshold: count_N > 400
            c_N = f"{neutron_sum:.3f}" if (neutron_count > 0 and neutron_sum > 400.0) else "nan"

            out.write(csv_line([ts_str, c_T, c_B, c_C, avg_t, avg_p,
                                *day_metadata[b].columns(all_metadata), c_N, neutron_station]) + "\n")
    temp_day.replace(day_out)

    # Output 3: ADC distribution (1024 lines)
    # Compatible format: adc_val,count_T,count_B,count_M
    adc_out = build_processed_day_path(base, "adc", target_date, product_label, named_detector=detector_label is not None)
    adc_out.parent.mkdir(parents=True, exist_ok=True)
    temp_adc = adc_out.with_suffix(".tmp")

    with temp_adc.open(mode="w", encoding="utf-8") as out:
        out.write(csv_line(ADC_COLUMNS) + "\n")
        for adc_val in range(1024):
            cnt_T, cnt_B, cnt_C = adc_bins[adc_val]
            out.write(csv_line([adc_val, cnt_T, cnt_B, cnt_C,
                                *adc_metadata[adc_val].columns(all_metadata)]) + "\n")
    temp_adc.replace(adc_out)

    # Output 4: Hourly L2 file (24 lines)
    # Path: data/hour/YYYY/YYYY-MM/YYYY-MM-DD.csv
    # Fields: DateTime,T,B,C,live_seconds,missing_events,temp,pres,neutrons
    hour_out = build_processed_day_path(base, "hour", target_date, detector_label or "", "csv", named_detector=detector_label is not None)
    hour_dir = hour_out.parent
    hour_dir.mkdir(parents=True, exist_ok=True)
    temp_hour = hour_out.with_suffix(".tmp")

    total_live_ms = 0
    total_missing = 0
    valid_hours = 0

    with temp_hour.open(mode="w", encoding="utf-8") as out:
        out.write(csv_line(HOUR_COLUMNS) + "\n")
        for h in range(24):
            ts_str = f"{date_str} {h:02d}:00:00"
            cnt_T, cnt_B, cnt_C, live_ms, missing, sum_t, sum_p = hour_bins[h]
            tot_cnt = cnt_T + cnt_B + cnt_C
            total_live_ms += live_ms
            total_missing += missing
            if tot_cnt > 0:
                valid_hours += 1

            live_sec = live_ms / 1000.0
            avg_t = f"{sum_t / tot_cnt:.2f}" if tot_cnt > 0 else "nan"
            avg_p = f"{sum_p / tot_cnt:.2f}" if tot_cnt > 0 else "nan"

            # Hourly neutron sum
            neutron_h_sum = 0.0
            neutron_h_count = 0
            for mm in range(60):
                key = f"{h:02d}:{mm:02d}"
                if key in neutron_by_minute:
                    neutron_h_sum += neutron_by_minute[key]
                    neutron_h_count += 1
            n_str = f"{neutron_h_sum:.3f}" if neutron_h_count > 0 else "nan"

            out.write(csv_line([ts_str, cnt_T, cnt_B, cnt_C, f"{live_sec:.1f}", missing,
                                avg_t, avg_p, *hour_metadata[h].columns(all_metadata),
                                n_str, neutron_station]) + "\n")
    temp_hour.replace(hour_out)

    # Output 5: Update/Append data/daily/summary.csv
    summary_path = build_daily_summary_path(base, detector_label)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    day_cnt_T = sum(b[0] for b in hour_bins)
    day_cnt_B = sum(b[1] for b in hour_bins)
    day_cnt_C = sum(b[2] for b in hour_bins)
    tot_day_cnt = day_cnt_T + day_cnt_B + day_cnt_C
    tot_t_sum = sum(b[5] for b in hour_bins)
    tot_p_sum = sum(b[6] for b in hour_bins)
    mean_temp = f"{tot_t_sum / tot_day_cnt:.2f}" if tot_day_cnt > 0 else "nan"
    mean_pres = f"{tot_p_sum / tot_day_cnt:.2f}" if tot_day_cnt > 0 else "nan"
    coverage_pct = (valid_hours / 24.0) * 100.0

    summary_rows: Dict[str, str] = {}
    if summary_path.exists():
        with summary_path.open(mode="r", encoding="utf-8", errors="replace") as sf:
            for line in sf:
                if line.startswith("#"):
                    continue
                line = line.strip()
                if line and not line.startswith("DateTime,"):
                    key = next(csv.reader([line]))[0]
                    summary_rows[key] = line

    new_row = csv_line([
        f"{date_str} 00:00:00", day_cnt_T, day_cnt_B, day_cnt_C, mean_temp,
        mean_pres, valid_hours, f"{coverage_pct:.1f}", total_missing, detector_name,
    ])
    summary_rows[f"{date_str} 00:00:00"] = new_row

    temp_summary = summary_path.with_suffix(".tmp")
    with temp_summary.open(mode="w", encoding="utf-8") as sf:
        sf.write("DateTime,Count_T,Count_B,Count_C,Mean_Temp,Mean_Pres,ValidHours,CoveragePercent,MissingEvents,DetectorName\n")
        for key in sorted(summary_rows.keys()):
            sf.write(f"{summary_rows[key]}\n")
    temp_summary.replace(summary_path)

    log_message(
        source,
        f"Completed daily data processing for {date_str} ({total_events} events, "
        f"{valid_hours}/24 hours, missing_events={total_missing})",
    )
    return 0


def main() -> None:
    args = parse_arguments()
    target = args.target_date or get_target_date()
    try:
        result = process_daily(target, detector=args.detector)
    except (OSError, ValueError, RuntimeError) as error:
        log_error(SCRIPT_NAME, f"FAILED [{args.detector or 'single'}] - {error}")
        result = 1
    sys.exit(result)


if __name__ == "__main__":
    main()
