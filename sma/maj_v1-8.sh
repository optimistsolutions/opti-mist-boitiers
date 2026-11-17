#!/bin/sh
# OPTI-MIST SOLUTIONS - Mise a jour boitier OPTI-087 vers v1.8 (v1.7 + journal d'evenements SMA + compteur, lecture seule)
# A lancer en root sur le boitier :  sh /root/maj_v1-8.sh   (opti087_collect.py v1.8 copie dans /root avant)
# Ensuite : mise a jour automatique -> sh /root/install_maj_auto.sh OPTI-087 (maj_auto.py dans /root)
set -e
[ "$(id -u)" = "0" ] || { echo "Lancer en root"; exit 1; }
[ -f /root/opti087_collect.py ] || { echo "Fichier /root/opti087_collect.py absent"; exit 1; }
grep -q 'VERSION = "1.8' /root/opti087_collect.py || { echo "Le fichier copie n'est pas la v1.8"; exit 1; }
python3 -m py_compile /root/opti087_collect.py
[ -f /opt/opti087/opti087_collect.py.v1-3.bak ] || cp /opt/opti087/opti087_collect.py /opt/opti087/opti087_collect.py.v1-3.bak
cp /opt/opti087/opti087_collect.py /opt/opti087/opti087_collect.py.precedent.bak
install -m 755 /root/opti087_collect.py /opt/opti087/opti087_collect.py
C=/etc/opti087/opti087.conf
[ -f "$C.v1-3.bak" ] || { cp "$C" "$C.v1-3.bak"; chmod 640 "$C.v1-3.bak"; }
if ! grep -q '^\[onduleurs\]' "$C"; then
cat >> "$C" <<'EOC'

[onduleurs]
# v1.4 : lecture directe des 9 onduleurs (interface web integree, lecture seule), sans le Data Manager.
# source = onduleurs (lecture directe) ou data_manager (Modbus du Data Manager, v1.3)
source = onduleurs
reseau = 192.168.1
# droit : istl (installateur) ou usr (utilisateur). Mot de passe : coffre uniquement, jamais en photo.
droit = istl
mot_de_passe =
# Ordre terrain 1 a 9 (n de serie)
numeros_serie = 1901377257,1901378626,1901378798,1901378561,1901376900,1901376928,1901378559,1901377399,1901378335
EOC
fi
chown root:opti087 "$C"; chmod 640 "$C"
cat > /usr/local/bin/opti087 <<'EOW'
#!/bin/sh
case "$1" in
  scan)    sudo -u opti087 /usr/bin/python3 /opt/opti087/opti087_collect.py --scan ;;
  sonde)   sudo -u opti087 /usr/bin/python3 /opt/opti087/opti087_collect.py --sonde ;;
  releve)  sudo -u opti087 /usr/bin/python3 /opt/opti087/opti087_collect.py --once ;;
  dernier) /usr/bin/python3 /opt/opti087/opti087_collect.py --show ;;
  journal) sudo journalctl -u opti087-collect.service -n 30 --no-pager ;;
  etat)    systemctl list-timers opti087-collect.timer --no-pager ;;
  evenements) sudo -u opti087 /usr/bin/python3 /opt/opti087/opti087_collect.py --evenements ${2:-2} ;;
  compteur) /usr/bin/python3 /opt/opti087/opti087_collect.py --compteur ;;
  deverrouiller) rm -f /var/lib/opti087/VERROU_MOT_DE_PASSE && echo "Verrou retire. Un seul essai sera fait au prochain releve." ;;
  *) echo "Usage : opti087 sonde | releve | dernier | evenements [jours] | compteur | journal | etat | scan | deverrouiller" ;;
esac
EOW
chmod 755 /usr/local/bin/opti087
echo "v1.8 installee (Speedwire + direct detaille + evenements + compteur). Sauvegardes : /opt/opti087/opti087_collect.py.v1-3.bak et $C.v1-3.bak"
grep -q "^mot_de_passe *= *[^ ]" "$C" && echo "Mot de passe deja renseigne." || echo "Etape suivante : nano $C  -> section [onduleurs], ligne mot_de_passe ="
echo "Puis : opti087 sonde ; opti087 evenements 10 ; opti087 compteur"
