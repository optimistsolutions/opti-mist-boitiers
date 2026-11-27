#!/bin/sh
# OPTI-MIST SOLUTIONS - campagne de validation au banc du lecteur universel v1.7 - v2.3 du 27/11/2026 (v2.3 : chien de garde controle dans le journal du systeme, plus seulement la presence du fichier ; v2.2 : fin eteint le boitier sans relancer la mesure, bilan controle la mise a jour a distance ; v2.1 : scenario 8b)
# GO S.S. 26/11 22h50 : tout est valide au banc avant la pose du 28/11 (un boitier pose ne revient plus au banc).
# Lecture seule des convertisseurs. Un seul script par boitier, 4 commandes :
#   sh /root/campagne_v2.sh prepare   installe la v1.7 depuis /root (install_universel v1.1), controle l'installation,
#                                     efface les donnees, marque le boitier « BANC » (pas d'historique horaire sous le
#                                     code du client ; le direct reste actif), relance la mesure chaque minute.
#   sh /root/campagne_v2.sh suivi     affiche chaque minute la mesure et les nouveaux evenements (Ctrl+C pour sortir ;
#                                     la mesure continue). A relancer apres chaque redemarrage du boitier.
#   sh /root/campagne_v2.sh blocage   scenario 8 : plantage volontaire du noyau, chien de garde seul -> redemarrage
#   sh /root/campagne_v2.sh redemarrage  scenario 8b : redemarrage normal (certaines cartes H6 restent bloquees, forums)
#   sh /root/campagne_v2.sh bilan     controle automatique (VERT / ROUGE) -> /root/bilan_<boitier>_<date>.txt
#   sh /root/campagne_v2.sh fin       efface les donnees d'essai et le marquage BANC (a faire avant la pose)
set -u
D=/var/lib/opti061
CMD=${1:-suivi}
H=$(hostname)
[ "$(id -u)" = "0" ] || { echo "Lancer en root"; exit 1; }

