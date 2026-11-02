"""Geração do PDF da Ficha Técnica de Tratamento (modelo Clinica).

Reproduz fielmente o formulário institucional:

* Página 1 (retrato): cortes ortogonais + DVH — gerada quando há série de TC
  e RT Dose/Struct (ver ``cortes_dvh``); caso contrário é omitida.
* Página 2 (paisagem): Ficha Técnica de Tratamento.
* Página 3 (paisagem): mapa de acompanhamento das frações.
* 600CD: após as frações, os DRRs de setup (portais AP e perfil, quando os RT
  Images vêm na pasta) e a folha de conferência de portais.

As coordenadas usam o canto superior esquerdo como origem (mais intuitivo
para um formulário), convertidas para o sistema do ReportLab nos helpers.
"""

from __future__ import annotations

import io
import logging
import os
import re
from dataclasses import dataclass

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from isocentro import raiz
from isocentro.dominio import constantes
# No topo, e não dentro da função: import tardio some do pacote e a falha só
# aparece na clínica. ``dicom_rt`` não importa este módulo, então não há ciclo.
from isocentro.desenho import corte
from isocentro.dicom import dicom_rt
from isocentro.papel import rodape

_LOG = logging.getLogger(__name__)

# Empacotado, os logos ficam em ``_internal/assets`` — um nível ABAIXO do
# executável. Por isso ``pasta_assets`` e não ``pasta_do_app``: errar aqui é a
# ficha sair sem logo, impressa, sem nenhum aviso na tela.
_ASSETS     = str(raiz.pasta_assets())
LOGO        = os.path.join(_ASSETS, "logo_clinica.png")
TABLE_TB    = os.path.join(_ASSETS, "table_TB.png")
TABLE_SERIE_C = os.path.join(_ASSETS, "table_serie_c.png")
# Faixa superior EM BRANCO da folha de portais (logo, rótulos Paciente/RGH/Médico,
# caixa GANTRY e os três diagramas). Quando presente, é o fundo do topo e só os
# dados do paciente (e o logo da pasta) são escritos por cima.
# ``assets/600CD.png`` — a imagem-modelo que ERA a folha de portais inteira
# (logo gravado, rótulos do paciente, caixa GANTRY e os três diagramas).
# Deixou de ser usada em 25/08/2026: os três diagramas deram lugar ao
# diagrama de orientação da própria ficha (``TABLE_SERIE_C``) com a legenda
# ao lado, e o resto a folha desenha. O arquivo fica no pacote — quem for
# apagá-lo confira antes se nenhuma instalação antiga o reimporta.


def logo_da_maquina(maquina: str | None) -> str:
    """Caminho do logo da unidade que trata naquele acelerador.

    Cada máquina pode ter o seu (``Maquina.logo``) — o Synergy é do SAT, e a
    ficha dele sai com o logo do SAT. Sem logo próprio, o institucional.
    """
    m = constantes.identificar_maquina(maquina)
    if m is not None and m.logo:
        caminho = os.path.join(_ASSETS, m.logo)
        if os.path.exists(caminho):
            return caminho
        _LOG.warning("Logo %r da máquina %r não encontrado em assets — usando o "
                     "institucional", m.logo, maquina)
    return LOGO


def _logo(c, x, y, w, h, maquina: str | None = None, **extra) -> None:
    """Desenha o logo institucional, se houver. Ausência ou falha não derruba o PDF.

    Era o mesmo bloco (existe? try/desenha/engole) repetido em sete cabeçalhos —
    e nos sete o erro sumia sem deixar rastro, então um logo que parasse de
    aparecer não tinha como ser diagnosticado.

    ``maquina``: o acelerador do plano, para a ficha sair com o logo da unidade
    que o trata (ver ``logo_da_maquina``).
    """
    arquivo = logo_da_maquina(maquina)
    if not os.path.exists(arquivo):
        _LOG.warning("Logo não encontrado em %s — cabeçalho sai sem ele", arquivo)
        return
    try:
        c.drawImage(arquivo, x, y, w, h, preserveAspectRatio=True, mask="auto", **extra)
    except Exception:  # noqa: BLE001 — a ficha sai sem o logo, não sai quebrada
        _LOG.exception("Falha ao desenhar o logo")

# Paleta do modelo.
# 2º isocentro. Era LARANJA (#F8CBAD) e não combinava com marca nenhuma: briga
# com o verde-água da Clinica e, pior, com o vermelho do SAT, onde laranja ao
# lado de vermelho fica sujo. Este azul é o mesmo tom da família do amarelo e do
# antigo laranja (mesma claridade), então a folha não muda de peso — só de
# temperatura, e passa a conversar com o logo nas duas unidades.
AZUL_ISO = HexColor("#BDD7EE")
AMARELO = HexColor("#FFF2CC")
CINZA = HexColor("#D9D9D9")
VERDE_CLINICA       = HexColor("#00A89D")
VERDE_CLINICA_CLARO = HexColor("#B3E8E5")


@dataclass(frozen=True)
class Tema:
    """Cor de MARCA das páginas 2 e 3 — a que identifica a unidade.

    ``forte`` pinta a linha "Fase", o 1º plano e o 1º isocentro; ``clara`` é o
    fundo suave que os acompanha. O resto
    da paleta não muda de unidade: o AMARELO é semântico (gating, mesa fora do
    zero, bólus — "confira isto"), o CINZA é célula inativa, e as demais cores de
    plano só precisam ser distinguíveis entre si.
    """
    forte: "HexColor"
    clara: "HexColor"


TEMA_CLINICA = Tema(VERDE_CLINICA, VERDE_CLINICA_CLARO)
# SAT: vermelho e rosa claro do logo (o vermelho é o #ED323E do próprio arquivo;
# o claro é o mesmo tom clareado na proporção que o verde claro tem do verde).
TEMA_SAT = Tema(HexColor("#ED323E"), HexColor("#FAC8CB"))

TEMAS = {"sat": TEMA_SAT}


def tema_da_maquina(maquina: str | None) -> Tema:
    """Cores da ficha para a unidade que trata naquele acelerador.

    Sai da mesma tabela do logo (``Maquina.paleta``): a ficha do Synergy é do SAT
    e sai na cor do SAT. Máquina sem paleta própria usa a da Clinica.
    """
    m = constantes.identificar_maquina(maquina)
    return TEMAS.get(m.paleta if m else "", TEMA_CLINICA)


def _cor_iso(feixes: list, j: int, tema: Tema = TEMA_CLINICA) -> "HexColor":
    """Cor da coluna do isocentro ``j``. O iso 0 usa a cor de marca, para casar
    com a linha "Fase" da pág. 2; os demais, cores distintas entre si."""
    cores = [tema.forte, AZUL_ISO, AMARELO]
    idx = feixes[j].get("iso_index", 0) if j < len(feixes) else 0
    return cores[min(idx, len(cores) - 1)]


# ---------------------------------------------------------------------------
# Helpers de desenho (origem no canto superior esquerdo)
# ---------------------------------------------------------------------------


def br(valor, casas: int = 1) -> str:
    """Formata número no padrão brasileiro (vírgula decimal). Vazio -> ''.

    Mostra SEMPRE ``casas`` decimais. A versão que omitia a casa nos valores
    inteiros convidava a chamar com ``casas=0`` — e aí o número era arredondado
    de verdade: mesa de 7,5° saía "8" e 352,5° saía "352" (o arredondamento do
    Python é bancário, para o par mais próximo). Na ficha nenhum valor pode ser
    arredondado; contagens (nº de frações) não passam por aqui.
    """
    if valor is None or valor == "":
        return ""
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    txt = f"{f:.{casas}f}"
    if float(txt) == 0:
        txt = f"{0.0:.{casas}f}"   # -0,04 não vira "-0,0"
    return txt.replace(".", ",")


# Tipografia das tabelas da pág. 2 (tabela do plano e tabela de campos). Um só
# tamanho para os VALORES e um para os CABEÇALHOS, em vez dos 8,5/9/9,5 que se
# misturavam na mesma tabela. Os valores são dimensionados pela célula mais
# apertada com conteúdo real ("Dias alter." em 50pt, valores de campo em 36pt),
# e o cabeçalho pela palavra mais larga ("Modalidade"); o que ainda assim não
# couber encolhe sozinho em ``Tela.txt``.
_FONTE_VAL_TABELA = 9.5
_FONTE_CAB_TABELA = 9
_PAD_CELULA = 5    # folga (pt) reservada nas laterais da célula
_FONTE_MIN = 5.5   # piso do encolhimento automático


def _tam_uniforme(c, textos, largura: float,
                  font: str = "Helvetica", teto: float = _FONTE_VAL_TABELA) -> float:
    """Maior corpo (≤ ``teto``) em que TODOS os ``textos`` cabem em ``largura``.

    O encolhimento por célula de ``Tela.txt`` é por texto: numa coluna estreita,
    "1800,0" saía menor que "500,0" e a coluna ficava com três tamanhos. Aqui o
    grupo inteiro (as doses de uma grade, os rótulos de Imagem) é dimensionado
    pelo item mais largo e desenhado no MESMO corpo.
    """
    disp = largura - _PAD_CELULA
    maior = max((c.stringWidth(str(s), font, teto) for s in textos if str(s)),
                default=0.0)
    if maior <= disp or maior <= 0 or disp <= 0:
        return teto
    return max(teto * disp / maior, _FONTE_MIN)


class Tela:
    """Canvas com origem no topo-esquerda e helpers de célula/grade."""

    def __init__(self, c: canvas.Canvas, largura: float, altura: float):
        self.c = c
        self.W = largura
        self.H = altura

    def ret(self, x, y, w, h, fill=None, stroke=True, lw=0.6):
        c = self.c
        if fill is not None:
            c.setFillColor(fill)
        c.setStrokeColor(black)
        c.setLineWidth(lw)
        c.rect(x, self.H - (y + h), w, h, stroke=1 if stroke else 0, fill=1 if fill else 0)

    def moldura(self, x, y, w, h, r=4, lw=1.1):
        """Contorno externo ARREDONDADO (só borda) desenhado POR CIMA de uma
        tabela/caixa: as células internas seguem retas e só o quadro externo fica
        com cantos redondos."""
        c = self.c
        c.setStrokeColor(black)
        c.setLineWidth(lw)
        c.roundRect(x, self.H - (y + h), w, h, r, stroke=1, fill=0)

    def recorte_ini(self, x, y, w, h, r=4):
        """Começa a recortar o desenho a um retângulo de cantos arredondados: a
        grade quadrada desenhada em seguida é APARADA na curva, para os cantos
        ficarem perfeitamente redondos (sem o quadradinho da grade vazando fora
        do arco). Pareie com :meth:`recorte_fim` antes de chamar :meth:`moldura`."""
        c = self.c
        c.saveState()
        p = c.beginPath()
        p.roundRect(x, self.H - (y + h), w, h, r)
        c.clipPath(p, stroke=0, fill=0)

    def recorte_fim(self):
        """Encerra o recorte iniciado por :meth:`recorte_ini`."""
        self.c.restoreState()

    def txt(self, x, y, s, font="Helvetica", size=8.5, align="l", w=None, h=None, color=black):
        if s is None or s == "":
            return
        c = self.c
        # Com largura de célula conhecida, encolhe SÓ o texto que não caberia, em
        # vez de baixar a fonte da tabela inteira: o tamanho nominal é uniforme e
        # um valor atípico (rótulo de plano longo, "Fase (30-70%)") não vaza para
        # a célula vizinha nem obriga a tabela a ficar miúda.
        if w:
            disp = w - _PAD_CELULA
            larg = c.stringWidth(str(s), font, size)
            if larg > disp > 0:
                size = max(size * disp / larg, _FONTE_MIN)
        c.setFont(font, size)
        c.setFillColor(color)
        baseline = self.H - (y + (h / 2 + size * 0.36 if h else size))
        if align == "c" and w:
            c.drawCentredString(x + w / 2, baseline, str(s))
        elif align == "r" and w:
            c.drawRightString(x + w - 3, baseline, str(s))
        else:
            c.drawString(x + 3, baseline, str(s))

    def vtxt(self, x, y, s, font="Helvetica", size=8, w=None, h=None, color=black):
        """Texto girado 90° (lê de baixo p/ cima), centrado na célula x,y,w,h."""
        if s is None or s == "":
            return
        c = self.c
        cx = x + (w / 2 if w else 0)
        cy = y + (h / 2 if h else 0)
        c.saveState()
        c.setFont(font, size)
        c.setFillColor(color)
        c.translate(cx, self.H - cy)
        c.rotate(90)
        c.drawCentredString(0, -size * 0.36, str(s))
        c.restoreState()

    def celula(self, x, y, w, h, valor="", label=None, font="Helvetica", size=8.5,
               align="l", fill=None, label_font="Helvetica-Bold"):
        """Desenha uma célula com borda; opcionalmente rótulo em negrito + valor."""
        self.ret(x, y, w, h, fill=fill)
        if label is not None:
            self.txt(x, y, label, font=label_font, size=size, h=h)
            lw = self.c.stringWidth(label, label_font, size) + 6
            self.txt(x + lw, y, valor, font=font, size=size, h=h)
        else:
            self.txt(x, y, valor, font=font, size=size, align=align, w=w, h=h)


# ---------------------------------------------------------------------------
# Página 2 — Ficha Técnica de Tratamento
# ---------------------------------------------------------------------------

# Altura (pt) do bloco de Observações no modo COMPACTO (mapa embutido abaixo):
# título(13) + caixa(91). Era o bloco Observações+Checklist, dimensionado pela
# tabela do Checklist — que se mudou para a contracapa (``capa_pdf``). A altura
# ficou como estava de propósito: é ela que decide quanto do mapa de frações
# cabe na pág. 2, e mexer nisso é mudar quantas fichas saem numa folha só.
_ALTURA_OBS_COMPACTA = 13 + 91

CAMPOS_LINHAS = [
    ("Campo", "numero"),
    ("Fase", "fase"),
    ("Energia", "energia_rotulo"),
    ("SSD", "ssd"),
    ("Y1", "y1"),
    ("Y2", "y2"),
    ("X1", "x1"),
    ("X2", "x2"),
    ("Gantry", "gantry"),
    ("Coll", "colimador"),
    ("Mesa", "mesa"),
    ("Bólus", "bolus"),
    ("Tabela", "tabela"),
    ("UM", "um"),
]

# Na Elekta a linha "Tabela" (tolerance table) dá lugar a "Filtro": o Monaco usa
# cunha motorizada nos campos 3D e quem monta o campo precisa ver qual é. Nos
# planos do Eclipse a linha segue sendo a Tabela.
_LINHA_TABELA = ("Tabela", "tabela")
_LINHA_FILTRO = ("Filtro", "filtro")


def linhas_campos(planos_rp) -> list[tuple[str, str]]:
    """Linhas da tabela de campos para os planos dados (um dict de RP ou vários).

    Troca Tabela por Filtro quando QUALQUER plano da página vem da Elekta — na
    ficha multi-plano a tabela é uma só, então o critério é da página, não do
    plano. Fichas antigas (registro JSON sem ``fabricante``) seguem com Tabela.
    """
    rps = [planos_rp] if isinstance(planos_rp, dict) else list(planos_rp or [])
    elekta = any("elekta" in str((rp or {}).get("fabricante", "")).lower()
                 for rp in rps)
    if not elekta:
        return CAMPOS_LINHAS
    return [_LINHA_FILTRO if lin == _LINHA_TABELA else lin
            for lin in CAMPOS_LINHAS]

N_CAMPOS = 21  # colunas de campo no formulário

# Tratamentos curtos (≤ este nº de frações no mapa) cabem na própria página 2:
# o mapa de frações vira uma faixa horizontal e a Ficha inteira fica em 1 folha.
_MAX_FRAC_EMBUTIR = 5
# Altura da linha do mapa de frações — a MESMA nos três mapas (página própria,
# embutido na pág. 2 e combinado agendado), para a grade nunca esticar nem
# espremer: é isso que deformava a tabela. Dimensionada pelo pior caso real,
# _MAX_LINHAS_MAPA linhas na página própria: abaixo do cabeçalho sobram 517pt
# (595 de folha − 40 do topo − 14 do cabeçalho da grade − 24 de margem inferior),
# e 39 × 13 = 507pt cabem. A 14pt caberiam só 36 linhas.
_HLIN_MAPA = 13
# Nº de linhas (frações + linhas de replanejamento) que o mapa comporta sem
# comprimir a linha. Acima disso a grade ainda sai, mas encolhe.
_MAX_LINHAS_MAPA = 39
# Margem inferior (pt) reservada abaixo da grade: ~8,5 mm, para ela não cair na
# área não-imprimível e sair cortada.
_MARGEM_INFERIOR = 24
_HCAB_MAPA = 14   # altura do cabeçalho da grade do mapa


def frac_tem_imagem(i: int, imagem_texto: str, frequencia: str,
                    dias_img: set | None = None) -> bool:
    """True se a fração ``i`` (0-based) recebe imagem, dada a frequência.

    ``Diária`` → todas; ``Semanal`` → frações 1 e 2 e a 1ª de cada semana (a
    cada 5); ``Personalizado`` → só as frações (1-based) em ``dias_img``. Sem
    modalidade de imagem, nunca marca."""
    if not imagem_texto:
        return False
    if frequencia == "Diária":
        return True
    if frequencia == "Semanal":
        return i in (0, 1) or (i >= 5 and (i - 5) % 5 == 0)
    if frequencia == "Personalizado":
        return (i + 1) in (dias_img or set())
    return False


def imagem_por_fracao(protocolos: list, sequencia: list) -> list[str]:
    """Modalidade de imagem de CADA fração do mapa combinado (pág. 3 multi-plano).

    Args:
        protocolos: ``(imagem, frequencia, dias)`` por plano, na ordem dos planos
            — o que cada aba do formulário definiu. ``dias`` (1-based) só vale no
            "Personalizado".
        sequencia: ``sequencia[i]`` = índices dos planos tratados na fração ``i``
            (o agendamento).

    Cada plano responde pelas SUAS frações: o "Personalizado" do boost numera os
    dias a partir da 1ª fração do boost, não da 1ª do tratamento. Antes tudo saía
    do protocolo do plano 1, então o boost herdava a frequência da fase e os dias
    escolhidos caíam em linhas do outro plano.

    Num dia com planos concomitantes de protocolos diferentes devolve as
    modalidades distintas juntas (ex.: ``"MV/CBCT"``) — omitir uma faria o
    técnico deixar de tirar a imagem que aquele plano pede.

    Returns:
        Lista do tamanho de ``sequencia``; ``""`` nas frações sem imagem.
    """
    n = len(protocolos)
    corrida = [0] * n           # nº de frações já dadas de cada plano
    saida: list[str] = []
    for linha in sequencia:
        ativos = [p for p in linha if 0 <= p < n]
        vistos: list[str] = []
        for p in sorted(ativos):
            imagem, freq, dias = protocolos[p]
            if imagem and imagem not in vistos and frac_tem_imagem(
                    corrida[p], imagem, freq, dias):
                vistos.append(imagem)
        for p in ativos:
            corrida[p] += 1
        saida.append("/".join(vistos))
    return saida


def _cabecalho(t: Tela, dados: dict):
    M = 14
    x, y = M, 14
    h = 72
    # Logo.
    xl = x
    wl = 150
    _logo(t.c, xl + 6, t.H - (y + h - 6), wl - 12, h - 18, anchor="c",
          maquina=dados.get("maquina"))
    # Título.
    xt = xl + wl
    wt = 176
    # Título sem moldura (só o texto).
    t.txt(xt, y + 16, "Ficha Técnica", font="Helvetica-Bold", size=17, align="c", w=wt)
    t.txt(xt, y + 40, "de Tratamento", font="Helvetica-Bold", size=17, align="c", w=wt)
    # Caixa do paciente (4 linhas).
    xp = xt + wt
    wp = 360
    lh = h / 4
    meia = wp / 2
    t.recorte_ini(xp, y, wp, h)
    t.celula(xp, y, wp, lh, valor=dados.get("pac_nome", ""), label="Nome:", size=10,
             font="Helvetica-Bold")
    t.celula(xp, y + lh, meia, lh, valor=dados.get("pac_registro", ""), label="RGH:", size=9.5)
    t.celula(xp + meia, y + lh, wp - meia, lh, valor=dados.get("pac_nascimento", ""),
             label="Data de Nasc:", size=9.5)
    t.celula(xp, y + 2 * lh, wp, lh, valor=dados.get("eq_medico", ""), label="Médico(a):", size=9.5)
    t.celula(xp, y + 3 * lh, wp - 130, lh, valor=dados.get("eq_fisico", ""), label="Físico(a):",
             size=9.5)
    t.celula(xp + wp - 130, y + 3 * lh, 130, lh, label="AL:", size=9.5,
             valor=constantes.rotulo_maquina(dados.get("maquina", "")))
    t.recorte_fim()
    t.moldura(xp, y, wp, h)   # contorno arredondado da caixa do paciente
    # Imagem da mesa (canto superior direito do cabeçalho).
    ximg = xp + wp
    wimg = t.W - M - ximg
    if wimg > 10:
        _m = constantes.identificar_maquina(dados.get("maquina", ""))
        _grupo = _m.grupo_mesa if _m else None
        img_mesa = TABLE_TB if _grupo == "TB" else (
            TABLE_SERIE_C if _grupo == "serie_c" else None)
        if img_mesa and os.path.exists(img_mesa):
            try:
                t.c.drawImage(img_mesa, ximg + 2, t.H - (y + h - 2), wimg - 4, h - 4,
                              preserveAspectRatio=True, mask="auto", anchor="c")
            except Exception:  # noqa: BLE001
                _LOG.exception("Falha ao desenhar a imagem da mesa %r", img_mesa)
    return y + h + 4


