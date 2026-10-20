#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
source "$(dirname "${BASH_SOURCE[0]}")/logging.sh"
LOG_DIR="$PICOMUON_BASE_PATH/logfiles"
mkdir -p "$LOG_DIR"

LOG_DIRS=("$LOG_DIR")
for unit_dir in "$LOG_DIR/detectors/"*; do
    [ ! -d "$unit_dir" ] || LOG_DIRS+=("$unit_dir")
done
for directory in "${LOG_DIRS[@]}"; do
    for log_name in log-PicoMuon.txt log-error.txt; do
        [ ! -e "$directory/$log_name-2" ] || cp -p "$directory/$log_name-2" "$directory/$log_name-3"
        [ ! -e "$directory/$log_name-1" ] || cp -p "$directory/$log_name-1" "$directory/$log_name-2"
        [ ! -e "$directory/$log_name-0" ] || cp -p "$directory/$log_name-0" "$directory/$log_name-1"
        [ ! -e "$directory/$log_name" ] || cp -p "$directory/$log_name" "$directory/$log_name-0"
        : > "$directory/$log_name"
        chown "$PICOMUON_FILE_OWNER:$PICOMUON_FILE_GROUP" "$directory/$log_name"
    done
    write_log_entry "managelogfiles.sh" "Completed weekly log rotation" >> "$directory/log-PicoMuon.txt"
done
