#!/bin/bash

# script reprocessData.sh to rebuild processed data from the raw data archive.
# Use after a software update that changes processing, or after copying older
# raw data files back onto the system. Regenerates CPM, ADC, Day and Hourly data
# for every raw day in range, then refreshes multi-day period products.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
source "$(dirname "${BASH_SOURCE[0]}")/logging.sh"

BASE_PATH=$PICOMUON_BASE_PATH
LOG_DIR="$BASE_PATH/logfiles"
MAIN_LOG="$LOG_DIR/log-PicoMuon.txt"
ERROR_LOG="$LOG_DIR/log-error.txt"
PYTHON=/usr/bin/python3
GNUPLOT=/usr/bin/gnuplot

log_msg() {
    write_log_entry "reprocessData.sh" "$1" >> "$MAIN_LOG"
}

log_err() {
    write_log_entry "reprocessData.sh" "$1" >> "$ERROR_LOG"
}

usage() {
    cat <<EOF
Usage: sudo bash $0 [options]

Rebuilds minute CPM, ADC, 5-minute Day and hourly products from raw files,
then refreshes week, month, and multi-day period products.

Options:
  --detector LABEL    Registered detector to reprocess (required in named mode)
  --from YYYY-MM-DD    First day to reprocess (default: oldest raw file)
  --to YYYY-MM-DD      Last day to reprocess (default: yesterday)
  --skip-period        Do not regenerate multi-day period products after reprocessing
  --plot               Run gnuplot to render refreshed plots
  --dry-run            List the days that would be reprocessed and exit
  --help               Show this help

Existing processed files for each reprocessed day are replaced safely.
Today's partial raw file is never reprocessed.
EOF
}

valid_date() {
    [[ "$1" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] && date -d "$1" '+%Y-%m-%d' >/dev/null 2>&1
}

FROM_DATE=""
TO_DATE=$(date -u -d yesterday +%Y-%m-%d)
DETECTOR=""
DETECTOR_ARGS=()
RUN_PERIOD=true
RUN_PLOTS=false
DRY_RUN=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --detector)
            DETECTOR=${2:-}
            if [ -z "$DETECTOR" ]; then usage; exit 2; fi
            DETECTOR_ARGS=(--detector "$DETECTOR")
            shift 2
            ;;
        --from)
            FROM_DATE=${2:-}
            shift 2 || { usage; exit 2; }
            ;;
        --to)
            TO_DATE=${2:-}
            shift 2 || { usage; exit 2; }
            ;;
        --skip-period) RUN_PERIOD=false; shift ;;
        --plot) RUN_PLOTS=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) usage; exit 0 ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 2
            ;;
    esac
done

if [ -n "$FROM_DATE" ] && ! valid_date "$FROM_DATE"; then
    echo "Invalid --from date: $FROM_DATE (expected YYYY-MM-DD)"
    exit 2
fi

if ! valid_date "$TO_DATE"; then
    echo "Invalid --to date: $TO_DATE (expected YYYY-MM-DD)"
    exit 2
fi

TODAY=$(date -u +%Y-%m-%d)
if [[ ! "$TO_DATE" < "$TODAY" ]]; then
    TO_DATE=$(date -u -d yesterday +%Y-%m-%d)
    echo "Limiting --to to $TO_DATE (today's raw file is still being written)"
fi

if [ -n "$FROM_DATE" ] && [[ "$FROM_DATE" > "$TO_DATE" ]]; then
    echo "--from ($FROM_DATE) is after --to ($TO_DATE)"
    exit 2
fi

DATE_ARGS=(--to "$TO_DATE")
if [ -n "$FROM_DATE" ]; then
    DATE_ARGS+=(--from "$FROM_DATE")
fi
RAW_DATES=$(PYTHONPATH="$BASE_PATH/scripts" "$PYTHON" \
    "$BASE_PATH/scripts/picomuon_processing.py" "${DETECTOR_ARGS[@]}" "${DATE_ARGS[@]}")

if [ -z "$RAW_DATES" ]; then
    echo "No raw data files found for ${DETECTOR:-single} in the requested range" >&2
    exit 1
fi
mapfile -t TARGET_DATES <<< "$RAW_DATES"

echo "Days to reprocess: ${#TARGET_DATES[@]} (${TARGET_DATES[0]} to ${TARGET_DATES[-1]})"

