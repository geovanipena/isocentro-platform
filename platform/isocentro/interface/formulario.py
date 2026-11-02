"""O painel de formulário da esquerda: as abas de plano e os dados do caso.

Separado de ``gui.py`` em 27/08/2026. Vieram junto as constantes que só ele
usava — ``_VAZIO_SPIN``, ``_OPCOES_FRAC`` e ``_DOSE_FRAC_ALTA``. A do cache de
render 3D (``_MAX_CACHE_3D``) não veio: apesar de estar no meio delas, é do
visualizador — e desde 16/09/2026 mora no ``controle_viewer.py``.

``_carregar_fisicos``/``_carregar_medicos`` vêm de ``equipe.py``, o mesmo lugar
de onde o ``gui.py`` os importa — e não do ``gui``, que importaria este módulo
de volta.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

from isocentro.banco import capa_dados
from isocentro.banco import tratamento_db
from isocentro.dominio import constantes
from isocentro.interface import estilo
from isocentro.interface import ui
from isocentro.dados.equipe import (_carregar_fisicos, _carregar_medicos,
                                    equipe_da_maquina)

_LOG = logging.getLogger(__name__)


# O que um contador mostra quando ainda não tem valor (``setSpecialValueText``,
# exibido enquanto o valor é o mínimo). Um ESPAÇO, e não string vazia: o Qt
# entende ``""`` como "não há texto especial" e volta a escrever o "0,00 Gy"
# que este truque existe para esconder.
_VAZIO_SPIN = " "

def _grupo_form(titulo: str) -> tuple[QGroupBox, QFormLayout]:
    g = QGroupBox(titulo)
    g.setMinimumHeight(90)
    lay = QFormLayout(g)
    lay.setRowWrapPolicy(QFormLayout.DontWrapRows)
    # Campos sem largura fixa (ex.: Nome) crescem para preencher o grupo —
    # senão o Fusion mantém o campo no sizeHint e o grupo fica desbalanceado.
    lay.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    lay.setVerticalSpacing(4)
    lay.setHorizontalSpacing(8)
    lay.setContentsMargins(8, 4, 8, 6)
    return g, lay

# Padrões de fracionamento oferecidos ao confirmar dose/fração alta. A lista
# mora no domínio porque é ela que traduz a frequência da prescrição
# (``constantes.fracionamento_da_frequencia``): duas cópias divergiriam em
# silêncio, e a divergência apareceria como fracionamento que "não entrou".
_OPCOES_FRAC = list(constantes.OPCOES_FRACIONAMENTO)

# Acima desta dose/fração (Gy) o fracionamento é confirmado com o usuário.
_DOSE_FRAC_ALTA = 6.0

def _frac_inicial(nfr: int, atual: str, dose_alta: bool = True) -> str:
    """Fracionamento já selecionado ao abrir o popup de dose alta.

    Para o plano de DOSE ALTA com mais de 2 frações sugere 'Dias alter.' — o
    hipofracionamento costuma ser em dias alternados, e deixar isso pré-escolhido
    resolve o caso comum num Ok. Plano de dose NORMAL (incluído só para ajustar o
    dia de início) mantém o fracionamento que já traz — convencional é 1x/dia, não
    dias alternados. Fora disso mantém o que a aba já traz ('Única' para 1 fração).
    """
    if dose_alta and nfr > 2:
        return "Dias alter."
    return atual if atual in _OPCOES_FRAC else _OPCOES_FRAC[0]


class _AbaPlano(QWidget):
    """Uma aba do formulário: Prescrição + Protocolo + Relação de UM plano."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rotulo = ""   # identificação do plano (ex.: "Plano 2/3: BOOST")
        # O fracionamento desta aba veio da prescrição aprovada? Quando veio,
        # não se pergunta de novo (ver ``perguntar_doses_altas``).
        self._frac_prescrito = False
        self._dia_inicio = 1   # dia de início no agendamento (tela de fracionamento)
        self._imagem_dias: list = []   # frações (1-based) com imagem (freq Personalizado)
        self._freq_anterior = ""       # última frequência não-personalizada escolhida
        # Dose total = dose/fração × nº frações enquanto o usuário não a digitar à
        # mão: editar dose/fração ou nº frações recalcula o total sozinho.
        self._total_auto = True
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        # ── Prescrição ───────────────────────────────────
        g_rx, l_rx = _grupo_form("Prescrição")
        l_rx.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        # Zero aparece VAZIO, não como "0,00 Gy". Ninguém prescreve zero: o zero
        # aqui significa "ainda não veio", e escrito por extenso ele se lê como
        # um valor conferido — a mesma armadilha do "Nome completo" em cinza
        # dentro do campo do nome. É só a pintura: ``coletar`` já converte 0 em
        # ``None``, então o que sai da tela não muda.
        self.rx_dose_total = QDoubleSpinBox()
        self.rx_dose_total.setRange(0, 200); self.rx_dose_total.setDecimals(2)
        self.rx_dose_total.setSuffix(" Gy"); self.rx_dose_total.setFixedWidth(160)
        self.rx_dose_total.setSpecialValueText(_VAZIO_SPIN)
        self.rx_dose_fracao = QDoubleSpinBox()
        self.rx_dose_fracao.setRange(0, 50); self.rx_dose_fracao.setDecimals(2)
        self.rx_dose_fracao.setSuffix(" Gy"); self.rx_dose_fracao.setFixedWidth(160)
        self.rx_dose_fracao.setSpecialValueText(_VAZIO_SPIN)
        self.rx_fracoes = QSpinBox()
        self.rx_fracoes.setRange(0, 200); self.rx_fracoes.setFixedWidth(160)
        self.rx_fracoes.setSpecialValueText(_VAZIO_SPIN)
        self.rx_fracionamento = QComboBox(); self.rx_fracionamento.setEditable(True)
        self.rx_fracionamento.addItems(_OPCOES_FRAC)
        self.rx_fracionamento.setCurrentIndex(-1)
        self.rx_fracionamento.setFixedWidth(160)
        l_rx.addRow("Dose total", self.rx_dose_total)
        l_rx.addRow("Dose / fração", self.rx_dose_fracao)
        l_rx.addRow("Nº frações", self.rx_fracoes)
        l_rx.addRow("Fracionamento", self.rx_fracionamento)

        # ── Protocolo ────────────────────────────────────
        g_proto, l_proto = _grupo_form("Protocolo")
        l_proto.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        self.proto_imagem = QComboBox()
        self.proto_imagem.setEditable(True)
        self.proto_imagem.setInsertPolicy(QComboBox.NoInsert)
        self.proto_imagem.addItems(list(constantes.TIPOS_IMAGEM))
        self.proto_imagem.setCurrentIndex(-1)
        self.proto_imagem.setFixedWidth(160)
        self.proto_freq = QComboBox()
        self.proto_freq.setEditable(True)
        self.proto_freq.setInsertPolicy(QComboBox.NoInsert)
        self.proto_freq.addItems(list(constantes.FREQUENCIAS))
        self.proto_freq.setCurrentIndex(-1)
        self.proto_freq.setFixedWidth(160)
        self.rx_gating = QComboBox(); self.rx_gating.addItems(["Não", "Sim"])
        self.rx_gating.setFixedWidth(160)
        self.rx_gating_modal = QComboBox()
        self.rx_gating_modal.addItems(list(constantes.MODALIDADES_GATING))
        # Nasce em branco, como Imagem e Frequência: a primeira modalidade da
        # lista aparecendo sozinha é um palpite com cara de leitura. Quando o
        # DICOM diz qual é, quem escreve é ``_definir_gating``.
        self.rx_gating_modal.setCurrentIndex(-1)
        self.rx_gating_modal.setFixedWidth(160)
        self._w_fase_janela = QWidget()
        _lf = QHBoxLayout(self._w_fase_janela)
        _lf.setContentsMargins(0, 0, 0, 0); _lf.setSpacing(4)
        self.rx_fase_ini = QSpinBox()
        self.rx_fase_ini.setRange(0, 100); self.rx_fase_ini.setSingleStep(10)
        self.rx_fase_ini.setValue(10); self.rx_fase_ini.setSuffix("%")
        self.rx_fase_ini.setFixedWidth(52)
        self.rx_fase_fim = QSpinBox()
        self.rx_fase_fim.setRange(0, 100); self.rx_fase_fim.setSingleStep(10)
        self.rx_fase_fim.setValue(80); self.rx_fase_fim.setSuffix("%")
        self.rx_fase_fim.setFixedWidth(52)
        _lf.addWidget(self.rx_fase_ini); _lf.addWidget(QLabel("-"))
        _lf.addWidget(self.rx_fase_fim); _lf.addStretch()
        self._lbl_gating_modal = QLabel("Modalidade")
        self._lbl_gating_fase  = QLabel("Janela")
        l_proto.addRow("Imagem", self.proto_imagem)
        l_proto.addRow("Frequência", self.proto_freq)
        l_proto.addRow("Gating", self.rx_gating)
        l_proto.addRow(self._lbl_gating_modal, self.rx_gating_modal)
        l_proto.addRow(self._lbl_gating_fase,  self._w_fase_janela)
        self._lbl_gating_modal.hide(); self.rx_gating_modal.hide()
        self._lbl_gating_fase.hide();  self._w_fase_janela.hide()

        # (A relação entre planos foi movida para a tela "Agendamento do
        #  Tratamento", acessível quando há mais de um plano.)

        # Nunca comprimir os grupos abaixo do conteúdo — senão os títulos e as
        # linhas de Prescrição/Protocolo "somem" quando a janela aperta.
        for _g in (g_rx, g_proto):
            _g.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            _g.setMinimumHeight(_g.sizeHint().height())
        # Grupos no tamanho natural (rótulo + campo 160), sem esticar — o
        # FieldsStayAtSizeHint evita vão interno. Espalhados pela metade direita
        # com folga igual entre e ao redor (preenchem o espaço).
        lay.addStretch(1)
        lay.addWidget(g_rx)
        lay.addStretch(1)
        lay.addWidget(g_proto)
        lay.addStretch(1)

        self.rx_fracoes.valueChanged.connect(self._auto_fracionamento)
        self.rx_fracoes.valueChanged.connect(self._sincronizar_dose_total)
        # Antes do ``_verificar_dose_fracao``, que abre modal: quando o
        # fracionamento é perguntado, a frequência de imagem já tem de estar
        # ajustada à dose que acabou de ser digitada.
        self.rx_dose_fracao.valueChanged.connect(self._aplicar_imagem_por_dose)
        self.rx_dose_fracao.valueChanged.connect(self._verificar_dose_fracao)
        self.rx_dose_fracao.valueChanged.connect(self._sincronizar_dose_total)
        self.rx_dose_total.valueChanged.connect(self._on_dose_total_editada)
        self.rx_gating.currentTextChanged.connect(self._toggle_gating)
        self.rx_gating_modal.currentTextChanged.connect(self._toggle_gating_fase)
        # 'activated' só dispara em escolha do usuário (não em setCurrentText),
        # então preencher o formulário não abre o editor de dias de imagem.
        self.proto_freq.activated.connect(lambda _i: self._on_freq_activated())

    # ── Sinais ────────────────────────────────────────────────────────────────
    def _auto_fracionamento(self, valor: int) -> None:
        atual = self.rx_fracionamento.currentText().strip()
        if valor == 1:
            # 1 fração é sempre sessão única.
            self.rx_fracionamento.setCurrentText("Única")
        elif atual in ("", "Única"):
            # >1 fração e o usuário não escolheu (ou saiu de "Única") → padrão
            # "1x dia". Escolhas manuais (ex.: "2x sem.") são preservadas.
            self.rx_fracionamento.setCurrentText("1x dia")

    def _aplicar_imagem_por_dose(self, *_) -> None:
        """Dose alta por fração → imagem DIÁRIA, seja qual for a máquina.

        A frequência vinha só do protocolo do acelerador
        (``constantes.MAQUINAS``), e três dos cinco são semanais: a mama
        *fast-forward* (26 Gy em 5 frações) saía da carga com imagem semanal.
        Ver ``constantes.DOSE_IMAGEM_DIARIA_CGY`` para o porquê do corte.

        "Personalizado" não é tocado: ali alguém marcou os dias na mão, e
        sobrescrever uma escolha explícita é pior do que não aplicar a regra —
        os dias escolhidos sumiriam sem aviso.
        """
        if self.proto_freq.currentText() == constantes.IMAGEM_PERSONALIZADO:
            return
        if constantes.imagem_diaria_por_dose(self.rx_dose_fracao.value() * 100):
            self.proto_freq.setCurrentText(constantes.IMAGEM_DIARIA)

    def _sincronizar_dose_total(self, *_) -> None:
        """Recalcula a Dose total = dose/fração × nº frações, enquanto o total
        não tiver sido digitado à mão (``_total_auto``). O bloqueio de sinais
        evita que este ``setValue`` seja lido como edição do usuário."""
        if not self._total_auto:
            return
        df, nf = self.rx_dose_fracao.value(), self.rx_fracoes.value()
        if df <= 0 or nf <= 0:
            return
        self.rx_dose_total.blockSignals(True)
        self.rx_dose_total.setValue(round(df * nf, 2))
        self.rx_dose_total.blockSignals(False)

    def _on_dose_total_editada(self, _v) -> None:
        """Só dispara em edição do usuário (os ``setValue`` programáticos usam
        ``blockSignals``): a partir daí o total é manual e não é mais recalculado
        sozinho — respeita uma dose total digitada divergente do produto."""
        self._total_auto = False

    def _total_bate_produto(self) -> bool:
        """True se a Dose total atual condiz com dose/fração × nº frações (ou está
        vazia) — usado ao carregar para decidir se o total continua automático."""
        df, nf = self.rx_dose_fracao.value(), self.rx_fracoes.value()
        if self.rx_dose_total.value() == 0:
            return True
        return df > 0 and nf > 0 and abs(self.rx_dose_total.value() - df * nf) < 0.02

    def _verificar_dose_fracao(self, valor: float) -> None:
        """Dose/fração alta → confirma o fracionamento DESTE plano (edição avulsa).

        É o gatilho interativo, quando o usuário mexe na dose/fração de uma aba.
        Ao carregar uma pasta, o fracionamento de todos os planos altos é pedido
        de uma vez em ``PainelFormulario.perguntar_doses_altas``.
        """
        if valor <= _DOSE_FRAC_ALTA or self._frac_prescrito:
            return
        atual = self.rx_fracionamento.currentText()
        nfr = self.rx_fracoes.value()
        dlg = QDialog(self)
        dlg.setWindowTitle("Dose alta por fração"
                           + (f" — {self._rotulo}" if self._rotulo else ""))
        dlg.setMinimumWidth(360)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16); lay.setSpacing(12)
        if self._rotulo:
            cab = QLabel(f"<b>{self._rotulo}</b>")
            cab.setAlignment(Qt.AlignCenter)
            estilo.pintar(cab, lambda: f"color:{estilo.ACAO}; font-size:13px;")
            lay.addWidget(cab)
        frs = f" × {nfr} fr" if nfr else ""
        lbl = QLabel(f"Dose/fração: <b>{valor:.2f} Gy</b>{frs} (> 600 cGy)")
        lbl.setAlignment(Qt.AlignCenter)
        sub = QLabel("Confirme o fracionamento:"); sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl); lay.addWidget(sub)
        cmb = QComboBox(dlg); cmb.addItems(_OPCOES_FRAC); cmb.setEditable(True)
        cmb.setCurrentText(_frac_inicial(nfr, atual))
        lay.addWidget(cmb); lay.addSpacing(4)
        btns = QHBoxLayout(); btns.setSpacing(8)
        btn_ok = QPushButton("Ok"); btn_ok.setDefault(True); btn_ok.setFixedWidth(90)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.setFixedWidth(90)
        btn_ok.clicked.connect(dlg.accept); btn_cancel.clicked.connect(dlg.reject)
        btns.addStretch(); btns.addWidget(btn_ok); btns.addWidget(btn_cancel); btns.addStretch()
        lay.addLayout(btns)
        if dlg.exec() == QDialog.Accepted and cmb.currentText():
            self.rx_fracionamento.setCurrentText(cmb.currentText())

    def _toggle_gating(self, texto: str):
        vis = texto == "Sim"
        self._lbl_gating_modal.setVisible(vis)
        self.rx_gating_modal.setVisible(vis)
        if not vis:
            self._lbl_gating_fase.hide(); self._w_fase_janela.hide()
        else:
            self._toggle_gating_fase(self.rx_gating_modal.currentText())

    def _toggle_gating_fase(self, texto: str):
        vis = texto == "Fase"
        self._lbl_gating_fase.setVisible(vis)
        self._w_fase_janela.setVisible(vis)

    def _on_freq_activated(self) -> None:
        """Escolha de Frequência pelo usuário: 'Personalizado' abre o editor de
        dias de imagem; as demais são guardadas para reverter se preciso."""
        txt = self.proto_freq.currentText()
        if txt != "Personalizado":
            self._freq_anterior = txt
            return
        nfr = self.rx_fracoes.value()
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
            # Cancelou sem nunca ter escolhido dias → volta à frequência anterior.
            self._reverter_freq()

    def _reverter_freq(self) -> None:
        self.proto_freq.blockSignals(True)
        if self._freq_anterior:
            self.proto_freq.setCurrentText(self._freq_anterior)
        else:
            self.proto_freq.setCurrentIndex(-1)
        self.proto_freq.blockSignals(False)

    def modalidade_gating(self) -> str:
        """Modalidade de gating atual (vazio se o gating não estiver ligado)."""
        return (self.rx_gating_modal.currentText()
                if self.rx_gating.currentText() == "Sim" else "")

    def aplicar_modalidade(self, modal: str, origem: "_AbaPlano | None" = None) -> None:
        """Liga o gating e define a modalidade (usado ao replicar de outro plano).
        Se for 'Fase', copia também a janela do plano de origem."""
        self.rx_gating.setCurrentText("Sim")
        self.rx_gating_modal.setCurrentText(modal)
        if modal == "Fase" and origem is not None:
            self.rx_fase_ini.setValue(origem.rx_fase_ini.value())
            self.rx_fase_fim.setValue(origem.rx_fase_fim.value())

    # ── Dados ─────────────────────────────────────────────────────────────────
    def coletar(self) -> dict:
        """Campos por plano (chaves iguais às que a geração/JSON já esperam)."""
        gating = self.rx_gating.currentText()
        modal = self.rx_gating_modal.currentText() if gating == "Sim" else ""
        fase = (f"{self.rx_fase_ini.value()}-{self.rx_fase_fim.value()}"
                if gating == "Sim" and modal == "Fase" else "")
        return {
            "rx_dose_total": self.rx_dose_total.value() or None,
            "rx_dose_fracao": self.rx_dose_fracao.value() or None,
            "rx_fracoes": self.rx_fracoes.value() or None,
            "fracionamento": self.rx_fracionamento.currentText(),
            "proto_imagem": self.proto_imagem.currentText(),
            "proto_frequencia": self.proto_freq.currentText(),
            "proto_imagem_dias": (sorted(self._imagem_dias)
                                  if self.proto_freq.currentText() == "Personalizado"
                                  else []),
            "gating": gating,
            "gating_modalidade": modal,
            "gating_fase": fase,
        }

    def aplicar(self, d: dict) -> None:
        # Decide JÁ, pelos dados salvos, se o total é automático (condiz com
        # dose/fração × frações, ou está vazio) ou foi editado à mão — ANTES de
        # setar as frações, que dispara o recálculo do total.
        _dt, _df, _nf = (d.get("rx_dose_total"), d.get("rx_dose_fracao"),
                         d.get("rx_fracoes"))
        self._total_auto = (not _dt) or bool(
            _df and _nf and abs(float(_dt) - float(_df) * int(_nf)) < 0.02)
        for chave, sb in (("rx_dose_total", self.rx_dose_total),
                          ("rx_dose_fracao", self.rx_dose_fracao)):
            if d.get(chave) is not None:
                sb.blockSignals(True); sb.setValue(float(d[chave])); sb.blockSignals(False)
        if d.get("rx_fracoes") is not None:
            self.rx_fracoes.setValue(int(d["rx_fracoes"]))
        # Só sobrescreve o fracionamento se veio salvo; vazio → mantém o
        # auto-preenchido (ex.: "Única" p/ 1 fração, "1x dia" p/ >10).
        _frac = str(d.get("fracionamento", "") or "").strip()
        if _frac:
            self.rx_fracionamento.setCurrentText(_frac)
        self.proto_imagem.setCurrentText(str(d.get("proto_imagem", "") or ""))
        _freq = str(d.get("proto_frequencia", "") or "")
        self.proto_freq.setCurrentText(_freq)
        self._imagem_dias = [int(x) for x in (d.get("proto_imagem_dias") or [])]
        if _freq != "Personalizado":
            self._freq_anterior = _freq
        self.rx_gating.setCurrentText(str(d.get("gating", "Não") or "Não"))
        if d.get("gating") == "Sim" and d.get("gating_modalidade"):
            self.rx_gating_modal.setCurrentText(str(d["gating_modalidade"]))
            _fase = str(d.get("gating_fase", "") or "")
            if "-" in _fase:
                try:
                    a, b = _fase.split("-", 1)
                    self.rx_fase_ini.setValue(int(a)); self.rx_fase_fim.setValue(int(b))
                except ValueError:
                    pass

    def preencher_de_rp(self, rp: dict) -> None:
        """Preenche prescrição e protocolo a partir do RP parseado do plano.

        Ao carregar, a dose/fração é aplicada por último e SEM bloquear o sinal,
        para que cada plano com dose/fração > 6 Gy pergunte o fracionamento
        (``_verificar_dose_fracao``).
        """
        if rp.get("dose_total"):
            # Bloqueia o sinal para não marcar o total como "editado à mão" — a
            # dose do DICOM é a fonte da verdade, e continua automática.
            self.rx_dose_total.blockSignals(True)
            self.rx_dose_total.setValue(float(rp["dose_total"]))
            self.rx_dose_total.blockSignals(False)
        if rp.get("num_fracoes"):
            self.rx_fracoes.setValue(int(rp["num_fracoes"]))
        if rp.get("dose_fracao"):
            self.rx_dose_fracao.setValue(float(rp["dose_fracao"]))
        # Total automático se condiz com dose/fração × frações (DICOM consistente).
        self._total_auto = self._total_bate_produto()
        _maq = constantes.identificar_maquina(rp.get("maquina"))
        if _maq is not None:
            self.proto_imagem.setCurrentText(_maq.imagem)
            self.proto_freq.setCurrentText(_maq.frequencia)
        # Depois da máquina: a dose por fração manda sobre o protocolo dela.
        self._aplicar_imagem_por_dose()
        # Gating lido do RT Plan: se o plano tem a tag, marca "Sim". A modalidade
        # e a janela vêm de dicom_rt.enriquecer_gating (Breath-Hold do próprio
        # plano; Fase + janela deduzidas da série 4DCT). Quando não dá para
        # deduzir (ex.: amplitude), a modalidade fica em branco para o usuário
        # escolher (ver o aviso em ControleFicha.gerar_pdf quando fica pendente).
        if rp.get("gating_plano"):
            self.rx_gating.setCurrentText("Sim")
            _modal = str(rp.get("gating_modalidade", "") or "")
            if _modal:
                self.rx_gating_modal.setCurrentText(_modal)
                _fase = str(rp.get("gating_fase", "") or "")
                if "-" in _fase:
                    try:
                        a, b = _fase.split("-", 1)
                        self.rx_fase_ini.setValue(int(a)); self.rx_fase_fim.setValue(int(b))
                    except ValueError:
                        pass
            else:
                self.rx_gating_modal.setCurrentIndex(-1)

    def carregar_plano(self, plano: dict) -> None:
        """Preenche a aba (RP) SEM abrir o diálogo de dose alta.

        Quem decide perguntar é o chamador, via ``perguntar_dose_se_alta`` após
        as abas estarem montadas (evita modal aninhado durante a construção).
        """
        self.rx_dose_fracao.blockSignals(True)
        self.preencher_de_rp(plano.get("rp") or {})
        self.rx_dose_fracao.blockSignals(False)

    def perguntar_dose_se_alta(self) -> None:
        """Se dose/fração > 6 Gy, abre o diálogo de fracionamento deste plano."""
        self._verificar_dose_fracao(self.rx_dose_fracao.value())

    def limpar(self) -> None:
        self._total_auto = True   # volta a seguir dose/fração × nº frações
        for sb in (self.rx_dose_total, self.rx_dose_fracao):
            sb.blockSignals(True); sb.setValue(0.0); sb.blockSignals(False)
        self.rx_fracoes.setValue(0)
        self.rx_fracionamento.setCurrentIndex(-1)
        self.rx_gating.setCurrentIndex(0)
        self.proto_imagem.setCurrentIndex(-1)
        self.proto_freq.setCurrentIndex(-1)
        self._imagem_dias = []
        self._freq_anterior = ""


