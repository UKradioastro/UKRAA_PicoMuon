#!/bin/bash

set -euo pipefail

REPO_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT
source "$REPO_PATH/scripts/logging.sh"
MAIN_LOG="$TEST_ROOT/main.log"
ERROR_LOG="$TEST_ROOT/error.log"
PATTERN='^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} UTC : [^:]+ : '
export TZ=Pacific/Auckland

write_log_entry "test.sh" $'first line\nsecond line' > "$MAIN_LOG"
[ "$(wc -l < "$MAIN_LOG")" -eq 2 ]
! grep -Ev "$PATTERN" "$MAIN_LOG"
grep -Eq ' UTC : test.sh +: first line$' "$MAIN_LOG"
[ "$(head -c 13 "$MAIN_LOG")" = "$(date -u '+%Y-%m-%d %H')" ]

formatted=$(write_log_entry "child.py" "already formatted")
printf '%s\nraw diagnostic\r\nunterminated' "$formatted" |
    format_log_stream "parent.sh" > "$MAIN_LOG"
[ "$(head -n 1 "$MAIN_LOG")" = "$formatted" ]
[ "$(wc -l < "$MAIN_LOG")" -eq 3 ]
! grep -Ev "$PATTERN" "$MAIN_LOG"
grep -Eq 'parent.sh +: unterminated$' "$MAIN_LOG"

sample_command() {
    printf '%s\n' "$formatted"
    printf 'normal output\n'
    printf 'diagnostic one\ndiagnostic two' >&2
    return 7
}
: > "$MAIN_LOG"
: > "$ERROR_LOG"
status=0
run_logged_command "child.py" sample_command || status=$?
[ "$status" -eq 7 ]
[ "$(wc -l < "$MAIN_LOG")" -eq 2 ]
[ "$(wc -l < "$ERROR_LOG")" -eq 3 ]
[ "$(head -n 1 "$MAIN_LOG")" = "$formatted" ]
grep -F 'diagnostic two' "$ERROR_LOG"
grep -F 'exit code 7' "$ERROR_LOG"
! grep -q 'diagnostic' "$MAIN_LOG"
! grep -Ev "$PATTERN" "$MAIN_LOG" "$ERROR_LOG"

# Warnings on stderr must not be hidden or change a successful exit status.
warning_command() { printf 'warning from command\n' >&2; }
run_logged_command "warning.sh" warning_command
grep -F 'warning from command' "$ERROR_LOG"

export PICOMUON_BASE_PATH="$TEST_ROOT/project with spaces"
export PICOMUON_FILE_OWNER
PICOMUON_FILE_OWNER=$(id -un)
export PICOMUON_FILE_GROUP
PICOMUON_FILE_GROUP=$(id -g)
mkdir -p "$PICOMUON_BASE_PATH"
GNUPLOT=mock_gnuplot
mock_gnuplot() {
    printf 'gnuplot target=%s\n' "$PICOMUON_TARGET_DATE"
    printf 'gnuplot arguments=%s\n' "$*"
    printf 'gnuplot diagnostic\n' >&2
    return "${PLOT_STATUS:-0}"
}
target=2026-10-09
day_dir="$PICOMUON_BASE_PATH/data/day/ACM0/2026/2026-10"
mkdir -p "$day_dir"
printf 'data\n' > "$day_dir/$target.txt"
: > "$MAIN_LOG"
: > "$ERROR_LOG"
run_logged_plot PlotDataWeekACM0.gp "$target"
run_logged_plot PlotDataMonthACM0.gp "$target"
grep -F 'Skipped:' "$MAIN_LOG"
[ ! -s "$ERROR_LOG" ]
! grep -q 'gnuplot target=' "$MAIN_LOG"
run_logged_plot PlotDataDayACM0.gp "$target"
grep -F 'gnuplot target=2026-10-09' "$MAIN_LOG"
grep -Eq 'PlotDataDayACM0.gp +: Completed plot' "$MAIN_LOG"
grep -Eq 'PlotDataDayACM0.gp +: gnuplot diagnostic' "$ERROR_LOG"
grep -F 'neutronColumn=7' "$MAIN_LOG"

# New CSV schemas move neutrons behind the five detector/settings columns.
printf 'DateTime,CPM_T,CPM_B,CPM_C,Mean_Temp,Mean_Pres,detector_name,threshold_top,reset_top,threshold_bottom,reset_bottom,neutrons,station\n' \
    > "$day_dir/$target.txt"
: > "$MAIN_LOG"
run_logged_plot PlotDataDayACM0.gp "$target"
grep -F 'neutronColumn=12' "$MAIN_LOG"

: > "$MAIN_LOG"
: > "$ERROR_LOG"
PLOT_STATUS=9
status=0
run_logged_plot PlotDataDayACM0.gp "$target" || status=$?
[ "$status" -eq 9 ]
grep -F 'exit code 9' "$ERROR_LOG"
! grep -q 'Completed plot' "$MAIN_LOG"
status=0
run_logged_plot PlotDataAdcACM0.gp "$target" || status=$?
[ "$status" -eq 1 ]
grep -F 'required input missing:' "$ERROR_LOG"
! grep -Ev "$PATTERN" "$MAIN_LOG" "$ERROR_LOG"

