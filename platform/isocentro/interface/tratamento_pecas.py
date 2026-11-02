"""As peças visuais da aba **Ficha Virtual** — nenhuma delas sabe o que é tratamento.

Saíram do ``tratamento.py`` em 13/10/2026 (R-13, ``docs/PROPOSTA_TRATAMENTO.md``,
corte 1): o arquivo tinha 3.321 linhas e duas naturezas misturadas — as peças
de tela do topo e o ``PainelFichaVirtual``. Medido por AST, nenhuma peça daqui
cita ``tratamento_db``, ``checklist``, ``constantes`` ou ``dicom_rt``: só o
painel conhece o domínio. Por isso a fronteira é esta, e não outra.

Ficaram num arquivo PRÓPRIO, e não no ``ui.py`` (decisão do usuário, 13/10):
nenhuma outra tela as usa hoje, e o ``ui.py`` já passa de mil linhas. Quando
uma segunda tela precisar de ``_Fileira`` ou ``_Elide``, é a hora de promovê-las.

O ``tratamento.py`` reimporta todos os nomes: os testes os citam pelo endereço
antigo (``tratamento._JanelaTexto`` …), e mudar o endereço não era o objetivo.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QLayout, QListWidget, QListWidgetItem, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from isocentro.interface import estilo as st
from isocentro.interface import ui


# Altura de cada linha da lista suspensa dos seletores. Tem de ser aplicada
# item a item (ver ``_popup_legivel``): o ``min-height`` da folha de estilo NÃO
# entra na conta que o Qt faz da altura do pop-up.
_ALTURA_ITEM = 30


# Teto da largura do pop-up. Sem ele, um nome de plano comprido abriria uma
# lista mais larga que a janela — e o que sai pela direita da tela não volta.
_LARG_MAX_POPUP = 900


def _popup_legivel(combo: QComboBox) -> None:
    """Faz a lista suspensa caber e caber INTEIRA. Chamar depois de preencher.

    O seletor de cursos abria com dois itens e meio, cortando o terceiro no
    meio da linha — e o pedaço que sumia era a data, que é o que distingue um
    curso do outro. São dois defeitos do Qt, e nenhum se resolve na folha de
    estilo:

    1. **Altura.** Com folha de estilo aplicada, o Qt calcula a altura do
       pop-up pelo ``sizeHint`` de cada item; o ``min-height`` do
       ``QAbstractItemView::item`` só pinta o item DEPOIS, grande demais para o
       espaço que já foi reservado. Daí a altura ir item a item, pelo
       ``SizeHintRole`` — e, no fim, a altura do conjunto ir cravada, porque o
       cálculo do Qt ainda sobrava a faixa de um item em branco embaixo.
    2. **Largura.** O pop-up nasce com a largura do combo FECHADO, e o combo
       fechado ELIDE o texto. A lista aberta repetia o texto cortado — que é
       justamente o que se abriu a lista para ler.
    """
    if not combo.count():
        return
    fm = combo.fontMetrics()
    largura = 0
    for i in range(combo.count()):
        combo.setItemData(i, QSize(0, _ALTURA_ITEM), Qt.SizeHintRole)
        largura = max(largura, fm.horizontalAdvance(combo.itemText(i)))
    # A folga é o padding do item nos dois lados mais a barra de rolagem, que
    # aparece a partir de ``setMaxVisibleItems`` linhas: medida a menos, e a
    # última palavra sai elidida com o pop-up aberto.
    combo.view().setMinimumWidth(min(largura + 40, _LARG_MAX_POPUP))
    # A altura, CRAVADA no que a lista tem para mostrar. O cálculo do Qt sobra
    # — abre um pop-up de dois cursos com a faixa de um terceiro em branco
    # embaixo, e uma linha vazia numa lista lê-se como opção que não carregou.
    # Cravada aqui ela não depende de estilo nem de DPI: são os itens que
    # existem, vezes a altura que cada um tem.
    #
    # ``frameWidth`` já traz a borda MAIS o padding da folha (medido: 4 px de
    # 1+3), e é por isso que ele não pode virar número fixo: mudar o padding em
    # ``_folha_combo`` voltaria a deixar sobra ou a cortar a última linha.
    visiveis = min(combo.count(), max(1, combo.maxVisibleItems()))
    combo.view().setFixedHeight(
        visiveis * _ALTURA_ITEM + 2 * combo.view().frameWidth())


def _abrir_na_frente(janela) -> int:
    """Abre a modal GARANTIDAMENTE na frente. Um caminho para as quatro.

    ``exec_()`` sozinho não basta no Windows: quando a janela nasce durante o
    processamento de um clique, o sistema pode devolver o foco à janela que
    estava embaixo — e a modal fica atrás dela, viva e invisível, com o app
    aparentemente travado (nada responde, porque há uma modal aberta que
    ninguém vê). Foi o que o usuário relatou em 26/08/2026 ao clicar em
    "Campos".

    A outra metade da correção está nos cliques, que passaram a agir no SOLTAR
    (ver ``_ValorClicavel.mousePressEvent``). As duas juntas, porque uma
    ataca a causa e a outra não deixa o sintoma voltar por outro caminho.
    """
    janela.show()
    janela.raise_()
    janela.activateWindow()
    return janela.exec()


class _Fileira(QLayout):
    """Fileira de cartões que QUEBRA A LINHA em vez de empurrar a janela.

    Os cartões de valor não encolhem — ``setWordWrap(False)``, porque cartão
    que corta o próprio valor não é cartão (ver ``_pintar_valores``). Numa
    ``QHBoxLayout`` isso vira PISO de largura: a soma dos cartões passa a ser o
    mínimo do painel inteiro, e o painel maximizado num monitor de 1920 pedia
    2110 px. O Qt não tem para onde crescer e corta o que fica à direita — foi
    assim que o botão "Trocar paciente" sumiu do canto do cabeçalho, com o
    paciente de TRÊS planos que o usuário mandou em 21/08/2026.

    Aqui o mínimo é o do MAIOR cartão sozinho: a fileira cabe em qualquer
    janela, e o que não coube na primeira linha desce para a segunda. Nada é
    cortado e nada sai da tela — que são as duas coisas que não podem
    acontecer numa tela de conferência.

    Só quebra de linha, sem esticar: os cartões têm a largura do que escrevem
    (esticados em partes iguais, seis deles espremiam tudo em 110 px e a ÚLTIMA
    SESSÃO perdia a hora). A sobra fica à direita, onde antes ficava o
    espaçador.
    """

    def __init__(self, espaco: int = 10, parent=None):
        super().__init__(parent)
        self._itens: list = []
        self._espaco = espaco
        self._altura_dispor = 0
        self._vao = 0
        self.setContentsMargins(0, 0, 0, 0)

    # ── O contrato que todo QLayout precisa cumprir ──────────────────────
    # Sem os cinco, o Qt não sabe percorrer a lista — e a remoção automática
    # de um filho destruído (``setParent(None)``) passa por ``itemAt``/
    # ``takeAt``, não por um método nosso.

    def addItem(self, item):  # noqa: N802 — assinatura do Qt
        self._itens.append(item)

    def count(self) -> int:
        return len(self._itens)

    def itemAt(self, i):  # noqa: N802 — assinatura do Qt
        return self._itens[i] if 0 <= i < len(self._itens) else None

    def takeAt(self, i):  # noqa: N802 — assinatura do Qt
        return self._itens.pop(i) if 0 <= i < len(self._itens) else None

    def expandingDirections(self):  # noqa: N802 — assinatura do Qt
        return Qt.Orientations(Qt.Orientation(0))

    # ── Altura em função da largura ──────────────────────────────────────

    def hasHeightForWidth(self) -> bool:  # noqa: N802 — assinatura do Qt
        return True

    def heightForWidth(self, largura: int) -> int:  # noqa: N802
        return self._dispor(QRect(0, 0, largura, 0), medir=True)

    def setGeometry(self, rect):  # noqa: N802 — assinatura do Qt
        super().setGeometry(rect)
        altura = self._dispor(rect, medir=False)
        # A altura que a quebra de linha PRECISA nesta largura vira o mínimo de
        # altura (ver ``minimumSize``). O Qt só pergunta o mínimo sem largura, e
        # sem isto ele respondia "uma linha": com a janela baixa o cartão do
        # quadro era espremido abaixo do que a fileira usa, e a segunda linha
        # (PARADA, PDF, CHECKLIST, FICHA TÉCNICA) saía cortada pela borda.
        # Só invalida quando muda — a altura depende da largura, e a largura não
        # depende da altura, então não há laço.
        if altura != self._altura_dispor:
            self._altura_dispor = altura
            self.invalidate()

    def sizeHint(self) -> QSize:  # noqa: N802 — assinatura do Qt
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 — assinatura do Qt
        """O MAIOR cartão sozinho na largura — é isto que solta a largura da
        janela — e, na altura, o que a quebra de linha usa agora."""
        s = QSize(0, 0)
        for it in self._itens:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        s = s + QSize(m.left() + m.right(), m.top() + m.bottom())
        return QSize(s.width(), max(s.height(), self._altura_dispor))

    def definir_vao(self, px: int) -> None:
        """O vão da coluna de imagens à direita, em pixels (0 = sem vão).

        É um vão FLEXÍVEL (ver ``_dispor``), e por isso não é uma margem do
        layout: margem é sempre paga, e este só vale quando não custa uma linha.
        """
        px = max(0, int(px))
        if px != self._vao:
            self._vao = px
            self.invalidate()

    def vao(self) -> int:
        return self._vao

    def _dispor(self, rect: QRect, medir: bool) -> int:
        """Coloca os cartões e devolve a altura usada.

        ``medir=True`` só calcula (é o ``heightForWidth``): mover widget ali
        dentro repintaria a tela a cada consulta de tamanho do Qt.

        O vão da coluna de imagens é o que faz os cartões terminarem onde a
        lista de sessões termina — mas SÓ enquanto os cartões cabem assim. Com
        onze cartões (três planos, mais as três portas) o vão empurrava os
        últimos para uma segunda linha, e a segunda linha saía cortada da tela:
        informação escondida para manter um alinhamento. Se o vão custa uma
        linha, ele é dispensado e a fileira usa a largura toda.
        """
        m = self.contentsMargins()
        direita = rect.right() - m.right()
        limite = direita - self._vao
        if self._vao and (self._colocar(rect, limite, True)[1]
                          > self._colocar(rect, direita, True)[1]):
            limite = direita
        return self._colocar(rect, limite, medir)[0]

    def _colocar(self, rect: QRect, direita: int, medir: bool) -> tuple:
        """``(altura usada, número de linhas)`` com os cartões até ``direita``."""
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        alt_linha = 0
        linhas = 1
        for it in self._itens:
            tam = it.sizeHint()
            # ``alt_linha > 0`` guarda o primeiro da linha: sem isso, um cartão
            # mais largo que a faixa inteira desceria para uma linha vazia e
            # continuaria não cabendo — uma linha em branco a cada repinte.
            if alt_linha > 0 and x + tam.width() - 1 > direita:
                x = rect.x() + m.left()
                y += alt_linha + self._espaco
                alt_linha = 0
                linhas += 1
            if not medir:
                it.setGeometry(QRect(QPoint(x, y), tam))
            x += tam.width() + self._espaco
            alt_linha = max(alt_linha, tam.height())
        return y + alt_linha - rect.y() + m.bottom(), linhas


class _NumeroGrande(QWidget):
    """A fração atual, do tamanho de ser lida de longe.

    O valor e o total têm pesos diferentes de propósito: "12" é o que se
    procura, "/ 25" é o contexto. Iguais, o olho tem de ler os dois para achar
    um — que é exatamente o custo que esta tela existe para eliminar.
    """

    def __init__(self, rotulo: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.rot = QLabel(rotulo.upper())
        st.pintar(self.rot, lambda: (
            f"color:{st.TEXTO_FRACO}; font-size:12px; font-weight:700;"
            " letter-spacing:2px; background:transparent;"))
        lay.addWidget(self.rot)

        linha = QHBoxLayout()
        linha.setSpacing(10)
        linha.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.valor = QLabel("—")
        st.pintar(self.valor, lambda: (
            f"color:{st.TEXTO}; font-size:64px; font-weight:bold;"
            " background:transparent;"))
        self.total = QLabel("")
        st.pintar(self.total, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:30px; font-weight:600;"
            " background:transparent;"))
        linha.addWidget(self.valor)
        linha.addWidget(self.total)
        linha.addStretch(1)
        lay.addLayout(linha)

    def definir(self, valor: str, total: str = "") -> None:
        self.valor.setText(valor or "—")
        self.total.setText(total or "")


class _ValorClicavel(ui.Valor):
    """Um cartão de valor que se clica — a forma de dado, o gesto de botão.

    Herda de ``ui.Valor`` em vez de imitá-lo: "mesma formatação" que se copia
    à mão vira formatação parecida na primeira vez que a original mudar.

    Apagado (``definir_ativo(False)``) ele perde o cursor de mão e o clique:
    cartão aceso que só avisa que não deu é a promessa que este projeto não
    faz. A opacidade é o único desvio de aparência, e é o que diz "isto aqui
    não está disponível agora" sem tirar o campo da fileira — e sem ele a
    fileira mudaria de tamanho conforme houvesse ficha ou não.
    """

    clicado = Signal()

    def __init__(self, rotulo: str, valor: str, tom: str = "azul", parent=None):
        super().__init__(rotulo, valor, tom, parent)
        self._ativo = True
        self.definir_ativo(True)

    def definir_ativo(self, ativo: bool) -> None:
        self._ativo = bool(ativo)
        self.setCursor(Qt.PointingHandCursor if self._ativo
                       else Qt.ArrowCursor)
        efeito = QGraphicsOpacityEffect(self)
        efeito.setOpacity(1.0 if self._ativo else 0.45)
        self.setGraphicsEffect(efeito)

    def mousePressEvent(self, e):  # noqa: N802 — assinatura do Qt
        """Só ACEITA o clique. Quem age é o ``mouseReleaseEvent``.

        Agir aqui abria a janela com o botão do mouse ainda apertado: o Windows
        entrega o SOLTAR à janela que estava sob o cursor — a principal —, e ela
        vem para a frente por cima da modal recém-aberta. Foi o que o usuário
        viu em 26/08/2026 ao clicar em "Campos": a janela abria ATRÁS.

        Soltar também é o gesto certo de um botão: quem aperta e arrasta para
        fora desiste, e no apertar não havia como desistir.
        """
        if self._ativo:
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):  # noqa: N802 — assinatura do Qt
        # Só quando o dedo é solto DENTRO do cartão: arrastar para fora é
        # desistir, e é o que dá a chance de corrigir a mira.
        if self._ativo and self.rect().contains(e.pos()):
            self.clicado.emit()
        else:
            super().mouseReleaseEvent(e)


class _JanelaTexto(ui.Dialogo):
    """A nota de posicionamento inteira, em tamanho de leitura.

    Irmã da ``_JanelaImagem``, e não a mesma janela: o conteúdo da nota é
    TEXTO, e rasterizá-lo para caber no mesmo caminho das fotos daria um
    borrão ao ampliar — justamente no gesto que existe para poder LER. Aqui o
    texto continua texto: nítido em qualquer tamanho e selecionável para quem
    quiser copiar um acessório.
    """

    def __init__(self, texto: str, titulo: str = "", procedencia: str = "",
                 parent=None):
        super().__init__(titulo or "Nota de posicionamento", parent)
        lay = self.corpo
        # ``texto`` e não ``corpo``: ``corpo`` é o layout do ``ui.Dialogo``, e
        # um QLabel com esse nome o apagaria da instância — a janela abriria
        # sem rodapé e sem lugar para o próprio texto.
        self.texto = QLabel(texto)
        self.texto.setWordWrap(True)
        self.texto.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.texto.setTextInteractionFlags(Qt.TextSelectableByMouse)
        st.pintar(self.texto, lambda: (
            f"color:{st.TEXTO}; font-size:16px; line-height:150%;"))
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        rolagem.setWidget(self.texto)
        st.pintar(rolagem, lambda: (
            "QScrollArea{background:transparent; border:none;}"
            "QScrollArea > QWidget > QWidget{background:transparent;}"
            + ui.barras()))
        lay.addWidget(rolagem, 1)
        # A mesma linha de procedência da ``_JanelaImagem``, pelo mesmo motivo
        # e no mesmo lugar: a nota também é dado de outra montagem quando o
        # paciente tem duas, e quem lê precisa saber de qual.
        self.procedencia = QLabel(procedencia)
        st.pintar(self.procedencia, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:12px; padding-top:10px;"))
        # ``setVisible`` DEPOIS do ``addWidget`` — ver ``_JanelaCampos``.
        lay.addWidget(self.procedencia)
        self.procedencia.setVisible(bool(procedencia))
        self.rodape()
        tela = QApplication.primaryScreen().availableGeometry()
        self.resize(min(760, int(tela.width() * 0.6)),
                    min(560, int(tela.height() * 0.7)))


class _Nota(QLabel):
    """A palavra POSICIONAMENTO do título, que abre a nota ao ser clicada.

    A nota NÃO ocupa lugar na tela (escolhido com o usuário em 21/08/2026):
    como ladrilho ela roubava um terço da faixa das fotos para mostrar um texto
    ilegível de tão miúdo, e como rodapé competia com a procedência das
    imagens. Aqui ela não ocupa nada — a própria palavra do título é a porta —
    e quem precisa do conteúdo clica e o lê inteiro.

    Sem nota a palavra continua ali, como título, sem cursor de mão e sem cor
    de ação: título que promete clique e não faz nada é pior que título mudo.
    """

    def __init__(self, texto: str = "POSICIONAMENTO", parent=None):
        super().__init__(texto, parent)
        self._texto = ""
        self._procedencia = ""
        st.pintar(self, self._folha)

    def _folha(self) -> str:
        # A MESMA fonte do título do cartão (ver ``ui.Cartao._titulo``): a
        # palavra faz parte dele, e qualquer corpo diferente a destacaria como
        # se fosse outra coisa. Com nota, muda só a COR — e o sublinhado, que é
        # o que diz "isto se clica" sem depender de cor.
        base = "font-size:11px; font-weight:bold; letter-spacing:1px;"
        if self._texto:
            return f"color:{st.ACAO}; {base} text-decoration:underline;"
        return f"color:{st.TEXTO_FRACO}; {base}"

    def definir(self, texto: str) -> None:
        self._texto = (texto or "").strip()
        self.setStyleSheet(self._folha())
        self.setCursor(Qt.PointingHandCursor if self._texto
                       else Qt.ArrowCursor)
        self.setToolTip("Clique para ler a nota de posicionamento"
                        if self._texto else "")

    def tem_nota(self) -> bool:
        return bool(self._texto)

    def definir_procedencia(self, texto: str = "") -> None:
        """De que montagem é esta nota. Aparece ao abrir, não no título."""
        self._procedencia = texto or ""

    def mousePressEvent(self, e):  # noqa: N802 — assinatura do Qt
        # No SOLTAR, como os cartões-porta: abrir com o botão apertado deixa a
        # janela atrás da principal (ver ``_ValorClicavel.mousePressEvent``).
        if self._texto:
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):  # noqa: N802 — assinatura do Qt
        if self._texto and self.rect().contains(e.pos()):
            _abrir_na_frente(_JanelaTexto(
                self._texto, "Nota de posicionamento",
                self._procedencia, self))
        else:
            super().mouseReleaseEvent(e)


class _JanelaImagem(QDialog):
    """A imagem grande, do tamanho da tela. Fecha no clique ou no Esc.

    Sem botões e sem barra de ferramentas: a janela existe para UMA coisa — ver
    o corte de perto —, e qualquer controle a mais é uma pergunta que ela não
    precisa fazer. Fechar no próprio clique é o gesto que quem abriu já tem na
    mão.
    """

    def __init__(self, dados: bytes, titulo: str = "", procedencia: str = "",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo or "Imagem")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._lbl = QLabel()
        self._lbl.setAlignment(Qt.AlignCenter)
        st.pintar(self, lambda: f"background:{st.FUNDO_TELA};")
        lay.addWidget(self._lbl)
        # De ONDE veio a imagem — aqui, e não no rosto do cartão (pedido do
        # usuário em 22/08/2026: "fica mais clean"). A procedência continua
        # obrigatória, e continua a um clique: um corte de duas versões atrás
        # mostra um alvo que já não é o do tratamento em curso, e imagem sem
        # procedência é a pior espécie de imagem numa tela de conferência. O
        # que mudou é QUANDO ela aparece — no gesto de olhar de perto, que é
        # quando alguém decide alguma coisa por ela.
        self.procedencia = QLabel(procedencia)
        self.procedencia.setAlignment(Qt.AlignCenter)
        st.pintar(self.procedencia, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:12px; padding:8px 12px;"))
        # ``setVisible`` DEPOIS do ``addWidget`` — ver ``_JanelaCampos``.
        lay.addWidget(self.procedencia)
        self.procedencia.setVisible(bool(procedencia))
        pix = QPixmap()
        pix.loadFromData(dados)
        # 90% da tela DISPONÍVEL (sem a barra de tarefas), e nunca ampliando
        # além do tamanho original: um PNG de 900px esticado para 1800 vira
        # borrão, e borrão numa imagem de conferência é pior que imagem pequena.
        tela = QApplication.primaryScreen().availableGeometry()
        alvo = pix.size().scaled(int(tela.width() * 0.9),
                                 int(tela.height() * 0.9), Qt.KeepAspectRatio)
        if alvo.width() > pix.width():
            alvo = pix.size()
        self._lbl.setPixmap(pix.scaled(alvo, Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation))
        # A linha de procedência entra na ALTURA da janela. Sem somá-la, o Qt
        # espremia a imagem para caber os dois no tamanho de um só — e o gesto
        # todo existe para ver o corte MAIOR, não menor.
        self.resize(alvo.width(),
                    alvo.height() + (self.procedencia.sizeHint().height()
                                     if procedencia else 0))

    def pixmap_vazio(self) -> bool:
        """A imagem chegou a ser montada? Existe para o teste poder afirmar
        isso sem abrir a janela modal, que travaria a suíte."""
        pix = self._lbl.pixmap()
        return pix is None or pix.isNull()

    def mousePressEvent(self, e):  # noqa: N802 — assinatura do Qt
        self.accept()


class _ImagemEscalada(QLabel):
    """Um PNG que acompanha a largura disponível, mantendo a proporção.

    Guarda os BYTES, não o ``QPixmap`` já escalado: o cartão muda de largura
    quando a janela muda, e reescalar a partir de uma cópia já reduzida perde
    definição a cada passo — num corte de TC isso vira borrão em duas
    redimensionadas.
    """

    clicada = Signal()

    def __init__(self, vazio: str = "", titulo: str = "", parent=None):
        super().__init__(parent)
        self._dados: Optional[bytes] = None
        self._vazio = vazio
        self._titulo = titulo
        # De onde veio a imagem. Guardada aqui e mostrada só na janela grande —
        # ver ``_JanelaImagem``.
        self._procedencia = ""
        self.setAlignment(Qt.AlignCenter)
        # Piso baixo de propósito: as duas imagens empilhadas na coluna da
        # direita davam 302 px de mínimo e, com o quadro completo, o painel
        # pedia mais altura que a tela tem — o rodapé saía da janela. Aqui o piso
        # só pesa com a janela apertada; folgada, elas crescem (Expanding).
        self.setMinimumHeight(55)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        st.pintar(self, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:11px;"))
        self.setText(vazio)

    def definir(self, dados: Optional[bytes]) -> None:
        self._dados = dados or None
        # O cursor de mão SÓ com imagem: ele é a promessa de que o clique faz
        # alguma coisa, e numa moldura vazia essa promessa é falsa.
        self.setCursor(Qt.PointingHandCursor if self._dados
                       else Qt.ArrowCursor)
        self.setToolTip("Clique para ver em tamanho grande"
                        if self._dados else "")
        self._reescalar()

    def definir_procedencia(self, texto: str = "") -> None:
        """De onde veio esta imagem. Aparece ao abrir, não no cartão."""
        self._procedencia = texto or ""

    def mousePressEvent(self, e):  # noqa: N802 — assinatura do Qt
        # No SOLTAR, como os cartões-porta: abrir com o botão apertado deixa a
        # janela atrás da principal (ver ``_ValorClicavel.mousePressEvent``).
        if self._dados:
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):  # noqa: N802 — assinatura do Qt
        if self._dados and self.rect().contains(e.pos()):
            _abrir_na_frente(_JanelaImagem(
                self._dados, self._titulo, self._procedencia, self))
        self.clicada.emit()

    def tem_imagem(self) -> bool:
        return self._dados is not None

    def _reescalar(self) -> None:
        if not self._dados:
            self.setPixmap(QPixmap())
            self.setText(self._vazio)
            return
        pix = QPixmap()
        if not pix.loadFromData(self._dados):
            self.setPixmap(QPixmap())
            self.setText(self._vazio)
            return
        self.setText("")
        self.setPixmap(pix.scaled(max(1, self.width()), max(1, self.height()),
                                  Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e):  # noqa: N802 — assinatura do Qt
        super().resizeEvent(e)
        self._reescalar()


class _Barra(QWidget):
    """O andamento em barra. Desenhada à mão, não ``QProgressBar``.

    A barra do Qt herda o tema do sistema operacional e sai azul do Windows no
    meio de uma tela que tem paleta própria — e, pior, ela anima quando o valor
    muda, o que numa tela de consulta lê-se como "está carregando".

    A cor é a de AÇÃO, que nesta paleta é o verde-azulado. Aqui isso não fere a
    regra "verde é dose": a barra não é um elemento de interface que se clica,
    é a própria grandeza sendo mostrada.
    """

    ALTURA = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 0
        self.setFixedHeight(self.ALTURA)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._trilho = QWidget(self)
        self._cheio = QWidget(self)
        st.pintar(self._trilho, lambda: (
            f"background:{st.FUNDO_CAMPO}; border:1px solid {st.BORDA};"
            f" border-radius:{self.ALTURA // 2}px;"))
        st.pintar(self._cheio, lambda: (
            f"background:{st.ACAO}; border-radius:{self.ALTURA // 2}px;"))
        self._recolocar()

    def definir(self, pct: int) -> None:
        self._pct = max(0, min(100, int(pct or 0)))
        self._recolocar()

    def _recolocar(self) -> None:
        larg = max(0, self.width())
        self._trilho.setGeometry(0, 0, larg, self.ALTURA)
        cheio = int(larg * self._pct / 100)
        self._cheio.setGeometry(0, 0, cheio, self.ALTURA)
        # Zero por cento não desenha nada: uma pílula de 16 px de largura no
        # começo da barra lê-se como "já começou", e não começou.
        self._cheio.setVisible(cheio >= self.ALTURA)

    def resizeEvent(self, e):  # noqa: N802 - assinatura do Qt
        super().resizeEvent(e)
        self._recolocar()


class _ComboMedico(QComboBox):
    """De quem é a lista: um médico, ou todos.

    Até 22/09/2026 esta caixa fazia duas coisas ao mesmo tempo — escolher o
    médico e formar o grupo —, com caixinhas dentro da lista suspensa. Quem
    abria via uma coluna de nomes sem hierarquia nenhuma e tinha de deduzir que
    marcar vários era o jeito de somar agendas. Agora a caixa responde uma
    pergunta só, e o grupo tem botão próprio embaixo (ver
    :class:`_SeletorMedicos`).
    """

    TODOS = "Todos os médicos"

    mudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        # Folha PRÓPRIA, não a de campo de texto: ``ui.CAMPO`` traz um padding
        # pensado para ``QLineEdit`` e, num combo dentro do cabeçalho do cartão,
        # ele empurrava o nome do médico para fora da caixa — o texto saía
        # cortado ao meio na horizontal.
        self.setFixedHeight(32)
        st.pintar(self, lambda: (
            f"QComboBox {{ background:{st.FUNDO_CAMPO}; color:{st.TEXTO};"
            f"  border:1px solid {st.BORDA}; border-radius:7px;"
            "   padding:0 8px; font-size:12.5px; }"
            "QComboBox::drop-down { border:none; width:18px; }"
            f"QComboBox QAbstractItemView {{ background:{st.FUNDO_BLOCO};"
            f"  color:{st.TEXTO}; selection-background-color:{st.ACAO_FUNDO};"
            f"  border:1px solid {st.BORDA}; }}"))
        self._silencio = False
        self.currentIndexChanged.connect(self._trocou)

    def definir(self, medicos: list, escolhido: str = "") -> None:
        """Repõe a lista. ``escolhido`` é o nome BRUTO, "" = todos."""
        self._silencio = True
        self.clear()
        # "Todos os médicos" é o PRIMEIRO item, e existe de propósito: é assim
        # que o físico e o admin olham o serviço inteiro, e era o estado de quem
        # não marcava ninguém na caixa antiga.
        self.addItem(self.TODOS, None)
        for m in medicos:
            self.addItem(m.nome, m)
        alvo = 0
        for i in range(1, self.count()):
            if self.itemData(i).bruto == escolhido:
                alvo = i
                break
        self.setCurrentIndex(alvo)
        self._silencio = False

    def escolhido(self):
        """O :class:`Medico` selecionado, ou ``None`` para "todos"."""
        return self.currentData()

    def _trocou(self, _indice) -> None:
        if not self._silencio:
            self.mudou.emit()


class _DialogGrupoMedicos(ui.Dialogo):
    """Com quem este médico divide a agenda.

    Caixinhas numa janela própria, e não na tela: o grupo é escolhido uma vez e
    depois fica parado por semanas, então ele não merece ocupar altura
    permanente numa tela cujo assunto é outro.

    O médico da caixa de cima NÃO aparece na lista para marcar: ele está sempre
    dentro. Oferecê-lo desmarcável criaria um estado em que a caixa diz um nome
    e a lista mostra a agenda de outro.
    """

    def __init__(self, medicos: list, principal, marcados=(), parent=None):
        super().__init__("Grupo Médico", parent)
        alvo = {m for m in marcados}
        explica = QLabel(
            f"A lista mostra sempre os pacientes de <b>{principal.nome}</b>. "
            "Marque quem mais entra na agenda em conjunto.")
        explica.setWordWrap(True)
        st.pintar(explica, lambda: f"color:{st.TEXTO_FRACO}; font-size:12px;")
        self.corpo.addWidget(explica)
        self.lista = QListWidget()
        st.pintar(self.lista, lambda: ui.LISTA)
        for m in medicos:
            if m.bruto == principal.bruto:
                continue
            item = QListWidgetItem(m.nome)
            item.setData(Qt.UserRole, m)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked if m.bruto in alvo else Qt.Unchecked)
            self.lista.addItem(item)
        self.corpo.addWidget(self.lista, 1)
        self.rodape("Usar este grupo", "Cancelar",
                    extras=[("Limpar", self._limpar)])
        self.resize(360, 460)

    def _limpar(self) -> None:
        """Desmarca todos — o caminho de volta para "só os meus".

        Sem ele, desfazer um grupo de oito médicos é desmarcar oito caixas, e
        quem desiste no meio fica com um grupo que não é o de antes nem o novo.
        """
        for i in range(self.lista.count()):
            self.lista.item(i).setCheckState(Qt.Unchecked)

    def escolhidos(self) -> list:
        """Os nomes BRUTOS marcados, sem o principal."""
        return [self.lista.item(i).data(Qt.UserRole).bruto
                for i in range(self.lista.count())
                if self.lista.item(i).checkState() == Qt.Checked]


class _SeletorMedicos(QWidget):
    """A caixa do médico e, ao lado ou embaixo dela, o botão do Grupo Médico.

    Pedido do usuário em 22/09/2026, e a razão é de quem usa: o radioterapeuta
    abre a aba para ver a SUA agenda, e de vez em quando precisa ver a do colega
    junto — férias, plantão, quem cobre quem. As duas coisas são perguntas
    diferentes e por isso têm controles diferentes; a caixa única com caixinhas
    dentro respondia as duas de um jeito que não se descobre olhando.

    O que sai daqui é o mesmo de antes: uma lista de médicos (vazia = todos),
    com o PRINCIPAL na frente. Quem consome é ``tratamento_db.em_tratamento``,
    que não distingue um do outro — a hierarquia é da tela.

    ``horizontal``: o combo e o botão lado a lado, numa linha só de altura
    única — pedido do usuário em 24/09/2026, para a aba **Agenda**
    (:mod:`agenda_tela`), onde o empilhado (o padrão, ainda usado na Ficha
    Virtual — ver :meth:`PainelFichaVirtual._cartao_painel`) deixava "Só os meus"
    flutuando no meio da altura dupla do bloco, em vez de alinhado com o
    combo.
    """

    mudou = Signal()

    def __init__(self, parent=None, horizontal: bool = False):
        super().__init__(parent)
        lay = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8 if horizontal else 4)
        self.combo = _ComboMedico()
        self.combo.mudou.connect(self._trocou_o_medico)
        lay.addWidget(self.combo)

        self.btn_grupo = QPushButton("👥  Grupo Médico")
        self.btn_grupo.setCursor(Qt.PointingHandCursor)
        st.pintar(self.btn_grupo, lambda: st.btn_contorno(12.0))
        self.btn_grupo.clicked.connect(self.abrir_grupo)
        lay.addWidget(self.btn_grupo)

        self._medicos: list = []
        self._grupo: list = []          # nomes BRUTOS, sem o principal
        self._atualizar_botao()

    # ── O que a janela põe e tira ──────────────────────────────────────────

    def definir(self, medicos: list, marcados=()) -> None:
        """Repõe a lista de médicos e a escolha.

        ``marcados`` são nomes BRUTOS, o PRIMEIRO sendo o principal — é a ordem
        em que :meth:`escolhidos` os entrega e em que o ``QSettings`` os grava.
        Uma escolha gravada pela caixa antiga (multisseleção sem principal) é
        lida do mesmo jeito: o primeiro nome vira o principal e o resto vira
        grupo, que é o mais próximo do que a pessoa tinha.
        """
        self._medicos = list(medicos)
        brutos = [str(m or "") for m in marcados if str(m or "").strip()]
        principal = brutos[0] if brutos else ""
        # Só os que ainda existem na lista do banco: um médico que saiu do
        # serviço ficaria filtrando a lista para sempre, invisível.
        existentes = {m.bruto for m in self._medicos}
        self._grupo = [b for b in brutos[1:] if b in existentes]
        self.combo.definir(self._medicos, principal)
        self._atualizar_botao()

    def escolhidos(self) -> list:
        """Os :class:`Medico` da lista — vazio quando é "todos"."""
        principal = self.combo.escolhido()
        if principal is None:
            return []
        por_bruto = {m.bruto: m for m in self._medicos}
        fora = [principal]
        fora += [por_bruto[b] for b in self._grupo if b in por_bruto]
        return fora

    # ── O botão ────────────────────────────────────────────────────────────

    def abrir_grupo(self) -> None:
        principal = self.combo.escolhido()
        if principal is None:
            return
        d = _DialogGrupoMedicos(self._medicos, principal, self._grupo, self)
        if d.exec() != QDialog.Accepted:
            return
        novo = d.escolhidos()
        if novo == self._grupo:
            return
        self._grupo = novo
        self._atualizar_botao()
        self.mudou.emit()

    def _trocou_o_medico(self) -> None:
        principal = self.combo.escolhido()
        if principal is None:
            # "Todos" já mostra o serviço inteiro: somar um grupo a isso não
            # muda nada, e deixar o grupo guardado faria o botão anunciar um
            # número que não está valendo.
            self._grupo = []
        else:
            # O principal nunca fica no grupo: ele entra pela caixa de cima, e
            # nas duas listas ele apareceria duas vezes na consulta.
            self._grupo = [b for b in self._grupo if b != principal.bruto]
        self._atualizar_botao()
        self.mudou.emit()

    def _atualizar_botao(self) -> None:
        tem_medico = self.combo.escolhido() is not None
        self.btn_grupo.setEnabled(tem_medico and len(self._medicos) > 1)
        if not tem_medico:
            self.btn_grupo.setText("👥  Grupo Médico")
            self.btn_grupo.setToolTip(
                "Escolha um médico acima para montar um grupo. Com \"Todos os "
                "médicos\" a lista já mostra o serviço inteiro.")
            return
        # O NÚMERO no rótulo: um grupo montado semanas atrás continua valendo, e
        # sem ele a pessoa lê a lista como se fosse só a dela — que é o modo de
        # errar mais caro desta tela.
        self.btn_grupo.setText(
            "👥  Grupo Médico" if not self._grupo else
            f"👥  Grupo Médico · +{len(self._grupo)}")
        self.btn_grupo.setToolTip(
            "Ver a agenda em conjunto com outros médicos."
            if not self._grupo else
            "Em conjunto com: " + ", ".join(
                m.nome for m in self.escolhidos()[1:]))


class _Elide(QLabel):
    """Rótulo de largura fixa que corta o texto com reticências.

    ``QLabel`` de largura fixa CLIPA: o texto some no meio de uma letra, sem
    aviso. E cortar por número de caracteres (``nome[:30]``) erra porque a fonte
    é proporcional — "MILL" e "WWWW" ocupam larguras diferentes.

    A elisão é refeita no ``resizeEvent`` de propósito: só ali a folha de estilo
    já foi aplicada e a ``fontMetrics`` conhece o tamanho real da fonte. Feita no
    ``__init__``, ela mediria a fonte padrão do Qt e cortaria no lugar errado.
    """

    def __init__(self, texto: str = "", parent=None):
        super().__init__(parent)
        self._inteiro = texto
        self.setText(texto)

    def definir(self, texto: str) -> None:
        self._inteiro = texto or ""
        self._reelidir()

    def _reelidir(self) -> None:
        largura = max(0, self.width())
        if largura:
            self.setText(self.fontMetrics().elidedText(
                self._inteiro, Qt.ElideRight, largura))

    def resizeEvent(self, e):  # noqa: N802 - assinatura do Qt
        super().resizeEvent(e)
        self._reelidir()


class _LinhaPainel(QWidget):
    """Uma linha do painel, montada com layout — não com espaços.

    A primeira versão era texto monoespaçado preenchido com ``:<30``. Não
    alinhava, e não tinha como: os símbolos das marcas NÃO têm a largura da
    fonte monoespaçada (o ``⚠`` é largo, o ``✓`` é estreito), então cada linha
    empurrava o nome para um lugar diferente. Vinte e cinco linhas assim viram
    um muro de texto torto.

    Com layout, cada coluna tem largura própria e o nome pode usar fonte
    proporcional — que é a que se lê rápido.
    """

    LARG_MARCAS = 46
    LARG_NOME = 330
    # A coluna do médico só existe na agenda em CONJUNTO (Grupo Médico, ou
    # "Todos"): na lista de um médico só ela repetiria o mesmo nome em vinte e
    # cinco linhas, empurrando o resto para a direita sem dizer nada.
    LARG_MEDICO = 170
    LARG_FRACAO = 68
    LARG_CURSOS = 74
    LARG_DATA = 52
    LARG_NOTA = 300
    # Altura à MÃO, e não pelo ``sizeHint``. O palpite do Qt é calculado antes
    # de ele aplicar a folha de estilo, então ele não sabe que os rótulos são de
    # 13 px: as linhas saíam com uns 26 px e cortavam as letras em cima e
    # embaixo. Vinte e cinco linhas mutiladas foi o "layout de doer os olhos".
    ALTURA = 34

    def __init__(self, e, hoje=None, parent=None, mostrar_medico: bool = False):
        super().__init__(parent)
        self.setFixedHeight(self.ALTURA)
        # Um filete embaixo de cada linha. Vinte e cinco linhas sem separação
        # nenhuma leem-se como um bloco de texto, e o olho perde a linha ao
        # atravessar da esquerda (nome) para a direita (nota). O filete é
        # SUAVE de propósito: grade forte vira planilha e compete com o dado.
        self.setObjectName("linha")
        st.pintar(self, lambda: (
            f"QWidget#linha {{ border-bottom:1px solid {st.BORDA_SUAVE}; }}"))
        marcas = e.marcas(hoje)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(10)

        # As marcas primeiro, em largura fixa: é a coluna que se varre de cima a
        # baixo, e ela só funciona se todos os símbolos começarem no mesmo x.
        simbolos = QLabel("".join(s for s, _t in marcas))
        simbolos.setFixedWidth(self.LARG_MARCAS)
        urgente = any(s == "⚠" for s, _t in marcas)
        st.pintar(simbolos, lambda u=urgente: (
            f"color:{st.AMBAR if u else st.TEXTO_APAGADO}; font-size:13px;"))
        lay.addWidget(simbolos)

        # Largura FIXA, não elástica. Com o nome esticando, numa tela de 1900 px
        # abria-se um vão de 700 px entre ele e a fração: o olho não liga o
        # paciente ao próprio número atravessando isso, e o resto da linha ficava
        # espremido na borda direita. Colunas presas à esquerda leem-se de cima a
        # baixo; colunas espalhadas pela largura da janela, não.
        nome = _Elide(e.nome)
        nome.setFixedWidth(self.LARG_NOME)
        st.pintar(nome, lambda: (
            f"color:{st.TEXTO}; font-size:13px; font-weight:600;"))
        lay.addWidget(nome)

        if mostrar_medico:
            # Colada no nome do paciente, e apagada: é atributo DELE, não uma
            # grandeza do tratamento. Entre os números ela competiria com a
            # fração, que é o que se varre de cima a baixo.
            #
            # O "+1" diz que o paciente tem mais de um oncologista vinculado e
            # que este é um deles (ver o SQL em ``tratamento_db``). Sem ele, o
            # nome sozinho afirmaria uma exclusividade que o banco não disse.
            extra = e.medicos_total > 1
            self.medico = _Elide(
                (e.medico or "—") + (" +1" if extra else ""))
            self.medico.setFixedWidth(self.LARG_MEDICO)
            st.pintar(self.medico, lambda: (
                f"color:{st.TEXTO_APAGADO}; font-size:12px;"))
            if extra:
                self.medico.setToolTip(
                    f"{e.medico} — este paciente tem mais de um médico "
                    "vinculado; a lista mostra um deles.")
            elif not e.medico:
                self.medico.setToolTip("Sem médico vinculado no sistema.")
            lay.addWidget(self.medico)

        fracao = QLabel(f"{e.entregues}/{e.previstas or '?'}")
        fracao.setFixedWidth(self.LARG_FRACAO)
        fracao.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        st.pintar(fracao, lambda: (
            f"color:{st.ACAO}; font-size:13.5px; font-weight:bold;"))
        lay.addWidget(fracao)

        # Quantos cursos o paciente já teve. Contagem, não ordinal ("3º"):
        # com "incluir concluídos" ligado a linha pode ser de um curso ANTIGO, e
        # aí o ordinal mentiria. "3 cursos" é verdade nos dois casos.
        #
        # A coluna aparece SEMPRE, inclusive no "1 curso": mostrar só quando há
        # retratamento faria "vazio" significar duas coisas — primeiro curso e
        # contagem que não veio.
        cursos = QLabel("—" if not e.cursos_total else
                        f"{e.cursos_total} curso" +
                        ("s" if e.cursos_total > 1 else ""))
        cursos.setFixedWidth(self.LARG_CURSOS)
        cursos.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        retratado = e.cursos_total > 1
        st.pintar(cursos, lambda r=retratado: (
            f"color:{st.TEXTO_FRACO if r else st.TEXTO_APAGADO};"
            f" font-size:11.5px;{' font-weight:600;' if r else ''}"))
        if not e.cursos_total:
            cursos.setToolTip("Não consegui contar os cursos deste paciente.")
        lay.addWidget(cursos)

        data = QLabel(e.ultima.strftime("%d/%m") if e.ultima else "—")
        data.setFixedWidth(self.LARG_DATA)
        data.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        st.pintar(data, lambda: f"color:{st.TEXTO_APAGADO}; font-size:12px;")
        lay.addWidget(data)

        # A nota é a marca MAIS urgente em palavras. Elidida à direita, para
        # nunca alargar a linha — barra horizontal numa lista que se varre de
        # cima a baixo é o pior dos mundos.
        self.nota = _Elide(marcas[0][1] if marcas else "")
        self.nota.setFixedWidth(self.LARG_NOTA)
        st.pintar(self.nota, lambda u=urgente: (
            f"color:{st.AMBAR if u else st.TEXTO_FRACO}; font-size:12px;"))
        lay.addWidget(self.nota)
        # Toda a sobra da janela vai para o FIM. É o que mantém as colunas
        # juntas, em qualquer largura de tela.
        lay.addStretch(1)

        if len(marcas) > 1:
            self.setToolTip("\n".join(f"{s}  {t}" for s, t in marcas))
