#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/picomuon-env.sh"
source "$(dirname "${BASH_SOURCE[0]}")/logging.sh"
LOG_DIR="$PICOMUON_BASE_PATH/logfiles"
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
    printf '%s : runCronJob.sh : skipped because another PicoMuon job holds the lock\n' \
        "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    exit 0
fi

STDERR_FILE=$(mktemp "$LOG_DIR/.cron-stderr.XXXXXX")
trap 'rm -f "$STDERR_FILE"' EXIT

if "$@" 2> "$STDERR_FILE"; then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi
COMMAND_NAME=$(basename "${2:-$1}")

while IFS= read -r line || [ -n "$line" ]; do
    [ -n "$line" ] && log_error "$COMMAND_NAME stderr: $line"
done < "$STDERR_FILE"

if [ "$EXIT_CODE" -ne 0 ]; then
    log_error "$COMMAND_NAME FAILED with exit code $EXIT_CODE"
fi

exit "$EXIT_CODE"
