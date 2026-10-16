#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
source "$(dirname "${BASH_SOURCE[0]}")/logging.sh"
BASE_PATH=$PICOMUON_BASE_PATH
MAIN_LOG="$BASE_PATH/logfiles/log-PicoMuon.txt"
ERROR_LOG="$BASE_PATH/logfiles/log-error.txt"
PYTHON=/usr/bin/python3
GNUPLOT=/usr/bin/gnuplot
TARGET_DATE="${1:-${PICOMUON_TARGET_DATE:-$(date -u -d yesterday +%F)}}"
export PICOMUON_TARGET_DATE="$TARGET_DATE"
TARGET_YEAR="${TARGET_DATE:0:4}"
TARGET_MONTH="${TARGET_DATE:0:7}"

mkdir -p "$BASE_PATH/logfiles"
SOFTWARE_VERSION=$(PYTHONPATH="$BASE_PATH/scripts" "$PYTHON" -c \
    'from picomuon_common import get_version; print(get_version())')

log_message() {
    write_log_entry "processData.sh" "$1" >> "$MAIN_LOG"
}

log_failure() {
    write_log_entry "processData.sh" "$1" >> "$ERROR_LOG"
}

run_as_owner() {
    # If already running as the file owner, execute directly without su/password prompt
    if [ "$(id -un 2>/dev/null || true)" = "$PICOMUON_FILE_OWNER" ]; then
        (
            export PICOMUON_BASE_PATH="$BASE_PATH" TZ=UTC TERM=dumb
            cd "$BASE_PATH"
            "$@"
        )
        return $?
    fi

    local command_text=""
    local argument
    for argument in "$@"; do
        printf -v argument '%q' "$argument"
        command_text+="$argument "
    done
    su -s /bin/bash "$PICOMUON_FILE_OWNER" -c \
        "export PICOMUON_BASE_PATH=$(printf '%q' "$BASE_PATH") TZ=UTC TERM=dumb; cd $(printf '%q' "$BASE_PATH") && $command_text"
}

run_stage() {
    local description=$1
    shift
    log_message "Starting $description (version $SOFTWARE_VERSION)"
    if run_as_owner "$@" >> "$MAIN_LOG" 2>> "$ERROR_LOG"; then
        log_message "Completed $description"
    else
        log_failure "FAILED - $description"
        return 1
    fi
}

FAILURES=0
run_stage "NMDB download" "$PYTHON" "$BASE_PATH/scripts/GetDataNeutron.py" || FAILURES=$((FAILURES + 1))
run_stage "fast daily processing" "$PYTHON" "$BASE_PATH/scripts/ProcessDaily.py" --date "$TARGET_DATE" || FAILURES=$((FAILURES + 1))
run_stage "multi-day period processing" "$PYTHON" "$BASE_PATH/scripts/ProcessPeriod.py" --date "$TARGET_DATE" || FAILURES=$((FAILURES + 1))

for plot_script in \
    PlotDataCpmACM0.gp \
    PlotDataFreqACM0.gp \
    PlotDataAdcACM0.gp \
    PlotDataDayACM0.gp \
    PlotDataWeekACM0.gp \
    PlotDataMonthACM0.gp
do
    case "$plot_script" in
        PlotDataWeekACM0.gp)
            period_file="$BASE_PATH/data/week/ACM0/$TARGET_YEAR/$TARGET_MONTH/$TARGET_DATE.txt"
            ;;
        PlotDataMonthACM0.gp)
            period_file="$BASE_PATH/data/month/ACM0/$TARGET_YEAR/$TARGET_MONTH/$TARGET_DATE.txt"
            ;;
        *)
            period_file=""
            ;;
    esac

    if [ -n "$period_file" ] && [ ! -f "$period_file" ]; then
        log_message "Skipped plot $plot_script (period data unavailable; insufficient history)"
        continue
    fi
    run_stage "plot $plot_script" "$GNUPLOT" "$BASE_PATH/scripts/$plot_script" || FAILURES=$((FAILURES + 1))
done

# Publish to web server directory if accessible (e.g. under root cron)
if [ -d "/var/www/html" ]; then
    if [ -w "/var/www/html" ]; then
        PLOT_SOURCE="$BASE_PATH/temp"
        PLOT_DEST=/var/www/html/temp
        PLOT_FILES=("$PLOT_SOURCE"/*.png)
        log_message "Publishing plot assets from $PLOT_SOURCE to $PLOT_DEST"
        if [ -f "${PLOT_FILES[0]}" ]; then
            if { install -d -m 0755 "$PLOT_DEST" &&
                install -p -m 0644 "${PLOT_FILES[@]}" "$PLOT_DEST/"; } 2>> "$ERROR_LOG"; then
                log_message "Published ${#PLOT_FILES[@]} plot assets from $PLOT_SOURCE to $PLOT_DEST"
            else
                log_failure "FAILED - could not publish plot assets from $PLOT_SOURCE to $PLOT_DEST (see command errors above)"
                FAILURES=$((FAILURES + 1))
            fi
        else
            log_failure "FAILED - no PNG plot assets found in $PLOT_SOURCE for publishing to $PLOT_DEST"
            FAILURES=$((FAILURES + 1))
        fi
        VERSION_MARKER=/var/www/html/picomuon-version.txt
        if [ -f "$VERSION_MARKER" ] && cmp -s "$BASE_PATH/VERSION" "$VERSION_MARKER"; then
            :
        elif [ -e "$VERSION_MARKER" ] && [ ! -w "$VERSION_MARKER" ]; then
            log_message "Skipped publishing version marker (not writable by current user; published under root cron)"
        elif ! cp "$BASE_PATH/VERSION" "$VERSION_MARKER" 2>> "$ERROR_LOG"; then
            log_failure "FAILED - could not publish version marker"
            FAILURES=$((FAILURES + 1))
        fi
    else
        log_message "Skipped publishing to /var/www/html (not writable by current user; published under root cron)"
    fi
else
    log_message "Skipped publishing to /var/www/html (web directory does not exist)"
fi

if [ "$FAILURES" -gt 0 ]; then
    log_message "Completed daily processing with $FAILURES failed stage(s); see log-error.txt"
    exit 1
fi
log_message "Completed daily processing and publishing"
