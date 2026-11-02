"""Índices e complexidade da aba Qualidade — o que já saiu errado.

Cada teste guarda um erro que ESTE cálculo cometeu contra um caso real de
``TCs_Teste``, medido em 31/08/2026. Nenhum deles é a definição do índice
copiada da publicação: essa está no comentário do ``qualidade.py``, e um teste
que só repete a fórmula passa igual quando a fórmula está certa e a leitura
está errada.

Rodar:  python -m unittest tests.test_qualidade -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from isocentro.dicom import dvh  # noqa: E402
from isocentro.dominio import qualidade as q  # noqa: E402


# ── Dublês de DICOM ─────────────────────────────────────────────────────────
# Datasets de verdade custam segundos para ler e amarram o teste ao acervo.
# O que estes cálculos leem do DICOM é pouco e bem delimitado — posição de
# lâmina, peso cumulativo, contorno —, então o dublê é honesto: ele traz
# exatamente os atributos que o código procura, e nenhum a mais.

class Coisa:
    """Objeto com os atributos que lhe derem — o pydicom se comporta assim."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class Grade:
    """Uma ``dose3d.GradeDose`` de mentira, com eixos regulares em mm."""

    def __init__(self, dose, x0=0.0, y0=0.0, z0=0.0, passo=2.0):
        self.dose = np.asarray(dose, dtype=np.float32)
        nz, ny, nx = self.dose.shape
        self.x = np.arange(nx, dtype=float) * passo + x0
        self.y = np.arange(ny, dtype=float) * passo + y0
        self.z = np.arange(nz, dtype=float) * passo + z0


def _rs_cubo(nome: str, z_dos_cortes, x0=2.0, x1=8.0, y0=2.0, y1=8.0):
    """RT Struct com UMA estrutura: um retângulo repetido nos z pedidos."""
    contornos = [
        Coisa(ContourData=[x0, y0, z, x1, y0, z, x1, y1, z, x0, y1, z])
        for z in z_dos_cortes
    ]
    return Coisa(
        StructureSetROISequence=[Coisa(ROINumber=1, ROIName=nome)],
        ROIContourSequence=[Coisa(ReferencedROINumber=1,
                                  ContourSequence=contornos)],
    )


def _feixe(posicoes, pesos=None, tipo="MLCX"):
    """Feixe com os pontos de controle dados.

    ``posicoes`` é uma lista de ``(banco_a, banco_b)`` ou ``None`` para um ponto
    que NÃO repete o MLC — que é o caso que o DICOM permite e o cálculo tem de
    aguentar.
    """
    cps = []
    for i, par in enumerate(posicoes):
        peso = (pesos[i] if pesos is not None
                else i / max(len(posicoes) - 1, 1))
        if par is None:
            cps.append(Coisa(CumulativeMetersetWeight=peso))
            continue
        a, b = par
        cps.append(Coisa(
            CumulativeMetersetWeight=peso,
            BeamLimitingDevicePositionSequence=[
                Coisa(RTBeamLimitingDeviceType=tipo,
                      LeafJawPositions=list(a) + list(b))],
        ))
    return Coisa(BeamName="teste", ControlPointSequence=cps)


# ── Máscara: a espessura do corte ───────────────────────────────────────────

