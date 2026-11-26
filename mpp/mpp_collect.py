#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTI-MIST SOLUTIONS - Lecteur universel : MPP / Voltronic (PI30), SRNE et Felicity (Modbus) - v1.7 du 27/11/2026
v1.7 (27/11, GO S.S. 26/11 22h50 ; boitiers poses le 28/11 et ne revenant plus au banc ; audit du 26/11) : le boitier
  capte et garde TOUT en brut ; l'interpretation (codes, alertes, rapports) se fait cote serveur et peut evoluer sans
  toucher aux boitiers poses. Toujours LECTURE SEULE (QPIGS..., QPIRI, QFLAG, QVFW, QBEQI ; Modbus fonction 03).
  - MESURE CHAQUE MINUTE (minuteur systemd), releve complet toutes les 5 min ; cadence reglable a distance dans
    envoi.conf (mesure_s, complet_min) ; lignes minute en memoire vive, ecrites sur le disque toutes les 5 min.
  - EVENEMENTS DATES (DATA/evenements.jsonl, numerotes) : demarrage du boitier, heure synchronisee, coupure et
    retour du reseau, changement de mode, avertissement (QPIWS brut), convertisseur absent / de retour, detection
    refaite, nouvelle fiche au journal des defauts, reglage modifie, temperature du boitier, disque presque plein.
    Un changement survenu boitier eteint est marque pendant_arret. Envoyes avec le direct, les plus anciens non
    accuses d'abord (20 au plus) : aucun ne se perd quand le tableau de bord accusera reception (evenements_recus).
  - ENERGIE CALCULEE minute par minute (C) : solaire, consommation, charge et decharge batterie, par jour
    (DATA/energie.json, 730 jours) ; le MPP n'a pas d'historique d'energie (QET/QEY/QEM/QED = NAK, M 26/11).
  - SANTE : temperature du processeur, disque et memoire libres, charge, temps depuis le demarrage, nombre de
    demarrages (DATA/demarrages.json), chien de garde, duree de la mesure.
  - MEMOIRE DES CONVERTISSEURS une fois par jour : journal des defauts SRNE 0xF800-0xF87F (8 fiches, M 26/11) et
    bloc 0xE000-0xE03F, reponses QPIRI / QFLAG / QVFW / QBEQI du MPP, gardes bruts dans DATA/memoire/.
  - SRNE : sens du courant deduit sur batterie sans reseau quand le solaire ne couvre pas la consommation
    (registre 0x0102 sans sens sur le HYP, M 26/11) ; registres bruts gardes dans le releve complet.
  - Ecritures protegees, heure non verifiee puis recalee, purge sur l'age reel : voir felicity_collect v1.8.
  Commandes : --test (sans cable), --complet, --evenements, --sante. Rejeu : rejeu/rejeu_cycle17.py.
v1.6b (26/11 21h, banc, SRNE HYP4860S100-H 6,2 kVA) : ADRESSE MODBUS DU SRNE. Ce SRNE etait regle sur l'adresse 2
  (ecran « Id: 2 », M) ; la detection ne l'essayait qu'a l'adresse 1 -> non reconnu (M 20h56). Desormais, a la
  detection, adresses 1 a 9 essayees une par une (Felicity 0x1100 puis SRNE 0x0100, lecture seule fonction 03) ;
  l'adresse trouvee est gardee dans detection.json (unites) et sert a la lecture et au numero de serie.
  Carte HESP verifiee sur le HYP par la sonde (M 21h02 = ecran) : 51,8 V, +1,2 A, reseau 233,5 V / 49,97 Hz, bus 399,6 V,
  49,0 C, etat 4 = reseau. phase_max_w (0x020C) n'est garde qu'en triphase : sur le HYP il vaut 9729 (autre sens, M).
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

