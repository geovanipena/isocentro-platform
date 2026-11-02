"""Seleção de físico/médico a partir das tags do RTPLAN.

Cenários tirados dos RTPLAN reais (TCs_Teste): o físico vem de ``OperatorsName``
(quem elaborou o plano no TPS), com prioridade sobre ``ReviewerName`` (quem
aprovou — às vezes é o médico).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import equipe
from isocentro.dicom import dicom_rt as dr

_LISTAS = {"fisicos": equipe.FISICOS, "medicos": equipe.MEDICOS}


class TestSelecionarFisico(unittest.TestCase):
    def test_operators_fisico_conhecido(self):
        # TC10: OperatorsName e ReviewerName são o mesmo físico.
        self.assertEqual(
            dr._selecionar_fisico(operators="Geovani Pires Pena",
                                  reviewer="Geovani Pires Pena", **_LISTAS),
            "Geovani Pires Pena")

    def test_operators_tem_prioridade_sobre_revisor(self):
        # TC5: quem ELABOROU (OperatorsName) foi Plinio Henrique — ainda fora da
        # lista canônica; quem aprovou (ReviewerName) foi Geovani. A ficha deve
        # trazer o autor do plano, não o aprovador.
        self.assertEqual(
            dr._selecionar_fisico(operators="Plinio Henrique Dias Coelho",
                                  reviewer="Geovani Pires Pena", **_LISTAS),
            "Plinio Henrique Dias Coelho")

    def test_revisor_medico_e_ignorado(self):
        # TC1: ReviewerName é o médico (Jean); o físico é o OperatorsName.
        self.assertEqual(
            dr._selecionar_fisico(operators="Geovani Pires Pena",
                                  reviewer="Jean Teixeira de Prado", **_LISTAS),
            "Geovani Pires Pena")

    def test_sem_operators_cai_no_revisor_se_fisico(self):
        self.assertEqual(
            dr._selecionar_fisico(operators="", reviewer="Nathalia Bittencourt", **_LISTAS),
            "Nathalia Bittencourt")

    def test_operators_medico_nao_vaza_para_fisico(self):
        # Guarda: um nome de médico em OperatorsName não deve virar "físico".
        self.assertEqual(
            dr._selecionar_fisico(operators="Jean Teixeira de Prado", reviewer="", **_LISTAS),
            "")

    def test_operators_login_ou_iniciais_cai_no_revisor(self):
        # OperatorsName com login/iniciais (1 token, ex.: "QA") não é nome: cai no
        # revisor se este for um físico conhecido.
        self.assertEqual(
            dr._selecionar_fisico(operators="QA", reviewer="Geovani Pires Pena", **_LISTAS),
            "Geovani Pires Pena")

    def test_operators_login_sem_revisor_fica_vazio(self):
        self.assertEqual(dr._selecionar_fisico(operators="QA", reviewer="", **_LISTAS), "")

    def test_sem_nenhum_nome(self):
        self.assertEqual(dr._selecionar_fisico(operators="", reviewer="", **_LISTAS), "")


class TestSelecionarMedico(unittest.TestCase):
    def test_casa_lista_canonica_formato_caret(self):
        # PhysiciansOfRecord vem "Sobrenome^Nome".
        self.assertEqual(dr._selecionar_medico("Teixeira de Prado^Jean", medicos=equipe.MEDICOS),
                         "Jean Teixeira de Prado")

    def test_desconhecido_devolve_nome_formatado(self):
        # PersonName real ("Família^Nome") é reordenado para a ordem natural.
        from pydicom.valuerep import PersonName
        self.assertEqual(dr._selecionar_medico(PersonName("Fulano^Beltrano"), medicos=equipe.MEDICOS),
                         "Beltrano Fulano")


class TestListasSaoObrigatorias(unittest.TestCase):
    """As listas moram em ``dados.equipe`` e o leitor do plano as recebe por
    parâmetro. Com um padrão vazio, quem esquecesse de passá-las teria um
    físico em branco na ficha sem erro nenhum na tela; sem padrão, é
    TypeError na primeira execução."""

    def test_agrupar_planos_sem_equipe_recusa(self):
        with self.assertRaises(TypeError):
            dr.agrupar_planos([], [], [])

    def test_parse_rtplan_sem_equipe_recusa(self):
        from pydicom.dataset import Dataset
        with self.assertRaises(TypeError):
            dr.parse_rtplan(Dataset())

    def test_completar_equipe_sem_equipe_recusa(self):
        with self.assertRaises(TypeError):
            dr.completar_equipe({"fisico": ""}, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
