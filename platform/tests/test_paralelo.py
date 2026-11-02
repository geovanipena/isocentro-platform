"""Cálculo paralelo — o que já saiu errado, e as travas que não podem cair.

Como no ``test_qualidade.py``, cada teste guarda um caso real ou uma decisão de
domínio, não a fórmula copiada da publicação. As duas travas — a da máquina e a
do build-up — têm teste próprio porque são o que separa uma verificação de um
número com aparência de verificação.

Rodar:  python -m unittest tests.test_paralelo -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dominio import paralelo as par  # noqa: E402
from isocentro.dominio import qualidade as q  # noqa: E402


class Coisa:
    """Objeto com os atributos que lhe derem — como o pydicom se comporta."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _mordente(x_cm, y_cm):
    """A ``BeamLimitingDevicePositionSequence`` de um par de mordentes."""
    return [
        Coisa(RTBeamLimitingDeviceType="ASYMX",
              LeafJawPositions=[-x_cm * 5.0, x_cm * 5.0]),
        Coisa(RTBeamLimitingDeviceType="ASYMY",
              LeafJawPositions=[-y_cm * 5.0, y_cm * 5.0]),
    ]


def _feixe(pesos, campos=None, energia=6.0, tipo="STATIC", sad_mm=1000.0,
           ssd_mm=900.0, wedges=0, nome="teste"):
    """Um feixe com um ponto de controle por peso cumulativo.

    ``campos`` é uma lista de ``(X, Y)`` em cm, ou ``None`` num ponto que NÃO
    repete o mordente — o caso que o DICOM permite e o cálculo tem de aguentar.
    """
    cps = []
    for i, mw in enumerate(pesos):
        campo = (campos[i] if campos is not None
                 else (10.0, 10.0) if i == 0 else None)
        cp = Coisa(ControlPointIndex=i, CumulativeMetersetWeight=float(mw))
        if i == 0:
            cp.NominalBeamEnergy = energia
            cp.SourceToSurfaceDistance = ssd_mm
        if campo is not None:
            cp.BeamLimitingDevicePositionSequence = _mordente(*campo)
        cps.append(cp)
    return Coisa(BeamName=nome, BeamNumber=1, BeamType=tipo,
                 SourceAxisDistance=sad_mm, NumberOfWedges=wedges,
                 ControlPointSequence=cps)


def _pasta_de_dados(profundidades=(1.5, 5.0, 10.0), campos=(5.0, 10.0, 20.0),
                    nomes_dicom=("MAQ_TESTE",)):
    """Pasta temporária com uma máquina e um par de tabelas simples.

    TMR inventado, mas MONOTÔNICO e ancorado em 1,000 no dmax — o teste precisa
    de números cuja resposta se possa conferir de cabeça.
    """
    d = Path(tempfile.mkdtemp())
    (d / "_maquinas.json").write_text(json.dumps({
        "MAQ_TESTE": {
            "rotulo": "Máquina de teste",
            "nomes_dicom": list(nomes_dicom),
            "energias": {"6": {"fd": 1.0, "fw": 0.5}},
        }
    }), encoding="utf-8")
    linhas = ["profundidade_cm," + ",".join(f"{c:g}" for c in campos)]
    # TMR cai 0,02 por cm e sobe 0,004 por cm de campo — inventado e regular.
    for p in profundidades:
        vals = [min(1.0, 1.0 - 0.02 * (p - profundidades[0]) + 0.004 * (c - 10.0))
                for c in campos]
        linhas.append(f"{p:g}," + ",".join(f"{v:.4f}" for v in vals))
    (d / "MAQ_TESTE__6MV__TMR.csv").write_text("\n".join(linhas) + "\n",
                                               encoding="utf-8")
    linhas = ["campo_cm,scp"] + [f"{c:g},{1.0 + 0.005 * (c - 10.0):.4f}"
                                 for c in campos]
    (d / "MAQ_TESTE__6MV__SCP.csv").write_text("\n".join(linhas) + "\n",
                                               encoding="utf-8")
    return d


