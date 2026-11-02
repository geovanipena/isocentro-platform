"""Diferenças entre versões do paciente (módulo diff_versoes, funções puras).

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import diff_versoes as dv  # noqa: E402


class TestAchatar(unittest.TestCase):
    def test_dict_aninhado(self):
        self.assertEqual(dv.achatar({"a": {"b": 1, "c": 2}}),
                         {"a.b": 1, "a.c": 2})

    def test_lista_de_escalares_inteira(self):
        # lista de escalares fica como um todo (sem faixa[0], faixa[1])
        self.assertEqual(dv.achatar({"faixa": [50, 100]}), {"faixa": [50, 100]})

    def test_lista_de_dicts_indexada(self):
        self.assertEqual(dv.achatar({"fx": [{"g": 0}, {"g": 90}]}),
                         {"fx[0].g": 0, "fx[1].g": 90})


class TestDiffBloco(unittest.TestCase):
    def test_mudancas_com_rotulo(self):
        a = {"rx_dose_total": 50, "gating": "Não"}
        b = {"rx_dose_total": 60, "gating": "Sim", "gating_modalidade": "Breath-Hold"}
        diff = {rot: (old, new) for rot, old, new in dv.diff_bloco(a, b)}
        self.assertEqual(diff["Dose total"], (50, 60))
        self.assertEqual(diff["Gating"], ("Não", "Sim"))
        self.assertEqual(diff["Modalidade"], (dv.AUSENTE, "Breath-Hold"))

    def test_sem_mudanca(self):
        self.assertEqual(dv.diff_bloco({"x": 1}, {"x": 1}), [])


class TestFormatar(unittest.TestCase):
    def test_valores(self):
        self.assertEqual(dv.formatar(dv.AUSENTE), "—")
        self.assertEqual(dv.formatar(None), "—")
        self.assertEqual(dv.formatar(""), "—")
        self.assertEqual(dv.formatar(True), "Sim")
        self.assertEqual(dv.formatar(False), "Não")
        self.assertEqual(dv.formatar([1, 2, 3]), "1, 2, 3")
        self.assertEqual(dv.formatar([]), "—")
        self.assertEqual(dv.formatar(42), "42")


class TestHtmlDiff(unittest.TestCase):
    def test_mostra_mudanca_de_dose(self):
        v1 = {"versao": 1, "dados": {"rx_dose_total": 50}, "plano_rp": {}, "render": {}}
        v2 = {"versao": 2, "dados": {"rx_dose_total": 60}, "plano_rp": {}, "render": {}}
        html = dv.html_diff([v1, v2])
        self.assertIn("Dose total", html)
        self.assertIn("v1", html)
        self.assertIn("v2", html)


if __name__ == "__main__":
    unittest.main()
