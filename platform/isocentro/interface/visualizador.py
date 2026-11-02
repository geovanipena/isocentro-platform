"""O painel que mostra os cortes e a faixa de isodose, e o sub-painel de corte.

Separado de ``gui.py`` em 27/08/2026. Junto vieram as constantes ``_ISO_*``:
elas descrevem a faixa de isodose e não eram usadas em nenhum outro lugar.

O nome do logger é ``__name__``, como no resto do programa — e
``visualizador`` está em ``LOGGERS_APP`` (``dados/log_app.py``), que é a lista de quem
chega ao histórico compartilhado. Sem estar lá, a falha da faixa de isodose
sumiria do histórico sem nenhum sinal; ``tests/test_loggers_app.py`` é o
guarda que não deixa isso acontecer de novo.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QSlider, QSpinBox,
    QStackedLayout, QVBoxLayout, QWidget)

from isocentro.desenho import corte
from isocentro.interface import estilo
from isocentro.papel import ficha_pdf

_LOG = logging.getLogger(__name__)


# Unidades da faixa de isodose. O % é o padrão (e o que a ficha grava); o cGy é
# para conferir dose absoluta na tela. O teto de 200% deixa a faixa alcançar o
# ponto quente — parando em 100% não dava para ver o que passa da prescrição.
_ISO_PCT, _ISO_CGY = "%", "cGy"
_ISO_PCT_MAX = 200
# Os campos mostram só o NÚMERO — a unidade fica no seletor ao lado, uma vez.
# Repetida em cada campo ela comia a largura e cortava o valor ("116%" saía
# "1169"). Largura só para os dígitos: 3 em %, 4 em cGy.
_ISO_LARG_PCT, _ISO_LARG_CGY = 58, 74

# ── Sub-painel de corte (imagem + slider) ────────────────────────────────────


class _PainelCorte(QWidget):
    angulos_alterados = Signal()

    def __init__(self, titulo: str, com_slider: bool = True,
                 com_controles_3d: bool = False, parent=None):
        super().__init__(parent)
        # Expanding → o QGridLayout distribui largura igual às duas colunas.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)

        self.lbl_titulo = QLabel(titulo)
        self.lbl_titulo.setAlignment(Qt.AlignCenter)
        estilo.pintar(self.lbl_titulo, lambda: (
            f"color:{estilo.ACAO}; font-size:10px; font-weight:bold;"
            f" background:{estilo.FUNDO_FUNDO}; border-radius:2px; padding:1px 0;"
        ))
        lay.addWidget(self.lbl_titulo)

        self.lbl_img = QLabel()
        self.lbl_img.setAlignment(Qt.AlignCenter)
        self.lbl_img.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Fundo PRETO: casa com o fundo preto da máscara do corte, então a faixa
        # (letterbox) ao redor da imagem não aparece cinza — visualização uniforme.
        estilo.pintar(self.lbl_img, lambda: (
            f"background:#000000; border:1px solid {estilo.BORDA};"
            " border-radius:3px;"))
        self.lbl_img.setMinimumSize(110, 90)
        lay.addWidget(self.lbl_img)

        if com_slider:
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setRange(0, 0)
            lay.addWidget(self.slider)
        else:
            self.slider = None

        if com_controles_3d:
            self._elev = 10
            self._azim = -30

            ctrl = QHBoxLayout()
            ctrl.setContentsMargins(0, 2, 0, 0)
            ctrl.setSpacing(2)

            _btn_style = "padding: 0 2px; min-width: 22px; max-width: 22px; min-height: 20px;"

            btn_az_m = QPushButton("◀")
            btn_az_p = QPushButton("▶")
            self._lbl_azim = QLabel(f"Az {self._azim:+d}°")
            self._lbl_azim.setFixedWidth(48)

            btn_el_p = QPushButton("▲")
            btn_el_m = QPushButton("▼")
            self._lbl_elev = QLabel(f"El {self._elev:+d}°")
            self._lbl_elev.setFixedWidth(48)

            for b in (btn_az_m, btn_az_p, btn_el_p, btn_el_m):
                b.setStyleSheet(_btn_style)

            def _az(d):
                self._azim = (self._azim + d + 180) % 360 - 180
                self._lbl_azim.setText(f"Az {self._azim:+d}°")
                self.angulos_alterados.emit()

            def _el(d):
                self._elev = max(-90, min(90, self._elev + d))
                self._lbl_elev.setText(f"El {self._elev:+d}°")
                self.angulos_alterados.emit()

            btn_az_m.clicked.connect(lambda: _az(-30))
            btn_az_p.clicked.connect(lambda: _az(+30))
            btn_el_p.clicked.connect(lambda: _el(+30))
            btn_el_m.clicked.connect(lambda: _el(-30))

            ctrl.addWidget(btn_az_m)
            ctrl.addWidget(btn_az_p)
            ctrl.addWidget(self._lbl_azim)
            ctrl.addStretch()
            ctrl.addWidget(self._lbl_elev)
            ctrl.addWidget(btn_el_p)
            ctrl.addWidget(btn_el_m)
            lay.addLayout(ctrl)


# ── Painel de visualizador (direita) ─────────────────────────────────────────


class PainelVisualizador(QWidget):
    # Recado curto para a barra de status (a janela é quem tem a barra).
    aviso_isodose = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Controles globais — barra com fundo próprio
        ctrl_w = QWidget()
        estilo.pintar(ctrl_w, lambda: (
            f"background:{estilo.FUNDO_BLOCO}; border-radius:4px;"
        ))
        ctrl = QHBoxLayout(ctrl_w)
        ctrl.setContentsMargins(10, 5, 10, 5)
        ctrl.setSpacing(10)
        lbl_janela = QLabel("Janela:")
        estilo.pintar(lbl_janela, lambda: f"color:{estilo.TEXTO_FRACO};")
        ctrl.addWidget(lbl_janela)
        self.cmb_janela = QComboBox()
        self.cmb_janela.addItems(list(corte.JANELAS.keys()))
        self.cmb_janela.setCurrentText("Mama")
        self.cmb_janela.setFixedWidth(120)
        ctrl.addWidget(self.cmb_janela)
        ctrl.addWidget(QFrame())   # divisor visual leve
        self.chk_estruturas = QCheckBox("Contornos")
        self.chk_estruturas.setChecked(True)
        ctrl.addWidget(self.chk_estruturas)
        self.chk_isodose = QCheckBox("Isodoses")
        self.chk_isodose.setChecked(True)
        ctrl.addWidget(self.chk_isodose)
        lbl_dose = QLabel("Dose:")
        estilo.pintar(lbl_dose,
                      lambda: f"color:{estilo.TEXTO_FRACO}; margin-left:4px;")
        ctrl.addWidget(lbl_dose)
        # Faixa do colorwash. O renderizador SEMPRE recebe %, mas quem confere a
        # ficha às vezes quer ler em dose absoluta — daí o seletor de unidade
        # (ver ``faixa_isodose_pct`` e ``_trocar_unidade_iso``).
        self._iso_ref_cgy = 0.0    # quanto vale 100% (a prescrição), em cGy
        self._iso_max_cgy = 0.0    # ponto quente da grade, em cGy
        # Unidade em que os spins ESTÃO agora — não a escolhida no combo. São
        # duas coisas: a conversão acontece uma vez na troca, e sem esse registro
        # ela rodava de novo sobre valores já convertidos.
        self._iso_spins_em = _ISO_PCT
        self.spn_iso_min = QSpinBox()
        self.spn_iso_min.setRange(0, _ISO_PCT_MAX)
        self.spn_iso_min.setValue(50)
        self.spn_iso_min.setFixedWidth(_ISO_LARG_PCT)
        ctrl.addWidget(self.spn_iso_min)
        lbl_sep = QLabel("–")
        estilo.pintar(lbl_sep, lambda: f"color:{estilo.TEXTO_APAGADO};")
        ctrl.addWidget(lbl_sep)
        self.spn_iso_max = QSpinBox()
        self.spn_iso_max.setRange(0, _ISO_PCT_MAX)
        self.spn_iso_max.setValue(100)
        self.spn_iso_max.setFixedWidth(_ISO_LARG_PCT)
        ctrl.addWidget(self.spn_iso_max)
        self.cmb_iso_unid = QComboBox()
        self.cmb_iso_unid.addItems([_ISO_PCT, _ISO_CGY])
        self.cmb_iso_unid.setFixedWidth(66)
        self.cmb_iso_unid.setToolTip(
            "Unidade da faixa de isodose.\n"
            "%: da prescrição do plano (100% = dose prescrita).\n"
            "cGy: dose absoluta.\n"
            "Nas duas, a faixa abre em 50% e vai até a dose MÁXIMA do plano.")
        # Quem sabe a prescrição e o ponto quente é a janela: ela instala aqui um
        # callable que os devolve, e a conversão pergunta ANTES de converter (o
        # valor tem de estar fresco no instante da troca, não do último render).
        self.dose_iso_provider = None
        self.cmb_iso_unid.currentTextChanged.connect(self._trocar_unidade_iso)
        ctrl.addWidget(self.cmb_iso_unid)
        ctrl.addStretch()
        self.lbl_info = QLabel()
        estilo.pintar(self.lbl_info,
                      lambda: f"color:{estilo.TEXTO_APAGADO}; font-size:11px;")
        ctrl.addWidget(self.lbl_info)
        root.addWidget(ctrl_w)

        # Grade 2×2: Axial | Sagital / Coronal | 3D
        grade = QGridLayout()
        grade.setSpacing(6)
        self.painel_axial = _PainelCorte("AXIAL")
        self.painel_sagital = _PainelCorte("SAGITAL")
        self.painel_coronal = _PainelCorte("CORONAL")
        self.painel_3d = _PainelCorte("3D CORPO", com_slider=False, com_controles_3d=True)
        grade.addWidget(self.painel_axial, 0, 0)
        grade.addWidget(self.painel_sagital, 0, 1)
        grade.addWidget(self.painel_coronal, 1, 0)
        grade.addWidget(self.painel_3d, 1, 1)
        # Colunas/linhas iguais (mesma base + mesmo stretch) → os quatro painéis
        # têm o mesmo tamanho e preenchem o centro por igual.
        grade.setColumnMinimumWidth(0, 200); grade.setColumnMinimumWidth(1, 200)
        grade.setColumnStretch(0, 1); grade.setColumnStretch(1, 1)
        grade.setRowStretch(0, 1); grade.setRowStretch(1, 1)
        grade_w = QWidget()
        grade_w.setLayout(grade)
        grade_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Seleção de estruturas — coluna à esquerda da grade
        g_est = QGroupBox("Estruturas")
        lay_est = QVBoxLayout(g_est)
        lay_est.setContentsMargins(6, 4, 6, 4)
        lay_est.setSpacing(6)
        btn_col = QHBoxLayout()
        btn_col.setSpacing(4)
        self._btn_all = QPushButton("Todas")
        self._btn_none = QPushButton("Nenhuma")
        self._btn_all.setFixedHeight(22)
        self._btn_none.setFixedHeight(22)
        estilo.pintar(self._btn_all, lambda: (
            f"padding:0 8px; background:{estilo.ACAO}; color:{estilo.SOBRE_ACAO};"
            " border-radius:3px; font-size:11px;"
        ))
        estilo.pintar(self._btn_none, lambda: (
            f"padding:0 8px; background:transparent; color:{estilo.TEXTO_FRACO};"
            f" border:1px solid {estilo.BORDA}; border-radius:3px; font-size:11px;"
        ))
        btn_col.addWidget(self._btn_all)
        btn_col.addWidget(self._btn_none)
        btn_col.addStretch()
        self.lst_estruturas = QListWidget()
        self.lst_estruturas.setAlternatingRowColors(True)
        self.lst_estruturas.setStyleSheet("font-size: 11px;")
        lay_est.addLayout(btn_col)
        lay_est.addWidget(self.lst_estruturas, 1)
        g_est.setFixedWidth(230)
        g_est.setMinimumHeight(120)

        # Coluna de ações à DIREITA — mesma largura de Estruturas (simetria).
        # Margens simétricas → botões centralizados na coluna (não colados à borda).
        acoes_w = QWidget()
        acoes_w.setFixedWidth(230)
        self.lay_acoes = QVBoxLayout(acoes_w)
        self.lay_acoes.setContentsMargins(18, 10, 18, 10)
        self.lay_acoes.setSpacing(10)

        # Simetria: Estruturas (esq.) e trilha de botões (dir.) na mesma largura;
        # os cortes PREENCHEM todo o centro entre elas (sem folga lateral vazia).
        conteudo = QHBoxLayout()
        conteudo.setSpacing(6)
        # Centro: ou os quatro cortes, ou o convite de janela vazia. Sem ele, a
        # janela recém-aberta é só um retângulo cinza com quatro rótulos
        # apagados — lê como programa quebrado, não como programa esperando.
        self._centro = QStackedLayout()
        self._centro.addWidget(self._painel_vazio(self))   # 0: sem caso
        self._centro.addWidget(grade_w)                # 1: cortes
        centro_w = QWidget()
        centro_w.setLayout(self._centro)

        conteudo.addWidget(g_est)        # estruturas (esquerda)
        conteudo.addWidget(centro_w, 1)  # cortes preenchem o centro
        conteudo.addWidget(acoes_w)      # trilha de botões (direita)
        root.addLayout(conteudo, 1)

        # Tudo que só faz sentido com um caso carregado (ver habilitar_controles).
        # A trilha de botões fica de FORA: é por ela que se abre a pasta.
        self._so_com_caso = (ctrl_w, g_est, grade_w)

    @staticmethod
    def _painel_vazio(pai: QWidget) -> QWidget:
        """Convite mostrado enquanto não há caso: diz o que fazer, e as DUAS
        formas de fazer (o arrastar não é descoberto sozinho).

        Nasce **com pai**: sem ele, o widget é de topo até o ``addWidget``
        adotá-lo, e o ``QStackedWidget`` o exibe nesse intervalo — o que pisca
        uma janelinha solta na tela entre o login e a janela principal.
        """
        w = QWidget(pai)
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(10)
        icone = QLabel("📁")
        icone.setAlignment(Qt.AlignCenter)
        estilo.pintar(icone,
                      lambda: f"font-size:46px; color:{estilo.BORDA_FORTE};")
        titulo = QLabel("Abra a pasta do paciente")
        titulo.setAlignment(Qt.AlignCenter)
        # Tons claros o bastante para 4,5:1 sobre o fundo: 17px em negrito ainda
        # não é "texto grande" para a WCAG, e a dica de 12px muito menos.
        estilo.pintar(titulo, lambda: "font-size:17px; font-weight:bold;"
                      f" color:{estilo.TEXTO_FRACO};")
        dica = QLabel("ou arraste a pasta para esta janela")
        dica.setAlignment(Qt.AlignCenter)
        estilo.pintar(dica,
                      lambda: f"font-size:12px; color:{estilo.TEXTO_APAGADO};")
        for x in (icone, titulo, dica):
            lay.addWidget(x)
        return w

    def habilitar_controles(self, on: bool) -> None:
        """Liga/desliga janela, contornos, isodose, estruturas e os cortes, e
        troca os cortes pelo convite de janela vazia.

        Os botões de ação (Abrir pasta, Histórico…) NÃO entram: são a única
        saída de uma janela sem caso nenhum."""
        for w in self._so_com_caso:
            w.setEnabled(on)
        self._centro.setCurrentIndex(1 if on else 0)

    # ── Faixa de isodose: % (padrão) ou cGy ──────────────────────────────────
    def definir_dose_iso(self, ref_cgy: float, max_cgy: float) -> None:
        """Informa quanto valem 100% e o ponto quente, em cGy, no caso atual.

        Só a janela sabe disso (depende do plano ativo e do modo Soma). Ao
        conhecer uma dose nova, o TOPO da faixa vai para o ponto quente nas duas
        unidades: parar em 100% cortava justamente o que se quer olhar — o que
        passa da prescrição some do colorwash como se não existisse.

        O piso preserva o que SIGNIFICA (o mesmo % da nova prescrição), não o
        número: manter os cGy do plano anterior seria uma faixa que não quer
        dizer nada no plano em que se está."""
        ref_cgy, max_cgy = float(ref_cgy or 0), float(max_cgy or 0)
        if (ref_cgy, max_cgy) == (self._iso_ref_cgy, self._iso_max_cgy):
            return
        pct_lo = self.faixa_isodose_pct()[0]      # com a referência ANTIGA
        self._iso_ref_cgy, self._iso_max_cgy = ref_cgy, max_cgy
        if self._iso_spins_em == _ISO_CGY:
            self._aplicar_unidade_cgy(pct_lo)
        else:
            self._aplicar_topo_pct(pct_lo)

    def topo_pct(self) -> float:
        """Ponto quente em % da prescrição; 100 enquanto não se sabe a dose."""
        if self._iso_ref_cgy > 0 and self._iso_max_cgy > 0:
            return 100.0 * self._iso_max_cgy / self._iso_ref_cgy
        return 100.0

    def _aplicar_topo_pct(self, pct_lo: float) -> None:
        """Em %, leva o topo da faixa ao ponto quente (o piso segue onde estava)."""
        topo = self.topo_pct()
        teto = max(_ISO_PCT_MAX, int(topo) + 1)
        for spn in (self.spn_iso_min, self.spn_iso_max):
            spn.blockSignals(True)
            spn.setRange(0, teto)
            spn.blockSignals(False)
        self.spn_iso_min.setValue(int(round(pct_lo)))
        self.spn_iso_max.setValue(int(round(topo)))

    def em_cgy(self) -> bool:
        return self.cmb_iso_unid.currentText() == _ISO_CGY

    def faixa_isodose_pct(self) -> tuple:
        """Faixa escolhida, SEMPRE em % — é o que o colorwash e a ficha entendem.

        Sem prescrição conhecida não há como converter cGy: aí devolve a faixa
        padrão, em vez de recortar a isodose por um número sem sentido."""
        lo, hi = self.spn_iso_min.value(), self.spn_iso_max.value()
        if self._iso_spins_em == _ISO_PCT:
            return (float(lo), float(hi))
        if self._iso_ref_cgy <= 0:
            return (50.0, 100.0)
        k = 100.0 / self._iso_ref_cgy
        return (lo * k, hi * k)

    def definir_faixa_pct(self, lo: float, hi: float) -> None:
        """Repõe a faixa a partir de valores em % (estado salvo por plano)."""
        if self._iso_spins_em == _ISO_CGY and self._iso_ref_cgy > 0:
            k = self._iso_ref_cgy / 100.0
            lo, hi = lo * k, hi * k
        self.spn_iso_min.setValue(int(round(lo)))
        self.spn_iso_max.setValue(int(round(hi)))

    def _trocar_unidade_iso(self, unid: str) -> None:
        """Converte a faixa ao trocar a unidade, preservando o que ela significa.

        Indo para cGy, o topo passa a ser o PONTO QUENTE e não a conversão de
        100%: em dose absoluta o que se quer ver é até onde a dose chegou, que é
        justamente o que o % esconde ao parar na prescrição."""
        if unid == _ISO_CGY:
            if self.dose_iso_provider is not None:
                try:
                    self.definir_dose_iso(*self.dose_iso_provider())
                except Exception:  # noqa: BLE001 — sem dose legível, segue em %
                    _LOG.exception("Faixa de isodose: dose de referência ilegível")
            if self._iso_ref_cgy <= 0:
                # Sem prescrição não há dose absoluta: em vez de mostrar uma
                # faixa que não quer dizer nada, volta para % e avisa.
                self.cmb_iso_unid.blockSignals(True)
                self.cmb_iso_unid.setCurrentText(_ISO_PCT)
                self.cmb_iso_unid.blockSignals(False)
                self.aviso_isodose.emit(
                    "Sem prescrição carregada — a faixa de isodose segue em %.")
                return
            self._aplicar_unidade_cgy()
            return
        lo, hi = self.faixa_isodose_pct()
        self._iso_spins_em = _ISO_PCT
        for spn in (self.spn_iso_min, self.spn_iso_max):
            spn.blockSignals(True)
            spn.setSingleStep(1)
            spn.setRange(0, _ISO_PCT_MAX)
            spn.setFixedWidth(_ISO_LARG_PCT)
            spn.blockSignals(False)
        self.spn_iso_min.setValue(int(round(lo)))
        self.spn_iso_max.setValue(int(round(hi)))

    def _aplicar_unidade_cgy(self, pct_lo: float | None = None) -> None:
        """Põe os spins em cGy: piso na dose do % atual, topo no ponto quente.

        ``pct_lo``: o piso a preservar, em % — usado quando a referência mudou
        (troca de plano) e os spins já estão em cGy da prescrição ANTIGA."""
        ref, topo = self._iso_ref_cgy, self._iso_max_cgy
        if pct_lo is None:
            pct_lo = self.faixa_isodose_pct()[0]
        teto = int(round(max(topo, ref, 1.0)))
        lo = int(round(pct_lo / 100.0 * ref)) if ref > 0 else 0
        hi = int(round(topo)) if topo > 0 else teto
        self._iso_spins_em = _ISO_CGY
        for spn in (self.spn_iso_min, self.spn_iso_max):
            spn.blockSignals(True)
            spn.setSingleStep(10)
            spn.setRange(0, teto)
            spn.setFixedWidth(_ISO_LARG_CGY)
            spn.blockSignals(False)
        self.spn_iso_min.setValue(lo)
        self.spn_iso_max.setValue(hi)

    @staticmethod
    def _marcada_por_padrao(nome: str) -> bool:
        """Alvos/OARs começam marcados; estruturas de apoio (anel/CTV/auxiliares)
        começam desmarcadas. Convenção única em ``ficha_pdf.estrutura_auxiliar``."""
        return not ficha_pdf.estrutura_auxiliar(nome)

    def popular_estruturas(self, nomes: list) -> None:
        self.lst_estruturas.blockSignals(True)
        self.lst_estruturas.clear()
        for nome in nomes:
            item = QListWidgetItem(nome)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if self._marcada_por_padrao(nome)
                               else Qt.Unchecked)
            self.lst_estruturas.addItem(item)
        self.lst_estruturas.blockSignals(False)

    @property
    def estruturas_selecionadas(self) -> set:
        out = set()
        for i in range(self.lst_estruturas.count()):
            item = self.lst_estruturas.item(i)
            if item.checkState() == Qt.Checked:
                out.add(item.text())
        return out
