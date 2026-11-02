# -*- coding: utf-8 -*-
"""Roda só os testes da frente que está aberta, em vez da suíte inteira.

A suíte completa são 1742 testes em ~2,5 minutos (08/09/2026). Isso é o preço
justo do **fechamento** — e é o que o ``/pronto`` faz. Durante o trabalho, entre
uma edição e a seguinte, é preço de espera: quinze rodadas ao longo de uma
manhã são meia hora parado esperando 1700 testes para conferir três linhas.

Esta ferramenta pergunta ao git o que mudou e roda apenas os arquivos de teste
que **importam** o módulo mexido. Não substitui a suíte: teste que não rodou não
diz nada, e é justamente um vizinho não rodado que quebra. Ela diz isso na
saída, de propósito — atalho que se esquece de anunciar vira falso "está pronto".

Rodar:
    python tools/testar.py                  # o que o git diz que mudou
    python tools/testar.py fichinha gui     # módulos, na mão
    python tools/testar.py tests/test_capa.py

Por que casar por IMPORT e não por nome de arquivo: ``fichinha.py`` é coberto
por ``test_fichinha_trilha.py`` e por ``test_gui_smoke.py``, e o nome só acha o
primeiro. Foi um caso real — a trilha da Fichinha passou e a fumaça da janela
quebrou, porque a faixa de modo mora no ``gui``.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TESTES = RAIZ / "tests"
sys.path.insert(0, str(RAIZ))


def _mudou_no_git() -> list[Path]:
    """Os .py que o git vê diferentes: na árvore, no índice e os novos.

    ``--porcelain`` cobre os três de uma vez; ``diff HEAD`` sozinho perde o
    arquivo novo que ainda não foi adicionado, que é exatamente o teste que
    acabou de nascer.
    """
    saida = subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stdout
    achados = []
    for linha in saida.splitlines():
        if not linha.strip():
            continue
        caminho = linha[3:].strip().strip('"')
        # renomeado vem como "velho -> novo"; o que interessa é o novo
        if " -> " in caminho:
            caminho = caminho.split(" -> ", 1)[1]
        if caminho.endswith(".py"):
            achados.append(RAIZ / caminho)
    return achados


def _modulo(caminho: Path) -> str:
    """Nome pelo qual os testes importam este arquivo."""
    try:
        rel = caminho.resolve().relative_to(RAIZ)
    except ValueError:
        rel = Path(caminho.name)
    partes = list(rel.with_suffix("").parts)
    # ``pacote/__init__.py`` se importa como ``pacote``: com o ``__init__`` no
    # nome, nenhum teste casava, e o manifesto de um módulo saía "ninguém
    # importa isto".
    if len(partes) > 1 and partes[-1] == "__init__":
        partes.pop()
    return ".".join(partes)


def _padrao_de_import(m: str) -> re.Pattern:
    """As três formas pelas quais um teste daqui importa ``m``.

    ``from isocentro.papel import ficha_pdf`` é a forma mais comum nos testes
    do papel, e casar só ``from isocentro.papel.ficha_pdf`` deixava o recorte
    sem nenhum deles. E ``tools/`` não é pacote: os testes põem a pasta no
    ``sys.path`` e importam ``mapa``, não ``tools.mapa``.
    """
    formas = [r"(?:from|import)\s+%s\b" % re.escape(m)]
    pacote, _, nome = m.rpartition(".")
    if pacote:
        formas.append(r"from\s+%s\s+import\s+(?:\([^)]*?|[^(\n]*?)\b%s\b"
                      % (re.escape(pacote), re.escape(nome)))
    if pacote == "tools":
        formas.append(r"(?:from|import)\s+%s\b" % re.escape(nome))
    return re.compile(r"^\s*(?:%s)" % "|".join(formas), re.MULTILINE)


def _quem_importa(modulos: set[str]) -> dict[str, set[str]]:
    """Para cada módulo, os arquivos de teste que o importam.

    Casa ``import x``, ``from x import`` e ``import x as y`` — em qualquer
    coluna, porque neste repositório há import tardio dentro de método (e é
    justamente o que já ficou de fora do pacote uma vez).
    """
    padroes = {m: _padrao_de_import(m) for m in modulos}
    mapa: dict[str, set[str]] = {m: set() for m in modulos}
    for arq in sorted(TESTES.glob("test_*.py")):
        texto = arq.read_text(encoding="utf-8", errors="replace")
        for m, padrao in padroes.items():
            if padrao.search(texto):
                mapa[m].add(f"tests.{arq.stem}")
    return mapa


def _arquivos_do_raio(ref: str) -> list[Path] | None:
    """Os arquivos que o raio do diff manda cobrir; ``None`` = suíte inteira.

    O raio é mais largo que "o que mudou": mexer em ``papel/rodape.py`` pede
    os testes de TODO o Radioteraficha, porque é do módulo que se responde.
    Quando o raio é "tudo", não há recorte honesto — e dizer isso é o
    serviço, não uma falha.
    """
    # ``tools/`` só é o sys.path[0] quando este arquivo roda como script.
    sys.path.insert(0, str(RAIZ / "tools"))
    import raio
    diff = raio.arquivos_do_diff(ref, RAIZ)
    if not diff:
        print(f"Nada mudou contra {ref}. Para a suíte inteira: /pronto")
        return []
    itens = raio.avaliar(diff, raio.montar_grafo(RAIZ))
    print(raio.relatorio(itens, ref))
    print()
    rels = raio.recorte(itens, RAIZ)
    if rels is None:
        print("O raio é a suíte inteira: não há recorte. Rode /pronto.")
        return None
    if not rels:
        print("Só documento que nenhum teste lê.")
    return [RAIZ / r for r in rels]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("alvos", nargs="*",
                   help="módulos ou arquivos; vazio = o que o git diz que mudou")
    p.add_argument("-v", "--verboso", action="store_true",
                   help="nome de cada teste, para achar o que travou")
    # ``--raio`` é chave, e a ref vai à parte: com ``--raio [REF]`` opcional,
    # ``--raio tests/test_capa.py`` engolia o alvo como se fosse a ref.
    p.add_argument("--raio", action="store_true",
                   help="recorte pelo raio de revisão do diff: o módulo dono "
                        "inteiro e os consumidores da fachada (tools/raio.py)")
    p.add_argument("--ref", default="HEAD",
                   help="ref do git para o --raio (padrão HEAD)")
    args = p.parse_args(argv)
    if args.raio and args.alvos:
        p.error("--raio já diz o que rodar; não junte com alvos na mão")

    # Saída por LINHA, não por bloco. O unittest relata em stderr, que sai na
    # hora; o `print` daqui vai para stdout, que o Python bufferiza quando a
    # saída é um cano. Sem isto o resumo aparece ANTES do relatório, e um
    # `| tail` corta justamente o veredito — custou uma rodada inteira em
    # 08/09/2026, na conversa que criou esta ferramenta.
    sys.stdout.reconfigure(line_buffering=True)

    if args.raio:
        arquivos = _arquivos_do_raio(args.ref)
        if arquivos is None:
            return 2
        if arquivos == []:
            print("Nenhum teste no raio. O fechamento continua sendo a "
                  "suíte: /pronto")
            return 0
    elif args.alvos:
        arquivos = [RAIZ / a if a.endswith(".py") else RAIZ / f"{a}.py"
                    for a in args.alvos]
    else:
        arquivos = _mudou_no_git()
        if not arquivos:
            print("Nada mudou segundo o git. Para a suíte inteira: /pronto")
            return 0

    # Teste mexido roda a si mesmo; módulo mexido roda quem o importa.
    escolhidos: set[str] = set()
    motivos: list[str] = []
    modulos = set()
    for arq in arquivos:
        mod = _modulo(arq)
        if mod.startswith("tests.test_"):
            escolhidos.add(mod)
            motivos.append(f"  {mod}  ← mexido")
        elif mod.startswith("tests."):
            # limpeza_de_tela, ordem_aleatoria e afins: mexer neles afeta TUDO
            print(f"{mod} é infraestrutura de teste — isto pede a suíte "
                  f"inteira, não um recorte. Rode /pronto.")
            return 2
        else:
            modulos.add(mod)

    if modulos:
        for mod, testes in sorted(_quem_importa(modulos).items()):
            if not testes:
                motivos.append(f"  {mod}  ← NINGUÉM importa isto em tests/")
                continue
            escolhidos |= testes
            motivos.append(f"  {mod}  → {', '.join(sorted(testes))}")

    print("O que mudou, e o que cobre:")
    print("\n".join(motivos))
    if not escolhidos:
        print("\nNenhum teste casou. Ou o módulo é novo e não tem teste — e aí "
              "o próximo passo é escrevê-lo —, ou é caso para a suíte inteira.")
        return 1

    print(f"\nRodando {len(escolhidos)} arquivo(s) de teste…\n")
    carregador = unittest.TestLoader()
    suite = carregador.loadTestsFromNames(sorted(escolhidos))
    inicio = time.monotonic()
    r = unittest.TextTestRunner(verbosity=2 if args.verboso else 1).run(suite)
    print(f"\n{len(escolhidos)} arquivo(s), {r.testsRun} testes, "
          f"{time.monotonic() - inicio:.1f}s")
    # O aviso é a parte séria: recorte verde NÃO é suíte verde.
    # Sem o total da suíte de propósito: o "de ~1742" fixo envelheceu calado
    # até a suíte ter 2.369 e o recorte parecer cobrir mais do que cobria.
    print(f"Recorte, não a suíte: rodaram {r.testsRun} testes, não a suíte "
          f"inteira. Antes de dizer que está pronto, /pronto.")
    return 0 if r.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
