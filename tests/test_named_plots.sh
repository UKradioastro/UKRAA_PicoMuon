#!/bin/bash

set -euo pipefail

REPO_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT
source "$REPO_PATH/scripts/logging.sh"
export PICOMUON_BASE_PATH="$TEST_ROOT/project with spaces"
export PICOMUON_FILE_OWNER
PICOMUON_FILE_OWNER=$(id -un)
MAIN_LOG="$TEST_ROOT/main.log"
ERROR_LOG="$TEST_ROOT/error.log"
TARGET=2026-10-19
PYTHON=mock_validator
GNUPLOT=mock_gnuplot
mock_validator() {
    printf '%s\n' "$*" > "$TEST_ROOT/validation.txt"
}
mock_gnuplot() {
    printf '%s\n' "$*" > "$TEST_ROOT/gnuplot.txt"
    local root="$PICOMUON_BASE_PATH/temp/detectors/Unit_2"
    if [ "${NO_OUTPUT:-0}" -eq 0 ]; then
        if [[ "$*" = *PlotDataCpmACM0.gp* ]]; then
            for event in T B C; do
                printf 'mock PNG\n' > "$root/yesterday/Unit_2_${event}-Cpm.png"
            done
        else
            printf 'mock PNG\n' > "$root/periods/Unit_2_day_plot.png"
        fi
    fi
    return "${PLOT_STATUS:-0}"
}
root="$PICOMUON_BASE_PATH/temp/detectors/Unit_2"
mkdir -p "$PICOMUON_BASE_PATH/data/day/detectors/Unit_2/2026/2026-10" "$root/periods"
printf 'DateTime,CPM_T,CPM_B,CPM_C,Mean_Temp,Mean_Pres,detector_name,threshold_top,reset_top,threshold_bottom,reset_bottom,neutrons,station\n' \
    > "$PICOMUON_BASE_PATH/data/day/detectors/Unit_2/2026/2026-10/$TARGET.txt"
run_logged_plot PlotDataDayACM0.gp "$TARGET" Unit_2
grep -F "processing_label(get_base_path(), sys.argv[1]) Unit_2" "$TEST_ROOT/validation.txt"
grep -F "detectorLabel='Unit_2'" "$TEST_ROOT/gnuplot.txt"
grep -F 'neutronColumn=12' "$TEST_ROOT/gnuplot.txt"
[ -s "$root/periods/Unit_2_day_plot.png" ]
[ -d "$PICOMUON_BASE_PATH/plots/day/detectors/Unit_2" ]
[ ! -e "$PICOMUON_BASE_PATH/temp/periods/ACM0_day_plot.png" ]
[ ! -e "$PICOMUON_BASE_PATH/temp/detectors/Unit_3" ]

# Missing optional history removes stale latest plots rather than reusing them.
printf 'old week plot\n' > "$root/periods/Unit_2_week_plot.png"
run_logged_plot PlotDataWeekACM0.gp "$TARGET" Unit_2
[ ! -e "$root/periods/Unit_2_week_plot.png" ]
grep -F 'Skipped: no week product' "$MAIN_LOG"

# Failed and output-less plotters must not leave success-shaped latest images.
PLOT_STATUS=9
status=0
run_logged_plot PlotDataDayACM0.gp "$TARGET" Unit_2 || status=$?
[ "$status" -eq 9 ]
[ ! -e "$root/periods/Unit_2_day_plot.png" ]
PLOT_STATUS=0
NO_OUTPUT=1
status=0
run_logged_plot PlotDataDayACM0.gp "$TARGET" Unit_2 || status=$?
[ "$status" -eq 1 ]
grep -F 'expected plot output missing or empty' "$ERROR_LOG"
NO_OUTPUT=0

# No named-to-legacy fallback even if a legacy product exists.
mkdir -p "$PICOMUON_BASE_PATH/data/cpm/ACM0/2026/2026-10"
printf 'legacy data\n' > "$PICOMUON_BASE_PATH/data/cpm/ACM0/2026/2026-10/$TARGET.txt"
status=0
run_logged_plot PlotDataCpmACM0.gp "$TARGET" Unit_2 || status=$?
[ "$status" -eq 1 ]
grep -F 'required input missing:' "$ERROR_LOG"
mkdir -p "$PICOMUON_BASE_PATH/data/cpm/detectors/Unit_2/2026/2026-10"
printf 'named data\n' > "$PICOMUON_BASE_PATH/data/cpm/detectors/Unit_2/2026/2026-10/$TARGET.txt"
run_logged_plot PlotDataCpmACM0.gp "$TARGET" Unit_2
for event in T B C; do
    [ -s "$root/yesterday/Unit_2_${event}-Cpm.png" ]
done
echo "Named plotting passed: identity selection, output isolation, stale removal, missing inputs and plot failures."

# Rotation covers each existing unit without merging its logs with another unit.
mkdir -p "$PICOMUON_BASE_PATH/scripts"
cp "$REPO_PATH/scripts/logging.sh" "$REPO_PATH/scripts/picomuon-env.sh" "$PICOMUON_BASE_PATH/scripts/"
export PICOMUON_FILE_GROUP
PICOMUON_FILE_GROUP=$(id -g)
for label in Unit_2 Unit_3; do
    directory="$PICOMUON_BASE_PATH/logfiles/detectors/$label"
    mkdir -p "$directory"
    printf '%s current\n' "$label" > "$directory/log-PicoMuon.txt"
    printf '%s error\n' "$label" > "$directory/log-error.txt"
    printf '%s previous\n' "$label" > "$directory/log-PicoMuon.txt-0"
done
chown() { return 0; }
export -f chown
bash "$REPO_PATH/scripts/managelogfiles.sh"
unset -f chown
for label in Unit_2 Unit_3; do
    directory="$PICOMUON_BASE_PATH/logfiles/detectors/$label"
    grep -Fx "$label current" "$directory/log-PicoMuon.txt-0"
    grep -Fx "$label previous" "$directory/log-PicoMuon.txt-1"
    grep -Fx "$label error" "$directory/log-error.txt-0"
    [ ! -s "$directory/log-error.txt" ]
    grep -F 'Completed weekly log rotation' "$directory/log-PicoMuon.txt"
done
echo "Named log rotation passed: separate current logs and archive generations."
