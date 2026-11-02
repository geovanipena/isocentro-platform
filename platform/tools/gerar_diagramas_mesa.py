"""Gera os diagramas de deslocamento da mesa impressos no cabeçalho da ficha.

Saída: ``assets/table_TB.png`` (TrueBeam/VitalBeam/Synergy) e
``assets/table_serie_c.png`` (600CD/6EX) — os dois arquivos que
``ficha_pdf._cabecalho`` desenha conforme o ``grupo_mesa`` da máquina
(ver ``constantes.MAQUINAS``).

O desenho é a ROSETA de eixos do console: três eixos (lateral, longitudinal e
vertical), o sinal que o console mostra em cada sentido e a faixa de números
correspondente, mais o sentido de rotação da mesa. A mesa em si saiu do desenho
— num slot de 124×68 pt a caixa em perspectiva só roubava espaço dos números,
que são a informação que o técnico procura.

O que muda entre as duas máquinas:
  · vertical — o console da série C inverte o sinal (ver
    ``Maquina.mesa_vert_invertida``): sobe negativo, desce positivo;
  · números negativos — a série C conta de trás para frente (…,998,999) no
    lateral e no vertical; o longitudinal segue em (…,−2,−1) nas duas;
  · rotação — a série C usa a escala Varian (360 − IEC), então os 90° e 270°
    trocam de lado (ver ``dicom_rt._mesa_angulo_console``).

Rodar (a partir da raiz do projeto):  python tools/gerar_diagramas_mesa.py
"""
from __future__ import annotations

import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                        # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch  # noqa: E402

# Tamanho do slot no cabeçalho da ficha (ver ``ficha_pdf._cabecalho``). Desenhar
# JÁ nessa proporção é o que dá tamanho aos números: as imagens antigas eram
# quase quadradas e encolhiam para metade da largura disponível.
W, H = 124.0, 68.0

INK = "#26333B"     # grafite dos eixos
ACC = "#0F7B6C"     # teal dos sinais
NUM = INK           # texto dos números: mesma tinta dos eixos

CX, CY = 64.0, 39.0     # centro da roseta
LX, LY = 24.0, 12.0     # semi-eixos (o campo de raios é elíptico: a caixa é larga)
ANG_LONG = 45.0         # inclinação do eixo longitudinal
R_CHIP = 4.2
GAP_CHIP = 4.4          # da ponta da seta ao centro do chip
GAP_TXT = 2.6           # do chip ao texto

# Os números saem em duas COLUNAS alinhadas, e não colados em cada chip: assim a
# roseta fecha com as bordas retas, em vez de uma escadinha de textos.
X_ESQ = CX - LX - GAP_CHIP - R_CHIP - GAP_TXT
X_DIR = CX + LX + GAP_CHIP + R_CHIP + GAP_TXT

POS = "1,2,…"
NEG = "…,−2,−1"
NEG_C = "…,998,999"     # série C: o console conta de trás para frente

MAIS = "+"
MENOS = "−"

# Ponta esbelta: o triângulo cheio padrão fica pesado num desenho deste tamanho.
SETA = "<|-|>,head_length=0.42,head_width=0.21"
ESCALA_SETA = 6.4


def _ponta(ang: float) -> tuple[float, float, float, float]:
    """Ponta da seta e centro do chip para o raio no ângulo ``ang`` (graus)."""
    a = math.radians(ang)
    px, py = CX + LX * math.cos(a), CY + LY * math.sin(a)
    ux, uy = px - CX, py - CY
    n = math.hypot(ux, uy)
    return px, py, px + GAP_CHIP * ux / n, py + GAP_CHIP * uy / n


def _eixo(ax, ang: float):
    """Um eixo inteiro: seta de duas pontas passando pelo miolo.

    Devolve o centro do chip do lado negativo e o do lado positivo.
    """
    ax_, ay_, cxn, cyn = _ponta(ang + 180)
    bx, by, cxp, cyp = _ponta(ang)
    ax.add_patch(FancyArrowPatch(
        (ax_, ay_), (bx, by), arrowstyle=SETA, mutation_scale=ESCALA_SETA,
        lw=0.85, color=INK, shrinkA=0, shrinkB=0, joinstyle="miter"))
    return (cxn, cyn), (cxp, cyp)


