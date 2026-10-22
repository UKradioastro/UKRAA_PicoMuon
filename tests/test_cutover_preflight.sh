#!/bin/bash

set -euo pipefail
trap 'printf "Test failed at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

REPO_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
mkdir -p "$TEMP_DIR/bin" "$TEMP_DIR/evidence"
export EVIDENCE="$TEMP_DIR/evidence"
export SYSTEMCTL_LOG="$TEMP_DIR/systemctl.log"
export PATH="$TEMP_DIR/bin:$PATH"

# Run the real capture block without any production prechecks or host access.
awk '/^\[\[ "\$\(id -un\)"/ { exit } { print }' \
    "$REPO_PATH/scripts/CollectUnit1CutoverPreflight.sh" > "$TEMP_DIR/capture.sh"
printf 'EVIDENCE=%q\n' "$EVIDENCE" >> "$TEMP_DIR/capture.sh"
awk '/^mapfile -t UNIT_NAMES/ { copying=1 }
     /^capture_crontab pi / { exit }
     copying { print }' \
    "$REPO_PATH/scripts/CollectUnit1CutoverPreflight.sh" >> "$TEMP_DIR/capture.sh"

cat > "$TEMP_DIR/bin/systemctl" <<'MOCK'
#!/bin/bash
set -euo pipefail
printf '%s\n' "$*" >> "$SYSTEMCTL_LOG"
action=$1
unit=$2
if [[ "$action" == show && "$unit" == *@.service ]]; then
    echo "Cannot query runtime properties of a template" >&2
    exit 1
fi
if [[ "$action:$unit" == "${FAIL_QUERY:-}" ]]; then
    echo "Injected systemctl failure" >&2
    exit 7
fi
case "$action" in
    show) printf 'Id=%s\nActiveState=active\n' "$unit" ;;
    cat) printf '# %s\n[Service]\nExecStart=/test/collector\n' "$unit" ;;
    *) exit 2 ;;
esac
MOCK
chmod +x "$TEMP_DIR/bin/systemctl"
printf 'PicoMuon.service loaded active running\nPicoMuon@Unit_1.service loaded inactive dead\n' \
    > "$EVIDENCE/services-loaded.txt"
printf 'PicoMuon.service enabled\nPicoMuon@.service disabled\nPicoMuon@Unit_1.service disabled\n' \
    > "$EVIDENCE/services-installed.txt"

bash "$TEMP_DIR/capture.sh"
printf 'PicoMuon.service\nPicoMuon@.service\nPicoMuon@Unit_1.service\n' \
    > "$TEMP_DIR/expected-names.txt"
cmp "$TEMP_DIR/expected-names.txt" "$EVIDENCE/picom_unit_names.txt"
[[ -f "$EVIDENCE/PicoMuon@.service.properties-not-applicable.txt" ]]
[[ ! -e "$EVIDENCE/PicoMuon@.service.properties.txt" ]]
[[ $(wc -l < "$SYSTEMCTL_LOG") -eq 5 ]]
grep -Fxq 'cat PicoMuon@.service' "$SYSTEMCTL_LOG"
for unit in PicoMuon.service PicoMuon@Unit_1.service; do
    grep -Fxq "Id=$unit" "$EVIDENCE/$unit.properties.txt"
    [[ $(cat "$EVIDENCE/$unit.properties.txt.exit") == 0 ]]
done
for unit in PicoMuon.service PicoMuon@.service PicoMuon@Unit_1.service; do
    [[ $(cat "$EVIDENCE/$unit.unit.txt.exit") == 0 ]]
done

for query in show:PicoMuon.service cat:PicoMuon@.service; do
    if FAIL_QUERY="$query" bash "$TEMP_DIR/capture.sh" > "$TEMP_DIR/failure.log" 2>&1; then
        echo "Preflight unexpectedly passed after $query failed" >&2
        exit 1
    fi
    grep -Fq 'PREFLIGHT FAILED:' "$TEMP_DIR/failure.log"
    if [[ "$query" == show:* ]]; then
        destination="$EVIDENCE/PicoMuon.service.properties.txt"
    else
        destination="$EVIDENCE/PicoMuon@.service.unit.txt"
    fi
    [[ $(cat "$destination.exit") == 7 ]]
    grep -Fxq 'Injected systemctl failure' "$destination.stderr"
done

echo "Cutover preflight service capture passed: templates, instances, and explicit failures."
