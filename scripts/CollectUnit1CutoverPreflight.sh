#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

BASE="$HOME/UKRAA_PicoMuon"
ADOPTION_TEST="$HOME/picomuon-adoption-test.UYOjre"
APPROVED_MANIFEST="$HOME/unit1-adoption-manifest.RpgaZH.json"
APPROVED_MANIFEST_SHA256="b59b5608aa489ba0c288b0c0222bde95c011f27c2bca08d8c5a062514b6452fd"
ADOPTION_TOOL_SHA256="22b5f22cf20c55758e870cd1fa7c34d4736083ba0b8b914fbcf6b65a3e0fdfc1"
DEVICE="/dev/serial/by-id/usb-Raspberry_Pi_Pico_E660D4A0A7598522-if00"
CAPTURE_ERRORS=0

fail() {
    printf 'PREFLIGHT FAILED: %s\n' "$*" >&2
    exit 1
}

capture_command() {
    local label=$1
    local destination=$2
    shift 2
    local status=0
    if "$@" > "$destination" 2> "$destination.stderr"; then
        status=0
    else
        status=$?
    fi
    printf '%s\n' "$status" > "$destination.exit"
    return 0
}

capture_crontab() {
    local label=$1
    local destination=$2
    shift 2
    local status=0
    if "$@" > "$destination" 2> "$destination.stderr"; then
        printf 'present\n' > "$destination.state"
        : > "$destination.exit"
    else
        status=$?
        printf '%s\n' "$status" > "$destination.exit"
        if grep -Eqi 'no crontab for' "$destination.stderr"; then
            printf 'absent\n' > "$destination.state"
        else
            printf 'ERROR: inspect exit/stderr\n' > "$destination.state"
            CAPTURE_ERRORS=$((CAPTURE_ERRORS + 1))
            printf 'Could not capture %s crontab; evidence retained at %s\n' \
                "$label" "$EVIDENCE" >&2
        fi
    fi
}

[[ "$(id -un)" == "pi" ]] || fail "Run as pi, not root or another account."
[[ -d "$BASE" ]] || fail "Production installation missing: $BASE"
[[ -d "$ADOPTION_TEST/scripts" ]] || fail "Adoption test tools missing: $ADOPTION_TEST/scripts"
[[ -f "$APPROVED_MANIFEST" ]] || fail "Approved archive manifest missing: $APPROVED_MANIFEST"
[[ -e "$DEVICE" ]] || fail "Expected Unit_1 serial alias is absent: $DEVICE"

EVIDENCE=$(mktemp -d "$HOME/unit1-cutover-preflight.XXXXXX")
chmod 0700 "$EVIDENCE"
printf 'PREFLIGHT DIRECTORY: %s\n' "$EVIDENCE"
printf 'This script is read-only with respect to production; it only creates this evidence directory.\n'

date -u --iso-8601=seconds > "$EVIDENCE/utc.txt"
hostnamectl > "$EVIDENCE/host.txt"
id > "$EVIDENCE/account.txt"
uname -a > "$EVIDENCE/kernel.txt"
df -h "$BASE" "$HOME" > "$EVIDENCE/space.txt"
df -i "$BASE" "$HOME" > "$EVIDENCE/inodes.txt"
findmnt -T "$BASE" > "$EVIDENCE/installation-mount.txt"
findmnt -T "$HOME" > "$EVIDENCE/home-mount.txt"
ps -eo user,pid,ppid,lstart,args --width 300 > "$EVIDENCE/processes.txt"
systemctl list-units --all --type=service --no-legend --no-pager \
    > "$EVIDENCE/services-loaded.txt"
systemctl list-unit-files --type=service --no-legend --no-pager \
    > "$EVIDENCE/services-installed.txt"
systemctl list-timers --all --no-pager > "$EVIDENCE/timers.txt"

