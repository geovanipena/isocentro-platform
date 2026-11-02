"""Rodapé "Impresso em …" — o mesmo no pé de toda página de todo PDF do serviço.

Mora fora do ``ficha_pdf`` e do ``capa_pdf`` porque os dois carimbam o mesmo
rodapé e nenhum importa o outro (mesmo motivo do ``estilo.py``). Não importa nada
do projeto.

O carimbo entra no ``showPage`` do canvas, e não em cada função de página: são
oito geradores de página espalhados (cortes+DVH, ficha, mapa de frações,
registro SUS, DRRs, folha de portais, alta e as duas folhas da capa), e uma
página nova nasceria sem ele. Assim, quem emite página ganha o rodapé de graça.

Antes disso a data saía como "Ficha confeccionada em … por …" no pé da folha 2
da capa e como "Impresso em …" em corpo 7/8 em ALGUMAS páginas da ficha — ora
solta na margem, ora dentro da caixa de Observações. É uma informação de
procedência, não conteúdo da folha: agora é miúda, cinza e sempre no mesmo lugar.
"""
from __future__ import annotations

from datetime import date

from reportlab.lib.colors import HexColor

TAMANHO = 5.5                    # miúdo: procedência não disputa com o formulário
COR = HexColor("#8C8C8C")
MARGEM_X = 14.0                  # a margem lateral das folhas
# Linha de base a 10 pt do pé — é onde o "Impresso em" da ficha já saía, dentro
# da faixa que as grades reservam (``ficha_pdf._MARGEM_INFERIOR``) e acima da
# área não-imprimível.
MARGEM_Y = 10.0


def texto(quando: date | None = None) -> str:
    return f"Impresso em {(quando or date.today()).strftime('%d/%m/%Y')}"


def carimbar(c) -> None:
    """Escreve o rodapé no pé da página CORRENTE do canvas ``c``."""
    c.saveState()
    # ZERA a transformação antes de escrever. O ``ficha_pdf`` desenha com a
    # origem no TOPO (a classe ``Tela`` inverte o eixo), e o carimbo entra pelo
    # ``showPage``, quando essa inversão ainda pode estar valendo: as
    # coordenadas de baixo para cima cairiam no lugar errado — ou fora do papel.
    # Sem isto, o rodapé aparecia em umas páginas e não em outras.
    try:
        c.resetTransforms()
    except Exception:  # noqa: BLE001 — canvas sem o método: segue como estava
        pass
    c.setFont("Helvetica", TAMANHO)
    c.setFillColor(COR)
    c.drawString(MARGEM_X, MARGEM_Y, texto())
    c.restoreState()


def em_todas(c):
    """Faz ``c`` carimbar o rodapé em toda página que emitir; devolve o ``c``.

    Embrulha o ``showPage`` da INSTÂNCIA — o canvas continua sendo um canvas do
    ReportLab para todo o resto, e quem gera a página não precisa saber de nada.
    """
    original = c.showPage

    def showPage():
        carimbar(c)
        original()

    c.showPage = showPage
    return c
