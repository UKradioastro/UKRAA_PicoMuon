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

# Named mode: root publishes named pages and the sole detector's plots under legacy names.
NAMED_BLOCK=$(sed -n '/^publish_named_web() {/,/^}/p' "$REPO_PATH/scripts/processData.sh" |
    sed "s|/var/www/html|$WEB_ROOT|g")
eval "$NAMED_BLOCK"
UNIT="$BASE_PATH/temp/detectors/Unit_1"
mkdir -p "$UNIT/yesterday" "$UNIT/periods" "$BASE_PATH/WWW/detectors/Unit_1/2026-10-24"
printf 'named cpm\n' > "$UNIT/yesterday/Unit_1_T-Cpm.png"
printf 'named day\n' > "$UNIT/periods/Unit_1_day_plot.png"
printf 'not named\n' > "$UNIT/periods/Other_day_plot.png"
printf 'page\n' > "$BASE_PATH/WWW/detectors/Unit_1/index.html"
printf 'dated\n' > "$BASE_PATH/WWW/detectors/Unit_1/2026-10-24/Unit_1_T-Cpm.png"
printf 'public page\n' > "$WEB_ROOT/index.html"
: > "$MAIN_LOG"
DETECTORS=Unit_1
publish_named_web
cmp "$UNIT/yesterday/Unit_1_T-Cpm.png" "$WEB_ROOT/temp/ACM0_T-Cpm.png"
cmp "$UNIT/periods/Unit_1_day_plot.png" "$WEB_ROOT/temp/ACM0_day_plot.png"
[ ! -e "$WEB_ROOT/temp/ACM0_Other_day_plot.png" ]
cmp "$BASE_PATH/WWW/detectors/Unit_1/index.html" "$WEB_ROOT/detectors/Unit_1/index.html"
cmp "$BASE_PATH/WWW/detectors/Unit_1/2026-10-24/Unit_1_T-Cpm.png" "$WEB_ROOT/detectors/Unit_1/2026-10-24/Unit_1_T-Cpm.png"
[ "$(cat "$WEB_ROOT/index.html")" = "public page" ]
grep -F "Published 2 Unit_1 plot assets to $WEB_ROOT/temp as legacy ACM0 plots" "$MAIN_LOG"

printf 'untouched\n' > "$WEB_ROOT/temp/ACM0_day_plot.png"
DETECTORS=$'Unit_1\nUnit_2'
publish_named_web
[ "$(cat "$WEB_ROOT/temp/ACM0_day_plot.png")" = "untouched" ]
grep -F "Skipped legacy public plots: 2 named detectors configured" "$MAIN_LOG"

rm "$UNIT/yesterday/"*.png "$UNIT/periods/Unit_1_day_plot.png"
DETECTORS=Unit_1
status=0
publish_named_web || status=$?
[ "$status" -ne 0 ]
grep -F "FAILED - no Unit_1 PNG plot assets found for legacy publishing to $WEB_ROOT/temp" "$ERROR_LOG"

echo "Publishing passed: grouped PNGs, ignored stale flat files, single group, missing/empty source, command failure diagnostics, and named legacy publishing."
