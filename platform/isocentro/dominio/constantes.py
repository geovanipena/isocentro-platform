"""Constantes de domínio do serviço (máquinas, protocolos, gating).

Fonte ÚNICA das strings/propriedades específicas do serviço, que antes viviam
espalhadas por gui/ficha_pdf/dicom_rt. Ajustar aqui ao trocar de acelerador ou
protocolo evita drift entre os módulos.

Este módulo é dados puros — não importa nada do projeto (evita ciclos).
"""
from __future__ import annotations

from dataclasses import dataclass


# ── Unidades ─────────────────────────────────────────────────────────────────
# Cada acelerador é de uma unidade, e cada pessoa da equipe atende numa delas
# (ver ``equipe.unidade_da_pessoa``): a ficha do Synergy não oferece quem só
# atende na Clinica, e vice-versa. Unidade vazia = sem unidade definida, atende
# em qualquer máquina.
UNIDADES: tuple[str, ...] = ("Clinica", "SAT")
UNIDADE_PADRAO = "Clinica"


# ── Aceleradores ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Maquina:
    """Um acelerador e as propriedades que a ficha deriva dele."""
    chave: str                 # nome canônico (como no DICOM TreatmentMachineName)
    imagem: str                # protocolo de imagem padrão (proto_imagem)
    frequencia: str            # frequência de imagem padrão (proto_frequencia)
    grupo_mesa: str            # imagem da mesa na ficha: "TB" ou "serie_c"
    mesa_vert_invertida: bool  # console inverte o sinal do deslocamento vertical
    sus_elegivel: bool         # dispara o fluxo de Registro SUS
    rotulo: str = ""           # nome IMPRESSO na ficha, quando difere do DICOM
    logo: str = ""             # arquivo do logo em assets/, quando a unidade tem o seu
    paleta: str = ""           # cores das págs. 2 e 3 (ver ficha_pdf.TEMAS)
    unidade: str = UNIDADE_PADRAO   # quem trata nesta máquina (ver UNIDADES)


MAQUINAS: tuple[Maquina, ...] = (
    # O DICOM continua trazendo "TrueBeamSN1001" (nome de fábrica, usado no
    # casamento); a ficha imprime o nome pelo qual o serviço chama a máquina.
    #
    # Sem o "SN1001" desde 31/08/2026: o sufixo era o número de série, que só
    # servia para distinguir duas máquinas com o mesmo nome de família — e elas
    # já não têm o mesmo nome, porque a outra passou a se chamar TrueBeam. Na
    # sala são "a VitalBeam" e "a TrueBeam", e é assim que a ficha as nomeia.
    Maquina("TrueBeamSN1001", imagem="MV-kV", frequencia="Semanal",
            grupo_mesa="TB", mesa_vert_invertida=False, sus_elegivel=True,
            rotulo="VitalBeam"),
    # Mesma história: "TBuniverSN1002" é o nome de fábrica, e é por ele que o
    # DICOM e o casamento continuam indo. Na sala a máquina se chama TrueBeam, e
    # é esse o nome que a ficha e as telas mostram — o de fábrica sobrevive em
    # Configurações → Máquinas, que é onde ele serve para alguma coisa.
    Maquina("TBuniverSN1002", imagem="CBCT", frequencia="Diária",
            grupo_mesa="TB", mesa_vert_invertida=False, sus_elegivel=False,
            rotulo="TrueBeam"),
    Maquina("600CD", imagem="MV", frequencia="Semanal",
            grupo_mesa="serie_c", mesa_vert_invertida=True, sus_elegivel=False),
    Maquina("6EX", imagem="MV", frequencia="Semanal",
            grupo_mesa="serie_c", mesa_vert_invertida=True, sus_elegivel=False),
    # Elekta Synergy (planejada no Monaco). Usa o MESMO desenho de mesa do
    # TrueBeam. Imagem: os planos do Monaco trazem o campo de setup nomeado
    # "CBCT", que é o protocolo do XVI.
    Maquina("Synergy01", imagem="CBCT", frequencia="Diária",
            grupo_mesa="TB", mesa_vert_invertida=False, sus_elegivel=False,
            logo="logo_sat.png", paleta="sat", unidade="SAT"),
)


