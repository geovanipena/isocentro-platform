"""A janela do método: equações, limiares e as fontes de cada um.

Ela existe porque a página não pode carregar tudo o que sustenta um número —
mas o que sai da página não pode sair do programa. Estes testes guardam as duas
pontas: que toda equação aponta para uma referência que EXISTE, e que os
limiares mostrados são os que o cálculo está usando de verdade.

Rodar:  python -m unittest tests.test_qualidade_metodo -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ISOCENTRO_USERS_DIR", tempfile.mkdtemp())

try:
    from PySide6.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    from isocentro.dominio import qualidade as q  # noqa: E402
    from isocentro.dominio import qualidade_metodo as metodo  # noqa: E402
except Exception as exc:  # noqa: BLE001
    metodo = None
    _MOTIVO = str(exc)


@unittest.skipIf(metodo is None, "PySide6 indisponível")
class TestEquacoes(unittest.TestCase):

    def setUp(self):
        self.secoes = metodo._equacoes()
        self.equacoes = [eq for _, lista in self.secoes for eq in lista]

    def test_toda_equacao_aponta_para_uma_referencia_que_existe(self):
        """O link é o que transforma "fora da faixa" de opinião em citação.

        Uma chave errada aqui não quebraria nada em produção: o botão da sigla
        simplesmente não acharia a âncora e a janela ficaria parada — o modo
        mais silencioso possível de perder a fonte.
        """
        for eq in self.equacoes:
            for chave in eq.refs:
                with self.subTest(equacao=eq.nome, ref=chave):
                    self.assertIn(chave, metodo.REFERENCIAS)

    def test_nenhuma_equacao_fica_sem_fonte(self):
        for eq in self.equacoes:
            with self.subTest(equacao=eq.nome):
                self.assertTrue(eq.refs, "equação sem referência")

    def test_os_limiares_mostrados_sao_os_do_calculo(self):
        """Régua escrita à mão na tela envelhece calada.

        O dia em que a calibração local mexer em ``MCS_ATENCAO``, a janela tem
        de mudar junto — senão ela passa a documentar a régua de ontem, com a
        mesma convicção.
        """
        texto = " ".join(eq.limiares for eq in self.equacoes)
        self.assertIn(metodo._n(q.MCS_ATENCAO, 2), texto)
        self.assertIn(metodo._n(q.MUCGY_FALHA, 1), texto)
        self.assertIn(metodo._n(q.HI_FALHA, 3), texto)

    def test_o_fator_de_modulacao_esta_em_cGy(self):
        """O erro que o print de 02/09/2026 apontou: o rótulo dizia Gy."""
        nomes = [eq.nome for eq in self.equacoes]
        self.assertIn("UM/cGy — fator de modulação", nomes)


@unittest.skipIf(metodo is None, "PySide6 indisponível")
class TestJanela(unittest.TestCase):

    def test_a_janela_monta_e_cada_sigla_acha_a_sua_ancora(self):
        """O clique na sigla leva à referência — se a âncora não foi montada,
        ele não faz nada, e "não faz nada" é indistinguível de janela travada."""
        janela = metodo.JanelaMetodo()
        self.addCleanup(janela.deleteLater)
        self.assertEqual(janela.abas.count(), 3)
        for chave in metodo.REFERENCIAS:
            with self.subTest(ref=chave):
                self.assertIn(chave, janela._ancoras)
        janela.ir_para("icru83")
        self.assertEqual(janela.abas.currentIndex(), metodo.FONTES)

    def test_a_regua_curta_diz_o_essencial(self):
        """A frase que fica NA PÁGINA tem de bastar sozinha: quem não clicar em
        nada precisa saber com que régua o número foi medido."""
        curta = metodo.regua_curta()
        if q.CALIBRADO:
            self.assertIn("calibradas", curta)
        else:
            self.assertIn("LITERATURA", curta)
            self.assertIn("TG-218", curta)
        self.assertLess(len(curta), 200, "de volta ao parágrafo de cinco linhas")


from tests.limpeza_de_tela import load_tests  # noqa: E402,F401

if __name__ == "__main__":
    unittest.main()