class TestMascaraEspessa(unittest.TestCase):
    """O volume do alvo saía pela METADE quando a TC é mais grossa que a dose.

    Medido no TC8 em 31/08/2026: corte de TC de 5 mm, grade de dose de 2,5 mm.
    ``_mascara_grade`` põe cada contorno no frame de dose mais próximo e para
    por aí, então um frame sim, um não ficava vazio: o PTV da mama ocupava 42
    frames num intervalo de 83, saía com 758 cc em vez de 1556, e o índice de
    Paddick — que cruza esse volume com o da isodose, contada em TODOS os
    frames — dava 0,20 num plano cujo CI RTOG era 1,25. Um Paddick de 0,20 é um
    plano inaceitável; o plano estava bom.
    """

    def test_contorno_grosso_preenche_os_frames_do_meio(self):
        # Dose com 9 frames de 2 mm (z = 0..16); contornos de 4 em 4 mm.
        grade = Grade(np.ones((9, 10, 10)), passo=2.0)
        rs = _rs_cubo("PTV", [0.0, 4.0, 8.0, 12.0, 16.0])
        cubo = dvh.mascara_3d(grade, rs, "PTV")
        cheios = np.flatnonzero(cubo.any(axis=(1, 2)))
        self.assertEqual(list(cheios), list(range(9)),
                         "os frames ENTRE dois contornos ficaram vazios")

    def test_volume_dobra_ao_cobrir_a_espessura(self):
        """O número que o erro estragava: cc, não 'quantidade de frames'."""
        grade = Grade(np.ones((9, 20, 20)), passo=2.0)
        rs = _rs_cubo("PTV", [0.0, 4.0, 8.0, 12.0, 16.0], 2.0, 10.0, 2.0, 10.0)
        ind = q.indices_do_alvo(grade, rs, "PTV", presc_gy=1.0)
        # 5×5 pixels por corte (o polígono do PIL preenche a borda), 9 frames de
        # 2 mm, voxel de 2×2×2 = 8 mm³ -> 1,8 cc. O erro antigo enchia só os 5
        # frames que TÊM contorno, e dava 1,0 cc — 56 % do volume real.
        self.assertAlmostEqual(ind.volume_cc, 25 * 9 * 8 / 1000.0, places=3)
        self.assertGreater(ind.volume_cc, 25 * 5 * 8 / 1000.0)

    def test_ilhas_do_mesmo_corte_ainda_se_combinam_por_xor(self):
        """Espalhar não pode quebrar o buraco.

        Dois contornos do MESMO z são ilha e buraco e se combinam por XOR. Se o
        espalhamento tratasse todos os contornos juntos, dois cortes VIZINHOS
        caídos no mesmo frame se cancelariam onde se sobrepõem — a estrutura
        ficaria com um rombo no meio.
        """
        grade = Grade(np.ones((3, 20, 20)), passo=2.0)
        rs = _rs_cubo("PTV", [2.0])
        # Um segundo contorno no MESMO z, menor e dentro do primeiro: o buraco.
        rs.ROIContourSequence[0].ContourSequence.append(
            Coisa(ContourData=[4.0, 4.0, 2.0, 6.0, 4.0, 2.0,
                               6.0, 6.0, 2.0, 4.0, 6.0, 2.0]))
        cubo = dvh.mascara_3d(grade, rs, "PTV")
        # O miolo (x≈5, y≈5) tem de estar VAZIO — é o buraco.
        self.assertFalse(bool(cubo[:, 2, 2].any()),
                         "o buraco do contorno foi preenchido")

    def test_estrutura_vazia_devolve_nada(self):
        """ROI criada e nunca contornada é comum no acervo; um cubo todo falso
        faria o volume sair 0,0 cc, que se lê como medida."""
        grade = Grade(np.ones((3, 10, 10)))
        rs = Coisa(StructureSetROISequence=[Coisa(ROINumber=1, ROIName="PTV")],
                   ROIContourSequence=[Coisa(ReferencedROINumber=1,
                                             ContourSequence=[])])
        self.assertIsNone(dvh.mascara_3d(grade, rs, "PTV"))


# ── Índices do alvo ─────────────────────────────────────────────────────────