def _tabela_plano(t: Tela, y0: float, dados: dict, rp: dict):
    M = 14
    x0, W = M, t.W - 2 * M
    _gating_val = dados.get("gating", "")
    _fase_janela = dados.get("gating_fase", "")  # ex.: "10-80"
    if _gating_val == "Sim":
        _modal = dados.get("gating_modalidade", "")
        if _modal == "Breath-Hold":
            _fase_janela = "DIBH"
        elif _modal == "Fase":
            _fase_janela = f"Fase ({_fase_janela})"
        elif _modal:
            _fase_janela = _modal
    _fracio_val = dados.get("fracionamento", "")
    _fill_fase   = AMARELO if _gating_val == "Sim" else None
    _fill_fracio = AMARELO if _fracio_val not in ("", "1x dia") else None
    # 4-tuplas: (nome, largura, valor, fill_condicional)
    simples = [
        # Gating cede 6pt para Modalidade: só recebe "Sim"/"Não" e sobrava largura,
        # enquanto "Modalidade" era a palavra que travava o tamanho do cabeçalho.
        ("Gating", 40, _gating_val, None),
        ("Modalidade", 61, _fase_janela, _fill_fase),
        # Decúbito + lado que entra no gantry: o técnico monta o setup por aqui.
        # Destacado em amarelo quando NÃO é o dorsal cabeça-primeiro de rotina.
        ("Posicio-\nnamento", 62, constantes.rotulo_posicao(rp.get("patient_position")),
         AMARELO if _posicao_incomum(rp) else None),
        ("Plano", 96, rp.get("rotulo_plano") or rp.get("nome_plano", ""), None),
        ("Qtde de\nFrações", 46, rp.get("num_fracoes"), None),
        ("Dose/dia\n(cGy)", 46, br((rp.get("dose_fracao") or 0) * 100) if rp.get("dose_fracao") else "", None),
        ("Dose\n(cGy)", 46, br((rp.get("dose_total") or 0) * 100) if rp.get("dose_total") else "", None),
        ("Fracio-\nnamento", 50, _fracio_val, _fill_fracio),
    ]
    grupos = [("SSD TP0 (cm)", ["G0", "G270", "G90"]),
              ("Deslocamento (cm)", ["Lat.", "Long.", "Vert."]),
              ("SSD Iso (cm)", ["G0", "G270", "G90"])]
    larg_simples = sum(w for _, w, *_ in simples)
    larg_sub = (W - larg_simples) / 9
    hh = 14  # altura de uma sub-linha de cabeçalho
    hcab = 2 * hh
    hlin = 15

    t.recorte_ini(x0, y0, W, hcab + hlin)
    # Cabeçalho — colunas simples (2 linhas).
    x = x0
    for nome, w, _, _fill_cond in simples:
        t.ret(x, y0, w, hcab, fill=white)
        linhas = nome.split("\n")
        for i, ln in enumerate(linhas):
            t.txt(x, y0 + (hcab / 2 - len(linhas) * 5) + i * 9, ln, font="Helvetica-Bold",
                  size=_FONTE_CAB_TABELA, align="c", w=w)
        x += w
    # Cabeçalho — grupos.
    for titulo, subs in grupos:
        wg = larg_sub * len(subs)
        t.ret(x, y0, wg, hh, fill=white)
        t.txt(x, y0, titulo, font="Helvetica-Bold", size=_FONTE_CAB_TABELA,
              align="c", w=wg, h=hh)
        for j, sub in enumerate(subs):
            t.ret(x + j * larg_sub, y0 + hh, larg_sub, hh, fill=white)
            t.txt(x + j * larg_sub, y0 + hh, sub, font="Helvetica-Bold",
                  size=_FONTE_CAB_TABELA, align="c", w=larg_sub, h=hh)
        x += wg

    sub_vals = [
        br(rp.get("ssd_tp0_g0")),   br(rp.get("ssd_tp0_g270")),  br(rp.get("ssd_tp0_g90")),
        br(rp.get("desl_lat")),      br(rp.get("desl_long")),      br(rp.get("desl_vert")),
        br(rp.get("ssd_iso_g0")),    br(rp.get("ssd_iso_g270")),   br(rp.get("ssd_iso_g90")),
    ]

    # Uma única linha de dados (só o que tem informação — a grade não se estende
    # por linhas vazias).
    yr = y0 + hcab
    x = x0
    for _, w, val, fill_cond in simples:
        t.ret(x, yr, w, hlin, fill=fill_cond if val else None)
        t.txt(x, yr, val, size=_FONTE_VAL_TABELA, align="c", w=w, h=hlin)
        x += w
    for sv in sub_vals:
        t.ret(x, yr, larg_sub, hlin)
        if sv:
            t.txt(x, yr, sv, size=_FONTE_VAL_TABELA, align="c", w=larg_sub, h=hlin)
        x += larg_sub
    t.recorte_fim()
    t.moldura(x0, y0, W, hcab + hlin)
    return y0 + hcab + hlin + 4


def _posicao_incomum(rp: dict) -> bool:
    """True quando o decúbito NÃO é o de rotina (HFS: dorsal, cabeça no gantry).

    Mesmo destaque amarelo do DIBH/mesa/bólus: o que muda o setup em relação ao
    padrão salta aos olhos. Sem ``PatientPosition`` no DICOM não destaca nada —
    campo vazio não é exceção, é ausência de informação.
    """
    pos = str(rp.get("patient_position") or "").strip().upper()
    return bool(pos) and pos != "HFS"


def _mesa_nao_zero(feixe: dict) -> bool:
    """True quando o ângulo de mesa do feixe é diferente de zero (não-coplanar)."""
    try:
        return abs(float(feixe.get("mesa") or 0)) > 1e-9
    except (TypeError, ValueError):
        return False


def _bolus_presente(feixe: dict) -> bool:
    """True quando o feixe usa bólus (campo preenchido e não-negativo)."""
    v = str(feixe.get("bolus", "") or "").strip().lower()
    return v not in ("", "-", "nao", "não", "n", "sem", "0")


def valor_do_campo(feixe: dict, chave: str, col: int = 0) -> str:
    """O texto de UMA célula da tabela de campos.

    Extraída de ``_tabela_campos`` para a Ficha Virtual poder mostrar a mesma
    tabela na tela sem recompor a regra. Ela tem quatro armadilhas, e as quatro
    já custaram um número errado no papel:

    * ``numero`` não existe no feixe — é a POSIÇÃO na tabela, e o feixe 1 do
      DICOM pode não ser o primeiro impresso (ver ``ordenar_feixes``);
    * ``or ""`` engole o ZERO: colimador 0° e mesa 0° são o caso mais comum, e
      saíam como célula vazia, que se lê como "a ficha não gravou";
    * número vai em vírgula decimal (``br``), nunca em ponto;
    * gantry de ARCO é ``300→179 h``, não o ângulo inicial — só ele descreve um
      campo parado que não existe;
    * a chave pode EXISTIR valendo ``None`` — apagar uma célula na Edição da
      Ficha grava exatamente isso. O default do ``get`` só cobre a chave
      AUSENTE, então ``str()`` cru fazia a palavra "None" sair IMPRESSA na
      ficha. Vazio é vazio em toda célula.
    """
    if chave == "numero":
        return str(col + 1)
    if chave == "fase":
        valor = feixe.get("fase", 1)
        return "" if valor is None else str(valor)
    if chave in ("ssd", "y1", "y2", "x1", "x2", "colimador", "mesa", "um"):
        # 1 casa também em colimador e mesa: com 0 casas, mesa 7,5° saía "8".
        valor = feixe.get(chave)
        return br(valor, 1) if valor is not None else ""
    if chave == "gantry":
        return str(dicom_rt.gantry_texto(feixe, 1))
    valor = feixe.get(chave, "")
    return "" if valor is None else str(valor)


# Corpo do SENTIDO ("h"/"ah") na segunda linha da célula de gantry. Menor que o
# dos ângulos de propósito: o número é o que se compara com o console, a letra
# só desfaz a ambiguidade de por qual lado o braço passa.
_FONTE_SENTIDO_ARCO = 6.0


def _celula_gantry(t: Tela, x: float, y: float, w: float, h: float,
                   texto: str) -> None:
    """A célula do gantry — em DUAS linhas quando é arco.

    "352,5→7,5 ah" precisa de 34,5pt onde a célula tem 31,4, e o encolhimento
    automático de ``Tela.txt`` para no piso de 5,5pt: o excedente ia INVADIR a
    coluna vizinha, porque o recorte é da tabela inteira, não da célula — o
    ângulo de um campo saía por cima do ângulo do outro, na folha que se confere
    contra o console. Quebrado em duas, o par de ângulos cabe a ~7pt e o sentido
    fica embaixo, legível.

    Campo parado não tem sufixo e continua exatamente como sempre saiu: uma
    linha, centrada, no corpo cheio da tabela.
    """
    angulos, _, sentido = str(texto or "").partition(" ")
    if not sentido:
        t.txt(x, y, texto, size=_FONTE_VAL_TABELA, align="c", w=w, h=h)
        return
    # Cada metade recebe a ALTURA de meia célula: é ela que ``Tela.txt`` usa
    # para centrar verticalmente, então as duas linhas se dividem sozinhas.
    t.txt(x, y, angulos, size=_FONTE_VAL_TABELA, align="c", w=w, h=h * 0.62)
    t.txt(x, y + h * 0.48, sentido, size=_FONTE_SENTIDO_ARCO, align="c",
          w=w, h=h * 0.52)


def _tabela_campos(t: Tela, y0: float, feixes: list, cor_fase=None, linhas=None,
                   tema: Tema = TEMA_CLINICA):
    """Tabela de campos. ``cor_fase`` (opcional): callable ``col -> cor`` que
    pinta a célula da linha "Fase" por coluna — usado no multi-plano para dar
    uma cor por plano. Sem ele, a linha Fase inteira usa a cor de destaque.
    ``linhas``: linhas a desenhar (ver ``linhas_campos``); sem ela, ``CAMPOS_LINHAS``.
    ``tema``: cor de marca da unidade (ver ``tema_da_maquina``)."""
    linhas = linhas or CAMPOS_LINHAS
    M = 14
    x0, W = M, t.W - 2 * M
    wlbl = 50
    # Só desenha colunas de campo que EXISTEM (um feixe cada); a grade preta não
    # se estende por colunas vazias. Largura da coluna preserva a da folha cheia
    # (N_CAMPOS), então poucos campos = tabela compacta à esquerda, sem esticar.
    n_cols = max(len(feixes), 1)
    wcol = (W - wlbl) / N_CAMPOS
    hlin = 13   # 14 linhas: cada 0,5pt aqui vale 7pt de folga para o mapa embutido
    t.recorte_ini(x0, y0, wlbl + n_cols * wcol, len(linhas) * hlin)
    for i, (rotulo, chave) in enumerate(linhas):
        yr = y0 + i * hlin
        eh_fase = rotulo == "Fase"
        # Rótulo (à esquerda).
        t.ret(x0, yr, wlbl, hlin, fill=tema.forte if eh_fase else None)
        t.txt(x0, yr, rotulo + ":", font="Helvetica-Bold", size=_FONTE_VAL_TABELA,
              align="r", w=wlbl, h=hlin)
        # Colunas dos campos.
        for col in range(n_cols):
            xc = x0 + wlbl + col * wcol
            if eh_fase:
                if cor_fase is not None:
                    fill = cor_fase(col) if col < len(feixes) else None
                else:
                    fill = tema.forte
            elif chave == "mesa" and col < len(feixes) and _mesa_nao_zero(feixes[col]):
                # Mesa != 0 (feixe não-coplanar): destaca em amarelo, igual ao DIBH.
                fill = AMARELO
            elif chave == "bolus" and col < len(feixes) and _bolus_presente(feixes[col]):
                # Bólus presente: destaca em amarelo, igual ao DIBH.
                fill = AMARELO
            else:
                fill = None
            t.ret(xc, yr, wcol, hlin, fill=fill)
            if col < len(feixes):
                # UMA regra para a célula, aqui e na tela da Ficha Virtual —
                # ver ``valor_do_campo``.
                valor = valor_do_campo(feixes[col], chave, col)
                if chave == "gantry":
                    _celula_gantry(t, xc, yr, wcol, hlin, valor)
                else:
                    t.txt(xc, yr, valor, size=_FONTE_VAL_TABELA, align="c",
                          w=wcol, h=hlin)
    t.recorte_fim()
    t.moldura(x0, y0, wlbl + n_cols * wcol, len(linhas) * hlin)
    return y0 + len(linhas) * hlin + 6


# ── Observações digitadas pelo usuário (Edição da Ficha) ─────────────────────
# O texto vai na caixa "Observações gerais do tratamento"; o trecho escrito entre
# ``**`` sai em NEGRITO sobre tarja amarela (o mesmo AMARELO das tabelas), que é
# como o usuário pede destaque sem precisar de um editor rico.
_OBS_MARCA = "**"
_OBS_FONTE = "Helvetica"
_OBS_FONTE_HL = "Helvetica-Bold"
# Mesmo corpo dos valores das tabelas da pág. 2 (tabela do plano e de campos),
# nos dois layouts da caixa: a observação é para ser lida de longe, junto com a
# ficha, e cabe folgado mesmo no bloco compacto.
_OBS_TAM = _FONTE_VAL_TABELA


def _obs_segmentos(linha: str) -> list[tuple[str, bool]]:
    """Divide a linha em trechos ``(texto, destaque)`` pelos pares de ``**``.

    Um ``**`` sem fechar não destaca o resto do texto: só pares contam.
    """
    partes = linha.split(_OBS_MARCA)
    sobrando = len(partes) % 2 == 0        # nº ímpar de marcadores → último aberto
    segs = []
    for i, p in enumerate(partes):
        if not p:
            continue
        segs.append((p, i % 2 == 1 and not (sobrando and i == len(partes) - 1)))
    return segs


def _maior_prefixo(c, palavra: str, fonte: str, size: float, larg: float) -> str:
    """Maior pedaço inicial de ``palavra`` que cabe em ``larg`` (mín. 1 caractere)."""
    n = 1
    while n < len(palavra) and c.stringWidth(palavra[:n + 1], fonte, size) <= larg:
        n += 1
    return palavra[:n]


def _obs_quebrar(c, texto: str, larg: float, size: float) -> list[list[tuple]]:
    """Quebra o texto em linhas de ``larg`` pt, preservando as quebras digitadas.

    Devolve uma lista de linhas, cada uma com ``(token, destaque, x, largura)``.
    Palavra maior que a caixa (URL, código) é partida em vez de vazar.
    """
    linhas: list[list[tuple]] = []
    for bruta in str(texto).replace("\t", " ").split("\n"):
        atual: list[tuple] = []
        x = 0.0
        for trecho, hl in _obs_segmentos(bruta):
            fonte = _OBS_FONTE_HL if hl else _OBS_FONTE
            for tok in re.findall(r"\s+|\S+", trecho):
                w = c.stringWidth(tok, fonte, size)
                if tok.isspace():
                    # Espaço não abre linha nem estoura a margem: some na quebra.
                    if atual and x + w <= larg:
                        atual.append((tok, hl, x, w))
                        x += w
                    continue
                while w > larg:
                    if atual:
                        linhas.append(atual); atual = []; x = 0.0
                    pedaco = _maior_prefixo(c, tok, fonte, size, larg)
                    linhas.append([(pedaco, hl, 0.0,
                                    c.stringWidth(pedaco, fonte, size))])
                    tok = tok[len(pedaco):]
                    w = c.stringWidth(tok, fonte, size)
                if not tok:
                    continue
                if atual and x + w > larg:
                    linhas.append(atual); atual = []; x = 0.0
                atual.append((tok, hl, x, w))
                x += w
        linhas.append(atual)
    return linhas


def _fim_tarja(linha: list[tuple], j: int, ini: float) -> float:
    """x do fim da tarja: borda direita do último token com tinta antes de ``j``
    (espaços à direita do destaque não entram na tarja)."""
    for tok, _hl, tx, tw in reversed(linha[:j]):
        if tok.strip():
            return max(tx + tw, ini)
    return ini


def _obs_texto(t: Tela, x: float, y: float, w: float, h: float, texto: str,
               size: float = _OBS_TAM, pad: float = 5) -> None:
    """Escreve as Observações dentro da caixa (x, y, w, h), quebrando linhas e
    destacando com tarja amarela os trechos marcados com ``**``. O que não couber
    é aparado — a caixa (e o resto da página) nunca é estourada."""
    if not str(texto or "").strip():
        return
    larg = w - 2 * pad
    if larg <= 0 or h <= 0:
        return
    c = t.c
    lh = size * 1.32
    linhas = _obs_quebrar(c, texto, larg, size)
    t.recorte_ini(x, y, w, h)
    for i, linha in enumerate(linhas):
        ytop = y + pad + i * lh
        if ytop + lh > y + h:
            break     # o excedente é aparado (a caixa manda no tamanho)
        # Tarjas primeiro (ficam ATRÁS do texto), fundindo destaques vizinhos
        # numa faixa só — senão sobrariam buracos brancos entre as palavras.
        ini = None
        for j, (_tok, hl, tx, _tw) in enumerate(linha + [("", False, 0.0, 0.0)]):
            if hl and ini is None:
                ini = tx
            elif not hl and ini is not None:
                fim = _fim_tarja(linha, j, ini)
                t.ret(x + pad + ini - 1, ytop, fim - ini + 2, lh,
                      fill=AMARELO, stroke=False)
                ini = None
        base = t.H - (ytop + lh / 2 + size * 0.36)   # mesma centragem de Tela.txt
        c.setFillColor(black)
        for tok, hl, tx, _tw in linha:
            if not tok.strip():
                continue
            c.setFont(_OBS_FONTE_HL if hl else _OBS_FONTE, size)
            c.drawString(x + pad + tx, base, tok)
    t.recorte_fim()


def _obs_dos_planos(planos: list, rotulos: list | None) -> str:
    """Observações da pág. 2 combinada (multi-plano) — a caixa é UMA só.

    A observação é do caso (o mesmo texto vem repetido em todos os planos), então
    o normal é sair uma vez, sem rótulo. Textos diferentes por plano só aparecem
    em registros antigos ou em fichas remontadas de planos separados; aí cada
    bloco sai rotulado, para não misturar.
    """
    itens = [(rotulos[i] if rotulos and i < len(rotulos) else f"Plano {i + 1}",
              str((p.get("dados") or {}).get("observacoes", "") or "").strip())
             for i, p in enumerate(planos)]
    itens = [(rot, txt) for rot, txt in itens if txt]
    distintos = list(dict.fromkeys(txt for _rot, txt in itens))
    if len(distintos) <= 1:
        return distintos[0] if distintos else ""
    return "\n".join(f"{rot}: {txt}" for rot, txt in itens)


def _observacoes(t: Tela, y0: float, altura_bloco: float | None = None,
                 texto: str = ""):
    """Caixa "Observações gerais do tratamento", da margem à margem.

    Sem ``altura_bloco`` (página inteira) ela desce até a margem de impressão;
    com ``altura_bloco`` (modo COMPACTO) fica com essa altura, para o mapa de
    frações caber embaixo.

    Dividia a faixa com o Checklist Pré-Tratamento, que se mudou INTEIRO para a
    contracapa (ver ``capa_pdf.CHECKLIST_ITENS``) — com ele foram a legenda das
    colunas e o "Nome, Carimbo e Data", que era a assinatura DELE; a contracapa
    já tem o carimbo da equipe. A largura que ele ocupava ficou com as
    Observações, que é onde o texto do caso é escrito.

    ``texto``: observações digitadas em Edição da Ficha (``**destaque**``)."""
    M = 14
    x0, W = M, t.W - 2 * M
    h_titulo = 14 if altura_bloco is None else 13
    # ``altura_bloco`` é a altura do BLOCO (título + caixa) — é o que o chamador
    # reserva na folha antes do mapa.
    altura = (t.H - 24 - y0 - h_titulo) if altura_bloco is None \
        else altura_bloco - h_titulo

    t.txt(x0, y0, "Observações gerais do tratamento", font="Helvetica-Bold", size=10)
    t.moldura(x0, y0 + h_titulo, W, altura)   # só a borda arredondada
    _obs_texto(t, x0, y0 + h_titulo, W, altura, texto)


def _largura_campos(t: Tela, n_feixes: int, margem: float = 14) -> float:
    """Largura da tabela de campos — rótulos + uma coluna por feixe.

    A coluna tem sempre a largura da folha cheia (``N_CAMPOS``), então poucos
    campos deixam a tabela curta e o resto da faixa VAZIO. É esse vazio que o
    layout lateral aproveita (ver ``_observacoes_lado``)."""
    W = t.W - 2 * margem
    wlbl = 50
    return wlbl + max(n_feixes, 1) * (W - wlbl) / N_CAMPOS


def _observacoes_lado(t: Tela, x0: float, y0: float, larg: float,
                      alt: float, texto: str = "") -> None:
    """Observações AO LADO da tabela de campos, na faixa livre à direita.

    Com poucos campos a tabela ocupa só a esquerda da folha e sobra meia página
    em branco à direita; embaixo, as Observações gastavam uma faixa inteira e
    empurravam o mapa de frações para uma página só dele. Encaixadas nesse vazio,
    a altura que custavam some — e o mapa cabe na própria pág. 2, com 15 frações
    em vez das 5 de antes.

    Dividia a faixa com o Checklist Pré-Tratamento, que se mudou para a
    contracapa; a caixa ficou com a faixa inteira.

    ``x0``/``larg``: faixa livre à direita da tabela. ``alt``: altura dela (a da
    tabela de campos), que é o teto da caixa."""
    h_titulo = 13
    t.txt(x0, y0, "Observações gerais do tratamento", font="Helvetica-Bold",
          size=10)
    h_obs = alt - h_titulo
    t.moldura(x0, y0 + h_titulo, larg, h_obs)
    _obs_texto(t, x0, y0 + h_titulo, larg, h_obs, texto)


# Até este nº de campos a tabela deixa faixa livre bastante para as Observações
# caberem ao lado dela (ver _observacoes_lado). Com 6+, a tabela já toma a
# folha e o layout volta ao clássico.
_MAX_CAMPOS_LADO = 5


def _lado_a_lado(t: Tela, feixes: list, y_apos_campos: float,
                 total_linhas: int, H: float) -> bool:
    """Vale usar o layout lateral nesta página?

    Duas condições: poucos campos (senão não há faixa livre) e o mapa cabendo
    embaixo (senão a folha ficaria com o vazio de sempre e o mapa numa página à
    parte — aí o layout clássico, com a caixa de Observações grande, é melhor)."""
    return (0 < len(feixes) <= _MAX_CAMPOS_LADO
            and total_linhas > 0
            and _cabe_mapa_ao_lado(y_apos_campos, total_linhas, H))


def _mapa_ao_lado(t: Tela, y_campos: float, y_apos: float, feixes: list,
                  linhas: list, obs: str, tema: Tema) -> None:
    """Desenha as Observações na faixa livre e o título do mapa."""
    M = 14
    x_livre = M + _largura_campos(t, len(feixes), M) + 8
    _observacoes_lado(t, x_livre, y_campos, (t.W - M) - x_livre,
                      len(linhas) * 13, texto=obs)
    t.txt(M, y_apos, "Mapa de frações", font="Helvetica-Bold", size=10)


def _cabe_mapa_ao_lado(y_apos_campos: float, total_linhas: int, H: float) -> bool:
    """O mapa cabe logo abaixo da tabela de campos, no layout lateral?

    Aqui Observações/Checklist não custam altura nenhuma — estão ao lado —,
    então o mapa começa direto depois da tabela de campos."""
    y_mapa = y_apos_campos + 13                      # título "Mapa de frações"
    return (y_mapa + _HCAB_MAPA + total_linhas * _HLIN_MAPA
            <= H - _MARGEM_INFERIOR)


