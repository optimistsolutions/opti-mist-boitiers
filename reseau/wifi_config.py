#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTI-MIST SOLUTIONS - Wi-Fi de configuration du boitier - v1.0a du 20/11/2026 (GO S.S. 20/11)
v1.0a (20/11 21h20, essai banc opti-098) : au retour en Wi-Fi normal, « netplan apply » relancait wpa_supplicant
  ~90 s plus tard (M, journal 21:13 -> 21:14:36) : l'essai de 75 s echouait meme avec le bon mot de passe.
  Correctif : netplan generate + demarrage direct de netplan-wpa-wlan0 (connexion en 2 s, M) ; essai porte a 120 s ;
  temps de connexion ecrit au journal.
v1.0b (20/11 21h35, essai banc) : refus WRONG_KEY constate (M) avec le mot de passe tape au telephone. Champs sans
  majuscule ni correction automatique du clavier, case « afficher le mot de passe » pour que le technicien relise.
v1.0c (20/11 23h55, scenario 5 maison) : le Wi-Fi principal de la maison, MASQUE, n'apparaissait pas dans la liste (D).
  Un Wi-Fi tape a la main (ou absent du releve) est enregistre avec « hidden: true » (netplan -> scan_ssid=1, S a
  confirmer sur le banc) ; la page explique quoi faire si le Wi-Fi du client n'apparait pas.
v1.0d (23/11 10h30, test de pose par les techniciens, GO S.S.) : apres « oublier », le boitier se reconnectait
  au Wi-Fi d'atelier (/etc/netplan/30-wifi.yaml, non gere par cette page) et le Wi-Fi de configuration ne
  s'ouvrait jamais (M, journal opti-098). Correctifs : les Wi-Fi d'atelier sont comptes comme connus, affiches par
  « etat » et retires par « oublier NOM » ou « oublier --tout » (fichier deplace dans /root, pas supprime) ;
  « etat » dit si le boitier est pret a expedier (aucun Wi-Fi, ni client ni atelier). Delais : boitier neuf 45 s
  apres le demarrage (au lieu de 2 min), Wi-Fi client visible mais refuse 2 min (au lieu de 4) ; Wi-Fi client
  invisible : 10 min inchange (laisser redemarrer la box du client apres une coupure).
v1.0e (23/11 11h, GO S.S. 10h49) : RAPPORT DE POSE. Le boitier note les etapes de la pose (demarrage, ouverture du Wi-Fi
  de configuration, arrivee du telephone sur la page, validation, connexion), le nombre d'essais rates, le Wi-Fi choisi
  (nom et signal, JAMAIS le mot de passe), les convertisseurs reconnus et les initiales du technicien (champ de la page).
  Une fois connecte, il envoie le rapport au tableau de bord (canal direct, jeton du boitier) -> e-mail S.S. + Raphaele ;
  garde une copie (/var/lib/opti-mist/poses.jsonl) et renvoie au demarrage suivant si l'envoi a echoue.
  Commande : « opti-wifi pose » (dernier rapport + renvoi si en attente).
v1.0f (23/11 12h15, GO S.S. 12h08-12h10, 3 essais techniciens) : (1) initiales du technicien OBLIGATOIRES (2 rapports sur 2
  « non renseigne » avec le champ facultatif) ; (2) noms de Wi-Fi decodes (iw ecrit « Riven\x20 » pour « Riven ») ;
  (3) REMISE A NEUF A DISTANCE pour les boitiers en atelier : « wifi_config.py commande » (minuterie opti-wifi-commande,
  toutes les 2 min, seulement si le boitier est en ligne) demande au tableau de bord s'il y a une consigne ; « remise_a_neuf »
  -> accuse reception, oublie tous les Wi-Fi (clients + atelier), redemarre. Le boitier appelle, on ne l'appelle pas.