class TestIndicesAlvo(unittest.TestCase):

    def _alvo_uniforme(self, dose_gy, presc_gy):
        grade = Grade(np.full((5, 12, 12), dose_gy, dtype=np.float32))
        rs = _rs_cubo("PTV", [0.0, 2.0, 4.0, 6.0, 8.0], 2.0, 10.0, 2.0, 10.0)
        return q.indices_do_alvo(grade, rs, "PTV", presc_gy)

    def test_d98_e_d2_nao_trocam_de_lugar(self):
        """D_x% é o percentil (100−x), e inverter os dois dá HI negativo.

        Com o alvo em degrau — metade em 40 Gy, metade em 60 —, D98 tem de
        ficar embaixo e D2 em cima. Trocados, o teste do HI ainda passaria (a
        diferença muda de sinal e some no módulo), então a asserção é nos dois
        valores, não no índice.
        """
        dose = np.zeros((5, 12, 12), dtype=np.float32)
        dose[:, :6, :] = 40.0
        dose[:, 6:, :] = 60.0
        grade = Grade(dose)
        rs = _rs_cubo("PTV", [0.0, 2.0, 4.0, 6.0, 8.0], 2.0, 20.0, 2.0, 20.0)
        ind = q.indices_do_alvo(grade, rs, "PTV", presc_gy=50.0)
        self.assertLess(ind.d98, ind.d50)
        self.assertGreater(ind.d2, ind.d50)
        self.assertGreater(ind.hi, 0.0)

    def test_dose_uniforme_da_hi_zero(self):
        ind = self._alvo_uniforme(50.0, 50.0)
        self.assertAlmostEqual(ind.hi, 0.0, places=6)
        self.assertAlmostEqual(ind.d50, 100.0, places=3)

    def test_alvo_de_outro_plano_nao_recebe_status(self):
        """O TC8 tinha quatro alvos, quatro FALHA vermelhas, e dois planos certos.

        Mama e fossa supraclavicular são dois planos com um RT Struct só. Na aba
        do plano da mama, o PTV da fossa recebia mediana de 1,26 Gy contra 40,05
        de prescrição e saía reprovado — junto com o seu clone ``Z_``. Tela
        cheia de vermelho em plano bom é pior que tela nenhuma.
        """
        ind = self._alvo_uniforme(1.26, 40.05)
        self.assertFalse(ind.deste_plano)
        self.assertEqual(ind.status, q.NA)

    def test_alvo_com_outra_prescricao_nao_recebe_status(self):
        """O TC1: boost integrado, 60 Gy e 48 Gy, e UMA prescrição no RT Plan.

        Normalizado pelos 60 Gy, o PTV de 48 sai com D98 de 74,7 % — número
        certo, leitura errada: contra os seus próprios 48 Gy ele está em 93 %.
        Julgar um alvo por uma prescrição que não é a dele é o mesmo defeito de
        julgar o alvo de outro plano.
        """
        ind = self._alvo_uniforme(50.0, 60.0)     # mediana em 83 %
        self.assertTrue(ind.deste_plano)
        self.assertFalse(ind.na_prescricao)
        self.assertEqual(ind.status, q.NA)
        self.assertTrue(np.isnan(ind.ci_rtog),
                        "CI de um alvo com outra prescrição não é um CI ruim, "
                        "é um CI de outra coisa")

    def test_ci_baixo_tambem_reprova(self):
        """A primeira versão só olhava o CI para CIMA, e 0,61 saía verde.

        1,0 é o ideal geométrico do CI RTOG: acima, a isodose derrama fora do
        alvo; ABAIXO, ela não cobre o alvo — que é o defeito mais grave dos
        dois. Medido no TC8: o PTV da mama deu 0,61 e a linha ficava em tinta
        de "dentro".
        """
        alvo = q.IndicesAlvo("PTV", d50=100.0, ci_rtog=0.61)
        self.assertEqual(alvo.status_ci, q.FALHA)
        alvo.ci_rtog = 1.05
        self.assertEqual(alvo.status_ci, q.OK)
        alvo.ci_rtog = 2.4
        self.assertEqual(alvo.status_ci, q.FALHA)

    def test_conformidade_perfeita(self):
        """Alvo e isodose de prescrição coincidindo: CI e Paddick = 1."""
        dose = np.zeros((5, 12, 12), dtype=np.float32)
        # A isodose de 50 Gy tem de casar com o retângulo do contorno, que na
        # grade de 2 mm começando em 0 cobre as colunas/linhas 1..4.
        dose[:, 1:6, 1:6] = 50.0
        grade = Grade(dose)
        rs = _rs_cubo("PTV", [0.0, 2.0, 4.0, 6.0, 8.0], 2.0, 10.0, 2.0, 10.0)
        ind = q.indices_do_alvo(grade, rs, "PTV", presc_gy=50.0)
        self.assertAlmostEqual(ind.ci_rtog, 1.0, places=2)
        self.assertAlmostEqual(ind.ci_paddick, 1.0, places=2)


# ── Alvo primário ───────────────────────────────────────────────────────────

