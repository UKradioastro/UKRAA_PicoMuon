#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
source "$(dirname "${BASH_SOURCE[0]}")/logging.sh"
BASE_PATH=$PICOMUON_BASE_PATH
MAIN_LOG="$BASE_PATH/logfiles/log-PicoMuon.txt"
ERROR_LOG="$BASE_PATH/logfiles/log-error.txt"
PYTHON=/usr/bin/python3
GNUPLOT=/usr/bin/gnuplot
mkdir -p "$BASE_PATH/logfiles"

log_message() {
    write_log_entry "processData.sh" "$1" >> "$MAIN_LOG"
}

log_failure() {
    write_log_entry "processData.sh" "$1" >> "$ERROR_LOG"
}

# Named processing runs as the data owner; root cron then publishes its pages and,
# for exactly one named detector, keeps the legacy public ACM0 plot URLs current.
publish_named_web() {
    local web_root=/var/www/html failures=0 count=0 label plot name
    local labels=() sources=()
    if [ -d "$BASE_PATH/WWW/detectors" ]; then
        if run_logged_command "processData.sh" install -d -m 0755 "$web_root/detectors" &&
            run_logged_command "processData.sh" cp -R --no-preserve=mode,ownership \
                "$BASE_PATH/WWW/detectors/." "$web_root/detectors/"; then
            log_message "Published named detector pages from $BASE_PATH/WWW/detectors to $web_root/detectors"
        else
            log_failure "FAILED - could not publish named detector pages to $web_root/detectors"
            failures=$((failures + 1))
        fi
    else
        log_failure "FAILED - no named detector pages found in $BASE_PATH/WWW/detectors"
        failures=$((failures + 1))
    fi
    mapfile -t labels <<< "$DETECTORS"
    if [ "${#labels[@]}" -ne 1 ] || [ -z "${labels[0]}" ]; then
        log_message "Skipped legacy public plots: ${#labels[@]} named detectors configured"
    else
        label=${labels[0]}
        for plot in "$BASE_PATH/temp/detectors/$label/yesterday/${label}_"*.png \
            "$BASE_PATH/temp/detectors/$label/periods/${label}_"*.png; do
            [ -f "$plot" ] && sources+=("$plot")
        done
        if [ "${#sources[@]}" -eq 0 ]; then
            log_failure "FAILED - no $label PNG plot assets found for legacy publishing to $web_root/temp"
            failures=$((failures + 1))
        elif run_logged_command "processData.sh" install -d -m 0755 "$web_root/temp"; then
            for plot in "${sources[@]}"; do
                name=$(basename "$plot")
                if run_logged_command "processData.sh" install -m 0644 "$plot" "$web_root/temp/ACM0_${name#"${label}_"}"; then
                    count=$((count + 1))
                else
                    failures=$((failures + 1))
                fi
            done
            log_message "Published $count $label plot assets to $web_root/temp as legacy ACM0 plots"
        else
            log_failure "FAILED - could not create $web_root/temp for legacy $label plots"
            failures=$((failures + 1))
        fi
    fi
    local version_marker="$web_root/picomuon-version.txt"
    if [ -f "$version_marker" ] && cmp -s "$BASE_PATH/VERSION" "$version_marker"; then
        :
    elif ! run_logged_command "processData.sh" cp "$BASE_PATH/VERSION" "$version_marker"; then
        log_failure "FAILED - could not publish version marker"
        failures=$((failures + 1))
    fi
    [ "$failures" -eq 0 ]
}

DETECTORS=$(PYTHONPATH="$BASE_PATH/scripts" "$PYTHON" -c \
    'from picomuon_detectors import get_detectors; print("\n".join(get_detectors()))')
if [ -n "$DETECTORS" ]; then
    STATUS=0
    run_as_owner "$PYTHON" "$BASE_PATH/scripts/ProcessDetectors.py" "$@" || STATUS=$?
    if [ -d /var/www/html ] && [ -w /var/www/html ]; then
        publish_named_web || STATUS=1
    else
        log_message "Skipped publishing named detectors to /var/www/html (not writable by current user)"
    fi
    exit "$STATUS"
fi
TARGET_DATE="${1:-${PICOMUON_TARGET_DATE:-$(date -u -d yesterday +%F)}}"
export PICOMUON_TARGET_DATE="$TARGET_DATE"
SOFTWARE_VERSION=$(PYTHONPATH="$BASE_PATH/scripts" "$PYTHON" -c \
    'from picomuon_common import get_usb_options, get_version; get_usb_options(); print(get_version())')

run_stage() {
    local description=$1
    shift
    log_message "Starting $description (version $SOFTWARE_VERSION)"
    local source_name
    source_name=$(basename "$2")
    if run_logged_command "$source_name" run_as_owner "$@"; then
        log_message "Completed $description"
    else
        log_failure "FAILED - $description"
        return 1
    fi
}

FAILURES=0
run_stage "NMDB download" "$PYTHON" "$BASE_PATH/scripts/GetDataNeutron.py" || FAILURES=$((FAILURES + 1))
run_stage "weather download" "$PYTHON" "$BASE_PATH/scripts/GetDataWeather.py" --date "$TARGET_DATE" || FAILURES=$((FAILURES + 1))
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
    run_logged_plot "$plot_script" "$TARGET_DATE" || FAILURES=$((FAILURES + 1))
done

# Publish to web server directory if accessible (e.g. under root cron)
if [ -d "/var/www/html" ]; then
    if [ -w "/var/www/html" ]; then
        PLOT_SOURCE="$BASE_PATH/temp"
        PLOT_DEST=/var/www/html/temp
        PLOT_FILES=()
        for PLOT_GROUP in yesterday periods; do
            for PLOT_FILE in "$PLOT_SOURCE/$PLOT_GROUP/"*.png; do
                [ -f "$PLOT_FILE" ] && PLOT_FILES+=("$PLOT_FILE")
            done
        done
        log_message "Publishing plot assets from $PLOT_SOURCE to $PLOT_DEST"
        if [ "${#PLOT_FILES[@]}" -gt 0 ]; then
            if run_logged_command "processData.sh" install -d -m 0755 "$PLOT_DEST" &&
                run_logged_command "processData.sh" install -p -m 0644 "${PLOT_FILES[@]}" "$PLOT_DEST/"; then
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
        elif ! run_logged_command "processData.sh" cp "$BASE_PATH/VERSION" "$VERSION_MARKER"; then
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
