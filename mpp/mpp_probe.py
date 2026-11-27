#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTI-MIST SOLUTIONS - Sonde MPP Solar (GK, MK et apparentes) - v1.1 du 19/11/2026
v1.1 (19/11, plaques du banc) : ajout de QPIGS2 (2e entree panneaux des modeles a 2 MPPT, ex. VM III-6000 TWIN), lecture seule.
GO S.S. 19/11 09h57 : preparer la supervision des systemes MPP Solar des sites clients (MPP Solar).
Banc d'essai : 2 MPP Solar (GK et MK) au bureau, sur batteries V5, sans champ PV ni charge.

BUT : identifier le protocole parle par le convertisseur et la signification des valeurs, AVANT d'ecrire le collecteur.
LECTURE SEULE, sans exception : la liste QUESTIONS ci-dessous est figee, elle ne contient que des requetes
d'interrogation (PI30 : commandes commencant par Q ; PI18 : ^P...). Aucune commande de reglage n'existe dans ce fichier
et aucune option ne permet d'en envoyer une.

Usage (en root sur le boitier) :
  python3 mpp_probe.py                        -> essaie /dev/hidraw0, /dev/ttyUSB0, /dev/ttyUSB1 (le premier qui repond)
  python3 mpp_probe.py /dev/ttyUSB0           -> port impose
  python3 mpp_probe.py /dev/ttyUSB0 --tous    -> toutes les questions, meme si le protocole est deja reconnu
  python3 mpp_probe.py /dev/ttyUSB0 --memoire -> v1.2 : en plus, memoire et energie (QFLAG, QET, QEY, QEM, QED, QBEQI)
