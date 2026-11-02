"""O método por trás da aba Qualidade: a régua, as equações e as referências.

**Por que isto saiu da página.** A aba mostrava, empilhados acima das tabelas,
um parágrafo de cinco linhas sobre a calibração das tolerâncias, um rodapé
longo sobre o MCSv e um cartão com nove referências. Nada disso é errado — é
justamente o que impede um "fora da faixa" de virar veredito —, mas tudo isso
se lê UMA vez, e as tabelas se leem todo dia. Texto permanente para leitura
eventual é o que enche uma tela: na de 02/09/2026 o texto ocupava mais altura
que os números.

O que fica na página é o que muda de plano para plano. O que explica COMO se
mediu mora aqui, a um clique de distância, e o clique está ao lado do número
que ele explica.

**As equações estão na tela, e não só no código.** Um índice de conformidade
sem a fórmula é um número que o programa afirma; com a fórmula e a referência,
é uma conta que o físico confere. Os limiares desta janela são LIDOS das
constantes de :mod:`qualidade` e :mod:`paralelo` — escrevê-los à mão aqui seria
criar uma segunda régua, que envelheceria calada no dia em que a primeira
mudasse.
"""
from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                             QVBoxLayout, QWidget)

from isocentro.interface import estilo as st
from isocentro.dominio import paralelo as par
from isocentro.dominio import qualidade as q
from isocentro.interface import ui

# ── Referências ──────────────────────────────────────────────────────────────
# A chave é o apelido usado nas equações; a ordem é a de exibição. É delas que
# sai a régua: um "fora da faixa" sem a fonte é uma opinião do programa, e
# opinião de programa não se discute com o médico.
#
# Cada uma é (sigla curta, citação inteira, o que ela sustenta). A CURTA existe
# por causa do link ao lado da equação: com a citação inteira, o "Paddick,
# J Neurosurg 93 Supl.3:219 (2000); Paddick & Lippitz…" ocupava a largura do
# cartão e empurrava a fórmula para debaixo de uma linha de referência.
REFERENCIAS = {
    "icru83": (
        "ICRU 83",
        "ICRU Report 83 (2010)",
        "D98 %, D50 %, D2 % e o índice de homogeneidade — a régua de relato do "
        "alvo em IMRT."),
    "tg218": (
        "TG-218",
        "AAPM TG-218 (2018)",
        "Limites de tolerância e de ação do QA paciente-específico. Manda "
        "derivá-los do PRÓPRIO serviço, por controle estatístico de processo."),
    "tg219": (
        "TG-219",
        "AAPM TG-219 (2021) e TG-114 (2011)",
        "Verificação independente de dose/UM. É o que o cartão do cálculo "
        "paralelo faz — com TMR, Scp e fator distância medidos no acelerador."),
    "rtog": (
        "RTOG",
        "RTOG — Shaw et al., Int J Radiat Oncol Biol Phys 27:1231 (1993)",
        "O índice de conformidade como razão entre o volume da isodose de "
        "prescrição e o volume do alvo."),
    "paddick": (
        "Paddick",
        "Paddick, J Neurosurg 93 Supl.3:219 (2000); Paddick & Lippitz, "
        "J Neurosurg 105 Supl.:194 (2006)",
        "Índice de conformidade que penaliza os dois defeitos (derramar fora e "
        "não cobrir), e índice de gradiente."),
    "mcniven": (
        "McNiven",
        "McNiven, Sharpe & Purdie, Med Phys 37(2):505 (2010)",
        "MCS = variabilidade da abertura (AAV) × variabilidade da sequência de "
        "lâminas (LSV)."),
    "masi": (
        "Masi",
        "Masi et al., Med Phys 40(7):071718 (2013)",
        "MCSv (a versão para arco) e SAS — fração de aberturas pequenas."),
    "tg100": (
        "TG-100",
        "AAPM TG-100 (2016)",
        "Análise de risco (FMEA): o que conferir primeiro sai da gravidade e "
        "da chance de passar despercebido, não do que é fácil de medir."),
    "tg275": (
        "TG-275",
        "AAPM TG-275 (2022) e TG-315 (2024)",
        "Revisão física do plano e do prontuário: o que um segundo par de "
        "olhos confere antes do primeiro tratamento."),
    "anvisa": (
        "ANVISA · CNEN",
        "RDC ANVISA 611/2022 · CNEN NN 6.10",
        "Exigem programa de garantia da qualidade documentado no serviço de "
        "radioterapia."),
}


