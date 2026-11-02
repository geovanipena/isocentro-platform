#!/usr/bin/env python3
"""Gera um CSV enriquecido com o quadrante da lesão classificado automaticamente
a partir dos relatórios de tratamento do INTRABEAM (ZEISS).

Para cada linha do CSV de entrada (formato iort4), localiza a subpasta da paciente
pelo número (folder_number), encontra o relatório de tratamento do INTRABEAM
(o PDF com o diagrama "Application Type") e acrescenta a coluna `quadrant_auto`
(QSL / QSM / QIL / QIM / Areolar / Junção), além de `quadrant_auto_obs` com os
detalhes da detecção ou o motivo da falha.

Uso típico (no computador com o Google Drive sincronizado em G:):

    python build_quadrant_csv.py \
        --root "G:/4 - FÍSICA/Fis. Geovani/POPs/INTRABEAM NOVO" \
        --in   iort4.csv \
        --out  iort5.csv

A regra de classificação está em iort_quadrant.py (mantenha os dois arquivos
juntos). Dependências: pandas, pypdf, pdf2image (+ poppler), opencv, Pillow.
"""
import argparse
import os
import re
import sys

import pandas as pd

import iort_quadrant as iq

_LAT = {"direita": "Right", "esquerda": "Left", "dir": "Right", "esq": "Left"}


def leading_number(name):
    """Número inicial do nome da pasta (ex.: '90- Kenia ...' -> 90)."""
    m = re.match(r"\s*(\d+)", str(name))
    return int(m.group(1)) if m else None


def index_folders(root):
    """Mapeia número da pasta -> caminho, varrendo a árvore recursivamente."""
    idx = {}
    for dirpath, dirnames, _ in os.walk(root):
        for d in dirnames:
            n = leading_number(d)
            if n is not None and n not in idx:
                idx[n] = os.path.join(dirpath, d)
    return idx


def _pdf_candidates(folder):
    """PDFs da pasta ordenados por probabilidade de serem o relatório INTRABEAM
    (nome com 'intrabeam'/'rt' e arquivo pequeno vêm primeiro; manuais grandes
    e temporários '~$' são descartados)."""
    cands = []
    for f in os.listdir(folder):
        if f.lower().endswith(".pdf") and not f.startswith("~$"):
            cands.append(os.path.join(folder, f))

    def score(p):
        b = os.path.basename(p).lower()
        sz = os.path.getsize(p)
        s = 0
        if "intrabeam" in b:
            s -= 4
        if re.search(r"(^|[ _-])rt([ _-]|$)", b):
            s -= 2
        if sz < 500_000:        # relatórios de tratamento são pequenos (~100 KB)
            s -= 1
        return (s, sz)

    return sorted(cands, key=score)


def classify_folder(folder, csv_laterality, junction_tol):
    """Tenta classificar o relatório de tratamento da pasta. Devolve (codigo, obs)."""
    cands = _pdf_candidates(folder)
    if not cands:
        return "", "sem PDF na pasta"
    fallback_lat = _LAT.get(str(csv_laterality).strip().lower())
    last_err = "nenhum PDF com diagrama 'Application Type'"
    for p in cands:
        try:
            data = open(p, "rb").read()
        except Exception as e:
            last_err = f"falha ao ler {os.path.basename(p)}: {e}"
            continue
        lat = None
        try:
            lat = iq.read_laterality(data)
        except Exception:
            pass
        lat = lat or fallback_lat
        try:
            r = iq.classify_pdf(data, laterality=lat, junction_tol=junction_tol)
            obs = (f"{r['description']}; mama={r['laterality']}; lesão={r['cross']}; "
                   f"mamilo={r['nipple']}; r_aréola={r['areola_r']}; pdf={os.path.basename(p)}")
            return r["code"], obs
        except Exception as e:
            last_err = f"{e} (em {os.path.basename(p)})"
    return "", f"erro: {last_err}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="Pasta raiz 'INTRABEAM NOVO'.")
    ap.add_argument("--in", dest="inp", required=True, help="CSV de entrada (iort4).")
    ap.add_argument("--out", required=True, help="CSV de saída (iort5).")
    ap.add_argument("--junction-tol", type=float, default=0.5,
                    help="Tolerância (unidades do plano) para 'junção de quadrantes'.")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        sys.exit(f"Pasta raiz não encontrada: {args.root}")

    df = pd.read_csv(args.inp, dtype=str, keep_default_na=False)
    idx = index_folders(args.root)
    print(f"{len(df)} linhas no CSV · {len(idx)} pastas numeradas encontradas em {args.root}")

    codes, obss = [], []
    for _, row in df.iterrows():
        n = leading_number(row.get("folder_number", "")) or leading_number(row.get("folder_name", ""))
        folder = idx.get(n)
        if folder is None:
            codes.append("")
            obss.append("pasta não encontrada")
            continue
        c, o = classify_folder(folder, row.get("laterality", ""), args.junction_tol)
        codes.append(c)
        obss.append(o)
        print(f"  #{n:<4} {row.get('folder_name','')[:38]:38} -> {c or '—'}")

    df["quadrant_auto"] = codes
    df["quadrant_auto_obs"] = obss
    df.to_csv(args.out, index=False)

    ok = sum(1 for c in codes if c)
    print(f"\nConcluído: {ok}/{len(df)} classificados. Saída: {args.out}")
    print("Distribuição:", dict(pd.Series([c for c in codes if c]).value_counts()))


if __name__ == "__main__":
    main()
