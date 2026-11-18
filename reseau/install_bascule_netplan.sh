#!/bin/bash
# install_bascule_netplan.sh v1.0 (18/11/2026) — OPTI-MIST SOLUTIONS — à lancer avec sudo sur le boîtier,
# dans le dossier contenant bascule_netplan.sh.
# Usage : sudo bash install_bascule_netplan.sh <fichier netplan principal> <fichier netplan secours> <fichier actif>
# Cas OPTI-061 (18/11) : le boîtier est déjà sur le secours ; la sauvegarde du réglage maison est /root/maison.bak :
#   sudo bash install_bascule_netplan.sh /root/maison.bak /etc/netplan/30-wifi-maison.yaml /etc/netplan/30-wifi-maison.yaml
# Aucun mot de passe n'est saisi ni affiché : les deux fichiers netplan existent déjà sur le boîtier.
set -e
[ "$(id -u)" = 0 ] || { echo "Lancer avec sudo"; exit 1; }
PRIN="${1:-}"; SEC="${2:-}"; CIBLE="${3:-}"
[ -r "$PRIN" ] && [ -r "$SEC" ] && [ -n "$CIBLE" ] || { echo "Usage : sudo bash install_bascule_netplan.sh <principal.yaml> <secours.yaml> <fichier actif dans /etc/netplan>"; exit 1; }
command -v netplan >/dev/null || { echo "netplan absent : arrêt, prévenir Claude"; exit 1; }
grep -q 'access-points' "$PRIN" && grep -q 'access-points' "$SEC" || { echo "Un des fichiers n'est pas un réglage Wi-Fi netplan : arrêt"; exit 1; }
cmp -s "$PRIN" "$SEC" && { echo "Les fichiers principal et secours sont identiques : arrêt"; exit 1; }
install -d -m 700 /etc/opti-mist /var/lib/opti-mist
install -m 600 -o root -g root "$PRIN" /etc/opti-mist/netplan-principal.yaml
install -m 600 -o root -g root "$SEC"  /etc/opti-mist/netplan-secours.yaml
printf 'CIBLE="%s"\n' "$CIBLE" > /etc/opti-mist/netplan-bascule.conf
# Mode de départ : celui du fichier actif aujourd'hui
if cmp -s "$CIBLE" /etc/opti-mist/netplan-secours.yaml; then echo secours > /var/lib/opti-mist/netplan_mode; date +%s > /var/lib/opti-mist/netplan_essai
else echo principal > /var/lib/opti-mist/netplan_mode; fi
echo 0 > /var/lib/opti-mist/netplan_echecs
install -m 755 bascule_netplan.sh /usr/local/bin/bascule_netplan.sh
cat > /etc/systemd/system/bascule-netplan.service <<'U'
[Unit]
Description=OPTI-MIST SOLUTIONS - bascule Wi-Fi principal / secours (netplan)
[Service]
Type=oneshot
ExecStart=/usr/local/bin/bascule_netplan.sh
TimeoutStartSec=180
U
cat > /etc/systemd/system/bascule-netplan.timer <<'U'
[Unit]
Description=OPTI-MIST SOLUTIONS - test internet toutes les 2 min
[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
U
systemctl daemon-reload && systemctl enable --now bascule-netplan.timer >/dev/null
echo "Bascule installée. Mode actuel : $(cat /var/lib/opti-mist/netplan_mode)"
/usr/local/bin/bascule_netplan.sh etat
echo "Journal : journalctl -t bascule_netplan -n 20"