def identificar_maquina(texto: str | None) -> Maquina | None:
    """Casa o nome de máquina (ex.: TreatmentMachineName do DICOM) com o registro.

    Casamento por SUBSTRING sem diferenciar caixa — tolera sufixos/variações do
    nome no DICOM. Os nomes canônicos não são substrings uns dos outros, então a
    ordem não importa."""
    t = (texto or "").lower()
    for m in MAQUINAS:
        if m.chave.lower() in t:
            return m
    return None


def unidade_da_maquina(texto: str | None) -> str:
    """Unidade que trata no acelerador ``texto``, ou "" se não o reconhece.

    "" não é "nenhuma unidade": é "não sei" — quem chama deve então oferecer a
    equipe inteira, em vez de esconder o nome de quem vai assinar."""
    m = identificar_maquina(texto)
    return m.unidade if m is not None else ""


def maquinas_da_unidade(unidade: str | None = None) -> tuple[Maquina, ...]:
    """Os aceleradores de uma unidade — TODOS quando ela não é conhecida.

    É a mesma regra dos combos de equipe (``equipe.equipe_da_maquina``): a
    ficha do Synergy não oferece quem só atende na Clinica, e a da Clinica não
    oferece o Synergy. Oferecer numa lista uma máquina que não existe naquela
    sala é convidar a escolher errado com o paciente na mesa.

    Unidade desconhecida devolve tudo, de propósito: "não sei em que unidade
    este caso está" não é motivo para esconder a máquina certa de quem edita.
    """
    alvo = (unidade or "").strip().lower()
    if not alvo:
        return MAQUINAS
    return tuple(m for m in MAQUINAS if m.unidade.lower() == alvo)


def rotulo_maquina(texto: str | None) -> str:
    """Nome do acelerador COMO SAI IMPRESSO na ficha.

    O casamento (``identificar_maquina``) continua pelo nome de fábrica que vem no
    DICOM; só a exibição muda. Troca apenas o trecho reconhecido e preserva o
    resto do texto — 'Sala2-TrueBeamSN1001' vira 'Sala2-VitalBeam' —, e
    devolve o original quando não reconhece a máquina ou ela não tem rótulo
    próprio. Assim o registro JSON e o DICOM seguem com o nome de fábrica.
    """
    t = texto or ""
    for m in MAQUINAS:
        if not m.rotulo or m.rotulo == m.chave:
            continue
        i = t.lower().find(m.chave.lower())
        if i >= 0:
            return t[:i] + m.rotulo + t[i + len(m.chave):]
    return t


# ── Tabela de tolerância (ToleranceTableLabel) ───────────────────────────────

# Abreviações de rótulos de tabela de tolerância para a ficha (chave em minúsculo
# e sem espaços nas bordas).
TABELAS_TOLERANCIA_ABREV = {
    "imrt indexado": "IMRT-i",
}


def abreviar_tabela_tolerancia(rotulo: str | None) -> str:
    """Abrevia o rótulo da tabela de tolerância p/ exibição (ex.: 'IMRT-i')."""
    r = (rotulo or "").strip()
    return TABELAS_TOLERANCIA_ABREV.get(r.lower(), r)


# ── Protocolo de imagem ──────────────────────────────────────────────────────

IMAGEM_DIARIA = "Diária"
IMAGEM_SEMANAL = "Semanal"
IMAGEM_PERSONALIZADO = "Personalizado"
FREQUENCIAS = (IMAGEM_SEMANAL, IMAGEM_DIARIA, IMAGEM_PERSONALIZADO)

TIPOS_IMAGEM = ("MV", "MV-kV", "CBCT")

# A partir desta dose POR FRAÇÃO (cGy) a imagem é diária, seja qual for o
# protocolo da máquina. A frequência saía só de ``MAQUINAS`` — e a 600CD, a 6EX
# e o TrueBeamSN1001 são semanais —, então a mama *fast-forward* (26 Gy em 5
# frações, 520 cGy por fração) ia para a sala com imagem semanal: cinco frações
# em que um erro de posicionamento vale cinco vezes mais que numa convencional,
# conferidas duas vezes. O corte é 501 e não 500 porque 500 cGy/fr é
# fracionamento convencional de paliativo (20 Gy em 4), que o serviço trata com
# a frequência da máquina; o *fast-forward* começa logo acima.
DOSE_IMAGEM_DIARIA_CGY = 501.0