# CPM plots explicitly include or omit the optional weather overlay.
cpm_dir="$PICOMUON_BASE_PATH/data/cpm/ACM0/2026/2026-10"
weather_dir="$PICOMUON_BASE_PATH/data/weather/2026/2026-10"
mkdir -p "$cpm_dir" "$weather_dir"
printf 'data\n' > "$cpm_dir/$target.txt"
PLOT_STATUS=0
: > "$MAIN_LOG"
run_logged_plot PlotDataCpmACM0.gp "$target"
grep -F 'Temperature overlay unavailable:' "$MAIN_LOG"
grep -F 'plotWeather=0' "$MAIN_LOG"
printf 'weather\n' > "$weather_dir/$target.txt"
: > "$MAIN_LOG"
run_logged_plot PlotDataCpmACM0.gp "$target"
grep -F 'Using stored modelled 2 m air temperature' "$MAIN_LOG"
grep -F 'plotWeather=1' "$MAIN_LOG"

# Run the real reprocessing orchestration with isolated command substitutes.
BASE="$TEST_ROOT/reprocessing"
mkdir -p "$BASE/scripts" "$BASE/data/raw/2026/2026-10"
cp "$REPO_PATH/scripts/logging.sh" "$REPO_PATH/scripts/picomuon-env.sh" "$BASE/scripts/"
printf 'raw event\n' > "$BASE/data/raw/2026/2026-10/$target.txt"
cat > "$BASE/scripts/fake-python" <<'PYTHON'
#!/bin/bash
if [[ "$1" = *ProcessDaily.py ]]; then
    for category in cpm adc day; do
        dir="$PICOMUON_BASE_PATH/data/$category/ACM0/2026/2026-10"
        mkdir -p "$dir"
        printf 'data\n' > "$dir/2026-10-09.txt"
    done
fi
if [ "$1" = -c ]; then
    printf '2026.10.0\n'
    exit 0
fi
if [[ "$1" = *GetDataWeather.py ]] && [ "${FAIL_WEATHER:-0}" -eq 1 ]; then
    printf 'weather download unavailable\n' >&2
    exit 7
fi
printf 'processor output\n'
PYTHON
cat > "$BASE/scripts/fake-gnuplot" <<'GNUPLOT'
#!/bin/bash
printf 'gnuplot output for %s\n' "$PICOMUON_TARGET_DATE"
if [ "${FAIL_PLOT:-0}" -eq 1 ]; then
    printf 'bad plot input\n' >&2
    exit 8
fi
GNUPLOT
chmod +x "$BASE/scripts/fake-python" "$BASE/scripts/fake-gnuplot"
sed -e 's|PYTHON=/usr/bin/python3|PYTHON="$BASE_PATH/scripts/fake-python"|' \
    -e 's|GNUPLOT=/usr/bin/gnuplot|GNUPLOT="$BASE_PATH/scripts/fake-gnuplot"|' \
    "$REPO_PATH/scripts/reprocessData.sh" > "$BASE/scripts/reprocessData.sh"
PICOMUON_BASE_PATH="$BASE" bash "$BASE/scripts/reprocessData.sh" --to "$target" --plot
grep -F 'Completed reprocessing with 0 failure(s)' "$BASE/logfiles/log-PicoMuon.txt"
[ ! -s "$BASE/logfiles/log-error.txt" ]
! grep -q 'FAILED' "$BASE/logfiles/log-PicoMuon.txt"
status=0
FAIL_PLOT=1 PICOMUON_BASE_PATH="$BASE" bash "$BASE/scripts/reprocessData.sh" --to "$target" --plot || status=$?
[ "$status" -eq 1 ]
grep -F 'Completed reprocessing with 4 failure(s)' "$BASE/logfiles/log-PicoMuon.txt"
grep -F 'bad plot input' "$BASE/logfiles/log-error.txt"
! grep -Ev "$PATTERN" "$BASE/logfiles/log-PicoMuon.txt" "$BASE/logfiles/log-error.txt"

# Daily processing must share the same skip and failure behavior.
sed -e 's|PYTHON=/usr/bin/python3|PYTHON="$BASE_PATH/scripts/fake-python"|' \
    -e 's|GNUPLOT=/usr/bin/gnuplot|GNUPLOT="$BASE_PATH/scripts/fake-gnuplot"|' \
    -e "s|/var/www/html|$BASE/absent-web-root|g" \
    "$REPO_PATH/scripts/processData.sh" > "$BASE/scripts/processData.sh"
