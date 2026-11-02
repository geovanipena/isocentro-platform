"""A aba Qualidade na tela — o que ela mostrava de errado.

Importa o Qt em modo headless; pula o arquivo inteiro se o PyQt5 não estiver
presente, como os outros testes de tela deste projeto.

Rodar:  python -m unittest tests.test_qualidade_tela -v
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
    from isocentro.interface import fichinha  # noqa: E402
    from isocentro.dominio import qualidade as q  # noqa: E402
    from isocentro.dominio import qualidade_metodo  # noqa: E402
    from isocentro.interface import qualidade_tela  # noqa: E402
except Exception as exc:  # noqa: BLE001
    qualidade_tela = None
    _MOTIVO = str(exc)


def _plano(rotulo: str, dose_total=None) -> dict:
    """Um plano do app sem DICOM nenhum.

    É o caso incompleto de propósito: a aba tem de continuar montando a tela e
    dizendo o que falta, em vez de abortar. Um caso com RT Dose de verdade é
    coberto pelo ``tests/test_qualidade.py``, que não precisa de janela.
    """
    return {"rotulo": rotulo, "rp": {"dose_total": dose_total},
            "rp_ds": None, "rs_ds": None, "rd_ds": None}


@unittest.skipIf(qualidade_tela is None, "PySide6 indisponível")
class TestPainelQualidade(unittest.TestCase):

    def setUp(self):
        self.painel = qualidade_tela.PainelQualidade()
        self.addCleanup(self.painel.deleteLater)

    def test_sem_caso_a_tela_diz_o_que_fazer(self):
        """Seis cartões em branco não dizem que falta abrir a pasta."""
        self.painel.definir_planos([], False, "")
        self.assertTrue(self.painel.lbl_vazio.isVisibleTo(self.painel))
        self.assertFalse(self.painel.bloco_resumo.isVisibleTo(self.painel))
        self.assertFalse(self.painel.cmb_plano.isEnabled())

    def test_com_caso_a_frase_de_vazio_some(self):
        self.painel.definir_planos([_plano("P1", 60.0)], False, "Fulano")
        self.assertFalse(self.painel.lbl_vazio.isVisibleTo(self.painel))
        self.assertTrue(self.painel.bloco_resumo.isVisibleTo(self.painel))
        self.assertEqual(self.painel.lbl_paciente.text(), "Fulano")

    def test_a_soma_so_aparece_com_dois_planos_na_mesma_tc(self):
        """Somar grades de tomografias diferentes dá um cubo que não
        corresponde a paciente nenhum — a opção não pode nem existir."""
        um = [_plano("P1", 60.0)]
        dois = [_plano("P1", 46.0), _plano("P2", 14.0)]
        self.painel.definir_planos(um, True, "")
        self.assertNotIn("Soma dos planos", self._itens())
        self.painel.definir_planos(dois, False, "")
        self.assertNotIn("Soma dos planos", self._itens())
        self.painel.definir_planos(dois, True, "")
        self.assertIn("Soma dos planos", self._itens())

    def _itens(self):
        return [self.painel.cmb_plano.itemText(i)
                for i in range(self.painel.cmb_plano.count())]

    def test_trocar_de_plano_nao_deixa_nota_velha_na_tela(self):
        """``deleteLater`` não entrega antes do próximo desenho.

        O widget agendado só morre quando o laço de eventos processa o
        ``DeferredDelete``, e trocar de plano no seletor repovoa as notas antes
        disso: as antigas continuavam vivas e desenhavam por cima do cartão. No
        TC8 sobrava um retângulo branco ao lado da nota e o título do cartão
        sumia. É a mesma armadilha registrada no CLAUDE.md para os testes — e
        ela também morde em produção.
        """
        self.painel.definir_planos([_plano("P1", 60.0), _plano("P2", 14.0)],
                                   False, "")
        self.painel.ao_abrir()
        antes = self.painel.lay_notas.count()
        self.painel.cmb_plano.setCurrentIndex(1)
        self.assertEqual(self.painel.lay_notas.count(), antes,
                         "as notas do plano anterior continuaram no layout")

    def test_caso_incompleto_ainda_monta_a_tela(self):
        """Sem RT Dose a aba não pode ficar vazia: é onde ela mais serviria."""
        self.painel.definir_planos([_plano("P1")], False, "")
        self.painel.ao_abrir()
        self.assertGreater(self.painel.lay_notas.count(), 0)
        self.assertEqual(self.painel.tab_alvos.rowCount(), 0)

    def test_o_aviso_da_regua_esta_na_tela_enquanto_nao_houver_calibracao(self):
        """Reserva usada é reserva anunciada. Um "fora da faixa" medido com
        régua da literatura não pode se parecer com um veredito da clínica."""
        texto = self.painel.lbl_regua.text()
        if q.CALIBRADO:
            self.assertIn("calibradas", texto)
        else:
            self.assertIn("LITERATURA", texto)
            self.assertIn("TG-218", texto)

    def test_as_referencias_estao_a_um_clique(self):
        """Elas são a régua. Fora da tela, um limiar vira opinião do programa.

        Saíram do fim da página — nove parágrafos permanentes para uma consulta
        eventual — e viraram botão na faixa. O que este teste guarda é que a
        PORTA existe e que ela abre na aba certa: uma referência que ninguém
        alcança é o mesmo que referência nenhuma.
        """
        fontes = [curta for curta, *_ in qualidade_metodo.REFERENCIAS.values()]
        self.assertTrue(any("TG-218" in f for f in fontes))
        self.assertTrue(any("ICRU 83" in f for f in fontes))
        self.assertTrue(any("Masi" in f for f in fontes))

        self.painel.abrir_metodo(qualidade_metodo.FONTES)
        self.addCleanup(self.painel._metodo.deleteLater)
        self.assertEqual(self.painel._metodo.abas.currentIndex(),
                         qualidade_metodo.FONTES)

    def test_a_janela_do_metodo_e_uma_so(self):
        """Ela nasce no primeiro clique e é reaproveitada: cada montagem
        registra ~90 ouvintes de dia↔noite, e a lista é do processo."""
        self.painel.abrir_metodo(qualidade_metodo.EQUACOES)
        primeira = self.painel._metodo
        self.addCleanup(primeira.deleteLater)
        self.painel.abrir_metodo(qualidade_metodo.REGUA)
        self.assertIs(self.painel._metodo, primeira)
        self.assertEqual(primeira.abas.currentIndex(), qualidade_metodo.REGUA)

    def test_o_fator_de_modulacao_sai_em_UM_por_cGy(self):
        """O rótulo dizia MU/Gy e o número saía 325.

        1 UM entrega ~1 cGy na condição de referência: em UM/cGy o mesmo plano
        é 3,25 — "três vezes o que um campo aberto gastaria" —, que é como o
        físico lê o fator de modulação. Foi o primeiro item do print de
        02/09/2026.
        """
        an = q.AnaliseQualidade(rotulo="P1", mu_total=2355.0,
                                mu_cgy=q.mu_por_cgy(2355.0, 7.25))
        self.painel._pintar(an)
        # A unidade vai no VALOR, e não no rótulo: ``ui.Valor`` põe o rótulo em
        # caixa alta, e "UM/CGY" não é unidade nenhuma — cGy é centigray.
        self.assertEqual(self.painel.val_mucgy.rot.text(), "MODULAÇÃO")
        self.assertEqual(self.painel.val_mucgy.texto(), "3,25 UM/cGy")


@unittest.skipIf(qualidade_tela is None, "PySide6 indisponível")
class TestModoNaFaixa(unittest.TestCase):
    """A aba entrou no FIM da PILHA em 08/09/2026, e a ordem do empilhamento É
    o índice — não mais a última: a Agenda entrou depois dela (23/09/2026) e
    ocupa o índice seguinte. O contrato real é o índice FIXO, não "o maior".

    Pôr um modo no meio renumeraria os que vêm depois, e ``MODO_CAPA`` passaria
    a apontar para outra tela — sem erro nenhum, só a tela errada.
    """

    def test_o_indice_e_o_da_pilha(self):
        self.assertEqual(fichinha.MODO_QUALIDADE, 4)

    def test_so_fisico_e_admin_veem(self):
        """Reprovar um plano é decisão de física médica. E, com as tolerâncias
        ainda sem calibração local, quem não é físico não pode ser posto na
        posição de responder por um "fora da faixa"."""
        for papel in ("fisico", "admin"):
            self.assertIn(fichinha.MODO_QUALIDADE,
                          fichinha.modos_do_papel(papel), papel)
        for papel in ("medico", "dosimetrista", "tecnico", "recepcionista"):
            self.assertNotIn(fichinha.MODO_QUALIDADE,
                             fichinha.modos_do_papel(papel), papel)

    def test_papel_vazio_continua_vendo_tudo(self):
        """Janela aberta sem login (teste, e qualquer fluxo que não passe pela
        tela de entrada) não tem função para recortar."""
        self.assertIn(fichinha.MODO_QUALIDADE, fichinha.modos_do_papel(""))


from tests.limpeza_de_tela import load_tests  # noqa: E402,F401

if __name__ == "__main__":
    unittest.main()
