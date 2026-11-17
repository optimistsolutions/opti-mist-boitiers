#!/bin/bash
# install_bascule_wifi.sh v1.0 (17/11/2026) — OPTI-MIST SOLUTIONS — à lancer avec sudo sur le boîtier, dans le dossier
# contenant bascule_wifi.sh. Usage : sudo bash install_bascule_wifi.sh "<nom de la connexion Wi-Fi principale>"
set -e
P="${1:-}"; [ -z "$P" ] && { echo "Usage : sudo bash install_bascule_wifi.sh \"<connexion principale>\""; nmcli -t -f NAME,TYPE con show; exit 1; }
command -v nmcli >/dev/null || { echo "NetworkManager absent : arrêt, prévenir Claude"; exit 1; }
nmcli -t -f NAME con show | grep -Fxq "$P" || { echo "Connexion « $P » inconnue. Connexions présentes :"; nmcli -t -f NAME,TYPE con show; exit 1; }
nmcli -t -f NAME con show | grep -Fxq "SECOURS-4G" || { echo "Déclarez d'abord le réseau de secours (étape C de la check-list)"; exit 1; }
install -m 755 bascule_wifi.sh /usr/local/bin/bascule_wifi.sh
mkdir -p /etc/opti-mist; printf 'PRINCIPAL="%s"\nSECOURS="SECOURS-4G"\n' "$P" > /etc/opti-mist/wifi.conf
nmcli con mod "$P" connection.autoconnect yes connection.autoconnect-priority 50
nmcli con mod SECOURS-4G connection.autoconnect yes connection.autoconnect-priority 10
cat > /etc/systemd/system/bascule-wifi.service <<'U'
[Unit]
Description=OPTI-MIST SOLUTIONS - bascule Wi-Fi principal / secours
[Service]
Type=oneshot
ExecStart=/usr/local/bin/bascule_wifi.sh
U
cat > /etc/systemd/system/bascule-wifi.timer <<'U'
[Unit]
Description=OPTI-MIST SOLUTIONS - test internet toutes les 2 min
[Timer]
OnBootSec=3min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
U
systemctl daemon-reload && systemctl enable --now bascule-wifi.timer
echo "OK : bascule Wi-Fi installée (principal = $P, secours = SECOURS-4G). Journal : journalctl -t bascule_wifi -n 20"
