"""Copia para Markdown só as páginas TÉCNICAS de um PPR em PDF.

Uso: python extrair_ppr_pdf.py <ppr.pdf> <clinica> <páginas, ex. 34-38,52-55> <raiz isocentro>
Saída: conhecimento/servico/<clinica>-ppr.md, com <!-- p. N --> por página.
As páginas são escolhidas à mão (anexos E, F, G, J e "Testes e Tolerâncias"),
para que IOEs, ASOs e responsáveis (dados pessoais) nunca entrem.
"""
import os, re, sys

import pymupdf4llm

sys.stdout.reconfigure(encoding="utf-8")


def paginas(spec):
    out = []
    for parte in spec.split(","):
        a, _, b = parte.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def main():
    pdf, clinica, spec, raiz = sys.argv[1:5]
    pgs = paginas(spec)
    chunks = pymupdf4llm.to_markdown(pdf, pages=[p - 1 for p in pgs], page_chunks=True, show_progress=False)
    corpo = []
    for p, c in zip(pgs, chunks):
        t = re.sub(r"(?i)<mark>.*?</mark>|docusign envelope id:?\s*\S*", "", c["text"])
        corpo.append(f"<!-- p. {p} -->\n\n{t.strip()}\n")
    out = os.path.join(os.path.abspath(raiz), "conhecimento", "servico", f"{clinica}-ppr.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("---\n" f"clinica: {clinica}\n" f'fonte: "{os.path.basename(pdf)}"\n'
                f'paginas: "{spec}"\n' "gerado_por: scripts/extrair_ppr_pdf.py\n---\n\n"
                f"# PPR {clinica}: páginas técnicas\n\n" + "\n".join(corpo))
    print("ok", out)


if __name__ == "__main__":
    main()
