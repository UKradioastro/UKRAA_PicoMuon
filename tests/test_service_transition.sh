#!/bin/bash

set -euo pipefail

REPO_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
mkdir -p "$TEMP_DIR/bin"

cat > "$TEMP_DIR/bin/systemctl" <<'MOCK'
#!/bin/bash
set -euo pipefail
action=$1
case "$action" in
    list-units)
        while IFS= read -r unit; do
            if [ -n "$unit" ]; then
                printf '%s loaded active running\n' "$unit"
            fi
        done <<< "${FAKE_ACTIVE_UNITS:-}"
        ;;
    list-unit-files)
        if [ "${FAKE_FAIL_UNIT_FILE_QUERY:-}" = true ]; then
            exit 1
        fi
        while IFS= read -r unit; do
            if [ -n "$unit" ]; then
                printf '%s enabled\n' "$unit"
            fi
        done <<< "${FAKE_ENABLED_UNITS:-}"
        ;;
    is-active)
        unit=${!#}
        printf '%s\n' "${FAKE_ACTIVE_UNITS:-}" | grep -Fxq "$unit"
        ;;
    is-enabled)
        unit=${!#}
        printf '%s\n' "${FAKE_ENABLED_UNITS:-}" | grep -Fxq "$unit"
        ;;
    *)
        printf '%s\n' "$*" >> "$FAKE_SYSTEMCTL_LOG"
        ;;
esac
MOCK
chmod +x "$TEMP_DIR/bin/systemctl"
export PATH="$TEMP_DIR/bin:$PATH"
export FAKE_SYSTEMCTL_LOG="$TEMP_DIR/systemctl.log"

if bash "$REPO_PATH/install/service-transition.sh" --check named >/dev/null 2>&1; then
    echo "Named mode unexpectedly passed without explicit activation." >&2
    exit 1
fi
if ! bash "$REPO_PATH/install/service-transition.sh" --check named --activate-services East; then
    echo "Named mode did not pass after explicit activation." >&2
    exit 1
fi

export FAKE_FAIL_UNIT_FILE_QUERY=true
if bash "$REPO_PATH/install/service-transition.sh" --check single >/dev/null 2>&1; then
    echo "Service preflight unexpectedly passed after a systemd query failure." >&2
    exit 1
fi
unset FAKE_FAIL_UNIT_FILE_QUERY

export FAKE_ACTIVE_UNITS=PicoMuon@East.service
if bash "$REPO_PATH/install/service-transition.sh" --check single >/dev/null 2>&1; then
    echo "Single mode unexpectedly passed while a named service was active." >&2
    exit 1
fi
export FAKE_ACTIVE_UNITS=
export FAKE_ENABLED_UNITS=PicoMuon@East.service
if bash "$REPO_PATH/install/service-transition.sh" --check single >/dev/null 2>&1; then
    echo "Single mode unexpectedly passed while a named service was enabled." >&2
    exit 1
fi

export FAKE_ACTIVE_UNITS=$'PicoMuon.service\nPicoMuonACM0.service\nPicoMuon@Old.service'
export FAKE_ENABLED_UNITS=$'PicoMuon.service\nPicoMuonACM0.service\nPicoMuon@Old.service'
: > "$FAKE_SYSTEMCTL_LOG"
bash "$REPO_PATH/install/service-transition.sh" --apply named --activate-services East West
NAMED_LOG=$(<"$FAKE_SYSTEMCTL_LOG")
for expected in \
    "stop PicoMuon@Old.service" \
    "disable PicoMuon@Old.service" \
    "stop PicoMuonACM0.service" \
    "disable PicoMuonACM0.service" \
    "stop PicoMuon.service" \
    "disable PicoMuon.service" \
    "daemon-reload" \
    "enable --now PicoMuon@East.service" \
    "enable --now PicoMuon@West.service"
do
    if ! grep -Fxq "$expected" <<< "$NAMED_LOG"; then
        echo "Missing systemctl call during named transition: $expected" >&2
        exit 1
    fi
done
START_LINE=$(grep -n -m1 '^enable --now PicoMuon@East.service$' "$FAKE_SYSTEMCTL_LOG" | cut -d: -f1)
for old_unit in PicoMuon@Old.service PicoMuonACM0.service PicoMuon.service; do
    STOP_LINE=$(grep -n -m1 "^stop $old_unit$" "$FAKE_SYSTEMCTL_LOG" | cut -d: -f1)
    if [ "$STOP_LINE" -ge "$START_LINE" ]; then
        echo "A named instance started before $old_unit was stopped." >&2
        exit 1
    fi
done

export FAKE_ACTIVE_UNITS=PicoMuon@East.service
export FAKE_ENABLED_UNITS=PicoMuon@East.service
: > "$FAKE_SYSTEMCTL_LOG"
bash "$REPO_PATH/install/service-transition.sh" --apply single --activate-services
SINGLE_LOG=$(<"$FAKE_SYSTEMCTL_LOG")
for expected in "stop PicoMuon@East.service" "disable PicoMuon@East.service" \
    "enable PicoMuon.service" "restart PicoMuon.service"
do
    if ! grep -Fxq "$expected" <<< "$SINGLE_LOG"; then
        echo "Missing systemctl call during single transition: $expected" >&2
        exit 1
    fi
done
if [ "$(grep -n -m1 '^stop PicoMuon@East.service$' "$FAKE_SYSTEMCTL_LOG" | cut -d: -f1)" -ge \
     "$(grep -n -m1 '^restart PicoMuon.service$' "$FAKE_SYSTEMCTL_LOG" | cut -d: -f1)" ]; then
    echo "The single collector restarted before the named instance was stopped." >&2
    exit 1
fi

echo "Service transition checks passed."
