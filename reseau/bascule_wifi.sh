#!/bin/bash
# bascule_wifi.sh v1.1 (17/11/2026) — OPTI-MIST SOLUTIONS
# v1.1 (17/11 10h53) : principal en câble (Ethernet) possible, cas OPTI-087 : la connexion principale est coupée
#   avant d'activer le secours (sinon la route par le câble reste prioritaire), et le secours est coupé au retour.
# v1.0 (17/11 10h21, GO S.S.) : 1re version, Wi-Fi principal et Wi-Fi de secours.
# Bascule le Wi-Fi du boîtier entre le réseau PRINCIPAL et le réseau de SECOURS (routeur 4G d'un autre opérateur)
# selon l'accès internet RÉEL, pas seulement la présence du Wi-Fi.
# Pourquoi : le 16/11, la fibre du bureau est tombée ; le Wi-Fi de la maison restait allumé, donc NetworkManager
# ne voyait aucune panne et ne basculait pas. Ce script teste internet et bascule lui-même.
# Règles : 3 échecs de suite (≈ 6 min) sur le principal → secours ; sur le secours, essai de retour toutes les 15 min.
# Lecture seule vis-à-vis des équipements du site. Aucun mot de passe ici : les réseaux sont déclarés dans NetworkManager.
# Configuration : /etc/opti-mist/wifi.conf  →  PRINCIPAL="<nom de la connexion principale>"  SECOURS="SECOURS-4G"
set -u
CONF=/etc/opti-mist/wifi.conf
[ -r "$CONF" ] && . "$CONF"
PRINCIPAL="${PRINCIPAL:-}"; SECOURS="${SECOURS:-SECOURS-4G}"
D=/var/lib/opti-mist; mkdir -p "$D"
ECHECS="$D/bascule_echecs"; DEPUIS="$D/bascule_essai"
log() { logger -t bascule_wifi "$*"; echo "$(date '+%F %T') $*"; }
[ -z "$PRINCIPAL" ] && { log "PRINCIPAL non défini dans $CONF : rien à faire"; exit 0; }
nmcli -t -f NAME con show | grep -Fxq "$SECOURS" || { log "connexion $SECOURS absente : rien à faire"; exit 0; }
internet() {
  curl -s -o /dev/null -m 15 -w '%{http_code}' https://clients3.google.com/generate_204 2>/dev/null | grep -q 204 && return 0
  ping -c 2 -W 5 1.1.1.1 >/dev/null 2>&1
}
actif=$(nmcli -t -f NAME con show --active | grep -Fx -e "$PRINCIPAL" -e "$SECOURS" | head -1)
if [ "$actif" != "$SECOURS" ]; then
  if internet; then echo 0 > "$ECHECS"; exit 0; fi
  n=$(( $(cat "$ECHECS" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$ECHECS"
  [ "$n" -lt 3 ] && { log "internet absent sur ${actif:-aucune connexion} ($n/3)"; exit 0; }
  log "internet absent 3 fois de suite : bascule sur $SECOURS"
  nmcli con down "$PRINCIPAL" >/dev/null 2>&1   # v1.1 : indispensable si le principal est un câble
  if nmcli con up "$SECOURS" >/dev/null 2>&1 && sleep 15 && internet; then log "en ligne sur $SECOURS"; else log "ECHEC sur $SECOURS : retour sur $PRINCIPAL"; nmcli con down "$SECOURS" >/dev/null 2>&1; nmcli con up "$PRINCIPAL" >/dev/null 2>&1; fi
  echo 0 > "$ECHECS"; date +%s > "$DEPUIS"
else
  now=$(date +%s); last=$(cat "$DEPUIS" 2>/dev/null || echo 0)
  if [ $((now - last)) -lt 900 ]; then internet || log "pas d'internet non plus sur $SECOURS"; exit 0; fi
  date +%s > "$DEPUIS"
  nmcli con down "$SECOURS" >/dev/null 2>&1   # v1.1
  if nmcli con up "$PRINCIPAL" >/dev/null 2>&1 && sleep 20 && internet; then log "internet revenu : retour sur $PRINCIPAL"; exit 0; fi
  log "principal toujours sans internet : maintien sur $SECOURS"; nmcli con down "$PRINCIPAL" >/dev/null 2>&1; nmcli con up "$SECOURS" >/dev/null 2>&1
fi
