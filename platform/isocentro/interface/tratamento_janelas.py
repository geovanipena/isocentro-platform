"""As duas janelas grandes da aba **Ficha Virtual**: o checklist e os campos do plano.

Saíram do ``tratamento.py`` em 13/10/2026 (R-13, corte 2 da
``docs/PROPOSTA_TRATAMENTO.md``). São diálogos fechados: ``_JanelaChecklist``
não cita nada do módulo de onde veio, e ``_JanelaCampos`` só a ``_Fileira``,
que está nas peças. Trazem o único uso de ``ficha_pdf`` fora do painel.

O ``tratamento.py`` reimporta as duas: os testes as citam pelo endereço antigo.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractScrollArea, QApplication, QGridLayout, QHeaderView, QLabel,
    QPushButton, QSizePolicy, QStyle, QTableWidget, QTableWidgetItem, QWidget)

from isocentro.papel import ficha_pdf
from isocentro.interface import estilo as st
from isocentro.interface import ui
from isocentro.interface.tratamento_pecas import _Fileira


class _JanelaChecklist(ui.Dialogo):
    """O Checklist Pré-Tratamento da contracapa, conferível AQUI.

    Os itens e as colunas são os do papel (``checklist.ITENS`` reexporta
    ``capa_pdf.CHECKLIST_ITENS``): a folha continua saindo impressa e continua
    sendo assinada: esta janela existe para responder, de outra estação e sem a
    folha na mão, se aquele paciente já passou pela conferência.

    Cada linha tem as quatro marcas em botões EXCLUSIVOS entre si — marcar
    "conforme" e "não conforme" no mesmo item é um estado que o papel não
    permite, e permitir aqui deixaria a tela afirmar as duas coisas. Clicar na
    marca já acesa a APAGA: é como se desfaz um clique errado, e sem isso a
    única saída seria deixar registrada uma conferência que ninguém quis fazer.

    Grava a CADA clique, e não num botão "Salvar" no pé. Conferência se faz com
    o paciente na porta e se interrompe no meio; o que ficou marcado até a
    interrupção é informação verdadeira, e um Salvar que ninguém apertou a
    jogaria fora inteira.
    """

    # (item, marca) — marca vazia = desmarcar. Quem grava é a janela principal.
    marcou = Signal(str, str)

    def __init__(self, marcas: dict, itens=(), colunas=(), legenda: str = "",
                 titulo: str = "", parent=None):
        super().__init__(titulo or "Checklist Pré-Tratamento", parent)
        self._itens = list(itens)
        self._colunas = list(colunas)
        self._botoes: dict = {}
        self._assinaturas: dict = {}
        self._teto_assinatura = 0     # medido no primeiro ``showEvent``
        # SEM título repetido dentro da janela: a barra de título já o traz, e
        # é assim que as outras telas próprias do app fazem (Configurações,
        # Histórico). Repetido, ele gastava a primeira linha para dizer o que
        # já estava escrito uma linha acima.
        lay = self.corpo

        # A grade numa SUPERFÍCIE própria (``ui.Cartao``, o mesmo bloco da
        # janela de Campos e do resto do app): solta no fundo da tela, ela não
        # se lia como uma coisa só — eram seis frases e vinte e quatro botões
        # sobre o nada, sem nada dizendo onde a conferência começa e termina.
        self.bloco = ui.Cartao()
        grade = QGridLayout()
        grade.setHorizontalSpacing(6)
        # Respiro entre as linhas: com 6 px, item e botões de linhas vizinhas
        # ficavam à mesma distância um do outro, e o olho que vai da frase até
        # a coluna certa pulava de linha no meio do caminho.
        grade.setVerticalSpacing(9)
        # Coluna 0 = item; 1..n = marcas; n+1 = quem marcou. O item leva o
        # espaço que sobra: são frases ("Prescrição Médica (capa x ficha)"), e
        # elidi-las esconderia justamente o que se está atestando.
        grade.setColumnStretch(0, 1)
        for j, nome in enumerate(self._colunas):
            rot = QLabel(nome)
            rot.setAlignment(Qt.AlignCenter)
            # ``background:transparent`` em tudo que mora no cartão: sem
            # isso o rótulo herda o fundo da TELA e vira um retângulo cinza
            # sobre a superfície clara do bloco.
            st.pintar(rot, lambda: (
                f"color:{st.TEXTO_FRACO}; font-size:11px; font-weight:700;"
                " background:transparent;"))
            grade.addWidget(rot, 0, j + 1)
        assin = QLabel("QUEM CONFERIU")
        st.pintar(assin, lambda: (
            f"color:{st.TEXTO_FRACO}; font-size:11px; font-weight:700;"
            " background:transparent;"))
        grade.addWidget(assin, 0, len(self._colunas) + 1)
        # Uma linha fina separando o cabeçalho dos itens — só ela: uma por
        # item viraria uma tabela, e o que se lê aqui é a lista, não a grade.
        grade.addWidget(ui.divisor(), 1, 0, 1, len(self._colunas) + 2)

        for i, item in enumerate(self._itens):
            rot = QLabel(item)
            rot.setWordWrap(True)
            # Largura mínima do ITEM, e a coluna da assinatura sem esticar (ver
            # abaixo). Sem as duas coisas o Qt dava 182 px à frase que se está
            # atestando e 595 ao nome de quem marcou: "Prescrição Médica (capa
            # x ficha)" quebrava em três linhas ao lado de um vão vazio. O que
            # se lê aqui é o ITEM — o nome é conferência do que já foi feito.
            rot.setMinimumWidth(240)
            st.pintar(rot, lambda: (f"color:{st.TEXTO}; font-size:13px;"
                                    " background:transparent;"))
            grade.addWidget(rot, i + 2, 0)
            for j, marca in enumerate(self._colunas):
                b = QPushButton(marca)
                b.setCheckable(True)
                b.setFixedSize(52, 28)
                b.setCursor(Qt.PointingHandCursor)
                st.pintar(b, self._folha_marca)
                # ``item``/``marca`` amarrados por padrão do argumento: sem
                # isso todo botão fecharia sobre a ÚLTIMA volta do laço e as
                # seis linhas marcariam o mesmo item.
                b.clicked.connect(
                    lambda _c, it=item, mc=marca: self._clicou(it, mc))
                grade.addWidget(b, i + 2, j + 1)
                self._botoes[(item, marca)] = b
            quem = QLabel("")
            # TETO de largura, não só política de tamanho: a política sozinha
            # não impede a COLUNA de crescer, e sem o teto o Qt dava 595 px ao
            # nome de quem marcou e 240 à frase que se está atestando —
            # invertido, porque o que se lê aqui é o item.
            #
            # O teto é MEDIDO na fonte, sobre a data (que tem largura fixa),
            # nunca um número de pixels escolhido a olho: a mesma folha de
            # estilo dá larguras diferentes por fonte e por DPI, e um valor
            # cravado cortaria a data em metade das estações. Nome comprido
            # quebra a linha em vez de sumir.
            quem.setWordWrap(True)
            quem.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
            st.pintar(quem, lambda: (
                f"color:{st.TEXTO_APAGADO}; font-size:11.5px;"
                " background:transparent;"))
            grade.addWidget(quem, i + 2, len(self._colunas) + 1)
            self._assinaturas[item] = quem
        self.bloco.corpo.addLayout(grade)

        # A legenda das siglas fica DENTRO do bloco, colada na grade que ela
        # explica: "C: conforme  N/C: não conforme…" é o cabeçalho por extenso,
        # e solta no pé da janela virava um parágrafo à parte de algo que só
        # faz sentido ao lado dos botões.
        self.legenda = QLabel(legenda)
        self.legenda.setWordWrap(True)
        st.pintar(self.legenda, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:11.5px;"
            " background:transparent;"))
        # ``setVisible`` DEPOIS do ``addWidget`` — ver ``_JanelaCampos``: sem
        # pai, o rótulo é uma JANELA, e a legenda piscava no meio do monitor.
        self.bloco.corpo.addWidget(self.legenda)
        self.legenda.setVisible(bool(legenda))
        lay.addWidget(self.bloco)
        lay.addStretch(1)

        # Tela de LEITURA no rodapé, e não por descuido: cada marca já foi ao
        # disco no clique (ver ``_clicou``), então não há o que confirmar aqui.
        # Um "Salvar" prometeria que fechar sem ele desfaz — e não desfaz.
        self.rodape()
        self.definir_marcas(marcas)
        # Do tamanho do que mostra, como a janela de Campos: a largura sai da
        # frase mais longa mais as colunas de marca, e não de um 720 fixo que
        # sobrava de um lado e faltava do outro conforme a estação.
        tela = QApplication.primaryScreen().availableGeometry()
        self.resize(min(self.sizeHint().width(), int(tela.width() * 0.6)),
                    min(self.sizeHint().height(), int(tela.height() * 0.9)))

    def showEvent(self, e):  # noqa: N802 — assinatura do Qt
        """O teto da coluna de assinatura, medido quando a fonte é a de verdade.

        A folha de estilo é que define o corpo (11,5px), e ela só chega ao
        ``fontMetrics`` do widget quando ele é exibido: medindo no ``__init__``
        — com ou sem ``ensurePolished`` — mede-se a fonte PADRÃO, e o teto saía
        apertado para a própria data que ele existe para acomodar.

        O teto é medido, nunca cravado: a mesma folha dá larguras diferentes
        por fonte e por DPI, e um número escolhido a olho cortaria a data em
        metade das estações.
        """
        super().showEvent(e)
        if self._assinaturas and not self._teto_assinatura:
            qualquer = next(iter(self._assinaturas.values()))
            teto = qualquer.fontMetrics().horizontalAdvance("00/00/0000 00:00") + 14
            # Mínimo E máximo: só o máximo deixava a coluna ser ESPREMIDA pela
            # largura da janela até abaixo da data (238 px para uma data de
            # 272), e o teto não servia para nada. Fixando os dois, a coluna
            # tem exatamente o tamanho do que escreve e a janela cresce para
            # acomodá-la — a sobra continua indo para a coluna do item, que é
            # a única com esticador.
            for rot in self._assinaturas.values():
                rot.setMinimumWidth(teto)
                rot.setMaximumWidth(teto)
            self._teto_assinatura = teto

    def _folha_marca(self) -> str:
        """Marcado = sólido; livre = contorno.

        Peso, não matiz (regra do projeto): as quatro marcas são a MESMA
        pergunta respondida de quatro jeitos, e pintar "não conforme" de
        vermelho aqui faria o olho procurar o vermelho em vez de ler a linha.
        O que importa de relance é ONDE está a marca, não qual é.
        """
        return (
            f"QPushButton {{ background:transparent; color:{st.TEXTO_FRACO};"
            f"  border:1px solid {st.BORDA}; border-radius:7px;"
            "   font-size:11.5px; font-weight:700; }"
            f"QPushButton:hover {{ border-color:{st.ACAO}; }}"
            f"QPushButton:checked {{ background:{st.ACAO}; color:{st.FUNDO_TELA};"
            f"  border-color:{st.ACAO}; }}")

    def _clicou(self, item: str, marca: str) -> None:
        """Exclusividade e desmarcar, num lugar só."""
        botao = self._botoes.get((item, marca))
        # ``setCheckable`` já inverteu o estado no clique. Se ele ficou LIGADO,
        # é marcação; se ficou desligado, o usuário clicou na marca que já
        # estava acesa — e isso apaga.
        ligou = bool(botao and botao.isChecked())
        self.marcou.emit(item, marca if ligou else "")

    def definir_marcas(self, marcas: dict) -> None:
        """Repõe a grade a partir do que está GRAVADO.

        A tela não decide sozinha o que ficou marcado: ela pede, a janela
        principal grava e devolve o arquivo lido de novo. Sem essa volta, um
        erro de gravação deixaria a marca acesa na tela e ausente no disco —
        que é o pior desfecho possível para uma conferência.
        """
        marcas = marcas or {}
        for (item, marca), b in self._botoes.items():
            b.blockSignals(True)
            b.setChecked((marcas.get(item) or {}).get("marca") == marca)
            b.blockSignals(False)
        for item, rot in self._assinaturas.items():
            dado = marcas.get(item) or {}
            quem = str(dado.get("por") or "")
            quando = self._data_br(dado.get("em"))
            # DUAS linhas, não uma. Numa linha só, "usuario.exemplo · 25/08/2026
            # 10:15" não cabia na coluna, e alargá-la para caber tirava da
            # coluna do ITEM — que é o texto que se está atestando. Empilhados,
            # os dois cabem folgados na altura que a linha já tem.
            #
            # Sem quem, nada — nem um traço. Rótulo vazio já diz "ninguém
            # marcou"; um "—" no lugar do nome de quem conferiu se lê como
            # "conferido por alguém que não sei quem é".
            rot.setText(f"{quem}\n{quando}".strip() if quem else "")

    @staticmethod
    def _data_br(iso) -> str:
        """``2026-08-25T10:15:00`` → ``25/08/2026 10:15``.

        O arquivo guarda ISO (ordenável e sem ambiguidade de fuso); a tela
        mostra o formato do serviço. Todo o resto do app escreve dd/mm/aaaa, e
        uma data em outro formato nesta janela se lê como dado de outra fonte.
        """
        texto = str(iso or "")
        if len(texto) < 10:
            return ""
        ano, mes, dia = texto[:4], texto[5:7], texto[8:10]
        hora = texto[11:16]
        return f"{dia}/{mes}/{ano} {hora}".strip()


class _JanelaCampos(ui.Dialogo):
    """Os campos de tratamento da pág. 2 da ficha JÁ ELABORADA.

    LEITURA, como o resto da aba: é o que foi impresso e foi para a sala, lido
    do ``plano_rp`` da versão salva. Recalcular aqui exigiria a TC inteira, que
    esta aba não tem — e, mais importante, o que se quer conferir é o papel que
    está na mesa, não uma segunda versão dele.

    A tabela é TRANSPOSTA em relação à leitura natural — uma coluna por campo,
    uma linha por grandeza —, e é assim de propósito: é o desenho da folha
    impressa, e quem confere alterna entre as duas o tempo todo. Virar a grade
    aqui obrigaria a reaprender onde cada número está.
    """

    def __init__(self, plano: list, campos: list, linhas: list,
                 origem: str = "", parent=None):
        super().__init__("Ficha Técnica — Campos", parent)
        # Sem título repetido dentro da janela: a barra já o traz (ver
        # ``_JanelaChecklist``).
        lay = self.corpo

        # TRÊS blocos, na ordem da folha: os dados do plano, a geometria do
        # setup e a grade dos campos. Eram onze cartões e uma grade soltos na
        # mesma coluna, sem nada que dissesse onde um assunto termina e o outro
        # começa — a fileira quebrava no meio dos SSD e o corte parecia
        # acidental, porque era. Os blocos são os ``ui.Cartao`` do resto do
        # app: mesma superfície, mesmo título miúdo.
        self._cartoes: list = []
        self._fileiras: list = []
        self.bloco_plano = self._bloco(
            "Dados do plano",
            [(i, r, v) for i, (r, v) in enumerate(plano or [])
             if not isinstance(v, list)], linhas=2)
        # Os trios (os dois SSD e o deslocamento) num bloco SÓ deles: são a
        # geometria do setup, não a prescrição, e é o grupo que quem posiciona
        # o paciente procura primeiro. Separá-los também põe os três na mesma
        # linha — juntos com os outros oito, a quebra caía onde calhasse.
        self.bloco_setup = self._bloco(
            "SSD e deslocamento",
            [(i, r, v) for i, (r, v) in enumerate(plano or [])
             if isinstance(v, list)])

        # Os CAMPOS numa grade de verdade — uma coluna por campo, uma linha por
        # grandeza, como a folha impressa. Era texto monoespaçado num rótulo, e
        # o rótulo centrava o bloco no meio de uma janela vazia: a tabela
        # flutuava com metade da tela em branco à volta.
        self.tabela = QTableWidget(0, 0)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.verticalHeader().setDefaultAlignment(
            Qt.AlignRight | Qt.AlignVCenter)
        # ``ResizeToContents`` aqui é para MEDIR: é dele que sai a largura
        # natural de cada coluna, que vira o piso do ``Stretch`` logo adiante
        # (ver ``_ajustar_grade``). O piso é o que garante a rolagem horizontal
        # com 21 campos — eles não cabem em tela nenhuma, e espremer a coluna
        # esconderia o UM, que é o número que se confere.
        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        st.pintar(self.tabela, ui.grade)
        self._preencher(campos, linhas)
        self._ajustar_grade()
        self.bloco_campos = ui.Cartao("Campos")
        # A grade ocupa o bloco inteiro, sem esticador ao lado: as COLUNAS é
        # que dividem o espaço que sobra (ver ``_ajustar_grade``). Com o
        # esticador, a tabela ficava com a largura dos números e o resto do
        # bloco em branco.
        self.bloco_campos.corpo.addWidget(self.tabela, 1)
        # O esticador FECHA o bloco: a grade tem teto de altura (ver
        # ``_ajustar_grade``) e, sobrando espaço, o Qt repartia a folga entre o
        # título e a grade — o nome do bloco flutuava a meia altura, longe do
        # que ele nomeia. Com ele, a sobra fica toda embaixo, onde não separa
        # nada de nada.
        self.bloco_campos.corpo.addStretch(0)
        lay.addWidget(self.bloco_campos, 1)

        self.origem = QLabel(origem)
        self.origem.setWordWrap(True)
        st.pintar(self.origem, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:11.5px;"))
        # ``setVisible`` DEPOIS de entrar no layout. Antes dele o rótulo não
        # tem pai — e no Qt um widget sem pai É UMA JANELA: "Da ficha
        # elaborada" abria como uma telinha de 107×16 no meio do monitor, que
        # sumia quando o ``addWidget`` lhe dava um pai. Era a "mini tela que
        # pisca" relatada em 26/08/2026 ao abrir os Campos.
        lay.addWidget(self.origem)
        self.origem.setVisible(bool(origem))

        # Leitura: a janela mostra o que já foi impresso e não muda nada.
        self.rodape()
        self._dimensionar()

    def _bloco(self, titulo: str, itens: list, linhas: int = 1):
        """Um ``ui.Cartao`` com uma fileira de cartões de valor dentro.

        ``itens`` é ``[(posição no plano, rótulo, valor)]`` — a posição vem de
        fora porque é ela que dá o TOM: a alternância azul↔neutro é da fileira
        inteira, e recomeçá-la em cada bloco deixaria dois vizinhos da mesma
        cor na emenda.

        ``linhas`` é em quantas o bloco PODE quebrar sem ficar estranho — é o
        que ``_dimensionar`` usa para decidir a largura da janela. Os oito
        cartões do plano cabem bem em duas; os três trios, não: quebrá-los
        separa o SSD do deslocamento que se confere junto.

        Lista vazia não vira bloco nenhum: cartão com título e nada dentro
        promete um dado que a ficha não gravou.
        """
        if not itens:
            return None
        cartao = ui.Cartao(titulo)
        faixa = QWidget()
        fileira = _Fileira(espaco=8)
        faixa.setLayout(fileira)
        for pos, rot, val in itens:
            tom = "azul" if pos % 2 == 0 else "neutro"
            # Valor em LISTA é um trio de posições (os dois SSD e o
            # deslocamento): vai para o cartão de três colunas, que escreve o
            # eixo em cima de cada número. Num cartão comum eles saíam como
            # "90,1 / 85,3 / 84,8", e descobrir de quem era o número do meio
            # custava duas contagens — a da barra e a do rótulo.
            v = (ui.ValorTrio(rot, val, tom, faixa)
                 if isinstance(val, list)
                 else ui.Valor(rot, val, tom, faixa))
            v.nao_quebrar()            # ver ``_pintar_valores``
            fileira.addWidget(v)
            self._cartoes.append(v)
        cartao.corpo.addWidget(faixa)
        self._fileiras.append((fileira, max(linhas, 1)))
        self.corpo.addWidget(cartao)
        return cartao

    def _dimensionar(self) -> None:
        """A janela do tamanho do que ela MOSTRA, dentro do que a tela tem.

        Era 1100×620 fixo. Com dois campos, a grade ocupava um quarto da
        largura e o resto era deserto — e vazio à direita de uma tabela se lê
        como coluna que não carregou, que é o contrário do que esta janela
        precisa dizer. Com 21 campos, o mesmo 1100 cortava a grade.

        A largura é a do bloco mais LARGO: a soma dos cartões de uma fileira
        numa linha só, ou a grade inteira. Somada aqui porque a ``_Fileira``
        pede de propósito a largura de um cartão sozinho (é o que a faz quebrar
        linha em vez de empurrar a janela) — perguntar a ela devolveria uma
        janela do tamanho do maior cartão.
        """
        tela = QApplication.primaryScreen().availableGeometry()
        # Margens da janela + as do ``ui.Cartao`` que hospeda a fileira, mais a
        # borda de 1 px e uma folga: faltando 2 px, o último cartão desce
        # sozinho para uma segunda linha e a quebra parece defeito.
        molduras = 18 * 2 + 16 * 2 + 2 + 10
        larg = self._larg_grade + molduras
        # Cada bloco pede a largura de que precisa DIVIDIDA pelas linhas em que
        # ele pode quebrar (ver ``_bloco``): os três trios inteiros numa linha,
        # os oito cartões do plano em duas. Exigir os oito numa linha só dava
        # uma janela de 950 px com uma grade de 300 px dentro — o resto era
        # deserto, e vazio à direita de uma tabela se lê como coluna que não
        # carregou.
        for fileira, linhas in self._fileiras:
            itens = [fileira.itemAt(i) for i in range(fileira.count())]
            pedido = (sum(it.sizeHint().width() for it in itens)
                      + 8 * max(len(itens) - 1, 0)) / linhas
            # Nunca menos que o maior cartão: dividido, o pedido pode ficar
            # abaixo dele, e aí a fileira estoura a janela em vez de quebrar.
            pedido = max(pedido, max(it.sizeHint().width() for it in itens))
            larg = max(larg, int(pedido) + molduras)
        larg = min(larg, int(tela.width() * 0.86))
        # A altura vem DEPOIS da largura: as fileiras só sabem quantas linhas
        # vão ocupar depois de saber em que largura cabem (``heightForWidth``).
        self.resize(larg, self.sizeHint().height())
        # A grade entra na conta pela altura que TEM para mostrar, não pela que
        # pede: ela pede pouco de propósito (precisa poder encolher e rolar
        # quando a tela é baixa), e a janela nascia cortando as três últimas
        # grandezas — Coll, Mesa e o UM — numa tela que tinha espaço de sobra.
        alt = self.sizeHint().height()
        if self._alt_grade:
            alt += max(self._alt_grade - self.tabela.sizeHint().height(), 0)
        self.resize(larg, min(alt, int(tela.height() * 0.9)))

    def _preencher(self, campos: list, linhas: list) -> None:
        """Enche a grade: colunas = campos, linhas = grandezas.

        A linha "Campo" da folha vira o CABEÇALHO da coluna — é a mesma
        informação, e como cabeçalho ela fica congelada no topo em vez de rolar
        junto e sumir na primeira linha que se desce.

        Sem campos, a grade não fica vazia: uma tabela em branco se lê como
        "não carregou", e o caso é outro — a ficha não gravou campo nenhum.
        """
        self._vazia = not campos or not linhas
        if self._vazia:
            self.tabela.setRowCount(1)
            self.tabela.setColumnCount(1)
            self.tabela.setHorizontalHeaderLabels([""])
            self.tabela.setVerticalHeaderLabels([""])
            item = QTableWidgetItem("Esta ficha não tem campos gravados.")
            item.setTextAlignment(Qt.AlignCenter)
            self.tabela.setItem(0, 0, item)
            self.tabela.horizontalHeader().setSectionResizeMode(
                QHeaderView.Stretch)
            return
        # A linha do NÚMERO sai da grade — ela virou o cabeçalho da coluna.
        grandezas = [(rot, chave) for rot, chave in linhas
                     if chave != "numero"]
        self.tabela.setRowCount(len(grandezas))
        self.tabela.setColumnCount(len(campos))
        self.tabela.setVerticalHeaderLabels([r for r, _c in grandezas])
        self.tabela.setHorizontalHeaderLabels(
            [ficha_pdf.valor_do_campo(c, "numero", i)
             for i, c in enumerate(campos)])
        for col, feixe in enumerate(campos):
            for lin, (_rot, chave) in enumerate(grandezas):
                # A MESMA regra de célula do papel (``valor_do_campo``).
                # Montá-la aqui deixava o número do campo em branco, o
                # colimador 0° sumindo e o arco virando ângulo parado — três
                # jeitos de a tela discordar da folha que está na mesa.
                item = QTableWidgetItem(
                    ficha_pdf.valor_do_campo(feixe, chave, col))
                item.setTextAlignment(Qt.AlignCenter)
                self.tabela.setItem(lin, col, item)

    def _ajustar_grade(self) -> None:
        """As colunas dividem o espaço que sobra, sem nunca espremer.

        A grade ficava com a largura exata dos campos e o resto do bloco vazio:
        com dois campos, 300 px de tabela e 230 px de nada ao lado — e vazio à
        direita de uma tabela se lê como coluna que não carregou. (O papel faz
        assim de propósito, e lá continua: a grade preta não se estende por
        colunas vazias, ver ``ficha_pdf._tabela_campos``. Aqui não sobra coluna
        vazia nenhuma — são as colunas REAIS que ficam mais largas.)

        ``Stretch`` com ``setMinimumSectionSize`` no maior conteúdo é o que faz
        as duas coisas ao mesmo tempo: sobrando espaço as colunas crescem
        juntas, faltando espaço elas param no tamanho do que escrevem e a
        grade ganha a barra horizontal — que é o comportamento certo com 21
        campos, porque espremer a coluna esconderia o UM.
        """
        # ``AdjustIgnored`` (o padrão) e não ``AdjustToContents``: com as
        # colunas em ``Stretch``, pedir o tamanho do conteúdo devolvia a
        # largura JÁ esticada e o Qt concluía que ela não cabia na viewport —
        # a grade abria com uma barra horizontal de 1 px de sobra, embaixo de
        # uma tabela que cabia inteira.
        self.tabela.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.tabela.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._larg_grade = self._alt_grade = 0
        if self._vazia:
            return
        cab = self.tabela.horizontalHeader()
        # As larguras naturais ANTES de trocar o modo: depois de ``Stretch`` o
        # Qt já responde a largura esticada, e tanto o mínimo da coluna quanto
        # o tamanho da janela sairiam do tamanho da JANELA — que é justamente o
        # que eles deveriam determinar.
        larguras = [cab.sectionSize(c) for c in range(self.tabela.columnCount())]
        minimo = max(max(larguras), 46)
        cab.setMinimumSectionSize(minimo)
        cab.setSectionResizeMode(QHeaderView.Stretch)
        # A largura que a grade PRECISA é o mínimo vezes o número de campos, e
        # não a soma das larguras naturais: com ``Stretch`` toda coluna passa a
        # valer pelo menos o mínimo, que é o da coluna mais larga (a do
        # "181→90"). Somando as naturais, a grade de 9 campos pedia 449 px onde
        # precisava de 486 e abria com a última coluna cortada.
        #
        # O rótulo das grandezas, a moldura e a BARRA VERTICAL entram na conta:
        # com 13 linhas ela quase sempre existe, e o que ela ocupa sai da
        # largura das colunas.
        # ``sizeHint`` do cabeçalho vertical, não ``width``: no construtor ele
        # ainda tem a largura padrão (45 px) e só cresce para caber "Gantry" e
        # "Energia" no primeiro layout — 37 px que faltavam na conta e saíam da
        # última coluna.
        vcab = self.tabela.verticalHeader()
        self._larg_grade = (minimo * len(larguras)
                            + max(vcab.width(), vcab.sizeHint().width())
                            + 2 * self.tabela.frameWidth()
                            + self.tabela.style().pixelMetric(
                                QStyle.PM_ScrollBarExtent) + 8)
        # Linha um pouco mais baixa que o padrão do Qt (37 px): são 13
        # grandezas, e com a linha folgada a grade não cabia na altura da tela
        # — a janela abria com barra vertical e o UM, que é a última linha,
        # ficava fora da vista. ``Fixed`` junto: sozinho,
        # ``setDefaultSectionSize`` só vale para linha criada DEPOIS dele, e as
        # 13 já estavam preenchidas.
        vh = self.tabela.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Fixed)
        vh.setDefaultSectionSize(30)
        # A altura do que ela TEM para mostrar, como TETO. Sem teto, a grade
        # esticava até o fim do bloco e sobrava uma faixa vazia embaixo da
        # última linha — a mesma leitura de "não carregou" que o vazio ao lado
        # das colunas dava. Teto e não altura fixa: faltando espaço na tela,
        # ela precisa poder encolher e rolar.
        #
        # A altura vem de ``rowHeight``, e não de um número escolhido aqui: o
        # ``padding`` da folha (``ui.grade``) dá o piso da linha, e um teto
        # calculado com uma linha mais baixa do que a pintada cortava a
        # ÚLTIMA — que é o UM.
        self._alt_grade = (
            cab.sizeHint().height()
            + sum(self.tabela.rowHeight(r)
                  for r in range(self.tabela.rowCount()))
            + 2 * self.tabela.frameWidth() + 2)
        self.tabela.setMaximumHeight(self._alt_grade)

    def valor_na_grade(self, rotulo: str, campo: int = 0) -> str:
        """O que está escrito numa célula. Existe para o teste poder afirmar
        que a tela mostra o mesmo que o papel, sem remontar a grade."""
        for lin in range(self.tabela.rowCount()):
            if self.tabela.verticalHeaderItem(lin).text() == rotulo:
                item = self.tabela.item(lin, campo)
                return item.text() if item is not None else ""
        return ""
