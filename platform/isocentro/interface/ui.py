"""Peças visuais compartilhadas pelas telas de Capa e Simulação.

As duas telas nasceram como **formulário**: uma grade de rótulo à esquerda e
campo à direita, tudo com o mesmo peso, do nome do paciente ao último combo de
preparo. Funciona, mas não guia o olho — quem abre a tela tem de ler tudo para
achar o que importa, e nada distingue "isto é o paciente" de "isto é um detalhe
que quase nunca se mexe".

Aqui estão as peças que substituem essa grade:

``Cartao``
    Agrupa um assunto numa superfície própria, um passo mais clara que o papel.
    O título fica dentro, pequeno e discreto — a borda não precisa gritar.
``campo``
    Rótulo **acima** do campo, miúdo. Some a coluna de rótulos que dobrava a
    largura de tudo, e cada par vira um bloco que se empilha em qualquer ordem.
``Chip``
    Um dado curto numa pílula — registro, idade, máquina. É o que se lê de
    relance sem precisar de rótulo.
``CabecalhoPaciente``
    A faixa de identidade: foto grande, nome grande, chips embaixo. Responde
    "de quem é isto?" antes de qualquer outra pergunta.
``ZonaArraste``
    O alvo de soltar fotos, do tamanho de um alvo — não uma linha de quadradinhos.

Nada aqui sabe o que é uma capa ou uma simulação: são peças, e quem as monta é
a tela. A paleta vem toda do :mod:`estilo`.

Por onde começa uma tela nova
-----------------------------

Não montar nada do Qt direto quando existe a peça aqui. A regra é curta:

===========================  ==========================================
o que se quer                o que se chama
===========================  ==========================================
uma janela própria           ``ui.Dialogo(titulo, pai)`` + ``rodape(...)``
abas                         ``ui.abas((pagina, "Título"), ...)``
avisar, alertar, falhar      ``ui.avisar/alertar/falhar(pai, ...)``
perguntar antes de agir      ``ui.confirmar(pai, ..., acao="Verbo")``
oferecer 2-3 caminhos        ``ui.escolher(pai, ..., opcoes)``
avisar que está trabalhando  ``with ui.trabalhando(pai, "Gerando…"):``
agrupar um assunto           ``ui.Cartao(titulo)``
rótulo + campo               ``ui.campo("Rótulo", ui.entrada())``
um botão                     ``ui.botao(...)`` (peso de ``estilo.btn_*``)
um link no meio do texto     ``ui.link("texto", funcao)``
uma cor, qualquer que seja   ``estilo.pintar(w, receita)``
===========================  ==========================================

Isto não é gosto, e por isso não é conselho: ``tests/test_padrao_visual.py``
**reprova** ``QDialog``, ``QTabWidget`` e hexadecimal de tela montados fora
daqui. A trava nasceu porque o desvio não vinha de discordância — vinha de
esquecimento, e era descoberto por print de tela, uma tela de cada vez, depois
de pronta.

Quem precisar mesmo fugir do padrão (a lupa de imagem foge: não tem rodapé, de
propósito) escreve o motivo na lista de exceções do teste. Exceção com nome e
motivo é decisão; exceção silenciosa é a divergência voltando.
"""
from __future__ import annotations

import contextlib
from typing import Optional

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (QColor, QKeySequence, QPainter, QPixmap,
                           QPolygonF, QShortcut)
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFrame,
                             QGridLayout,
                             QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPlainTextEdit,
                             QPushButton, QSizePolicy,
                             QTabWidget, QVBoxLayout, QWidget)

from isocentro.interface import estilo as st

# ── Folhas de estilo ─────────────────────────────────────────────────────────

def _campo() -> str:
    return (
        "QLineEdit, QPlainTextEdit, QComboBox {"
        f"  background:{st.FUNDO_CAMPO}; color:{st.TEXTO};"
        f"  border:1px solid {st.BORDA_SUAVE}; border-radius:7px;"
        "   padding:6px 9px; font-size:12.5px; }"
        f"QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover {{"
        f"  border-color:{st.BORDA}; }}"
        f"QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{"
        f"  border:1px solid {st.AZUL}; background:{st.FUNDO_CARTAO}; }}"
        "QComboBox::drop-down { border:none; width:18px; }"
        f"QComboBox QAbstractItemView {{ background:{st.FUNDO_CAMPO};"
        f"  color:{st.TEXTO}; selection-background-color:{st.AZUL};"
        f"  border:1px solid {st.BORDA}; outline:none; }}"
    )


def _lista() -> str:
    return (
        "QListWidget {"
        f"  background:{st.FUNDO_TELA}; color:{st.TEXTO};"
        f"  border:1px solid {st.BORDA_SUAVE}; border-radius:7px;"
        "   padding:4px; font-size:12.5px; }"
        "QListWidget::item { padding:5px 6px; border-radius:5px; }"
        f"QListWidget::item:hover {{ background:{st.FUNDO_CARTAO}; }}"
        f"QListWidget::item:selected {{ background:{st.AZUL_FUNDO};"
        f"  color:{st.AZUL_CLARO}; }}"
    )


# A aba ABERTA tem de se ver de longe: ela diz em qual posicionamento as fotos
# arrastadas vão cair, e com dois setups na tela trocar sem perceber significa
# gravar as fotos do tórax como se fossem do crânio. Distinguir só pela cor do
# texto não bastava — as duas abas ficavam do mesmo tom.
#
# São TRÊS marcas somadas: a ativa é mais clara (sobe até o tom da página),
# leva uma barra azul no topo e funde-se com o miolo; as outras ficam num tom
# mais escuro que o cartão, afundadas. Nada de fonte aqui — ver ``estilizar_abas``.
def _abas() -> str:
    return (
        "QTabWidget::pane {"
        f"  border:1px solid {st.BORDA_SUAVE}; border-radius:8px; top:-1px;"
        f"  background:{st.FUNDO_CARTAO}; }}"
        "QTabBar::tab {"
        f"  background:{st.FUNDO_TELA}; color:{st.TEXTO_APAGADO};"
        "   padding:7px 18px; margin-right:3px;"
        f"  border:1px solid {st.BORDA_SUAVE}; border-bottom:none;"
        "   border-top:2px solid transparent;"
        "   border-top-left-radius:7px; border-top-right-radius:7px; }"
        f"QTabBar::tab:hover {{ color:{st.TEXTO}; background:{st.FUNDO_CAMPO}; }}"
        "QTabBar::tab:selected {"
        f"  background:{st.FUNDO_CARTAO}; color:{st.AZUL_CLARO};"
        f"  border-top:2px solid {st.AZUL}; }}"
    )


# Fundo das páginas de aba. Tem de ser o MESMO da aba selecionada, senão ela
# fica flutuando sobre um miolo de outro tom em vez de se abrir nele — e é essa
# continuidade que diz qual aba está aberta.
def _pagina_aba() -> str:
    return (f"QWidget#pagina_aba {{ background:{st.FUNDO_CARTAO};"
            "  border-radius:8px; }"
            # Rótulo solto herda o fundo da paleta, não o da página: sobre a
            # página clara cada um virava um retângulo escuro em volta do texto.
            "QWidget#pagina_aba QLabel { background:transparent; }")


def transparente(w: QWidget) -> QWidget:
    """Marca um agrupador como sem fundo próprio.

    ``QWidget`` usado só para juntar peças (o par rótulo+campo, a fileira de
    fotos) pinta o fundo da paleta. Enquanto tudo era do mesmo tom isso não
    aparecia; sobre a página de aba, mais clara, cada agrupador virava um
    retângulo escuro em volta do conteúdo.
    """
    w.setObjectName("agrupador")
    w.setStyleSheet("QWidget#agrupador { background:transparent; }")
    return w


