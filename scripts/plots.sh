#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
for plot_script in \
    PlotDataCpmACM0.gp \
    PlotDataFreqACM0.gp \
    PlotDataAdcACM0.gp \
    PlotDataDayACM0.gp \
    PlotDataWeekACM0.gp \
    PlotDataMonthACM0.gp
do
    su -s /bin/bash "$PICOMUON_FILE_OWNER" -c \
        "export PICOMUON_BASE_PATH=$(printf '%q' "$PICOMUON_BASE_PATH") TZ=UTC TERM=dumb; exec /usr/bin/gnuplot $(printf '%q' "$PICOMUON_BASE_PATH/scripts/$plot_script")"
done