VERSION = "mpp 1.7"
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
ADR_SRNE = {}                      # v1.6b : {prise SRNE: adresse Modbus trouvee a la detection}
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
        trouve = None
        for a in range(1, 10):                                # v1.6b : adresses 1 a 9 (SRNE HYP regle sur 2, M)
            if fc.lire(fd, 0x1100, 1, 2, a) is not None:
                trouve = "FELICITY"
                break
            srne = fc.lire(fd, 0x0100, 2, 2, a)
            if srne is not None and 200 <= srne[1] <= 700:   # tension batterie 20-70 V (/10) : garde-fou
                trouve = "SRNE"
                ADR_SRNE[port] = a
                break
            time.sleep(0.05)
        os.close(fd)
    except OSError:
        return None
    return trouve


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
            r = fc.lire(fd, 0x0035, 20, 2, adresse_srne(port))     # v1.6b
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
        fc.ecrire_json(p, vus)                    # v1.7 : ecriture protegee
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
        elif m == "SRNE":
            unites[port] = [ADR_SRNE.get(port, 1)]          # v1.6b : adresse gardee pour la lecture
    conv.sort(key=lambda c: c[0])
    os.makedirs(fc.DATA, exist_ok=True)
    fc.ecrire_json(os.path.join(fc.DATA, "identites.json"), ids)            # v1.7 : ecritures protegees
    fc.ecrire_json(p, {"horodatage": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "prises": liste,
                       "convertisseurs": conv, "cles": cles, "unites": unites})
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
    pv1 = val.get("pv1_puissance_w") or 0
    tri = {}
    for nom, a, signe, div in SRNE_TRI:
        x = reg(a, signe)
        if x is not None:
            tri[nom] = round(x / div, 2) if div != 1 else x
    pvt = tri.pop("pv_total_w", None)
    val["pv_w"] = pvt if pvt is not None and pvt >= pv1 else pv1
    # v1.7 : SENS DU COURANT. Sur le HYP le registre 0x0102 ne donne pas toujours le sens (M 26/11). Regle physique :
    # sur batterie (mode B), sans reseau, avec moins de solaire que de consommation, la batterie ne peut pas charger
    # -> courant compte en decharge (C). La valeur lue reste dans batterie_courant_lu_a.
    c = val.get("batterie_courant_a")
    if c is not None and c > 0 and val.get("mode_brut") == "B" and (val.get("reseau_tension_v") or 0) < 150 \
            and (val.get("pv_w") or 0) < (val.get("charge_puissance_w") or 0) + 50:
        val["batterie_courant_lu_a"] = c
        val["batterie_courant_a"] = -c
        val["courant_sens"] = "deduit"
    if val.get("batterie_tension_v") is not None and val.get("batterie_courant_a") is not None:
        val["batterie_puissance_w"] = round(val["batterie_tension_v"] * val["batterie_courant_a"])   # C
    for k in ("pv2_tension_v", "pv_jour_kwh"):          # v1.6b : phase_max_w seulement en triphase
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


def adresse_srne(port):
    """v1.6b : adresse Modbus du SRNE sur cette prise (detection, sinon cle esclaves de envoi.conf, sinon 1)."""
    return ADR_SRNE.get(port) or (UNITES_PRISE.get(port) or ESCLAVES_CONF or [1])[0]


def lire_srne(port):
    """v1.3 : SRNE en Modbus RTU, fonction 03 uniquement (fc.lire). v1.6 : blocs triphase et compteurs."""
    fc.PORT = port
    try:
        fd = fc.ouvrir()
        blocs = {}
        for a, n in SRNE_BLOCS:
            r = fc.lire(fd, a, n, essais=4 if a in (0x0100, 0x0210) else 1, esclave=adresse_srne(port))   # v1.6b
            if r is not None:
                blocs[a] = r
            time.sleep(0.1)
        os.close(fd)
    except OSError as e:
        return {"statut": "PORT_INDISPONIBLE", "erreur": str(e)}
    val = srne_valeurs(blocs)
    if val is None:
        return {"statut": "CONVERTISSEUR_MUET"}
    return {"statut": "OK", "valeurs": val, "brut": {"%04X" % a: r for a, r in blocs.items()}}    # v1.7 : brut garde


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
    par, statuts, bruts = {}, {}, {}
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
        if r.get("brut"):
            bruts[nom] = r["brut"]                # v1.7 : registres / reponses brutes gardes (releve complet)
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
    if bruts:
        rec["brut_par_convertisseur"] = bruts
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


