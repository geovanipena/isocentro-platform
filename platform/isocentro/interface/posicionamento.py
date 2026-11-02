"""Bloco de **posicionamento**: fotos, nota, preparo e imobilizador.

É o que o dosimetrista preenche ao sair da tomografia — e é, exatamente, a folha
2 da capa. Por isso não é uma tela: é um pedaço que a Capa embute. Preencher a
mesma coisa em dois lugares era duplicar o trabalho e criar a chance de as duas
versões discordarem.

Cada setup é uma aba. Um paciente tratado de fêmur e de tórax tem dois jeitos de
ser deitado, com acessórios e preparo diferentes, e as fotos de cada um vão para
a sua aba: o que se arrasta cai sempre no setup aberto.

O **imobilizador** do inventário é a última aba dessa mesma fileira. Não é um
posicionamento, mas é o mesmo assunto — a máscara existe por causa da montagem,
e quem confere uma confere a outra —, e num cartão à parte ele gastava um bloco
inteiro da tela para três linhas de lista.

A nota vem da biblioteca (:mod:`notas_setup`), que já chega semeada do acervo
``.docx`` do serviço — escolher o modelo da região e ajustar o que for diferente
é mais rápido, e mais fiel, do que digitar do zero.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QFileDialog,
                             QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem,
                             QPlainTextEdit, QVBoxLayout, QWidget)

from isocentro.banco import capa_dados
from isocentro.papel import capa_pdf
from isocentro.interface import estilo as st
from isocentro.dados import inventario
from isocentro.dados import notas_setup
from isocentro.interface import ui

# Quadros de foto por posicionamento. Três é o que a mesa rende: a montagem
# vista de frente, de lado e o detalhe do acessório. A folha 2 imprime até
# quatro com um posicionamento e duas quando há dois — ver
# ``capa_pdf.fotos_impressas``, que é quem a tela consulta para avisar o que não
# vai sair impresso.
MAX_FOTOS = 3


@dataclass
class Acrescimo:
    """O que aconteceu com as fotos que se tentou pôr: entraram e sobraram.

    Existe porque "quantas entraram" não é a notícia inteira. Quem soltou
    quatro fotos e recebe "3 foto(s)" lê isso como sucesso.
    """
    entraram: int = 0
    sem_espaco: int = 0     # o posicionamento já estava cheio
    ilegiveis: int = 0      # o arquivo não abriu

    def recado_do_que_sobrou(self) -> str:
        """A metade ruim da notícia, ou "" quando não houve nenhuma."""
        partes = []
        if self.sem_espaco:
            partes.append(
                f"{self.sem_espaco} não coube(ram): o limite é {MAX_FOTOS} por "
                "posicionamento — use outra aba ou remova alguma")
        if self.ilegiveis:
            partes.append(f"{self.ilegiveis} não abriu(ram)")
        return ("Mas " + "; ".join(partes) + ".") if partes else ""

# Largura de conforto de um cartão de preparo: "ACIMA DA CABEÇA" cabe sem
# quebrar. Quantos entram por linha sai da largura disponível — de dois, na
# coluna estreita da Capa, aos seis numa linha só quando o cartão pega a tela
# inteira. Fixar o número esticava cada cartão a meio metro no cadastro.
_LARGURA_CARTAO = 235
_MAX_CARTOES_POR_LINHA = 6
# O que o cartão e a página da aba comem da largura do painel (margens e bordas
# somadas), para a conta de quantos cartões cabem não prometer o que não cabe.
_RESPIRO_ABA = 70

# A foto do setup: teto de largura e a proporção que a altura persegue. Sem a
# proporção, a mesma moldura vira panorâmica no cartão largo e retrato na
# coluna estreita — e o recorte come justamente a montagem que se quer ver.
_LARGURA_MAX_FOTO = 400
_PROPORCAO_FOTO = 0.70
_ALTURA_MIN_FOTO, _ALTURA_MAX_FOTO = 150, 250


def _tem_conteudo(setup: capa_dados.Setup) -> bool:
    """O setup diz alguma coisa, ou é só uma aba que ficou aberta?

    Nome não conta: a aba nasce com um e ele sozinho não descreve montagem
    nenhuma. Foto, acessório ou preparo diferente do padrão, sim.
    """
    if setup.fotos or setup.acessorios.strip():
        return True
    return any(v and v != capa_pdf.VAZIO for v in setup.preparo.values())


class _Foto(ui.Retrato):
    """Uma foto do setup, do tamanho de uma foto. Clicar remove.

    Era um selo de 112×84 num cartão de mil e quinhentos pixels: o elemento
    menor da tela era justamente o que se abre a tela para olhar. Aqui ela é
    elástica — reparte a largura da coluna com as irmãs — e alta o bastante
    para se reconhecer a montagem sem abrir arquivo nenhum.
    """

    def __init__(self, indice: int, parent=None):
        super().__init__(150, _ALTURA_MIN_FOTO, "+", parent, elastico=True)
        # Teto de largura: no cartão que pega a tela inteira, três molduras de
        # meio metro viravam panorâmicas. A altura acompanha a largura de
        # verdade — ver ``PainelPosicionamento._ajustar_fotos``.
        self.setMaximumWidth(_LARGURA_MAX_FOTO)
        self.indice = indice

    def definir(self, dados):
        super().definir(dados)
        self.setCursor(Qt.PointingHandCursor if self.tem_imagem()
                       else Qt.ArrowCursor)
        self.setToolTip("Clique para remover" if self.tem_imagem() else "")


class PainelPosicionamento(QWidget):
    """O cartão da montagem na mesa, pronto para embutir.

    Uma fileira de abas: um posicionamento em cada, e o imobilizador do
    inventário na última.
    """

    mudou = Signal()               # algo aqui dentro mudou (habilita ações)
    aviso = Signal(str, bool)      # (mensagem, é erro) para quem hospeda

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setups: list[dict] = []
        self._registro = ""            # de quem e o cadastro em curso
        # Qual aba de SETUP estava aberta por último. A aba do imobilizador é
        # irmã das de posicionamento, mas não é um posicionamento: sem lembrar
        # deste índice, arrastar uma foto com ela aberta não teria destino.
        self._i_setup = 0
        self._por_linha = 0            # cartões de preparo por linha (ver resizeEvent)
        self.setAcceptDrops(True)      # arrastar fotos para qualquer ponto

        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(14)
        fora.addWidget(self._bloco_montagem(), 1)
        self._nova_aba_setup()

    def _bloco_montagem(self) -> ui.Cartao:
        """Como o paciente vai à mesa: posicionamentos e imobilizador.

        Um cartão só, e as duas coisas na mesma fileira de abas, porque são o
        mesmo assunto — a máscara existe por causa da montagem, e quem confere
        uma confere a outra. Em cartões separados, o inventário empurrava as
        fotos para cima e ocupava um bloco inteiro para três linhas de lista.
        """
        cartao = ui.Cartao("Posicionamento e imobilizador", "2")
        self.btn_fotos = ui.botao("🖼  Escolher fotos…", altura=28)
        # Arrastar é o caminho rápido, mas não pode ser o único: por RDP ou com
        # o app elevado o drag-and-drop não chega, e sem este botão a tela
        # ficaria impossível de usar.
        self.btn_fotos.clicked.connect(self._escolher_fotos)
        cartao.linha_titulo.addWidget(self.btn_fotos)

        self.zona = ui.ZonaArraste("Arraste as fotos do setup aqui")
        self.zona.soltou.connect(self._soltou_fotos)
        cartao.corpo.addWidget(self.zona)

        self.abas = ui.abas()
        self.abas.currentChanged.connect(self._aba_mudou)
        cartao.corpo.addWidget(self.abas, 1)
        # A do imobilizador entra primeiro e fica sempre por último: os setups
        # são inseridos ANTES dela (ver _nova_aba_setup), então o índice de uma
        # aba de posicionamento é o mesmo índice em ``_setups``.
        self.abas.addTab(self._pagina_imobilizador(), "Imobilizador")

        linha = QHBoxLayout()
        linha.setSpacing(6)
        self.btn_add_setup = ui.botao("+  Posicionamento", altura=28)
        self.btn_del_setup = ui.botao("−  Posicionamento", altura=28)
        linha.addWidget(self.btn_add_setup)
        linha.addWidget(self.btn_del_setup)
        linha.addStretch(1)
        cartao.corpo.addLayout(linha)
        # A dica em linha própria e com quebra: em linha com os botões, o aviso
        # de folha dividida é um rótulo de seiscentos pixels que não quebra —
        # ele sozinho impunha ao cartão uma largura mínima que a coluna da
        # direita não tem, e a tela ganhava barra de rolagem horizontal.
        self.lbl_dica = QLabel("Clique numa foto para removê-la.")
        self.lbl_dica.setWordWrap(True)
        self._dica_alerta = False
        st.pintar(self.lbl_dica, self._folha_dica)
        cartao.corpo.addWidget(self.lbl_dica)
        self.btn_add_setup.clicked.connect(self._pedir_novo_setup)
        self.btn_del_setup.clicked.connect(self._remover_setup)
        return cartao

    def _soltou_fotos(self, caminhos: list) -> None:
        """Fotos largadas na zona — expandidas se vier uma pasta."""
        expandidos = []
        for c in caminhos:
            if os.path.isdir(c):
                # Pasta que some ou nega leitura entre o soltar e o ler nao
                # pode derrubar o arraste inteiro.
                try:
                    expandidos += [os.path.join(c, n)
                                   for n in sorted(os.listdir(c))]
                except OSError:
                    self.aviso.emit("Nao consegui ler a pasta " + c, True)
            else:
                expandidos.append(c)
        imagens = [c for c in expandidos
                   if c.lower().endswith(capa_dados.EXT_FOTOS)]
        r = self._acrescentar(expandidos)
        if r.entraram:
            # O destino é a aba de SETUP ativa — que pode não ser a aba aberta,
            # se quem soltou estava olhando o imobilizador.
            entrou = (f"{r.entraram} foto(s) em "
                      f"“{self.abas.tabText(self._i_setup)}”.")
            sobra = r.recado_do_que_sobrou()
            # UMA frase, e com erro=True quando houve sobra: são a mesma
            # notícia. Duas chamadas seguidas a ``mostrar_status`` mostram só a
            # última, que foi como a sobra sumia.
            self.mostrar_status(f"{entrou} {sobra}".strip(), erro=bool(sobra))
        elif not imagens:
            self.mostrar_status("Nada que eu reconheça como imagem foi soltado.",
                                erro=True)
        else:
            self.mostrar_status(r.recado_do_que_sobrou(), erro=True)

    def _pedir_novo_setup(self) -> None:
        """O ``+`` da tela — que para em ``capa_pdf.MAX_SETUPS``.

        O teto é do PAPEL: acima dele a folha 2 deformava (fotos encolhendo até
        não se conferir a montagem, carimbo empurrado para fora). Recusar aqui,
        com o motivo na tela, é melhor que aceitar e descartar na impressão —
        que era o que acontecia: a aba existia, recebia fotos, e sumia do PDF.
        """
        if len(self._setups) >= capa_pdf.MAX_SETUPS:
            self.aviso.emit(
                f"A folha 2 comporta {capa_pdf.MAX_SETUPS} posicionamentos. "
                "Para um terceiro, use uma segunda contracapa.", True)
            return
        self._nova_aba_setup()

    def _nova_aba_setup(self, setup: Optional[capa_dados.Setup] = None) -> dict:
        """Uma aba de posicionamento, no mesmo padrão da identificação.

        O que a montagem MANDA FAZER — máscara curta, decúbito dorsal, bexiga
        cheia — se lê em pílulas, como a identidade do paciente. A grade de
        campos existe para corrigir, e corrigir é o caso raro: aberta o tempo
        todo, ela punha nove caixas de texto na frente de quem só precisava
        conferir como o paciente foi deitado. Metade delas dizendo "N/A", que é
        ruído com aparência de dado.
        """
        setup = setup or capa_dados.Setup()
        pagina = ui.pagina_de_aba(QWidget())
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        campos: dict = {}

        campos["nome"] = ui.entrada()
        campos["nome"].setText(setup.nome)
        campos["nome"].textChanged.connect(self._renomear_abas)
        campos["nome"].textChanged.connect(self._repintar_valores)
        # A nota fica FORA do painel de correção: escolher o modelo da região é
        # a ação de abertura do posicionamento, não um acerto de detalhe.
        campos["nota"] = ui.escolha()
        campos["nota"].activated.connect(self._aplicar_nota)
        # O conteúdo tal como a nota o deixou, e em que item o seletor parou.
        # É o que permite saber se houve ajuste à mão — e voltar atrás quando a
        # troca é recusada. Ver ``_aplicar_nota``.
        campos["nota_base"] = None
        campos["nota_indice"] = 0
        campos["aberta"] = False

        # ── Cabeçalho: título, seletor de nota e o botão de correção ──────
        campos["titulo"] = QLabel(setup.nome or "Posicionamento")
        st.pintar(campos["titulo"], lambda: (
            f"color:{st.TEXTO}; font-size:15px; font-weight:bold;"))
        campos["btn_corrigir"] = ui.botao("✎  Corrigir", altura=28)
        campos["btn_corrigir"].setToolTip(
            "Abre os campos de nome, acessórios e preparo")
        campos["btn_corrigir"].clicked.connect(self._alternar_correcao)

        topo = QHBoxLayout()
        topo.setSpacing(10)
        topo.addWidget(campos["titulo"])
        topo.addStretch(1)
        topo.addWidget(ui.campo("Nota de posicionamento", campos["nota"]), 2)
        topo.addWidget(campos["btn_corrigir"], 0, Qt.AlignBottom)
        lay.addLayout(topo)

        # ── O que a nota manda fazer, em cartões de ler de longe ──────────
        # Só o que está preenchido, e acima das fotos: é a instrução, e ela
        # vale mais que a confirmação visual de como ficou.
        campos["valores"] = QGridLayout()
        campos["valores"].setHorizontalSpacing(8)
        campos["valores"].setVerticalSpacing(8)
        for c in range(_MAX_CARTOES_POR_LINHA):
            campos["valores"].setColumnStretch(c, 1)
        lay.addLayout(campos["valores"])

        # ── As fotos ──────────────────────────────────────────────────────
        campos["fotos"] = list(setup.fotos[:MAX_FOTOS])
        campos["fotos"] += [None] * (MAX_FOTOS - len(campos["fotos"]))
        campos["miniaturas"] = []
        faixa = QHBoxLayout()
        faixa.setSpacing(7)
        for i in range(MAX_FOTOS):
            m = _Foto(i)
            m.clicado.connect(lambda k=i: self._remover_foto(k))
            campos["miniaturas"].append(m)
            # Peso igual: as três repartem a largura em vez de se amontoarem
            # num canto. O que passar do teto de ``_Foto`` sobra para o
            # esticador abaixo, e elas ficam alinhadas à esquerda.
            faixa.addWidget(m, 1)
        faixa.addStretch(0)
        # Sem rótulo: três molduras com um "+" dentro já dizem o que são, e o
        # rótulo só empurrava para baixo o que interessa olhar.
        caixa_fotos = ui.transparente(QWidget())
        caixa_fotos.setLayout(faixa)
        campos["caixa_fotos"] = caixa_fotos
        lay.addWidget(caixa_fotos)

        # ── Correção: nome, acessórios, preparo e a biblioteca de notas ───
        campos["acessorios"] = ui.area(4)
        campos["acessorios"].setPlainText(setup.acessorios)
        campos["acessorios"].textChanged.connect(self._repintar_valores)

        campos["preparo"] = {}
        grade_prep = QGridLayout()
        grade_prep.setHorizontalSpacing(8)
        grade_prep.setVerticalSpacing(8)
        for k, col in enumerate(capa_pdf.COLUNAS_PREPARO):
            cmb = ui.escolha(capa_pdf.OPCOES_PREPARO.get(col, (capa_pdf.VAZIO,)),
                             editavel=True)
            cmb.setCurrentText(setup.preparo.get(col) or capa_pdf.VAZIO)
            cmb.currentTextChanged.connect(self._repintar_valores)
            campos["preparo"][col] = cmb
            grade_prep.addWidget(ui.campo(col, cmb), k // 3, k % 3)
        caixa_prep = ui.transparente(QWidget())
        caixa_prep.setLayout(grade_prep)

        botoes = QHBoxLayout()
        botoes.setSpacing(5)
        botoes.addWidget(ui.rotulo("Biblioteca de notas"))
        for texto, alvo in (("Nova…", self._nota_nova),
                            ("Editar…", self._nota_editar),
                            ("Excluir…", self._nota_excluir)):
            b = ui.botao(texto, altura=29)
            b.clicked.connect(alvo)
            botoes.addWidget(b)
        botoes.addStretch(1)

        baixo = QHBoxLayout()
        baixo.setSpacing(14)
        baixo.addWidget(ui.campo("Acessórios", campos["acessorios"]), 2)
        # O preparo já tem um rótulo em cada coluna; um "Preparo" por cima deles
        # era um terceiro nível de título para seis caixas de escolha.
        baixo.addWidget(caixa_prep, 3)

        dentro = QVBoxLayout()
        dentro.setContentsMargins(0, 6, 0, 0)
        dentro.setSpacing(10)
        dentro.addWidget(ui.campo("Nome do posicionamento", campos["nome"]))
        dentro.addLayout(baixo)
        dentro.addLayout(botoes)
        campos["caixa_edicao"] = ui.transparente(QWidget())
        campos["caixa_edicao"].setLayout(dentro)
        campos["caixa_edicao"].setVisible(False)
        lay.addWidget(campos["caixa_edicao"])
        lay.addStretch(1)

        campos["pagina"] = pagina
        self._setups.append(campos)
        # ANTES da aba do imobilizador, que fica sempre por último: assim o
        # índice da aba e o índice em ``_setups`` continuam sendo o mesmo.
        i = len(self._setups) - 1
        self.abas.insertTab(i, pagina,
                            setup.nome or f"Posicionamento {len(self._setups)}")
        self.abas.setCurrentIndex(i)
        self._recarregar_notas()
        self._ajustar_fotos()      # a aba nova nasce com a altura de agora
        self._pintar_fotos()
        self._repintar_valores()
        # O "+" apaga assim que a folha enche — sem isto ele só se atualizava
        # na próxima mudança de campo, e até lá aceitava o clique.
        self._atualizar_botoes()
        return campos

    def _remover_setup(self) -> None:
        if len(self._setups) <= 1:
            self.mostrar_status("A simulação precisa de ao menos um "
                                "posicionamento.", erro=True)
            return
        # O último posicionamento ABERTO, e não a aba atual: com o imobilizador
        # à mostra, "− Posicionamento" apagaria a aba errada — ou o inventário.
        i = min(self._i_setup, len(self._setups) - 1)
        self.abas.removeTab(i)
        self._setups.pop(i)["pagina"].deleteLater()
        self._i_setup = min(i, len(self._setups) - 1)
        self._renomear_abas()
        self._rotular_aba_imob()
        # Sem isto o "+" continuava apagado depois de remover, com o tooltip
        # dizendo que a folha está cheia — em UM posicionamento. E o "−" ficava
        # aceso com um setup só, prometendo o que ele mesmo recusa.
        self._atualizar_botoes()

    def _renomear_abas(self, *_) -> None:
        for i, s in enumerate(self._setups):
            self.abas.setTabText(i, s["nome"].text().strip()
                                 or f"Posicionamento {i + 1}")

    def _aba(self) -> dict:
        """O posicionamento em que se está trabalhando.

        Pela aba de setup aberta por último, não pela aba atual: com o
        imobilizador aberto, a foto arrastada tem de cair em algum lugar.
        """
        if not self._setups:
            return self._nova_aba_setup()
        return self._setups[min(max(self._i_setup, 0), len(self._setups) - 1)]

    # ── Notas: escolher, criar, editar ───────────────────────────────────

    def _recarregar_notas(self) -> None:
        """Repõe a biblioteca em todos os combos, preservando a escolha atual.

        Biblioteca VAZIA tem de se anunciar. Ela abria um seletor com um único
        item — "(escolher nota…)" — e nada dentro: clicar não fazia nada e não
        dizia por quê, e quem estava na clínica concluiu que a função estava
        quebrada. Estava mesmo, mas em outro lugar: a instalação nova saía sem
        biblioteca nenhuma (ver ``notas_setup``). Aqui fica o recado.
        """
        notas = notas_setup.carregar()
        for aba in self._setups:
            cmb = aba["nota"]
            atual = cmb.currentText()
            cmb.blockSignals(True)
            cmb.clear()
            cmb.addItem("(escolher nota…)" if notas
                        else "(nenhuma nota na biblioteca)")
            for n in notas:
                cmb.addItem(("★ " if not n.modelo else "") + n.nome, n.nome)
            i = cmb.findText(atual)
            cmb.setCurrentIndex(i if i > 0 else 0)
            # Seletor apagado quando não há o que escolher: aceso, ele promete
            # uma lista que não existe.
            cmb.setEnabled(bool(notas))
            cmb.setToolTip("" if notas else (
                "A biblioteca de notas está vazia.\n\n"
                "Para criar a primeira: “✎ Corrigir”, preencha acessórios e "
                "preparo, e então “Nova…”.\n"
                "Para trazer as do serviço: o arquivo "
                f"{notas_setup.ARQUIVO} da instalação antiga, ao lado do "
                "programa."))
            cmb.blockSignals(False)

    def _conteudo(self, aba: dict) -> tuple:
        """Acessórios e preparo como estão agora — para comparar com a nota."""
        return (aba["acessorios"].toPlainText().strip(),
                tuple(w.currentText() for w in aba["preparo"].values()))

    def _tem_ajuste_manual(self, aba: dict) -> bool:
        """Há na aba algo que a nota escolhida não colocou lá?

        É o que distingue "ainda não mexi" de "ajustei este paciente": trocar a
        nota reescreve acessórios e preparo inteiros, e um ajuste perdido vira
        um paciente montado errado — a folha não guarda rascunho.
        """
        atual = self._conteudo(aba)
        base = aba.get("nota_base")
        if base is None:
            return bool(atual[0]) or any(v != capa_pdf.VAZIO for v in atual[1])
        return atual != base

    def _confirmar_troca_de_nota(self, para: str) -> bool:
        return ui.confirmar(
            self, "Trocar a nota de posicionamento?",
            "Este posicionamento tem ajustes que não vieram da nota.",
            acao="Trocar mesmo assim", recusa="Manter como está",
            detalhe=(f"Aplicar “{para}” reescreve os acessórios e o preparo.\n"
                     "Se os ajustes são deste paciente, guarde-os como nota "
                     "antes (botão Nova…)."),
            perigo=True)

    def _aplicar_nota(self, indice: int) -> None:
        """Escolher uma nota preenche acessórios e preparo da aba ativa.

        Só o gesto de ESCOLHER troca — ``ui.Escolha`` já impede que a roda do
        mouse o faça de passagem —, e havendo ajuste à mão ainda é preciso
        confirmar. Recusar devolve o seletor ao item anterior: um seletor
        apontando uma nota que não foi aplicada é pior que nenhuma, porque quem
        confere a folha acredita nele.
        """
        aba = self._aba()
        if indice <= 0:
            aba["nota_indice"] = indice
            return
        nome = aba["nota"].itemData(indice) or aba["nota"].itemText(indice)
        nota = notas_setup.por_nome(nome)
        if nota is None:
            return
        if (self._tem_ajuste_manual(aba)
                and not self._confirmar_troca_de_nota(nota.nome)):
            cmb = aba["nota"]
            cmb.blockSignals(True)
            cmb.setCurrentIndex(aba.get("nota_indice", 0))
            cmb.blockSignals(False)
            self.mostrar_status("Nota mantida — nada foi reescrito.")
            return
        aba["acessorios"].setPlainText(nota.acessorios)
        for col, cmb in aba["preparo"].items():
            cmb.setCurrentText(nota.preparo.get(col) or capa_pdf.VAZIO)
        # O nome do posicionamento passa a ser o da nota: é o rótulo que sai
        # impresso na folha 2, e ele tem de dizer a mesma montagem que os
        # acessórios logo abaixo. O campo continua livre — quem tratar dois
        # sítios com a mesma nota ("TÓRAX D" e "TÓRAX E") renomeia por cima.
        aba["nome"].setText(nota.nome)
        aba["nota_base"] = self._conteudo(aba)
        aba["nota_indice"] = indice
        self._repintar_valores()
        self.mostrar_status(f"Nota “{nota.nome}” aplicada — ajuste o que for "
                            "diferente neste paciente.")

    def _nota_nova(self) -> None:
        """Cria uma nota a partir do que já está na aba — o caminho mais curto.

        Quem clica em "Nova" acabou de montar um setup fora do padrão; o
        conteúdo dele já está na tela, e começar do zero seria redigitar.
        """
        aba = self._aba()
        base = notas_setup.Nota(
            nome="", acessorios=aba["acessorios"].toPlainText(),
            preparo={c: w.currentText() for c, w in aba["preparo"].items()},
            modelo=False)
        self._editar_nota(base, titulo="Nova nota de posicionamento")

    def _nota_editar(self) -> None:
        aba = self._aba()
        nome = aba["nota"].currentData() or ""
        nota = notas_setup.por_nome(nome) if nome else None
        if nota is None:
            self.mostrar_status("Escolha primeiro a nota que quer editar.",
                                erro=True)
            return
        self._editar_nota(nota, titulo=f"Editar “{nota.nome}”")

    def _nota_excluir(self) -> None:
        """Tira a nota escolhida da biblioteca — depois de confirmar.

        Sem apagar, a biblioteca só cresce: a nota de um paciente de dois anos
        atrás continua na lista de todo mundo, e é entre elas que se procura a
        certa com o paciente já na mesa.
        """
        aba = self._aba()
        nome = aba["nota"].currentData() or ""
        nota = notas_setup.por_nome(nome) if nome else None
        if nota is None:
            self.mostrar_status("Escolha primeiro a nota que quer excluir.",
                                erro=True)
            return
        if not ui.confirmar(
                self, "Excluir a nota?",
                f"“{nota.nome}” sai da biblioteca.",
                acao="Excluir", recusa="Manter a nota",
                detalhe=("Isto não desfaz o que já foi aplicado neste "
                         "posicionamento, e não mexe em simulação nenhuma já "
                         "cadastrada.\n"
                         + ("Esta é uma nota do acervo — some para todos os "
                            "usuários." if nota.modelo
                            else "Esta é uma nota de paciente.")),
                perigo=True):
            return
        no_disco = notas_setup.remover(nota.nome)
        self._recarregar_notas()
        aba["nota_indice"] = 0
        if no_disco:
            self.mostrar_status(f"Nota “{nota.nome}” excluída da biblioteca.")
        else:
            self.mostrar_status(
                f"“{nota.nome}” saiu da lista, mas não consegui gravar a "
                "biblioteca — ela volta na próxima abertura.", erro=True)

    def _editar_nota(self, nota: "notas_setup.Nota", titulo: str) -> None:
        dlg = _DialogoNota(nota, titulo, self)
        if dlg.exec() != QDialog.Accepted:
            return
        nova = dlg.nota()
        if not nova.nome.strip():
            self.mostrar_status("A nota precisa de um nome para ser guardada.",
                                erro=True)
            return
        no_disco = notas_setup.guardar(nova)
        self._recarregar_notas()
        aba = self._aba()
        i = aba["nota"].findData(nova.nome)
        if i > 0:
            aba["nota"].setCurrentIndex(i)
            self._aplicar_nota(i)
        if no_disco:
            self.mostrar_status(f"Nota “{nova.nome}” guardada na biblioteca.")
        else:
            # Vale nesta sessão e some no fechamento. Dizer "guardada" seria
            # mentir sobre um trabalho que a pessoa acha que não precisa refazer.
            self.mostrar_status(
                f"Nota “{nova.nome}” vale só nesta sessão — não consegui gravar "
                "a biblioteca em disco. Avise quem instalou o programa.",
                erro=True)

    # ── Fotos ────────────────────────────────────────────────────────────

    def _alternar_correcao(self) -> None:
        """Abre/fecha os campos da aba ativa.

        O estado mora no dicionário da aba, não no ``isVisible`` do Qt: este
        responde sobre a TELA estar aberta, e com a Capa em outro modo o botão
        abriria sem nunca fechar.
        """
        aba = self._aba()
        aba["aberta"] = not aba["aberta"]
        aba["caixa_edicao"].setVisible(aba["aberta"])
        aba["btn_corrigir"].setText(
            "✕  Fechar" if aba["aberta"] else "✎  Corrigir")

    def _repintar_valores(self, *_) -> None:
        """Redesenha os cartões da aba ativa com o que está nos campos.

        Um cartão por coluna de preparo, e um largo com os acessórios. ``N/A``
        não vira cartão: é a ausência de preparo, e ocuparia a mesma atenção
        que "bexiga cheia" — que é instrução de verdade, e a única que não pode
        passar batida.

        Cada cartão nasce **com pai** (ver ``ui.CabecalhoPaciente``): sem ele o
        Qt o exibe como janela solta até o layout adotá-lo, e aqui o repinte é
        a cada tecla digitada nos acessórios.
        """
        if not self._setups:
            return
        aba = self._aba()
        grade = aba["valores"]
        pai = grade.parentWidget()
        for i in reversed(range(grade.count())):
            item = grade.takeAt(i)
            velho = item.widget()
            if velho is not None:
                # ``hide`` ANTES do agendamento: fora do layout e ainda não
                # destruído, o cartão velho fica desenhado na geometria antiga
                # — um fantasma sobre a barra de abas até o Qt recolhê-lo.
                velho.hide()
                velho.deleteLater()

        # O rótulo é a coluna. Só o valor, "CHEIA" e "VAZIO" lado a lado não
        # dizem de quê — e é bexiga e reto trocados que põem o paciente na mesa
        # do jeito errado.
        prep = [(col.capitalize(), v)
                for col, v in ((c, w.currentText().strip())
                               for c, w in aba["preparo"].items())
                if v and v != capa_pdf.VAZIO]
        por_linha = self._cartoes_por_linha()
        # Peso só nas colunas em uso: as vazias continuavam reservando a fatia
        # delas, e os cartões de duas colunas ficavam com metade da largura —
        # "ACIMA DA CABEÇA" saía cortado num cartão com espaço de sobra ao lado.
        for c in range(_MAX_CARTOES_POR_LINHA):
            grade.setColumnStretch(c, 1 if c < por_linha else 0)
        linha = 0
        for k, (rot, val) in enumerate(prep):
            linha, coluna = divmod(k, por_linha)
            grade.addWidget(ui.Valor(rot, val, "azul", pai), linha, coluna)

        acess = [l.strip() for l in aba["acessorios"].toPlainText().splitlines()
                 if l.strip()]
        if acess:
            # Num cartão só, e não um por acessório: eles se leem juntos ("o
            # que vai na mesa"), e sete cartõezinhos empurrariam as fotos para
            # fora da tela.
            grade.addWidget(
                ui.Valor("Acessórios", "\n".join(acess), "neutro", pai),
                linha + 1, 0, 1, por_linha)
        aba["titulo"].setText(aba["nome"].text().strip() or "Posicionamento")

    def _cartoes_por_linha(self) -> int:
        """Quantos cartões de preparo cabem na largura de agora.

        Medida no PAINEL, não nas abas: dentro do ``resizeEvent`` a largura
        nova ainda não desceu para os filhos, e perguntar a eles devolvia a
        largura antiga — dois cartões por linha numa tela que comporta seis.
        """
        largura = max(self.width() - _RESPIRO_ABA, 0)
        return max(2, min(_MAX_CARTOES_POR_LINHA,
                          largura // _LARGURA_CARTAO))

    def _ajustar_fotos(self) -> None:
        """Altura das molduras a partir da largura que cada uma vai ter."""
        disponivel = max(self.width() - _RESPIRO_ABA - 2 * 7, 0)
        larg = min(_LARGURA_MAX_FOTO, disponivel // MAX_FOTOS)
        alt = int(max(_ALTURA_MIN_FOTO,
                      min(_ALTURA_MAX_FOTO, larg * _PROPORCAO_FOTO)))
        for aba in self._setups:
            for m in aba["miniaturas"]:
                if m.height() != alt:
                    m.setFixedHeight(alt)

    def resizeEvent(self, e):  # noqa: N802 - assinatura do Qt
        """Mudou a largura, mudam os cartões por linha e a altura das fotos.

        Os cartões só são repintados quando o NÚMERO muda: refazê-los a cada
        pixel de arrasto da janela recriaria sete widgets por quadro.
        """
        super().resizeEvent(e)
        self._ajustar_fotos()
        por_linha = self._cartoes_por_linha()
        if por_linha != self._por_linha:
            self._por_linha = por_linha
            self._repintar_valores()

    def _ajustar_zona(self) -> None:
        """A faixa de arraste recua quando a aba ativa já tem foto."""
        aba = self._aba() if self._setups else None
        tem = bool(aba and any(aba["fotos"]))
        # Com o imobilizador aberto, a faixa diz PARA ONDE a foto vai: o
        # destino é o posicionamento aberto por último, e nada na tela estaria
        # dizendo isso.
        no_imob = self.abas.currentIndex() == self._i_aba_imob()
        destino = self.abas.tabText(self._i_setup) if no_imob else ""
        # A legenda vai junto: ``dizer`` sem ela a apaga, e a faixa vazia
        # perderia a única menção ao botão — o caminho de quem não pode
        # arrastar (RDP, app elevado).
        self.zona.dizer(
            f"Arraste fotos aqui — vão para “{destino}”" if destino
            else ("Arraste mais fotos aqui" if tem
                  else "Arraste as fotos do setup aqui"),
            "" if (tem or destino) else "ou use o botão Escolher fotos")
        self.zona.compactar(tem or bool(destino))

    def _pintar_fotos(self) -> None:
        for aba in self._setups:
            for i, m in enumerate(aba["miniaturas"]):
                m.definir(aba["fotos"][i])
        self._ajustar_zona()      # a faixa segue a aba ATIVA, não cada uma
        self._atualizar_botoes()

    def _remover_foto(self, indice: int) -> None:
        aba = self._aba()
        if not aba["fotos"][indice]:
            return
        # Fecha o buraco: a foto 3 removida faz a 4 virar 3, senão o cadastro
        # gravaria uma lacuna na numeração dos arquivos.
        restantes = [f for i, f in enumerate(aba["fotos"]) if f and i != indice]
        aba["fotos"] = restantes + [None] * (MAX_FOTOS - len(restantes))
        self._pintar_fotos()

    def acrescentar_fotos(self, caminhos: list[str]) -> int:
        """Põe as imagens na aba ativa. Devolve quantas entraram."""
        return self._acrescentar(caminhos).entraram

    def _acrescentar(self, caminhos: list[str]) -> Acrescimo:
        """O mesmo trabalho, dizendo também o que FICOU DE FORA.

        A contagem de quem entrou não basta para falar com quem está na frente,
        e isso custou um defeito: o aviso de "já tem 3 fotos" era emitido aqui
        e o chamador, vendo que uma foto entrou, escrevia por cima dele a
        mensagem de sucesso. A quarta foto sumia sem recado — e quem soltou
        quatro viu "3 foto(s)" e foi embora achando que estavam as quatro.

        Por isso este método não fala com a tela: ele RELATA, e quem compõe a
        frase é o chamador, que sabe se houve sucesso e sobra ao mesmo tempo.
        O arquivo ilegível vai junto pela mesma razão — até 04/09/2026 ele era
        descartado em silêncio absoluto, sem nem o aviso que o limite tinha.
        """
        aba = self._aba()
        r = Acrescimo()
        for caminho in caminhos:
            if not caminho.lower().endswith(capa_dados.EXT_FOTOS):
                continue
            livre = next((i for i, f in enumerate(aba["fotos"]) if not f), -1)
            if livre < 0:
                # As que ainda faltavam também não cabem: o contador para de
                # tentar, mas quem lê precisa do número CHEIO para conferir com
                # o que soltou.
                r.sem_espaco += 1
                continue
            try:
                with open(caminho, "rb") as fh:
                    aba["fotos"][livre] = fh.read()
                r.entraram += 1
            except OSError:
                r.ilegiveis += 1
        self._pintar_fotos()
        return r

    def _escolher_fotos(self) -> None:
        caminhos, _ = QFileDialog.getOpenFileNames(
            self, "Fotos de posicionamento", "",
            "Imagens (*.jpg *.jpeg *.png *.bmp)")
        if caminhos:
            r = self._acrescentar(caminhos)
            sobra = r.recado_do_que_sobrou()
            self.mostrar_status(
                f"{r.entraram} foto(s) neste posicionamento. {sobra}".strip(),
                erro=bool(sobra))

    # ── 4. Imobilizadores ────────────────────────────────────────────────

    def _pagina_imobilizador(self) -> QWidget:
        """A prateleira, como página de aba do cartão da montagem."""
        pagina = ui.pagina_de_aba(QWidget())
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        linha = QHBoxLayout()
        linha.setSpacing(6)
        titulo = QLabel("Imobilizador vinculado ao paciente")
        st.pintar(titulo, lambda: f"color:{st.TEXTO}; font-size:15px;"
                             " font-weight:bold;")
        linha.addWidget(titulo)
        linha.addStretch(1)
        for texto, alvo in (("🔄  Reler", self.recarregar_inventario),
                            ("↩  Devolver", self._devolver_imobilizador),
                            ("🗑  Descartar", self._descartar_imobilizador)):
            b = ui.botao(texto, altura=28)
            b.clicked.connect(alvo)
            linha.addWidget(b)
            if "Devolver" in texto:
                self.btn_devolver = b
                b.setToolTip("Selecione um item EM USO para devolvê-lo")
            elif "Descartar" in texto:
                self.btn_descartar = b
                b.setToolTip("Retira o item de circulação")
            else:
                self.btn_rec_imob = b
        lay.addLayout(linha)

        self.lista_imob = QListWidget()
        st.pintar(self.lista_imob, lambda: ui.LISTA)
        self.lista_imob.setMinimumHeight(150)
        # Marcar/desmarcar tem de repintar o rótulo da aba: fechada, ela é a
        # única coisa na tela dizendo que há máscara vinculada.
        self.lista_imob.itemChanged.connect(lambda _i: self._rotular_aba_imob())
        lay.addWidget(self.lista_imob, 1)

        self.lbl_imob = QLabel("")
        self.lbl_imob.setWordWrap(True)
        st.pintar(self.lbl_imob, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:10.5px;"))
        lay.addWidget(self.lbl_imob)
        self.recarregar_inventario()
        return pagina

    def _i_aba_imob(self) -> int:
        """A aba do imobilizador é sempre a última — depois dos setups."""
        return len(self._setups)

    def _rotular_aba_imob(self) -> None:
        """Diz na aba quantos itens estão vinculados.

        Fechada, a aba é tudo o que se vê do inventário: sem o número, a
        máscara vinculada some da tela e a conferência passa por cima dela.
        """
        i = self._i_aba_imob()
        if i >= self.abas.count():
            return          # a aba ainda está sendo montada (ver __init__)
        n = len(self.imobilizadores())
        self.abas.setTabText(i, f"Imobilizador ({n})" if n else "Imobilizador")

    def _aba_mudou(self, i: int) -> None:
        """Lembra o último posicionamento aberto e reavalia a faixa de arraste.

        A faixa fala do posicionamento ABERTO: sem reavaliar, ela promete
        espaço vazio numa aba já cheia.
        """
        if 0 <= i < len(self._setups):
            self._i_setup = i
        self._ajustar_zona()

    def recarregar_inventario(self) -> None:
        """Mostra a prateleira: os livres marcáveis, os em uso só para consulta.

        Só os disponíveis podem ser marcados — oferecer um item que está com
        outro paciente convida ao erro que o inventário existe para evitar. Mas
        os em uso aparecem, apagados, porque é neles que se clica para
        **devolver**: sem isso o item vinculado sumia da lista para sempre e o
        inventário se esgotava sem volta.
        """
        self.lista_imob.clear()
        itens = [i for i in inventario.carregar()
                 if i.estado != inventario.DESCARTADO]
        livres = [i for i in itens if i.disponivel()]
        # Item ja vinculado a ESTE paciente segue marcavel e marcado: sem isso,
        # recadastrar no mesmo mes regravaria o SIMULACAO.json com a lista de
        # imobilizadores vazia, porque o item some por ja estar em uso.
        do_paciente = {i.codigo for i in itens
                       if i.estado == inventario.EM_USO and self._registro
                       and i.registro == self._registro}
        for item in itens:
            it = QListWidgetItem(item.rotulo())
            it.setData(Qt.UserRole, item.codigo)
            if item.codigo in do_paciente:
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked)
                it.setForeground(QColor(st.AZUL_CLARO))
                it.setToolTip("Ja vinculado a este paciente")
            elif item.disponivel():
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked)
                if item.gasto():
                    it.setForeground(QColor(st.AMBAR))
                    it.setToolTip("No limite de utilizações — confira o material")
            else:
                it.setForeground(QColor(st.TEXTO_APAGADO))
                it.setToolTip("Em uso — selecione e clique em Devolver")
            self.lista_imob.addItem(it)
        if not itens:
            self.lista_imob.addItem("(inventário vazio)")
        self.lbl_imob.setText(
            f"Opcional — {len(livres)} de {len(itens)} disponível(is). Máscara "
            "e VacLok ficam vinculados ao paciente; acessório padrão (rampa, "
            "base, apoio) vai na lista de acessórios, sem inventário.")
        self._rotular_aba_imob()

    def imobilizadores(self) -> list[str]:
        """Códigos marcados."""
        return [self.lista_imob.item(i).data(Qt.UserRole)
                for i in range(self.lista_imob.count())
                if self.lista_imob.item(i).checkState() == Qt.Checked
                and self.lista_imob.item(i).data(Qt.UserRole)]

    def _selecionado_em_uso(self) -> Optional[str]:
        itens = self.lista_imob.selectedItems()
        codigo = itens[0].data(Qt.UserRole) if itens else None
        if not codigo:
            self.mostrar_status("Selecione na lista o imobilizador.", erro=True)
            return None
        item = inventario.por_codigo(codigo)
        if item is None or item.disponivel():
            self.mostrar_status(f"{codigo} já está na prateleira.", erro=True)
            return None
        return codigo

    def _devolver_imobilizador(self) -> None:
        """Fim do tratamento: o item volta à prateleira."""
        codigo = self._selecionado_em_uso()
        if not codigo:
            return
        inventario.liberar([codigo])
        self.recarregar_inventario()
        self.mostrar_status(f"{codigo} devolvido à prateleira.")

    def _descartar_imobilizador(self) -> None:
        """Material que não volta. Pergunta antes: descarte não tem desfazer."""
        itens = self.lista_imob.selectedItems()
        codigo = itens[0].data(Qt.UserRole) if itens else None
        if not codigo:
            self.mostrar_status("Selecione na lista o imobilizador.", erro=True)
            return
        if not ui.confirmar(
                self, "Descartar imobilizador?",
                f"Retirar {codigo} de circulação?",
                acao="Descartar", recusa="Manter em circulação",
                detalhe="Ele sai da lista e não volta a ser oferecido.",
                perigo=True):
            return
        inventario.liberar([codigo], descartar=True)
        self.recarregar_inventario()
        self.mostrar_status(f"{codigo} retirado de circulação.")

    # ── Arrastar-e-soltar ────────────────────────────────────────────────

    def dragEnterEvent(self, e):  # noqa: N802 - assinatura do Qt
        # A zona é o alvo declarado, mas soltar em qualquer canto da tela
        # continua valendo: quem chega com o celular na mão não mira.
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):  # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):  # noqa: N802
        caminhos = [u.toLocalFile() for u in e.mimeData().urls()
                    if u.toLocalFile()]
        e.acceptProposedAction()
        if caminhos:
            self._soltou_fotos(caminhos)

    # ── API da janela principal ──────────────────────────────────────────

    def mostrar_status(self, msg: str, erro: bool = False) -> None:
        """Repassa o recado para a tela que hospeda este bloco."""
        self.aviso.emit(msg or "", bool(erro))

    def setups(self) -> list[capa_dados.Setup]:
        """Os posicionamentos como estão na tela.

        Aba aberta e não usada não entra: ela consumiria uma das metades da
        folha 2 para não dizer nada, e sobreviveria no cadastro como um
        posicionamento que nunca existiu.
        """
        out = []
        for i, aba in enumerate(self._setups, start=1):
            setup = capa_dados.Setup(
                nome=aba["nome"].text().strip() or f"POSICIONAMENTO {i}",
                fotos=[f for f in aba["fotos"] if f],
                acessorios=aba["acessorios"].toPlainText(),
                preparo={c: w.currentText().strip()
                         for c, w in aba["preparo"].items()},
            )
            if _tem_conteudo(setup):
                out.append(setup)
        return out

    def carregar(self, setups) -> None:
        """Repõe as abas a partir de uma lista de setups.

        Remover sempre a aba 0 esvazia só os posicionamentos: a do imobilizador
        é a última e vai recuando conforme as outras saem.
        """
        while self._setups:
            self.abas.removeTab(0)
            self._setups.pop(0)["pagina"].deleteLater()
        self._i_setup = 0
        for s in (setups or [capa_dados.Setup()]):
            self._nova_aba_setup(s)
        self._atualizar_botoes()

    def definir_paciente(self, registro: str) -> None:
        """Quem esta sendo cadastrado — o inventario usa para reconhecer o que
        ja e dele (ver ``recarregar_inventario``)."""
        novo = str(registro or "").strip()
        if novo == self._registro:
            return
        self._registro = novo
        self.recarregar_inventario()

    def tem_fotos(self) -> bool:
        return any(f for aba in self._setups for f in aba["fotos"])

    def limpar(self) -> None:
        self.carregar([])
        self.recarregar_inventario()

    def _atualizar_botoes(self, *_) -> None:
        # O "+" apaga no teto: um botão que aceita e depois avisa que não deu é
        # pior que um botão apagado com o motivo no tooltip.
        no_teto = len(self._setups) >= capa_pdf.MAX_SETUPS
        self.btn_add_setup.setEnabled(not no_teto)
        self.btn_add_setup.setToolTip(
            f"A folha 2 comporta {capa_pdf.MAX_SETUPS} posicionamentos"
            if no_teto else "")
        self.btn_del_setup.setEnabled(len(self._setups) > 1)
        self._avisar_setups()
        self.mudou.emit()

    def _folha_dica(self) -> str:
        """Cor da dica pelo TIPO da mensagem, lida na hora — é esta a receita
        que o ``pintar`` refaz a cada troca de dia↔noite.

        A receita registrada era o cinza FIXO, e o âmbar do alerta ia direto
        por ``setStyleSheet``: na troca de modo o ouvinte reaplicava o cinza, e
        o "os demais não serão impressos" perdia a cor com o aviso ainda de pé.
        """
        cor = st.AMBAR if self._dica_alerta else st.TEXTO_APAGADO
        return f"color:{cor}; font-size:10.5px;"

    def _pintar_dica(self) -> None:
        self.lbl_dica.setStyleSheet(self._folha_dica())

    def _avisar_setups(self) -> None:
        """Diz quantos posicionamentos saem impressos — e o que nao cabe.

        A folha 2 comporta ``capa_pdf.MAX_SETUPS``. Um a mais seria descartado
        por ``capa_pdf.setups_impressos`` sem nada na tela dizendo isso.
        """
        n = len(self._setups)
        cabem = capa_pdf.fotos_impressas(n)
        sobrando = max((sum(1 for f in a["fotos"] if f) - cabem
                        for a in self._setups), default=0)
        if n > capa_pdf.MAX_SETUPS:
            pass          # o aviso dos setups, abaixo, é o mais grave
        elif sobrando > 0:
            # Cada posicionamento a mais divide a faixa: com três, sobram dois
            # quadros para cada, e a terceira foto de cada um deixa de sair. Sem
            # este aviso isso só apareceria com a folha já impressa.
            self.lbl_dica.setText(
                f"⚠ Com {n} posicionamentos a folha imprime {cabem} fotos de "
                "cada — as demais ficam só no cadastro.")
            self._dica_alerta = True; self._pintar_dica()
            return
        if n <= 1:
            self.lbl_dica.setText(
                f"Até {MAX_FOTOS} fotos. Clique numa foto para removê-la.")
            self._dica_alerta = False; self._pintar_dica()
        elif n <= capa_pdf.MAX_SETUPS:
            self.lbl_dica.setText(
                f"{n} posicionamentos — a folha 2 imprime {cabem} fotos de cada.")
            self._dica_alerta = False; self._pintar_dica()
        else:
            self.lbl_dica.setText(
                f"⚠ {n} posicionamentos, mas só {capa_pdf.MAX_SETUPS} cabem na "
                "folha — os demais não serão impressos.")
            self._dica_alerta = True; self._pintar_dica()


class _DialogoNota(ui.Dialogo):
    """Cria ou edita uma nota da biblioteca.

    Mesmos campos do setup, e de propósito: quem edita a nota está descrevendo o
    mesmo objeto que vai aplicar depois, e um formulário diferente obrigaria a
    traduzir de cabeça.
    """

    def __init__(self, nota: "notas_setup.Nota", titulo: str, parent=None):
        super().__init__(titulo, parent)
        self.setMinimumWidth(600)
        # A receita REPETE o fundo do ``ui.Dialogo``: ``estilo.pintar`` chama
        # ``setStyleSheet``, que substitui a folha inteira — pintar só a regra
        # do QLabel apagaria o fundo herdado e a janela voltaria ao cinza do
        # sistema.
        st.pintar(self, lambda: f"QDialog{{background:{st.FUNDO_TELA};}}"
                           f"QLabel{{color:{st.TEXTO_FRACO}; font-size:11px;}}")
        lay = self.corpo
        lay.setSpacing(8)

        grade = QGridLayout()
        grade.setHorizontalSpacing(10)
        self.f_nome = QLineEdit(nota.nome)
        st.pintar(self.f_nome, lambda: ui.CAMPO)
        self.f_nome.setMinimumHeight(28)
        grade.addWidget(QLabel("Nome"), 0, 0)
        grade.addWidget(self.f_nome, 0, 1)
        lay.addLayout(grade)

        lay.addWidget(QLabel("Acessórios — um por linha"))
        self.f_acessorios = QPlainTextEdit(nota.acessorios)
        st.pintar(self.f_acessorios, lambda: ui.CAMPO)
        self.f_acessorios.setFixedHeight(120)
        lay.addWidget(self.f_acessorios)

        lay.addWidget(QLabel("Preparo"))
        prep = QHBoxLayout()
        self._preparo = {}
        for col in capa_pdf.COLUNAS_PREPARO:
            caixa = QVBoxLayout()
            caixa.setSpacing(2)
            # ``ui.escolha`` e não um QComboBox cru: é dele que vem a seta (ver
            # ``ui.Escolha``), e são os mesmos campos da aba de posicionamento.
            cmb = ui.escolha(capa_pdf.OPCOES_PREPARO.get(col, (capa_pdf.VAZIO,)),
                             editavel=True)
            cmb.setCurrentText(nota.preparo.get(col) or capa_pdf.VAZIO)
            rot = QLabel(col)
            st.pintar(rot, lambda: f"color:{st.TEXTO_FRACO}; font-size:10px;")
            caixa.addWidget(rot)
            caixa.addWidget(cmb)
            prep.addLayout(caixa)
            self._preparo[col] = cmb
        lay.addLayout(prep)

        self.chk_modelo = ui.escolha()
        self.chk_modelo.addItem("Modelo da biblioteca (serve para qualquer paciente)",
                                True)
        self.chk_modelo.addItem("Só deste paciente", False)
        self.chk_modelo.setCurrentIndex(0 if nota.modelo else 1)
        lay.addWidget(self.chk_modelo)

        # O ``QDialogButtonBox`` desenhava dois botões de peso IGUAL: nada na
        # tela dizia qual continua o trabalho. ``rodape`` dá o sólido ao
        # "Guardar" e o Enter junto — que aqui não existia.
        self.rodape("Guardar")

    def nota(self) -> "notas_setup.Nota":
        return notas_setup.Nota(
            nome=self.f_nome.text().strip(),
            acessorios=self.f_acessorios.toPlainText(),
            preparo={c: w.currentText().strip() for c, w in self._preparo.items()},
            modelo=bool(self.chk_modelo.currentData()))
