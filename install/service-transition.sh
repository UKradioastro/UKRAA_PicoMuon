#!/bin/bash

set -euo pipefail

usage() {
    echo "Usage: $0 --check|--apply single|named [--activate-services] [LABEL ...]" >&2
    exit 2
}

[ "$#" -ge 2 ] || usage
ACTION=$1
MODE=$2
shift 2

ACTIVATE_SERVICES=false
if [ "${1:-}" = --activate-services ]; then
    ACTIVATE_SERVICES=true
    shift
fi

case "$ACTION" in
    --check|--apply) ;;
    *) usage ;;
esac
case "$MODE" in
    single|named) ;;
    *) usage ;;
esac
if [ "$MODE" = named ] && [ "$#" -eq 0 ]; then
    echo "Named service mode requires at least one validated detector label." >&2
    exit 2
fi
for label in "$@"; do
    lower_label=$(printf '%s' "$label" | tr '[:upper:]' '[:lower:]')
    if [[ ! "$label" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,15}$ ]] ||
        [ "$lower_label" = rejected ] || [ "$lower_label" = single ]; then
        echo "Unsafe detector label for a systemd instance: $label" >&2
        exit 2
    fi
done

list_named_units() {
    local loaded installed
    if ! loaded=$(systemctl list-units --all --type=service --no-legend --no-pager |
            awk '$1 ~ /^PicoMuon@[^.]+\.service$/ { print $1 }'); then
            echo "Unable to enumerate loaded PicoMuon detector services." >&2
            return 1
    fi
    if ! installed=$(systemctl list-unit-files --type=service --no-legend --no-pager |
            awk '$1 ~ /^PicoMuon@[^.]+\.service$/ { print $1 }'); then
            echo "Unable to enumerate installed PicoMuon detector services." >&2
            return 1
    fi
    printf '%s\n%s\n' "$loaded" "$installed" | awk 'NF && !seen[$1]++'
}

named_transition_pending=false
NAMED_UNITS=$(list_named_units)
while IFS= read -r unit; do
    [ -n "$unit" ] || continue
    if systemctl is-active --quiet "$unit" || systemctl is-enabled --quiet "$unit"; then
            named_transition_pending=true
    fi
done <<< "$NAMED_UNITS"

if [ "$ACTION" = --check ]; then
    if [ "$MODE" = named ] && [ "$ACTIVATE_SERVICES" != true ]; then
        echo "Named detector services are opt-in. Re-run with --activate-services after reviewing the detector mapping and legacy settings." >&2
        exit 1
    fi
    if [ "$MODE" = single ] && [ "$named_transition_pending" = true ] && [ "$ACTIVATE_SERVICES" != true ]; then
        echo "Named detector services are active or enabled. Re-run with --activate-services to authorize the transition to single-detector mode." >&2
        exit 1
    fi
    exit 0
fi

deactivate_if_present() {
    local unit=$1
    if systemctl is-active --quiet "$unit"; then
        echo "Stopping $unit..."
        systemctl stop "$unit"
    fi
    if systemctl is-enabled --quiet "$unit"; then
        echo "Disabling $unit..."
        systemctl disable "$unit"
    fi
}

# Stop every previous named instance before enabling any service in the target mode.
NAMED_UNITS=$(list_named_units)
while IFS= read -r unit; do
    [ -n "$unit" ] || continue
    deactivate_if_present "$unit"
done <<< "$NAMED_UNITS"

deactivate_if_present PicoMuonACM0.service
if [ "$MODE" = named ]; then
    deactivate_if_present PicoMuon.service
fi

systemctl daemon-reload
if [ "$MODE" = named ]; then
    for label in "$@"; do
        systemctl enable --now "PicoMuon@$label.service"
    done
else
    systemctl enable PicoMuon.service
    systemctl restart PicoMuon.service
fi
