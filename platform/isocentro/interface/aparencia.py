"""Aparência do app: a folha global, o ícone, a paleta e a troca dia↔noite.

Separado de ``gui.py`` em 27/08/2026, quando aquele arquivo passou de 9 mil
linhas. Não confundir com ``estilo.py``: lá ficam as CORES (constantes que o
modo em vigor reescreve); aqui fica o que as aplica no Qt — e por isso este
módulo depende de ``QApplication``, que ``estilo.py`` de propósito não conhece.

O endereço antigo continua valendo: ``gui.py`` reimporta tudo o que está aqui,
porque ``gui.aplicar_modo`` é o nome que a suíte e o resto do programa já usam.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

from isocentro.interface.ajustes import ajustes
from isocentro.interface import estilo


def _ESTILO() -> str:
    """Folha global do app, montada no modo em vigor.

    Vale para todo widget que não tem folha própria — campos, listas, caixas de
    marcação, deslizadores, a barra de status. É FUNÇÃO e não constante porque
    a troca dia↔noite a refaz (ver ``estilo.pintar``); como texto fixo, ela
    congelaria as cores do import e seria a única superfície a não acompanhar.

    ``QAbstractItemView::indicator`` entrou em 24/09/2026: o indicador de item
    MARCÁVEL (``lst_estruturas`` e toda lista com ``ItemIsUserCheckable`` —
    ``capa``, ``controle_viewer``, ``posicionamento``, ``tratamento``,
    ``visualizador``) não tinha regra própria e caía no tema NATIVO do
    Windows no estado desmarcado: o quadradinho claro do Windows arrastava
    consigo um retângulo de fundo BRANCO cobrindo a linha inteira do item,
    mesmo com a paleta escura aplicada em tudo mais — achado num print real da
    lista de estruturas do DVH.
    """
    return f"""
QGroupBox {{
    font-weight: bold;
    color: {estilo.ACAO};
    border: 1px solid {estilo.BORDA};
    border-radius: 7px;
    margin-top: 18px;
    padding-top: 2px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    top: 2px;
    left: 10px;
    padding: 0 6px;
}}
QGroupBox * {{ font-weight: normal; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    border: 1px solid {estilo.BORDA};
    border-radius: 5px;
    padding: 3px 6px;
    background: {estilo.FUNDO_CAMPO};
    color: {estilo.TEXTO};
    selection-background-color: {estilo.SELECAO};
    selection-color: {estilo.SOBRE_SELECAO};
}}
QLineEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {estilo.ACAO};
}}
QLineEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {estilo.TEXTO_APAGADO};
    border-color: {estilo.BORDA_SUAVE};
}}
QListWidget, QTableWidget, QTextBrowser, QPlainTextEdit {{
    border: 1px solid {estilo.BORDA};
    border-radius: 5px;
    background: {estilo.FUNDO_CAMPO};
    color: {estilo.TEXTO};
    outline: none;
}}
QListWidget::item {{ padding: 3px 4px; border-radius: 4px; }}
QListWidget::item:hover {{ background: {estilo.ACAO_FUNDO}; }}
QListWidget::item:selected {{
    background: {estilo.ACAO_FUNDO};
    color: {estilo.ACAO};
}}
QHeaderView::section {{
    background: {estilo.FUNDO_BLOCO};
    color: {estilo.TEXTO_FRACO};
    border: none;
    border-bottom: 1px solid {estilo.BORDA};
    padding: 4px 6px;
    font-weight: 600;
}}

QCheckBox::indicator, QRadioButton::indicator, QAbstractItemView::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {estilo.BORDA_FORTE};
    border-radius: 3px;
    background: {estilo.FUNDO_CAMPO};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked,
QAbstractItemView::indicator:checked {{
    background: {estilo.ACAO};
    border-color: {estilo.ACAO};
}}
QRadioButton::indicator {{ border-radius: 7px; }}

