"""O protótipo da aba Radioteradados (13/10/2026).

O que se protege aqui é o que o protótipo promete e um ajuste descuidado
quebraria calado: nenhum cartão do núcleo RDC mostra número enquanto a fórmula
não existe (a regra de nunca inventar dado), a falta de uma fonte vira
travessão e nunca zero, e o mês nunca avança para o futuro.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from isocentro.interface import controle_radioteradados as ctl  # noqa: E402
from isocentro.interface import radioteradados_tela as tela  # noqa: E402

_APP = QApplication.instance() or QApplication([])


class TestMeses(unittest.TestCase):

    def test_abre_no_mes_anterior_inclusive_na_virada_do_ano(self):
        self.assertEqual(ctl.mes_anterior(date(2026, 10, 13)), date(2026, 9, 1))
        self.assertEqual(ctl.mes_anterior(date(2027, 1, 5)), date(2026, 12, 1))

    def test_andar_atravessa_o_ano(self):
        self.assertEqual(ctl.andar_mes(date(2026, 12, 1), 1), date(2027, 1, 1))
        self.assertEqual(ctl.andar_mes(date(2026, 1, 1), -1), date(2025, 12, 1))

    def test_nome_do_mes(self):
        self.assertEqual(tela.nome_do_mes(date(2026, 9, 1)), "Setembro/2026")


class TestPainel(unittest.TestCase):

    def setUp(self):
        self.p = tela.PainelRadioteradados()

    def tearDown(self):
        self.p.deleteLater()

    def test_nucleo_rdc_tem_os_seis_e_nenhum_numero(self):
        """Número de exemplo num cartão de indicador é o número que alguém
        copia para a chefia."""
        self.assertEqual(len(self.p.cartoes_rdc), 6)
        for titulo, cartao in self.p.cartoes_rdc.items():
            with self.subTest(titulo=titulo):
                # "v2" é a versão do produto em que o indicador entra, não valor.
                texto = cartao.texto().replace("v2", "")
                self.assertFalse(any(ch.isdigit() for ch in texto))

    def test_os_dois_de_fora_do_banco_aparecem_marcados(self):
        self.assertEqual(self.p.cartoes_rdc["Adesão a protocolos"].texto(),
                         "Fora do banco — v2")
        self.assertEqual(self.p.cartoes_rdc["Desvio da dose absoluta"].texto(),
                         "Fora do banco — v2")

    def test_botoes_apagados_com_motivo(self):
        for b in (self.p.btn_congelar, self.p.btn_relatorio):
            with self.subTest(botao=b.text()):
                self.assertFalse(b.isEnabled())
                self.assertTrue(b.toolTip())

    def test_falta_vira_travessao_nunca_zero(self):
        self.p.definir_operacao([("6EX", None, 120, 9, None)])
        textos = [self.p.grade_operacao.itemAt(i).widget().text()
                  for i in range(self.p.grade_operacao.count())
                  if isinstance(self.p.grade_operacao.itemAt(i).widget(), QLabel)]
        self.assertIn("—", textos)
        self.assertNotIn("0", textos)

    def test_sem_fonte_mostra_o_motivo_e_nenhuma_linha(self):
        self.p.definir_operacao(None, "a agenda não respondeu")
        self.assertEqual(self.p.status.text(), "a agenda não respondeu")
        self.assertEqual(self.p.grade_operacao.count(), 0)


class TestControle(unittest.TestCase):

    def test_nao_avanca_para_o_futuro(self):
        p = tela.PainelRadioteradados()
        c = ctl.ControleRadioteradados(p)
        try:
            c._atualizar = lambda: None    # sem banco: só a regra do mês
            c._mes = date.today().replace(day=1)
            c._andar(1)
            self.assertEqual(c._mes, date.today().replace(day=1))
        finally:
            p.deleteLater()


from tests.limpeza_de_tela import load_tests  # noqa: E402,F401

if __name__ == "__main__":
    unittest.main()
