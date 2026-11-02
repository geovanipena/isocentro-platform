"""Extrai as tabelas de artigos JATS XML (Europe PMC) para CSV, uma linha por linha de tabela."""
import csv, sys, re, xml.etree.ElementTree as ET
from pathlib import Path

def txt(e):
    return re.sub(r"\s+", " ", "".join(e.itertext())).strip() if e is not None else ""

def grid(table):
    rows, spans = [], {}
    for tr in table.iter("tr"):
        row, c = [], 0
        cells = [x for x in tr if x.tag in ("td", "th")]
        it = iter(cells)
        while True:
            while (len(rows), c) in spans:
                row.append(spans.pop((len(rows), c))); c += 1
            cell = next(it, None)
            if cell is None:
                break
            v = txt(cell); rs = int(cell.get("rowspan", 1)); cs = int(cell.get("colspan", 1))
            for k in range(cs):
                row.append(v)
                for r in range(1, rs):
                    spans[(len(rows) + r, c + k)] = v
            c += cs
        rows.append(row)
    return rows

out = csv.writer(open(sys.argv[2], "w", newline="", encoding="utf-8"), delimiter=";")
out.writerow(["doc", "tabela", "titulo", "linha", "celulas", "notas"])
for f in sys.argv[1].split(","):
    root = ET.parse(f).getroot(); doc = Path(f).stem
    for tw in root.iter("table-wrap"):
        lab, cap = txt(tw.find("label")), txt(tw.find("caption"))
        notes = " | ".join(txt(x) for x in tw.iter("fn"))
        t = tw.find(".//table")
        if t is None:
            continue
        for i, r in enumerate(grid(t)):
            out.writerow([doc, lab, cap[:300], i, " ¦ ".join(r), notes[:1500] if i == 0 else ""])
