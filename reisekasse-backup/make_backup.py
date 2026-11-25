"""Baut aus den exportierten Datenbank-Dokumenten der Reisekasse die Backup-Dateien.

Aufruf: python3 -I make_backup.py <export-ordner> <ziel-ordner> <datum YYYY-MM-DD>
<export-ordner> enthält expenses/*.json (und optional trip/settings.json),
so wie ArtifactData list mit out_dir sie ablegt.
Erzeugt im Ziel-Ordner: reisekasse.json, reisekasse.csv, notion.md
"""
import csv
import glob
import io
import json
import os
import sys

src, dst, stand = sys.argv[1], sys.argv[2], sys.argv[3]

settings = {}
sp = os.path.join(src, "trip", "settings.json")
if os.path.exists(sp):
    settings = json.load(open(sp, encoding="utf-8"))
names = {0: settings.get("a") or "Jannik", 1: settings.get("b") or "Partner·in", 2: "Beide je Hälfte"}
code = settings.get("code") or "THB"
rate_now = settings.get("rate") or 38

rows = []
for f in glob.glob(os.path.join(src, "expenses", "*.json")):
    o = json.load(open(f, encoding="utf-8"))
    o["id"] = os.path.basename(f)[:-5]
    rows.append(o)
rows.sort(key=lambda r: (r.get("date", ""), r.get("createdAt", 0)))

json.dump({"artifact": "https://claude.ai/artifact/66AYdbAHJG4f9fHoyAtmoR", "stand": stand,
           "settings": settings or None, "expenses": rows},
          open(os.path.join(dst, "reisekasse.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def local(r):
    return r["amount"] * (r.get("rate") or rate_now) if r.get("cur") == "EUR" else r["amount"]


def de(n, dec=2):
    s = f"{n:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s[:-3] if dec == 2 and s.endswith(",00") else s


# Saldo wie in der App
owed_to_a, paid, total = 0.0, [0.0, 0.0], 0.0
for r in rows:
    v = local(r)
    if r.get("payer") == 2:
        paid[0] += v / 2; paid[1] += v / 2
        continue
    share = v if r.get("split") == "other" else v / 2
    owed_to_a += share if r.get("payer") == 0 else -share
    if r.get("cat") == "ausgleich":
        continue
    paid[r["payer"]] += v
    total += v
total += sum(local(r) for r in rows if r.get("payer") == 2)

if abs(owed_to_a) < 0.5:
    saldo = "Ihr seid quitt."
else:
    cred = 0 if owed_to_a > 0 else 1
    saldo = f"{names[1 - cred]} gibt {names[cred]} {de(abs(owed_to_a))} {code} (≈ {de(abs(owed_to_a) / rate_now)} €)"

head = ["Datum", "Was", "Betrag", "Währung", "Kurs", "Bezahlt von", "Aufteilung", "Kategorie", "ID"]


def cells(r):
    return [r.get("date", ""), r.get("note", ""), de(r["amount"]), "EUR" if r.get("cur") == "EUR" else code,
            str(r.get("rate", "")), names.get(r.get("payer"), str(r.get("payer"))),
            "nur für den anderen" if r.get("split") == "other" else "50/50", r.get("cat", ""), r["id"]]


out = io.StringIO()
w = csv.writer(out, delimiter=";")
w.writerow(head)
for r in rows:
    w.writerow(cells(r))
open(os.path.join(dst, "reisekasse.csv"), "w", encoding="utf-8-sig").write(out.getvalue())


def esc(s):
    return str(s).replace("\\", "\\\\").replace("|", "\\|").replace("<", "&lt;").replace("\n", " ")


md = [f"Stand: <date start=\"{stand}\" />  ·  {len(rows)} Einträge  ·  Quelle: [Reisekasse-App](https://claude.ai/artifact/66AYdbAHJG4f9fHoyAtmoR)", "",
      f"**Saldo:** {esc(saldo)}  ",
      f"**Bezahlt:** {esc(names[0])} {de(paid[0])} {code} · {esc(names[1])} {de(paid[1])} {code} · gesamt {de(total)} {code}", "",
      "Wird täglich automatisch überschrieben. Ältere Stände: Seitenverlauf in Notion oder die Git-Historie im Projekt mein-erstes-projekt.", "",
      "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
for r in rows:
    md.append("| " + " | ".join(esc(c) for c in cells(r)) + " |")
open(os.path.join(dst, "notion.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print(len(rows), "Einträge;", saldo)