def _n(valor, casas: int = 2) -> str:
    """Número com vírgula, como o resto do programa escreve."""
    return f"{float(valor):.{casas}f}".replace(".", ",")


class Equacao(NamedTuple):
    """Uma conta da aba: o que ela mede, como se calcula e com que régua.

    ``limiares`` é texto pronto, montado a partir das CONSTANTES — nunca
    digitado. ``refs`` são chaves de :data:`REFERENCIAS`, e a janela as
    transforma em link para a aba de referências.
    """
    nome: str
    formula: str
    nota: str = ""
    limiares: str = ""
    refs: tuple = ()


def _equacoes() -> list:
    """As equações, montadas na hora para lerem os limiares em vigor.

    Função e não constante de módulo: ``qualidade`` e ``paralelo`` podem ter
    seus limiares mexidos (é o que a calibração local vai fazer), e uma lista
    congelada no import mostraria a régua de ontem com toda a convicção.
    """
    return [
        ("Alvo — ICRU 83", [
            Equacao(
                "D<sub>x %</sub>",
                "D<sub>x %</sub> = dose que x % do volume do alvo recebe ou "
                "supera<br>= percentil (100 − x) dos voxels dentro do PTV",
                "D98 é a cobertura, D2 é o ponto quente. Trocar os dois é o "
                "erro que dá HI negativo — foi assim que ele apareceu aqui.",
                refs=("icru83",)),
            Equacao(
                "Doses em % e em Gy",
                "D<sub>x %</sub> = 100 · D<sub>x</sub> (Gy) / prescrição do plano",
                "A coluna D50 (Gy) é a mesma mediana em dose absoluta. Num "
                "boost integrado o alvo de dose baixa só pode ser julgado em "
                "Gy: contra a prescrição do plano ele sai com 75 % e não está "
                "subdosado.",
                refs=("icru83",)),
            Equacao(
                "HI — homogeneidade",
                "HI = (D<sub>2 %</sub> − D<sub>98 %</sub>) / D<sub>50 %</sub>",
                "Zero é dose uniforme. É MUITO dependente da técnica: um SIB "
                "tem HI alto por construção.",
                _faixa_maior(q.HI_ATENCAO, q.HI_FALHA, 3),
                ("icru83",)),
        ]),
        ("Conformidade e queda de dose", [
            Equacao(
                "CI RTOG",
                "CI = V<sub>presc</sub> / V<sub>alvo</sub>",
                "Volume que recebe a prescrição dividido pelo volume do alvo. "
                "Julgado dos DOIS lados: acima de 1 a isodose derrama fora, "
                "abaixo de 1 ela não cobre — e não cobrir é o defeito mais "
                "grave dos dois.",
                "atenção acima de " + _n(q.CI_ALTO_ATENCAO) + " ou abaixo de "
                + _n(q.CI_BAIXO_ATENCAO) + "  ·  fora da faixa acima de "
                + _n(q.CI_ALTO_FALHA) + " ou abaixo de " + _n(q.CI_BAIXO_FALHA),
                ("rtog",)),
            Equacao(
                "CI Paddick",
                "CI<sub>Paddick</sub> = V<sub>alvo ∩ presc</sub>² / "
                "(V<sub>alvo</sub> · V<sub>presc</sub>)",
                "Vai a 1 só quando a isodose cobre o alvo E não sai dele. Um "
                "CI RTOG de 1,00 com a isodose deslocada dá Paddick baixo — é "
                "por isso que os dois aparecem lado a lado.",
                refs=("paddick",)),
            Equacao(
                "GI — índice de gradiente",
                "GI = V<sub>presc / 2</sub> / V<sub>presc</sub>",
                "Quão rápido a dose cai fora do alvo. É do PLANO, não do alvo: "
                "as duas isodoses são as mesmas seja qual for o PTV.",
                _faixa_maior(q.GI_ATENCAO, q.GI_FALHA, 2)
                + "  ·  só julgado com dose por fração ≥ "
                + _n(q.GI_SO_ACIMA_DE_GY_FRACAO, 1) + " Gy e até "
                + str(q.GI_SO_ATE_FRACOES) + " frações (SRS/SBRT)",
                ("paddick",)),
        ]),
        ("Complexidade dos campos", [
            Equacao(
                "AAV — abertura",
                "AAV = Σ<sub>lâminas</sub> vão / Σ<sub>lâminas</sub> vão máximo",
                "Quanto da abertura máxima de cada lâmina está sendo usado "
                "neste ponto de controle.",
                refs=("mcniven",)),
            Equacao(
                "LSV — sequência das lâminas",
                "LSV = Σ (faixa − |pos<sub>i+1</sub> − pos<sub>i</sub>|) / "
                "((N − 1) · faixa)<br>"
                "LSV<sub>ponto</sub> = LSV<sub>banco A</sub> · "
                "LSV<sub>banco B</sub>",
                "Mede o quanto lâminas VIZINHAS diferem entre si: banco "
                "alinhado dá 1, banco em serrote dá perto de 0.",
                refs=("mcniven",)),
            Equacao(
                "MCSv",
                "MCSv = Σ<sub>segmentos</sub> ΔUM<sub>rel</sub> · "
                "AAV<sub>médio</sub> · LSV<sub>médio</sub>",
                "MENOR significa mais modulado, e mais modulado significa mais "
                "difícil de entregar — não significa errado. Serve para "
                "ESCOLHER o que medir com câmara ou matriz, não para "
                "substituir a medida.",
                _faixa_menor(q.MCS_ATENCAO, q.MCS_FALHA, 2),
                ("mcniven", "masi")),
            Equacao(
                "SAS — aberturas pequenas",
                "SAS(x) = nº de lâminas abertas com vão &lt; x mm / nº de "
                "lâminas abertas<br>(média pesada pelo UM de cada segmento)",
                "A coluna avaliada é a de "
                + _n(q.SAS_LARGO_MM, 0) + " mm; a de "
                + _n(q.SAS_ESTREITO_MM, 0) + " mm é informativa. Vão abaixo de "
                + _n(q.ABERTO_MM, 2) + " mm conta como lâmina FECHADA, não "
                "como abertura pequena.",
                _faixa_maior(q.SAS_ATENCAO * 100, q.SAS_FALHA * 100, 0, " %"),
                ("masi",)),
            Equacao(
                "Abertura e percurso",
                "abertura = vão médio das lâminas abertas<br>"
                "percurso = Σ |Δposição| dos dois bancos, arco inteiro",
                "Sem status: são descrições do campo, não medidas com faixa "
                "publicada. O percurso alto ao lado de MCSv baixo é o retrato "
                "de um arco muito dinâmico.",
                refs=("masi",)),
            Equacao(
                "UM/cGy — fator de modulação",
                "UM/cGy = UM de UMA fração / dose DAQUELA fração (cGy)",
                "Em cGy, e não em Gy: o acelerador é calibrado para 1 UM ≈ "
                "1 cGy na condição de referência, então este número é quantas "
                "vezes o plano gasta mais UM que um campo aberto gastaria — "
                "3,25 é um VMAT modulado, 1,1 é um campo simples.",
                _faixa_maior(q.MUCGY_ATENCAO, q.MUCGY_FALHA, 1),
                ("tg218",)),
        ]),
        ("Cálculo paralelo — verificação independente de UM", [
            Equacao(
                "Campo equivalente",
                "L = 2 · X · Y / (X + Y)",
                "X e Y são os MORDENTES do ponto de controle. Num campo "
                "modulado isso ignora a modulação: a abertura real é menor, o "
                "TMR e o Scp saem altos demais e o UM calculado sai baixo. É "
                "rastreio grosseiro em IMRT/VMAT, e a tela diz isso.",
                refs=("tg219",)),
            Equacao(
                "Profundidade",
                "profundidade = SAD − SSD  (cm, ao isocentro)",
                "Profundidade FÍSICA, não radiológica: em mama e pulmão a "
                "diferença é grande, e o desvio estoura por causa do pulmão, "
                "não por erro do plano. Supõe que o ponto de dose é o "
                "isocentro — o RT Plan não traz a geometria desse ponto.",
                refs=("tg219",)),
            Equacao(
                "UM calculado",
                "UM = Σ<sub>segmentos</sub> ΔMw · D / (TMR · Scp · FD)",
                "ΔMw é a diferença de CumulativeMetersetWeight entre pontos de "
                "controle. TMR e Scp vêm da tabela DAQUELA máquina; sem ela o "
                "resultado é DEMONSTRAÇÃO e não tem veredito.",
                refs=("tg219",)),
            Equacao(
                "Desvio",
                "desvio % = 100 · (UM<sub>calculado</sub> − "
                "UM<sub>plano</sub>) / UM<sub>plano</sub>",
                "Positivo significa que o cálculo pede MAIS UM que o plano. O "
                "total é a soma dos campos, não a média dos desvios: a média "
                "daria o mesmo peso a um campo de 20 UM e a um de 600.",
                "campo estático: " + _faixa_maior(par.DESVIO_ATENCAO,
                                                  par.DESVIO_FALHA, 0, " %")
                + "  ·  modulado: "
                + _faixa_maior(par.DESVIO_ATENCAO_MODULADO,
                               par.DESVIO_FALHA_MODULADO, 0, " %"),
                ("tg219",)),
        ]),
    ]


