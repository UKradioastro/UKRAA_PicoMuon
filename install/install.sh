#!/bin/bash

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer with sudo, for example: sudo bash install/install.sh" >&2
    exit 1
fi

PICOMUON_USER=${SUDO_USER:-}
if [ -z "$PICOMUON_USER" ] || [ "$PICOMUON_USER" = root ] || ! getent passwd "$PICOMUON_USER" >/dev/null; then
    echo "Cannot determine the non-root installing user. Run this script with sudo from that user's account." >&2
    exit 1
fi

PICOMUON_GROUP=$(id -gn "$PICOMUON_USER")
BASE_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)

escape_sed_replacement() {
    printf '%s' "$1" | sed 's/[\\&|]/\\&/g'
}

BASE_PATH_SED=$(escape_sed_replacement "$BASE_PATH")
BASE_PATH_SHELL=$(printf '%q' "$BASE_PATH")
BASE_PATH_SHELL_SED=$(escape_sed_replacement "$BASE_PATH_SHELL")

echo "Installing UKRAA PicoMuon under $BASE_PATH for user $PICOMUON_USER"
# Production named-mode installation stays disabled until service/archive migration is ready.
PICOMUON_BASE_PATH="$BASE_PATH" PYTHONPATH="$BASE_PATH/scripts" python3 -c \
    'from picomuon_common import get_usb_options; get_usb_options()'
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    apache2 \
    gnuplot-nox \
    gnuplot-doc \
    python3-pandas \
    python3-serial

# Move existing processed products into the flat data directory layout.
for category in 3month adc cpm day month week; do
    legacy_path="$BASE_PATH/data/processed/$category"
    flat_path="$BASE_PATH/data/$category"
    if [ -d "$legacy_path" ] && [ ! -e "$flat_path" ]; then
        mv "$legacy_path" "$flat_path"
    fi
done

install -d -o "$PICOMUON_USER" -g "$PICOMUON_GROUP" -m 0755 \
    "$BASE_PATH/config" \
    "$BASE_PATH/data/raw" \
    "$BASE_PATH/data/raw/rejected" \
    "$BASE_PATH/data/status" \
    "$BASE_PATH/data/raw/ACM0" \
    "$BASE_PATH/data/3month/ACM0" \
    "$BASE_PATH/data/adc/ACM0" \
    "$BASE_PATH/data/cpm/ACM0" \
    "$BASE_PATH/data/day/ACM0" \
    "$BASE_PATH/data/month/ACM0" \
    "$BASE_PATH/data/week/ACM0" \
    "$BASE_PATH/data/neutrons" \
    "$BASE_PATH/logfiles" \
    "$BASE_PATH/plots/adc/ACM0" \
    "$BASE_PATH/plots/cpm/ACM0" \
    "$BASE_PATH/plots/day/ACM0" \
    "$BASE_PATH/plots/freq/ACM0" \
    "$BASE_PATH/plots/month/ACM0" \
    "$BASE_PATH/plots/week/ACM0" \
    "$BASE_PATH/temp/yesterday" \
    "$BASE_PATH/temp/periods" \
    "$BASE_PATH/WWW/temp"

if [ ! -f "$BASE_PATH/config/USB.ini" ] && [ -f "$BASE_PATH/install/USB.ini.example" ]; then
    install -o "$PICOMUON_USER" -g "$PICOMUON_GROUP" -m 0644 \
        "$BASE_PATH/install/USB.ini.example" "$BASE_PATH/config/USB.ini"
elif [ -f "$BASE_PATH/config/USB.ini" ] && [ -f "$BASE_PATH/install/USB.ini.example" ]; then
    su -s /bin/bash "$PICOMUON_USER" -c \
        "python3 \"$BASE_PATH/scripts/MergeConfig.py\" \"$BASE_PATH/install/USB.ini.example\" \"$BASE_PATH/config/USB.ini\"" || true
fi

for name in legacy user; do
    if [ ! -f "$BASE_PATH/config/$name.ini" ]; then
        install -o "$PICOMUON_USER" -g "$PICOMUON_GROUP" -m 0600 \
            "$BASE_PATH/install/$name.ini.example" "$BASE_PATH/config/$name.ini"
    else
        su -s /bin/bash "$PICOMUON_USER" -c \
            "python3 \"$BASE_PATH/scripts/MergeConfig.py\" \"$BASE_PATH/install/$name.ini.example\" \"$BASE_PATH/config/$name.ini\""
    fi
