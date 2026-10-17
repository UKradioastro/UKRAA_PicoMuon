#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
source "$(dirname "${BASH_SOURCE[0]}")/logging.sh"
LOG_DIR="$PICOMUON_BASE_PATH/logfiles"
mkdir -p "$LOG_DIR"

for log_name in log-PicoMuon.txt log-error.txt; do
    [ ! -e "$LOG_DIR/$log_name-2" ] || cp -p "$LOG_DIR/$log_name-2" "$LOG_DIR/$log_name-3"
    [ ! -e "$LOG_DIR/$log_name-1" ] || cp -p "$LOG_DIR/$log_name-1" "$LOG_DIR/$log_name-2"
    [ ! -e "$LOG_DIR/$log_name-0" ] || cp -p "$LOG_DIR/$log_name-0" "$LOG_DIR/$log_name-1"
    [ ! -e "$LOG_DIR/$log_name" ] || cp -p "$LOG_DIR/$log_name" "$LOG_DIR/$log_name-0"
    : > "$LOG_DIR/$log_name"
    chown "$PICOMUON_FILE_OWNER:$PICOMUON_FILE_GROUP" "$LOG_DIR/$log_name"
done
write_log_entry "managelogfiles.sh" "Completed weekly log rotation" >> "$LOG_DIR/log-PicoMuon.txt"