Resultat a l'ecran et dans /var/lib/opti-mist/mpp_probe_AAAA-MM-JJ_HHMM.json (a transmettre a Claude, sans capture d'autre chose).
"""
import datetime as dt, json, os, select, sys, termios, time, tty

# --- Questions autorisees (lecture seule) -----------------------------------------------------------------------
QUESTIONS = [
    ("PI30", "QPI"),      # protocole
    ("PI30", "QID"),      # numero de serie
    ("PI30", "QVFW"),     # version du logiciel
    ("PI30", "QMOD"),     # mode (L reseau, B batterie, ...)
    ("PI30", "QPIGS"),    # mesures generales (reseau, sortie, batterie, PV)
    ("PI30", "QPIGS2"),   # v1.1 : 2e entree panneaux (modeles TWIN / 2 MPPT)
    ("PI30", "QPIRI"),    # valeurs nominales
    ("PI30", "QPIWS"),    # avertissements
    ("PI30", "QPGS0"),    # mesures en parallele, unite 0
    ("PI30", "QPGS1"),    # unite 1
    ("PI30", "QPGS2"),    # unite 2
    ("PI18", "^P005PI"),  # protocole PI18
    ("PI18", "^P005GS"),  # mesures generales PI18
    ("PI18", "^P006MOD"), # mode PI18
]
# v1.2 (26/11, campagne banc) : option --memoire = questions de memoire et d'energie (PI30, interrogation seule ;
# reponse ou NAK selon le modele, S) : drapeaux, energie PV totale / annee / mois / jour.
_J = dt.date.today()
MEMOIRE = [("PI30", "QFLAG"), ("PI30", "QET"), ("PI30", "QEY%04d" % _J.year), ("PI30", "QEM%04d%02d" % (_J.year, _J.month)),
           ("PI30", "QED%04d%02d%02d" % (_J.year, _J.month, _J.day)), ("PI30", "QBEQI")]
for _p, _q in MEMOIRE:      # garde-fou : interrogations seulement
    assert _q.startswith("Q"), _q
for _p, _q in QUESTIONS:   # garde-fou : rien d'autre que des interrogations
    assert _q.startswith("Q") or _q.startswith("^P"), _q

CHAMPS_QPIGS = ["reseau_tension_v", "reseau_frequence_hz", "sortie_tension_v", "sortie_frequence_hz", "sortie_apparente_va",
                "sortie_puissance_w", "charge_pct", "bus_tension_v", "batterie_tension_v", "batterie_courant_charge_a",
                "batterie_soc_pct", "temperature_c", "pv_courant_a", "pv_tension_v", "batterie_tension_scc_v",
                "batterie_courant_decharge_a", "etat_bits", "ecart_ventilateur", "version_eeprom", "pv_puissance_w"]


def crc_xmodem(d):
    c = 0
    for b in d:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    hi, lo = c >> 8, c & 0xFF
    if hi in (0x28, 0x0D, 0x0A):   # octets reserves du protocole MPP : incrementes
        hi += 1
    if lo in (0x28, 0x0D, 0x0A):
        lo += 1
    return bytes([hi, lo])


def trame(q):
    b = q.encode("ascii")
    return b + crc_xmodem(b) + b"\r"


def ouvrir(port):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    if "hidraw" not in port:
        tty.setraw(fd)
        a = termios.tcgetattr(fd)
        a[4] = a[5] = termios.B2400
        a[2] = (a[2] & ~(termios.PARENB | termios.CSTOPB | termios.CSIZE)) | termios.CS8 | termios.CLOCAL | termios.CREAD
        termios.tcsetattr(fd, termios.TCSANOW, a)
        termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def demander(fd, port, q, attente=2.5):
    t = trame(q)
    if "hidraw" in port:                       # USB : morceaux de 8 octets
        for i in range(0, len(t), 8):
            os.write(fd, t[i:i + 8].ljust(8, b"\x00"))
    else:
        termios.tcflush(fd, termios.TCIOFLUSH)
        os.write(fd, t)
    buf, fin = b"", time.time() + attente
    while time.time() < fin:
        if select.select([fd], [], [], 0.1)[0]:
            try:
                buf += os.read(fd, 256)
            except (BlockingIOError, OSError):
                pass
            if b"\r" in buf:
                break
    buf = buf.replace(b"\x00", b"")
    if b"\r" not in buf:
        return None, buf
    corps = buf[:buf.index(b"\r")]
    texte = corps[:-2] if len(corps) > 2 else corps
    crc_ok = len(corps) > 2 and crc_xmodem(corps[:-2]) == corps[-2:]
    return texte.decode("ascii", "replace"), crc_ok


def decoder_qpigs(t):
    if not t.startswith("("):
        return {}
    xs = t[1:].split()
    out = {}
    for nom, x in zip(CHAMPS_QPIGS, xs):
        try:
            out[nom] = float(x) if nom != "etat_bits" else x
        except ValueError:
            out[nom] = x
    return out


def sonder(port, tous, memoire=False):
    res = {"port": port, "reponses": {}}
    fd = ouvrir(port)
    time.sleep(0.3)
    try:
        for proto, q in QUESTIONS + (MEMOIRE if memoire else []):
            if not tous and proto == "PI18" and res.get("protocole") == "PI30":
                continue
            r, crc = demander(fd, port, q)
            res["reponses"][q] = {"texte": r, "crc_ok": crc if r is not None else None,
                                  "brut": None if r is not None else (crc.hex() if isinstance(crc, bytes) else None)}
            if r and q == "QPI" and r.startswith("(PI"):
                res["protocole"] = "PI30"
            if r and q == "^P005PI" and r.startswith("^D"):
                res["protocole"] = "PI18"
            if r and q == "QPIGS":
                res["qpigs"] = decoder_qpigs(r)
            time.sleep(0.2)
    finally:
        os.close(fd)
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tous = "--tous" in sys.argv
    memoire = "--memoire" in sys.argv
    ports = args or ["/dev/hidraw0", "/dev/ttyUSB0", "/dev/ttyUSB1"]
    resultat = {"outil": "mpp_probe 1.2", "horodatage": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "essais": []}
    for p in ports:
        if not os.path.exists(p):
            resultat["essais"].append({"port": p, "absent": True})
            continue
        try:
            r = sonder(p, tous, memoire)
        except OSError as e:
            resultat["essais"].append({"port": p, "erreur": str(e)})
            continue
        resultat["essais"].append(r)
        repondu = [q for q, x in r["reponses"].items() if x["texte"]]
        print("%s : %d reponse(s) sur %d, protocole %s" % (p, len(repondu), len(r["reponses"]), r.get("protocole", "inconnu")))
        for q, x in r["reponses"].items():
            if x["texte"]:
                print("  %-9s %s %s" % (q, x["texte"][:110], "" if x["crc_ok"] else "(controle KO)"))
        for k, v in (r.get("qpigs") or {}).items():
            print("    %-28s %s" % (k, v))
        if repondu and not args:
            break
    d = "/var/lib/opti-mist"
    try:
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, "mpp_probe_" + dt.datetime.now().strftime("%Y-%m-%d_%H%M") + ".json")
        json.dump(resultat, open(f, "w"), ensure_ascii=False, indent=1)
        print("Resultat enregistre :", f)
    except OSError as e:
        print("Resultat non enregistre :", e)


if __name__ == "__main__":
    main()
