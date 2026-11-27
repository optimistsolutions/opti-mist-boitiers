#!/bin/sh
# OPTI-MIST SOLUTIONS - Installation du LECTEUR UNIVERSEL (MPP / Voltronic, Felicity, SRNE ; lecture seule) - v1.3 du 27/11/2026
# v1.3 (27/11 11h20, banc OPTI-108, M) : la carte H6 refuse un chien de garde de 30 s (maximum 16 s, sunxi-wdt) ;
#   systemd l'ignorait ("Failed to set watchdog hardware timeout to 30s") et la carte restait figee apres un blocage.
#   Reglage a 10 s (redemarrage seul en 19 s, M) et controle reel dans le journal du systeme.
# v1.2 (27/11, veille forums Armbian / Solar Assistant, checking etendu GO S.S. 26/11 23h52) : boitier FIGE pour la duree
#   (pose sans retour) : mises a jour automatiques du systeme coupees et noyau bloque (une mise a jour a deja empeche des
#   Orange Pi 3 LTS de redemarrer, forums) ; processeur plafonne a 1,2 GHz (chaleur en coffret 55-60 C : un H6 vers 80-90 C
#   ralentit et gele, forums) ; Bluetooth coupe.
# v1.1 (27/11, GO S.S. 26/11 22h50 - boitiers poses le 28/11, sans retour au banc) : mpp_collect v1.7 requis ;
#   minuteur CHAQUE MINUTE (la cadence reelle se regle dans envoi.conf : mesure_s, complet_min) ; CHIEN DE GARDE
#   materiel (systemd le nourrit toutes les 15 s ; noyau bloque -> redemarrage en 30 s) ; noyau en panne ou erreur
#   grave -> redemarrage en 10 s ; journal systeme plafonne a 50 Mo (memoire eMMC) ; nouvelles commandes
#   opti061 evenements | sante | complet.
# GO S.S. 25/11/2026 : un seul boitier universel pour tous les sites, mis a jour a distance.
# Lancer en root depuis le dossier qui contient : mpp_collect.py, mpp_probe.py, felicity_collect.py
#   (et, pour la mise a jour automatique : maj_auto.py + install_maj_auto.sh v1.3).
#   sh install_universel.sh OPTI-046            nouveau boitier (envoi.conf cree, detection automatique des prises)
#   sh install_universel.sh OPTI-111 1,2,3      nouveau boitier, Felicity en parallele sur un cable (adresses Modbus)
#   sh install_universel.sh OPTI-111            boitier Felicity deja installe : passage au lecteur universel
#                                               (envoi.conf, jeton et donnees gardes ; l'ancien releve Felicity est arrete)
# url / direct_url / direct_jeton ne sont JAMAIS ecrits ici : S.S. les colle depuis le coffre dans /etc/opti061/envoi.conf.
# Retour arriere : sh install_universel.sh --retour  (rallume le releve Felicity seul, arrete le lecteur universel).
set -e
[ "$(id -u)" = "0" ] || { echo "Lancer en root"; exit 1; }
ICI="$(cd "$(dirname "$0")" && pwd)"
CONF=/etc/opti061/envoi.conf

if [ "$1" = "--retour" ]; then
  systemctl disable --now opti-mpp.timer 2>/dev/null || true
  [ -f /etc/systemd/system/opti061-felicity.timer ] || { echo "Pas de releve Felicity a rallumer"; exit 1; }
  systemctl enable --now opti061-felicity.timer
  [ -f /usr/local/bin/opti061.felicity ] && cp /usr/local/bin/opti061.felicity /usr/local/bin/opti061
  echo "Retour fait : releve Felicity seul rallume."
  exit 0
fi