QSlider::groove:horizontal {{
    height: 4px;
    background: {estilo.BORDA};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {estilo.ACAO};
    border: none;
    width: 13px; height: 13px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {estilo.ACAO_LINHA};
    border-radius: 2px;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle {{ background: {estilo.BORDA_FORTE}; border-radius: 5px; }}
QScrollBar::handle:hover {{ background: {estilo.ACAO_LINHA}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QStatusBar {{
    background: {estilo.FUNDO_FUNDO};
    color: {estilo.TEXTO_FRACO};
    border-top: 1px solid {estilo.BORDA};
    font-size: 11px;
    padding-left: 4px;
}}
QToolTip {{
    background: {estilo.FUNDO_BLOCO};
    color: {estilo.TEXTO};
    border: 1px solid {estilo.BORDA};
    padding: 4px 7px;
}}
"""


def _icone_app():
    """Ícone do app: a MESMA marca do topo da Torre (``torre._desenhar("marca")``),
    em índigo sobre um quadrado azul-ardósia.

    Até a R-23 era um alvo branco sobre gradiente verde→teal, da paleta antiga;
    com a Torre ele ficou sendo o único verde da interface — e verde é dose.
    As cores são as do modo NOITE fixas, e não as do modo em vigor: o ícone da
    barra de tarefas é desenhado uma vez no arranque, e o quadrado escuro se lê
    tanto na barra clara quanto na escura do Windows."""
    from PySide6.QtGui import QIcon, QPainter, QPen, QBrush
    from PySide6.QtCore import QRectF
    from isocentro.interface.torre import _desenhar
    noite = estilo._TORRE_NOITE
    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(noite["BORDA"]), 1.5))
    p.setBrush(QBrush(QColor(noite["SUPERFICIE"])))
    p.drawRoundedRect(QRectF(3, 3, 58, 58), 14, 14)
    caneta = QPen(QColor(noite["ACAO"])); caneta.setWidthF(3.4)
    caneta.setCapStyle(Qt.RoundCap)
    p.setPen(caneta); p.setBrush(Qt.NoBrush)
    _desenhar("marca", p, QRectF(13, 13, 38, 38))
    p.end()
    return QIcon(px)


def _titlebar_escura(win) -> None:
    """Deixa a barra de título nativa escura (Windows) para combinar com o app.

    Usa a DWM: DWMWA_USE_IMMERSIVE_DARK_MODE (barra escura, Win10 2004+/Win11) e,
    quando disponível (Win11 22H2+), DWMWA_CAPTION_COLOR para casar a cor da
    barra com o chrome escuro do app. Silenciosa fora do Windows.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(win.winId())
        dwm = ctypes.windll.dwmapi
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE; 19 é o valor em builds antigos.
        # No modo claro ele sai: barra escura sobre app claro é a emenda que
        # denuncia que o tema é do app e não da janela.
        val = ctypes.c_int(1 if estilo.modo() == "noite" else 0)
        if dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val),
                                     ctypes.sizeof(val)) != 0:
            dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val),
                                      ctypes.sizeof(val))
        # 35 = DWMWA_CAPTION_COLOR, em 0x00BBGGRR — a ordem dos bytes é o
        # inverso do hexadecimal da folha de estilo.
        _rgb = estilo.FUNDO_FUNDO.lstrip("#")
        cor = ctypes.c_int(int(_rgb[4:6] + _rgb[2:4] + _rgb[0:2], 16))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(cor),
                                  ctypes.sizeof(cor))
    except Exception:  # noqa: BLE001
        pass


def _paleta_dark() -> QPalette:
    """Paleta do sistema no modo em vigor (ver ``estilo``).

    É ela que veste TUDO que não tem folha de estilo própria — rótulos, tabelas,
    contadores, menus, barras de rolagem, o desabilitado do Fusion. Por isso a
    troca de modo começa aqui: uma chamada repinta o app inteiro, e as folhas
    escritas à mão só precisam alcançá-la (ver ``estilo.pintar``).

    O nome sobreviveu à época em que só havia escuro; hoje o modo é que decide.
    """
    p = QPalette()
    c = QColor
    p.setColor(QPalette.Window,          c(estilo.FUNDO_TELA))
    p.setColor(QPalette.WindowText,      c(estilo.TEXTO))
    p.setColor(QPalette.Base,            c(estilo.FUNDO_CAMPO))
    p.setColor(QPalette.AlternateBase,   c(estilo.FUNDO_BLOCO))
    p.setColor(QPalette.ToolTipBase,     c(estilo.FUNDO_BLOCO))
    p.setColor(QPalette.ToolTipText,     c(estilo.TEXTO))
    p.setColor(QPalette.Text,            c(estilo.TEXTO))
    p.setColor(QPalette.Button,          c(estilo.FUNDO_BLOCO))
    p.setColor(QPalette.ButtonText,      c(estilo.TEXTO))
    p.setColor(QPalette.BrightText,      c(estilo.VERMELHO))
    p.setColor(QPalette.Highlight,       c(estilo.SELECAO))
    p.setColor(QPalette.HighlightedText, c(estilo.SOBRE_SELECAO))
    p.setColor(QPalette.Link,            c(estilo.ACAO))
    p.setColor(QPalette.Disabled, QPalette.Text,       c(estilo.TEXTO_APAGADO))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, c(estilo.TEXTO_APAGADO))
    p.setColor(QPalette.Disabled, QPalette.WindowText, c(estilo.TEXTO_APAGADO))
    return p


def aplicar_modo(nome: str) -> str:
    """Troca dia↔noite no app inteiro. Devolve o modo em vigor.

    Três passos, nesta ordem: as constantes (``estilo``), a paleta do sistema
    (tudo que não tem folha própria) e as folhas registradas em
    ``estilo.pintar``. O modo fica gravado nas preferências da estação.
    """
    atual = estilo.definir_modo(nome)
    app = QApplication.instance()
    if app is not None:
        app.setPalette(_paleta_dark())
    ajustes().setValue("modo_cor", atual)
    return atual
