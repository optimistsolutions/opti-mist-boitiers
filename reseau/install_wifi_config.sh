#!/bin/sh
# OPTI-MIST SOLUTIONS - Installation du Wi-Fi de configuration du boitier - v1.0j du 24/11/2026 (v1.0 du 20/11, GO S.S. 20/11 ; v1.0f : minuterie de consigne ; v1.0g : info ; v1.0h : code ; v1.0i : essai interrompu retabli, adresse sur la carte ; v1.0j : ecritures forcees sur le disque)
# Lancer en root depuis le dossier qui contient wifi_config.py :   sh install_wifi_config.sh
# Le boitier doit avoir internet (cable ou Wi-Fi) pour telecharger hostapd et dnsmasq.
# Aucun mot de passe dans ce script : celui du Wi-Fi de configuration est tire au hasard sur le boitier
# (/etc/opti061/wifi_config.secret, root 600) et s'affiche avec « opti-wifi etiquette », a l'ecran seulement.
set -e
[ "$(id -u)" = "0" ] || { echo "Lancer en root"; exit 1; }
ICI="$(cd "$(dirname "$0")" && pwd)"
[ -f "$ICI/wifi_config.py" ] || { echo "wifi_config.py manquant"; exit 1; }
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$ICI/wifi_config.py"

echo "1/4 Paquets hostapd et dnsmasq"
# policy-rc.d : empeche apt de demarrer dnsmasq a l'installation (il entrerait en conflit sur le port 53)
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod 755 /usr/sbin/policy-rc.d
apt-get update -q >/dev/null || true
DEBIAN_FRONTEND=noninteractive apt-get install -y hostapd dnsmasq >/dev/null || { rm -f /usr/sbin/policy-rc.d; exit 1; }
rm -f /usr/sbin/policy-rc.d
# Ils ne doivent JAMAIS tourner seuls : seul wifi_config.py les lance, et seulement hors ligne.
systemctl disable --now dnsmasq >/dev/null 2>&1 || true
systemctl disable --now hostapd >/dev/null 2>&1 || true
systemctl mask hostapd dnsmasq >/dev/null 2>&1 || true

echo "2/4 Programme"
install -d -m 755 /opt/opti061 && install -d -m 750 /etc/opti061 /var/lib/opti-mist
install -m 755 "$ICI/wifi_config.py" /opt/opti061/wifi_config.py
python3 - <<'EOP'
import sys; sys.path.insert(0, "/opt/opti061")
import wifi_config as w
w.mot_de_passe_config()      # cree le mot de passe du boitier s'il n'existe pas (root 600)
EOP
chmod 600 /etc/opti061/wifi_config.secret

echo "3/4 Service au demarrage"
cat > /etc/systemd/system/opti-wifi.service <<'EOF'
[Unit]
Description=OPTI-MIST SOLUTIONS - Wi-Fi de configuration (ouvert seulement si le boitier reste sans adresse)
After=systemd-networkd.service
Wants=systemd-networkd.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/opti061/wifi_config.py auto
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
EOF
# v1.0f : remise a neuf a distance (boitiers en atelier) - le boitier demande toutes les 2 min, aucun port ouvert
cat > /etc/systemd/system/opti-wifi-commande.service <<'FIN'
[Unit]
Description=OPTI-MIST SOLUTIONS - consigne du tableau de bord (remise a neuf des boitiers en atelier)
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/opti061/wifi_config.py commande
TimeoutStartSec=120
FIN
cat > /etc/systemd/system/opti-wifi-commande.timer <<'FIN'
[Unit]
Description=OPTI-MIST SOLUTIONS - consigne du tableau de bord toutes les 2 min
[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
FIN
cat > /usr/local/bin/opti-wifi <<'EOF'
#!/bin/sh
case "$1" in
  ouvrir)    systemctl stop opti-wifi.service 2>/dev/null
             systemd-run --unit=opti-wifi-manuel --collect /usr/bin/python3 /opt/opti061/wifi_config.py ouvrir >/dev/null \
               && echo "Ouverture lancee (15 min). Suivi : opti-wifi journal" ;;
  info)      systemd-run --unit=opti-wifi-info --collect /usr/bin/python3 /opt/opti061/wifi_config.py info >/dev/null \
               && echo "Wi-Fi de consultation ouvert 10 min. Suivi : opti-wifi journal" ;;
  etiquette|etat|oublier|pose|code) exec /usr/bin/python3 /opt/opti061/wifi_config.py "$@" ;;
  journal)   journalctl -t opti-wifi -n 30 --no-pager ;;
  *) echo "Usage : opti-wifi etat | ouvrir | etiquette | journal | oublier NOM_DU_WIFI | oublier --tout | pose | info | code" ;;
esac
EOF
chmod 755 /usr/local/bin/opti-wifi
systemctl daemon-reload && systemctl enable opti-wifi.service >/dev/null 2>&1
systemctl enable --now opti-wifi-commande.timer >/dev/null 2>&1

echo "4/4 Controle"
sha256sum /opt/opti061/wifi_config.py
opti-wifi etat
echo
echo "Installe. Le Wi-Fi de configuration s'ouvrira au demarrage seulement si le boitier reste sans adresse."
echo "Pour l'etiquette : opti-wifi etiquette  (a recopier a la main, jamais en message ni en capture)"