def _chip(ax, xy: tuple[float, float], sinal: str) -> None:
    """Sinal do console. O '+' vem CHEIO e o '−' VAZADO — a distinção sobrevive
    a uma fotocópia em preto e branco, que a cor sozinha não garante."""
    x, y = xy
    cheio = sinal == MAIS
    ax.add_patch(Circle((x, y), R_CHIP, facecolor=ACC if cheio else "white",
                        edgecolor=ACC, lw=0.85, zorder=3))
    ax.text(x, y + 0.1, sinal, ha="center", va="center", zorder=4,
            color="white" if cheio else ACC, fontsize=7.0, fontweight="bold")


def _num(ax, xy: tuple[float, float], txt: str, onde: str) -> None:
    """Faixa de números na posição ``onde`` ('e', 'd', 'cima', 'baixo')."""
    x, y = xy
    d = R_CHIP + GAP_TXT
    pos = {"d": (X_DIR, y, "left", "center"), "e": (X_ESQ, y, "right", "center"),
           "cima": (x, y + d, "center", "bottom"),
           "baixo": (x, y - d, "center", "top")}[onde]
    ax.text(pos[0], pos[1], txt, ha=pos[2], va=pos[3], color=NUM, fontsize=4.1)


def desenhar(destino: str, vert_cima: str, num_vert_neg: str, num_lat_neg: str,
             rot_esq: str, rot_dir: str) -> str:
    """Escreve o PNG de uma máquina.

    ``vert_cima``   sinal que o console mostra ao SUBIR a mesa;
    ``num_vert_neg``/``num_lat_neg``  faixa negativa do vertical e do lateral;
    ``rot_esq``/``rot_dir``  ângulos de mesa nas pontas do arco de rotação.
    """
    fig = plt.figure(figsize=(W / 72.0, H / 72.0), dpi=600)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")

    # Lateral: negativo à esquerda, positivo à direita.
    esq, dir_ = _eixo(ax, 0)
    _chip(ax, esq, MENOS)
    _num(ax, esq, num_lat_neg, "e")
    _chip(ax, dir_, MAIS)
    _num(ax, dir_, POS, "d")

    # Longitudinal: a diagonal, positiva para cima/direita.
    tras, frente = _eixo(ax, ANG_LONG)
    _chip(ax, tras, MENOS)
    _num(ax, tras, NEG, "e")
    _chip(ax, frente, MAIS)
    _num(ax, frente, POS, "d")

    # Vertical: o de cima é o sinal da máquina; o de baixo, o oposto.
    baixo_s = MAIS if vert_cima == MENOS else MENOS
    num_cima = num_vert_neg if vert_cima == MENOS else POS
    num_baixo = POS if vert_cima == MENOS else num_vert_neg
    baixo, cima = _eixo(ax, 90)
    _chip(ax, cima, vert_cima)
    _num(ax, cima, num_cima, "cima")
    _chip(ax, baixo, baixo_s)
    _num(ax, baixo, num_baixo, "baixo")

    # Miolo (o isocentro, de onde os três eixos saem).
    ax.add_patch(Circle((CX, CY), 1.7, facecolor=INK, edgecolor="none", zorder=5))

    # Rotação da mesa.
    ax.add_patch(FancyArrowPatch((41, 8.0), (87, 8.0), arrowstyle=SETA,
                                 mutation_scale=ESCALA_SETA, lw=0.85, color=INK,
                                 connectionstyle="arc3,rad=0.24"))
    ax.text(37.5, 7.6, rot_esq, ha="right", va="center", color=INK,
            fontsize=4.4, fontweight="bold")
    ax.text(90.5, 7.6, rot_dir, ha="left", va="center", color=INK,
            fontsize=4.4, fontweight="bold")

    # Fundo transparente: o desenho pousa direto no branco do cabeçalho.
    fig.savefig(destino, transparent=True, dpi=600)
    plt.close(fig)
    return destino


def main(pasta: str) -> None:
    print(desenhar(os.path.join(pasta, "table_TB.png"),
                   vert_cima=MAIS, num_vert_neg=NEG, num_lat_neg=NEG,
                   rot_esq="270°", rot_dir="90°"))
    print(desenhar(os.path.join(pasta, "table_serie_c.png"),
                   vert_cima=MENOS, num_vert_neg=NEG_C, num_lat_neg=NEG_C,
                   rot_esq="90°", rot_dir="270°"))


if __name__ == "__main__":
    padrao = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "assets")
    main(sys.argv[1] if len(sys.argv) > 1 else padrao)
