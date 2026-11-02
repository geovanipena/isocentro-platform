"""Confere se teste e limite de cada item aparecem literalmente no texto da fonte (normalizando espaços e hífens)."""
import csv, re, sys, xml.etree.ElementTree as ET
from pathlib import Path
pdfs = Path(sys.argv[2]); S = Path(sys.argv[3])
def norm(s):
    s = re.sub(r"[‐-―−]", "-", s)
    s = re.sub(r"[±×�°]|(?<=\d) o", "?", s)
    return re.sub(r"\s+", " ", s).strip().lower()
src = {}
for d in ["MPPG8b", "MPPG2b", "MPPG5b", "MPPG9b", "MPPG11a"]:
    src[d] = norm(" ".join(ET.parse(pdfs / f"{d}.xml").getroot().itertext()))
src["TRS"] = norm(open(S / "trs398.txt", encoding="utf-8", errors="replace").read())
src["TEC"] = norm(open(S / "tecdoc1274.txt", encoding="utf-8", errors="replace").read())
src["TG51"] = norm(open(S / "tg51add.txt", encoding="utf-8", errors="replace").read())
key = {"AAPM MPPG 8.b": "MPPG8b", "AAPM MPPG 2.b": "MPPG2b", "AAPM MPPG 5.b": "MPPG5b", "AAPM-RSS MPPG 9.b": "MPPG9b",
       "AAPM MPPG 11.a": "MPPG11a", "IAEA TRS-398 Rev. 1": "TRS", "IAEA TECDOC-1274": "TEC"}
ok = falta = pulado = 0; out = []
for x in csv.DictReader(open(sys.argv[1], encoding="utf-8-sig"), delimiter=";"):
    k = key.get(x["protocolo"], "TG51" if "TG-51" in x["protocolo"] else None)
    lim = x["limite"]
    if lim in ("—", "Verificado/conforme") or lim.startswith("ver Table") or "[≥]" in lim or "(isocêntrico" in lim:
        pulado += 1; continue
    partes = [p for p in re.split(r";\s*|\s\(", lim) if len(p) > 3]
    miss = [p for p in partes if norm(p.rstrip(")")) not in src[k]]
    if miss: falta += 1; out.append((x["item_id"], x["protocolo"], lim[:80], miss[:2]))
    else: ok += 1
sys.stdout.reconfigure(encoding="utf-8")
print(f"limite encontrado literal: {ok}; não encontrado: {falta}; sem limite numérico: {pulado}")
for o in out: print(*o)
