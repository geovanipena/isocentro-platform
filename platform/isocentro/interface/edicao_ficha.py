"""O diálogo que edita uma ficha já gerada, e os dois auxiliares dele.

Separado de ``gui.py`` em 27/08/2026. ``DialogImagemDias`` vem de
``formulario.py``, para onde foi na mesma leva — e não do ``gui``, que
importaria este módulo de volta.
"""
from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

from isocentro.dominio import constantes
from isocentro.dicom import dicom_rt
from isocentro.interface import estilo
from isocentro.papel import ficha_pdf
from isocentro.interface import ui
from isocentro.interface.formulario import DialogImagemDias


# ── Diálogo de edição da ficha ───────────────────────────────────────────────


class _RealceObservacoes(QSyntaxHighlighter):
    """Pré-visualiza no editor o destaque que sairá na ficha: o trecho entre
    ``**`` aparece em negrito sobre tarja amarela (o AMARELO da pág. 2) e os
    marcadores ficam apagados — o que se vê aqui é o que se lê no PDF."""

    _PADRAO = re.compile(r"\*\*(.+?)\*\*")

    def highlightBlock(self, texto: str) -> None:
        marca = QTextCharFormat()
        marca.setForeground(QColor(estilo.TEXTO_APAGADO))
        destaque = QTextCharFormat()
        # As duas cores são as do PAPEL, e por isso não saem do ``estilo``:
        # a tarja é o amarelo que a ficha imprime, e o texto tem de ficar
        # escuro sobre ele nos DOIS modos. Trocado pelo ``TEXTO`` do modo
        # noite, o realce viraria letra clara sobre amarelo — ilegível
        # justamente no trecho que existe para ser lido primeiro.
        destaque.setBackground(QColor("#" + ficha_pdf.AMARELO.hexval()[2:]))
        destaque.setForeground(QColor("#1a1a1a"))
        destaque.setFontWeight(QFont.Bold)
        for m in self._PADRAO.finditer(texto):
            self.setFormat(m.start(), len("**"), marca)
            self.setFormat(m.start(1), len(m.group(1)), destaque)
            self.setFormat(m.end(1), len("**"), marca)


class _TravaDuploClique(QObject):
    """Campos que só aceitam edição depois de um duplo clique.

    A Edição da Ficha é uma tela densa: dezenas de campos, muitos deles
    preenchidos pelo DICOM e que ninguém deveria tocar. Um clique perdido, uma
    roda do mouse sobre um spin box ou um Tab distraído bastavam para trocar uma
    dose sem ninguém perceber — e o valor sai impresso na ficha.

    Aqui todo campo nasce desabilitado (o Fusion já o pinta como inativo, que é
    o aviso visual) e abre individualmente no duplo clique. Uma vez aberto,
    continua aberto até fechar o diálogo: a trava é contra o acidente, não
    contra quem decidiu editar.

    O filtro fica no DIÁLOGO, não em cada campo: widget desabilitado não recebe
    evento de mouse, ele sobe para o pai. Quem descobre o alvo é ``childAt``,
    que enxerga filhos desabilitados.
    """

    def __init__(self, dialogo: QDialog, widgets):
        super().__init__(dialogo)
        self._alvos = list(widgets)
        for w in self._alvos:
            w.setEnabled(False)
            dica = w.toolTip()
            w.setToolTip((dica + "\n" if dica else "") + "Duplo clique para editar.")
        dialogo.installEventFilter(self)

    def eventFilter(self, obj, ev):  # noqa: N802 - assinatura do Qt
        if ev.type() == QEvent.MouseButtonDblClick:
            alvo = obj.childAt(ev.pos())
            # childAt devolve o filho mais profundo — no combo editável, o
            # QLineEdit interno. Sobe até achar o campo que a trava conhece.
            while alvo is not None and alvo not in self._alvos:
                alvo = alvo.parentWidget()
            if alvo is not None:
                self._liberar(alvo)
                return True
        return super().eventFilter(obj, ev)

    @staticmethod
    def _liberar(w) -> None:
        """Abre o campo e o deixa pronto para receber a digitação."""
        w.setEnabled(True)
        w.setFocus(Qt.MouseFocusReason)
        if isinstance(w, QComboBox):
            w.showPopup()          # o duplo clique já escolhe: mostra as opções
        elif isinstance(w, QLineEdit):
            w.selectAll()
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            w.selectAll()


