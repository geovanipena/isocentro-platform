"""Ordem dos campos na ficha: a volta do gantry, não a numeração do TPS.

Quem monta o tratamento acompanha o braço girando. Lida por ``BeamNumber``, a
tabela obrigava a saltar de 270° para 30° e voltar — e é nesse vaivém que se
confere um campo duas vezes e outro nenhuma.

A volta começa em **181°** e termina em **180°**: uma volta inteira no sentido
horário a partir de logo depois do "por baixo do paciente". A exceção é a
**mama direita**, que o serviço monta no sentido anti-horário.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dicom import dicom_rt  # noqa: E402


def _feixes(*pares) -> list[dict]:
    """``(numero, gantry)`` → lista de feixes como o ``parse_rtplan`` monta."""
    return [{"numero": n, "gantry": g} for n, g in pares]


def _angulos(feixes) -> list:
    return [f["gantry"] for f in feixes]


def _numeros(feixes) -> list:
    return [f["numero"] for f in feixes]


class TestVoltaHoraria(unittest.TestCase):

    def test_comeca_em_181_e_termina_em_180(self):
        ordem = dicom_rt.ordenar_feixes(
            _feixes((1, 0), (2, 90), (3, 180), (4, 181), (5, 270), (6, 359)))
        self.assertEqual(_angulos(ordem), [181, 270, 359, 0, 90, 180])

    def test_a_ancora_e_fixa_e_nao_deduzida_dos_angulos(self):
        """Dois planos do mesmo paciente têm de sair na mesma ordem.

        Se o começo fosse deduzido do maior vão entre os feixes presentes, um
        plano de 4 campos e outro de 3 poderiam começar em pontos diferentes da
        volta — e a tabela de um se leria ao contrário da do outro.
        """
        quatro = dicom_rt.ordenar_feixes(_feixes((1, 200), (2, 300), (3, 40), (4, 120)))
        tres = dicom_rt.ordenar_feixes(_feixes((1, 300), (2, 40), (3, 120)))
        self.assertEqual(_angulos(quatro), [200, 300, 40, 120])
        self.assertEqual(_angulos(tres), [300, 40, 120])

    def test_cruzar_o_zero_nao_quebra_a_varredura(self):
        """350° → 10° → 30° é uma varredura contínua, não um salto de 340°."""
        ordem = dicom_rt.ordenar_feixes(_feixes((1, 30), (2, 350), (3, 10)))
        self.assertEqual(_angulos(ordem), [350, 10, 30])

    def test_180_e_o_ultimo_e_181_o_primeiro(self):
        ordem = dicom_rt.ordenar_feixes(_feixes((1, 180), (2, 181)))
        self.assertEqual(_angulos(ordem), [181, 180])

    def test_empate_de_angulo_desempata_pelo_numero(self):
        """Dois campos no mesmo gantry não podem depender de como o arquivo
        DICOM foi escrito."""
        ordem = dicom_rt.ordenar_feixes(_feixes((3, 90), (1, 90), (2, 90)))
        self.assertEqual(_numeros(ordem), [1, 2, 3])

    def test_feixe_sem_angulo_vai_para_o_fim(self):
        """Sem ângulo não há lugar na volta — mas o campo não pode sumir."""
        ordem = dicom_rt.ordenar_feixes(_feixes((1, 90), (2, None), (3, 10)))
        self.assertEqual(_angulos(ordem), [10, 90, None])

    def test_nenhum_feixe_se_perde_nem_se_duplica(self):
        entrada = _feixes((1, 0), (2, 181), (3, None), (4, 95), (5, 180))
        ordem = dicom_rt.ordenar_feixes(entrada)
        self.assertEqual(len(ordem), len(entrada))
        self.assertEqual({id(f) for f in ordem}, {id(f) for f in entrada})

    def test_angulo_fracionario(self):
        ordem = dicom_rt.ordenar_feixes(_feixes((1, 180.5), (2, 181.5)))
        self.assertEqual(_angulos(ordem), [181.5, 180.5])

    def test_lista_vazia(self):
        self.assertEqual(dicom_rt.ordenar_feixes([]), [])


class TestMamaDireita(unittest.TestCase):
    """A exceção anti-horária, reconhecida pelo rótulo do plano."""

    def test_inverte_a_volta(self):
        pares = _feixes((1, 0), (2, 90), (3, 180), (4, 181), (5, 270))
        horario = _angulos(dicom_rt.ordenar_feixes(pares))
        anti = _angulos(dicom_rt.ordenar_feixes(pares, "MAMA D 40.05Gy@15fr"))
        self.assertEqual(anti, list(reversed(horario)))
        self.assertEqual(anti, [180, 90, 0, 270, 181])

    def test_sem_angulo_continua_no_fim_mesmo_invertendo(self):
        """Inverter a lista inteira jogaria o feixe sem ângulo para a frente."""
        ordem = dicom_rt.ordenar_feixes(
            _feixes((1, 90), (2, None), (3, 10)), "MAMA D")
        self.assertEqual(_angulos(ordem), [90, 10, None])

    def test_reconhece_as_escritas_do_servico(self):
        for rotulo in ("MAMA D 40.05Gy@15fr", "MAMA DIREITA", "MAMA_D",
                       "mama dir 15fr", "Mama Direito", "MAMA D + FSC D"):
            self.assertTrue(dicom_rt.mama_direita(rotulo), rotulo)

    def test_mama_esquerda_nao_inverte(self):
        """O "d" solto dentro de "esquerda" faria toda mama esquerda sair ao
        contrário — que é o plano mais comum dos dois."""
        for rotulo in ("MAMA E 40Gy", "MAMA ESQUERDA", "MAMA_E", "mama esq"):
            self.assertFalse(dicom_rt.mama_direita(rotulo), rotulo)

    def test_outro_sitio_a_direita_nao_inverte(self):
        """A exceção é da mama, não da lateralidade."""
        for rotulo in ("PULMAO D 27Gy@3fr", "FEMUR D", "PAROTIDA D"):
            self.assertFalse(dicom_rt.mama_direita(rotulo), rotulo)

    def test_mama_sem_lado_nao_inverte(self):
        for rotulo in ("MAMA", "MAMA 40Gy@15fr", "iCP_11C", ""):
            self.assertFalse(dicom_rt.mama_direita(rotulo), rotulo)

    def test_rotulo_ausente_nao_quebra(self):
        self.assertFalse(dicom_rt.mama_direita(None))
        ordem = dicom_rt.ordenar_feixes(_feixes((1, 90), (2, 10)))
        self.assertEqual(_angulos(ordem), [10, 90])


class TestDoseAltaSegueOTPS(unittest.TestCase):
    """Acima de 600 cGy por fração, a ordem dos campos é a que o TPS deu.

    Pedido do usuário em 31/08/2026. Em hipofracionamento a sequência dos
    campos é parte do plano — reordená-la pela volta do gantry faria a ficha
    discordar do console justamente na classe de caso em que a ordem importa.
    """

    def _com_tps(self, *trios):
        """``(numero, gantry, ordem_tps)`` → feixes como o parse os monta."""
        return [{"numero": n, "gantry": g, "ordem_tps": o} for n, g, o in trios]

    def test_acima_de_600_cgy_vale_a_ordem_do_tps(self):
        feixes = self._com_tps((1, 90, 0), (2, 10, 1), (3, 200, 2))
        ordem = dicom_rt.ordenar_feixes(feixes, "", dose_fracao=7.0)
        self.assertEqual(_numeros(ordem), [1, 2, 3])

    def test_ate_600_cgy_segue_a_volta_do_gantry(self):
        """600 exatos ainda é a volta do gantry: o pedido foi ACIMA de 600."""
        feixes = self._com_tps((1, 90, 0), (2, 10, 1), (3, 200, 2))
        ordem = dicom_rt.ordenar_feixes(feixes, "", dose_fracao=6.0)
        self.assertEqual(_angulos(ordem), [200, 10, 90])

    def test_sem_dose_nada_muda(self):
        """``None`` é "não sei" — e não é motivo para trocar a ordem de sempre."""
        feixes = self._com_tps((1, 90, 0), (2, 10, 1))
        self.assertEqual(_angulos(dicom_rt.ordenar_feixes(feixes)), [10, 90])
        self.assertEqual(
            _angulos(dicom_rt.ordenar_feixes(feixes, "", dose_fracao=None)),
            [10, 90])

    def test_limite(self):
        self.assertFalse(dicom_rt.ordem_e_do_tps(6.0))
        self.assertTrue(dicom_rt.ordem_e_do_tps(6.01))
        self.assertTrue(dicom_rt.ordem_e_do_tps(20.0))
        for nao in (None, "", "abc"):
            self.assertFalse(dicom_rt.ordem_e_do_tps(nao), nao)

    def test_mama_direita_nao_inverte_a_ordem_do_tps(self):
        """A inversão é da leitura do braço; a ordem do TPS não se lê assim."""
        feixes = self._com_tps((1, 90, 0), (2, 10, 1))
        ordem = dicom_rt.ordenar_feixes(feixes, "MAMA D 24Gy@3fr", dose_fracao=8.0)
        self.assertEqual(_numeros(ordem), [1, 2])

    def test_feixe_sem_marca_do_tps_vai_para_o_fim(self):
        """Registro JSON antigo não tem ``ordem_tps`` — e não pode sumir."""
        feixes = [{"numero": 2, "gantry": 10, "ordem_tps": 1},
                  {"numero": 9, "gantry": 40},
                  {"numero": 1, "gantry": 90, "ordem_tps": 0}]
        self.assertEqual(_numeros(dicom_rt.ordem_do_tps(feixes)), [1, 2, 9])


if __name__ == "__main__":
    unittest.main()