# ── Interpolação e campo equivalente ────────────────────────────────────────

class TestInterpolacao(unittest.TestCase):

    def test_bate_exato_nos_nos_da_tabela(self):
        """Um valor tabelado tem de sair da interpolação SEM mudar.

        É o teste que pega troca de eixo: com campo e profundidade invertidos a
        conta continua devolvendo números plausíveis, e só um nó conhecido
        denuncia.
        """
        d = _pasta_de_dados()
        tmr = par.carregar_tmr(d / "MAQ_TESTE__6MV__TMR.csv")
        self.assertAlmostEqual(par.tmr(tmr, 10.0, 1.5), 1.0, places=6)
        self.assertAlmostEqual(par.tmr(tmr, 10.0, 10.0), 0.83, places=6)
        self.assertAlmostEqual(par.tmr(tmr, 20.0, 5.0), 0.97, places=6)

    def test_nao_extrapola_fora_da_tabela(self):
        """Clamp, não extrapolação — é a regra do programa de origem.

        Extrapolar TMR além da tabela dá número que a máquina nunca produziu.
        Preso na borda, o valor ao menos foi medido, e o desvio grande que ele
        gera é o que chama atenção para o campo estar fora da faixa tabelada.
        """
        d = _pasta_de_dados()
        tmr = par.carregar_tmr(d / "MAQ_TESTE__6MV__TMR.csv")
        self.assertEqual(par.tmr(tmr, 10.0, 99.0), par.tmr(tmr, 10.0, 10.0))
        self.assertEqual(par.tmr(tmr, 99.0, 5.0), par.tmr(tmr, 20.0, 5.0))

    def test_campo_equivalente_do_quadrado_e_o_proprio_lado(self):
        self.assertAlmostEqual(par.campo_equivalente(10, 10), 10.0)
        self.assertAlmostEqual(par.campo_equivalente(20, 5), 8.0)

    def test_campo_fechado_nao_tem_equivalente(self):
        self.assertIsNone(par.campo_equivalente(0, 0))


# ── A trava da máquina ──────────────────────────────────────────────────────

class TestTravaDaMaquina(unittest.TestCase):
    """TMR e Scp são de CADA acelerador — casar por parecença é o erro caro.

    O dado que veio com o código é de uma Elekta do SAT e os planos desta
    clínica são Varian; se o casamento fosse por prefixo, "TrueBeamSN1001"
    cairia numa tabela cadastrada como "TrueBeam" e o programa passaria a
    "verificar" planos com a curva de outra máquina — em silêncio, que é o pior
    modo de errar.
    """

    def setUp(self):
        self.maquinas = par.carregar_maquinas(_pasta_de_dados())

    def test_casa_pelo_nome_exato(self):
        m = par.maquina_do_plano("MAQ_TESTE", self.maquinas)
        self.assertIsNotNone(m)
        self.assertEqual(m.chave, "MAQ_TESTE")

    def test_ignora_caixa(self):
        self.assertIsNotNone(par.maquina_do_plano("maq_teste", self.maquinas))

    def test_nao_casa_por_prefixo(self):
        self.assertIsNone(par.maquina_do_plano("MAQ_TESTE_2", self.maquinas))
        self.assertIsNone(par.maquina_do_plano("MAQ", self.maquinas))

    def test_nome_vazio_nao_casa_com_ninguem(self):
        self.assertIsNone(par.maquina_do_plano("", self.maquinas))

    def test_maquina_do_acervo_nao_casa_com_a_tabela_de_exemplo(self):
        """O dado que veio no repositório é de outra clínica — e o cadastro dele
        tem ``nomes_dicom`` VAZIO justamente para não casar com nada."""
        reais = par.carregar_maquinas()
        for nome in ("6EX", "600CD", "TBuniverSN1002", "TrueBeamSN1001"):
            self.assertIsNone(par.maquina_do_plano(nome, reais), nome)


