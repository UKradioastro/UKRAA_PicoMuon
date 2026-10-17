#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
source "$(dirname "${BASH_SOURCE[0]}")/logging.sh"
MAIN_LOG="$PICOMUON_BASE_PATH/logfiles/log-PicoMuon.txt"
ERROR_LOG="$PICOMUON_BASE_PATH/logfiles/log-error.txt"
GNUPLOT=/usr/bin/gnuplot
TARGET_DATE="${1:-${PICOMUON_TARGET_DATE:-$(date -u -d yesterday +%F)}}"
mkdir -p "$PICOMUON_BASE_PATH/logfiles"
PYTHONPATH="$PICOMUON_BASE_PATH/scripts" /usr/bin/python3 -c \
    'from picomuon_common import get_usb_options; get_usb_options()'
FAILURES=0
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
write_log_entry "plots.sh" "Completed plotting with $FAILURES failure(s)" >> "$MAIN_LOG"
[ "$FAILURES" -eq 0 ]