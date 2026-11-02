"""Índices de qualidade do plano e complexidade dos campos — a aba Qualidade.

Porte para Python do plug-in ESAPI ``Plano_Índices_e_Qualidade.cs`` (repositório
``scriptsvarian``, ramo ``claude/soma-plan-preprocessing-5uzieu``), com dois
acréscimos: os índices de CONFORMIDADE, que o C# não calculava, e a correção do
fator de modulação (ver :func:`mu_por_cgy`).

**Por que porte e não integração.** O script original roda dentro do Eclipse, em
Citrix, e lê o plano pela API da Varian. Nada do que ele calcula precisa disso:
as métricas de complexidade usam apenas a posição das lâminas e o
``CumulativeMetersetWeight`` dos pontos de controle — que estão no RT Plan —, e
os índices dosimétricos saem do RT Dose com o RT Struct. Os três datasets já
estão carregados aqui (``gui.JanelaPrincipal._planos[i]``), então a aba lê o
mesmo DICOM que a ficha lê, sem licença e sem servidor.

**As tolerâncias são PROVISÓRIAS.** Vieram da literatura, não da base histórica
desta clínica. O AAPM TG-218 é explícito em mandar derivar limite de tolerância
e de ação do próprio processo, por controle estatístico — a mediana e o desvio
dos casos já tratados AQUI. Enquanto isso não existe, o que esta aba mostra é
"fora do que a literatura chama de usual", não "reprovado". Quem lê os números
tem de ver essa diferença na tela: ver ``CALIBRADO`` e o aviso que a tela monta
a partir dele.

Referências
-----------
ICRU 83 (2010) — D98%/D50%/D2% e HI.
AAPM TG-218 (2018) — limites de tolerância e ação; calibração local por SPC.
AAPM TG-219 (2021) — verificação independente de dose/UM.
McNiven, Sharpe & Purdie, Med Phys 37(2):505 (2010) — MCS = AAV × LSV.
Masi et al., Med Phys 40(7):071718 (2013) — MCSv (VMAT) e SAS.
Paddick, J Neurosurg 93(Suppl 3):219 (2000) — índice de conformidade.
Paddick & Lippitz, J Neurosurg 105(Suppl):194 (2006) — índice de gradiente.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# ── Status ───────────────────────────────────────────────────────────────────
# Mesmas quatro chaves do relatório ESAPI, para que quem lê os dois documentos
# não tenha de traduzir. O "VERIFICAR" do C# não veio: lá ele marca item que
# depende de julgamento humano, e esta aba não tem itens desse tipo.
OK = "OK"
ATENCAO = "ATENCAO"
FALHA = "FALHA"
NA = "NA"

ROTULO_STATUS = {
    OK: "OK",
    ATENCAO: "Atenção",
    FALHA: "Fora da faixa",
    NA: "Sem dado",
}

# Gravidade para escolher o PIOR status de um conjunto. Menor = pior.
_GRAVIDADE = {FALHA: 0, ATENCAO: 1, OK: 2, NA: 3}


# ── Tolerâncias ──────────────────────────────────────────────────────────────
# NENHUMA destas foi calibrada com dados desta clínica. Ver o cabeçalho do
# módulo: enquanto ``CALIBRADO`` for falso, a tela anuncia isso em primeiro
# lugar, do mesmo jeito que a capa anuncia quando não veio do banco.
CALIBRADO = False

# ICRU 83, em % da dose de prescrição.
D98_ATENCAO, D98_FALHA = 95.0, 90.0      # cobertura: abaixo é pior
D2_ATENCAO, D2_FALHA = 107.0, 110.0      # ponto quente: acima é pior
HI_ATENCAO, HI_FALHA = 0.12, 0.20        # homogeneidade — MUITO dependente da técnica

# Conformidade. Faixas de IMRT/VMAT convencional; SBRT tem régua própria
# (Timmerman / ASTRO 2025) e não está embutida aqui.
#
# O CI RTOG é de DOIS LADOS, e a primeira versão só olhava para cima. 1,0 é o
# ideal geométrico: acima, a isodose de prescrição derrama fora do alvo; ABAIXO,
# ela não cobre o alvo — que é o defeito mais grave dos dois e passava como OK.
# Medido no TC8: o PTV da mama saiu com CI 0,61 e a linha ficou verde.
CI_ALTO_ATENCAO, CI_ALTO_FALHA = 1.50, 2.00
CI_BAIXO_ATENCAO, CI_BAIXO_FALHA = 0.90, 0.75
GI_ATENCAO, GI_FALHA = 4.50, 6.00        # queda da dose fora do alvo

# O índice de GRADIENTE só é avaliado em plano hipofracionado.
#
# Os limiares de GI vêm da literatura de SRS/SBRT, onde o alvo é pequeno e a
# queda da dose ao redor é o próprio objetivo do plano. Num 3D conformado de
# mama a conta continua valendo aritmeticamente e não quer dizer nada: a fossa
# supraclavicular do TC8 deu GI 7,25 e aparecia como "fora da faixa" num plano
# correto. A heurística é a mesma do checklist do ESAPI — dose por fração alta
# e poucas frações.
GI_SO_ACIMA_DE_GY_FRACAO = 5.0
GI_SO_ATE_FRACOES = 5

# Complexidade (McNiven 2010 / Masi 2013).
MCS_ATENCAO, MCS_FALHA = 0.25, 0.18      # MCSv: MENOR = mais complexo
SAS_ATENCAO, SAS_FALHA = 0.30, 0.45      # fração de aberturas pequenas: maior = pior
# Fator de modulação em UM/cGy — maior = mais modulado.
#
# A unidade é UM/**cGy**, e não UM/Gy: 1 UM entrega ~1 cGy na condição de
# referência, então UM/cGy é quantas vezes o plano gasta mais UM que um campo
# aberto — 3,25 lê-se "três vezes e pouco". Os mesmos limiares em UM/Gy (400 e
# 600) davam números de três dígitos que ninguém compara de cabeça com nada.
MUCGY_ATENCAO, MUCGY_FALHA = 4.0, 6.0

# Parâmetros de cálculo da complexidade.
SAS_LARGO_MM = 10.0     # abertura abaixo disto conta como "pequena" (é o SAS avaliado)
SAS_ESTREITO_MM = 5.0   # segundo limiar, informativo
ABERTO_MM = 0.10        # abaixo disto o par de lâminas está fechado, não aberto

# Quanto a mediana pode se afastar de 100 % e o alvo ainda estar RECEBENDO a
# prescrição do plano — e, portanto, poder ser julgado por ela.
#
# O caso é o TC1: próstata VMAT com boost integrado, 60 Gy no PTV 60Gy e 48 Gy
# no PTV 48Gy, e o RT Plan traz UMA prescrição só (medido: nos 19 casos de
# TCs_Teste, a ``DoseReferenceSequence`` nunca tem ``ReferencedROINumber`` e
# nunca traz mais de uma dose). Normalizado pelos 60 Gy, o PTV 48Gy sai com D98
# de 74,7 % e um "CI" de 0,27 — números corretos e leitura errada: contra os
# seus próprios 48 Gy ele está com 93 %. Julgar um alvo por uma prescrição que
# não é a dele é o mesmo defeito de julgar o alvo de outro plano.
#
# Os números do alvo continuam na tela; o que sai é o STATUS, com o motivo
# escrito. Esconder a linha esconderia um alvo de verdade mal coberto.
TOLERANCIA_D50_DA_PRESCRICAO = 10.0

# Abaixo desta mediana (% da prescrição), o alvo NÃO é deste plano.
#
# O caso que obrigou a isto é o TC8: mama direita em dois planos (mama e FSC),
# cada um com o seu RT Dose, e o RT Struct — que é um só — trazendo os alvos dos
# dois. Analisando o plano da mama, o PTV_FSC recebia mediana de 1,26 Gy contra
# 40,05 Gy de prescrição, e saía com D98 de 0,9 %: quatro alvos, quatro FALHA
# vermelhas, num par de planos que está correto. Tela cheia de vermelho em plano
# bom é pior que tela nenhuma — na segunda semana ninguém olha mais.
#
# 20 % é folgado de propósito. Os alvos de verdade ficam perto de 100 % e os de
# outro plano ficaram abaixo de 4 % no caso medido; qualquer corte entre os dois
# serviria, e o mais alto seria o que erraria primeiro num boost sequencial de
# dose baixa. Quem cai fora do corte não some da tela — aparece dizendo que é de
# outro plano, porque sumir esconderia um alvo REALMENTE não tratado.
MEDIANA_MINIMA_DO_ALVO = 20.0


def _menor_e_pior(v, atencao: float, falha: float) -> str:
    if v is None or not np.isfinite(v):
        return NA
    if v < falha:
        return FALHA
    if v < atencao:
        return ATENCAO
    return OK


def _maior_e_pior(v, atencao: float, falha: float) -> str:
    if v is None or not np.isfinite(v):
        return NA
    if v > falha:
        return FALHA
    if v > atencao:
        return ATENCAO
    return OK


def pior(*status: str) -> str:
    """O status mais grave do conjunto. ``NA`` só vence se for o único."""
    reais = [s for s in status if s]
    if not reais:
        return NA
    return min(reais, key=lambda s: _GRAVIDADE.get(s, 3))


# ── Índices do alvo ──────────────────────────────────────────────────────────

@dataclass
class IndicesAlvo:
    """Os índices de UM alvo. Doses em % da prescrição, volume em cc."""
    nome: str
    volume_cc: float = float("nan")
    d98: float = float("nan")
    d95: float = float("nan")
    d50: float = float("nan")
    d2: float = float("nan")
    d_media: float = float("nan")
    # As mesmas doses em Gy ABSOLUTO. Não é redundância: o alvo cuja prescrição
    # o RT Plan não traz (o de dose baixa de um boost integrado) só pode ser
    # julgado em Gy, e obrigar quem lê a multiplicar de cabeça pela prescrição
    # do plano é pedir a conta que a tela existe para fazer.
    d98_gy: float = float("nan")
    d50_gy: float = float("nan")
    d2_gy: float = float("nan")
    hi: float = float("nan")
    ci_rtog: float = float("nan")
    ci_paddick: float = float("nan")
    # É o alvo que o RT Plan aponta como o da prescrição? Ver ``alvo_primario``.
    # Este é CAMPO porque não sai da dose: sai do texto do RT Plan, e quem
    # constrói o objeto é que sabe.
    primario: bool = False

    @property
    def vazia(self) -> bool:
        """ROI de alvo SEM CONTORNO — declarada no RT Struct e nunca desenhada.

        Sem volume não há D98, HI nem conformidade: não é um alvo mal coberto,
        é um alvo que não existe na tomografia. No TC12 são duas ("PTV Primary"
        e "PTV Low Risk"), e elas enchiam a tabela com uma linha de travessões
        cada. Quem chama é que decide o que fazer — ver ``analisar``.
        """
        return self.volume_cc != self.volume_cc      # NaN

    @property
    def deste_plano(self) -> bool:
        """Este alvo é tratado POR ESTE plano? Ver ``MEDIANA_MINIMA_DO_ALVO``.

        PROPRIEDADE, e não campo com padrão. Era campo, com padrão ``True``, e
        só ``indices_do_alvo`` o preenchia: qualquer ``IndicesAlvo`` montado
        fora dali — no teste, e um dia em outro chamador — nascia dizendo "sou
        deste plano" sem que ninguém tivesse medido. O teste da soma pegou:
        dois planos de alvos disjuntos apareciam com os quatro alvos em comum,
        e a soma teria sido feita.
        """
        return (np.isfinite(self.d50)
                and self.d50 >= MEDIANA_MINIMA_DO_ALVO)

    @property
    def na_prescricao(self) -> bool:
        """Este alvo RECEBE a prescrição do plano — logo, pode ser julgado por ela.

        É a condição de todo status desta linha. Ver
        ``TOLERANCIA_D50_DA_PRESCRICAO``.
        """
        return (self.deste_plano and np.isfinite(self.d50)
                and abs(self.d50 - 100.0) <= TOLERANCIA_D50_DA_PRESCRICAO)

    @property
    def status_cobertura(self) -> str:
        if not self.na_prescricao:
            return NA
        return _menor_e_pior(self.d98, D98_ATENCAO, D98_FALHA)

    @property
    def status_quente(self) -> str:
        if not self.na_prescricao:
            return NA
        return _maior_e_pior(self.d2, D2_ATENCAO, D2_FALHA)

    @property
    def status_hi(self) -> str:
        if not self.na_prescricao:
            return NA
        return _maior_e_pior(self.hi, HI_ATENCAO, HI_FALHA)

    @property
    def status_ci(self) -> str:
        """CI RTOG dos DOIS lados: derramar fora e não cobrir são dois defeitos."""
        if not self.na_prescricao:
            return NA
        return pior(_maior_e_pior(self.ci_rtog, CI_ALTO_ATENCAO, CI_ALTO_FALHA),
                    _menor_e_pior(self.ci_rtog, CI_BAIXO_ATENCAO, CI_BAIXO_FALHA))

    @property
    def status(self) -> str:
        return pior(self.status_cobertura, self.status_quente, self.status_hi,
                    self.status_ci)


def e_alvo(nome: str) -> bool:
    """PTV pelo NOME. Mesma regra do ``grafico_dvh._e_alvo``, e é deliberado que seja:
    a lista de alvos da aba tem de bater com as curvas do DVH da ficha, senão o
    físico vê um conjunto de PTV num documento e outro no outro.
    """
    return "ptv" in str(nome or "").lower()


def alvos_do_struct(rs) -> list[str]:
    """Nomes das estruturas de alvo no RT Struct, na ordem em que ele as traz.

    Também aceita o ``RTROIObservationsSequence`` quando ele marca o tipo DICOM
    como PTV: no Monaco há alvo cujo nome não contém "PTV", e aí o tipo é a
    única pista que sobra.
    """
    tipos: dict[int, str] = {}
    for obs in getattr(rs, "RTROIObservationsSequence", []) or []:
        num = getattr(obs, "ReferencedROINumber", None)
        if num is not None:
            tipos[int(num)] = str(
                getattr(obs, "RTROIInterpretedType", "") or "").upper()
    nomes = []
    for r in getattr(rs, "StructureSetROISequence", []) or []:
        nome = str(getattr(r, "ROIName", "") or "")
        num = getattr(r, "ROINumber", None)
        if e_alvo(nome) or (num is not None and tipos.get(int(num)) == "PTV"):
            nomes.append(nome)
    return nomes


def _sem_acento(texto: str) -> str:
    import unicodedata
    forma = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in forma
                   if unicodedata.category(c) != "Mn").upper().strip()


# Nomes que denunciam ESTRUTURA DE OTIMIZAÇÃO com cara de alvo.
#
# "PTV_casca" é o anel em volta do alvo que o otimizador usa para forçar a
# queda da dose fora dele; "PTV núcleo" é o miolo que recebe o reforço. Nenhum
# dos dois é volume a tratar, e julgá-los por ICRU 83 produz linha vermelha em
# plano correto: a casca é uma casca, então recebe metade da prescrição por
# construção e sai com cobertura péssima e conformidade absurda.
#
# Medido no acervo em 02/09/2026: 5 ROI em 4 dos 19 casos (TC7, TC9, TC11,
# TC13), todas "*PTV_casca*". Nenhum alvo de verdade contém as duas palavras —
# em particular "PTV cúneo E" (TC6) NÃO casa com "nucleo", que é a colisão que
# se teme ao comparar por pedaço de nome.
#
# É divergência DELIBERADA de ``grafico_dvh._e_alvo``, que esta aba segue no resto: a
# curva da casca no DVH da ficha é informação legítima para quem olha o
# gráfico; uma linha de tabela que a JULGA contra ICRU 83 não é.
OTIMIZACAO = ("CASCA", "NUCLEO")


def e_otimizacao(nome) -> bool:
    """O nome diz "estrutura de otimização" em vez de "alvo"?"""
    limpo = _sem_acento(nome)
    return any(palavra in limpo for palavra in OTIMIZACAO)


def _alvos_para_analise(rs_ds) -> tuple:
    """``(alvos a analisar, estruturas de otimização)`` do RT Struct."""
    nomes = alvos_do_struct(rs_ds)
    fora = [n for n in nomes if e_otimizacao(n)]
    return [n for n in nomes if n not in fora], fora


def alvo_primario(rp_ds, nomes: list) -> str:
    """O nome do alvo a que a prescrição do plano pertence, segundo o DICOM.

    O RT Plan escreve o alvo da prescrição em
    ``DoseReferenceSequence[].DoseReferenceDescription`` — é o equivalente do
    ``plan.TargetVolumeID`` que o ESAPI entrega pronto. Medido nos 19 casos de
    ``TCs_Teste``: existe em todos, e é a única pista de qual PTV a dose de
    prescrição descreve.

    O casamento é tolerante porque o campo vem CORTADO. No TC7 a descrição é
    ``1_PTV esternocla`` para uma estrutura chamada ``1_PTV esternoclavicular``:
    dezesseis caracteres, e comparar por igualdade não acha nada. Compara-se sem
    acento e sem caixa, primeiro por igualdade e depois por prefixo — nessa
    ordem, senão um ``PTV`` genérico casaria com o primeiro PTV da lista.

    Devolve "" quando não há descrição ou nada casa: é melhor não apontar
    primário nenhum do que apontar o errado, e quem chama tem o critério de
    reserva (a mediana perto de 100 %).
    """
    descricoes = []
    for dr in getattr(rp_ds, "DoseReferenceSequence", []) or []:
        d = _sem_acento(getattr(dr, "DoseReferenceDescription", ""))
        if d:
            descricoes.append(d)
    if not descricoes:
        return ""
    limpos = {n: _sem_acento(n) for n in nomes}
    for d in descricoes:
        for nome, limpo in limpos.items():
            if limpo == d:
                return nome
    for d in descricoes:
        for nome, limpo in limpos.items():
            if limpo.startswith(d) or d.startswith(limpo):
                return nome
    return ""


def _volume_do_voxel_cc(grade) -> float:
    """Volume de um voxel da grade de dose, em cc.

    Os eixos vêm em mm e são regulares (``dose3d`` garante isso ao construir a
    grade), então o passo é a diferença entre dois pontos quaisquer.
    """
    def _passo(eixo) -> float:
        return float(abs(eixo[1] - eixo[0])) if len(eixo) > 1 else 1.0
    return _passo(grade.x) * _passo(grade.y) * _passo(grade.z) / 1000.0


def indices_do_alvo(grade, rs, nome: str, presc_gy: float) -> IndicesAlvo:
    """Índices ICRU 83 e de conformidade de UM alvo sobre a grade de dose.

    ``presc_gy`` é a dose TOTAL prescrita ao plano, em Gy — é a ela que o RT
    Dose está normalizado, porque a grade guarda a dose do curso inteiro e não
    a de uma fração.

    Num plano com boost integrado (SIB) há mais de uma prescrição e só uma entra
    aqui: o alvo de dose mais baixa sai com D98 abaixo de 100 %, e isso não é
    defeito do plano. A tela diz qual prescrição foi usada — sem isso o número
    seria lido como falta de cobertura.
    """
    from isocentro.dicom import dvh

    ind = IndicesAlvo(nome=nome)
    mascara = dvh.mascara_3d(grade, rs, nome)
    if mascara is None:
        return ind

    voxel_cc = _volume_do_voxel_cc(grade)
    amostras = grade.dose[mascara].astype(np.float64)
    ind.volume_cc = float(mascara.sum()) * voxel_cc
    if amostras.size == 0 or not (presc_gy and presc_gy > 0):
        return ind

    def _pct(dose_gy) -> float:
        return float(dose_gy) / float(presc_gy) * 100.0

    # D_x% = a dose que x % do volume RECEBE OU SUPERA — logo, o percentil
    # (100 − x) da amostra. Trocar os dois põe D98 e D2 no lugar um do outro, e
    # o sintoma é um HI negativo.
    ind.d98_gy = float(np.percentile(amostras, 2.0))
    ind.d50_gy = float(np.percentile(amostras, 50.0))
    ind.d2_gy = float(np.percentile(amostras, 98.0))
    ind.d98 = _pct(ind.d98_gy)
    ind.d95 = _pct(np.percentile(amostras, 5.0))
    ind.d50 = _pct(ind.d50_gy)
    ind.d2 = _pct(ind.d2_gy)
    ind.d_media = _pct(amostras.mean())
    if ind.d50 > 0:
        ind.hi = (ind.d2 - ind.d98) / ind.d50

    # Conformidade: contar voxels dos dois lados da MESMA grade. O volume da
    # isodose sai da grade inteira, e não de dentro do corpo — fora do paciente
    # a dose não chega à prescrição, então a diferença é de arredondamento; e
    # exigir o BODY faria o índice sumir nos casos em que ele não veio.
    #
    # Só para o alvo que RECEBE esta prescrição. A isodose de prescrição de um
    # plano de mama dividida pelo volume do PTV da fossa dá um "CI" de 13,7, e
    # a isodose de 60 Gy dividida pelo PTV de 48 Gy de um boost integrado dá
    # 0,27: não são índices ruins, são índices de outra coisa.
    if ind.na_prescricao:
        v_alvo = float(mascara.sum())
        presc = grade.dose >= float(presc_gy)
        v_presc = float(presc.sum())
        if v_alvo > 0 and v_presc > 0:
            v_intersec = float(np.logical_and(mascara, presc).sum())
            ind.ci_rtog = v_presc / v_alvo
            ind.ci_paddick = (v_intersec * v_intersec) / (v_alvo * v_presc)
    return ind


def gradiente(grade, presc_gy: float) -> float:
    """Índice de gradiente: volume da meia-prescrição / volume da prescrição.

    É do PLANO, não do alvo — as duas isodoses são as mesmas seja qual for o
    PTV que se olhe. Ficava repetida em cada linha de alvo na primeira versão,
    e um número idêntico em quatro linhas se lê como quatro medidas que por
    acaso coincidiram.
    """
    if not (presc_gy and presc_gy > 0):
        return float("nan")
    v_presc = float((grade.dose >= float(presc_gy)).sum())
    if v_presc <= 0:
        return float("nan")
    return float((grade.dose >= float(presc_gy) / 2.0).sum()) / v_presc


# ── Complexidade dos campos ──────────────────────────────────────────────────

@dataclass
class ComplexidadeFeixe:
    """Métricas de complexidade de UM campo."""
    nome: str
    tecnica: str = ""
    mu: float = float("nan")
    mcsv: float = float("nan")
    sas: float = float("nan")          # fração 0..1 no limiar SAS_LARGO_MM
    sas_estreito: float = float("nan")
    abertura_mm: float = float("nan")
    percurso_mm: float = float("nan")
    n_pontos: int = 0
    modulado: bool = False

    @property
    def status_mcsv(self) -> str:
        if not self.modulado:
            return NA
        return _menor_e_pior(self.mcsv, MCS_ATENCAO, MCS_FALHA)

    @property
    def status_sas(self) -> str:
        if not self.modulado:
            return NA
        return _maior_e_pior(self.sas, SAS_ATENCAO, SAS_FALHA)

    @property
    def status(self) -> str:
        return pior(self.status_mcsv, self.status_sas)


def _mlc_dos_pontos(beam_ds):
    """(banco A, banco B, peso cumulativo) por ponto de controle, em mm.

    **A armadilha do DICOM.** O padrão permite que um ponto de controle traga
    apenas o que MUDOU em relação ao anterior. Na prática o Eclipse repete o
    MLC em todos, mas isso não é garantido, e há RT Plan em que só o primeiro
    ponto carrega ``BeamLimitingDevicePositionSequence``. Ler ponto a ponto sem
    arrastar o último valor conhecido dá aberturas zeradas no meio do arco: o
    MCSv despenca e o campo aparece como o mais complexo do plano. Daí o
    ``ultimo_a``/``ultimo_b``.

    O ESAPI não tem esse problema porque resolve o arrasto antes de entregar as
    posições — é a única diferença real entre este cálculo e o do C#.

    Devolve ``None`` quando o campo não tem multilâminas.
    """
    cps = list(getattr(beam_ds, "ControlPointSequence", []) or [])
    if len(cps) < 2:
        return None

    ultimo_a = ultimo_b = None
    lista_a: list = []
    lista_b: list = []
    pesos: list[float] = []
    for cp in cps:
        for dev in getattr(cp, "BeamLimitingDevicePositionSequence", []) or []:
            tipo = str(getattr(dev, "RTBeamLimitingDeviceType", "") or "").upper()
            if not tipo.startswith("MLC"):
                continue
            pos = np.asarray(getattr(dev, "LeafJawPositions", []) or [], dtype=float)
            if pos.size < 2 or pos.size % 2:
                continue
            meio = pos.size // 2
            ultimo_a, ultimo_b = pos[:meio], pos[meio:]
        if ultimo_a is None:
            # Nem o primeiro ponto trouxe MLC: campo sem multilâminas.
            continue
        lista_a.append(ultimo_a)
        lista_b.append(ultimo_b)
        pesos.append(float(getattr(cp, "CumulativeMetersetWeight", 0.0) or 0.0))

    if len(lista_a) < 2:
        return None
    return np.array(lista_a), np.array(lista_b), np.array(pesos)


def _lsv(pos, ativas) -> float:
    """Leaf Sequence Variability de UM banco num ponto de controle (McNiven).

    Mede o quanto as lâminas VIZINHAS diferem entre si: banco alinhado dá 1,
    banco em serrote dá perto de 0.
    """
    p = pos[ativas]
    if p.size < 2:
        return 1.0
    faixa = float(p.max() - p.min())
    if faixa <= 0:
        return 1.0
    return float(np.sum(faixa - np.abs(np.diff(p))) / ((p.size - 1) * faixa))


def complexidade_do_feixe(beam_ds, mu: float = float("nan"),
                          tecnica: str = "") -> ComplexidadeFeixe:
    """MCSv, SAS, abertura média e percurso de lâminas de um campo.

    MCSv (Masi 2013) é o MCS de McNiven levado ao arco: cada SEGMENTO entre dois
    pontos de controle contribui com ``AAV × LSV``, pesado pela fração de UM que
    ele entrega. Menor = mais modulado = mais difícil de entregar.

    A abertura é contada em MILÍMETROS DE VÃO, sem pesar pela largura da lâmina
    — é o que o C# faz, e manter a mesma conta é o que permite comparar um caso
    analisado aqui com o relatório que o Eclipse já emitiu. Pesar pela largura
    (o DICOM tem ``LeafPositionBoundaries``, e o ESAPI não entrega isso de
    graça) seria mais fiel à definição de área do McNiven, mas os dois números
    deixariam de ser comparáveis sem aviso.
    """
    nome = str(getattr(beam_ds, "BeamName", "")
               or getattr(beam_ds, "BeamNumber", "") or "")
    m = ComplexidadeFeixe(nome=nome, tecnica=tecnica, mu=float(mu))

    lido = _mlc_dos_pontos(beam_ds)
    if lido is None:
        return m
    banco_a, banco_b, pesos = lido
    n_cp = banco_a.shape[0]
    m.n_pontos = n_cp

    aberturas = np.clip(banco_b - banco_a, 0.0, None)      # (n_cp, n_lâminas)
    maior_por_lamina = aberturas.max(axis=0)
    ativas = np.flatnonzero(maior_por_lamina > ABERTO_MM)
    if ativas.size == 0:
        return m

    ab = aberturas[:, ativas]
    soma_maxima = float(maior_por_lamina[ativas].sum())
    abertas = ab > ABERTO_MM
    n_abertas = abertas.sum(axis=1).astype(float)

    # AAV: quanto da abertura MÁXIMA de cada lâmina está sendo usado agora.
    aav = (ab.sum(axis=1) / soma_maxima) if soma_maxima > 0 else np.zeros(n_cp)
    sas = np.where(n_abertas > 0,
                   np.logical_and(abertas, ab < SAS_LARGO_MM).sum(axis=1)
                   / np.where(n_abertas > 0, n_abertas, 1.0), 0.0)
    sas_e = np.where(n_abertas > 0,
                     np.logical_and(abertas, ab < SAS_ESTREITO_MM).sum(axis=1)
                     / np.where(n_abertas > 0, n_abertas, 1.0), 0.0)
    media = np.where(n_abertas > 0,
                     ab.sum(axis=1) / np.where(n_abertas > 0, n_abertas, 1.0), 0.0)
    lsv = np.array([_lsv(banco_a[i], ativas) * _lsv(banco_b[i], ativas)
                    for i in range(n_cp)])

    # Peso do SEGMENTO = UM entregue entre dois pontos de controle. Negativo não
    # existe: o peso cumulativo só cresce, e um plano em que ele cai está
    # corrompido — zerar é mais seguro que somar um peso negativo, que puxaria a
    # média para fora da faixa 0..1 sem nenhum aviso.
    peso = np.clip(np.diff(pesos), 0.0, None)
    if peso.sum() <= 0:
        # Pesos degenerados (todos iguais, ou ausentes): média simples entre os
        # segmentos. Sem isto, um campo estático dava divisão por zero e saía
        # inteiro como "sem dado".
        peso = np.ones(n_cp - 1)

    def _medio(v) -> float:
        meio = 0.5 * (v[:-1] + v[1:])
        return float(np.sum(peso * meio) / peso.sum())

    m.mcsv = float(np.sum(peso * (0.5 * (aav[:-1] + aav[1:]))
                          * (0.5 * (lsv[:-1] + lsv[1:]))) / peso.sum())
    m.sas = _medio(sas)
    m.sas_estreito = _medio(sas_e)
    m.abertura_mm = _medio(media)
    m.percurso_mm = float(np.abs(np.diff(banco_a[:, ativas], axis=0)).sum()
                          + np.abs(np.diff(banco_b[:, ativas], axis=0)).sum())
    # Campo modulado é o que tem sequência dinâmica: mais de dois pontos de
    # controle. Num campo estático o MCSv existe aritmeticamente e não quer
    # dizer nada — daí o status ``NA``, em vez de um OK enganoso.
    m.modulado = n_cp > 2
    return m


def mu_por_cgy(mu_total, dose_fracao_gy) -> float:
    """Fator de modulação: UM de UMA fração por cGy DAQUELA fração.

    **Em cGy, não em Gy.** Um acelerador é calibrado para entregar 1 cGy por UM
    na condição de referência, então este número é diretamente "quantas vezes o
    plano gasta mais UM que um campo aberto entregaria": 3,25 é um VMAT
    modulado, 1,1 é um campo simples. Em UM/Gy os mesmos planos saem 325 e 110
    — grandezas certas que não se comparam de cabeça com nada, e foi o que o
    físico apontou na tela de 02/09/2026.

    O ``BeamMeterset`` do RT Plan é o UM de uma fração. O C# do ESAPI dividia a
    soma desses UM pela dose TOTAL do plano (``plan.TotalDose``), e o resultado
    saía dividido pelo número de frações: um VMAT de próstata com 600 UM por
    fração e 60 Gy em 30 frações dava 0,1 UM/cGy contra os 3,0 reais — sempre
    abaixo do limiar, então o indicador nunca acendia. Aqui a divisão é pela
    dose da FRAÇÃO, que é o que torna o número comparável ao da literatura.
    """
    if not (dose_fracao_gy and dose_fracao_gy > 0):
        return float("nan")
    if not (mu_total and mu_total > 0):
        return float("nan")
    return float(mu_total) / (float(dose_fracao_gy) * 100.0)


# ── A análise de um plano ────────────────────────────────────────────────────

@dataclass
class AnaliseQualidade:
    """O que a aba mostra de um plano — ou da soma dos planos."""
    rotulo: str = ""
    presc_gy: float = float("nan")
    dose_fracao_gy: float = float("nan")
    num_fracoes: object = None
    mu_total: float = float("nan")
    mu_cgy: float = float("nan")
    gi: float = float("nan")
    soma: bool = False          # é a análise da dose COMBINADA?
    alvos: list = field(default_factory=list)
    feixes: list = field(default_factory=list)
    avisos: list = field(default_factory=list)

    @property
    def status_mu_cgy(self) -> str:
        return _maior_e_pior(self.mu_cgy, MUCGY_ATENCAO, MUCGY_FALHA)

    @property
    def hipofracionado(self) -> bool:
        """SRS/SBRT pela dose por fração e pelo número de frações."""
        try:
            fx = int(self.num_fracoes) if self.num_fracoes else 0
        except (TypeError, ValueError):
            fx = 0
        return (np.isfinite(self.dose_fracao_gy)
                and self.dose_fracao_gy >= GI_SO_ACIMA_DE_GY_FRACAO
                and 0 < fx <= GI_SO_ATE_FRACOES)

    @property
    def status_gi(self) -> str:
        if not self.hipofracionado:
            return NA
        return _maior_e_pior(self.gi, GI_ATENCAO, GI_FALHA)

    @property
    def status(self) -> str:
        return pior(*self._todos())

    def _todos(self) -> list:
        return ([a.status for a in self.alvos]
                + [f.status for f in self.feixes]
                + [self.status_mu_cgy, self.status_gi])

    def contagem(self) -> dict:
        """Quantos itens em cada status — alimenta as pílulas do resumo."""
        todos = self._todos()
        return {s: todos.count(s) for s in (FALHA, ATENCAO, OK, NA)}


def _avisos_dos_alvos(an: AnaliseQualidade, vazias=(), otimizacao=()) -> list:
    """O que a lista de alvos exige que a tela diga em palavras.

    Um índice sozinho não se defende: quem lê um D98 de 81 % precisa saber se
    olha um alvo mal coberto, um alvo de outro plano ou o alvo de dose baixa de
    um boost integrado. São três coisas diferentes com o mesmo número.

    ``vazias`` e ``otimizacao`` são os nomes que NÃO estão em ``an.alvos`` — as
    ROI sem contorno e as cascas/núcleos, que saíram da tabela. Vêm por
    parâmetro justamente porque já não estão na análise: o que sai da tabela
    não pode sair da tela.
    """
    avisos = []
    if otimizacao:
        avisos.append(
            "Fora da análise: " + ", ".join(otimizacao) + ". O nome diz "
            "estrutura de OTIMIZAÇÃO — casca ou núcleo —, e não volume a "
            "tratar: a casca recebe parte da prescrição por construção, e "
            "julgá-la por ICRU 83 daria linha vermelha em plano correto. Ela "
            "continua no DVH da ficha, onde a curva ainda diz alguma coisa.")
    if vazias:
        avisos.append(
            "Sem contorno: " + ", ".join(vazias) + ". São ROI de alvo "
            "declaradas no RT Struct e nunca desenhadas — sem volume não há "
            "índice nenhum a calcular, então ficam FORA da tabela. Continuam "
            "escritas aqui porque uma delas pode ser um alvo que alguém "
            "esqueceu de contornar, e isso não pode sumir da tela.")
    fora = [a.nome for a in an.alvos if not a.deste_plano]
    if fora:
        avisos.append(
            "Fora deste plano: " + ", ".join(fora) + ". Recebem quase nada da "
            "dose desta grade — são alvos de outro plano do mesmo curso, e "
            "aparecem sem status para não somar reprovações que não existem."
            + (" Analise a SOMA para avaliar a cobertura do curso inteiro."
               if not an.soma else ""))
    outra_dose = [a.nome for a in an.alvos
                  if a.deste_plano and not a.na_prescricao]
    if outra_dose:
        avisos.append(
            "Prescrição própria desconhecida: " + ", ".join(outra_dose)
            + f". Recebem dose desta grade, mas não os {an.presc_gy:g} Gy "
            "prescritos — é o alvo de dose baixa de um boost integrado, ou uma "
            "estrutura de otimização. O RT Plan traz UMA prescrição só, então "
            "não há a que comparar: os números aparecem, o status não. Julgue "
            "pela dose em Gy, não pela percentagem.")
    return avisos


def analisar(plano: dict) -> AnaliseQualidade:
    """Analisa UM plano do app (``gui.JanelaPrincipal._planos[i]``).

    Cada perna falha sozinha: um caso sem RT Dose ainda tem a complexidade dos
    campos, e um caso cujo RT Plan não traz MLC ainda tem os índices do alvo.
    Abortar a análise inteira por causa de uma peça faltando daria tela vazia
    justamente no caso incompleto, que é onde ela mais serviria.
    """
    from isocentro.dicom import dose3d

    rp = plano.get("rp") or {}
    an = AnaliseQualidade(rotulo=str(plano.get("rotulo") or ""))

    presc = rp.get("dose_total")
    fracao = rp.get("dose_fracao")
    an.presc_gy = float(presc) if presc else float("nan")
    an.dose_fracao_gy = float(fracao) if fracao else float("nan")
    an.num_fracoes = rp.get("num_fracoes")

    # (A) Índices do alvo.
    rd_ds, rs_ds = plano.get("rd_ds"), plano.get("rs_ds")
    if rd_ds is None:
        an.avisos.append("Sem RT Dose: os índices do alvo não podem ser calculados.")
    elif rs_ds is None:
        an.avisos.append("Sem RT Struct: os índices do alvo não podem ser calculados.")
    elif not np.isfinite(an.presc_gy) or an.presc_gy <= 0:
        an.avisos.append("Sem dose de prescrição no RT Plan: os índices do alvo "
                         "seriam relativos a nada.")
    else:
        nomes, otimizacao = _alvos_para_analise(rs_ds)
        if not nomes:
            an.avisos.append(
                "Só estruturas de otimização no RT Struct: nenhum alvo a "
                "analisar." if otimizacao
                else "Nenhum PTV encontrado no RT Struct.")
            an.avisos.extend(_avisos_dos_alvos(an, (), otimizacao))
        else:
            grade = dose3d.grade_de_rd(rd_ds)
            todos = [indices_do_alvo(grade, rs_ds, n, an.presc_gy)
                     for n in nomes]
            # ROI sem contorno não vira linha. Ela não tem número nenhum para
            # mostrar — a linha inteira saía de travessões —, e a coluna de
            # situação a julgava com uma palavra ("estrutura vazia") que só
            # repetia o que os travessões já diziam. No TC12 eram duas linhas
            # assim em quatro, e cada uma contava um "sem status" na pílula do
            # resumo: a tela anunciava nove itens não avaliados num plano que
            # tinha dois. O nome delas continua na nota do caso.
            an.alvos = [a for a in todos if not a.vazia]
            vazias = [a.nome for a in todos if a.vazia]
            primario = alvo_primario(plano.get("rp_ds"), nomes)
            for a in an.alvos:
                a.primario = bool(primario) and a.nome == primario
            an.gi = gradiente(grade, an.presc_gy)
            an.avisos.extend(_avisos_dos_alvos(an, vazias, otimizacao))

    # (B) Complexidade dos campos.
    rp_ds = plano.get("rp_ds")
    if rp_ds is None:
        an.avisos.append("Sem o RT Plan original: a complexidade dos campos não "
                         "pode ser calculada.")
        return an

    mu_por_feixe: dict = {}
    for grupo in getattr(rp_ds, "FractionGroupSequence", []) or []:
        for rb in getattr(grupo, "ReferencedBeamSequence", []) or []:
            num = getattr(rb, "ReferencedBeamNumber", None)
            meterset = getattr(rb, "BeamMeterset", None)
            if num is not None and meterset is not None:
                mu_por_feixe[int(num)] = float(meterset)

    tecnicas = {str(f.get("nome") or ""): str(f.get("tecnica") or "")
                for f in (rp.get("feixes") or [])}
    for beam in getattr(rp_ds, "BeamSequence", []) or []:
        if str(getattr(beam, "TreatmentDeliveryType", "TREATMENT")).upper() == "SETUP":
            continue
        num = getattr(beam, "BeamNumber", None)
        nome = str(getattr(beam, "BeamName", "") or "")
        an.feixes.append(complexidade_do_feixe(
            beam,
            mu=mu_por_feixe.get(int(num), float("nan")) if num is not None
            else float("nan"),
            tecnica=tecnicas.get(nome, "")))

    mus = [f.mu for f in an.feixes if np.isfinite(f.mu)]
    an.mu_total = float(sum(mus)) if mus else float("nan")
    an.mu_cgy = mu_por_cgy(an.mu_total, an.dose_fracao_gy)
    if not np.isfinite(an.mu_cgy) and an.feixes:
        an.avisos.append("Sem UM ou sem dose por fração no RT Plan: o fator de "
                         "modulação (UM/cGy) não pôde ser calculado.")
    return an


def alvos_em_comum(analises: list) -> list:
    """Os alvos que MAIS DE UM plano trata — a assinatura de um boost.

    É o que separa os dois cursos multi-plano que existem na prática:

    * **boost** (sequencial ou integrado) — os planos empilham dose no MESMO
      alvo, e a cobertura só existe na soma;
    * **alvos diferentes** — mama e fossa supraclavicular, o TC8 —, em que cada
      plano trata o seu e somar as prescrições não descreve paciente nenhum.

    A distinção não é estética. Somando o TC8 dá 80,1 Gy de "prescrição" e todo
    alvo cai para ~50 % de cobertura: quatro linhas vermelhas num curso correto.
    """
    conta: dict[str, int] = {}
    for an in analises:
        for a in an.alvos:
            if a.deste_plano:
                conta[a.nome] = conta.get(a.nome, 0) + 1
    return [n for n, q in conta.items() if q > 1]


def analisar_soma(planos: list, analises: list | None = None,
                  rotulo: str = "Soma dos planos") -> AnaliseQualidade:
    """Índices do alvo sobre a dose COMBINADA de vários planos.

    É a análise que responde à pergunta de um curso com boost: a cobertura do
    alvo não está em nenhum dos planos isolados, e sim na soma. Reaproveita
    ``dose3d.somar_rds``, o mesmo caminho da ficha soma; quem chama é
    responsável por só juntar planos da MESMA tomografia (ver
    ``gui.JanelaPrincipal._planos_mesma_tc``), porque somar grades de geometrias
    diferentes dá um cubo que não corresponde a paciente nenhum.

    ``analises`` são as análises por plano já calculadas — é delas que sai a
    decisão de somar ou não (ver :func:`alvos_em_comum`). Sem elas, são
    recalculadas aqui, ao custo de ler as grades duas vezes.

    A COMPLEXIDADE não é somada: ela é por campo, e um campo pertence a um plano
    só. A tabela de campos da soma fica vazia de propósito — quem quer a
    complexidade escolhe o plano.
    """
    from isocentro.dicom import dose3d

    an = AnaliseQualidade(rotulo=rotulo, soma=True)
    rds = [p.get("rd_ds") for p in planos if p.get("rd_ds") is not None]
    rs_ds = next((p.get("rs_ds") for p in planos if p.get("rs_ds") is not None),
                 None)
    if len(rds) < 2 or rs_ds is None:
        an.avisos.append("A soma precisa de pelo menos dois RT Dose e de um "
                         "RT Struct.")
        return an

    if analises is None:
        analises = [analisar(p) for p in planos]
    comuns = alvos_em_comum(analises)
    if not comuns:
        an.avisos.append(
            "Os planos deste curso tratam alvos DIFERENTES — nenhum PTV é "
            "tratado por mais de um deles. Somar as prescrições daria uma dose "
            "que ninguém prescreveu, e todo alvo cairia para a metade da "
            "cobertura. A avaliação certa aqui é a de cada plano, separada.")
        return an

    # A prescrição da soma é a SOMA das prescrições — é o que o alvo comum
    # recebe ao fim do curso. Um plano sem dose_total no RT Plan invalida a
    # conta inteira: 40 Gy de dois planos somados contra uma prescrição de 40
    # daria 100 % de cobertura num alvo que recebeu o dobro.
    doses = [(p.get("rp") or {}).get("dose_total") for p in planos]
    if any(not d for d in doses):
        an.avisos.append("Algum plano não traz dose de prescrição: a soma não "
                         "tem a que normalizar os índices.")
        return an
    an.presc_gy = float(sum(float(d) for d in doses))
    an.dose_fracao_gy = float(sum(
        float((p.get("rp") or {}).get("dose_fracao") or 0) for p in planos))
    an.num_fracoes = sum(int((p.get("rp") or {}).get("num_fracoes") or 0)
                         for p in planos) or None

    grade = dose3d.somar_rds(rds)
    # Sem marcar primário: "prescrição do plano" não existe numa soma de
    # planos, e marcar os alvos comuns com esse rótulo dizia que os DOIS eram o
    # alvo da prescrição — no TC12 saíam PTV40Gy e PTV60Gy os dois em negrito.
    # Quem são eles já está escrito no aviso, com o nome.
    nomes, otimizacao = _alvos_para_analise(rs_ds)
    todos = [indices_do_alvo(grade, rs_ds, n, an.presc_gy) for n in nomes]
    an.alvos = [a for a in todos if not a.vazia]      # ver ``analisar``
    vazias = [a.nome for a in todos if a.vazia]
    an.gi = gradiente(grade, an.presc_gy)
    an.avisos.append(
        f"Dose combinada de {len(rds)} planos, normalizada pela soma das "
        f"prescrições ({an.presc_gy:g} Gy). Alvo tratado por mais de um plano: "
        + ", ".join(comuns) + ".")
    an.avisos.extend(_avisos_dos_alvos(an, vazias, otimizacao))
    return an