# ── Profundidade ────────────────────────────────────────────────────────────

class TestProfundidade(unittest.TestCase):

    def test_sad_menos_ssd(self):
        f = _feixe([0.0, 1.0], sad_mm=1000.0, ssd_mm=923.0)
        self.assertAlmostEqual(par.profundidade_no_isocentro(f), 7.7, places=6)

    def test_ssd_de_fora_vence_o_do_dicom(self):
        """É por aqui que entra o SSD do contorno BODY, para o RT Plan que não
        traz ``SourceToSurfaceDistance``."""
        f = _feixe([0.0, 1.0], sad_mm=1000.0, ssd_mm=900.0)
        self.assertAlmostEqual(par.profundidade_no_isocentro(f, ssd_cm=95.0),
                               5.0, places=6)

    def test_isocentro_fora_do_paciente_nao_vira_profundidade(self):
        """SSD maior que o SAD = isocentro no ar. Devolver o negativo faria a
        tabela ser lida no clamp e sair TMR = 1,0 — o campo apareceria perfeito
        justamente onde a conta não se aplica."""
        f = _feixe([0.0, 1.0], sad_mm=1000.0, ssd_mm=1050.0)
        self.assertIsNone(par.profundidade_no_isocentro(f))


class TestBuildUp(unittest.TestCase):
    """Acima do dmax o formalismo TMR não vale, e o clamp mentiria.

    O caso é a fossa supraclavicular do TC8: isocentro a 0,8 cm da pele, TMR
    travado no 1,000 da primeira linha da tabela, e os dois campos saindo com
    −49 % e +174 % de desvio. Isocentro tão raso quase sempre significa que o
    ponto de dose NÃO é o isocentro — a fossa costuma ser prescrita a 3 cm —, e
    isso é justamente o que o RT Plan não diz.
    """

    def test_recusa_e_diz_o_motivo(self):
        d = _pasta_de_dados()
        maq = par.carregar_maquinas(d)["MAQ_TESTE"]
        tmr, scp = par.tabelas_da_maquina("MAQ_TESTE", 6, d)
        f = _feixe([0.0, 1.0], sad_mm=1000.0, ssd_mm=992.0)   # 0,8 cm
        r = par.calcular_feixe(f, dose_cgy=200.0, um_plano=250.0, maquina=maq,
                               tabela_tmr=tmr, tabela_scp=scp)
        self.assertNotEqual(r.motivo, "")
        self.assertIn("build-up", r.motivo)
        self.assertNotEqual(r.um_calculado, r.um_calculado)   # NaN


# ── O somatório ─────────────────────────────────────────────────────────────

