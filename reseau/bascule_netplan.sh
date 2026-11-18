#!/bin/bash
# bascule_netplan.sh v1.1 (18/11/2026, GO S.S. 19h02) — OPTI-MIST SOLUTIONS
# v1.1 : COMPTEUR DE DONNÉES DU SECOURS. À chaque passage (2 min), les octets reçus + envoyés par l'interface Wi-Fi depuis le
#   passage précédent sont ajoutés au compteur du jour et du mois quand le mode est « secours » (forfait 4G). Fichiers :
#   /var/lib/opti-mist/secours_octets_AAAA-MM-JJ et secours_octets_AAAA-MM (lus aussi par le collecteur Felicity v1.5,
#   qui les envoie au tableau de bord : alerte du Veilleur au passage sur le secours). « etat » affiche Mo du jour et du mois.
# v1.0 (18/11/2026, GO S.S. 11h46)
# Version de bascule_wifi.sh pour les boîtiers dont le Wi-Fi est géré par netplan + systemd-networkd
# (pas de NetworkManager, cas d'OPTI-061 constaté le 18/11 : « nmcli: command not found »).
# Bascule le Wi-Fi du boîtier entre le réseau PRINCIPAL et le réseau de SECOURS selon l'accès internet RÉEL.
# Règles : 3 échecs de suite (≈ 6 min) sur le principal → secours ; sur le secours, essai de retour toutes les 15 min
#          (si le principal n'a toujours pas internet après 45 s, retour immédiat sur le secours).
# Fonctionnement : deux fichiers netplan complets préparés à l'installation (mots de passe inclus, root 600) :
#   /etc/opti-mist/netplan-principal.yaml  et  /etc/opti-mist/netplan-secours.yaml
#   Le fichier actif (CIBLE, dans /etc/netplan) est remplacé par l'un ou l'autre, puis « netplan apply ».
# Aucun mot de passe dans ce script. Lecture seule vis-à-vis des équipements du site.
# Configuration : /etc/opti-mist/netplan-bascule.conf → CIBLE="/etc/netplan/30-wifi-maison.yaml"
# Usage : bascule_netplan.sh            (passage normal, lancé toutes les 2 min par bascule-netplan.timer)
#         bascule_netplan.sh etat       (affiche le mode actif et le test internet)
#         bascule_netplan.sh principal|secours   (forçage manuel ; le passage suivant reprend la règle normale)
set -u
CONF=/etc/opti-mist/netplan-bascule.conf
[ -r "$CONF" ] && . "$CONF"
CIBLE="${CIBLE:-}"
P=/etc/opti-mist/netplan-principal.yaml; S=/etc/opti-mist/netplan-secours.yaml
D=/var/lib/opti-mist; mkdir -p "$D"
MODE="$D/netplan_mode"; ECHECS="$D/netplan_echecs"; ESSAI="$D/netplan_essai"
log() { logger -t bascule_netplan "$*"; echo "$(date '+%F %T') $*"; }
[ -n "$CIBLE" ] && [ -r "$P" ] && [ -r "$S" ] || { log "configuration incomplète ($CONF, $P, $S) : rien à faire"; exit 0; }
exec 9>"$D/netplan.verrou"; flock -n 9 || exit 0   # jamais deux passages en même temps

internet() {
  curl -s -o /dev/null -m 15 -w '%{http_code}' http://connectivitycheck.gstatic.com/generate_204 2>/dev/null | grep -q 204 && return 0
  ping -c 2 -W 5 1.1.1.1 >/dev/null 2>&1
}
appliquer() {  # $1 = principal | secours
  local f="$P"; [ "$1" = secours ] && f="$S"
  install -m 600 -o root -g root "$f" "$CIBLE" && netplan apply >/dev/null 2>&1
  echo "$1" > "$MODE"
}
mode=$(cat "$MODE" 2>/dev/null || echo principal)

# v1.1 — compteur de données du secours (interface Wi-Fi = première interface qui a un dossier « wireless »)
IFACE=$(for i in /sys/class/net/*; do [ -d "$i/wireless" ] && basename "$i" && break; done)
compter() {
  [ -n "$IFACE" ] || return 0
  local rx tx tot prec delta j m
  rx=$(cat "/sys/class/net/$IFACE/statistics/rx_bytes" 2>/dev/null || echo 0)
  tx=$(cat "/sys/class/net/$IFACE/statistics/tx_bytes" 2>/dev/null || echo 0)
  tot=$((rx + tx)); prec=$(cat "$D/octets_dernier" 2>/dev/null || echo "$tot")
  delta=$((tot - prec)); [ "$delta" -lt 0 ] && delta=$tot   # compteur remis à zéro (redémarrage)
  echo "$tot" > "$D/octets_dernier"
  [ "$mode" = secours ] || return 0
  j="$D/secours_octets_$(date +%F)"; m="$D/secours_octets_$(date +%Y-%m)"
  echo $(( $(cat "$j" 2>/dev/null || echo 0) + delta )) > "$j"
  echo $(( $(cat "$m" 2>/dev/null || echo 0) + delta )) > "$m"
  find "$D" -maxdepth 1 -name 'secours_octets_????-??-??' -mtime +40 -delete 2>/dev/null
}
mo() { echo $(( $(cat "$1" 2>/dev/null || echo 0) / 1048576 )); }

case "${1:-}" in
  etat) internet && i=oui || i=non
        echo "mode=$mode internet=$i echecs=$(cat "$ECHECS" 2>/dev/null || echo 0) secours_mo_jour=$(mo "$D/secours_octets_$(date +%F)") secours_mo_mois=$(mo "$D/secours_octets_$(date +%Y-%m)")"; exit 0 ;;
  principal|secours) log "forçage manuel : $1"; appliquer "$1"; echo 0 > "$ECHECS"; date +%s > "$ESSAI"; exit 0 ;;
esac

compter
if [ "$mode" != secours ]; then
  if internet; then echo 0 > "$ECHECS"; exit 0; fi
  n=$(( $(cat "$ECHECS" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$ECHECS"
  [ "$n" -lt 3 ] && { log "internet absent sur le principal ($n/3)"; exit 0; }
  log "internet absent 3 fois de suite : bascule sur le secours"
  appliquer secours; sleep 45
  if internet; then log "en ligne sur le secours"; else log "ECHEC : pas d'internet non plus sur le secours (on y reste, nouvel essai du principal dans 15 min)"; fi
  echo 0 > "$ECHECS"; date +%s > "$ESSAI"
else
  now=$(date +%s); last=$(cat "$ESSAI" 2>/dev/null || echo 0)
  if [ $((now - last)) -lt 900 ]; then internet || log "pas d'internet non plus sur le secours"; exit 0; fi
  date +%s > "$ESSAI"
  appliquer principal; sleep 45
  if internet; then log "internet revenu : retour sur le principal"; echo 0 > "$ECHECS"; exit 0; fi
  log "principal toujours sans internet : retour sur le secours"
  appliquer secours
fi