readlink -v "$DEVICE" > "$EVIDENCE/unit1-device-link.txt"
readlink -f "$DEVICE" > "$EVIDENCE/unit1-device-resolved.txt"
udevadm info --query=property --name="$DEVICE" > "$EVIDENCE/unit1-udev-properties.txt"
grep -Fx 'ID_SERIAL=Raspberry_Pi_Pico_E660D4A0A7598522' \
    "$EVIDENCE/unit1-udev-properties.txt" > /dev/null \
    || fail "Unit_1 ID_SERIAL differs from the reviewed physical identity."
grep -Fx 'ID_SERIAL_SHORT=E660D4A0A7598522' \
    "$EVIDENCE/unit1-udev-properties.txt" > /dev/null \
    || fail "Unit_1 ID_SERIAL_SHORT differs from the reviewed physical identity."

UTC_DAY=$(date -u +%F)
CURRENT_RAW="$BASE/data/raw/${UTC_DAY:0:4}/${UTC_DAY:0:7}/$UTC_DAY.txt"
CURRENT_STATUS="$BASE/data/status/current.json"
[[ -f "$CURRENT_RAW" ]] || fail "Current UTC single-mode raw file missing: $CURRENT_RAW"
[[ -f "$CURRENT_STATUS" ]] || fail "Current collector status file missing: $CURRENT_STATUS"
stat --printf='%n\nsize_bytes=%s\nmtime=%y\nowner=%U:%G\nmode=%a\n' \
    "$CURRENT_RAW" "$CURRENT_STATUS" > "$EVIDENCE/current-collector-files.txt"
cp -a "$CURRENT_STATUS" "$EVIDENCE/current-status-before.json"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); assert isinstance(d, dict); print(json.dumps({k:d.get(k) for k in ("updated_at","last_event_utc","last_event_type","total_events_today","detector_name")}, indent=2))' \
    "$CURRENT_STATUS" > "$EVIDENCE/current-status-summary.json"

mapfile -t UNIT_NAMES < <(
    {
        awk '$1 ~ /^PicoMuon(@[^.]*)?\.service$/ { print $1 }' \
            "$EVIDENCE/services-loaded.txt"
        awk '$1 ~ /^PicoMuon(@[^.]*)?\.service$/ { print $1 }' \
            "$EVIDENCE/services-installed.txt"
    } | sort -u
)
printf '%s\n' "${UNIT_NAMES[@]}" > "$EVIDENCE/picom_unit_names.txt"
for unit in "${UNIT_NAMES[@]}"; do
    if [[ "$unit" == *@.service ]]; then
        printf 'Template only; runtime properties do not apply. See the captured unit definition and services-installed.txt.\n' \
            > "$EVIDENCE/${unit}.properties-not-applicable.txt"
    else
        capture_command "$unit systemd show" "$EVIDENCE/${unit}.properties.txt" \
            systemctl show "$unit" \
            -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
            -p MainPID -p ExecStart -p Environment -p WorkingDirectory \
            -p User -p Group -p SupplementaryGroups -p Restart
        [[ "$(cat "$EVIDENCE/${unit}.properties.txt.exit")" == 0 ]] \
            || fail "Could not capture runtime properties for $unit; inspect the saved exit/stderr."
    fi
    capture_command "$unit systemd cat" "$EVIDENCE/${unit}.unit.txt" \
        systemctl cat "$unit"
    [[ "$(cat "$EVIDENCE/${unit}.unit.txt.exit")" == 0 ]] \
        || fail "Could not capture installed unit definition for $unit."
done

capture_crontab pi "$EVIDENCE/pi-crontab.txt" crontab -l
capture_crontab root "$EVIDENCE/root-crontab.txt" sudo crontab -l

for path in /etc/crontab /etc/cron.d /etc/cron.hourly /etc/cron.daily \
    /etc/cron.weekly /etc/cron.monthly; do
    [[ -e "$path" ]] && printf '%s\n' "${path#/}"