def _faixa_maior(atencao, falha, casas: int = 2, sufixo: str = "") -> str:
    return (f"atenção acima de {_n(atencao, casas)}{sufixo}  ·  "
            f"fora da faixa acima de {_n(falha, casas)}{sufixo}")


def _faixa_menor(atencao, falha, casas: int = 2, sufixo: str = "") -> str:
    return (f"atenção abaixo de {_n(atencao, casas)}{sufixo}  ·  "
            f"fora da faixa abaixo de {_n(falha, casas)}{sufixo}")


# ── O texto da régua ─────────────────────────────────────────────────────────

def regua_curta() -> str:
    """A linha que fica NA PÁGINA, sempre visível. Ver ``regua_inteira``."""
    if q.CALIBRADO:
        return ("Tolerâncias calibradas com a base histórica deste serviço "
                "(AAPM TG-218).")
    return ("Régua da LITERATURA, não calibrada neste serviço (AAPM TG-218): "
            "\"fora da faixa\" quer dizer fora do que a literatura chama de "
            "usual — não plano reprovado.")


def regua_inteira() -> list:
    """Os parágrafos da aba "A régua". Um por item da lista."""
    if q.CALIBRADO:
        return [
            "As tolerâncias desta aba foram calibradas com a base histórica "
            "deste serviço, por controle estatístico de processo, como manda o "
            "AAPM TG-218.",
            "Nada nesta aba substitui a medida de QA paciente-específico nem a "
            "revisão do físico.",
        ]
    return [
        "As tolerâncias desta aba vêm da LITERATURA, não da base histórica "
        "deste serviço.",
        "O AAPM TG-218 manda derivar limite de tolerância e de ação do PRÓPRIO "
        "processo — a mediana e o desvio dos casos já tratados aqui. Enquanto "
        "essa calibração não existir, leia \"fora da faixa\" como \"fora do "
        "que a literatura chama de usual\", e não como plano reprovado.",
        "Os limiares de conformidade são de IMRT/VMAT convencional; SBRT tem "
        "régua própria, que não está embutida aqui. Os de gradiente são de "
        "SRS/SBRT, e por isso o GI só é julgado em plano hipofracionado.",
        "Nada nesta aba substitui a medida de QA paciente-específico nem a "
        "revisão do físico. O que ela faz é dizer o que olhar primeiro.",
    ]