class TestSomatorio(unittest.TestCase):

    def setUp(self):
        self.d = _pasta_de_dados()
        self.maq = par.carregar_maquinas(self.d)["MAQ_TESTE"]
        self.tmr, self.scp = par.tabelas_da_maquina("MAQ_TESTE", 6, self.d)

    def _calc(self, feixe, dose=100.0, um=100.0):
        return par.calcular_feixe(feixe, dose_cgy=dose, um_plano=um,
                                  maquina=self.maq, tabela_tmr=self.tmr,
                                  tabela_scp=self.scp)

    def test_campo_estatico_soma_os_impares_e_o_peso_fecha_em_um(self):
        """Somar TODOS os pontos num campo estático contaria cada segmento duas
        vezes — o UM calculado sairia o dobro.

        Campo de quatro pontos (dois segmentos), 10x10 a 5 cm: TMR 0,93 e
        Scp 1,000, com FD 1,0. O UM tem de ser 100/0,93 = 107,5, e não 215.
        """
        f = _feixe([0.0, 0.4, 0.4, 1.0], campos=[(10.0, 10.0)] * 4,
                   tipo="STATIC", ssd_mm=950.0)
        r = self._calc(f)
        self.assertEqual(r.n_segmentos, 2)
        self.assertAlmostEqual(r.um_calculado, 100.0 / 0.93, places=3)

    def test_campo_dinamico_soma_todos_menos_o_zero(self):
        f = _feixe([0.0, 0.25, 0.5, 0.75, 1.0], campos=[(10.0, 10.0)] * 5,
                   tipo="DYNAMIC", ssd_mm=950.0)
        r = self._calc(f)
        self.assertEqual(r.n_segmentos, 4)
        self.assertAlmostEqual(r.um_calculado, 100.0 / 0.93, places=3)

    def test_mordente_ausente_num_ponto_arrasta_o_anterior(self):
        """O DICOM permite o ponto que só traz o que MUDOU.

        Sem arrastar, o ponto sem mordente não teria campo e a conta pararia —
        ou, pior, cairia num campo zerado.
        """
        cheio = _feixe([0.0, 0.5, 1.0], campos=[(10.0, 10.0)] * 3,
                       tipo="DYNAMIC", ssd_mm=950.0)
        vazado = _feixe([0.0, 0.5, 1.0], campos=[(10.0, 10.0), None, None],
                        tipo="DYNAMIC", ssd_mm=950.0)
        self.assertAlmostEqual(self._calc(cheio).um_calculado,
                               self._calc(vazado).um_calculado, places=9)

    def test_peso_que_nao_cresce_nao_entra(self):
        """Peso cumulativo só sobe. Um que cai é arquivo corrompido, e somar a
        diferença negativa reduziria o UM em silêncio."""
        f = _feixe([0.0, 0.6, 0.4, 1.0], campos=[(10.0, 10.0)] * 4,
                   tipo="DYNAMIC", ssd_mm=950.0)
        r = self._calc(f)
        self.assertEqual(r.n_segmentos, 2)

    def test_campo_com_filtro_nao_e_calculado(self):
        """O ``k`` (fração com filtro) não sai do DICOM — a tag do ângulo do
        wedge devolve 60 no Elekta seja qual for o valor real. O programa de
        origem PERGUNTA o k; esta aba não tem onde perguntar."""
        f = _feixe([0.0, 1.0], campos=[(10.0, 10.0)] * 2, wedges=1,
                   ssd_mm=950.0)
        r = self._calc(f)
        self.assertIn("filtro", r.motivo)
        self.assertNotEqual(r.um_calculado, r.um_calculado)

    def test_sem_tabela_da_energia_diz_qual_falta(self):
        f = _feixe([0.0, 1.0], campos=[(10.0, 10.0)] * 2, energia=15.0,
                   ssd_mm=950.0)
        r = par.calcular_feixe(f, dose_cgy=100.0, um_plano=100.0,
                               maquina=self.maq, tabela_tmr=None,
                               tabela_scp=None)
        self.assertIn("15 MV", r.motivo)

    def test_sem_dose_no_rt_plan_nao_inventa(self):
        f = _feixe([0.0, 1.0], campos=[(10.0, 10.0)] * 2, ssd_mm=950.0)
        r = self._calc(f, dose=None)
        self.assertIn("dose", r.motivo)


class TestDesvio(unittest.TestCase):

    def test_positivo_quer_dizer_que_o_calculo_pede_mais_um(self):
        f = par.UmDoFeixe(um_plano=100.0, um_calculado=105.0)
        self.assertAlmostEqual(f.desvio_pct, 5.0)

    def test_total_e_da_soma_dos_um_nao_da_media_dos_desvios(self):
        """A média daria peso igual a um campo de 20 UM e a um de 600 — e é o
        TOTAL que sai na máquina.

        Aqui: 600 UM com +1 % e 20 UM com −30 %. A média dos desvios seria
        −14,5 %; o desvio do total é +0,0 %.
        """
        ver = par.VerificacaoParalela(feixes=[
            par.UmDoFeixe(um_plano=600.0, um_calculado=606.0),
            par.UmDoFeixe(um_plano=20.0, um_calculado=14.0),
        ])
        self.assertAlmostEqual(ver.desvio_total_pct, 0.0, places=6)

    def test_campo_modulado_tem_faixa_propria(self):
        """O mordente não descreve a abertura de um IMRT: 8 % ali é esperado, e
        no campo simples é motivo de olhar."""
        self.assertEqual(par.status_do_desvio(8.0, modulado=False), q.FALHA)
        self.assertEqual(par.status_do_desvio(8.0, modulado=True), q.OK)

    def test_sem_desvio_nao_e_aprovacao(self):
        self.assertEqual(par.status_do_desvio(float("nan")), q.NA)


