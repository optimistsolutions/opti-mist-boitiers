#!/bin/sh
# OPTI-MIST SOLUTIONS - Mise a jour manuelle du boitier OPTI-087 vers v1.9 (evenements 24 h + statut NUIT, lecture seule)
# Voie normale : mise a jour automatique (optimaj), apres approbation de l'empreinte par S.S. (MAJ_APPROUVEES).
# Voie de secours, en root sur le boitier :  sh /root/maj_v1-9.sh   (opti087_collect.py v1.9 copie dans /root avant)
set -e
[ "$(id -u)" = "0" ] || { echo "Lancer en root"; exit 1; }
[ -f /root/opti087_collect.py ] || { echo "Fichier /root/opti087_collect.py absent"; exit 1; }
grep -q 'VERSION = "1.9' /root/opti087_collect.py || { echo "Le fichier copie n'est pas la v1.9"; exit 1; }
python3 -m py_compile /root/opti087_collect.py
cp /opt/opti087/opti087_collect.py /opt/opti087/opti087_collect.py.precedent.bak
install -m 755 /root/opti087_collect.py /opt/opti087/opti087_collect.py
sudo -u opti087 /usr/bin/python3 /opt/opti087/opti087_collect.py --once | tail -2
echo "v1.9 installee. Retour arriere : cp /opt/opti087/opti087_collect.py.precedent.bak /opt/opti087/opti087_collect.py"