done > "$EVIDENCE/system-cron-paths.txt"
mapfile -t CRON_PATHS < "$EVIDENCE/system-cron-paths.txt"
if ((${#CRON_PATHS[@]})); then
    sudo tar -czf "$EVIDENCE/system-cron-files.tar.gz" -C / "${CRON_PATHS[@]}"
    sudo chown "$(id -un):$(id -gn)" "$EVIDENCE/system-cron-files.tar.gz"
fi

sudo find /etc/systemd/system -maxdepth 2 \
    \( -type f -o -type l \) \
    -path '/etc/systemd/system/PicoMuon*' -print0 \
    > "$EVIDENCE/systemd-paths.nul"
mapfile -d '' -t SYSTEMD_PATHS < "$EVIDENCE/systemd-paths.nul"
printf '%s\n' "${SYSTEMD_PATHS[@]}" > "$EVIDENCE/systemd-paths.txt"
if ((${#SYSTEMD_PATHS[@]})); then
    SYSTEMD_RELATIVE=()
    for path in "${SYSTEMD_PATHS[@]}"; do
        SYSTEMD_RELATIVE+=("${path#/}")
    done
    sudo tar -czf "$EVIDENCE/systemd-unit-files.tar.gz" -C / "${SYSTEMD_RELATIVE[@]}"
    sudo chown "$(id -un):$(id -gn)" "$EVIDENCE/systemd-unit-files.tar.gz"
fi

sha256sum "$APPROVED_MANIFEST" "$ADOPTION_TEST/scripts/AdoptUnit1Archive.py" \
    > "$EVIDENCE/archive-approval-hashes.txt"
printf '%s  %s\n' "$APPROVED_MANIFEST_SHA256" "$APPROVED_MANIFEST" \
    | sha256sum -c > "$EVIDENCE/approved-manifest-check.txt"
printf '%s  %s\n' "$ADOPTION_TOOL_SHA256" "$ADOPTION_TEST/scripts/AdoptUnit1Archive.py" \
    | sha256sum -c > "$EVIDENCE/adoption-tool-check.txt"
python3 -B "$ADOPTION_TEST/scripts/AdoptUnit1Archive.py" \
    --source-base "$BASE" --destination-base "$BASE" \
    > "$EVIDENCE/fresh-adoption-manifest.json"
cmp "$APPROVED_MANIFEST" "$EVIDENCE/fresh-adoption-manifest.json"
sha256sum "$EVIDENCE/fresh-adoption-manifest.json" \
    > "$EVIDENCE/fresh-adoption-manifest.sha256"

find "$BASE/config" "$BASE/scripts" "$BASE/install" "$BASE/VERSION" \
    -type f -print0 \
    | sort -z \
    | xargs -0 sha256sum > "$EVIDENCE/production-config-code.sha256"
tar -czf "$EVIDENCE/production-config-code-backup.tar.gz" \
    -C "$BASE" config scripts install VERSION
tar -tzf "$EVIDENCE/production-config-code-backup.tar.gz" \
    > "$EVIDENCE/production-config-code-backup-members.txt"

date -u --iso-8601=seconds > "$EVIDENCE/completed-utc.txt"
(
    cd "$EVIDENCE"
    find . -type f ! -name SHA256SUMS -print0 \
        | sort -z \
        | xargs -0 sha256sum > SHA256SUMS
)
chmod -R go-rwx "$EVIDENCE"

((CAPTURE_ERRORS == 0)) || fail "One or more crontab captures failed; inspect the saved evidence."
printf '\nPREFLIGHT CAPTURE COMPLETE: %s\n' "$EVIDENCE"
printf 'Fresh archive manifest matches the approved hash.\n'
printf 'Production config/code backup: %s/production-config-code-backup.tar.gz\n' "$EVIDENCE"
printf 'Review and privately download this entire folder. It contains private configuration and system scheduling evidence.\n'
