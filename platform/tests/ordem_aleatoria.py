"""Roda a suíte em ordem ALEATÓRIA, para achar teste que depende de outro.

Duas vezes um teste passou sozinho e derrubou outro arquivo por estado global
que vazou:

* ``test_capa_tela`` antes de ``test_capa`` quebrava 16 casos (a pasta de
  relatórios ficava fixada no processo);
* o ``tearDown`` de ``test_fotos_mhtml`` congelava essa mesma pasta ao
  "restaurar" o valor que tinha LIDO, em vez da variável de ambiente.

Os dois só apareceram por acidente. O ``discover`` roda em ordem alfabética
sempre, então a suíte verde não quer dizer "os testes são independentes": quer
dizer "nesta ordem, hoje, deu certo". Acrescentar um arquivo cujo nome caia
antes de outro pode acender um problema que já existia há meses.

Rodar:
    python tests/ordem_aleatoria.py            (semente ao acaso)
    python tests/ordem_aleatoria.py --semente 12345   (repete uma falha)

A semente é impressa sempre — é com ela que se reproduz a ordem que quebrou.
"""
from __future__ import annotations

import argparse
import random
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def _espalhar(suite, aleatorio) -> unittest.TestSuite:
    """Embaralha em todos os níveis: arquivos, classes e métodos.

    Embaralhar só os arquivos esconderia dependência entre dois testes da
    MESMA classe — que é justamente onde o estado costuma vazar sem ninguém ver.
    """
    itens = list(suite)
    aleatorio.shuffle(itens)
    fora = unittest.TestSuite()
    for item in itens:
        if isinstance(item, unittest.TestSuite):
            fora.addTest(_espalhar(item, aleatorio))
        else:
            fora.addTest(item)
    return fora


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--semente", type=int, default=None,
                   help="repete uma ordem que já quebrou")
    p.add_argument("--vezes", type=int, default=1,
                   help="quantas ordens diferentes tentar")
    args = p.parse_args(argv)

    falhou = 0
    for _volta in range(args.vezes):
        semente = args.semente if args.semente is not None \
            else random.randrange(1, 10 ** 9)
        print("=" * 70)
        print(f"  Ordem aleatória — semente {semente}")
        print(f"  Para repetir esta ordem: "
              f"python tests/ordem_aleatoria.py --semente {semente}")
        print("=" * 70, flush=True)

        # ``top_level_dir`` na RAIZ exigiria ``tests`` como pacote (com
        # __init__.py), que ele não é — o discover do dia a dia roda com
        # ``-s tests`` e o mesmo diretório dos dois lados.
        suite = unittest.defaultTestLoader.discover(str(RAIZ / "tests"))
        embaralhada = _espalhar(suite, random.Random(semente))
        r = unittest.TextTestRunner(verbosity=1).run(embaralhada)
        if not r.wasSuccessful():
            falhou += 1
            print(f"\n  FALHOU com a semente {semente}.")
            print("  Isto quase sempre é teste que depende de outro, não código"
                  " quebrado: rode a mesma semente para confirmar, e procure "
                  "estado global (variável de ambiente, cache de módulo, pasta "
                  "fixada) que alguém deixou para trás.")
            if args.vezes == 1:
                return 1
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