class DialogImagemDias(ui.Dialogo):
    """Grade de frações (calendário) para marcar em quais dias há imagem.

    Usado quando a Frequência do protocolo é 'Personalizado'. Cada fração 1..N
    é um botão que liga/desliga a imagem; ``dias()`` devolve as frações ligadas
    (1-based). A última fração aparece rotulada como 'Final Tto.' (a página 3
    sempre imprime imagem nela, independentemente da marcação)."""

    _POR_LINHA = 10

    def __init__(self, num_fracoes: int, dias: list | None = None, parent=None):
        super().__init__("Dias de imagem", parent, 560, 420)
        self._n = int(num_fracoes or 0)
        root = self.corpo

        tit = QLabel(f"Marque as frações em que será feita imagem — {self._n} frações.")
        tit.setWordWrap(True)
        estilo.pintar(tit, lambda: (
            f"font-weight:bold; font-size:13px; color:{estilo.ACAO};"))
        root.addWidget(tit)

        atalhos = QHBoxLayout()
        for txt, fn in (("Diária", self._preset_diaria),
                        ("Semanal", self._preset_semanal),
                        ("Limpar", self._preset_limpar)):
            b = QPushButton(txt); b.setCursor(Qt.PointingHandCursor)
            estilo.pintar(b, estilo.btn_contorno)
            b.clicked.connect(fn)
            atalhos.addWidget(b)
        atalhos.addStretch()
        root.addLayout(atalhos)

        area = QScrollArea(); area.setWidgetResizable(True)
        cont = QWidget(); grade = QGridLayout(cont)
        grade.setSpacing(4)
        marcados = {int(x) for x in (dias or [])}
        self._botoes: list[QPushButton] = []
        for i in range(1, self._n + 1):
            rotulo = "Final\nTto." if i == self._n else str(i)
            b = QPushButton(rotulo); b.setCheckable(True)
            b.setChecked(i in marcados)
            b.setFixedSize(48, 40); b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(self._estilo_dia())
            grade.addWidget(b, (i - 1) // self._POR_LINHA, (i - 1) % self._POR_LINHA)
            self._botoes.append(b)
        area.setWidget(cont)
        root.addWidget(area, 1)
        self.rodape("Aplicar")

    @staticmethod
    def _estilo_dia() -> str:
        return (f"QPushButton{{background:transparent; color:{estilo.TEXTO_FRACO};"
            f" border:1px solid {estilo.BORDA};"
                "border-radius:4px; font-weight:bold;}"
                f"QPushButton:checked{{background:{estilo.ACAO};"
            f" color:{estilo.SOBRE_ACAO}; border:1px solid {estilo.ACAO};}}")

    def _preset_diaria(self):
        for b in self._botoes:
            b.setChecked(True)

    def _preset_semanal(self):
        # Frações 1 e 2 sempre; depois a 1ª de cada semana (a cada 5): 1,2,6,11,…
        for idx, b in enumerate(self._botoes):
            b.setChecked(idx in (0, 1) or (idx >= 5 and (idx - 5) % 5 == 0))

    def _preset_limpar(self):
        for b in self._botoes:
            b.setChecked(False)

    def dias(self) -> list:
        """Frações marcadas (1-based), em ordem."""
        return [i + 1 for i, b in enumerate(self._botoes) if b.isChecked()]


class DialogGerenciarNomes(ui.Dialogo):
    """Adicionar/remover nomes de uma lista (Médicos ou Físicos)."""

    def __init__(self, titulo: str, itens: list, parent=None):
        super().__init__(f"Gerenciar {titulo}", parent, 380, 400)
        lay = self.corpo

        self.lst = QListWidget()
        self.lst.addItems(itens)
        lay.addWidget(self.lst, 1)

        linha = QHBoxLayout(); linha.setSpacing(6)
        self.ed = QLineEdit()
        b_add = QPushButton("＋ Adicionar")
        estilo.pintar(b_add, estilo.btn_contorno)
        b_add.setCursor(Qt.PointingHandCursor)
        # O Enter do CAMPO adiciona; o Enter da JANELA salva.
        #
        # ``setAutoDefault(False)`` aqui não bastava: quem recebe o Enter do
        # campo é o botão DEFAULT do diálogo — o "Salvar" do rodapé —, então
        # digitar um nome e apertar Enter acrescentava e FECHAVA a janela na
        # mesma tecla. Quem cadastra três médicos seguidos perdia a janela no
        # primeiro. O filtro abaixo consome o Enter enquanto o foco está no
        # campo; fora dele, o Salvar continua respondendo.
        b_add.setAutoDefault(False)
        self.ed.installEventFilter(self)
        linha.addWidget(self.ed, 1); linha.addWidget(b_add)
        lay.addLayout(linha)

        b_rem = QPushButton("🗑  Remover selecionado")
        estilo.pintar(b_rem, estilo.btn_perigo)
        b_rem.setCursor(Qt.PointingHandCursor)
        b_rem.setAutoDefault(False)
        lay.addWidget(b_rem)

        b_add.clicked.connect(self._adicionar)
        b_rem.clicked.connect(self._remover)
        self.lst.itemDoubleClicked.connect(lambda _i: self._remover())
        self.rodape("Salvar")

    def eventFilter(self, obj, ev):  # noqa: N802 — assinatura do Qt
        """Enter no campo de nome ADICIONA, e para aí.

        ``returnPressed`` sozinho não resolvia: ele é emitido, mas a tecla
        segue para o botão default do diálogo, que aceita e fecha a janela.
        """
        if (obj is self.ed and ev.type() == QEvent.KeyPress
                and ev.key() in (Qt.Key_Return, Qt.Key_Enter)):
            self._adicionar()
            return True
        return super().eventFilter(obj, ev)

    def _existe(self, nome: str) -> bool:
        return any(self.lst.item(i).text() == nome for i in range(self.lst.count()))

    def _adicionar(self) -> None:
        nome = self.ed.text().strip()
        if nome and not self._existe(nome):
            self.lst.addItem(nome)
        self.ed.clear(); self.ed.setFocus()

    def _remover(self) -> None:
        for item in self.lst.selectedItems():
            self.lst.takeItem(self.lst.row(item))

    def resultado(self) -> list:
        return [self.lst.item(i).text() for i in range(self.lst.count())]


class PainelFormulario(QWidget):
    """Paciente/Equipe (globais) no topo + abas de plano (até 5)."""

    fracoes_mudou = Signal()   # nº de frações de alguma aba mudou
    planos_reordenados = Signal(int, int)  # (de, para): usuário arrastou uma aba

    def __init__(self, parent=None):
        super().__init__(parent)
        # Texto da caixa "Observações gerais do tratamento" (pág. 2). É do CASO,
        # não do plano: a caixa é uma só na ficha, então editar em qualquer aba
        # vale para a ficha inteira. Sem widget aqui — vem de Edição da Ficha.
        self._observacoes = ""
        # Duas colunas: à esquerda Paciente + Equipe (empilhados); à direita o
        # Plano de Tratamento (abas). Topo mais baixo → mais altura p/ os cortes.
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(10, 10, 10, 8)
        raiz.setSpacing(10)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        # ── Painel único: Paciente + Equipe (2 seções com divisor) ───────
        def _form_compacto() -> QFormLayout:
            f = QFormLayout()
            f.setRowWrapPolicy(QFormLayout.DontWrapRows)
            f.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            f.setVerticalSpacing(4); f.setHorizontalSpacing(8)
            return f

        g_pac = QGroupBox("Dados do paciente")
        v_pac = QVBoxLayout(g_pac)
        v_pac.setContentsMargins(8, 4, 8, 6); v_pac.setSpacing(4)

        # Paciente e Equipe num ÚNICO QFormLayout: dois forms separados teriam
        # cada um a sua coluna de rótulos, dimensionada pelo próprio rótulo mais
        # longo — "Nascimento" contra "Médico" — e os campos de um grupo não
        # alinhariam com os do outro. O divisor e o título da seção entram como
        # linhas que ocupam as duas colunas.
        # Campos SEM texto de dica: cada um já tem o rótulo do lado, e a dica
        # dentro da caixa repetia o que ele diz ("Nome" / "Nome completo",
        # "Médico" / "Nome do médico"). Repetido, o cinza não informa — só faz a
        # caixa vazia parecer preenchida de longe, que é o oposto do que um
        # formulário de conferência precisa mostrar.
        l_pac = _form_compacto()
        self.pac_nome = QLineEdit()
        # O nome sai do campo na grafia do app, venha de onde vier: DICOM antigo,
        # ficha reaberta ou digitação à mão. Ao SAIR do campo, não a cada tecla —
        # reformatar enquanto se digita move o cursor e briga com quem escreve.
        self.pac_nome.editingFinished.connect(
            lambda: self.pac_nome.setText(
                capa_dados.como_nome_proprio(self.pac_nome.text().strip())))
        self.pac_registro = QLineEdit(); self.pac_registro.setFixedWidth(130)
        self.pac_nascimento = QLineEdit(); self.pac_nascimento.setFixedWidth(130)
        for _t, _w in (("Nome", self.pac_nome), ("Registro", self.pac_registro),
                       ("Nascimento", self.pac_nascimento)):
            l_pac.addRow(QLabel(_t), _w)

        _div = QFrame(); _div.setFrameShape(QFrame.HLine)
        estilo.pintar(_div, lambda: f"background:{estilo.BORDA};"
                      " max-height:1px; margin:3px 0;")
        _lbl_eq_sec = QLabel("Equipe responsável")
        estilo.pintar(_lbl_eq_sec,
                      lambda: f"color:{estilo.ACAO}; font-weight:bold;")
        l_pac.addRow(_div)
        l_pac.addRow(_lbl_eq_sec)

        # Equipe: SÓ SELEÇÃO. A lista de médicos/físicos é gerida apenas por admin
        # em Configurações -> Equipe. Os combos ficam editáveis apenas para EXIBIR
        # nomes vindos do DICOM/registro que não estejam na lista — digitar aqui
        # NÃO grava na lista compartilhada (sem botão gerenciar, sem auto-salvar).
        # Máquina que filtra os combos de equipe; definida ao carregar o plano.
        self._maquina_equipe: str | None = None
        self.eq_medico = QComboBox(); self.eq_medico.setEditable(True)
        self.eq_medico.setInsertPolicy(QComboBox.NoInsert)
        self.eq_medico.addItems(_carregar_medicos()[0])
        self.eq_medico.setCurrentIndex(-1)
        self.eq_fisico = QComboBox(); self.eq_fisico.setEditable(True)
        self.eq_fisico.setInsertPolicy(QComboBox.NoInsert)
        self.eq_fisico.addItems(_carregar_fisicos()[0])
        self.eq_fisico.setCurrentIndex(-1)
        l_pac.addRow(QLabel("Médico"), self.eq_medico)
        l_pac.addRow(QLabel("Físico"), self.eq_fisico)
        v_pac.addLayout(l_pac)

        # Altura mínima = conteúdo (nunca corta uma linha). Sem teto de largura
        # nos combos: eles crescem para preencher o painel largo.
        g_pac.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        g_pac.setMinimumHeight(g_pac.sizeHint().height())
        self.pac_nome.setMinimumWidth(200)

        # Coluna esquerda: o painel Paciente+Equipe ocupa METADE da largura do
        # topo (o Plano de Tratamento fica na outra metade).
        col_esq = QWidget()
        lay_esq = QVBoxLayout(col_esq)
        lay_esq.setContentsMargins(0, 0, 0, 0); lay_esq.setSpacing(6)
        lay_esq.addWidget(g_pac)
        lay_esq.addStretch(1)
        col_esq.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        raiz.addWidget(col_esq, 1)

        # ── Abas por plano ───────────────────────────────
        # ``ui.abas`` e não ``QTabWidget``: é a mesma barra de abas do
        # Posicionamento e da Administração. Aqui ela nasceu crua e ficou —
        # duas barras de aba diferentes na mesma janela, e quem olha não
        # distingue "outra tela" de "outro programa".
        #
        # O ``setDocumentMode(True)`` saiu junto: ele é a aba CHAPADA do
        # sistema, e a folha do ``ui`` desenha a borda, o raio e a barra azul
        # do topo. Os dois ligados brigam — o modo documento tira justamente a
        # moldura que diz qual aba está aberta.
        self.abas = ui.abas()
        self.abas.setMovable(True)   # arrastar abas reordena planos/cortes/alta/PDF
        self.abas.tabBar().tabMoved.connect(self._on_aba_movida)
        # Botão Agendamento vive na TRILHA lateral (JanelaPrincipal o posiciona,
        # abaixo de Limpar); criado aqui para definir_multiplano controlar sua
        # visibilidade. O seletor Soma/Individual foi movido para dentro do
        # diálogo de Agendamento. Sempre visível; começa DESABILITADO (só é
        # habilitado com ≥2 planos).
        self.btn_agendamento = QPushButton("🗓  Agendamento")
        self.btn_agendamento.setEnabled(False)
        self._mesma_tc = False
        raiz.addWidget(self.abas, 1)   # coluna direita ocupa o restante
        self.montar_abas([])          # começa com uma aba vazia (entrada manual)

        # A política Minimum + altura mínima (= conteúdo da coluna) evita que a
        # janela esprema o formulário e corte os títulos dos grupos.
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.setMinimumHeight(self.sizeHint().height())

    def definir_multiplano(self, is_multi: bool, mesma_tc: bool,
                           tem_plano: bool | None = None) -> None:
        """Estado do botão Agendamento (trilha lateral). Ele fica sempre visível;
        o seletor Soma/Individual vive no diálogo, e guarda-se ``mesma_tc``. O
        botão habilita com QUALQUER plano carregado (``tem_plano``) — dá acesso ao
        Replanejamento também no plano único; sem esse dado, cai no ≥2 planos."""
        self._mesma_tc = bool(mesma_tc)
        self.btn_agendamento.setEnabled(is_multi if tem_plano is None
                                        else bool(tem_plano))

    # ── Abas ──────────────────────────────────────────────────────────────────
    def montar_abas(self, planos: list) -> None:
        """(Re)cria as abas a partir da lista de planos (ou 1 aba vazia).

        Monta em silêncio; o diálogo de dose alta é disparado depois, por
        ``perguntar_doses_altas`` (evita modal aninhado durante a construção).
        """
        self.abas.blockSignals(True)
        while self.abas.count():
            w = self.abas.widget(0)
            self.abas.removeTab(0)
            w.deleteLater()
        if not planos:
            aba = _AbaPlano()
            aba._rotulo_base = "Plano de Tratamento"
            aba.rx_fracoes.valueChanged.connect(self.fracoes_mudou)
            aba.rx_gating_modal.activated.connect(
                lambda _i, ab=aba: self._propagar_modalidade(ab))
            self.abas.addTab(aba, "Plano de Tratamento")
        else:
            n = len(planos)
            for i, p in enumerate(planos, start=1):
                aba = _AbaPlano()
                aba.rx_fracoes.valueChanged.connect(self.fracoes_mudou)
                aba.rx_gating_modal.activated.connect(
                    lambda _i, ab=aba: self._propagar_modalidade(ab))
                rot = (p.get("rotulo") or f"Plano {i}").strip()
                aba._rotulo_base = rot
                aba._rotulo = f"Plano {i}/{n}: {rot}" if n > 1 else rot
                aba.carregar_plano(p)
                self.abas.addTab(aba, f"{i}. {rot[:18]}")
        self.abas.setCurrentIndex(0)
        self.abas.blockSignals(False)

    def _on_aba_movida(self, de: int, para: int) -> None:
        """Usuário arrastou uma aba: avisa a janela para reordenar o estado por
        índice (planos/dose/RS/RD) na MESMA ordem e renumera os rótulos. Sem isto
        a aba mudaria de lugar mas o PDF pareava a dose de um plano com o
        formulário de outro."""
        self._renumerar_abas()
        self.planos_reordenados.emit(de, para)

    def _renumerar_abas(self) -> None:
        """Reaplica os rótulos "i. rótulo" e "Plano i/n" na ordem atual das abas."""
        n = self.abas.count()
        for i in range(n):
            aba = self.abas.widget(i)
            if aba is None:
                continue
            rot = (getattr(aba, "_rotulo_base", "") or f"Plano {i+1}").strip()
            aba._rotulo = f"Plano {i+1}/{n}: {rot}" if n > 1 else rot
            self.abas.setTabText(i, f"{i+1}. {rot[:18]}")

    def _propagar_modalidade(self, origem) -> None:
        """Usuário escolheu a modalidade de gating num plano: se OUTRO plano
        também tem gating e ainda sem modalidade, pergunta se é a mesma e, em
        caso afirmativo, replica (inclusive a janela, se for 'Fase')."""
        modal = origem.modalidade_gating()
        if not modal:
            return
        for i in range(self.abas.count()):
            outra = self.abas.widget(i)
            if outra is None or outra is origem:
                continue
            # Só planos que também têm gating ligado e ainda SEM modalidade
            # definida (não sobrescreve escolha/auto-preenchimento existente).
            if outra.rx_gating.currentText() != "Sim":
                continue
            if outra.rx_gating_modal.currentText().strip():
                continue
            rot = (getattr(outra, "_rotulo", "") or self.abas.tabText(i)).strip()
            if ui.confirmar(
                    self, "Mesma modalidade de gating?",
                    f"O {rot} também tem gating.",
                    acao=f"Sim, também é {modal}",
                    recusa="Não, deixar em branco",
                    detalhe=(f"A modalidade é a mesma ({modal})? Deixar em "
                             "branco é o correto quando não se sabe — campo "
                             "sem fonte nasce vazio.")):
                outra.aplicar_modalidade(modal, origem)

    def aplicar_fracionamento_prescrito(self, registro: str,
                                        curso: str = "") -> str:
        """Preenche o Fracionamento de todas as abas com o da prescrição.

        O ritmo do tratamento é prescrito e assinado no ARIA; digitá-lo de novo
        em cada ficha é uma chance por ficha de divergir do que o
        radioterapeuta aprovou. Devolve a frequência aplicada (para a tela
        dizer de onde veio), ou ``""`` quando não deu — e aí o pop-up de
        sempre pergunta.

        Não se pergunta por prescrição ausente: com UMA aprovada ela é a do
        tratamento, e é só com duas ou mais sem casar com o curso que a escolha
        volta para a pessoa (ver ``tratamento_db.fracionamento_prescrito``).
        Aba com fracionamento já digitado é respeitada: a prescrição preenche o
        que está vazio, não corrige o que alguém escreveu.
        """
        if not str(registro or "").strip():
            return ""
        try:
            achado = tratamento_db.fracionamento_prescrito(registro, curso)
        except Exception:  # noqa: BLE001 — a ficha vive sem a prescrição
            _LOG.exception("Não consegui ler o fracionamento prescrito")
            return ""
        frac = achado.get("fracionamento") or ""
        if not frac:
            return ""
        for i in range(self.abas.count()):
            aba = self.abas.widget(i)
            if aba is None or aba.rx_fracionamento.currentText().strip():
                continue
            aba.rx_fracionamento.setCurrentText(frac)
            aba._frac_prescrito = True
        return achado.get("frequencia") or ""

    def perguntar_doses_altas(self) -> None:
        """Confirma, num popup ÚNICO, o fracionamento dos planos de dose alta.

        Ao carregar uma pasta, em vez de um modal por plano acima de
        ``_DOSE_FRAC_ALTA``, mostra uma linha por plano — rótulo, dose/fração e
        nº de frações — cada uma com o seu combo de fracionamento. Um Ok aplica
        todos; Cancelar mantém o auto-preenchido. Planos de dose normal não
        entram (nada a confirmar).
        """
        todas = [aba for i in range(self.abas.count())
                 if (aba := self.abas.widget(i)) is not None]
        # Fracionamento que veio da prescrição não se pergunta: ele já foi
        # aprovado por quem prescreveu, e reabrir a escolha convida a trocá-lo.
        altos = [aba for aba in todas
                 if aba.rx_dose_fracao.value() > _DOSE_FRAC_ALTA
                 and not aba._frac_prescrito]
        if not altos:
            return
        # Com mais de um plano no tratamento, lista TODOS (não só os de dose alta):
        # o "Dia de início" interliga os planos no agendamento, então o usuário
        # ajusta o fracionamento e o início de todos de uma vez. Com um plano só,
        # mostra apenas ele.
        linhas_aba = todas if len(todas) > 1 else altos

        dlg = QDialog(self)
        dlg.setWindowTitle("Fracionamento — dose alta por fração")
        dlg.setMinimumWidth(620)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 16); lay.setSpacing(12)
        _msg = ("Há plano com dose/fração > 600 cGy. Confirme o fracionamento e o "
                "dia de início de cada plano:" if len(linhas_aba) > len(altos)
                else "Confirme o fracionamento dos planos abaixo "
                     "(dose/fração > 600 cGy):")
        lay.addWidget(QLabel(_msg))

        grade = QGridLayout(); grade.setHorizontalSpacing(14); grade.setVerticalSpacing(8)
        # Cabeçalho das colunas Fracionamento / Dia de início.
        _hf = QLabel("Fracionamento"); _hd = QLabel("Dia de início")
        for _h in (_hf, _hd):
            estilo.pintar(_h, lambda: f"color:{estilo.TEXTO_FRACO}; font-size:11px;")
        grade.addWidget(_hf, 0, 2); grade.addWidget(_hd, 0, 3)
        combos: list[QComboBox] = []
        spins_dia: list[QSpinBox] = []
        for r, aba in enumerate(linhas_aba):
            linha = r + 1   # linha 0 é o cabeçalho
            rot = aba._rotulo or f"Plano {r + 1}"
            nfr = aba.rx_fracoes.value()
            frs = f" × {nfr} fr" if nfr else ""
            nome = QLabel(f"<b>{rot}</b>")
            estilo.pintar(nome, lambda: f"color:{estilo.ACAO};")
            dose = QLabel(f"{aba.rx_dose_fracao.value():.2f} Gy{frs}")
            eh_alto = aba.rx_dose_fracao.value() > _DOSE_FRAC_ALTA
            # Dose alta em âmbar, para o plano que disparou o aviso saltar aos olhos.
            if eh_alto:
                estilo.pintar(dose, lambda: f"color:{estilo.AMBAR}; font-weight:bold;")
            cmb = QComboBox(dlg); cmb.addItems(_OPCOES_FRAC); cmb.setEditable(True)
            cmb.setCurrentText(_frac_inicial(nfr, aba.rx_fracionamento.currentText(),
                                             dose_alta=eh_alto))
            # Dia de início do plano no agendamento (1 = começa no 1º dia).
            spin_dia = QSpinBox(dlg); spin_dia.setRange(1, 99)
            spin_dia.setValue(int(getattr(aba, "_dia_inicio", 1) or 1))
            spin_dia.setFixedWidth(64)
            spin_dia.setToolTip("Dia em que este plano começa. Ex.: Dia 2 faz o "
                                "plano iniciar um dia depois; o agendamento "
                                "interliga os planos conforme o fracionamento.")
            grade.addWidget(nome, linha, 0)
            grade.addWidget(dose, linha, 1)
            grade.addWidget(cmb,  linha, 2)
            grade.addWidget(spin_dia, linha, 3)
            combos.append(cmb); spins_dia.append(spin_dia)
        lay.addLayout(grade); lay.addSpacing(4)

        btns = QHBoxLayout(); btns.setSpacing(8)
        btn_ok = QPushButton("Ok"); btn_ok.setDefault(True); btn_ok.setFixedWidth(90)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.setFixedWidth(90)
        btn_ok.clicked.connect(dlg.accept); btn_cancel.clicked.connect(dlg.reject)
        btns.addStretch(); btns.addWidget(btn_ok); btns.addWidget(btn_cancel); btns.addStretch()
        lay.addLayout(btns)

        if dlg.exec() == QDialog.Accepted:
            for aba, cmb, spin_dia in zip(linhas_aba, combos, spins_dia):
                if cmb.currentText():
                    aba.rx_fracionamento.setCurrentText(cmb.currentText())
                aba._dia_inicio = spin_dia.value()

    def _aba(self) -> "_AbaPlano":
        return self.abas.currentWidget()

    # ── Dados ─────────────────────────────────────────────────────────────────
    def _globais(self) -> dict:
        return {
            # Última rede: o que vai para o PDF, o JSON e o log tem UMA grafia.
            # O campo já formata ao perder o foco, mas "gerar" pode ser clicado
            # com o cursor ainda dentro dele — e aí o texto cru passaria.
            "pac_nome": capa_dados.como_nome_proprio(self.pac_nome.text()),
            "pac_registro": self.pac_registro.text(),
            "pac_nascimento": self.pac_nascimento.text(),
            "maquina": "",
            "eq_medico": self.eq_medico.currentText(),
            "eq_fisico": self.eq_fisico.currentText(),
            # Repetido em todo plano: a ficha junta tem uma caixa só, e a ficha
            # separada leva a observação do caso para cada documento.
            "observacoes": self._observacoes,
        }

    def coletar(self) -> dict:
        """Dict achatado do plano ATIVO (globais + aba atual)."""
        d = self._globais()
        aba = self._aba()
        if aba is not None:
            d.update(aba.coletar())
        return d

    def coletar_planos(self) -> list:
        """Um dict achatado por plano (globais repetidos + cada aba)."""
        out = []
        for i in range(self.abas.count()):
            d = self._globais()
            d.update(self.abas.widget(i).coletar())
            out.append(d)
        return out

    def preencher(self, dados: dict) -> None:
        """Preenche apenas os globais (paciente/equipe). Abas via montar_abas."""
        pac: dict = {}
        for c in ("RP", "RS", "RD", "TC"):
            p = (dados.get(c) or {}).get("paciente")
            if p:
                pac = p
                break
        if pac.get("nome"):
            self.pac_nome.setText(pac["nome"])
        if pac.get("registro"):
            self.pac_registro.setText(pac["registro"])
        if pac.get("nascimento"):
            self.pac_nascimento.setText(pac["nascimento"])
        # Cursor no início: senão o texto rola e esconde o 1º caractere.
        for _w in (self.pac_nome, self.pac_registro, self.pac_nascimento):
            _w.setCursorPosition(0)
        rp = dados.get("RP") or {}
        # Já sabendo a máquina do plano, os combos passam a oferecer só a equipe
        # que atende nela (ver equipe.equipe_da_maquina). RP sem máquina vira
        # "" (equipe inteira), não None — None manteria o filtro do caso
        # ANTERIOR, e a ficha nova herdaria a unidade errada.
        self.recarregar_equipe(str(rp.get("maquina") or ""))
        # Exibe médico/físico vindos do RP mesmo fora da lista (combo editável);
        # NÃO grava na lista compartilhada (edição da equipe é só do admin).
        if rp.get("medico"):
            self.eq_medico.setCurrentText(str(rp["medico"]))
        if rp.get("fisico"):
            self.eq_fisico.setCurrentText(str(rp["fisico"]))

    def aplicar(self, d: dict) -> None:
        """Aplica edições (Edição Ficha) ou uma ficha reaberta ao global + aba ativa."""
        # Ficha reaberta traz o nome como ele foi gravado — as de antes de
        # 25/08/2026, em caixa alta. Regerar a partir dela sairia com a grafia
        # da época, ao lado de uma capa nova já canônica.
        self.pac_nome.setText(
            capa_dados.como_nome_proprio(str(d.get("pac_nome", "") or "")))
        self.pac_registro.setText(str(d.get("pac_registro", "") or ""))
        self.pac_nascimento.setText(str(d.get("pac_nascimento", "") or ""))
        for _w in (self.pac_nome, self.pac_registro, self.pac_nascimento):
            _w.setCursorPosition(0)
        # O filtro dos combos acompanha a máquina do que está sendo aplicado:
        # reabrir uma ficha do SAT depois de um caso da Clinica deixava os combos
        # presos na equipe da Clinica (este caminho não passa por ``preencher``).
        # Sem a chave, mantém o filtro atual — quem chama não sabe a máquina.
        if "maquina" in d:
            self.recarregar_equipe(str(d.get("maquina") or ""))
        self.eq_medico.setCurrentText(str(d.get("eq_medico", "") or ""))
        self.eq_fisico.setCurrentText(str(d.get("eq_fisico", "") or ""))
        self._observacoes = str(d.get("observacoes", "") or "")
        aba = self._aba()
        if aba is not None:
            aba.aplicar(d)

    def limpar(self) -> None:
        self._observacoes = ""
        for w in (self.pac_nome, self.pac_registro, self.pac_nascimento):
            w.clear()
        self.eq_medico.lineEdit().clear()
        self.eq_fisico.lineEdit().clear()
        # Caso novo: volta a oferecer a equipe inteira até saber a máquina.
        self.recarregar_equipe("")
        self.montar_abas([])
        self.definir_multiplano(False, False)

    def recarregar_equipe(self, maquina: str | None = None):
        """Recarrega os combos de médico/físico dos arquivos (após editar em
        Configurações), preservando o que estiver selecionado/digitado.

        ``maquina``: oferece só quem atende naquele acelerador (ver
        ``equipe.equipe_da_maquina``). ``""`` = sem máquina conhecida, oferece
        a lista inteira; ``None`` = mantém o filtro atual (é o que Configurações
        usa ao recarregar os nomes sem trocar de caso). O combo é editável,
        então um nome fora da lista continua podendo ser digitado."""
        if maquina is None:
            maquina = self._maquina_equipe
        else:
            self._maquina_equipe = maquina
        for combo, carregar in ((self.eq_medico, _carregar_medicos),
                                (self.eq_fisico, _carregar_fisicos)):
            nomes, unidades = carregar()
            sel = combo.currentText().strip()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(equipe_da_maquina(nomes, maquina, unidades))
            combo.setCurrentText(sel)   # editável: mostra mesmo fora da lista
            combo.blockSignals(False)