class TestAlvoPrimario(unittest.TestCase):
    """O RT Plan diz a que alvo a prescrição pertence — e diz CORTADO.

    Medido nos 19 casos de ``TCs_Teste``: a ``DoseReferenceSequence`` sempre tem
    ``DoseReferenceDescription``, nunca tem ``ReferencedROINumber``, e o texto
    vem truncado em dezesseis caracteres. No TC7 a descrição é
    ``1_PTV esternocla`` para a estrutura ``1_PTV esternoclavicular``: comparar
    por igualdade não acha nada.
    """

    def test_casa_por_prefixo_quando_o_nome_veio_cortado(self):
        rp = Coisa(DoseReferenceSequence=[
            Coisa(DoseReferenceDescription="1_PTV esternocla")])
        achado = q.alvo_primario(rp, ["PTV corpo", "1_PTV esternoclavicular"])
        self.assertEqual(achado, "1_PTV esternoclavicular")

    def test_igualdade_vence_prefixo(self):
        """Um ``PTV`` genérico casaria por prefixo com o primeiro PTV da lista;
        a igualdade tem de ser testada em todos ANTES de qualquer prefixo."""
        rp = Coisa(DoseReferenceSequence=[
            Coisa(DoseReferenceDescription="PTV")])
        self.assertEqual(q.alvo_primario(rp, ["PTV_boost", "PTV"]), "PTV")

    def test_acento_nao_impede_o_casamento(self):
        rp = Coisa(DoseReferenceSequence=[
            Coisa(DoseReferenceDescription="PTV cúneo E")])
        self.assertEqual(q.alvo_primario(rp, ["PTV CUNEO E"]), "PTV CUNEO E")

    def test_sem_casar_devolve_vazio(self):
        """Melhor primário nenhum que o primário errado: quem chama tem o
        critério de reserva (a mediana perto de 100 %)."""
        rp = Coisa(DoseReferenceSequence=[
            Coisa(DoseReferenceDescription="PTV fígado")])
        self.assertEqual(q.alvo_primario(rp, ["PTV mama", "PTV FSC"]), "")


# ── Complexidade ────────────────────────────────────────────────────────────

class TestComplexidade(unittest.TestCase):

    def test_mlc_ausente_num_ponto_arrasta_o_anterior(self):
        """O DICOM permite o ponto de controle que só traz o que MUDOU.

        Lendo ponto a ponto sem arrastar o último valor conhecido, as aberturas
        zeram no meio do arco: o MCSv despenca e o campo aparece como o mais
        complexo do plano. O ESAPI não sofre disso porque resolve o arrasto
        antes de entregar as posições — é a única diferença real entre este
        cálculo e o do C#.
        """
        a, b = [-20.0, -20.0, -20.0], [20.0, 20.0, 20.0]
        cheio = _feixe([(a, b), (a, b), (a, b), (a, b)])
        vazado = _feixe([(a, b), None, None, (a, b)])
        self.assertAlmostEqual(q.complexidade_do_feixe(cheio).mcsv,
                               q.complexidade_do_feixe(vazado).mcsv, places=9)

    def test_abertura_constante_da_mcsv_um(self):
        """Banco alinhado e abertura sempre máxima: nada varia, MCSv = 1.

        É o degenerado que prova a escala. Um MCSv acima de 1 ou abaixo de 0
        significa peso negativo entrando na média (ver o ``clip`` do
        ``complexidade_do_feixe``).
        """
        a, b = [-30.0] * 5, [30.0] * 5
        m = q.complexidade_do_feixe(_feixe([(a, b)] * 4))
        self.assertAlmostEqual(m.mcsv, 1.0, places=9)
        self.assertTrue(m.modulado)

    def test_serrote_e_mais_complexo_que_banco_alinhado(self):
        """LSV: o que o índice mede é a variação entre lâminas VIZINHAS."""
        reto = ([-20.0] * 6, [20.0] * 6)
        serrote = ([-20.0, -5.0, -20.0, -5.0, -20.0, -5.0],
                   [5.0, 20.0, 5.0, 20.0, 5.0, 20.0])
        m_reto = q.complexidade_do_feixe(_feixe([reto] * 4))
        m_serra = q.complexidade_do_feixe(_feixe([serrote] * 4))
        self.assertLess(m_serra.mcsv, m_reto.mcsv)

    def test_campo_estatico_nao_recebe_status(self):
        """Com dois pontos de controle o MCSv existe aritmeticamente e não quer
        dizer nada. Um OK ali seria um OK sobre nada."""
        a, b = [-20.0] * 4, [20.0] * 4
        m = q.complexidade_do_feixe(_feixe([(a, b), (a, b)]))
        self.assertFalse(m.modulado)
        self.assertEqual(m.status, q.NA)

    def test_pesos_degenerados_nao_dividem_por_zero(self):
        """Peso cumulativo todo igual (ou ausente) dava divisão por zero, e o
        campo inteiro saía como 'sem dado'."""
        a, b = [-20.0] * 4, [20.0] * 4
        m = q.complexidade_do_feixe(
            _feixe([(a, b)] * 4, pesos=[0.0, 0.0, 0.0, 0.0]))
        self.assertTrue(np.isfinite(m.mcsv))

    def test_sas_conta_so_as_laminas_abertas(self):
        """SAS é a fração das aberturas PEQUENAS entre as ABERTAS.

        Contar as fechadas no denominador diluiria o índice: um campo com duas
        fendas de 2 mm e cinquenta lâminas fechadas mediria SAS baixo, que é o
        contrário do que ele existe para dizer.
        """
        # Duas lâminas com 2 mm de fenda, duas fechadas.
        a = [-1.0, -1.0, 0.0, 0.0]
        b = [1.0, 1.0, 0.0, 0.0]
        largo = [-30.0, -30.0, 0.0, 0.0]
        m = q.complexidade_do_feixe(_feixe([(a, b), (largo, b), (a, b)]))
        self.assertGreater(m.sas, 0.0)
        self.assertLessEqual(m.sas, 1.0)

    def test_sem_mlc_nao_inventa_metrica(self):
        feixe = Coisa(BeamName="x", ControlPointSequence=[
            Coisa(CumulativeMetersetWeight=0.0),
            Coisa(CumulativeMetersetWeight=1.0)])
        m = q.complexidade_do_feixe(feixe)
        self.assertTrue(np.isnan(m.mcsv))
        self.assertEqual(m.status, q.NA)


