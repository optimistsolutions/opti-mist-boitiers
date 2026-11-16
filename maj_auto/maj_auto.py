#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTI-MIST SOLUTIONS - Mise a jour automatique des boitiers (v1.1 du 16/11/2026 : retour arriere aussi si le test depasse le delai ; v1.0 GO S.S. 15/11/2026 22h35)

Le boitier cherche lui-meme ses mises a jour, une fois par jour. AUCUN port ouvert, aucune connexion entrante :
le boitier sort vers internet comme pour l'envoi de ses releves.

DEUX CANAUX INDEPENDANTS (un pirate devrait compromettre les deux) :
  1. APPROBATION : le tableau de bord (Apps Script, meme adresse et meme jeton que le direct) renvoie, pour ce
     boitier, la liste des fichiers APPROUVES par S.S. avec leur empreinte sha256 (propriete MAJ_APPROUVEES).
  2. FICHIERS : telecharges depuis le depot de code (adresse depot_url).
  Un fichier n'est installe QUE si son empreinte est exactement celle approuvee. Sinon : rien n'est touche.

SECURITE DE L'INSTALLATION :
  - controle de syntaxe Python avant installation ;
  - copie de l'ancienne version (.precedent) ;
  - test apres installation (commande "test" du composant) ; en cas d'echec : RETOUR AUTOMATIQUE a l'ancienne version ;
  - journal : /var/lib/opti-maj/journal.log ; le resultat part aussi au tableau de bord (statut du boitier, mode "maj").
Configuration : /etc/opti-maj/maj.conf (root, 600)
Usage : maj_auto.py --verifier (montre ce qui serait fait, n'installe rien) | --appliquer
"""
import argparse
import configparser
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

VERSION = "1.1 (16/11/2026)"
CONF = "/etc/opti-maj/maj.conf"
JOURNAL = "/var/lib/opti-maj/journal.log"


def log(msg):
    ligne = "%s %s" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(ligne)
    try:
        os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except OSError:
        pass


def lire_conf():
    c = configparser.ConfigParser(interpolation=None)
    if not c.read(CONF, encoding="utf-8"):
        sys.exit("Configuration absente : %s" % CONF)
    g = c["general"]
    envoi = configparser.ConfigParser(interpolation=None)
    try:
        envoi.read(g.get("fichier_envoi"), encoding="utf-8")
    except configparser.Error:
        pass
    sect = g.get("section_envoi", "")
    src = dict(envoi[sect]) if sect and envoi.has_section(sect) else {}
    if not src:   # format cle = valeur sans section (boitier OPTI-061)
        src = {}
        try:
            for l in open(g.get("fichier_envoi"), encoding="utf-8"):
                if "=" in l and not l.strip().startswith("#"):
                    k, v = l.split("=", 1)
                    src[k.strip()] = v.strip()
        except OSError:
            pass
    comps = {}
    for s in c.sections():
        if s.startswith("composant:"):
            comps[s.split(":", 1)[1]] = dict(c[s])
    return {"code": g.get("code"), "depot_url": g.get("depot_url").rstrip("/"),
            "direct_url": src.get("direct_url", ""), "direct_jeton": src.get("direct_jeton", ""), "composants": comps}


def poster(cfg, corps):
    req = urllib.request.Request(cfg["direct_url"], data=json.dumps(corps).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def approbations(cfg):
    r = poster(cfg, {"jeton": cfg["direct_jeton"], "direct": {"code": cfg["code"], "mode": "maj", "statut": "MAJ_DEMANDE",
                                                             "horodatage": dt.datetime.now().isoformat(timespec="seconds"), "valeurs": {}}})
    if r.get("status") != "ok":
        raise RuntimeError("tableau de bord : %s" % r.get("status"))
    return r.get("maj") or {}


def sha(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def appliquer(cfg, essai):
    appr = approbations(cfg)
    if not appr:
        log("Aucune mise a jour approuvee pour %s." % cfg["code"])
        return 0
    bilan = []
    for nom, a in appr.items():
        comp = cfg["composants"].get(nom)
        if not comp:
            log("%s : approuve mais inconnu sur ce boitier -> ignore." % nom)
            continue
        cible, attendu = comp["chemin"], str(a.get("sha256", "")).lower()
        if len(attendu) != 64:
            log("%s : empreinte approuvee invalide -> ignore." % nom)
            continue
        if os.path.exists(cible) and sha(cible) == attendu:
            continue
        url = "%s/%s" % (cfg["depot_url"], comp["source"])
        if essai:
            log("[verification] %s : version %s a installer depuis %s" % (nom, a.get("version", "?"), url))
            continue
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(cible))
        tmp.close()
        remplace = False
        try:
            urllib.request.urlretrieve(url, tmp.name)
            recu = sha(tmp.name)
            if recu != attendu:
                log("%s : REFUS - empreinte recue %s differente de l'approuvee %s. Rien n'est installe." % (nom, recu[:12], attendu[:12]))
                bilan.append("%s refus empreinte" % nom)
                continue
            if cible.endswith(".py"):
                subprocess.run([sys.executable, "-m", "py_compile", tmp.name], check=True, capture_output=True)
            if os.path.exists(cible):
                shutil.copy2(cible, cible + ".precedent")
            mode = os.stat(cible).st_mode if os.path.exists(cible) else 0o755
            os.chmod(tmp.name, mode & 0o777)
            os.replace(tmp.name, cible)
            remplace = True
            ok = True
            if comp.get("test"):
                r = subprocess.run(comp["test"], shell=True, capture_output=True, text=True, timeout=240)
                ok = r.returncode == 0
            if not ok:
                if os.path.exists(cible + ".precedent"):
                    shutil.copy2(cible + ".precedent", cible)
                log("%s : test en ECHEC apres installation -> RETOUR a la version precedente." % nom)
                bilan.append("%s retour arriere" % nom)
            else:
                log("%s : version %s installee (empreinte %s), test OK." % (nom, a.get("version", "?"), attendu[:12]))
                bilan.append("%s %s ok" % (nom, a.get("version", "?")))
        except Exception as e:
            if remplace and os.path.exists(cible + ".precedent"):   # v1.1 (audit N13 add. 2, B#2) : retour aussi si le test depasse le delai ou plante
                shutil.copy2(cible + ".precedent", cible)
                log("%s : echec du test (%s) apres installation -> RETOUR a la version precedente." % (nom, type(e).__name__))
                bilan.append("%s retour arriere" % nom)
            else:
                log("%s : echec (%s) -> rien n'est change." % (nom, type(e).__name__))
                bilan.append("%s echec" % nom)
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)
    if bilan and not essai:
        try:
            poster(cfg, {"jeton": cfg["direct_jeton"], "direct": {"code": cfg["code"], "mode": "maj", "statut": "MAJ " + " ; ".join(bilan)[:80],
                                                                  "horodatage": dt.datetime.now().isoformat(timespec="seconds"), "valeurs": {}}})
        except Exception:
            pass
    return 0


def main():
    ap = argparse.ArgumentParser(description="Mise a jour automatique " + VERSION)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--verifier", action="store_true")
    g.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()
    if os.geteuid() != 0:
        sys.exit("Lancer en root.")
    cfg = lire_conf()
    sys.exit(appliquer(cfg, a.verifier))


if __name__ == "__main__":
    main()
