#!/usr/bin/env python3
"""Opt-in named-detector daily/plot pipeline; no service or cron installation."""

from __future__ import annotations

import argparse
import configparser
import getpass
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

from ProcessDaily import process_daily
from ProcessPeriod import process_period_data
from picomuon_common import get_base_path, get_target_date, log_error, log_message, utc_now
from picomuon_detectors import get_detectors
from picomuon_processing import processing_label, processing_lock
from picomuon_web import publish_detector, publish_index

PLOTS = (
    "PlotDataCpmACM0.gp", "PlotDataFreqACM0.gp", "PlotDataAdcACM0.gp",
    "PlotDataDayACM0.gp", "PlotDataWeekACM0.gp", "PlotDataMonthACM0.gp",
)


def run_shell_stage(base: Path, target: date, label: Optional[str], arguments: list[str], *, plot: bool = False) -> int:
    logs = base / "logfiles"
    if label is not None:
        logs = logs / "detectors" / label
    logs.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment.update(
        PICOMUON_BASE_PATH=str(base), PICOMUON_TARGET_DATE=str(target), TERM="dumb", TZ="UTC",
        MAIN_LOG=str(logs / "log-PicoMuon.txt"), ERROR_LOG=str(logs / "log-error.txt"),
        PYTHON=sys.executable, GNUPLOT=environment.get("PICOMUON_GNUPLOT", "/usr/bin/gnuplot"),
        PICOMUON_FILE_OWNER=getpass.getuser(),
    )
    if plot:
        command = (
            'source "$PICOMUON_BASE_PATH/scripts/logging.sh"; '
            'run_logged_plot "$1" "$PICOMUON_TARGET_DATE" "$2"'
        )
        argv = [arguments[0], label or ""]
    else:
        command = (
            'source "$PICOMUON_BASE_PATH/scripts/logging.sh"; '
            'run_logged_command "$1" "${@:2}"'
        )
        argv = [Path(arguments[1]).name, *arguments]
    result = subprocess.run(["bash", "-c", command, "picomuon-stage", *argv], env=environment, cwd=base)
    return result.returncode


def run_pipeline(
    base: Path, target: date, detector: Optional[str] = None, *,
    skip_downloads: bool = False, plots_only: bool = False, web_root: Optional[Path] = None,
) -> int:
    configured = get_detectors(base)
    if not configured:
        raise ValueError("No named detectors configured; use the existing single-detector entry points")
    labels = [processing_label(base, detector)] if detector is not None else list(configured)
    if target >= utc_now().date():
        raise ValueError("The named daily pipeline requires a completed UTC day")
    if web_root is not None and not web_root.is_dir():
        raise ValueError(f"External web root must already exist: {web_root}")
    logs = base / "logfiles"
    logs.mkdir(parents=True, exist_ok=True)
    failures = 0
    if not skip_downloads:
        # Shared site inputs are fetched once, not once per configured detector.
        with processing_lock(base, None, pipeline=True):
            for script in ("GetDataNeutron.py", "GetDataWeather.py"):
                if run_shell_stage(base, target, None, [sys.executable, str(base / "scripts" / script)]):
                    log_error("ProcessDetectors.py", f"FAILED - shared {script}; continuing detector processing")
                    failures += 1
    roots = [base / "WWW"]
    if web_root is not None and web_root.resolve() != roots[0].resolve():
        roots.append(web_root)
    for label in labels:
        if label is None:
            raise ValueError("A named detector label is required")
        unit_logs = logs / "detectors" / label
        unit_logs.mkdir(parents=True, exist_ok=True)
        with (unit_logs / "log-PicoMuon.txt").open("a", encoding="utf-8") as output, \
                (unit_logs / "log-error.txt").open("a", encoding="utf-8") as errors, \
                redirect_stdout(output), redirect_stderr(errors):
            try:
                with processing_lock(base, label, pipeline=True):
                    log_message(f"Pipeline[{label}]", f"Started {'plot' if plots_only else 'daily'} run for {target}")
                    if not plots_only:
                        if process_daily(target, base, label):
                            raise RuntimeError(f"Daily processing failed for {target}; plots/publication not attempted")
                        for period in ("week", "month", "3month"):
                            if process_period_data(period, target, base, detector=label):
                                raise RuntimeError(f"{period} processing failed for {target}")
                    with processing_lock(base, label):
                        plot_failures = sum(
                            run_shell_stage(base, target, label, [script], plot=True) != 0
                            for script in PLOTS
                        )
                        if plot_failures:
                            raise RuntimeError(f"{plot_failures} plot stage(s) failed; publication not attempted")
                        for root in roots:
                            publish_detector(base, label, target, root)
                    log_message(f"Pipeline[{label}]", f"Completed run for {target}")
            except (OSError, ValueError, RuntimeError, configparser.Error) as error:
                log_error(f"Pipeline[{label}]", f"FAILED - {error}")
                failures += 1
        log_message("ProcessDetectors.py", f"{label}: run attempted for {target}; see {unit_logs}")
    for root in roots:
        publish_index(base, root)
    log_message("ProcessDetectors.py", f"Completed named pipeline with {failures} failure(s)")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target_date", nargs="?", type=date.fromisoformat)
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--detector", help="Process only this label; otherwise all configured labels")
    parser.add_argument("--skip-downloads", action="store_true", help="Use stored NMDB/weather inputs (offline pilot)")
    parser.add_argument("--plots-only", action="store_true", help="Plot existing products without reprocessing raw data")
    parser.add_argument("--web-root", type=Path, help="Also publish under ROOT/detectors; never replace ROOT/index.html")
    args = parser.parse_args()
    try:
        return run_pipeline(
            get_base_path(), args.date or args.target_date or get_target_date(), args.detector,
            skip_downloads=args.skip_downloads, plots_only=args.plots_only, web_root=args.web_root,
        )
    except (OSError, ValueError, RuntimeError, configparser.Error) as error:
        log_error("ProcessDetectors.py", f"FAILED - {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