case "$CMD" in
prepare)
  CODE=$(sed -n 's/^code *= *//p' /etc/opti061/envoi.conf 2>/dev/null | head -1)
  [ -n "$CODE" ] || { echo "envoi.conf sans code : arret"; exit 1; }
  for f in mpp_collect.py mpp_probe.py felicity_collect.py install_universel.sh; do
    [ -f /root/$f ] || { echo "/root/$f manquant : arret"; exit 1; }
  done
  echo "=== $H ($CODE) - installation v1.7 $(date '+%d/%m %T')"
  (cd /root && sh install_universel.sh "$CODE") > /root/install_v17.log 2>&1
  echo "installation : code retour $? (detail : /root/install_v17.log)"
  systemctl stop opti-mpp.timer
  rm -rf "${D:?}"/* /run/opti061
  date -Iseconds > $D/BANC
  systemctl start opti-mpp.timer
  echo "=== CONTROLES D'INSTALLATION"
  for f in mpp_collect.py felicity_collect.py mpp_probe.py; do echo "  $f $(sha256sum /opt/opti061/$f | cut -c1-8)"; done
  python3 /opt/opti061/mpp_collect.py --test
  grep -q 'OnCalendar=\*:\*:00' /etc/systemd/system/opti-mpp.timer && echo "  minuteur chaque minute : OUI" || echo "  minuteur chaque minute : NON"
  WD=$(journalctl -b --no-pager 2>/dev/null | grep -iE "watchdog hardware timeout|Watchdog running with a hardware timeout" | tail -1)
  case "$WD" in
    *"Watchdog running with a hardware timeout"*) echo "  chien de garde : OUI (${WD##*timeout of }, confirme par le systeme)" ;;
    *) echo "  chien de garde : NON - ROUGE (journal : ${WD:-aucune ligne}) ; corriger avant la pose" ;;
  esac
  echo "  redemarrage sur panne du noyau : $(cat /proc/sys/kernel/panic) s"
  echo "  heure synchronisee : $(timedatectl show -p NTPSynchronized --value)"
  echo "  mise a jour automatique : $(grep -c '^\[composant' /etc/opti-maj/maj.conf 2>/dev/null) composant(s)"
  opti061 detecter
  echo "=== PRET. Lancer : sh /root/campagne_v2.sh suivi"
  ;;
suivi)
  echo "=== $H - suivi (Ctrl+C pour sortir, la mesure continue)"
  DER=0
  while true; do
    python3 - "$DER" <<'EOP'
import json, sys
try:
    r = json.load(open("/run/opti061/dernier.json"))
except Exception:
    print("  (pas encore de mesure)"); sys.exit()
v = r.get("valeurs") or {}
pc = r.get("par_convertisseur") or {}
print("%s %s%s bat %s V %s A | pv %s W | charge %s W | %s" % (r["horodatage"][11:19], r.get("statut"),
      "" if r.get("heure_verifiee") else " HEURE?", v.get("batterie_tension_v"), v.get("batterie_courant_a"), v.get("pv_w"),
      v.get("charge_puissance_w"), " ".join("%s:%s/%sV/%sW" % (n, c.get("statut") or c.get("mode_brut"),
      c.get("reseau_tension_v"), c.get("charge_puissance_w")) for n, c in pc.items())))
n = int(sys.argv[1])
try:
    for l in open("/var/lib/opti061/evenements.jsonl"):
        e = json.loads(l)
        if e["id"] > n:
            print("   >> EVENEMENT %s %s %s" % (e["id"], e["type"], e.get("conv", "")))
except Exception:
    pass
EOP
    DER=$(tail -1 $D/evenements.jsonl 2>/dev/null | python3 -c "import json,sys;print(json.loads(sys.stdin.read() or '{\"id\":0}')['id'])" 2>/dev/null || echo 0)
    sleep 60
  done
  ;;
blocage)
  echo "=== $H - scenario 8 : plantage volontaire a $(date +%T). Le boitier doit redemarrer SEUL en moins de 2 min."
  echo "    (redemarrage automatique du noyau coupe : seul le chien de garde materiel peut le relancer)"
  date -Iseconds > $D/BLOCAGE_DEMANDE
  sync
  sysctl -q -w kernel.panic=0
  echo 1 > /proc/sys/kernel/sysrq
  sleep 2
  echo c > /proc/sysrq-trigger
  ;;
redemarrage)
  echo "=== $H - scenario 8b : redemarrage normal a $(date +%T). Le boitier doit revenir en moins de 3 min."
  date -Iseconds > $D/REDEMARRAGE_DEMANDE
  sync
  systemctl reboot
  ;;
bilan)
  F=/root/bilan_${H}_$(date +%Y%m%d_%H%M).txt
  {
  echo "OPTI-MIST SOLUTIONS - bilan de campagne v2.0 - $H - $(date '+%d/%m/%Y %T')"
  echo "debut de campagne : $(cat $D/BANC 2>/dev/null)"
  for f in mpp_collect.py felicity_collect.py mpp_probe.py; do echo "empreinte $f $(sha256sum /opt/opti061/$f | cut -c1-8)"; done
  echo "--- sante actuelle"; python3 /opt/opti061/mpp_collect.py --sante
  echo "--- redemarrages vus par le systeme"; last -x reboot 2>/dev/null | head -12
  echo "--- erreurs du releve (journal)"; journalctl -u opti-mpp.service --since "$(cut -c1-19 $D/BANC | tr T ' ')" -p warning --no-pager 2>/dev/null | tail -15
  echo "    traces Python : $(journalctl -u opti-mpp.service --since "$(cut -c1-19 $D/BANC | tr T ' ')" --no-pager 2>/dev/null | grep -c Traceback)"
  python3 - <<'EOP'
import glob, json, os, collections
D = "/var/lib/opti061"
res = []
def ctl(ok, txt):
    ok = bool(ok)
    res.append(ok)
    print("%-6s %s" % ("VERT" if ok else "ROUGE", txt))
# evenements
ev, casses = [], 0
for l in open(os.path.join(D, "evenements.jsonl")) if os.path.exists(os.path.join(D, "evenements.jsonl")) else []:
    try:
        ev.append(json.loads(l))
    except ValueError:
        casses += 1
t = collections.Counter(e["type"] for e in ev)
print("--- evenements (%d) : %s" % (len(ev), ", ".join("%s x%d" % kv for kv in sorted(t.items()))))
for e in ev:
    print("  %4s %s%s %-20s %s" % (e["id"], e["t"][5:19], "" if e.get("hv", 1) else "(h?)", e["type"],
          " ".join("%s=%s" % (k, x) for k, x in e.items() if k not in ("id", "t", "hv", "type", "boot", "site", "up"))))
# mesures minute par demarrage
mins, bad = [], 0
for f in sorted(glob.glob(os.path.join(D, "min-*.jsonl")) + glob.glob("/run/opti061/minutes.jsonl")):
    if f.endswith(".recale"):
        continue
    for l in open(f):
        try:
            mins.append(json.loads(l))
        except ValueError:
            bad += 1
par = collections.defaultdict(list)
for m in mins:
    par[m.get("boot")].append(m.get("up") or 0)
print("--- couverture des mesures minute (par demarrage du boitier)")
cov = []
for b, ups in par.items():
    ups = sorted(set(ups))
    att = int((ups[-1] - ups[0]) / 60) + 1 if ups else 0
    cov.append((len(ups), att))
    print("  demarrage %s : %d mesures / %d minutes (%.1f %%)" % (b, len(ups), att, 100.0 * len(ups) / max(1, att)))
tot, att = sum(c[0] for c in cov), sum(c[1] for c in cov)
ctl(att > 0 and tot >= 0.98 * att, "mesure chaque minute : %d / %d (%.1f %%, objectif 98 %%)" % (tot, att, 100.0 * tot / max(1, att)))
ok_s = sum(1 for m in mins if m.get("s") == "OK")
ctl(mins and ok_s >= 0.95 * len(mins), "mesures OK : %d / %d (hors cables arraches volontairement, objectif 95 %%)" % (ok_s, len(mins)))
ctl(bad + casses <= 1 + t["demarrage_boitier"], "lignes illisibles : %d (au plus 1 par coupure du boitier)" % (bad + casses))
# releves complets
comp = []
for f in glob.glob(os.path.join(D, "20*.jsonl")) + glob.glob(os.path.join(D, "nv-*.jsonl")):
    for l in open(f):
        try:
            comp.append(json.loads(l))
        except ValueError:
            pass
s = [c.get("sante") or {} for c in comp]
cpu = [x["cpu_c"] for x in s if x.get("cpu_c")]
dur = [x["duree_mesure_s"] for x in s if x.get("duree_mesure_s")]
ram = [x["ram_libre_mo"] for x in s if x.get("ram_libre_mo")]
print("--- releves complets : %d ; processeur max %s C ; duree de mesure max %s s ; memoire libre min %s Mo" % (
      len(comp), max(cpu) if cpu else "?", max(dur) if dur else "?", min(ram) if ram else "?"))
ctl(cpu and max(cpu) < 75, "temperature du processeur < 75 C")
ctl(dur and max(dur) < 40, "duree d'une mesure < 40 s (cadence 60 s tenue)")
ctl(ram and min(ram) > 200, "memoire libre > 200 Mo")
# scenarios
conv = sorted(set(e.get("conv") for e in ev if e.get("conv")))
ctl(t["coupure_reseau"] >= 1 and t["retour_reseau"] >= 1, "scenarios 2-3 : coupure et retour du reseau dates (%d / %d)" % (t["coupure_reseau"], t["retour_reseau"]))
ctl(t["changement_mode"] >= 2, "changements de mode dates (%d)" % t["changement_mode"])
ctl(t["convertisseur_absent"] >= 1 and t["convertisseur_retour"] >= 1, "scenario 4 : cable arrache puis rebranche (%d / %d)" % (t["convertisseur_absent"], t["convertisseur_retour"]))
noms = collections.defaultdict(set)
for m in mins:
    for n in (m.get("pc") or {}):
        noms[n].add(1)
print("   noms des convertisseurs vus : %s (scenario 5 : noms inchanges apres echange des cables)" % ", ".join(sorted(noms)))
ctl(t["demarrage_boitier"] >= 7, "scenarios 7-8b : demarrages du boitier dates (%d, objectif 7 = 5 coupures + blocage + redemarrage)" % t["demarrage_boitier"])
ctl(any(e.get("pendant_arret") for e in ev), "changement survenu boitier eteint signale (pendant_arret)")
ctl(any(c.get("heure_verifiee") == 2 for c in comp) or t["heure_synchronisee"] >= 1, "scenario 6 : heure non verifiee puis recalee")
srne = [c for c in comp for n, v in (c.get("par_convertisseur") or {}).items() if v.get("courant_sens") == "deduit"]
print("   SRNE : %d releve(s) avec sens du courant deduit (decharge sur batterie)" % len(srne))
blo = os.path.exists(os.path.join(D, "BLOCAGE_DEMANDE"))
ctl(blo and t["demarrage_boitier"] >= 1, "scenario 8 : redemarrage par le chien de garde apres blocage%s" % ("" if blo else " (non fait)"))
en = json.load(open(os.path.join(D, "energie.json"))) if os.path.exists(os.path.join(D, "energie.json")) else {}
print("--- energie calculee (C) : %s" % json.dumps(en, ensure_ascii=False))
ctl(any((x.get("charge_kwh") or 0) > 0 for x in en.values()), "energie consommee calculee")
mem = glob.glob(os.path.join(D, "memoire", "*.json"))
print("--- memoire des convertisseurs : %s" % ", ".join(os.path.basename(m) for m in mem))
for m in mem:
    b = json.load(open(m)).get("brut") or {}
    print("   %s : %s" % (os.path.basename(m), ", ".join("%s(%d)" % (k, len(x)) for k, x in b.items())))
ctl(len(mem) >= 1, "memoire lue (journal des defauts SRNE / reglages MPP)")
try:
    mc = open("/etc/opti-maj/maj.conf").read()
except OSError:
    mc = ""
manque = [c for c in ("mpp_collect.py", "mpp_probe.py", "felicity_collect.py") if "[composant:%s]" % c not in mc]
ctl(not manque, "mise a jour a distance : composants installes%s" % (" - MANQUE " + ", ".join(manque) if manque else " (3/3)"))
ctl(os.path.exists("/etc/systemd/system/opti-maj.timer") or os.path.exists("/etc/systemd/system/optimaj.timer") or
    "opti-maj" in os.popen("systemctl list-timers --all --no-pager 2>/dev/null").read(), "mise a jour a distance : minuteur present")
print("=== RESULTAT : %s (%d VERT / %d)" % ("VERT" if all(res) else "ROUGE", sum(res), len(res)))
EOP
  } > "$F" 2>&1
  cat "$F"
  echo "=== bilan ecrit dans $F (a copier sur le PC et a envoyer)"
  ;;
fin)
  # v2.2 : la mesure n'est PAS relancee au banc (sinon detection, noms et unites du banc gardes chez le client) ;
  # le boitier s'eteint ; il repart seul a la mise sous tension sur le site, avec une detection neuve.
  systemctl stop opti-mpp.timer opti-mpp.service 2>/dev/null
  rm -rf "${D:?}"/* /run/opti061
  sysctl -q -p /etc/sysctl.d/90-opti.conf 2>/dev/null
  systemctl is-enabled opti-mpp.timer >/dev/null 2>&1 || systemctl enable opti-mpp.timer >/dev/null 2>&1
  echo "=== $H - donnees d'essai effacees, marquage BANC retire ; mesure active au prochain demarrage."
  echo "    Le boitier s'eteint dans 10 s : debrancher ensuite, il est pret pour la pose ($(date '+%d/%m %T'))"
  sync; sleep 10; systemctl poweroff
  ;;
*) echo "Usage : sh campagne_v2.sh prepare | suivi | blocage | redemarrage | bilan | fin" ;;
esac
