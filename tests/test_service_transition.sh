#!/bin/bash

set -euo pipefail
trap 'printf "Test failed at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

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

mkdir -p "$TEMP_DIR/installer/install"
cp "$REPO_PATH/install/service-transition.sh" "$TEMP_DIR/installer/install/"
# Execute the real installer preflight only; never reach package or file changes.
awk '/^escape_sed_replacement\(\)/ { exit } { print }' \
    "$REPO_PATH/install/install.sh" > "$TEMP_DIR/installer/install/install.sh"
cat > "$TEMP_DIR/bin/id" <<'MOCK'
#!/bin/bash
case "$1" in
    -u) echo 0 ;;
    -gn) echo pi ;;
    *) exit 2 ;;
esac
MOCK
cat > "$TEMP_DIR/bin/getent" <<'MOCK'
#!/bin/bash
exit 0
MOCK
cat > "$TEMP_DIR/bin/python3" <<'MOCK'
#!/bin/bash
printf '%s\n' "$FAKE_CONFIG_REPORT"
MOCK
chmod +x "$TEMP_DIR/bin/id" "$TEMP_DIR/bin/getent" "$TEMP_DIR/bin/python3"
export SUDO_USER=pi
export FAKE_ACTIVE_UNITS=
export FAKE_ENABLED_UNITS=
export FAKE_CONFIG_REPORT=$'named\nUnit_2\nUnit_3'
: > "$FAKE_SYSTEMCTL_LOG"
if bash "$TEMP_DIR/installer/install/install.sh" > "$TEMP_DIR/preflight.log" 2>&1; then
    echo "Installer unexpectedly accepted named mode without explicit activation." >&2
    exit 1
fi
if ! grep -Fq "Named detector services are opt-in" "$TEMP_DIR/preflight.log"; then
    cat "$TEMP_DIR/preflight.log" >&2
    echo "Installer failed before checking named-mode authorization." >&2
    exit 1
fi
bash "$TEMP_DIR/installer/install/install.sh" --activate-services
export FAKE_CONFIG_REPORT=single
bash "$TEMP_DIR/installer/install/install.sh"
if [ -s "$FAKE_SYSTEMCTL_LOG" ]; then
    echo "Installer preflight unexpectedly mutated service state." >&2
    exit 1
fi

# Run the complete installer against disposable files and mocked host commands.
cp "$REPO_PATH/install/install.sh" "$TEMP_DIR/installer/install/"
cp "$REPO_PATH/install/"*.example "$TEMP_DIR/installer/install/"
cp "$REPO_PATH/install/"*.service "$TEMP_DIR/installer/install/"
cp "$REPO_PATH/install/crontab-PicoMuon.cron" "$TEMP_DIR/installer/install/"
mkdir -p "$TEMP_DIR/installer/scripts" "$TEMP_DIR/installer/WWW" \
    "$TEMP_DIR/host/etc/systemd/system" "$TEMP_DIR/host/var/www/html" \
    "$TEMP_DIR/installer/data/raw/Unit_2"
printf '#!/bin/bash\n' > "$TEMP_DIR/installer/scripts/example.sh"
printf 'test site\n' > "$TEMP_DIR/installer/WWW/index.html"
printf 'test version\n' > "$TEMP_DIR/installer/VERSION"
printf 'preserved raw events\n' > "$TEMP_DIR/installer/data/raw/Unit_2/events.txt"
cp "$TEMP_DIR/installer/data/raw/Unit_2/events.txt" "$TEMP_DIR/raw-original"
export FAKE_HOST_ROOT="$TEMP_DIR/host"
export FAKE_INSTALL_LOG="$TEMP_DIR/install.log"
export REAL_INSTALL
export REAL_CP
REAL_INSTALL=$(command -v install)
REAL_CP=$(command -v cp)

