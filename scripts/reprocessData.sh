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

mkdir -p "$LOG_DIR"

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
TO_DATE=$(date -d yesterday +%Y-%m-%d)
RUN_PERIOD=true
RUN_PLOTS=false
DRY_RUN=false

while [ "$#" -gt 0 ]; do
    case "$1" in
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
    TO_DATE=$(date -d yesterday +%Y-%m-%d)
    echo "Limiting --to to $TO_DATE (today's raw file is still being written)"
fi

if [ -n "$FROM_DATE" ] && [[ "$FROM_DATE" > "$TO_DATE" ]]; then
    echo "--from ($FROM_DATE) is after --to ($TO_DATE)"
    exit 2
fi

RAW_ROOT="$BASE_PATH/data/raw"
TARGET_DATES=()

if [ -d "$RAW_ROOT" ]; then
    while IFS= read -r raw_name; do
        day="${raw_name%.txt}"
        if ! valid_date "$day"; then
            continue
        fi
        if [ -n "$FROM_DATE" ] && [[ "$day" < "$FROM_DATE" ]]; then
            continue
        fi
        if [[ "$day" > "$TO_DATE" ]]; then
            continue
        fi
        TARGET_DATES+=("$day")
    done < <(find "$RAW_ROOT" -type f -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].txt' -printf '%f\n' | sort -u)
fi

if [ "${#TARGET_DATES[@]}" -eq 0 ]; then
    echo "No raw data files found in $RAW_ROOT for the requested range"
    exit 1
fi

echo "Days to reprocess: ${#TARGET_DATES[@]} (${TARGET_DATES[0]} to ${TARGET_DATES[-1]})"

if [ "$DRY_RUN" = "true" ]; then
    printf '%s\n' "${TARGET_DATES[@]}"
    exit 0
fi

log_msg "Started reprocessing ${#TARGET_DATES[@]} day(s) from ${TARGET_DATES[0]} to ${TARGET_DATES[-1]}"

FAILURES=0
COUNT=0
TOTAL=${#TARGET_DATES[@]}

for day in "${TARGET_DATES[@]}"; do
    COUNT=$((COUNT + 1))
    printf '[%d/%d] Reprocessing %s\n' "$COUNT" "$TOTAL" "$day"
    if ! run_logged_command "ProcessDaily.py" run_as_owner "$PYTHON" "$BASE_PATH/scripts/ProcessDaily.py" --target-date "$day"; then
        log_err "FAILED daily reprocessing for $day"
        FAILURES=$((FAILURES + 1))
    fi
done

if [ "$RUN_PERIOD" = "true" ]; then
    log_msg "Refreshing period products for ${TO_DATE}"
    if run_logged_command "ProcessPeriod.py" run_as_owner "$PYTHON" "$BASE_PATH/scripts/ProcessPeriod.py" --target-date "$TO_DATE"; then
        log_msg "Completed period products refresh"
    else
        log_err "FAILED period products refresh"
        FAILURES=$((FAILURES + 1))
    fi
fi

if [ "$RUN_PLOTS" = "true" ]; then
    log_msg "Refreshing gnuplot plots"
    for plot_script in \
        PlotDataCpmACM0.gp \
        PlotDataFreqACM0.gp \
        PlotDataAdcACM0.gp \
        PlotDataDayACM0.gp \
        PlotDataWeekACM0.gp \
        PlotDataMonthACM0.gp
    do
        run_logged_plot "$plot_script" "$TO_DATE" || FAILURES=$((FAILURES + 1))
    done
fi

log_msg "Completed reprocessing with $FAILURES failure(s)"
if [ "$FAILURES" -gt 0 ]; then
    exit 1
fi