done

touch "$BASE_PATH/logfiles/log-PicoMuon.txt" "$BASE_PATH/logfiles/log-error.txt"
chown "$PICOMUON_USER:$PICOMUON_GROUP" \
    "$BASE_PATH/logfiles/log-PicoMuon.txt" "$BASE_PATH/logfiles/log-error.txt"
chmod +x "$BASE_PATH"/scripts/*.sh

# Transition from legacy PicoMuonACM0.service if active
if systemctl is-active --quiet PicoMuonACM0.service 2>/dev/null; then
    echo "Stopping legacy PicoMuonACM0.service..."
    systemctl stop PicoMuonACM0.service || true
    systemctl disable PicoMuonACM0.service || true
    rm -f /etc/systemd/system/PicoMuonACM0.service
fi

SERVICE_TMP=$(mktemp --suffix=.service)
trap 'rm -f "$SERVICE_TMP"' EXIT
sed \
    -e "s|@PICOMUON_USER@|$(escape_sed_replacement "$PICOMUON_USER")|g" \
    -e "s|@PICOMUON_GROUP@|$(escape_sed_replacement "$PICOMUON_GROUP")|g" \
    -e "s|@PICOMUON_BASE_PATH@|$BASE_PATH_SED|g" \
    "$BASE_PATH/install/PicoMuon.service" > "$SERVICE_TMP"
systemd-analyze verify "$SERVICE_TMP"
install -o root -g root -m 0644 "$SERVICE_TMP" /etc/systemd/system/PicoMuon.service
systemctl daemon-reload
systemctl enable PicoMuon.service
systemctl restart PicoMuon.service

CRON_TMP_DIR=$(mktemp -d)
trap 'rm -f "$SERVICE_TMP"; rm -rf "$CRON_TMP_DIR"' EXIT
CURRENT_CRON="$CRON_TMP_DIR/current"
FILTERED_CRON="$CRON_TMP_DIR/filtered"
NEW_CRON="$CRON_TMP_DIR/new"
if ! crontab -u root -l > "$CURRENT_CRON" 2>/dev/null; then
    : > "$CURRENT_CRON"
fi
BEGIN_MARKERS=$(grep -Fxc '# BEGIN UKRAA PicoMuon' "$CURRENT_CRON" || true)
END_MARKERS=$(grep -Fxc '# END UKRAA PicoMuon' "$CURRENT_CRON" || true)
if [ "$BEGIN_MARKERS" -ne "$END_MARKERS" ] || [ "$BEGIN_MARKERS" -gt 1 ]; then
    echo "Root crontab has an incomplete or duplicated PicoMuon block; refusing to modify it." >&2
    exit 1
fi

# Remove this application's legacy unmarked entries before installing the
# managed block; leave unrelated root cron jobs untouched.
awk '
    /^# BEGIN UKRAA PicoMuon$/ { skip = 1; next }
    /^# END UKRAA PicoMuon$/ { skip = 0; next }
    skip { next }
    /UKRAA_PicoMuon\/scripts\/(GetDataNeutron|ProcessData(Cpm|Day|Week|Month|Adc)|plots|managelogfiles)\.py?/ { next }
    /UKRAA_PicoMuon\/scripts\/(plots|managelogfiles)\.sh/ { next }
    /UKRAA_PicoMuon\/scripts\/process(CPM|ADC|Data)\.sh([[:space:]"]|$)/ { next }
    /UKRAA_PicoMuon\/temp[[:space:]]+\/var\/www\/html/ { next }
    { print }
' "$CURRENT_CRON" > "$FILTERED_CRON"

sed \
    -e "s|@PICOMUON_BASE_PATH_SHELL@|$BASE_PATH_SHELL_SED|g" \
    "$BASE_PATH/install/crontab-PicoMuon.cron" > "$NEW_CRON"
cat "$FILTERED_CRON" "$NEW_CRON" > "$CRON_TMP_DIR/combined"
crontab -u root "$CRON_TMP_DIR/combined"

if [ -d "$BASE_PATH/WWW" ]; then
    install -d -o root -g root -m 0755 /var/www/html
    cp -a "$BASE_PATH/WWW/." /var/www/html/
    cp "$BASE_PATH/VERSION" /var/www/html/picomuon-version.txt
fi
systemctl enable --now apache2

echo "UKRAA PicoMuon installation completed."
echo "Daily processing runs at 01:15 local time; logs are in $BASE_PATH/logfiles."
