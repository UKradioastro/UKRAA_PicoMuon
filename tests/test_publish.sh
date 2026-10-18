#!/bin/bash

set -euo pipefail

REPO_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT
BASE_PATH="$TEST_ROOT/project"
WEB_ROOT="$TEST_ROOT/web"
MAIN_LOG="$TEST_ROOT/main.log"
ERROR_LOG="$TEST_ROOT/error.log"
mkdir -p "$BASE_PATH/temp/yesterday" "$BASE_PATH/temp/periods" "$BASE_PATH/WWW/temp" "$WEB_ROOT/temp"
printf '2026.10.0\n' > "$BASE_PATH/VERSION"
printf 'fresh plot\n' > "$BASE_PATH/temp/periods/ACM0_day_plot.png"
printf 'second plot\n' > "$BASE_PATH/temp/yesterday/ACM0_T-Cpm.png"
printf 'obsolete flat plot\n' > "$BASE_PATH/temp/ACM0_day_plot.png"
printf 'obsolete flat plot\n' > "$BASE_PATH/temp/obsolete.png"
printf 'stale plot\n' > "$BASE_PATH/WWW/temp/ACM0_day_plot.png"
printf 'stale plot\n' > "$WEB_ROOT/temp/ACM0_day_plot.png"
printf 'not a plot\n' > "$BASE_PATH/temp/unrelated.txt"

# Exercise the actual publication block with an isolated web root.
PUBLISH_BLOCK=$(sed -n '/^# Publish to web server/,/^if \[ "$FAILURES" -gt 0 \]; then/p' \
    "$REPO_PATH/scripts/processData.sh" | sed '$d' |
    sed "s|/var/www/html|$WEB_ROOT|g")
source "$REPO_PATH/scripts/logging.sh"
log_message() { write_log_entry "processData.sh" "$1" >> "$MAIN_LOG"; }
log_failure() { write_log_entry "processData.sh" "$1" >> "$ERROR_LOG"; }

FAILURES=0
eval "$PUBLISH_BLOCK"
[ "$FAILURES" -eq 0 ]
for plot in "$BASE_PATH/temp/yesterday/"*.png "$BASE_PATH/temp/periods/"*.png; do
    cmp "$plot" "$WEB_ROOT/temp/$(basename "$plot")"
done
[ ! -e "$WEB_ROOT/temp/unrelated.txt" ]
[ ! -e "$WEB_ROOT/temp/obsolete.png" ]
cmp "$BASE_PATH/VERSION" "$WEB_ROOT/picomuon-version.txt"
grep -F "Published 2 plot assets from $BASE_PATH/temp to $WEB_ROOT/temp" "$MAIN_LOG"

rm "$BASE_PATH/temp/yesterday/"*.png "$BASE_PATH/temp/periods/"*.png
: > "$MAIN_LOG"
FAILURES=0
eval "$PUBLISH_BLOCK"
[ "$FAILURES" -eq 1 ]
grep -F "FAILED - no PNG plot assets found in $BASE_PATH/temp" "$ERROR_LOG"
! grep -q "Published .* plot assets" "$MAIN_LOG"

rm "$BASE_PATH/temp/unrelated.txt"
rm "$BASE_PATH/temp/ACM0_day_plot.png" "$BASE_PATH/temp/obsolete.png"
rmdir "$BASE_PATH/temp/yesterday" "$BASE_PATH/temp/periods"
rmdir "$BASE_PATH/temp"
FAILURES=0
eval "$PUBLISH_BLOCK"
[ "$FAILURES" -eq 1 ]

mkdir -p "$BASE_PATH/temp/periods"
printf 'fresh plot\n' > "$BASE_PATH/temp/periods/ACM0_day_plot.png"
FAILURES=0
eval "$PUBLISH_BLOCK"
[ "$FAILURES" -eq 0 ]
cmp "$BASE_PATH/temp/periods/ACM0_day_plot.png" "$WEB_ROOT/temp/ACM0_day_plot.png"
install() { printf 'simulated install failure\n' >&2; return 1; }
: > "$MAIN_LOG"
FAILURES=0
eval "$PUBLISH_BLOCK"
[ "$FAILURES" -eq 1 ]
grep -F "simulated install failure" "$ERROR_LOG"
grep -F "FAILED - could not publish plot assets from $BASE_PATH/temp to $WEB_ROOT/temp" "$ERROR_LOG"
! grep -q "Published .* plot assets" "$MAIN_LOG"
unset -f install

echo "Publishing passed: grouped PNGs, ignored stale flat files, single group, missing/empty source, and command failure diagnostics."
