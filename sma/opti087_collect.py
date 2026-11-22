#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTI-MIST SOLUTIONS - Collecte supervision site OPTI-087
Lecture des onduleurs SMA (directement, ou par Modbus TCP du Data Manager) et envoi vers la plateforme.

v1.9 (GO S.S. 22/11/2026 12h58) : EVENEMENTS 24 H et NUIT, toujours en lecture seule.
  - Le DIRECT porte, par onduleur, le dernier evenement des 24 dernieres heures (ondN_evt24 = code, ondN_evt24_hhmm =
    heure HHMM du site, ondN_evt24_nb = nombre sur 24 h). La plateforme les garde jusqu'a leur prise en compte
    (encart « Evenements des 24 dernieres heures » du tableau de bord) : un defaut du matin reste visible le soir.
  - Nuit (entre nuit_debut et nuit_fin, [site], 19 h et 6 h par defaut) : onduleurs en veille et non lus = statut NUIT
    (et plus ONDULEURS_INJOIGNABLES) ; l'historique garde HORS LIGNE avec l'alerte « NUIT : ... boitier en ligne » :
    les heures de nuit deviennent « non imputables » (boitier vivant, centrale a l'arret normal) au lieu d'« inconnues ».
v1.8 (GO S.S. 15/11/2026 22h35) : JOURNAL D'EVENEMENTS et COMPTEUR, toujours en lecture seule.
  - Evenements : a chaque releve, dans la meme session Speedwire, le boitier lit le journal d'evenements de chaque
    onduleur depuis le dernier evenement connu (commande de lecture du journal, droit du compte configure). Les
    evenements sont gardes sur le boitier (evenements.jsonl, 60 jours) et le DIRECT porte, par onduleur, le dernier
    code des 60 dernieres minutes (ondN_evt) et leur nombre (ondN_evt_nb). Libelles : table EVENEMENTS (codes vus
    sur le site en 2026 : 101, 1302, 3501, 3701, 7702 - M, journal installateur ; autres libelles a confirmer, S).
    Nouveau mode : --evenements [jours] (affiche le journal et le nombre par code ; validation terrain).
  - Compteur : ecoute PASSIVE du compteur d'energie SMA (multicast Speedwire 239.12.255.254:9522), sans connexion ni
    mot de passe. S'il en existe un sur le reseau, le DIRECT porte compteur_import_w / compteur_export_w et les index
    compteur_import_kwh / compteur_export_kwh. Sinon rien n'est envoye. Nouveau mode : --compteur (ecoute 10 s).
  - Mise a jour automatique : voir boitiers/maj_auto (verifie l'empreinte publiee avant toute installation).

v1.7 (GO S.S. 15/11/2026 09h38, arret du groupe 1 a 9h20) : le DIRECT porte aussi, pour chaque onduleur, la tension
reseau la plus haute des 3 phases (ondN_v), la frequence (ondN_hz), la puissance DC des panneaux (ondN_dc_w) et l'etat
du relais reseau (ondN_relais : 51 ferme, 311 ouvert). Lecture seule, aucun parametre ecrit. Sert a distinguer a distance :
plus de reseau en sortie (0 V), surtension (> 253 V), panneaux absents (DC 0 W) ou defaut interne de l'onduleur.
v1.6 (14/11/2026 18h20) : le DIRECT (toutes les 5 min) porte aussi le detail des onduleurs : lus / attendus / en
anomalie, energie du jour, et pour chacun (ordre terrain 1-9) puissance, etat SMA, energie du jour. Nombres seulement.
v1.5 (14/11/2026 17h10) : la lecture directe passe par SPEEDWIRE (UDP 9522, protocole de Sunny Explorer) : les
STP 20000TL-30 du site n'ont pas d'interface web (ports 80/443 fermes, M).
v1.4 (ordre S.S. 14/11/2026 16h36) : SOURCE "onduleurs". Le boitier lit directement les 9 onduleurs,
EN LECTURE SEULE, sans passer par le Data Manager (onduleurs non
enregistres dans le Data Manager, mot de passe de celui-ci inconnu). La centrale = somme des onduleurs lus.
Securite mot de passe : au premier refus de connexion, le boitier se bloque (fichier verrou) et ne retente plus
rien tant que S.S. n'a pas lance "opti087 deverrouiller" -> jamais plusieurs essais de mot de passe.
Les adresses IP sont retrouvees automatiquement par les numeros de serie (sans connexion), DHCP ou pas.
Nouveau mode : --sonde (liste les onduleurs trouves avec leurs valeurs).

v1.3 (GO S.S. 13/11/2026 14h45) : DIRECT. A chaque releve, le dernier releve (puissance AC de la centrale) part aussi
vers la carte "Boitiers en direct" du tableau de bord si direct_url et direct_jeton sont renseignes dans la section
[envoi] de la configuration. Un echec du direct ne bloque ni le stockage ni l'envoi horaire.

v1.2 (GO S.S. 13/11/2026 03h13) : envoi dans l'HISTORIQUE FUSIONNE, au meme format que le boitier Felicity
(une ligne par heure : PV_W = puissance AC de la centrale ; pas de batterie ni de charge sur ce site), avec
RATTRAPAGE apres coupure internet (une ligne par heure non transmise, tiree du stock local, 7 jours au plus).
La v1.0 envoyait un autre format et effacait sa file sur simple reponse HTTP 200 : risque de perte, corrige ici
(la file n'est videe que sur reponse "ok" du webhook).

Aucune dependance externe : Python 3 standard uniquement.

Modes :
  opti087_collect.py --scan     cherche les Unit ID qui repondent (validation terrain)
  opti087_collect.py --once     un releve : lecture + sauvegarde locale + envoi
  opti087_collect.py --show     affiche le dernier releve enregistre
  opti087_collect.py --sonde    v1.4 : trouve les onduleurs et affiche leurs valeurs (lecture directe)
"""
import argparse
import configparser
import datetime as dt
import json
import os
import concurrent.futures
import socket
import ssl
import struct
import sys
import urllib.request

CONF_PATH = "/etc/opti087/opti087.conf"
VERSION = "1.9 (22/11/2026)"

# ---------------------------------------------------------------------------
# Registres SMA (profil SMA standard). A VALIDER SUR SITE avec --scan
# et en comparant aux valeurs de l'interface web du Data Manager.
# (nom, adresse, type, diviseur)
# ---------------------------------------------------------------------------
REG_PLANT = [
    ("puissance_ac_w",     30775, "S32", 1),
    ("energie_jour_wh",    30535, "U32", 1),
    ("energie_totale_wh",  30529, "U32", 1),
]
REG_ONDULEUR = [
    ("etat",               30201, "U32", 1),
    ("puissance_ac_w",     30775, "S32", 1),
    ("energie_jour_wh",    30535, "U32", 1),
    ("energie_totale_wh",  30529, "U32", 1),
    ("tension_l1_v",       30783, "U32", 100),
    ("tension_l2_v",       30785, "U32", 100),
    ("tension_l3_v",       30787, "U32", 100),
    ("frequence_hz",       30803, "U32", 100),
    ("dc_a_puissance_w",   30773, "S32", 1),
    ("dc_b_puissance_w",   30961, "S32", 1),
    ("temperature_c",      30953, "S32", 10),
]
ETATS = {35: "DEFAUT", 303: "ARRET", 307: "OK", 455: "AVERTISSEMENT"}
# v1.8 : numeros d'evenement SMA (onduleurs STP). M = vus sur le site (journal installateur 05-14/11/2026),
# S = libelle courant de la documentation SMA, a confirmer sur la notice du modele.
EVENEMENTS = {
    101: "Surtension reseau (valeur instantanee) (M)", 102: "Surtension reseau (S)", 103: "Surtension reseau (S)",
    202: "Sous-tension / coupure reseau (S)", 203: "Sous-tension / coupure reseau (S)", 205: "Sous-tension reseau (S)",
    301: "Tension moyenne 10 min trop haute (S)", 401: "Ilotage / saut de frequence (S)", 404: "Ilotage (S)",
    501: "Frequence reseau hors plage (S)", 601: "Composante continue sur le reseau (S)", 701: "Frequence non autorisee (S)",
    801: "Attente de la tension reseau / coupure (S)", 901: "Conducteur de protection non raccorde (S)",
    1001: "Phase et neutre inverses (S)", 1302: "Phase ou neutre non connecte / point de raccordement (M)",
    1501: "Defaut de reconnexion au reseau (S)", 3301: "Fonctionnement instable : DC insuffisant (S)",
    3401: "Surtension DC (S)", 3402: "Surtension DC (S)", 3501: "Erreur d'isolement (M)",
    3601: "Courant de fuite eleve (S)", 3701: "Courant de defaut trop eleve (M)", 3801: "Surintensite DC (S)",
    3901: "Attente des conditions de demarrage DC (S)", 6501: "Surtemperature (S)", 6502: "Surtemperature (S)",
    6603: "Surcharge (S)", 6701: "Communication perturbee (S)", 7001: "Defaut capteur (S)",
    7702: "Diagnostic automatique / dysfonctionnement onduleur (M)", 8001: "Derating (reduction de puissance) (S)",
}

NAN = {"S32": 0x80000000, "U32": 0xFFFFFFFF}


# ---------------------------------------------------------------------------
# Client Modbus TCP minimal (fonctions 03 puis 04 en secours)
# ---------------------------------------------------------------------------
class ModbusTCP:
    def __init__(self, host, port=502, timeout=4.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock, self.tid = None, 0

    def __enter__(self):
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)
        return self

    def __exit__(self, *a):
        try:
            self.sock.close()
        except Exception:
            pass

    def _recv(self, n):
        buf = b""
        while len(buf) < n:
            part = self.sock.recv(n - len(buf))
            if not part:
                raise ConnectionError("connexion fermee par l'appareil")
            buf += part
        return buf

    def read(self, unit, addr, count, fc=3):
        self.tid = (self.tid + 1) % 65536
        pdu = struct.pack(">BHH", fc, addr, count)
        self.sock.sendall(struct.pack(">HHHB", self.tid, 0, len(pdu) + 1, unit) + pdu)
        _, _, length, _ = struct.unpack(">HHHB", self._recv(7))
        body = self._recv(length - 1)
        if body[0] & 0x80:
            raise IOError("exception Modbus %d" % body[1])
        return body[2:2 + body[1]]

    def read_value(self, unit, addr, typ):
        try:
            raw = self.read(unit, addr, 2, 3)
        except IOError:
            raw = self.read(unit, addr, 2, 4)
        val = struct.unpack(">i" if typ == "S32" else ">I", raw)[0]
        if (val & 0xFFFFFFFF) == NAN[typ]:
            return None
        return val


def lire_bloc(cli, unit, registres):
    out = {}
    for nom, addr, typ, div in registres:
        try:
            v = cli.read_value(unit, addr, typ)
            out[nom] = None if v is None else (v / div if div != 1 else v)
        except (IOError, socket.timeout) as e:
            out[nom] = None
            out.setdefault("_erreurs", []).append("%s:%s" % (addr, e))
    if "etat" in out and out["etat"] is not None:
        out["etat_texte"] = ETATS.get(out["etat"], str(out["etat"]))
    return out


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def charger_conf(path):
    c = configparser.ConfigParser()
    if not c.read(path, encoding="utf-8"):
        sys.exit("Configuration introuvable : %s" % path)
    s = c["site"]
    ids = [int(x) for x in s.get("unit_ids_onduleurs", "").replace(" ", "").split(",") if x]
    return {
        "code": s.get("code_site", "OPTI-087"),
        "host": s.get("ip_data_manager", "192.168.1.124"),
        "port": s.getint("port_modbus", 502),
        "unit_plant": s.getint("unit_id_centrale", 2),
        "unit_ond": ids,
        "dossier": s.get("dossier_donnees", "/var/lib/opti087"),
        "jours": s.getint("jours_conserves", 60),
        "nuit_debut": s.getint("nuit_debut", 19),      # v1.9 : heure du site
        "nuit_fin": s.getint("nuit_fin", 6),
        "url": c["envoi"].get("url", "").strip(),
        "jeton": c["envoi"].get("jeton", "").strip(),
        "direct_url": c["envoi"].get("direct_url", "").strip(),       # v1.3
        "direct_jeton": c["envoi"].get("direct_jeton", "").strip(),   # v1.3 (coffre uniquement)
        # v1.4 : lecture directe des onduleurs
        "source": (c["onduleurs"].get("source", "data_manager") if c.has_section("onduleurs") else "data_manager").strip(),
        "reseau": (c["onduleurs"].get("reseau", "192.168.1") if c.has_section("onduleurs") else "192.168.1").strip(),
        "droit": (c["onduleurs"].get("droit", "istl") if c.has_section("onduleurs") else "istl").strip(),
        "mdp": (c["onduleurs"].get("mot_de_passe", "") if c.has_section("onduleurs") else ""),
        "series": [x.strip() for x in (c["onduleurs"].get("numeros_serie", "") if c.has_section("onduleurs") else "").split(",") if x.strip()],
    }


# ---------------------------------------------------------------------------
# Stockage local + file d'attente d'envoi
# ---------------------------------------------------------------------------
def sauver(cfg, rec):
    os.makedirs(cfg["dossier"], exist_ok=True)
    jour = rec["horodatage"][:10]
    with open(os.path.join(cfg["dossier"], jour + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with open(os.path.join(cfg["dossier"], "dernier.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)


def purger(cfg):
    limite = (dt.date.today() - dt.timedelta(days=cfg["jours"])).isoformat()
    ancienne = os.path.join(cfg["dossier"], "a_envoyer.jsonl")   # file de la v1.0, remplacee par le rattrapage v1.2
    if os.path.exists(ancienne):
        os.remove(ancienne)
    for n in os.listdir(cfg["dossier"]):
        if n.endswith(".jsonl") and n[:10] < limite and n[:4].isdigit():
            os.remove(os.path.join(cfg["dossier"], n))


RATTRAPAGE_H = 168      # 7 jours au plus
LOT = 48


def heure(d):
    return d.strftime("%Y-%m-%dT%H")


def ligne_historique(rec, cfg):
    """Un releve local -> une ligne de l'historique fusionne (date = heure du releve)."""
    ok = rec.get("statut") == "OK"
    p = (rec.get("centrale") or {}).get("puissance_ac_w")
    quand = dt.datetime.fromisoformat(rec["horodatage"])
    return {"date": quand.strftime("%d/%m/%Y %H:%M"), "date_only": quand.strftime("%d/%m/%Y"),
            "site": cfg["code"], "pv_w": round(p) if (ok and p is not None) else "",
            "load_w": "", "batt_pct": "", "grid_w": "",      # non mesures sur ce site : jamais inventes
            "mode": "Grid" if ok else "-", "eco_fcfa": 0,
            "statut": "OK" if ok else "HORS LIGNE", "alertes": (rec.get("alertes") or "")[:200]}   # v1.9 : nuit = HORS LIGNE + alerte NUIT


def releves_par_heure(cfg, depuis):
    out = {}
    for n in sorted(os.listdir(cfg["dossier"])):
        if not (n.endswith(".jsonl") and n[:4].isdigit()) or n[:10] < depuis[:10]:
            continue
        for l in open(os.path.join(cfg["dossier"], n), encoding="utf-8"):
            try:
                r = json.loads(l)
                h = heure(dt.datetime.fromisoformat(r["horodatage"]))
            except Exception:
                continue
            if h > depuis and (h not in out or r["horodatage"] > out[h]["horodatage"]):
                out[h] = r
    return out


def envoyer(cfg):
    if not cfg["url"]:
        print("Envoi : aucune URL configuree, donnees gardees en local (rattrapees des que l'URL est renseignee, 7 jours).")
        return
    etat = os.path.join(cfg["dossier"], "envoi_etat.json")
    maint = dt.datetime.now()
    try:
        derniere = json.load(open(etat))["derniere_heure"]
    except (OSError, ValueError, KeyError):
        derniere = None
    plancher = heure(maint - dt.timedelta(hours=RATTRAPAGE_H))
    if derniere is None or derniere < plancher:
        derniere = plancher
    if derniere >= heure(maint):
        return
    a_envoyer = sorted(releves_par_heure(cfg, derniere).items())
    envoyees = 0
    for i in range(0, len(a_envoyer), LOT):
        lot = a_envoyer[i:i + LOT]
        try:
            req = urllib.request.Request(cfg["url"], data=json.dumps({"rows": [ligne_historique(r, cfg) for _, r in lot],
                                         "deduplicate": True}).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("Envoi : echec (%s), %d/%d ligne(s) transmise(s), reprise au prochain passage." % (type(e).__name__, envoyees, len(a_envoyer)))
            return
        if res.get("status") != "ok":
            print("Envoi : refuse par l'historique, %d/%d ligne(s) transmise(s)." % (envoyees, len(a_envoyer)))
            return
        envoyees += len(lot)
        with open(etat, "w") as f:
            json.dump({"derniere_heure": lot[-1][0], "maj": maint.isoformat(timespec="seconds")}, f)
    print("Envoi : %d ligne(s) transmise(s)." % envoyees)


def envoyer_direct(cfg, rec):
    """v1.3 : dernier releve -> carte "Boitiers en direct" (valeurs lues telles quelles)."""
    if not cfg["direct_url"] or not cfg["direct_jeton"]:
        return "Direct : non configure."
    c = rec.get("centrale") or {}
    p = c.get("puissance_ac_w")
    v = {"pv_w": p, "puissance_ac_w": p} if (rec.get("statut") == "OK" and p is not None) else {}
    if "onduleurs_attendus" in c:      # v1.6 : detail des onduleurs (source = onduleurs)
        v["onduleurs_lus"] = c.get("onduleurs_lus")
        v["onduleurs_attendus"] = c.get("onduleurs_attendus")
        onds = rec.get("onduleurs") or {}
        v["onduleurs_anormaux"] = sum(1 for o in onds.values() if o.get("etat") not in (None, 307) and "numero_serie" in o and o.get("etat_texte") != "NON_LU")
        if c.get("energie_jour_wh") is not None:
            v["energie_jour_kwh"] = round(c["energie_jour_wh"] / 1000, 1)
        for k, o in onds.items():
            n = k.replace("OND", "ond")
            if o.get("puissance_ac_w") is not None:
                v[n + "_w"] = o["puissance_ac_w"]
            if o.get("etat") is not None:
                v[n + "_etat"] = o["etat"]
            if o.get("energie_jour_wh") is not None:
                v[n + "_jour_kwh"] = round(o["energie_jour_wh"] / 1000, 1)
            tens = [o.get("tension_l%d_v" % i) for i in (1, 2, 3) if o.get("tension_l%d_v" % i) is not None]
            if tens:                                   # v1.7 : diagnostic a distance (lecture seule)
                v[n + "_v"] = round(max(tens), 1)
            if o.get("frequence_hz") is not None:
                v[n + "_hz"] = o["frequence_hz"]
            if o.get("dc_puissance_w") is not None:
                v[n + "_dc_w"] = o["dc_puissance_w"]
            if o.get("relais") is not None:
                v[n + "_relais"] = o["relais"]
            if o.get("evt_nb") is not None:            # v1.8 : evenements des 60 dernieres minutes
                v[n + "_evt_nb"] = o["evt_nb"]
            if o.get("evt") is not None:
                v[n + "_evt"] = o["evt"]
            for s24 in ("evt24", "evt24_nb", "evt24_hhmm"):   # v1.9 : 24 dernieres heures
                if o.get(s24) is not None:
                    v[n + "_" + s24] = o[s24]
    cpt = rec.get("compteur") or {}                    # v1.8 : compteur SMA (ecoute passive)
    for k in ("import_w", "export_w", "import_kwh", "export_kwh"):
        if cpt.get(k) is not None:
            v["compteur_" + k] = cpt[k]
    if v:
        v = {k: x for k, x in v.items() if x is not None}
    corps = {"jeton": cfg["direct_jeton"], "direct": {"code": cfg["code"], "horodatage": rec["horodatage"],
             "statut": rec.get("statut", ""), "mode": "reseau" if v else "-", "valeurs": v}}
    try:
        req = urllib.request.Request(cfg["direct_url"], data=json.dumps(corps).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return "Direct : echec (%s)." % type(e).__name__
    return "Direct : ok." if res.get("status") == "ok" else "Direct : refuse (verifier direct_jeton)."


# ---------------------------------------------------------------------------
# v1.5 : lecture directe des onduleurs par SPEEDWIRE (UDP 9522), le protocole de Sunny Explorer.
# Lecture seule : connexion, lecture des compteurs, deconnexion. Aucun parametre n'est ecrit.
# (v1.4 interrogeait l'interface web : absente sur ces STP 20000TL-30, ports 80/443 fermes - M 14/11 17h07)
# ---------------------------------------------------------------------------
SW_PORT = 9522
APP_SUSY = 125
APP_SERIAL = 900000000 + (os.getpid() % 90000000)
GROUPES = {"istl": (0x0A, 0xBB), "usr": (0x07, 0x88)}
REQUETES = [  # (commande, premier, dernier)
    (0x54000200, 0x00260100, 0x002622FF),   # energie totale + jour
    (0x51000200, 0x00263F00, 0x00263FFF),   # puissance AC
    (0x51800200, 0x00214800, 0x002148FF),   # etat
    (0x51800200, 0x00416400, 0x004164FF),   # v1.7 : relais reseau (51 ferme, 311 ouvert)
    (0x53800200, 0x00251E00, 0x00251EFF),   # puissance DC par entree
    (0x51000200, 0x00464800, 0x004655FF),   # tensions L1-L3 (et courants)
    (0x51000200, 0x00465700, 0x004657FF),   # frequence
]
_pid = [0]


def _paquet(longmots, ctrl, ctrl2, dst_susy, dst_serie, charge):
    _pid[0] = (_pid[0] + 1) & 0x7FFF
    corps = (struct.pack("<I", 0x65601000) + bytes([longmots, ctrl]) +
             struct.pack("<HIHHIHHHH", dst_susy, dst_serie, ctrl2, APP_SUSY, APP_SERIAL, ctrl2, 0, 0, _pid[0] | 0x8000) +
             charge + b"\x00\x00\x00\x00")
    tete = struct.pack("<III", 0x00414D53, 0xA0020400, 0x01000000)
    return tete + struct.pack(">H", 14 + len(corps) - 20) + corps


def _echange(sock, ip, pq, timeout=3.0):
    sock.settimeout(timeout)
    sock.sendto(pq, (ip, SW_PORT))
    fin = dt.datetime.now() + dt.timedelta(seconds=timeout)
    while dt.datetime.now() < fin:
        try:
            data, (src, _) = sock.recvfrom(2048)
        except socket.timeout:
            break
        if src == ip and len(data) >= 42 and data[:4] == b"SMA\x00" and data[14:18] == b"\x00\x10\x60\x65":
            if (struct.unpack_from("<H", data, 40)[0] & 0x7FFF) == _pid[0]:
                return data
    raise socket.timeout("pas de reponse de %s" % ip)


def _socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", SW_PORT))
    except OSError:
        s.bind(("", 0))
    return s


def _echange_multi(sock, ip, pq, timeout=4.0):
    """v1.8 : reponse en plusieurs fragments (journal d'evenements) : liste des paquets, jusqu'au fragment 0."""
    sock.settimeout(timeout)
    sock.sendto(pq, (ip, SW_PORT))
    morceaux, fin = [], dt.datetime.now() + dt.timedelta(seconds=timeout)
    while dt.datetime.now() < fin:
        try:
            data, (src, _) = sock.recvfrom(4096)
        except socket.timeout:
            break
        if src == ip and len(data) >= 58 and data[:4] == b"SMA\x00" and data[14:18] == b"\x00\x10\x60\x65":
            if (struct.unpack_from("<H", data, 40)[0] & 0x7FFF) == _pid[0]:
                morceaux.append(data)
                if struct.unpack_from("<H", data, 38)[0] == 0:
                    break
    return morceaux


def _lire_evenements(sock, ip, susy, serie, groupe, depuis, jusqu):
    """v1.8 : journal d'evenements (lecture seule). Retourne [(horodatage, code, n_entree)]."""
    cmd = 0x70100200 if groupe == 0x0A else 0x70000200   # installateur / utilisateur
    paquets = _echange_multi(sock, ip, _paquet(0x09, 0xE0, 0, susy, serie, struct.pack("<III", cmd, int(depuis), int(jusqu))))
    vus, out = set(), []
    for rep in paquets:
        if struct.unpack_from("<H", rep, 36)[0] != 0:
            continue
        pos, fin = 54, len(rep) - 4
        while pos + 48 <= fin:
            t, entree = struct.unpack_from("<IH", rep, pos)
            code = struct.unpack_from("<H", rep, pos + 12)[0]
            if t and code and (t, entree) not in vus and depuis <= t <= jusqu + 3600:
                vus.add((t, entree))
                out.append((t, code, entree))
            pos += 48
    return sorted(out)


def lire_onduleur_sw(cfg, ip, evt_depuis=None):
    groupe, cle = GROUPES.get(cfg["droit"], GROUPES["istl"])
    mdp = cfg["mdp"].encode("latin-1")[:12]
    code = bytes([((mdp[i] + cle) & 0xFF) if i < len(mdp) else cle for i in range(12)])
    charge = struct.pack("<IIIII", 0xFFFD040C, groupe, 900, int(dt.datetime.now().timestamp()), 0) + code
    sock = _socket()
    try:
        rep = _echange(sock, ip, _paquet(0x0E, 0xA0, 0x0100, 0xFFFF, 0xFFFFFFFF, charge))
        err = struct.unpack_from("<H", rep, 36)[0]
        if err == 0x0100:
            raise RefusMdp("refus du mot de passe par %s" % ip)
        if err != 0:
            raise IOError("connexion refusee (code %d)" % err)
        susy, serie = struct.unpack_from("<HI", rep, 28)
        out = {"ip": ip, "numero_serie": str(serie), "susy_id": susy}
        dc = 0
        vu_dc = False
        for cmd, p1, p2 in REQUETES:
            try:
                rep = _echange(sock, ip, _paquet(0x09, 0xA0, 0, susy, serie, struct.pack("<III", cmd, p1, p2)))
            except socket.timeout:
                continue
            if struct.unpack_from("<H", rep, 36)[0] != 0:
                continue
            taille = {0x54000200: 16, 0x51800200: 40}.get(cmd, 28)
            pos, fin = 54, len(rep) - 4
            while pos + taille <= fin:
                code_r = struct.unpack_from("<I", rep, pos)[0]
                lri, cls = code_r & 0x00FFFF00, code_r & 0xFF
                if cmd == 0x54000200:
                    v = struct.unpack_from("<Q", rep, pos + 8)[0]
                    v = None if v in (0x8000000000000000, 0xFFFFFFFFFFFFFFFF) else v
                    if lri == 0x00260100:
                        out["energie_totale_wh"] = v
                    elif lri == 0x00262200:
                        out["energie_jour_wh"] = v
                elif cmd == 0x51800200:
                    for k in range(8, 40, 4):
                        att = struct.unpack_from("<I", rep, pos + k)[0]
                        if att == 0x00FFFFFE:
                            break
                        if (att >> 24) == 1:
                            out["relais" if lri == 0x00416400 else "etat"] = att & 0x00FFFFFF
                else:
                    v = struct.unpack_from("<i", rep, pos + 8)[0]
                    if v in (-0x80000000, 0x7FFFFFFF):
                        v = None
                    if lri == 0x00263F00:
                        out["puissance_ac_w"] = v
                    elif lri == 0x00251E00 and v is not None:
                        dc += v
                        vu_dc = True
                    elif lri in (0x00464800, 0x00464900, 0x00464A00) and v is not None:
                        out["tension_l%d_v" % ((lri >> 8) - 0x4647)] = v / 100
                    elif lri == 0x00465700 and v is not None:
                        out["frequence_hz"] = v / 100
                pos += taille
        if vu_dc:
            out["dc_puissance_w"] = dc
        if evt_depuis is not None:   # v1.8 : journal d'evenements, meme session (aucune nouvelle connexion)
            try:
                d = evt_depuis.get(str(serie), evt_depuis.get("*")) if isinstance(evt_depuis, dict) else evt_depuis
                out["evenements"] = _lire_evenements(sock, ip, susy, serie, groupe, d, int(dt.datetime.now().timestamp()))
            except Exception as e:
                out["evenements_erreur"] = type(e).__name__
        try:   # deconnexion
            sock.sendto(_paquet(0x08, 0xA0, 0x0300, 0xFFFF, 0xFFFFFFFF, struct.pack("<II", 0xFFFD010E, 0xFFFFFFFF)), (ip, SW_PORT))
        except OSError:
            pass
    finally:
        sock.close()
    if out.get("etat") is not None:
        out["etat_texte"] = ETATS.get(out["etat"], str(out["etat"]))
    return out


def chercher_onduleurs(cfg):
    """Sans connexion : adresses SMA (00:40:ad) vues sur le reseau, Data Manager exclu."""
    ips = set()
    try:
        for l in open("/proc/net/arp").read().splitlines()[1:]:
            c = l.split()
            if len(c) >= 4 and c[3].lower().startswith("00:40:ad") and c[0].startswith(cfg["reseau"] + "."):
                ips.add(c[0])
    except OSError:
        pass
    try:   # annonce Speedwire (multicast) pour reveiller la table ARP
        s = _socket()
        s.settimeout(2)
        s.sendto(bytes.fromhex("534d4100000402a0ffffffff0000002000000000"), ("239.12.255.254", SW_PORT))
        fin = dt.datetime.now() + dt.timedelta(seconds=2)
        while dt.datetime.now() < fin:
            try:
                d, (src, _) = s.recvfrom(2048)
                if d[:4] == b"SMA\x00" and src.startswith(cfg["reseau"] + "."):
                    ips.add(src)
            except socket.timeout:
                break
        s.close()
    except OSError:
        pass
    ips.discard(cfg["host"])     # jamais de connexion au Data Manager
    return sorted(ips, key=lambda x: int(x.split(".")[-1]))


def ecouter_compteur(duree=3.0):
    """v1.8 : ecoute PASSIVE du compteur d'energie SMA (multicast 239.12.255.254:9522). Aucune emission."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", SW_PORT))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton("239.12.255.254") + socket.inet_aton("0.0.0.0"))
    except OSError:
        s.close()
        return None
    s.settimeout(0.5)
    fin = dt.datetime.now() + dt.timedelta(seconds=duree)
    try:
        while dt.datetime.now() < fin:
            try:
                d, (src, _) = s.recvfrom(2048)
            except socket.timeout:
                continue
            if len(d) < 32 or d[:4] != b"SMA\x00" or d[16:18] != b"\x60\x69":
                continue
            out = {"ip": src, "numero_serie": str(struct.unpack_from(">I", d, 20)[0])}
            pos = 28
            while pos + 4 <= len(d):
                b, c, typ, e = d[pos], d[pos + 1], d[pos + 2], d[pos + 3]
                if b == 0 and c == 0 and typ == 0 and e == 0:
                    break
                lg = 8 if typ == 8 else 4
                if pos + 4 + lg > len(d):
                    break
                val = struct.unpack_from(">Q" if lg == 8 else ">I", d, pos + 4)[0]
                if c == 1 and typ == 4:
                    out["import_w"] = round(val / 10.0, 1)
                elif c == 2 and typ == 4:
                    out["export_w"] = round(val / 10.0, 1)
                elif c == 1 and typ == 8:
                    out["import_kwh"] = round(val / 3600000.0, 2)
                elif c == 2 and typ == 8:
                    out["export_kwh"] = round(val / 3600000.0, 2)
                pos += 4 + lg
            return out
    finally:
        try:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, socket.inet_aton("239.12.255.254") + socket.inet_aton("0.0.0.0"))
        except OSError:
            pass
        s.close()
    return None


def verrou(cfg):
    return os.path.join(cfg["dossier"], "VERROU_MOT_DE_PASSE")


class RefusMdp(Exception):
    pass


def lire_onduleurs(cfg, forcer_recherche=False, evt_depuis=None):
    """Retourne (onduleurs par n de serie, message). Leve RefusMdp au premier refus (verrou pose)."""
    if os.path.exists(verrou(cfg)):
        raise RefusMdp("verrou actif (refus de mot de passe precedent) : lancer 'opti087 deverrouiller' apres correction")
    if not cfg["mdp"]:
        raise RefusMdp("mot_de_passe vide dans [onduleurs]")
    cache = os.path.join(cfg["dossier"], "ip_onduleurs.json")
    try:
        carte = {} if forcer_recherche else json.load(open(cache))
    except (OSError, ValueError):
        carte = {}
    lus = {}

    def passe(ips):
        for ip in ips:
            if any(o["ip"] == ip for o in lus.values()):
                continue
            try:
                o = lire_onduleur_sw(cfg, ip, evt_depuis)
            except RefusMdp:
                open(verrou(cfg), "w").write(dt.datetime.now().isoformat(timespec="seconds") + " refus " + ip + "\n")
                raise
            except Exception:
                continue
            if o.get("numero_serie"):
                lus[o["numero_serie"]] = o

    passe(sorted(set(carte.values())))
    manquants = [s for s in cfg["series"] if s not in lus]
    if manquants or not lus:
        passe(chercher_onduleurs(cfg))
    os.makedirs(cfg["dossier"], exist_ok=True)
    json.dump({s: o["ip"] for s, o in lus.items()}, open(cache, "w"))
    return lus


def _etat_evt(cfg):
    try:
        return json.load(open(os.path.join(cfg["dossier"], "evenements_etat.json")))
    except (OSError, ValueError):
        return {}


def traiter_evenements(cfg, lus, etat):
    """v1.8 : garde les nouveaux evenements (evenements.jsonl), met a jour l'etat, resume des 60 dernieres minutes."""
    maintenant = int(dt.datetime.now().timestamp())
    chemin = os.path.join(cfg["dossier"], "evenements.jsonl")
    nouveaux = 0
    with open(chemin, "a", encoding="utf-8") as f:
        for sn, o in lus.items():
            e = etat.setdefault(sn, {"dernier": 0, "recents": []})
            for t, code, entree in o.get("evenements", []):
                if t <= e["dernier"] and [t, code] in e["recents"]:
                    continue
                f.write(json.dumps({"serie": sn, "t": dt.datetime.fromtimestamp(t).isoformat(timespec="seconds"),
                                    "code": code, "libelle": EVENEMENTS.get(code, "?")}, ensure_ascii=False) + "\n")
                e["recents"].append([t, code])
                e["dernier"] = max(e["dernier"], t)
                nouveaux += 1
            e["recents"] = [r for r in e["recents"] if r[0] >= maintenant - 86400]
            heure = [r for r in e["recents"] if r[0] >= maintenant - 3600]
            o["evt_nb"] = len(heure)
            if heure:
                o["evt"] = sorted(heure)[-1][1]
            o["evt24_nb"] = len(e["recents"])                # v1.9 : 24 dernieres heures
            if e["recents"]:
                t, code = sorted(e["recents"])[-1]
                d = dt.datetime.fromtimestamp(t)
                o["evt24"], o["evt24_hhmm"] = code, d.hour * 100 + d.minute
    json.dump(etat, open(os.path.join(cfg["dossier"], "evenements_etat.json"), "w"))
    try:   # 60 jours gardes
        lignes = open(chemin, encoding="utf-8").read().splitlines()
        lim = (dt.datetime.now() - dt.timedelta(days=60)).isoformat()
        garde = [l for l in lignes if l[l.find('"t": "') + 6:l.find('"t": "') + 25] >= lim[:19]]
        if len(garde) < len(lignes):
            open(chemin, "w", encoding="utf-8").write("\n".join(garde) + ("\n" if garde else ""))
    except (OSError, ValueError):
        pass
    return nouveaux


def est_nuit(cfg, maintenant=None):
    """v1.9 : heure du site entre nuit_debut et nuit_fin (les onduleurs SMA s'endorment sans soleil)."""
    h = (maintenant or dt.datetime.now()).hour
    return h >= cfg["nuit_debut"] or h < cfg["nuit_fin"]


def releve_onduleurs(cfg, rec):
    os.makedirs(cfg["dossier"], exist_ok=True)
    etat = _etat_evt(cfg)
    defaut = int(dt.datetime.now().timestamp()) - 86400          # premier passage : 24 h
    depuis = {sn: max(e.get("dernier", 0) - 60, int(dt.datetime.now().timestamp()) - 7 * 86400) for sn, e in etat.items()}
    depuis["*"] = defaut
    try:
        lus = lire_onduleurs(cfg, evt_depuis=depuis)
    except RefusMdp as e:
        rec["statut"] = "MOT_DE_PASSE_REFUSE"
        rec["erreur"] = str(e)
        return
    try:
        rec["evenements_nouveaux"] = traiter_evenements(cfg, lus, etat)
    except Exception as e:
        rec["evenements_erreur"] = type(e).__name__
    for o in lus.values():
        o.pop("evenements", None)
    ordre = cfg["series"] or sorted(lus)
    rec["onduleurs"] = {}
    absents = []
    for n, sn in enumerate(ordre, 1):
        if sn in lus:
            rec["onduleurs"]["OND%d" % n] = lus[sn]
        else:
            absents.append(sn)
            rec["onduleurs"]["OND%d" % n] = {"numero_serie": sn, "etat_texte": "NON_LU"}
    def somme(cle):
        v = [o.get(cle) for o in lus.values() if o.get(cle) is not None]
        return sum(v) if v else None
    rec["centrale"] = {"puissance_ac_w": somme("puissance_ac_w"), "energie_jour_wh": somme("energie_jour_wh"),
                       "energie_totale_wh": somme("energie_totale_wh"), "onduleurs_lus": len(lus),
                       "onduleurs_attendus": len(ordre)}
    rec["statut"] = "OK" if lus else ("NUIT" if est_nuit(cfg) else "ONDULEURS_INJOIGNABLES")   # v1.9
    if rec["statut"] == "NUIT":
        rec["alertes"] = "NUIT : onduleurs en veille, boitier en ligne"
        return
    if absents:
        rec["alertes"] = "non lus : " + ", ".join(absents)
    defauts = [o["numero_serie"] for o in lus.values() if o.get("etat") not in (None, 307)]
    if defauts:
        rec["alertes"] = (rec.get("alertes", "") + " ; " if rec.get("alertes") else "") + "etat anormal : " + ", ".join(defauts)


def mode_sonde(cfg):
    print("Recherche des onduleurs SMA sur %s.x (sans connexion, Data Manager exclu)..." % cfg["reseau"])
    ips = chercher_onduleurs(cfg)
    print("Appareils SMA trouves : %s" % (", ".join(ips) or "aucun"))
    if not ips:
        print("-> Aucun appareil SMA : verifier le reseau du boitier (ip a).")
        return
    try:
        lus = lire_onduleurs(cfg, forcer_recherche=True)
    except RefusMdp as e:
        sys.exit("ARRET : %s. Aucun autre essai ne sera fait. Ecrire a Claude." % e)
    print("%-11s %-15s %8s %10s %13s %-14s %10s %8s %6s %6s" % ("Serie", "IP", "P (W)", "Jour (kWh)", "Total (kWh)", "Etat", "DC (W)", "Vmax", "Hz", "Relais"))
    for sn in (cfg["series"] or sorted(lus)):
        o = lus.get(sn)
        if not o:
            print("%-11s %-15s NON TROUVE" % (sn, "-"))
            continue
        f = lambda v, d=1: "-" if v is None else ("%.1f" % (v / d))
        print("%-11s %-15s %8s %10s %13s %-14s %10s" % (sn, o["ip"], f(o.get("puissance_ac_w")), f(o.get("energie_jour_wh"), 1000),
              f(o.get("energie_totale_wh"), 1000), o.get("etat_texte", "-"), f(o.get("dc_puissance_w")),
              f(max([o[k] for k in ("tension_l1_v", "tension_l2_v", "tension_l3_v") if o.get(k) is not None] or [None]) if any(o.get(k) is not None for k in ("tension_l1_v", "tension_l2_v", "tension_l3_v")) else None),
              f(o.get("frequence_hz")), {51: "ferme", 311: "OUVERT"}.get(o.get("relais"), "-" if o.get("relais") is None else str(o.get("relais")))))
    print("Onduleurs lus : %d / %d" % (len(lus), len(cfg["series"]) or len(lus)))


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
def mode_scan(cfg):
    print("Scan du Data Manager %s:%d (Unit ID 1 a 30, environ 1 min)" % (cfg["host"], cfg["port"]))
    try:
        socket.create_connection((cfg["host"], cfg["port"]), 3).close()
    except OSError as e:
        sys.exit("ECHEC connexion : %s\n-> Verifier IP, cable, et que le serveur Modbus "
                 "est active dans le Data Manager." % e)
    trouves = []
    for unit in range(1, 31):
        try:
            with ModbusTCP(cfg["host"], cfg["port"], 1.5) as cli:
                p = cli.read_value(unit, 30775, "S32")
                vals = {}
                for nom, addr in (("e", 30529), ("et", 30201)):
                    try:
                        vals[nom] = cli.read_value(unit, addr, "U32")
                    except Exception:
                        vals[nom] = None
        except (OSError, ConnectionError):
            continue
        trouves.append(unit)
        print("  Unit ID %3d : puissance=%s W  energie_totale=%s Wh  etat=%s"
              % (unit, p, vals["e"], ETATS.get(vals["et"], vals["et"])))
    print("Unit ID qui repondent : %s" % (", ".join(map(str, trouves)) or "aucun"))
    print("-> Reporter le Unit ID centrale (normalement 2) et ceux des 9 onduleurs "
          "dans /etc/opti087/opti087.conf, dans l'ordre terrain 1 a 9.")


def mode_once(cfg):
    rec = {"site": cfg["code"],
           "horodatage": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "version": VERSION}
    if cfg["source"] == "onduleurs":       # v1.4
        releve_onduleurs(cfg, rec)
        try:                               # v1.8 : compteur SMA, ecoute passive
            c = ecouter_compteur(3.0)
            if c:
                rec["compteur"] = c
        except Exception:
            pass
    else:
        try:
            with ModbusTCP(cfg["host"], cfg["port"]) as cli:
                rec["centrale"] = lire_bloc(cli, cfg["unit_plant"], REG_PLANT)
                rec["onduleurs"] = {}
                for n, unit in enumerate(cfg["unit_ond"], 1):
                    rec["onduleurs"]["OND%d" % n] = lire_bloc(cli, unit, REG_ONDULEUR)
            rec["statut"] = "OK"
        except OSError as e:
            rec["statut"] = "DATA_MANAGER_INJOIGNABLE"
            rec["erreur"] = str(e)
    sauver(cfg, rec)
    purger(cfg)
    c = rec.get("centrale", {})
    print("%s %s puissance=%s W jour=%s Wh%s%s"
          % (rec["horodatage"], rec["statut"], c.get("puissance_ac_w"), c.get("energie_jour_wh"),
             (" onduleurs=%s/%s" % (c.get("onduleurs_lus"), c.get("onduleurs_attendus"))) if "onduleurs_lus" in c else "",
             (" | " + rec["alertes"]) if rec.get("alertes") else ""))
    print(envoyer_direct(cfg, rec))   # v1.3
    envoyer(cfg)


def mode_evenements(cfg, jours):
    """v1.8 : journal d'evenements de chaque onduleur sur N jours + nombre par code (validation terrain)."""
    depuis = int(dt.datetime.now().timestamp()) - int(jours * 86400)
    try:
        lus = lire_onduleurs(cfg, evt_depuis=depuis)
    except RefusMdp as e:
        sys.exit("ARRET : %s. Aucun autre essai ne sera fait." % e)
    total = {}
    for n, sn in enumerate(cfg["series"] or sorted(lus), 1):
        o = lus.get(sn)
        if not o:
            print("N%d %s : NON LU" % (n, sn))
            continue
        ev = o.get("evenements", [])
        print("N%d %s : %d evenement(s)%s" % (n, sn, len(ev), (" - erreur " + o["evenements_erreur"]) if o.get("evenements_erreur") else ""))
        for t, code, _ in ev[-15:]:
            print("   %s  %5d  %s" % (dt.datetime.fromtimestamp(t).strftime("%d/%m %H:%M"), code, EVENEMENTS.get(code, "?")))
            total.setdefault(code, {}).setdefault("N%d" % n, 0)
        for t, code, _ in ev:
            total.setdefault(code, {}).setdefault("N%d" % n, 0)
            total[code]["N%d" % n] += 1
    print("\nNombre par code sur %s jour(s) :" % jours)
    for code in sorted(total):
        print("  %5d %-55s %s" % (code, EVENEMENTS.get(code, "?"), ", ".join("%s:%d" % kv for kv in sorted(total[code].items()))))


def mode_compteur():
    print("Ecoute du compteur SMA (10 s, sans connexion)...")
    c = ecouter_compteur(10.0)
    print(json.dumps(c, ensure_ascii=False) if c else "Aucun compteur SMA entendu sur le reseau (normal s'il n'y en a pas).")


def mode_show(cfg):
    p = os.path.join(cfg["dossier"], "dernier.json")
    if not os.path.exists(p):
        sys.exit("Aucun releve pour l'instant.")
    print(open(p, encoding="utf-8").read())


def main():
    ap = argparse.ArgumentParser(description="Collecte OPTI-087 " + VERSION)
    ap.add_argument("--conf", default=CONF_PATH)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan", action="store_true")
    g.add_argument("--once", action="store_true")
    g.add_argument("--show", action="store_true")
    g.add_argument("--sonde", action="store_true")      # v1.4
    g.add_argument("--evenements", nargs="?", type=float, const=2.0)   # v1.8 (jours, 2 par defaut)
    g.add_argument("--compteur", action="store_true")                 # v1.8
    a = ap.parse_args()
    if a.compteur:
        mode_compteur()
        return
    cfg = charger_conf(a.conf)
    if a.evenements is not None:
        mode_evenements(cfg, a.evenements)
    elif a.scan:
        mode_scan(cfg)
    elif a.sonde:
        mode_sonde(cfg)
    elif a.once:
        mode_once(cfg)
    else:
        mode_show(cfg)


if __name__ == "__main__":
    main()
