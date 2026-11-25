#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTI-MIST SOLUTIONS - Lecteur universel : MPP / Voltronic (PI30), SRNE et Felicity (Modbus) - v1.6a du 25/11/2026
v1.6a (25/11, GO S.S. boitier universel) : commentaires seulement (aucun nom de client, pour le depot public) ; code identique a v1.6.
v1.6 (24/11 13h30, GO S.S. apres la sonde OPTI-063 du 24/11, carte boitiers/sonde/CARTE_SRNE_OPTI-063_2026-11-24.md) :
  SRNE TRIPHASE A 2 ENTREES PV (OPTI-063, 48 V / 20 kW). En v1.5d : solaire = PV1 seul (moitie du reel) et
  consommation = L1 seule. Desormais, toujours en lecture seule (fonction 03) :
  - pv_w = PV total 0x010A (C : 6951 = PV1 3533 + PV2 ~3418) si present et >= PV1, sinon PV1 ; pv2_tension_v 0x010F (M).
  - phases L2 / L3 lues si le bloc 0x0230 repond et si la sortie L2 (0x022C) depasse 100 V : charge_l1_w / l2 / l3
    (0x021B, 0x0232, 0x0233, S), apparentes (0x021C M, 0x0234, 0x0235 S), sorties L2/L3 (0x022C/0x022D, M),
    reseau L2/L3 (0x022A/0x022B, S). charge_puissance_w = somme des 3 phases (C) ; triphase = 1.
  - puissance max par phase 0x020C (6667 W = 20 kW / 3, S) -> phase_max_w, pour l'analyse d'equilibre des phases.
  - compteurs : pv_jour_kwh 0xF02F /10 (S, coherent C avec l'ecran), pv_total_kwh 0xF038-39 et
    conso_total_kwh 0xF03A-3B (mot bas d'abord, /10, M = ecran 12 619,6 et 13 069,4 kWh).
  - etat 0x0210 = 3 a l'ecran « NORMAL » sur batterie et solaire, reseau 0 A (M) -> mode B (S).
  Un SRNE monophase (banc) ne change pas : blocs absents ou L2 < 100 V -> valeurs v1.5d.
v1.5 (20/11 22h, essai banc S.S. : « les techniciens debranchent et rebranchent les onduleurs ») : IDENTITE PAR NUMERO
  DE SERIE. En v1.4 les noms suivaient l'ordre des prises : un echange de cables changeait l'appareil derriere MPP1
  (M, banc 21h48 : VM III sur l'ancienne prise du MK). Desormais chaque convertisseur est reconnu par son numero de serie
  lu en lecture seule (MPP : QID, M banc VM III = 96342211105916 ; SRNE : registres 0x0035-0x0048 en ASCII, S ;
  Felicity : pas de numero connu -> identite par prise, marquee « incertaine »). Le nom (MPP1, SRNE1...) est attache au
  numero dans DATA/identites.json et ne change plus, quel que soit le port. A chaque releve, le numero des MPP est
  reverifie : s'il ne correspond plus a la prise (cables echanges), detection refaite aussitot. Un convertisseur muet sur
  une prise presente declenche aussi une nouvelle detection. « --detecter » affiche nom, marque, identite et prise.
v1.5a (20/11 22h20, banc) : SRNE - sens du courant batterie : l'ecran affiche 1,1 A EN CHARGE, le registre 0x0102 donne
  -1,2 (M) -> signe inverse pour respecter la convention commune (+ = charge). Etat de marche lu en 0x0210 (S, carte
  publique SRNE : 4 = sur reseau -> mode L, 5 = sur onduleur/batterie -> mode B, autres valeurs gardees telles quelles).
v1.5b (20/11 22h25, banc) : SOLAIRE FANTOME du VM III : la nuit il annonce 19-26 W de PV avec 0 V aux panneaux
  (ecran et QPIGS, M). Ce faux solaire etait additionne et faisait choisir le VM III comme chargeur deduit (M 22h19).
  Regle : puissance PV comptee 0 si la tension PV de la meme entree est sous 30 V (C) ; valeur brute gardee (pv1_brut_w).
v1.5c (20/11 22h40, banc) : CONVERTISSEUR ABSENT. Cable du MK debranche -> le releve affichait 2/2 sans rien signaler (M
  22h36) : un cable arrache chez un client passait inapercu. Desormais le boitier garde la date de derniere lecture de
  chaque convertisseur (DATA/vus.json, par nom) ; « attendus » = ceux lus dans les 7 derniers jours (ou la cle
  convertisseurs_attendus = N de envoi.conf si elle est renseignee). Il manque quelqu'un -> lus/attendus (ex. 2/3),
  champ « absents » et alerte « convertisseur absent : MPP1 ». Au-dela de 7 jours d'absence (appareil retire ou
  remplace), il n'est plus attendu.
v1.5d (21/11 00h20, GO S.S. production des 4 boitiers) : FELICITY EN PARALLELE SUR UN SEUL CABLE (sites clients a
  3 x 8 kVA). En v1.4-1.5c le Felicity detecte n'etait lu qu'a l'adresse 1 (2/3 de la production
  manquants). A la detection, adresses Modbus 1 a 9 essayees sur la prise Felicity (lecture 0x1100, fonction 03) ;
  toutes celles qui repondent sont lues et additionnees par le collecteur Felicity v1.7 (ESCLAVES). Les unites comptent
  dans lus / attendus (ex. 3 Felicity : 3/3 ; une unite muette : 2/3). Cle esclaves = 1,2,3 de envoi.conf prioritaire.
  A valider sur le premier site a 3 Felicity (S).
v1.4 (20/11 19h30, GO S.S.) : DETECTION AUTOMATIQUE et ROLE CHARGEUR.
  envoi.conf : convertisseurs = auto  -> le boitier essaie chaque prise serie (/dev/serial/by-path, ttyUSB et ttyACM) :
  PI30 (QPI, 2400 bauds) -> MPP ; sinon Modbus esclave 1 a 9600 : 0x1100 -> FELICITY, 0x0100 -> SRNE. Resultat garde dans
  DATA/detection.json ; nouvelle detection seulement si les prises branchees changent. Noms : MPP1, MPP2, SRNE1... (ordre
  des prises). Le technicien ne recopie plus aucun nom de prise. « python3 mpp_collect.py --detecter » affiche le resultat.
  chargeur = NOM (facultatif) : batterie (V, %) et reseau pris sur ce convertisseur. Sans la cle : chargeur DEDUIT = celui
  qui a le plus de solaire ou de courant de charge a ce releve. Alerte si un convertisseur declare non chargeur charge
  (> 1 A avec du solaire). Lecture seule partout (QPI/QPIGS..., fonctions Modbus 03).
  Limite connue (M, banc 20/11) : Growatt SPF 6000 ES Plus par USB (ttyACM) ne repond ni en PI30 ni en Modbus : non reconnu.
v1.3 (20/11 16h15, GO S.S.) : SRNE sur le meme boitier. Un convertisseur dont le NOM commence par « SRNE » est lu en
  Modbus RTU (9600 bauds, esclave 1, fonction 03 = lecture seule, fonctions de stockage/liaison de felicity_collect).
  Carte verifiee banc 20/11 16h08 (HESP4860S100-H, sonde) contre l'ecran 16h09-16h11 (M) :
  0x0100 SOC % · 0x0101 batterie /10 V · 0x0102 courant batterie /10 A signe (sens a confirmer, S) · 0x0107-0x0109 PV1
  V/10, A/10, W · 0x0212 bus /10 V · 0x0213 reseau /10 V · 0x0215 reseau /100 Hz · 0x0216 sortie /10 V ·
  0x0218 sortie /100 Hz · 0x021B sortie W · 0x021C sortie VA · 0x021F taux de charge %. Temperatures 0x0220-0x0223 /10 C (S).
v1.2 (20/11 16h, GO S.S. « on commence par les 2 MPP ») : PLUSIEURS CONVERTISSEURS SUR UN BOITIER, un cable chacun.
  envoi.conf : convertisseurs = VM3@platform-5101400.usb-usb-0:1:1.0-port0, MK@platform-5311400.usb-usb-0:1:1.0-port0
  (nom fixe de la prise USB, /dev/serial/by-path : ne s'inverse pas au redemarrage). Chaque convertisseur est lu seul ;
  le releve garde le detail par convertisseur (par_convertisseur) et additionne production et consommation (C).
  Batterie et reseau : ceux du PREMIER convertisseur de la liste (meme batterie pour tous, M banc : 53,0 / 53,1 V).
  Sans la cle « convertisseurs » : comportement v1.1 inchange (un seul port).
  Banc 20/11 15h46-15h47 (M) : ttyUSB0 = VM III (57 C, PV 0,3 A / 30 W affiches aussi a l'ecran), ttyUSB1 = MK
  (5000 VA, 47 C, sortie 3 W / 23 VA = ecran), QPGS0-2 sans reponse valide (pas de parallele), QPIGS2 NAK sur le MK.
v1.1 (19/11 23h45, essai banc) : VERROU - un seul releve a la fois sur le cable (le releve automatique et un releve
manuel lances ensemble melangeaient les reponses : CONVERTISSEUR_MUET a 23h40, OK a 23h42 une fois seul, M).
Banc du bureau (opti-098, 19/11 23h24-23h28, M) : VM III-6000 (VERFW 00060.03) et PIP 5048MK (VERFW 00071.80)
repondent tous deux en PI30, 2400 bauds, cable USB-serie (/dev/ttyUSB0). Systemes vises : sites clients MPP (3 x PIP 5048MK)
et OPTI-046 (3 x PIP 8048MAX).

LECTURE SEULE : uniquement les questions QPIGS, QPIGS2, QMOD, QPIWS, QPGSn (interrogation). Aucune commande de reglage
n'existe dans ce fichier (garde-fou assert ci-dessous).

Stockage local, rattrapage apres coupure, envoi horaire et direct : REPRIS TELS QUELS du collecteur Felicity
(felicity_collect.py v1.7, meme dossier /opt/opti061) - meme format de releve, memes cles de valeurs, meme envoi.conf.

envoi.conf (/etc/opti061/envoi.conf) :
  code = OPTI-045          port = /dev/ttyUSB0 (defaut : essai hidraw0, ttyUSB0, ttyUSB1)
  unites = 3               (convertisseurs en parallele ; defaut 1)
  jours_conserves = 730    rattrapage_jours = 90      url / direct_url / direct_jeton : depuis le coffre

Valeurs (M = verifie sur le banc ; S = a confirmer a l'ecran a la premiere pose) :
  reseau, sortie, batterie (tension, %, courants), charge (W, VA, %) : QPIGS, M (banc, sans charge ni PV)
  pv1_puissance_w : 20e champ QPIGS, S (15 W lu sur le VM III sans panneau : a comparer a l'ecran en journee)
  pv2_puissance_w : QPIGS2 (modeles a 2 entrees panneaux, ex. 8048MAX), S - NAK sur le banc (1 entree)
  unites > 1 : QPGS0..n-1 par convertisseur (production = tension x courant PV, charge = puissance de sortie), S :
  le banc n'a pas de parallele ; a valider a la premiere pose sur site (comparaison a l'ecran a la meme minute).
"""
import datetime as dt, fcntl, glob, json, os, sys, time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import felicity_collect as fc      # stockage, rattrapage, envoi (v1.7)
import mpp_probe as mp             # trame, CRC, liaison serie / USB (v1.1)

VERSION = "mpp 1.6a"
SRNE = [("batterie_soc_pct", 0x0100, False, 1), ("batterie_tension_v", 0x0101, False, 10),
        ("batterie_courant_a", 0x0102, True, 10), ("pv1_tension_v", 0x0107, False, 10),
        ("pv1_courant_a", 0x0108, False, 10), ("pv1_puissance_w", 0x0109, False, 1),
        ("bus_tension_v", 0x0212, False, 10), ("reseau_tension_v", 0x0213, False, 10),
        ("reseau_frequence_hz", 0x0215, False, 100), ("sortie_tension_v", 0x0216, False, 10),
        ("sortie_frequence_hz", 0x0218, False, 100), ("charge_puissance_w", 0x021B, False, 1),
        ("charge_apparente_va", 0x021C, False, 1), ("charge_pct", 0x021F, False, 1),
        ("temperature_c", 0x0220, False, 10)]      # lecture seule : blocs 0x0100 et 0x0210-0x0220
QUESTIONS = ("QMOD", "QPIGS", "QPIGS2", "QPIWS")
Q_SERIE = "QID"                    # v1.5 : numero de serie (interrogation)
for _q in QUESTIONS + ("QPGS0", Q_SERIE):
    assert _q.startswith("Q"), _q          # interrogation seulement
UNITES = 1
PORT = None
CONVERTISSEURS = []                # v1.2 : [(nom, port)] ; v1.4 : [(nom, port, marque)]
CHARGEUR = None                    # v1.4
AUTO = False                       # v1.5 : convertisseurs = auto
ATTENDUS = 0                       # v1.5c : cle convertisseurs_attendus (0 = automatique, 7 jours)
CLES = {}                          # v1.5 : {prise: identite} de la derniere detection
UNITES_PRISE = {}                  # v1.5d : {prise Felicity: [adresses Modbus qui repondent]}
ESCLAVES_CONF = []                 # v1.5d : cle esclaves de envoi.conf (prioritaire)
FC_RELEVE = fc.releve              # v1.4 : releve Felicity d'origine (avant remplacement dans main)
QPGS = ["parallele", "serie", "mode", "defaut", "reseau_tension_v", "reseau_frequence_hz", "sortie_tension_v",
        "sortie_frequence_hz", "charge_apparente_va", "charge_puissance_w", "charge_pct", "batterie_tension_v",
        "batterie_courant_charge_a", "batterie_soc_pct", "pv_tension_v", "charge_totale_a", "total_va", "total_w",
        "total_pct", "etat", "mode_sortie", "priorite_charge", "courant_max", "plage", "courant_max_reseau",
        "pv_courant_a", "batterie_courant_decharge_a"]


def regler():
    global UNITES, PORT, CONVERTISSEURS, CHARGEUR, AUTO, ATTENDUS, ESCLAVES_CONF
    fc.regler()                                   # code, jours_conserves, rattrapage (v1.7)
    cfg = fc.lire_envoi_brut()
    PORT = cfg.get("port") or None
    CHARGEUR = (cfg.get("chargeur") or "").strip() or None
    CONVERTISSEURS = []
    conv = (cfg.get("convertisseurs") or "").strip()
    AUTO = conv.lower() == "auto"
    try:
        ESCLAVES_CONF = [int(x) for x in str(cfg.get("esclaves") or "").replace(" ", "").split(",") if x]
    except ValueError:
        ESCLAVES_CONF = []
    try:
        ATTENDUS = int(cfg.get("convertisseurs_attendus") or 0)
    except ValueError:
        ATTENDUS = 0
    if AUTO:
        CONVERTISSEURS = detecter()               # v1.4
    for x in conv.split(","):
        if "@" in x:
            nom, prise = [y.strip() for y in x.split("@", 1)]
            if nom and prise:
                CONVERTISSEURS.append((nom, prise if prise.startswith("/") else "/dev/serial/by-path/" + prise,
                                       "SRNE" if nom.upper().startswith("SRNE") else
                                       "FELICITY" if nom.upper().startswith("FELICITY") else "MPP"))
    try:
        u = int(cfg.get("unites") or 1)
        UNITES = u if 1 <= u <= 9 else 1
    except ValueError:
        UNITES = 1


def prises():
    """v1.4 : une entree par prise serie branchee (nom fixe by-path si possible), ttyUSB et ttyACM."""
    vues, out = set(), []
    d = "/dev/serial/by-path"
    noms = sorted(os.listdir(d)) if os.path.isdir(d) else []
    noms = [n for n in noms if "usbv" not in n] + [n for n in noms if "usbv" in n]
    for n in noms:
        reel = os.path.realpath(os.path.join(d, n))
        if reel not in vues:
            vues.add(reel)
            out.append(os.path.join(d, n))
    for reel in sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")):
        if reel not in vues:
            vues.add(reel)
            out.append(reel)
    return out


def identifier(port):
    """v1.4 : MPP (PI30), FELICITY ou SRNE (Modbus), sinon None. Lecture seule."""
    try:
        fd = mp.ouvrir(port)
        time.sleep(0.3)
        r, ok = mp.demander(fd, port, "QPI")
        os.close(fd)
        if ok and r and r.startswith("(PI"):
            return "MPP"
    except OSError:
        pass
    fc.PORT = port
    try:
        fd = fc.ouvrir()
        time.sleep(0.3)
        felicity = fc.lire(fd, 0x1100, 1, 2, 1)
        srne = None if felicity is not None else fc.lire(fd, 0x0100, 2, 2, 1)
        os.close(fd)
    except OSError:
        return None
    if felicity is not None:
        return "FELICITY"
    if srne is not None and 200 <= srne[1] <= 700:           # tension batterie 20-70 V (/10) : garde-fou
        return "SRNE"
    return None


def serie(port, marque):
    """v1.5 : numero de serie, lecture seule. None si l'appareil n'en donne pas."""
    try:
        if marque == "MPP":
            fd = mp.ouvrir(port)
            time.sleep(0.3)
            r, ok = mp.demander(fd, port, Q_SERIE)
            os.close(fd)
            x = (r or "").strip().lstrip("(").strip()
            return x if ok and len(x) >= 6 and x.isalnum() else None
        if marque == "SRNE":                       # S : registres du numero de serie, a confirmer sur le banc
            fc.PORT = port
            fd = fc.ouvrir()
            time.sleep(0.3)
            r = fc.lire(fd, 0x0035, 20, 2, 1)
            os.close(fd)
            if r:
                b = b"".join(v.to_bytes(2, "big") for v in r).replace(b"\x00", b"").strip()
                x = b.decode("ascii", "ignore")
                if len(x) >= 6 and all(c.isalnum() or c in "-_/." for c in x):
                    return x
    except OSError:
        pass
    return None


def absents_7j(lus):
    """v1.5c : met a jour DATA/vus.json (nom -> derniere lecture) ; renvoie les noms lus < 7 j et absents maintenant."""
    p = os.path.join(fc.DATA, "vus.json")
    try:
        vus = json.load(open(p))
    except (OSError, ValueError):
        vus = {}
    maintenant = time.time()
    for n in lus:
        vus[n] = maintenant
    vus = {n: t for n, t in vus.items() if maintenant - t < 7 * 86400}
    try:
        json.dump(vus, open(p, "w"), indent=1)
    except OSError:
        pass
    return sorted(n for n in vus if n not in lus)


def adresses_felicity(port):
    """v1.5d : adresses Modbus 1 a 9 qui repondent sur la prise (lecture seule 0x1100)."""
    if ESCLAVES_CONF:
        return ESCLAVES_CONF
    fc.PORT = port
    vues = []
    try:
        fd = fc.ouvrir()
        time.sleep(0.3)
        for a in range(1, 10):
            if fc.lire(fd, 0x1100, 1, 2, a) is not None:
                vues.append(a)
            time.sleep(0.05)
        os.close(fd)
    except OSError:
        pass
    return vues or [1]


def identites():
    try:
        return json.load(open(os.path.join(fc.DATA, "identites.json")))
    except (OSError, ValueError):
        return {}


def detecter(forcer=False):
    """v1.4 : detection gardee dans DATA/detection.json ; refaite si les prises changent.
    v1.5 : noms attaches au numero de serie (DATA/identites.json), stables quel que soit le port."""
    global CLES, UNITES_PRISE
    p = os.path.join(fc.DATA, "detection.json")
    liste = prises()
    if not forcer and os.path.exists(p):
        try:
            d = json.load(open(p))
            if d.get("prises") == liste and "cles" in d and "unites" in d:
                CLES = d["cles"]
                UNITES_PRISE = d["unites"]
                return [tuple(c) for c in d["convertisseurs"]]
        except (OSError, ValueError, KeyError):
            pass
    ids = identites()
    conv, cles, unites = [], {}, {}
    for port in liste:
        m = identifier(port)
        if not m:
            continue
        sn = serie(port, m)
        cle = "%s:%s" % (m, sn) if sn else "%s:prise:%s" % (m, port)
        if cle not in ids and not sn:            # sans numero : reprendre le nom d'une prise du meme type debranchee
            libres = [c for c in ids if c.startswith(m + ":prise:") and c.split(":prise:", 1)[1] not in liste
                      and ids[c] not in [x[0] for x in conv]]
            if libres:
                ids[cle] = ids.pop(sorted(libres)[0])
        if cle not in ids:
            pris = set(ids.values())
            k = 1
            while "%s%d" % (m, k) in pris:
                k += 1
            ids[cle] = "%s%d" % (m, k)
        conv.append((ids[cle], port, m))
        cles[port] = cle
        if m == "FELICITY":
            unites[port] = adresses_felicity(port)
    conv.sort(key=lambda c: c[0])
    os.makedirs(fc.DATA, exist_ok=True)
    json.dump(ids, open(os.path.join(fc.DATA, "identites.json"), "w"), indent=1)
    json.dump({"horodatage": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "prises": liste,
               "convertisseurs": conv, "cles": cles, "unites": unites}, open(p, "w"), indent=1)
    CLES, UNITES_PRISE = cles, unites
    return conv


def nombre(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def depuis_qpigs(t):
    q = mp.decoder_qpigs(t)
    if not q:
        return {}
    v = {k: q.get(k) for k in ("reseau_tension_v", "reseau_frequence_hz", "sortie_tension_v", "sortie_frequence_hz",
                                "charge_pct", "batterie_tension_v", "batterie_soc_pct", "temperature_c", "bus_tension_v")}
    v["charge_apparente_va"] = q.get("sortie_apparente_va")
    v["charge_puissance_w"] = q.get("sortie_puissance_w")
    ch, de = q.get("batterie_courant_charge_a") or 0, q.get("batterie_courant_decharge_a") or 0
    v["batterie_courant_a"] = ch - de                                     # + charge, - decharge (C)
    if q.get("batterie_tension_v") is not None:
        v["batterie_puissance_w"] = round(q["batterie_tension_v"] * v["batterie_courant_a"])   # C
    v["pv1_puissance_w"] = q.get("pv_puissance_w")                       # S
    v["pv1_tension_v"] = q.get("pv_tension_v")
    v["etat_bits"] = q.get("etat_bits")
    return {k: x for k, x in v.items() if x is not None}


def depuis_qpgs(t):
    if not t or not t.startswith("(") or t.startswith("(NAK"):
        return None
    xs = t[1:].split()
    if len(xs) < 26:
        return None
    d = dict(zip(QPGS, xs))
    if d.get("parallele") != "1":
        return None                               # unite absente du parallele
    v = {k: nombre(d[k]) for k in ("reseau_tension_v", "sortie_tension_v", "charge_apparente_va", "charge_puissance_w",
                                    "charge_pct", "batterie_tension_v", "batterie_soc_pct", "pv_tension_v", "pv_courant_a")}
    if v["pv_tension_v"] is not None and v["pv_courant_a"] is not None:
        v["pv_w"] = round(v["pv_tension_v"] * v["pv_courant_a"])         # C, S
    v["mode"] = d.get("mode")
    v["defaut"] = d.get("defaut")
    return {k: x for k, x in v.items() if x is not None}


def releve():
    rec = {"site": fc.CODE, "horodatage": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "version": VERSION}
    if CONVERTISSEURS:
        return releve_plusieurs(rec)
    ports = [PORT] if PORT else ["/dev/hidraw0", "/dev/ttyUSB0", "/dev/ttyUSB1"]
    port = next((p for p in ports if os.path.exists(p)), None)
    if not port:
        rec["statut"] = "PORT_INDISPONIBLE"
        return rec
    return lire_port(port, rec, UNITES)


SRNE_TRI = [("pv_total_w", 0x010A, False, 1), ("pv2_tension_v", 0x010F, False, 10),
            ("reseau_l2_tension_v", 0x022A, False, 10), ("reseau_l3_tension_v", 0x022B, False, 10),
            ("sortie_l2_tension_v", 0x022C, False, 10), ("sortie_l3_tension_v", 0x022D, False, 10),
            ("charge_l2_w", 0x0232, False, 1), ("charge_l3_w", 0x0233, False, 1),
            ("charge_l2_va", 0x0234, False, 1), ("charge_l3_va", 0x0235, False, 1),
            ("phase_max_w", 0x020C, False, 1), ("pv_jour_kwh", 0xF02F, False, 10)]     # v1.6, lecture seule
SRNE_BLOCS = ((0x0100, 16), (0x0200, 16), (0x0210, 16), (0x0220, 16), (0x0230, 8), (0xF020, 16), (0xF030, 12))


def srne_valeurs(blocs):
    """v1.6 : decode les blocs SRNE lus (dict adresse -> liste). Separe de la lecture pour le rejeu."""
    def reg(a, signe=False):
        for base, liste in blocs.items():
            if base <= a < base + len(liste):
                x = liste[a - base]
                return x - 0x10000 if signe and x >= 0x8000 else x
        return None
    if reg(0x0100) is None:
        return None
    val = {}
    for nom, a, signe, div in SRNE:
        x = reg(a, signe)
        if x is not None:
            val[nom] = round(x / div, 2) if div != 1 else x
    if val.get("batterie_courant_a") is not None:
        val["batterie_courant_a"] = -val["batterie_courant_a"]    # v1.5a : SRNE negatif en charge (M) -> + = charge
    etat = reg(0x0210)
    if etat is not None:                                          # v1.5a / v1.6 : etat de marche (S)
        val["etat_srne"] = etat
        val["mode_brut"] = {3: "B", 4: "L", 5: "B"}.get(etat, "E%d" % etat)
    if val.get("batterie_tension_v") is not None and val.get("batterie_courant_a") is not None:
        val["batterie_puissance_w"] = round(val["batterie_tension_v"] * val["batterie_courant_a"])   # C
    pv1 = val.get("pv1_puissance_w") or 0
    tri = {}
    for nom, a, signe, div in SRNE_TRI:
        x = reg(a, signe)
        if x is not None:
            tri[nom] = round(x / div, 2) if div != 1 else x
    pvt = tri.pop("pv_total_w", None)
    val["pv_w"] = pvt if pvt is not None and pvt >= pv1 else pv1
    for k in ("pv2_tension_v", "pv_jour_kwh", "phase_max_w"):
        if k in tri:
            val[k] = tri.pop(k)
    for nom, a in (("pv_total_kwh", 0xF038), ("conso_total_kwh", 0xF03A)):
        bas, haut = reg(a), reg(a + 1)
        if bas is not None and haut is not None:
            val[nom] = round((haut * 65536 + bas) / 10, 1)          # mot bas d'abord (M, 24/11)
    if (tri.get("sortie_l2_tension_v") or 0) > 100:                 # triphase reel (garde-fou)
        val.update(tri)
        val["triphase"] = 1
        val["charge_l1_w"] = val.get("charge_puissance_w")
        if val["charge_l1_w"] is not None:
            val["charge_puissance_w"] = val["charge_l1_w"] + (tri.get("charge_l2_w") or 0) + (tri.get("charge_l3_w") or 0)   # C
        if val.get("charge_apparente_va") is not None:
            val["charge_l1_va"] = val["charge_apparente_va"]
            val["charge_apparente_va"] = val["charge_l1_va"] + (tri.get("charge_l2_va") or 0) + (tri.get("charge_l3_va") or 0)
    return val


def lire_srne(port):
    """v1.3 : SRNE en Modbus RTU, fonction 03 uniquement (fc.lire). v1.6 : blocs triphase et compteurs."""
    fc.PORT = port
    try:
        fd = fc.ouvrir()
        blocs = {}
        for a, n in SRNE_BLOCS:
            r = fc.lire(fd, a, n, essais=4 if a in (0x0100, 0x0210) else 1, esclave=1)   # v1.6 : blocs facultatifs, 1 essai
            if r is not None:
                blocs[a] = r
            time.sleep(0.1)
        os.close(fd)
    except OSError as e:
        return {"statut": "PORT_INDISPONIBLE", "erreur": str(e)}
    val = srne_valeurs(blocs)
    if val is None:
        return {"statut": "CONVERTISSEUR_MUET"}
    return {"statut": "OK", "valeurs": val}


def releve_plusieurs(rec, deja=False):
    """v1.2 : un cable par convertisseur ; chacun lu seul, puis additionne."""
    global CONVERTISSEURS
    if AUTO and not deja:                         # v1.5 : les MPP sont-ils toujours sur la meme prise ?
        for nom, port, marque in CONVERTISSEURS:
            if marque == "MPP" and os.path.exists(port) and not CLES.get(port, "").startswith("MPP:prise:"):
                sn = serie(port, "MPP")
                if sn and CLES.get(port) != "MPP:" + sn:
                    CONVERTISSEURS = detecter(forcer=True)
                    rec["detection"] = "refaite (cables echanges)"
                    break
    par, statuts = {}, {}
    for nom, port, marque in CONVERTISSEURS:
        if not os.path.exists(port):
            r = {"statut": "PORT_INDISPONIBLE"}
        elif marque == "SRNE":
            r = lire_srne(port)                   # v1.3
        elif marque == "FELICITY":
            fc.PORT, fc.ESCLAVES = port, UNITES_PRISE.get(port) or ESCLAVES_CONF or [1]   # v1.4 ; v1.5d : toutes les unites
            r = FC_RELEVE()
        else:
            r = lire_port(port, {}, 1)
        statuts[nom] = r["statut"]
        if r["statut"] == "OK":
            par[nom] = r["valeurs"]
        else:
            par[nom] = {"statut": r["statut"]}
    ok = [c[0] for c in CONVERTISSEURS if statuts[c[0]] == "OK"]
    if AUTO and not deja and any(statuts[c[0]] != "OK" and os.path.exists(c[1]) for c in CONVERTISSEURS):
        avant = list(CONVERTISSEURS)              # v1.5 : un muet sur une prise presente -> nouvelle detection
        CONVERTISSEURS = detecter(forcer=True)
        if CONVERTISSEURS != avant:
            rec["detection"] = "refaite (convertisseur muet)"
            return releve_plusieurs(rec, deja=True)
    rec["par_convertisseur"] = par
    rec["statuts"] = statuts
    if not ok:
        rec["statut"] = "CONVERTISSEUR_MUET" if any(s == "CONVERTISSEUR_MUET" for s in statuts.values()) else "PORT_INDISPONIBLE"
        return rec
    # v1.4 : batterie et reseau pris sur le chargeur (declare, sinon deduit : plus de solaire / courant de charge)
    if CHARGEUR in ok:
        chg, source = CHARGEUR, "declare"
    else:
        chg = max(ok, key=lambda n: ((par[n].get("pv_w") or 0), (par[n].get("batterie_courant_a") or 0)))
        source = "deduit"
    ref = par[chg]
    val = {k: ref[k] for k in ("reseau_tension_v", "reseau_frequence_hz", "sortie_tension_v", "sortie_frequence_hz",
                               "batterie_tension_v", "batterie_soc_pct", "mode_brut") if k in ref}
    for k in ("pv_w", "charge_puissance_w", "charge_apparente_va", "batterie_courant_a", "batterie_puissance_w"):
        xs = [par[n][k] for n in ok if par[n].get(k) is not None]
        if xs:
            val[k] = round(sum(xs), 1)            # C
    val["avertissements"] = " ".join("%s:%s" % (n, par[n].get("avertissements", "")) for n in ok)
    val["temperature_c"] = max([par[n]["temperature_c"] for n in ok if par[n].get("temperature_c") is not None] or [0]) or None
    val["chargeur"], val["chargeur_source"] = chg, source
    if CHARGEUR:
        autres = [n for n in ok if n != CHARGEUR and (par[n].get("batterie_courant_a") or 0) > 1 and (par[n].get("pv_w") or 0) > 50]
        if autres:
            val["alerte"] = "charge par un convertisseur non chargeur : " + ", ".join(autres)
    unit = lambda c: len(UNITES_PRISE.get(c[1]) or [1]) if c[2] == "FELICITY" else 1          # v1.5d
    val["convertisseurs_lus"] = sum((par[c[0]].get("convertisseurs_lus") or unit(c)) if c[2] == "FELICITY" else 1
                                    for c in CONVERTISSEURS if c[0] in ok)
    val["convertisseurs_attendus"] = sum(unit(c) for c in CONVERTISSEURS)
    if AUTO:                                      # v1.5c : qui manque par rapport aux 7 derniers jours ?
        absents = absents_7j(ok)
        if absents:
            val["absents"] = ", ".join(absents)
            val["alerte"] = ((val.get("alerte") + " ; ") if val.get("alerte") else "") + \
                "convertisseur absent : " + ", ".join(absents)
        val["convertisseurs_attendus"] = ATTENDUS or (val["convertisseurs_attendus"] + len(absents))
    rec["statut"] = "OK"
    rec["valeurs"] = {k: x for k, x in val.items() if x is not None}
    return rec


def lire_port(port, rec, unites):
    brut, ctrl = {}, {}
    try:
        fd = mp.ouvrir(port)
        time.sleep(0.3)
        qs = list(QUESTIONS) + (["QPGS%d" % i for i in range(unites)] if unites > 1 else [])
        for q in qs:
            r, ok = mp.demander(fd, port, q)
            if r is not None:
                brut[q], ctrl[q] = r, bool(ok)
            time.sleep(0.15)
        os.close(fd)
    except OSError as e:
        rec["statut"] = "PORT_INDISPONIBLE"
        rec["erreur"] = str(e)
        return rec
    if not ctrl.get("QPIGS"):
        rec["statut"] = "CONVERTISSEUR_MUET"
        rec["brut"] = brut
        return rec
    val = depuis_qpigs(brut["QPIGS"])
    m = brut.get("QMOD", "")
    val["mode_brut"] = m[1:2] if m.startswith("(") else ""
    q2 = brut.get("QPIGS2", "")
    if q2.startswith("(") and not q2.startswith("(NAK"):
        xs = q2[1:].split()
        if len(xs) >= 3:
            val["pv2_tension_v"], val["pv2_puissance_w"] = nombre(xs[1]), nombre(xs[2])   # S
    for i in ("1", "2"):                          # v1.5b : pas de solaire sans tension aux panneaux
        if (val.get("pv%s_puissance_w" % i) or 0) > 0 and (val.get("pv%s_tension_v" % i) or 0) < 30:
            val["pv%s_brut_w" % i] = val["pv%s_puissance_w" % i]
            val["pv%s_puissance_w" % i] = 0
    val["pv_w"] = round((val.get("pv1_puissance_w") or 0) + (val.get("pv2_puissance_w") or 0))
    w = brut.get("QPIWS", "")
    val["avertissements"] = w[1:] if w.startswith("(") else ""
    if unites > 1:
        par = {}
        for i in range(unites):
            u = depuis_qpgs(brut.get("QPGS%d" % i))
            if u:
                par[str(i + 1)] = u
        val["convertisseurs_lus"] = len(par)
        val["convertisseurs_attendus"] = unites
        if par:
            for k in ("pv_w", "charge_puissance_w", "charge_apparente_va"):
                xs = [u[k] for u in par.values() if u.get(k) is not None]
                if xs:
                    val[k] = round(sum(xs))
            rec["par_convertisseur"] = par
    rec["brut"] = brut
    rec["controle"] = ctrl
    rec["statut"] = "OK"
    rec["valeurs"] = val
    return rec


def verrou():
    """v1.1 : attend au plus 60 s que le releve en cours se termine ; sinon abandonne (le suivant passera)."""
    f = open("/run/opti-mpp.lock", "w")
    fin = time.time() + 60
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            if time.time() > fin:
                sys.exit("releve deja en cours : abandon")
            time.sleep(1)


def main():
    fc.releve = releve                            # le reste du cycle (stockage, envoi, direct) est celui de v1.7
    regler()
    if "--detecter" in sys.argv:                 # v1.4 : pour le technicien / l'atelier
        for nom, port, marque in detecter(forcer=True):
            cle = CLES.get(port, "")
            u = UNITES_PRISE.get(port)
            print("%-8s %-9s %-28s %s%s" % (nom, marque, cle.split(":", 1)[1] if ":prise:" not in cle else
                                            "identite incertaine (par prise)", port,
                                            ("  [%d unites : adresses %s]" % (len(u), ",".join(map(str, u)))) if u else ""))
        print("prises vues :", len(prises()))
        return
    if "--show" in sys.argv:
        p = os.path.join(fc.DATA, "dernier.json")
        if not os.path.exists(p):
            sys.exit("Aucun releve pour l'instant.")
        d = json.load(open(p))
        print(d["horodatage"], d["statut"], d.get("version", ""))
        for k, v in (d.get("valeurs") or {}).items():
            print("  %-24s %s" % (k, v))
        for nom, v in (d.get("par_convertisseur") or {}).items():      # v1.2
            print("  [%s] batterie=%s V pv=%s W charge=%s W temp=%s C %s" % (nom, v.get("batterie_tension_v"),
                  v.get("pv_w"), v.get("charge_puissance_w"), v.get("temperature_c"), v.get("statut", "")))
        return
    garde = verrou()                              # v1.1
    rec = releve()
    fc.sauver(rec)
    if "--sans-envoi" not in sys.argv:
        rec["direct"] = fc.envoyer_direct(rec)
        rec["envoi"] = fc.envoyer(rec)
    v = rec.get("valeurs", {})
    print("%s %s mode=%s batterie=%s V %s %% charge=%s W pv=%s W reseau=%s V convertisseurs=%s/%s" % (
        rec["horodatage"], rec["statut"], v.get("mode_brut"), v.get("batterie_tension_v"), v.get("batterie_soc_pct"),
        v.get("charge_puissance_w"), v.get("pv_w"), v.get("reseau_tension_v"), v.get("convertisseurs_lus", 1),
        v.get("convertisseurs_attendus", 1)), rec.get("direct", ""), rec.get("envoi", ""))


if __name__ == "__main__":
    main()
