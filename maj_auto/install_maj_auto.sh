#!/bin/sh
# OPTI-MIST SOLUTIONS - Installation de la mise a jour automatique (v1.4, 27/11/2026 : boitier universel -> composant
#   mpp_probe.py ajoute, tests par mpp_collect.py --test (lecteur et module commun), GO S.S. 26/11 ; v1.3, 25/11/2026 : boitier universel -> composant
#   mpp_collect.py ajoute si le lecteur universel est installe (/opt/opti061/mpp_collect.py), GO S.S. 25/11 ; v1.2, 24/11/2026 : tout nouveau boitier Felicity OPTI-XXX,
#   composants felicity_collect.py + wifi_config.py, GO S.S. 24/11 « on fait tout aujourd'hui » ; v1.1, 22/11/2026 : 7h30 ET 13h ; v1.0, 15/11/2026)
# A lancer en root depuis le dossier qui contient maj_auto.py :  sh install_maj_auto.sh OPTI-087   (ou OPTI-061)
set -e
[ "$(id -u)" = "0" ] || { echo "Lancer en root (sudo sh install_maj_auto.sh OPTI-0XX)"; exit 1; }
CODE="$1"; ICI="$(cd "$(dirname "$0")" && pwd)"
DEPOT="https://raw.githubusercontent.com/optimistsolutions/opti-mist-boitiers/main"
install -d -m 755 /opt/opti-maj && install -m 755 "$ICI/maj_auto.py" /opt/opti-maj/maj_auto.py
install -d -m 700 /etc/opti-maj /var/lib/opti-maj
case "$CODE" in
  OPTI-087) cat > /etc/opti-maj/maj.conf <<EOC
[general]
code = OPTI-087
depot_url = $DEPOT
fichier_envoi = /etc/opti087/opti087.conf
section_envoi = envoi

[composant:opti087_collect.py]
source = sma/opti087_collect.py
chemin = /opt/opti087/opti087_collect.py
test = sudo -u opti087 /usr/bin/python3 /opt/opti087/opti087_collect.py --show >/dev/null
EOC
  ;;
  OPTI-061) cat > /etc/opti-maj/maj.conf <<EOC
[general]
code = OPTI-061
depot_url = $DEPOT
fichier_envoi = /etc/opti061/envoi.conf
section_envoi =

[composant:sa_relais.py]
source = sa_relais/sa_relais.py
chemin = /opt/optisa/sa_relais.py
test = sudo -u optisa env HOME=/var/lib/optisa /usr/bin/python3 /opt/optisa/sa_relais.py --test >/dev/null

[composant:felicity_collect.py]
source = felicity/felicity_collect.py
chemin = /opt/opti061/felicity_collect.py
test = /usr/bin/python3 /opt/opti061/felicity_collect.py --show >/dev/null
EOC
  ;;
  OPTI-[0-9][0-9][0-9]) cat > /etc/opti-maj/maj.conf <<EOC
[general]
code = $CODE
depot_url = $DEPOT
fichier_envoi = /etc/opti061/envoi.conf
section_envoi =

[composant:felicity_collect.py]
source = felicity/felicity_collect.py
chemin = /opt/opti061/felicity_collect.py
test = /usr/bin/python3 -m py_compile /opt/opti061/felicity_collect.py && { [ ! -f /opt/opti061/mpp_collect.py ] || /usr/bin/python3 /opt/opti061/mpp_collect.py --test >/dev/null; }

[composant:wifi_config.py]
source = reseau/wifi_config.py
chemin = /opt/opti061/wifi_config.py
test = /usr/bin/python3 -m py_compile /opt/opti061/wifi_config.py
EOC
  if [ -f /opt/opti061/mpp_collect.py ]; then cat >> /etc/opti-maj/maj.conf <<EOC

[composant:mpp_collect.py]
source = mpp/mpp_collect.py
chemin = /opt/opti061/mpp_collect.py
test = /usr/bin/python3 /opt/opti061/mpp_collect.py --test >/dev/null

[composant:mpp_probe.py]
source = mpp/mpp_probe.py
chemin = /opt/opti061/mpp_probe.py
test = /usr/bin/python3 /opt/opti061/mpp_collect.py --test >/dev/null
EOC
  fi
  ;;
  *) echo "Usage : sh install_maj_auto.sh OPTI-087 | OPTI-061 | OPTI-XXX (nouveau boitier Felicity)"; exit 1 ;;
esac
chmod 600 /etc/opti-maj/maj.conf
cat > /etc/systemd/system/opti-maj.service <<'EOS'
[Unit]
Description=OPTI-MIST SOLUTIONS - mise a jour automatique (fichiers approuves par S.S. seulement)
After=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/opti-maj/maj_auto.py --appliquer
TimeoutStartSec=600
EOS
cat > /etc/systemd/system/opti-maj.timer <<'EOS'
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
cat > /usr/local/bin/optimaj <<'EOW'
#!/bin/sh
case "$1" in
  verifier) sudo /usr/bin/python3 /opt/opti-maj/maj_auto.py --verifier ;;
  maintenant) sudo /usr/bin/python3 /opt/opti-maj/maj_auto.py --appliquer ;;
  journal) sudo tail -n 30 /var/lib/opti-maj/journal.log ;;
  retour) for f in $(sudo grep -h '^chemin' /etc/opti-maj/maj.conf | cut -d= -f2); do [ -f "$f.precedent" ] && sudo cp "$f.precedent" "$f" && echo "Retour : $f"; done ;;
  *) echo "Usage : optimaj verifier | maintenant | journal | retour" ;;
esac
EOW
chmod 755 /usr/local/bin/optimaj
systemctl daemon-reload && systemctl enable --now opti-maj.timer
echo "Mise a jour automatique installee pour $CODE. Test : optimaj verifier"
