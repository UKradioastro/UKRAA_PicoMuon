#!/bin/bash

# Shared columnar logging helper for UKRAA PicoMuon bash scripts.
# Format: YYYY-MM-DD HH:MM:SS UTC : %-26s : message

write_log_entry() {
    local source_name=$1
    local message=$2
    printf '%s : %-26s : %s\n' \
        "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$source_name" "$message"
}