def pagina_de_aba(w: QWidget) -> QWidget:
    """Prepara um widget para ser página de um ``QTabWidget`` estilizado."""
    w.setObjectName("pagina_aba")
    st.pintar(w, lambda: _pagina_aba())
    return w


def abas(*paginas) -> "QTabWidget":
    """O ``QTabWidget`` do programa, já estilizado. **Use esta, não a do Qt.**

    ``estilizar_abas`` existe desde que as abas ganharam cara própria, e
    mesmo assim 2 dos 3 ``QTabWidget`` do programa nasceram sem ela — não por
    discordância, por esquecimento: quem monta uma tela nova escreve
    ``QTabWidget()`` porque é o que o Qt oferece, e a linha seguinte nunca
    aparece sozinha. As abas da Administração e as de plano do Formulário
    ficaram meses com a barra crua do sistema ao lado das do Posicionamento,
    que é a mesma tela para quem olha.

    ``paginas``: ``(widget, "Título")`` — cada página já passa por
    ``pagina_de_aba``, que é o outro passo que se esquecia. Sem argumento
    nenhum, devolve o widget vazio para quem preenche depois (o Formulário
    monta e desmonta as abas conforme os planos).
    """
    w = QTabWidget()
    estilizar_abas(w)
    for pagina, titulo in paginas:
        w.addTab(pagina_de_aba(pagina), titulo)
    return w


def estilizar_abas(abas) -> None:
    """Aplica o estilo das abas — e a fonte na própria barra.

    A fonte tem de ser posta no widget, e não só na folha de estilo: o Qt mede
    a largura de cada aba com a fonte do widget e desenha o texto com a da
    folha. Declarar ``font-size``/``font-weight`` apenas no QSS media com uma
    fonte e pintava com outra, maior — e o nome do posicionamento saía cortado
    nas duas pontas, que é justamente o rótulo que diz em qual setup as fotos
    arrastadas vão cair.
    """
    st.pintar(abas, lambda: _abas())
    fonte = abas.tabBar().font()
    fonte.setBold(True)
    fonte.setPixelSize(12)
    abas.tabBar().setFont(fonte)


def _btn_discreto(cor_texto: str = "") -> str:
    """Botão secundário: contorno, sem preenchimento. Não compete com a ação."""
    cor = cor_texto or st.TEXTO_FRACO
    return (
        "QPushButton {"
        f"  background:transparent; color:{cor};"
        f"  border:1px solid {st.BORDA}; border-radius:7px;"
        "   padding:6px 13px; font-size:11.5px; }"
        f"QPushButton:hover {{ border-color:{st.AZUL}; color:{st.AZUL_CLARO};"
        f"  background:{st.FUNDO_CARTAO}; }}"
        f"QPushButton:pressed {{ background:{st.FUNDO_TELA}; }}"
        f"QPushButton:disabled {{ color:{st.TEXTO_APAGADO};"
        f"  border-color:{st.BORDA_SUAVE}; }}"
    )


# ── Peças ────────────────────────────────────────────────────────────────────

class Cartao(QFrame):
    """Um assunto, numa superfície própria.

    Substitui o ``QGroupBox``: mesmo agrupamento, sem a moldura com o título
    encaixado na borda — que é o que dá cara de formulário de repartição.
    """

    def __init__(self, titulo: str = "", passo: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("cartao")
        st.pintar(self, lambda: (
            f"QFrame#cartao {{ background:{st.FUNDO_BLOCO};"
            f"  border:1px solid {st.BORDA_SUAVE}; border-radius:11px; }}"))
        self.corpo = QVBoxLayout(self)
        self.corpo.setContentsMargins(16, 13, 16, 14)
        self.corpo.setSpacing(10)
        if titulo:
            self.corpo.addLayout(self._titulo(titulo, passo))

    def _titulo(self, texto: str, passo: str) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(8)
        if passo:
            # O número do passo em vez de "1 · " no meio do texto: vira âncora
            # visual e o título fica livre para dizer só o assunto.
            n = QLabel(passo)
            n.setFixedSize(20, 20)
            n.setAlignment(Qt.AlignCenter)
            st.pintar(n, lambda: (
                f"background:{st.AZUL_FUNDO}; color:{st.AZUL_CLARO};"
                "border-radius:10px; font-size:11px; font-weight:bold;"))
            linha.addWidget(n)
        rot = QLabel(texto.upper())
        # O título não estica: num cartão cujo conteúdo tem teto de altura (a
        # grade da janela de Campos), a sobra ia toda para a linha do título e
        # ele abria um vão de 125 px entre o nome do bloco e o que ele nomeia.
        rot.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        st.pintar(rot, lambda: (
            f"color:{st.TEXTO_FRACO}; font-size:11px; font-weight:bold;"
            " letter-spacing:1px;"))
        linha.addWidget(rot)
        linha.addStretch(1)
        self.linha_titulo = linha
        return linha

    def juntar(self, *widgets, espaco: int = 10) -> QHBoxLayout:
        """Põe widgets lado a lado dentro do cartão."""
        linha = QHBoxLayout()
        linha.setSpacing(espaco)
        for w in widgets:
            linha.addWidget(w) if isinstance(w, QWidget) else linha.addLayout(w)
        self.corpo.addLayout(linha)
        return linha


def rotulo(texto: str, forte: bool = False) -> QLabel:
    """Rótulo miúdo, do tipo que fica ACIMA do campo."""
    lbl = QLabel(texto)
    st.pintar(lbl, lambda: (
        f"color:{st.TEXTO_FRACO if forte else st.TEXTO_APAGADO};"
        " font-size:10.5px; font-weight:600; letter-spacing:0.4px;"))
    return lbl


def campo(texto: str, widget: QWidget, dica: str = "") -> QWidget:
    """Um par rótulo-em-cima + campo, empacotado como um bloco só.

    Empilhar o rótulo economiza a coluna que a grade gastava com ele e deixa os
    campos alinharem-se por conta própria em qualquer largura.
    """
    caixa = transparente(QWidget())
    lay = QVBoxLayout(caixa)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(3)
    lay.addWidget(rotulo(texto))
    lay.addWidget(widget)
    if dica:
        d = QLabel(dica)
        d.setWordWrap(True)
        st.pintar(d, lambda: f"color:{st.TEXTO_APAGADO}; font-size:10px;")
        lay.addWidget(d)
    caixa.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    return caixa


def entrada(largura: int = 0, dica: str = "") -> QLineEdit:
    w = QLineEdit()
    st.pintar(w, lambda: _campo())
    w.setMinimumHeight(31)
    if dica:
        w.setPlaceholderText(dica)
    if largura:
        w.setFixedWidth(largura)
    return w


def area(linhas: int = 3, dica: str = "") -> QPlainTextEdit:
    w = QPlainTextEdit()
    st.pintar(w, lambda: _campo())
    w.setFixedHeight(19 * linhas + 14)
    if dica:
        w.setPlaceholderText(dica)
    return w


class Escolha(QComboBox):
    """Seletor com seta visível, que só muda quando alguém o escolhe.

    **A seta é desenhada aqui.** A folha de estilo zera o ``::drop-down`` para
    matar o botão cinza que o Fusion desenha — ele não combina com nada nesta
    tela —, e sem imagem no ``::down-arrow`` o Qt simplesmente não desenha seta
    nenhuma. Um combo editável sem seta é indistinguível de uma caixa de texto:
    o preparo (bexiga, reto, jejum) parecia campo livre, e as opções prontas
    ficavam invisíveis para quem não soubesse que estavam lá.

    O ``QComboBox`` do Qt troca de item com a roda do mouse, e emite
    ``activated`` como se a pessoa tivesse escolhido. Numa tela rolável cheia
    de seletores — que é esta —, rolar a página com o cursor por cima de um
    deles troca o valor sem que ninguém perceba. Aqui a nota de posicionamento
    e as colunas de preparo são justamente o que não pode mudar sozinho: são o
    que a folha manda fazer com o paciente na mesa.

    Com o popup ABERTO a roda continua valendo — ali ela é o gesto de escolher.
    """

    # Metade da largura reservada ao ``::drop-down`` na folha de estilo.
    _SETA_LARG = 9
    _SETA_ALT = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentTextChanged.connect(self._mostrar_o_comeco)

    def _mostrar_o_comeco(self, *_) -> None:
        """Valor maior que o campo: deixa à mostra o COMEÇO, não o fim.

        Ao receber texto o Qt leva o cursor para o fim, e o campo estreito
        passa a exibir "CIMA DA CABEÇA" — que se lê como um valor errado, não
        como um valor cortado. Quem tem o cursor ali dentro fica de fora: é a
        pessoa digitando, e mover o cursor dela seria pior.
        """
        campo = self.lineEdit()
        if campo is not None and not campo.hasFocus():
            campo.setCursorPosition(0)
        # E o valor inteiro fica no tooltip enquanto não couber — "ACIMA DA
        # CABEÇ" não é um preparo, e a folha impressa vai sair com o resto.
        texto = self.currentText()
        largura = self.width() - self._SETA_LARG - 26   # seta + respiros
        cabe = self.fontMetrics().boundingRect(texto).width() <= largura
        self.setToolTip("" if cabe else texto)

    def wheelEvent(self, e):  # noqa: N802 - assinatura do Qt
        if self.view().isVisible():
            super().wheelEvent(e)
        else:
            # Ignorar devolve a rolagem à página, que é o que a pessoa queria.
            e.ignore()

    def paintEvent(self, e):  # noqa: N802 - assinatura do Qt
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(st.TEXTO_FRACO if self.isEnabled()
                          else st.TEXTO_APAGADO))
        x = self.width() - self._SETA_LARG - 8
        y = (self.height() - self._SETA_ALT) / 2
        p.drawPolygon(QPolygonF([
            QPointF(x, y),
            QPointF(x + self._SETA_LARG, y),
            QPointF(x + self._SETA_LARG / 2, y + self._SETA_ALT)]))