CODE="$1"; ESCL="$2"
case "$CODE" in OPTI-[0-9][0-9][0-9]) ;; *) echo "Usage : sh install_universel.sh OPTI-XXX [adresses Felicity ex. 1,2,3] | --retour"; exit 1 ;; esac
case "$ESCL" in ""|*[!0-9,]*) [ -z "$ESCL" ] || { echo "Adresses invalides : $ESCL (ex. 1,2,3)"; exit 1; } ;; esac
for f in mpp_collect.py mpp_probe.py felicity_collect.py; do [ -f "$ICI/$f" ] || { echo "$f manquant"; exit 1; }; done
grep -q 'VERSION = "mpp 1\.[7-9]' "$ICI/mpp_collect.py" || { echo "mpp_collect.py v1.7 ou plus requis"; exit 1; }
grep -q 'def ecrire_json' "$ICI/felicity_collect.py" || { echo "felicity_collect.py v1.8 ou plus requis"; exit 1; }

install -d -m 755 /opt/opti061 && install -d -m 750 /var/lib/opti061 /etc/opti061
if [ -f "$CONF" ]; then
  ANCIEN=$(sed -n 's/^code *= *//p' "$CONF" | head -1)
  [ "$ANCIEN" = "$CODE" ] || { echo "envoi.conf est au code $ANCIEN, pas $CODE : arret (rien n'est change)"; exit 1; }
  grep -q '^convertisseurs *=' "$CONF" || printf "convertisseurs = auto\n" >> "$CONF"
  [ -z "$ESCL" ] || grep -q '^esclaves *=' "$CONF" || printf "esclaves = %s\n" "$ESCL" >> "$CONF"
  chmod 600 "$CONF"                                  # v1.2
  echo "envoi.conf garde ($CODE) ; detection automatique des prises activee"
else
  cat > "$CONF" <<EOC
# OPTI-MIST SOLUTIONS - envoi du boitier $CODE (lecteur universel, cree le $(date +%d/%m/%Y))
code = $CODE
convertisseurs = auto
jours_conserves = 730
rattrapage_jours = 90
periode_min = 60
alertes = non
# A coller depuis le coffre par S.S. (jamais dans un message, un e-mail ou GitHub) :
url =
direct_url =
direct_jeton =
EOC
  [ -z "$ESCL" ] || printf "esclaves = %s\n" "$ESCL" >> "$CONF"
  chmod 600 "$CONF"
  echo "envoi.conf cree pour $CODE (url et jeton a coller depuis le coffre)"
fi

for f in mpp_collect.py mpp_probe.py felicity_collect.py; do install -m 755 "$ICI/$f" /opt/opti061/$f; done

# un seul lecteur sur les cables : l'ancien releve Felicity est arrete (garde pour le retour arriere)
systemctl disable --now opti061-felicity.timer 2>/dev/null || true
[ -f /usr/local/bin/opti061 ] && [ ! -f /usr/local/bin/opti061.felicity ] && cp /usr/local/bin/opti061 /usr/local/bin/opti061.felicity

cat > /etc/systemd/system/opti-mpp.service <<EOF
[Unit]
Description=OPTI-MIST SOLUTIONS - releve universel $CODE
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/opti061/mpp_collect.py
TimeoutStartSec=170
Nice=5
EOF
cat > /etc/systemd/system/opti-mpp.timer <<'EOF'
[Unit]
Description=OPTI-MIST SOLUTIONS - mesure universelle chaque minute (releve complet toutes les 5 min)
[Timer]
OnBootSec=60
OnCalendar=*:*:00
AccuracySec=1s
Persistent=false
[Install]
WantedBy=timers.target
EOF
cat > /usr/local/bin/opti061 <<'EOF'
#!/bin/sh
case "$1" in
  releve)   /usr/bin/python3 /opt/opti061/mpp_collect.py ;;
  essai)    /usr/bin/python3 /opt/opti061/mpp_collect.py --sans-envoi ;;
  complet)  /usr/bin/python3 /opt/opti061/mpp_collect.py --complet ;;
  evenements) /usr/bin/python3 /opt/opti061/mpp_collect.py --evenements ;;
  sante)    /usr/bin/python3 /opt/opti061/mpp_collect.py --sante ;;
  detecter) /usr/bin/python3 /opt/opti061/mpp_collect.py --detecter ;;
  dernier)  /usr/bin/python3 /opt/opti061/mpp_collect.py --show ;;
  journal)  journalctl -u opti-mpp.service -n 30 --no-pager ;;
  etat)     systemctl list-timers opti-mpp.timer --no-pager ;;
  *) echo "Usage : opti061 releve | essai (sans envoi) | complet | detecter | dernier | evenements | sante | journal | etat" ;;