class TestMuPorCgy(unittest.TestCase):
    """O C# dividia pela dose TOTAL, e o indicador nunca acendia.

    ``BeamMeterset`` é o UM de UMA fração. Dividido pela dose do curso inteiro,
    um VMAT de próstata com 600 UM por fração e 60 Gy em 30 frações dava
    0,1 UM/cGy contra os 3,0 reais — sempre abaixo do limiar.
    """

    def test_divide_pela_dose_da_fracao(self):
        self.assertAlmostEqual(q.mu_por_cgy(600.0, 2.0), 3.0)

    def test_a_unidade_e_por_cGy_e_nao_por_Gy(self):
        """UM/cGy é "quantas vezes mais UM que um campo aberto" — 1 UM ≈ 1 cGy
        na referência. Em UM/Gy o mesmo plano saía 300, um número que não se
        compara de cabeça com nada; foi o que o físico apontou na tela."""
        self.assertAlmostEqual(q.mu_por_cgy(325.0, 1.0), 3.25)
        self.assertLess(q.mu_por_cgy(2355.0, 7.25), q.MUCGY_ATENCAO)

    def test_sem_dose_por_fracao_nao_inventa(self):
        self.assertTrue(np.isnan(q.mu_por_cgy(600.0, 0)))
        self.assertTrue(np.isnan(q.mu_por_cgy(600.0, None)))
        self.assertTrue(np.isnan(q.mu_por_cgy(0, 2.0)))


class TestGradiente(unittest.TestCase):
    """O GI só é julgado em SRS/SBRT — fora disso a conta vale e não diz nada.

    A fossa supraclavicular do TC8 deu GI 7,25 e aparecia como "fora da faixa"
    num plano 3D conformado correto. Os limiares vêm da literatura de SRS, onde
    a queda da dose ao redor do alvo é o próprio objetivo do plano.
    """

    def test_nao_avalia_plano_convencional(self):
        an = q.AnaliseQualidade(gi=7.25, dose_fracao_gy=2.67, num_fracoes=15)
        self.assertFalse(an.hipofracionado)
        self.assertEqual(an.status_gi, q.NA)

    def test_avalia_sbrt(self):
        an = q.AnaliseQualidade(gi=7.25, dose_fracao_gy=9.0, num_fracoes=3)
        self.assertTrue(an.hipofracionado)
        self.assertEqual(an.status_gi, q.FALHA)

    def test_conta_as_duas_isodoses(self):
        dose = np.zeros((4, 10, 10), dtype=np.float32)
        dose[:, :, :] = 10.0     # metade da prescrição em toda a grade
        dose[:, :5, :] = 20.0    # a prescrição em metade dela
        self.assertAlmostEqual(q.gradiente(Grade(dose), 20.0), 2.0, places=6)


