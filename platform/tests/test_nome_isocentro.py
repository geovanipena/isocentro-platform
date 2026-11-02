"""O app virou ISOCENTRO em 15/10/2026 — e nenhuma estação podia perceber.

Ele já tinha mudado de nome uma vez (ficha-py → Radioteraficha). Cada nome
deixou rastro na estação: variável de ambiente que a TI configurou, a lista de
médicos e físicos na pasta do usuário e o ``QSettings`` no registro. Trocar o
nome e pronto faria a estação perder os três SEM ERRO: capa vazia porque o
servidor "não está apontado", equipe que some do formulário, app abrindo no
modo e no tamanho de fábrica. Estes testes seguram o elo com cada nome antigo.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import ambiente  # noqa: E402
from isocentro.dados import equipe  # noqa: E402


class TestVariaveisPelosTresNomes(unittest.TestCase):
    """``ambiente.ler`` acha o valor por qualquer um dos três prefixos."""

    VAR = "ISOCENTRO_TESTE_NOME"

    def setUp(self):
        self._antes = {n: os.environ.pop(n, None) for n in ambiente.nomes(self.VAR)}

    def tearDown(self):
        for nome, valor in self._antes.items():
            os.environ.pop(nome, None)
            if valor is not None:
                os.environ[nome] = valor

    def test_os_tres_nomes_na_ordem_de_precedencia(self):
        self.assertEqual(ambiente.nomes("FICHAPY_TESTE_NOME"),
                         ["ISOCENTRO_TESTE_NOME", "RADIOTERAFICHA_TESTE_NOME",
                          "FICHAPY_TESTE_NOME"])

    def test_cada_nome_antigo_sozinho_ainda_vale(self):
        for nome in ambiente.nomes_antigos(self.VAR):
            os.environ[nome] = nome
            try:
                self.assertEqual(ambiente.ler(self.VAR), nome)
                self.assertEqual(ambiente.qual_valeu(self.VAR), nome)
            finally:
                os.environ.pop(nome, None)

    def test_o_mais_novo_vence(self):
        for nome in ambiente.nomes(self.VAR):
            os.environ[nome] = nome
        self.assertEqual(ambiente.ler(self.VAR), self.VAR)
        self.assertEqual(ambiente.qual_valeu(self.VAR), self.VAR)

    def test_variavel_fora_da_convencao_tem_um_nome_so(self):
        self.assertEqual(ambiente.nomes("PATH"), ["PATH"])


class TestEquipeDaEstacao(unittest.TestCase):
    """A lista de médicos/físicos vem do arquivo do nome antigo, uma vez."""

    def setUp(self):
        self._d = Path(tempfile.mkdtemp(prefix="equipe_nome_"))
        self.novo = self._d / ".isocentro_medicos.json"
        self.meio = self._d / ".radioteraficha_medicos.json"
        self.velho = self._d / ".ficha_py_medicos.json"

    def tearDown(self):
        shutil.rmtree(self._d, ignore_errors=True)

    def test_adota_o_radioteraficha(self):
        self.meio.write_text('{"de": "radioteraficha"}', encoding="utf-8")
        self.velho.write_text('{"de": "ficha_py"}', encoding="utf-8")
        equipe._migrar_nome_antigo(self.novo, (self.meio, self.velho))
        self.assertIn("radioteraficha", self.novo.read_text(encoding="utf-8"))
        self.assertTrue(self.meio.exists(), "cópia, não movimentação")

    def test_sem_radioteraficha_adota_o_ficha_py(self):
        self.velho.write_text('{"de": "ficha_py"}', encoding="utf-8")
        equipe._migrar_nome_antigo(self.novo, (self.meio, self.velho))
        self.assertIn("ficha_py", self.novo.read_text(encoding="utf-8"))

    def test_o_novo_existente_nunca_e_sobrescrito(self):
        self.novo.write_text('{"de": "isocentro"}', encoding="utf-8")
        self.meio.write_text('{"de": "radioteraficha"}', encoding="utf-8")
        equipe._migrar_nome_antigo(self.novo, (self.meio, self.velho))
        self.assertIn("isocentro", self.novo.read_text(encoding="utf-8"))


class TestAjustesDoNomeAntigo(unittest.TestCase):
    """O ``QSettings`` novo nasce com o que estava no ``Radioteraficha``.

    Em ``.ini`` numa pasta descartável, pelo ``ajustes._abrir``: o construtor
    ``QSettings(organização, aplicativo)`` ignora o ``setDefaultFormat`` e iria
    ao registro do Windows de quem roda a suíte.
    """

    def setUp(self):
        from PySide6.QtCore import QSettings

        from isocentro.interface import ajustes
        self.ajustes = ajustes
        self._d = tempfile.mkdtemp(prefix="ajustes_nome_")
        self._abrir = ajustes._abrir
        ajustes._abrir = lambda org, app: QSettings(
            os.path.join(self._d, f"{org}-{app}.ini"), QSettings.IniFormat)

    def tearDown(self):
        self.ajustes._abrir = self._abrir    # guardar e devolver, nunca ``del``
        shutil.rmtree(self._d, ignore_errors=True)

    def _antigo(self):
        return self.ajustes._abrir(*self.ajustes._ANTIGO)

    def test_copia_o_antigo_na_primeira_vez(self):
        antigo = self._antigo()
        antigo.setValue("modo_cor", "noite")
        antigo.sync()
        self.assertEqual(self.ajustes.ajustes().value("modo_cor"), "noite")

    def test_depois_da_copia_o_novo_manda(self):
        antigo = self._antigo()
        antigo.setValue("modo_cor", "noite")
        antigo.sync()
        novo = self.ajustes.ajustes()
        novo.setValue("modo_cor", "dia")
        novo.sync()
        self.assertEqual(self.ajustes.ajustes().value("modo_cor"), "dia")
        self.assertEqual(self._antigo().value("modo_cor"), "noite",
                         "o antigo fica intacto")


if __name__ == "__main__":
    unittest.main()