: > "$BASE/logfiles/log-PicoMuon.txt"
: > "$BASE/logfiles/log-error.txt"
PICOMUON_BASE_PATH="$BASE" bash "$BASE/scripts/processData.sh" "$target"
[ ! -s "$BASE/logfiles/log-error.txt" ]
grep -F 'Completed daily processing and publishing' "$BASE/logfiles/log-PicoMuon.txt"
status=0
FAIL_PLOT=1 PICOMUON_BASE_PATH="$BASE" bash "$BASE/scripts/processData.sh" "$target" || status=$?
[ "$status" -eq 1 ]
grep -F 'Completed daily processing with 4 failed stage(s)' "$BASE/logfiles/log-PicoMuon.txt"
! grep -Ev "$PATTERN" "$BASE/logfiles/log-PicoMuon.txt" "$BASE/logfiles/log-error.txt"

# Weather failures are counted while all existing plots still run.
: > "$BASE/logfiles/log-PicoMuon.txt"
: > "$BASE/logfiles/log-error.txt"
status=0
FAIL_WEATHER=1 PICOMUON_BASE_PATH="$BASE" bash "$BASE/scripts/processData.sh" "$target" || status=$?
[ "$status" -eq 1 ]
grep -F 'weather download unavailable' "$BASE/logfiles/log-error.txt"
grep -F 'Completed daily processing with 1 failed stage(s)' "$BASE/logfiles/log-PicoMuon.txt"
grep -Eq 'PlotDataCpmACM0.gp +: Completed plot' "$BASE/logfiles/log-PicoMuon.txt"

sed -e 's|PYTHON=/usr/bin/python3|PYTHON="$PICOMUON_BASE_PATH/scripts/fake-python"|' \
    -e 's|GNUPLOT=/usr/bin/gnuplot|GNUPLOT="$PICOMUON_BASE_PATH/scripts/fake-gnuplot"|' \
    "$REPO_PATH/scripts/plots.sh" > "$BASE/scripts/plots.sh"
PICOMUON_BASE_PATH="$BASE" bash "$BASE/scripts/plots.sh" "$target"
status=0
FAIL_WEATHER=1 PICOMUON_BASE_PATH="$BASE" bash "$BASE/scripts/plots.sh" "$target" || status=$?
[ "$status" -eq 1 ]
status=0
FAIL_WEATHER=1 PICOMUON_BASE_PATH="$BASE" bash "$BASE/scripts/reprocessData.sh" --to "$target" --plot || status=$?
[ "$status" -eq 1 ]
grep -F 'Completed reprocessing with 1 failure(s)' "$BASE/logfiles/log-PicoMuon.txt"

# Simulate flock to test cron routing even on Git Bash, which lacks flock.
flock() { return 0; }
export -f flock
cat > "$BASE/scripts/cron-child.sh" <<'CHILD'
#!/bin/bash
source "$PICOMUON_BASE_PATH/scripts/logging.sh"
write_log_entry "child.py" "already formatted error" >&2
printf 'plain cron output\n'
printf 'plain cron error\n' >&2
exit 6
CHILD
: > "$BASE/logfiles/log-PicoMuon.txt"
: > "$BASE/logfiles/log-error.txt"
status=0
PICOMUON_BASE_PATH="$BASE" bash "$REPO_PATH/scripts/runCronJob.sh" \
    /bin/bash "$BASE/scripts/cron-child.sh" || status=$?
[ "$status" -eq 6 ]
grep -Eq 'child.py +: already formatted error$' "$BASE/logfiles/log-error.txt"
grep -Eq 'cron-child.sh +: plain cron error$' "$BASE/logfiles/log-error.txt"
[ "$(grep -c 'UTC : .*UTC :' "$BASE/logfiles/log-error.txt")" -eq 0 ]
! grep -Ev "$PATTERN" "$BASE/logfiles/log-PicoMuon.txt" "$BASE/logfiles/log-error.txt"
flock() { return 1; }
PICOMUON_BASE_PATH="$BASE" bash "$REPO_PATH/scripts/runCronJob.sh" /bin/false
grep -Eq 'runCronJob.sh +: Skipped: another PicoMuon job holds the lock$' "$BASE/logfiles/log-PicoMuon.txt"
unset -f flock

# Rotation keeps historic entries intact and uses the shared format afterwards.
chown() { return 0; }
export -f chown
PICOMUON_BASE_PATH="$BASE" bash "$REPO_PATH/scripts/managelogfiles.sh"
grep -F 'plain cron output' "$BASE/logfiles/log-PicoMuon.txt-0"
grep -F 'plain cron error' "$BASE/logfiles/log-error.txt-0"
[ ! -s "$BASE/logfiles/log-error.txt" ]
grep -Eq 'managelogfiles.sh +: Completed weekly log rotation$' "$BASE/logfiles/log-PicoMuon.txt"
! grep -Ev "$PATTERN" "$BASE/logfiles/log-PicoMuon.txt"
unset -f chown

echo "Logging passed: UTC format, routing, multiline output, exit codes, daily/reprocessing plots and cron."