class TestSomaDosPlanos(unittest.TestCase):
    """Somar dois planos que tratam alvos DIFERENTES é somar prescrições que
    ninguém prescreveu.

    O TC8 de novo: mama 40,05 Gy e fossa 40,05 Gy, alvos disjuntos. A soma dava
    80,1 Gy de "prescrição" e todo alvo caía para ~50 % de cobertura — quatro
    linhas vermelhas num curso correto. O que separa esse caso do boost, em que
    a soma é a única leitura certa, é haver alvo tratado por MAIS DE UM plano.
    """

    @staticmethod
    def _analise(nomes_tratados, nomes_todos):
        an = q.AnaliseQualidade()
        for n in nomes_todos:
            alvo = q.IndicesAlvo(n, d50=100.0 if n in nomes_tratados else 0.5)
            an.alvos.append(alvo)
        return an

    def test_alvos_disjuntos_nao_tem_alvo_em_comum(self):
        todos = ["PTV_Mama", "PTV_FSC"]
        analises = [self._analise(["PTV_Mama"], todos),
                    self._analise(["PTV_FSC"], todos)]
        self.assertEqual(q.alvos_em_comum(analises), [])

    def test_boost_tem(self):
        """No boost sequencial o alvo em comum é o BOOST, não o alvo grande.

        É o contrário do que parece à primeira vista, e por isso está escrito
        aqui. O plano de 46 Gy trata os dois — o boost está DENTRO do alvo
        grande, e recebe os 46 junto. O plano de reforço trata só o boost. Quem
        aparece nas duas listas é ele; o alvo grande recebe do reforço uma
        fração pequena da dose do reforço, e fica de fora.
        """
        todos = ["PTV_46", "PTV_boost"]
        analises = [self._analise(todos, todos),
                    self._analise(["PTV_boost"], todos)]
        self.assertEqual(q.alvos_em_comum(analises), ["PTV_boost"])

    def test_a_soma_se_recusa_e_diz_por_que(self):
        todos = ["PTV_Mama", "PTV_FSC"]
        analises = [self._analise(["PTV_Mama"], todos),
                    self._analise(["PTV_FSC"], todos)]
        planos = [{"rd_ds": Coisa(), "rs_ds": Coisa(),
                   "rp": {"dose_total": 40.05}} for _ in range(2)]
        an = q.analisar_soma(planos, analises)
        self.assertEqual(an.alvos, [])
        self.assertTrue(any("alvos DIFERENTES" in a for a in an.avisos),
                        "a recusa tem de dizer o motivo, senão vira tela vazia")


class TestAlvoSemContorno(unittest.TestCase):
    """ROI de alvo declarada no RT Struct e nunca desenhada.

    No TC12 são duas em quatro — "PTV Primary" e "PTV Low Risk" —, e elas
    entravam na tabela como uma linha inteira de travessões, cada uma contando
    mais um "sem status" na pílula do resumo. A tela anunciava itens não
    avaliados que não eram itens: sem volume não há D98, HI nem conformidade.

    O nome delas NÃO pode sumir junto: uma pode ser um alvo que alguém esqueceu
    de contornar, e é por isso que a linha virou nota em vez de virar nada.
    """

    def setUp(self):
        from isocentro.dicom import dose3d

        # Guardar e devolver — ``del dose3d.grade_de_rd`` apagaria a ORIGINAL
        # do módulo para o resto do processo (ver o CLAUDE.md).
        self.dose3d = dose3d
        self.original = dose3d.grade_de_rd
        grade = Grade(np.full((5, 10, 10), 60.0), passo=2.0)
        dose3d.grade_de_rd = lambda _rd: grade
        self.addCleanup(setattr, dose3d, "grade_de_rd", self.original)

    @staticmethod
    def _rs_com_uma_vazia():
        """Dois PTV: um contornado, outro só declarado."""
        contornos = [Coisa(ContourData=[2.0, 2.0, z, 8.0, 2.0, z,
                                        8.0, 8.0, z, 2.0, 8.0, z])
                     for z in (0.0, 2.0, 4.0, 6.0, 8.0)]
        return Coisa(
            StructureSetROISequence=[Coisa(ROINumber=1, ROIName="PTV Cheio"),
                                     Coisa(ROINumber=2, ROIName="PTV Vazio")],
            ROIContourSequence=[Coisa(ReferencedROINumber=1,
                                      ContourSequence=contornos)],
        )

    def _analisar(self):
        return q.analisar({"rotulo": "P1", "rp": {"dose_total": 60.0},
                           "rp_ds": None, "rd_ds": Coisa(),
                           "rs_ds": self._rs_com_uma_vazia()})

    def test_a_vazia_nao_vira_linha(self):
        an = self._analisar()
        self.assertEqual([a.nome for a in an.alvos], ["PTV Cheio"])

    def test_a_vazia_nao_conta_sem_status(self):
        """A pílula do resumo dizia itens não avaliados que não eram itens.

        O ``NA`` que sobra na contagem é dos indicadores do plano — gradiente e
        fator de modulação, que este caso de teste não tem como calcular. O que
        não pode existir é ALVO sem julgamento na tabela: cada um deles era uma
        linha de travessões somando um "sem status" à pílula.
        """
        an = self._analisar()
        self.assertNotIn(q.NA, [a.status for a in an.alvos])

    def test_o_nome_dela_continua_na_tela(self):
        an = self._analisar()
        self.assertTrue(
            any("Sem contorno" in aviso and "PTV Vazio" in aviso
                for aviso in an.avisos),
            "sair da tabela não pode ser sair da tela: pode ser um alvo que "
            "alguém esqueceu de contornar")


