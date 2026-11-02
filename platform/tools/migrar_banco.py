#!/usr/bin/env python
"""Aplica as migrações de ``migracoes/`` no banco central, como ``isocentro_dono``.

    python tools/migrar_banco.py --conexao "host=localhost port=5433 user=postgres dbname=isocentro"
    python tools/migrar_banco.py --conexao "..." --papeis    # cria os 3 papéis antes (superusuário)
    python tools/migrar_banco.py --conexao "..." --simular   # só diz o que aplicaria

Por que uma ferramenta e não o app: o AD-19 tira do app o direito de mudar o
esquema. Se o app migrasse ao abrir, a primeira estação atualizada mudaria o
banco debaixo das outras, que ainda gravam com o modelo antigo. Aqui quem
migra é uma pessoa, de propósito, com o papel dono — e as estações velhas
passam a abrir somente leitura até serem atualizadas.

O banco precisa existir e ser do ``isocentro_dono`` (ele cria os schemas):
``createdb -O isocentro_dono isocentro``. O roteiro do banco de
desenvolvimento está no ``docs/AMBIENTE.md``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import psycopg  # noqa: E402

from isocentro.adaptadores.postgres import esquema  # noqa: E402

PASTA = RAIZ / "migracoes"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--conexao", required=True,
                    help="conninfo do psycopg (quem conecta precisa poder "
                         "assumir o papel isocentro_dono)")
    ap.add_argument("--papeis", action="store_true",
                    help="cria os papéis que faltarem (exige superusuário)")
    ap.add_argument("--simular", action="store_true",
                    help="lista as migrações pendentes e não aplica")
    args = ap.parse_args(argv)

    arquivos = esquema.migracoes(PASTA)
    # connect_timeout: no Windows, conectar numa porta sem servidor NÃO
    # falha — fica pendurado para sempre (medido em 29/10/2026; ARMADILHAS).
    with psycopg.connect(args.conexao, autocommit=True,
                         connect_timeout=5) as conexao:
        if args.papeis:
            criados = esquema.criar_papeis(conexao)
            print(f"papéis criados: {', '.join(criados) or 'nenhum (já existiam)'}")
        atual = esquema.versao_do_banco(conexao) or 0
        pendentes = [a.name for n, a in arquivos if n > atual]
        print(f"banco na versão {atual}; pendentes: {', '.join(pendentes) or 'nenhuma'}")
        if args.simular or not pendentes:
            return 0
        aplicadas = esquema.aplicar(conexao, PASTA)
        print(f"aplicadas: {aplicadas}; banco agora na versão "
              f"{esquema.versao_do_banco(conexao)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
