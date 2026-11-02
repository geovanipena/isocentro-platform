"""Constantes de domínio: identificação de máquina e equivalência com a
lógica antiga (imagem da mesa e sinal do deslocamento vertical).

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dominio import constantes  # noqa: E402
from isocentro.dicom import dicom_rt  # noqa: E402


class TestImagemDiariaPorDose(unittest.TestCase):
    """A mama fast-forward saía da carga com imagem SEMANAL.

    A frequência vinha só do protocolo da máquina, e a 600CD, a 6EX e o
    TrueBeamSN1001 são semanais: 26 Gy em 5 frações (520 cGy/fr) ia para a sala
    conferido duas vezes em cinco.
    """

    def test_fast_forward_entra_e_paliativo_convencional_nao(self):
        self.assertTrue(constantes.imagem_diaria_por_dose(520))
        self.assertTrue(constantes.imagem_diaria_por_dose(501))
        # 500 cGy/fr é o paliativo de 20 Gy em 4, que segue a máquina.
        self.assertFalse(constantes.imagem_diaria_por_dose(500))
        self.assertFalse(constantes.imagem_diaria_por_dose(180))

    def test_dose_ilegivel_nao_aplica_a_regra(self):
        """Sem dose não há regra; o protocolo da máquina continua valendo."""
        for valor in (None, "", "abc", 0):
            self.assertFalse(constantes.imagem_diaria_por_dose(valor), valor)


class TestFracionamentoDaPrescricao(unittest.TestCase):
    """O fracionamento era digitado em toda ficha; a prescrição já o diz."""

    def test_traduz_o_vocabulario_do_aria(self):
        for freq, esperado in (("Uma Vez por Dia", "1x dia"),
                               ("once daily", "1x dia"),
                               ("Dias Alternados", "Dias alter."),
                               ("dias alternado", "Dias alter."),
                               ("Duas Vezes por Semana", "2x sem."),
                               ("Aplicação Única", "Única")):
            self.assertEqual(constantes.fracionamento_da_frequencia(freq),
                             esperado, freq)

    def test_o_que_a_ficha_nao_tem_fica_vazio(self):
        """"Duas vezes por dia" não existe na ficha: escolher a opção mais
        parecida imprimiria um ritmo que ninguém prescreveu."""
        self.assertEqual(
            constantes.fracionamento_da_frequencia("Duas Vezes por Dia"), "")
        self.assertEqual(constantes.fracionamento_da_frequencia(""), "")
        self.assertEqual(constantes.fracionamento_da_frequencia(None), "")

    def test_o_que_sai_e_opcao_da_ficha(self):
        """Tradução que devolvesse texto fora da lista sairia impressa assim."""
        for freq in ("Uma Vez por Dia", "Dias Alternados", "Aplicação Única"):
            self.assertIn(constantes.fracionamento_da_frequencia(freq),
                          constantes.OPCOES_FRACIONAMENTO)


class TestIdentificarMaquina(unittest.TestCase):
    def test_casa_por_substring_sem_caixa(self):
        for texto, chave in (("TrueBeamSN1001", "TrueBeamSN1001"),
                              ("truebeamsn1001", "TrueBeamSN1001"),
                              ("Sala2-TrueBeamSN1001", "TrueBeamSN1001"),
                              ("TBuniverSN1002", "TBuniverSN1002"),
                              ("600CD", "600CD"), ("6EX", "6EX")):
            m = constantes.identificar_maquina(texto)
            self.assertIsNotNone(m, texto)
            self.assertEqual(m.chave, chave)

    def test_desconhecida_e_vazio(self):
        self.assertIsNone(constantes.identificar_maquina("Halcyon"))
        self.assertIsNone(constantes.identificar_maquina(""))
        self.assertIsNone(constantes.identificar_maquina(None))


class TestMesaVertSign(unittest.TestCase):
    """Equivalência exata com a regra antiga: -1 só para 6EX/600CD."""

    def _antigo(self, maquina: str) -> float:
        m = (maquina or "").upper()
        return -1.0 if any(x in m for x in ("6EX", "600CD")) else 1.0

    def test_equivale_ao_antigo(self):
        for maq in ("6EX", "600CD", "TrueBeamSN1001", "TBuniverSN1002",
                    "sala 600CD", "6ex", "", "Halcyon", None):
            self.assertEqual(dicom_rt._mesa_vert_sign(maq or ""),
                             self._antigo(maq or ""), repr(maq))

    def test_invertidas(self):
        self.assertEqual(dicom_rt._mesa_vert_sign("6EX"), -1.0)
        self.assertEqual(dicom_rt._mesa_vert_sign("600CD"), -1.0)
        self.assertEqual(dicom_rt._mesa_vert_sign("TrueBeamSN1001"), 1.0)


class TestMesaAnguloConsole(unittest.TestCase):
    def test_serie_c_usa_escala_varian(self):
        # 600CD/6EX: console mostra 360 - IEC (ex.: 315→45, 295→65, 270→90).
        for maq in ("600CD", "6EX"):
            self.assertEqual(dicom_rt._mesa_angulo_console(315, maq), 45.0, maq)
            self.assertEqual(dicom_rt._mesa_angulo_console(295, maq), 65.0, maq)
            self.assertEqual(dicom_rt._mesa_angulo_console(270, maq), 90.0, maq)
            self.assertEqual(dicom_rt._mesa_angulo_console(45, maq), 315.0, maq)
            self.assertEqual(dicom_rt._mesa_angulo_console(0, maq), 0.0, maq)

    def test_outras_maquinas_mantem_iec(self):
        for maq in ("TrueBeamSN1001", "TBuniverSN1002", ""):
            self.assertEqual(dicom_rt._mesa_angulo_console(315, maq), 315, maq)

    def test_none(self):
        self.assertIsNone(dicom_rt._mesa_angulo_console(None, "600CD"))


class TestMordentes(unittest.TestCase):
    """X1/Y1 saem com o sinal trocado (abertura a partir do eixo); X2/Y2 como
    estão. Um mordente que ultrapassa o eixo central fica NEGATIVO na ficha."""

    @staticmethod
    def _cp(x=None, y=None):
        from pydicom.dataset import Dataset
        cp = Dataset()
        seq = []
        for tipo, pos in (("ASYMX", x), ("ASYMY", y)):
            if pos is not None:
                d = Dataset()
                d.RTBeamLimitingDeviceType = tipo
                d.LeafJawPositions = list(pos)
                seq.append(d)
        cp.BeamLimitingDevicePositionSequence = seq
        return cp

    def test_campo_normal_sai_positivo(self):
        # 10×10 simétrico: DICOM [-50, +50] mm → 5,0 de cada lado.
        jaws = dicom_rt._mordentes(self._cp(x=[-50.0, 50.0], y=[-50.0, 50.0]))
        self.assertEqual(jaws, {"x1": 5.0, "x2": 5.0, "y1": 5.0, "y2": 5.0})

    def test_over_travel_mantem_o_sinal_negativo(self):
        # Regressão (6EX): X1 que cruza o eixo central vem POSITIVO no DICOM e o
        # console mostra −0,1. O abs() de antes imprimia 0,1, invertendo o lado.
        jaws = dicom_rt._mordentes(self._cp(x=[1.0, 52.0], y=[-45.0, -3.0]))
        self.assertEqual(jaws["x1"], -0.1)
        self.assertEqual(jaws["x2"], 5.2)
        self.assertEqual(jaws["y1"], 4.5)
        self.assertEqual(jaws["y2"], -0.3)   # Y2 também cruzou o eixo

    def test_zero_nao_vira_menos_zero(self):
        jaws = dicom_rt._mordentes(self._cp(x=[0.0, 50.0]))
        self.assertEqual(str(jaws["x1"]), "0.0")

    def test_sem_sequencia_ou_incompleto(self):
        self.assertEqual(dicom_rt._mordentes(self._cp()), {})
        self.assertEqual(dicom_rt._mordentes(self._cp(x=[10.0])), {})


class TestRotuloMaquina(unittest.TestCase):
    """A ficha imprime o nome do serviço; o DICOM e o casamento seguem no nome de
    fábrica (o TrueBeamSN1001 é impresso como VitalBeam)."""

    def test_truebeam_sai_como_vitalbeam(self):
        for texto in ("TrueBeamSN1001", "truebeamsn1001"):
            with self.subTest(texto=texto):
                self.assertEqual(constantes.rotulo_maquina(texto), "VitalBeam")

    def test_preserva_prefixo_do_dicom(self):
        self.assertEqual(constantes.rotulo_maquina("Sala2-TrueBeamSN1001"),
                         "Sala2-VitalBeam")

    def test_tbuniver_sai_como_truebeam(self):
        """Na sala a máquina se chama TrueBeam; TBuniverSN1002 é o nome de
        fábrica, e ele só aparece em Configurações → Máquinas."""
        for texto in ("TBuniverSN1002", "tbuniversn1002"):
            with self.subTest(texto=texto):
                self.assertEqual(constantes.rotulo_maquina(texto), "TrueBeam")

    def test_rotular_duas_vezes_nao_muda_nada(self):
        """A capa rotula o que pode já vir rotulado da bancada (ver
        ``capa_pdf.de_resultado``). Se o nome trocado casasse de novo, a
        segunda passada estragaria o que a primeira acertou."""
        for texto in ("TrueBeam", "VitalBeam"):
            with self.subTest(texto=texto):
                self.assertEqual(constantes.rotulo_maquina(texto), texto)

    def test_demais_maquinas_e_desconhecidas_saem_intactas(self):
        for texto in ("600CD", "6EX", "Outra", "", None):
            with self.subTest(texto=texto):
                self.assertEqual(constantes.rotulo_maquina(texto), texto or "")

    def test_renomear_nao_afeta_o_casamento(self):
        # O DICOM continua dizendo TrueBeam — SUS, mesa e protocolo dependem disso.
        m = constantes.identificar_maquina("TrueBeamSN1001")
        self.assertEqual(m.chave, "TrueBeamSN1001")
        self.assertEqual(
            constantes.identificar_maquina("TBuniverSN1002").chave,
            "TBuniverSN1002")
        self.assertTrue(m.sus_elegivel)
        # E o nome de EXIBIÇÃO não casa com máquina nenhuma — de propósito:
        # quem grava o que a tela mostra fica sem máquina, em vez de com a
        # errada. "TrueBeam" é o caso perigoso, porque é prefixo do nome de
        # fábrica da OUTRA máquina.
        for exibicao in ("VitalBeam", "TrueBeam"):
            self.assertIsNone(constantes.identificar_maquina(exibicao), exibicao)


class TestGrupoMesa(unittest.TestCase):
    def test_grupos(self):
        self.assertEqual(constantes.identificar_maquina("TrueBeamSN1001").grupo_mesa, "TB")
        self.assertEqual(constantes.identificar_maquina("TBuniverSN1002").grupo_mesa, "TB")
        self.assertEqual(constantes.identificar_maquina("600CD").grupo_mesa, "serie_c")
        self.assertEqual(constantes.identificar_maquina("6EX").grupo_mesa, "serie_c")

    def test_sus_so_truebeam(self):
        self.assertTrue(constantes.identificar_maquina("TrueBeamSN1001").sus_elegivel)
        for outra in ("TBuniverSN1002", "600CD", "6EX"):
            self.assertFalse(constantes.identificar_maquina(outra).sus_elegivel)


class TestTabelaTolerancia(unittest.TestCase):
    def test_imrt_indexado_vira_imrt_i(self):
        self.assertEqual(constantes.abreviar_tabela_tolerancia("IMRT Indexado"), "IMRT-i")

    def test_tolerante_a_caixa_e_espacos(self):
        self.assertEqual(constantes.abreviar_tabela_tolerancia("  imrt indexado "), "IMRT-i")

    def test_outros_rotulos_intactos(self):
        for r in ("3D", "SRS", "", None):
            self.assertEqual(constantes.abreviar_tabela_tolerancia(r), (r or "").strip())


if __name__ == "__main__":
    unittest.main()
