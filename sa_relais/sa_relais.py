#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTI-MIST SOLUTIONS - Relais Solar Assistant -> "Boitiers en direct" (essai, GO S.S. 15/11/2026 18h30)

Tourne sur le boitier OPTI-061 (toujours allume). Toutes les 5 minutes, pour chaque site de la liste :
  sacli site <slug> metrics   (LECTURE SEULE)
puis envoie le dernier releve au tableau de bord (meme adresse et meme jeton que le boitier, envoi.conf),
sous le code OPTI-XXX du site. Le tableau de bord l'archive dans DIRECT_5MIN : visuels "Energie" au pas de
5 minutes pour les sites Solar Assistant, sans boitier sur site et sans minutes GitHub.

SECURITE (obligatoire) :
  - Ce programme n'appelle QUE "site <slug> metrics". Toute autre commande est refusee par sacli_lecture().
  - Le jeton Solar Assistant est configure pour l'utilisateur systeme "optisa" (HOME=/var/lib/optisa, droits 700),
    jamais dans ce fichier, jamais dans GitHub, jamais dans le chat.
  - Le jeton permet aussi des ecritures (commande "set") : ne jamais lancer sacli a la main avec ce compte
    en dehors de "metrics". Demande en cours a Solar Assistant : jeton en lecture seule.

Champs envoyes (liste blanche Boitiers.gs v1.7) :
  pv_w, charge_puissance_w, reseau_w, reseau_tension_v, batterie_soc_pct,
  batterie_puissance_w = pv + reseau - charge (C : bilan, + = charge, - = decharge),
  e_pv_kwh, e_charge_kwh, e_reseau_in_kwh, e_reseau_out_kwh, e_bat_in_kwh, e_bat_out_kwh (v1.1 : energie du jour, C), e_base_h.

Configuration : /etc/opti061/sa_relais.conf (droits 640, root:optisa)
  sites = OPTI-XXX:nom-du-module-solar-assistant, OPTI-YYY:autre-module (liste reelle : sur le boitier seulement)
