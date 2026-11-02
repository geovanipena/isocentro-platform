"""A aba Qualidade — índices do alvo e complexidade dos campos na tela.

O cálculo mora em ``qualidade.py`` e não sabe que existe Qt; aqui só se monta a
leitura. A divisão é a mesma de ``capa``/``capa_dados``, e serve à mesma coisa:
os índices são testáveis sem levantar janela.

**A ordem da tela é a ordem da desconfiança.** Primeiro o aviso de que as
tolerâncias não foram calibradas nesta clínica, depois o resumo, depois as
tabelas. É a mesma regra da capa que veio de reserva: quem lê um "fora da
faixa" precisa saber, ANTES de ler o número, com que régua ele foi medido.

**O que se lê UMA vez saiu da página.** O aviso da régua era um parágrafo de
cinco linhas, o MCSv tinha um rodapé de quatro e as referências um cartão de
nove — mais altura de texto que de número, numa tela cujas tabelas se leem
todo dia. Tudo isso continua na tela, a um clique: ``qualidade_metodo`` (botões
"Equações" e "Referências", e o link da faixa da régua). O que ficou na página
é o que muda de plano para plano, mais a UMA linha que não pode faltar — a
régua, que muda a leitura de todo número abaixo dela.

**Nenhum verde.** Verde é dose nesta interface (ver ``estilo.py``), e uma tabela
de conferência com linhas verdes de "OK" seria a maior superfície verde do
programa. O que está certo fica em tinta fraca; âmbar e vermelho ficam para o
que precisa de olho. Uma tela em que só o problema tem cor é uma tela que se lê
de relance.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QCursor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QHBoxLayout,
                             QHeaderView, QLabel, QScrollArea, QSizePolicy,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

from isocentro.interface import estilo as st
from isocentro.dominio import paralelo as par
from isocentro.dominio import qualidade as q
from isocentro.dominio import qualidade_metodo as metodo
from isocentro.interface import ui

_COLUNAS_ALVO = ("Alvo", "Vol (cc)", "D98 %", "D95 %", "D50 %", "D2 %",
                 "D méd %", "D50 (Gy)", "HI", "CI RTOG", "Paddick", "Situação")
_COLUNAS_CAMPO = ("Campo", "Técnica", "UM", "Pontos", "MCSv", "SAS 10 mm",
                  "SAS 5 mm", "Abertura (mm)", "Percurso (mm)", "Situação")
_COLUNAS_PARALELO = ("Campo", "MV", "Prof. (cm)", "L eq. (cm)", "TMR", "Scp",
                     "Segm.", "UM do plano", "UM calculado", "Desvio", "Situação")


# O tom da pílula por status. "Fora da faixa" e "atenção" precisam ser
# DISTINGUÍVEIS: os dois em âmbar deixavam a pílula mais grave da tela igual à
# segunda mais grave.
_TOM_DO_STATUS = {q.FALHA: "vermelho", q.ATENCAO: "ambar"}


def _cor_do_status(status: str) -> str:
    """A tinta de um status. Ver a nota sobre o verde no topo do módulo."""
    return {q.FALHA: st.VERMELHO, q.ATENCAO: st.AMBAR,
            q.NA: st.TEXTO_APAGADO}.get(status, st.TEXTO_FRACO)


def _n(valor, casas: int = 1) -> str:
    """Número para a célula, ou travessão quando não há.

    Travessão e não "0,0": zero é uma medida, ausência não é. A regra vale para
    a ficha inteira e não ia mudar aqui.
    """
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "—"
    if v != v:      # NaN
        return "—"
    return f"{v:.{casas}f}".replace(".", ",")


class PainelQualidade(QWidget):
    """A aba: escolhe um plano (ou a soma) e mostra a conferência dele."""

    def __init__(self, parent=None):
        super().__init__(parent)
        st.pintar(self, lambda: f"background:{st.FUNDO_TELA};")

        self._planos: list = []
        self._mesma_tc = False
        self._analises: list = []      # cache por índice de plano
        self._paralelos: list = []     # idem, para o cálculo paralelo
        self._soma = None              # cache da análise da soma

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── Faixa de escolha ────────────────────────────────────────────
        faixa, lay_faixa = ui.faixa()
        self.lbl_paciente = QLabel("")
        st.pintar(self.lbl_paciente, lambda: (
            f"color:{st.TEXTO}; font-size:14px; font-weight:650;"))
        lay_faixa.addWidget(self.lbl_paciente)
        lay_faixa.addSpacing(14)
        lay_faixa.addWidget(ui.rotulo("PLANO"))
        self.cmb_plano = ui.escolha(largura=280)
        self.cmb_plano.currentIndexChanged.connect(self._mostrar_escolhido)
        lay_faixa.addWidget(self.cmb_plano)
        lay_faixa.addStretch(1)
        self.chip_status = ui.Chip("", "neutro")
        lay_faixa.addWidget(self.chip_status)
        # UMA porta para o método, no TOPO: a pergunta "com que conta?" nasce
        # ao ler o primeiro número, não depois de rolar seis cartões. Botão de
        # contorno — leva a outra janela, não age sobre o caso.
        #
        # Um botão, e não dois. "Equações" e "Referências" lado a lado eram
        # duas portas para a MESMA janela, e a segunda não abria nada que a
        # primeira não abrisse: as equações estão a uma aba de distância lá
        # dentro. Dois botões para um destino é o tipo de repetição que se
        # confunde com escolha.
        lay_faixa.addSpacing(6)
        self.btn_referencias = ui.botao("Referências", altura=30)
        self.btn_referencias.setToolTip(
            "As fontes de cada limiar, e as equações desta aba na aba ao lado")
        self.btn_referencias.clicked.connect(
            lambda: self.abrir_metodo(metodo.FONTES))
        lay_faixa.addWidget(self.btn_referencias)
        self._metodo = None            # a janela nasce no primeiro clique
        raiz.addWidget(faixa)
        raiz.addWidget(ui.divisor())

        # ── Miolo rolável ───────────────────────────────────────────────
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QScrollArea.NoFrame)
        st.pintar(rolagem, lambda: f"background:{st.FUNDO_TELA};" + ui.barras())
        dentro = ui.transparente(QWidget())
        self.corpo = QVBoxLayout(dentro)
        self.corpo.setContentsMargins(18, 16, 18, 20)
        self.corpo.setSpacing(14)
        rolagem.setWidget(dentro)
        raiz.addWidget(rolagem, 1)

        self._montar_cartoes()
        self.definir_planos([], False, "")

    # ── Montagem ────────────────────────────────────────────────────────

    def _montar_cartoes(self) -> None:
        # 1. A régua, em UMA linha e sempre em primeiro lugar (ver o topo do
        #    módulo). Era um cartão com um parágrafo de cinco linhas: o aviso
        #    mais importante da aba ocupava mais altura que a tabela de alvos,
        #    e texto que se lê uma vez empurrava para baixo o número que se lê
        #    todo dia. O que não pode faltar é a FRASE; o parágrafo inteiro
        #    está a um clique, no link ao lado.
        self.faixa_regua = QWidget()
        self.faixa_regua.setObjectName("regua")
        st.pintar(self.faixa_regua, lambda: (
            f"QWidget#regua {{ background:{st.AMBAR_FUNDO};"
            f"  border:1px solid {st.AMBAR}; border-radius:9px; }}"
            f"QWidget#regua QLabel {{ color:{st.AMBAR}; font-size:12px;"
            "   background:transparent; border:none; }}"))
        lay_regua = QHBoxLayout(self.faixa_regua)
        lay_regua.setContentsMargins(12, 7, 10, 7)
        lay_regua.setSpacing(8)
        self.lbl_regua = QLabel(metodo.regua_curta())
        self.lbl_regua.setWordWrap(True)
        lay_regua.addWidget(self.lbl_regua, 1)
        lay_regua.addWidget(ui.link(
            "entenda a régua", lambda: self.abrir_metodo(metodo.REGUA)))
        self.corpo.addWidget(self.faixa_regua)

        # 2. Resumo — os números do plano à esquerda, a contagem de status à
        #    direita, numa linha só e SEM cartão. A moldura com o título
        #    "RESUMO" acrescentava 40 px e uma palavra que ninguém precisa
        #    ler: os cartões de valor já são superfície própria.
        self.bloco_resumo = ui.transparente(QWidget())
        self.linha_valores = QHBoxLayout(self.bloco_resumo)
        self.linha_valores.setContentsMargins(0, 0, 0, 0)
        self.linha_valores.setSpacing(10)
        self.val_presc = ui.Valor("PRESCRIÇÃO", "—")
        self.val_mu = ui.Valor("UM (1 FRAÇÃO)", "—")
        # UM/cGy, e não UM/Gy. O acelerador entrega ~1 cGy por UM na condição
        # de referência, então este número é "quantas vezes o plano gasta mais
        # UM que um campo aberto": 3,25 se lê de relance, os 325 de antes não
        # se comparavam de cabeça com nada. Ver ``qualidade.mu_por_cgy``.
        # O rótulo do cartão sai em CAIXA ALTA (``ui.Valor``), e "UM/CGY" não
        # é unidade nenhuma — cGy é centigray. A unidade vai no VALOR, onde a
        # caixa se preserva, como já acontece com "36,25 Gy / 5 fr".
        self.val_mucgy = ui.Valor("MODULAÇÃO", "—")
        self.val_gi = ui.Valor("ÍNDICE DE GRADIENTE", "—")
        for v in (self.val_presc, self.val_mu, self.val_mucgy, self.val_gi):
            # Nenhum destes quebra linha. O do gradiente traz a ressalva "só
            # SRS/SBRT" grudada no número: com quebra, ele virava um cartão de
            # duas linhas ao lado de três de uma, e a fileira inteira ficava
            # torta por causa de um caso.
            v.nao_quebrar()
            self.linha_valores.addWidget(v)
        self.linha_valores.addStretch(1)
        self.pilulas = {}
        for chave in (q.FALHA, q.ATENCAO, q.OK, q.NA):
            chip = ui.Chip("", _TOM_DO_STATUS.get(chave, "neutro"))
            self.pilulas[chave] = chip
            self.linha_valores.addWidget(chip)
        self.corpo.addWidget(self.bloco_resumo)

        # 3. Alvos.
        self.cartao_alvos = ui.Cartao("Alvos — ICRU 83 e conformidade")
        self.tab_alvos = self._tabela(_COLUNAS_ALVO)
        self.cartao_alvos.corpo.addWidget(self.tab_alvos)
        self.corpo.addWidget(self.cartao_alvos)

        # 4. Campos.
        self.cartao_campos = ui.Cartao("Campos — complexidade e preditor de QA")
        self.tab_campos = self._tabela(_COLUNAS_CAMPO)
        self.cartao_campos.corpo.addWidget(self.tab_campos)
        # A ressalva do MCSv cabe numa linha; as quatro que ela tinha estão na
        # janela das equações, junto da fórmula que elas ressalvam.
        nota = QLabel("MCSv menor = mais modulado, não = errado. Serve para "
                      "ESCOLHER o que medir, não para substituir a medida.")
        nota.setWordWrap(True)
        st.pintar(nota, lambda: f"color:{st.TEXTO_APAGADO}; font-size:11.5px;")
        self.cartao_campos.corpo.addWidget(nota)
        self.corpo.addWidget(self.cartao_campos)

        # 5. Cálculo paralelo — a verificação independente de UM.
        self.cartao_paralelo = ui.Cartao(
            "Cálculo paralelo — verificação independente de UM (TG-219)")
        self.lbl_paralelo_maquina = QLabel("")
        self.lbl_paralelo_maquina.setWordWrap(True)
        st.pintar(self.lbl_paralelo_maquina, lambda: (
            f"color:{st.VERMELHO}; font-size:12.5px; font-weight:600;"
            " line-height:150%;"))
        self.cartao_paralelo.corpo.addWidget(self.lbl_paralelo_maquina)
        self.linha_paralelo = QHBoxLayout()
        self.linha_paralelo.setSpacing(10)
        self.val_desvio = ui.Valor("DESVIO DO UM TOTAL", "—")
        self.linha_paralelo.addWidget(self.val_desvio)
        self.linha_paralelo.addStretch(1)
        self.cartao_paralelo.corpo.addLayout(self.linha_paralelo)
        self.tab_paralelo = self._tabela(_COLUNAS_PARALELO)
        self.cartao_paralelo.corpo.addWidget(self.tab_paralelo)
        self.lay_paralelo_notas = QVBoxLayout()
        self.lay_paralelo_notas.setSpacing(7)
        self.cartao_paralelo.corpo.addLayout(self.lay_paralelo_notas)
        self.corpo.addWidget(self.cartao_paralelo)

        # 6. O que o caso obriga a dizer em palavras.
        self.cartao_notas = ui.Cartao("Notas deste caso")
        self.lay_notas = QVBoxLayout()
        self.lay_notas.setSpacing(7)
        self.cartao_notas.corpo.addLayout(self.lay_notas)
        self.corpo.addWidget(self.cartao_notas)

        # 7. As referências NÃO estão mais aqui: eram nove parágrafos
        #    permanentes para uma consulta eventual. Estão no botão
        #    "Referências" da faixa, e cada equação da janela do método aponta
        #    para a sua — que é onde a pergunta pela fonte de fato nasce.
        self.corpo.addStretch(1)

        # A tela vazia: uma frase só, no lugar de seis cartões em branco.
        self.lbl_vazio = QLabel(
            "Nenhum caso carregado. Abra a pasta do paciente na aba Fichinha ou "
            "Total — a Qualidade lê o mesmo DICOM que a ficha, sem recarregar "
            "nada.")
        self.lbl_vazio.setWordWrap(True)
        self.lbl_vazio.setAlignment(Qt.AlignCenter)
        st.pintar(self.lbl_vazio, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:14px; padding:60px 40px;"))
        self.corpo.insertWidget(0, self.lbl_vazio)

    @staticmethod
    def _tabela(colunas) -> QTableWidget:
        t = QTableWidget(0, len(colunas))
        t.setHorizontalHeaderLabels(list(colunas))
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.NoSelection)
        t.setAlternatingRowColors(False)
        t.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        st.pintar(t, ui.grade)
        cab = t.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        # A PRIMEIRA coluna estica, e não a última: o nome da estrutura é o que
        # varia de tamanho, e deixar a sobra na coluna de status abria um vão
        # entre o número e a palavra que o julga.
        cab.setSectionResizeMode(0, QHeaderView.Stretch)
        return t

    def abrir_metodo(self, aba: int = 0) -> None:
        """A janela do método, na aba pedida.

        UMA janela por painel, guardada em ``self._metodo``. Remontá-la a cada
        clique registraria ~90 ouvintes de dia↔noite por abertura (ver a
        armadilha do ``estilo.pintar`` no CLAUDE.md), e a lista de ouvintes é
        do processo, não da janela: quem consulta as equações três vezes numa
        tarde pagaria as três.
        """
        if self._metodo is None:
            self._metodo = metodo.JanelaMetodo(self)
        self._metodo.abrir_em(aba)

    # ── Dados de fora ───────────────────────────────────────────────────

    def definir_planos(self, planos: list, mesma_tc: bool = False,
                       paciente: str = "") -> None:
        """Recebe o caso carregado. Não calcula nada — só prepara a escolha.

        O cálculo espera a aba ser aberta (ver :meth:`ao_abrir`): ler as grades
        de dose de um caso de quatro planos custa segundos, e pagá-los toda vez
        que alguém carrega uma pasta — inclusive quem nunca abre esta aba — é
        cobrar de todo mundo o preço de um.
        """
        self._planos = list(planos or [])
        self._mesma_tc = bool(mesma_tc)
        self._analises = [None] * len(self._planos)
        self._paralelos = [None] * len(self._planos)
        self._soma = None
        self.lbl_paciente.setText(paciente or "")

        self.cmb_plano.blockSignals(True)
        self.cmb_plano.clear()
        for i, p in enumerate(self._planos, start=1):
            self.cmb_plano.addItem(str(p.get("rotulo") or f"Plano {i}"), i - 1)
        if len(self._planos) >= 2 and self._mesma_tc:
            self.cmb_plano.addItem("Soma dos planos", -1)
        self.cmb_plano.setCurrentIndex(0 if self._planos else -1)
        self.cmb_plano.blockSignals(False)

        vazio = not self._planos
        self.lbl_vazio.setVisible(vazio)
        for w in (self.faixa_regua, self.bloco_resumo, self.cartao_alvos,
                  self.cartao_campos, self.cartao_paralelo, self.cartao_notas):
            w.setVisible(not vazio)
        self.cmb_plano.setEnabled(not vazio)
        if vazio:
            self.chip_status.definir("")

    def ao_abrir(self) -> None:
        """Chamado quando a aba vem para a frente: calcula o que falta."""
        if self._planos:
            self._mostrar_escolhido()

    # ── Cálculo e pintura ───────────────────────────────────────────────

    def _analise_atual(self):
        indice = self.cmb_plano.currentData()
        if indice is None:
            return None
        if indice == -1:
            if self._soma is None:
                # A soma precisa das análises por plano para decidir se somar
                # faz sentido (ver ``qualidade.alvos_em_comum``) — então elas
                # vêm primeiro, e de quebra ficam no cache.
                for i in range(len(self._planos)):
                    self._garantir(i)
                self._soma = q.analisar_soma(self._planos, self._analises)
            return self._soma
        return self._garantir(indice)

    def _garantir(self, indice: int):
        if self._analises[indice] is None:
            self._analises[indice] = q.analisar(self._planos[indice])
        return self._analises[indice]

    def _garantir_paralelo(self, indice):
        """O cálculo paralelo do plano escolhido, ou ``None`` para a soma.

        A soma não tem cálculo paralelo: o UM é de um plano e de um campo, e
        não existe "UM da soma" a que comparar. Somar os UM dos planos daria um
        número que nenhuma máquina entrega numa sessão.
        """
        if indice is None or indice < 0:
            return None
        if self._paralelos[indice] is None:
            self._paralelos[indice] = par.verificar(self._planos[indice])
        return self._paralelos[indice]

    def _mostrar_escolhido(self) -> None:
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            an = self._analise_atual()
            ver = self._garantir_paralelo(self.cmb_plano.currentData())
        finally:
            QApplication.restoreOverrideCursor()
        if an is None:
            return
        self._pintar(an)
        self._pintar_paralelo(ver)

    def _pintar(self, an) -> None:
        contagem = an.contagem()
        rotulos = {q.FALHA: "fora da faixa", q.ATENCAO: "atenção",
                   q.OK: "dentro", q.NA: "sem status"}
        for chave, chip in self.pilulas.items():
            n = contagem.get(chave, 0)
            chip.definir(f"{n} {rotulos[chave]}" if n else "")
        self.chip_status.definir(q.ROTULO_STATUS.get(an.status, ""),
                                 _TOM_DO_STATUS.get(an.status, "neutro"))

        # ``ui.Valor`` não tem setter: o texto mora no ``.val``. Escrever nele é
        # o que a Ficha Virtual já faz.
        self.val_presc.val.setText(
            "—" if an.presc_gy != an.presc_gy
            else f"{_n(an.presc_gy, 2)} Gy" + (
                f" / {an.num_fracoes} fr" if an.num_fracoes else ""))
        # UM e UM/cGy são POR PLANO — um campo pertence a um plano só, e a
        # soma não os tem. Mostrá-los com travessão reservaria espaço para um
        # dado que nunca vai chegar; a regra da casa é não reservar vazio.
        for cartao in (self.val_mu, self.val_mucgy):
            cartao.setVisible(not an.soma)
        self.val_mu.val.setText(_n(an.mu_total, 0))
        # DUAS casas: o fator de modulação útil vive entre 1 e 6, e arredondado
        # a inteiro um VMAT de 3,25 e um de 2,51 sairiam ambos como "3".
        self.val_mucgy.val.setText(
            "—" if an.mu_cgy != an.mu_cgy else f"{_n(an.mu_cgy, 2)} UM/cGy")
        # O GI aparece SEMPRE, mas só é julgado em plano hipofracionado (ver
        # ``qualidade.GI_SO_ACIMA_DE_GY_FRACAO``). Escondê-lo no plano
        # convencional tiraria um número que ainda serve de comparação entre
        # planos parecidos; mostrá-lo sem a ressalva o faria parecer avaliado.
        self.val_gi.val.setText(
            _n(an.gi, 2) if an.hipofracionado
            else f"{_n(an.gi, 2)} · só SRS/SBRT")

        self._preencher_alvos(an)
        self._preencher_campos(an)
        self._preencher_notas(an)

    def _celula(self, texto: str, status: str = "", forte: bool = False):
        item = QTableWidgetItem(texto)
        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
        cor = _cor_do_status(status) if status else st.TEXTO
        item.setForeground(QBrush(QColor(cor)))
        if forte:
            f = QFont()
            f.setBold(True)
            item.setFont(f)
        return item

    def _preencher_alvos(self, an) -> None:
        t = self.tab_alvos
        t.setRowCount(len(an.alvos))
        for lin, a in enumerate(an.alvos):
            nome = a.nome + ("  ·  prescrição do plano" if a.primario else "")
            primeira = self._celula(nome, forte=a.primario)
            primeira.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            t.setItem(lin, 0, primeira)
            t.setItem(lin, 1, self._celula(_n(a.volume_cc, 1)))
            t.setItem(lin, 2, self._celula(_n(a.d98, 1), a.status_cobertura))
            t.setItem(lin, 3, self._celula(_n(a.d95, 1)))
            t.setItem(lin, 4, self._celula(_n(a.d50, 1)))
            t.setItem(lin, 5, self._celula(_n(a.d2, 1), a.status_quente))
            t.setItem(lin, 6, self._celula(_n(a.d_media, 1)))
            t.setItem(lin, 7, self._celula(_n(a.d50_gy, 2)))
            # HI só onde ele significa alguma coisa. Num alvo de outro plano o
            # D50 é quase zero e a razão explode: o PTV da mama aparecia com
            # "HI = 133,445" na aba do plano da fossa. Número sem sentido em
            # tinta apagada continua sendo número na tela.
            t.setItem(lin, 8, self._celula(
                _n(a.hi, 3) if a.deste_plano else "—", a.status_hi))
            t.setItem(lin, 9, self._celula(_n(a.ci_rtog, 2), a.status_ci))
            t.setItem(lin, 10, self._celula(_n(a.ci_paddick, 2)))
            t.setItem(lin, 11, self._celula(self._situacao(a), a.status))
        self._ajustar_altura(t)

    @staticmethod
    def _situacao(a) -> str:
        """A palavra da última coluna. Diz POR QUE não há status, quando não há.

        "Sem dado" sozinho não serve: são motivos diferentes — o alvo é de
        outro plano, o alvo tem outra prescrição, ou o cálculo não saiu — e
        quem lê precisa saber qual, senão volta ao DICOM para descobrir.

        Não há caso de ROI SEM CONTORNO aqui: ela não chega à tabela (ver
        ``qualidade.analisar``), e o nome dela vai para as notas do caso.
        """
        if not a.deste_plano:
            return "alvo de outro plano"
        if not a.na_prescricao:
            return "outra prescrição"
        return q.ROTULO_STATUS.get(a.status, "—")

    def _preencher_campos(self, an) -> None:
        t = self.tab_campos
        t.setRowCount(len(an.feixes))
        for lin, f in enumerate(an.feixes):
            primeira = self._celula(f.nome)
            primeira.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            t.setItem(lin, 0, primeira)
            tec = self._celula(f.tecnica or "—")
            tec.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            t.setItem(lin, 1, tec)
            t.setItem(lin, 2, self._celula(_n(f.mu, 1)))
            t.setItem(lin, 3, self._celula(str(f.n_pontos or "—")))
            t.setItem(lin, 4, self._celula(_n(f.mcsv, 3), f.status_mcsv))
            t.setItem(lin, 5, self._celula(_n(f.sas * 100, 1) + " %"
                                           if f.sas == f.sas else "—",
                                           f.status_sas))
            t.setItem(lin, 6, self._celula(_n(f.sas_estreito * 100, 1) + " %"
                                           if f.sas_estreito == f.sas_estreito
                                           else "—"))
            t.setItem(lin, 7, self._celula(_n(f.abertura_mm, 1)))
            t.setItem(lin, 8, self._celula(_n(f.percurso_mm, 0)))
            t.setItem(lin, 9, self._celula(
                q.ROTULO_STATUS.get(f.status, "—") if f.modulado
                else "campo estático", f.status))
        self._ajustar_altura(t)
        # A soma não tem campos: um cartão vazio com o cabeçalho da tabela
        # sugere que o cálculo falhou.
        self.cartao_campos.setVisible(bool(an.feixes))

    @staticmethod
    def _ajustar_altura(t: QTableWidget) -> None:
        """A tabela ocupa a altura das linhas que tem — ela vive dentro de uma
        rolagem, e uma tabela com rolagem PRÓPRIA dentro de outra é a receita
        para a pessoa não achar o resto da página."""
        altura = t.horizontalHeader().height() + 6
        for lin in range(t.rowCount()):
            altura += t.rowHeight(lin)
        t.setFixedHeight(max(altura, 60))

    def _pintar_paralelo(self, ver) -> None:
        """O cartão do cálculo paralelo. ``None`` = a soma, que não tem um.

        A ordem aqui é a mesma do resto da aba: primeiro com que régua, depois
        o número. Se o dado de feixe não é da máquina do plano, a faixa vermelha
        vem ANTES da tabela — quem lê um desvio de 8 % precisa saber, antes de
        lê-lo, que ele foi calculado com a tabela de outro acelerador.
        """
        self.cartao_paralelo.setVisible(ver is not None)
        if ver is None:
            return

        if ver.demonstracao:
            self.lbl_paralelo_maquina.setText(
                "DEMONSTRAÇÃO — isto não é uma verificação. " + (
                    f"O plano é da máquina '{ver.maquina_dicom}' e o cálculo "
                    f"usou a tabela de '{ver.maquina.rotulo}'."
                    if ver.maquina is not None else ""))
        else:
            self.lbl_paralelo_maquina.setText("")
        self.lbl_paralelo_maquina.setVisible(bool(
            self.lbl_paralelo_maquina.text()))

        desvio = ver.desvio_total_pct
        self.val_desvio.val.setText(
            "—" if desvio != desvio else f"{_n(desvio, 1)} %")
        # Sem tom de status no cartão do total quando é demonstração: um número
        # em vermelho ao lado de "isto não é verificação" seria lido como
        # reprovação do plano, e não é reprovação de nada.
        self.val_desvio.definir_tom("neutro" if ver.demonstracao else "azul")

        t = self.tab_paralelo
        t.setRowCount(len(ver.feixes))
        for lin, f in enumerate(ver.feixes):
            status = (q.NA if ver.demonstracao
                      else par.status_do_desvio(f.desvio_pct, f.modulado))
            primeira = self._celula(f.nome)
            primeira.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            t.setItem(lin, 0, primeira)
            t.setItem(lin, 1, self._celula(_n(f.energia_mv, 0)))
            t.setItem(lin, 2, self._celula(_n(f.profundidade_cm, 1)))
            t.setItem(lin, 3, self._celula(_n(f.campo_eq_cm, 1)))
            t.setItem(lin, 4, self._celula(_n(f.tmr, 3)))
            t.setItem(lin, 5, self._celula(_n(f.scp, 3)))
            t.setItem(lin, 6, self._celula(str(f.n_segmentos or "—")))
            t.setItem(lin, 7, self._celula(_n(f.um_plano, 1)))
            t.setItem(lin, 8, self._celula(_n(f.um_calculado, 1)))
            t.setItem(lin, 9, self._celula(
                "—" if f.desvio_pct != f.desvio_pct
                else f"{_n(f.desvio_pct, 1)} %", status))
            # Na célula vai o RÓTULO CURTO; a explicação inteira vai para o
            # rodapé do cartão e para a dica do mouse. Com o texto longo na
            # célula, a coluna esticava e a tabela ganhava barra horizontal —
            # cortando justamente a explicação que ela existia para dar.
            situacao = (f.resumo if f.resumo
                        else ("demonstração" if ver.demonstracao
                              else q.ROTULO_STATUS.get(status, "—")))
            celula = self._celula(situacao, status)
            celula.setToolTip(f.motivo or "")
            t.setItem(lin, 10, celula)
        self._ajustar_altura(t)

        # Cada motivo aparece UMA vez, com os campos que caíram nele. Repetir a
        # mesma explicação em quatro linhas é como esconder as outras três.
        por_motivo: dict = {}
        for f in ver.feixes:
            if f.motivo:
                por_motivo.setdefault(f.motivo, []).append(f.nome)
        notas = list(ver.avisos)
        for motivo, campos in por_motivo.items():
            notas.append(", ".join(campos) + ": " + motivo)
        self._encher_notas(self.lay_paralelo_notas, notas)

    def _preencher_notas(self, an) -> None:
        self._encher_notas(self.lay_notas, an.avisos)
        self.cartao_notas.setVisible(bool(an.avisos))

    @staticmethod
    def _encher_notas(layout, avisos) -> None:
        """Repõe as linhas de aviso de um cartão.

        ``setParent(None)`` e NÃO só ``deleteLater()``. O agendado só morre
        quando o laço de eventos entrega o ``DeferredDelete``, e trocar de plano
        no seletor repovoa as notas antes disso: as antigas continuavam vivas e
        desenhavam por cima do cartão — no TC8 sobrava um retângulo branco ao
        lado da nota e o título do cartão sumia. É a mesma armadilha que o
        CLAUDE.md registra para os testes, e ela também morde em produção.
        """
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for texto in avisos:
            lbl = QLabel("•  " + texto)
            lbl.setWordWrap(True)
            st.pintar(lbl, lambda: (
                f"color:{st.TEXTO_FRACO}; font-size:12.5px; line-height:150%;"))
            layout.addWidget(lbl)
