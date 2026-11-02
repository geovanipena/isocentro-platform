"""Camada 1: converte referencias/ (PDF, DOC, MD) em texto integral Markdown.

Uso: python converter_referencias.py <raiz isocentro>
Saída: conhecimento/texto/<pasta temática>/<CÓDIGO>.md, com cabeçalho YAML e
marcadores <!-- p. N --> para citar página. Gera texto/_relatorio.csv com
páginas, caracteres e alerta de PDF digitalizado (pouco texto por página).
Não sobrescreve arquivo cujo PDF de origem não mudou (compara mtime).
"""
import csv, os, re, subprocess, sys

import pymupdf4llm

sys.stdout.reconfigure(encoding="utf-8")

R = os.path.abspath(sys.argv[1])
ORIG = os.path.join(R, "referencias")
DEST = os.path.join(R, "conhecimento", "texto")
SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.exe"
POUCO_TEXTO = 200  # caracteres por página abaixo disso = provável imagem


# Documentos internos do serviço saíram de referencias/ (P6, 22/10/2026), mas o texto
# continua em texto/10 POPs CLINICA/, que é onde as fichas e o Mapa os procuram.
EXTRAS = [("10 POPs CLINICA", os.path.join(R, "servico", "pops"), "servico/pops")]


def cabecalho(cod, tit, pasta, arq, extra, origem):
    linhas = ["---", f"codigo: {cod}", f'titulo: "{tit}"', f'pasta: "{pasta}"',
              f'origem: "{origem}/{arq}"']
    linhas += [f"{k}: {v}" for k, v in extra.items()]
    return "\n".join(linhas + ["---", "", f"# {cod} — {tit}", ""])


def limpar(t):
    t = t.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)        # hifenização no fim da linha
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def pdf(caminho):
    """pymupdf4llm: reflui colunas, descarta marca d'água lateral e gera tabelas Markdown.
    Atenção: símbolos de fontes sem mapa Unicode (±, γ) podem sair como � ou letra latina;
    valor numérico citado em ficha deve ser conferido na imagem da página."""
    pags = pymupdf4llm.to_markdown(caminho, page_chunks=True, show_progress=False)
    partes, vazias = [], 0
    for i, c in enumerate(pags, 1):
        t = limpar(c["text"])
        if len(t) < POUCO_TEXTO:
            vazias += 1
        partes.append(f"<!-- p. {i} -->\n\n{t}\n")
    return "\n".join(partes), {"paginas": len(pags), "paginas_sem_texto": vazias}


def pdf_ocr(caminho):
    """OCR nativo do Windows (pt-BR), para PDF digitalizado ou com fonte sem mapa
    Unicode (texto extraído vira �). Tabelas perdem a ordem das colunas."""
    import pymupdf, winocr
    from PIL import Image
    doc = pymupdf.open(caminho)
    partes, vazias = [], 0
    for i, pg in enumerate(doc, 1):
        pix = pg.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        t = limpar("\n".join(l["text"] for l in winocr.recognize_pil_sync(img, "pt-BR")["lines"]))
        if len(t) < POUCO_TEXTO:
            vazias += 1
        partes.append(f"<!-- p. {i} -->\n\n{t}\n")
    return "\n".join(partes), {"paginas": len(doc), "paginas_sem_texto": vazias, "ocr": True}


def ilegivel(corpo, info):
    return corpo.count("�") > 0.05 * max(len(corpo), 1) or info["paginas_sem_texto"] > info["paginas"] / 2


def doc_word(caminho):
    """.doc antigo: LibreOffice headless, salvando como texto UTF-8."""
    tmpdir = os.path.join(DEST, "_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    subprocess.run([SOFFICE, "--headless", "--convert-to", "txt:Text (encoded):UTF8",
                    "--outdir", tmpdir, caminho], check=True, capture_output=True, timeout=180)
    tmp = os.path.join(tmpdir, os.path.splitext(os.path.basename(caminho))[0] + ".txt")
    with open(tmp, encoding="utf-8-sig", errors="replace") as f:
        t = limpar(f.read().replace("\r", "\n"))
    os.remove(tmp)
    return t + "\n", {"paginas": "", "paginas_sem_texto": 0}


def main():
    os.makedirs(DEST, exist_ok=True)
    rel = []
    fontes = [(p, os.path.join(ORIG, p), f"referencias/{p}") for p in sorted(os.listdir(ORIG))
              if os.path.isdir(os.path.join(ORIG, p)) and not p.startswith("_")]
    fontes += [x for x in EXTRAS if os.path.isdir(x[1])]
    for pasta, cam, origem in fontes:
        os.makedirs(os.path.join(DEST, pasta), exist_ok=True)
        for arq in sorted(os.listdir(cam)):
            base, ext = os.path.splitext(arq)
            ext = ext.lower()
            if ext not in (".pdf", ".doc", ".docx", ".md"):
                continue
            m = re.match(r"(.+?) - (.+)$", base)
            cod, tit = (m.group(1), m.group(2)) if m else (base, base)
            src = os.path.join(cam, arq)
            out = os.path.join(DEST, pasta, f"{cod}.md")
            if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src):
                with open(out, encoding="utf-8") as f:
                    t = f.read()
                cab = dict(re.findall(r"(?m)^(paginas|digitalizado|ocr): ?(.*)$", t.split("\n---\n", 1)[0]))
                rel.append([pasta, cod, ext, "ok (OCR)" if cab.get("ocr") == "True" else "ok",
                            cab.get("paginas", ""), len(t), cab.get("digitalizado", "")])
                continue
            try:
                if ext == ".pdf":
                    corpo, info = pdf(src)
                    if ilegivel(corpo, info):
                        corpo, info = pdf_ocr(src)
                elif ext == ".md":
                    with open(src, encoding="utf-8") as f:
                        corpo, info = f.read(), {"paginas": "", "paginas_sem_texto": 0}
                else:
                    corpo, info = doc_word(src)
                info["digitalizado"] = bool(info["paginas"]) and info["paginas_sem_texto"] > info["paginas"] / 2
                with open(out, "w", encoding="utf-8", newline="\n") as f:
                    f.write(cabecalho(cod, tit.replace('"', "'"), pasta, arq, info, origem) + corpo)
                rel.append([pasta, cod, ext, "ok", info["paginas"], len(corpo), info["digitalizado"]])
            except Exception as e:  # registra e segue
                rel.append([pasta, cod, ext, f"ERRO: {e}".replace("\n", " ")[:200], "", "", ""])
            print(rel[-1][:4], flush=True)
    with open(os.path.join(DEST, "_relatorio.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["pasta", "codigo", "ext", "status", "paginas", "caracteres", "digitalizado"])
        w.writerows(rel)


if __name__ == "__main__":
    main()
