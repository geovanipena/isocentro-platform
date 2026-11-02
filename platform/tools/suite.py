#!/usr/bin/env python
"""A suíte inteira num comando só, com a saída em arquivo e o veredito na tela.

    python tools/suite.py              # discover, como no CLAUDE.md
    python tools/suite.py --aleatoria  # tests/ordem_aleatoria.py

Por que existe: a sessão do robô (`claude -p`, `--permission-mode dontAsk`)
não tinha como rodar a suíte do jeito que o `/pronto` manda. Em 15/09/2026 a
R-01 tentou três formas — `> arquivo 2>&1; echo`, e duas com
`run_in_background` — e as três foram RECUSADAS: redirecionamento e comando
encadeado não casam com `Bash(python:*)`. A sessão então escreveu "aguardo o
resultado das duas" e terminou, porque no `-p` a resposta que acaba é a sessão
que acaba; a árvore ficou suja e a conferência reprovou.

Aqui o redirecionamento é do próprio script: o comando é `python ...` puro,
roda em primeiro plano, e o que volta para o contexto são as poucas linhas que
decidem — não as milhares do modo verboso. O código de saída é o da suíte.

**Roda os testes da pasta ATUAL, não da pasta deste arquivo.** O robô chama
esta cópia (a do checkout do usuário) por caminho absoluto de dentro do
worktree: a `robo` só ganha o arquivo quando o usuário junta, e até lá a sessão
não teria suíte nenhuma para rodar. Os testes medidos são os do worktree.

**Com vigia** (29/10/2026): em 28–29/10 a suíte ficou 1h40 parada no primeiro
teste de banco (``psycopg.connect`` sem tempo-limite, servidor fora), e quem
esperava só via um arquivo que parou de crescer. Agora cada teste rearma o
``faulthandler``: passou de ``--limite`` segundos (padrão 180), ele imprime a
pilha com o nome do teste e encerra; o veredito diz ``TRAVOU em <teste>``.
O executor vigiado vai EMBUTIDO (``_VIGIADO``), e não num arquivo de
``tests/``: o worktree do robô pode ainda não ter o arquivo.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Ignorada inteira pelo git (ver `.gitignore`): relatório não entra em commit.
RELATORIOS = Path("relatorios_ferramentas") / "suite"

# O que decide o veredito, e a semente da ordem aleatória, que é com o que se
# repete a ordem que quebrou.
_IMPORTA = re.compile(r"^(Ran \d+ tests?|OK\b|FAILED\b|FAIL:|ERROR:|\s*Ordem aleatória — semente|\s*FALHOU com a semente)")


# Troca o resultado padrão do ``TextTestRunner`` pelo vigiado e roda o que
# foi pedido. Pela classe, e não por parâmetro: o ``ordem_aleatoria.py`` cria
# o próprio runner, e assim ele também passa a ser vigiado sem mudar nada lá.
_VIGIADO = """
import faulthandler, sys, unittest
faulthandler.enable()
LIMITE = int(sys.argv[1])
class Vigiado(unittest.TextTestResult):
    def startTest(self, teste):
        sys.stderr.write("\\n[vigia] " + teste.id() + "\\n")
        sys.stderr.flush()
        faulthandler.dump_traceback_later(LIMITE, exit=True)
        super().startTest(teste)
    def stopTest(self, teste):
        faulthandler.cancel_dump_traceback_later()
        super().stopTest(teste)
unittest.TextTestRunner.resultclass = Vigiado
if sys.argv[2] == "aleatoria":
    sys.path.insert(0, "tests")
    import ordem_aleatoria
    sys.exit(ordem_aleatoria.main([]))
unittest.main(module=None, argv=["unittest", "discover", "-s", "tests"])
"""


def veredito(texto: str) -> list[str]:
    """As linhas que decidem, na ordem em que saíram.

    Travou: o teste que estava rodando (o último ``[vigia]`` antes do
    ``Timeout``) e a primeira linha da pilha dele, que é onde parou.
    """
    linhas = [linha.rstrip() for linha in texto.splitlines() if _IMPORTA.match(linha)]
    if "Timeout (" in texto:
        antes, depois = texto.split("Timeout (", 1)
        rodando = [ln for ln in antes.splitlines() if ln.startswith("[vigia] ")]
        onde = next((ln.strip() for ln in depois.splitlines()
                     if ln.strip().startswith("File ")), "")
        linhas.append(f"TRAVOU em {rodando[-1][8:] if rodando else '?'} "
                      f"(passou do limite; {onde})")
    return linhas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--aleatoria", action="store_true",
                   help="roda tests/ordem_aleatoria.py em vez do discover")
    p.add_argument("--limite", type=int, default=180,
                   help="segundos por teste antes de declarar travado")
    args = p.parse_args(argv)

    raiz = Path.cwd()
    if not (raiz / "tests").is_dir():
        print(f"{raiz} não tem pasta tests/: rodar da raiz do repositório (ou do worktree)")
        return 2
    nome = "aleatoria" if args.aleatoria else "discover"
    comando = [sys.executable, "-c", _VIGIADO, str(args.limite), nome]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    pasta = raiz / RELATORIOS
    pasta.mkdir(parents=True, exist_ok=True)
    relatorio = pasta / f"{nome}_{datetime.now():%Y%m%d-%H%M%S}.txt"
    # Em arquivo, nunca por pipe: o `unittest` relata em stderr e os `print`
    # dos testes vão em stdout, e o resumo cairia no meio (ver `| tail` no
    # ARMADILHAS.md).
    with relatorio.open("w", encoding="utf-8") as saida:
        r = subprocess.run(comando, cwd=raiz, stdout=saida, stderr=subprocess.STDOUT, env=env)

    texto = relatorio.read_text(encoding="utf-8", errors="replace")
    for linha in veredito(texto) or ["(nenhuma linha de veredito: a suíte nem chegou a rodar?)"]:
        print(linha)
    print(f"código de saída: {r.returncode}")
    print(f"relatório completo: {relatorio}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