esac
EOF
chmod 755 /usr/local/bin/opti061
ln -sf /usr/local/bin/opti061 /usr/local/bin/opti
H=$(hostname | tr -d '-'); case "$H" in opti[0-9][0-9][0-9]) ln -sf /usr/local/bin/opti061 /usr/local/bin/$H ;; esac   # commande de la banniere (ex. opti111)

install -d /etc/opti087
[ -f /etc/opti087/opti087.conf ] || printf "[site]\ncode_site = %s\n" "$CODE" > /etc/opti087/opti087.conf
timedatectl set-timezone Africa/Ouagadougou 2>/dev/null || true
timedatectl set-ntp true 2>/dev/null || true

# v1.1 : chien de garde materiel, redemarrage sur panne du noyau, journal plafonne
if [ -e /dev/watchdog ]; then
  install -d /etc/systemd/system.conf.d
  printf "[Manager]\nRuntimeWatchdogSec=10\nRebootWatchdogSec=2min\n" > /etc/systemd/system.conf.d/opti-watchdog.conf
  systemctl daemon-reexec
  sleep 2
  if journalctl -b --no-pager 2>/dev/null | grep -q "Watchdog running with a hardware timeout"; then
    echo "Chien de garde materiel actif (10 s, confirme par le systeme)"
  else
    echo "ATTENTION : chien de garde materiel NON confirme par le systeme"
  fi
else
  echo "ATTENTION : /dev/watchdog absent - chien de garde materiel NON actif"
fi
# v1.2 : systeme fige (aucune mise a jour automatique, noyau bloque) ; processeur plafonne ; Bluetooth coupe
systemctl disable --now unattended-upgrades.service apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
for p in $(dpkg-query -W -f='${Package}\n' 2>/dev/null | grep -E '^(linux-image|linux-dtb|linux-u-boot|armbian-firmware|armbian-bsp)'); do
  apt-mark hold "$p" >/dev/null 2>&1 || true
done
echo "Mises a jour automatiques coupees ; noyau bloque ($(apt-mark showhold 2>/dev/null | wc -l) paquet(s))"
if [ -d /sys/devices/system/cpu/cpu0/cpufreq ]; then
  printf 'ENABLE=true\nGOVERNOR=schedutil\nMIN_SPEED=480000\nMAX_SPEED=1200000\n' > /etc/default/cpufrequtils
  for c in /sys/devices/system/cpu/cpu*/cpufreq; do echo 1200000 > $c/scaling_max_freq 2>/dev/null || true; done
  echo "Processeur plafonne a 1,2 GHz : $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null)"
fi
systemctl disable --now bluetooth.service 2>/dev/null || true
printf "kernel.panic = 10\nkernel.panic_on_oops = 1\n" > /etc/sysctl.d/90-opti.conf
sysctl -q -p /etc/sysctl.d/90-opti.conf || true
install -d /etc/systemd/journald.conf.d
printf "[Journal]\nSystemMaxUse=50M\n" > /etc/systemd/journald.conf.d/opti.conf
systemctl restart systemd-journald 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now opti-mpp.timer

if [ -f "$ICI/install_maj_auto.sh" ] && [ -f "$ICI/maj_auto.py" ]; then
  sh "$ICI/install_maj_auto.sh" "$CODE"
else
  echo "(maj_auto.py ou install_maj_auto.sh absent : mise a jour automatique non (re)installee)"
fi
echo "Lecteur universel installe pour $CODE. Prises vues :"
opti061 detecter || true
echo "Releve d'essai (sans envoi) :"
opti061 essai || true
