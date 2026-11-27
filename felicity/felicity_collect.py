#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTI-MIST SOLUTIONS - Pilote Felicity IVEM (RS232/RS485, Modbus RTU 9600 8N1) - v1.8b du 27/11/2026
v1.8b (27/11 01h, relecture contradictoire) : recalage des lignes minute (champs up / t) et renommage seulement si quelque
  chose a ete recale ; lecture tolerante aux lignes coupees au milieu d'un caractere (errors=replace), ecriture en ASCII ;
  envoi horaire au plus 2 lots par passage et 40 s au plus (le reste aux passages suivants).
v1.8 (27/11, GO S.S. 26/11 22h50, boitiers poses le 28/11 sans retour au banc ; audit du 26/11) : FONDATIONS.
  - ECRITURES PROTEGEES : dernier.json, envoi_etat.json et tous les fichiers d'etat sont ecrits dans un fichier
    temporaire, forces sur le disque (fsync), puis mis en place d'un coup (os.replace) : une coupure de courant
    pendant l'ecriture laisse l'ancien fichier entier, jamais un fichier a moitie ecrit (constat de l'audit A).
    Les lignes du stock (.jsonl) sont ajoutees avec fsync ; une ligne coupee par une coupure est isolee par un
    saut de ligne avant la suivante (elle seule est perdue, la suivante est lue).
  - HORLOGE SANS PILE (pas d'horloge sauvegardee sur la carte, S) : un releve fait avant la synchronisation de
    l'heure par internet est marque heure_verifiee = 0 et range dans nv-<demarrage>.jsonl, avec le temps ecoule
    depuis le demarrage (uptime_s). Des que l'heure est synchronisee, ces releves sont RECALES (heure reelle =
    heure de synchronisation - temps ecoule entre le releve et la synchronisation, C) et copies dans le fichier
    du bon jour, marques heure_verifiee = 2 (recalee) ; ils partent alors au rattrapage normal.
  - PURGE SUR L'AGE REEL : rien n'est efface tant que l'heure n'est pas verifiee (une horloge fausse ne peut plus
    effacer le stock).
v1.7 (19/11, standard « zone isolee » GO S.S. 17/11, pour les NOUVEAUX boitiers) : dans envoi.conf, facultatif :
  jours_conserves = 730    (stock local en jours ; defaut 60, 7 a 1000)
  rattrapage_jours = 90    (profondeur du rattrapage apres coupure ; defaut 7, 1 a 90)
Au plus 20 lots de 48 lignes par passage (le reste part aux passages suivants). Absents = comportement v1.6 inchange (OPTI-061).
v1.6 (GO S.S. 19/11 09h57) : PLUSIEURS CONVERTISSEURS EN PARALLELE et CODE DE SITE PARAMETRABLE (sites clients en essai).
Dans envoi.conf (facultatif ; absent = comportement v1.5 d'OPTI-061, inchange) :
  code = OPTI-0xx          (code du site ; defaut OPTI-061)
  port = /dev/ttyUSB0      (port serie ; defaut /dev/ttyUSB0)
  esclaves = 1,2,3         (adresses Modbus des convertisseurs en parallele sur le meme cable ; defaut 1)
Les convertisseurs en parallele se lisent sur un seul cable (D, S.S. 19/11). Chaque convertisseur est lu a son adresse ;
le releve additionne production (pv_w), charge (charge_puissance_w, charge_apparente_va) et prend la batterie, le reseau et
la sortie au premier convertisseur qui repond (parc batterie commun). convertisseurs_lus / convertisseurs_attendus disent
combien ont repondu ; le detail par convertisseur est garde dans le releve local. Toujours LECTURE SEULE (fonction 03).
v1.5 (GO S.S. 18/11 19h02) : INTERNET DE SECOURS. Le direct porte aussi secours (1 = boitier sur le Wi-Fi de secours 4G,
0 = principal ; lu dans /var/lib/opti-mist/netplan_mode ecrit par bascule_netplan.sh) et secours_mo_jour / secours_mo_mois
(donnees consommees sur le secours, compteurs de bascule_netplan v1.1). Rien n'est envoye si la bascule n'est pas installee.
v1.4 (GO S.S. 13/11 14h45) : DIRECT. A chaque releve (5 min), le dernier releve part aussi vers le tableau de bord
(carte "Boitiers en direct") si direct_url et direct_jeton sont renseignes dans envoi.conf. Un seul releve est garde
la-bas (rien dans l'historique). Un echec du direct ne bloque ni le stockage ni l'envoi horaire.
v1.4 (13/11 15h15) : PRODUCTION SOLAIRE. Registres PV identifies le 13/11 (releves 14:43, 14:48, 15:11 + photos ecran) :
PV1 0x1126 V/10, 0x1129 A/10, 0x112A W ; PV2 0x1159 V/10, 0x115A A/10, 0x115B W. Dans chaque entree, V x A = W (C).
PV1 verifie sur l'ecran (226 W lu / 221 W affiche, M). PV2 coherent V x A mais pas encore compare a l'ecran
a la meme minute (S, batterie passee a 100 % entre la photo et la lecture). pv_w = PV1 + PV2 (C).
v1.3 (GO S.S. 13/11 03h13) : RATTRAPAGE apres coupure internet. Le boitier lit et stocke toutes les 5 min meme
sans internet ; a chaque passage, il envoie UNE ligne par heure non encore transmise (le dernier releve de
chaque heure, tire du stock local), jusqu'a 7 jours en arriere. Une coupure d'internet ne laisse plus de trou dans
l'historique ; seule une heure sans aucun releve (boitier eteint) reste vide. Etat : DATA/envoi_etat.json.
LECTURE SEULE : fonction 03 uniquement, aucune fonction d'ecriture dans ce fichier.

Registres identifies le 12/11/2026 sur OPTI-061 (IVEM8048) par comparaison avec l'ecran :
  M = verifie sur l'ecran ; S = suppose, a confirmer (PV en journee, compteurs d'energie)
Les blocs bruts 0x1100-0x115F sont aussi enregistres, pour corriger la table sans perdre l'historique.

Usage : felicity_collect.py --once | --show     (port /dev/ttyUSB0, esclave 1)
"""
import json, os, sys, termios, time, tty, select, subprocess, urllib.request, datetime as dt

PORT, SLAVE, CODE = "/dev/ttyUSB0", 1, "OPTI-061"
ESCLAVES = [1]
SOMMES = ("pv_w", "pv1_puissance_w", "pv2_puissance_w", "charge_puissance_w", "charge_apparente_va")   # v1.6 : additionnes


def regler():
    """v1.6 : code, port et esclaves lus dans envoi.conf (absents = valeurs v1.5)."""
    global PORT, CODE, ESCLAVES
    cfg = lire_envoi_brut()
    CODE = cfg.get("code") or CODE
    PORT = cfg.get("port") or PORT
    try:
        e = [int(x) for x in str(cfg.get("esclaves") or "").replace(" ", "").split(",") if x]
        if e and all(1 <= x <= 247 for x in e):
            ESCLAVES = e
    except ValueError:
        pass
    global JOURS, RATTRAPAGE_H                      # v1.7 : standard « zone isolee »
    try:
        j = int(cfg.get("jours_conserves") or 0)
        if 7 <= j <= 1000:
            JOURS = j
    except ValueError:
        pass
    try:
        r = int(cfg.get("rattrapage_jours") or 0)
        if 1 <= r <= 90:
            RATTRAPAGE_H = r * 24
    except ValueError:
        pass
DATA = os.environ.get("OPTI_DATA", "/var/lib/opti061")
JOURS = 60

# (nom, adresse, signe, diviseur, statut)
CARTE = [
    ("mode_brut",              0x1101, False, 1,   "S"),
    ("batterie_tension_v",     0x1108, False, 100, "M"),   # 5326 -> 53,26 V (ecran 53,3)
    ("batterie_courant_a",     0x1109, True,  1,   "M"),   # -24 -> decharge 24 A (ecran 24 A)
    ("batterie_puissance_w",   0x110A, True,  1,   "C"),   # -1304 W ~ 53,3 x 24
    ("batterie_soc_pct",       0x110B, False, 1,   "M"),   # 71 (ecran 71 %)
    ("sortie_tension_v",       0x110C, False, 10,  "M"),   # 230,1 V (ecran 230)
    ("sortie_frequence_hz",    0x110E, False, 100, "S"),   # 50,12
    ("charge_puissance_w",     0x1115, False, 1,   "M"),   # 1189 W (ecran 1,18 kW)
    ("charge_apparente_va",    0x1116, False, 1,   "M"),   # 1242 VA (ecran 1,21 kVA)
    ("reseau_tension_v",       0x1117, False, 10,  "M"),   # 232,8 V (ecran 233)
    ("reseau_frequence_hz",    0x1119, False, 100, "M"),   # 50,06 (ecran 50,1)
    ("charge_pct",             0x1120, False, 1,   "M"),   # 15 (ecran 15 %)
    ("temperature_1_c",        0x1121, False, 1,   "S"),
    ("temperature_2_c",        0x1122, False, 1,   "S"),
    ("temperature_3_c",        0x1123, False, 1,   "S"),
    ("pv1_tension_v",          0x1126, False, 10,  "M"),   # 963 -> 96,3 V (ecran ~100 V)
    ("pv1_courant_a",          0x1129, False, 10,  "C"),   # 209 -> 20,9 A ; 96,3 x 20,9 = 2013 W ~ 1969
    ("pv1_puissance_w",        0x112A, False, 1,   "M"),   # 226 W (ecran PV1 221 W, 13/11 15h10)
    ("pv2_tension_v",          0x1159, False, 10,  "S"),   # 966 -> 96,6 V
    ("pv2_courant_a",          0x115A, False, 10,  "C"),   # 38 -> 3,8 A ; 96,6 x 3,8 = 367 W ~ 366
    ("pv2_puissance_w",        0x115B, False, 1,   "S"),   # 366 W ; a comparer a l'ecran PV2 a la meme minute
]
BLOCS = [0x1100, 0x1110, 0x1120, 0x1130, 0x1140, 0x1150]


def crc16(d):
    c = 0xFFFF
    for b in d:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return bytes([c & 0xFF, c >> 8])


def ouvrir():
    fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    tty.setraw(fd)
    a = termios.tcgetattr(fd)
    a[4] = a[5] = termios.B9600
    a[2] = (a[2] & ~(termios.PARENB | termios.CSTOPB | termios.CSIZE)) | termios.CS8 | termios.CLOCAL | termios.CREAD
    termios.tcsetattr(fd, termios.TCSANOW, a)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def lire(fd, addr, n=16, essais=4, esclave=None):
    sl = SLAVE if esclave is None else esclave
    req = bytes([sl, 3, addr >> 8, addr & 0xFF, 0, n])
    req += crc16(req)
    entete = bytes([sl, 3, 2 * n])
    for _ in range(essais):
        termios.tcflush(fd, termios.TCIOFLUSH)
        os.write(fd, req)
        buf, fin = b"", time.time() + 1.2
        while time.time() < fin:
            if select.select([fd], [], [], 0.05)[0]:
                try:
                    buf += os.read(fd, 256)
                except BlockingIOError:
                    pass
                i = buf.find(entete)          # tolere des octets parasites avant la trame
                if i >= 0 and len(buf) >= i + 5 + 2 * n:
                    trame = buf[i:i + 3 + 2 * n]
                    if crc16(trame) == buf[i + 3 + 2 * n:i + 5 + 2 * n]:
                        return [int.from_bytes(trame[3 + 2 * k:5 + 2 * k], "big") for k in range(n)]
        time.sleep(0.3)
    return None


def decoder(brut):
    val = {}
    for nom, a, signe, div, _ in CARTE:
        bloc = "%04X" % (a & 0xFFF0)
        if bloc in brut:
            x = brut[bloc][a - (a & 0xFFF0)]
            if signe and x >= 0x8000:
                x -= 0x10000
            val[nom] = x / div if div != 1 else x
    if "pv1_puissance_w" in val or "pv2_puissance_w" in val:   # v1.4 : production solaire totale (C)
        val["pv_w"] = (val.get("pv1_puissance_w") or 0) + (val.get("pv2_puissance_w") or 0)
    return val


def releve():
    rec = {"site": CODE, "horodatage": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "version": "felicity 1.6"}
    bruts = {}
    try:
        fd = ouvrir()
        time.sleep(0.5)                       # laisser la liaison se stabiliser
        for sl in ESCLAVES:
            lire(fd, 0x1100, 1, 1, sl)        # premier echange de reveil, ignore
            brut = {}
            for b in BLOCS:
                v = lire(fd, b, esclave=sl)
                if v is not None:
                    brut["%04X" % b] = v
                time.sleep(0.05)
            if brut:
                bruts[sl] = brut
        os.close(fd)
    except OSError as e:
        rec["statut"] = "PORT_INDISPONIBLE"
        rec["erreur"] = str(e)
        return rec
    if not bruts:
        rec["statut"] = "CONVERTISSEUR_MUET"
        return rec
    par = {sl: decoder(b) for sl, b in bruts.items()}
    premier = par[sorted(par)[0]]
    val = dict(premier)                       # batterie, reseau, sortie : premier convertisseur qui repond
    if len(ESCLAVES) > 1:
        for k in SOMMES:                      # v1.6 : production et charge additionnees
            xs = [p[k] for p in par.values() if p.get(k) is not None]
            if xs:
                val[k] = sum(xs)
        val["convertisseurs_lus"] = len(par)
        val["convertisseurs_attendus"] = len(ESCLAVES)
        rec["par_convertisseur"] = {str(sl): par[sl] for sl in sorted(par)}
        rec["brut"] = {str(sl): bruts[sl] for sl in sorted(bruts)}
    else:
        rec["brut"] = bruts[sorted(bruts)[0]]   # v1.5 : meme forme qu'avant pour un seul convertisseur
    rec["statut"] = "OK"
    rec["valeurs"] = val
    return rec


def ecrire_json(p, obj, indent=1):
    """v1.8 : ecriture protegee (temporaire + fsync + remplacement d'un coup)."""
    d = os.path.dirname(p) or "."
    os.makedirs(d, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)
    try:
        fd = os.open(d, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except OSError:
        pass


def lire_json(p, defaut=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def ajouter_lignes(p, lignes):
    """v1.8 : ajout au stock avec fsync ; une ligne coupee par une coupure est isolee par un saut de ligne."""
    if not lignes:
        return
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "a+b") as f:
        if f.tell() > 0:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                f.write(b"\n")
        f.write("".join(l.rstrip("\n") + "\n" for l in lignes).encode("utf-8"))
        f.flush()
        os.fsync(f.fileno())


def boot_id():
    try:
        return open("/proc/sys/kernel/random/boot_id").read().strip()
    except OSError:
        return "inconnu"


def uptime_s():
    try:
        return round(float(open("/proc/uptime").read().split()[0]), 1)
    except (OSError, ValueError):
        return None


RUN = os.environ.get("OPTI_RUN", "/run/opti061")


def horloge_ok():
    """v1.8 : heure synchronisee par internet dans ce demarrage ? (marque en memoire vive une fois vue)."""
    m = os.path.join(RUN, "horloge_ok")
    if os.path.exists(m):
        return True
    ok = os.path.exists("/run/systemd/timesync/synchronized")
    if not ok:
        try:
            r = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], capture_output=True,
                               text=True, timeout=5)
            ok = r.stdout.strip() == "yes"
        except (OSError, subprocess.SubprocessError):
            ok = False
    ok = ok and dt.date.today().year >= 2026
    if ok:
        try:
            os.makedirs(RUN, exist_ok=True)
            open(m, "w").write(dt.datetime.now().astimezone().isoformat(timespec="seconds") + " %s\n" % uptime_s())
        except OSError:
            pass
    return ok


def fichier_stock(rec, prefixe=""):
    """v1.8 : fichier du jour si l'heure est verifiee, sinon nv-<demarrage>.jsonl (a recaler)."""
    if rec.get("heure_verifiee") == 0:
        return os.path.join(DATA, "%snv-%s.jsonl" % (prefixe, (rec.get("boot") or "inconnu")[:8]))
    return os.path.join(DATA, prefixe + rec["horodatage"][:10] + ".jsonl")


def recaler():
    """v1.8 : heure synchronisee -> les releves de CE demarrage faits avant la synchronisation sont recales."""
    if not horloge_ok():
        return 0
    b = boot_id()[:8]
    maint, up = dt.datetime.now().astimezone(), uptime_s()
    if up is None:
        return 0
    n = 0
    for prefixe in ("", "min-"):
        p = os.path.join(DATA, "%snv-%s.jsonl" % (prefixe, b))
        if not os.path.exists(p):
            continue
        par_jour, k = {}, 0
        for l in open(p, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(l)
                u = float(r["uptime_s"] if "uptime_s" in r else r["up"])     # v1.8b : releves complets ET lignes minute
            except Exception:
                continue
            reel = (maint - dt.timedelta(seconds=max(0.0, up - u))).isoformat(timespec="seconds")
            if "t" in r and "horodatage" not in r:
                r["t_brut"], r["t"], r["hv"] = r["t"], reel, 2
            else:
                r["horodatage_brut"], r["horodatage"], r["heure_verifiee"] = r.get("horodatage"), reel, 2   # recalee (C)
            par_jour.setdefault(os.path.join(DATA, prefixe + reel[:10] + ".jsonl"), []).append(
                json.dumps(r, ensure_ascii=True))
            k += 1
        for f, lignes in par_jour.items():
            ajouter_lignes(f, lignes)
        if k:
            os.replace(p, p + ".recale")                # v1.8b : renomme seulement si quelque chose est recale
        n += k
    return n


def purger():
    """v1.8 : purge sur l'age reel, seulement quand l'heure est verifiee."""
    if not horloge_ok():
        return
    limite = (dt.date.today() - dt.timedelta(days=JOURS)).isoformat()
    for n in os.listdir(DATA):
        p = os.path.join(DATA, n)
        if n.endswith(".jsonl") and n[-16:-6] < limite and n[-16:-6][:2] == "20":
            os.remove(p)
        elif (".jsonl" in n and "nv-" in n) and time.time() - os.path.getmtime(p) > JOURS * 86400:
            os.remove(p)


def sauver(rec):
    os.makedirs(DATA, exist_ok=True)
    ajouter_lignes(fichier_stock(rec), [json.dumps(rec, ensure_ascii=True)])       # v1.8 ; v1.8b : ASCII
    ecrire_json(os.path.join(DATA, "dernier.json"), rec)                            # v1.8 : protege
    purger()


# ---------------------------------------------------------------------------
# v1.2 : envoi vers l'historique fusionne (meme format que la supervision GitHub)
# Fichier /etc/opti061/envoi.conf (droits 600) :
#   url = <adresse du webhook de l'historique>     (vide = pas d'envoi)
#   site = OPTI-061                                (nom affiche dans l'historique)
#   periode_min = 60                               (un envoi par heure)
#   alertes = non                                  (site de test : aucune alerte)
#   direct_url = <adresse publique du tableau de bord>   (v1.4 ; vide = pas de direct)
#   direct_jeton = <jeton BOITIERS_DIRECT_JETON>          (v1.4 ; coffre uniquement)
# ---------------------------------------------------------------------------
ENVOI_CONF = "/etc/opti061/envoi.conf"


def lire_envoi_brut():
    cfg = {}
    try:
        for ligne in open(ENVOI_CONF, encoding="utf-8"):
            if "=" in ligne and not ligne.strip().startswith("#"):
                k, v = ligne.split("=", 1)
                cfg[k.strip()] = v.strip()
    except OSError:
        pass
    return cfg


def lire_envoi():
    cfg = {"url": "", "site": CODE, "periode_min": "60", "alertes": "non", "direct_url": "", "direct_jeton": ""}
    try:
        for ligne in open(ENVOI_CONF, encoding="utf-8"):
            if "=" in ligne and not ligne.strip().startswith("#"):
                k, v = ligne.split("=", 1)
                cfg[k.strip()] = v.strip()
    except OSError:
        pass
    return cfg


def categorie(v, ok):
    if not ok:
        return "OFFLINE"
    b = v.get("batterie_soc_pct") or 0
    if 0 < b < 15:
        return "BATTERY_CRITICAL"
    if 0 < b < 30:
        return "BATTERY_WARNING"
    return ""


RATTRAPAGE_H = 168      # 7 jours au plus
LOT = 48                # lignes par envoi
MAX_LOTS = 20           # v1.7 : au plus 20 lots par passage (le reste au passage suivant)


def ligne_historique(rec, cfg):
    """Un releve local -> une ligne de l'historique fusionne (date = heure du releve, jamais l'heure d'envoi)."""
    v = rec.get("valeurs") or {}
    ok = rec.get("statut") == "OK"
    reseau = (v.get("reseau_tension_v") or 0) > 150
    bat = v.get("batterie_courant_a") or 0
    mode = "Battery" if bat < 0 else ("Grid" if reseau else "-")
    quand = dt.datetime.fromisoformat(rec["horodatage"])
    return {
        "date": quand.strftime("%d/%m/%Y %H:%M"), "date_only": quand.strftime("%d/%m/%Y"),
        "site": cfg["site"],
        "pv_w": round(v["pv_w"]) if ok and v.get("pv_w") is not None else "",   # v1.4 : PV1 + PV2
        "load_w": round(v.get("charge_puissance_w") or 0) if ok else "",
        "batt_pct": round(v.get("batterie_soc_pct") or 0) if ok else "",
        "grid_w": "",                                 # puissance reseau non identifiee : jamais inventee
        "mode": mode if ok else "-", "eco_fcfa": 0,
        "statut": "OK" if ok else "HORS LIGNE",
        "alertes": categorie(v, ok) if cfg["alertes"] == "oui" else "",
    }


def heure(d):
    return d.strftime("%Y-%m-%dT%H")


def releves_par_heure(depuis):
    """{AAAA-MM-JJTHH: dernier releve de l'heure} lu dans le stock local, a partir de l'heure 'depuis' (exclue)."""
    out = {}
    for n in sorted(os.listdir(DATA)):
        if not n.endswith(".jsonl") or len(n) != 16 or n[:2] != "20" or n[:10] < depuis[:10]:
            continue                # v1.8 : fichiers du jour seulement (ni minutes, ni releves a recaler)
        for l in open(os.path.join(DATA, n), encoding="utf-8", errors="replace"):
            try:
                r = json.loads(l)
                h = heure(dt.datetime.fromisoformat(r["horodatage"]))
            except Exception:
                continue
            if h > depuis and (h not in out or r["horodatage"] > out[h]["horodatage"]):
                out[h] = r          # le dernier releve de l'heure l'emporte
    return out


def lire_etat_envoi():
    p = os.path.join(DATA, "envoi_etat.json")
    try:
        return json.load(open(p))["derniere_heure"]
    except (OSError, ValueError, KeyError):
        pass
    try:   # passage v1.2 -> v1.3 : repartir de l'heure du dernier envoi reussi
        return heure(dt.datetime.fromtimestamp(float(open(os.path.join(DATA, "dernier_envoi.txt")).read().strip())))
    except (OSError, ValueError):
        return None


def envoyer(rec):
    cfg = lire_envoi()
    if not cfg["url"]:
        return "envoi=non_configure"
    if not horloge_ok():
        return "envoi=attente_heure"      # v1.8 : pas d'historique horaire sur une horloge non verifiee
    maint = dt.datetime.now()
    derniere = lire_etat_envoi()
    plancher = heure(maint - dt.timedelta(hours=RATTRAPAGE_H))
    if derniere is None or derniere < plancher:
        derniere = heure(maint - dt.timedelta(hours=1)) if derniere is None else plancher
    if derniere >= heure(maint):
        return "envoi=attente"            # heure en cours deja transmise
    a_envoyer = sorted(releves_par_heure(derniere).items())
    if not a_envoyer:
        return "envoi=rien"
    envoyees, debut = 0, time.time()
    a_envoyer = a_envoyer[:LOT * MAX_LOTS]        # v1.7
    if len(a_envoyer) > LOT and os.environ.get("OPTI_BUDGET_ENVOI") != "0":
        a_envoyer = a_envoyer[:LOT * 2]           # v1.8b : au plus 2 lots par passage (budget de temps du cycle)
    for i in range(0, len(a_envoyer), LOT):
        lot = a_envoyer[i:i + LOT]
        try:
            if time.time() - debut > 40:
                break                             # v1.8b : le reste au passage suivant
            req = urllib.request.Request(cfg["url"], data=json.dumps({"rows": [ligne_historique(r, cfg) for _, r in lot],
                                         "deduplicate": True}).encode(), headers={"Content-Type": "application/json"})
            res = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
        except Exception as e:
            return "envoi=echec(%s) %d/%d" % (type(e).__name__, envoyees, len(a_envoyer))
        if res.get("status") != "ok":
            return "envoi=refuse %d/%d" % (envoyees, len(a_envoyer))
        envoyees += len(lot)
        ecrire_json(os.path.join(DATA, "envoi_etat.json"), {"derniere_heure": lot[-1][0],
                    "maj": maint.isoformat(timespec="seconds")}, None)            # v1.8 : protege
    return "envoi=ok %d ligne(s)%s" % (envoyees, " dont %d de rattrapage" % (envoyees - 1) if envoyees > 1 else "")


def etat_secours():
    """v1.5 : mode de la bascule netplan et donnees consommees sur le secours (Mo). {} si la bascule n'est pas installee."""
    d = "/var/lib/opti-mist"
    try:
        with open(os.path.join(d, "netplan_mode")) as f:
            mode = f.read().strip()
    except OSError:
        return {}

    def mo(suffixe):
        try:
            with open(os.path.join(d, "secours_octets_" + suffixe)) as f:
                return round(int(f.read().strip() or 0) / 1048576, 1)
        except (OSError, ValueError):
            return 0
    maint = dt.datetime.now()
    return {"secours": 1 if mode == "secours" else 0,
            "secours_mo_jour": mo(maint.strftime("%Y-%m-%d")), "secours_mo_mois": mo(maint.strftime("%Y-%m"))}


REPONSE_DIRECT = {}      # v1.8 : derniere reponse du tableau de bord (accuse de reception des evenements)


def envoyer_direct(rec):
    """v1.4 : dernier releve -> carte "Boitiers en direct" du tableau de bord (valeurs lues telles quelles)."""
    cfg = lire_envoi()
    if not cfg["direct_url"] or not cfg["direct_jeton"]:
        return "direct=non_configure"
    v = rec.get("valeurs") or {}
    bat = v.get("batterie_courant_a") or 0
    reseau = (v.get("reseau_tension_v") or 0) > 150
    corps = {"jeton": cfg["direct_jeton"], "direct": {
        "code": CODE, "horodatage": rec["horodatage"], "statut": rec.get("statut", ""),
        "mode": "batterie" if bat < 0 else ("reseau" if reseau else "-"),
        "valeurs": dict({k: v[k] for k in ("batterie_tension_v", "batterie_soc_pct", "batterie_courant_a", "batterie_puissance_w",
                                           "charge_puissance_w", "charge_apparente_va", "charge_pct", "reseau_tension_v",
                                           "reseau_frequence_hz", "sortie_tension_v", "pv_w",
                                           "convertisseurs_lus", "convertisseurs_attendus") if k in v}, **etat_secours())}}
    for k in ("sante", "evenements", "energie_jour", "heure_verifiee", "absents", "alerte"):   # v1.8 : donnees brutes
        x = rec.get(k, v.get(k))
        if x not in (None, "", []):
            corps["direct"][k] = x
    global REPONSE_DIRECT
    REPONSE_DIRECT = {}
    try:
        req = urllib.request.Request(cfg["direct_url"], data=json.dumps(corps).encode(),
                                     headers={"Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
    except Exception as e:
        return "direct=echec(%s)" % type(e).__name__
    REPONSE_DIRECT = res if isinstance(res, dict) else {}
    return "direct=ok" if res.get("status") == "ok" else "direct=refuse"


def main():
    regler()
    if "--show" in sys.argv:
        p = os.path.join(DATA, "dernier.json")
        if not os.path.exists(p):
            sys.exit("Aucun releve pour l'instant.")
        d = json.load(open(p))
        print(d["horodatage"], d["statut"])
        for k, v in (d.get("valeurs") or {}).items():
            print("  %-22s %s" % (k, v))
        for sl, p in (d.get("par_convertisseur") or {}).items():   # v1.6
            print("  convertisseur %s : pv=%s W charge=%s W batterie=%s %%" % (sl, p.get("pv_w"), p.get("charge_puissance_w"), p.get("batterie_soc_pct")))
        return
    rec = releve()
    sauver(rec)
    if "--sans-envoi" not in sys.argv:
        rec["direct"] = envoyer_direct(rec)
        rec["envoi"] = envoyer(rec)
    v = rec.get("valeurs", {})
    if v.get("convertisseurs_attendus"):   # v1.6
        print("site=%s convertisseurs lus %s/%s" % (CODE, v.get("convertisseurs_lus"), v.get("convertisseurs_attendus")))
    print("%s %s batterie=%s V %s %% charge=%s W pv=%s W (%s + %s) reseau=%s V" % (
        rec["horodatage"], rec["statut"], v.get("batterie_tension_v"), v.get("batterie_soc_pct"),
        v.get("charge_puissance_w"), v.get("pv_w"), v.get("pv1_puissance_w"), v.get("pv2_puissance_w"), v.get("reseau_tension_v")), rec.get("direct", ""), rec.get("envoi", ""))


if __name__ == "__main__":
    main()