def _cabe_mapa_embutido(y_apos_campos: float, total_linhas: int, H: float) -> bool:
    """O mapa só embute na pág. 2 se couber INTEIRO com a linha de ``_HLIN_MAPA``
    (mesma geometria da pág. 3) dentro da margem inferior. Não cabendo
    (muitos planos e/ou frações), vai para a página própria em vez de espremer as
    linhas — é o que deformava a tabela."""
    y_mapa = y_apos_campos + _ALTURA_OBS_COMPACTA + 4 + 13   # bloco Obs + título
    return (y_mapa + _HCAB_MAPA + total_linhas * _HLIN_MAPA
            <= H - _MARGEM_INFERIOR)


def pagina_ficha(c: canvas.Canvas, dados: dict, store: dict,
                 replan: int = 0, dose_replan: float = 0) -> bool:
    """Página 2 (Ficha Técnica). Em tratamentos curtos (≤ ``_MAX_FRAC_EMBUTIR``
    frações, e desde que o mapa caiba sem espremer) o mapa de frações entra aqui
    como uma faixa horizontal e a Observações/Checklist encolhem — a Ficha fica em
    uma folha só. Devolve ``True`` se embutiu (o chamador não emite a pág. 3)."""
    W, H = landscape(A4)
    t = Tela(c, W, H)
    rp = store.get("RP", {})
    feixes = rp.get("feixes", [])
    y = _cabecalho(t, dados)
    y = _tabela_plano(t, y, dados, rp)
    tema = tema_da_maquina(dados.get("maquina"))
    linhas = linhas_campos(rp)
    y_campos = y
    y = _tabela_campos(t, y, feixes, linhas=linhas, tema=tema)
    n_linhas = total_linhas_fracoes(dados, store, replan)
    obs = str(dados.get("observacoes", "") or "")
    if _lado_a_lado(t, feixes, y, n_linhas, H):
        _mapa_ao_lado(t, y_campos, y, feixes, linhas, obs, tema)
        y += 13
        _grade_fracoes(t, dados, store, y, replan, dose_replan,
                       (H - _MARGEM_INFERIOR) - y, tema=tema)
        return True
    embutir = (n_linhas <= _MAX_FRAC_EMBUTIR
               and _cabe_mapa_embutido(y, n_linhas, H))
    if embutir:
        # Observações/Checklist compactos em cima e o Mapa de frações logo
        # abaixo, com a MESMA geometria da pág. 3 (``_HLIN_MAPA``), sobrando a
        # margem inferior de impressão.
        _observacoes(t, y, altura_bloco=_ALTURA_OBS_COMPACTA, texto=obs)
        y += _ALTURA_OBS_COMPACTA + 4
        t.txt(14, y, "Mapa de frações", font="Helvetica-Bold", size=10)
        y += 13
        _grade_fracoes(t, dados, store, y, replan, dose_replan,
                       (H - _MARGEM_INFERIOR) - y, tema=tema)
    else:
        _observacoes(t, y, texto=obs)
    return embutir


def _valores_linha_plano(p: dict):
    """Valores de uma linha da tabela do plano (multi): (simples, subs, fills)."""
    dados = p["dados"]
    rp = p["store"].get("RP", {})
    gating = dados.get("gating", "")
    janela = dados.get("gating_fase", "")
    if gating == "Sim":
        modal = dados.get("gating_modalidade", "")
        if modal == "Breath-Hold":
            janela = "DIBH"
        elif modal == "Fase":
            janela = f"Fase ({janela})"
        elif modal:
            janela = modal
    fracio = dados.get("fracionamento", "")
    simples = [
        gating, janela,
        constantes.rotulo_posicao(rp.get("patient_position")),
        rp.get("rotulo_plano") or rp.get("nome_plano", ""),
        rp.get("num_fracoes"),
        br((rp.get("dose_fracao") or 0) * 100) if rp.get("dose_fracao") else "",
        br((rp.get("dose_total") or 0) * 100) if rp.get("dose_total") else "",
        fracio,
    ]
    fills = [None, AMARELO if gating == "Sim" else None,
             AMARELO if _posicao_incomum(rp) else None,
             None, None, None, None,
             AMARELO if fracio not in ("", "1x dia") else None]
    subs = [
        br(rp.get("ssd_tp0_g0")), br(rp.get("ssd_tp0_g270")), br(rp.get("ssd_tp0_g90")),
        br(rp.get("desl_lat")), br(rp.get("desl_long")), br(rp.get("desl_vert")),
        br(rp.get("ssd_iso_g0")), br(rp.get("ssd_iso_g270")), br(rp.get("ssd_iso_g90")),
    ]
    return simples, subs, fills