v1.0g (23/11 12h40, GO S.S. 12h20-12h22, option A + basculement) : CONSULTATION SANS INTERNET POUR LE CLIENT.
  Wi-Fi « OPTI-XXX-INFO » (meme mot de passe que l'etiquette), page en lecture seule : direct (batterie, solaire,
  consommation, reseau), bilan du jour et des 7 derniers jours calcules depuis les releves gardes sur le boitier, plus le
  formulaire Wi-Fi reserve au technicien. Aucun port ouvert sur le reseau du client ni sur internet : la page n'existe que
  sur le petit reseau du boitier, ouvert 10 min. Ouverture : (a) boitier deja installe (Wi-Fi connu) sans adresse au
  demarrage -> INFO au lieu de CONFIG (boitier neuf : CONFIG, inchange) ; (b) minuterie 2 min : internet absent depuis
  30 min -> INFO 10 min, puis retour au Wi-Fi du client (les releves continuent d'etre stockes sur le boitier).
v1.0h (23/11 12h35, GO S.S. 12h31, revue securite) : (1) en mode INFO, changer le Wi-Fi exige le CODE TECHNICIEN (pas sur
  l'etiquette ; empreinte seulement sur le boitier, /etc/opti061/code_technicien.sha256, root 600 ; « opti-wifi code »
  pour le saisir, sans affichage) ; 5 codes faux -> formulaire bloque jusqu'a la fermeture. Boitier neuf (CONFIG) :
  inchange, pas de code. (2) Internet absent depuis plus de 2 h (credit epuise) : INFO 15 min toutes les 30 min
  (au lieu de 10 min toutes les 40 min).
v1.0j (24/11 20h30, GO S.S., test E du 24/11 sur opti-098) : ECRITURES FORCEES SUR LE DISQUE. Test E (M) : coupure ~20 s
  apres « Le boitier se connecte » -> ni la copie d'avant ni le nouveau Wi-Fi n'etaient sur le disque (aucun fsync : Linux
  garde les ecritures quelques secondes en memoire) ; le boitier est reparti sur l'ancien Wi-Fi par hasard, sans la ligne
  « ESSAI INTERROMPU ». Risque : une ecriture survit et pas l'autre (cas probable du 23/11 17:06). Desormais : copie d'avant
  ecrite ET forcee sur le disque (fsync fichier + dossier) AVANT le nouveau Wi-Fi ; nouveau Wi-Fi et fichier netplan forces
  aussi ; journal « essai du Wi-Fi X lance » au debut de chaque essai (sans mot de passe).
v1.0i (23/11 18h28, GO S.S., tests A-B-C du 23/11 sur opti-098) :
  (1) ESSAI INTERROMPU : a 17:06 un essai de Wi-Fi (mode INFO) a ete coupe par une coupure de courant avant la fin des
      120 s ; le nouveau mot de passe etait deja enregistre et l'ancien (bon) perdu -> 24 refus WRONG_KEY a 17:50 (M, journal).
      Desormais la liste d'avant l'essai est gardee (wifi_essai_avant.json, root 600) et RETABLIE au demarrage suivant ou a la
      minuterie de 2 min si l'essai n'a pas abouti. Un Wi-Fi ne remplace donc l'ancien qu'apres une connexion reussie.
  (2) HEURES DE POSE : les etapes sont notees sur l'horloge du demarrage (/proc/uptime), puis converties en heure reelle
      au moment du rapport, apres synchronisation de l'heure (60 s au plus). Le boitier n'a pas d'horloge sauvegardee :
      apres un redemarrage sans internet, l'heure repartait en arriere (17:06 -> 17:00, M).
  (3) Page INFO : duree d'ouverture reelle affichee (10 ou 15 min, plus « 15 min » fixe) ; texte d'attente « Wi-Fi de
      consultation » en mode INFO ; « En direct » : dernier releve VALIDE si le dernier est vide (port indisponible).
  (4) ADRESSE DU BOITIER : la minuterie de consigne envoie ses adresses (cable / Wi-Fi) au tableau de bord (Boitiers v1.8p),
      affichees sur sa carte : plus besoin de chercher le boitier avec arp.
  (5) Plus de message systemd « opti-wifi-info.service: Failed to open » toutes les 2 min (test de l'unite temporaire).

But : poser un boitier chez le client SANS visite prealable et SANS connaitre son Wi-Fi a l'avance.
Le technicien branche le boitier ; s'il n'a pas internet, le boitier ouvre son propre Wi-Fi
« OPTI-XXX-CONFIG » ; le technicien s'y connecte avec son telephone, choisit le Wi-Fi du client,
tape le mot de passe, valide. Le boitier ferme son Wi-Fi et se connecte.

Garde-fous (decides avec S.S. le 20/11) :
  - ouvert SEULEMENT quand le boitier n'a aucune adresse (ni cable ni Wi-Fi) ; jamais quand il est en ligne ;
  - ferme tout seul apres 15 min (30 min au plus si un essai echoue) ;
  - protege par un mot de passe propre au boitier (fichier root 600, inscrit sur l'etiquette, jamais dans le chat) ;
  - la page ne fait que : choisir un Wi-Fi + afficher les convertisseurs reconnus. AUCUNE commande vers les convertisseurs ;
  - rien n'est expose a internet (reseau local 10.42.0.0/24 du boitier uniquement, pendant 15 min).

Reseau : netplan + systemd-networkd + wpa_supplicant (pas de NetworkManager, constate sur opti-098 le 20/11).
La puce ne fait pas « connecte » et « point d'acces » en meme temps (managed, AP <= 1) : le boitier releve
d'abord les Wi-Fi visibles, puis ouvre son point d'acces, puis le ferme pour essayer le Wi-Fi choisi.

Fichiers :
  /etc/opti061/wifi_config.secret   mot de passe du Wi-Fi de configuration (root 600, cree a l'installation)
  /etc/opti061/wifi_clients.json    Wi-Fi des clients enregistres par cette page (root 600)
  /etc/netplan/40-opti-wifi.yaml    genere depuis wifi_clients.json (root 600) ; s'ajoute au Wi-Fi d'atelier (30-wifi.yaml)
  /etc/opti061/wifi_config_desactive  si ce fichier existe : rien ne s'ouvre au demarrage
Usage :
  wifi_config.py auto        au demarrage (service opti-wifi) : ouvre seulement si le boitier reste sans adresse
  wifi_config.py ouvrir      ouvre maintenant 15 min (atelier ; brancher le cable avant, sinon la session SSH tombe)
  wifi_config.py etat        adresses, Wi-Fi clients enregistres (noms seulement), derniers evenements
  wifi_config.py etiquette   affiche nom + mot de passe du Wi-Fi de configuration (pour l'etiquette, a l'ecran seulement)
  wifi_config.py oublier NOM retire un Wi-Fi client ou d'atelier enregistre
  wifi_config.py info       ouvre le Wi-Fi de consultation OPTI-XXX-INFO 10 min (atelier : cable branche avant)
  wifi_config.py code       saisir le code technicien (exige en mode INFO pour changer le Wi-Fi)
  wifi_config.py commande   (minuterie 2 min) consigne du tableau de bord : remise a neuf (boitiers en atelier)
  wifi_config.py pose       dernier rapport de pose (et renvoi s'il n'a pas ete recu)
  wifi_config.py oublier --tout   retire tous les Wi-Fi (client + atelier) : boitier « neuf » avant expedition
"""
import html
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "wifi_config 1.0j"
IFACE = "wlan0"
AP_IP = "10.42.0.1"
CONF = "/etc/opti061"
SECRET = os.path.join(CONF, "wifi_config.secret")
CLIENTS = os.path.join(CONF, "wifi_clients.json")
DESACTIVE = os.path.join(CONF, "wifi_config_desactive")
NETPLAN = "/etc/netplan/40-opti-wifi.yaml"
ATELIER = "/etc/netplan/30-wifi.yaml"          # Wi-Fi d'atelier pose a la preparation du boitier
ATELIER_RANGE = "/root/30-wifi.yaml.atelier"   # « oublier » le deplace ici (retour possible a la main)
RUN = "/run/opti-wifi"
NET_AP = "/run/systemd/network/05-opti-wifi-ap.network"
DATA = os.environ.get("OPTI_DATA", "/var/lib/opti061")
JOURNAL = "/var/lib/opti-mist/wifi_config.log"
POSES = "/var/lib/opti-mist/poses.jsonl"                 # v1.0e : rapports de pose (copie locale)
POSE_ATTENTE = "/var/lib/opti-mist/pose_a_envoyer.json"   # v1.0e : rapport pas encore recu par le tableau de bord
ENVOI_CONF = os.path.join(CONF, "envoi.conf")
ESSAI_AVANT = os.path.join(CONF, "wifi_essai_avant.json")   # v1.0i : Wi-Fi d'avant l'essai en cours (root 600)

DUREE_S = 15 * 60          # duree d'ouverture
DUREE_MAX_S = 30 * 60      # plafond si des essais echouent
ATTENTE_NEUF_S = 45        # v1.0d : aucun Wi-Fi connu (boitier neuf) -> ouverture 45 s apres le demarrage du service
ATTENTE_CONNU_S = 120      # v1.0d : Wi-Fi connu -> premier releve apres 2 min sans adresse
ATTENTE_VISIBLE_S = 120    # v1.0d : Wi-Fi connu visible mais pas d'adresse (mot de passe change ?) -> 2 min (au lieu de 4)
ATTENTE_ABSENT_S = 600     # Wi-Fi client invisible (box qui redemarre apres coupure) -> apres 10 min
ESSAI_S = 120              # temps laisse a la connexion au Wi-Fi choisi


def log(msg):
    ligne = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(ligne, flush=True)
    try:
        os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
        with open(JOURNAL, "a") as f:
            f.write(ligne + "\n")
    except OSError:
        pass
    subprocess.call(["logger", "-t", "opti-wifi", msg])


def sh(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def nom_boitier():
    return socket.gethostname().upper()          # opti-098 -> OPTI-098


DUREE_PAGE = {"s": 15 * 60}     # v1.0i : duree reelle d'ouverture, affichee sur la page
MODE = {"m": "config"}          # v1.0g : « config » (boitier neuf) ou « info » (consultation client + technicien)
INFO_S = 10 * 60                # v1.0g : duree d'ouverture du Wi-Fi de consultation
SANS_INTERNET_S = 30 * 60       # v1.0g : internet absent depuis 30 min -> consultation
MARQUE_SANS_NET = "/run/opti-wifi/sans_internet.json"
LONG_S = 2 * 3600               # v1.0h : au-dela, consultation plus frequente
CODE_TECH = "/etc/opti061/code_technicien.sha256"   # v1.0h : empreinte du code technicien (jamais le code)
ESSAIS_CODE_MAX = 5


def empreinte_code(code):
    import hashlib
    return hashlib.sha256(("opti-mist|" + code.strip()).encode("utf-8")).hexdigest()


def code_technicien_ok(code):
    import hmac
    try:
        attendu = open(CODE_TECH).read().strip()
    except OSError:
        return False
    return bool(code) and hmac.compare_digest(attendu, empreinte_code(code))


def ssid_config():
    return nom_boitier() + ("-INFO" if MODE["m"] == "info" else "-CONFIG")


def ssids_boitier():
    return (nom_boitier() + "-CONFIG", nom_boitier() + "-INFO")


def mot_de_passe_config():
    if not os.path.exists(SECRET):
        abc = "abcdefghjkmnpqrstuvwxyz23456789"     # sans 0/o, 1/l/i : lisible sur une etiquette
        mdp = "".join(secrets.choice(abc) for _ in range(10))
        os.makedirs(CONF, exist_ok=True)
        fd = os.open(SECRET, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(mdp + "\n")
    return open(SECRET).read().strip()


def adresses():
    """Adresses IPv4 du cable et du Wi-Fi (hors point d'acces)."""
    _, out = sh(["ip", "-4", "-br", "addr"])
    res = {}
    for l in out.splitlines():
        p = l.split()
        if len(p) >= 3 and p[0] != "lo":
            ips = [x.split("/")[0] for x in p[2:] if re.match(r"\d+\.\d+\.\d+\.\d+/", x)]
            ips = [i for i in ips if i != AP_IP and not i.startswith("169.254.")]
            if ips:
                res[p[0]] = ips
    return res


def clients():
    try:
        return json.load(open(CLIENTS))
    except (OSError, ValueError):
        return []


def atelier():
    """Noms des Wi-Fi d'atelier (30-wifi.yaml) : cles directement sous « access-points: »."""
    try:
        lignes = open(ATELIER).read().splitlines()
    except OSError:
        return []
    noms, dans, niveau = [], False, None
    for l in lignes:
        if not l.strip() or l.strip().startswith("#"):
            continue
        ind = len(l) - len(l.lstrip())
        if l.strip() == "access-points:":
            dans, niveau, base = True, None, ind
            continue
        if dans:
            if ind <= base:
                dans = False
                continue
            if niveau is None:
                niveau = ind
            if ind == niveau:
                m = re.match(r'\s*"?(.*?)"?\s*:\s*(\{\})?\s*$', l)
                if m and m.group(1):
                    noms.append(m.group(1))
    return noms


def ranger_atelier():
    """Deplace le fichier d'atelier (tous ses Wi-Fi) dans /root ; rien n'est supprime."""
    if os.path.exists(ATELIER):
        shutil.move(ATELIER, ATELIER_RANGE)
        os.chmod(ATELIER_RANGE, 0o600)
        log("Wi-Fi d'atelier retires (%s -> %s)" % (ATELIER, ATELIER_RANGE))


def connus_tous():
    return [c["ssid"] for c in clients()] + atelier()


def ecrire_sur(chemin, texte):
    """v1.0j : ecriture atomique ET forcee sur le disque (fichier tmp + fsync, remplacement, fsync du dossier), root 600."""
    tmp = chemin + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(texte)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, chemin)
    try:
        d = os.open(os.path.dirname(chemin) or ".", os.O_RDONLY)
        try:
            os.fsync(d)
        finally:
            os.close(d)
    except OSError:
        pass


def ecrire_clients(liste):
    os.makedirs(CONF, exist_ok=True)
    ecrire_sur(CLIENTS, json.dumps(liste, ensure_ascii=False, indent=1))     # v1.0j
    # netplan : YAML accepte les chaines JSON entre guillemets -> json.dumps protege les caracteres speciaux
    if liste:
        lignes = ["# OPTI-MIST SOLUTIONS - genere par wifi_config.py, ne pas modifier a la main", "network:",
                  "  version: 2", "  renderer: networkd", "  wifis:", "    %s:" % IFACE, "      dhcp4: true",
                  "      access-points:"]
        for c in liste:
            if c.get("mdp") or c.get("masque"):
                lignes.append("        %s:" % json.dumps(c["ssid"], ensure_ascii=False))
                if c.get("mdp"):
                    lignes.append("          password: %s" % json.dumps(c["mdp"], ensure_ascii=False))
                if c.get("masque"):                 # v1.0c : Wi-Fi masque
                    lignes.append("          hidden: true")
            else:                                   # Wi-Fi ouvert : netplan attend une table vide
                lignes.append("        %s: {}" % json.dumps(c["ssid"], ensure_ascii=False))
        ecrire_sur(NETPLAN, "\n".join(lignes) + "\n")                        # v1.0j
    elif os.path.exists(NETPLAN):
        os.remove(NETPLAN)


def decoder_ssid(s):
    """v1.0f : iw echappe les octets non imprimables (\\x20 = espace) -> nom reel du Wi-Fi."""
    try:
        b = re.sub(rb"\\x([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]), s.encode("utf-8"))
        return b.decode("utf-8", "replace")
    except Exception:
        return s


def scanner():
    """Wi-Fi visibles : [(ssid, signal_dbm)] tries du plus fort au plus faible."""
    sh(["ip", "link", "set", IFACE, "up"])
    vus = {}
    for _ in range(4):
        code, out = sh(["iw", "dev", IFACE, "scan"], timeout=40)
        if code == 0 and out:
            sig = None
            for l in out.splitlines():
                l = l.strip()
                if l.startswith("BSS "):
                    sig = None
                elif l.startswith("signal:"):
                    try:
                        sig = float(l.split()[1])
                    except (IndexError, ValueError):
                        sig = None
                elif l.startswith("SSID:"):
                    s = decoder_ssid(l[5:].strip())   # v1.0f
                    if s and "\x00" not in s and s.strip() and s not in ssids_boitier():
                        if s not in vus or (sig or -999) > vus[s]:
                            vus[s] = sig if sig is not None else -999
            break
        time.sleep(5)
    return sorted(vus.items(), key=lambda x: -x[1])


def convertisseurs():
    """Lecture seule de la detection du collecteur (detection.json) ; aucun acces aux convertisseurs."""
    try:
        d = json.load(open(os.path.join(DATA, "detection.json")))
        return d.get("convertisseurs") or [], d.get("horodatage", ""), len(d.get("prises") or [])
    except (OSError, ValueError):
        return [], "", 0


# --------------------------------------------------------------------------- point d'acces
class PointAcces:
    def __init__(self):
        self.procs = []

    def ouvrir(self):
        os.makedirs(RUN, exist_ok=True)
        sh(["systemctl", "stop", "netplan-wpa-%s.service" % IFACE])
        sh(["rfkill", "unblock", "wlan"])
        with open(NET_AP, "w") as f:
            f.write("[Match]\nName=%s\n\n[Network]\nAddress=%s/24\nDHCP=no\nLinkLocalAddressing=no\n"
                    "IPv6AcceptRA=no\nConfigureWithoutCarrier=yes\n" % (IFACE, AP_IP))
        sh(["networkctl", "reload"])
        sh(["networkctl", "reconfigure", IFACE])
        conf = os.path.join(RUN, "hostapd.conf")
        fd = os.open(conf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("interface=%s\ndriver=nl80211\nssid=%s\ncountry_code=BF\nhw_mode=g\nchannel=6\n"
                    "wmm_enabled=1\nauth_algs=1\nwpa=2\nwpa_key_mgmt=WPA-PSK\nrsn_pairwise=CCMP\n"
                    "wpa_passphrase=%s\nmax_num_sta=4\n" % (IFACE, ssid_config(), mot_de_passe_config()))
        self.procs.append(subprocess.Popen(["hostapd", conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(3)
        if self.procs[0].poll() is not None:
            raise RuntimeError("hostapd n'a pas demarre")
        sh(["ip", "addr", "replace", AP_IP + "/24", "dev", IFACE])
        self.procs.append(subprocess.Popen(
            ["dnsmasq", "-k", "--conf-file=/dev/null", "--no-resolv", "--no-hosts", "--bind-interfaces",
             "--interface=" + IFACE, "--listen-address=" + AP_IP, "--except-interface=lo",
             "--dhcp-range=10.42.0.10,10.42.0.50,255.255.255.0,15m", "--dhcp-option=3," + AP_IP,
             "--dhcp-option=6," + AP_IP, "--address=/#/" + AP_IP, "--dhcp-leasefile=" + os.path.join(RUN, "baux"),
             "--pid-file=" + os.path.join(RUN, "dnsmasq.pid")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        log("Wi-Fi %s OUVERT : %s" % ("de consultation" if MODE["m"] == "info" else "de configuration", ssid_config()))

    def fermer(self):
        for p in self.procs:
            try:
                p.terminate()
                p.wait(timeout=10)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        self.procs = []
        if os.path.exists(NET_AP):
            os.remove(NET_AP)
        sh(["ip", "addr", "flush", "dev", IFACE])
        sh(["netplan", "generate"], timeout=60)   # v1.0a : regenere /run/netplan/wpa-wlan0.conf et les fichiers networkd
        sh(["systemctl", "daemon-reload"])
        sh(["networkctl", "reload"])
        sh(["systemctl", "restart", "netplan-wpa-%s.service" % IFACE])   # v1.0a : direct, pas « netplan apply » (lent)
        sh(["networkctl", "reconfigure", IFACE])
        log("Wi-Fi de configuration ferme ; retour au Wi-Fi normal")


# --------------------------------------------------------------------------- page
ETAT = {"reseaux": [], "message": "", "demande": None, "masque": False, "codes_faux": 0}
POSE = {"service": None, "ap_ouvert": None, "premiere_visite": None, "validation": None, "connecte": None,
        "essais": 0, "technicien": ""}                          # v1.0e : horodatages (epoch) de la pose en cours


def hm(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if t else ""


def depuis_demarrage():
    """v1.0i : secondes depuis le demarrage (ne saute pas quand l'heure est corrigee par internet)."""
    try:
        return float(open("/proc/uptime").read().split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0


def demarrage_epoch():
    u = depuis_demarrage()
    return time.time() - u if u else None


def heure_synchronisee(max_s=60):
    """v1.0i : attend que l'heure soit synchronisee (timesyncd) ; False si pas en 60 s (heure peut-etre fausse)."""
    fin = time.time() + max_s
    while True:
        code, out = sh(["timedatectl", "show", "-p", "NTPSynchronized", "--value"])
        if code == 0 and out.strip() == "yes":
            return True
        if time.time() >= fin:
            return False
        time.sleep(5)


def lire_envoi():
    cfg = {}
    try:
        for l in open(ENVOI_CONF):
            if "=" in l and not l.strip().startswith("#"):
                k, v = l.split("=", 1)
                cfg[k.strip()] = v.split("#")[0].strip() if k.strip() != "direct_jeton" else v.strip()
    except OSError:
        pass
    return cfg


def code_boitier(cfg):
    for k in ("code", "site"):
        if re.match(r"^OPTI-\d{3}$", str(cfg.get(k, "")).upper()):
            return cfg[k].upper()
    return nom_boitier()


def rapport_pose(ssid):
    """Rapport sans aucun mot de passe : etapes, durees (s), Wi-Fi choisi et signal, convertisseurs, technicien.
    v1.0i : POSE contient des secondes depuis le demarrage ; converties ici en heure reelle (heure deja synchronisee)."""
    sync = heure_synchronisee()
    d0 = demarrage_epoch()
    sig = dict(ETAT["reseaux"]).get(ssid)
    conv, _, nprises = convertisseurs()

    def reel(k):
        return hm(d0 + POSE[k]) if POSE.get(k) is not None and d0 else ""

    def ecart(a, b):
        va = 0.0 if a == "demarrage" else POSE.get(a)
        return int(POSE[b] - va) if POSE.get(b) is not None and va is not None else None
    return {"version": VERSION, "boitier": nom_boitier(), "technicien": POSE["technicien"] or "non renseigne",
            "demarrage": hm(d0) + ("" if sync else " (heure non verifiee)"), "ap_ouvert": reel("ap_ouvert"),
            "premiere_visite": reel("premiere_visite"), "validation": reel("validation"), "connecte": reel("connecte"),
            "s_demarrage_ap": ecart("demarrage", "ap_ouvert"), "s_ap_page": ecart("ap_ouvert", "premiere_visite"),
            "s_page_validation": ecart("premiere_visite", "validation"), "s_validation_connecte": ecart("validation", "connecte"),
            "s_total": ecart("demarrage", "connecte"), "essais_rates": max(POSE["essais"] - 1, 0),
            "wifi": ssid[:32], "signal_dbm": int(sig) if sig and sig > -999 else None,
            "convertisseurs": [c[0] for c in conv][:8], "prises": nprises}


def envoyer_pose(rapport, essais=10, pause=30):
    """Canal direct du tableau de bord (meme jeton que les releves). True si recu."""
    cfg = lire_envoi()
    if not cfg.get("direct_url") or not cfg.get("direct_jeton"):
        log("rapport de pose garde sur le boitier : direct_url / direct_jeton absents de envoi.conf")
        return False
    corps = json.dumps({"jeton": cfg["direct_jeton"], "direct": {"code": code_boitier(cfg), "mode": "pose",
                                                                  "pose": rapport}}).encode()
    import urllib.request
    for i in range(essais):
        try:
            req = urllib.request.Request(cfg["direct_url"], data=corps, headers={"Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
            if r.get("status") == "ok":
                log("rapport de pose ENVOYE au tableau de bord (%s)" % code_boitier(cfg))
                return True
            log("rapport de pose refuse par le tableau de bord (%s)" % r.get("status"))
            return False
        except Exception as e:
            if i == essais - 1:
                log("rapport de pose non envoye (%s) : nouvel essai au prochain demarrage" % type(e).__name__)
        time.sleep(pause)
    return False


def oublier_tout():
    ecrire_clients([])
    ranger_atelier()
    sh(["netplan", "generate"], timeout=60)


def info_en_cours_session():
    """v1.0i : une page (CONFIG ou INFO) tourne-t-elle ? (l'unite temporaire n'est testee que si elle existe)."""
    return os.path.exists(NET_AP) or (os.path.exists("/run/systemd/transient/opti-wifi-info.service") and
                                      sh(["systemctl", "is-active", "--quiet", "opti-wifi-info.service"])[0] == 0)


def info_en_cours():
    return info_en_cours_session() or sh(["systemctl", "is-active", "--quiet", "opti-wifi.service"])[0] == 0


def veille_internet():
    """v1.0g : boitier installe, internet absent depuis 30 min -> Wi-Fi de consultation 10 min (unite separee)."""
    if not connus_tous() or os.path.exists(DESACTIVE) or info_en_cours():
        return
    if a_internet():
        if os.path.exists(MARQUE_SANS_NET):
            os.remove(MARQUE_SANS_NET)
        return
    os.makedirs(RUN, exist_ok=True)
    maint = time.time()
    try:
        m = json.load(open(MARQUE_SANS_NET))
    except (OSError, ValueError):
        m = None
    if not m:
        json.dump({"depuis": maint, "prochain": maint + SANS_INTERNET_S}, open(MARQUE_SANS_NET, "w"))
        log("internet absent : consultation dans %d min si rien ne change" % (SANS_INTERNET_S // 60))
        return
    if maint < m.get("prochain", 0):
        return
    long_ = maint - m.get("depuis", maint) >= LONG_S          # v1.0h : credit epuise ?
    duree = 15 * 60 if long_ else INFO_S
    m["prochain"] = maint + duree + (15 * 60 if long_ else SANS_INTERNET_S)
    json.dump(m, open(MARQUE_SANS_NET, "w"))
    log("internet absent depuis %d min : ouverture du Wi-Fi de consultation %d min" % (
        (maint - m.get("depuis", maint)) // 60, duree // 60))
    sh(["systemd-run", "--unit=opti-wifi-info", "--collect", "/usr/bin/python3", "/opt/opti061/wifi_config.py",
        "info", str(duree // 60)])


def commande():
    """v1.0f : minuterie 2 min. En ligne seulement ; demande au tableau de bord s'il y a une consigne pour ce boitier."""
    try:
        retablir_essai_interrompu()                     # v1.0i
    except Exception as e:
        log("retablissement apres essai : erreur %s" % type(e).__name__)
    try:
        veille_internet()                               # v1.0g
    except Exception as e:
        log("veille internet : erreur %s" % type(e).__name__)
    if not adresses():
        return
    cfg = lire_envoi()
    if not cfg.get("direct_url") or not cfg.get("direct_jeton"):
        return
    import urllib.request
    code = code_boitier(cfg)

    def poster(extra):
        corps = json.dumps({"jeton": cfg["direct_jeton"],
                            "direct": dict({"code": code, "mode": "commande"}, **extra)}).encode()
        req = urllib.request.Request(cfg["direct_url"], data=corps, headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
    ip = {k: v[0] for k, v in adresses().items()}       # v1.0i : adresses du boitier (cable / Wi-Fi) pour sa carte
    try:
        c = (poster({"ip": ip, "version": VERSION}) or {}).get("commande") or {}
    except Exception:
        return
    if c.get("action") != "remise_a_neuf" or not c.get("id"):
        return
    cable = any(i.startswith(("end", "eth")) for i in adresses())
    log("CONSIGNE recue du tableau de bord : remise a neuf (%s)" % c["id"])
    try:
        poster({"fait": c["id"], "note": "cable branche : le debrancher" if cable else "redemarrage"})
    except Exception:
        log("accuse de reception non envoye : remise a neuf quand meme")
    oublier_tout()
    log("remise a neuf : Wi-Fi clients et atelier oublies ; redemarrage")
    sh(["sync"])
    sh(["systemctl", "reboot"])


def finir_pose(ssid):
    rapport = rapport_pose(ssid)
    os.makedirs(os.path.dirname(POSES), exist_ok=True)
    with open(POSES, "a") as f:
        f.write(json.dumps(rapport, ensure_ascii=False) + "\n")
    with open(POSE_ATTENTE, "w") as f:
        json.dump(rapport, f, ensure_ascii=False)
    log("POSE terminee en %s s par %s (essais rates : %d)" % (rapport["s_total"], rapport["technicien"],
                                                              rapport["essais_rates"]))
    if envoyer_pose(rapport):
        os.remove(POSE_ATTENTE)


def renvoyer_pose_en_attente(essais=3):
    if os.path.exists(POSE_ATTENTE):
        try:
            if envoyer_pose(json.load(open(POSE_ATTENTE)), essais=essais, pause=10):
                os.remove(POSE_ATTENTE)
        except (OSError, ValueError):
            pass

STYLE = ("body{font-family:sans-serif;margin:0;background:#f4f6f9;color:#1d2433}"
         "header{background:#0b3a6e;color:#fff;padding:14px 16px}header b{color:#ecc62e}"
         "main{padding:14px 16px;max-width:520px;margin:auto}"
         ".carte{background:#fff;border-radius:10px;padding:14px;margin-bottom:14px;box-shadow:0 1px 3px #0002}"
         "label{display:block;margin:10px 0 4px;font-weight:bold}select,input{width:100%;padding:12px;font-size:17px;"
         "box-sizing:border-box;border:1px solid #c9ced8;border-radius:8px}"
         "button{width:100%;margin-top:14px;padding:14px;font-size:18px;background:#0b3a6e;color:#fff;border:0;"
         "border-radius:8px}.msg{background:#fff4d6;border-left:4px solid #ecc62e;padding:10px;margin-bottom:14px}"
         "td{padding:4px 6px}small{color:#5a6475}")


def page_principale():
    opts = "".join('<option value="%s">%s  (%s dBm)</option>' % (html.escape(s, True), html.escape(s), int(sig))
                   for s, sig in ETAT["reseaux"])
    conv, horo, nprises = convertisseurs()
    lignes = "".join("<tr><td><b>%s</b></td><td>%s</td></tr>" % (html.escape(c[0]), html.escape(c[2]))
                     for c in conv) or "<tr><td colspan=2>Aucun convertisseur reconnu pour l'instant.</td></tr>"
    msg = '<div class="msg">%s</div>' % html.escape(ETAT["message"]) if ETAT["message"] else ""
    if MODE["m"] == "info":                                      # v1.0g : consultation d'abord, Wi-Fi ensuite
        msg = section_info() + msg + "<p><b>Reserve au technicien</b> : changer le Wi-Fi du boitier</p>"
    return ("<!doctype html><html lang=fr><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'><title>%s</title><style>%s</style>"
            "</head><body><header>OPTI-MIST <b>SOLUTIONS</b><br><small style='color:#cfd8e6'>Boitier %s - "
            "%s</small></header><main>%s"
            "<div class=carte><form method=post action=/connecter>"
            "<label>Wi-Fi du client</label><select name=ssid><option value=''>- choisir -</option>%s</select>"
            "<small>Le Wi-Fi du client n'apparait pas ? Il est peut-etre masque : tapez son nom exact ci-dessous "
            "(majuscules comprises). Le boitier capte le Wi-Fi 2,4 GHz.</small>"
            "<label>ou nom du Wi-Fi (s'il est masque)</label><input name=ssid_libre autocomplete=off autocapitalize=off "
            "autocorrect=off spellcheck=false>"
            "<label>Mot de passe du Wi-Fi</label><input id=mdp name=mdp type=password autocomplete=off "
            "autocapitalize=off autocorrect=off spellcheck=false>"
            "<label style='font-weight:normal'><input type=checkbox style='width:auto' onclick=\"document."
            "getElementById('mdp').type=this.checked?'text':'password'\"> afficher le mot de passe pour le relire</label>"
            "%s<label>Vos initiales (technicien) - obligatoire</label><input name=tech maxlength=12 required autocomplete=off "
            "autocapitalize=characters autocorrect=off spellcheck=false placeholder='ex. O.G.'>"
            "<button>Connecter le boitier</button></form></div>"
            "<div class=carte><b>Convertisseurs reconnus</b> <small>(%s prise(s) vue(s) - %s)</small>"
            "<table>%s</table></div>"
            "<small>Ce Wi-Fi se ferme tout seul apres %d minutes. Assistance : +226 25 46 53 00</small>"
            "</main></body></html>") % (html.escape(ssid_config()), STYLE, html.escape(nom_boitier()),
                                        "vos donnees, sans internet" if MODE["m"] == "info" else "configuration du Wi-Fi",
                                        msg, opts, champ_code(),
                                        nprises, html.escape(horo[:16].replace("T", " ")), lignes,
                                        max(1, DUREE_PAGE["s"] // 60))


def _fr(x, d=0):
    if x is None:
        return "-"
    return ("%%.%df" % d % x).replace(".", ",")


def donnees_locales():
    """v1.0g : dernier releve + bilans calcules (C) depuis les releves gardes sur le boitier (DATA/AAAA-MM-JJ.jsonl)."""
    try:
        dern = json.load(open(os.path.join(DATA, "dernier.json")))
    except (OSError, ValueError):
        dern = {}
    if not any(x is not None for x in (dern.get("valeurs") or {}).values()):   # v1.0i : dernier releve VALIDE
        dern = dernier_valide() or dern
    jours = []
    try:
        fichiers = sorted(n for n in os.listdir(DATA) if re.match(r"^\d{4}-\d{2}-\d{2}\.jsonl$", n))[-7:]
    except OSError:
        fichiers = []
    for n in reversed(fichiers):
        prod = conso = 0.0
        sans_res = 0.0
        bmin = None
        prec = None
        try:
            for l in open(os.path.join(DATA, n), encoding="utf-8"):
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                v = r.get("valeurs") or {}
                try:
                    t = time.mktime(time.strptime(str(r.get("horodatage", ""))[:19], "%Y-%m-%dT%H:%M:%S"))
                except ValueError:
                    continue
                dt_h = min(max(t - prec, 0), 900) / 3600.0 if prec else 5 / 60.0
                prec = t
                if v.get("pv_w") is not None:
                    prod += max(v["pv_w"], 0) * dt_h / 1000
                if v.get("charge_puissance_w") is not None:
                    conso += max(v["charge_puissance_w"], 0) * dt_h / 1000
                if v.get("reseau_tension_v") is not None and v["reseau_tension_v"] <= 150:
                    sans_res += dt_h
                if v.get("batterie_soc_pct") is not None:
                    bmin = v["batterie_soc_pct"] if bmin is None else min(bmin, v["batterie_soc_pct"])
        except OSError:
            continue
        jours.append((n[8:10] + "/" + n[5:7], prod, conso, bmin, sans_res))
    return dern, jours


def dernier_valide():
    """v1.0i : releve le plus recent avec au moins une valeur (2 derniers jours), marque « ancien »."""
    try:
        fichiers = sorted(n for n in os.listdir(DATA) if re.match(r"^\d{4}-\d{2}-\d{2}\.jsonl$", n))[-2:]
    except OSError:
        return None
    for n in reversed(fichiers):
        trouve = None
        try:
            for l in open(os.path.join(DATA, n), encoding="utf-8"):
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                if any(x is not None for x in (r.get("valeurs") or {}).values()):
                    trouve = r
        except OSError:
            continue
        if trouve:
            trouve["ancien"] = True
            return trouve
    return None


def section_info():
    dern, jours = donnees_locales()
    v = dern.get("valeurs") or {}
    res = v.get("reseau_tension_v")
    bp = v.get("batterie_puissance_w")
    etat_bat = "" if bp is None else (" - en charge" if bp > 0 else " - alimente la maison" if bp < 0 else "")
    cartes = [("Batterie", _fr(v.get("batterie_soc_pct")) + " %" + etat_bat),
              ("Solaire", _fr(v.get("pv_w")) + " W"),
              ("Consommation", _fr(v.get("charge_puissance_w")) + " W"),
              ("Reseau electrique", "-" if res is None else ("present" if res > 150 else "absent"))]
    direct = "".join("<tr><td>%s</td><td><b>%s</b></td></tr>" % (html.escape(a), html.escape(b)) for a, b in cartes)
    lignes = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        d, _fr(p, 1), _fr(c, 1), "-" if b is None else _fr(b) + " %", _fr(sr, 1)) for d, p, c, b, sr in jours)
    titre = "Dernier releve valide" if dern.get("ancien") else "En direct"      # v1.0i
    return ("<div class=carte><b>" + titre + "</b> <small>(releve du %s)</small><table>%s</table></div>"
            "<div class=carte><b>Les 7 derniers jours</b><table><tr><td><small>Jour</small></td><td><small>Solaire kWh</small>"
            "</td><td><small>Conso. kWh</small></td><td><small>Batterie min.</small></td><td><small>Heures sans reseau"
            "</small></td></tr>%s</table><small>Valeurs lues sur le boitier, sans internet. Les kWh et les heures sont "
            "calcules a partir des releves toutes les 5 minutes.</small></div>") % (
        html.escape(str(dern.get("horodatage", "-"))[:16].replace("T", " a ")), direct,
        lignes or "<tr><td colspan=5>Aucun releve garde pour l'instant.</td></tr>")


def champ_code():
    if MODE["m"] != "info":
        return ""
    if ETAT["codes_faux"] >= ESSAIS_CODE_MAX:
        return "<p><b>Trop de codes faux : modification du Wi-Fi bloquee.</b> Appelez le +226 25 46 53 00.</p>"
    return ("<label>Code technicien OPTI-MIST SOLUTIONS</label><input name=code type=password autocomplete=off "
            "autocapitalize=off autocorrect=off spellcheck=false required>")


def page_attente(ssid):
    return ("<!doctype html><html lang=fr><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'><style>%s</style></head><body>"
            "<header>OPTI-MIST <b>SOLUTIONS</b></header><main><div class=carte>"
            "<b>Le boitier se connecte au Wi-Fi &laquo; %s &raquo;.</b><br><br>"
            "Ce Wi-Fi %s va se fermer : votre telephone va s'en deconnecter.<br><br>"
            "Si la connexion echoue, le Wi-Fi <b>%s</b> se rouvre dans 3 minutes environ : reconnectez-vous et "
            "verifiez le mot de passe.<br><br>Si elle reussit, le boitier apparait dans la supervision "
            "au relevé suivant (5 minutes environ).</div></main></body></html>") % (
        STYLE, html.escape(ssid), "de consultation" if MODE["m"] == "info" else "de configuration",
        html.escape(ssid_config()))


class Page(BaseHTTPRequestHandler):
    server_version = "OPTI"

    def log_message(self, *a):
        pass

    def envoyer(self, corps, code=200):
        b = corps.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.headers.get("Host", "").split(":")[0] not in (AP_IP,):
            self.send_response(302)                  # detection de portail des telephones -> notre page
            self.send_header("Location", "http://%s/" % AP_IP)
            self.end_headers()
            return
        if not POSE["premiere_visite"]:
            POSE["premiere_visite"] = depuis_demarrage()     # v1.0e ; v1.0i : horloge du demarrage
        self.envoyer(page_principale())

    def do_POST(self):
        n = min(int(self.headers.get("Content-Length") or 0), 4096)
        f = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        libre = f.get("ssid_libre", [""])[0].strip()[:32]
        ssid = (libre or f.get("ssid", [""])[0].strip())[:32]
        ETAT["masque"] = bool(libre) and libre not in [s for s, _ in ETAT["reseaux"]]   # v1.0c
        mdp = f.get("mdp", [""])[0]
        if not ssid:
            ETAT["message"] = "Choisissez un Wi-Fi."
            return self.envoyer(page_principale())
        if mdp and not (8 <= len(mdp) <= 63):
            ETAT["message"] = "Le mot de passe d'un Wi-Fi fait de 8 a 63 caracteres."
            return self.envoyer(page_principale())
        if MODE["m"] == "info":                                                       # v1.0h : code technicien
            if ETAT["codes_faux"] >= ESSAIS_CODE_MAX or not code_technicien_ok(f.get("code", [""])[0][:64]):
                ETAT["codes_faux"] += 1
                log("code technicien refuse (%d)" % ETAT["codes_faux"])
                ETAT["message"] = "Code technicien incorrect." if ETAT["codes_faux"] < ESSAIS_CODE_MAX else \
                    "Trop de codes faux : modification bloquee jusqu'a la fermeture de ce Wi-Fi."
                return self.envoyer(page_principale())
        tech = re.sub(r"[^A-Za-z. -]", "", f.get("tech", [""])[0])[:12].strip().upper()   # v1.0e
        if not re.search(r"[A-Z]", tech):                                              # v1.0f : obligatoire
            ETAT["message"] = "Tapez vos initiales (technicien) avant de connecter le boitier."
            return self.envoyer(page_principale())
        ETAT["message"] = ""
        POSE["technicien"] = tech
        POSE["validation"] = depuis_demarrage()           # v1.0i
        POSE["essais"] += 1
        self.envoyer(page_attente(ssid))
        ETAT["demande"] = (ssid, mdp)


def a_internet():
    for hote in (("1.1.1.1", 443), ("8.8.8.8", 53)):
        try:
            socket.create_connection(hote, timeout=5).close()
            return True
        except OSError:
            pass
    return False


def garder_avant(anciens):
    """v1.0i : copie de la liste d'avant l'essai (root 600), retablie si l'essai est interrompu (coupure, redemarrage)."""
    os.makedirs(CONF, exist_ok=True)
    ecrire_sur(ESSAI_AVANT, json.dumps({"pid": os.getpid(), "anciens": anciens}, ensure_ascii=False))   # v1.0j : force


def essai_vivant(pid):
    """v1.0i : l'essai est-il encore en cours (meme processus wifi_config vivant) ?"""
    try:
        return pid != os.getpid() and b"wifi_config" in open("/proc/%d/cmdline" % int(pid), "rb").read()
    except (OSError, ValueError, TypeError):
        return False


def fin_essai():
    if os.path.exists(ESSAI_AVANT):
        os.remove(ESSAI_AVANT)
        try:
            os.sync()                                   # v1.0j
        except OSError:
            pass


def retablir_essai_interrompu():
    """v1.0i : un essai de Wi-Fi n'a pas abouti (coupure pendant les 120 s) -> on remet les Wi-Fi d'avant."""
    if not os.path.exists(ESSAI_AVANT):
        return False
    try:
        g = json.load(open(ESSAI_AVANT))
    except (OSError, ValueError):
        g = {}
    if essai_vivant(g.get("pid")):              # essai en cours (120 s) : ne rien toucher
        return False
    anciens = g.get("anciens")
    if not isinstance(anciens, list):
        fin_essai()
        return False
    ecrire_clients(anciens)
    fin_essai()
    sh(["netplan", "generate"], timeout=60)
    sh(["systemctl", "restart", "netplan-wpa-%s.service" % IFACE])
    log("ESSAI DE WI-FI INTERROMPU (coupure ?) : Wi-Fi d'avant retablis (%s)" % (
        ", ".join(c["ssid"] for c in anciens) or "aucun"))
    return True


def essayer(ap, ssid, mdp):
    """Ferme le point d'acces, enregistre le Wi-Fi choisi, attend une adresse ; sinon le retire.
    v1.0i : la liste d'avant est gardee sur disque jusqu'au resultat (retablie si l'essai est coupe)."""
    anciens = clients()
    nouveaux = [c for c in anciens if c["ssid"] != ssid] + [{"ssid": ssid, "mdp": mdp, "masque": ETAT.get("masque", False),
                                                            "ajoute": time.strftime("%Y-%m-%d %H:%M")}]
    garder_avant(anciens)                      # v1.0j : sur le disque AVANT le nouveau Wi-Fi
    log("essai du Wi-Fi « %s » lance (%d s au plus) ; Wi-Fi d'avant gardes" % (ssid, ESSAI_S))
    ecrire_clients(nouveaux)
    ap.fermer()
    t0 = time.time()
    fin = t0 + ESSAI_S
    while time.time() < fin:
        time.sleep(3)
        if IFACE in adresses():
            duree = int(time.time() - t0)
            time.sleep(3)
            log("CONNECTE au Wi-Fi « %s » (%s) en %d s ; internet : %s" % (ssid, adresses().get(IFACE), duree,
                                                                        "oui" if a_internet() else "non"))
            POSE["connecte"] = depuis_demarrage() - 3    # v1.0e ; v1.0i
            fin_essai()                                  # v1.0i : le nouveau Wi-Fi est valide
            try:
                finir_pose(ssid)
            except Exception as e:                       # le rapport ne doit jamais empecher la connexion
                log("rapport de pose : erreur %s" % type(e).__name__)
            return True
    log("ECHEC de connexion au Wi-Fi « %s » (mot de passe ? signal ?)" % ssid)
    ecrire_clients(anciens)                    # on ne garde pas un Wi-Fi qui ne marche pas
    fin_essai()
    return False


def session(duree=DUREE_S, mode="config"):
    """Ouvre le point d'acces, sert la page, traite les demandes ; ferme au plus tard a DUREE_MAX_S."""
    MODE["m"] = mode                                 # v1.0g
    DUREE_PAGE["s"] = duree                          # v1.0i
    debut = time.time()
    fin = debut + duree
    ETAT["reseaux"] = scanner()
    log("%d Wi-Fi visibles avant ouverture" % len(ETAT["reseaux"]))
    ap = PointAcces()
    srv = None

    def arret(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, arret)
    try:
        ap.ouvrir()
        POSE["ap_ouvert"] = POSE["ap_ouvert"] if POSE["ap_ouvert"] is not None else depuis_demarrage()   # v1.0e ; v1.0i
        srv = ThreadingHTTPServer((AP_IP, 80), Page)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        while time.time() < fin:
            time.sleep(1)
            if ETAT["demande"]:
                ssid, mdp = ETAT["demande"]
                ETAT["demande"] = None
                time.sleep(3)                           # laisser la page partir vers le telephone
                srv.shutdown()
                srv.server_close()
                srv = None
                if essayer(ap, ssid, mdp):
                    return True
                if time.time() - debut > DUREE_MAX_S - 120:
                    log("plafond de 30 min atteint : pas de nouvelle ouverture")
                    return False
                time.sleep(30)
                ETAT["reseaux"] = scanner()
                ETAT["message"] = ("Le boitier n'a pas pu se connecter a « %s ». Verifiez le mot de passe "
                                   "et reessayez." % ssid)
                fin = min(max(fin, time.time() + 5 * 60), debut + DUREE_MAX_S)
                ap.ouvrir()
                srv = ThreadingHTTPServer((AP_IP, 80), Page)
                threading.Thread(target=srv.serve_forever, daemon=True).start()
        log("%d minutes ecoulees sans configuration" % (duree // 60))
        return False
    except KeyboardInterrupt:
        log("arret demande")
        return False
    finally:
        if srv:
            srv.shutdown()
            srv.server_close()
        if ap.procs or os.path.exists(NET_AP):
            ap.fermer()


def auto():
    try:
        retablir_essai_interrompu()                 # v1.0i
    except Exception as e:
        log("retablissement apres essai : erreur %s" % type(e).__name__)
    if os.path.exists(DESACTIVE):
        log("desactive (%s) : rien a faire" % DESACTIVE)
        return
    connus = connus_tous()                      # v1.0d : Wi-Fi clients + atelier
    t0 = time.time()
    attente = ATTENTE_CONNU_S if connus else ATTENTE_NEUF_S
    log("demarrage : %d Wi-Fi connu(s) ; ouverture a %d s si le boitier reste sans adresse" % (len(connus), attente))
    decide = not connus
    while True:
        if adresses():
            log("en ligne (%s) : Wi-Fi de configuration non ouvert" % ", ".join(adresses()))
            renvoyer_pose_en_attente()                  # v1.0e
            return
        ecoule = time.time() - t0
        if not decide and ecoule >= ATTENTE_CONNU_S:
            decide = True
            visibles = {s for s, _ in scanner()}
            attente = ATTENTE_VISIBLE_S if visibles & set(connus) else ATTENTE_ABSENT_S
            log("sans adresse ; Wi-Fi connu %s : ouverture a %d s si rien ne change" % (
                "visible" if attente == ATTENTE_VISIBLE_S else "invisible", attente))
        if ecoule >= attente:
            break
        time.sleep(5)
    if connus:                                      # v1.0g : boitier deja installe -> consultation + Wi-Fi technicien
        log("sans adresse depuis %d s : ouverture du Wi-Fi de consultation" % attente)
        session(DUREE_S, mode="info")
    else:
        log("sans adresse depuis %d s : ouverture du Wi-Fi de configuration" % attente)
        session()


def etat():
    print(VERSION, "-", ssid_config())
    print("adresses        :", adresses() or "aucune")
    print("Wi-Fi clients   :", ", ".join("%s (%s)" % (c["ssid"], c.get("ajoute", "")) for c in clients()) or "aucun")
    print("Wi-Fi atelier   :", ", ".join(atelier()) or "aucun")
    print("pret a expedier :", "OUI (aucun Wi-Fi enregistre)" if not connus_tous() else
          "NON : lancer « opti-wifi oublier --tout » avant l'expedition")
    print("desactive       :", "oui" if os.path.exists(DESACTIVE) else "non")
    print("code technicien :", "enregistre" if os.path.exists(CODE_TECH) else "ABSENT : lancer « opti-wifi code »")
    print("point d'acces   :", "OUVERT" if os.path.exists(NET_AP) else "ferme")
    conv, horo, n = convertisseurs()
    print("convertisseurs  :", ", ".join("%s=%s" % (c[0], c[2]) for c in conv) or "aucun", "(%s prises, %s)" % (n, horo))
    try:
        print("derniers evenements :")
        print("".join(open(JOURNAL).readlines()[-8:]), end="")
    except OSError:
        print("  aucun")


def main():
    if os.geteuid() != 0:
        sys.exit("Lancer en root")
    a = sys.argv[1] if len(sys.argv) > 1 else "etat"
    if a == "auto":
        auto()
    elif a == "ouvrir":
        if not (shutil.which("hostapd") and shutil.which("dnsmasq")):
            sys.exit("hostapd ou dnsmasq manquant : lancer install_wifi_config.sh")
        session()
    elif a == "info":                                    # v1.0g ; v1.0h : duree en minutes facultative
        mn = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else INFO_S // 60
        session(max(5, min(mn, 30)) * 60, mode="info")
    elif a == "code":                                    # v1.0h : saisie du code technicien (jamais affiche)
        import getpass
        c1 = getpass.getpass("Code technicien (6 caracteres ou plus) : ")
        c2 = getpass.getpass("Retaper le code : ")
        if c1 != c2 or len(c1.strip()) < 6:
            sys.exit("Codes differents ou trop courts : rien n'est change.")
        os.makedirs(CONF, exist_ok=True)
        fd = os.open(CODE_TECH + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(empreinte_code(c1) + "\n")
        os.replace(CODE_TECH + ".tmp", CODE_TECH)
        print("Code technicien enregistre (empreinte seulement, root 600).")
    elif a == "commande":                                # v1.0f
        commande()
    elif a == "pose":                                    # v1.0e
        renvoyer_pose_en_attente()
        try:
            dernier = open(POSES).read().strip().splitlines()[-1]
            print(json.dumps(json.loads(dernier), ensure_ascii=False, indent=1))
        except (OSError, IndexError, ValueError):
            print("aucun rapport de pose")
        print("en attente d'envoi :", "oui" if os.path.exists(POSE_ATTENTE) else "non")
    elif a == "etiquette":
        print("Wi-Fi de configuration : %s   (consultation client : %s)" % ssids_boitier())
        print("Mot de passe           : %s" % mot_de_passe_config())
        print("(a recopier sur l'etiquette du boitier ; ne jamais l'envoyer par message ni en capture)")
    elif a == "oublier" and len(sys.argv) > 2:
        nom = sys.argv[2]
        tout = nom == "--tout"
        reste = [] if tout else [c for c in clients() if c["ssid"] != nom]
        ecrire_clients(reste)
        if tout or nom in atelier():                # v1.0d : le fichier d'atelier est range entier
            ranger_atelier()
        sh(["netplan", "generate"], timeout=60)
        sh(["systemctl", "restart", "netplan-wpa-%s.service" % IFACE])
        print("Wi-Fi clients restants :", ", ".join(c["ssid"] for c in reste) or "aucun")
        print("Wi-Fi atelier restants :", ", ".join(atelier()) or "aucun")
        if "end0" in adresses() or "eth0" in adresses():
            print("Attention : un cable reseau est branche ; debrancher pour tester le Wi-Fi de configuration.")
    else:
        etat()


if __name__ == "__main__":
    main()
