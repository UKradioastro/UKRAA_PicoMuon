#!/bin/bash

set -euo pipefail

BASE_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
FILTER=$(sed -n "/^awk '/,/^' /p" "$BASE_PATH/install/install.sh" | sed '1d;$d')
RESULT=$(awk "$FILTER" <<'CRON'
0 2 * * * /opt/unrelated/backup.sh
30 0 * * * su pi -c "sudo bash /home/pi/UKRAA_PicoMuon/scripts/processCPM.sh >> old.log"
15 3 * * * su pi -c "sudo bash /home/pi/UKRAA_PicoMuon/scripts/processADC.sh >> old.log"
30 4 * * * su pi -c "sudo bash /home/pi/UKRAA_PicoMuon/scripts/processData.sh >> old.log"
# BEGIN UKRAA PicoMuon
15 1 * * * /bin/bash /home/pi/UKRAA_PicoMuon/scripts/processData.sh
# END UKRAA PicoMuon
CRON
)

if [ "$RESULT" != '0 2 * * * /opt/unrelated/backup.sh' ]; then
    printf 'Unexpected filtered crontab:\n%s\n' "$RESULT" >&2
    exit 1
fi
echo "Cron filtering passed: legacy wrappers removed; unrelated job preserved."