def _tabela_plano_multi(t: Tela, y0: float, planos: list, base: int = 0,
                        tema: Tema = TEMA_CLINICA):
    """Tabela do plano com UMA LINHA POR PLANO (ficha multi-plano).

    ``base``: nº do primeiro plano DESTA página dentro do caso (0-based) — na
    ficha partida em várias páginas 2 (ver ``_grupos_por_campos``) é ele que
    mantém a cor de cada plano igual à das outras páginas."""
    M = 14
    x0, W = M, t.W - 2 * M
    col_defs = [("Gating", 40), ("Modalidade", 61), ("Posicio-\nnamento", 62),
                ("Plano", 96),
                ("Qtde de\nFrações", 46), ("Dose/dia\n(cGy)", 46),
                ("Dose\n(cGy)", 46), ("Fracio-\nnamento", 50)]
    grupos = [("SSD TP0 (cm)", ["G0", "G270", "G90"]),
              ("Deslocamento (cm)", ["Lat.", "Long.", "Vert."]),
              ("SSD Iso (cm)", ["G0", "G270", "G90"])]
    _i_plano = [n for n, _w in col_defs].index("Plano")
    larg_simples = sum(w for _, w in col_defs)
    larg_sub = (W - larg_simples) / 9
    hh = 14
    hcab = 2 * hh
    hlin = 15
    n_rows = max(len(planos), 1)   # uma linha por plano
    t.recorte_ini(x0, y0, W, hcab + n_rows * hlin)
    # Cabeçalho — colunas simples.
    x = x0
    for nome, w in col_defs:
        t.ret(x, y0, w, hcab, fill=white)
        linhas = nome.split("\n")
        for i, ln in enumerate(linhas):
            t.txt(x, y0 + (hcab / 2 - len(linhas) * 5) + i * 9, ln,
                  font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c", w=w)
        x += w
    for titulo, subs in grupos:
        wg = larg_sub * len(subs)
        t.ret(x, y0, wg, hh, fill=white)
        t.txt(x, y0, titulo, font="Helvetica-Bold", size=_FONTE_CAB_TABELA,
              align="c", w=wg, h=hh)
        for j, sub in enumerate(subs):
            t.ret(x + j * larg_sub, y0 + hh, larg_sub, hh, fill=white)
            t.txt(x + j * larg_sub, y0 + hh, sub, font="Helvetica-Bold",
                  size=_FONTE_CAB_TABELA, align="c", w=larg_sub, h=hh)
        x += wg
    # Uma linha por plano — a grade não desce por linhas vazias.
    for r in range(n_rows):
        yr = y0 + hcab + r * hlin
        x = x0
        p = planos[r] if r < len(planos) else None
        if p is not None:
            simples, subs_v, fills = _valores_linha_plano(p)
            # A célula do Plano leva a COR DA FASE dele (a mesma da linha "Fase"
            # da tabela de campos abaixo e do mapa de frações): casar plano e
            # campos vira reconhecimento de cor, sem contar número de coluna.
            fills[_i_plano] = _cor_plano(base + r, tema)
        else:
            simples, subs_v, fills = ([""] * len(col_defs), [""] * 9,
                                      [None] * len(col_defs))
        for k, ((_nome, w), val, fill) in enumerate(zip(col_defs, simples, fills)):
            # A cor do plano pinta mesmo sem rótulo (a linha é do plano); as
            # demais só destacam célula com conteúdo.
            t.ret(x, yr, w, hlin, fill=fill if (val or k == _i_plano) else None)
            if val not in (None, ""):
                t.txt(x, yr, val, size=_FONTE_VAL_TABELA, align="c", w=w, h=hlin)
            x += w
        for sv in subs_v:
            t.ret(x, yr, larg_sub, hlin)
            if sv:
                t.txt(x, yr, sv, size=_FONTE_VAL_TABELA, align="c", w=larg_sub, h=hlin)
            x += larg_sub
    t.recorte_fim()
    t.moldura(x0, y0, W, hcab + n_rows * hlin)
    return y0 + hcab + n_rows * hlin + 4


def pagina_ficha_multi(c: canvas.Canvas, planos: list, sequencia: list | None = None,
                       rotulos: list | None = None, replan: int = 0,
                       dose_replan: float = 0, base: int = 0,
                       obs: str | None = None, numeros: list | None = None,
                       ultima: int | None = None, grupos_dose: list | None = None,
                       acc_ini: list | None = None) -> bool:
    """Página 2 com os planos recebidos: tabela do plano (1 linha por plano)
    + tabela de campos concatenada (Fase = nº do plano, colorida por plano).

    Em tratamentos curtos (mapa com ≤ ``_MAX_FRAC_EMBUTIR`` frações, e desde que
    ele caiba sem espremer as linhas) o mapa de frações entra aqui como faixa
    horizontal e Observações/Checklist encolhem; devolve ``True`` (o chamador não
    emite a página 3 separada).

    ``base``: nº do 1º plano desta página dentro do caso (0-based). Quando os
    campos de todos os planos não cabem nas ``N_CAMPOS`` colunas, a ficha sai em
    várias páginas 2 (ver ``_grupos_por_campos``) e ``base`` mantém Fase e cores
    numeradas pelo caso, não pela página. ``obs``: texto das Observações (é do
    CASO, então o chamador passa o mesmo em todas as páginas)."""
    W, H = landscape(A4)
    t = Tela(c, W, H)
    # ``planos`` já chega ordenado por número do plano (ver gerar_ficha_multiplano).
    dados0 = planos[0]["dados"] if planos else {}
    tema = tema_da_maquina(dados0.get("maquina"))
    y = _cabecalho(t, dados0)
    y = _tabela_plano_multi(t, y, planos, base, tema)
    combinado = []
    for i, p in enumerate(planos):
        for f in p["store"].get("RP", {}).get("feixes", []):
            g = dict(f); g["fase"] = base + i + 1; g["_plano"] = base + i
            combinado.append(g)

    def _cor_fase(col):
        return (_cor_plano(combinado[col]["_plano"], tema)
                if col < len(combinado) else None)

    linhas = linhas_campos([p["store"].get("RP", {}) for p in planos])
    y_campos = y
    y = _tabela_campos(t, y, combinado, cor_fase=_cor_fase, tema=tema,
                       linhas=linhas)
    n_linhas = replan + len(sequencia or [])
    if obs is None:
        obs = _obs_dos_planos(planos, rotulos)
    rot = rotulos or [f"Plano {base + i + 1}" for i in range(len(planos))]
    if bool(sequencia) and _lado_a_lado(t, combinado, y, n_linhas, H):
        _mapa_ao_lado(t, y_campos, y, combinado, linhas, obs, tema)
        y += 13
        _grade_fracoes_multi(t, planos, sequencia, rot, y, replan, dose_replan,
                             (H - _MARGEM_INFERIOR) - y, base=base,
                             numeros=numeros, ultima=ultima,
                             grupos_dose=grupos_dose, acc_ini=acc_ini,
                             tema=tema)
        return True
    embutir = (bool(sequencia) and n_linhas <= _MAX_FRAC_EMBUTIR
               and _cabe_mapa_embutido(y, n_linhas, H))
    if embutir:
        _observacoes(t, y, altura_bloco=_ALTURA_OBS_COMPACTA, texto=obs)
        y += _ALTURA_OBS_COMPACTA + 4
        t.txt(14, y, "Mapa de frações", font="Helvetica-Bold", size=10)
        y += 13
        _grade_fracoes_multi(t, planos, sequencia, rot, y, replan, dose_replan,
                             (H - _MARGEM_INFERIOR) - y, base=base,
                             numeros=numeros, ultima=ultima,
                             grupos_dose=grupos_dose, acc_ini=acc_ini,
                             tema=tema)
    else:
        _observacoes(t, y, texto=obs)
    return embutir


def _grupos_por_campos(planos: list, max_campos: int = N_CAMPOS) -> list[list[int]]:
    """Divide os planos em grupos cujos campos SOMADOS cabem na tabela da pág. 2.

    A tabela de campos tem ``N_CAMPOS`` colunas; passando disso a grade estoura a
    folha. Enche cada grupo com o máximo de planos INTEIROS que couber — nenhum
    plano é partido entre duas páginas —, e o que não couber vai para a página 2
    seguinte (com a sua própria página 3). Um plano que sozinho já passa do
    limite ocupa uma página só dele (aí a tabela transborda, mas não há como
    dividi-lo sem separar campos do mesmo plano).

    Returns:
        Lista de grupos, cada um com os índices (em ``planos``) daquela página.
    """
    grupos: list[list[int]] = []
    atual: list[int] = []
    soma = 0
    for i, p in enumerate(planos):
        n = len(p["store"].get("RP", {}).get("feixes", []) or [])
        if atual and soma + n > max_campos:
            grupos.append(atual)
            atual, soma = [], 0
        atual.append(i)
        soma += n
    if atual:
        grupos.append(atual)
    return grupos


def _dose_por_plano(planos: list, sequencia: list) -> list[float]:
    """Dose total (cGy) que cada plano entrega no mapa: dose/dia × nº de frações
    dele no agendamento."""
    dia = [float((p["dados"].get("rx_dose_fracao")
                  or p["store"].get("RP", {}).get("dose_fracao") or 0)) * 100
           for p in planos]
    n = [0] * len(planos)
    for linha in (sequencia or []):
        for p in linha:
            if 0 <= p < len(planos):
                n[p] += 1
    return [d * k for d, k in zip(dia, n)]


def _grupos_dose_do_bloco(grupos_dose: list | None, bloco: list,
                          dose_plano: list) -> tuple[list | None, list | None]:
    """Traduz os grupos de soma de dose para os planos de UM bloco de páginas.

    Índices viram locais ao bloco e cada grupo leva a dose que os seus planos já
    entregaram em blocos anteriores — assim a coluna Dose continua de onde parou
    quando a ficha é partida em várias páginas 2/3.
    """
    if not grupos_dose:
        return None, None
    pos = {p: k for k, p in enumerate(bloco)}
    inicio = bloco[0]
    gd: list = []
    acc: list = []
    for g in grupos_dose:
        locais = [pos[p] for p in g if p in pos]
        if not locais:
            continue
        gd.append(locais)
        acc.append(sum(dose_plano[p] for p in g
                       if p not in pos and 0 <= p < inicio))
    return gd, acc


def _sequencia_do_grupo(sequencia: list, grupo: list) -> tuple[list, list]:
    """Mapa de frações restrito aos planos de ``grupo`` (ficha em várias págs. 2).

    Mantém só os dias em que algum plano do grupo é tratado e renumera os índices
    para a posição DENTRO do grupo. Devolve também o nº global de cada fração
    mantida (1-based na sequência inteira), para a coluna "Fração" seguir a
    numeração do tratamento em vez de recomeçar em 1 a cada página.
    """
    pos = {g: k for k, g in enumerate(grupo)}
    seq: list = []
    numeros: list = []
    for d, dia in enumerate(sequencia or []):
        linha = [pos[i] for i in dia if i in pos]
        if linha:
            seq.append(linha)
            numeros.append(d + 1)
    return seq, numeros


# ---------------------------------------------------------------------------
# Página 3 — Mapa de frações
# ---------------------------------------------------------------------------


def tempo_fracao(isos_no_dia: int, primeiro_dia: bool) -> int:
    """Tempo (min) de uma fração: 24 min por isocentro tratado no 1º dia, 12 min
    nos demais. Planos sequenciais não somam — só os que caem no mesmo dia."""
    return int(isos_no_dia) * (24 if primeiro_dia else 12)


def total_linhas_fracoes(dados: dict, store: dict, replan: int = 0) -> int:
    """Nº de linhas do mapa de frações (plano único) = replan + prescrição."""
    nfr = int(dados.get("rx_fracoes") or store.get("RP", {}).get("num_fracoes") or 0)
    return (max(0, int(replan or 0)) + nfr) if nfr else 20


def texto_replanejamento(replan: int, dose_replan: float) -> str:
    """O que a faixa das frações já tratadas diz na coluna Observações.

    O rótulo era só a palavra "REPLANEJAMENTO", centrada nas sub-colunas de
    campo: com dois campos essa faixa tem ~34 pt e a palavra pede o triplo, de
    modo que ela saía por cima de Imagem e das Observações — medido no PDF em
    23/09/2026, ilegível. Aqui vai o dado inteiro, na coluna mais larga da
    grade: quem confere na sala precisa saber QUANTAS frações e a QUE dose,
    que é o que justifica a folha começar na fração 6.
    """
    plural = "frações já tratadas" if replan != 1 else "fração já tratada"
    if dose_replan:
        return (f"REPLANEJAMENTO — {replan} {plural} × {br(dose_replan)} cGy "
                f"= {br(replan * dose_replan)} cGy")
    return f"REPLANEJAMENTO — {replan} {plural}"


# Geometria da PÁGINA PRÓPRIA do mapa: topo do cabeçalho (logo + paciente) e topo
# da grade. Os 26 pt entre os dois são o cabeçalho mais o respiro até a tabela.
_Y_CAB_MAPA = 14.0
_Y0_MAPA = 40.0


def _faixa_mapa_centrado(total_linhas: int, H: float) -> tuple[float, float]:
    """``(y0, altura)`` da grade do mapa na PÁGINA PRÓPRIA, centralizada na vertical.

    A linha da grade não estica (``_HLIN_MAPA`` é teto, não alvo), então um
    tratamento curto que não coubesse na pág. 2 saía com a grade pendurada no
    topo e meia folha em branco embaixo. A sobra passa a ser dividida igualmente
    acima e abaixo. Grade que já ocupa a faixa inteira (muitas frações, linha
    comprimida) não sai do lugar: a sobra é zero.

    Quem desce é o BLOCO todo — ver ``_cabecalho_mapa``.
    """
    faixa = H - _MARGEM_INFERIOR - _Y0_MAPA
    alt = min(_HCAB_MAPA + max(int(total_linhas), 1) * _HLIN_MAPA, faixa)
    return _Y0_MAPA + (faixa - alt) / 2, alt


# x de origem de "Nome:", "RGH:" e "Data de Nascimento:" na linha do paciente
# da página própria do mapa, medidos a partir da margem. São PISOS, não posições
# fixas: ver ``_linha_paciente``.
_X_CAB_MAPA = (100.0, 352.0, 468.0)
_TAM_CAB_MAPA = 10.0        # corpo cheio da linha
_TAM_CAB_MAPA_MIN = 7.0     # até onde ela encolhe antes de aparar o nome


def _linha_paciente(t: Tela, y: float, pares: list[tuple[str, str]],
                    x_min: tuple[float, ...], x0: float, x_fim: float) -> None:
    """Escreve os pares rótulo+valor numa linha só, sem um passar por cima do outro.

    Os ``x_min`` são os do modelo e valem enquanto couberem; um valor mais largo
    que a sua vaga EMPURRA os pares seguintes para a direita, em vez de ser
    escrito por baixo deles. Se a linha inteira estourar a margem, o corpo cai
    junto até ``_TAM_CAB_MAPA_MIN`` e, só então, o nome é aparado com reticências
    — nome de paciente é o último a ceder.
    """
    c = t.c
    pad = 3.0        # o recuo que ``Tela.txt`` aplica no drawString
    gap = 12.0       # respiro entre um par e o próximo

    def medir(tam: float, textos: list[str]) -> tuple[list[tuple[float, float]], float]:
        xs, x = [], x0
        for i, (rot, val) in enumerate(zip((p[0] for p in pares), textos)):
            x = max(x, x_min[i])
            xr = x
            x += pad + c.stringWidth(rot, "Helvetica-Bold", tam) + 5
            xv = x
            x += pad + c.stringWidth(val, "Helvetica", tam) + gap
            xs.append((xr, xv))
        return xs, x - gap

    textos = [str(v or "") for _, v in pares]
    tam = _TAM_CAB_MAPA
    while True:
        xs, fim = medir(tam, textos)
        if fim <= x_fim or tam <= _TAM_CAB_MAPA_MIN:
            break
        tam -= 0.25
    # Piso alcançado e ainda estoura (nome absurdamente longo): apara o nome.
    while fim > x_fim and len(textos[0]) > 4:
        textos[0] = textos[0][:-2] + "…"
        xs, fim = medir(tam, textos)

    for (xr, xv), (rot, _), val in zip(xs, pares, textos):
        t.txt(xr, y, rot, font="Helvetica-Bold", size=tam, h=18)
        t.txt(xv, y, val, size=tam, h=18)


def _cabecalho_mapa(t: Tela, dados: dict, y0: float) -> None:
    """Logo e dados do paciente da PÁGINA PRÓPRIA do mapa, colados acima da grade.

    Descem junto com a grade quando ela é centralizada: o que se move é o bloco
    inteiro. Sozinho no topo, o cabeçalho deixava um vão no meio da folha.
    """
    M = 14
    d = y0 - _Y0_MAPA          # o quanto a grade desceu
    _logo(t.c, M, t.H - 36 - d, 68, 22, maquina=dados.get("maquina"))
    _linha_paciente(
        t, _Y_CAB_MAPA + d,
        [("Nome:", dados.get("pac_nome", "")),
         ("RGH:", dados.get("pac_registro", "")),
         ("Data de Nascimento:", dados.get("pac_nascimento", ""))],
        x_min=tuple(M + x for x in _X_CAB_MAPA), x0=M + _X_CAB_MAPA[0],
        x_fim=t.W - M)


def pagina_fracoes(c: canvas.Canvas, dados: dict, store: dict,
                   replan: int = 0, dose_replan: float = 0):
    """Mapa de frações (plano único) em página própria. ``replan``: nº de frações
    já tratadas no plano anterior — saem RASURADAS da Data até os campos, com a
    dose anterior acumulada (``dose_replan`` cGy/fração) na coluna Dose e o
    rótulo do replanejamento nas Observações da primeira delas; o plano começa
    depois da faixa."""
    W, H = landscape(A4)
    t = Tela(c, W, H)
    y0, alt = _faixa_mapa_centrado(total_linhas_fracoes(dados, store, replan), H)
    _cabecalho_mapa(t, dados, y0)
    _grade_fracoes(t, dados, store, y0, replan, dose_replan, alt,
                   tema=tema_da_maquina(dados.get("maquina")))


def _grade_fracoes(t: Tela, dados: dict, store: dict, y0: float,
                   replan: int, dose_replan: float, altura: float,
                   hlin_max: float = _HLIN_MAPA,
                   tema: Tema = TEMA_CLINICA) -> float:
    """Desenha a grade do mapa de frações a partir de ``y0`` dentro de ``altura``
    (pt) e devolve o y do fim. ``hlin_max`` limita a altura da linha (a mesma na
    página própria e no embute): a grade nunca estica, e só encolhe acima de
    ``_MAX_LINHAS_MAPA`` linhas."""
    c = t.c
    W = t.W
    M = 14
    rp = store.get("RP", {})
    nfr = int(dados.get("rx_fracoes") or rp.get("num_fracoes") or 0)
    dose_dia = float((dados.get("rx_dose_fracao") or rp.get("dose_fracao") or 0)) * 100
    n_campos_ativo = max(len(rp.get("feixes", [])), 1)

    W_util = W - 2 * M
    col_fracao, col_data, col_hora, col_t, col_tec, col_img = 30, 56, 36, 30, 84, 46
    col_tec_sub = col_tec // 2   # 42 pt por sub-coluna de Técnicos
    col_med, col_dose = 50, 60
    # Só as sub-colunas de campo que EXISTEM (uma por feixe) — sem bloco cinza de
    # colunas vazias. A largura da sub-coluna é a mesma da folha cheia (N_CAMPOS);
    # a Observações absorve o espaço que sobra (mais área p/ anotar).
    n_sub = n_campos_ativo
    larg_fixa = col_fracao + col_data + col_hora + col_t + col_tec + col_img
    larg_sub = (W_util - larg_fixa - 155 - col_med - col_dose) / N_CAMPOS
    col_obs = W_util - larg_fixa - n_sub * larg_sub - col_med - col_dose
    # Muitos feixes (n_sub > N_CAMPOS): manter a largura da folha cheia empurraria
    # a Observações para largura negativa e a grade estouraria a página. Aí encolhe
    # as sub-colunas para caber, preservando um mínimo de Observações.
    if col_obs < 60:
        larg_sub = max((W_util - larg_fixa - 60 - col_med - col_dose) / max(n_sub, 1), 8)
        col_obs = W_util - larg_fixa - n_sub * larg_sub - col_med - col_dose
    # Sub-coluna direita de Imagem: mesma largura de 1-1 / 1-2
    col_img_dir = larg_sub
    col_img_esq = col_img - col_img_dir   # sub-coluna esquerda (tipo: CBCT etc.)
    imagem_texto = dados.get("proto_imagem", "")
    col_img_esq, col_obs = _alargar_imagem(
        c, [imagem_texto, _FIM_TTO], col_img_esq, col_obs)
    col_img = col_img_dir + col_img_esq
    tam_img = _tam_uniforme(c, [imagem_texto, _FIM_TTO], col_img_esq)
    hh = _HCAB_MAPA
    # Nº de linhas e altura da linha ANTES do cabeçalho — para recortar a grade
    # inteira no retângulo arredondado (cantos perfeitos).
    replan = max(0, int(replan or 0))
    total_linhas = (replan + nfr) if nfr else 20
    hlin = min((altura - hh) / total_linhas, hlin_max)
    # Todas as doses no MESMO corpo, dimensionado pela maior (a última, com mais
    # dígitos) — senão cada célula encolhia por conta e a coluna saía escadinha.
    tam_dose = _tam_uniforme(c, [br(dose_replan * replan) if dose_replan else "",
                                 br(replan * dose_replan + dose_dia * nfr)
                                 if dose_dia else ""], col_dose)
    t.recorte_ini(M, y0, W - 2 * M, hh + total_linhas * hlin)
    # Cabeçalho: célula única por coluna (sem divisor interno em Técnicos/Imagem)
    cabs = [("Fração", col_fracao), ("Data", col_data), ("Horário", col_hora),
            ("T (min)", col_t), ("Técnicos", col_tec), ("Imagem", col_img)]
    x = M
    for nome, w in cabs:
        t.ret(x, y0, w, hh, fill=white)
        t.txt(x, y0, nome, font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c", w=w, h=hh)
        x += w
    feixes = rp.get("feixes", [])
    for j in range(n_sub):
        fill = _cor_iso(feixes, j, tema) if j < n_campos_ativo else CINZA
        t.ret(x, y0, larg_sub, hh, fill=fill)
        if j < len(feixes):
            fase_num = feixes[j].get("fase", 1)
            t.txt(x, y0, f"{fase_num}-{j + 1}", size=_FONTE_VAL_TABELA, align="c", w=larg_sub, h=hh)
        x += larg_sub
    t.ret(x, y0, col_obs, hh, fill=white)
    t.txt(x, y0, "Observações", font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c",
          w=col_obs, h=hh)
    x += col_obs
    t.ret(x, y0, col_med, hh, fill=white)
    t.txt(x, y0, "Med/Enf", font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c",
          w=col_med, h=hh)
    x += col_med
    t.ret(x, y0, col_dose, hh, fill=white)
    t.txt(x, y0, "Dose", font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c", w=col_dose, h=hh)

    n_isos   = int(rp.get("n_isocentros") or 1)
    t_min_d1 = tempo_fracao(n_isos, True)   # 1º dia: 24 min por isocentro
    t_min_dn = tempo_fracao(n_isos, False)  # demais dias: 12 min por isocentro

    imagem_texto = dados.get("proto_imagem", "")
    frequencia   = dados.get("proto_frequencia", "")
    dias_img     = {int(x) for x in (dados.get("proto_imagem_dias") or [])}

    def _tem_imagem(i: int) -> bool:
        return frac_tem_imagem(i, imagem_texto, frequencia, dias_img)

    # Replanejamento: as 'replan' primeiras linhas são do plano anterior (já
    # tratadas); o plano só começa em frac_idx = i - replan. (replan/total_linhas/
    # hlin já calculados acima, antes do recorte.)
    for i in range(total_linhas):
        yr = y0 + hh + i * hlin
        x = M
        rasurada = i < replan
        frac_idx = i - replan
        ativo = 0 <= frac_idx < nfr
        t.ret(x, yr, col_fracao, hlin)
        t.txt(x, yr, i + 1, size=_FONTE_VAL_TABELA, align="c", w=col_fracao, h=hlin)
        x += col_fracao
        x_rasura0 = x          # a rasura da fração já tratada começa na Data
        for w in (col_data, col_hora):
            t.ret(x, yr, w, hlin)
            x += w
        # T(min): primeiro dia com AMARELO, demais dias sem fill
        if ativo:
            t_val  = t_min_d1 if frac_idx == 0 else t_min_dn
            t_fill = AMARELO  if frac_idx == 0 else None
            t.ret(x, yr, col_t, hlin, fill=t_fill)
            t.txt(x, yr, str(t_val), font="Helvetica-Bold", size=_FONTE_VAL_TABELA,
                  align="c", w=col_t, h=hlin)
        else:
            t.ret(x, yr, col_t, hlin)
        x += col_t
        # Técnicos: 2 sub-colunas (a rasura da linha inteira vem depois dos
        # campos, quando o x já chegou ao fim da faixa a rasurar)
        t.ret(x, yr, col_tec_sub, hlin)
        t.ret(x + col_tec_sub, yr, col_tec_sub, hlin)
        x += col_tec
        # Imagem: quadrado vazio (largura de 1 campo) à ESQUERDA p/ o técnico
        #         marcar; texto (CBCT/Final Tto.) na célula mais larga à DIREITA
        #         — mesmo layout do mapa combinado (multi-plano).
        texto_img = None
        if ativo:
            if frac_idx == nfr - 1:
                texto_img = _FIM_TTO
            elif _tem_imagem(frac_idx):
                texto_img = imagem_texto
        t.ret(x, yr, col_img_dir, hlin)                # vazio à esquerda (estreito)
        t.ret(x + col_img_dir, yr, col_img_esq, hlin)  # texto à direita (largo)
        if texto_img:
            t.txt(x + col_img_dir, yr, texto_img, size=tam_img, align="c",
                  w=col_img_esq, h=hlin)
        x += col_img
        # Sub-colunas: brancas (ativas) para o técnico marcar; cinza nas demais
        for j in range(n_sub):
            fill = (None if j < n_campos_ativo else CINZA) if ativo else CINZA
            t.ret(x, yr, larg_sub, hlin, fill=fill)
            x += larg_sub
        # Rasura da fração já tratada: uma diagonal só, da Data até o fim dos
        # campos. Antes ela cobria apenas as duas células de Técnicos, e Data,
        # Horário, T(min) e Imagem ficavam brancas e abertas numa fração que já
        # foi tratada — convite a preencher a linha do plano que acabou.
        if rasurada:
            c.setStrokeColor(black); c.setLineWidth(1)
            c.line(x_rasura0, t.H - (yr + hlin), x, t.H - yr)
        t.ret(x, yr, col_obs, hlin)
        # O rótulo vai na PRIMEIRA linha da faixa, que é por onde o olho entra
        # na tabela (ver ``texto_replanejamento``).
        if rasurada and i == 0:
            t.txt(x, yr, texto_replanejamento(replan, dose_replan),
                  font="Helvetica-Bold", size=_FONTE_VAL_TABELA, w=col_obs,
                  h=hlin, color=tema.forte)
        x += col_obs
        t.ret(x, yr, col_med, hlin)
        x += col_med
        # Dose cumulativa (CONTINUAÇÃO): nas rasuradas é só a dose já tratada; a
        # partir do plano atual soma-se essa dose anterior à do plano (dose total).
        dose_anterior = replan * dose_replan
        if rasurada:
            t.ret(x, yr, col_dose, hlin, fill=CINZA)
            if dose_replan:
                t.txt(x, yr, br(dose_replan * (i + 1)), size=tam_dose,
                      align="c", w=col_dose, h=hlin)
        elif ativo and dose_dia:
            t.ret(x, yr, col_dose, hlin, fill=_cor_iso(feixes, 0, tema))
            t.txt(x, yr, br(dose_anterior + dose_dia * (frac_idx + 1)),
                  size=tam_dose, align="c", w=col_dose, h=hlin)
        else:
            t.ret(x, yr, col_dose, hlin)
    t.recorte_fim()
    t.moldura(M, y0, W - 2 * M, hh + total_linhas * hlin)
    return y0 + hh + total_linhas * hlin


_FIM_TTO = "Final Tto."     # rótulo da última fração na coluna Imagem
_TAM_ALVO_IMG = 8           # corpo mínimo desejado para CBCT / Final Tto.


def _alargar_imagem(c, textos, col_img_esq: float, col_obs: float,
                    col_obs_min: float = 60) -> tuple[float, float]:
    """Alarga a célula de texto da coluna Imagem até os rótulos caberem em
    ``_TAM_ALVO_IMG``, descontando da Observações (que sobra larga na grade).

    Sem isso, "Final Tto." encolhia sozinho até quase o piso e saía com metade
    do corpo do "CBCT" da linha de cima. Devolve ``(col_img_esq, col_obs)``, e
    a Observações nunca cai abaixo de ``col_obs_min``.
    """
    precisa = max((c.stringWidth(str(s), "Helvetica", _TAM_ALVO_IMG)
                   for s in textos if str(s)), default=0.0) + _PAD_CELULA
    extra = min(max(0.0, precisa - col_img_esq), max(0.0, col_obs - col_obs_min))
    return col_img_esq + extra, col_obs - extra


# Paleta de cores por plano (mapa de frações combinado). O 1º plano leva a cor de
# MARCA da unidade (``None`` aqui = "usa o tema"); os demais só precisam ser
# distinguíveis entre si e entre unidades.
# O 1º plano era LARANJA (#F4B183) — o outro laranja da folha, que sobrou
# quando troquei só a cor do isocentro. Este é o verde-água do logo da Clinica
# clareado: o plano 1 passa a ser a cor da casa, e os outros três continuam
# distinguíveis entre si por matiz.
_CORES_PLANO = [None, HexColor("#8ED9D5"), HexColor("#9DC3E6"),
                HexColor("#C5E0B4"), HexColor("#D9B3FF")]


def _cor_plano(idx: int, tema: Tema = TEMA_CLINICA):
    return _CORES_PLANO[idx % len(_CORES_PLANO)] or tema.forte


def pagina_fracoes_agendada(c: canvas.Canvas, planos: list, sequencia: list,
                            rotulos: list):
    """Mapa de frações COMBINADO: cada fração indica o(s) plano(s) tratado(s).

    ``planos``: lista de ``{"dados","store"}`` (um por plano).
    ``sequencia``: ``sequencia[i]`` = lista de índices de planos na fração i+1.
    """
    W, H = landscape(A4)
    t = Tela(c, W, H)
    M = 14
    d0 = planos[0]["dados"] if planos else {}
    tema = tema_da_maquina(d0.get("maquina"))

    y0 = _Y0_MAPA
    _cabecalho_mapa(t, d0, y0)

    W_util = W - 2 * M
    col_fracao, col_data, col_hora, col_t, col_tec, col_img = 30, 52, 34, 28, 78, 44
    col_plano, col_obs, col_med, col_dose = 78, 116, 42, 54
    n_sub = N_CAMPOS
    larg_fixa = col_fracao + col_data + col_hora + col_t + col_tec + col_img
    larg_dir = col_plano + col_obs + col_med + col_dose
    larg_sub = (W_util - larg_fixa - larg_dir) / n_sub
    col_img_dir = larg_sub
    col_img_esq = col_img - col_img_dir
    hh = _HCAB_MAPA

    feixes_por = [p["store"].get("RP", {}).get("feixes", []) or [] for p in planos]
    dose_dia_por = [
        float((p["dados"].get("rx_dose_fracao")
               or p["store"].get("RP", {}).get("dose_fracao") or 0)) * 100
        for p in planos
    ]

    # Cabeçalho de colunas.
    cabs = [("Fração", col_fracao), ("Data", col_data), ("Horário", col_hora),
            ("T (min)", col_t), ("Técnicos", col_tec), ("Imagem", col_img)]
    x = M
    for nome, w in cabs:
        t.ret(x, y0, w, hh, fill=white)
        t.txt(x, y0, nome, font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c", w=w, h=hh)
        x += w
    for j in range(n_sub):
        t.ret(x, y0, larg_sub, hh, fill=white)
        t.txt(x, y0, str(j + 1), size=_FONTE_VAL_TABELA, align="c", w=larg_sub, h=hh)
        x += larg_sub
    for nome, w in (("Plano", col_plano), ("Observações", col_obs),
                    ("Med/Enf", col_med), ("Dose", col_dose)):
        t.ret(x, y0, w, hh, fill=white)
        t.txt(x, y0, nome, font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c", w=w, h=hh)
        x += w

    total = len(sequencia)
    total_linhas = max(_MAX_LINHAS_MAPA, total)   # linhas em branco até o fim
    hlin = min((H - _MARGEM_INFERIOR - (y0 + hh)) / total_linhas, _HLIN_MAPA)
    dose_acc = [0.0] * len(planos)

    for i in range(total_linhas):
        yr = y0 + hh + i * hlin
        x = M
        linha = sequencia[i] if i < total else []
        # Lista (plano, feixe) da fração, na ordem dos planos ativos.
        cols_feixe = [(p, k) for p in linha for k in range(len(feixes_por[p]))]

        t.ret(x, yr, col_fracao, hlin)
        t.txt(x, yr, i + 1, size=_FONTE_VAL_TABELA, align="c", w=col_fracao, h=hlin)
        x += col_fracao
        for w in (col_data, col_hora):
            t.ret(x, yr, w, hlin)
            x += w
        t.ret(x, yr, col_t, hlin, fill=(AMARELO if (linha and i == 0) else None))
        x += col_t
        t.ret(x, yr, col_tec // 2, hlin)
        t.ret(x + col_tec // 2, yr, col_tec // 2, hlin)
        x += col_tec
        t.ret(x, yr, col_img_esq, hlin)
        t.ret(x + col_img_esq, yr, col_img_dir, hlin)
        x += col_img
        # Sub-colunas de campo: coloridas por plano nos feixes ativos.
        for j in range(n_sub):
            fill = _cor_plano(cols_feixe[j][0], tema) if j < len(cols_feixe) else CINZA
            t.ret(x, yr, larg_sub, hlin, fill=fill)
            x += larg_sub
        # Plano.
        rot = " / ".join(rotulos[p] for p in linha) if linha else ""
        t.ret(x, yr, col_plano, hlin,
              fill=(_cor_plano(linha[0], tema) if len(linha) == 1 else None))
        t.txt(x, yr, rot[:14], size=7, align="c", w=col_plano, h=hlin)
        x += col_plano
        t.ret(x, yr, col_obs, hlin)
        x += col_obs
        t.ret(x, yr, col_med, hlin)
        x += col_med
        # Dose do dia = soma das doses dos planos da fração; acumulada por plano.
        dose_dia = sum(dose_dia_por[p] for p in linha)
        for p in linha:
            dose_acc[p] += dose_dia_por[p]
        if linha and dose_dia:
            t.ret(x, yr, col_dose, hlin, fill=_cor_plano(linha[0], tema))
            t.txt(x, yr, br(sum(dose_acc[p] for p in linha)),
                  size=_FONTE_VAL_TABELA, align="c", w=col_dose, h=hlin)
        else:
            t.ret(x, yr, col_dose, hlin)


def pagina_fracoes_multi(c: canvas.Canvas, planos: list, sequencia: list,
                         rotulos: list, replan: int = 0, dose_replan: float = 0,
                         base: int = 0, numeros: list | None = None,
                         ultima: int | None = None,
                         grupos_dose: list | None = None,
                         acc_ini: list | None = None):
    """Mapa de frações combinado no FORMATO CLÁSSICO (igual pagina_fracoes):
    sub-colunas de campo por plano (rótulo fase-campo ``p-c``), T(min)/Imagem
    preenchidos e Dose acumulada POR PLANO. A ``sequencia`` (agendamento) diz
    quais planos entram em cada fração.

    ``replan`` (replanejamento): nº de frações já tratadas no plano anterior. Essas
    primeiras linhas saem RASURADAS na coluna de assinatura (Técnicos), com a dose
    anterior acumulada (``dose_replan`` cGy/fração) registrada na coluna Dose e o
    rótulo do replanejamento nas Observações da primeira linha rasurada; o
    fracionamento do plano só
    começa depois delas."""
    W, H = landscape(A4)
    t = Tela(c, W, H)
    d0 = planos[0]["dados"] if planos else {}
    # Mesmo nº de linhas que ``_grade_fracoes_multi`` calcula lá dentro.
    y0, alt = _faixa_mapa_centrado(
        max(0, int(replan or 0)) + len(sequencia or []), H)
    _cabecalho_mapa(t, d0, y0)
    _grade_fracoes_multi(t, planos, sequencia, rotulos, y0, replan, dose_replan,
                         alt, base=base, numeros=numeros, ultima=ultima,
                         grupos_dose=grupos_dose, acc_ini=acc_ini,
                         tema=tema_da_maquina(d0.get("maquina")))


def _acumuladores_de_dose(n_planos: int, grupos_dose: list | None,
                          acc_ini: list | None, replan: int,
                          dose_replan: float) -> tuple[list, list]:
    """Grupos de acúmulo da coluna Dose (pág. 3) e o valor inicial de cada um.

    Planos da MESMA região tratados em sequência (fase → boost) somam a dose num
    total contínuo; planos de outra região acumulam por conta própria. Quem diz
    o que soma com o que é ``grupos_dose`` (listas de índices de plano); todo
    plano fora dele vira um grupo só seu — o comportamento de sempre.

    No replanejamento a dose já é um total único e contínuo do tratamento
    inteiro (a dose anterior + tudo o que vier), então ele manda: um grupo com
    todos os planos, partindo das frações já tratadas.

    ``acc_ini``: dose (cGy) que cada grupo já acumulou em páginas anteriores —
    na ficha partida em vários blocos (``_grupos_por_campos``) a contagem não
    recomeça do zero na página seguinte.
    """
    if replan > 0:
        return [list(range(n_planos))], [replan * dose_replan]
    grupos: list[list[int]] = []
    vistos: set = set()
    for g in (grupos_dose or []):
        membros = [p for p in g if 0 <= p < n_planos and p not in vistos]
        if membros:
            grupos.append(membros)
            vistos.update(membros)
    ini = list(acc_ini or [])
    ini = [(ini[i] if i < len(ini) else 0.0) for i in range(len(grupos))]
    for p in range(n_planos):        # planos avulsos: cada um no seu grupo
        if p not in vistos:
            grupos.append([p])
            ini.append(0.0)
    return grupos, ini


def _grade_fracoes_multi(t: Tela, planos: list, sequencia: list, rotulos: list,
                         y0: float, replan: int, dose_replan: float,
                         altura: float, hlin_max: float = _HLIN_MAPA,
                         base: int = 0, numeros: list | None = None,
                         ultima: int | None = None,
                         grupos_dose: list | None = None,
                         acc_ini: list | None = None,
                         tema: Tema = TEMA_CLINICA) -> float:
    """Núcleo da grade do mapa de frações combinado; desenha a partir de ``y0``
    em ``altura`` pt e devolve o y do fim. ``hlin_max`` limita a altura da linha
    (a mesma na página própria e no embute): nunca estica, e só encolhe acima de
    ``_MAX_LINHAS_MAPA`` linhas.

    ``base``, ``numeros`` e ``ultima`` só entram na ficha partida em várias
    páginas 2/3 (``_grupos_por_campos``): ``base`` é o nº do 1º plano do grupo no
    caso (cor e rótulo ``fase-campo``), ``numeros`` traz o nº GLOBAL de cada
    fração desenhada (a coluna "Fração" não recomeça em 1 na página seguinte) e
    ``ultima`` é o nº da última fração do tratamento — só nela sai "Final Tto.".
    ``grupos_dose``/``acc_ini``: ver ``_acumuladores_de_dose``.
    """
    c = t.c
    W = t.W
    M = 14
    n_planos = len(planos)

    feixes_por = [p["store"].get("RP", {}).get("feixes", []) or [] for p in planos]
    # (plano_idx, campo_local_idx) por sub-coluna de campo, na ordem dos planos.
    combinado = [(pi, ci) for pi, fx in enumerate(feixes_por) for ci in range(len(fx))]
    n_campos_ativo = len(combinado)
    dose_dia_por = [
        float((p["dados"].get("rx_dose_fracao")
               or p["store"].get("RP", {}).get("dose_fracao") or 0)) * 100
        for p in planos
    ]
    grupos_d, dose_acc = _acumuladores_de_dose(n_planos, grupos_dose, acc_ini,
                                               replan, dose_replan)
    grupo_de = {p: gi for gi, g in enumerate(grupos_d) for p in g}

    W_util = W - 2 * M
    col_fracao, col_data, col_hora, col_t, col_tec, col_img = 30, 56, 36, 30, 84, 46
    col_med = 46
    col_dose_p = max(28, 60 // max(n_planos, 1))   # largura por plano na Dose
    col_dose = col_dose_p * max(n_planos, 1)
    # Só as sub-colunas de campo que EXISTEM (soma dos feixes dos planos); largura
    # igual à da folha cheia (N_CAMPOS) e a Observações absorve o que sobra.
    n_sub = max(n_campos_ativo, 1)
    larg_fixa = col_fracao + col_data + col_hora + col_t + col_tec + col_img
    larg_sub = (W_util - larg_fixa - 150 - col_med - col_dose) / N_CAMPOS
    col_obs = W_util - larg_fixa - n_sub * larg_sub - col_med - col_dose
    # Muitos feixes somados (n_sub > N_CAMPOS): encolhe as sub-colunas para caber,
    # senão a Observações fica negativa e a grade estoura a página.
    if col_obs < 60:
        larg_sub = max((W_util - larg_fixa - 60 - col_med - col_dose) / max(n_sub, 1), 8)
        col_obs = W_util - larg_fixa - n_sub * larg_sub - col_med - col_dose
    col_img_dir = larg_sub
    col_img_esq = col_img - col_img_dir
    hh = _HCAB_MAPA
    # Nº de linhas / altura da linha ANTES do cabeçalho — para recortar a grade
    # inteira no retângulo arredondado.
    total = len(sequencia)
    replan = max(0, int(replan or 0))
    total_linhas = max(replan + total, 1)
    hlin = min((altura - hh) / total_linhas, hlin_max)

    # Rótulos da Imagem (um por plano) e doses: corpo ÚNICO em cada grupo, senão
    # "Final Tto." e "1800,0" saem menores que "CBCT" e "500,0" da linha vizinha.
    _txt_img = [p["dados"].get("proto_imagem", "") for p in planos] + [_FIM_TTO]
    col_img_esq, col_obs = _alargar_imagem(c, _txt_img, col_img_esq, col_obs)
    col_img = col_img_dir + col_img_esq
    tam_img = _tam_uniforme(c, _txt_img, col_img_esq)
    # Maior dose impressa: o acumulado de cada GRUPO de dose ao fim do
    # tratamento (sem grupos, cada plano é um; com replan, um total contínuo).
    _tot_plano = [sum(dose_dia_por[pi] for dia in sequencia if pi in dia)
                  for pi in range(n_planos)]
    _doses = [br(replan * dose_replan)] if (replan and dose_replan) else []
    _doses += [br(dose_acc[gi] + sum(_tot_plano[p] for p in g))
               for gi, g in enumerate(grupos_d)]
    tam_dose = _tam_uniforme(c, _doses, col_dose_p)

    t.recorte_ini(M, y0, W - 2 * M, hh + total_linhas * hlin)

    cabs = [("Fração", col_fracao), ("Data", col_data), ("Horário", col_hora),
            ("T (min)", col_t), ("Técnicos", col_tec), ("Imagem", col_img)]
    x = M
    for nome, w in cabs:
        t.ret(x, y0, w, hh, fill=white)
        t.txt(x, y0, nome, font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c", w=w, h=hh)
        x += w
    for j in range(n_sub):
        if j < n_campos_ativo:
            pi, ci = combinado[j]
            t.ret(x, y0, larg_sub, hh, fill=_cor_plano(base + pi, tema))
            t.txt(x, y0, f"{base + pi + 1}-{ci + 1}", size=_FONTE_VAL_TABELA,
                  align="c", w=larg_sub, h=hh)
        else:
            t.ret(x, y0, larg_sub, hh, fill=CINZA)
        x += larg_sub
    for nome, w in (("Observações", col_obs), ("Med/Enf", col_med)):
        t.ret(x, y0, w, hh, fill=white)
        t.txt(x, y0, nome, font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c", w=w, h=hh)
        x += w
    t.ret(x, y0, col_dose, hh, fill=white)
    t.txt(x, y0, "Dose", font="Helvetica-Bold", size=_FONTE_CAB_TABELA, align="c", w=col_dose, h=hh)
    x_dose0 = x

    # Tempo por dia = (isocentros dos planos tratados NAQUELE dia) × 24 no 1º dia
    # e × 12 nos demais. Planos sequenciais não somam (cada dia trata um plano);
    # só somam quando vários planos caem no mesmo dia (simultâneo).
    n_iso_plano = [int(p["store"].get("RP", {}).get("n_isocentros") or 1)
                   for p in planos]

    def _t_min(i: int, linha: list) -> int:
        isos = sum(n_iso_plano[p] for p in linha if 0 <= p < len(n_iso_plano))
        return tempo_fracao(isos, i == 0)

    # Imagem de cada fração pelo protocolo do PLANO tratado nela (ver
    # ``imagem_por_fracao``): a fase e o boost têm modalidade, frequência e dias
    # personalizados próprios.
    imagens = imagem_por_fracao(
        [(p["dados"].get("proto_imagem", ""),
          p["dados"].get("proto_frequencia", ""),
          {int(v) for v in (p["dados"].get("proto_imagem_dias") or [])})
         for p in planos],
        sequencia)

    # (total/replan/total_linhas/hlin já calculados acima, antes do recorte.)
    # Dose: cada GRUPO de dose (``grupos_d``) tem um acumulado só, escrito na
    # sub-coluna do plano tratado no dia. Planos da mesma região declarados
    # juntos somam num total contínuo (fase → boost); os demais acumulam
    # sozinhos. No replanejamento o grupo é um só, com todos os planos.
    for i in range(total_linhas):
        yr = y0 + hh + i * hlin
        x = M
        # Replanejamento: as 'replan' primeiras linhas são do plano anterior (já
        # tratadas) — o mapa deste plano só começa em seq_idx = i - replan.
        rasurada = i < replan
        seq_idx = i - replan
        linha = sequencia[seq_idx] if 0 <= seq_idx < total else []
        ativa = bool(linha)
        planos_ativos = set(linha)
        # Nº da fração NO TRATAMENTO (não na página): na ficha partida em vários
        # grupos de planos, a pág. 3 do 2º grupo continua a numeração da do 1º.
        num_g = (numeros[seq_idx] if (numeros and 0 <= seq_idx < len(numeros))
                 else seq_idx + 1)
        t.ret(x, yr, col_fracao, hlin)
        t.txt(x, yr, (i + 1) if rasurada else (replan + num_g),
              size=_FONTE_VAL_TABELA, align="c", w=col_fracao, h=hlin)
        x += col_fracao
        x_rasura0 = x          # a rasura da fração já tratada começa na Data
        for w in (col_data, col_hora):
            t.ret(x, yr, w, hlin); x += w
        if ativa:
            # 1º dia do TRATAMENTO (24 min/iso) = fração global 1, não a 1ª linha
            # desta página.
            t_val = _t_min(num_g - 1, linha)
            t.ret(x, yr, col_t, hlin, fill=(AMARELO if num_g == 1 else None))
            t.txt(x, yr, str(t_val), font="Helvetica-Bold", size=_FONTE_VAL_TABELA,
                  align="c", w=col_t, h=hlin)
        else:
            t.ret(x, yr, col_t, hlin)
        x += col_t
        t.ret(x, yr, col_tec // 2, hlin)
        t.ret(x + col_tec // 2, yr, col_tec // 2, hlin)
        x += col_tec
        texto_img = None
        if ativa:
            if num_g == (ultima if ultima is not None else total):
                texto_img = _FIM_TTO
            elif 0 <= seq_idx < len(imagens):
                texto_img = imagens[seq_idx] or None
        # Quadrado vazio (largura de 1 campo) à ESQUERDA p/ o técnico; texto
        # (MV/CBCT/Final Tto.) na célula mais larga à DIREITA — igual ao exemplo.
        t.ret(x, yr, col_img_dir, hlin)
        t.ret(x + col_img_dir, yr, col_img_esq, hlin)
        if texto_img:
            t.txt(x + col_img_dir, yr, texto_img, size=tam_img, align="c",
                  w=col_img_esq, h=hlin)
        x += col_img
        # Sub-colunas de campo: brancas p/ marcar nos campos do(s) plano(s) da
        # fração; cinza nos demais/inativos.
        for j in range(n_sub):
            if j < n_campos_ativo and ativa and combinado[j][0] in planos_ativos:
                fill = None
            else:
                fill = CINZA
            t.ret(x, yr, larg_sub, hlin, fill=fill)
            x += larg_sub
        # Rasura e rótulo: os mesmos do mapa de plano único (ver lá o porquê
        # de a diagonal cobrir a linha e de o rótulo morar nas Observações).
        if rasurada:
            c.setStrokeColor(black); c.setLineWidth(1)
            c.line(x_rasura0, t.H - (yr + hlin), x, t.H - yr)
        t.ret(x, yr, col_obs, hlin)
        if rasurada and i == 0:
            t.txt(x, yr, texto_replanejamento(replan, dose_replan),
                  font="Helvetica-Bold", size=_FONTE_VAL_TABELA, w=col_obs,
                  h=hlin, color=tema.forte)
        x += col_obs
        t.ret(x, yr, col_med, hlin); x += col_med
        # Dose TOTAL acumulada (única, contínua): a cada dia soma a dose dos
        # planos tratados; o valor sai na sub-coluna do plano tratado.
        if rasurada:
            # Dias do plano anterior: registra a dose já tratada, acumulada
            # (nº da fração × dose/fração informada no replanejamento).
            t.ret(x_dose0, yr, col_dose, hlin, fill=CINZA)
            if dose_replan:
                t.txt(x_dose0, yr, br((i + 1) * dose_replan), size=tam_dose,
                      align="c", w=col_dose, h=hlin)
        else:
            for p in linha:
                dose_acc[grupo_de[p]] += dose_dia_por[p]
            xd = x_dose0
            for pi in range(n_planos):
                tratado = pi in planos_ativos
                t.ret(xd, yr, col_dose_p, hlin,
                      fill=(_cor_plano(base + pi, tema) if (ativa and tratado) else None))
                # Valor na célula do plano tratado: o acumulado do GRUPO dele
                # (só ele, quando não soma com ninguém). Vazia nas demais.
                valor = dose_acc[grupo_de[pi]]
                if ativa and tratado and valor:
                    t.txt(xd, yr, br(valor), size=tam_dose, align="c",
                          w=col_dose_p, h=hlin)
                xd += col_dose_p
    t.recorte_fim()
    t.moldura(M, y0, W - 2 * M, hh + total_linhas * hlin)
    return y0 + hh + total_linhas * hlin


# ---------------------------------------------------------------------------
# Página 1 — Cortes ortogonais + DVH (requer a TC completa)
# ---------------------------------------------------------------------------


def _img(c: canvas.Canvas, png: bytes, x, y, w, h, H, legenda=""):
    """Desenha um PNG (bytes) sem borda, com origem no topo-esquerda."""
    t = Tela(c, c._pagesize[0], H)
    try:
        c.drawImage(ImageReader(io.BytesIO(png)), x, H - (y + h - 14), w, h - 16,
                    preserveAspectRatio=True, mask="auto", anchor="c")
    except Exception:  # noqa: BLE001 — a ficha sai sem a imagem, não sai quebrada
        # São os cortes e o DVH da página 1: sumir em silêncio é o pior caso.
        _LOG.exception("Falha ao desenhar a imagem %r no PDF", legenda or "(sem legenda)")
    if legenda:
        t.txt(x, y + h - 12, legenda, font="Helvetica-Bold", size=8, align="c", w=w)


def pagina_cortes_dvh(c: canvas.Canvas, dados: dict, recursos: dict):
    """Página retrato: [Axial | 3D] / [Coronal | Sagital] + DVH abaixo."""
    W, H = portrait(A4)
    t = Tela(c, W, H)
    M = 22
    ct = recursos.get("ct")
    rs = recursos.get("rs")
    rd = recursos.get("rd")

    # Cabeçalho.
    _logo(c, M, H - 72, 148, 58, maquina=dados.get("maquina"))
    _w_cab = W - 2 * M
    t.txt(M, 14, "Cortes Ortogonais e DVH", font="Helvetica-Bold", size=14, h=20, align="c", w=_w_cab)
    # Nome, NASCIMENTO e ID, nesta ordem. A data de nascimento entrou porque
    # esta folha circula solta (cortes e DVH são o que o físico confere fora da
    # ficha): nome e ID sozinhos não distinguem homônimo, e é a DDN que a equipe
    # usa para conferir paciente em toda parte do serviço.
    t.txt(M, 33, dados.get("pac_nome", ""), size=10, align="c", w=_w_cab)
    t.txt(M, 46, dados.get("pac_nascimento", ""), size=10, align="c", w=_w_cab)
    t.txt(M, 59, dados.get("pac_registro", ""), size=10, align="c", w=_w_cab)

    # Grade 2 × 2: [Axial | 3D] na linha 1 / [Coronal | Sagital] na linha 2.
    y0 = 78
    gap = 8
    w_col = (W - 2 * M - gap) / 2
    h_row = w_col * 0.76

    x_esq = M
    x_dir = M + w_col + gap
    y_l1 = y0
    y_l2 = y0 + h_row + gap

    rd = recursos.get("rd")
    mostrar_iso = recursos.get("mostrar_isodose", True)
    iso_range = recursos.get("isodose_range", (50.0, 100.0))
    mostrar_est = recursos.get("mostrar_estruturas", True)
    est_vis = recursos.get("estruturas_visiveis")

    def _idx(plano):
        """O corte escolhido na tela, ou o central quando não houve escolha.

        ``capitalize()`` no caminho do central: ``ct.n_cortes`` indexa um dict
        de chaves ``"Axial"/"Coronal"/"Sagital"`` e levanta ``KeyError`` com
        qualquer outra grafia — e estas chamadas passam o plano em minúsculas.
        A ficha inteira estourava ao gerar a página 1 sem índice escolhido, que
        é o que acontece quando o plano nunca foi aberto no visualizador (a
        GUI manda ``idx_axial=None``). Medido no caso 9000021ANA, 21/08/2026.
        """
        v = recursos.get(f"idx_{plano.lower()}")
        return v if v is not None else ct.indice_central(plano.capitalize())

    if ct is not None:
        png_axial = corte.renderizar_corte(ct, "Axial", _idx("axial"),
                                           janela="Mama", rs=rs,
                                           rd=rd, mostrar_isodose=mostrar_iso,
                                           isodose_range=iso_range,
                                           mostrar_estruturas=mostrar_est,
                                           estruturas_visiveis=est_vis,
                                           dose_ref=recursos.get("dose_ref"))
        _img(c, png_axial, x_esq, y_l1, w_col, h_row, H)
        png_coronal = corte.renderizar_corte(ct, "Coronal", _idx("coronal"),
                                             janela="Mama", rs=rs,
                                             rd=rd, mostrar_isodose=mostrar_iso,
                                             isodose_range=iso_range,
                                             mostrar_estruturas=mostrar_est,
                                             estruturas_visiveis=est_vis,
                                             dose_ref=recursos.get("dose_ref"))
        _img(c, png_coronal, x_esq, y_l2, w_col, h_row, H)
        png_sagital = corte.renderizar_corte(ct, "Sagital", _idx("sagital"),
                                             janela="Mama", rs=rs,
                                             rd=rd, mostrar_isodose=mostrar_iso,
                                             isodose_range=iso_range,
                                             mostrar_estruturas=mostrar_est,
                                             estruturas_visiveis=est_vis,
                                             dose_ref=recursos.get("dose_ref"))
        _img(c, png_sagital, x_dir, y_l2, w_col, h_row, H)
        # Guarda os cortes já renderizados para reuso (ex.: imagem do registro
        # JSON), evitando um segundo passe de renderização.
        recursos["_pngs_cortes"] = {"Axial": png_axial,
                                    "Coronal": png_coronal,
                                    "Sagital": png_sagital}
    else:
        for x, y in ((x_esq, y_l1), (x_esq, y_l2), (x_dir, y_l2)):
            t.ret(x, y, w_col, h_row)
        t.txt(x_esq, y_l1 + h_row / 2,
              "TC não carregada — importe a série completa.",
              size=10, align="c", w=W - 2 * M)

    # 3D corpo (coluna direita, linha 1) — usa o PNG já exibido no app.
    png3d = recursos.get("png_3d")
    if png3d is None and rs is not None:
        try:
            from isocentro.desenho import corpo
            png3d = corpo.renderizar_corpo(rs)
        except Exception:  # noqa: BLE001
            png3d = None
    if png3d:
        _img(c, png3d, x_dir, y_l1, w_col, h_row, H)
    else:
        t.ret(x_dir, y_l1, w_col, h_row)

    # DVH — linha 3, largura total.
    y_dvh = y_l2 + h_row + gap
    h_dvh = H - y_dvh - M - 16
    w_dvh = W - 2 * M

    if rs is not None and rd is not None:
        try:
            from isocentro.desenho import grafico_dvh
            from isocentro.dicom import dvh
            nomes = (_ordem_do_dvh(rs, recursos["estruturas_dvh"]) if recursos.get("estruturas_dvh")
                     else _estruturas_para_dvh(rs))
            curvas = dvh.calcular_dvh(rd, rs, nomes)
            if curvas:
                png_dvh = grafico_dvh.plotar_dvh(curvas, "")
                recursos["_png_dvh"] = png_dvh  # reuso no registro/regeração
                _img(c, png_dvh, M, y_dvh, w_dvh, h_dvh, H)
            else:
                t.ret(M, y_dvh, w_dvh, h_dvh)
                t.txt(M, y_dvh + h_dvh / 2, "DVH indisponível.",
                      size=9, align="c", w=w_dvh)
        except Exception as exc:  # noqa: BLE001
            t.ret(M, y_dvh, w_dvh, h_dvh)
            t.txt(M, y_dvh + h_dvh / 2, f"DVH: {exc}", size=8, align="c", w=w_dvh)
    else:
        t.ret(M, y_dvh, w_dvh, h_dvh)
        t.txt(M, y_dvh + h_dvh / 2, "DVH requer RT Struct + RT Dose.",
              size=9, align="c", w=w_dvh)



def estrutura_auxiliar(nome: str) -> bool:
    """True para estrutura 'de apoio' — anel, CTV, estrutura de dose, ou nome
    iniciado por minúscula, dígito ou ``Z_``. Essas começam DESMARCADAS no
    DVH/cortes e não entram no DVH quando não há seleção explícita (fonte única
    da convenção, usada aqui e pelo viewer)."""
    s = (nome or "").strip()
    if not s:
        return False
    low = s.lower()
    return bool(s[0].islower() or s[0].isdigit() or s.startswith("Z_")
                or "anel" in low or "ctv" in low or "dose" in low)


def estrutura_oculta(nome: str) -> bool:
    """True para estrutura que NÃO deve aparecer na lista de Estruturas nem no
    DVH/cortes: nome iniciado por ``_``, ou que contenha ``PRV`` ou ``GTV``.

    Diferente de ``estrutura_auxiliar`` (que apenas começa DESMARCADA): estas
    são removidas da lista de vez."""
    s = (nome or "").strip()
    if not s:
        return False
    low = s.lower()
    return s.startswith("_") or "prv" in low or "gtv" in low


# Tipos DICOM que não são anatomia do paciente: ficam fora do DVH e da lista de
# estruturas (logo, também dos cortes). O Monaco (Elekta) exporta a mesa como
# SUPPORT ("Foam Core", "Carbon Fiber") e os pontos de referência como MARKER
# ("TP0", "ISO TTO") — nomes que nenhum filtro por texto pega. A mesa saía
# desenhada por cima da TC, feito um barco embaixo do paciente, e ainda ocupava
# vaga de órgão no DVH.
TIPOS_NAO_PACIENTE = {"SUPPORT", "MARKER", "FIDUCIAL", "REGISTRATION",
                      "ISOCENTER", "DOSE_REGION", "CONTROL", "BRACHY_CHANNEL"}
_TIPOS_FORA_DVH = TIPOS_NAO_PACIENTE | {"EXTERNAL"}


def _estruturas_para_dvh(rs, limite: int = 8) -> list[str]:
    """Seleciona alvos e órgãos de risco (nomes) que tenham contorno, para o DVH.

    Ignora estruturas de apoio (anel/CTV/auxiliares — ver ``estrutura_auxiliar``)
    e o que não é paciente (``_TIPOS_FORA_DVH``).

    Os ALVOS vêm primeiro: o corte em ``limite`` segue a ordem do RT Struct, e
    nos planos do Monaco o PTV costuma vir depois dos órgãos — o DVH saía inteiro
    de OARs, sem o alvo do tratamento.
    """
    com_contorno = {
        int(rc.ReferencedROINumber)
        for rc in getattr(rs, "ROIContourSequence", [])
        if getattr(rc, "ContourSequence", None)
    }
    tipos = {
        int(o.ReferencedROINumber): str(getattr(o, "RTROIInterpretedType", ""))
        for o in getattr(rs, "RTROIObservationsSequence", [])
    }
    alvos, outras = [], []
    for r in rs.StructureSetROISequence:
        num = int(r.ROINumber)
        if num not in com_contorno or tipos.get(num, "").upper() in _TIPOS_FORA_DVH:
            continue
        nome = str(r.ROIName)
        if estrutura_oculta(nome) or estrutura_auxiliar(nome):
            continue
        eh_alvo = tipos.get(num, "").upper() == "PTV" or "PTV" in nome.upper()
        (alvos if eh_alvo else outras).append(nome)
    return (alvos + outras)[:limite]


def _ordem_do_dvh(rs, nomes) -> list[str]:
    """As estruturas escolhidas na tela, na ordem do RT Struct e com os alvos primeiro.

    A escolha chega da tela como ``set`` (``Visualizador.estruturas_selecionadas``),
    e a ordem de um ``set`` de texto muda a cada processo. Como a cor de cada curva
    sai da posição dela (``grafico_dvh._cor``), a mesma ficha impressa duas vezes trocava a
    ordem da legenda e a cor das estruturas — o Coração preto numa via, cinza na
    outra (medido em 22/10/2026 no TC8, gerando o PDF duas vezes).
    """
    escolhidos = set(nomes)
    tipos = {
        int(o.ReferencedROINumber): str(getattr(o, "RTROIInterpretedType", ""))
        for o in getattr(rs, "RTROIObservationsSequence", [])
    }
    alvos, outras = [], []
    for r in rs.StructureSetROISequence:
        nome = str(r.ROIName)
        if nome not in escolhidos or nome in alvos or nome in outras:
            continue
        eh_alvo = tipos.get(int(r.ROINumber), "").upper() == "PTV" or "PTV" in nome.upper()
        (alvos if eh_alvo else outras).append(nome)
    return alvos + outras


# ---------------------------------------------------------------------------
# Página Alta — igual à pág. 1 com cabeçalho "RELATÓRIO DE ALTA"
# ---------------------------------------------------------------------------


def pagina_alta(c: canvas.Canvas, dados: dict, recursos: dict):
    """Retrato A4: mesmo conteúdo da pág. 1 com cabeçalho de Relatório de Alta."""
    W, H = portrait(A4)
    t = Tela(c, W, H)
    M = 22
    ct = recursos.get("ct")
    rs = recursos.get("rs")
    rd = recursos.get("rd")

    # Cabeçalho: logo à esquerda + "RELATÓRIO DE ALTA" centralizado na largura total.
    _w_cab = W - 2 * M
    h_logo = 48
    y_logo = 14
    _logo(c, M, H - (y_logo + h_logo - 4), 120, h_logo - 8, anchor="w", maquina=dados.get("maquina"))
    t.txt(M, y_logo, "RELATÓRIO DE ALTA", font="Helvetica-Bold", size=20,
          align="c", w=_w_cab, h=h_logo)

    # Informações do paciente — centralizadas na mesma largura, sem negrito.
    lh = 15
    y_info = y_logo + h_logo + 2
    t.txt(M, y_info,        f"PACIENTE: {dados.get('pac_nome', '')}",
          font="Helvetica", size=11, align="c", w=_w_cab, h=lh)
    t.txt(M, y_info + lh,   f"DATA DE NASCIMENTO: {dados.get('pac_nascimento', '')}",
          font="Helvetica", size=11, align="c", w=_w_cab, h=lh)
    t.txt(M, y_info + 2*lh, f"RADIO-ONCOLOGISTA: {dados.get('eq_medico', '')}",
          font="Helvetica", size=11, align="c", w=_w_cab, h=lh)

    # Grade 2 × 2: mesma lógica de pagina_cortes_dvh.
    y0 = y_info + 3 * lh + 6
    gap = 8
    w_col = (W - 2 * M - gap) / 2
    h_row = w_col * 0.76

    x_esq = M
    x_dir = M + w_col + gap
    y_l1 = y0
    y_l2 = y0 + h_row + gap

    mostrar_iso = recursos.get("mostrar_isodose", True)
    iso_range = recursos.get("isodose_range", (50.0, 100.0))
    mostrar_est = recursos.get("mostrar_estruturas", True)
    est_vis = recursos.get("estruturas_visiveis")

    def _idx(plano):
        """O corte escolhido na tela, ou o central quando não houve escolha.

        ``capitalize()`` no caminho do central: ``ct.n_cortes`` indexa um dict
        de chaves ``"Axial"/"Coronal"/"Sagital"`` e levanta ``KeyError`` com
        qualquer outra grafia — e estas chamadas passam o plano em minúsculas.
        A ficha inteira estourava ao gerar a página 1 sem índice escolhido, que
        é o que acontece quando o plano nunca foi aberto no visualizador (a
        GUI manda ``idx_axial=None``). Medido no caso 9000021ANA, 21/08/2026.
        """
        v = recursos.get(f"idx_{plano.lower()}")
        return v if v is not None else ct.indice_central(plano.capitalize())

    if ct is not None:
        png_axial = corte.renderizar_corte(ct, "Axial", _idx("axial"),
                                           janela="Mama", rs=rs,
                                           rd=rd, mostrar_isodose=mostrar_iso,
                                           isodose_range=iso_range,
                                           mostrar_estruturas=mostrar_est,
                                           estruturas_visiveis=est_vis,
                                           dose_ref=recursos.get("dose_ref"))
        _img(c, png_axial, x_esq, y_l1, w_col, h_row, H)
        png_coronal = corte.renderizar_corte(ct, "Coronal", _idx("coronal"),
                                             janela="Mama", rs=rs,
                                             rd=rd, mostrar_isodose=mostrar_iso,
                                             isodose_range=iso_range,
                                             mostrar_estruturas=mostrar_est,
                                             estruturas_visiveis=est_vis,
                                             dose_ref=recursos.get("dose_ref"))
        _img(c, png_coronal, x_esq, y_l2, w_col, h_row, H)
        png_sagital = corte.renderizar_corte(ct, "Sagital", _idx("sagital"),
                                             janela="Mama", rs=rs,
                                             rd=rd, mostrar_isodose=mostrar_iso,
                                             isodose_range=iso_range,
                                             mostrar_estruturas=mostrar_est,
                                             estruturas_visiveis=est_vis,
                                             dose_ref=recursos.get("dose_ref"))
        _img(c, png_sagital, x_dir, y_l2, w_col, h_row, H)
    else:
        for x, y in ((x_esq, y_l1), (x_esq, y_l2), (x_dir, y_l2)):
            t.ret(x, y, w_col, h_row)
        t.txt(x_esq, y_l1 + h_row / 2,
              "TC não carregada — importe a série completa.",
              size=10, align="c", w=W - 2 * M)

    png3d = recursos.get("png_3d")
    if png3d is None and rs is not None:
        try:
            from isocentro.desenho import corpo
            png3d = corpo.renderizar_corpo(rs)
        except Exception:  # noqa: BLE001
            png3d = None
    if png3d:
        _img(c, png3d, x_dir, y_l1, w_col, h_row, H)
    else:
        t.ret(x_dir, y_l1, w_col, h_row)

    y_dvh = y_l2 + h_row + gap
    h_dvh = H - y_dvh - M - 16
    w_dvh = W - 2 * M

    if rs is not None and rd is not None:
        try:
            from isocentro.desenho import grafico_dvh
            from isocentro.dicom import dvh
            nomes = (_ordem_do_dvh(rs, recursos["estruturas_dvh"]) if recursos.get("estruturas_dvh")
                     else _estruturas_para_dvh(rs))
            curvas = dvh.calcular_dvh(rd, rs, nomes)
            if curvas:
                png_dvh = grafico_dvh.plotar_dvh(curvas, "")
                recursos["_png_dvh"] = png_dvh  # reuso no registro/regeração
                _img(c, png_dvh, M, y_dvh, w_dvh, h_dvh, H)
            else:
                t.ret(M, y_dvh, w_dvh, h_dvh)
                t.txt(M, y_dvh + h_dvh / 2, "DVH indisponível.",
                      size=9, align="c", w=w_dvh)
        except Exception as exc:  # noqa: BLE001
            t.ret(M, y_dvh, w_dvh, h_dvh)
            t.txt(M, y_dvh + h_dvh / 2, f"DVH: {exc}", size=8, align="c", w=w_dvh)
    else:
        t.ret(M, y_dvh, w_dvh, h_dvh)
        t.txt(M, y_dvh + h_dvh / 2, "DVH requer RT Struct + RT Dose.",
              size=9, align="c", w=w_dvh)


def _meta(c: canvas.Canvas, dados: dict, prefixo: str) -> None:
    """Define título/autor do PDF (aparece no leitor em vez de 'untitled')."""
    nome = (dados.get("pac_nome") or "Paciente").strip()
    reg = (dados.get("pac_registro") or "").strip()
    c.setTitle(f"{prefixo} - {nome}" + (f" ({reg})" if reg else ""))
    c.setAuthor("Clinica")
    c.setSubject(prefixo)


def gerar_alta(dados: dict, recursos: dict) -> bytes:
    """Gera somente o PDF de Relatório de Alta (uma página retrato)."""
    buffer = io.BytesIO()
    c = rodape.em_todas(canvas.Canvas(buffer, pagesize=portrait(A4)))
    _meta(c, dados, "Relatório de Alta")
    pagina_alta(c, dados, recursos)
    c.showPage()
    c.save()
    return buffer.getvalue()


def _pagina_alta_arquivada(c: canvas.Canvas, dados: dict,
                           cortes_png: bytes | None, dvh_png: bytes | None):
    """Página de Alta a partir dos PNGs já gerados (cabeçalho de Alta + cortes +
    DVH). Mesma montagem visual de ``pagina_alta``, mas usando as imagens prontas
    — é o que permite uma página por plano no multi-plano."""
    W, H = portrait(A4)
    c.setPageSize((W, H))
    t = Tela(c, W, H)
    M = 22
    _w = W - 2 * M
    h_logo = 48
    y_logo = 14
    _logo(c, M, H - (y_logo + h_logo - 4), 120, h_logo - 8, anchor="w", maquina=dados.get("maquina"))
    t.txt(M, y_logo, "RELATÓRIO DE ALTA", font="Helvetica-Bold", size=20,
          align="c", w=_w, h=h_logo)
    lh = 15
    y_info = y_logo + h_logo + 2
    t.txt(M, y_info,         f"PACIENTE: {dados.get('pac_nome', '')}",
          font="Helvetica", size=11, align="c", w=_w, h=lh)
    t.txt(M, y_info + lh,    f"DATA DE NASCIMENTO: {dados.get('pac_nascimento', '')}",
          font="Helvetica", size=11, align="c", w=_w, h=lh)
    t.txt(M, y_info + 2 * lh, f"RADIO-ONCOLOGISTA: {dados.get('eq_medico', '')}",
          font="Helvetica", size=11, align="c", w=_w, h=lh)

    y0 = y_info + 3 * lh + 6
    gap = 10
    h_util = H - y0 - M
    h_cortes = h_util * 0.60
    h_dvh = h_util - h_cortes - gap
    if cortes_png:
        _img(c, cortes_png, M, y0, _w, h_cortes, H)
    else:
        t.ret(M, y0, _w, h_cortes)
        t.txt(M, y0 + h_cortes / 2, "Imagem de cortes não disponível.",
              size=10, align="c", w=_w)
    y_dvh = y0 + h_cortes + gap
    if dvh_png:
        _img(c, dvh_png, M, y_dvh, _w, h_dvh, H)
    else:
        t.ret(M, y_dvh, _w, h_dvh)
        t.txt(M, y_dvh + h_dvh / 2, "DVH não disponível.", size=9, align="c", w=_w)


def gerar_alta_arquivada(dados: dict, cortes_png: bytes | None,
                         dvh_png: bytes | None) -> bytes:
    """Relatório de Alta de UM plano reaberto do registro (sem DICOM).

    ``gerar_alta`` desenha os cortes a partir de ``recursos["ct"]``, e numa
    ficha recarregada do JSON não há TC nenhuma: a Alta saía com "TC não
    carregada" e "DVH requer RT Struct + RT Dose" no lugar das imagens, ao lado
    de uma ficha que, no mesmo clique, saía certa com os PNGs do registro. O
    multi-plano nunca teve o defeito — lá os PNGs salvos já iam por plano.
    """
    buffer = io.BytesIO()
    c = rodape.em_todas(canvas.Canvas(buffer, pagesize=portrait(A4)))
    _meta(c, dados, "Relatório de Alta")
    _pagina_alta_arquivada(c, dados, cortes_png, dvh_png)
    c.showPage()
    c.save()
    return buffer.getvalue()


def gerar_alta_multiplano(planos: list, modo: str = "individual",
                          planos_ficha: list | None = None,
                          grupos_dose: list | None = None) -> bytes:
    """Relatório de Alta multi-plano, seguindo o mesmo modo escolhido na Ficha.

    Espelha a seção de cortes+DVH da ficha multi-plano:
    ``"individual"`` → uma página de Alta por plano; ``"soma"`` → uma combinando
    TODOS os planos; ``"personalizado"`` → uma combinando só os de ``planos_ficha``.
    Usa os PNGs salvos (``cortes_salvo``/``dvh_salvo``, no fluxo arquivado) ou os
    renderiza do DICOM de cada plano."""
    buffer = io.BytesIO()
    c = rodape.em_todas(canvas.Canvas(buffer, pagesize=portrait(A4)))
    _meta(c, planos[0]["dados"], "Relatório de Alta")
    if modo in ("soma", "personalizado"):
        sub = planos
        restantes = []
        if modo == "personalizado" and planos_ficha:
            idx_sub = [i for i in planos_ficha if 0 <= i < len(planos)]
            if idx_sub:
                sub = [planos[i] for i in idx_sub]
                restantes = [p for i, p in enumerate(planos) if i not in set(idx_sub)]
        cortes_png, dvh_png = _pagina1_soma(sub, grupos_dose)
        _pagina_alta_arquivada(c, planos[0]["dados"], cortes_png, dvh_png)
        c.showPage()
        for p in restantes:   # planos fora da combinação mantêm a sua página
            cp = p.get("cortes_salvo") or montar_imagem_pagina1(
                p["dados"], p.get("recursos") or {})
            dp = p.get("dvh_salvo") or _dvh_png(p.get("recursos") or {})
            _pagina_alta_arquivada(c, p["dados"], cp, dp)
            c.showPage()
    else:
        for p in planos:
            cortes_png = p.get("cortes_salvo") or montar_imagem_pagina1(
                p["dados"], p.get("recursos") or {})
            dvh_png = p.get("dvh_salvo") or _dvh_png(p.get("recursos") or {})
            _pagina_alta_arquivada(c, p["dados"], cortes_png, dvh_png)
            c.showPage()
    c.save()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Registro de Tratamento (SUS) — folha de assinaturas por fração
# ---------------------------------------------------------------------------


def _hline(t: "Tela", x, y, w, lw=0.8) -> None:
    """Linha horizontal em coordenadas da Tela (origem no topo-esquerda)."""
    t.c.setStrokeColor(black)
    t.c.setLineWidth(lw)
    t.c.line(x, t.H - y, x + w, t.H - y)


def pagina_registro_sus(c: canvas.Canvas, dados: dict, total_fracoes: int):
    """Folha 'REGISTRO DE TRATAMENTO' (SUS): cabeçalho do paciente + Número SUS
    e uma tabela de assinaturas por fração, em duas colunas (igual ao modelo)."""
    W, H = landscape(A4)
    c.setPageSize((W, H))
    t = Tela(c, W, H)
    M = 14

    # ── Cabeçalho: logo | dados do paciente | caixa "REGISTRO DE TRATAMENTO" ──
    y = 10
    h_cab = 78
    _logo(c, M + 4, H - (y + h_cab - 6), 150, h_cab - 22, anchor="c", maquina=dados.get("maquina"))

    xp = M + 168
    w_lab = 96
    info = [
        ("Paciente:", dados.get("pac_nome", "")),
        ("RGH:", dados.get("pac_registro", "")),
        ("Médico(a):", dados.get("eq_medico", "")),
        ("Nascimento:", dados.get("pac_nascimento", "")),
        ("Número SUS:", dados.get("numero_sus", "")),
    ]
    lh = h_cab / len(info)
    for i, (lab, val) in enumerate(info):
        yy = y + i * lh
        t.txt(xp, yy, lab, font="Helvetica-Bold", size=10, align="r", w=w_lab, h=lh)
        t.txt(xp + w_lab + 6, yy, val, font="Helvetica", size=10, h=lh)

    w_box = 210
    x_box = W - M - w_box
    t.ret(x_box, y + 8, w_box, h_cab - 16)
    _hb = (h_cab - 16) / 2
    t.txt(x_box, y + 8, "REGISTRO DE", font="Helvetica-Bold", size=16,
          align="c", w=w_box, h=_hb)
    t.txt(x_box, y + 8 + _hb, "TRATAMENTO", font="Helvetica-Bold", size=16,
          align="c", w=w_box, h=_hb)

    # ── Tabela em dois grupos (colunas): Fração | Data | Assinatura ──────────
    total = max(int(total_fracoes or 0), 1)
    n_rows = (total + 1) // 2       # altura das colunas (a maior)
    n_left = total - n_rows         # esquerda recebe a metade MENOR (como o modelo)

    y0 = y + h_cab + 8
    W_util = W - 2 * M
    gap = 20
    gw = (W_util - gap) / 2
    col_frac = 46
    col_data = 104
    col_ass = gw - col_frac - col_data
    hh = 18

    def _cab_grupo(gx):
        t.ret(gx, y0, col_frac, hh, fill=CINZA)
        t.txt(gx, y0, "Fração", font="Helvetica-Bold", size=10, align="c", w=col_frac, h=hh)
        t.ret(gx + col_frac, y0, col_data, hh, fill=CINZA)
        t.txt(gx + col_frac, y0, "Data", font="Helvetica-Bold", size=10,
              align="c", w=col_data, h=hh)
        t.ret(gx + col_frac + col_data, y0, col_ass, hh, fill=CINZA)
        t.txt(gx + col_frac + col_data, y0, "Assinatura", font="Helvetica-Bold",
              size=10, align="c", w=col_ass, h=hh)

    gxs = [M, M + gw + gap]
    for gx in gxs:
        _cab_grupo(gx)

    # Altura de linha para caber n_rows linhas no espaço restante (teto de 22).
    h_disp = H - (y0 + hh) - M
    hlin = min(h_disp / n_rows, 22)

    for r in range(n_rows):
        yr = y0 + hh + r * hlin
        y_base = yr + hlin * 0.66
        for g, gx in enumerate(gxs):
            # Esquerda: frações 1..n_left; direita: n_left+1..total.
            frac = (r + 1) if g == 0 else (n_left + r + 1)
            if g == 0 and frac > n_left:
                continue
            if frac > total:
                continue
            t.txt(gx, yr, str(frac), font="Helvetica-Bold", size=10,
                  align="c", w=col_frac, h=hlin)
            t.txt(gx + col_frac, yr, "_____/_____/_____", size=10,
                  align="c", w=col_data, h=hlin)
            _hline(t, gx + col_frac + col_data + 4, y_base, col_ass - 8, lw=0.6)


def _anexar_registro_sus(c: canvas.Canvas, dados: dict, total_fracoes: int) -> None:
    """Anexa as folhas de Registro de Tratamento (SUS): duas páginas idênticas
    (pág. 4 e 5), só quando o paciente é SUS (``dados['pac_sus']``)."""
    if not dados.get("pac_sus"):
        return
    for _ in range(2):
        pagina_registro_sus(c, dados, total_fracoes)
        c.showPage()
        c.setPageSize(landscape(A4))


# ---------------------------------------------------------------------------
# Páginas de conferência do 600CD — DRRs de setup + folha de portais
# ---------------------------------------------------------------------------


def pagina_drr(c: canvas.Canvas, dados: dict, png: bytes,
               titulo: str = "DRR") -> None:
    """Página retrato com um DRR de setup (AP ou perfil) e o cabeçalho DRR.

    Textos centralizados; ``titulo`` traz o portal (ex.: 'DRR - Portal 0').
    """
    W, H = portrait(A4)
    c.setPageSize((W, H))
    t = Tela(c, W, H)
    M = 14
    w = W - 2 * M
    t.txt(M, 20, titulo, font="Helvetica-Bold", size=20, h=24, align="c", w=w)
    t.txt(M, 60, f"PACIENTE: {dados.get('pac_nome', '')}", size=11, align="c", w=w)
    t.txt(M, 78, f"DATA DE NASCIMENTO: {dados.get('pac_nascimento', '')}",
          size=11, align="c", w=w)
    t.txt(M, 96, f"RADIO-ONCOLOGISTA: {dados.get('eq_medico', '')}",
          size=11, align="c", w=w)
    # DRR o maior possível na folha: limitado pela largura (retrato) e pela
    # altura útil abaixo do cabeçalho. Sem borda (a folha impressa não a tem).
    y0 = 112
    lado = min(w, H - y0 - M)
    x = M + (w - lado) / 2              # centraliza quando a altura limita
    if png:
        _img(c, png, x, y0, lado, lado + 16, H)


# Os três eixos de correção, na ordem em que ``PORTAL_ISO`` os traz. Servem à
# LEGENDA da faixa de orientação, e saem da mesma tupla que rotula as colunas da
# tabela: legenda e cabeçalho discordarem sobre um sinal é o defeito que manda
# deslocar o paciente para o lado errado, e duas listas discordam cedo ou tarde.
PORTAL_EIXOS = ("Lateral", "Longitudinal", "Vertical")


def portal_legenda() -> list:
    """``[(eixo, "+ Nome", "− Nome")]`` — a legenda da folha de portais.

    Derivada de ``PORTAL_ISO`` aos pares: as seis direções são três eixos, na
    ordem lateral → longitudinal → vertical. O sinal mostrado é o da tupla, não
    um "+" fixo na primeira coluna: em dois dos três eixos o positivo é o
    SEGUNDO nome (Pés e Anterior), e escrever "+ Cabeça" ali seria inverter a
    correção no papel.
    """
    linhas = []
    for i, eixo in enumerate(PORTAL_EIXOS):
        (s1, n1), (_s2, n2) = PORTAL_ISO[2 * i], PORTAL_ISO[2 * i + 1]
        mais = n1 if s1 == "+" else n2
        menos = n2 if s1 == "+" else n1
        linhas.append((eixo, f"+ {mais}", f"−  {menos}"))
    return linhas


def pagina_portal_checagem(c: canvas.Canvas, dados: dict) -> None:
    """Última página: folha de conferência de portais do 600CD.

    **RETRATO** — voltou a ser, em 25/08/2026, depois de um dia em paisagem. A
    paisagem alinhava a folha com as págs. 1 a 3, mas a altura que sobrava só
    dava para DEZ portais, e o usuário confere mais que isso: "em paisagem pode
    ser corrigido somente 10 portais, deixe como retrato que tava antes". Numa
    folha de conferência, a quantidade de linhas é a função — a orientação é a
    forma.

    O que a passagem por paisagem deixou de bom, e ficou: o cabeçalho com a
    identidade completa do paciente, os rótulos de coluna DEITADOS em vez de
    rotacionados, o título que nomeia a folha e o campo GANTRY como célula de
    escrever.

    E o que fez as linhas caberem: os TRÊS diagramas antigos (cubo, sagital e
    frontal) deram lugar ao diagrama de orientação da própria ficha — uma
    imagem só, com a legenda dos sinais ao lado (pedido do usuário). Os três
    ocupavam uma faixa inteira para dizer o que a legenda diz em três linhas.
    """
    W, H = portrait(A4)
    c.setPageSize((W, H))
    t = Tela(c, W, H)
    M = 14

    y = _portal_cabecalho(c, t, dados, M)
    # A folha PRECISA se nomear: é a que se solta do maço para ficar na sala,
    # sendo preenchida por dias. Sem nome, vira "mais uma folha da ficha", que
    # é como um papel de conferência se perde. Negrito e sem tarja, como o
    # "Observações gerais do tratamento" da pág. 2 — é assim que esta ficha
    # abre um bloco.
    h_tit = 13
    t.txt(M, y, "CONFERÊNCIA DE PORTAIS", font="Helvetica-Bold",
          size=_FONTE_CAB_TABELA + 1, h=h_tit)
    y += h_tit + 2
    # A TABELA tem tamanho alvo (teto de linhas × altura de linha) e a faixa de
    # orientação fica com a SOBRA — o inverso de como era. Quem manda na folha
    # agora é o número de portais que o serviço confere de fato; o que passa
    # disso vale mais como espaço de escrever do que como linha em branco.
    alt_faixa = max(_PORTAL_FAIXA_MIN,
                    H - 24 - _portal_altura_tabela() - 8 - y)
    y = _portal_faixa(c, t, dados, M, y, alt_faixa)
    _portal_tabela(t, W, M, y)


def _portal_cabecalho(c: canvas.Canvas, t: "Tela", dados: dict,
                      M: float) -> float:
    """Cabeçalho em RETRATO, com o vocabulário do cabeçalho da ficha.

    Não dá para usar o ``_cabecalho`` das outras páginas: ele mede 686 pt de
    largura (logo + título + caixa do paciente lado a lado) e a folha retrato
    tem 567. Aqui as mesmas peças se empilham — e são as MESMAS ``celula``, com
    os mesmos rótulos e a mesma ordem, para quem alterna entre as folhas achar
    cada dado no lugar que já conhece.
    """
    W, H = t.W, t.H
    larg = W - 2 * M
    y = 14
    h_logo = 46
    _logo(c, M, H - (y + h_logo), 132, h_logo, anchor="c",
          maquina=dados.get("maquina"))
    t.txt(M + 140, y + 6, "Ficha Técnica", font="Helvetica-Bold", size=14,
          align="c", w=larg - 140)
    t.txt(M + 140, y + 24, "de Tratamento", font="Helvetica-Bold", size=14,
          align="c", w=larg - 140)
    y += h_logo + 6

    lh = 17
    meia = larg / 2
    t.recorte_ini(M, y, larg, 3 * lh)
    t.celula(M, y, larg, lh, valor=dados.get("pac_nome", ""), label="Nome:",
             size=9.5, font="Helvetica-Bold")
    t.celula(M, y + lh, meia, lh, valor=dados.get("pac_registro", ""),
             label="RGH:", size=9)
    t.celula(M + meia, y + lh, larg - meia, lh,
             valor=dados.get("pac_nascimento", ""), label="Data de Nasc:",
             size=9)
    t.celula(M, y + 2 * lh, larg - 120, lh, valor=dados.get("eq_medico", ""),
             label="Médico(a):", size=9)
    t.celula(M + larg - 120, y + 2 * lh, 120, lh, label="AL:", size=9,
             valor=constantes.rotulo_maquina(dados.get("maquina", "")))
    t.recorte_fim()
    t.moldura(M, y, larg, 3 * lh)
    return y + 3 * lh + 8


def _portal_faixa(c: canvas.Canvas, t: "Tela", dados: dict, M: float,
                  y0: float, alt: float) -> float:
    """Diagrama de orientação + legenda dos sinais, GANTRY e OBSERVAÇÕES.

    O diagrama é o MESMO que a ficha já traz no canto do cabeçalho — a
    convenção de mesa da série C, com os sinais de cada eixo. Reusá-lo aqui foi
    pedido do usuário, e é a decisão certa por um motivo além do espaço: dois
    desenhos da mesma convenção, um em cada folha do maço, é a chance de eles
    discordarem no dia em que um for corrigido e o outro não.

    A LEGENDA (ver ``portal_legenda``) é o que o diagrama sozinho não diz: qual
    direção anatômica cada sinal empurra. Os três diagramas antigos existiam
    para isso, e gastavam uma faixa inteira.

    A faixa fica com a SOBRA da folha, e não com uma altura cravada: o teto de
    linhas de portal (``_PORTAL_LINHAS_MAX``) passou a valer em 25/08/2026, e o
    que sobra é dela — "21 é muito, mas o espaço para observação precisa ser
    maior, pode aumentar tamanho e fonte da figura e sua legenda".

    Duas colunas: à esquerda o diagrama com a legenda EMBAIXO dele (empilhados
    cabem maiores que lado a lado numa folha retrato de 567 pt úteis); à
    direita o GANTRY e as observações, que herdam a altura toda.
    """
    W = t.W
    larg_total = W - 2 * M
    larg_esq = larg_total * 0.55
    xd = M + larg_esq + 10
    larg_dir = W - M - xd

    # Legenda embaixo do diagrama: uma linha por eixo, corpo de leitura.
    passo = 16.0
    alt_legenda = passo * len(PORTAL_EIXOS)
    alt_diag = max(0.0, alt - alt_legenda - 4)

    img_mesa = TABLE_SERIE_C if os.path.exists(TABLE_SERIE_C) else None
    if img_mesa and alt_diag > 20:
        try:
            # A CAIXA é dada e o reportlab encaixa mantendo a proporção — não
            # há multiplicador de razão cravado no código para envelhecer se a
            # imagem for trocada.
            c.drawImage(img_mesa, M, t.H - (y0 + alt_diag), larg_esq, alt_diag,
                        preserveAspectRatio=True, anchor="c", mask="auto")
        except Exception:  # noqa: BLE001 — a folha vive sem o diagrama
            _LOG.exception("Falha ao desenhar o diagrama da folha de portais")

    yl = y0 + alt_diag + 4
    for i, (eixo, mais, menos) in enumerate(portal_legenda()):
        y = yl + i * passo
        t.txt(M + 4, y, eixo, font="Helvetica-Bold", size=9.5, h=passo)
        t.txt(M + 4 + 76, y, mais, size=10, h=passo)
        t.txt(M + 4 + 152, y, menos, size=10, h=passo)

    # SEM campo GANTRY (tirado a pedido do usuário em 25/08/2026). Ele vinha do
    # papel antigo e era o único dado do plano nesta folha — e um dado que a
    # ficha JÁ TRAZ, com um ângulo por campo, na linha "Gantry" da pág. 2.
    # Aqui era uma casa só, para um tratamento que tem vários; escrever um
    # ângulo nela obrigava a escolher qual, e a folha não diz qual.
    #
    # A altura que ele ocupava foi para as OBSERVAÇÕES, que é o que se preenche
    # de fato — pelo mesmo motivo que aparou as linhas de portal de 21 para 15.
    t.txt(xd, y0, "OBSERVAÇÕES", font="Helvetica-Bold",
          size=_FONTE_CAB_TABELA)
    t.ret(xd, y0 + 12, larg_dir, alt - 12)
    return y0 + alt + 8


# As seis direções de correção do isocentro, com o SINAL de cada uma. O sinal
# é o mesmo dos diagramas da faixa de cima — os dois têm de ser lidos juntos, e
# é por isso que os diagramas não podem sair da folha.
PORTAL_ISO = (("+", "Direita"), ("-", "Esquerda"), ("-", "Cabeça"),
              ("+", "Pés"), ("+", "Anterior"), ("-", "Posterior"))

# O rótulo CURTO de cada direção, para o cabeçalho da coluna. O nome inteiro
# vive na LEGENDA, logo acima e na mesma folha — e é ela a autoridade sobre a
# convenção.
#
# Abreviar não foi economia de gosto: "Esquerda" numa coluna de 28 pt travava o
# cabeçalho INTEIRO em 5,5 pt, porque o corpo é um só para toda a linha de
# rótulos (dois tamanhos ali leem-se como defeito de impressão). Com "Esq." o
# mesmo cabeçalho sobe para 9 pt — o corpo das outras tabelas da ficha.
#
# A coluna ISO não pode simplesmente ficar mais larga: a largura teria de sair
# de "Técnicos" e "Médico", que são onde se escreve NOME À MÃO.
PORTAL_ISO_CURTO = {"Direita": "Dir.", "Esquerda": "Esq.", "Cabeça": "Cab.",
                    "Pés": "Pés", "Anterior": "Ant.", "Posterior": "Post."}

# As colunas finais, com o rótulo já QUEBRADO em linhas. Escritas assim, e não
# quebradas na hora de desenhar: o corte fica onde faz sentido ler ("Corrigido
# pelo / técnico"), e não onde a largura calhou de acabar.
#
# Três linhas em "Corrigido pelo técnico" e "Repetir?" no lugar de "Repetir
# Portal?": era "Portal? (S/N)" numa linha só que segurava o cabeçalho em
# 6,6 pt depois de a coluna ISO parar de segurar. O "(S/N)" embaixo diz o
# formato da resposta, que é o que essa coluna precisa.
PORTAL_FINAIS = ((("Corrigido", "pelo", "técnico"), 66),
                 (("Data da", "Correção"), 62),
                 (("Repetir?", "(S/N)"), 62))

# Altura MÍNIMA de uma linha de portal. Menos que isto e não se escreve a data
# e as iniciais de dois técnicos à mão, que é o que a linha recebe.
_PORTAL_ALT_MIN = 24

# TETO de linhas de portal. A folha em retrato comporta 21, e o usuário aparou
# para 15 em 25/08/2026: "21 é muito, mas o espaço para observação precisa ser
# maior". Quinze é o que este serviço confere de fato — e o que sobra vale mais
# como espaço de escrever do que como linha que nunca se preenche.
#
# É TETO, não número fixo: a folha continua entregando menos se a altura
# encolher (uma faixa de orientação maior, um cabeçalho que cresça), em vez de
# empurrar a última linha para fora da página.
_PORTAL_LINHAS_MAX = 15

# Altura ALVO de uma linha, com o teto de linhas valendo. É ela que decide
# quanto sobra para a faixa de orientação e as observações — ver
# ``_portal_altura_tabela``.
_PORTAL_ALT_ALVO = 26


# Piso da faixa de orientação. Existe para o caso de um cabeçalho crescer: em
# vez de espremer o diagrama até ilegível, a folha entrega menos linhas de
# portal — o teto de linhas é teto, não promessa.
_PORTAL_FAIXA_MIN = 120

# Altura do cabeçalho da tabela: título de grupo + linha dos sinais + rótulos.
_PORTAL_CAB = 16 + 12 + 32


def _portal_altura_tabela() -> float:
    """Quanto a tabela quer, com o teto de linhas na altura alvo."""
    return _PORTAL_CAB + _PORTAL_LINHAS_MAX * _PORTAL_ALT_ALVO


def portal_linhas(disponivel: float) -> int:
    """Quantas linhas de portal cabem em ``disponivel`` pontos, até o teto.

    A conta existe porque o número de linhas é a FUNÇÃO desta folha: dez era um
    número fixo herdado do papel antigo, e foi o que fez a versão em paisagem
    ser recusada ("em paisagem pode ser corrigido somente 10 portais").
    """
    return max(1, min(_PORTAL_LINHAS_MAX,
                      int(disponivel // _PORTAL_ALT_MIN)))


def _portal_tabela(t: "Tela", W: float, M: float, ytab: float) -> None:
    """Tabela de portais, de ``ytab`` até o pé da folha.

    Os rótulos saíram do VERTICAL: em paisagem as colunas cabem deitadas, que é
    como se lê. O cabeçalho rotacionado custava 104 pt de altura — mais que
    quatro linhas de preenchimento — e obrigava a girar a cabeça para conferir
    qual coluna se estava preenchendo, com o paciente na mesa.

    As linhas ficam com a altura que SOBRA, repartida igualmente: numa folha
    que se preenche à mão, espaço de escrita é o recurso escasso, e deixá-lo
    como resto de uma altura fixa é o que fazia o pé da folha ficar vazio.
    """
    H = t.H
    x0 = M
    # nº | Realizado(Dia, Técnicos) | Corrigido(Médico, Data) | ISO(6) | 3 finais
    w_num = 30
    w_real = [56, 118]          # Dia, Técnicos
    w_corr = [118, 62]          # Médico, Data da Correção
    w_iso = 40                  # cada subcoluna ISO
    w_fim = [larg for _rot, larg in PORTAL_FINAIS]
    larg = w_num + sum(w_real) + sum(w_corr) + 6 * w_iso + sum(w_fim)
    esc = (W - 2 * M) / larg    # escala para ocupar a largura útil inteira
    w_num *= esc
    w_real = [v * esc for v in w_real]
    w_corr = [v * esc for v in w_corr]
    w_iso *= esc
    w_fim = [v * esc for v in w_fim]

    h_grp = 16          # faixa do título de grupo (Realizado/Corrigido/ISO)
    h_sign = 12         # linha dos sinais ± (só no grupo ISO)
    h_rot = 32          # linha dos rótulos de coluna (até TRÊS linhas)
    hcab = h_grp + h_sign + h_rot
    # Uma conta só: ``_PORTAL_CAB`` é quem a página usa para reservar o espaço
    # da tabela, e as duas divergirem deixaria a faixa de orientação com uma
    # sobra que a tabela não tem — o pé da folha abriria ou estouraria.
    assert hcab == _PORTAL_CAB, (hcab, _PORTAL_CAB)
    # Quantas linhas cabem, e a sobra repartida entre elas — o pé da folha
    # fecha rente à última, sem faixa em branco.
    disponivel = H - 24 - (ytab + hcab)
    n_linhas = portal_linhas(disponivel)
    hlin = disponivel / n_linhas
    # DOIS corpos, e não um: os títulos de GRUPO ("Realizado", "Correções ISO
    # (cm)") têm a largura do grupo inteiro e ficam no corpo da ficha; só os
    # rótulos de COLUNA são medidos, porque em retrato as colunas encolhem 30%
    # e "pelo técnico" não cabe em 9 pt.
    #
    # Medidos em GRUPO, nunca um a um: encolher só o rótulo que estourou
    # deixaria uma palavra menor no meio do cabeçalho — parece defeito de
    # impressão, e é o rótulo de uma coluna que o médico assina.
    grupo = _FONTE_CAB_TABELA
    # Cada rótulo medido na COLUNA DELE, e o menor resultado vale para todos.
    # Medir tudo contra a coluna mais estreita — que era como estava — punha
    # "Técnicos" (coluna de 82 pt) no mesmo aperto de "Esquerda" (28 pt) e
    # derrubava o cabeçalho inteiro para 5,5 pt.
    _medir = [("Dia", w_real[0]), ("Técnicos", w_real[1]),
              ("Médico", w_corr[0]), ("Data da", w_corr[1]),
              ("Correção", w_corr[1])]
    _medir += [(PORTAL_ISO_CURTO[n], w_iso) for _s, n in PORTAL_ISO]
    _medir += [(ln, larg) for (linhas_rot, _l), larg in zip(PORTAL_FINAIS, w_fim)
               for ln in linhas_rot]
    cab = min(_tam_uniforme(t.c, [txt], larg, font="Helvetica-Bold",
                            teto=_FONTE_CAB_TABELA)
              for txt, larg in _medir)

    def rotulo(x, y, w, h, linhas, negrito=True, size=cab):
        """Um rótulo de coluna centrado, em uma a três linhas.

        NEGRITO por padrão: é a convenção das tabelas da ficha (pág. 1 e 2), e
        aqui pesa mais — o cabeçalho é lido de relance, com o paciente na mesa,
        para saber em que coluna se está escrevendo.
        """
        fonte = "Helvetica-Bold" if negrito else "Helvetica"
        linhas = [l for l in linhas if l]
        passo = size + 1.5
        y_ini = y + (h - len(linhas) * passo) / 2
        for i, ln in enumerate(linhas):
            t.txt(x, y_ini + i * passo, ln, font=fonte, size=size, align="c",
                  w=w, h=passo)

    # Coluna do número: o cabeçalho ocupa as três faixas de uma vez.
    # BRANCO nos cabeçalhos, como as tabelas das págs. 1 e 2 — e como esta
    # folha já era. O cinza da ficha é do quadro GANTRY e dos diagramas, não
    # da grade que se preenche.
    t.ret(x0, ytab, w_num, hcab, fill=white)
    rotulo(x0, ytab, w_num, hcab, ("Portal", "nº"), negrito=True, size=grupo)
    x = x0 + w_num

    # Os nomes de subcoluna vêm como TUPLA de linhas, como os finais: "Data da
    # Correção" não cabe deitada numa coluna de data, e encolher a fonte só
    # dela deixaria uma palavra menor no meio do cabeçalho — parece defeito de
    # impressão, e é o rótulo de uma coluna que o médico assina.
    for titulo, larguras, nomes in (
            ("Realizado", w_real, (("Dia",), ("Técnicos",))),
            ("Corrigido", w_corr, (("Médico",), ("Data da", "Correção")))):
        wg = sum(larguras)
        t.ret(x, ytab, wg, h_grp, fill=white)
        t.txt(x, ytab, titulo, font="Helvetica-Bold", size=grupo, align="c",
              w=wg, h=h_grp)
        for j, (nome, wj) in enumerate(zip(nomes, larguras)):
            xc = x + sum(larguras[:j])
            t.ret(xc, ytab + h_grp, wj, h_sign + h_rot)
            rotulo(xc, ytab + h_grp, wj, h_sign + h_rot, nome)
        x += wg

    # Grupo "Correções ISO (cm)": a linha dos SINAIS fica entre o título e o
    # nome da direção, e não junto do nome — é ela que diz para que lado o
    # número positivo empurra o paciente, e vale para a coluna inteira.
    wg_iso = 6 * w_iso
    t.ret(x, ytab, wg_iso, h_grp, fill=white)
    t.txt(x, ytab, "Correções ISO (cm)", font="Helvetica-Bold", size=grupo,
          align="c", w=wg_iso, h=h_grp)
    for j, (sinal, nome) in enumerate(PORTAL_ISO):
        xc = x + j * w_iso
        t.ret(xc, ytab + h_grp, w_iso, h_sign, fill=white)
        t.txt(xc, ytab + h_grp, sinal, font="Helvetica-Bold", size=grupo + 1,
              align="c", w=w_iso, h=h_sign)
        t.ret(xc, ytab + h_grp + h_sign, w_iso, h_rot)
        rotulo(xc, ytab + h_grp + h_sign, w_iso, h_rot,
               (PORTAL_ISO_CURTO.get(nome, nome),))
    x += wg_iso

    for (linhas_rot, _larg), wj in zip(PORTAL_FINAIS, w_fim):
        t.ret(x, ytab, wj, hcab)
        rotulo(x, ytab, wj, hcab, linhas_rot)
        x += wj

    # Linhas 1..10. O número em cinza, como o cabeçalho: a coluna é rótulo de
    # linha, não campo de preencher.
    todas = w_real + w_corr + [w_iso] * 6 + w_fim
    for r in range(n_linhas):
        yr = ytab + hcab + r * hlin
        t.ret(x0, yr, w_num, hlin, fill=white)
        t.txt(x0, yr, str(r + 1), font="Helvetica-Bold", size=_FONTE_VAL_TABELA,
              align="c", w=w_num, h=hlin)
        xx = x0 + w_num
        for wj in todas:
            t.ret(xx, yr, wj, hlin)
            xx += wj
    t.moldura(x0, ytab, W - 2 * M, hcab + n_linhas * hlin)


def _titulo_drr(ds, titulo_salvo: str = "", planos=None) -> str:
    """'DRR - <Portal>' com o nome do portal; no Histórico usa o título salvo.

    ``planos`` são os RT Plans do caso: com eles o nome sai INTEIRO, do feixe de
    setup, em vez do rótulo de dezesseis caracteres da imagem (ver
    ``dicom_rt.rotulo_drr_setup``). Sem nada, 'DRR'.
    """
    if titulo_salvo:
        return titulo_salvo
    if ds is not None:
        import re
        from isocentro.dicom import dicom_rt
        nome = re.sub(r"^\s*PORTAL", "Portal",
                      dicom_rt.rotulo_drr_setup(ds, planos), flags=re.IGNORECASE)
        if nome:
            return f"DRR - {nome}"
    return "DRR"


def _paginas_conferencia_600cd(c: canvas.Canvas, dados: dict,
                               recursos: dict | None) -> None:
    """Anexa (SOMENTE para o 600CD) os DRRs de setup e a folha de portais.

    ``recursos["drrs"]`` é a LISTA de RT Images (datasets, com DICOM); no Histórico
    vêm as ``recursos["drrs_png"]`` (PNGs prontos) e ``recursos["drrs_titulos"]``.
    ``recursos["planos_ds"]``, quando vem, é o que dá o nome INTEIRO do portal.
    Uma página de DRR por portal; a folha de portais sempre sai para o 600CD.
    """
    maq = constantes.identificar_maquina(dados.get("maquina", ""))
    if not maq or maq.chave != "600CD":
        return
    drrs_png = (recursos or {}).get("drrs_png") or []    # PNGs prontos (alinhados)
    titulos = (recursos or {}).get("drrs_titulos") or []
    # Fonte única de itens (png, título, dataset), na MESMA ordem, para não parear
    # listas de tamanhos diferentes: com PNGs prontos usa-os (já casados com os
    # títulos); senão renderiza da lista de datasets.
    if drrs_png:
        itens = [(png, titulos[i] if i < len(titulos) else "", None)
                 for i, png in enumerate(drrs_png)]
    else:
        itens = [(None, "", ds) for ds in ((recursos or {}).get("drrs") or [])]
    for png, titulo, ds in itens:
        if png is None and ds is not None:
            try:
                from isocentro.papel import drr as _drr
                png = _drr.render_drr(ds)
            except Exception:  # noqa: BLE001 — a folha de portais ainda sai
                _LOG.exception("Falha ao renderizar um DRR de setup")
        if not png:
            continue
        pagina_drr(c, dados, png,
                   _titulo_drr(ds, titulo, (recursos or {}).get("planos_ds")))
        c.showPage()
    pagina_portal_checagem(c, dados)
    c.showPage()
    c.setPageSize(landscape(A4))


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------


def gerar_ficha(dados: dict, store: dict, recursos: dict | None = None,
                replan: int = 0, dose_replan: float = 0) -> bytes:
    """Monta o PDF completo da ficha e devolve os bytes.

    ``recursos`` (opcional) carrega a TC completa e os datasets RS/RD para a
    página 1 (cortes + DVH). Sem ele, o PDF começa na ficha (página 2).
    ``replan``/``dose_replan``: replanejamento (ver ``pagina_fracoes``).
    """
    buffer = io.BytesIO()
    c = rodape.em_todas(canvas.Canvas(buffer, pagesize=landscape(A4)))
    _meta(c, dados, "Ficha Técnica")
    if recursos and recursos.get("ct") is not None:
        c.setPageSize(portrait(A4))
        pagina_cortes_dvh(c, dados, recursos)
        c.showPage()
        c.setPageSize(landscape(A4))
    embutido = pagina_ficha(c, dados, store, replan=replan, dose_replan=dose_replan)
    c.showPage()
    if not embutido:
        pagina_fracoes(c, dados, store, replan=replan, dose_replan=dose_replan)
        c.showPage()
    _anexar_registro_sus(c, dados, int(dados.get("rx_fracoes")
                                       or store.get("RP", {}).get("num_fracoes") or 0))
    _paginas_conferencia_600cd(c, dados, recursos)
    c.save()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Regeneração da ficha a partir do registro JSON (sem DICOM)
# ---------------------------------------------------------------------------


def _pagina_cortes_dvh_arquivada(c: canvas.Canvas, dados: dict,
                                 cortes_png: bytes | None, dvh_png: bytes | None):
    """Página 1 (retrato) reconstruída a partir dos PNGs salvos: cortes + DVH.

    Usa o helper ``_img`` (origem no topo-esquerda) para posicionar corretamente,
    igual à página 1 normal.
    """
    W, H = portrait(A4)
    c.setPageSize((W, H))
    t = Tela(c, W, H)
    M = 22
    _logo(c, M, H - 72, 148, 58, maquina=dados.get("maquina"))
    _w = W - 2 * M
    t.txt(M, 14, "Cortes Ortogonais e DVH", font="Helvetica-Bold", size=14, h=20, align="c", w=_w)
    # Nome, NASCIMENTO e ID — o MESMO cabeçalho de ``_pagina_cortes``. Esta é a
    # folha reconstruída dos PNGs salvos (ficha reaberta para reimprimir), e a
    # DDN tinha ficado só na outra: o mesmo paciente saía com um cabeçalho na
    # primeira impressão e outro na reimpressão. Quem confere não sabe de qual
    # caminho a folha veio — os dois têm de imprimir igual.
    t.txt(M, 33, dados.get("pac_nome", ""), size=10, align="c", w=_w)
    t.txt(M, 46, dados.get("pac_nascimento", ""), size=10, align="c", w=_w)
    t.txt(M, 59, dados.get("pac_registro", ""), size=10, align="c", w=_w)

    y0 = 78
    gap = 10
    # Cortes ocupam ~60% da altura útil (topo); DVH abaixo.
    h_util = H - y0 - M
    h_cortes = h_util * 0.60
    h_dvh = h_util - h_cortes - gap
    if cortes_png:
        _img(c, cortes_png, M, y0, _w, h_cortes, H)
    else:
        t.ret(M, y0, _w, h_cortes)
        t.txt(M, y0 + h_cortes / 2, "Imagem de cortes não disponível.",
              size=10, align="c", w=_w)
    y_dvh = y0 + h_cortes + gap
    if dvh_png:
        _img(c, dvh_png, M, y_dvh, _w, h_dvh, H)
    else:
        t.ret(M, y_dvh, _w, h_dvh)
        t.txt(M, y_dvh + h_dvh / 2, "DVH não disponível.", size=9, align="c", w=_w)


def gerar_ficha_arquivada(dados: dict, store: dict,
                          imagem_png: bytes | None = None,
                          dvh_png: bytes | None = None,
                          drrs_png: list | None = None,
                          replan: int = 0, dose_replan: float = 0,
                          drrs_titulos: list | None = None) -> bytes:
    """Remonta o PDF da ficha a partir dos dados salvos no registro JSON.

    Reaproveita ``pagina_ficha`` e ``pagina_fracoes``; como não há TC/RS/RD, a
    1ª página (cortes + DVH) é reconstruída a partir dos PNGs salvos, quando
    disponíveis.
    """
    buffer = io.BytesIO()
    c = rodape.em_todas(canvas.Canvas(buffer, pagesize=landscape(A4)))
    _meta(c, dados, "Ficha Técnica")
    if imagem_png or dvh_png:
        _pagina_cortes_dvh_arquivada(c, dados, imagem_png, dvh_png)
        c.showPage()
        c.setPageSize(landscape(A4))
    embutido = pagina_ficha(c, dados, store, replan=replan, dose_replan=dose_replan)
    c.showPage()
    if not embutido:
        pagina_fracoes(c, dados, store, replan=replan, dose_replan=dose_replan)
        c.showPage()
    _anexar_registro_sus(c, dados, int(dados.get("rx_fracoes")
                                       or store.get("RP", {}).get("num_fracoes") or 0))
    # Reimpressão de 600CD: os DRRs vêm dos PNGs salvos no registro (quando há);
    # a folha de portais (estática) sai de qualquer forma.
    _paginas_conferencia_600cd(c, dados, {"drrs_png": drrs_png or [],
                                          "drrs_titulos": drrs_titulos or []})
    c.save()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Ficha multi-plano — DVH/imagem SOMA ou INDIVIDUAL
# ---------------------------------------------------------------------------


def _dvh_png(recursos: dict) -> bytes | None:
    """PNG do DVH de um plano (rs + rd das ``recursos``), ou None."""
    rs = recursos.get("rs")
    rd = recursos.get("rd")
    if rs is None or rd is None:
        return None
    try:
        from isocentro.desenho import grafico_dvh
        from isocentro.dicom import dvh
        nomes = (_ordem_do_dvh(rs, recursos["estruturas_dvh"]) if recursos.get("estruturas_dvh")
                 else _estruturas_para_dvh(rs))
        curvas = dvh.calcular_dvh(rd, rs, nomes)
        if not curvas:
            _LOG.warning("DVH sem curva nenhuma (estruturas: %s)", nomes)
            return None
        return grafico_dvh.plotar_dvh(curvas, "")
    except Exception:  # noqa: BLE001
        # A ficha segue sem o DVH (o papel diz "DVH não disponível."), mas o
        # motivo fica no log. Em 22/10/2026 a regressão do papel pegou o TC6
        # saindo sem DVH uma vez em seis dentro da suíte, e nunca sozinha: com
        # a exceção engolida calada, não havia o que investigar.
        _LOG.warning("DVH não gerado", exc_info=True)
        return None


def _dose_ref_total(planos: list, grupos_dose: list | None = None) -> float:
    """100% da dose combinada (Gy): a maior prescrição ACUMULADA entre os planos.

    Dentro de um grupo de "Somar dose" as prescrições somam (fase → boost, mesma
    região); entre grupos — e entre planos sem grupo — vale a MAIOR, que é a dose
    que algum ponto do paciente de fato recebe. Somar tudo tratava mama e FSC
    como se a dose se acumulasse no mesmo alvo, e o colorwash da combinada saía
    pela metade (ver ``gui._dose_prescrita_total``, a mesma regra na tela).

    Usa ``recursos["dose_ref"]`` (posto pelo app, com a edição do formulário) e,
    na falta dele, a prescrição do RT Plan. Zero quando nenhum plano tem
    prescrição: aí o colorwash cai no máximo da grade, como antes.
    """
    def _presc(p) -> float:
        ref = (p.get("recursos") or {}).get("dose_ref")
        if not ref:
            ref = (p.get("dados") or {}).get("rx_dose_total") \
                or p.get("store", {}).get("RP", {}).get("dose_total")
        try:
            return float(ref or 0.0)
        except (TypeError, ValueError):
            return 0.0

    total, agrupados = 0.0, set()
    for g in (grupos_dose or []):
        membros = [i for i in g if 0 <= i < len(planos)]
        if len(membros) >= 2:
            agrupados.update(membros)
            total = max(total, sum(_presc(planos[i]) for i in membros))
    for i, p in enumerate(planos):
        if i not in agrupados:
            total = max(total, _presc(p))
    return total


def _pagina1_soma(planos: list, grupos_dose: list | None = None) -> tuple:
    """Cortes (montagem) + DVH combinando a dose SOMA de todos os planos.

    Todos os planos compartilham a TC. A base da montagem — cortes escolhidos,
    estruturas marcadas e 3D — é o plano ATIVO no app (``recursos["_ativo"]``):
    é a visão que o usuário ajustou na tela, e é ela que ele espera ver na
    ficha. Sem plano ativo no conjunto (a aba aberta pode ter ficado de fora da
    ficha separada), cai no primeiro. Devolve ``(cortes_png, dvh_png)``.
    """
    from isocentro.dicom import ct_series
    from isocentro.dicom import dose3d
    base_p = next((p for p in planos if (p.get("recursos") or {}).get("_ativo")),
                  planos[0])
    base = base_p["recursos"]
    ct = base.get("ct")
    rds = [p["recursos"].get("rd") for p in planos if p["recursos"].get("rd") is not None]
    if ct is None or not rds:
        # Sem TC/dose para somar: cai para o plano-base.
        return montar_imagem_pagina1(base_p["dados"], base), _dvh_png(base)

    soma = dose3d.somar_rds(rds)
    # 100% da dose combinada: ver _dose_ref_total. Não pode ser o ponto quente
    # da soma (o limiar da faixa em % subiria sozinho e o colorwash da
    # combinada sairia MENOR que o de um plano só), nem a soma cega das
    # prescrições (regiões vizinhas não acumulam dose no mesmo alvo).
    dose_grade = ct_series.tupla_dose(
        soma, dose_ref=_dose_ref_total(planos, grupos_dose))

    # Cortes com isodose da dose somada (sem cache). Na visão combinada as
    # estruturas e o 3D vêm da RS unificada — a mesma que a tela desenha.
    rec_cortes = {k: v for k, v in base.items() if k != "_pngs_cortes"}
    rec_cortes["dose_grade"] = dose_grade
    if base.get("rs_soma") is not None:
        rec_cortes["rs"] = base["rs_soma"]
    cortes_png = montar_imagem_pagina1(base_p["dados"], rec_cortes)

    # DVH combinado: união das estruturas selecionadas, dose somada.
    dvh_png = None
    rs = rec_cortes.get("rs")
    if rs is not None:
        try:
            from isocentro.desenho import grafico_dvh
            from isocentro.dicom import dvh
            nomes: list = []
            for p in planos:
                for n in (p["recursos"].get("estruturas_dvh") or []):
                    if n not in nomes:
                        nomes.append(n)
            nomes = _ordem_do_dvh(rs, nomes) if nomes else _estruturas_para_dvh(rs)
            curvas = dvh.calcular_dvh_grade(soma, rs, nomes)
            dvh_png = grafico_dvh.plotar_dvh(curvas, "") if curvas else None
        except Exception:  # noqa: BLE001
            dvh_png = None
    return cortes_png, dvh_png


def _ordem_planos_ficha(planos: list, ordem_planos: list | None) -> list:
    """Ordem dos planos nas páginas 2 e 3 (índices de ``planos``).

    ``ordem_planos`` (do agendamento, definida arrastando os chips) tem
    prioridade; se ausente ou inválida, cai na ordem por número do rótulo
    (fase antes de boost). É esta ordem que dita Fase, cores e colunas — e é
    SEPARADA da ordem dos cortes (que segue as abas).
    """
    from isocentro.dominio import agendamento as ag
    n = len(planos)
    if ordem_planos:
        vista = [i for i in ordem_planos if isinstance(i, int) and 0 <= i < n]
        # Completa com os que faltarem (robustez) preservando a ordem por número.
        if len(set(vista)) == n:
            return list(dict.fromkeys(vista))

    def _rot(p):
        rp = p["store"].get("RP", {})
        return rp.get("rotulo_plano") or rp.get("nome_plano") or ""
    return ag.ordem_por_numero([_rot(p) for p in planos])


def gerar_ficha_multiplano(planos: list, modo: str = "individual",
                           sequencia: list | None = None,
                           rotulos: list | None = None,
                           planos_ficha: list | None = None,
                           replan: int = 0, dose_replan: float = 0,
                           ordem_planos: list | None = None,
                           grupos_dose: list | None = None) -> tuple:
    """Monta a ficha de múltiplos planos.

    Devolve ``(pdf_bytes, [png_cortes], [png_dvh])`` — as duas listas paralelas,
    um item por plano, para persistir no registro e reusar na regeração.

    ``planos``: lista de ``{"dados", "store", "recursos"}`` (um por plano).
    ``modo``: ``"individual"`` (uma página de cortes+DVH por plano), ``"soma"``
    (uma combinando TODOS) ou ``"personalizado"`` (uma combinando só os planos
    de ``planos_ficha``, por índice).
    ``sequencia`` (agendamento): se dado, a página 3 é UM mapa de frações
    combinado (na ordem do agendamento); senão, uma por plano. Com um único
    plano (ficha separada), sai a página clássica de plano único.
    ``ordem_planos``: ordem dos planos nas págs 2 e 3 (arrastando os chips do
    agendamento). Sem ela, ordena por número do rótulo.
    ``grupos_dose``: listas de índices de plano cuja dose SOMA na coluna Dose da
    pág. 3 (planos sequenciais da mesma região). Fora deles, cada plano acumula
    a sua própria dose, como sempre.
    """
    buffer = io.BytesIO()
    c = rodape.em_todas(canvas.Canvas(buffer, pagesize=landscape(A4)))
    _meta(c, planos[0]["dados"], "Ficha Técnica")
    imagens: list = []
    dvhs: list = []   # paralela a 'imagens': DVH de cada plano, p/ regeração

    # Ordem das págs 2/3 = a escolhida no agendamento (chips) ou, na falta, por
    # número do rótulo. Fase, cores e colunas seguem esta ordem; os cortes e as
    # listas devolvidas (persistência) ficam na ordem original (abas).
    _ordem = _ordem_planos_ficha(planos, ordem_planos)
    _pos = {old: new for new, old in enumerate(_ordem)}   # índice antigo → novo
    planos_ord = [planos[i] for i in _ordem]
    rotulos_ord = [rotulos[i] for i in _ordem] if rotulos else None
    sequencia_ord = ([[_pos[i] for i in dia if i in _pos] for dia in sequencia]
                     if sequencia else None)
    grupos_dose_ord = [sorted(_pos[i] for i in g if i in _pos)
                       for g in (grupos_dose or [])]
    grupos_dose_ord = [g for g in grupos_dose_ord if len(g) >= 2]

    # ── Seção de cortes + DVH ────────────────────────────────────────────────
    if modo in ("soma", "personalizado"):
        sub = planos
        restantes = []   # planos FORA da combinação → uma página individual cada
        if modo == "personalizado" and planos_ficha:
            idx_sub = [i for i in planos_ficha if 0 <= i < len(planos)]
            if idx_sub:
                sub = [planos[i] for i in idx_sub]
                restantes = [p for i, p in enumerate(planos) if i not in set(idx_sub)]
        cortes_png, dvh_png = _pagina1_soma(sub, grupos_dose)
        if cortes_png or dvh_png:
            imagens.append(cortes_png)
            dvhs.append(dvh_png)
            _pagina_cortes_dvh_arquivada(c, planos[0]["dados"], cortes_png, dvh_png)
            c.showPage(); c.setPageSize(landscape(A4))
        # Planos de outra TC (fora do subconjunto personalizado) mantêm os seus
        # próprios cortes — senão sumiriam da ficha.
        for p in restantes:
            cp = p.get("cortes_salvo") or montar_imagem_pagina1(p["dados"], p["recursos"])
            dp = p.get("dvh_salvo") or _dvh_png(p["recursos"])
            if cp or dp:
                imagens.append(cp)
                dvhs.append(dp)
                _pagina_cortes_dvh_arquivada(c, p["dados"], cp, dp)
                c.showPage(); c.setPageSize(landscape(A4))
    else:
        # Uma página de cortes+DVH por plano. Renderiza cada uma UMA vez.
        # Arquivado: usa os PNGs salvos; senão renderiza do DICOM.
        pgs = []
        for p in planos:
            cortes_png = p.get("cortes_salvo") or montar_imagem_pagina1(p["dados"], p["recursos"])
            dvh_png = p.get("dvh_salvo") or _dvh_png(p["recursos"])
            if cortes_png or dvh_png:
                pgs.append((p, cortes_png, dvh_png))
        # Folha em branco após cada página de cortes, exceto a última: no
        # impresso frente-e-verso cada plano ocupa uma folha (verso em branco),
        # e a Ficha Técnica (página seguinte) cai no verso da última.
        for k, (p, cortes_png, dvh_png) in enumerate(pgs):
            imagens.append(cortes_png)
            dvhs.append(dvh_png)
            _pagina_cortes_dvh_arquivada(c, p["dados"], cortes_png, dvh_png)
            c.showPage(); c.setPageSize(landscape(A4))
            if k + 1 < len(pgs):
                c.showPage(); c.setPageSize(landscape(A4))   # folha em branco

    # Sequência do mapa combinado (só multi-plano) — calculada ANTES da página 2
    # para que ela possa embutir o mapa curto como faixa horizontal.
    seq = rot = None
    if len(planos) >= 2:
        rot = rotulos_ord or [f"Plano {i + 1}" for i in range(len(planos_ord))]
        seq = sequencia_ord
        if not seq:
            # Sem agendamento explícito: simultâneo (todos os planos em toda fração).
            nfr = max((int(p["store"].get("RP", {}).get("num_fracoes") or 0)
                       for p in planos_ord), default=0)
            seq = [list(range(len(planos_ord))) for _ in range(nfr)]

    # ── Corpo: página 2 (+ página 3 de frações só se ela não couber lá) ──────
    if len(planos) == 1:
        # Ficha de UM plano só (ex.: separada de um caso com vários): usa a
        # página clássica de plano único — a tabela de uma linha só e a Fase
        # colorida não fazem sentido aqui, e ela já embute o mapa na pág. 2 nos
        # tratamentos curtos: um fígado de 3 frações sai numa folha só, em vez
        # de uma página 3 quase vazia.
        p0 = planos[0]
        embutido = pagina_ficha(c, p0["dados"], p0["store"],
                                replan=replan, dose_replan=dose_replan)
        c.showPage()
        if not embutido:
            pagina_fracoes(c, p0["dados"], p0["store"],
                           replan=replan, dose_replan=dose_replan)
            c.showPage()
        total_sus = int(p0["dados"].get("rx_fracoes")
                        or p0["store"].get("RP", {}).get("num_fracoes") or 0)
    else:
        # A tabela de campos da pág. 2 só tem N_CAMPOS colunas. Passando disso,
        # a ficha sai em blocos "pág. 2 + pág. 3", cada um com os planos INTEIROS
        # que couberem (ver _grupos_por_campos) — o resto vai para o bloco
        # seguinte. Observações são do CASO: o mesmo texto em todas as páginas 2.
        grupos = _grupos_por_campos(planos_ord)
        obs = _obs_dos_planos(planos_ord, rot)
        dose_plano = _dose_por_plano(planos_ord, seq)
        for g, grupo in enumerate(grupos):
            planos_g = [planos_ord[i] for i in grupo]
            rot_g = [rot[i] for i in grupo] if rot else None
            if len(grupos) == 1:
                seq_g, num_g = seq, None
            else:
                seq_g, num_g = _sequencia_do_grupo(seq, grupo)
            gd_g, acc_g = _grupos_dose_do_bloco(grupos_dose_ord, grupo,
                                                dose_plano)
            # O replanejamento (frações já tratadas antes do 1º plano) é do
            # começo do tratamento: só o primeiro bloco leva as linhas rasuradas.
            rep_g = replan if g == 0 else 0
            embutido = pagina_ficha_multi(
                c, planos_g, sequencia=seq_g, rotulos=rot_g, replan=rep_g,
                dose_replan=dose_replan, base=grupo[0], obs=obs,
                numeros=num_g, ultima=len(seq or []),
                grupos_dose=gd_g, acc_ini=acc_g)
            c.showPage()
            if not embutido:
                pagina_fracoes_multi(c, planos_g, seq_g, rot_g, replan=rep_g,
                                     dose_replan=dose_replan, base=grupo[0],
                                     numeros=num_g, ultima=len(seq or []),
                                     grupos_dose=gd_g, acc_ini=acc_g)
                c.showPage()
        total_sus = len(seq)

    # Registro de Tratamento (SUS): pág. 4 e 5, quando o paciente é SUS.
    _anexar_registro_sus(c, planos[0]["dados"], total_sus)

    # DRRs de setup + folha de portais (só 600CD) — os DRRs são do caso, então
    # basta o primeiro plano que os trouxer (datasets ou PNGs salvos) nos recursos.
    rec_drr = next((p.get("recursos") for p in planos
                    if (p.get("recursos") or {}).get("drrs")
                    or (p.get("recursos") or {}).get("drrs_png")), None)
    _paginas_conferencia_600cd(c, planos[0]["dados"], rec_drr)

    c.save()
    return buffer.getvalue(), imagens, dvhs


# ---------------------------------------------------------------------------
# Imagem dos cortes (Axial | 3D / Coronal | Sagital) como PNG — registro JSON
# ---------------------------------------------------------------------------


def montar_imagem_pagina1(dados: dict, recursos: dict) -> bytes | None:
    """Monta um PNG único com a grade 2×2 de cortes, sem DVH nem texto.

    Layout: [Axial | 3D] / [Coronal | Sagital]. Reaproveita os cortes já
    renderizados pelo PDF (``recursos["_pngs_cortes"]``) quando disponíveis, e o
    ``png_3d`` do app. Devolve ``None`` quando não há TC.
    """
    ct = recursos.get("ct")
    if ct is None:
        return None

    from PIL import Image, ImageDraw

    rs = recursos.get("rs")

    def _abrir(png):
        if not png:
            return None
        try:
            return Image.open(io.BytesIO(png)).convert("RGB")
        except Exception:  # noqa: BLE001
            return None

    # Reusa os cortes renderizados pelo PDF; só re-renderiza se ausentes.
    pngs = recursos.get("_pngs_cortes")
    if not pngs:
        mostrar_iso = recursos.get("mostrar_isodose", True)
        iso_range = recursos.get("isodose_range", (50.0, 100.0))
        mostrar_est = recursos.get("mostrar_estruturas", True)
        est_vis = recursos.get("estruturas_visiveis")

        def _idx(plano):
            v = recursos.get(f"idx_{plano.lower()}")
            return v if v is not None else ct.indice_central(plano)

        pngs = {p: corte.renderizar_corte(ct, p, _idx(p), janela="Mama", rs=rs,
                                          rd=recursos.get("rd"), mostrar_isodose=mostrar_iso,
                                          isodose_range=iso_range, mostrar_estruturas=mostrar_est,
                                          estruturas_visiveis=est_vis,
                                          dose_grade=recursos.get("dose_grade"),
                                          dose_ref=recursos.get("dose_ref"))
                for p in ("Axial", "Coronal", "Sagital")}

    img_axial   = _abrir(pngs.get("Axial"))
    img_coronal = _abrir(pngs.get("Coronal"))
    img_sagital = _abrir(pngs.get("Sagital"))

    png3d = recursos.get("png_3d")
    if png3d is None and rs is not None:
        try:
            from isocentro.desenho import corpo
            png3d = corpo.renderizar_corpo(rs)
        except Exception:  # noqa: BLE001
            png3d = None
    img_3d = _abrir(png3d)

    # ── Composição (grade 2×2, sem cabeçalho nem DVH) ────────────────────────
    M = 20
    gap = 12
    cell_w = 460
    cell_h = int(cell_w * 0.76)

    W = 2 * cell_w + gap + 2 * M
    H = 2 * cell_h + gap + 2 * M

    fundo = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(fundo)

    def _colar(img, x, y, w, h):
        if img is None:
            draw.rectangle([x, y, x + w, y + h], outline="black")
            return
        cp = img.copy()
        cp.thumbnail((w, h), Image.LANCZOS)
        ox = x + (w - cp.width) // 2
        oy = y + (h - cp.height) // 2
        fundo.paste(cp, (ox, oy))

    x_esq = M
    x_dir = M + cell_w + gap
    y1 = M
    y2 = y1 + cell_h + gap
    _colar(img_axial,   x_esq, y1, cell_w, cell_h)
    _colar(img_3d,      x_dir, y1, cell_w, cell_h)
    _colar(img_coronal, x_esq, y2, cell_w, cell_h)
    _colar(img_sagital, x_dir, y2, cell_w, cell_h)

    buf = io.BytesIO()
    fundo.save(buf, format="PNG")
    return buf.getvalue()