# ---------------------------------------------------------------------------------------------------------------
# v1.7 (27/11) : MESURE CHAQUE MINUTE, EVENEMENTS DATES, ENERGIE CALCULEE, SANTE, MEMOIRE DES CONVERTISSEURS
# Le minuteur lance ce fichier chaque minute ; la cadence reelle se regle dans envoi.conf (sans toucher au boitier) :
#   mesure_s = 60        (secondes entre deux mesures ; 60 a 900)
#   complet_min = 5      (minutes entre deux releves complets : disque, direct, rattrapage horaire ; 5 a 60)
# Chaque minute : mesure, evenements, energie, ligne courte en memoire vive (/run, pas d'usure du disque).
# Tous les 5 min : lignes de la periode ecrites sur le disque d'un coup, releve complet (avec les reponses brutes),
#   sante du boitier, envoi direct (avec les evenements non encore accuses), historique horaire.
# Une fois par jour : lecture seule de la memoire des convertisseurs (journal des defauts et reglages SRNE,
#   reglages et drapeaux MPP), gardee brute ; un changement produit un evenement.
# ---------------------------------------------------------------------------------------------------------------
MESURE_S, COMPLET_S = 60, 300
ETAT_RAM = os.path.join(fc.RUN, "etat.json")
MINUTES_RAM = os.path.join(fc.RUN, "minutes.jsonl")
MPP_MEMOIRE = ("QPIRI", "QFLAG", "QVFW", "QBEQI")
for _q in MPP_MEMOIRE:
    assert _q.startswith("Q"), _q                # interrogation seulement
SRNE_MEMOIRE = ((0xF800, 32), (0xF820, 32), (0xF840, 32), (0xF860, 32), (0xE000, 32), (0xE020, 32))
TYPES_EVENEMENTS = ("demarrage_boitier", "heure_synchronisee", "coupure_reseau", "retour_reseau", "changement_mode",
                    "avertissement", "convertisseur_absent", "convertisseur_retour", "detection_refaite",
                    "journal_defauts", "reglages_modifies", "temperature_boitier", "disque_presque_plein")


def p_data(n):
    return os.path.join(fc.DATA, n)


def regler_cadence():
    global MESURE_S, COMPLET_S
    cfg = fc.lire_envoi_brut()
    try:
        MESURE_S = min(900, max(60, int(cfg.get("mesure_s") or 60)))
    except ValueError:
        MESURE_S = 60
    try:
        COMPLET_S = 60 * min(60, max(5, int(cfg.get("complet_min") or 5)))
    except ValueError:
        COMPLET_S = 300


def cpu_c():
    t = []
    for f in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            t.append(int(open(f).read().strip()) / 1000.0)
        except (OSError, ValueError):
            pass
    return round(max(t), 1) if t else None


def sante(t0):
    s = {"version": VERSION, "boot": fc.boot_id()[:8], "uptime_s": fc.uptime_s(), "cpu_c": cpu_c(),
         "duree_mesure_s": round(time.time() - t0, 1)}
    try:
        st = os.statvfs(fc.DATA)
        s["disque_libre_mo"] = round(st.f_bavail * st.f_frsize / 1048576)
        s["disque_libre_pct"] = round(100.0 * st.f_bavail / st.f_blocks, 1)
    except OSError:
        pass
    try:
        for l in open("/proc/meminfo"):
            if l.startswith("MemAvailable:"):
                s["ram_libre_mo"] = round(int(l.split()[1]) / 1024)
        s["charge_1m"] = round(os.getloadavg()[0], 2)
    except (OSError, ValueError):
        pass
    d = fc.lire_json(p_data("demarrages.json"), []) or []
    s["demarrages_total"] = len(d)
    s["banc"] = 1 if os.path.exists(p_data("BANC")) else 0
    s["chien_de_garde"] = 1 if os.path.exists("/etc/systemd/system.conf.d/opti-watchdog.conf") and \
        os.path.exists("/dev/watchdog") else 0
    return {k: v for k, v in s.items() if v is not None}