def escolha(itens=(), editavel: bool = False, largura: int = 0) -> QComboBox:
    w = Escolha()
    w.setEditable(editavel)
    st.pintar(w, lambda: _campo())
    w.setMinimumHeight(31)
    if itens:
        w.addItems(list(itens))
    if largura:
        w.setFixedWidth(largura)
    return w


def botao(texto: str, cor: str = "", hover: str = "", altura: int = 38,
          parent=None) -> QPushButton:
    """Botão de ação (preenchido) ou discreto (sem cor).

    Sem brilho desde a R-23: a Torre é chapada (DESIGN.md, Elevation &
    Depth), e o brilho era VERDE — a cor que é só da isodose.
    """
    b = QPushButton(texto)
    b.setCursor(Qt.PointingHandCursor)
    b.setMinimumHeight(altura)
    if cor:
        st.pintar(b, lambda: st.btn_solido(12.5))
    else:
        st.pintar(b, _btn_discreto)
    return b


def link(texto: str, ao_clicar=None, parent=None) -> QPushButton:
    """Um link: texto sublinhado que leva a outro lugar, sem moldura de botão.

    É um ``QPushButton`` chapado, e não um ``QLabel`` com ``<a href>``, por uma
    razão de cor: o Qt desenha a âncora de um rótulo com a cor **Link da
    paleta**, que a folha de estilo não alcança — a única saída seria escrever
    a cor dentro do HTML, e cor escrita no texto não acompanha a troca
    dia↔noite (é a armadilha que o ``test_padrao_visual`` reprova em toda parte
    do programa). Como botão, a cor vem da folha e a troca funciona sozinha.

    Peso NENHUM: link não é o quarto peso de botão, é a saída lateral que não
    disputa clique com o fluxo da tela — "veja as referências" ao lado de um
    número não é um passo do trabalho.
    """
    b = QPushButton(texto, parent)
    b.setCursor(Qt.PointingHandCursor)
    b.setFlat(True)
    b.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    st.pintar(b, lambda: (
        "QPushButton {"
        f"  background:transparent; color:{st.AZUL_CLARO}; border:none;"
        "   padding:1px 2px; font-size:11.5px; text-decoration:underline; }"
        f"QPushButton:hover {{ color:{st.ACAO_FORTE}; }}"
        f"QPushButton:disabled {{ color:{st.TEXTO_APAGADO};"
        "   text-decoration:none; }}"))
    if ao_clicar is not None:
        b.clicked.connect(ao_clicar)
    return b


# Até onde uma pílula pode crescer ao dividir a sobra da fileira (ver
# ``CabecalhoPaciente._encher``). O teto existe para o caso de UMA pílula
# sozinha na linha: sem ele, ela viraria uma faixa da largura da tela, que não é
# um dado — é uma barra. É PROPORCIONAL ao texto, e não um número de pixels,
# porque o que faz uma pílula parecer pílula é a relação com o que está escrito
# dentro dela: "Feminino" esticado em 400 px fica estranho no mesmo lugar em que
# o nome de um médico fica natural.
_CRESC_CHIP = 2.2      # até pouco mais do dobro da largura do próprio texto
_FOLGA_CHIP = 60       # mais uma folga fixa, para os textos muito curtos


class Chip(QLabel):
    """Um dado curto numa pílula. Lê-se de relance, sem rótulo."""

    def __init__(self, texto: str = "", tom: str = "neutro", parent=None):
        super().__init__(parent)
        self.tom = tom
        self.setAlignment(Qt.AlignCenter)
        self.definir(texto)
        st.pintar(self, self._folha)

    def _folha(self) -> str:
        """A folha a partir do TOM — recalculada a cada troca de dia↔noite."""
        fundo, cor = {
            "neutro": (st.FUNDO_CAMPO, st.TEXTO_FRACO),
            "azul": (st.ACAO_FUNDO, st.ACAO),
            "verde": (st.ACAO_FUNDO, st.ACAO),
            "ambar": (st.AMBAR_FUNDO, st.AMBAR),
            # O vermelho entrou com a aba Qualidade: sem ele, "fora da faixa" e
            # "atenção" saíam da mesma cor, e a pílula mais grave da tela era
            # indistinguível da segunda mais grave.
            "vermelho": (st.AMBAR_FUNDO, st.VERMELHO),
        }.get(self.tom, (st.FUNDO_CAMPO, st.TEXTO_FRACO))
        return (f"background:{fundo}; color:{cor}; border-radius:14px;"
                " padding:6px 16px; font-size:15px; font-weight:600;")

    def definir(self, texto: str, tom: str = "") -> None:
        self.tom = tom or self.tom
        self.setStyleSheet(self._folha())
        self.setText(texto or "")
        self.setVisible(bool(texto))


