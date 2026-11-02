"""Cálculo paralelo — verificação independente de UM (AAPM TG-219).

Porte do `app.py` do repositório PRIVADO `geovanipena/parallel-mu-check`, com o
dado de feixe que mora na pasta do Drive **CODIGO CALC. PARALELO**. O formalismo
é o do cálculo de mão de sempre — TMR, Scp, fator distância —, aplicado segmento
a segmento:

    L   = 2·X·Y / (X+Y)                       campo equivalente, cm
    UM  = Σ_segmentos [ ΔMw · Dose / (TMR·Scp·FD) ]

    com filtro:
    UM  = k·Dose/(TMRw·Scp·FW·FD) + (1−k)·Σ_segmentos

``ΔMw`` é a diferença de ``CumulativeMetersetWeight`` entre pontos de controle
consecutivos. **Campo STATIC soma os CP ímpares; DYNAMIC soma todos menos o 0.**

**Três coisas que este módulo NÃO faz, e é importante que não faça em silêncio:**

1. **Não calcula com a tabela de outra máquina.** É a trava de
   :func:`maquina_do_plano`. O dado que veio junto com o código é de uma Elekta
   do SAT; os planos desta clínica são Varian. Um cálculo paralelo com TMR de
   outro acelerador não é uma verificação — é um número com aparência de
   verificação, que é pior que número nenhum. Sem tabela da máquina do plano, o
   resultado sai marcado como DEMONSTRAÇÃO e sem veredito.
2. **Não calcula campo com filtro.** O ``k`` (fração da dose entregue com o
   filtro) não sai do DICOM: a tag do ângulo do wedge devolve 60 no Elekta
   independentemente do valor real, e o programa de origem PERGUNTA o ``k`` ao
   usuário. Esta aba não tem onde perguntar, então campo com filtro fica sem
   cálculo, com o motivo escrito. Medido em 31/08/2026: nenhum dos 84 feixes de
   ``TCs_Teste`` usa filtro, então a perna não faz falta hoje.
3. **Não usa a abertura do MLC.** O campo equivalente sai dos MORDENTES, como no
   programa de origem. Num campo modulado isso ignora justamente a modulação: a
   abertura real é menor que o mordente, o TMR e o Scp saem altos demais e o UM
   calculado sai BAIXO. Separar Sc (mordente) de Sp (abertura) seria o certo, e
   exigiria duas tabelas em vez de uma Sc,p combinada. Enquanto não houver, o
   resultado de IMRT/VMAT é rastreio grosseiro e a tela diz isso.

**A profundidade é CALCULADA, e essa é a maior diferença para o original.** O
`app.py` lê ``BeamDosePointEquivalentDepth (300a,0089)`` e desiste sem ela.
Medido nos 26 planos de ``TCs_Teste``: **nenhum** traz essa tag, nem
``BeamDosePointDepth``, nem ``BeamDosePointSSD`` — são tags que o Monaco escreve
e este Eclipse não. Aqui a profundidade vem da geometria:

    profundidade = SAD − SSD          (ambos em cm, ao ISOCENTRO)

com o SSD do próprio RT Plan (``SourceToSurfaceDistance``) ou, na falta dele, o
que ``dicom_rt.calcular_ssds`` calcula pelo contorno BODY. Duas consequências
que precisam estar na tela:

* é profundidade **física**, não radiológica. Em mama e pulmão a diferença é
  grande, e o desvio contra o TPS vai estourar por causa do pulmão, não por erro
  do plano;
* supõe que o **ponto de dose é o isocentro**. O ``BeamDose`` do RT Plan é a
  dose no ponto de referência, e a geometria desse ponto não está no arquivo.

Referências
-----------
AAPM TG-219 (2021) — verificação independente de dose/UM para IMRT e VMAT.
AAPM TG-114 (2011) — verificação de UM em cálculo com heterogeneidade.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from isocentro import raiz
from isocentro.dados import ambiente

# Limites do DESVIO entre o UM do plano e o calculado, em %.
#
# O TG-219 não fixa número universal — manda o serviço estabelecer o seu na
# validação, como o TG-218 faz para o gamma. Estes são os de uso corrente na
# literatura para campo simples; para IMRT/VMAT o próprio TG-219 admite faixas
# bem mais largas. Enquanto a validação local não existir, valem como referência
# e a tela diz isso (ver ``qualidade.CALIBRADO``, que rege o mesmo aviso).
DESVIO_ATENCAO = 3.0
DESVIO_FALHA = 5.0

# Campo com modulação: o mordente não descreve a abertura (ver o item 3 do
# cabeçalho). O desvio esperado é grande e não significa erro, então a faixa é
# outra — e mesmo assim o resultado entra como rastreio, nunca como veredito.
DESVIO_ATENCAO_MODULADO = 10.0
DESVIO_FALHA_MODULADO = 20.0

PASTA_PADRAO = "dados_feixe"


def pasta_dados() -> Path:
    """Onde moram as tabelas de feixe.

    Variável de ambiente com precedência, padrão ao lado do programa — a mesma
    regra do resto da configuração (ver o CLAUDE.md). Lida por
    ``ambiente.ler``, nunca por ``os.environ`` direto: os três nomes
    (``ISOCENTRO_*``, ``RADIOTERAFICHA_*`` e ``FICHAPY_*``) têm de continuar valendo.
    """
    escolhido = ambiente.ler("ISOCENTRO_DADOS_FEIXE")
    if escolhido:
        return Path(escolhido)
    # "Ao lado do programa" é literal: a pasta do executável, e não a do
    # módulo. Empacotado, a conta antiga (``dirname(__file__)``) caía dentro do
    # ``_internal/``, onde ``dados_feixe/`` não é desdobrado — sem tabela, o
    # cálculo paralelo vira DEMONSTRAÇÃO e não dá veredito, calado.
    return raiz.pasta_do_app() / PASTA_PADRAO


# ── Cadastro de máquinas ─────────────────────────────────────────────────────

@dataclass
class Maquina:
    """Uma máquina com dado de feixe cadastrado."""
    chave: str
    rotulo: str = ""
    fabricante: str = ""
    exemplo: bool = False
    fonte: str = ""
    nomes_dicom: list = field(default_factory=list)
    energias: dict = field(default_factory=dict)

    def fd(self, energia_mv) -> float | None:
        return self._fator(energia_mv, "fd")

    def fw(self, energia_mv) -> float | None:
        return self._fator(energia_mv, "fw")

    def _fator(self, energia_mv, qual: str):
        dados = _energia_casada(self.energias, energia_mv)
        if not dados:
            return None
        v = dados.get(qual)
        return float(v) if v is not None else None


def _energia_casada(mapa: dict, energia_mv) -> dict:
    """A entrada da energia, tolerando "6" contra 6.0 e vírgula decimal."""
    try:
        alvo = float(str(energia_mv).replace(",", "."))
    except (TypeError, ValueError):
        return {}
    for chave, dados in (mapa or {}).items():
        try:
            if abs(float(str(chave).replace(",", ".")) - alvo) < 0.01:
                return dados or {}
        except (TypeError, ValueError):
            continue
    return {}


def carregar_maquinas(pasta=None) -> dict:
    """Lê ``_maquinas.json``. Devolve ``{chave: Maquina}``; ``{}`` se não houver.

    Sem cadastro não há cálculo paralelo, e isso não é erro: é o estado de quem
    ainda não mediu o feixe. Levantar exceção aqui derrubaria a aba Qualidade
    inteira por causa de uma perna que ainda não existe.
    """
    caminho = Path(pasta or pasta_dados()) / "_maquinas.json"
    if not caminho.is_file():
        return {}
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    saida = {}
    for chave, d in bruto.items():
        if chave.startswith("_") or not isinstance(d, dict):
            continue      # "_leia_me" e afins
        saida[chave] = Maquina(
            chave=chave,
            rotulo=str(d.get("rotulo") or chave),
            fabricante=str(d.get("fabricante") or ""),
            exemplo=bool(d.get("exemplo")),
            fonte=str(d.get("fonte") or ""),
            nomes_dicom=[str(n) for n in (d.get("nomes_dicom") or [])],
            energias=d.get("energias") or {},
        )
    return saida


def maquina_do_plano(nome_dicom: str, maquinas=None):
    """A máquina cadastrada cujo ``nomes_dicom`` casa com o RT Plan — ou ``None``.

    **É a trava.** Casa por nome, sem acento e sem caixa, e sem heurística de
    parecença: "TrueBeamSN1001" não pode cair numa tabela cadastrada como
    "TrueBeam" por acaso, porque duas TrueBeam da mesma clínica têm dado de
    feixe DIFERENTE — é para isso que existe o número de série no nome.
    """
    alvo = str(nome_dicom or "").strip().upper()
    if not alvo:
        return None
    for maq in (maquinas if maquinas is not None else carregar_maquinas()).values():
        for n in maq.nomes_dicom:
            if str(n).strip().upper() == alvo:
                return maq
    return None


# ── Tabelas ──────────────────────────────────────────────────────────────────

@dataclass
class TabelaTMR:
    campos_cm: list
    profundidades_cm: list
    valores: list          # valores[i_profundidade][j_campo]


@dataclass
class TabelaScp:
    campos_cm: list
    valores: list


def _linhas_csv(caminho: Path) -> list:
    texto = caminho.read_text(encoding="utf-8-sig")
    return [ln for ln in texto.replace("\r\n", "\n").split("\n") if ln.strip()]


def caminho_tabela(maquina: str, energia_mv, categoria: str, pasta=None) -> Path:
    """``<MAQUINA>__<ENERGIA>MV__<TMR|SCP>.csv`` na pasta de dados."""
    try:
        e = float(str(energia_mv).replace(",", "."))
    except (TypeError, ValueError):
        e = 0.0
    rotulo = f"{e:g}"
    return Path(pasta or pasta_dados()) / f"{maquina}__{rotulo}MV__{categoria.upper()}.csv"


def carregar_tmr(caminho: Path):
    """Lê a tabela de TMR: linha 1 = campos (cm), coluna A = profundidade (cm).

    É o mesmo formato das planilhas do Drive, com o cabeçalho já convertido de
    "10x10" para 10 na hora de gravar o CSV — converter aqui obrigaria cada
    leitor a repetir a regra do "LxL", e é o tipo de conversão que se escreve
    diferente na segunda vez.
    """
    linhas = _linhas_csv(caminho)
    if len(linhas) < 2:
        return None
    campos = [float(c) for c in linhas[0].split(",")[1:]]
    profs, valores = [], []
    for ln in linhas[1:]:
        partes = ln.split(",")
        profs.append(float(partes[0]))
        valores.append([float(v) for v in partes[1:]])
    if not campos or not profs:
        return None
    return TabelaTMR(campos, profs, valores)


def carregar_scp(caminho: Path):
    """Lê a tabela de Scp: coluna A = campo (cm), coluna B = valor."""
    linhas = _linhas_csv(caminho)
    if len(linhas) < 2:
        return None
    campos, valores = [], []
    for ln in linhas[1:]:
        partes = ln.split(",")
        campos.append(float(partes[0]))
        valores.append(float(partes[1]))
    if not campos:
        return None
    return TabelaScp(campos, valores)


def tabelas_da_maquina(maquina: str, energia_mv, pasta=None) -> tuple:
    """``(TabelaTMR|None, TabelaScp|None)`` para a máquina e a energia."""
    tmr = scp = None
    p = caminho_tabela(maquina, energia_mv, "TMR", pasta)
    if p.is_file():
        try:
            tmr = carregar_tmr(p)
        except (OSError, ValueError, IndexError):
            tmr = None
    p = caminho_tabela(maquina, energia_mv, "SCP", pasta)
    if p.is_file():
        try:
            scp = carregar_scp(p)
        except (OSError, ValueError, IndexError):
            scp = None
    return tmr, scp


# ── Interpolação ─────────────────────────────────────────────────────────────

def interp1d(xs, ys, x) -> float:
    """Linear, com CLAMP nas bordas.

    O clamp é do programa de origem e é deliberado: extrapolar TMR além da
    tabela dá número que a máquina nunca produziu. Preso na borda, o valor ao
    menos é um valor medido — e o desvio grande que ele gera é o que chama
    atenção para o campo estar fora da faixa tabelada.
    """
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            larg = xs[i + 1] - xs[i]
            if larg == 0:
                return float(ys[i])
            t = (x - xs[i]) / larg
            return float(ys[i] + t * (ys[i + 1] - ys[i]))
    return float(ys[-1])


def campo_equivalente(x_cm, y_cm) -> float | None:
    """Lado do quadrado equivalente: ``L = 2·X·Y / (X+Y)``.

    É a média harmônica dobrada — a aproximação clássica de Sterling, a mesma do
    programa de origem. Não é a razão área/perímetro (``4A/P``), que dá o MESMO
    resultado para o retângulo e é como a fórmula costuma ser deduzida.
    """
    try:
        X, Y = abs(float(x_cm)), abs(float(y_cm))
    except (TypeError, ValueError):
        return None
    if X + Y <= 0:
        return None
    return (2.0 * X * Y) / (X + Y)


def tmr(tabela: TabelaTMR, campo_L_cm: float, profundidade_cm: float) -> float | None:
    """TMR por interpolação BILINEAR: primeiro no campo, depois na profundidade."""
    if tabela is None:
        return None
    por_prof = [interp1d(tabela.campos_cm, linha, campo_L_cm)
                for linha in tabela.valores]
    return interp1d(tabela.profundidades_cm, por_prof, profundidade_cm)


def scp(tabela: TabelaScp, campo_L_cm: float) -> float | None:
    if tabela is None:
        return None
    return interp1d(tabela.campos_cm, tabela.valores, campo_L_cm)


# ── Geometria do feixe ───────────────────────────────────────────────────────

def _mordentes_do_ponto(cp) -> tuple:
    """(X, Y) em cm de UM ponto de controle, ou (None, None).

    MLC é pulado de propósito — ver o item 3 do cabeçalho do módulo. O tipo do
    dispositivo pode vir em ``RTBeamLimitingDeviceType``; quando não vem, a
    ordem da sequência é X e depois Y, que é como o programa de origem lê.
    """
    x = y = None
    indice = 0
    for bc in getattr(cp, "BeamLimitingDevicePositionSequence", []) or []:
        tipo = str(getattr(bc, "RTBeamLimitingDeviceType", "") or "").upper().strip()
        if "MLC" in tipo:
            continue
        pos = list(getattr(bc, "LeafJawPositions", []) or [])
        if len(pos) < 2:
            continue
        largura = abs(float(pos[1]) - float(pos[0])) / 10.0
        if tipo.startswith("ASYMX") or tipo == "X" or (not tipo and indice == 0):
            x = largura
            indice = 1
        elif tipo.startswith("ASYMY") or tipo == "Y" or (not tipo and indice == 1):
            y = largura
            indice = 2
        if x is not None and y is not None:
            break
    return x, y


def profundidade_no_isocentro(beam_ds, ssd_cm=None) -> float | None:
    """``SAD − SSD``, em cm — a profundidade do isocentro no eixo do feixe.

    ``ssd_cm`` vence o que está no DICOM: é por onde entra o SSD que
    ``dicom_rt.calcular_ssds`` calcula do contorno BODY, para o caso do RT Plan
    que não traz ``SourceToSurfaceDistance``.
    """
    sad = getattr(beam_ds, "SourceAxisDistance", None)
    if sad is None:
        return None
    try:
        sad_cm = float(sad) / 10.0
    except (TypeError, ValueError):
        return None

    if ssd_cm is None:
        cps = getattr(beam_ds, "ControlPointSequence", []) or []
        bruto = getattr(cps[0], "SourceToSurfaceDistance", None) if cps else None
        if bruto is None:
            return None
        try:
            ssd_cm = float(bruto) / 10.0
        except (TypeError, ValueError):
            return None

    prof = sad_cm - float(ssd_cm)
    # Profundidade negativa é isocentro FORA do paciente — acontece em campo de
    # setup e em plano com isocentro no ar. Devolver o número negativo faria a
    # tabela ser consultada no clamp da borda e sair um TMR de 1,0, que é a
    # resposta mais errada possível: o campo apareceria perfeito.
    return prof if prof > 0 else None


# ── Cálculo ──────────────────────────────────────────────────────────────────

@dataclass
class UmDoFeixe:
    """O resultado de UM campo."""
    nome: str = ""
    tecnica: str = ""
    energia_mv: float = float("nan")
    um_plano: float = float("nan")
    um_calculado: float = float("nan")
    dose_cgy: float = float("nan")
    profundidade_cm: float = float("nan")
    campo_eq_cm: float = float("nan")
    tmr: float = float("nan")
    scp: float = float("nan")
    fd: float = float("nan")
    n_segmentos: int = 0
    modulado: bool = False
    # Por que NÃO calculou. São DOIS campos porque vão para lugares diferentes:
    # ``resumo`` cabe na célula da tabela, ``motivo`` é a explicação inteira e
    # vai para o rodapé do cartão e para a dica do mouse. Com um só, o texto
    # longo esticava a coluna e a tabela ganhava barra horizontal — cortando
    # justamente a explicação.
    resumo: str = ""
    motivo: str = ""

    @property
    def desvio_pct(self) -> float:
        """(calculado − plano) / plano, em %. Positivo = o cálculo pede MAIS UM."""
        if not (self.um_plano and self.um_plano > 0):
            return float("nan")
        if self.um_calculado != self.um_calculado:      # NaN
            return float("nan")
        return (self.um_calculado - self.um_plano) / self.um_plano * 100.0


def _recusar(res: UmDoFeixe, resumo: str, motivo: str) -> UmDoFeixe:
    """Marca o campo como não calculado, com o rótulo curto e a explicação."""
    res.resumo, res.motivo = resumo, motivo
    return res


def _tecnica_modulada(tecnica: str) -> bool:
    t = str(tecnica or "").upper()
    return "DYNAMIC" in t or "VMAT" in t or "ARC" in t


def calcular_feixe(beam_ds, dose_cgy, um_plano, maquina: Maquina,
                   tabela_tmr, tabela_scp, ssd_cm=None) -> UmDoFeixe:
    """UM calculado de UM campo, somando segmento a segmento.

    O ``motivo`` fica preenchido quando não deu para calcular, e é ele que a
    tela mostra no lugar do número: "sem dado" não distingue tabela faltando de
    profundidade impossível, e são coisas que se resolvem de maneiras diferentes.
    """
    cps = list(getattr(beam_ds, "ControlPointSequence", []) or [])
    cp0 = cps[0] if cps else None
    tecnica = str(getattr(beam_ds, "BeamType", "") or "")
    res = UmDoFeixe(
        nome=str(getattr(beam_ds, "BeamName", "") or ""),
        tecnica=tecnica,
        modulado=_tecnica_modulada(tecnica),
        dose_cgy=float(dose_cgy) if dose_cgy else float("nan"),
        um_plano=float(um_plano) if um_plano else float("nan"),
    )
    try:
        res.energia_mv = float(getattr(cp0, "NominalBeamEnergy", None) or 0) or float("nan")
    except (TypeError, ValueError):
        pass

    if int(getattr(beam_ds, "NumberOfWedges", 0) or 0) > 0:
        return _recusar(res, "campo com filtro",
                        "O k (fração da dose entregue com o filtro) não sai do "
                        "DICOM: a tag do ângulo do wedge devolve 60 no Elekta "
                        "seja qual for o valor real, e o programa de origem o "
                        "PERGUNTA ao usuário. Esta tela não tem onde perguntar.")
    if not (res.dose_cgy == res.dose_cgy and res.dose_cgy > 0):
        return _recusar(res, "sem dose no plano",
                        "O RT Plan não traz a dose deste campo "
                        "(BeamDose no grupo de frações).")
    if tabela_tmr is None or tabela_scp is None:
        return _recusar(res, f"sem tabela de {res.energia_mv:g} MV",
                        f"Não há tabela de TMR e Scp cadastrada para "
                        f"{res.energia_mv:g} MV nesta máquina.")
    fd = maquina.fd(res.energia_mv)
    if fd is None or fd == 0:
        return _recusar(res, "sem fator distância",
                        f"O fator distância (FD) não está cadastrado para "
                        f"{res.energia_mv:g} MV.")
    res.fd = float(fd)

    prof = profundidade_no_isocentro(beam_ds, ssd_cm)
    if prof is None:
        return _recusar(res, "sem profundidade",
                        "Sem SAD ou SSD utilizável: a profundidade do "
                        "isocentro não pôde ser calculada, e sem ela não há "
                        "TMR.")
    res.profundidade_cm = prof

    # BUILD-UP: acima da primeira profundidade da tabela o formalismo TMR não
    # vale. A tabela começa no dmax (1,5 cm em 6 MV, 2,2 em 10), e o clamp da
    # interpolação devolveria TMR = 1,000 — a resposta mais enganosa possível,
    # porque o campo apareceria perfeito num lugar onde a conta não se aplica.
    #
    # O caso que obrigou a isto é a fossa supraclavicular do TC8: isocentro a
    # 0,8 cm da pele, TMR travado em 1,000, e os dois campos saindo com −49 % e
    # +174 % de desvio. Isocentro raso assim quase sempre quer dizer que o
    # ponto de dose NÃO é o isocentro — a fossa costuma ser prescrita a 3 cm de
    # profundidade —, e essa é a suposição que este módulo não tem como
    # verificar (o RT Plan não traz a geometria do ponto de dose).
    prof_minima = tabela_tmr.profundidades_cm[0]
    if prof < prof_minima:
        return _recusar(
            res, f"build-up ({prof:.1f} cm)",
            f"O isocentro está a {prof:.1f} cm, acima da primeira profundidade "
            f"da tabela ({prof_minima:g} cm, o dmax). Na região de build-up o "
            f"formalismo TMR não se aplica. Isocentro tão raso costuma "
            f"significar que o ponto de dose NÃO é o isocentro — a fossa "
            f"supraclavicular, por exemplo, costuma ser prescrita a 3 cm.")

    if len(cps) < 2:
        return _recusar(res, "sem pontos de controle",
                        "O campo tem menos de dois pontos de controle.")

    # STATIC soma os CP ÍMPARES, DYNAMIC soma todos menos o zero. É a regra do
    # programa de origem, e ela vem do jeito como o Elekta escreve o
    # step-and-shoot: o segmento fica ENTRE um par de pontos, e o ímpar é o que
    # fecha o par. Somar todos num campo estático contaria cada segmento duas
    # vezes.
    so_impares = not res.modulado

    soma = 0.0
    mw_anterior = 0.0
    ultimo_x = ultimo_y = None
    tmr_ult = scp_ult = float("nan")
    for cp in cps:
        try:
            indice = int(getattr(cp, "ControlPointIndex", -1))
        except (TypeError, ValueError):
            continue
        x, y = _mordentes_do_ponto(cp)
        # Herda do ponto anterior: o DICOM permite trazer só o que MUDOU, e um
        # ponto sem mordente não é um campo fechado.
        if x is not None:
            ultimo_x = x
        if y is not None:
            ultimo_y = y
        x, y = (x if x is not None else ultimo_x), (y if y is not None else ultimo_y)

        try:
            mw = float(getattr(cp, "CumulativeMetersetWeight", None) or 0.0)
        except (TypeError, ValueError):
            continue
        d_mw = mw - mw_anterior
        mw_anterior = mw

        if so_impares and indice % 2 == 0:
            continue
        if not so_impares and indice == 0:
            continue
        if d_mw <= 0:
            continue
        if x is None or y is None:
            return _recusar(res, "sem mordentes",
                            f"O ponto de controle {indice} não traz mordentes, "
                            f"nem há um anterior de onde herdá-los.")

        L = campo_equivalente(x, y)
        if L is None:
            continue
        v_tmr = tmr(tabela_tmr, L, prof)
        v_scp = scp(tabela_scp, L)
        if not v_tmr or not v_scp:
            return _recusar(res, "TMR/Scp indisponível",
                            f"A tabela não devolveu TMR ou Scp no ponto de "
                            f"controle {indice}.")
        soma += d_mw * res.dose_cgy / (v_tmr * v_scp * res.fd)
        res.n_segmentos += 1
        res.campo_eq_cm, tmr_ult, scp_ult = L, v_tmr, v_scp

    if res.n_segmentos == 0:
        return _recusar(res, "sem segmento com peso",
                        "Nenhum ponto de controle tem peso de UM positivo.")
    res.tmr, res.scp = tmr_ult, scp_ult
    res.um_calculado = soma
    return res


@dataclass
class VerificacaoParalela:
    """O cálculo paralelo de um plano inteiro."""
    rotulo: str = ""
    maquina_dicom: str = ""
    maquina: object = None       # Maquina casada, ou None (ver a trava)
    demonstracao: bool = False   # calculado com tabela que NÃO é desta máquina
    feixes: list = field(default_factory=list)
    avisos: list = field(default_factory=list)

    @property
    def calculavel(self) -> bool:
        return any(f.um_calculado == f.um_calculado for f in self.feixes)

    @property
    def desvio_total_pct(self) -> float:
        """Desvio do UM TOTAL do plano — a soma dos campos, não a média dos desvios.

        A média dos desvios daria peso igual a um campo de 20 UM e a um de 600,
        e é o total que sai na máquina.
        """
        plano = sum(f.um_plano for f in self.feixes
                    if f.um_plano == f.um_plano and f.um_calculado == f.um_calculado)
        calc = sum(f.um_calculado for f in self.feixes
                   if f.um_plano == f.um_plano and f.um_calculado == f.um_calculado)
        if plano <= 0:
            return float("nan")
        return (calc - plano) / plano * 100.0


def status_do_desvio(desvio_pct, modulado: bool = False) -> str:
    """OK / ATENÇÃO / FALHA do desvio, na faixa que couber (ver as constantes)."""
    from isocentro.dominio import qualidade

    if desvio_pct is None or desvio_pct != desvio_pct:
        return qualidade.NA
    atencao = DESVIO_ATENCAO_MODULADO if modulado else DESVIO_ATENCAO
    falha = DESVIO_FALHA_MODULADO if modulado else DESVIO_FALHA
    return qualidade._maior_e_pior(abs(desvio_pct), atencao, falha)


def verificar(plano: dict, pasta=None) -> VerificacaoParalela:
    """Cálculo paralelo de um plano do app (``gui.JanelaPrincipal._planos[i]``).

    Sem máquina cadastrada, o cálculo NÃO é abandonado: ele roda com a primeira
    tabela que existir, e o resultado volta marcado ``demonstracao``. É o que
    permite exercitar a conta antes de o dado da clínica existir — e o
    ``demonstracao`` é o que impede a tela de chamar isso de verificação.
    """
    rp = plano.get("rp") or {}
    rp_ds = plano.get("rp_ds")
    ver = VerificacaoParalela(rotulo=str(plano.get("rotulo") or ""),
                              maquina_dicom=str(rp.get("maquina") or ""))
    if rp_ds is None:
        ver.avisos.append("Sem o RT Plan original: não há o que calcular.")
        return ver

    maquinas = carregar_maquinas(pasta)
    if not maquinas:
        ver.avisos.append(
            "Nenhuma máquina cadastrada em 'dados_feixe/_maquinas.json'. O "
            "cálculo paralelo precisa de TMR, Scp e do fator distância medidos "
            "no acelerador — sem eles não há verificação independente.")
        return ver

    maq = maquina_do_plano(ver.maquina_dicom, maquinas)
    if maq is None:
        maq = next(iter(maquinas.values()))
        ver.demonstracao = True
        ver.avisos.append(
            f"DEMONSTRAÇÃO — não é verificação. O plano é da máquina "
            f"'{ver.maquina_dicom}', que não tem dado de feixe cadastrado; a "
            f"conta abaixo usou a tabela de '{maq.rotulo}'. TMR e Scp são de "
            f"CADA acelerador: os números servem para conferir que a conta "
            f"roda, e para nada além disso.")
    elif maq.exemplo:
        ver.demonstracao = True
        ver.avisos.append(
            f"A tabela de '{maq.rotulo}' está marcada como dado de exemplo.")
    ver.maquina = maq

    # UM e dose por feixe saem do grupo de frações — é a dose de UMA fração, a
    # mesma a que o UM se refere.
    dose_por_feixe, um_por_feixe = {}, {}
    for grupo in getattr(rp_ds, "FractionGroupSequence", []) or []:
        for rb in getattr(grupo, "ReferencedBeamSequence", []) or []:
            num = getattr(rb, "ReferencedBeamNumber", None)
            if num is None:
                continue
            if getattr(rb, "BeamDose", None) is not None:
                # BeamDose vem em Gy; o formalismo trabalha em cGy.
                dose_por_feixe[int(num)] = float(rb.BeamDose) * 100.0
            if getattr(rb, "BeamMeterset", None) is not None:
                um_por_feixe[int(num)] = float(rb.BeamMeterset)

    # SSD por feixe, do que a ficha já calculou — cai para o do DICOM quando não
    # houver (ver ``profundidade_no_isocentro``).
    ssd_por_nome = {str(f.get("nome") or ""): f.get("ssd")
                    for f in (rp.get("feixes") or [])}

    cache = {}
    for beam in getattr(rp_ds, "BeamSequence", []) or []:
        if str(getattr(beam, "TreatmentDeliveryType", "TREATMENT")).upper() == "SETUP":
            continue
        num = getattr(beam, "BeamNumber", None)
        nome = str(getattr(beam, "BeamName", "") or "")
        cps = getattr(beam, "ControlPointSequence", []) or []
        try:
            energia = float(getattr(cps[0], "NominalBeamEnergy", 0) or 0)
        except (TypeError, ValueError, IndexError):
            energia = 0.0
        if energia not in cache:
            cache[energia] = tabelas_da_maquina(maq.chave, energia, pasta)
        t_tmr, t_scp = cache[energia]
        ver.feixes.append(calcular_feixe(
            beam,
            dose_cgy=dose_por_feixe.get(int(num)) if num is not None else None,
            um_plano=um_por_feixe.get(int(num)) if num is not None else None,
            maquina=maq, tabela_tmr=t_tmr, tabela_scp=t_scp,
            ssd_cm=ssd_por_nome.get(nome),
        ))

    if any(f.modulado and f.um_calculado == f.um_calculado for f in ver.feixes):
        ver.avisos.append(
            "Campo modulado: o campo equivalente sai dos MORDENTES, não da "
            "abertura do MLC. Num IMRT ou VMAT isso ignora a modulação — o TMR "
            "e o Scp saem altos demais e o UM calculado sai baixo. Serve de "
            "rastreio, não de verificação.")
    if any(f.um_calculado == f.um_calculado for f in ver.feixes):
        ver.avisos.append(
            "Profundidade = SAD − SSD ao ISOCENTRO, calculada da geometria: "
            "estes planos não trazem BeamDosePointDepth nem "
            "BeamDosePointEquivalentDepth. É profundidade FÍSICA, não "
            "radiológica — em mama e pulmão o desvio estoura por causa do ar, "
            "não por erro do plano —, e supõe que o ponto de dose é o "
            "isocentro.")
    return ver