class TestVerificarPlano(unittest.TestCase):

    def _plano(self, maquina="MAQ_TESTE", dose_gy=1.0, um=110.0):
        feixe = _feixe([0.0, 0.5, 1.0], campos=[(10.0, 10.0)] * 3,
                       tipo="DYNAMIC", ssd_mm=950.0)
        rp_ds = Coisa(
            BeamSequence=[feixe],
            FractionGroupSequence=[Coisa(ReferencedBeamSequence=[
                Coisa(ReferencedBeamNumber=1, BeamDose=dose_gy, BeamMeterset=um)])],
        )
        return {"rotulo": "P1", "rp_ds": rp_ds,
                "rp": {"maquina": maquina, "feixes": []}}

    def test_dose_do_rt_plan_vem_em_gy_e_a_conta_e_em_cgy(self):
        """``BeamDose`` é Gy; o formalismo é cGy. Sem o fator 100 o UM sai cem
        vezes menor e o desvio dá −99 % em todo campo — que se lê como bug do
        plano, não da unidade."""
        d = _pasta_de_dados()
        ver = par.verificar(self._plano(dose_gy=1.0), pasta=d)
        self.assertEqual(len(ver.feixes), 1)
        self.assertAlmostEqual(ver.feixes[0].dose_cgy, 100.0)
        self.assertAlmostEqual(ver.feixes[0].um_calculado, 100.0 / 0.93,
                               places=3)

    def test_maquina_conhecida_nao_e_demonstracao(self):
        ver = par.verificar(self._plano(), pasta=_pasta_de_dados())
        self.assertFalse(ver.demonstracao)

    def test_maquina_desconhecida_vira_demonstracao_e_avisa(self):
        """Calcular com a tabela de outro acelerador é permitido — para provar
        que a conta roda —, mas nunca sem dizer."""
        ver = par.verificar(self._plano(maquina="OUTRA"), pasta=_pasta_de_dados())
        self.assertTrue(ver.demonstracao)
        self.assertTrue(any("DEMONSTRAÇÃO" in a for a in ver.avisos))

    def test_sem_cadastro_nenhum_nao_calcula_nada(self):
        vazia = Path(tempfile.mkdtemp())
        ver = par.verificar(self._plano(), pasta=vazia)
        self.assertEqual(ver.feixes, [])
        self.assertFalse(ver.calculavel)
        self.assertTrue(any("máquina cadastrada" in a for a in ver.avisos))

    def test_sem_rt_plan_avisa_em_vez_de_quebrar(self):
        ver = par.verificar({"rotulo": "P1", "rp": {}}, pasta=_pasta_de_dados())
        self.assertEqual(ver.feixes, [])
        self.assertTrue(ver.avisos)

    def test_a_suposicao_da_profundidade_vai_para_a_tela(self):
        """Profundidade física ao isocentro é uma SUPOSIÇÃO — o RT Plan não traz
        a geometria do ponto de dose. Suposição que não aparece na tela vira
        fato em duas semanas."""
        ver = par.verificar(self._plano(), pasta=_pasta_de_dados())
        self.assertTrue(any("isocentro" in a.lower() for a in ver.avisos))


if __name__ == "__main__":
    unittest.main()
