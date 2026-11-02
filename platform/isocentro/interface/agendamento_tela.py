"""O diálogo que monta o agendamento do tratamento, e os chips que ele usa.

Separado de ``gui.py`` em 27/08/2026: só ``DialogAgendamento`` tinha mais de
mil linhas, num arquivo que já passava de nove mil. Não confundir com
``agendamento.py`` (importado aqui como ``ag``): lá está a REGRA — sequência de
etapas, resumo, projeção de datas; aqui está a tela que a opera.

O endereço antigo continua valendo: ``gui.py`` reimporta ``DialogAgendamento``
e ``DialogSepararFicha``, que são o nome que a suíte já usa em 18 lugares.
"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QMimeData, QPropertyAnimation, Qt,
                          QTimer)
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QMenu, QPushButton, QScrollArea, QSpinBox,
    QToolButton, QVBoxLayout, QWidget, QWidgetAction)

from isocentro.dominio import agendamento as ag
from isocentro.interface import estilo
from isocentro.interface import ui
from isocentro.interface.estilo import _estilo_btn_menu, _estilo_btn_sel, _marcar_ativo


# Menu dos botões "Planos ▾" e "Somar dose ▾": os chips ficam dentro dele, então
# o menu é só a moldura (fundo do diálogo + borda azul).
_ESTILO_MENU_AG = (
    f"QMenu{{background:{estilo.FUNDO_BLOCO};"
        f" border:1px solid {estilo.BORDA}; border-radius:8px;}}")

# Larguras do agendamento: rótulo ("Ficha:"/"Tipo:"/"Frequência:") e botões
# seletores/ação, para as três linhas ficarem alinhadas coluna a coluna e os
# botões do mesmo tamanho.
_LARG_ROTULO_AG = 86
_LARG_BTN_AG = 132

_DICA_SOMAR_DOSE = (
    "Dose acumulada no mapa de frações (pág. 3).\n"
    "Clique para agrupar: planos com a MESMA letra somam a dose num total "
    "contínuo — use nos planos sequenciais da MESMA região (fase → boost).\n"
    "Sem letra, cada plano acumula só a dose dele.")

# Plano desmarcado no "Planos ▾" não está no agendamento: sem dia nenhum, ele não
# tem linha no mapa da pág. 3, não tem dose para somar e não compõe a ficha.
_DICA_FORA_DO_AGENDAMENTO = (
    "Fora do agendamento (menu \"Planos\").\n"
    "Sem nenhum dia, este plano não tem linha no mapa de frações nem dose para "
    "acumular — marque-o em \"Planos ▾\" para usá-lo aqui.")

# ── Diálogo de agendamento do tratamento ─────────────────────────────────────


class _ChipPlano(QPushButton):
    """Chip de plano no agendamento.

    Clique = marca/desmarca o plano no dia; ARRASTAR = reordena a ordem dos
    planos nas páginas 2 e 3 (igual a arrastar as abas reordena os cortes). O
    clique só alterna no soltar; iniciar um arraste no meio cancela o clique,
    então as duas ações não conflitam. Soltar sobre outro chip pede à janela
    para mover este plano para a posição do alvo.
    """

    _MIME = "application/x-ficha-plano-idx"

    def __init__(self, rotulo: str, pidx: int, on_drop, parent=None):
        super().__init__(rotulo, parent)
        self._pidx = pidx          # índice do plano que este chip representa
        self._on_drop = on_drop    # callback(origem_pidx, alvo_pidx)
        self._press = None
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setToolTip("Clique para marcar/desmarcar; arraste para reordenar "
                        "os planos (páginas 2 e 3).")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.pos()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if (self._press is not None and (e.buttons() & Qt.LeftButton)
                and (e.pos() - self._press).manhattanLength()
                >= QApplication.startDragDistance()):
            self._press = None
            self.setDown(False)
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(self._MIME, str(self._pidx).encode())
            drag.setMimeData(mime)
            drag.setPixmap(self.grab())
            drag.exec(Qt.MoveAction)
            return
        super().mouseMoveEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(self._MIME):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(self._MIME):
            e.acceptProposedAction()

    def dropEvent(self, e):
        if not e.mimeData().hasFormat(self._MIME):
            return
        try:
            origem = int(bytes(e.mimeData().data(self._MIME)).decode())
        except ValueError:
            return
        if origem != self._pidx:
            self._on_drop(origem, self._pidx)
        e.acceptProposedAction()


class DialogSepararFicha(ui.Dialogo):
    """Escolhe QUAIS planos carregados compõem a ficha (pode marcar vários).

    Serve para dividir um caso de vários planos em fichas SEPARADAS: só os
    planos marcados entram no documento (cortes, tabela do plano, mapa de
    frações e Relatório de Alta). Os não marcados seguem carregados, prontos
    para uma segunda ficha depois — nada é apagado aqui.
    """

    def __init__(self, itens, marcados, cores, bloqueados=None, parent=None):
        """``itens``: [(índice do plano, rótulo)] na ordem em que aparecem.

        ``bloqueados``: índices que NÃO podem compor a ficha — os que estão fora
        do agendamento ("Planos ▾"). Aparecem travados e desmarcados, com o
        motivo na dica: omiti-los faria a lista mudar de tamanho sem explicação.
        """
        super().__init__("Separar Ficha", parent)
        self._bloqueados = set(bloqueados or ())
        self.setMinimumWidth(420)
        root = self.corpo

        tit = QLabel("Marque os planos que devem compor esta ficha. Os não "
                     "marcados ficam de fora do documento — continuam "
                     "carregados e podem virar outra ficha depois.")
        tit.setWordWrap(True)
        estilo.pintar(tit, lambda: (
            f"font-weight:bold; font-size:13px; color:{estilo.ACAO};"))
        root.addWidget(tit)

        self._chks = []   # [(índice do plano, QCheckBox)]
        for i, rotulo in itens:
            travado = i in self._bloqueados
            chk = QCheckBox(rotulo + ("   (fora do agendamento)" if travado else ""))
            chk.setChecked(i in marcados and not travado)
            chk.setEnabled(not travado)
            chk.setToolTip(_DICA_FORA_DO_AGENDAMENTO if travado else "")
            chk.setCursor(Qt.ArrowCursor if travado else Qt.PointingHandCursor)
            chk.setStyleSheet("color:%s; font-weight:600;"
                              % (estilo.TEXTO_APAGADO if travado else cores[i % len(cores)]))
            chk.toggled.connect(self._validar)
            root.addWidget(chk)
            self._chks.append((i, chk))

        self._aviso = QLabel("Marque ao menos um plano.")
        estilo.pintar(self._aviso, lambda: (
            f"color:{estilo.AMBAR}; font-weight:bold;"))
        root.addWidget(self._aviso)

        # Este rodapé era o pior do programa: "Cancelar" ANTES de "Aplicar"
        # (invertido em relação a todo o resto), os três com peso de contorno —
        # nenhum sólido — e ``Expanding``, o que dava a "Cancelar" a mesma
        # largura e o mesmo peso do botão que conclui o trabalho.
        botoes = self.rodape(
            "Aplicar",
            extras=[("Todos", self._marcar_todos)])
        self._b_ok = botoes["Aplicar"]
        botoes["Todos"].setToolTip(
            "Marca todos os planos do agendamento." if self._bloqueados
            else "Volta à ficha única, com todos os planos carregados.")
        self._validar()

    def _marcar_todos(self) -> None:
        for i, c in self._chks:
            if i not in self._bloqueados:
                c.setChecked(True)

    def _validar(self, *_) -> None:
        """Uma ficha sem plano nenhum não existe: Aplicar só com ≥1 marcado."""
        algum = any(c.isChecked() for _i, c in self._chks)
        self._b_ok.setEnabled(algum)
        self._aviso.setVisible(not algum)

    def resultado(self) -> list:
        """Índices dos planos marcados (crescente)."""
        return sorted(i for i, c in self._chks if c.isChecked())


class DialogAgendamento(ui.Dialogo):
    """Monta o agendamento do tratamento por DIAS, de forma visual.

    Cada dia entrega os planos marcados por N frações, na ordem de cima para
    baixo. Modelos rápidos (sequencial, simultâneo) e ajuste dia a dia cobrem os
    cenários. Um contador acompanha as frações agendadas por plano e avisa
    quando fecham.
    """

    # Hexadecimal cru, de propósito: são as CORES DE PLANO, e um plano tem de
    # sair da mesma cor nos dois modos — é por ela que se casa o chip do menu
    # com a linha do calendário. Puxadas do ``estilo`` elas trocariam entre dia
    # e noite, e quem agenda no escuro veria um plano de outra cor.
    _CORES = ["#33b876", "#e0a63a", "#8ec5e6", "#c084fc", "#ef7a85"]

    def __init__(self, planos_info, atual=None, mesma_tc=False,
                 seed_etapas=None, fade_in=False, parent=None):
        super().__init__("Agendamento do Tratamento", parent)
        self._planos = planos_info            # [{"rotulo","num_fracoes"}]
        self._mesma_tc = mesma_tc
        # Ordem dos planos nas págs 2 e 3 (arrastando os chips). Começa na ordem
        # por número do rótulo (ou na guardada num agendamento anterior). É
        # SEPARADA da ordem dos cortes, que segue as abas.
        _ord0 = [i for i in ((atual or {}).get("ordem_planos") or [])
                 if isinstance(i, int) and 0 <= i < len(planos_info)]
        self._ordem_planos = (list(dict.fromkeys(_ord0))
                              if len(set(_ord0)) == len(planos_info)
                              else ag.ordem_por_numero([p["rotulo"] for p in planos_info]))
        # Entrada suave: quando o diálogo é aberto na sequência de outra ação
        # (reordenar as abas invalida o agendamento e reabre isto), surgir de
        # chofre incomoda. Começa transparente e faz fade-in no showEvent.
        self._fade_in = fade_in
        self._fade_anim = None
        if fade_in:
            self.setWindowOpacity(0.0)
        self.resize(1000, 660)
        self._replan_fracoes = int((atual or {}).get("replan_fracoes") or 0)
        self._replan_dose = float((atual or {}).get("replan_dose") or 0)
        root = self.corpo

        tit = QLabel("Monte os dias do tratamento — cada dia entrega os "
                     "planos marcados por N frações, de cima para baixo.")
        tit.setWordWrap(True)
        tit.setStyleSheet(f"font-weight:bold; font-size:13px; color:{estilo.ACAO};")
        root.addWidget(tit)
        # Replanejamento, Dia a dia, Limpar, Cancelar e Aplicar ficam todos na
        # barra inferior (criados lá), verdes e do mesmo tamanho.

        # TC de cada plano → quais fichas combinadas fazem sentido:
        #  • Soma combina TODOS os planos → só com uma única TC.
        #  • Personalizado combina um SUBCONJUNTO → basta existir alguma TC com
        #    ≥2 planos (ex.: 4 planos em 2 TCs, 2+2: dá para combinar cada par).
        # O conjunto avaliado é o que ENTRA na ficha (ver "Separar Ficha").
        self._frame_uids = [str(info.get("frame_uid") or "") for info in planos_info]
        # Separação: índices dos planos que compõem a ficha; None = todos.
        self._planos_separados = None

        # ── Ficha: QUAIS planos entram e como as doses deles se somam ────────
        # Três botões, dois deles com menu — antes eram linhas soltas de chips
        # ("Aplicar a:" e "Somar:") que empurravam os dias para baixo:
        #   • Planos ▾     → a quais planos os modelos de Frequência se aplicam
        #   • Somar dose ▾ → quais planos acumulam dose junta na pág. 3
        #   • Separar Ficha → quais planos compõem ESTE documento
        self._chips_ficha = []
        self._btns_ag = []   # botões das três linhas, p/ largura uniforme
        fl = QHBoxLayout(); fl.setSpacing(8)
        _lf = QLabel("Ficha:"); _lf.setFixedWidth(_LARG_ROTULO_AG)
        _lf.setStyleSheet("font-weight:bold;")
        fl.addWidget(_lf)

        # "Planos ▾" — quais planos estão NO AGENDAMENTO. Desmarcar tira o plano
        # de todos os dias; marcar de volta repõe exatamente os dias que ele
        # tinha (ver ``_desagendar_plano``/``_reagendar_plano``). Os modelos de
        # Frequência também só reescrevem as etapas dos marcados. Todos marcados
        # por padrão. Com um plano só não há o que escolher.
        self._modelo_chips = [None] * len(self._planos)
        self._lay_modelo_sel = None
        # Identidade dos dias (ver ``_add_etapa``) e o que os planos fora do ar
        # deixaram guardado: a que dias cada um pertence, os dias que ficaram
        # sem ninguém no ar e a ordem de todos eles, visíveis ou não.
        self._seq_dia = 0
        self._agenda_off = {}
        self._dias_ocultos = {}
        self._ordem_ids = []
        self.btn_planos = QToolButton()
        self.btn_planos.setText("Planos ▾")
        self.btn_planos.setPopupMode(QToolButton.InstantPopup)
        self.btn_planos.setCursor(Qt.PointingHandCursor)
        self.btn_planos.setToolTip(
            "Quais planos entram no agendamento e a quais os modelos de "
            "Frequência se aplicam.\nDesmarcar tira o plano dos dias; marcar "
            "de volta repõe o agendamento que ele tinha.")
        self.btn_planos.setStyleSheet(_estilo_btn_menu())
        self.btn_planos.setEnabled(len(self._planos) >= 2)
        if len(self._planos) >= 2:
            self._lay_modelo_sel = self._novo_menu(self.btn_planos)
            self._montar_modelo_chips()
        self._btns_ag.append(self.btn_planos)
        fl.addWidget(self.btn_planos)

        # "Somar dose ▾" — planos cuja dose acumula JUNTA na coluna Dose da
        # pág. 3 (fase → boost na mesma região: o boost continua de onde a fase
        # parou). Clicar no chip percorre os grupos (— / A / B / …): planos com
        # a mesma letra somam entre si, e quem fica em "—" acumula só a dose
        # dele, como sempre. Assim um caso de 3 planos numa região + 1 avulso
        # sai certo.
        self._dose_grupos = [0] * len(self._planos)
        self._dose_chips = [None] * len(self._planos)
        self._lay_dose_sel = None
        self.btn_somar = QToolButton()
        self.btn_somar.setText("Somar dose ▾")
        self.btn_somar.setPopupMode(QToolButton.InstantPopup)
        self.btn_somar.setCursor(Qt.PointingHandCursor)
        self.btn_somar.setToolTip(_DICA_SOMAR_DOSE)
        self.btn_somar.setStyleSheet(_estilo_btn_menu())
        self.btn_somar.setEnabled(len(self._planos) >= 2)
        if len(self._planos) >= 2:
            grupos0 = (atual or {}).get("grupos_dose") or []
            # Calculado AQUI, dos rótulos: este bloco roda antes da semente das
            # etapas, e ler um flag que só é definido lá embaixo daria sempre
            # falso — o grupo nunca seria semeado.
            rotulos = [str(p.get("rotulo") or "") for p in self._planos]
            semear_grupo = (ag.mama_com_boost(rotulos)
                            and not ag.mama_com_fsc(rotulos))
            if not grupos0 and semear_grupo:
                # Mama + boost: um grupo só, com todos. É "A e A" — a dose de um
                # acumula sobre a do outro, que é o que a conferência olha.
                grupos0 = [list(range(len(self._planos)))]
            for g, membros in enumerate(grupos0):
                for i in membros:
                    if isinstance(i, int) and 0 <= i < len(self._planos):
                        self._dose_grupos[i] = g + 1
            self._lay_dose_sel = self._novo_menu(self.btn_somar)
            self._montar_dose_chips()
        self._btns_ag.append(self.btn_somar)
        fl.addWidget(self.btn_somar)

        # Separar Ficha — ORTOGONAL ao Tipo de ficha: ele diz COMO os cortes/
        # DVH/3D se combinam; este diz QUAIS planos entram no documento.
        # Marcado (cheio) = separação ativa; o rótulo ao lado mostra quem ficou.
        self.btn_separar = QPushButton("Separar Ficha")
        self.btn_separar.setToolTip(
            "Escolha quais dos planos carregados compõem ESTA ficha (pode "
            "marcar vários). Os demais ficam de fora do documento e podem "
            "virar outra ficha depois.")
        self.btn_separar.setCheckable(True)
        self.btn_separar.setCursor(Qt.PointingHandCursor)
        # Âmbar, não azul: os seletores são grupos exclusivos (o Tipo) e este
        # não pertence a nenhum — a cor evita lê-lo como mais um modo.
        self.btn_separar.setStyleSheet(_estilo_btn_sel())
        self.btn_separar.setEnabled(len(self._planos) >= 2)
        self.btn_separar.clicked.connect(self._pedir_separacao)
        self._btns_ag.append(self.btn_separar)
        fl.addWidget(self.btn_separar)

        self.lbl_separar = QLabel()
        self.lbl_separar.setStyleSheet(f"color:{estilo.AMBAR}; font-weight:bold;")
        fl.addWidget(self.lbl_separar)
        fl.addStretch()
        root.addLayout(fl)

        # ── Tipo: Individual / Soma / Personalizado ──────────────────────────
        # Como cortes, DVH e 3D se combinam. Grupo exclusivo, mesma linha-base
        # das outras duas linhas (rótulo e botões da mesma largura).
        tl = QHBoxLayout(); tl.setSpacing(8)
        _lt = QLabel("Tipo:"); _lt.setFixedWidth(_LARG_ROTULO_AG)
        _lt.setStyleSheet("font-weight:bold;")
        tl.addWidget(_lt)
        self.rb_indiv = QPushButton("Individual")
        self.rb_indiv.setToolTip("Um DVH/imagem/3D por plano.")
        self.rb_soma = QPushButton("Soma")
        self.rb_soma.setToolTip("Um DVH/imagem/3D combinando TODOS os planos "
                                "(exige uma única TC).")
        self.rb_person = QPushButton("Personalizado")
        self.rb_person.setToolTip("Escolha quais planos compõem os mesmos "
                                  "cortes, DVH e 3D (os planos de uma mesma TC).")
        self._grupo_ficha = QButtonGroup(self)
        self._grupo_ficha.setExclusive(True)
        for rb in (self.rb_indiv, self.rb_soma, self.rb_person):
            rb.setCheckable(True); rb.setCursor(Qt.PointingHandCursor)
            rb.setStyleSheet(_estilo_btn_sel())
            self._grupo_ficha.addButton(rb)
            self._btns_ag.append(rb)
            tl.addWidget(rb)
        self.rb_indiv.setChecked(True)
        self._atualizar_modos_ficha()
        tl.addStretch()
        root.addLayout(tl)

        # Chips de seleção — visíveis só no modo Personalizado. A seleção fica
        # restrita a uma TC (combinar geometrias diferentes daria dado errado).
        self._person_widget = QWidget()
        pl = QHBoxLayout(self._person_widget)
        pl.setContentsMargins(20, 0, 0, 0)
        pl.addWidget(QLabel("Compõem a ficha:"))
        self._lay_person = pl
        pl.addStretch()
        # Chips (arrastáveis) exibidos na ORDEM ESCOLHIDA; guardados por índice.
        self._chips_ficha = [None] * len(self._planos)
        self._montar_chips_ficha()
        self._person_widget.setVisible(False)
        self.rb_person.toggled.connect(self._on_person_toggled)
        root.addWidget(self._person_widget)

        # ── Frequência: Sequencial / Simultâneo / Alternado ──────────────────
        # Modelos rápidos de montagem dos dias, aplicados aos planos escolhidos
        # em "Planos ▾". Seletores exclusivos como o Tipo: fundo azul só no
        # modelo escolhido, contorno nos demais. Clicar aplica o modelo E marca
        # o botão — some o azul "cheio" permanente que parecia sempre ativo.
        ml = QHBoxLayout(); ml.setSpacing(8)
        _lm = QLabel("Frequência:"); _lm.setFixedWidth(_LARG_ROTULO_AG)
        _lm.setStyleSheet("font-weight:bold;")
        ml.addWidget(_lm)
        self._grupo_modelo = QButtonGroup(self)
        self._grupo_modelo.setExclusive(True)
        for txt, fn in (("Sequencial", ag.modelo_sequencial),
                        ("Simultâneo", ag.modelo_simultaneo),
                        ("Alternado", ag.modelo_alternado)):
            b = QPushButton(txt); b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(_estilo_btn_sel())
            b.clicked.connect(lambda _c, f=fn: self._aplicar_modelo(f))
            self._grupo_modelo.addButton(b)
            self._btns_ag.append(b)
            ml.addWidget(b)
        ml.addStretch()
        # Todos os botões das três linhas do MESMO tamanho, alinhados coluna a
        # coluna. A largura já conta o MAIOR rótulo que os botões de menu podem
        # assumir ("Planos (4/4) ▾", "Somar dose · A B ▾"): o texto deles muda
        # com a escolha, e nem pode cortar nem empurrar a linha depois de pronta.
        _n = len(self._planos)
        _gmax = min(_n // 2, len(self._LETRAS_DOSE))   # grupos de 2+ que cabem
        _larg = [_LARG_BTN_AG] + [b.sizeHint().width() for b in self._btns_ag]
        for btn, pior in ((self.btn_planos, f"Planos ({_n}/{_n}) ▾"),
                          (self.btn_somar,
                           "Somar dose · " + " ".join(self._LETRAS_DOSE[:_gmax])
                           + " ▾" if _gmax else "Somar dose ▾")):
            _txt = btn.text()
            btn.setText(pior)
            _larg.append(btn.sizeHint().width())
            btn.setText(_txt)
        _w = max(_larg)
        for b in self._btns_ag:
            b.setFixedWidth(_w)
        root.addLayout(ml)

        # Etapas (scroll).
        self._etapas = []
        cont = QWidget(); self._lay_etapas = QVBoxLayout(cont)
        self._lay_etapas.setContentsMargins(4, 4, 4, 4); self._lay_etapas.setSpacing(8)
        self._lay_etapas.addStretch(1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(cont)
        scroll.setStyleSheet(
            f"QScrollArea{{border:1px solid {estilo.BORDA}; border-radius:6px;"
            f" background:{estilo.FUNDO_CAMPO};}}")
        root.addWidget(scroll, 1)

        # (Adicionar dia agora é o botão ＋ em cada linha, ao lado das setas/✕.)

        # Contador de frações: acompanha, por plano, quantas já foram agendadas
        # contra a prescrição, e avisa quando todas entram (substitui a linha
        # do tempo).
        self.lbl_total = QLabel()
        self.lbl_total.setWordWrap(True)
        self.lbl_total.setStyleSheet(f"color:{estilo.ACAO}; font-weight:bold;")
        root.addWidget(self.lbl_total)

        # Barra inferior. Antes: os quatro com o MESMO peso de contorno e
        # ``Expanding`` — "Cancelar" com a largura e o peso de "Aplicar" —, e
        # Cancelar ANTES de Aplicar, ao contrário do resto do programa.
        # "Replanejamento" e "Limpar" são ações do trabalho e ficam à esquerda;
        # o par que fecha a tela vai à direita, com o sólido em Aplicar.
        botoes = self.rodape(
            "Aplicar",
            extras=[("↻  Replanejamento", self._pedir_replanejamento),
                    ("Limpar", self._limpar_agendamento)])
        self.btn_replan = botoes["↻  Replanejamento"]
        self.btn_replan.setToolTip(
            "Paciente já tratado que foi replanejado: informe quantas frações já "
            "foram feitas. Elas saem rasuradas no mapa e o plano começa depois.")
        botoes["Limpar"].setToolTip(
            "Remove todos os dias e recomeça o agendamento do zero.")
        for b in botoes.values():
            b.setMinimumHeight(40)

        # Restaura ou seeda com um modelo padrão (sequencial: cada plano no seu
        # bloco de dias; o usuário troca para Simultâneo com um clique).
        etapas0 = (atual or {}).get("etapas")
        if not etapas0:
            # Seed vindo do dia de início + fracionamento (planos interligados);
            # sem ele, um bloco por plano (sequencial).
            fracoes0 = [p["num_fracoes"] for p in planos_info]
            rotulos0 = [str(p.get("rotulo") or "") for p in planos_info]
            if seed_etapas:
                etapas0 = seed_etapas
            elif ag.mama_com_boost(rotulos0) and not ag.mama_com_fsc(rotulos0):
                # Fase e boost SE SEGUEM — sequencial, como o padrão. O que muda
                # é a leitura: a dose é do mesmo alvo, e o que se confere é o
                # acumulado. Daí ficha em SOMA e os dois no mesmo grupo de
                # "Somar dose", que alguém marcava à mão em todo caso de mama.
                etapas0 = ag.modelo_sequencial(fracoes0,
                                               ordem=self._ordem_planos)
                self._semear_soma = True
            elif ag.mama_com_fsc(rotulos0):
                # Mama e FSC são campos da MESMA sessão, não fases que se
                # seguem: entram juntos em toda fração. O padrão sequencial
                # descrevia esse caso errado e alguém corrigia à mão toda vez.
                # É semente, não trava — os botões de modelo continuam ali.
                etapas0 = ag.modelo_simultaneo(fracoes0)
                self._semear_soma = True
            else:
                etapas0 = ag.modelo_sequencial(fracoes0,
                                               ordem=self._ordem_planos)
        for et in etapas0:
            self._add_etapa(et.get("planos"), et.get("fracoes"))
        # Separação antes do modo: ela é que define quais modos continuam válidos.
        if (atual or {}).get("planos_separados"):
            self._aplicar_separacao((atual or {}).get("planos_separados"))
        modo_ficha0 = (atual or {}).get("modo_ficha")
        # Mama+FSC pede ficha de SOMA: o que interessa conferir é a dose que os
        # dois campos entregam juntos, não cada plano em separado.
        if (modo_ficha0 is None and getattr(self, "_semear_soma", False)
                and self.rb_soma.isEnabled()):
            modo_ficha0 = "soma"
        if modo_ficha0 == "soma" and self.rb_soma.isEnabled():
            self.rb_soma.setChecked(True)
        elif modo_ficha0 == "personalizado" and self.rb_person.isEnabled():
            self.rb_person.setChecked(True)
            escolhidos = set((atual or {}).get("planos_ficha") or [])
            for i, chip in enumerate(self._chips_ficha):
                chip.setChecked(i in escolhidos)
            self._restringir_chips_ficha()
        self._atualizar_btn_replan()
        self._preview()

    def showEvent(self, event):
        """Fade-in de abertura (só quando ``fade_in``), uma única vez."""
        super().showEvent(event)
        if self._fade_in and self._fade_anim is None:
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(220)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._fade_anim = anim   # guarda a ref: sem ela o GC mata a animação

    # ── Chips ────────────────────────────────────────────────────────────────
    def _estilo_chip(self, cor: str) -> str:
        # Fonte/padding enxutos para caber vários planos de nome longo na linha.
        return (
            "QPushButton{border:1.5px solid %s; border-radius:10px;"
            " padding:2px 8px; color:%s; background:transparent;"
            " font-size:11px; font-weight:600;}"
            # ``#10201a``: quase-preto sobre a cor do plano, que é clara nas
            # cinco. Do ``estilo`` viria o TEXTO do modo — claro na noite, e
            # ilegível sobre o chip aceso.
            "QPushButton:checked{background:%s; color:#10201a;}" % (cor, cor, cor)
        )

    def _novo_menu(self, btn) -> QVBoxLayout:
        """Prende ao botão um menu de chips e devolve o layout que os recebe.

        Os chips vão num ``QWidgetAction``: como são widgets, e não itens de
        menu, clicar num deles alterna o chip SEM fechar o menu — dá para
        marcar vários de uma vez. O layout leva um esticador no fim, que é onde
        os ``_montar_*`` ancoram a inserção.
        """
        menu = QMenu(btn)
        menu.setStyleSheet(_ESTILO_MENU_AG)
        cont = QWidget()
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        lay.addStretch()
        act = QWidgetAction(menu)
        act.setDefaultWidget(cont)
        menu.addAction(act)
        btn.setMenu(menu)
        return lay

    def _atualizar_btn_planos(self, *_) -> None:
        """Rótulo/realce do 'Planos ▾': acende quando os modelos de Frequência
        passam a valer só para parte dos planos — com o menu fechado, é o único
        sinal de que o próximo modelo não vai reescrever o agendamento inteiro."""
        btn = getattr(self, "btn_planos", None)
        if btn is None:
            return
        chips = [c for c in self._modelo_chips if c is not None]
        marc = [c for c in chips if c.isChecked()]
        parcial = bool(chips) and len(marc) != len(chips)
        btn.setText(f"Planos ({len(marc)}/{len(chips)}) ▾" if parcial
                    else "Planos ▾")
        _marcar_ativo(btn, parcial)

    def _atualizar_btn_somar(self) -> None:
        """Rótulo/realce do 'Somar dose ▾': lista as letras dos grupos que de
        fato somam (2+ planos DO AGENDAMENTO). Sem grupo, o botão fica apagado."""
        btn = getattr(self, "btn_somar", None)
        if btn is None:
            return
        ligados = set(self._planos_ligados())
        n = min(len(self._planos), len(self._LETRAS_DOSE))
        letras = [self._LETRAS_DOSE[g - 1] for g in range(1, n + 1)
                  if sum(1 for i, v in enumerate(self._dose_grupos)
                         if v == g and i in ligados) >= 2]
        btn.setText("Somar dose · " + " ".join(letras) + " ▾" if letras
                    else "Somar dose ▾")
        _marcar_ativo(btn, bool(letras))

    # ── Etapas ───────────────────────────────────────────────────────────────
    def _add_etapa(self, planos=None, fracoes=1, did=None):
        # ``did``: identidade do dia, estável entre reconstruções. É por ela que
        # um plano desagendado sabe voltar para os dias certos, na ordem certa —
        # posição na lista não serve, a lista encolhe quando um dia some.
        if did is None:
            self._seq_dia += 1
            did = self._seq_dia
        frame = QFrame()
        frame.setStyleSheet(f"QFrame{{background:{estilo.FUNDO_BLOCO}; border-radius:6px;}}")
        h = QHBoxLayout(frame); h.setContentsMargins(10, 6, 8, 6); h.setSpacing(5)
        lbl = QLabel(); lbl.setFixedWidth(50)
        h.addWidget(lbl)
        # Chips exibidos na ORDEM ESCOLHIDA (self._ordem_planos, arrastável), mas
        # guardados por ÍNDICE do plano — a leitura usa a posição na lista.
        chips = [None] * len(self._planos)
        marcados = set(int(p) for p in planos) if planos is not None else None
        ligados = set(self._planos_ligados())
        for i in self._ordem_planos:
            p = self._planos[i]
            chip = _ChipPlano(p["rotulo"], i, self._mover_plano)
            chip.setChecked(True if marcados is None else (i in marcados))
            # Plano fora do agendamento (menu "Planos") não se marca aqui: o
            # botão diria "3/4" com ele agendado assim mesmo.
            chip.setEnabled(i in ligados)
            chip.setStyleSheet(self._estilo_chip(self._CORES[i % len(self._CORES)]))
            chip.toggled.connect(self._preview)
            h.addWidget(chip); chips[i] = chip
        h.addStretch(1)
        lbl_fr = QLabel("Frações:")
        h.addWidget(lbl_fr)
        spin = QSpinBox(); spin.setRange(1, 80); spin.setValue(int(fracoes or 1) or 1)
        spin.setFixedWidth(58); spin.valueChanged.connect(self._preview)
        h.addWidget(spin)
        # Botões de mover/remover/adicionar o dia: maiores e com folga.
        b_up = QPushButton("↑"); b_dn = QPushButton("↓"); b_rm = QPushButton("✕")
        b_new = QPushButton("＋")
        b_up.setToolTip("Subir o dia"); b_dn.setToolTip("Descer o dia")
        b_rm.setToolTip("Remover o dia")
        b_new.setToolTip("Adicionar um dia abaixo")
        b_new.setStyleSheet(estilo.btn_contorno(11.5)
                            + "QPushButton{padding:0; border-radius:4px;}")
        for b in (b_up, b_dn, b_rm, b_new):
            b.setFixedSize(30, 28); b.setCursor(Qt.PointingHandCursor)
        h.addSpacing(8)
        for b in (b_up, b_dn, b_rm, b_new):
            h.addWidget(b)
        ent = {"frame": frame, "lbl": lbl, "chips": chips, "spin": spin, "id": did}
        b_up.clicked.connect(lambda: self._mover_etapa(ent, -1))
        b_dn.clicked.connect(lambda: self._mover_etapa(ent, 1))
        b_rm.clicked.connect(lambda: self._remover_etapa(ent))
        b_new.clicked.connect(lambda: self._inserir_etapa_apos(ent))
        self._etapas.append(ent)
        self._lay_etapas.insertWidget(self._lay_etapas.count() - 1, frame)
        self._renumerar(); self._preview()

    def _mover_etapa(self, ent, delta):
        i = self._etapas.index(ent); j = i + delta
        if not (0 <= j < len(self._etapas)):
            return
        self._etapas[i], self._etapas[j] = self._etapas[j], self._etapas[i]
        for e in self._etapas:
            self._lay_etapas.removeWidget(e["frame"])
        for k, e in enumerate(self._etapas):
            self._lay_etapas.insertWidget(k, e["frame"])
        self._renumerar(); self._preview()

    def _remover_etapa(self, ent):
        if len(self._etapas) <= 1:
            return
        self._etapas.remove(ent)
        ent["frame"].setParent(None); ent["frame"].deleteLater()
        self._renumerar(); self._preview()

    def _inserir_etapa_apos(self, ent):
        """Insere um novo dia logo ABAIXO de ``ent`` (botão ＋ da linha)."""
        idx = self._etapas.index(ent)
        # Só os planos que estão no agendamento: um dia novo não pode trazer de
        # volta, pela porta dos fundos, quem foi tirado no menu "Planos".
        self._add_etapa(self._planos_ligados())   # nasce no fim da lista
        nova = self._etapas.pop()             # tira do fim…
        self._etapas.insert(idx + 1, nova)    # …e recoloca logo após a origem
        for e in self._etapas:                # reordena os widgets no layout
            self._lay_etapas.removeWidget(e["frame"])
        for k, e in enumerate(self._etapas):
            self._lay_etapas.insertWidget(k, e["frame"])
        self._renumerar(); self._preview()

    def _limpar_agendamento(self) -> None:
        """Zera o agendamento: remove todos os dias e desmarca o modelo, para o
        usuário remontar do zero."""
        # Deixa UM dia com os planos que estão no agendamento (menu "Planos") —
        # sem nenhuma linha não haveria o botão ＋ para recomeçar a montar. O
        # que estava guardado de quem saiu perde o sentido depois de zerar.
        self._agenda_off.clear()
        self._dias_ocultos.clear()
        self._ordem_ids.clear()
        # Se nenhum plano está no agendamento, o dia nasce vazio mesmo — marcar
        # todos contradiria o "Planos (0/N)" do menu.
        self._reconstruir([{"planos": self._planos_ligados(), "fracoes": 1}])
        self._desmarcar_botao_modelo()

    def _reconstruir(self, etapas):
        """Substitui todas as linhas pelas etapas dadas (mantém o modo atual).

        Uma etapa que traz ``id`` reaproveita a identidade do dia — é o mesmo
        dia, redesenhado; sem ``id`` nasce um dia novo.
        """
        for e in list(self._etapas):
            e["frame"].setParent(None); e["frame"].deleteLater()
        self._etapas.clear()
        for et in etapas:
            self._add_etapa(et.get("planos"), et.get("fracoes"), et.get("id"))
        self._preview()

    def _aplicar_modelo(self, fn):
        fracoes = [p["num_fracoes"] for p in self._planos]
        # Planos marcados no menu "Planos" na ordem de modelo (chip ausente = 1
        # plano só → todos). Nada marcado: não há o que aplicar.
        sel = [i for i in self._ordem_planos
               if self._modelo_chips[i] is None or self._modelo_chips[i].isChecked()]
        if not sel:
            # Nada a aplicar: desmarca o botão de modelo que o clique acendeu,
            # senão ele fica azul indicando um modelo que não foi aplicado.
            self._desmarcar_botao_modelo()
            return
        # Sequencial e Alternado seguem a ordem escolhida; Simultâneo junta os
        # marcados num bloco (nº = maior nº de frações entre eles).
        if fn is ag.modelo_simultaneo:
            n = max((int(fracoes[i] or 0) for i in sel), default=0) or 1
            etapas_modelo = [{"planos": sorted(sel), "fracoes": n}]
        else:
            etapas_modelo = fn(fracoes, ordem=sel)
        # Todos marcados → substitui o agendamento inteiro (comportamento antigo);
        # subconjunto → sobrepõe o modelo mantendo intactos os dias dos demais.
        if len(sel) == len(self._planos):
            etapas = etapas_modelo
        else:
            etapas = ag.aplicar_modelo_em(self._etapas_dados(), etapas_modelo, sel)
        self._reconstruir(etapas)

    def _desmarcar_botao_modelo(self) -> None:
        """Tira o destaque do botão de modelo marcado (grupo exclusivo não deixa
        desmarcar por clique; alterna a exclusividade para limpar)."""
        grp = self._grupo_modelo
        b = grp.checkedButton()
        if b is not None:
            grp.setExclusive(False)
            b.setChecked(False)
            grp.setExclusive(True)

    def _renumerar(self):
        for k, e in enumerate(self._etapas, 1):
            e["lbl"].setText(f"Dia {k}")
            e["lbl"].setStyleSheet(f"font-weight:bold; color:{estilo.ACAO};")

    def _etapas_dados(self, com_id: bool = False):
        out = []
        for e in self._etapas:
            planos = [i for i, c in enumerate(e["chips"]) if c.isChecked()]
            d = {"planos": planos, "fracoes": e["spin"].value()}
            if com_id:
                # Só quem vai reconstruir as linhas pede a identidade: ela é de
                # dentro do diálogo e não tem o que fazer no agendamento salvo.
                d["id"] = e["id"]
            out.append(d)
        return out

    # ── Preview / resultado ──────────────────────────────────────────────────
    def _preview(self, *_):
        """Atualiza o contador: frações agendadas por plano contra a prescrição."""
        etapas = self._etapas_dados()
        rot = [p["rotulo"] for p in self._planos]
        presc = [int(p.get("num_fracoes") or 0) for p in self._planos]
        agend = ag.fracoes_por_plano(etapas, len(rot))

        partes, completo = [], True
        for i in range(len(rot)):
            ok = agend[i] == presc[i]
            completo = completo and ok
            partes.append(f"{rot[i]} {agend[i]}/{presc[i]}" + (" ✓" if ok else ""))
        det = "    ".join(partes)

        if completo:
            self.lbl_total.setText(f"{det}      ✓ Todas as frações agendadas")
            self.lbl_total.setStyleSheet(f"color:{estilo.ACAO}; font-weight:bold;")
        else:
            faltam = [rot[i] for i in range(len(rot)) if agend[i] < presc[i]]
            acima = [rot[i] for i in range(len(rot)) if agend[i] > presc[i]]
            msg = []
            if faltam:
                msg.append("faltam " + ", ".join(faltam))
            if acima:
                msg.append("acima " + ", ".join(acima))
            self.lbl_total.setText(f"{det}      ⚠ " + " · ".join(msg))
            self.lbl_total.setStyleSheet(f"color:{estilo.AMBAR}; font-weight:bold;")

    # ── Separar Ficha ────────────────────────────────────────────────────────
    def _indices_ficha(self) -> list:
        """Índices dos planos que compõem a ficha, de fato.

        Quem manda é o "Planos ▾": plano fora do agendamento não tem dia nenhum,
        logo não tem linha no mapa da pág. 3 nem dose para acumular — ele não
        compõe esta ficha. O Separar Ficha escolhe DENTRO desse conjunto.

        A escolha do Separar Ficha fica guardada como o usuário a fez
        (``_planos_separados``) e é cruzada com o agendamento só aqui: assim um
        plano que sai e volta ao "Planos ▾" volta à ficha exatamente se estava
        marcado na separação — em vez de a ida ao agendamento apagar a escolha.
        """
        ligados = self._planos_ligados()
        if self._planos_separados is None:
            return ligados
        return [i for i in ligados if i in self._planos_separados]

    def _pedir_separacao(self, *_) -> None:
        """Botão 'Separar Ficha': popup com os planos carregados (multi-escolha).

        Plano fora do agendamento entra no popup travado e desmarcado: ele não
        pode compor a ficha, e mostrá-lo (em vez de omiti-lo) é o que explica
        por quê — a lista some sem aviso se o item simplesmente não aparecer.
        """
        itens = [(i, self._planos[i]["rotulo"]) for i in self._ordem_planos]
        fora = [i for i in self._ordem_planos if i not in self._planos_ligados()]
        dlg = DialogSepararFicha(itens, set(self._indices_ficha()),
                                 self._CORES, bloqueados=set(fora), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._aplicar_separacao(dlg.resultado())
        else:
            # Cancelou: o clique já tinha alternado o botão — desfaz o visual.
            self._atualizar_rotulo_separar()

    def _aplicar_separacao(self, indices) -> None:
        """Guarda a separação e reavalia o que ela permite.

        Marcar TUDO o que foi OFERECIDO (ou nada) equivale a não separar →
        ``None``. É contra o oferecido, não contra os planos carregados: com um
        plano fora do agendamento, marcar os outros três não é uma escolha de
        separação — e guardá-la como tal congelaria o plano fora da ficha quando
        ele voltasse ao "Planos ▾".

        Os modos de ficha e os chips do Personalizado passam a valer só para os
        planos que ficaram — combinar com um plano que nem sai no documento não
        faz sentido.
        """
        oferecidos = set(self._planos_ligados())
        idx = {i for i in (indices or [])
               if isinstance(i, int) and 0 <= i < len(self._planos)} & oferecidos
        self._planos_separados = (None if not idx or idx == oferecidos
                                  else sorted(idx))
        self._atualizar_rotulo_separar()
        self._atualizar_modos_ficha()
        if self._chips_ficha and all(c is not None for c in self._chips_ficha):
            self._restringir_chips_ficha()

    def _atualizar_rotulo_separar(self) -> None:
        """Botão/rótulo do Separar Ficha a partir do conjunto EFETIVO da ficha.

        Aceso sempre que a ficha não tem todos os planos carregados — não
        importa se o que tirou um deles foi a separação ou o "Planos ▾". Com o
        popup fechado, esse rótulo é o único lugar que diz quem entra."""
        dentro = self._indices_ficha()
        ativa = len(dentro) < len(self._planos)
        self.btn_separar.setChecked(ativa)
        self.lbl_separar.setText(
            "só: " + ", ".join(self._planos[i]["rotulo"] for i in dentro)
            if ativa else "")

    def _atualizar_modos_ficha(self) -> None:
        """Reavalia quais modos fazem sentido para os planos que entram na ficha.

        Soma exige TC única; Personalizado, ao menos dois planos de uma mesma
        TC. Separar muda esse conjunto: 4 planos em 2 TCs viram uma Soma válida
        depois de separar os 2 de uma delas. Se o modo escolhido deixa de valer,
        cai para Individual.
        """
        uids = [self._frame_uids[i] for i in self._indices_ficha()]
        ok = [u for u in uids if u]
        todos_mesma = (len(ok) == len(uids) and len(set(ok)) == 1 and len(uids) >= 2)
        grupos = {u: ok.count(u) for u in set(ok)}
        self.rb_soma.setEnabled(todos_mesma)
        self.rb_person.setEnabled(any(n >= 2 for n in grupos.values()))
        if ((self.rb_soma.isChecked() and not self.rb_soma.isEnabled())
                or (self.rb_person.isChecked() and not self.rb_person.isEnabled())):
            self.rb_indiv.setChecked(True)

    def _on_person_toggled(self, on: bool) -> None:
        """Ao entrar no Personalizado, semeia a seleção com o maior grupo de
        mesma TC (ponto de partida válido) e mostra os chips."""
        self._person_widget.setVisible(on)
        if not on:
            return
        # TC com mais planos (ao menos 2) vira a seleção inicial — contando só
        # os planos que a separação deixou na ficha.
        dentro = set(self._indices_ficha())
        contagem = {}
        for i in dentro:
            u = self._frame_uids[i]
            if u:
                contagem[u] = contagem.get(u, 0) + 1
        alvo = max((u for u in contagem if contagem[u] >= 2),
                   key=lambda u: contagem[u], default=None)
        for i, c in enumerate(self._chips_ficha):
            c.blockSignals(True)
            c.setChecked(alvo is not None and i in dentro
                         and self._frame_uids[i] == alvo)
            c.blockSignals(False)
        self._restringir_chips_ficha()

    def _montar_chips_ficha(self, marcados=None) -> None:
        """(Re)constrói os chips 'Compõem a ficha' (Personalizado) na ordem atual
        (``self._ordem_planos``), preservando quais estão marcados."""
        for c in self._chips_ficha:
            if c is not None:
                c.setParent(None); c.deleteLater()
        self._chips_ficha = [None] * len(self._planos)
        for i in self._ordem_planos:
            p = self._planos[i]
            chip = _ChipPlano(p["rotulo"], i, self._mover_plano)
            chip.setStyleSheet(self._estilo_chip(self._CORES[i % len(self._CORES)]))
            chip.setChecked(True if marcados is None else (i in marcados))
            chip.toggled.connect(self._restringir_chips_ficha)
            self._lay_person.insertWidget(self._lay_person.count() - 1, chip)
            self._chips_ficha[i] = chip
        self._restringir_chips_ficha()

    def _montar_modelo_chips(self, marcados=None) -> None:
        """(Re)cria os chips do menu 'Planos ▾' na ordem atual dos planos,
        preservando quais estão marcados (padrão: todos). São checáveis
        independentes — só escolhem a quais planos os modelos de Frequência se
        aplicam, sem reordenar nada."""
        if getattr(self, "_lay_modelo_sel", None) is None:
            return
        for c in self._modelo_chips:
            if c is not None:
                c.setParent(None); c.deleteLater()
        self._modelo_chips = [None] * len(self._planos)
        for i in self._ordem_planos:
            p = self._planos[i]
            chip = QPushButton(p["rotulo"]); chip.setCheckable(True)
            chip.setChecked(True if marcados is None else (i in marcados))
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(self._estilo_chip(self._CORES[i % len(self._CORES)]))
            # As conexões vêm DEPOIS do setChecked: remontar a lista (reordenar
            # os planos) não pode disparar desagendamento nenhum.
            chip.toggled.connect(self._atualizar_btn_planos)
            chip.toggled.connect(lambda on, k=i: self._on_plano_no_agendamento(k, on))
            self._lay_modelo_sel.insertWidget(self._lay_modelo_sel.count() - 1, chip)
            self._modelo_chips[i] = chip
        self._atualizar_btn_planos()

    def _on_plano_no_agendamento(self, i: int, ligado: bool) -> None:
        """Chip do menu 'Planos' virou: refaz as linhas com quem está no ar.

        Tirar e repor é a MESMA operação — reprojetar o agendamento completo
        sobre os planos ligados —, então não importa em que ordem os planos
        saem e voltam, nem quantos ficam fora ao mesmo tempo.

        O ÚLTIMO plano no ar não sai: sem nenhum, todo dia fica sem plano, sai
        de cena e o agendamento vira zero linhas — sem linha não há botão ＋
        para recriar uma, e Aplicar salvaria ``sequencia: []`` (mapa da pág. 3
        vazio). É o mesmo piso de uma linha que ``_remover_etapa`` mantém.
        """
        if not ligado and not self._planos_ligados():
            chip = self._modelo_chips[i]
            if chip is not None:
                chip.blockSignals(True)      # repor não é um novo evento
                chip.setChecked(True)
                chip.blockSignals(False)
                self._atualizar_btn_planos()
            return
        self._reprojetar()
        self._sincronizar_ficha_com_agendamento()
        if not ligado or any(i in et["planos"] for et in self._etapas_dados()):
            return
        # Voltou sem dia nenhum: ou nunca teve, ou um modelo reescreveu por cima
        # dos dias em que ele estava. Entra com a prescrição dele num dia no fim
        # — plano no agendamento sem dia nenhum só confundiria o contador.
        self._add_etapa([i], self._planos[i].get("num_fracoes") or 1)
        self._ordem_ids.append(self._etapas[-1]["id"])

    def _sincronizar_ficha_com_agendamento(self) -> None:
        """Repassa o "Planos ▾" para quem depende dele: Somar dose e Separar Ficha.

        Plano fora do agendamento não some dose com ninguém nem compõe a ficha
        (ver ``_indices_ficha``). Os grupos de dose dele ficam GUARDADOS, como os
        dias: se voltar ao agendamento, volta com o grupo que tinha.
        """
        for i in range(len(self._planos)):
            self._pintar_chip_dose(i)          # trava/destrava e repinta
        self._atualizar_btn_somar()
        self._atualizar_rotulo_separar()
        self._atualizar_modos_ficha()
        if self._chips_ficha and all(c is not None for c in self._chips_ficha):
            self._restringir_chips_ficha()

    def _planos_ligados(self) -> list:
        """Índices dos planos que estão no agendamento (menu 'Planos'). Sem os
        chips (um plano só), todos estão."""
        return [i for i in range(len(self._planos))
                if self._modelo_chips[i] is None
                or self._modelo_chips[i].isChecked()]

    def _ordem_canonica(self) -> list:
        """Ordem de TODOS os dias (visíveis e ocultos), por identidade.

        Os visíveis mandam na ordem — é o que está na tela, e o usuário pode
        tê-los movido. Cada oculto entra logo depois do dia que o precedia na
        ordem anterior; os ocultos são colocados nessa mesma sequência, então
        uma fila deles se reancora um no outro e volta na ordem original.
        """
        res = [e["id"] for e in self._etapas]
        pos = {d: k for k, d in enumerate(self._ordem_ids)}
        for did in sorted(self._dias_ocultos,
                          key=lambda d: pos.get(d, len(self._ordem_ids))):
            antes = self._ordem_ids[:pos[did]] if did in pos else None
            if antes is None:
                res.append(did)          # sem ancoragem conhecida: vai para o fim
                continue
            # Como os ocultos entram em ordem, todo antecessor que ainda existe
            # já está em ``res``: o último deles é a âncora.
            alvo = [res.index(o) + 1 for o in antes if o in res]
            if alvo:
                res.insert(alvo[-1], did)
            elif antes:
                res.append(did)          # os antecessores dele sumiram (um
                                         # modelo reescreveu os dias): vai ao fim
            else:
                res.insert(0, did)       # era o primeiro dia, e volta a ser
        return res

    def _agenda_cheia(self) -> list:
        """Todos os dias na ordem canônica, cada um com TODOS os planos que lhe
        pertencem — inclusive os que estão fora do agendamento."""
        dias = {}
        for e, d in zip(self._etapas, self._etapas_dados()):
            dias[e["id"]] = {"planos": set(d["planos"]), "fracoes": d["fracoes"]}
        for did, d in self._dias_ocultos.items():
            dias.setdefault(did, {"planos": set(d["planos"]),
                                  "fracoes": d["fracoes"]})
        # Planos fora do ar não aparecem em linha nenhuma: quem sabe a que dias
        # eles pertencem é o registro guardado quando saíram.
        for i, ids in self._agenda_off.items():
            for did in ids:
                if did in dias:
                    dias[did]["planos"].add(i)
        return [(did, dias[did]) for did in self._ordem_canonica() if did in dias]

    def _reprojetar(self) -> None:
        """Reconstrói as linhas mostrando só os planos que estão no agendamento.

        Um dia que fica sem nenhum plano no ar sai de cena inteiro, guardado, e
        volta no lugar certo assim que um dos seus voltar. Como tudo é derivado
        do agendamento completo, o que os outros planos ganharam no meio-tempo
        (frações editadas, dias novos) fica de pé.
        """
        cheia = self._agenda_cheia()
        self._ordem_ids = [did for did, _ in cheia]
        ligados = set(self._planos_ligados())
        novas, ocultos, off = [], {}, {}
        for did, d in cheia:
            for i in sorted(d["planos"] - ligados):
                off.setdefault(i, []).append(did)
            visiveis = sorted(d["planos"] & ligados)
            if visiveis:
                novas.append({"planos": visiveis, "fracoes": d["fracoes"],
                              "id": did})
            else:
                ocultos[did] = {"planos": sorted(d["planos"]),
                                "fracoes": d["fracoes"]}
        self._dias_ocultos = ocultos
        self._agenda_off = off
        self._reconstruir(novas)

    _LETRAS_DOSE = "ABCDE"

    def _montar_dose_chips(self) -> None:
        """(Re)cria os chips do menu 'Somar dose ▾' na ordem atual dos planos.

        Cada chip mostra o plano e o grupo de dose dele ("1 MAMA · A"); clicar
        avança para o próximo grupo e volta a "—" no fim. O nº de letras é o de
        planos: no limite cada um fica no seu grupo, que é o mesmo que nenhum."""
        if self._lay_dose_sel is None:
            return
        for c in self._dose_chips:
            if c is not None:
                c.setParent(None); c.deleteLater()
        self._dose_chips = [None] * len(self._planos)
        for i in self._ordem_planos:
            chip = QPushButton()
            chip.setCursor(Qt.PointingHandCursor)
            chip.setToolTip(_DICA_SOMAR_DOSE)
            chip.clicked.connect(lambda _c=False, k=i: self._ciclar_grupo_dose(k))
            self._lay_dose_sel.insertWidget(self._lay_dose_sel.count() - 1, chip)
            self._dose_chips[i] = chip
            self._pintar_chip_dose(i)
            # Espaço da letra reservado JÁ na criação (medido com o estilo real
            # aplicado, e com folga): o chip ganha o "A · " ao entrar num grupo,
            # mas um menu aberto não se realarga — sem a reserva o nome do plano
            # saía cortado no primeiro clique.
            _real = chip.text()
            chip.setText(f"{self._LETRAS_DOSE[0]} · {self._planos[i]['rotulo']}")
            chip.setMinimumWidth(chip.sizeHint().width() + 8)
            chip.setText(_real)
        self._atualizar_btn_somar()

    def _pintar_chip_dose(self, i: int) -> None:
        """Chip do grupo de dose: apagado (cinza, só o nome) enquanto o plano
        acumula sozinho; aceso com a letra do grupo à frente quando soma com
        outro. A letra vem primeiro para os planos do mesmo grupo se lerem em
        coluna, sem caçar o sufixo no fim de nomes de tamanhos diferentes.

        Plano fora do agendamento fica TRAVADO: sem dia nenhum ele não tem linha
        no mapa da pág. 3, e portanto nenhuma dose para somar com ninguém."""
        chip = self._dose_chips[i]
        if chip is None:
            return
        fora = i not in set(self._planos_ligados())
        g = 0 if fora else self._dose_grupos[i]
        rot = self._planos[i]["rotulo"]
        cor = self._CORES[i % len(self._CORES)]
        chip.setEnabled(not fora)
        chip.setToolTip(_DICA_FORA_DO_AGENDAMENTO if fora else _DICA_SOMAR_DOSE)
        chip.setText(f"{self._LETRAS_DOSE[g - 1]} · {rot}" if g else rot)
        chip.setStyleSheet(
            self._estilo_chip(cor).replace(
                "QPushButton{", "QPushButton{background:%s; color:#10201a;" % cor)
            if g else
            f"QPushButton{{border:1.5px dashed {estilo.BORDA_FORTE}; border-radius:10px;"
            " padding:2px 8px; background:transparent;"
        f" color:{estilo.TEXTO_APAGADO};"
            " font-size:11px; font-weight:600;}"
            f"QPushButton:hover{{border-color:{estilo.ACAO}; color:{estilo.TEXTO};}}"
            f"QPushButton:disabled{{border-style:dotted; border-color:{estilo.BORDA};"
            f" color:{estilo.TEXTO_APAGADO};}}")

    def _ciclar_grupo_dose(self, i: int) -> None:
        if i not in set(self._planos_ligados()):
            return                     # chip travado; nem deveria clicar
        n = min(len(self._planos), len(self._LETRAS_DOSE))
        self._dose_grupos[i] = (self._dose_grupos[i] + 1) % (n + 1)
        self._pintar_chip_dose(i)
        self._atualizar_btn_somar()

    def _grupos_dose_dados(self) -> list:
        """Grupos de soma de dose (índices de plano). Só grupos com 2+ planos —
        um plano sozinho já acumula a própria dose.

        Conta apenas os planos do agendamento: um grupo que fique com um membro
        só depois disso deixa de existir, como qualquer grupo de um."""
        ligados = set(self._planos_ligados())
        n = min(len(self._planos), len(self._LETRAS_DOSE))
        grupos = []
        for g in range(1, n + 1):
            membros = [i for i, v in enumerate(self._dose_grupos)
                       if v == g and i in ligados]
            if len(membros) >= 2:
                grupos.append(membros)
        return grupos

    def _mover_plano(self, origem: int, alvo: int) -> None:
        """Arrastou um chip: move o plano ``origem`` para a posição do ``alvo`` na
        ordem das páginas 2 e 3. A reconstrução é ADIADA — o widget que recebeu o
        drop está prestes a ser destruído, e mexer nele dentro do dropEvent quebra.
        """
        o = self._ordem_planos
        if origem == alvo or origem not in o or alvo not in o:
            return
        o.remove(origem)
        o.insert(o.index(alvo), origem)
        QTimer.singleShot(0, self._apos_reordenar_planos)

    def _apos_reordenar_planos(self) -> None:
        marcados = {i for i, c in enumerate(self._chips_ficha)
                    if c is not None and c.isChecked()}
        marc_mod = {i for i, c in enumerate(self._modelo_chips)
                    if c is not None and c.isChecked()}
        self._reconstruir(self._etapas_dados(com_id=True))   # etapas na nova ordem
        self._montar_chips_ficha(marcados)         # chips do Personalizado idem
        self._montar_modelo_chips(marc_mod)        # chips do menu "Planos" idem
        self._montar_dose_chips()                  # chips do "Somar dose" idem
        self._preview()

    def _restringir_chips_ficha(self, *_) -> None:
        """Mantém a seleção do Personalizado numa única TC: uma vez marcado um
        plano, os de outra tomografia ficam desabilitados. Planos que não compõem
        a ficha também saem — pela separação ou por estarem fora do "Planos ▾"
        (ver ``_indices_ficha``): não estão no documento para combinar.
        """
        dentro = set(self._indices_ficha())
        for i, c in enumerate(self._chips_ficha):
            if c is not None and i not in dentro and c.isChecked():
                c.blockSignals(True); c.setChecked(False); c.blockSignals(False)
        marcadas = {self._frame_uids[i] for i, c in enumerate(self._chips_ficha)
                    if c is not None and c.isChecked()}
        for i, c in enumerate(self._chips_ficha):
            if c is not None:
                c.setEnabled(i in dentro
                             and (not marcadas or self._frame_uids[i] in marcadas))

    def _pedir_replanejamento(self):
        """Pergunta as frações já tratadas e a dose/fração (cGy) do plano anterior."""
        n, ok = QInputDialog.getInt(
            self, "Replanejamento", "Qual o número de frações tratado?",
            self._replan_fracoes, 0, 100)
        if not ok:
            return
        dose, ok = QInputDialog.getInt(
            self, "Replanejamento", "Dose por fração já tratada (cGy):",
            int(self._replan_dose), 0, 2000, 10)
        if not ok:
            return
        self._replan_fracoes = int(n)
        self._replan_dose = float(dose)
        self._atualizar_btn_replan()

    def _atualizar_btn_replan(self):
        txt = "↻  Replanejamento"
        if self._replan_fracoes > 0:
            txt += f"  ({self._replan_fracoes} fx"
            if self._replan_dose > 0:
                txt += f" × {int(self._replan_dose)} cGy"
            txt += ")"
        self.btn_replan.setText(txt)

    def resultado(self) -> dict:
        etapas = self._etapas_dados()
        rot = [p["rotulo"] for p in self._planos]
        dentro = self._indices_ficha()
        if self.rb_person and self.rb_person.isChecked():
            modo = "personalizado"
        elif self.rb_soma and self.rb_soma.isChecked():
            modo = "soma"
        else:
            modo = "individual"
        planos_ficha = ([i for i, c in enumerate(self._chips_ficha) if c.isChecked()]
                        if modo == "personalizado" else None)
        return {"etapas": etapas, "modo_ficha": modo,
                "planos_ficha": planos_ficha,
                # Planos cuja dose acumula junta na pág. 3 (mesma região).
                "grupos_dose": self._grupos_dose_dados(),
                # Separar Ficha: quais planos entram no documento (None = todos).
                # É o conjunto EFETIVO (ver _indices_ficha): quem está fora do
                # "Planos ▾" não entra, mesmo sem separação nenhuma.
                "planos_separados": (None if len(dentro) == len(self._planos)
                                     else dentro),
                "ordem_planos": list(self._ordem_planos),  # ordem das págs 2 e 3
                "replan_fracoes": self._replan_fracoes,
                "replan_dose": self._replan_dose,
                "sequencia": ag.sequencia_de_etapas(etapas),
                "resumo": ag.resumo_etapas(etapas, rot)}