def evenement_seq():
    """Plus grand numero d'evenement deja ecrit (fin du fichier : un arret brutal ne cree pas de doublon)."""
    p = p_data("evenements.jsonl")
    try:
        with open(p, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 65536))
            lignes = f.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return 0
    m = 0
    for l in lignes:
        try:
            m = max(m, int(json.loads(l)["id"]))
        except Exception:
            pass
    return m


def ecrire_evenements(evs, rec, etat):
    """Evenements ecrits tout de suite sur le disque (rares, importants)."""
    if not evs:
        return []
    seq = etat.get("seq") or evenement_seq()
    out = []
    for e in evs:
        seq += 1
        x = {"id": seq, "t": rec["horodatage"], "hv": rec.get("heure_verifiee", 1), "boot": rec.get("boot"),
             "up": rec.get("uptime_s"), "site": fc.CODE}
        x.update(e)
        out.append(x)
    etat["seq"] = seq
    try:
        fc.ajouter_lignes(p_data("evenements.jsonl"), [json.dumps(x, ensure_ascii=False) for x in out])
    except OSError:
        pass
    return out


def a_envoyer_evenements(n=20):
    """Les plus anciens evenements non encore accuses par le tableau de bord (aucun ne se perd)."""
    ack = (fc.lire_json(p_data("evenements_ack.json"), {}) or {}).get("id", 0)
    p = p_data("evenements.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    try:
        for l in open(p, encoding="utf-8"):
            try:
                e = json.loads(l)
            except ValueError:
                continue
            if int(e.get("id", 0)) > ack:
                out.append(e)
                if len(out) >= n:
                    break
    except OSError:
        pass
    return out


def accuser_evenements():
    """Le tableau de bord renvoie evenements_recus = dernier numero garde (a venir cote serveur)."""
    try:
        n = int(fc.REPONSE_DIRECT.get("evenements_recus") or 0)
    except (TypeError, ValueError):
        return
    ack = (fc.lire_json(p_data("evenements_ack.json"), {}) or {}).get("id", 0)
    if n > ack:
        fc.ecrire_json(p_data("evenements_ack.json"), {"id": n})


def par_conv(rec):
    if rec.get("par_convertisseur") and CONVERTISSEURS:
        return rec["par_convertisseur"]
    if rec.get("statut") == "OK":
        return {"principal": rec.get("valeurs") or {}}
    return {"principal": {"statut": rec.get("statut")}}


def resume(v):
    return {"ok": 0 if v.get("statut") else 1,
            "reseau": 1 if (v.get("reseau_tension_v") or 0) > 150 else 0,
            "mode": v.get("mode_brut"), "avert": v.get("avertissements")}


def detecter_evenements(rec, etat, premier):
    evs = []
    if premier:
        avant = fc.lire_json(p_data("dernier.json"), {}) or {}
        evs.append({"type": "demarrage_boitier", "version": VERSION, "dernier_releve_avant": avant.get("horodatage")})
    if rec.get("heure_verifiee") and not etat.get("hv_vu"):
        etat["hv_vu"] = 1
        if not premier or rec.get("uptime_s", 0) > 300:
            evs.append({"type": "heure_synchronisee"})
    if rec.get("detection"):
        evs.append({"type": "detection_refaite", "raison": rec["detection"]})
    anc = etat.get("conv") or {}
    nouv = {}
    for nom, v in par_conv(rec).items():
        r = resume(v)
        nouv[nom] = r
        a = anc.get(nom)
        if not a:
            continue
        pa = {"conv": nom}
        if premier:
            pa["pendant_arret"] = 1               # changement survenu boitier eteint (heure exacte inconnue)
        if a["ok"] and not r["ok"]:
            evs.append(dict(pa, type="convertisseur_absent", statut=v.get("statut")))
            continue
        if r["ok"] and not a["ok"]:
            evs.append(dict(pa, type="convertisseur_retour"))
        if not r["ok"] or not a["ok"]:
            continue
        if a["reseau"] and not r["reseau"]:
            evs.append(dict(pa, type="coupure_reseau", tension_v=v.get("reseau_tension_v")))
        elif r["reseau"] and not a["reseau"]:
            evs.append(dict(pa, type="retour_reseau", tension_v=v.get("reseau_tension_v")))
        if a["mode"] != r["mode"] and r["mode"]:
            evs.append(dict(pa, type="changement_mode", avant=a["mode"], apres=r["mode"]))
        if (a["avert"] or "") != (r["avert"] or "") and r["avert"] is not None:
            evs.append(dict(pa, type="avertissement", avant=a["avert"], apres=r["avert"]))
    for nom in anc:
        if nom not in nouv and anc[nom].get("ok"):
            evs.append({"type": "convertisseur_absent", "conv": nom, "statut": "plus_detecte"})
    etat["conv"] = dict(anc, **nouv) if not premier else nouv
    return evs


def integrer(rec, etat):
    """Energie calculee minute par minute (C) : solaire, consommation, charge et decharge batterie. Un intervalle
    de plus de 6 min (boitier eteint, releve manque) n'est pas compte : jamais d'energie inventee."""
    if rec.get("statut") != "OK":
        etat.pop("e_up", None)
        return
    v = rec["valeurs"]
    w = {"pv_kwh": v.get("pv_w"), "charge_kwh": v.get("charge_puissance_w")}
    b = v.get("batterie_puissance_w")
    if b is not None:
        w["batt_charge_kwh"], w["batt_decharge_kwh"] = max(0, b), max(0, -b)
    up = rec.get("uptime_s") or 0
    jour = rec["horodatage"][:10] if rec.get("heure_verifiee") else "nv-" + (rec.get("boot") or "")[:8]
    E = etat.setdefault("energie", {})
    if jour not in E:
        E[jour] = (fc.lire_json(p_data("energie.json"), {}) or {}).get(jour) or {}
    d = E[jour]
    pu, pw = etat.get("e_up"), etat.get("e_w") or {}
    if pu is not None and 0 < up - pu <= 360:
        h = (up - pu) / 3600.0
        for k, x in w.items():
            if x is not None and pw.get(k) is not None:
                d[k] = round(d.get(k, 0) + (x + pw[k]) / 2.0 * h / 1000.0, 4)
        d["minutes"] = round(d.get("minutes", 0) + (up - pu) / 60.0, 1)
    etat["e_up"], etat["e_w"] = up, w
    for j in sorted(E)[:-3]:
        E.pop(j, None)
    v["energie_jour"] = {k: round(x, 3) for k, x in d.items()}


def sauver_energie(etat):
    p = p_data("energie.json")
    tout = fc.lire_json(p, {}) or {}
    tout.update(etat.get("energie") or {})
    garde = sorted(k for k in tout if k[:2] == "20")[-730:]
    tout = {k: tout[k] for k in tout if k in garde or (k.startswith("nv-") and k in (etat.get("energie") or {}))}
    fc.ecrire_json(p, tout, None)


def memoire_du_jour(rec, etat):
    """Lecture seule, une fois par jour : journal des defauts / reglages SRNE, reglages / drapeaux MPP."""
    jour = rec["horodatage"][:10] if rec.get("heure_verifiee") else "boot-" + (rec.get("boot") or "")[:8]
    if etat.get("memoire_jour") == jour:
        return []
    etat["memoire_jour"] = jour
    evs = []
    os.makedirs(p_data("memoire"), exist_ok=True)
    for nom, port, marque in CONVERTISSEURS:
        if not os.path.exists(port) or marque not in ("SRNE", "MPP"):
            continue
        brut = {}
        try:
            if marque == "SRNE":
                fc.PORT = port
                fd = fc.ouvrir()
                time.sleep(0.3)
                for a, n in SRNE_MEMOIRE:
                    r = fc.lire(fd, a, n, essais=2, esclave=adresse_srne(port))
                    if r is not None:
                        brut["%04X" % a] = r
                    time.sleep(0.1)
                os.close(fd)
            else:
                fd = mp.ouvrir(port)
                time.sleep(0.3)
                for q in MPP_MEMOIRE:
                    r, ok = mp.demander(fd, port, q)
                    if r is not None and ok:
                        brut[q] = r
                    time.sleep(0.15)
                os.close(fd)
        except OSError:
            continue
        if not brut:
            continue
        p = p_data("memoire/%s.json" % nom)
        anc = (fc.lire_json(p, {}) or {}).get("brut") or {}
        if anc:
            if marque == "SRNE":
                vieux = set(tuple(x) for x in journal_srne(anc))
                neufs = [x for x in journal_srne(brut) if tuple(x) not in vieux]
                if neufs:
                    evs.append({"type": "journal_defauts", "conv": nom, "nouveaux": neufs[:8]})
                reg = [(k, i, anc[k][i], v[i]) for k, v in brut.items() if k.startswith("E") and k in anc
                       for i in range(min(len(v), len(anc[k]))) if v[i] != anc[k][i]]
                if reg:
                    evs.append({"type": "reglages_modifies", "conv": nom,
                                "changes": ["%04X:%s>%s" % (int(k, 16) + i, a, b) for k, i, a, b in reg[:20]]})
            else:
                ch = [q for q in brut if q in anc and brut[q] != anc[q] and q != "QBEQI"]
                if ch:
                    evs.append({"type": "reglages_modifies", "conv": nom,
                                "changes": ["%s:%s>%s" % (q, anc[q], brut[q]) for q in ch]})
        fc.ecrire_json(p, {"horodatage": rec["horodatage"], "heure_verifiee": rec.get("heure_verifiee"),
                           "marque": marque, "brut": brut})
    return evs


def journal_srne(brut):
    """Journal SRNE 0xF800-0xF87F : 8 fiches de 16 registres ; on garde les fiches non vides, brutes."""
    regs = []
    for a in ("F800", "F820", "F840", "F860"):
        regs += brut.get(a) or [None] * 32
    out = []
    for i in range(0, len(regs), 16):
        f = regs[i:i + 16]
        if None not in f and any(f):
            out.append(f)
    return out


def ligne_minute(rec):
    v = rec.get("valeurs") or {}
    x = {"t": rec["horodatage"], "hv": rec.get("heure_verifiee"), "up": rec.get("uptime_s"), "boot": rec.get("boot"),
         "s": rec.get("statut")}
    for k, c in (("batterie_tension_v", "bv"), ("batterie_soc_pct", "soc"), ("batterie_courant_a", "ba"),
                 ("pv_w", "pv"), ("charge_puissance_w", "w"), ("reseau_tension_v", "rv"), ("mode_brut", "m"),
                 ("convertisseurs_lus", "lus"), ("temperature_c", "tc")):
        if v.get(k) is not None:
            x[c] = v[k]
    pc = rec.get("par_convertisseur")
    if pc and len(pc) > 1:
        x["pc"] = {n: [c.get("statut") or "OK", c.get("reseau_tension_v"), c.get("pv_w"), c.get("charge_puissance_w"),
                       c.get("mode_brut")] for n, c in pc.items()}
    return x


def vider_minutes():
    """Lignes minute de la periode : de la memoire vive vers le disque, d'un coup."""
    try:
        lignes = open(MINUTES_RAM, encoding="utf-8").read().splitlines()
    except OSError:
        return 0
    par = {}
    for l in lignes:
        try:
            x = json.loads(l)
        except ValueError:
            continue
        f = fc.fichier_stock({"horodatage": x["t"], "heure_verifiee": x.get("hv"), "boot": x.get("boot")}, "min-")
        par.setdefault(f, []).append(l)
    for f, ls in par.items():
        fc.ajouter_lignes(f, ls)
    os.remove(MINUTES_RAM)
    return len(lignes)


def noter_demarrage(rec):
    p = p_data("demarrages.json")
    d = fc.lire_json(p, []) or []
    if not d or d[-1].get("boot") != rec.get("boot"):
        d.append({"boot": rec.get("boot"), "t": rec["horodatage"], "hv": rec.get("heure_verifiee"),
                  "up": rec.get("uptime_s")})
        fc.ecrire_json(p, d[-200:], None)


def cycle(t0, force=False, envoyer=True):
    """v1.7 : une mesure ; releve complet si la periode est ecoulee (ou force)."""
    regler_cadence()
    os.makedirs(fc.RUN, exist_ok=True)
    etat = fc.lire_json(ETAT_RAM, None)
    premier = etat is None or etat.get("boot") != fc.boot_id()[:8]
    if premier:                                           # memoire vive videe : nouveau demarrage du boitier
        etat = fc.lire_json(p_data("etat_persistant.json"), {}) or {}
        etat = {"conv": etat.get("conv") or {}, "seq": evenement_seq(), "boot": fc.boot_id()[:8],
                "memoire_jour": None}
    up = fc.uptime_s() or 0
    if not force and etat.get("m_up") is not None and up - etat["m_up"] < MESURE_S - 15:
        return None                                       # cadence reglee plus lente que le minuteur
    rec = releve()
    rec["heure_verifiee"] = 1 if fc.horloge_ok() else 0
    rec["boot"], rec["uptime_s"] = etat["boot"], fc.uptime_s()
    evs = detecter_evenements(rec, etat, premier)
    integrer(rec, etat)
    etat["m_up"] = up
    complet = force or premier or etat.get("c_up") is None or up - etat["c_up"] >= COMPLET_S - 20
    if complet:
        if premier:
            noter_demarrage(rec)
        evs += memoire_du_jour(rec, etat)
        s = sante(t0)
        h = etat.setdefault("alertes_sante", {})
        if s.get("cpu_c") and (s["cpu_c"] >= 75) != bool(h.get("cpu")):
            h["cpu"] = s["cpu_c"] >= 75
            evs.append({"type": "temperature_boitier", "cpu_c": s["cpu_c"], "etat": "haute" if h["cpu"] else "normale"})
        if s.get("disque_libre_pct") is not None and (s["disque_libre_pct"] < 10) != bool(h.get("disque")):
            h["disque"] = s["disque_libre_pct"] < 10
            evs.append({"type": "disque_presque_plein", "libre_pct": s["disque_libre_pct"], "etat": "oui" if h["disque"] else "non"})
        rec["sante"] = s
    ecrits = ecrire_evenements(evs, rec, etat)
    if ecrits:
        rec["evenements_nouveaux"] = [e["type"] + (":" + e["conv"] if e.get("conv") else "") for e in ecrits]
    fc.ajouter_lignes(MINUTES_RAM, [json.dumps(ligne_minute(rec), ensure_ascii=False)])
    fc.ecrire_json(os.path.join(fc.RUN, "dernier.json"), rec)
    if complet:
        etat["c_up"] = up
        vider_minutes()
        fc.recaler()
        fc.sauver(rec)
        rec["evenements"] = a_envoyer_evenements()
        sauver_energie(etat)
        fc.ecrire_json(p_data("etat_persistant.json"), {"conv": etat.get("conv"), "seq": etat.get("seq"),
                                                         "horodatage": rec["horodatage"]})
        if envoyer:
            rec["direct"] = fc.envoyer_direct(rec)
            accuser_evenements()
            # campagne au banc (fichier DATA/BANC) : pas d'historique horaire sous le code du site client
            rec["envoi"] = "envoi=banc" if os.path.exists(p_data("BANC")) else fc.envoyer(rec)
        rec.pop("evenements", None)
    fc.ecrire_json(ETAT_RAM, etat)
    rec["complet"] = 1 if complet else 0
    return rec


def verrou():
    """v1.1 : attend au plus 60 s que le releve en cours se termine ; sinon abandonne (le suivant passera)."""
    f = open("/run/opti-mpp.lock", "w")
    fin = time.time() + 45                        # v1.7 : mesure chaque minute
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
    if "--test" in sys.argv:                     # v1.7 : test apres mise a jour automatique (aucun cable touche)
        v = srne_valeurs({0x0100: [80, 532, 65524] + [0] * 13, 0x0210: [4] + [0] * 15})
        assert v and v["batterie_tension_v"] == 53.2 and v["batterie_courant_a"] == 1.2, v
        v = srne_valeurs({0x0100: [80, 532, 65524] + [0] * 13, 0x0210: [5] + [0] * 15})
        assert v["batterie_courant_a"] == -1.2 and v["courant_sens"] == "deduit", v
        assert depuis_qpigs is not None and fc.ecrire_json and fc.recaler and cycle
        print("test", VERSION, "OK")
        return
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
        p = os.path.join(fc.RUN, "dernier.json")          # v1.7 : mesure de la minute (memoire vive)
        p = p if os.path.exists(p) else os.path.join(fc.DATA, "dernier.json")
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
    if "--evenements" in sys.argv:               # v1.7 : 30 derniers evenements
        p = p_data("evenements.jsonl")
        for l in (open(p, encoding="utf-8").read().splitlines()[-30:] if os.path.exists(p) else []):
            try:
                e = json.loads(l)
            except ValueError:
                continue
            print("%5s %s%s %-22s %s" % (e.get("id"), e.get("t"), "" if e.get("hv", 1) else " (heure non verifiee)",
                  e.get("type"), " ".join("%s=%s" % (k, x) for k, x in e.items()
                                            if k not in ("id", "t", "hv", "type", "boot", "site", "up"))))
        return
    if "--sante" in sys.argv:                    # v1.7
        for k, x in sante(time.time()).items():
            print("  %-20s %s" % (k, x))
        print("  %-20s %s" % ("heure_verifiee", fc.horloge_ok()))
        return
    garde = verrou()                              # v1.1
    t0 = time.time()
    rec = cycle(t0, force="--sans-envoi" in sys.argv or "--complet" in sys.argv, envoyer="--sans-envoi" not in sys.argv)
    if rec is None:
        return
    v = rec.get("valeurs", {})
    print("%s %s%s mode=%s batterie=%s V %s %% %s A charge=%s W pv=%s W reseau=%s V convertisseurs=%s/%s %s" % (
        rec["horodatage"], rec["statut"], "" if rec.get("heure_verifiee") else " (heure non verifiee)", v.get("mode_brut"),
        v.get("batterie_tension_v"), v.get("batterie_soc_pct"), v.get("batterie_courant_a"), v.get("charge_puissance_w"),
        v.get("pv_w"), v.get("reseau_tension_v"), v.get("convertisseurs_lus", 1), v.get("convertisseurs_attendus", 1),
        "complet" if rec.get("complet") else "minute"), rec.get("direct", ""), rec.get("envoi", ""),
        ("evenements: " + ", ".join(rec["evenements_nouveaux"])) if rec.get("evenements_nouveaux") else "")

if __name__ == "__main__":
    main()