class TestEstruturaDeOtimizacao(unittest.TestCase):
    """Casca e núcleo têm "PTV" no nome e não são volume a tratar.

    A casca é o anel que o otimizador usa para forçar a queda da dose fora do
    alvo: ela recebe parte da prescrição POR CONSTRUÇÃO, então sai com
    cobertura péssima e conformidade absurda — linha vermelha em plano correto.

    Medido no acervo em 02/09/2026: 5 ROI em 4 dos 19 casos, todas
    "*PTV_casca*". O teste guarda a colisão que se teme ao comparar por pedaço
    de nome: "PTV cúneo E" (TC6) é alvo de verdade e NÃO pode casar com
    "nucleo".
    """

    def test_casca_e_nucleo_saem(self):
        for nome in ("PTV_casca", "2_PTV_casca", "PTV núcleo", "PTV_NUCLEO"):
            with self.subTest(nome=nome):
                self.assertTrue(q.e_otimizacao(nome))

    def test_o_cuneo_do_TC6_continua_sendo_alvo(self):
        for nome in ("PTV cúneo E", "PTV 60Gy", "ptv 48 opt", "PTV_Crop",
                     "1_PTV esternocla"):
            with self.subTest(nome=nome):
                self.assertFalse(q.e_otimizacao(nome))

    def test_a_lista_da_analise_perde_a_casca_e_diz_isso(self):
        rs = Coisa(StructureSetROISequence=[
            Coisa(ROINumber=1, ROIName="PTV 60Gy"),
            Coisa(ROINumber=2, ROIName="PTV_casca"),
            Coisa(ROINumber=3, ROIName="Medula"),
        ])
        nomes, fora = q._alvos_para_analise(rs)
        self.assertEqual(nomes, ["PTV 60Gy"])
        self.assertEqual(fora, ["PTV_casca"])

    def test_o_nome_dela_continua_na_tela(self):
        """Sair da tabela não é sair da tela — quem procura a casca precisa
        saber que ela foi tirada, e por quê."""
        an = q.AnaliseQualidade()
        avisos = q._avisos_dos_alvos(an, (), ["PTV_casca"])
        self.assertTrue(any("PTV_casca" in a and "OTIMIZAÇÃO" in a
                            for a in avisos))


class TestPiorStatus(unittest.TestCase):

    def test_falha_vence_tudo(self):
        self.assertEqual(q.pior(q.OK, q.ATENCAO, q.FALHA, q.NA), q.FALHA)

    def test_na_so_vence_sozinho(self):
        """``NA`` é ausência de julgamento, não um julgamento bom: um item sem
        dado ao lado de um OK não pode rebaixar o conjunto."""
        self.assertEqual(q.pior(q.NA, q.OK), q.OK)
        self.assertEqual(q.pior(q.NA), q.NA)


if __name__ == "__main__":
    unittest.main()