class Valor(QFrame):
    """Um dado da nota em tamanho de leitura: rótulo miúdo, valor grande.

    A pílula de 11 px serve para a identidade do paciente, que se confere de
    perto e de uma vez. O preparo é outra coisa: lê-se com o paciente já na
    mesa, de pé, longe da tela — "BEXIGA: CHEIA" em letra de rodapé é uma
    instrução que se perde, e é justamente a que não pode passar batida.
    """

    def _cores(self) -> tuple:
        return {
            "azul": (st.ACAO_FUNDO, st.ACAO, st.ACAO_LINHA),
            "neutro": (st.FUNDO_CAMPO, st.TEXTO, st.BORDA),
        }.get(self.tom, (st.FUNDO_CAMPO, st.TEXTO, st.BORDA))

    def _folha(self) -> str:
        fundo, _cor, borda = self._cores()
        return (f"QFrame#valor {{ background:{fundo};"
                f"  border:1px solid {borda}; border-radius:9px; }}")

    def _folha_val(self) -> str:
        """A folha do VALOR — cor do texto, que também depende do tom."""
        return (f"color:{self._cores()[1]}; font-size:14.5px;"
                " font-weight:bold; background:transparent; border:none;")

    def definir_tom(self, tom: str) -> None:
        """Troca o tom DEPOIS de construído — as DUAS folhas.

        A cor do texto mora na folha do ``val``, aplicada no nascimento: quem
        mexia só em ``self.tom`` e repintava o quadro ficava com valor azul
        sobre fundo neutro. Aconteceu na fileira da Ficha Virtual, onde as três
        portas do fim recebem o tom pela POSIÇÃO, a cada troca de paciente.

        Reaplicado à mão, sem ``estilo.pintar``: ele guarda um ouvinte por
        chamada, e este método roda a cada recarga da fileira (ver as
        armadilhas no CLAUDE.md). O ouvinte registrado no ``__init__`` continua
        valendo para o dia↔noite — ele relê ``self.tom``, que acabou de mudar.
        """
        self.tom = tom
        self.setStyleSheet(self._folha())
        for val in self._vals:
            val.setStyleSheet(self._folha_val())

    def __init__(self, rotulo: str, valor: str, tom: str = "azul", parent=None):
        super().__init__(parent)
        self.setObjectName("valor")
        self.tom = tom
        st.pintar(self, self._folha)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(11, 7, 11, 9)
        lay.setSpacing(2)
        self.rot = QLabel(rotulo.upper())
        st.pintar(self.rot, lambda: f"color:{st.TEXTO_FRACO};"
                  " font-size:10px; font-weight:600; letter-spacing:0.6px;"
                  " background:transparent; border:none;")
        lay.addWidget(self.rot)
        self._montar_valor(lay, valor)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def _montar_valor(self, lay, valor: str) -> None:
        """O miolo do cartão — um valor só. ``ValorTrio`` troca por três.

        Separado do ``__init__`` para que a variante de três colunas herde a
        moldura, o rótulo e a troca de tom sem copiar nenhum deles: o cartão do
        SSD tem de ser o MESMO cartão do resto da fileira, e dois construtores
        parecidos divergem no primeiro ajuste de cor.
        """
        self.val = QLabel(valor)
        self.val.setWordWrap(True)
        st.pintar(self.val, self._folha_val)
        lay.addWidget(self.val)
        self._vals = [self.val]

    def nao_quebrar(self) -> None:
        """Nenhum valor deste cartão quebra linha (ver ``_Fileira``): cartão
        que corta o próprio valor não é cartão."""
        for val in self._vals:
            val.setWordWrap(False)

    def texto(self) -> str:
        """O que o cartão MOSTRA, para quem confere e para o teste."""
        return self.val.text()


class ValorTrio(Valor):
    """Uma medida de TRÊS posições num cartão — os SSD e o deslocamento.

    No cartão comum os três viravam um texto só, ``90,1 / 85,3 / 84,8``, com o
    casamento de cada número ao seu gantry escondido no rótulo (``SSD TP0
    G0/G270/G90``): para saber de quem era o 85,3 contava-se a posição na barra
    e a posição no rótulo — duas contagens, no meio de uma conferência, para
    ler um número que já está escrito. Aqui cada valor tem o seu eixo em cima,
    na MESMA ordem e com o MESMO sub-cabeçalho da folha impressa (ver
    ``ficha_pdf._tabela_plano``), que é o papel com que se confere.

    O rótulo do cartão carrega a unidade, como o papel: ``90,1`` sozinho podia
    ser cm ou mm, e o número que vai para a mesa não pode depender de
    lembrança.

    Posição sem valor sai como ``—`` apagado, não em branco: com o eixo escrito
    em cima, a lacuna diz QUAL das três a ficha não gravou — e um vão vazio no
    meio de três números se lê como espaço, não como ausência.
    """

    def __init__(self, rotulo: str, partes, tom: str = "azul", parent=None):
        # Antes do ``super()``: é ele quem chama ``_montar_valor``.
        self._partes = [(str(sub), str(val or ""))
                        for sub, val in (partes or [])]
        super().__init__(rotulo, "", tom, parent)

    @staticmethod
    def _folha_sub() -> str:
        """O eixo (G0, Lat.) — o mesmo miúdo do rótulo, sem o espaçamento de
        letra: são palavras de três letras centradas sobre o número, e o
        espaçamento as descolava da coluna a que pertencem."""
        return (f"color:{st.TEXTO_FRACO}; font-size:10px; font-weight:600;"
                " background:transparent; border:none;")

    @staticmethod
    def _folha_ausente() -> str:
        """O ``—`` da posição que a ficha não gravou: mesmo tamanho do número,
        para a linha não desalinhar, e apagado, para não se confundir com um
        valor medido."""
        return (f"color:{st.TEXTO_APAGADO}; font-size:14.5px;"
                " font-weight:bold; background:transparent; border:none;")

    def _montar_valor(self, lay, _valor: str) -> None:
        grade = QGridLayout()
        grade.setContentsMargins(0, 3, 0, 0)
        # Espaço de sobra entre as colunas: com pouco, "85,3 84,8" se lia como
        # um número só de seis dígitos — que é exatamente a confusão que este
        # cartão existe para desfazer.
        grade.setHorizontalSpacing(18)
        grade.setVerticalSpacing(1)
        self._vals = []
        for col, (sub, valor) in enumerate(self._partes):
            rot = QLabel(sub)
            rot.setAlignment(Qt.AlignCenter)
            st.pintar(rot, self._folha_sub)
            val = QLabel(valor or "—")
            val.setAlignment(Qt.AlignCenter)
            st.pintar(val, self._folha_val if valor else self._folha_ausente)
            grade.addWidget(rot, 0, col)
            grade.addWidget(val, 1, col)
            # Só os PREENCHIDOS entram em ``_vals``: é essa lista que a troca
            # de tom repinta, e o ``—`` tem de continuar apagado quando o
            # cartão vira azul.
            if valor:
                self._vals.append(val)
        lay.addLayout(grade)

    def texto(self) -> str:
        return " / ".join(val for _sub, val in self._partes)