def imagem_diaria_por_dose(dose_cgy: float) -> bool:
    """A dose por fração (cGy) obriga imagem diária?

    Valor ilegível responde ``False``: sem dose não há regra a aplicar, e o
    protocolo da máquina continua valendo.
    """
    try:
        return float(dose_cgy or 0) >= DOSE_IMAGEM_DIARIA_CGY
    except (TypeError, ValueError):
        return False


# ── Fracionamento ────────────────────────────────────────────────────────────
# O que a ficha imprime no campo Fracionamento.
OPCOES_FRACIONAMENTO: tuple[str, ...] = ("1x dia", "Dias alter.", "2x sem.",
                                         "Única")

# Frequência como a prescrição do ARIA a entrega (crua, ou já traduzida por
# ``capa_dados.traduzir_frequencia``) → o fracionamento da ficha. As chaves são
# comparadas sem acento e em minúsculas.
#
# "Duas vezes por dia" está fora de propósito: não existe opção correspondente
# na ficha, e escolher a mais parecida imprimiria um fracionamento que ninguém
# prescreveu. Frequência sem correspondência devolve "" — e aí a ficha pergunta,
# que é o comportamento de antes desta tradução existir.
_FRACIONAMENTO_DA_FREQUENCIA: dict[str, str] = {
    "once daily": "1x dia",
    "uma vez por dia": "1x dia",
    "diaria": "1x dia",
    "diariamente": "1x dia",
    "dias alternado": "Dias alter.",
    "dias alternados": "Dias alter.",
    "every other day": "Dias alter.",
    "duas vezes por semana": "2x sem.",
    "twice weekly": "2x sem.",
    "aplicacao unica": "Única",
    "unica": "Única",
    "single fraction": "Única",
}


def _sem_acento(texto: str) -> str:
    import unicodedata

    return "".join(ch for ch in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(ch) != "Mn")


def fracionamento_da_frequencia(frequencia: str) -> str:
    """O fracionamento da ficha para a frequência que a prescrição traz.

    ``""`` quando a frequência não tem correspondência (ou vem vazia): o campo
    fica como estava e alguém decide, em vez de a ficha afirmar um ritmo de
    tratamento que a prescrição não disse.
    """
    chave = _sem_acento(frequencia).strip().lower()
    return _FRACIONAMENTO_DA_FREQUENCIA.get(chave, "")


# ── Posicionamento do paciente (DICOM PatientPosition) ───────────────────────

# Código DICOM → rótulo da ficha. Duas informações num campo só, que é como o
# técnico monta o setup: o DECÚBITO e para onde vai a CABEÇA no gantry.
#   H/F = Head/Feet first  ·  S=Supine, P=Prone, DR/DL=Decubitus Right/Left
POSICOES_PACIENTE: dict[str, str] = {
    "HFS":  "DD · cabeça",     # decúbito dorsal (supino), cabeça para o gantry
    "FFS":  "DD · pés",
    "HFP":  "DV · cabeça",     # decúbito ventral (prono)
    "FFP":  "DV · pés",
    "HFDR": "DLD · cabeça",    # decúbito lateral direito
    "FFDR": "DLD · pés",
    "HFDL": "DLE · cabeça",    # decúbito lateral esquerdo
    "FFDL": "DLE · pés",
}

# Decúbitos em que o paciente está de bruços — o IOP da TC/dose inverte o eixo Y.
POSICOES_PRONO = ("HFP", "FFP")


def rotulo_posicao(codigo: str | None) -> str:
    """Rótulo da ficha para o ``PatientPosition`` do DICOM ('HFP' → 'DV · cabeça').

    Código desconhecido volta em maiúsculas, sem tradução: melhor mostrar o
    código bruto ao técnico do que esconder um decúbito que o serviço não previu.
    """
    c = (codigo or "").strip().upper()
    return POSICOES_PACIENTE.get(c, c)


# ── Gating ───────────────────────────────────────────────────────────────────

MOD_BREATH_HOLD = "Breath-Hold"
MOD_AMPLITUDE = "Amplitude"
MOD_FASE = "Fase"
MODALIDADES_GATING = (MOD_BREATH_HOLD, MOD_AMPLITUDE, MOD_FASE)

# Técnicas de compensação de movimento (RespiratoryMotionCompensationTechnique).
TEC_NONE = "NONE"
TEC_BREATH_HOLD = "BREATH_HOLD"
