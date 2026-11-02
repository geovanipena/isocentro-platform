"""Camada 1 dos manuais: PDF de manuais/ em texto integral Markdown.

Uso: python converter_manuais.py <raiz isocentro>
Saída: conhecimento/texto/manuais/<Fabricante>/<Produto>/<nome do arquivo>.md, com o mesmo
cabeçalho e os mesmos marcadores <!-- p. N --> de converter_referencias.py.
Fica de fora: .pptx de treinamento (centenas de MB de imagem), HTML da documentação da ESAPI
(site navegável) e os programas da pasta srvariadb. Relatório em texto/manuais/_relatorio.csv.
"""
import csv, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import converter_referencias as cr  # noqa: E402

R = os.path.abspath(sys.argv[1])
ORIG = os.path.join(R, "manuais")
DEST = os.path.join(R, "conhecimento", "texto", "manuais")


def main():
    rel = []
    for raiz, pastas, arqs in os.walk(ORIG):
        pastas[:] = [p for p in pastas if "documentacao oficial" not in p and not p.startswith("DataLineage")]
        for arq in sorted(arqs):
            if not arq.lower().endswith(".pdf"):
                continue
            src = os.path.join(raiz, arq)
            sub = os.path.relpath(raiz, ORIG)
            out = os.path.join(DEST, sub, os.path.splitext(arq)[0] + ".md")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src):
                rel.append([sub, arq, "inalterado"])
                continue
            try:
                corpo, info = cr.pdf(src)
                if cr.ilegivel(corpo, info):
                    corpo, info = cr.pdf_ocr(src)
                titulo = os.path.splitext(arq)[0].replace('"', "'")
                cab = ["---", f'manual: "{titulo}"', f'pasta: "{sub}"',
                       f'origem: "manuais/{sub.replace(os.sep, "/")}/{arq}"']
                cab += [f"{k}: {v}" for k, v in info.items()]
                with open(out, "w", encoding="utf-8", newline="\n") as f:
                    f.write("\n".join(cab + ["---", "", f"# {titulo}", ""]) + corpo)
                rel.append([sub, arq, "ok (OCR)" if info.get("ocr") else "ok", info["paginas"]])
            except Exception as e:
                rel.append([sub, arq, f"ERRO: {e}"[:200]])
            print(rel[-1], flush=True)
    with open(os.path.join(DEST, "_relatorio.csv"), "w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=";").writerows([["pasta", "arquivo", "status", "paginas"]] + rel)


if __name__ == "__main__":
    main()
