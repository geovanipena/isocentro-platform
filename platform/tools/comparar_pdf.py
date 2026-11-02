#!/usr/bin/env python
"""Compara dois PDF por texto E posição, e imprime só o que DIFERE.

Por que existe: a regra do projeto é "conferir medindo, não lendo" — para
mudança no papel, gerar os dois PDF e comparar. Só que a comparação era feita a
olho, folha contra folha, e olho não vê célula que andou 3 pontos nem valor que
mudou de 92,3 para 91,8 no meio de uma tabela cheia. Reler o `ficha_pdf.py`
(3,5 mil linhas) para deduzir o efeito custa ~40 mil tokens e ainda não
responde: o que responde é o PDF gerado.

    python tools/caso.py TC8 -o antes.pdf      # antes da mudança
    python tools/caso.py TC8 -o depois.pdf     # depois
    python tools/comparar_pdf.py antes.pdf depois.pdf

Imprime as células que **mudaram de texto**, as que **andaram de lugar**, as que
**sumiram** e as que **surgiram** — e conta, sem listar, as que ficaram
idênticas. A saída é pensada para caber no contexto: célula igual não vira linha.

Código de saída: 0 se os dois PDF dizem a mesma coisa, 1 se diferem, 2 em erro.
Assim a ferramenta também serve dentro de script.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - depende da estação
    fitz = None


@dataclass(frozen=True)
class Celula:
    """Uma linha de texto desenhada no PDF, com o lugar onde ela ficou."""

    pagina: int
    x: float
    y: float
    texto: str


def _celulas(caminho: Path, so_pagina: int | None) -> tuple[list[Celula], list[str]]:
    """Extrai as células e o tamanho de cada página.

    Agrupa por (bloco, linha) do PyMuPDF em vez de por palavra: o veredito útil
    é "esta célula mudou", não "esta palavra mudou". Um ``drawString`` do
    reportlab vira um bloco, então o agrupamento casa com o que o
    ``ficha_pdf.py`` escreve — e a diferença sai na unidade em que a mudança foi
    pensada.
    """
    celulas: list[Celula] = []
    paginas: list[str] = []
    with fitz.open(caminho) as doc:
        for n, pagina in enumerate(doc, start=1):
            r = pagina.rect
            paginas.append(f"{r.width:.0f}x{r.height:.0f}")
            if so_pagina is not None and n != so_pagina:
                continue
            agrupadas: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
            for x0, y0, _x1, _y1, palavra, bloco, linha, _n in pagina.get_text("words"):
                agrupadas.setdefault((bloco, linha), []).append((x0, y0, palavra))
            for partes in agrupadas.values():
                partes.sort(key=lambda p: p[0])
                celulas.append(Celula(
                    pagina=n,
                    x=min(p[0] for p in partes),
                    y=min(p[1] for p in partes),
                    texto=" ".join(p[2] for p in partes),
                ))
    celulas.sort(key=lambda c: (c.pagina, round(c.y, 1), round(c.x, 1)))
    return celulas, paginas


def _perto(a: Celula, b: Celula, tol: float) -> bool:
    return abs(a.x - b.x) <= tol and abs(a.y - b.y) <= tol


def comparar(antes: list[Celula], depois: list[Celula], tol: float):
    """Devolve (iguais, mudou, moveu, sumiu, surgiu).

    Em quatro passadas, da mais forte para a mais fraca, porque a ordem é o que
    dá o diagnóstico certo: casar primeiro por posição faria uma célula que
    ANDOU aparecer como duas — uma que sumiu e uma que surgiu — e o
    deslocamento, que é a mudança real, se perderia entre duas linhas de ruído.
    """
    livres = list(range(len(depois)))
    iguais = 0
    mudou: list[tuple[Celula, Celula]] = []
    moveu: list[tuple[Celula, Celula]] = []
    sumiu: list[Celula] = []

    # 1) mesmo texto no mesmo lugar: é o caso comum, e não vira saída nenhuma.
    pendentes: list[Celula] = []
    for a in antes:
        achou = next(
            (i for i in livres
             if depois[i].texto == a.texto and depois[i].pagina == a.pagina
             and _perto(a, depois[i], tol)),
            None,
        )
        if achou is None:
            pendentes.append(a)
        else:
            livres.remove(achou)
            iguais += 1

    # 2) mesmo texto, outro lugar: andou. Pega o MAIS PRÓXIMO — senão uma
    #    célula repetida na página ("Gy", "cm") casaria com a primeira homônima
    #    e o deslocamento relatado seria de outra célula.
    ainda: list[Celula] = []
    for a in pendentes:
        candidatos = [i for i in livres
                      if depois[i].texto == a.texto and depois[i].pagina == a.pagina]
        if not candidatos:
            ainda.append(a)
            continue
        achou = min(candidatos,
                    key=lambda i: abs(depois[i].x - a.x) + abs(depois[i].y - a.y))
        livres.remove(achou)
        moveu.append((a, depois[achou]))

    # 3) mesmo lugar, outro texto: mudou o conteúdo da célula.
    for a in ainda:
        achou = next(
            (i for i in livres
             if depois[i].pagina == a.pagina and _perto(a, depois[i], tol)),
            None,
        )
        if achou is None:
            sumiu.append(a)
        else:
            livres.remove(achou)
            mudou.append((a, depois[achou]))

    surgiu = [depois[i] for i in livres]
    return iguais, mudou, moveu, sumiu, surgiu


def _curto(texto: str, largura: int) -> str:
    texto = texto.strip()
    return texto if len(texto) <= largura else texto[: largura - 1] + "…"


def _pos(c: Celula) -> str:
    return f"({c.x:6.1f},{c.y:6.1f})"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("antes", type=Path)
    p.add_argument("depois", type=Path)
    p.add_argument("--tol", type=float, default=1.0, metavar="PT",
                   help="tolerância de posição em pontos (padrão: 1,0)")
    p.add_argument("--pagina", type=int, metavar="N",
                   help="compara só a página N")
    p.add_argument("--max", type=int, default=120, metavar="N",
                   help="teto de linhas impressas (padrão: 120)")
    p.add_argument("--largura", type=int, default=52, metavar="N",
                   help="corte do texto de cada célula (padrão: 52)")
    args = p.parse_args(argv)

    if fitz is None:
        print("PyMuPDF não está instalado nesta estação: pip install pymupdf",
              file=sys.stderr)
        return 2
    for caminho in (args.antes, args.depois):
        if not caminho.is_file():
            print(f"não achei {caminho}", file=sys.stderr)
            return 2

    try:
        antes, paginas_a = _celulas(args.antes, args.pagina)
        depois, paginas_b = _celulas(args.depois, args.pagina)
    except Exception as erro:  # PDF truncado, protegido por senha, não-PDF
        print(f"não consegui ler: {erro}", file=sys.stderr)
        return 2

    iguais, mudou, moveu, sumiu, surgiu = comparar(antes, depois, args.tol)
    total = len(mudou) + len(moveu) + len(sumiu) + len(surgiu)

    print(f"{args.antes.name} -> {args.depois.name}")
    if paginas_a != paginas_b:
        # Página a mais, a menos ou de outro tamanho muda o documento inteiro.
        # A comparação é página a página (célula da p2 não casa com a da p3),
        # então tudo o que andou de página cai como "sumiu + surgiu" — medido
        # com a ficha do TC8 em modo individual contra a mesma em modo soma:
        # 208 sumiram e 202 surgiram, e nenhuma delas era mudança de verdade.
        print(f"  ATENÇÃO  páginas {len(paginas_a)} ({', '.join(paginas_a)}) -> "
              f"{len(paginas_b)} ({', '.join(paginas_b)}). O conteúdo mudou de "
              "página: a lista abaixo vira sumiu+surgiu em bloco, e o que vale "
              "olhar é a contagem, não cada linha.")
    print(f"  {iguais} célula(s) idêntica(s) · {len(mudou)} mudou · "
          f"{len(moveu)} moveu · {len(sumiu)} sumiu · {len(surgiu)} surgiu")

    if not total:
        print("  os dois PDF dizem a mesma coisa nos mesmos lugares.")
        return 0

    linhas: list[tuple[int, float, float, str]] = []
    for a, b in mudou:
        linhas.append((a.pagina, a.y, a.x,
                       f"MUDOU  {_pos(a)}  {_curto(a.texto, args.largura)!r}"
                       f" -> {_curto(b.texto, args.largura)!r}"))
    for a, b in moveu:
        linhas.append((a.pagina, a.y, a.x,
                       f"MOVEU  {_pos(a)} -> {_pos(b)}  "
                       f"(dx {b.x - a.x:+.1f} dy {b.y - a.y:+.1f})  "
                       f"{_curto(a.texto, args.largura)!r}"))
    for c in sumiu:
        linhas.append((c.pagina, c.y, c.x,
                       f"SUMIU  {_pos(c)}  {_curto(c.texto, args.largura)!r}"))
    for c in surgiu:
        linhas.append((c.pagina, c.y, c.x,
                       f"SURGIU {_pos(c)}  {_curto(c.texto, args.largura)!r}"))
    linhas.sort()

    print()
    for pagina, _y, _x, texto in linhas[: args.max]:
        print(f"  p{pagina}  {texto}")
    if len(linhas) > args.max:
        # Saída longa é justamente o custo que esta ferramenta existe para
        # evitar: corta e DIZ que cortou, em vez de despejar no contexto.
        print(f"  …e mais {len(linhas) - args.max} diferença(s) "
              "(subir com --max, ou uma página por vez com --pagina)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
