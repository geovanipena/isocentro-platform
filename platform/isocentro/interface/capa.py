"""Tela **Capa**: a Ficha de Tratamento, do posicionamento à impressão.

Uma tela só, porque é um documento só. O que o dosimetrista preenche ao sair da
tomografia — fotos do setup, nota de posicionamento, preparo, imobilizador — É a
folha 2 da capa; tê-lo numa tela à parte obrigava a preencher a mesma coisa duas
vezes, com a chance de as duas versões discordarem.

Os blocos se preenchem em momentos diferentes, e tudo bem:

* **na tomografia**, o dosimetrista escolhe o paciente e registra o
  posicionamento — não há plano nem prescrição aprovada ainda;
* **depois**, com o caso carregado na bancada, a identificação, o curso e as
  prescrições chegam dos relatórios e a capa fecha.

A caixa da **enfermagem** (alertas, dias alternados, planos de cuidado) não
aparece aqui: ela é preenchida à mão, no papel, depois de impressa. Continua
saindo no PDF, em branco, como sempre saiu.

Todo campo automático é editável. O relatório é um retrato do dia em que foi
exportado, e quem monta a ficha sabe coisas que ele ainda não sabe. O que o
programa não pode fazer é inventar: campo sem fonte nasce vazio, e a lista de
conferência no topo diz o que ele não conseguiu confirmar.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPlainTextEdit,
                             QPushButton, QScrollArea, QVBoxLayout, QWidget)

from isocentro.banco import capa_dados
from isocentro.papel import capa_pdf
from isocentro.dados import correcoes
from isocentro.interface import estilo as st
from isocentro.dados import inventario
from isocentro.interface import posicionamento
from isocentro.interface import simulacao
from isocentro.interface import ui

# Quantas linhas da busca de paciente aparecem de uma vez. São treze mil no
# relatório — mostrar todas trava a rolagem e não ajuda ninguém a escolher.
_MAX_RESULTADOS = 60

# O tamanho da coluna de onde vem a nota da prescrição (``DimPrescription.Notes``,
# ``VDT_STRING1024`` — ver ``capa_db._SQL_NOTAS``). A tela não deixa passar
# disso: nota editada maior que a do sistema seria uma capa dizendo o que o
# ARIA não comporta.
MAX_CARACTERES_NOTA = 1024

# A mesma tela em dois momentos do caso. Na TOMOGRAFIA não existe curso
# aprovado nem prescrição — o caso ainda não foi calculado, nem a TC importada
# —, e mostrar esses campos vazios faz a tela parecer um documento incompleto em
# vez do cadastro simples que ela é naquela hora.
SIMULACAO = "simulacao"
COMPLETA = "completa"

# Abaixo desta largura a tela volta a ser uma coluna só. Duas colunas de 400 px
# espremem a foto do setup de volta ao tamanho de selo — e uma foto que não se
# consegue conferir não tem por que ocupar espaço na tela.
LARGURA_DUAS_COLUNAS = 1180


@dataclass
class Importado:
    """O que a pasta do paciente rendeu — para a janela contar em uma frase."""
    fotos: int = 0
    notas: int = 0           # quantas notas existem na pasta
    nota_usada: str = ""     # qual delas entrou
    preparo: int = 0         # quantas colunas de preparo a nota preencheu
    da_simulacao: bool = False   # veio do cadastro da simulação
    preservado: bool = False     # achou, mas a tela já tinha posicionamento

    def achou(self) -> bool:
        return bool(self.fotos or self.nota_usada or self.preservado)

    def resumo(self) -> str:
        partes = []
        if self.fotos:
            partes.append(f"{self.fotos} foto(s)")
        if self.nota_usada:
            campos = f", {self.preparo} campo(s) de preparo" if self.preparo else ""
            partes.append(f"a nota {self.nota_usada}{campos}")
        if self.preservado:
            # Achou e recusou-se a sobrescrever: dizer "nada encontrado" manda
            # a pessoa procurar um arquivo que está bem ali.
            return ("há posicionamento arquivado, mas a tela já tem um montado "
                    "— limpe o posicionamento para trazer o da pasta")
        texto = " e ".join(partes)
        if self.da_simulacao:
            texto += " — do cadastro da simulação"
        # Nota sobrando é um segundo setup que ninguém pediu para esconder.
        if self.notas > 1:
            texto += (f" — há {self.notas} notas na pasta, confira se a certa "
                      "foi a usada")
        return texto

# As três respostas que a capa aceita. "Outro" existe para o caso em que o
# sexo não é F nem M: escolhê-lo é uma AFIRMAÇÃO, e por isso a faixa do nome sai
# neutra sem a tela reclamar — diferente de deixar em branco, que é ausência de
# resposta e continua sendo pendência.
SEXOS = ("Feminino", "Masculino", "Outro")


def normalizar_sexo(texto: str) -> str:
    """O que o relatório trouxe → uma das opções de :data:`SEXOS` (ou "").

    A coluna do relatório vem escrita de várias formas ("F", "FEM", "Feminino"),
    e o seletor só mostra as três. Sem esta tradução, um "F" legítimo cairia em
    branco e a tela pediria para preencher o que já estava preenchido.

    O que NÃO se reconhece volta VAZIO, nunca "Outro". "Outro" é a resposta de
    uma pessoa que olhou o caso e afirmou; traduzir "NÃO INFORMADO", "I" ou "-"
    para ele transformava a ausência de dado numa afirmação — e ainda apagava a
    pendência, porque "Outro" não acende aviso. A capa sairia dizendo "Outro"
    como se alguém tivesse respondido.
    """
    t = str(texto or "").strip().upper()
    # "Outro" volta como veio: é resposta gravada (correção de cadastro), não
    # valor a interpretar. Sem este caso, reabrir o paciente apagava a escolha.
    if t == "OUTRO":
        return "Outro"
    if t.startswith("F"):
        return "Feminino"
    if t.startswith("M"):
        return "Masculino"
    return ""


# Conjuntos de acessórios que o relatório institucional oferece prontos, na
# grafia dele. Aparecem como sugestão na caixa; o texto continua livre, porque a
# nota do técnico costuma trazer as medidas (inclinação, altura do braço) que
# nenhum conjunto padrão cobre.
ACESSORIOS_PADRAO = (
    "Travesseiro; Apoio de pé; Apoio de joelho",
    "Rampa de Mama; Apoio de joelho",
    "Rampa de tórax; Apoio de joelho",
    "Máscara Longa; Base (ver setup note); Apoio de joelho",
    "Máscara Curta; Base (ver setup note); Apoio de joelho",
)


class PainelCapa(QWidget):
    """A tela da capa. Emite pedidos; a janela principal os executa."""

    pedir_visualizacao = Signal()
    pedir_impressao = Signal()
    pedir_salvar = Signal()
    cadastrar_simulacao = Signal()  # grava a pasta do posicionamento
    paciente_escolhido = Signal()   # veio da busca, não da bancada
    # "É ESTE": duplo clique ou Enter na lista. Separado do
    # ``paciente_escolhido`` porque aquele dispara ao NAVEGAR — a lista usa
    # ``itemSelectionChanged``, e andar com as setas conta como escolher (é por
    # isso que a busca já tinha 260 ms de espera antes de ler o banco).
    #
    # Carregar a pasta DICOM de quem o cursor pousou, ou abrir o modal
    # "Substituir paciente atual?" a cada nome, é o que aconteceria pendurando
    # a sincronia no outro sinal — achado na revisão de 04/09/2026.
    paciente_confirmado = Signal(str, str)   # registro, nome
    # "Fechar paciente" descarrega a Capa; quem fecha as OUTRAS telas é a
    # janela, que é dona delas. Sem este aviso, o paciente fechado aqui
    # continuava inteiro na Ficha Virtual ao lado.
    paciente_fechado = Signal()
    correcao_salva = Signal(str, dict)   # (registro, campos gravados)
    pasta_escolhida = Signal(str)   # apontaram uma pasta de paciente aqui
    # A capa na tela mudou. A ficha técnica EMBUTE a capa na primeira página,
    # então a prévia já gerada nas outras telas envelhece no instante em que
    # alguém corrige um campo aqui — e o botão Visualização abriria o PDF com a
    # capa velha, sem nada indicando isso.
    mudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._capa = capa_pdf.Capa()
        self._opcoes: list = []          # prescrições oferecidas para escolha
        self._pasta_paciente = ""
        # Avisos da busca nos relatórios; os da própria tela entram por cima
        # (ver ``_repintar_avisos``).
        self._avisos_externos: list[str] = []
        self._dos_relatorios = False   # ver montada_dos_relatorios
        # (registro, nome) normalizados de quem são as fotos de posicionamento
        # na tela. Ver ``posicionamento_e_de``.
        self._dono_posicionamento: tuple[str, str] = ("", "")
        # O posicionamento na tela já está arquivado (cadastrado ou lido de uma
        # pasta)? Só o que NÃO está se perde ao ser descartado.
        self._posicionamento_arquivado = False
        self._id_aberta = False        # painel de correção da identificação
        # O que o relatório trouxe e o que já estava corrigido — o botão Salvar
        # compara os dois para gravar só a diferença (ver ``_salvar_correcoes``).
        self._do_relatorio: dict = {}
        self._corrigidos: list = []
        self._usuario = ""             # quem está logado (ver ``definir_usuario``)
        # Busca de paciente — só aparece quando não há caso carregado na
        # bancada, que é o caminho de quem chega da tomografia.
        self._pacientes: list = []
        self._escolhido = None
        # A busca é uma opção nesta tela? Só no fluxo da tomografia: com o caso
        # aberto na bancada, quem é o paciente já está decidido.
        self._busca_permitida = False
        # O modo nasce definido: a montagem das colunas já o consulta para saber
        # quanto vale cada uma (ver _arrumar_colunas).
        self._modo = COMPLETA

        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(0)

        # ── Faixa de status e conferência ────────────────────────────────
        topo = QWidget()
        st.pintar(topo, lambda: f"background:{st.FUNDO_CARTAO};")
        lay_topo = QVBoxLayout(topo)
        lay_topo.setContentsMargins(14, 8, 14, 8)
        lay_topo.setSpacing(6)

        linha_titulo = QHBoxLayout()
        self.lbl_titulo = QLabel("Capa de Tratamento")
        st.pintar(self.lbl_titulo, lambda: (
            f"font-size:16px; font-weight:bold; color:{st.AZUL_CLARO};"))
        linha_titulo.addWidget(self.lbl_titulo)
        linha_titulo.addSpacing(14)
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self._status_erro = False
        st.pintar(self.lbl_status, self._folha_status)
        linha_titulo.addWidget(self.lbl_status, 1)
        lay_topo.addLayout(linha_titulo)

        self.lista_avisos = QListWidget()
        self.lista_avisos.setFocusPolicy(Qt.NoFocus)
        self.lista_avisos.setSelectionMode(QListWidget.NoSelection)
        self.lista_avisos.setWordWrap(True)
        self.lista_avisos.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista_avisos.setMaximumHeight(84)
        st.pintar(self.lista_avisos, lambda: ui.LISTA)
        self.lista_avisos.hide()
        lay_topo.addWidget(self.lista_avisos)
        fora.addWidget(topo)

        _div = QFrame()
        _div.setFrameShape(QFrame.HLine)
        st.pintar(_div, lambda: f"background:{st.AZUL}; max-height:1px;")
        fora.addWidget(_div)

        # ── Formulário rolável ───────────────────────────────────────────
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        st.pintar(rolagem, lambda: f"background:{st.FUNDO_TELA};")
        miolo = QWidget()
        st.pintar(miolo, lambda: f"background:{st.FUNDO_TELA};")
        colunas = QHBoxLayout(miolo)
        colunas.setContentsMargins(18, 16, 18, 16)
        colunas.setSpacing(14)
        # Cada coluna é uma pilha própria. Numa grade as linhas seriam
        # partilhadas, e o cartão alto do posicionamento empurraria a
        # identificação para o meio da tela por não ter par à altura dele.
        self._col_esq, self._lay_esq = self._coluna()
        self._col_dir, self._lay_dir = self._coluna()
        self._colunas = colunas
        colunas.addWidget(self._col_esq)
        colunas.addWidget(self._col_dir)

        cartao_busca = self._bloco_busca()
        cartao_id = self._grupo_identificacao()
        self.cartao_curso = self._grupo_curso()
        self.cartao_presc = self._grupo_prescricoes()
        # O posicionamento é a folha 2, e é o que o dosimetrista preenche na TC.
        self.posicionamento = posicionamento.PainelPosicionamento()
        self.posicionamento.mudou.connect(self._posicionamento_mudou)
        self.posicionamento.aviso.connect(self.mostrar_status)

        # Duas colunas: à esquerda o DOCUMENTO — de quem é, que curso, que
        # prescrição —, à direita o que se OLHA: as fotos do setup, a nota e o
        # imobilizador. Numa coluna só, os cartões esticavam por mil e
        # quinhentos pixels com o conteúdo agarrado à esquerda, e as fotos —
        # a razão de a tela existir para quem vem da tomografia — só apareciam
        # rolando a página. Ver ``_arrumar_colunas``.
        self._esquerda = (cartao_busca, cartao_id, self.cartao_curso,
                          self.cartao_presc)
        self._direita = (self.posicionamento,)
        self._arranjo: Optional[tuple] = None
        self._duas_colunas = True
        self._arrumar_colunas(True)
        rolagem.setWidget(miolo)
        fora.addWidget(rolagem, 1)

        # ── Trilha de ações ──────────────────────────────────────────────
        rodape, acoes = ui.faixa()
        # Aqui ficava um rodapé dizendo de onde vinham o banco e as simulações.
        # Saiu: é CONFIGURAÇÃO, e está em Configurações → Serviço, onde se vai
        # de propósito. Repetido nesta tela virava linha fixa que ninguém lê —
        # e linha que ninguém lê é onde o recado importante se perde.
        #
        # O que precisa aparecer AQUI é quando a capa NÃO veio do sistema: isso
        # continua, como aviso em primeiro lugar na lista (EMERGÊNCIA / ÚLTIMO
        # RECURSO), com a data do dado. Aviso é para o que muda o que a pessoa
        # faz; estado permanente não é aviso.
        acoes.addStretch(1)

        # Os secundários ficam discretos e a IMPRESSÃO — a ação final — é a
        # única preenchida: seis botões verdes lado a lado não diziam qual era o
        # caminho, só que tudo era importante.
        # "Fechar paciente" é o que DESCARREGA. O "Trocar paciente" do
        # cabeçalho só reabre a busca e deixa o atual na tela de propósito (ver
        # ``_trocar_paciente``): com treze mil nomes a um clique, descartar ali
        # trocaria o paciente por engano com as fotos da tomografia na tela.
        # Faltava a porta que fecha de verdade — é esta.
        self.btn_fechar = ui.botao("✕  Fechar paciente")
        self.btn_fotos = ui.botao("📂  Abrir pasta do paciente")
        # Cadastrar a simulação é a ação de quem vem da TOMOGRAFIA; imprimir é a
        # de quem vem da bancada. As duas ficam no mesmo rodapé porque é a mesma
        # capa — o que muda é o momento.
        self.btn_cadastrar = ui.botao("📌  Cadastrar Simulação")
        self.btn_visualizar = ui.botao("👁  Visualizar")
        self.btn_salvar = ui.botao("💾  Salvar PDF")
        self.btn_imprimir = ui.botao("🖨  Impressão")
        self.btn_imprimir.setMinimumWidth(150)
        # UM sólido por tela, e ele ANDA COM O TRABALHO: na tomografia o passo
        # que não se desfaz é cadastrar a simulação (grava a pasta no disco e
        # marca o imobilizador no inventário); com a capa montada, é imprimir.
        # Deixar "Impressão" sólido durante o cadastro apontava para uma ação
        # que nem estava na tela.
        #
        # Um registro só por botão, reaplicado à mão em ``_pesar_botoes``:
        # ``pintar`` guarda um ouvinte por chamada, e chamá-lo a cada troca de
        # modo empilharia um por troca (ver as armadilhas no CLAUDE.md).
        for btn in (self.btn_cadastrar, self.btn_imprimir):
            st.pintar(btn, lambda b=btn: (st.btn_solido(12.5)
                                          if b is self._botao_do_passo()
                                          else ui._btn_discreto()))
        for btn in (self.btn_fechar, self.btn_fotos, self.btn_cadastrar,
                    self.btn_visualizar, self.btn_salvar, self.btn_imprimir):
            acoes.addWidget(btn)
        fora.addWidget(rodape)

        self.btn_fechar.clicked.connect(self._fechar_paciente)
        self.btn_fotos.clicked.connect(self._escolher_fotos)
        self.btn_cadastrar.clicked.connect(self.cadastrar_simulacao.emit)
        self.btn_visualizar.clicked.connect(self.pedir_visualizacao.emit)
        self.btn_salvar.clicked.connect(self.pedir_salvar.emit)
        self.btn_imprimir.clicked.connect(self.pedir_impressao.emit)

        self.definir_modo(SIMULACAO)
        self.habilitar(False)

    def _botao_do_passo(self):
        """Qual botão carrega o peso agora — ver o laço de ``pintar`` acima."""
        return (self.btn_cadastrar if self._modo == SIMULACAO
                else self.btn_imprimir)

    def _pesar_botoes(self) -> None:
        """Reaplica as folhas dos dois candidatos a sólido."""
        for btn in (self.btn_cadastrar, self.btn_imprimir):
            btn.setStyleSheet(st.btn_solido(12.5)
                              if btn is self._botao_do_passo()
                              else ui._btn_discreto())

    # ── As duas colunas ──────────────────────────────────────────────────

    @staticmethod
    def _coluna() -> tuple:
        """Uma pilha de cartões, com o vazio empurrado para o rodapé."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addStretch(1)
        return w, lay

    def _arrumar_colunas(self, duas: bool) -> None:
        """Reparte os cartões em duas colunas — ou empilha tudo numa só.

        A janela estreita (ou o notebook da sala de tomografia) não comporta
        duas colunas: espremer o cartão do posicionamento devolve a foto ao
        tamanho de selo, que é o problema que as colunas vieram resolver.
        Então a tela troca de arranjo com a largura, e nada é recriado — os
        mesmos cartões mudam de coluna, preservando o que já foi digitado
        neles.
        """
        if (duas, self._modo) == self._arranjo:
            return
        self._arranjo = (duas, self._modo)
        self._duas_colunas = duas
        for lay in (self._lay_esq, self._lay_dir):
            while lay.count() > 1:     # o esticador do fim fica
                lay.takeAt(0)
        # ``insertWidget`` reparenta preservando quem foi escondido de propósito
        # (o cartão que o modo Simulação tirou de cena continua fora dela).
        for destino, cartoes in ((self._lay_esq, self._esquerda),
                                 (self._lay_dir if duas else self._lay_esq,
                                  self._direita)):
            for w in cartoes:
                destino.insertWidget(destino.count() - 1, w)
        self._col_dir.setVisible(duas)
        # A esquerda é o documento (curso e três prescrições) e a direita são
        # as fotos; nem uma nem outra deve engolir a companheira.
        self._colunas.setStretch(0, 5)
        self._colunas.setStretch(1, 4)

    def _cabem_duas_colunas(self) -> bool:
        """Duas colunas só quando há duas colunas de conteúdo.

        No cadastro da simulação não há: curso e prescrições ainda não existem,
        e a identificação sozinha é um bloco baixo — a coluna da esquerda
        acabava na primeira quarta parte da tela e o resto ficava vazio até o
        rodapé. Empilhado, o cartão da montagem pega a largura inteira e as
        fotos com ele.
        """
        return (self.width() >= LARGURA_DUAS_COLUNAS
                and self._modo == COMPLETA)

    def resizeEvent(self, e):  # noqa: N802 - assinatura do Qt
        super().resizeEvent(e)
        self._arrumar_colunas(self._cabem_duas_colunas())

    # ── Montagem dos grupos ──────────────────────────────────────────────

    # As peças visuais vêm todas do :mod:`ui` — ver o cabeçalho daquele módulo
    # para o porquê de rótulo em cima em vez de coluna de rótulos.
    def _campo(self, largura: int = 0) -> QLineEdit:
        return ui.entrada(largura)

    def _area(self, linhas: int = 3) -> QPlainTextEdit:
        return ui.area(linhas)

    def _rotulo(self, texto: str) -> QLabel:
        return ui.rotulo(texto)

    def _grupo_solto(self, titulo: str, passo: str = "") -> tuple:
        """Como ``_grupo``, mas a grade NÃO entra no cartão automaticamente.

        Quem chama decide onde ela vai — na identificação ela mora dentro de um
        painel que abre e fecha.
        """
        cartao = ui.Cartao(titulo, passo)
        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(9)
        return cartao, grade

    def _grupo(self, titulo: str, passo: str = "") -> tuple:
        """Um cartão com uma grade dentro — a grade continua sendo o miolo.

        Trocar o ``QGroupBox`` pelo cartão muda só o invólucro: cada bloco
        segue montando os seus campos na grade que recebe aqui.
        """
        cartao = ui.Cartao(titulo, passo)
        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(9)
        cartao.corpo.addLayout(grade)
        return cartao, grade

    def _grupo_identificacao(self) -> QGroupBox:
        g, grade = self._grupo_solto("Identificação", "1")
        # A identidade em destaque, acima dos campos: é o que se confere de
        # relance antes de olhar qualquer outra coisa da capa.
        self.cabecalho = ui.CabecalhoPaciente()
        g.corpo.insertWidget(1, self.cabecalho)
        self.f_nome = self._campo()
        self.f_registro = self._campo(140)
        self.f_nascimento = self._campo(110)
        # Seletor, não caixa de texto: são três respostas possíveis, e é o
        # valor que escolhe a cor da faixa do nome na capa impressa.
        self.f_sexo = ui.escolha(SEXOS, largura=110)
        self.f_sexo.setCurrentIndex(-1)
        self.f_convenio = self._campo()
        self.f_contato = self._campo(160)
        self.f_medico = self._campo()
        self.f_maquina = self._campo()
        # Nome de gente sai na grafia do app, mesmo corrigido à mão aqui. Ao
        # SAIR do campo, não a cada tecla: reformatar durante a digitação move o
        # cursor e briga com quem escreve.
        for _de_pessoa in (self.f_nome, self.f_medico):
            _de_pessoa.editingFinished.connect(
                lambda w=_de_pessoa: w.setText(
                    capa_dados.como_nome_proprio(w.text().strip())))
        # A foto 3×4 vive no cabeçalho de identidade.
        self.lbl_foto = self.cabecalho.retrato

        # A identificação SE LÊ nos chips do cabeçalho; a grade de campos é
        # para corrigir, e corrigir é o caso raro. Deixá-la sempre aberta punha
        # oito caixas de texto na frente de quem só queria conferir quem era o
        # paciente — e é justamente esse dado que a tela existe para mostrar.
        for i, (rot, w) in enumerate((
                ("Nome", self.f_nome), ("Registro", self.f_registro),
                ("Nascimento", self.f_nascimento), ("Sexo", self.f_sexo),
                ("Convênio", self.f_convenio), ("Contato", self.f_contato),
                ("Médico assistente", self.f_medico),
                ("Máquina", self.f_maquina))):
            grade.addWidget(ui.campo(rot, w), i // 3, i % 3)
        for c in range(3):
            grade.setColumnStretch(c, 1)
            
        self.caixa_edicao = QWidget()
        self.caixa_edicao.setLayout(grade)
        self.caixa_edicao.setVisible(False)
        g.corpo.addWidget(self.caixa_edicao)

        # Mais altos que o botão discreto padrão: eles moram na faixa de
        # identidade, que cresceu, e um botão de 28 px ao lado de um nome de
        # 24 px lê-se como legenda em vez de ação.
        self.btn_editar_id = ui.botao("✎  Corrigir", altura=36)
        self.btn_editar_id.setToolTip(
            "Abre os campos para corrigir o que o relatório trouxe")
        self.btn_editar_id.clicked.connect(self._alternar_edicao_id)
        self.cabecalho.canto.addWidget(self.btn_editar_id)

        # Corrigir muda a capa DESTA impressão; salvar faz a correção durar.
        # Sem ele, o relatório reescrevia o conserto na próxima abertura e
        # alguém corrigia o mesmo sexo toda vez que o paciente voltava.
        self.btn_salvar_id = ui.botao("💾  Salvar correção", altura=36)
        self.btn_salvar_id.setToolTip(
            "Guarda o que foi corrigido aqui para este paciente — vale nas "
            "próximas capas, em qualquer estação")
        self.btn_salvar_id.clicked.connect(self._salvar_correcoes)
        self.btn_salvar_id.setVisible(False)
        self.cabecalho.canto.addWidget(self.btn_salvar_id)

        # A saída de volta para a busca, que sai de cena assim que o paciente é
        # carregado. Fica AQUI, no cabeçalho de quem é o paciente, porque é a
        # pergunta que ele responde — "não é este?".
        self.btn_trocar = ui.botao("⇄  Trocar paciente", altura=36)
        self.btn_trocar.setToolTip("Volta à busca; o paciente atual continua "
                                   "na tela até você escolher outro")
        self.btn_trocar.clicked.connect(self._trocar_paciente)
        self.btn_trocar.setVisible(False)
        self.cabecalho.canto.addWidget(self.btn_trocar)

        # Editar tem de repintar os chips: dois retratos do mesmo paciente
        # discordando na mesma tela é pior que um só desatualizado.
        for campo in (self.f_nome, self.f_registro, self.f_nascimento,
                      self.f_convenio, self.f_contato,
                      self.f_medico, self.f_maquina):
            campo.textChanged.connect(self._id_mudou)
        self.f_sexo.currentTextChanged.connect(self._id_mudou)
        return g

    def _alternar_edicao_id(self) -> None:
        """Abre/fecha os campos de correção.

        O estado é guardado aqui em vez de perguntado ao Qt: ``isVisible`` de um
        filho responde sobre a TELA estar aberta, não sobre o painel estar
        expandido — com a Capa em outro modo o botão nunca fechava.
        """
        self._id_aberta = not self._id_aberta
        self.caixa_edicao.setVisible(self._id_aberta)
        self.btn_salvar_id.setVisible(self._id_aberta)
        self.btn_editar_id.setText(
            "✕  Fechar" if self._id_aberta else "✎  Corrigir")

    def _salvar_correcoes(self) -> None:
        """Grava para durar o que diverge do relatório.

        Só o que DIVERGE: guardar a linha inteira transformaria a correção num
        segundo cadastro, que envelheceria em silêncio — o convênio mudaria na
        fonte e a capa seguiria imprimindo o de um ano atrás porque alguém, um
        dia, corrigiu o sexo.

        Campo devolvido ao valor do relatório APAGA a correção anterior: é
        assim que se desfaz um conserto errado.
        """
        atual = self._coletar_identificacao()
        registro = (atual.registro or "").strip()
        if not registro:
            self.mostrar_status(
                "Sem registro não dá para guardar a correção — é ele que diz "
                "de quem ela é.", erro=True)
            return
        mudou = {c: str(getattr(atual, c, "") or "").strip()
                 for c in correcoes.CAMPOS
                 if str(getattr(atual, c, "") or "").strip()
                 != self._do_relatorio.get(c, "")}
        # Devolvidos ao original: precisam ir com valor VAZIO, para apagar.
        for c in list(self._corrigidos):
            if c not in mudou:
                mudou[c] = ""
        if not mudou:
            self.mostrar_status("Nada diferente do relatório para guardar.")
            return
        try:
            gravados = correcoes.salvar(registro, mudou, self._usuario)
        except Exception as exc:  # noqa: BLE001
            self.mostrar_status(f"Não consegui guardar a correção: {exc}",
                                erro=True)
            return
        # ``_do_relatorio`` NÃO se mexe aqui: ele é o que o relatório trouxe, a
        # régua contra a qual se mede o que diverge, e vale enquanto este
        # paciente estiver na tela. Zerar o campo desfeito fazia a gravação
        # seguinte comparar o valor certo contra "" — e regravar o próprio valor
        # do relatório como correção permanente, que é exatamente o segundo
        # cadastro congelado que este módulo existe para não criar.
        self._corrigidos = list(gravados)
        self.correcao_salva.emit(registro, dict(gravados))
        quais = ", ".join(sorted(gravados)) or "nenhum campo"
        self.mostrar_status(
            f"Correção guardada para {registro}: {quais}. Vale nas próximas "
            "capas deste paciente.")

    def _definir_sexo(self, texto: str) -> None:
        """Põe o seletor no que o relatório trouxe — ou em BRANCO.

        ``setCurrentText("")`` num combo não editável não faz nada: o valor
        anterior fica, e o paciente novo herdava o sexo do anterior sem que a
        tela avisasse. Vazio tem de ser índice -1.
        """
        valor = normalizar_sexo(texto)
        if valor:
            self.f_sexo.setCurrentText(valor)
        else:
            self.f_sexo.setCurrentIndex(-1)

    def _id_mudou(self, *_) -> None:
        """Repinta os chips com o que está nos campos agora."""
        self._pintar_cabecalho(self._coletar_identificacao())
        self.mudou.emit()

    def _avisar_mudanca(self, *_) -> None:
        """Um campo do corpo mudou (curso, prescrição, posicionamento)."""
        self.mudou.emit()

    def _grupo_curso(self) -> QGroupBox:
        g, grade = self._grupo("Curso", "2")
        self.f_curso = self._campo()
        self.f_intencao = self._campo()
        self.f_data_aprov = self._campo(110)
        self.f_descricao = self._campo()
        self.f_cid = self._campo()
        for campo in (self.f_curso, self.f_intencao, self.f_data_aprov,
                      self.f_descricao, self.f_cid):
            campo.textChanged.connect(self._avisar_mudanca)
        grade.addWidget(ui.campo("Curso", self.f_curso), 0, 0)
        grade.addWidget(ui.campo("Intenção", self.f_intencao), 0, 1)
        grade.addWidget(ui.campo("Data de aprovação", self.f_data_aprov), 0, 2)
        grade.addWidget(ui.campo("Descrição do diagnóstico", self.f_descricao),
                        1, 0, 1, 2)
        grade.addWidget(ui.campo("CID", self.f_cid), 1, 2)
        for c in range(3):
            grade.setColumnStretch(c, 1)
        return g

    def _grupo_prescricoes(self) -> QGroupBox:
        """As prescrições aprovadas, uma por bloco de texto.

        Editar prescrição campo a campo daria uma tela dentro da tela, e o que
        se faz aqui é conferir e corrigir o que o relatório mandou — texto livre é
        o formato certo para isso. Cada linha do campo Volumes vira uma linha
        impressa, na ordem em que está.
        """
        g, grade = self._grupo("Prescrições aprovadas", "3")

        # Escolha, antes da edição. O relatório traz o histórico inteiro do
        # paciente — cursos de anos atrás inclusive —, e só três prescrições
        # cabem na folha. A lista mostra a data primeiro, que é o que distingue
        # o curso que está correndo do que já terminou.
        self.lbl_escolha = QLabel("")
        st.pintar(self.lbl_escolha, lambda: f"color:{st.TEXTO_FRACO}; font-size:11px;")
        grade.addWidget(self.lbl_escolha, 0, 0, 1, 2)

        self.lista_presc = QListWidget()
        st.pintar(self.lista_presc, lambda: ui.LISTA)
        self.lista_presc.setMaximumHeight(118)
        self.lista_presc.itemChanged.connect(self._escolha_mudou)
        self.lista_presc.hide()
        grade.addWidget(self.lista_presc, 1, 0, 1, 2)

        self.lay_blocos = QVBoxLayout()
        self.lay_blocos.setSpacing(8)
        self._widgets_blocos: list[dict] = []
        grade.addLayout(self.lay_blocos, 2, 0, 1, 2)

        linha = QHBoxLayout()
        self.btn_add_bloco = QPushButton("+  Prescrição")
        self.btn_del_bloco = QPushButton("−  Última")
        for b in (self.btn_add_bloco, self.btn_del_bloco):
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(26)
            st.pintar(b, lambda w=b: st.btn_contorno(11)
                      + "QPushButton{padding:4px 12px;}")
            linha.addWidget(b)
        linha.addStretch(1)
        grade.addLayout(linha, 3, 0, 1, 2)
        self.btn_add_bloco.clicked.connect(lambda: self._novo_bloco(capa_pdf.Bloco()))
        self.btn_del_bloco.clicked.connect(self._remover_bloco)
        return g

    def _montar_escolha(self, opcoes: list) -> None:
        """Pinta a lista de prescrições disponíveis, com a marcação de saída."""
        self._opcoes = list(opcoes)
        self.lista_presc.blockSignals(True)
        self.lista_presc.clear()
        for o in self._opcoes:
            item = QListWidgetItem(o.rotulo())
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if o.marcada else Qt.Unchecked)
            if not o.do_curso_atual:
                # Curso encerrado: continua na lista (reimpressão de capa antiga
                # é pedido real), mas apagado, para não competir com o atual.
                item.setForeground(QColor(st.TEXTO_APAGADO))
                item.setToolTip("De um curso anterior")
            self.lista_presc.addItem(item)
        self.lista_presc.blockSignals(False)
        # Uma prescrição só não é escolha nenhuma — a lista some e a tela volta
        # a ser o que era.
        muitas = len(self._opcoes) > 1
        self.lista_presc.setVisible(muitas)
        self.lbl_escolha.setVisible(muitas)
        if muitas:
            atuais = sum(1 for o in self._opcoes if o.do_curso_atual)
            self.lbl_escolha.setText(
                f"{len(self._opcoes)} prescrições aprovadas — {atuais} do curso "
                f"atual. Marque as que entram na capa (cabem "
                f"{capa_pdf.MAX_BLOCOS}).")

    def _escolha_mudou(self, _item=None) -> None:
        """Remonta os blocos editáveis a partir do que está marcado.

        Refaz do relatório em vez de tentar preservar o que já foi digitado: a
        escolha é o primeiro passo, e um bloco meio editado sobrevivendo à troca
        de prescrição seria pior do que refazer.
        """
        marcadas = []
        for i in range(self.lista_presc.count()):
            marcado = self.lista_presc.item(i).checkState() == Qt.Checked
            if i < len(self._opcoes):
                self._opcoes[i].marcada = marcado
                if marcado:
                    marcadas.append(self._opcoes[i])
        self._limpar_blocos()
        for o in marcadas[:capa_pdf.MAX_BLOCOS]:
            self._novo_bloco(o.bloco)
        # A data do cabeçalho acompanha a escolha (ver capa_pdf.de_resultado).
        datas = [o.data for o in marcadas if o.data]
        if datas:
            self.f_data_aprov.setText(capa_dados.data_curta(
                max(datas, key=capa_pdf._ordem_data)))
        sobra = len(marcadas) - capa_pdf.MAX_BLOCOS
        if sobra > 0:
            self.mostrar_status(
                f"{len(marcadas)} marcadas, mas só {capa_pdf.MAX_BLOCOS} cabem "
                "na folha — desmarque as que não entram.", erro=True)

    def _novo_bloco(self, bloco: capa_pdf.Bloco) -> None:
        caixa = QFrame()
        st.pintar(caixa, lambda: (
            f"QFrame{{border:1px solid {st.BORDA}; border-radius:6px;}}"))
        grade = QGridLayout(caixa)
        grade.setContentsMargins(8, 6, 8, 6)
        grade.setHorizontalSpacing(8)
        grade.setVerticalSpacing(4)
        campos = {
            "titulo": self._campo(),
            "aprovado_por": self._campo(190),
            "volumes": self._area(2),
            "frequencia": self._campo(),
            # Várias linhas: vinda do ARIA (``DimPrescription.Notes``) a nota
            # tem de três a sete. No campo de uma linha que era, as quebras
            # sumiam na edição e o PDF recebia tudo emendado.
            "notas": self._area(4),
        }
        campos["titulo"].setText(bloco.titulo)
        campos["aprovado_por"].setText(bloco.aprovado_por)
        campos["volumes"].setPlainText("\n".join(bloco.volumes))
        campos["frequencia"].setText(bloco.frequencia)
        campos["notas"].setPlainText(bloco.notas)
        contador = QLabel()
        contador.setWordWrap(True)
        contador.setMaximumWidth(110)
        contador._estado = ""
        # Um ouvinte só, registrado aqui; a cor muda por ``_estado`` e a folha
        # é reaplicada à mão (ver ``_nota_mudou``) — ``pintar`` a cada tecla
        # empilharia um ouvinte por tecla.
        st.pintar(contador, lambda: self._folha_contador(contador))
        rotulo_notas = QWidget()
        pilha = QVBoxLayout(rotulo_notas)
        pilha.setContentsMargins(0, 0, 0, 0)
        pilha.setSpacing(2)
        pilha.addWidget(self._rotulo("Notas"))
        pilha.addWidget(contador)
        pilha.addStretch(1)
        grade.addWidget(self._rotulo("Título"), 0, 0)
        grade.addWidget(campos["titulo"], 0, 1)
        grade.addWidget(self._rotulo("Aprovado por"), 0, 2)
        grade.addWidget(campos["aprovado_por"], 0, 3)
        # A nota mora na coluna direita, ao lado dos volumes e da frequência,
        # como no papel (``capa_pdf._NOTA_TOPO``): os volumes deixam de ocupar a
        # largura toda, e o quadro não cresce.
        grade.addWidget(self._rotulo("Volumes"), 1, 0)
        grade.addWidget(campos["volumes"], 1, 1)
        grade.addWidget(self._rotulo("Frequência"), 2, 0)
        grade.addWidget(campos["frequencia"], 2, 1)
        grade.addWidget(rotulo_notas, 1, 2, 2, 1)
        grade.addWidget(campos["notas"], 1, 3, 2, 1)
        campos["notas"]._anterior = campos["notas"].toPlainText()
        campos["notas"].textChanged.connect(
            lambda: self._nota_mudou(campos["notas"], contador))
        self._nota_mudou(campos["notas"], contador)
        grade.setColumnStretch(1, 3)
        grade.setColumnStretch(3, 2)
        self.lay_blocos.addWidget(caixa)
        self._widgets_blocos.append({"caixa": caixa, "contador": contador, **campos})

    def _nota_mudou(self, area: QPlainTextEdit, contador: QLabel) -> None:
        """Recusa a edição que passa do limite e atualiza o contador.

        Recusa, e não corta o fim: quem cola um parágrafo no MEIO da nota
        perderia as últimas linhas — justamente as que condicionam o tratamento
        — sem ver. Só a edição que AUMENTA o texto é recusada: uma nota que já
        chegou maior (correção antiga) pode ser encurtada até caber.
        """
        texto = area.toPlainText()
        anterior = getattr(area, "_anterior", "")
        if (len(texto) > MAX_CARACTERES_NOTA
                and len(texto) > len(anterior)):
            pos = area.textCursor().position() - (len(texto) - len(anterior))
            area.blockSignals(True)
            area.setPlainText(anterior)
            area.blockSignals(False)
            cursor = area.textCursor()
            cursor.setPosition(max(0, min(pos, len(anterior))))
            area.setTextCursor(cursor)
            self.mostrar_status(
                f"A nota passaria de {MAX_CARACTERES_NOTA} caracteres, o limite "
                "do sistema — o que foi digitado não entrou.", erro=True)
            texto = anterior
        area._anterior = texto
        n = len(texto)
        linhas = len(capa_pdf._linhas(texto))
        cabem = capa_pdf._MAX_LINHAS_NOTA
        partes = [f"{n}/{MAX_CARACTERES_NOTA}"] if n else []
        # A folha imprime as primeiras e anuncia o resto ("+ N linha(s)");
        # dizer aqui é para quem edita saber ANTES de imprimir.
        if linhas > cabem:
            partes.append(f"{linhas} linhas — {cabem} cabem na folha")
        contador._estado = ("vermelho" if n >= MAX_CARACTERES_NOTA
                            else "ambar" if linhas > cabem else "")
        contador.setText("\n".join(partes))
        contador.setVisible(bool(partes))
        contador.setStyleSheet(self._folha_contador(contador))

    @staticmethod
    def _folha_contador(contador: QLabel) -> str:
        cor = {"vermelho": st.VERMELHO, "ambar": st.AMBAR}.get(
            getattr(contador, "_estado", ""), st.TEXTO_APAGADO)
        # ``border:none``: a borda do quadro do bloco (``QFrame{...}``) desce
        # para todo QLabel dentro dele, e o contador saía encaixotado.
        return f"font-size:10.5px; color:{cor}; border:none;"

    def _remover_bloco(self) -> None:
        if not self._widgets_blocos:
            return
        w = self._widgets_blocos.pop()
        w["caixa"].setParent(None)
        w["caixa"].deleteLater()

    def _limpar_blocos(self) -> None:
        while self._widgets_blocos:
            self._remover_bloco()

    def _bloco_busca(self) -> ui.Cartao:
        """Escolher o paciente — o caminho de quem chega da tomografia.

        Só aparece quando não há caso carregado na bancada: com o DICOM aberto,
        o paciente já está definido e uma busca ali seria um convite a trocá-lo
        por engano.
        """
        cartao = ui.Cartao("Paciente")
        self.busca = ui.entrada()
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(self._filtrar)
        cartao.corpo.addWidget(self.busca)

        self.lista_pac = QListWidget()
        st.pintar(self.lista_pac, lambda: ui.LISTA)
        self.lista_pac.setMaximumHeight(118)
        self.lista_pac.itemSelectionChanged.connect(self._escolher_paciente)
        # ``itemActivated`` cobre o duplo clique E o Enter — os dois gestos que
        # significam "é este", em vez de "estou olhando este".
        self.lista_pac.itemActivated.connect(self._confirmar_paciente)
        self.lista_pac.setToolTip(
            "Duplo clique (ou Enter) traz o caso inteiro do paciente para as "
            "outras telas")
        cartao.corpo.addWidget(self.lista_pac)
        self.cartao_busca = cartao
        cartao.setVisible(False)
        return cartao

    def definir_pacientes(self, refs: list) -> None:
        """Lista para a busca (ver ``capa_dados.pacientes``)."""
        self._pacientes = list(refs)
        self._busca_permitida = True
        self._ajustar_busca()
        self._filtrar()

    def esconder_busca(self) -> None:
        """Caso carregado na bancada: quem e o paciente ja esta decidido."""
        self._busca_permitida = False
        self._ajustar_busca()

    def mostrar_busca(self) -> None:
        """Volta a oferecer a busca — o caminho de quem vem da tomografia.

        Separado de ``definir_pacientes`` porque a lista e carregada uma vez por
        sessao: sem isto, limpar a bancada e reabrir a Capa deixava o fluxo da
        TC sem como escolher paciente.
        """
        self._busca_permitida = True
        self._ajustar_busca()

    def _ajustar_busca(self) -> None:
        """Busca ou botão de trocar — nunca os dois.

        Com o paciente já carregado, a busca cumpriu o seu papel: continuar na
        tela custa o bloco mais alto da coluna para repetir uma escolha já
        feita, e deixa uma lista de treze mil nomes a um clique de trocar o
        paciente por engano, com as fotos da tomografia já na tela. Quem
        precisa mesmo trocar tem o botão, que diz o que está fazendo.
        """
        tem_lista = bool(self._pacientes)
        carregado = bool(self._capa.nome.strip() or self._capa.registro.strip())
        pode = self._busca_permitida and tem_lista
        self.cartao_busca.setVisible(pode and not carregado)
        self.btn_trocar.setVisible(pode and carregado)

    def _trocar_paciente(self) -> None:
        """Reabre a busca sem descartar nada.

        O paciente atual segue na tela até que outro seja escolhido — e é aí,
        não aqui, que o descarte das fotos é perguntado (ver
        ``_escolher_paciente``).
        """
        self.cartao_busca.setVisible(bool(self._pacientes))
        self.btn_trocar.setVisible(False)
        self.busca.clear()
        self.busca.setFocus()
        self.mostrar_status("Escolha o paciente — o atual continua na tela até "
                            "você escolher outro.")

    def _fechar_paciente(self) -> None:
        """Descarrega o paciente da tela — o que o "Trocar paciente" NÃO faz.

        Os dois botões existem porque são dois trabalhos: "Trocar" é "não é
        este, me mostre a lista" e mantém tudo até a escolha seguinte;
        "Fechar" é "terminei com este". Sem o segundo, a única forma de limpar
        a tela era escolher outro paciente e descartar — ou fechar o programa.

        A confirmação só aparece quando HÁ fotos, e é a mesma regra do
        ``_confirmar_troca``: foto de tomografia perdida não se refaz sem o
        paciente de volta na sala, então o Enter recai sobre a saída que não
        custa nada. Sem fotos não há o que perder, e perguntar viraria ruído.
        """
        atual = self._capa
        if self.posicionamento.tem_fotos():
            if not ui.confirmar(
                    self, "Fechar o paciente?",
                    f"Há fotos carregadas para {atual.nome or 'este paciente'}.",
                    acao="Descartar e fechar", recusa="Manter na tela",
                    detalhe=("Fechar descarta essas fotos.\n"
                             "Se elas são deste paciente, cadastre a simulação "
                             "antes."),
                    perigo=True):
                return
        self.limpar()
        self.mostrar_busca()
        self._atualizar_acoes()
        # A janela fecha o que não é desta tela — hoje, a Ficha Virtual. Fechar
        # o paciente aqui e reencontrá-lo inteiro na aba ao lado é o defeito
        # que o usuário viu em 31/08/2026: "fechar" que fecha em um lugar só
        # não é fechar, é esconder.
        self.paciente_fechado.emit()
        self.mostrar_status("Paciente fechado. Escolha o próximo.")

    def _filtrar(self, *_) -> None:
        termo = self.busca.text().strip()
        self.lista_pac.clear()
        # O campo DIZ que aceita o registro. A busca sempre aceitou (ver
        # ``capa_dados.PacienteRef.casa``, que casa por pedaço de nome E por
        # pedaço de ID), mas a tela não dizia — nem no campo, que abria sem
        # dica nenhuma, nem no convite, que falava em "letras". O usuário
        # concluiu, em 31/08/2026, que só dava para procurar pelo nome; e ele
        # estava certo sobre o que a tela oferecia. Mesmo texto da Ficha
        # Virtual, que já dizia: as duas buscas são a mesma pergunta.
        self.busca.setPlaceholderText(
            f"nome ou registro — {len(self._pacientes)} pacientes"
            if self._pacientes else "nome ou registro")
        if not self._pacientes:
            self.lista_pac.addItem("(relatórios de paciente não encontrados)")
            return
        # Sem nada digitado a lista fica vazia de propósito: treze mil nomes em
        # ordem alfabética não é uma escolha, é um obstáculo.
        if len(termo) < 2:
            self.lista_pac.addItem(
                f"Digite 2 caracteres do nome ou do registro para procurar "
                f"entre {len(self._pacientes)} pacientes…")
            return
        achados = [p for p in self._pacientes if p.casa(termo)]
        for p in achados[:_MAX_RESULTADOS]:
            item = QListWidgetItem(p.rotulo())
            item.setData(Qt.UserRole, p)
            self.lista_pac.addItem(item)
        if not achados:
            self.lista_pac.addItem("(nenhum paciente com esse nome ou registro)")
        elif len(achados) > _MAX_RESULTADOS:
            self.lista_pac.addItem(
                f"… e mais {len(achados) - _MAX_RESULTADOS} — refine a busca")

    def _escolher_paciente(self) -> None:
        itens = self.lista_pac.selectedItems()
        ref = itens[0].data(Qt.UserRole) if itens else None
        if ref is None:
            return
        # Trocar de paciente com fotos carregadas é o erro mais caro desta tela:
        # as fotos do paciente A seriam gravadas na pasta do B.
        anterior = self._escolhido
        # A troca se decide pelo DONO do posicionamento que está na tela, não
        # por ``self._escolhido``: ele só é preenchido por ESTA busca, e o
        # paciente que chegou pela bancada ou pelo botão "Da pasta" o deixava
        # em ``None``. Aí nada era limpo, o posicionamento dele era reassinado
        # para quem acabou de ser escolhido (a linha logo abaixo) e a busca o
        # "preservava" como se fosse do novo: a nota e as fotos de A saíam na
        # capa de B. Posicionamento vazio não tem dono, então abrir o primeiro
        # paciente continua não perguntando nada.
        trocou = not self.posicionamento_e_de(ref.registro, ref.nome)
        if trocou and self.posicionamento.tem_fotos():
            # O nome de quem está na tela, não o do ``_escolhido``: pelo mesmo
            # motivo de cima, ele pode não existir — e a pergunta precisa dizer
            # de quem são as fotos que se vai descartar.
            de = (anterior.nome if anterior is not None
                  else self.f_nome.text().strip())
            if not self._confirmar_troca(de, ref.nome):
                if anterior is not None:
                    self._marcar_na_lista(anterior)
                return
            self.posicionamento.limpar()
        elif trocou and self.posicionamento.setups():
            # Setup SEM foto ainda é trabalho do paciente anterior: acessorios,
            # preparo, imobilizador, a nota escolhida. So a guarda de fotos nao
            # bastava — o setup do anterior era reassinado para o novo e ia
            # inteiro para a folha 2 dele, calado. Aqui nao se pergunta nada:
            # nada se perde que nao se releia da pasta ou do cadastro.
            self.posicionamento.limpar()
        # E os DADOS do anterior — convênio, médico, curso, CID, prescrições,
        # avisos, a foto 3×4 e a pasta de onde saem as notas. Trocar só a
        # identificação deixava a tela afirmando o convênio e o médico de A sob
        # o nome de B até a busca nos relatórios responder (meio segundo
        # depois, ver ``ControleCapa.paciente_escolhido``) — e PARA SEMPRE quando ela
        # não achava o paciente ou falhava. Numa tela que vira documento
        # impresso, dado de outra pessoa na tela é o erro que não se pode
        # cometer nem por um instante.
        if self._e_outro_paciente(ref):
            self._esquecer_paciente_anterior()
        self._assumir_posicionamento(ref.registro, ref.nome)
        self._escolhido = ref
        capa = self._capa
        # Grafia canônica, não CAIXA ALTA: a capa e a ficha andam grampeadas, e
        # até 25/08/2026 a mesma pessoa saía "SANDRA CABRAL DA LUZ" numa e
        # "Sandra Cabral da Luz" na outra. O ``.upper()`` daqui vinha de quando
        # a fonte era só o relatório, que exporta em caixa alta.
        capa.nome = capa_dados.como_nome_proprio(ref.nome)
        capa.registro = ref.registro
        capa.nascimento = ref.nascimento
        self.f_nome.setText(capa.nome)
        self.f_registro.setText(capa.registro)
        self.f_nascimento.setText(capa.nascimento)
        self._pintar_cabecalho(capa)
        self.posicionamento.definir_paciente(capa.registro)
        # Sabemos QUEM e, nao o tratamento: convenio, curso, CID e prescricoes
        # continuam por buscar. Dizer o contrario faz a capa sair em branco.
        self._dos_relatorios = False
        self.habilitar(True)
        self._atualizar_acoes()
        self.paciente_escolhido.emit()

    def _confirmar_paciente(self, item) -> None:
        """Duplo clique ou Enter: é ESTE, e as outras telas que o sigam."""
        ref = item.data(Qt.UserRole) if item is not None else None
        if ref is None:
            return
        self.paciente_confirmado.emit(ref.registro, ref.nome)

    def _e_outro_paciente(self, ref) -> bool:
        """O escolhido na lista é diferente de quem está NA TELA?

        Pela tela, e não por ``self._escolhido``: quem chegou pela bancada ou
        pelo botão "Da pasta" não passou pela busca, e comparar com o
        ``_escolhido`` (vazio) responderia "é o mesmo" para qualquer um.

        Tela vazia não é outro paciente — é a primeira escolha, e não há o que
        esquecer.
        """
        na_tela_reg = capa_dados.normalizar_id(self._capa.registro)
        na_tela_nome = capa_dados.normalizar_nome(self._capa.nome)
        if not (na_tela_reg or na_tela_nome):
            return False
        alvo_reg = capa_dados.normalizar_id(getattr(ref, "registro", ""))
        if na_tela_reg or alvo_reg:
            return na_tela_reg != alvo_reg
        return na_tela_nome != capa_dados.normalizar_nome(
            getattr(ref, "nome", ""))

    def _esquecer_paciente_anterior(self) -> None:
        """Apaga da tela tudo que é DADO do paciente que estava aqui.

        Não é ``limpar``: a busca continua aberta e a lista, como está — a
        seleção anda a cada tecla de seta, e fechar a busca no primeiro nome
        tocado tiraria a lista de baixo de quem a percorre (ver
        ``_ajustar_busca``).

        Também não é ``carregar``: essa lê as correções de cadastro do disco
        (arquivo compartilhado, ver ``correcoes.ler``), e uma leitura de rede
        por tecla de seta travaria a lista. O que o novo paciente tem chega
        pela busca dos relatórios, meio segundo depois.

        A PASTA vai junto: ela é do paciente que saiu, e é dela que
        ``carregar_da_pasta`` tira as notas e as fotos — deixá-la valendo era o
        caminho pelo qual a nota de A entrava na capa de B.
        """
        vazia = capa_pdf.Capa()
        self._capa = vazia
        self._corrigidos = []
        self._do_relatorio = {c: "" for c in correcoes.CAMPOS}
        # Sabemos QUEM é, não o tratamento: a capa ainda está por montar.
        self._dos_relatorios = False
        self._pasta_paciente = ""
        for campo in (self.f_nome, self.f_registro, self.f_nascimento,
                      self.f_convenio, self.f_contato, self.f_medico,
                      self.f_maquina, self.f_curso, self.f_intencao,
                      self.f_data_aprov, self.f_descricao, self.f_cid):
            campo.clear()
        self._definir_sexo("")
        self._pintar_cabecalho(vazia)
        self._montar_escolha(())
        self._limpar_blocos()
        # Aviso é do caso do outro: "sem prescrição aprovada" sob o nome novo
        # manda conferir uma pendência que não é dele.
        self.mostrar_avisos(())

    def _confirmar_troca(self, de: str, para: str) -> bool:
        """``perigo=True``: descartar foto de tomografia não se desfaz.

        A foto só existe aqui até virar cadastro de simulação — perdida, ela
        não se refaz sem o paciente de volta na sala. Por isso o Enter recai
        sobre "Continuar com o atual", que é a saída que não custa nada.

        Recebe NOMES, não as referências da busca: quem está na tela pode ter
        chegado pela bancada, sem referência nenhuma (ver ``_escolher_paciente``).
        """
        de = (de or "").strip() or "o paciente que está na tela"
        return ui.confirmar(
            self, "Trocar de paciente?",
            f"Há fotos carregadas para {de}.",
            acao="Descartar e trocar", recusa="Continuar com o atual",
            detalhe=(f"Trocar para {para} descarta essas fotos.\n"
                     "Se elas são deste paciente, cadastre a simulação antes."),
            perigo=True)

    def _marcar_na_lista(self, ref) -> None:
        self.lista_pac.blockSignals(True)
        for i in range(self.lista_pac.count()):
            dado = self.lista_pac.item(i).data(Qt.UserRole)
            if dado is not None and dado.registro == ref.registro:
                self.lista_pac.setCurrentRow(i)
                break
        else:
            self.lista_pac.clearSelection()
        self.lista_pac.blockSignals(False)

    # ── API usada pela janela principal ──────────────────────────────────

    def habilitar(self, ligado: bool) -> None:
        """Sem paciente carregado a tela fica inerte, como a bancada.

        ``btn_fotos`` fica de fora: apontar a pasta do paciente é o que se faz
        *antes* de haver capa, e desligá-lo sem caso na bancada trancava
        justamente a porta de quem vem da tomografia.
        """
        for b in (self.btn_add_bloco, self.btn_del_bloco):
            b.setEnabled(ligado)
        self.btn_fotos.setEnabled(True)
        self._atualizar_acoes()

    def _atualizar_acoes(self) -> None:
        """Botão aceso significa pronto; apagado diz no tooltip o que falta.

        Antes, só "Cadastrar Simulação" seguia essa regra. Os outros ficavam
        acesos com a tela vazia e, clicados, respondiam com um recado de erro —
        que é justamente o que o botão apagado evita.
        """
        tem_paciente = bool(self._capa.nome.strip()
                            or self.f_nome.text().strip())
        tem_fotos = self.posicionamento.tem_fotos()

        self.btn_cadastrar.setEnabled(tem_paciente and tem_fotos)
        self.btn_cadastrar.setToolTip(
            "Grava a pasta da simulação com as fotos e a nota do posicionamento"
            if tem_paciente and tem_fotos
            else ("Escolha o paciente" if not tem_paciente
                  else "Arraste ao menos uma foto do posicionamento"))

        # Botão aceso significa pronto: sem paciente na tela não há o que
        # fechar, e o tooltip diz por que ele está apagado.
        self.btn_fechar.setEnabled(tem_paciente)
        self.btn_fechar.setToolTip(
            "Tira este paciente da tela e volta à busca — diferente de "
            "\"Trocar paciente\", que mantém o atual até você escolher outro"
            if tem_paciente else "Nenhum paciente na tela")

        dica = ("Abre a pasta que o dosimetrista cadastrou na tomografia para "
                "este paciente e importa as fotos e a nota do posicionamento. "
                "Sem cadastro, pergunta onde fica a pasta.")
        # O caminho da última pasta aberta fica À VISTA, e não é enfeite:
        # ``simulacao.procurar`` casa por NOME quando o cadastro não tem
        # registro, então um homônimo pode trazer a pasta de outra pessoa —
        # e ver o caminho é a única conferência que sobra para quem está na
        # frente.
        if getattr(self, "_ultima_pasta_do_botao", ""):
            dica += f"\n\nÚltima pasta aberta: {self._ultima_pasta_do_botao}"
        self.btn_fotos.setToolTip(dica)

        for btn, verbo in ((self.btn_visualizar, "Abre a capa em PDF para "
                                                 "conferir antes de imprimir"),
                           (self.btn_salvar, "Grava o PDF da capa onde você "
                                             "escolher"),
                           (self.btn_imprimir, "Manda a capa para a impressora")):
            btn.setEnabled(tem_paciente)
            btn.setToolTip(verbo if tem_paciente else "Escolha o paciente")

    def pasta_do_paciente(self) -> str:
        """A pasta que esta tela está lendo (pode não ser a da bancada)."""
        return self._pasta_paciente

    def definir_usuario(self, usuario: str) -> None:
        """Quem assina as correções. Dado de paciente que sobrescreve o sistema
        oficial não pode ser anônimo."""
        self._usuario = str(usuario or "")

    def permitir_escolher_pastas(self, pode: bool) -> None:
        """Os endereços do serviço saíram desta tela.

        Ficavam aqui como dois botões ("Relatórios…", "Simulações…"), onde
        competiam com o trabalho de montar a folha e ainda apareciam para quem
        não podia usá-los. Hoje moram em **Configurações → Serviço**, só de
        admin, e valem para todas as estações.

        O método continua existindo porque a janela ainda informa o papel do
        usuário — e é ele que decide o texto do recado quando os relatórios não
        aparecem: mandar a técnica apertar um botão que não existe mais seria
        pior que não dizer nada.
        """
        self._pode_apontar_pastas = bool(pode)

    def pode_apontar_pastas(self) -> bool:
        """Se esta estação tem os botões de pasta à vista.

        Existe para que os recados não mandem apertar botão que não está lá:
        quem não é admin não vê "Relatórios" e ficava procurando na tela.
        """
        return bool(getattr(self, "_pode_apontar_pastas", False))

    def mostrar_status(self, msg: str, erro: bool = False) -> None:
        # Guarda o TIPO da mensagem, não a cor: a folha é remontada a cada
        # troca de dia↔noite, e um vermelho de modo claro sobre fundo escuro
        # some.
        self._status_erro = bool(erro)
        self.lbl_status.setStyleSheet(self._folha_status())
        self.lbl_status.setText(msg or "")

    def _folha_status(self) -> str:
        cor = st.VERMELHO if getattr(self, "_status_erro", False) else st.TEXTO_FRACO
        return f"font-size:12px; color:{cor};"

    def mostrar_avisos(self, avisos: Iterable[str]) -> None:
        """Avisos vindos de FORA (a busca nos relatórios). Ver ``_repintar_avisos``."""
        self._avisos_externos = list(avisos or [])
        self._repintar_avisos()

    def _avisos_proprios(self) -> list[str]:
        """O que a própria tela tem a reclamar do que está nos campos AGORA.

        Reavaliados a cada tecla (``_pintar_cabecalho``), e não só quando a busca
        roda: quem apaga o sexo à mão precisa do aviso na hora, não na próxima
        busca.
        """
        proprios = []
        if self.f_nome.text().strip() and not self.f_sexo.currentText().strip():
            proprios.append(
                "Sexo não informado — a faixa do nome sai NEUTRA na capa, em "
                "vez de vermelha (feminino) ou azul (masculino). Escolha uma "
                "das opções.")
        return proprios

    def _repintar_avisos(self) -> None:
        self.lista_avisos.clear()
        for a in [*self._avisos_proprios(), *getattr(self, "_avisos_externos", [])]:
            it = QListWidgetItem(f"⚠   {a}")
            it.setForeground(QColor(st.AMBAR))
            self.lista_avisos.addItem(it)
        self.lista_avisos.setVisible(self.lista_avisos.count() > 0)

    def definir_modo(self, modo: str) -> None:
        """Escolhe o momento do caso que a tela está atendendo.

        ``SIMULACAO`` é a tomografia: identificar o paciente e registrar como
        ele foi deitado. Curso, prescrições e a impressão da capa saem de cena
        porque **ainda não existem** — o caso não foi calculado e a TC nem foi
        importada. Deixá-los na tela vazios transforma um cadastro de três
        campos num documento pela metade, e faz o dosimetrista procurar dados
        que ninguém tem para dar naquele momento.

        ``COMPLETA`` é a capa de verdade, com o caso na bancada.

        Os campos escondidos continuam preenchidos e são coletados: o que a
        busca trouxe não se perde, só não é mostrado agora.
        """
        if modo == self._modo:
            return
        self._modo = modo
        simulando = modo == SIMULACAO
        self.lbl_titulo.setText(
            "Cadastro de Simulação" if simulando else "Capa de Tratamento")
        self.cartao_curso.setVisible(not simulando)
        self.cartao_presc.setVisible(not simulando)
        # Imprimir a capa é o fim da outra ponta do caminho. Aqui a ação é uma
        # só, e ela fica sozinha para ser óbvia.
        for btn in (self.btn_visualizar, self.btn_salvar, self.btn_imprimir):
            btn.setVisible(not simulando)
        self.btn_cadastrar.setVisible(True)
        self._pesar_botoes()
        # Sair de cena muda o que a tela tem para mostrar — e, com isso, se há
        # duas colunas de conteúdo.
        self._arrumar_colunas(self._cabem_duas_colunas())
        self._atualizar_acoes()

    def modo(self) -> str:
        return self._modo

    def montada_dos_relatorios(self) -> bool:
        """A tela tem a capa COMPLETA, ou só o nome de quem ela é?

        A busca de paciente da TC preenche nome, registro e nascimento e mais
        nada. Tratar isso como capa pronta faz o documento sair sem convênio,
        curso, CID, médico, máquina e sem uma prescrição sequer — com a tela
        dizendo que está pronto para conferir.
        """
        return self._dos_relatorios

    def _posicionamento_mudou(self) -> None:
        """Mexer nas fotos ou na nota desfaz o "já está arquivado"."""
        self._posicionamento_arquivado = False
        self._atualizar_acoes()
        self.mudou.emit()

    def marcar_posicionamento_arquivado(self) -> None:
        """Cadastro gravado (ou lido da pasta): descartar da tela não perde nada."""
        self._posicionamento_arquivado = True

    def posicionamento_tem_fotos(self) -> bool:
        """Há foto de posicionamento na tela? Quem escreve o recado do próximo
        passo precisa saber o que já está feito."""
        return self.posicionamento.tem_fotos()

    def posicionamento_atual(self) -> list:
        """Os setups montados agora — para quem precisa repô-los depois."""
        return self.posicionamento.setups()

    def posicionamento_e_de(self, registro: str, nome: str = "") -> bool:
        """As fotos na tela são DESTE paciente?

        Repor o posicionamento ao remontar a capa existe para não perder as
        fotos da tomografia, que não se refazem sem o paciente na sala. Mas
        quem repunha não perguntava de quem eram: carregado o paciente A com
        fotos e pedida a capa do B, as fotos de A iam junto — e saíam impressas
        na capa de B, que é o erro que este documento existe para evitar.

        Posicionamento vazio não tem dono: qualquer paciente pode recebê-lo.
        """
        if not self.posicionamento.setups():
            return True
        dono_reg, dono_nome = self._dono_posicionamento
        alvo_reg = capa_dados.normalizar_id(registro)
        if dono_reg or alvo_reg:
            return dono_reg == alvo_reg
        # Sem registro dos dois lados (paciente da TC ainda sem cadastro), o
        # nome é a única chave que resta.
        return dono_nome == capa_dados.normalizar_nome(nome)

    def _assumir_posicionamento(self, registro: str, nome: str) -> None:
        """Marca de quem é o posicionamento que está na tela.

        Chamado onde o posicionamento é ZERADO ou trocado — nunca onde só a
        identificação muda. Reassinar a cada troca de nome devolveria o bug:
        as fotos passariam a "ser" de quem chegou depois.
        """
        self._dono_posicionamento = (capa_dados.normalizar_id(registro),
                                     capa_dados.normalizar_nome(nome))

    def repor_posicionamento(self, setups: list) -> None:
        """Devolve os setups que ``carregar`` zerou.

        Montar a capa do MESMO paciente não pode custar as fotos que acabaram de
        ser arrastadas: elas são dele, e refazê-las exige a pessoa de volta na
        sala da tomografia. Voltam como PENDENTES — repor não é cadastrar.
        """
        if not setups:
            return
        self.posicionamento.carregar(setups)
        self._posicionamento_arquivado = False
        self._atualizar_acoes()

    def posicionamento_pendente(self) -> bool:
        """Há posicionamento montado que ainda NÃO existe em lugar nenhum?

        É o dado mais caro desta tela: as fotos da tomografia não se refazem
        sem o paciente na sala. O que já foi cadastrado volta do disco sozinho
        e não merece uma pergunta.
        """
        return bool(self.posicionamento.setups()
                    and not self._posicionamento_arquivado)

    def confirmar_descarte_do_posicionamento(self, de: str, para: str) -> bool:
        """Pergunta antes de jogar fora fotos que ainda não foram cadastradas."""
        return ui.confirmar(
            self, "Descartar o posicionamento?",
            f"Há posicionamento montado para {de or 'o paciente atual'}.",
            acao="Descartar e montar", recusa="Manter o posicionamento",
            detalhe=(f"Montar a capa de {para} descarta essas fotos.\n"
                     "Se elas são do paciente atual, cadastre a simulação "
                     "antes."),
            perigo=True)

    def limpar(self) -> None:
        """Zera a tela para o próximo paciente."""
        self._escolhido = None
        self._capa = capa_pdf.Capa()
        # A pasta É do paciente que saiu. Sem esta linha, "Abrir pasta do
        # paciente" deixava de PERGUNTAR no paciente seguinte e relia a pasta
        # do anterior calado: a nota e as fotos de A iam para a capa de B, com
        # a tela dizendo "Importado: a nota SETUP_A.txt". É a mesma mistura que
        # ``ControleCapa.buscar`` já evitava por outra porta (ver o comentário sobre
        # herdar a pasta da tela, em ``gui``); esta ficou aberta pelo botão
        # "Próxima simulação", que passa por aqui.
        self._pasta_paciente = ""
        self.busca.clear()
        self.lista_pac.clear()
        self.carregar(capa_pdf.Capa())
        self.posicionamento.limpar()
        self._assumir_posicionamento("", "")
        self.mostrar_avisos(())
        self.mostrar_status("")

    def definir_pasta(self, pasta: str) -> None:
        """Pasta do paciente — de onde saem as fotos e as notas de posicionamento."""
        self._pasta_paciente = pasta or ""

    def carregar(self, capa: capa_pdf.Capa, opcoes=()) -> None:
        """Joga a capa montada nos campos. Tudo daqui em diante é editável.

        ``opcoes`` são TODAS as prescrições que o relatório tem para o paciente
        (ver ``capa_pdf.opcoes_de``); ``capa.blocos`` já traz só as marcadas.
        """
        # O que a pessoa corrigiu vale mais que o retrato exportado — que é
        # justamente o que estava errado. Entra ANTES de a capa virar campos,
        # senão a tela mostraria o valor certo e o PDF sairia com o do
        # relatório. Guardo o que veio do relatório para o botão Salvar poder
        # dizer o que de fato diverge (ver ``_salvar_correcoes``).
        # O sexo entra JÁ NORMALIZADO: o relatório escreve "M" e o seletor
        # mostra "Masculino". Comparando as duas grafias, devolver o campo ao
        # valor original parecia uma divergência — e a correção que se queria
        # desfazer era regravada.
        self._do_relatorio = {c: str(getattr(capa, c, "") or "")
                              for c in correcoes.CAMPOS}
        self._do_relatorio["sexo"] = normalizar_sexo(self._do_relatorio["sexo"])
        self._corrigidos = correcoes.aplicar(capa)
        self._capa = capa
        # Capa vinda dos relatorios (convenio, curso, CID, prescricoes) — ao
        # contrario da que a busca da TC monta, que so tem quem e o paciente.
        # A janela usa isto para saber se ainda precisa procurar. Ver
        # ``montada_dos_relatorios``.
        self._dos_relatorios = bool(capa.nome or capa.registro)
        self.f_nome.setText(capa.nome)
        self.f_registro.setText(capa.registro)
        self.f_nascimento.setText(capa.nascimento)
        self._definir_sexo(capa.sexo)
        self.f_convenio.setText(capa.convenio)
        self.f_contato.setText(capa.contato)
        self.f_medico.setText(capa.medico)
        self.f_maquina.setText(capa.maquina)
        self.f_curso.setText(capa.curso)
        self.f_intencao.setText(capa.intencao)
        self.f_data_aprov.setText(capa.data_aprovacao)
        self.f_descricao.setText(capa.descricao)
        self.f_cid.setText(capa.cid)
        self._pintar_cabecalho(capa)
        self.posicionamento.definir_paciente(capa.registro)

        self._montar_escolha(opcoes)
        self._limpar_blocos()
        for b in capa.blocos:
            self._novo_bloco(b)
        self.posicionamento.carregar(capa.setups)
        self._assumir_posicionamento(capa.registro, capa.nome)
        self.habilitar(True)
        self._atualizar_acoes()
        # Carregado o paciente, a busca dá lugar ao botão de trocar — e a capa
        # vazia de ``limpar`` faz o caminho de volta. É aqui, e não ao escolher
        # na lista: a seleção anda a cada tecla de seta, e fechar a busca no
        # primeiro nome tocado tiraria a lista de baixo de quem a percorre.
        self._ajustar_busca()

    def _pintar_cabecalho(self, capa: capa_pdf.Capa) -> None:
        """Toda a identificação em pílulas: é o que se confere de relance.

        Primeira fileira, quem é o paciente; segunda, com quem e onde trata. O
        convênio vem cortado no " - " porque o relatório traz o plano inteiro
        ("Unimed - Nacional Apartamento"), que não cabe e não distingue nada.
        """
        self.cabecalho.definir(capa.nome, [
            (capa.registro, "azul"),
            (capa.ddn(), "neutro"),
            (capa.sexo, "neutro"),
            (capa.convenio.split(" - ")[0] if capa.convenio else "", "neutro"),
            (capa.contato, "neutro"),
        ], capa.foto, extras=[
            (capa.medico, "azul"),
            (capa.maquina, "verde"),
        ])
        # A cor da faixa do nome na capa impressa depende do sexo; sem ele, sai
        # neutra. O aviso acompanha a digitação.
        self._repintar_avisos()

    def _coletar_identificacao(self) -> capa_pdf.Capa:
        """Só o que o cabeçalho pinta — sem remontar blocos nem setups."""
        return capa_pdf.Capa(
            nome=self.f_nome.text(), registro=self.f_registro.text(),
            nascimento=self.f_nascimento.text(),
            sexo=self.f_sexo.currentText(),
            convenio=self.f_convenio.text(), contato=self.f_contato.text(),
            medico=self.f_medico.text(), maquina=self.f_maquina.text(),
            foto=self._capa.foto)

    def coletar(self) -> capa_pdf.Capa:
        """A capa como está na tela — é esta que vira PDF."""
        c = self._capa
        # Rede do campo: "Imprimir" pode ser clicado com o cursor ainda dentro
        # do nome, e aí o ``editingFinished`` não chegou a rodar.
        c.nome = capa_dados.como_nome_proprio(self.f_nome.text().strip())
        c.registro = self.f_registro.text().strip()
        c.nascimento = self.f_nascimento.text().strip()
        c.sexo = self.f_sexo.currentText().strip()
        c.convenio = self.f_convenio.text().strip()
        c.contato = self.f_contato.text().strip()
        c.medico = capa_dados.como_nome_proprio(self.f_medico.text().strip())
        c.maquina = self.f_maquina.text().strip()
        c.curso = self.f_curso.text().strip()
        c.intencao = self.f_intencao.text().strip()
        c.data_aprovacao = self.f_data_aprov.text().strip()
        c.descricao = self.f_descricao.text().strip()
        c.cid = self.f_cid.text().strip()
        c.blocos = [capa_pdf.Bloco(
            titulo=w["titulo"].text().strip(),
            aprovado_por=w["aprovado_por"].text().strip(),
            volumes=[l for l in w["volumes"].toPlainText().splitlines() if l.strip()],
            frequencia=w["frequencia"].text().strip(),
            notas=w["notas"].toPlainText().strip(),
        ) for w in self._widgets_blocos]
        # Enfermagem (alertas, dias alternados, planos de cuidado) não tem
        # campo nesta tela: é preenchida à mão, no papel, depois de impressa. As
        # linhas continuam saindo no PDF, em branco.
        c.setups = self.posicionamento.setups() or [capa_dados.Setup()]
        return c

    def simulacao(self) -> simulacao.Simulacao:
        """O que o dosimetrista registrou, pronto para virar pasta."""
        c = self.coletar()
        sim = simulacao.Simulacao(nome=c.nome, registro=c.registro,
                                  nascimento=c.nascimento, setups=c.setups)
        for codigo in self.posicionamento.imobilizadores():
            item = inventario.por_codigo(codigo)
            if item is not None:
                sim.imobilizadores.append({"codigo": item.codigo,
                                           "tipo": item.tipo})
        return sim

    # ── Fotos e notas da pasta do paciente ───────────────────────────────

    def carregar_da_pasta(self, pasta: str = "", nome: str = "",
                          registro: str = "") -> "Importado":
        """Puxa os setups de posicionamento — do cadastro da simulação ou da pasta.

        Duas fontes, nesta ordem. Primeiro a **pasta do paciente** (onde está o
        DICOM): cada ``.docx``/``.txt`` é um setup, e as fotos são distribuídas
        pelo nome. Depois, se ali não houver nada, o **cadastro de simulação**
        gravado ao sair da tomografia — que é onde o posicionamento nasce, e vem
        estruturado, sem nada a interpretar.

        Só entra quando o posicionamento está vazio: reimportar depois de alguém
        ter corrigido o texto apagaria a correção.
        """
        pasta = pasta or self._pasta_paciente
        setups = capa_dados.setups_da_pasta(pasta)
        da_simulacao = False
        if not setups and (nome or registro):
            setups = capa_dados.simulacao_do_paciente(nome, registro)
            da_simulacao = bool(setups)
        if not setups:
            return Importado()

        res = Importado()
        res.da_simulacao = da_simulacao
        res.fotos = sum(len(s.fotos) for s in setups)
        # Arquivos DISTINTOS, não setups: um cadastro com dois posicionamentos
        # vem de UM arquivo só, e contar dois dispararia um aviso de ambiguidade
        # que não existe.
        fontes = {s.arquivo for s in setups if s.arquivo}
        res.notas = len(fontes)
        if self.posicionamento.setups():
            # Ja ha posicionamento montado na tela: nao sobrescreve o trabalho
            # de ninguem, nao diz que importou o que nao entrou, e tambem nao
            # diz que nada existe — o arquivo esta la.
            return Importado(notas=res.notas, da_simulacao=da_simulacao,
                             preservado=True)
        self.posicionamento.carregar(setups)
        # Veio do disco: descartá-lo da tela não perde nada — relê-se.
        self._posicionamento_arquivado = True
        res.nota_usada = ", ".join(sorted(fontes))
        # Só o que foi realmente preenchido — o cadastro guarda as seis colunas
        # sempre, e contá-las diria "6 campos" com tudo em N/A.
        res.preparo = sum(1 for s in setups for v in s.preparo.values()
                          if v and v != capa_pdf.VAZIO)
        self._atualizar_acoes()
        return res

    def _pasta_da_simulacao(self) -> str:
        """A pasta que o dosimetrista cadastrou na TC para ESTE paciente.

        A ponte já existia (``simulacao.procurar``, que a Ficha Virtual e o
        ``capa_dados`` usam), mas o botão não a atravessava: ele ia direto
        perguntar onde fica a pasta. Com o paciente vindo do BANCO — que é
        como todo paciente passa a ser aberto —, perguntar é pedir à pessoa
        uma informação que o programa já tem, e o preço do engano é apontar a
        pasta de outro paciente.

        Devolve "" quando não há cadastro: aí a pergunta continua sendo a
        resposta certa, porque a pasta pode existir sem ninguém ter cadastrado
        a simulação.
        """
        try:
            from isocentro.interface import simulacao

            return simulacao.procurar(self._capa.nome, self._capa.registro)
        except Exception as exc:  # noqa: BLE001
            # Raiz de simulações inacessível não pode virar tela travada: cai
            # na pergunta, que é o que a tela fazia antes de qualquer jeito.
            #
            # O recado vai para a TELA e não para o histórico, e é o contrário
            # do que este projeto faz no resto: aqui quem clicou está na frente
            # do computador, e o que ele precisa saber é por que o programa
            # está perguntando em vez de já saber. Log seria para quem lê
            # depois, e não há "depois" num clique.
            self.mostrar_status(
                f"Não deu para consultar as simulações cadastradas "
                f"({str(exc)[:60]}) — aponte a pasta.", erro=True)
            return ""

    def _escolher_fotos(self) -> None:
        """Botão "Abrir pasta do paciente": lê a pasta do caso.

        A ordem é: pasta já apontada → **cadastro de simulação** → perguntar.
        O degrau do meio entrou em 04/09/2026, quando todo paciente passou a
        ser aberto pelo banco: a pasta do paciente é justamente o que o
        dosimetrista registrou ao sair da tomografia, e o programa sabe achá-la.

        Perguntar continua existindo, e não é sobra: paciente com pasta e sem
        cadastro é caso real (a 9000001CEL, em 21/08/2026, tinha fotos e nota
        soltas na pasta e cadastro nenhum).
        """
        # Pasta que não existe MAIS conta como pasta nenhuma: a rede caiu, ou
        # alguém moveu/renomeou o caso desde que ela foi apontada. Sem esta
        # conferência a leitura seguia e o recado saía "nada de posicionamento
        # na pasta do paciente" — que manda procurar foto que não falta, em vez
        # de dizer que a pasta é que sumiu.
        if not self._pasta_paciente or not os.path.isdir(self._pasta_paciente):
            if self._pasta_paciente:
                self.mostrar_status(
                    f"A pasta apontada não está acessível "
                    f"({self._pasta_paciente}) — aponte outra.", erro=True)
                self._pasta_paciente = ""
            do_cadastro = self._pasta_da_simulacao()
            if do_cadastro:
                # O caminho vai no TOOLTIP do botão, e não só no status: quem
                # recebe o sinal escreve "Lendo a pasta…" logo em seguida, e o
                # recado que dizia QUAL pasta foi escolhida sumia antes de ser
                # lido (achado na revisão de 04/09/2026). No tooltip ele fica.
                #
                # E isso importa mais do que parece: ``simulacao.procurar``
                # casa por NOME quando o cadastro não tem registro, então um
                # homônimo pode trazer a pasta de outra pessoa. Ver o caminho é
                # a única conferência que sobra para quem está na frente.
                # Guardado no atributo, e não escrito direto no tooltip: o
                # ``_atualizar_acoes`` roda logo em seguida — dentro do próprio
                # tratamento do ``pasta_escolhida`` — e reescrevia o tooltip,
                # apagando o caminho antes de alguém o ler. Achado na revisão
                # de 04/09/2026; o teste não pegou porque dublava o sinal.
                self._ultima_pasta_do_botao = do_cadastro
                self.mostrar_status(
                    f"Pasta da simulação cadastrada: {do_cadastro}")
                self.pasta_escolhida.emit(do_cadastro)
                return
            pasta = QFileDialog.getExistingDirectory(
                self, "Pasta do paciente (DICOM, fotos e notas)")
            if not pasta:
                return
            self.pasta_escolhida.emit(pasta)
            return
        res = self.carregar_da_pasta(nome=self._capa.nome,
                                     registro=self._capa.registro)
        if res.preservado:
            self.mostrar_status(res.resumo().capitalize() + ".", erro=True)
        elif res.achou():
            self.mostrar_status("Importado: " + res.resumo() + ".")
        else:
            self.mostrar_status(
                "Nada de posicionamento na pasta do paciente nem no cadastro "
                "de simulação — arraste as fotos aqui.", erro=True)
