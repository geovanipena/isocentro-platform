"""``raiz.pasta_do_app`` e a variável ``ISOCENTRO_PASTA_APP`` (frente R-57).

Gravar na pasta errada é a quebra com aparência de funcionamento que o
``raiz.py`` descreve: o índice nasce vazio, sem erro. Por isso os três casos
ficam provados aqui — sem a variável, nada mudou; com ela, fora do pacote, a
pasta é a dela; empacotado, ela é ignorada e o executável grava ao lado de si.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro import raiz  # noqa: E402
from isocentro.dados import ambiente  # noqa: E402

VAR = "ISOCENTRO_PASTA_APP"


class TestPastaDoApp(unittest.TestCase):

    def setUp(self):
        self._antes = {n: os.environ.pop(n, None) for n in ambiente.nomes(VAR)}

    def tearDown(self):
        for nome, valor in self._antes.items():
            os.environ.pop(nome, None)
            if valor is not None:
                os.environ[nome] = valor

    def test_sem_a_variavel_e_a_raiz_do_projeto(self):
        self.assertEqual(raiz.pasta_do_app(), raiz.raiz_do_projeto())

    def test_com_a_variavel_fora_do_pacote_e_a_dela(self):
        os.environ[VAR] = r"C:\outra\estacao"
        self.assertEqual(raiz.pasta_do_app(), Path(r"C:\outra\estacao"))

    def test_vale_pelos_nomes_antigos(self):
        """A TI configura pelo nome que conhece; os três têm de valer."""
        antigo = ambiente.nomes_antigos(VAR)[0]
        os.environ[antigo] = r"C:\pelo\nome\antigo"
        self.assertEqual(raiz.pasta_do_app(), Path(r"C:\pelo\nome\antigo"))

    def test_empacotado_ignora_a_variavel(self):
        """O executável grava ao lado de si: é lá que o ``migrar.ps1`` procura."""
        os.environ[VAR] = r"C:\outra\estacao"
        exe = Path(r"C:\Isocentro\Isocentro.exe")
        antes = (getattr(sys, "frozen", None), sys.executable)
        sys.frozen = True
        sys.executable = str(exe)
        try:
            self.assertEqual(raiz.pasta_do_app(), exe.resolve().parent)
        finally:
            if antes[0] is None:
                del sys.frozen
            else:
                sys.frozen = antes[0]
            sys.executable = antes[1]


if __name__ == "__main__":
    unittest.main()