class DialogEdicaoFicha(ui.Dialogo):
    """Editor consolidado de tudo que vai para a ficha e o registro JSON.

    Recebe o dict achatado do formulário (``coletar``) e o plano ``rp``; devolve
    ``(form_edits, rp_edits)`` para o chamador aplicar de volta.
    """

    # (rótulo, chave no feixe, tipo)
    _FEIXE_COLS = [
        ("Fase", "fase", "int"), ("Energia", "energia_rotulo", "str"),
        ("SSD", "ssd", "float"), ("Y1", "y1", "float"), ("Y2", "y2", "float"),
        ("X1", "x1", "float"), ("X2", "x2", "float"), ("Gantry", "gantry", "float"),
        # O FIM do arco, em coluna própria. Vazio em campo estático — e vazio
        # aqui quer dizer "não é arco", não "não sei". Sem ela, um VMAT
        # aparecia como cinco campos parados em 300 e 179, e quem viesse
        # conferir a ficha pela tabela "corrigiria" o ângulo certo.
        ("Gantry fim", "gantry_fim", "float"),
        ("Coll", "colimador", "float"), ("Mesa", "mesa", "float"),
        ("Bólus", "bolus", "str"), ("Tabela", "tabela", "str"), ("UM", "um", "float"),
    ]

    def __init__(self, dados_form: dict, rp: dict, parent=None, rotulo: str = ""):
        super().__init__("Edição da Ficha" + (f" — {rotulo}" if rotulo else ""),
                         parent, 1060, 800)
        self._rp_orig = rp or {}

        root = self.corpo
        _txt = "Revise e ajuste os dados que irão para a ficha e o registro JSON"
        if rotulo:
            _txt = f"{rotulo}  ·  " + _txt
        titulo = QLabel(_txt)
        titulo.setStyleSheet(
            f"font-weight:bold; font-size:13px; color:{estilo.ACAO};"
                          " padding:2px 2px 0;")
        root.addWidget(titulo)
        dica_trava = QLabel("Os campos estão travados — dê duplo clique no "
                            "campo para liberar a edição.")
        dica_trava.setStyleSheet(
            f"font-size:11px; color:{estilo.TEXTO_APAGADO}; padding:0 2px 6px;")
        root.addWidget(dica_trava)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        conteudo = QWidget()
        scroll.setWidget(conteudo)
        col = QVBoxLayout(conteudo)
        col.setSpacing(10)
        root.addWidget(scroll, 1)

        # ── Linha 1: paciente/prescrição (esq) | equipe·máquina/protocolo (dir)
        linha = QHBoxLayout()
        linha.setSpacing(10)
        col.addLayout(linha)

        g_pac, l_pac = self._grupo("Paciente")
        self.pac_nome = QLineEdit(dados_form.get("pac_nome", "") or "")
        self.pac_registro = QLineEdit(dados_form.get("pac_registro", "") or "")
        self.pac_nascimento = QLineEdit(dados_form.get("pac_nascimento", "") or "")
        l_pac.addRow("Nome", self.pac_nome)
        l_pac.addRow("Registro", self.pac_registro)
        l_pac.addRow("Nascimento", self.pac_nascimento)

        g_rx, l_rx = self._grupo("Prescrição")
        self.dose_total = self._dspin(0, 200, 2, " Gy",
                                      dados_form.get("rx_dose_total") or rp.get("dose_total"))
        self.dose_fracao = self._dspin(0, 50, 2, " Gy",
                                       dados_form.get("rx_dose_fracao") or rp.get("dose_fracao"))
        self.num_fracoes = QSpinBox()
        self.num_fracoes.setRange(0, 200)
        self.num_fracoes.setValue(int(dados_form.get("rx_fracoes") or rp.get("num_fracoes") or 0))
        self.fracionamento = QComboBox()
        self.fracionamento.setEditable(True)
        self.fracionamento.addItems(["1x dia", "Dias alter.", "2x sem.", "Única"])
        self.fracionamento.setCurrentText(dados_form.get("fracionamento", "") or "")
        self.plano_rotulo = QLineEdit(str(rp.get("rotulo_plano") or rp.get("nome_plano") or ""))
        l_rx.addRow("Dose total", self.dose_total)
        l_rx.addRow("Dose / fração", self.dose_fracao)
        l_rx.addRow("Nº frações", self.num_fracoes)
        l_rx.addRow("Fracionamento", self.fracionamento)
        l_rx.addRow("Plano (rótulo)", self.plano_rotulo)

        c_esq = QVBoxLayout()
        c_esq.setSpacing(10)
        c_esq.addWidget(g_pac)
        c_esq.addWidget(g_rx)
        c_esq.addStretch()
        linha.addLayout(c_esq, 1)

        g_eq, l_eq = self._grupo("Equipe e Máquina")
        self.eq_medico = QLineEdit(dados_form.get("eq_medico", "") or "")
        self.eq_fisico = QLineEdit(dados_form.get("eq_fisico", "") or "")
        self.maquina = QComboBox()
        self._preencher_maquinas(
            str(dados_form.get("maquina") or rp.get("maquina") or ""))
        self.energia = QLineEdit(str(rp.get("energia") or ""))
        self.tecnica = QLineEdit(str(rp.get("tecnica") or ""))
        l_eq.addRow("Médico", self.eq_medico)
        l_eq.addRow("Físico", self.eq_fisico)
        l_eq.addRow("Máquina", self.maquina)
        l_eq.addRow("Energia", self.energia)
        l_eq.addRow("Técnica", self.tecnica)

        g_pr, l_pr = self._grupo("Protocolo")
        self.proto_imagem = QComboBox()
        self.proto_imagem.setEditable(True)
        self.proto_imagem.addItems(list(constantes.TIPOS_IMAGEM))
        self.proto_imagem.setCurrentText(dados_form.get("proto_imagem", "") or "")
        self.proto_freq = QComboBox()
        self.proto_freq.setEditable(True)
        self.proto_freq.addItems(list(constantes.FREQUENCIAS))
        self.proto_freq.setCurrentText(dados_form.get("proto_frequencia", "") or "")
        self._imagem_dias = [int(x) for x in (dados_form.get("proto_imagem_dias") or [])]
        self._freq_anterior = (dados_form.get("proto_frequencia", "") or "")
        self.proto_freq.activated.connect(lambda _i: self._on_freq_activated())
        self.gating = QComboBox()
        self.gating.addItems(["Não", "Sim"])
        self.gating.setCurrentText(dados_form.get("gating", "Não") or "Não")
        self.gating_modal = QComboBox()
        self.gating_modal.addItems(list(constantes.MODALIDADES_GATING))
        if dados_form.get("gating_modalidade"):
            self.gating_modal.setCurrentText(dados_form["gating_modalidade"])
        self.fase_ini = QSpinBox(); self.fase_ini.setRange(0, 100); self.fase_ini.setSuffix("%")
        self.fase_fim = QSpinBox(); self.fase_fim.setRange(0, 100); self.fase_fim.setSuffix("%")
        _fase = str(dados_form.get("gating_fase", "") or "")
        if "-" in _fase:
            try:
                _a, _b = _fase.split("-", 1)
                self.fase_ini.setValue(int(_a)); self.fase_fim.setValue(int(_b))
            except ValueError:
                pass
        w_jan = QWidget()
        _lj = QHBoxLayout(w_jan); _lj.setContentsMargins(0, 0, 0, 0); _lj.setSpacing(4)
        _lj.addWidget(self.fase_ini); _lj.addWidget(QLabel("–"))
        _lj.addWidget(self.fase_fim); _lj.addStretch()
        l_pr.addRow("Imagem", self.proto_imagem)
        l_pr.addRow("Frequência", self.proto_freq)
        l_pr.addRow("Gating", self.gating)
        l_pr.addRow("Modalidade", self.gating_modal)
        l_pr.addRow("Janela (fase)", w_jan)

        c_dir = QVBoxLayout()
        c_dir.setSpacing(10)
        c_dir.addWidget(g_eq)
        c_dir.addWidget(g_pr)
        c_dir.addStretch()
        linha.addLayout(c_dir, 1)

        # ── SSD e Deslocamento ───────────────────────────────────────────────
        g_ssd = QGroupBox("SSD e Deslocamento (cm)")
        g_ssd.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        grid = QGridLayout(g_ssd)
        grid.setContentsMargins(14, 18, 14, 12)
        grid.setHorizontalSpacing(10); grid.setVerticalSpacing(10)
        self.ssd: dict[str, QDoubleSpinBox] = {}

        def _linha_ssd(r, titulo, specs):
            grid.addWidget(QLabel(titulo), r, 0)
            for i, (lbl, key) in enumerate(specs):
                cel = QWidget()
                h = QHBoxLayout(cel); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(4)
                sp = self._dspin(-200, 400, 1, "", rp.get(key))
                self.ssd[key] = sp
                lb = QLabel(lbl); lb.setMinimumWidth(34)
                h.addWidget(lb); h.addWidget(sp)
                grid.addWidget(cel, r, i + 1)

        _linha_ssd(0, "SSD TP0", [("G0", "ssd_tp0_g0"), ("G270", "ssd_tp0_g270"), ("G90", "ssd_tp0_g90")])
        _linha_ssd(1, "Desloc.", [("Lat", "desl_lat"), ("Long", "desl_long"), ("Vert", "desl_vert")])
        _linha_ssd(2, "SSD Iso", [("G0", "ssd_iso_g0"), ("G270", "ssd_iso_g270"), ("G90", "ssd_iso_g90")])
        col.addWidget(g_ssd)

        # ── Campos / Feixes ──────────────────────────────────────────────────
        g_fx = QGroupBox("Campos / Feixes")
        vfx = QVBoxLayout(g_fx)
        self.tab_feixes = QTableWidget(0, len(self._FEIXE_COLS))
        self.tab_feixes.setHorizontalHeaderLabels([c[0] for c in self._FEIXE_COLS])
        feixes = rp.get("feixes") or []
        # De qual feixe ORIGINAL é cada linha. Começa 0,1,2… e acompanha as
        # linhas quando a ordem muda: sem ele, ``resultado`` casaria a linha 1
        # com o feixe 1 e devolveria os valores de um campo no outro.
        self._ordem = list(range(len(feixes)))
        self.tab_feixes.setRowCount(len(feixes))
        for i, f in enumerate(feixes):
            # O rótulo traz o NÚMERO do feixe, não a posição na tabela. Desde
            # que a ficha passou a sair na ordem da volta do gantry (ver
            # ``dicom_rt.ordenar_feixes``), a 4ª linha daqui não é o "Campo 4"
            # impresso — e quem corrige o campo lendo a folha editaria outro.
            _num = f.get("numero")
            self.tab_feixes.setVerticalHeaderItem(
                i, QTableWidgetItem(f"Campo {_num if _num is not None else i + 1}"))
            for j, (_hdr, key, _tipo) in enumerate(self._FEIXE_COLS):
                val = f.get(key)
                self.tab_feixes.setItem(
                    i, j, QTableWidgetItem("" if val is None else str(val)))
        self.tab_feixes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tab_feixes.setMinimumHeight(180)
        if not feixes:
            aviso = QLabel("Nenhum feixe carregado (importe um plano RP).")
            estilo.pintar(aviso, lambda: (
                f"color:{estilo.TEXTO_APAGADO};"
                " font-style:italic; padding:6px;"))
            vfx.addWidget(aviso)
        vfx.addWidget(self.tab_feixes)
        if feixes:
            vfx.addLayout(self._barra_de_ordem())
        col.addWidget(g_fx)

        # ── Observações (caixa "Observações gerais do tratamento" da pág. 2) ──
        g_obs = QGroupBox("Observações do tratamento (pág. 2)")
        vobs = QVBoxLayout(g_obs)
        vobs.setContentsMargins(12, 16, 12, 12)
        vobs.setSpacing(6)
        self.observacoes = QPlainTextEdit(str(dados_form.get("observacoes", "") or ""))
        self.observacoes.setMinimumHeight(96)
        self.observacoes.setTabChangesFocus(True)
        self._realce_obs = _RealceObservacoes(self.observacoes.document())
        barra = QHBoxLayout()
        barra.setSpacing(8)
        b_hl = QPushButton("Destacar seleção")
        b_hl.setToolTip("Envolve o trecho selecionado em ** ** — na ficha ele sai "
                        "em negrito sobre tarja amarela.")
        b_hl.clicked.connect(self._destacar_obs)
        dica = QLabel("Escreva **assim** para destacar; Enter quebra a linha. "
                      "O que não couber na caixa da ficha é aparado.")
        estilo.pintar(dica, lambda: (
            f"color:{estilo.TEXTO_APAGADO}; font-size:11px;"))
        barra.addWidget(b_hl)
        barra.addWidget(dica)
        barra.addStretch()
        vobs.addWidget(self.observacoes)
        vobs.addLayout(barra)
        col.addWidget(g_obs)

        # Mostra o início de textos longos (nomes) em vez do fim.
        # A Máquina saiu daqui ao virar combo: ela não tem cursor de texto.
        for le in (self.pac_nome, self.pac_registro, self.pac_nascimento,
                   self.eq_medico, self.eq_fisico,
                   self.energia, self.tecnica, self.plano_rotulo):
            le.setCursorPosition(0)

        # ── Trava contra edição acidental ────────────────────────────────────
        # Todo campo começa fechado e abre no duplo clique (ver
        # ``_TravaDuploClique``). A tabela de feixes fica de fora: o Qt já edita
        # célula só no duplo clique, e desabilitá-la inteira tiraria a rolagem.
        self._trava = _TravaDuploClique(self, [
            self.pac_nome, self.pac_registro, self.pac_nascimento,
            self.dose_total, self.dose_fracao, self.num_fracoes,
            self.fracionamento, self.plano_rotulo,
            self.eq_medico, self.eq_fisico, self.maquina, self.energia,
            self.tecnica, self.proto_imagem, self.proto_freq,
            self.gating, self.gating_modal, self.fase_ini, self.fase_fim,
            self.observacoes,
            *self.ssd.values(),
        ])
        # Só duplo clique: o padrão do Qt também abre a célula com qualquer
        # tecla, que é o mesmo acidente pela via do teclado.
        self.tab_feixes.setEditTriggers(QTableWidget.DoubleClicked)

        # ── Botões ───────────────────────────────────────────────────────────
        # A ordem AQUI era o inverso do resto do programa (Cancelar antes de
        # Aplicar). Como esta é a tela mais usada de todas, era ela que formava
        # a memória muscular errada — e a próxima janela punha "Cancelar" onde
        # a mão já ia clicar. Ver ``ui.Dialogo.rodape``.
        self.rodape("Aplicar")

    # ── Ordem dos campos ─────────────────────────────────────────────────────
    def _barra_de_ordem(self) -> QHBoxLayout:
        """Os botões que mudam a ordem em que os campos saem na ficha.

        A ordem impressa NÃO é a do DICOM: a ficha põe os campos na volta do
        gantry, para quem está na sala conferir o braço andando num sentido só
        (ver ``dicom_rt.ordenar_feixes``). Isso serve para a maioria dos casos e
        não serve para todos — daí poder mexer aqui, campo a campo.

        As duas ordens canônicas ficam a um clique. "Ordem do TPS" é a que o
        planejamento escolheu — e a que a ficha já usa sozinha acima de 600 cGy
        por fração (ver ``dicom_rt.DOSE_ORDEM_DO_TPS_CGY``); "Ordem do gantry" é
        a das demais fichas, e é o caminho de volta: sem ele, quem
        experimentasse a outra ordem só desfaria cancelando o diálogo inteiro,
        perdendo o resto da edição junto.

        A coluna "Campo" da ficha é a POSIÇÃO (1, 2, 3…), então reordenar aqui
        renumera os campos no papel. O cabeçalho de cada linha continua dizendo
        o número do feixe no plano, que é o que não muda.
        """
        barra = QHBoxLayout()
        barra.setSpacing(8)
        self._b_sobe = QPushButton("▲ Subir")
        self._b_desce = QPushButton("▼ Descer")
        b_tps = QPushButton("Ordem do TPS")
        b_gantry = QPushButton("Ordem do gantry")
        self._b_sobe.clicked.connect(lambda: self._mover_feixe(-1))
        self._b_desce.clicked.connect(lambda: self._mover_feixe(+1))
        b_tps.clicked.connect(lambda: self._reordenar_por("tps"))
        b_gantry.clicked.connect(lambda: self._reordenar_por("gantry"))
        b_tps.setToolTip("A ordem em que o plano foi exportado pelo TPS — a que "
                         "vale sozinha acima de 600 cGy por fração.")
        b_gantry.setToolTip("A volta do gantry, como saem as demais fichas.")
        for b in (self._b_sobe, self._b_desce, b_tps, b_gantry):
            b.setStyleSheet(estilo.btn_contorno(11.0))
            barra.addWidget(b)
        dica = QLabel("Selecione um campo e use ▲▼ para mudar a ordem "
                      "impressa.")
        dica.setStyleSheet(f"color:{estilo.TEXTO_APAGADO}; font-size:11px;")
        barra.addWidget(dica)
        barra.addStretch()
        # ▲▼ acesos só quando há campo selecionado, e apagados nas pontas: um
        # botão que, clicado, não faz nada devia estar apagado com o motivo no
        # tooltip. É também o que tira do caminho o clique perdido que
        # renumeraria os campos impressos sem ninguém pedir.
        self.tab_feixes.currentCellChanged.connect(
            lambda *_: self._atualizar_botoes_de_ordem())
        self._atualizar_botoes_de_ordem()
        return barra

    def _atualizar_botoes_de_ordem(self) -> None:
        """Acende ▲▼ conforme dê para mover a linha selecionada."""
        i = self.tab_feixes.currentRow()
        n = self.tab_feixes.rowCount()
        pode_subir = 0 < i < n
        pode_descer = 0 <= i < n - 1
        self._b_sobe.setEnabled(pode_subir)
        self._b_desce.setEnabled(pode_descer)
        self._b_sobe.setToolTip(
            "Sobe o campo selecionado uma posição na ficha." if pode_subir
            else ("Selecione um campo para mover." if i < 0
                  else "Este campo já é o primeiro."))
        self._b_desce.setToolTip(
            "Desce o campo selecionado uma posição na ficha." if pode_descer
            else ("Selecione um campo para mover." if i < 0
                  else "Este campo já é o último."))

    def _linhas_da_tabela(self) -> list:
        """``(feixe original, cabeçalho, textos)`` de cada linha, como está.

        Lê o que está NA TELA, e não o ``rp`` de origem: reordenar depois de
        corrigir um ângulo tem de levar a correção junto.
        """
        linhas = []
        for i in range(self.tab_feixes.rowCount()):
            cab = self.tab_feixes.verticalHeaderItem(i)
            textos = []
            for j in range(len(self._FEIXE_COLS)):
                item = self.tab_feixes.item(i, j)
                textos.append(item.text() if item else "")
            linhas.append((self._ordem[i], cab.text() if cab else "", textos))
        return linhas

    def _repor_linhas(self, linhas) -> None:
        """Reescreve a tabela na ordem dada, com o ``_ordem`` acompanhando."""
        self._ordem = [orig for orig, _cab, _txt in linhas]
        for i, (_orig, cab, textos) in enumerate(linhas):
            self.tab_feixes.setVerticalHeaderItem(i, QTableWidgetItem(cab))
            for j, txt in enumerate(textos):
                self.tab_feixes.setItem(i, j, QTableWidgetItem(txt))

    def _mover_feixe(self, passo: int) -> None:
        """Troca a linha selecionada com a de cima (-1) ou a de baixo (+1)."""
        i = self.tab_feixes.currentRow()
        j = i + passo
        if i < 0 or not 0 <= j < self.tab_feixes.rowCount():
            return                       # nada selecionado, ou já na ponta
        linhas = self._linhas_da_tabela()
        linhas[i], linhas[j] = linhas[j], linhas[i]
        self._repor_linhas(linhas)
        self.tab_feixes.setCurrentCell(j, max(self.tab_feixes.currentColumn(), 0))
        self._atualizar_botoes_de_ordem()

    def _reordenar_por(self, criterio: str) -> None:
        """Repõe uma das duas ordens canônicas: ``"tps"`` ou ``"gantry"``.

        O gantry é lido da TELA (coluna Gantry), não do plano: quem acabou de
        corrigir um ângulo espera que a ordem siga o valor corrigido, e não o
        que o DICOM trouxe.
        """
        linhas = self._linhas_da_tabela()
        feixes_orig = self._rp_orig.get("feixes") or []
        col_gantry = [c[1] for c in self._FEIXE_COLS].index("gantry")
        leves = []
        for pos, (orig, _cab, textos) in enumerate(linhas):
            base = feixes_orig[orig] if orig < len(feixes_orig) else {}
            leves.append({
                "_pos": pos,
                "numero": base.get("numero"),
                "ordem_tps": base.get("ordem_tps"),
                "gantry": self._como_numero(textos[col_gantry]),
            })
        if criterio == "tps":
            ordenados = dicom_rt.ordem_do_tps(leves)
        else:
            ordenados = dicom_rt.ordenar_feixes(
                leves, str(self.plano_rotulo.text() or ""))
        self._repor_linhas([linhas[f["_pos"]] for f in ordenados])

    @staticmethod
    def _como_numero(texto: str):
        """O texto de uma célula como número, ou ``None`` se não for um."""
        try:
            return float(str(texto).replace(",", ".").strip())
        except (TypeError, ValueError):
            return None

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _preencher_maquinas(self, atual: str) -> None:
        """Enche o combo de máquinas com as da UNIDADE do caso.

        Digitar o nome do acelerador era o pior tipo de campo livre: o texto
        vira a IDENTIDADE da máquina (``identificar_maquina``), e dela saem o
        desenho da mesa, o protocolo de imagem, o fluxo do SUS e o logo da
        página. Um "TrueBeamSN1003" trocado num dígito não dá erro nenhum —
        apenas deixa de casar, e a ficha sai com os padrões de máquina nenhuma.

        Cada item MOSTRA o nome pelo qual a máquina é chamada e GUARDA o nome de
        fábrica (``itemData``): é o de fábrica que vai para o ``rp`` e para o
        registro JSON, porque é por ele que o casamento acha a máquina. Combo
        que gravasse o nome de exibição quebraria os quatro em silêncio.

        Máquina que a lista não tem — nome com prefixo de sala, acervo antigo,
        caso de outra unidade — entra como primeiro item, com o valor original.
        O combo não pode trocar calado a máquina de uma ficha que já existe.
        """
        unidade = constantes.unidade_da_maquina(atual)
        chaves = []
        for m in constantes.maquinas_da_unidade(unidade):
            self.maquina.addItem(constantes.rotulo_maquina(m.chave), m.chave)
            chaves.append(m.chave)
        alvo = (atual or "").strip()
        if alvo and alvo not in chaves:
            self.maquina.insertItem(0, constantes.rotulo_maquina(alvo), alvo)
            self.maquina.setCurrentIndex(0)
        elif alvo:
            self.maquina.setCurrentIndex(chaves.index(alvo))
        else:
            # Sem máquina, VAZIO — e não a primeira da lista. Campo que se
            # preenche sozinho com um palpite é dado inventado.
            self.maquina.insertItem(0, " ", "")
            self.maquina.setCurrentIndex(0)

    def _maquina_escolhida(self) -> str:
        """O nome de FÁBRICA da máquina escolhida (o que vai para o registro)."""
        dado = self.maquina.currentData()
        if dado is None:
            dado = self.maquina.currentText()
        return str(dado).strip()

    @staticmethod
    def _grupo(titulo: str) -> tuple[QGroupBox, QFormLayout]:
        """Grupo com altura fixa (não comprime linhas) e espaçamento folgado."""
        g = QGroupBox(titulo)
        g.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay = QFormLayout(g)
        lay.setRowWrapPolicy(QFormLayout.DontWrapRows)
        lay.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        lay.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.setVerticalSpacing(9)
        lay.setHorizontalSpacing(10)
        lay.setContentsMargins(12, 16, 12, 12)
        return g, lay

    @staticmethod
    def _dspin(lo, hi, dec, suffix, val) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setDecimals(dec)
        if suffix:
            sp.setSuffix(suffix)
        sp.setMinimumWidth(78)
        try:
            if val is not None and val != "":
                sp.setValue(float(val))
        except (TypeError, ValueError):
            pass
        return sp

    def _on_freq_activated(self) -> None:
        """'Personalizado' abre o editor de dias de imagem (grade de frações)."""
        if self.proto_freq.currentText().strip() != "Personalizado":
            self._freq_anterior = self.proto_freq.currentText().strip()
            return
        nfr = self.num_fracoes.value()
        if nfr <= 0:
            ui.avisar(
                self, "Frações necessárias",
                "Defina o número de frações antes de personalizar os dias de imagem.")
            self._reverter_freq()
            return
        dlg = DialogImagemDias(nfr, self._imagem_dias, self)
        if dlg.exec() == QDialog.Accepted:
            self._imagem_dias = dlg.dias()
        elif not self._imagem_dias:
            self._reverter_freq()

    def _reverter_freq(self) -> None:
        self.proto_freq.blockSignals(True)
        if self._freq_anterior:
            self.proto_freq.setCurrentText(self._freq_anterior)
        else:
            self.proto_freq.setCurrentIndex(-1)
        self.proto_freq.blockSignals(False)

    def _destacar_obs(self) -> None:
        """Envolve a seleção em ``**`` (ou remove, se já estiver destacada)."""
        cur = self.observacoes.textCursor()
        if not cur.hasSelection():
            self.observacoes.setFocus()
            return
        sel = cur.selectedText()
        novo = (sel[2:-2] if sel.startswith("**") and sel.endswith("**") and len(sel) > 4
                else f"**{sel}**")
        cur.insertText(novo)
        self.observacoes.setFocus()

    def resultado(self) -> tuple[dict, dict]:
        """Devolve (form_edits, rp_edits) para o chamador aplicar."""
        gating = self.gating.currentText()
        modal = self.gating_modal.currentText() if gating == "Sim" else ""
        fase = (f"{self.fase_ini.value()}-{self.fase_fim.value()}"
                if gating == "Sim" and modal == "Fase" else "")
        form_edits = {
            "pac_nome": self.pac_nome.text().strip(),
            "pac_registro": self.pac_registro.text().strip(),
            "pac_nascimento": self.pac_nascimento.text().strip(),
            "rx_dose_total": self.dose_total.value() or None,
            "rx_dose_fracao": self.dose_fracao.value() or None,
            "rx_fracoes": self.num_fracoes.value() or None,
            "fracionamento": self.fracionamento.currentText().strip(),
            "proto_imagem": self.proto_imagem.currentText().strip(),
            "proto_frequencia": self.proto_freq.currentText().strip(),
            "proto_imagem_dias": (sorted(self._imagem_dias)
                                  if self.proto_freq.currentText().strip() == "Personalizado"
                                  else []),
            "gating": gating,
            "gating_modalidade": modal,
            "gating_fase": fase,
            "eq_medico": self.eq_medico.text().strip(),
            "eq_fisico": self.eq_fisico.text().strip(),
            "observacoes": self.observacoes.toPlainText().strip(),
        }

        rp = dict(self._rp_orig)
        rp["maquina"] = self._maquina_escolhida()
        rp["energia"] = self.energia.text().strip()
        rp["tecnica"] = self.tecnica.text().strip()
        rp["rotulo_plano"] = self.plano_rotulo.text().strip()
        rp["dose_total"] = self.dose_total.value() or None
        rp["dose_fracao"] = self.dose_fracao.value() or None
        rp["num_fracoes"] = self.num_fracoes.value() or None
        for key, sp in self.ssd.items():
            v = sp.value()
            # Não fabrica 0.0 onde o valor original era ausente.
            if v == 0.0 and self._rp_orig.get(key) in (None, ""):
                rp[key] = self._rp_orig.get(key)
            else:
                rp[key] = v

        feixes_orig = self._rp_orig.get("feixes") or []
        novos = []
        for i in range(self.tab_feixes.rowCount()):
            # A LINHA pode não ser mais o feixe de mesma posição: a ordem dos
            # campos é editável (ver ``_barra_de_ordem``), e é ``self._ordem``
            # que diz de quem é a linha. Casar por posição devolvia os valores
            # de um campo dentro de outro — e eles vão impressos.
            orig = self._ordem[i] if i < len(self._ordem) else i
            base = dict(feixes_orig[orig]) if orig < len(feixes_orig) else {}
            for j, (_hdr, key, tipo) in enumerate(self._FEIXE_COLS):
                item = self.tab_feixes.item(i, j)
                txt = item.text().strip() if item else ""
                if tipo in ("float", "int"):
                    if txt == "":
                        base[key] = None
                    else:
                        try:
                            num = float(txt.replace(",", "."))
                            base[key] = int(num) if tipo == "int" else num
                        except ValueError:
                            base[key] = txt
                else:
                    base[key] = txt
            novos.append(base)
        if novos or feixes_orig:
            rp["feixes"] = novos
        return form_edits, rp