class Retrato(QLabel):
    """Moldura de imagem — a foto 3×4 do paciente ou uma de posicionamento.

    ``elastico`` faz a moldura acompanhar a largura de quem a hospeda, com a
    altura fixa: é o que permite a foto do setup crescer numa coluna larga em
    vez de continuar o selo de 112 px que ninguém consegue conferir.
    """

    clicado = Signal()

    def __init__(self, larg: int = 86, alt: int = 106, vazio: str = "—",
                 parent=None, elastico: bool = False):
        super().__init__(parent)
        self._vazio = vazio
        self._tem = False
        self._dados: Optional[bytes] = None
        if elastico:
            self.setMinimumWidth(larg)
            self.setFixedHeight(alt)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        else:
            self.setFixedSize(larg, alt)
        self.setAlignment(Qt.AlignCenter)
        self.definir(None)
        st.pintar(self, self._folha)

    def definir(self, dados: Optional[bytes]) -> None:
        self._tem = False
        self._dados = dados
        if dados:
            pix = QPixmap()
            if pix.loadFromData(dados):
                self.setPixmap(pix.scaled(
                    self.width(), self.height(),
                    Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                self.setText("")
                self._tem = True
        if not self._tem:
            self.setPixmap(QPixmap())
            self.setText(self._vazio)
        self._pintar()

    def tem_imagem(self) -> bool:
        return self._tem

    def _folha(self) -> str:
        """Moldura cheia ou tracejada, conforme haja imagem."""
        if self._tem:
            return (f"border:1px solid {st.BORDA}; border-radius:9px;"
                    f" background:{st.FUNDO_TELA};")
        return (f"border:1.5px dashed {st.BORDA}; border-radius:9px;"
                f" background:{st.FUNDO_TELA}; color:{st.TEXTO_APAGADO};"
                " font-size:10.5px;")

    def _pintar(self) -> None:
        self.setStyleSheet(self._folha())

    def resizeEvent(self, e):  # noqa: N802 - assinatura do Qt
        """Moldura elástica: a imagem é reescalada para a largura nova.

        Sem isto o ``QPixmap`` continua no tamanho em que entrou e a foto fica
        num canto da moldura esticada, com fundo vazio ao lado.
        """
        super().resizeEvent(e)
        if self._dados is not None:
            self.definir(self._dados)

    def mousePressEvent(self, e):  # noqa: N802 - assinatura do Qt
        self.clicado.emit()


class CabecalhoPaciente(QFrame):
    """A faixa de identidade: foto, nome grande e chips.

    Responde "de quem é isto?" antes de qualquer outra coisa. Nas telas antigas
    o nome do paciente era mais um campo entre trinta, do mesmo tamanho do
    último combo de preparo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cab")
        st.pintar(self, lambda: (
            f"QFrame#cab {{ background:{st.FUNDO_BLOCO};"
            f"  border:1px solid {st.BORDA_SUAVE}; border-radius:11px; }}"))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 16, 20, 16)
        lay.setSpacing(18)

        self.retrato = Retrato(112, 138, "sem\nfoto")
        lay.addWidget(self.retrato)

        col = QVBoxLayout()
        col.setSpacing(9)
        self.nome = QLabel("—")
        st.pintar(self.nome, lambda: (
            f"color:{st.TEXTO}; font-size:24px; font-weight:bold;"))
        self.nome.setWordWrap(True)
        col.addWidget(self.nome)

        # Duas fileiras: quem é o paciente, e onde/com quem ele trata. Numa
        # fileira só, sete pílulas espremem e a leitura de relance se perde.
        self.linha_chips = QHBoxLayout()
        self.linha_chips.setSpacing(9)
        self.linha_extra = QHBoxLayout()
        self.linha_extra.setSpacing(9)
        self._chips: dict[str, Chip] = {}
        col.addLayout(self.linha_chips)
        col.addLayout(self.linha_extra)
        col.addStretch(1)
        lay.addLayout(col, 1)

        self.canto = QVBoxLayout()
        self.canto.setSpacing(6)
        self.canto.setAlignment(Qt.AlignTop)
        lay.addLayout(self.canto)

    @staticmethod
    def _encher(linha: QHBoxLayout, chips: list) -> None:
        """Refaz as pílulas da fileira, repartindo entre elas a largura livre.

        A faixa de identidade ocupa a janela inteira e as pílulas cabiam num
        terço dela: o resto era um vão, com os dados do paciente amontoados
        num canto de uma tela vazia. Aqui cada pílula cresce **na proporção do
        próprio texto** — quem tem nome de médico fica maior que quem tem
        "Feminino", e a fileira termina rente à borda em vez de no meio.

        O crescimento tem teto (``_FOLGA_CHIP``): numa fileira de uma pílula
        só, esticar sem limite daria uma barra da largura da tela. O que sobrar
        depois do teto vai para o vão do fim, que aí é pequeno.

        Cada pílula nasce **com pai**: sem ele, o widget é de topo até o
        ``addWidget`` adotá-lo, e o Qt o exibe nesse intervalo — uma pílula
        solta piscando sobre a tela a cada repinte. Com sete chips por paciente
        isso vira um popup no meio do trabalho.
        """
        pai = linha.parentWidget()
        for i in reversed(range(linha.count())):
            item = linha.takeAt(i)
            if item.widget():
                item.widget().deleteLater()
        for texto, tom in chips:
            if not texto:
                continue
            chip = Chip(texto, tom, pai)
            natural = max(1, chip.sizeHint().width())
            chip.setMaximumWidth(int(natural * _CRESC_CHIP) + _FOLGA_CHIP)
            chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            # O peso é a largura natural: a sobra se reparte na mesma
            # proporção, e as pílulas mantêm entre si o tamanho relativo que
            # tinham — é isso que impede "Feminino" de ficar do tamanho do
            # nome do médico.
            linha.addWidget(chip, natural)
        linha.addStretch(1)

    def definir(self, nome: str, chips: list, foto=None, extras=()) -> None:
        """``chips``/``extras``: listas de (texto, tom), uma fileira cada.

        Texto vazio some em vez de deixar pílula oca: um chip em branco lê-se
        como dado faltando, e a maioria dos pacientes não tem todos.
        """
        self.nome.setText(nome or "—")
        self.retrato.definir(foto)
        self._encher(self.linha_chips, chips)
        self._encher(self.linha_extra, list(extras))


class ZonaArraste(QFrame):
    """Alvo de soltar arquivos — do tamanho de um alvo.

    A tela antiga oferecia uma fileira de quadradinhos de 100 px como área de
    largar foto. Isto é uma faixa inteira, que muda de cor quando o arquivo
    passa por cima: a mesma affordance dos lugares onde se arrasta coisa.
    """

    soltou = Signal(list)

    def __init__(self, texto: str = "Arraste as fotos aqui", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("zona")
        self._texto = texto
        self._ativo = False
        self.setMinimumHeight(74)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        self.lbl = QLabel(texto)
        self.lbl.setAlignment(Qt.AlignCenter)
        st.pintar(self.lbl, lambda: (
            f"color:{st.TEXTO_FRACO}; font-size:12.5px; font-weight:600;"))
        self.sub = QLabel("ou use o botão Escolher fotos")
        self.sub.setAlignment(Qt.AlignCenter)
        st.pintar(self.sub, lambda: f"color:{st.TEXTO_APAGADO}; font-size:10.5px;")
        lay.addWidget(self.lbl)
        lay.addWidget(self.sub)
        self._pintar()
        st.pintar(self, self._folha)

    def _folha(self) -> str:
        """Tracejado normal ou aceso — o estado é lido AQUI, não capturado.

        Calcular a cor fora e passar por closure congelava o valor do momento
        do arraste; e registrar em ``_pintar`` empilhava um ouvinte a cada
        entrada e saída do cursor. Uma receita só, registrada na construção.
        """
        cor = st.ACAO if self._ativo else st.BORDA
        fundo = st.ACAO_FUNDO if self._ativo else st.FUNDO_TELA
        return (f"QFrame#zona {{ border:1.5px dashed {cor}; border-radius:10px;"
                f"  background:{fundo}; }}")

    def _pintar(self) -> None:
        self.setStyleSheet(self._folha())

    def compactar(self, sim: bool) -> None:
        """Encolhe a faixa depois que já há foto.

        Um alvo de arraste do tamanho de um alvo é o certo enquanto está vazio.
        Cheio, ele vira o maior elemento da tela dizendo o que já foi feito —
        e empurra para fora do campo de visão as fotos que a pessoa quer olhar.
        """
        self.sub.setVisible(not sim)
        # Compacta as margens junto com a altura: 34 px com o respiro de 10 em
        # cima e embaixo não sobravam linha para o texto, que saía cortado.
        self.layout().setContentsMargins(12, 4 if sim else 10,
                                         12, 4 if sim else 10)
        self.setMinimumHeight(30 if sim else 74)
        self.setMaximumHeight(30 if sim else 16777215)
        st.pintar(self.lbl, lambda: (
            f"color:{st.TEXTO_APAGADO if sim else st.TEXTO_FRACO};"
            f" font-size:{11 if sim else 12.5}px; font-weight:600;"))

    def dizer(self, texto: str, sub: str = "") -> None:
        self.lbl.setText(texto)
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))

    def dragEnterEvent(self, e):  # noqa: N802
        if e.mimeData().hasUrls():
            self._ativo = True
            self._pintar()
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):  # noqa: N802
        self._ativo = False
        self._pintar()

    def dropEvent(self, e):  # noqa: N802
        self._ativo = False
        self._pintar()
        caminhos = [u.toLocalFile() for u in e.mimeData().urls()
                    if u.toLocalFile()]
        if caminhos:
            self.soltou.emit(caminhos)
        e.acceptProposedAction()


def barras() -> str:
    """Folha das barras de rolagem — um traço, e não a coisa mais clara da tela.

    A barra vem CLARA do sistema e, sobre o fundo escuro, fica mais brilhante
    que o botão que se quer clicar: o olho vai para ela primeiro. A Fichinha já
    pagou isso (ver o comentário na rolagem dela) e a Edição da Ficha também —
    as duas têm cópias próprias desta folha, anteriores a esta função. Código
    novo usa esta; as duas antigas podem adotá-la quando forem mexidas, e não
    foram tocadas agora só para não misturar refatoração com correção.

    As duas orientações juntas: uma tela com a vertical discreta e a horizontal
    berrante é pior que as duas berrantes, porque a diferença sugere que uma
    delas significa alguma coisa.
    """
    return "".join(
        f"QScrollBar:{orient} {{ background:transparent; {espessura}"
        "   margin:0; }"
        f"QScrollBar::handle:{orient} {{ background:{st.BORDA};"
        f"  border-radius:4px; {minimo} }}"
        f"QScrollBar::handle:{orient}:hover {{ background:{st.AZUL}; }}"
        f"QScrollBar::add-line:{orient},QScrollBar::sub-line:{orient} {{"
        f"  {zero} border:none; }}"
        f"QScrollBar::add-page:{orient},QScrollBar::sub-page:{orient} {{"
        "   background:transparent; }"
        for orient, espessura, minimo, zero in (
            ("vertical", "width:8px;", "min-height:28px;", "height:0;"),
            ("horizontal", "height:8px;", "min-width:28px;", "width:0;")))


def grade() -> str:
    """Folha de uma ``QTableWidget`` de LEITURA, no tom das outras telas.

    Sem ela a tabela vem com a paleta crua do sistema: fundo branco no modo
    noite, cabeçalho em relevo e uma linha de seleção azul-Windows que não
    existe em lugar nenhum do app. Numa tela de conferência isso se lê como
    "esta janela é de outro programa".

    Sem grade alternada e sem hover: as linhas aqui são grandezas de um mesmo
    campo (SSD, Y1, Y2…), não itens de uma lista que se escolhe. Zebrar sugere
    que se está percorrendo registros, e é o contrário — lê-se COLUNA a coluna.
    """
    return (
        "QTableWidget {"
        f"  background:{st.FUNDO_TELA}; color:{st.TEXTO};"
        f"  gridline-color:{st.BORDA_SUAVE};"
        f"  border:1px solid {st.BORDA_SUAVE}; border-radius:7px;"
        "   font-size:12.5px; }"
        "QTableWidget::item { padding:3px 6px; }"
        f"QTableWidget::item:selected {{ background:{st.AZUL_FUNDO};"
        f"  color:{st.TEXTO}; }}"
        "QHeaderView::section {"
        f"  background:{st.FUNDO_CARTAO}; color:{st.TEXTO_FRACO};"
        f"  border:none; border-right:1px solid {st.BORDA_SUAVE};"
        f"  border-bottom:1px solid {st.BORDA_SUAVE};"
        "   padding:4px 8px; font-size:11.5px; font-weight:700; }"
        f"QTableCornerButton::section {{ background:{st.FUNDO_CARTAO};"
        f"  border:none; border-right:1px solid {st.BORDA_SUAVE};"
        f"  border-bottom:1px solid {st.BORDA_SUAVE}; }}"
        + barras())


def divisor() -> QFrame:
    linha = QFrame()
    linha.setFrameShape(QFrame.HLine)
    st.pintar(linha, lambda: f"background:{st.BORDA_SUAVE};"
              " max-height:1px; border:none;")
    return linha


def faixa(fundo: str = "") -> tuple[QWidget, QHBoxLayout]:
    """Barra de topo/rodapé da tela, com o respiro certo."""
    w = QWidget()
    st.pintar(w, lambda: f"background:{fundo or st.FUNDO_CARTAO};")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(18, 10, 18, 10)
    lay.setSpacing(10)
    return w, lay


class Dialogo(QDialog):
    """A moldura das telas próprias: título, corpo e um rodapé só.

    Havia 14 ``QDialog`` montados um a um, e o rodapé de cada um era escrito à
    mão. O resultado: **os dois botões trocavam de lugar entre telas** —
    ``[Confirmar][Cancelar]`` em cinco delas, ``[Cancelar][Confirmar]`` na
    Edição da Ficha, no Agendamento e no Separar Ficha. Quem acabou de clicar
    "Aplicar" à direita numa encontrava "Cancelar" naquela posição na seguinte.

    A ordem não é gosto: os ``QMessageBox`` desenham ``[OK][Cancelar]`` no
    Windows e isso não se muda; como eles são 5× mais frequentes, é ele que
    dita a ordem da casa. **Confirmar à esquerda**, sempre.

    Quem herda monta só o ``corpo`` e chama ``rodape()`` no fim. O tamanho
    continua de cada um: estas telas vão de uma pergunta de senha a uma bancada
    de mil pixels, e um tamanho único pioraria as duas pontas.
    """

    def __init__(self, titulo: str, pai=None, largura: int = 0,
                 altura: int = 0):
        super().__init__(pai)
        self.setWindowTitle(titulo)
        st.pintar(self, lambda: f"background:{st.FUNDO_TELA};")
        self._raiz = QVBoxLayout(self)
        self._raiz.setContentsMargins(18, 16, 18, 14)
        self._raiz.setSpacing(12)
        # O corpo é de quem herda; o rodapé entra depois dele, sempre por
        # último. Separá-los aqui é o que impede um rodapé no meio da tela.
        self.corpo = QVBoxLayout()
        self.corpo.setSpacing(10)
        self._raiz.addLayout(self.corpo, 1)
        if largura and altura:
            self.resize(largura, altura)

    def rodape(self, confirmar: str = "", cancelar: str = "",
               extras=(), perigo: bool = False) -> dict:
        """A faixa de botões. Devolve ``{rótulo: botão}`` para quem precisar.

        ``confirmar`` vazio = tela de LEITURA: sai o sólido e o cancelar vira
        "Fechar". Botão sólido significa "o passo que não se desfaz"; numa tela
        que só mostra, não há passo nenhum, e um sólido ali prometeria um
        efeito que não existe.

        ``cancelar=None`` = tela SEM SAÍDA, e é diferente de ``""``: a troca
        de senha forçada no primeiro acesso não tem como ser recusada — sem
        senha nova não se entra —, e um "Cancelar" ali seria um botão que não
        faz nada. ``""`` continua significando "use o rótulo padrão".

        ``extras``: ``[(rótulo, função)]`` — as ações laterais ("Todos",
        "Limpar", "Atualizar"). Ficam à ESQUERDA do par, com peso de contorno:
        são do trabalho, não do fechamento da tela.

        ``perigo`` pinta o confirmar de vermelho CONTORNADO (nunca preenchido —
        preenchido, ele atrai o clique de que avisa) e tira dele o Enter.

        Enter confirma e Esc cancela, nas 14 telas. Antes disso, ``setDefault``
        aparecia em 3 delas: nas outras 11 o Enter não fazia nada, e quem digita
        uma senha e aperta Enter concluía que o programa travou.
        """
        linha = QHBoxLayout()
        linha.setSpacing(8)
        botoes: dict = {}
        for rotulo, fn in extras:
            b = QPushButton(rotulo)
            b.setCursor(Qt.PointingHandCursor)
            st.pintar(b, st.btn_contorno)
            if fn is not None:
                b.clicked.connect(fn)
            linha.addWidget(b)
            botoes[rotulo] = b
        linha.addStretch(1)
        if confirmar:
            b_ok = QPushButton(confirmar)
            b_ok.setCursor(Qt.PointingHandCursor)
            st.pintar(b_ok, st.btn_perigo if perigo else st.btn_solido)
            b_ok.clicked.connect(self.accept)
            b_ok.setDefault(not perigo)
            b_ok.setAutoDefault(not perigo)
            linha.addWidget(b_ok)
            botoes[confirmar] = b_ok
            self.botao_confirmar = b_ok
        if cancelar is None:
            self._raiz.addLayout(linha)
            return botoes
        # "Cancelar" ao lado de um confirmar; "Fechar" quando não há o que
        # cancelar. Cancelar numa tela que só mostra sugere que algo estava
        # sendo feito e foi desfeito — e nada estava.
        rotulo_saida = cancelar or ("Cancelar" if confirmar else "Fechar")
        b_nao = QPushButton(rotulo_saida)
        b_nao.setCursor(Qt.PointingHandCursor)
        st.pintar(b_nao, st.btn_fantasma)
        b_nao.clicked.connect(self.reject)
        # Numa tela de leitura o Esc e o botão têm de dar no MESMO lugar. Antes,
        # "Fechar" chamava ``accept`` e o Esc chamava ``reject``: dois caminhos
        # para fechar a mesma janela, e quem lê o código não sabe qual valeu.
        b_nao.setDefault(perigo)
        b_nao.setAutoDefault(perigo)
        linha.addWidget(b_nao)
        botoes[rotulo_saida] = b_nao
        self._raiz.addLayout(linha)
        return botoes


# ── Os pop-ups, todos com a mesma cara ───────────────────────────────────────
# Havia ~75 sítios de pop-up montados um a um: 51 ``QMessageBox`` estático e 24
# à mão. Três coisas divergiam entre eles, e as três custam ao usuário:
#
# * **o verbo**. "Trocar de paciente?" com ``[Sim][Não]`` obriga a reler o
#   título para saber o que "Sim" faz. Os montados à mão já acertavam ("Sim,
#   descartar", "Manter aberto"); os ``question`` estáticos, não. Aqui o verbo
#   é OBRIGATÓRIO — ``confirmar`` não tem valor padrão para ``acao``.
# * **a ordem dos botões**. Ela não é escolha nossa: no Windows o Qt desenha
#   ``[OK][Cancelar]`` — confirmar à ESQUERDA — e isso não se muda. Como os
#   pop-ups são 5× mais frequentes que os diálogos próprios, é ELE que dita o
#   padrão da casa, e não o contrário (ver ``Dialogo.rodape``).
# * **o pai**. Sem pai o pop-up abre no canto da tela, longe de onde a pessoa
#   está olhando. Aqui é o primeiro parâmetro, sempre.
#
# O ícone vem da FUNÇÃO escolhida, não de um parâmetro: assim "isto é um
# aviso" e "isto é uma falha" são decisões tomadas na chamada, legíveis no
# ``grep``, e não um argumento que se copia errado.


def _caixa(pai, icone, titulo: str, texto: str, detalhe: str = "",
           tecnico: str = ""):
    """A caixa montada — o miolo comum das funções abaixo.

    ``detalhe`` vai em ``setInformativeText`` (o segundo parágrafo, menor), que
    é o que 22 dos 24 pop-ups à mão já faziam: o título diz o assunto, o texto
    diz o que houve, o detalhe diz o caminho do arquivo ou a lista de avisos.
    Amontoar tudo no texto principal transformava a pergunta num parágrafo.

    ``tecnico`` vai em ``setDetailedText`` — a gaveta "Mostrar detalhes". É
    outra coisa: o ``detalhe`` é para quem está usando o programa, o
    ``tecnico`` é o rastro cru para quem abre chamado. Misturados, ou o usuário
    lê um caminho de log que não lhe serve, ou a TI perde o rastro.
    """
    msg = QMessageBox(pai)
    msg.setWindowTitle(titulo)
    msg.setIcon(icone)
    msg.setText(texto)
    if detalhe:
        msg.setInformativeText(detalhe)
    if tecnico:
        msg.setDetailedText(tecnico)
    return msg


def _pesar_botoes(msg, solido=None, perigo: bool = False) -> None:
    """Dá aos botões do pop-up o mesmo PESO que eles têm nos diálogos.

    ``Dialogo.rodape`` já faz isto há tempo: sólido no passo que continua o
    trabalho, contorno nas ações laterais, fantasma no que só fecha. Os
    pop-ups nasceram fora dessa regra — três botões idênticos, sem dizer qual
    é o caminho —, e "peso de botão, não matiz" vale para a tela inteira, não
    só para as que herdam de ``Dialogo``.

    A folha vai por ``setStyleSheet`` DIRETO, e não por ``st.pintar``, de
    propósito: ``pintar`` registra um ouvinte de dia↔noite por chamada, e um
    pop-up é criado e destruído a cada uso — seriam ouvintes empilhados por
    pop-up aberto, para widgets que morrem em seguida (ver as armadilhas no
    CLAUDE.md). E não se troca o modo com um modal na frente, então não há o
    que acompanhar.
    """
    for b in msg.buttons():
        b.setCursor(Qt.PointingHandCursor)
        if b is solido:
            b.setStyleSheet(st.btn_perigo() if perigo else st.btn_solido())
        elif msg.buttonRole(b) == QMessageBox.RejectRole:
            b.setStyleSheet(st.btn_fantasma())
        else:
            b.setStyleSheet(st.btn_contorno())


def _so_avisar(icone, pai, titulo, texto, detalhe, tecnico) -> None:
    """Pop-up de um botão só. SEM sólido, de propósito.

    Mesma regra de ``Dialogo.rodape`` para tela de leitura: sólido significa
    "o passo que não se desfaz", e aqui não há passo — o único botão apenas
    reconhece o que já aconteceu. Um sólido ali prometeria um efeito que não
    existe.
    """
    msg = _caixa(pai, icone, titulo, texto, detalhe, tecnico)
    _pesar_botoes(msg)
    msg.exec()


def avisar(pai, titulo: str, texto: str, detalhe: str = "",
           tecnico: str = "") -> None:
    """Deu certo, ou é só informação. Um botão, nada a decidir."""
    _so_avisar(QMessageBox.Information, pai, titulo, texto, detalhe, tecnico)


def alertar(pai, titulo: str, texto: str, detalhe: str = "",
            tecnico: str = "") -> None:
    """Algo merece atenção, mas o trabalho segue."""
    _so_avisar(QMessageBox.Warning, pai, titulo, texto, detalhe, tecnico)


def falhar(pai, titulo: str, texto: str, detalhe: str = "",
           tecnico: str = "") -> None:
    """Não deu para fazer o que foi pedido.

    Separada de ``alertar`` de propósito: "não consegui" e "confira isto" são
    respostas diferentes, e o ícone é a única coisa que as distingue de longe.
    """
    _so_avisar(QMessageBox.Critical, pai, titulo, texto, detalhe, tecnico)


def confirmar(pai, titulo: str, texto: str, acao: str,
              recusa: str = "Cancelar", detalhe: str = "",
              perigo: bool = False) -> bool:
    """Pergunta de duas saídas. ``True`` = a pessoa escolheu ``acao``.

    ``acao`` é **obrigatório e é um verbo** — "Descartar e trocar", "Gerar
    assim mesmo". É a regra que esta função existe para impor: com ``[Sim]
    [Não]`` a resposta depende de reler o título, e o título de um modal que
    interrompe alguém no meio do trabalho é justamente o que não se lê.

    ``recusa`` também é palavra, não "Não": "Manter aberto" diz o que acontece
    ao recusar, e é a saída que se quer tornar fácil quando a outra destrói
    alguma coisa.

    ``perigo`` marca a ação como destrutiva: ela deixa de ser o botão PADRÃO, e
    o Enter passa a recair sobre a recusa. Botão destrutivo que responde ao
    Enter é o caminho mais curto para apagar o trabalho de alguém.
    """
    msg = _caixa(pai, QMessageBox.Question, titulo, texto, detalhe)
    b_acao = msg.addButton(acao, QMessageBox.AcceptRole)
    b_recusa = msg.addButton(recusa, QMessageBox.RejectRole)
    msg.setDefaultButton(b_recusa if perigo else b_acao)
    _pesar_botoes(msg, solido=b_acao, perigo=perigo)
    msg.exec()
    return msg.clickedButton() is b_acao


def escolher(pai, titulo: str, texto: str, opcoes, detalhe: str = "",
             cancelar: str = "Fechar", icone=None) -> str:
    """Pergunta de VÁRIAS saídas. Devolve o rótulo escolhido, ou ``""``.

    Existe porque o programa tem pop-ups de três e de cinco botões — o
    "Simulação cadastrada" oferece abrir a pasta, próximo paciente e fechar.
    Sem ela, esses continuariam montados à mão e o padrão nasceria já com
    exceção.

    Devolve o RÓTULO, não um índice: no ponto de chamada, ``if escolha ==
    "Abrir a pasta"`` diz o que aconteceu, enquanto ``if escolha == 1`` só diz
    onde o botão estava — e mexer na ordem dos botões passaria a trocar de
    ação em silêncio.

    A PRIMEIRA opção é a padrão (a do Enter): é o caminho que continua o
    trabalho, e por isso nenhuma opção destrutiva deve vir primeiro.
    """
    msg = _caixa(pai, icone or QMessageBox.Information, titulo, texto, detalhe)
    botoes = [(rot, msg.addButton(rot, QMessageBox.AcceptRole))
              for rot in opcoes if rot]
    if cancelar:
        msg.addButton(cancelar, QMessageBox.RejectRole)
    if botoes:
        msg.setDefaultButton(botoes[0][1])
    # O sólido é a PRIMEIRA opção, que é a padrão e a que continua o trabalho —
    # a mesma regra do ``Dialogo.rodape``. Por isso a docstring avisa que
    # nenhuma opção destrutiva deve vir primeiro.
    _pesar_botoes(msg, solido=botoes[0][1] if botoes else None)
    msg.exec()
    alvo = msg.clickedButton()
    return next((rot for rot, b in botoes if b is alvo), "")


# ── Atalhos ──────────────────────────────────────────────────────────────────
# O programa tinha DOIS atalhos (Ctrl+Tab e Ctrl+Shift+Tab) e nenhuma barra de
# menus — num programa usado com o paciente na mesa, onde a mão sai do teclado
# para pegar o mouse a cada passo.
#
# Duas regras, e as duas vêm do que já estava escrito no projeto:
#
# * **o atalho segue o botão sólido.** "O sólido anda com o trabalho": com a
#   bancada vazia ele é "Abrir pasta", com o caso carregado é "Impressão".
#   Ctrl+Enter faz o que o sólido faz AGORA — um atalho só, que nunca precisa
#   ser reaprendido porque acompanha a tela.
# * **atalho nenhum em ação destrutiva.** Atalho não pergunta, e a mão erra a
#   tecla. Fechar o caso, apagar, descartar: só no botão.
#
# E o atalho vai ESCRITO no tooltip do botão (ver ``atalho``): atalho que não
# aparece em lugar nenhum não é descoberto, e não ser descoberto é o mesmo que
# não existir.


@contextlib.contextmanager
def trabalhando(pai, mensagem: str):
    """Aviso "estou trabalhando" enquanto um trabalho BLOQUEANTE roda na UI.

    Alguns trabalhos são síncronos na thread da interface — montar o PDF,
    reconstruir o índice a partir de uma árvore de pastas. Durante eles a
    janela não repinta e não responde, e uma tela estática é indistinguível de
    uma tela travada: sem aviso, quem espera clica de novo.

    Por isso o aviso é pintado à força (``processEvents``) ANTES de o trabalho
    começar — depois já não haveria quem o pintasse — e o cursor de espera fica
    por cima. Ele é modal para que o clique repetido não chegue à janela de
    trás.

    Eram duas cópias desta janela, uma na geração do PDF e outra no Reindexar,
    com a mesma borda e margens de 24 e 26 px. Uma usava ``st.pintar``, a outra
    ``setStyleSheet`` — e a divergência não aparecia porque as duas só existem
    por alguns segundos.

    A folha vai por ``setStyleSheet`` DIRETO, e não por ``st.pintar``, pelo
    mesmo motivo do ``_pesar_botoes``: cada ``pintar`` registra um ouvinte de
    dia↔noite, este aviso nasce e morre a cada uso, e não se troca o modo com
    um modal na frente.

    O aviso sai de cena ANTES de o ``with`` devolver, cursor incluído: quem
    chama costuma abrir um pop-up com o desfecho na linha seguinte, e ele
    apareceria por baixo de um aviso de "aguarde" que já não vale.
    """
    dlg = QDialog(pai, Qt.FramelessWindowHint)
    dlg.setModal(True)
    dlg.setStyleSheet(f"QDialog{{background:{st.FUNDO_BLOCO};"
                      f" border:2px solid {st.ACAO_LINHA};"
                      " border-radius:10px;}")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(34, 26, 34, 26)
    lbl = QLabel(mensagem)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"color:{st.ACAO}; font-size:14px; font-weight:bold;"
                      " background:transparent; border:none;")
    lay.addWidget(lbl)
    dlg.show()
    QApplication.setOverrideCursor(Qt.WaitCursor)
    QApplication.processEvents()
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()
        dlg.close()
        dlg.deleteLater()
        QApplication.processEvents()


def atalho(sequencia: str, dono, acao, botao=None,
           contexto=Qt.WindowShortcut):
    """Liga uma tecla a uma ação e a ANUNCIA no botão correspondente.

    ``botao`` opcional: quando vem, o tooltip dele ganha a tecla entre
    parênteses, preservando o que já estava escrito — o motivo de o botão estar
    apagado, por exemplo, que é o texto mais útil da tela.

    O contexto é ``WindowShortcut`` por padrão, e não ``ApplicationShortcut``:
    com um modal aberto, atalho de aplicação continuaria disparando ação na
    janela de trás — que é a definição de clique fantasma.
    """
    atl = QShortcut(QKeySequence(sequencia), dono)
    atl.setContext(contexto)
    atl.activated.connect(acao)
    if botao is not None:
        anunciar_atalho(botao, sequencia)
    return atl


def anunciar_atalho(botao, sequencia: str) -> None:
    """Escreve a tecla no tooltip do botão, sem apagar o que já havia.

    Idempotente: ``definir_ativo`` e companhia reescrevem o tooltip a cada
    mudança de estado, e sem esta guarda o botão acabaria com "(Ctrl+P)
    (Ctrl+P) (Ctrl+P)" depois de três repinturas.
    """
    marca = f"({sequencia})"
    atual = botao.toolTip() or ""
    if marca in atual:
        return
    botao.setToolTip(f"{atual}  {marca}".strip() if atual else marca)


# ── Nomes antigos, valor do modo em vigor ────────────────────────────────────
# ``ui.CAMPO`` e companhia eram constantes montadas no import — congelavam as
# cores do modo que estivesse valendo naquele instante, e a troca dia↔noite
# nunca chegava às telas de Capa e Simulação. Como FUNÇÕES resolvidas na hora do
# acesso, cada widget nasce no modo correto sem mudar nenhuma das chamadas.
_FOLHAS = {
    "CAMPO": _campo,
    "LISTA": _lista,
    "ABAS": _abas,
    "PAGINA_ABA": _pagina_aba,
    "BOTAO_DISCRETO": _btn_discreto,
}


def __getattr__(nome: str) -> str:
    if nome in _FOLHAS:
        return _FOLHAS[nome]()
    raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")
