"""Mama + FSC entram JUNTAS na sessão — e a ficha sai em soma.

Mama e fossa supraclavicular são campos do mesmo tratamento, irradiados na
mesma sessão. O padrão do agendamento era sequencial (que serve para
fase→boost) e descrevia esse caso errado: alguém tinha de trocar para
Simultâneo e marcar "soma" à mão em todo paciente de mama com FSC.

É SEMENTE, não trava: os botões de modelo continuam ali, e um agendamento já
salvo manda sobre o padrão.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dominio import agendamento as ag  # noqa: E402


class TestReconhecerMamaComFSC(unittest.TestCase):

    def test_dois_planos_mama_e_fsc(self):
        self.assertTrue(ag.mama_com_fsc(["1 Mama E", "2 FSC E"]))
        self.assertTrue(ag.mama_com_fsc(["1 PTV_Mama D", "2 PTV_FSC D"]))

    def test_escrito_por_extenso_e_com_acento(self):
        """Rótulo é texto digitado: cada um escreve de um jeito."""
        self.assertTrue(ag.mama_com_fsc(
            ["Mama esquerda", "Fossa supraclavicular esquerda"]))

    def test_com_boost_junto_continua_valendo(self):
        self.assertTrue(ag.mama_com_fsc(["Mama D", "FSC D", "Boost D"]))

    def test_mama_com_boost_nao_e_o_caso(self):
        """Fase e boost são sequenciais de verdade — não pode virar simultâneo."""
        self.assertFalse(ag.mama_com_fsc(["1 Mama E", "2 Boost E"]))

    def test_um_plano_so_chamado_mama_mais_fsc(self):
        """Traz as duas palavras e não precisa de agendamento nenhum: já é uma
        sessão. Exigir planos DIFERENTES é o que separa os dois casos."""
        self.assertFalse(ag.mama_com_fsc(["Mama + FSC 40Gy"]))
        self.assertFalse(ag.mama_com_fsc(["1 Mama+FSC", "2 Boost"]))

    def test_nada_a_ver(self):
        self.assertFalse(ag.mama_com_fsc(["1 Prostata", "2 Boost"]))
        self.assertFalse(ag.mama_com_fsc([]))

    def test_palavra_dentro_de_outra_nao_conta(self):
        """Casamento por TOKEN, não por "contém" — mesmo critério do
        ``dicom_rt.mama_direita``, e pela mesma razão."""
        self.assertFalse(ag.mama_com_fsc(["Mamaria interna", "Boost"]))


class TestOAgendamentoQueSaiDisso(unittest.TestCase):

    def test_simultaneo_junta_os_planos_em_toda_fracao(self):
        etapas = ag.modelo_simultaneo([25, 25])
        self.assertEqual(etapas, [{"planos": [0, 1], "fracoes": 25}])
        seq = ag.sequencia_de_etapas(etapas)
        self.assertEqual(len(seq), 25)
        self.assertTrue(all(linha == [0, 1] for linha in seq))

    def test_cada_plano_recebe_todas_as_fracoes(self):
        """No simultâneo os dois campos entram na MESMA sessão: 25 frações de
        tratamento, 25 para cada plano — não 50 dias."""
        etapas = ag.modelo_simultaneo([25, 25])
        self.assertEqual(ag.fracoes_por_plano(etapas, 2), [25, 25])

    def test_o_sequencial_somaria_os_dias(self):
        """O contraste que motivou a mudança: sequencial dá 50 dias de
        tratamento para o que se entrega em 25."""
        etapas = ag.modelo_sequencial([25, 25])
        self.assertEqual(len(ag.sequencia_de_etapas(etapas)), 50)


if __name__ == "__main__":
    unittest.main()
