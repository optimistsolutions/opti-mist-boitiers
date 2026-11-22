#!/bin/sh
# OPTI-MIST SOLUTIONS - Passage de la mise a jour automatique a 7h30 ET 13h (v1.0, 22/11/2026, demande S.S.)
# Pour les boitiers deja equipes (OPTI-061, OPTI-087). A lancer une seule fois, en root :  sudo sh maj_horaire_matin.sh
# Ne touche qu'a l'horaire de recherche ; maj_auto.py, les approbations et les fichiers restent identiques.
set -e
[ "$(id -u)" = "0" ] || { echo "Lancer en root"; exit 1; }
T=/etc/systemd/system/opti-maj.timer
[ -f "$T" ] || { echo "Mise a jour automatique absente ($T) : rien a faire"; exit 1; }
cp "$T" "$T.precedent"
cat > "$T" <<'EOS'
[Unit]
Description=OPTI-MIST SOLUTIONS - recherche de mise a jour (vers 7h30 et 13h, plus 10 min apres demarrage)
[Timer]
OnBootSec=10min
OnCalendar=*-*-* 07:30:00
OnCalendar=*-*-* 13:00:00
RandomizedDelaySec=15min
Persistent=true
[Install]
WantedBy=timers.target
EOS
systemctl daemon-reload
systemctl restart opti-maj.timer
systemctl list-timers opti-maj.timer --no-pager | head -3
echo "OK : prochaines recherches vers 7h30 et 13h. Retour : cp $T.precedent $T ; systemctl daemon-reload"