cat > "$TEMP_DIR/bin/host-command" <<'MOCK'
#!/bin/bash
set -euo pipefail
command_name=${0##*/}
printf '%s %s\n' "$command_name" "$*" >> "$FAKE_INSTALL_LOG"
case "$command_name" in
    apt-get|chown)
        ;;
    su)
        # Configuration merging is covered by Python tests, not this host mock.
        if [ "${FAKE_FAIL_MERGE:-}" = true ]; then
            echo "Simulated configuration merge failure" >&2
            exit 1
        fi
        ;;
    systemd-analyze)
        [ "$1" = verify ]
        shift
        for unit in "$@"; do
            if grep -q '@PICOMUON_' "$unit"; then
                echo "Unrendered service placeholder" >&2
                exit 1
            fi
        done
        if [ "${FAKE_FAIL_VERIFY:-}" = true ]; then
            echo "Simulated unit verification failure" >&2
            exit 1
        fi
        ;;
    crontab)
        [ "$1" = -u ] && [ "$2" = root ]
        if [ "$3" = -l ]; then
            cat "$FAKE_HOST_ROOT/root-crontab"
        else
            "$REAL_CP" "$3" "$FAKE_HOST_ROOT/root-crontab"
        fi
        ;;
    install|cp)
        arguments=()
        while [ "$#" -gt 0 ]; do
            case "$1" in
                -o|-g)
                    [ "$command_name" = install ]
                    shift 2
                    continue
                    ;;
                /etc/*|/var/*)
                    arguments+=("$FAKE_HOST_ROOT$1")
                    ;;
                *)
                    arguments+=("$1")
                    ;;
            esac
            shift
        done
        if [ "$command_name" = install ]; then
            "$REAL_INSTALL" "${arguments[@]}"
        else
            "$REAL_CP" "${arguments[@]}"
        fi
        ;;
    *)
        echo "Unexpected mocked host command: $command_name" >&2
        exit 1
        ;;
esac
MOCK
chmod +x "$TEMP_DIR/bin/host-command"
for command_name in apt-get chown su systemd-analyze crontab install cp; do
    "$REAL_CP" "$TEMP_DIR/bin/host-command" "$TEMP_DIR/bin/$command_name"
done

printf '0 2 * * * /opt/unrelated/backup.sh\n' > "$FAKE_HOST_ROOT/root-crontab"
export FAKE_CONFIG_REPORT=$'named\nUnit_2\nUnit_3'
export FAKE_ACTIVE_UNITS=PicoMuon.service
export FAKE_ENABLED_UNITS=PicoMuon.service
: > "$FAKE_INSTALL_LOG"
: > "$FAKE_SYSTEMCTL_LOG"
if bash "$TEMP_DIR/installer/install/install.sh" > "$TEMP_DIR/full.log" 2>&1; then
    echo "Full installer accepted named mode without authorization." >&2
    exit 1
fi
test ! -s "$FAKE_INSTALL_LOG"
test ! -s "$FAKE_SYSTEMCTL_LOG"

bash "$TEMP_DIR/installer/install/install.sh" --activate-services > "$TEMP_DIR/full.log" 2>&1 ||
    { cat "$TEMP_DIR/full.log" >&2; exit 1; }
for label in Unit_2 Unit_3; do
    test -d "$TEMP_DIR/installer/logfiles/detectors/$label"
    grep -Fxq "enable --now PicoMuon@$label.service" "$FAKE_SYSTEMCTL_LOG"
done
grep -Fxq 'stop PicoMuon.service' "$FAKE_SYSTEMCTL_LOG"
grep -Fxq 'disable PicoMuon.service' "$FAKE_SYSTEMCTL_LOG"
grep -Fxq '0 2 * * * /opt/unrelated/backup.sh' "$FAKE_HOST_ROOT/root-crontab"
test "$(grep -Fxc '# BEGIN UKRAA PicoMuon' "$FAKE_HOST_ROOT/root-crontab")" = 1
test -f "$FAKE_HOST_ROOT/etc/systemd/system/PicoMuon@.service"
for expected in "WorkingDirectory=$TEMP_DIR/installer" 'User=pi'; do
    if ! grep -Fxq "$expected" "$FAKE_HOST_ROOT/etc/systemd/system/PicoMuon@.service"; then
        echo "Rendered service is missing the exact line: $expected" >&2
        echo "Check transferred service templates for CRLF endings (shown below as \\r$)." >&2
        sed -n '/^WorkingDirectory=/l; /^User=/l' \
            "$FAKE_HOST_ROOT/etc/systemd/system/PicoMuon@.service" >&2
        exit 1
    fi
done
grep -Fq '/scripts/processData.sh' "$FAKE_HOST_ROOT/root-crontab"
cmp "$TEMP_DIR/installer/WWW/index.html" "$FAKE_HOST_ROOT/var/www/html/index.html"
cmp "$TEMP_DIR/installer/VERSION" "$FAKE_HOST_ROOT/var/www/html/picomuon-version.txt"

# Re-running replaces rather than duplicates the managed cron block.
bash "$TEMP_DIR/installer/install/install.sh" --activate-services > "$TEMP_DIR/full.log" 2>&1 ||
    { cat "$TEMP_DIR/full.log" >&2; exit 1; }
test "$(grep -Fxc '# BEGIN UKRAA PicoMuon' "$FAKE_HOST_ROOT/root-crontab")" = 1

for failure in FAKE_FAIL_VERIFY FAKE_FAIL_MERGE; do
    : > "$FAKE_SYSTEMCTL_LOG"
    if env "$failure=true" bash "$TEMP_DIR/installer/install/install.sh" \
        --activate-services > "$TEMP_DIR/full.log" 2>&1; then
        echo "Installer ignored $failure." >&2
        exit 1
    fi
    test ! -s "$FAKE_SYSTEMCTL_LOG"
done

export FAKE_CONFIG_REPORT=single
export FAKE_ACTIVE_UNITS=PicoMuon@Unit_2.service
export FAKE_ENABLED_UNITS=PicoMuon@Unit_2.service
: > "$FAKE_INSTALL_LOG"
if bash "$TEMP_DIR/installer/install/install.sh" > "$TEMP_DIR/full.log" 2>&1; then
    echo "Full installer accepted an unauthorized reversal." >&2
    exit 1
fi
test ! -s "$FAKE_INSTALL_LOG"
bash "$TEMP_DIR/installer/install/install.sh" --activate-services > "$TEMP_DIR/full.log" 2>&1 ||
    { cat "$TEMP_DIR/full.log" >&2; exit 1; }
grep -Fxq 'stop PicoMuon@Unit_2.service' "$FAKE_SYSTEMCTL_LOG"
grep -Fxq 'disable PicoMuon@Unit_2.service' "$FAKE_SYSTEMCTL_LOG"
grep -Fxq 'restart PicoMuon.service' "$FAKE_SYSTEMCTL_LOG"
cmp "$TEMP_DIR/raw-original" "$TEMP_DIR/installer/data/raw/Unit_2/events.txt"

echo "Service transition and installer preflight checks passed."
echo "Full installer mock checks passed: activation, reversal, cron, web and failure handling."
