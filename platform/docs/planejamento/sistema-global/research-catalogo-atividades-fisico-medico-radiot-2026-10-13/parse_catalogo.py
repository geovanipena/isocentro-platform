"""Extrai as tabelas multilinha do pandoc do relatório do catálogo para CSV.

Uso: python -I parse_catalogo.py <relatorio.md> <saida_dir>
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

src = Path(sys.argv[1])
out = Path(sys.argv[2])
lines = src.read_text(encoding="utf-8").splitlines()

SEP = re.compile(r"^\s*-{3,}(\s+-{3,})+\s*$")   # linha de colunas
FRAME = re.compile(r"^\s*-{10,}\s*$")            # borda da tabela


def spans(sep_line):
    return [(m.start(), m.end()) for m in re.finditer(r"-+", sep_line)]


def cut(line, cols):
    cells = []
    for i, (a, _) in enumerate(cols):
        b = cols[i + 1][0] if i + 1 < len(cols) else len(line)
        cells.append(line[a:b].strip() if a < len(line) else "")
    return cells


def tables(start, end):
    """Devolve (titulo_secao, header, rows) para cada tabela em [start, end)."""
    i, section = start, ""
    while i < end:
        ln = lines[i]
        if ln.startswith("### "):
            section = ln[4:].strip()
        if FRAME.match(ln):
            # cabeçalho até a linha SEP
            j = i + 1
            head_lines = []
            while j < end and not SEP.match(lines[j]):
                head_lines.append(lines[j]); j += 1
            if j >= end:
                break
            cols = spans(lines[j])
            header = [" ".join(p for p in parts if p) for parts in
                      zip(*[cut(h, cols) for h in head_lines])] if head_lines else []
            rows, cur = [], []
            k = j + 1
            while k < end and not FRAME.match(lines[k]):
                if lines[k].strip() == "":
                    if cur: rows.append(cur); cur = []
                else:
                    cur.append(cut(lines[k], cols))
                k += 1
            if cur: rows.append(cur)
            merged = [[" ".join(c for c in col if c).replace("- ", "-") if False else
                       " ".join(c for c in col if c) for col in zip(*r)] for r in rows]
            yield section, header, merged
            i = k + 1
            continue
        i += 1


def idx(prefix):
    return next(n for n, l in enumerate(lines) if l.startswith(prefix))


cat_a, cat_b = idx("## 2."), idx("## 3.")
doc_a, doc_b = idx("## 4."), idx("## 5.")
conf_a = cat_b

fields = ["id", "area", "secao", "atividade", "gatilho_periodicidade", "nivel",
          "documento_item", "executa_aprova", "evidencia_guarda", "colunas_originais"]
out_rows, problems = [], []
for section, header, rows in tables(cat_a, cat_b):
    for r in rows:
        rid = r[0]
        if not re.match(r"^[A-H]\d{2}$", rid):
            problems.append(f"{section}: linha sem ID reconhecível: {r[:2]}")
            continue
        get = lambda n: r[n] if n < len(r) else ""
        out_rows.append({
            "id": rid, "area": rid[0], "secao": section, "atividade": get(1),
            "gatilho_periodicidade": get(2), "nivel": get(3), "documento_item": get(4),
            "executa_aprova": get(5), "evidencia_guarda": " | ".join(r[6:]),
            "colunas_originais": " / ".join(header),
        })

out.mkdir(parents=True, exist_ok=True)
with open(out / "catalogo-extraido.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
    w.writeheader(); w.writerows(out_rows)

doc_tables = list(tables(doc_a, doc_b))
conf_tables = list(tables(conf_a, doc_a))
with open(out / "documentos-e-conflitos.md", "w", encoding="utf-8") as f:
    for title, tbls in (("Conflitos entre fontes (seção 3)", conf_tables),
                        ("Documentos e vigência (seção 4)", doc_tables)):
        f.write(f"# {title}\n\nExtraído verbatim de imports/{src.name}.\n\n")
        for _, header, rows in tbls:
            f.write("| " + " | ".join(header) + " |\n")
            f.write("|" + " --- |" * len(header) + "\n")
            for r in rows:
                f.write("| " + " | ".join(c.replace("|", "/") for c in r) + " |\n")
            f.write("\n")

por_area = Counter(r["area"] for r in out_rows)
por_nivel = Counter(r["nivel"] for r in out_rows)
nao_verif = [r["id"] for r in out_rows
             if re.search(r"n[ãa]o (verificad|confirmad|localizad|definid)", " ".join(r.values()), re.I)]
with open(out / "resumo-extracao.md", "w", encoding="utf-8") as f:
    f.write("# Resumo da extração do catálogo\n\n")
    f.write(f"Total de atividades: {len(out_rows)}\n\n## Por área\n\n")
    for a in "ABCDEFGH":
        f.write(f"- {a}: {por_area.get(a, 0)}\n")
    f.write("\n## Por nível (como escrito no relatório)\n\n")
    for k, v in por_nivel.most_common():
        f.write(f"- {k}: {v}\n")
    f.write("\n## Linhas com 'não verificado/confirmado/localizado/definido'\n\n")
    f.write(", ".join(nao_verif) + "\n")
    f.write("\n## Problemas de leitura\n\n" + ("\n".join(f"- {p}" for p in problems) or "nenhum") + "\n")

print(len(out_rows), dict(por_area), dict(por_nivel), len(problems), sep="\n")
