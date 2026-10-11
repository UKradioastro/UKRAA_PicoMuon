#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
BASE_PATH=$PICOMUON_BASE_PATH
MAIN_LOG="$BASE_PATH/logfiles/log-PicoMuon.txt"
ERROR_LOG="$BASE_PATH/logfiles/log-error.txt"
PYTHON=/usr/bin/python3
GNUPLOT=/usr/bin/gnuplot

mkdir -p "$BASE_PATH/logfiles"
SOFTWARE_VERSION=$(PYTHONPATH="$BASE_PATH/scripts" "$PYTHON" -c \
    'from picomuon_common import get_version; print(get_version())')

log_message() {
    printf '%s : %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$1" >> "$MAIN_LOG"
}

run_as_owner() {
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
    if run_as_owner "$@" >> "$MAIN_LOG"; then
        log_message "Completed $description"
    else
        printf '%s : processData.sh : FAILED - %s\n' \
            "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$description" >> "$ERROR_LOG"
        return 1
    fi
}

FAILURES=0
run_stage "NMDB download" "$PYTHON" "$BASE_PATH/scripts/GetDataNeutron.py" || FAILURES=$((FAILURES + 1))
run_stage "minute-count processing" "$PYTHON" "$BASE_PATH/scripts/ProcessDataCpmACM0.py" || FAILURES=$((FAILURES + 1))
run_stage "daily processing" "$PYTHON" "$BASE_PATH/scripts/ProcessDataDayACM0.py" || FAILURES=$((FAILURES + 1))
run_stage "weekly processing" "$PYTHON" "$BASE_PATH/scripts/ProcessDataWeekACM0.py" || FAILURES=$((FAILURES + 1))
run_stage "monthly processing" "$PYTHON" "$BASE_PATH/scripts/ProcessDataMonthACM0.py" || FAILURES=$((FAILURES + 1))
run_stage "ADC processing" "$PYTHON" "$BASE_PATH/scripts/ProcessDataAdcACM0.py" || FAILURES=$((FAILURES + 1))

for plot_script in \
    PlotDataCpmACM0.gp \
    PlotDataFreqACM0.gp \
    PlotDataAdcACM0.gp \
    PlotDataDayACM0.gp \
    PlotDataWeekACM0.gp \
    PlotDataMonthACM0.gp
do
    run_stage "plot $plot_script" "$GNUPLOT" "$BASE_PATH/scripts/$plot_script" || FAILURES=$((FAILURES + 1))
done

if [ -d "$BASE_PATH/WWW/temp" ]; then
    if install -d -m 0755 /var/www/html/temp && cp -a "$BASE_PATH/WWW/temp/." /var/www/html/temp/; then
        log_message "Published plot assets"
    else
        printf '%s : processData.sh : FAILED - could not publish plot assets\n' \
            "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "$ERROR_LOG"
        FAILURES=$((FAILURES + 1))
    fi
fi
if ! cp "$BASE_PATH/VERSION" /var/www/html/picomuon-version.txt; then
    printf '%s : processData.sh : FAILED - could not publish version marker\n' \
        "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "$ERROR_LOG"
    FAILURES=$((FAILURES + 1))
fi

if [ "$FAILURES" -gt 0 ]; then
    log_message "Completed daily processing with $FAILURES failed stage(s); see log-error.txt"
    exit 1
fi
log_message "Completed daily processing and publishing"
