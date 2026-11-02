#!/usr/bin/env python
"""Regressão do PAPEL: a ficha de hoje contra a ficha aprovada, célula a célula.

Por que existe (22/10/2026): o `CLAUDE.md` manda "documento impresso muda com
aviso", e o aviso dependia de alguém lembrar de rodar o `tools/caso.py` e o
`tools/comparar_pdf.py` antes e depois. A suíte confere que cada função
devolve o que o teste espera; nenhum teste conferia que a ficha INTEIRA — 214
células no TC8 — continua dizendo a mesma coisa. Uma mudança no `dominio/` que
desloca uma dose passava verde.

A referência é o TEXTO e a POSIÇÃO de cada célula, em JSON, e não o PDF: JSON
se lê no diff do commit (é ali que o aviso ao usuário fica registrado) e passa
pelo `tools/varrer_identidade.py`. Os casos vêm de `../../dicom-teste/`, o
acervo PSEUDONIMIZADO — nunca do `TCs_Teste/`, que tem o paciente real.

    python tools/regressao_papel.py              # confere todos (saída 1 se o papel mudou)
    python tools/regressao_papel.py --gravar     # aceita o papel de hoje como referência
    python tools/regressao_papel.py --gravar TC8 # só um caso

`--gravar` é a decisão "o papel mudou DE PROPÓSITO": o diff do JSON vai no
commit e é o que se mostra ao usuário.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

import comparar_pdf  # noqa: E402

ACERVO = RAIZ.parents[1] / "dicom-teste"
REFERENCIAS = RAIZ / "tests" / "papel_referencia"

# (caso, modo). Um de cada família que o papel trata diferente: o TC8 é
# 600CD/6EX (mesa série C, folha de portais) e sai nos dois modos de corte; o
# TC6 é hipofracionamento (o popup de dose alta, respondido pelo `caso.py`); o
# Elekta é o DICOM do Monaco (sem File Meta, dose por feixe, mesa como ROI).
CASOS = (
    ("TC8", "individual"),
    ("TC8", "soma"),
    ("TC6", "individual"),
    ("Elekta", "individual"),
)

# Posição em pontos: o reportlab escreve no mesmo lugar ao centésimo, e uma
# célula que andou meio ponto já é mudança de layout que alguém fez.
TOLERANCIA = 0.5

# Um caso por vez. Com os quatro em paralelo, a suíte reprovou em 22/10/2026
# por falta de memória ("Unable to allocate 1.00 MiB" dentro do caso.py): os
# picos medidos são 0,8 GB (TC8), 2,5 GB (TC6) e 3,6 GB (Elekta), e somados
# passam dos 7,9 GB desta estação. Com dois, o Elekta e o TC6 ainda se
# encontram. Em série custa ~56 s em vez de ~34 s, e o pico é o de um caso só.
_SIMULTANEOS = 1

_HOJE = "<HOJE>"


def _nome(caso: str, modo: str) -> str:
    return f"{caso}_{modo}"


def extrair(pdf: Path) -> dict:
    """Células do PDF, com a data do dia trocada por um marcador.

    "Impresso em DD/MM/AAAA" é a única célula que muda sozinha (medido no TC8
    em 22/10/2026: as outras 213 são do caso). Sem a troca, a referência
    reprovaria no dia seguinte ao de ser gravada.
    """
    hoje = date.today().strftime("%d/%m/%Y")
    celulas, paginas = comparar_pdf._celulas(pdf, None)
    return {
        "paginas": paginas,
        "celulas": [[c.pagina, round(c.x, 2), round(c.y, 2),
                     c.texto.replace(hoje, _HOJE)] for c in celulas],
    }


def _como_celulas(dados: dict) -> list:
    return [comparar_pdf.Celula(p, x, y, t) for p, x, y, t in dados["celulas"]]


def gerar(caso: str, modo: str, pasta: Path) -> tuple[dict | None, str]:
    """Gera a ficha pelo `tools/caso.py`, num processo à parte.

    Processo à parte, e não importando o `caso.main`: ele monta a
    `JanelaPrincipal` e mexe no estado global do Qt e do `estilo`, e dentro da
    suíte isso contaminaria os testes seguintes.
    """
    saida = pasta / f"{_nome(caso, modo)}.pdf"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(
        [sys.executable, str(RAIZ / "tools" / "caso.py"), str(ACERVO / caso),
         "--modo", modo, "-o", str(saida)],
        cwd=RAIZ, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300,
    )
    if r.returncode != 0 or not saida.is_file():
        return None, (r.stdout + r.stderr)[-1500:]
    # O stderr volta mesmo quando a ficha sai: é onde o `ficha_pdf` diz por
    # que um pedaço dela (o DVH, por exemplo) não foi gerado.
    return extrair(saida), r.stderr[-1500:]


def diferencas(referencia: dict, atual: dict) -> list[str]:
    """As linhas do que mudou; vazia quando o papel é o mesmo."""
    linhas = []
    if referencia["paginas"] != atual["paginas"]:
        linhas.append(f"páginas: {referencia['paginas']} → {atual['paginas']}")
    _iguais, mudou, moveu, sumiu, surgiu = comparar_pdf.comparar(
        _como_celulas(referencia), _como_celulas(atual), TOLERANCIA)
    for a, b in mudou:
        linhas.append(f"p{a.pagina} {comparar_pdf._pos(a)} MUDOU  "
                      f"{a.texto[:50]!r} → {b.texto[:50]!r}")
    for a, b in moveu:
        linhas.append(f"p{a.pagina} {comparar_pdf._pos(a)} → "
                      f"{comparar_pdf._pos(b)} ANDOU  {a.texto[:50]!r}")
    linhas += [f"p{c.pagina} {comparar_pdf._pos(c)} SUMIU  {c.texto[:50]!r}"
               for c in sumiu]
    linhas += [f"p{c.pagina} {comparar_pdf._pos(c)} SURGIU {c.texto[:50]!r}"
               for c in surgiu]
    return linhas


def conferir(casos=CASOS) -> dict[str, list[str]]:
    """`nome → diferenças` de cada caso. Erro de geração também é diferença:
    ficha que não sai é o papel mais mudado que existe."""
    resultado: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(_SIMULTANEOS) as pool:
        futuros = {_nome(c, m): pool.submit(gerar, c, m, Path(tmp))
                   for c, m in casos}
        for nome, futuro in futuros.items():
            atual, erro = futuro.result()
            ref = REFERENCIAS / f"{nome}.json"
            if atual is None:
                resultado[nome] = [f"a ficha não foi gerada:\n{erro}"]
            elif not ref.is_file():
                resultado[nome] = [f"sem referência ({ref.name}); rode --gravar"]
            else:
                linhas = diferencas(
                    json.loads(ref.read_text(encoding="utf-8")), atual)
                # Diferença intermitente só se investiga com o que o processo
                # disse NA VEZ em que ela aconteceu.
                if linhas and erro.strip():
                    linhas.append(f"stderr da geração:\n{erro}")
                resultado[nome] = linhas
    return resultado


def gravar(casos=CASOS) -> int:
    REFERENCIAS.mkdir(parents=True, exist_ok=True)
    falhas = 0
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(_SIMULTANEOS) as pool:
        futuros = {(c, m): pool.submit(gerar, c, m, Path(tmp)) for c, m in casos}
        for (c, m), futuro in futuros.items():
            atual, erro = futuro.result()
            if atual is None:
                print(f"{_nome(c, m)}: NÃO gerou\n{erro}")
                falhas += 1
                continue
            destino = REFERENCIAS / f"{_nome(c, m)}.json"
            # Uma célula por linha: o diff do commit mostra a célula que mudou,
            # e não um JSON de uma linha só reescrito inteiro.
            corpo = ",\n".join(json.dumps(x, ensure_ascii=False)
                               for x in atual["celulas"])
            destino.write_text(
                '{"paginas": ' + json.dumps(atual["paginas"]) + ',\n'
                '"celulas": [\n' + corpo + "\n]}\n", encoding="utf-8")
            print(f"{destino.name}: {len(atual['celulas'])} células")
    return 1 if falhas else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--gravar", action="store_true",
                   help="aceita o papel de hoje como referência")
    p.add_argument("casos", nargs="*", help="TC8, Elekta… (padrão: todos)")
    args = p.parse_args(argv)
    if not ACERVO.is_dir():
        print(f"Sem o acervo pseudonimizado em {ACERVO}.", file=sys.stderr)
        return 2
    casos = [x for x in CASOS if not args.casos or x[0] in args.casos]
    if args.gravar:
        return gravar(casos)
    mudou = False
    for nome, linhas in conferir(casos).items():
        print(f"{nome}: {'igual' if not linhas else f'{len(linhas)} diferença(s)'}")
        for ln in linhas[:40]:
            print(f"  {ln}")
        mudou = mudou or bool(linhas)
    return 1 if mudou else 0


if __name__ == "__main__":
    sys.exit(main())