Usage : sa_relais.py --once | --test (lit et affiche, n'envoie rien)

v1.1 (15/11/2026 21h, GO S.S. : extension aux 20 sites Solar Assistant actifs) :
  - attente maximale 15 s par site (au lieu de 40) : 20 sites tiennent dans la limite de 290 s du service ;
  - compteurs DU JOUR calcules par le boitier : les compteurs Solar Assistant ne repartent pas tous de zero a minuit
    (OPTI-012 : 51 kWh "produits" pour 3,15 kWc - M/C). Le boitier garde, par site, la valeur au premier releve du jour
    (/var/lib/optisa/compteurs.json) et envoie e_*_kwh = valeur actuelle - valeur de depart ; si un compteur redescend
    (remise a zero par Solar Assistant), la valeur actuelle est prise telle quelle. e_base_h = heure du point de depart :
    le tableau de bord n'utilise ces compteurs que si le depart date d'avant 00h15 (sinon calcul par les releves).
"""
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request

VERSION = "1.1 (15/11/2026)"
ETAT = "/var/lib/optisa/compteurs.json"
SACLI = "/opt/optisa/sacli"
CONF = "/etc/opti061/sa_relais.conf"
ENVOI_CONF = "/etc/opti061/envoi.conf"
CLES = {   # sujet Solar Assistant -> champ direct (noms relevés dans notre code de supervision, M)
    "total/pv_power": "pv_w", "total/load_power": "charge_puissance_w", "total/grid_power": "reseau_w",
    "total/grid_voltage": "reseau_tension_v", "total/battery_state_of_charge": "batterie_soc_pct",
    "total/pv_energy": "e_pv_kwh", "total/load_energy": "e_charge_kwh", "total/grid_energy_in": "e_reseau_in_kwh",
    "total/grid_energy_out": "e_reseau_out_kwh", "total/battery_energy_in": "e_bat_in_kwh", "total/battery_energy_out": "e_bat_out_kwh",
}
REPLI = {"total/load_power": "inverter_1/load_power", "total/grid_voltage": "inverter_1/grid_voltage",
         "total/battery_state_of_charge": "inverter_1/battery_state_of_charge"}


def lire_conf(chemin, defaut):
    cfg = dict(defaut)
    try:
        for ligne in open(chemin, encoding="utf-8"):
            if "=" in ligne and not ligne.strip().startswith("#"):
                k, v = ligne.split("=", 1)
                cfg[k.strip()] = v.strip()
    except OSError:
        pass
    return cfg


def sacli_lecture(slug):
    """SEULE commande autorisee : site <slug> metrics (lecture)."""
    if not slug or any(c in slug for c in " ;|&$`'\"\\/"):
        raise ValueError("slug refuse")
    r = subprocess.run([SACLI, "site", slug, "metrics"], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return None, (r.stderr or "").strip()[:80]
    m = {}
    for ligne in r.stdout.strip().split("\n"):
        p = ligne.strip().split(" ", 1)
        if len(p) == 2:
            m[p[0]] = p[1]
    return m, ""


def nombre(brut, puissance=False):
    if brut is None:
        return None
    try:
        s = str(brut).strip()
        v = float(s.split()[0])
        if puissance and "kw" in s.lower():
            v *= 1000.0
        return v
    except (ValueError, IndexError):
        return None


def valeurs(m):
    v = {}
    for cle, champ in CLES.items():
        brut = m.get(cle, m.get(REPLI.get(cle, ""), None))
        x = nombre(brut, puissance=champ.endswith("_w"))
        if x is not None:
            v[champ] = round(x, 2)
    if all(k in v for k in ("pv_w", "charge_puissance_w")):
        v["batterie_puissance_w"] = round(v["pv_w"] + v.get("reseau_w", 0) - v["charge_puissance_w"], 1)
    return v


def compteurs_du_jour(code, v, etat, maintenant):
    """Remplace les compteurs cumules par l'energie depuis le premier releve du jour (C)."""
    cles = [k for k in v if k.startswith("e_") and k.endswith("_kwh")]
    if not cles:
        return v
    jour = maintenant.strftime("%Y-%m-%d")
    e = etat.get(code)
    if not e or e.get("jour") != jour:
        e = {"jour": jour, "h": round(maintenant.hour + maintenant.minute / 60.0, 2), "base": {k: v[k] for k in cles}}
        etat[code] = e
    for k in cles:
        b = e["base"].get(k)
        if b is None:
            e["base"][k] = b = v[k]
        v[k] = round(v[k] - b, 2) if v[k] >= b else v[k]
    v["e_base_h"] = e["h"]
    return v


def envoyer(code, v, cfg):
    corps = {"jeton": cfg["direct_jeton"], "direct": {"code": code, "horodatage": dt.datetime.now().isoformat(timespec="seconds"),
             "statut": "OK" if v else "HORS LIGNE", "mode": "sa", "valeurs": v}}
    req = urllib.request.Request(cfg["direct_url"], data=json.dumps(corps).encode(), headers={"Content-Type": "application/json"})
    try:
        res = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        return "ok" if res.get("status") == "ok" else "refuse"
    except Exception as e:
        return "echec(%s)" % type(e).__name__


def main():
    test = "--test" in sys.argv
    cfg = lire_conf(ENVOI_CONF, {"direct_url": "", "direct_jeton": ""})
    sites = [s.strip() for s in lire_conf(CONF, {"sites": ""})["sites"].split(",") if ":" in s]
    if not sites:
        sys.exit("Aucun site dans %s (sites = OPTI-XXX:slug, ...)" % CONF)
    if not test and (not cfg["direct_url"] or not cfg["direct_jeton"]):
        sys.exit("direct_url / direct_jeton absents de %s" % ENVOI_CONF)
    maintenant = dt.datetime.now()
    try:
        etat = json.load(open(ETAT, encoding="utf-8"))
    except (OSError, ValueError):
        etat = {}
    for s in sites:
        code, slug = [x.strip() for x in s.split(":", 1)]
        try:
            m, err = sacli_lecture(slug)
        except Exception as e:
            m, err = None, type(e).__name__
        v = valeurs(m) if m else {}
        if v and not test:
            v = compteurs_du_jour(code, v, etat, maintenant)
        if test:
            print("%s (%s) : %s" % (code, slug, json.dumps(v, ensure_ascii=False) if v else "injoignable " + err))
            continue
        print("%s %s : %d champ(s), direct=%s" % (dt.datetime.now().strftime("%H:%M"), code, len(v), envoyer(code, v, cfg)))
    if not test:
        try:
            with open(ETAT + ".tmp", "w", encoding="utf-8") as f:
                json.dump(etat, f)
            os.replace(ETAT + ".tmp", ETAT)
        except OSError as x:
            print("etat non enregistre :", x)


if __name__ == "__main__":
    main()
