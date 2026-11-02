"""O DVH desenhado: as curvas de ``dicom/dvh`` viram o PNG da ficha e da tela.

Separado do cálculo na R-58 (corte 3): o cálculo é dose como número e vai para
``rt/``; a cor de cada curva e o tamanho da legenda são decisão de quem imprime.
"""

from __future__ import annotations

import io

# Cores aproximadas do modelo, por nome de estrutura (em minúsculas). Só ÓRGÃOS
# aqui — o alvo tem regra própria, ver ``CORES_ALVO``.
CORES_PADRAO = {
    "reto": "#2E75B6",
    "femur e": "#548235",
    "femur d": "#C00000",
    "bexiga": "#7030A0",
}

# Família do ALVO. Duas decisões aqui, e nenhuma é estética:
#
# 1. Saiu do laranja do modelo (#ED7D31) para o teal da identidade do programa,
#    a pedido — o laranja não conversava com o resto da folha. É divergência
#    deliberada do modelo, não descuido.
#
# 2. São VÁRIOS tons da MESMA família, e não uma cor só, porque o casamento é
#    por substring: ``PTV``, ``PTV54``, ``PTV_boost`` e ``PTV_Mama_E`` caem
#    todos na regra do alvo. Com uma cor só, uma mama bilateral — que tem CINCO
#    alvos (PTV mama E, boost E, FSC E, mama D, boost D; ver ``capa_pdf``) —
#    saía com cinco curvas idênticas e a legenda com cinco nomes. A família
#    preserva a leitura "isto é alvo" e ainda separa um do outro.
#
# A ORDEM foi escolhida pelo caso comum, não pela escala. Os cinco tons vão de
# claro a quase preto, mas listá-los nessa sequência daria os dois mais
# parecidos justamente a quem tem DOIS alvos — que é a maioria das folhas. A
# ordem abaixo é a que deixa os primeiros tons o mais distantes possível em
# luminosidade: médio, claro, quase preto, brilhante, escuro. Cinco cobrem o
# pior caso conhecido (mama bilateral).
#
# Os valores estão CRUS aqui, e não como ``estilo.ACAO``, embora o primeiro
# seja a mesma cor: o ``ACAO`` troca no modo noite (#3FBFB6) e este gráfico vai
# para o PAPEL. Amarrar a cor impressa ao tema da tela faria a ficha sair de uma
# cor de manhã e de outra à noite.
CORES_ALVO = ["#0F7B7B", "#3FBFB6", "#063B3B", "#17A2A2", "#0A5252"]


def _e_alvo(nome: str) -> bool:
    return "ptv" in nome.lower()


def _cor(nome: str, idx: int, ordem_alvo: int = 0) -> str:
    """Cor da curva. ``ordem_alvo`` é a posição ENTRE OS ALVOS, não entre todas
    as estruturas: assim acrescentar um órgão de risco não remexe o tom dos
    PTVs, que é o que o físico já viu na folha anterior.
    """
    # O alvo é testado ANTES dos órgãos: num nome como "PTV reto" quem manda é
    # o alvo, senão ele sairia com a cor do órgão que está sendo poupado.
    if _e_alvo(nome):
        return CORES_ALVO[ordem_alvo % len(CORES_ALVO)]
    chave = nome.lower()
    for k, c in CORES_PADRAO.items():
        if k in chave:
            return c
    paleta = ["#264478", "#9E480E", "#636363", "#997300", "#43682B", "#000000"]
    return paleta[idx % len(paleta)]


# Proporção da vaga do DVH na página 1 da ficha (551 × 297 pt): desenhar já
# nela é o que garante que o gráfico ocupe a vaga inteira depois de escalado.
_FIG_L, _FIG_A = 7.2, 3.9      # polegadas
# Retângulo dos EIXOS na figura (esq., base, larg., alt.), em fração. O que sobra
# à direita é a faixa da legenda — e ela é FIXA: é o gráfico que manda no tamanho,
# não a lista de estruturas.
_CAIXA_EIXOS = (0.085, 0.135, 0.545, 0.835)
_FOLGA_LEGENDA = 0.02          # respiro entre os eixos e a legenda

# Corpos e nº de colunas que a legenda pode assumir, do mais legível para o menos.
_TAM_LEGENDA = (7.0, 6.5, 6.0, 5.5, 5.0, 4.5, 4.0)
_COLUNAS_LEGENDA = (1, 2, 3)


def _legenda_que_cabe(fig, ax, larg_pol: float, alt_pol: float):
    """Põe a legenda à direita dos eixos no MAIOR corpo que couber na faixa.

    Um caso de cabeça e pescoço traz 30+ estruturas, e a legenda de coluna única
    ficava mais alta que a figura inteira. Com ``bbox_inches="tight"`` no
    ``savefig``, era ela que definia o tamanho do PNG: o gráfico virava uma tira
    espremida num canto. Agora a faixa é fixa e quem se ajusta é a legenda —
    ganhando colunas e perdendo corpo até caber nela.
    """
    escolhida = None
    for tam in _TAM_LEGENDA:
        for ncol in _COLUNAS_LEGENDA:
            leg = ax.legend(fontsize=tam, ncol=ncol, loc="center left",
                            bbox_to_anchor=(1.0 + _FOLGA_LEGENDA, 0.5),
                            frameon=False, handlelength=1.1, handletextpad=0.4,
                            columnspacing=0.9, labelspacing=0.3, borderpad=0.0)
            bb = leg.get_window_extent(fig.canvas.get_renderer())
            if bb.width / fig.dpi <= larg_pol and bb.height / fig.dpi <= alt_pol:
                return leg
            escolhida = leg
    return escolhida   # nem no menor corpo coube: fica o mais compacto possível


def plotar_dvh(curvas: dict, titulo: str = "") -> bytes:
    """Gera o gráfico DVH (PNG em bytes) no estilo do modelo.

    O PNG tem SEMPRE o mesmo tamanho e a mesma proporção, com quantas estruturas
    forem: o gráfico ocupa a mesma área e só a legenda se acomoda (ver
    ``_legenda_que_cabe``).
    """
    # ``Figure`` direto, NÃO ``pyplot`` — mesma razão de ``corpo3d``: o registro
    # global do pyplot corrompia quando este gráfico e o corpo 3D (que roda numa
    # thread de fundo) eram desenhados ao mesmo tempo.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(_FIG_L, _FIG_A), dpi=150)
    FigureCanvasAgg(fig)
    ax = fig.add_axes(_CAIXA_EIXOS)
    alvos = 0
    for i, (nome, c) in enumerate(curvas.items()):
        cor = _cor(nome, i, alvos)
        alvos += _e_alvo(nome)
        ax.plot(c["dose"], c["volume"], color=cor, linewidth=1.3, label=nome)
    ax.set_xlabel("Dose [Gy]")
    ax.set_ylabel("Volume da Estrutura [%]")
    ax.set_xlim(left=0)
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 10))
    ax.tick_params(labelsize=7)
    ax.grid(True, linewidth=0.3, alpha=0.5)
    if titulo:
        ax.set_title(titulo, fontsize=9)

    esq, base, larg, alt = _CAIXA_EIXOS
    _legenda_que_cabe(fig, ax,
                      larg_pol=(1.0 - esq - larg - _FOLGA_LEGENDA * larg) * _FIG_L,
                      alt_pol=(1.0 - base * 0.5) * _FIG_A)

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()