# ── A janela ─────────────────────────────────────────────────────────────────

REGUA, EQUACOES, FONTES = 0, 1, 2      # as três abas, por nome


class JanelaMetodo(ui.Dialogo):
    """Com que régua, com que conta, e de onde saiu cada uma.

    Uma janela só para as três coisas, porque elas são a mesma pergunta feita
    em três profundidades: "isto é confiável?" → "como foi calculado?" → "quem
    disse?". Separá-las em três janelas obrigaria a fechar uma para abrir a
    próxima justamente quando a pessoa está seguindo o fio.

    Ela nasce UMA vez por painel e é reaproveitada (ver
    ``PainelQualidade._metodo``): são ~90 rótulos pintados, e cada
    ``estilo.pintar`` guarda um ouvinte — remontá-la a cada clique encheria a
    lista de ouvintes de uma sessão de trabalho normal.
    """

    def __init__(self, pai=None):
        super().__init__("Método, equações e referências", pai, 860, 700)
        self._ancoras: dict = {}
        pag_regua, self._area_regua = self._pagina()
        pag_eq, self._area_eq = self._pagina()
        pag_ref, self._area_ref = self._pagina()
        self._montar_regua(pag_regua)
        self._montar_equacoes(pag_eq)
        self._montar_referencias(pag_ref)
        self.abas = ui.abas((self._area_regua, "A régua"),
                            (self._area_eq, "Equações"),
                            (self._area_ref, "Referências"))
        self.corpo.addWidget(self.abas)
        self.rodape()

    def abrir_em(self, aba: int) -> None:
        """Mostra a janela já na aba pedida. Não modal: quem consulta a fórmula
        costuma querer olhar a tabela ao lado enquanto lê."""
        self.abas.setCurrentIndex(aba)
        self.show()
        self.raise_()
        self.activateWindow()

    # ── Molduras ────────────────────────────────────────────────────────

    def _pagina(self) -> tuple:
        """Um miolo rolável. Devolve ``(layout de dentro, área)``."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        st.pintar(area, lambda: "background:transparent;" + ui.barras())
        dentro = ui.transparente(QWidget())
        lay = QVBoxLayout(dentro)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(12)
        area.setWidget(dentro)
        # A folha da PÁGINA pinta todos os rótulos de dentro, por nome de
        # objeto. Pintar um a um custaria ~90 ouvintes de dia↔noite nesta
        # janela sozinha (ver a armadilha do ``estilo.pintar`` no CLAUDE.md).
        st.pintar(dentro, self._folha_do_texto)
        return lay, area

    @staticmethod
    def _folha_do_texto() -> str:
        return (
            f"QLabel {{ color:{st.TEXTO_FRACO}; font-size:12.5px;"
            "  line-height:150%; background:transparent; }"
            f"QLabel#eq_nome {{ color:{st.TEXTO}; font-size:12.5px;"
            "  font-weight:bold; }"
            f"QLabel#eq_formula {{ color:{st.AZUL_CLARO};"
            "  font-family:'Consolas','DejaVu Sans Mono',monospace;"
            "  font-size:13px; line-height:165%;"
            f"  background:{st.FUNDO_CAMPO}; border:1px solid {st.BORDA_SUAVE};"
            "  border-radius:7px; padding:8px 11px; }"
            f"QLabel#eq_limiar {{ color:{st.AMBAR}; font-size:11.5px; }}"
            f"QLabel#ref_sigla {{ color:{st.TEXTO}; font-size:12.5px;"
            "  font-weight:bold; }"
        )

    # ── As três abas ────────────────────────────────────────────────────

    def _montar_regua(self, lay) -> None:
        cartao = ui.Cartao("Com que régua isto foi medido")
        for i, paragrafo in enumerate(regua_inteira()):
            rot = QLabel(paragrafo)
            rot.setWordWrap(True)
            # O primeiro parágrafo é a frase que muda a leitura de todos os
            # números da aba: fica no peso do texto normal, e não no cinza das
            # explicações. Quem abre esta janela por causa de um "fora da
            # faixa" tem de bater nela antes de qualquer outra coisa.
            if i == 0:
                rot.setObjectName("eq_nome")
            cartao.corpo.addWidget(rot)
        lay.addWidget(cartao)

        cartao2 = ui.Cartao("O que a aba não faz")
        for texto in (
            "Não mede dose: o que ela lê é o RT Dose que o TPS calculou. Um "
            "erro de cálculo do TPS aparece aqui como um plano perfeito.",
            "Não substitui a medida do QA paciente-específico — ela ajuda a "
            "escolher qual plano medir e o que olhar na medida.",
            "Não reprova plano. A palavra da última coluna é o resultado de uma "
            "comparação com um número publicado; quem reprova é o físico.",
        ):
            rot = QLabel("•  " + texto)
            rot.setWordWrap(True)
            cartao2.corpo.addWidget(rot)
        lay.addWidget(cartao2)
        lay.addStretch(1)

    def _montar_equacoes(self, lay) -> None:
        for secao, equacoes in _equacoes():
            cartao = ui.Cartao(secao)
            for i, eq in enumerate(equacoes):
                if i:
                    cartao.corpo.addWidget(ui.divisor())
                cartao.corpo.addLayout(self._bloco_da_equacao(eq))
            lay.addWidget(cartao)
        lay.addStretch(1)

    def _bloco_da_equacao(self, eq: Equacao) -> QVBoxLayout:
        caixa = QVBoxLayout()
        caixa.setSpacing(5)

        topo = QHBoxLayout()
        topo.setSpacing(8)
        nome = QLabel(eq.nome)
        nome.setObjectName("eq_nome")
        nome.setTextFormat(Qt.RichText)
        topo.addWidget(nome)
        topo.addStretch(1)
        # A sigla é LINK, e não texto: a fonte de um limiar é a primeira coisa
        # que se quer ver depois da fórmula, e obrigar a rolar até a outra aba
        # procurando o nome certo é o mesmo que não ter posto a fonte.
        for chave in eq.refs:
            topo.addWidget(ui.link(REFERENCIAS[chave][0],
                                   lambda _=False, c=chave: self.ir_para(c)))
        caixa.addLayout(topo)

        formula = QLabel(eq.formula)
        formula.setObjectName("eq_formula")
        formula.setTextFormat(Qt.RichText)
        formula.setWordWrap(True)
        formula.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        caixa.addWidget(formula)

        if eq.nota:
            nota = QLabel(eq.nota)
            nota.setWordWrap(True)
            caixa.addWidget(nota)
        if eq.limiares:
            lim = QLabel(eq.limiares)
            lim.setObjectName("eq_limiar")
            lim.setWordWrap(True)
            caixa.addWidget(lim)
        return caixa

    def _montar_referencias(self, lay) -> None:
        cartao = ui.Cartao("De onde saiu cada régua")
        for i, (chave, (_curta, citacao, oque)) in enumerate(
                REFERENCIAS.items()):
            if i:
                cartao.corpo.addWidget(ui.divisor())
            bloco = QWidget()
            ui.transparente(bloco)
            dentro = QVBoxLayout(bloco)
            dentro.setContentsMargins(0, 0, 0, 0)
            dentro.setSpacing(3)
            rot = QLabel(citacao)
            rot.setObjectName("ref_sigla")
            rot.setWordWrap(True)
            dentro.addWidget(rot)
            texto = QLabel(oque)
            texto.setWordWrap(True)
            dentro.addWidget(texto)
            cartao.corpo.addWidget(bloco)
            self._ancoras[chave] = bloco
        lay.addWidget(cartao)
        lay.addStretch(1)

    def ir_para(self, chave: str) -> None:
        """Vai para a aba de referências, com a fonte pedida à vista."""
        self.abas.setCurrentIndex(FONTES)
        alvo = self._ancoras.get(chave)
        if alvo is not None:
            self._area_ref.ensureWidgetVisible(alvo, 0, 40)
