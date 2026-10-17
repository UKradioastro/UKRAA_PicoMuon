#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
source "$(dirname "${BASH_SOURCE[0]}")/logging.sh"
LOG_DIR="$PICOMUON_BASE_PATH/logfiles"
MAIN_LOG="$LOG_DIR/log-PicoMuon.txt"
ERROR_LOG="$LOG_DIR/log-error.txt"
LOCK_FILE="$LOG_DIR/.picomuon-cron.lock"

mkdir -p "$LOG_DIR"

log_error() {
    write_log_entry "runCronJob.sh" "$1" >> "$ERROR_LOG"
}

if [ "$#" -eq 0 ]; then
    log_error "FAILED - command is required"
    exit 2
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    write_log_entry "runCronJob.sh" "Skipped: another PicoMuon job holds the lock" >> "$MAIN_LOG"
    exit 0
fi

COMMAND_NAME=$(basename "$1")
case "$COMMAND_NAME" in
    bash|sh|python|python3|gnuplot)
        if [ "$#" -gt 1 ] && [[ "$2" != -* ]]; then
            COMMAND_NAME=$(basename "$2")
        fi
        ;;
esac
run_logged_command "$COMMAND_NAME" "$@"
