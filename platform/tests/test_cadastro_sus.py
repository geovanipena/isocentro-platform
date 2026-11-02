"""Cadastro de convênio SUS por paciente (nome + nascimento + registro)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Isola o JSON do cadastro num diretório temporário para não tocar o do app.
os.environ["ISOCENTRO_SUS_DIR"] = tempfile.mkdtemp()

from isocentro.dados import cadastro_sus as cs


class TestCadastroSus(unittest.TestCase):
    def setUp(self):
        # Cada teste começa com o JSON limpo.
        p = cs.caminho()
        if p.exists():
            p.unlink()

    def test_consultar_sem_cadastro_e_none(self):
        self.assertIsNone(cs.consultar("Fulano", "01/02/1990", "R1"))

    def test_registrar_e_consultar(self):
        cs.registrar("Fulano de Tal", "01/02/1990", "R1", True, "700000000000001")
        got = cs.consultar("Fulano de Tal", "01/02/1990", "R1")
        self.assertIsNotNone(got)
        self.assertTrue(got["pac_sus"])
        self.assertEqual(got["numero_sus"], "700000000000001")

    def test_identidade_ignora_acento_e_caixa(self):
        cs.registrar("João da Silva", "10/10/1980", "R2", True, "123")
        self.assertIsNotNone(cs.consultar("JOAO DA SILVA", "10/10/1980", "R2"))

    def test_registro_diferente_nao_casa(self):
        cs.registrar("Fulano", "01/02/1990", "R1", True, "999")
        self.assertIsNone(cs.consultar("Fulano", "01/02/1990", "R2"))

    def test_nascimento_diferente_nao_casa(self):
        # Mesmo registro e nome, nascimento diferente → não é o mesmo paciente.
        cs.registrar("Fulano", "01/02/1990", "R1", True, "999")
        self.assertIsNone(cs.consultar("Fulano", "02/02/1990", "R1"))

    def test_sem_registro_nao_grava_nem_consulta(self):
        self.assertFalse(cs.registrar("Fulano", "01/02/1990", "", True, "999"))
        self.assertIsNone(cs.consultar("Fulano", "01/02/1990", ""))

    def test_nao_sus_zera_numero(self):
        cs.registrar("Fulano", "01/02/1990", "R1", False, "999")
        got = cs.consultar("Fulano", "01/02/1990", "R1")
        self.assertFalse(got["pac_sus"])
        self.assertEqual(got["numero_sus"], "")

    def test_regravar_atualiza(self):
        cs.registrar("Fulano", "01/02/1990", "R1", True, "111")
        cs.registrar("Fulano", "01/02/1990", "R1", True, "222")
        self.assertEqual(cs.consultar("Fulano", "01/02/1990", "R1")["numero_sus"],
                         "222")


if __name__ == "__main__":
    unittest.main(verbosity=2)
