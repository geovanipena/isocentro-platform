"""Edição da Ficha: a ordem dos campos e a escolha da máquina.

Duas coisas que se digitavam ou não se mexiam, e as duas saem impressas.

A ORDEM dos campos era só a que a ficha decidia (a volta do gantry). Quando ela
não serve — e não serve sempre —, não havia como mudar sem editar o DICOM.

A MÁQUINA era campo livre. O texto dela é a IDENTIDADE do acelerador
(``constantes.identificar_maquina``), e dela saem o desenho da mesa, o
protocolo de imagem, o fluxo do SUS e o logo: um dígito trocado não dá erro
nenhum, só deixa de casar.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidgetItem  # noqa: E402

_APP = QApplication.instance() or QApplication([])

from isocentro.dominio import constantes  # noqa: E402
from isocentro.interface import edicao_ficha  # noqa: E402


def _feixes():
    """Três campos cuja ordem do TPS NÃO é a da volta do gantry.

    É o caso que separa as duas ordens; com elas coincidindo, o teste passaria
    sem testar nada.
    """
    return [
        {"numero": "1", "ordem_tps": 0, "gantry": 311.0, "energia_rotulo": "6X"},
        {"numero": "3", "ordem_tps": 2, "gantry": 0.0, "energia_rotulo": "6X"},
        {"numero": "2", "ordem_tps": 1, "gantry": 134.0, "energia_rotulo": "10X"},
    ]


class _ComDialogo(unittest.TestCase):
    RP: dict = {}
    FORM: dict = {}

    def setUp(self):
        self.dlg = edicao_ficha.DialogEdicaoFicha(dict(self.FORM), dict(self.RP))

    def tearDown(self):
        self.dlg.close()

    def _numeros_na_tela(self):
        return [self.dlg.tab_feixes.verticalHeaderItem(i).text()
                for i in range(self.dlg.tab_feixes.rowCount())]

    def _numeros_no_resultado(self):
        return [f.get("numero") for f in self.dlg.resultado()[1]["feixes"]]


class TestOrdemDosCampos(_ComDialogo):
    RP = {"feixes": _feixes(), "maquina": "600CD"}

    def test_a_tela_abre_na_ordem_que_recebeu(self):
        self.assertEqual(self._numeros_na_tela(),
                         ["Campo 1", "Campo 3", "Campo 2"])

    def test_subir_leva_o_campo_e_os_valores_dele(self):
        """O que se move é a LINHA inteira, não só o rótulo.

        Casar linha com feixe por POSIÇÃO era o que devolvia os valores de um
        campo dentro de outro — e eles vão impressos na tabela de campos.
        """
        self.dlg.tab_feixes.setCurrentCell(2, 0)
        self.dlg._mover_feixe(-1)
        self.assertEqual(self._numeros_na_tela(),
                         ["Campo 1", "Campo 2", "Campo 3"])
        self.assertEqual(self._numeros_no_resultado(), ["1", "2", "3"])
        feixes = self.dlg.resultado()[1]["feixes"]
        self.assertEqual([f["gantry"] for f in feixes], [311.0, 134.0, 0.0])
        self.assertEqual([f["energia_rotulo"] for f in feixes],
                         ["6X", "10X", "6X"])

    def test_descer_e_o_inverso(self):
        self.dlg.tab_feixes.setCurrentCell(0, 0)
        self.dlg._mover_feixe(+1)
        self.assertEqual(self._numeros_no_resultado(), ["3", "1", "2"])

    def test_nas_pontas_nao_faz_nada(self):
        """Subir a primeira linha não pode empurrá-la para fora da lista."""
        self.dlg.tab_feixes.setCurrentCell(0, 0)
        self.dlg._mover_feixe(-1)
        self.dlg.tab_feixes.setCurrentCell(2, 0)
        self.dlg._mover_feixe(+1)
        self.assertEqual(self._numeros_no_resultado(), ["1", "3", "2"])

    def test_sem_selecao_nao_faz_nada(self):
        self.dlg.tab_feixes.setCurrentCell(-1, -1)
        self.dlg._mover_feixe(-1)
        self.assertEqual(self._numeros_no_resultado(), ["1", "3", "2"])

    def test_ordem_do_tps(self):
        self.dlg._reordenar_por("tps")
        self.assertEqual(self._numeros_no_resultado(), ["1", "2", "3"])

    def test_ordem_do_gantry_desfaz(self):
        """Sem o caminho de volta, experimentar a outra ordem só se desfazia
        cancelando o diálogo — e levando junto o resto da edição."""
        self.dlg._reordenar_por("tps")
        self.dlg._reordenar_por("gantry")
        self.assertEqual(self._numeros_no_resultado(), ["1", "3", "2"])

    def test_reordenar_preserva_o_que_foi_corrigido(self):
        """Quem corrigiu um ângulo e depois reordenou não pode perder a correção."""
        col = [c[1] for c in edicao_ficha.DialogEdicaoFicha._FEIXE_COLS].index("um")
        self.dlg.tab_feixes.setItem(0, col, QTableWidgetItem("123"))
        self.dlg._reordenar_por("tps")
        feixes = self.dlg.resultado()[1]["feixes"]
        por_numero = {f["numero"]: f for f in feixes}
        self.assertEqual(por_numero["1"]["um"], 123.0)

    def test_a_ordem_do_gantry_segue_o_angulo_CORRIGIDO(self):
        """A ordem se lê da tela, não do plano: quem acabou de corrigir o
        gantry espera que a ordem siga o valor corrigido."""
        col = [c[1] for c in
               edicao_ficha.DialogEdicaoFicha._FEIXE_COLS].index("gantry")
        self.dlg.tab_feixes.setItem(0, col, QTableWidgetItem("5"))  # era 311
        self.dlg._reordenar_por("gantry")
        self.assertEqual(self._numeros_no_resultado(), ["3", "1", "2"])


class TestBotoesDeOrdem(_ComDialogo):
    """Botão aceso significa pronto — e este renumera campos no papel."""

    RP = {"feixes": _feixes(), "maquina": "600CD"}

    def test_sem_selecao_os_dois_ficam_apagados(self):
        self.dlg.tab_feixes.setCurrentCell(-1, -1)
        self.assertFalse(self.dlg._b_sobe.isEnabled())
        self.assertFalse(self.dlg._b_desce.isEnabled())

    def test_nas_pontas_apaga_o_que_nao_faria_nada(self):
        self.dlg.tab_feixes.setCurrentCell(0, 0)
        self.assertFalse(self.dlg._b_sobe.isEnabled())
        self.assertTrue(self.dlg._b_desce.isEnabled())
        self.dlg.tab_feixes.setCurrentCell(2, 0)
        self.assertTrue(self.dlg._b_sobe.isEnabled())
        self.assertFalse(self.dlg._b_desce.isEnabled())

    def test_o_motivo_fica_no_tooltip(self):
        self.dlg.tab_feixes.setCurrentCell(0, 0)
        self.assertIn("primeiro", self.dlg._b_sobe.toolTip())

    def test_mover_reacende_conforme_a_nova_posicao(self):
        self.dlg.tab_feixes.setCurrentCell(1, 0)
        self.dlg._mover_feixe(-1)
        self.assertFalse(self.dlg._b_sobe.isEnabled())


class TestSemFeixes(_ComDialogo):
    """Ficha sem plano RP não tem o que reordenar — e não pode quebrar."""

    RP = {"maquina": "600CD"}

    def test_nao_quebra(self):
        self.dlg._mover_feixe(-1)
        self.dlg._reordenar_por("tps")
        self.assertNotIn("feixes", self.dlg.resultado()[1])


class TestMaquinaEmLista(unittest.TestCase):
    def _combo(self, maquina):
        dlg = edicao_ficha.DialogEdicaoFicha({"maquina": maquina},
                                             {"maquina": maquina})
        self.addCleanup(dlg.close)
        return dlg

    def _opcoes(self, dlg):
        return [(dlg.maquina.itemText(i), dlg.maquina.itemData(i))
                for i in range(dlg.maquina.count())]

    def test_mostra_o_nome_do_servico_e_grava_o_de_fabrica(self):
        """O registro e o casamento seguem no nome de fábrica; só a tela muda."""
        dlg = self._combo("TBuniverSN1002")
        self.assertEqual(dlg.maquina.currentText(), "TrueBeam")
        self.assertEqual(dlg.resultado()[1]["maquina"], "TBuniverSN1002")

    def test_so_as_maquinas_da_unidade(self):
        """A ficha da Clinica não oferece o Synergy, e a do SAT só oferece ele."""
        clinica = [d for _t, d in self._opcoes(self._combo("600CD"))]
        self.assertNotIn("Synergy01", clinica)
        self.assertIn("TBuniverSN1002", clinica)
        sat = [d for _t, d in self._opcoes(self._combo("Synergy01"))]
        self.assertEqual(sat, ["Synergy01"])

    def test_maquina_desconhecida_nao_some(self):
        """Acervo antigo, nome com prefixo de sala, caso de fora: o combo não
        pode trocar calado a máquina de uma ficha que já existe."""
        for nome in ("Sala2-TBuniverSN1002", "MaquinaQueNaoExiste"):
            with self.subTest(nome=nome):
                dlg = self._combo(nome)
                self.assertEqual(dlg.resultado()[1]["maquina"], nome)

    def test_sem_maquina_o_combo_nao_inventa_uma(self):
        """Campo que se preenche sozinho com o primeiro da lista é dado
        inventado — e a máquina decide mesa, imagem, SUS e logo."""
        dlg = self._combo("")
        self.assertEqual(dlg.resultado()[1]["maquina"], "")

    def test_a_escolha_vale(self):
        dlg = self._combo("600CD")
        i = dlg.maquina.findData("6EX")
        self.assertGreaterEqual(i, 0)
        dlg.maquina.setCurrentIndex(i)
        self.assertEqual(dlg.resultado()[1]["maquina"], "6EX")
        self.assertEqual(
            constantes.identificar_maquina(dlg.resultado()[1]["maquina"]).chave,
            "6EX")


# A janela fica viva enquanto o ``unittest`` segurar o TestCase; sem a limpeza,
# ``estilo._ouvintes`` só cresce — ver ``tests/limpeza_de_tela.py``.
from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


if __name__ == "__main__":
    unittest.main()