if [ "$DRY_RUN" = "true" ]; then
    printf '%s\n' "${TARGET_DATES[@]}"
    exit 0
fi

if [ -n "$DETECTOR" ]; then
    LOG_DIR="$LOG_DIR/detectors/$DETECTOR"
    MAIN_LOG="$LOG_DIR/log-PicoMuon.txt"
    ERROR_LOG="$LOG_DIR/log-error.txt"
fi
run_as_owner mkdir -p "$LOG_DIR"
run_as_owner touch "$MAIN_LOG" "$ERROR_LOG" "$LOG_DIR/.reprocess.lock"
exec 8>"$LOG_DIR/.reprocess.lock"
if ! flock -n 8; then
    log_err "FAILED - another reprocessing job is running for ${DETECTOR:-single}"
    exit 1
fi
if [ -n "$DETECTOR" ]; then
    run_as_owner touch "$LOG_DIR/.pipeline.lock"
    exec 7>"$LOG_DIR/.pipeline.lock"
    if ! flock -n 7; then
        log_err "FAILED - another pipeline or plotting job is running for $DETECTOR"
        exit 1
    fi
fi

log_msg "Started reprocessing ${#TARGET_DATES[@]} day(s) from ${TARGET_DATES[0]} to ${TARGET_DATES[-1]}"

FAILURES=0
COUNT=0
TOTAL=${#TARGET_DATES[@]}

for day in "${TARGET_DATES[@]}"; do
    COUNT=$((COUNT + 1))
    printf '[%d/%d] Reprocessing %s\n' "$COUNT" "$TOTAL" "$day"
    if ! run_logged_command "ProcessDaily.py" run_as_owner "$PYTHON" "$BASE_PATH/scripts/ProcessDaily.py" --target-date "$day" "${DETECTOR_ARGS[@]}"; then
        log_err "FAILED daily reprocessing for $day"
        FAILURES=$((FAILURES + 1))
    fi
done

if [ "$RUN_PERIOD" = "true" ]; then
    log_msg "Refreshing period products for ${TO_DATE}"
    if run_logged_command "ProcessPeriod.py" run_as_owner "$PYTHON" "$BASE_PATH/scripts/ProcessPeriod.py" --target-date "$TO_DATE" "${DETECTOR_ARGS[@]}"; then
        log_msg "Completed period products refresh"
    else
        log_err "FAILED period products refresh"
        FAILURES=$((FAILURES + 1))
    fi
fi

if [ "$RUN_PLOTS" = "true" ]; then
    if [ -n "$DETECTOR" ] && [ "$FAILURES" -gt 0 ]; then
        log_err "FAILED - not plotting stale named products after reprocessing failures"
        exit 1
    fi
    if [ -n "$DETECTOR" ]; then
        run_as_owner touch "$LOG_DIR/.processing.lock"
        exec 6>"$LOG_DIR/.processing.lock"
        if ! flock -n 6; then
            log_err "FAILED - another processor is writing $DETECTOR products"
            exit 1
        fi
    fi
    if [ -n "$DETECTOR" ]; then
        run_as_owner touch "$BASE_PATH/logfiles/.pipeline.lock"
        exec 5>"$BASE_PATH/logfiles/.pipeline.lock"
        if ! flock -n 5; then
            log_err "FAILED - another named job is downloading shared site inputs"
            exit 1
        fi
    fi
    run_logged_command "GetDataWeather.py" run_as_owner "$PYTHON" \
        "$BASE_PATH/scripts/GetDataWeather.py" --date "$TO_DATE" || FAILURES=$((FAILURES + 1))
    if [ -n "$DETECTOR" ]; then
        exec 5>&-
    fi
    log_msg "Refreshing gnuplot plots"
    for plot_script in \
        PlotDataCpmACM0.gp \
        PlotDataFreqACM0.gp \
        PlotDataAdcACM0.gp \
        PlotDataDayACM0.gp \
        PlotDataWeekACM0.gp \
        PlotDataMonthACM0.gp
    do
        run_logged_plot "$plot_script" "$TO_DATE" "$DETECTOR" || FAILURES=$((FAILURES + 1))
    done
fi

log_msg "Completed reprocessing with $FAILURES failure(s)"
if [ "$FAILURES" -gt 0 ]; then
    exit 1
fi
