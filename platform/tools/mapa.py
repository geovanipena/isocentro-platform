#!/usr/bin/env python
"""Esqueleto de um arquivo .py: classes, métodos e onde cada um começa e acaba.

Por que existe: `gui.py` tem 9 mil linhas e `ficha_pdf.py` tem 3,5 mil. Abrir o
arquivo inteiro para achar um método é caro — e quem lê (pessoa ou agente)
precisa de DUAS coisas antes de abrir: o nome do método e o intervalo de
linhas. Com isso, a leitura seguinte é de 40 linhas em vez de 9 mil.

    python tools/mapa.py gui.py                 # só as classes e o tamanho
    python tools/mapa.py gui.py --metodos       # com os métodos de cada uma
    python tools/mapa.py gui.py --buscar capa   # só o que casa com "capa"

Não substitui ler o código: substitui ler o código INTEIRO para descobrir onde
ele está.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent


def _achar(pedido: Path) -> Path | None:
    """O arquivo, aceitando o NOME SOLTO além do caminho completo.

    Em 09/09/2026 os módulos saíram da raiz para o pacote ``isocentro``, e
    o `mapa.py gui.py` do CLAUDE.md — o comando que existe para NÃO se abrir um
    arquivo de 9 mil linhas — passou a responder "não achei". Exigir
    `isocentro/interface/gui.py` seria trocar o custo que a ferramenta
    economiza (contexto) por outro: saber de cabeça em que subpacote cada um
    dos 60 módulos foi parar.

    Nome ambíguo não é adivinhado: a ferramenta lista os candidatos e devolve
    None. Mapear o arquivo errado é pior que não mapear nenhum — o intervalo de
    linhas sairia certo para um arquivo que não é o da vez.
    """
    if pedido.is_file():
        return pedido
    if pedido.parent != Path("."):
        return None
    achados = [p for p in RAIZ.rglob(pedido.name)
               if p.is_file() and not set(p.parts) & {".venv", "build", "dist",
                                                      "__pycache__", ".git"}]
    if len(achados) == 1:
        return achados[0]
    if len(achados) > 1:
        print(f"{pedido.name} existe em {len(achados)} lugares:", file=sys.stderr)
        for p in sorted(achados):
            print(f"   {p.relative_to(RAIZ).as_posix()}", file=sys.stderr)
    return None


def _linha(nome: str, no: ast.AST, recuo: str = "") -> str:
    tamanho = no.end_lineno - no.lineno + 1
    return f"{recuo}{nome:<44} {no.lineno:>5}-{no.end_lineno:<5} ({tamanho:>4} linhas)"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("arquivo", type=Path)
    p.add_argument("--metodos", action="store_true",
                   help="lista também os métodos de cada classe")
    p.add_argument("--buscar", metavar="TEXTO",
                   help="mostra só nomes que contenham TEXTO (sem acento/caixa)")
    args = p.parse_args()

    alvo = _achar(args.arquivo)
    if alvo is None:
        print(f"não achei {args.arquivo}", file=sys.stderr)
        return 1
    if alvo != args.arquivo:
        print(f"# {alvo.as_posix()}", file=sys.stderr)

    # utf-8-sig porque posicionamento.py tem BOM — o utf-8 puro deixaria um
    # ﻿ no começo e o ast.parse falharia num arquivo perfeitamente válido.
    fonte = alvo.read_text(encoding="utf-8-sig")
    arvore = ast.parse(fonte)
    alvo = args.buscar.lower() if args.buscar else None

    print(f"{args.arquivo}: {fonte.count(chr(10)) + 1} linhas\n")

    for no in arvore.body:
        if isinstance(no, ast.ClassDef):
            metodos = [m for m in no.body
                       if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
            casa_classe = alvo is None or alvo in no.name.lower()
            filhos = [m for m in metodos
                      if alvo is None or alvo in m.name.lower() or casa_classe]
            # Com filtro ligado, classe sem nenhum acerto nem aparece: a lista
            # curta é o produto todo desta ferramenta.
            if alvo is not None and not casa_classe and not filhos:
                continue
            print(_linha(f"class {no.name}", no))
            if args.metodos:
                for m in filhos:
                    print(_linha(f".{m.name}", m, recuo="    "))
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if alvo is not None and alvo not in no.name.lower():
                continue
            print(_linha(f"def {no.name}", no))

    return 0


if __name__ == "__main__":
    sys.exit(main())
