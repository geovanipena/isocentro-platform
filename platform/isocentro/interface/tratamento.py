"""A aba **Ficha Virtual**: em que ponto do tratamento o paciente está.

As outras telas do app montam documentos — o que se vai fazer com o paciente.
Esta responde ao contrário, e para outra pessoa: o médico que encontra o
paciente no corredor e precisa saber, em segundos, em que fração ele está,
quando foi a última, e se o tratamento parou em algum momento.

Daí três decisões de tela que não se parecem com o resto do app:

**Os números são grandes.** Não é estética: quem consulta isto está de pé, com
o paciente do lado, muitas vezes olhando de longe. "12 / 25" em corpo 15 no meio
de um formulário é uma informação que existe e não é lida. Aqui a fração ocupa
o centro da tela e nada compete com ela.

**Não há impressão.** Decidido com o usuário em 19/08/2026: esta é uma consulta,
não um documento. Documento que sai daqui vira papel solto sem lugar na pasta —
e o que vai para a sala de tratamento continua sendo a ficha e a capa.

**Nada aqui é editável.** É leitura do banco, de ponta a ponta. Não há campo,
não há correção, não há gravação — quem discorda do que está na tela discorda do
sistema clínico, e o lugar de consertar é lá.

O dado vem de :mod:`tratamento_db`, que tem um portão: enquanto o mapeamento das
tabelas de tratamento entregue não for conferido contra o banco real, ele não
devolve número nenhum e esta tela diz por quê. Ver o docstring de lá.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QSizePolicy,
    QVBoxLayout, QWidget)

from isocentro.interface import checklist
from isocentro.dominio import constantes
from isocentro.dados import equipe
from isocentro.interface import estilo as st
from isocentro.banco import tratamento_db
from isocentro.interface import ui
# Endereços antigos, de propósito: o painel e os testes citam estas peças
# como ``tratamento.X`` desde antes da divisão (R-13, 13/10/2026).
from isocentro.interface.tratamento_janelas import (  # noqa: F401
    _JanelaCampos, _JanelaChecklist)
from isocentro.interface.tratamento_pecas import (  # noqa: F401
    _ALTURA_ITEM, _LARG_MAX_POPUP, _Barra, _ComboMedico, _DialogGrupoMedicos,
    _Elide, _Fileira, _ImagemEscalada, _JanelaImagem, _JanelaTexto,
    _LinhaPainel, _Nota, _NumeroGrande, _SeletorMedicos, _ValorClicavel,
    _abrir_na_frente, _popup_legivel)

_LOG = logging.getLogger(__name__)

# Teto de nomes na lista da busca — o mesmo da Capa, e pela mesma razão: treze
# mil linhas não é uma escolha, é um obstáculo.
_MAX_RESULTADOS = 40

# A partir de quantos dias úteis parados a faixa de intervalos fica âmbar. Um
# dia perdido é normal e aparece na lista; três seguidos é o que muda conduta.
_INTERVALO_ATENCAO = 3

# As colunas da lista de sessões. Largura FIXA só onde o conteúdo também é de
# largura fixa (fração, data, hora); plano e máquina são medidos na lista, e o
# nome de quem tratou é o último justamente por não ter teto.
#
# TRÊS espaços entre colunas, não um. Com um só, "TBuniverSN1002" e o nome
# vizinho eram lidos como uma coisa só — foi o que o usuário viu na tela em
# 20/08/2026 ("o nome wagner invade espaço da maquina"). O separador é o mesmo
# em todas as colunas: separação desigual sugere agrupamento que não existe.
_SEP = "   "
_COL_FRACAO = 6
_COL_DATA = 10          # "31/07/2026"
_COL_HORA = 5           # "13:22"
_CAB_FRACAO = "FRAÇÃO"
_CAB_PLANO = "PLANO"
_CAB_DATA = "DATA"
_CAB_HORA = "HORA"
_CAB_MAQUINA = "MÁQUINA"
_CAB_QUEM = "QUEM TRATOU"
# O recuo do rótulo de colunas até a primeira letra de uma linha da lista:
# 4px de padding do widget + 1px de borda + 6px do item (folha ``ui.LISTA``).
# Um pixel de diferença já desalinha a coluna inteira, que é o que a fonte
# monoespaçada e a medição em ``_colunas`` existem para evitar.
_RECUO_CAB = 11

# Altura do título de faixa no painel. Menor que a da linha (34): ele é rótulo,
# não conteúdo, e com a mesma altura os títulos passam a competir com os
# pacientes pela atenção — que é o oposto de agrupar.
_ALTURA_FAIXA = 24

# Largura da coluna da direita (Fotos/Posicionamento e Cortes/DVH). FIXA, e não
# uma fração da janela: é ela que os cartões de valor do quadro reservam para
# terminarem onde a lista de sessões termina, e proporção não alinha nada quando
# a janela muda de tamanho.
_LARG_IMAGENS = 560


class PainelFichaVirtual(QWidget):
    """Busca o paciente e mostra o tratamento entregue.

    Emite ``paciente_escolhido(registro, nome)`` — quem monta a janela é que
    sabe consultar o banco e devolve o resultado por :meth:`mostrar`. A tela não
    fala com o banco por conta própria: assim ela é testável sem rede, e a
    janela continua sendo o único lugar que decide o que fazer quando o banco
    não responde.
    """

    paciente_escolhido = Signal(str, str)
    # "É ESTE": duplo clique ou Enter. As duas listas desta aba disparam o
    # ``paciente_escolhido`` por ``itemSelectionChanged``, isto é, ao NAVEGAR —
    # e trazer o caso inteiro do paciente sobre o qual o cursor passou seria
    # carregar DICOM por engano. Ver a revisão de 04/09/2026.
    paciente_confirmado = Signal(str, str)
    # Quem abre o PDF é a JANELA: a aba não sabe abrir arquivo, e centralizar
    # isso mantém o tratamento de erro num lugar só.
    abrir_pdf = Signal()
    # As duas portas vizinhas do PDF. A aba pede; quem lê o disco (o checklist
    # gravado, o ``plano_rp`` da ficha salva) é a janela, pelo mesmo motivo de
    # sempre — assim a tela é testável sem arquivo nenhum.
    abrir_checklist = Signal()
    abrir_campos = Signal()
    # (item, marca); marca vazia = desmarcar. Quem grava é a janela.
    checklist_marcado = Signal(str, str)
    curso_escolhido = Signal(str, int)
    medicos_mudaram = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pacientes: list = []
        self._registro = ""
        self._foto: Optional[bytes] = None
        self._curso_na_tela = None
        # Antes de montar os widgets: ``_folha_curso`` é chamada de dentro do
        # ``st.pintar`` que monta o rótulo, e lê este atributo.
        self._curso_antigo = False
        # Lido por ``_folha_pct``, que roda de dentro do ``st.pintar`` da
        # montagem — antes de qualquer paciente existir.
        self._pct_alerta = False
        # O quadro que está na tela e os grupos de planos dele. Guardados
        # porque trocar de PLANO no seletor repinta a partir daqui, sem pedir
        # nada ao banco: as sessões já vieram todas na leitura do curso, e uma
        # segunda consulta para reordenar o que está na memória é a chance de
        # os dois números divergirem.
        self._t = None
        self._grupos: list = []
        # Qual grupo o quadro está mostrando: ``None`` = o CURSO INTEIRO, que é
        # como a aba abre (decidido em 20/08/2026 — o número grande fala do
        # curso). O seletor é que desce ao plano.
        self._grupo_na_tela = None
        # Há cortes/DVH e fotos para mostrar? Lidos por ``_estado``, que roda
        # ANTES de ``definir_imagens``/``definir_fotos`` na primeira pintura.
        self._tem_imagens = False
        self._tem_fotos = False
        # De onde vieram as imagens. O cartão não as mostra mais (pedido do
        # usuário em 22/08/2026); quem as diz é a janela do clique. Guardadas
        # aqui para a tela ter um lugar onde a procedência possa ser LIDA sem
        # abrir a modal — inclusive pelo teste, que a modal travaria.
        self._procedencia_fotos = ""
        self._procedencia_imagens = ""
        # A janela do checklist enquanto ela está aberta: é para ela que volta
        # o que a janela principal gravou (ver ``atualizar_checklist``).
        self._janela_chk = None
        self._chk_feitos = self._chk_total = 0

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(16, 14, 16, 14)
        raiz.setSpacing(12)

        # O aviso de indisponível ocupa a tela INTEIRA quando aparece. A
        # primeira versão o deixava numa linha de rodapé, com o cabeçalho vazio
        # e a busca vazia esticados acima: a tela parecia quebrada, e o único
        # texto que explicava o que houve era o menor da janela.
        self._cartao_aviso = self._aviso()
        raiz.addWidget(self._cartao_aviso, 1)

        self.cabecalho = ui.CabecalhoPaciente()
        raiz.addWidget(self.cabecalho)

        # O painel ANTES da busca: é ele que a aba abre. A busca continua ali,
        # logo abaixo, para quem já sabe o nome.
        raiz.addWidget(self._cartao_painel(), 1)
        raiz.addWidget(self._cartao_busca())
        # No canto do cabeçalho, junto da identidade do paciente: é o botão que
        # troca justamente aquilo, e é lá que se olha para conferir de quem é a
        # tela.
        self.cabecalho.canto.addWidget(self.btn_trocar)
        self._cartao_quadro = self._quadro()
        # ABAIXO do quadro, de propósito. Em cima, a lista de cursos seria a
        # primeira coisa lida e obrigaria a uma escolha antes de mostrar o que a
        # pessoa veio ver — e essa escolha o programa já sabe fazer.
        raiz.addWidget(self._cartao_quadro)
        # Embaixo, lado a lado: as sessões à esquerda e, no espaço que sobrava
        # em branco à direita, os cortes e o DVH da ficha já elaborada (pedido
        # do usuário em 21/08/2026). A lista usa a largura de um texto e deixava
        # metade da faixa vazia; quem confere o tratamento na tela quer ver o
        # alvo sem abrir outro documento.
        self._cartao_sessoes = self._sessoes()
        self._cartao_fotos = self._fotos()
        self._cartao_imagens = self._imagens()
        # A coluna da direita empilha os dois cartões de imagem: as FOTOS em
        # cima (é o que se confere primeiro, com o paciente na mesa) e os
        # cortes embaixo.
        coluna_dir = QVBoxLayout()
        coluna_dir.setSpacing(12)
        coluna_dir.addWidget(self._cartao_fotos, 1)
        coluna_dir.addWidget(self._cartao_imagens, 1)
        linha_baixo = QHBoxLayout()
        linha_baixo.setSpacing(12)
        linha_baixo.addWidget(self._cartao_sessoes, 1)
        linha_baixo.addLayout(coluna_dir)
        raiz.addLayout(linha_baixo, 1)

        # Sem paciente, TODOS os blocos que esticam estão escondidos — e o
        # cartão de busca herdava o espaço sobrando, virando uma caixa vazia de
        # meia tela com um campo no fundo. Este espaçador existe só para ficar
        # com essa sobra; ele some quando há paciente, para não disputar altura
        # com a lista de sessões.
        self._espaco = QWidget()
        self._espaco.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        raiz.addWidget(self._espaco)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        # Registrado UMA vez. ``mostrar_status`` roda a cada troca de paciente e
        # a cada resposta do banco; um ``st.pintar`` lá dentro empilharia um
        # ouvinte por chamada — a armadilha já paga em outras telas.
        self._status_erro = False
        st.pintar(self.status, self._folha_status)
        raiz.addWidget(self.status)

        self.limpar()

    # ── O aviso que toma a tela ──────────────────────────────────────────

    def _aviso(self) -> ui.Cartao:
        cartao = ui.Cartao()
        cartao.corpo.addStretch(1)
        self.aviso_titulo = QLabel("")
        self.aviso_titulo.setAlignment(Qt.AlignCenter)
        st.pintar(self.aviso_titulo, lambda: (
            f"color:{st.TEXTO}; font-size:19px; font-weight:bold;"))
        cartao.corpo.addWidget(self.aviso_titulo)
        self.aviso_texto = QLabel("")
        self.aviso_texto.setAlignment(Qt.AlignCenter)
        self.aviso_texto.setWordWrap(True)
        # Largura FIXA, não máxima: com ``AlignHCenter`` o Qt dá ao rótulo a
        # largura do seu ``sizeHint``, e o ``sizeHint`` de um rótulo com quebra
        # de linha é ambíguo — o texto saía cortado no meio da frase ("O sistema
        # (banco de dados) não está"), que é pior que não avisar nada.
        self.aviso_texto.setFixedWidth(520)
        st.pintar(self.aviso_texto, lambda: (
            f"color:{st.TEXTO_FRACO}; font-size:13.5px;"))
        # E altura mínima para QUATRO linhas. O ``minimumSizeHint`` de um rótulo
        # com quebra de linha vale UMA linha; entre os dois esticadores desta
        # coluna, era isso que ele recebia — e a frase saía cortada no meio
        # ("…não está apontado nesta instalação. Configurações →"). Medida na
        # fonte, não em pixel fixo, para não quebrar de novo se ela mudar.
        self.aviso_texto.setMinimumHeight(
            4 * self.aviso_texto.fontMetrics().lineSpacing())
        cartao.corpo.addWidget(self.aviso_texto, 0, Qt.AlignHCenter)
        cartao.corpo.addStretch(1)
        return cartao

    # ── O painel: quem está em tratamento ────────────────────────────────

    def _cartao_painel(self) -> ui.Cartao:
        """A lista que responde "quais dos meus precisam de mim hoje?".

        É o que a aba abre. A busca desceu para atalho — busca só serve a quem
        já sabe o nome, e esse é o caso raro.
        """
        cartao = ui.Cartao("Em tratamento")
        # A faixa de "não conferido" fica DENTRO do cartão da lista, colada nos
        # números a que se refere. No rodapé, ela seria lida depois deles — e o
        # aviso só serve se chegar antes.
        self.aviso_lista = QLabel(
            "⚠  Lista ainda NÃO conferida contra o sistema. Os números podem "
            "estar errados — confira no ARIA antes de decidir por eles.")
        self.aviso_lista.setWordWrap(True)
        st.pintar(self.aviso_lista, lambda: (
            f"background:{st.AMBAR_FUNDO}; color:{st.AMBAR};"
            " border-radius:7px; padding:7px 10px;"
            " font-size:12px; font-weight:600;"))
        cartao.corpo.addWidget(self.aviso_lista)

        # SEM "incluir concluídos" (tirado a pedido do usuário em 21/08/2026).
        # O cartão chama-se EM TRATAMENTO e a pergunta que ele responde é "de
        # quem eu preciso cuidar hoje" — quem terminou não é dessa lista, e a
        # caixa oferecia um estado em que o título passava a mentir. Quem
        # procura alguém que já teve alta chega por outro caminho: a BUSCA por
        # nome, logo abaixo, que alcança o paciente independentemente de curso
        # e de janela de dias.
        # O médico e, embaixo dele, o Grupo Médico (22/09/2026). Os dois no
        # cabeçalho do cartão, que é onde estava a caixa única de antes: quem
        # abre a aba lê "Em tratamento — <médico>" numa linha só.
        self.medicos = _SeletorMedicos()
        self.medicos.mudou.connect(self._pedir_painel)
        cartao.linha_titulo.addWidget(self.medicos)

        self.painel = QListWidget()
        st.pintar(self.painel, lambda: ui.LISTA)
        # SEM fonte monoespaçada: cada linha é um widget com colunas próprias
        # (ver ``_LinhaPainel``), e o nome se lê melhor na proporcional.
        self.painel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.painel.itemSelectionChanged.connect(self._escolher_do_painel)
        self.painel.itemActivated.connect(self._confirmar_do_painel)
        self.painel.setToolTip(
            "Duplo clique (ou Enter) traz o caso inteiro para as outras telas")
        cartao.corpo.addWidget(self.painel)
        self.cartao_painel = cartao
        return cartao

    def _pedir_painel(self) -> None:
        """Pede à janela uma lista nova com os filtros de agora."""
        self.medicos_mudaram.emit([m.bruto for m in self.medicos.escolhidos()])

    def incluir_concluidos(self) -> bool:
        """Nunca. A caixa saiu da tela (ver ``_cartao_painel``).

        O método FICA, e devolvendo ``False`` fixo: quem monta a lista é a
        janela, e ela pergunta isto ao painel. Tirar o método junto com a caixa
        obrigaria a mexer no caminho da consulta para desfazer uma decisão de
        tela — e ``em_tratamento`` continua sabendo incluir concluídos, o que é
        certo: a regra de quem entra na lista é do banco, não do widget.
        """
        return False

    def _escolher_do_painel(self) -> None:
        itens = self.painel.selectedItems()
        dado = itens[0].data(Qt.UserRole) if itens else None
        if dado is None:
            return
        self._registro = dado.registro
        # A 3×4 do paciente ANTERIOR não pode sobreviver à troca nem por um
        # repinte: a foto está ali justamente para conferir de relance de quem é
        # a tela, e uma foto errada nesse posto mente com mais força que
        # qualquer campo. Quem a repõe é ``definir_foto``, com a nova.
        self._foto = None
        self._pintar_cabecalho(dado.registro, dado.nome)
        self.paciente_escolhido.emit(dado.registro, dado.nome)

    @staticmethod
    def _linha_painel(e, hoje=None) -> str:
        marcas = e.marcas(hoje)
        simbolos = "".join(s for s, _t in marcas) or " "
        # As marcas vêm ANTES do nome: numa coluna à esquerda elas formam uma
        # faixa que se varre de cima a baixo em um movimento. À direita, seria
        # preciso ler cada linha inteira para descobrir se há algo lá.
        # SÓ a marca mais urgente em texto. Emendar as três punha a linha além
        # da largura da tela e ligava a barra horizontal — e uma lista que rola
        # de lado deixa de ser varrível de cima a baixo, que é a única coisa que
        # ela precisa ser. O resto vai no tooltip (ver ``definir_em_tratamento``).
        return (f"{simbolos:<4} {e.nome[:30]:<30} "
                f"{e.entregues:>3}/{e.previstas or '?':<4} "
                f"{(e.ultima.strftime('%d/%m') if e.ultima else '—'):<7} "
                + (marcas[0][1] if marcas else ""))

    def _por_titulo_de_faixa(self, titulo: str, quantos: int) -> None:
        """Põe o título de uma faixa na lista, como item NÃO selecionável.

        ``NoItemFlags`` e não só "item sem dado": selecionável, ele aceitaria o
        clique e o teclado pararia nele ao descer a lista.

        A contagem entra no título porque é ela que a faixa existe para dar —
        "quantos precisam de mim hoje" é a pergunta, e sem o número é preciso
        contar as linhas com o dedo.

        Widget com ``st.pintar``, e não ``setForeground`` no item: a cor do
        item é congelada no momento em que ele nasce, e o painel não é
        remontado na troca dia↔noite — o título ficaria com a cor do tema
        anterior enquanto o resto da lista já teria virado.
        """
        item = QListWidgetItem()
        item.setFlags(Qt.NoItemFlags)
        item.setSizeHint(QSize(0, _ALTURA_FAIXA))
        rot = QLabel(f"{titulo}   ({quantos})")
        st.pintar(rot, lambda: (f"color:{st.TEXTO_APAGADO}; font-size:11px;"
                                " font-weight:600; padding-left:6px;"))
        self.painel.addItem(item)
        self.painel.setItemWidget(item, rot)

    def definir_em_tratamento(self, linhas: list, hoje=None,
                              falhou: bool = False) -> None:
        """Repõe o painel. ``falhou`` distingue erro de "não há ninguém"."""
        self.painel.blockSignals(True)
        self.painel.clear()
        # De quem é cada paciente só interessa quando a lista tem mais de um
        # médico: com o Grupo Médico ligado, ou com "Todos os médicos". Um
        # médico só já está escrito no cabeçalho do cartão.
        mostrar_medico = len(self.medicos.escolhidos()) != 1
        # Em FAIXAS (pedido do usuário em 21/08/2026): a ordenação por urgência
        # já punha as linhas certas em cima, mas ordem sozinha não diz onde um
        # assunto termina e o outro começa. Quem varre a lista de manhã quer
        # saber QUANTOS casos exigem decisão hoje — e isso é contagem, não
        # posição.
        #
        # Estes títulos são item da lista, ao contrário do cabeçalho de colunas
        # das sessões: ali ficar parado é o certo (o rótulo vale para a lista
        # inteira), aqui rolar junto é o certo, porque o título pertence ao
        # bloco que vem embaixo dele.
        for _chave, titulo, do_grupo in tratamento_db.por_faixa(linhas, hoje):
            self._por_titulo_de_faixa(titulo, len(do_grupo))
            for e in do_grupo:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, e)
                linha = _LinhaPainel(e, hoje,
                                     mostrar_medico=mostrar_medico)
                # Largura ZERO no palpite de tamanho: o que interessa é a
                # ALTURA. Com a largura natural (que inclui o nome inteiro), o
                # item ficava mais largo que a área visível e ligava a barra
                # horizontal — a mesma armadilha já paga na lista de recentes
                # da Fichinha.
                item.setSizeHint(QSize(0, _LinhaPainel.ALTURA))
                self.painel.addItem(item)
                self.painel.setItemWidget(item, linha)
        if not linhas:
            self.painel.addItem(
                "(não consegui ler a lista — não é o mesmo que estar vazia)"
                if falhou else "(ninguém em tratamento nesta janela)")
        self.painel.blockSignals(False)

    def definir_medicos(self, medicos: list, marcados=()) -> None:
        self.medicos.definir(medicos, marcados)

    # ── Busca ────────────────────────────────────────────────────────────

    def _cartao_busca(self) -> ui.Cartao:
        cartao = ui.Cartao("Paciente")
        # Altura pelo conteúdo, não pelo espaço livre — ver ``self._espaco``.
        cartao.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.busca = ui.entrada(dica="nome ou registro")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(self._filtrar)
        cartao.corpo.addWidget(self.busca)

        self.lista = QListWidget()
        st.pintar(self.lista, lambda: ui.LISTA)
        self.lista.setMaximumHeight(132)
        self.lista.itemSelectionChanged.connect(self._escolher)
        self.lista.itemActivated.connect(self._confirmar)
        self.lista.setToolTip(
            "Duplo clique (ou Enter) traz o caso inteiro para as outras telas")
        cartao.corpo.addWidget(self.lista)
        self.cartao_busca = cartao

        # Fora do cartão: com o paciente na tela, a busca inteira sai e sobra
        # este botão. Deixá-la aberta custaria o bloco mais alto da tela para
        # repetir uma escolha já feita — e é o bloco que empurra para baixo
        # justamente o número que se veio ver.
        self.btn_trocar = ui.botao("🔎  Trocar paciente", altura=30)
        self.btn_trocar.clicked.connect(self._trocar_paciente)
        self.btn_trocar.setVisible(False)
        return cartao

    def _trocar_paciente(self) -> None:
        self.limpar()
        self.busca.setFocus()

    def definir_pacientes(self, refs: list) -> None:
        """A lista para a busca — a mesma de ``capa_dados.pacientes``."""
        self._pacientes = list(refs)
        self._filtrar()

    def _filtrar(self, *_) -> None:
        termo = self.busca.text().strip()
        self.lista.clear()
        # A lista SOME enquanto não há o que mostrar. Com o painel na tela, uma
        # caixa vazia embaixo dele era só altura gasta para repetir o convite
        # que o próprio campo já faz.
        self.lista.setVisible(bool(self._pacientes) and len(termo) >= 2)
        self.busca.setPlaceholderText(
            f"nome ou registro — {len(self._pacientes)} pacientes"
            if self._pacientes else "nome ou registro")
        if not self._pacientes:
            self.lista.setVisible(True)
            self.lista.addItem("(lista de pacientes não carregada)")
            return
        if len(termo) < 2:
            return
        achados = [p for p in self._pacientes if p.casa(termo)]
        for p in achados[:_MAX_RESULTADOS]:
            item = QListWidgetItem(p.rotulo())
            item.setData(Qt.UserRole, p)
            self.lista.addItem(item)
        if not achados:
            self.lista.addItem("(nenhum paciente com esse nome ou registro)")
        elif len(achados) > _MAX_RESULTADOS:
            self.lista.addItem(
                f"… e mais {len(achados) - _MAX_RESULTADOS} — refine a busca")

    def _escolher(self) -> None:
        itens = self.lista.selectedItems()
        ref = itens[0].data(Qt.UserRole) if itens else None
        if ref is None:
            return
        self._registro = ref.registro
        self._foto = None          # ver ``_escolher_do_painel``
        self._pintar_cabecalho(ref.registro, ref.nome)
        self.paciente_escolhido.emit(ref.registro, ref.nome)

    def _confirmar(self, item) -> None:
        """Duplo clique ou Enter na busca: é ESTE."""
        ref = item.data(Qt.UserRole) if item is not None else None
        if ref is not None:
            self.paciente_confirmado.emit(ref.registro, ref.nome)

    def _confirmar_do_painel(self, item) -> None:
        """O mesmo, no painel de quem está em tratamento."""
        dado = item.data(Qt.UserRole) if item is not None else None
        if dado is not None:
            self.paciente_confirmado.emit(dado.registro, dado.nome)

    def nome_na_tela(self) -> str:
        """O nome do paciente que está na faixa — quem monta a consulta de
        fotos precisa dele, e ``mostrar`` não recebe nome nenhum."""
        texto = self.cabecalho.nome.text()
        return "" if texto == "—" else texto

    def curso_na_tela(self):
        """O curso que está na tela, ou ``None``. É a chave do checklist.

        ``None`` não vira 0: um paciente cujo curso o banco não devolveu não é
        "o curso zero", e juntar os dois numa chave só misturaria a conferência
        de pacientes diferentes (ver ``checklist.chave``).
        """
        return self._curso_na_tela

    def registro_na_tela(self) -> str:
        """De quem é o que está na tela AGORA — vazio quando não há ninguém.

        Quem monta a janela usa isto para decidir se a aba já está no paciente
        da vez (``gui._tratamento_seguir_o_foco``). Comparar com o nome não
        serve: homônimo existe, e trocar de paciente por engano nesta tela é
        ler o tratamento de outra pessoa sem perceber.
        """
        return self._registro

    def assumir_paciente(self, ref) -> None:
        """Mostra ESTE paciente, como se ele tivesse sido escolhido na busca.

        Quem chama é a janela, quando a aba abre com um caso na bancada (ver
        ``gui._tratamento_seguir_a_bancada``). Passa pelo mesmo caminho do
        clique — inclusive zerando a foto — para não haver dois jeitos de a aba
        trocar de paciente, que é como um deles esquece de limpar alguma coisa.
        """
        self._registro = ref.registro
        self._foto = None
        self.definir_imagens()
        self.definir_fotos()
        self._pintar_cabecalho(ref.registro, ref.nome)
        self.paciente_escolhido.emit(ref.registro, ref.nome)

    def _pintar_cabecalho(self, registro: str, nome: str, medico: str = "",
                          nascimento: str = "", convenio: str = "",
                          maquina: str = "") -> None:
        """Identidade do paciente e, ao lado, com quem e onde ele trata.

        As MESMAS pílulas da Capa, na mesma ordem e com os mesmos tons: quem
        alterna entre as duas abas do mesmo paciente não deve ter de reaprender
        onde cada coisa está. Primeira fileira, quem é (registro, nascimento,
        convênio); segunda, o médico e a MÁQUINA em que ele está tratando —
        pedido do usuário em 21/08/2026.

        A máquina vem da última sessão APLICADA, não do plano: é a que a pessoa
        está usando de fato, e ela muda quando há remanejamento.

        Tudo além do registro chega VAZIO no gesto de escolher e é preenchido
        quando o quadro chega (``mostrar``): buscar isto no clique travava a
        tela até o servidor responder — 8 s com o banco fora do ar. Campo sem
        fonte sai vazio e ``definir`` esconde a pílula, porque pílula em branco
        lê-se como dado faltando.

        A foto vem de ``self._foto``: ``definir`` repõe TUDO da faixa, e sem
        devolvê-la aqui a 3×4 do paciente sumia quando o médico chegava.
        """
        self.cabecalho.definir(
            nome,
            [(registro, "azul"), (nascimento, "neutro"), (convenio, "neutro")],
            self._foto,
            extras=[(equipe.medico_por_extenso(medico), "azul"),
                    (maquina, "verde")])

    # ── O quadro: fração, dose, intervalos ───────────────────────────────

    def _escolher_curso(self, indice: int) -> None:
        """Só o GESTO de escolher troca — ``activated``, não ``currentIndexChanged``.

        O segundo dispara também quando o programa repõe a lista, e aí montar a
        tela pedia outra leitura ao banco, cuja resposta remontava a lista de
        novo.
        """
        curso = self.cursos.itemData(indice)
        if curso is None or curso == self._curso_na_tela:
            return
        self.curso_escolhido.emit(self._registro, int(curso))

    def _pintar_cursos(self, cursos: list, atual_na_tela) -> None:
        """Repõe o seletor e marca o que está na tela.

        O seletor aparece SEMPRE, mesmo com um curso só — é ele que responde
        "este paciente tem histórico?" sem obrigar ninguém a descobrir que
        havia uma lista escondida. Com um curso, fica apagado: botão aceso
        significa pronto, e não há para onde ir.
        """
        self.cursos.blockSignals(True)
        self.cursos.clear()
        for c in cursos:
            # A bolinha marca o curso em andamento e não depende de cor — que é
            # o que se perde numa tela vista de longe.
            marca = "●" if c.atual and not c.concluido() else "   "
            self.cursos.addItem(f"{marca} {c.rotulo()}", c.id)
            if c.id == atual_na_tela:
                self.cursos.setCurrentIndex(self.cursos.count() - 1)
        self.cursos.blockSignals(False)
        _popup_legivel(self.cursos)
        self.cursos.setEnabled(len(cursos) > 1)
        self.cursos.setToolTip("" if len(cursos) > 1
                               else "Este paciente tem um curso só.")

    def _pintar_planos(self, t) -> None:
        """Repõe o seletor de PLANO com os grupos deste curso.

        A lista abre no CURSO INTEIRO quando há mais de um grupo — o número
        grande fala do curso desde 20/08/2026, e mudar isso esconderia o
        replanejamento de quem não abre seletor nenhum. Os grupos vêm depois,
        do mais recente para trás.

        Com UM grupo só (o caso comum), o curso e o plano são a mesma coisa: o
        seletor mostra o nome do plano — que é o que o rótulo antigo mostrava —
        e fica apagado, porque não há para onde ir. O item guarda ``None`` de
        propósito: assim os números continuam vindo do CURSO, como sempre
        vieram, e um paciente comum não muda de comportamento por causa desta
        tela nova.
        """
        self._grupos = tratamento_db.grupos_do_curso(t)
        self.plano_sel.blockSignals(True)
        self.plano_sel.clear()
        varios = len(self._grupos) > 1
        if varios:
            # "Todos", e não "Curso inteiro": o item mora sob o rótulo
            # PLANO(S), e "PLANO: Curso inteiro" não responde à etiqueta que
            # está do lado dele. Com o QUE ele soma, porque sem o número o item
            # é uma opção sem consequência anunciada — e ninguém troca de item
            # para descobrir o que ele faz.
            self.plano_sel.addItem(
                f"Todos   ·   {t.entregues} "
                + ("fração" if t.entregues == 1 else "frações")
                + f" em {len(self._grupos)} planos", None)
        for i, g in enumerate(self._grupos):
            # A bolinha marca o grupo em curso e não depende de cor — que é o
            # que se perde numa tela vista de longe. A mesma do seletor de
            # cursos, pelo mesmo motivo.
            marca = "●" if g.atual else "   "
            self.plano_sel.addItem(f"{marca} {g.rotulo()}",
                                   i if varios else None)
        self.plano_sel.setCurrentIndex(0)
        self.plano_sel.blockSignals(False)
        self._grupo_na_tela = None
        self.plano_sel.setEnabled(varios)
        self.plano_sel.setToolTip(
            "" if varios else
            "Este curso tem um plano só — o quadro já é dele.")
        # O par rótulo+seletor some junto quando não há plano nenhum a nomear:
        # seletor vazio ao lado de um rótulo é campo que promete dado e não
        # entrega.
        tem = bool(self._grupos and any(g.nome for g in self._grupos))
        self.plano_rot.setVisible(tem)
        self.plano_sel.setVisible(tem)
        _popup_legivel(self.plano_sel)

    def _escolher_plano(self, indice: int) -> None:
        """Trocar de plano NÃO fala com o banco — ver ``_pintar_planos``.

        ``activated``, como no seletor de cursos: o outro sinal dispara também
        quando o programa repõe a lista, e aí repor a lista repintaria o quadro
        no meio da pintura que estava repondo a lista.
        """
        if self._t is None:
            return
        escolhido = self.plano_sel.itemData(indice)
        if escolhido == self._grupo_na_tela:
            return
        # Marcar o item é do CLIQUE, e o Qt já o fez quando o gesto veio da
        # tela. Refazê-lo aqui é o que mantém honesta a chamada de fora (o
        # teste, e a tela quando ela mesma escolher um plano): sem isto o
        # quadro passava a falar de um plano com o seletor ainda dizendo
        # "Todos" — a mesma mistura de escopos que produziu o "9 / 4".
        self.plano_sel.setCurrentIndex(indice)
        self._grupo_na_tela = escolhido
        self._pintar_quadro()

    def _escopo(self) -> tuple:
        """``(entregues, previstas, sessoes, doses, escopo)`` do que está na tela.

        UM lugar decide se o quadro fala do curso ou de um plano; sem isto, cada
        pedaço da pintura repetiria o mesmo ``if`` e um deles ficaria para trás
        na primeira mudança — que é exatamente como a lista de sessões passou a
        discordar do número grande em 20/08/2026.
        """
        t = self._t
        g = (self._grupos[self._grupo_na_tela]
             if self._grupo_na_tela is not None
             and self._grupo_na_tela < len(self._grupos) else None)
        if g is None:
            return (t.entregues, t.previstas, t.sessoes, t.doses, "curso")
        # A dose vem SÓ dos planos deste grupo. A do curso não serve aqui:
        # somar o que dois tratamentos diferentes entregaram a alvos diferentes
        # é a conta que não existe, e escrevê-la ao lado do nome de um plano é
        # atribuir a ele a dose do outro.
        doses = [d for d in t.doses if d.plano in g.planos]
        return (g.entregues, g.previstas, g.sessoes, doses, "plano")

    def _quadro(self) -> ui.Cartao:
        cartao = ui.Cartao()
        # Qual curso está na tela, e se ele é o de agora. Sem esta linha, quem
        # clica num curso de 2022 vê "5 / 5" em corpo 64 e nada dizendo que
        # aquilo terminou há quatro anos.
        # CURSO num seletor, sempre visível — e não num cartão que sumia
        # quando havia um curso só. Quem abre um paciente não tem como adivinhar
        # que existe histórico escondido; o seletor mostra que existe (ou que
        # não existe) sem precisar de nada.
        linha_curso = QHBoxLayout()
        linha_curso.setSpacing(10)
        linha_curso.addWidget(ui.rotulo("CURSO", forte=True))
        self.cursos = QComboBox()
        self.cursos.setMinimumWidth(330)
        self.cursos.setFixedHeight(30)
        # Cresce com a janela: com largura fixa, "C2_JUL_2026 03/08/2026 –
        # 19/08/2026 · EM TRATAMENTO" saía cortado no meio da data, e o pedaço
        # que sumia era justamente o que diz se o curso está ativo.
        self.cursos.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cursos.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        # Sem ``combobox-popup: 0`` o Qt IGNORA ``setMaxVisibleItems`` quando há
        # folha de estilo, e a lista suspensa abria com dois itens e meio,
        # cortando o de baixo pela metade.
        self.cursos.setMaxVisibleItems(12)
        st.pintar(self.cursos, self._folha_combo)
        self.cursos.activated.connect(self._escolher_curso)
        linha_curso.addWidget(self.cursos, 1)

        # O PLANO ao lado, e agora num SELETOR — não mais num rótulo.
        #
        # O rótulo bastava enquanto "o curso" e "o plano" fossem a mesma coisa.
        # Não são: a paciente de 26/08/2026 tinha um curso só com uma SBRT de
        # pulmão (4 frações) e, depois, uma mandíbula (5) — e o quadro mostrava
        # "9 / 4", que é a fração do CURSO dividida pelo total de UM plano. Com
        # o seletor, cada plano responde pelo próprio número, e o curso pelo
        # dele.
        #
        # O nome continua em destaque: é como o plano é chamado em toda
        # conversa do serviço ("MAMA D", "BOOST"), e o ``DimPlanID`` do banco
        # não diz nada a ninguém.
        self.plano_rot = ui.rotulo("PLANO", forte=True)
        linha_curso.addWidget(self.plano_rot)
        self.plano_sel = QComboBox()
        self.plano_sel.setMinimumWidth(260)
        self.plano_sel.setFixedHeight(30)
        self.plano_sel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.plano_sel.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.plano_sel.setMaxVisibleItems(12)
        st.pintar(self.plano_sel, self._folha_combo)
        self.plano_sel.activated.connect(self._escolher_plano)
        linha_curso.addWidget(self.plano_sel, 1)
        cartao.corpo.addLayout(linha_curso)

        self.curso_rot = QLabel("")
        st.pintar(self.curso_rot, self._folha_curso)
        cartao.corpo.addWidget(self.curso_rot)

        # A PRESCRIÇÃO, com o sítio: "Mama, esquerda: Mama + FSC E 40,05Gy@15fx"
        # (pedido do usuário em 21/08/2026). É o mesmo texto que a CAPA imprime
        # — vem de ``capa_db.prescricoes_do_paciente`` —, e é de propósito: a
        # aba mostra o que ACONTECEU, e ter ao lado o que foi PRESCRITO é o que
        # deixa comparar os dois sem abrir outro documento. Dois textos
        # diferentes para a mesma prescrição, em duas telas do mesmo programa,
        # é o que faz duvidar das duas.
        #
        # Vazio quando não há prescrição casada com ESTE curso — nunca a de
        # outro curso "porque é a única": num retratamento, sítio errado aqui é
        # o pior campo possível para se errar.
        self.rx = QLabel("")
        self.rx.setWordWrap(True)
        st.pintar(self.rx, lambda: (
            f"color:{st.TEXTO_FRACO}; font-size:12.5px;"))
        self.rx.hide()
        cartao.corpo.addWidget(self.rx)

        self.fracao = _NumeroGrande("Fração")
        cartao.corpo.addWidget(self.fracao)
        self.barra = _Barra()
        cartao.corpo.addWidget(self.barra)

        self.pct = QLabel("")
        self.pct.setWordWrap(True)
        # Registrada UMA vez, e reaplicada à mão em ``_pintar_quadro``: um
        # ``st.pintar`` a cada pintura empilharia um ouvinte por chamada — a
        # armadilha já paga em outras telas.
        st.pintar(self.pct, self._folha_pct)
        cartao.corpo.addWidget(self.pct)

        # A linha dos PLANOS: o que veio antes do de agora (replanejamento) e o
        # que trata junto com ele (mama + FSC). Cada metade só aparece quando é
        # o caso, e as duas são obrigatórias quando aparecem — o número grande
        # fala do CURSO, e sem esta linha "21 de 30" não diz que 8 delas são do
        # plano de agora e 13 vieram de antes, nem que as duas linhas de "fração
        # 7" do mesmo dia são uma sessão só.
        self.planos = QLabel("")
        st.pintar(self.planos, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:12.5px;"))
        cartao.corpo.addWidget(self.planos)

        # Uma fileira de cartõezinhos: última sessão, dose e intervalos. São o
        # segundo nível de leitura — quem chegou pela fração já tem o que
        # queria, e olha para cá só quando a resposta é "depende".
        self.linha_valores = _Fileira(espaco=10)
        cartao.corpo.addLayout(self.linha_valores)
        self._valores: list = []
        # O PDF da ficha com a MESMA forma dos cartões de valor (pedido do
        # usuário em 21/08/2026), para a fileira alternar azul e neutro sem um
        # botão de outra família quebrando o ritmo no fim dela. Ele continua
        # sendo um botão no comportamento — cursor de mão, clique, estado
        # apagado —, e é um ``ui.Valor`` na aparência para não haver duas
        # gramáticas visuais na mesma linha.
        self.btn_pdf = _ValorClicavel("PDF", "Ficha Técnica", "azul")
        self.btn_pdf.nao_quebrar()   # ver ``_pintar_valores``
        self.btn_pdf.clicado.connect(self.abrir_pdf)
        self.btn_pdf.definir_ativo(False)
        self.linha_valores.addWidget(self.btn_pdf)

        # Os dois vizinhos do PDF (pedido do usuário em 24/08/2026). Mesma
        # forma, mesmo gesto — três portas para a mesma ficha, e uma família
        # visual só. O NOME que distingue vai na linha grande: os três se
        # chamariam "… Ficha Técnica", e três cartões com a mesma linha em
        # destaque são indistinguíveis de relance.
        #
        # O checklist mostra o ANDAMENTO no próprio cartão. "Conferido" e "por
        # conferir" são estados diferentes, e é essa a pergunta que ele existe
        # para responder — um cartão que só dissesse "Checklist" obrigaria a
        # abrir a janela para descobrir se havia algo a fazer.
        self.btn_checklist = _ValorClicavel("Checklist", "—", "neutro")
        self.btn_checklist.nao_quebrar()
        self.btn_checklist.clicado.connect(self.abrir_checklist)
        self.btn_checklist.definir_ativo(False)
        self.linha_valores.addWidget(self.btn_checklist)

        self.btn_campos = _ValorClicavel("Ficha Técnica", "Campos", "azul")
        self.btn_campos.nao_quebrar()
        self.btn_campos.clicado.connect(self.abrir_campos)
        self.btn_campos.definir_ativo(False)
        self.linha_valores.addWidget(self.btn_campos)
        self._ajustar_vao()
        return cartao

    def _ajustar_vao(self) -> None:
        """O vão da coluna da direita só existe quando ELA existe.

        É um vão à direita da fileira (antes era um espaçador de largura
        fixa), do tamanho exato dos cartões de imagem mais o espaçamento: é o
        que faz os cartões de valor terminarem onde a lista de sessões termina.
        Flexível: a fileira o dispensa quando ele a obrigaria a quebrar linha
        (ver ``_Fileira._dispor``).
        Sem ele os valores passavam por baixo da coluna de imagens — duas
        grades desalinhadas na mesma tela, e o olho procura uma continuidade
        que não existe.

        Reservado SEMPRE, porém, ele somava 572 px de NADA à largura mínima da
        aba, e o paciente sem fotos e sem ficha elaborada é o caso comum. Junto
        com a fileira que não encolhia, era isso que empurrava o painel para
        2110 px e cortava o "Trocar paciente" fora da tela (ver ``_Fileira``).
        """
        # Pelas bandeiras, não por ``isVisible``: com a aba escondida (outro
        # modo na frente) todo filho responde False, e o vão zeraria por
        # motivo errado — voltando torto quando a aba aparecesse.
        coluna = self._tem_fotos or self._tem_imagens
        self.linha_valores.definir_vao(_LARG_IMAGENS + 12 if coluna else 0)

    def definir_pdf(self, caminho: str = "") -> None:
        """Há PDF da ficha para abrir? Liga ou apaga o cartão, com o motivo."""
        self._pdf = caminho or ""
        self.btn_pdf.definir_ativo(bool(self._pdf))
        self.btn_pdf.setToolTip(
            f"Abrir {self._pdf}" if self._pdf else
            "Este paciente não tem ficha elaborada neste programa — não há "
            "PDF para abrir.")

    def definir_checklist(self, feitos: int = 0, total: int = 0,
                          divergentes: int = 0, disponivel: bool = True) -> None:
        """O andamento da conferência, no rosto do cartão.

        Três estados, e cada um com uma frase diferente porque são perguntas
        diferentes: **por conferir** (ninguém marcou), **n de 6** (começou e
        parou no meio) e **conferido**. O caso do meio existe de verdade — a
        conferência se interrompe com o paciente na porta —, e um cartão que
        só soubesse dizer "sim/não" arredondaria isso para um dos dois.

        A DIVERGÊNCIA ganha a frente de tudo: seis de seis respondidos com um
        "não conforme" no meio é uma conferência completa e um paciente que não
        pode subir na mesa. Dizer "conferido" ali seria a tela dando um aval
        que a conferência justamente negou.
        """
        self._chk_feitos, self._chk_total = int(feitos), int(total)
        if not disponivel:
            # Sem curso identificado não há a QUE prender a conferência: o
            # checklist é por curso, e gravá-lo sem curso juntaria numa entrada
            # só o retratamento de dois anos depois.
            self.btn_checklist.val.setText("—")
            self.btn_checklist.definir_ativo(False)
            self.btn_checklist.setToolTip(
                "Sem curso identificado para este paciente — o checklist é "
                "por curso, e não há a qual prendê-lo.")
            return
        if divergentes:
            texto = f"{divergentes} não conforme"
        elif total and feitos >= total:
            texto = "conferido"
        elif feitos:
            texto = f"{feitos} de {total}"
        else:
            texto = "por conferir"
        self.btn_checklist.val.setText(texto)
        self.btn_checklist.definir_ativo(True)
        self.btn_checklist.setToolTip(
            "Checklist Pré-Tratamento — o mesmo da contracapa. Clique para "
            "conferir ou consultar quem conferiu.")

    def definir_campos(self, disponivel: bool = False) -> None:
        """Liga o cartão dos campos só quando há ficha elaborada para mostrar.

        Botão aceso significa pronto (regra do projeto): sem ficha salva, o
        clique só teria um aviso para dar, e o motivo cabe no tooltip.
        """
        self.btn_campos.definir_ativo(bool(disponivel))
        self.btn_campos.setToolTip(
            "Campos de tratamento da pág. 2 da ficha — SSD, mordentes, "
            "gantry, mesa, UM." if disponivel else
            "Este paciente não tem ficha elaborada neste programa — não há "
            "campos gravados para mostrar.")

    def mostrar_checklist(self, marcas: dict, titulo: str = "") -> None:
        """Abre a conferência. Quem lê e grava o arquivo é a janela principal.

        A janela fica GUARDADA enquanto está aberta: cada clique vai para o
        disco e volta por ``atualizar_checklist``, e sem a referência não
        haveria a quem devolver o que foi gravado.
        """
        self._janela_chk = _JanelaChecklist(
            marcas, checklist.ITENS, checklist.MARCAS, checklist.LEGENDA,
            titulo, self)
        self._janela_chk.marcou.connect(self.checklist_marcado)
        try:
            _abrir_na_frente(self._janela_chk)
        finally:
            self._janela_chk = None

    def atualizar_checklist(self, marcas: dict) -> None:
        """O que ficou GRAVADO volta para a grade — ver ``definir_marcas``."""
        if self._janela_chk is not None:
            self._janela_chk.definir_marcas(marcas)

    def mostrar_campos(self, plano: list, campos: list, linhas: list,
                       origem: str = "") -> None:
        """Abre a tabela de campos da ficha elaborada (leitura)."""
        _abrir_na_frente(
            _JanelaCampos(plano, campos, linhas, origem, self))

    def _pintar_valores(self, pares: list) -> None:
        """Refaz a fileira. ``pares``: lista de (rótulo, valor, tom).

        O ``tom`` de cada par é IGNORADO: a fileira alterna azul e neutro pela
        POSIÇÃO (pedido do usuário em 21/08/2026 — "verde branco verde
        branco"). A alternância só funciona por posição porque metade dos
        cartões é condicional: com o tom preso a cada assunto, sumir a parada
        ou a frequência deixava dois vizinhos da mesma cor.

        Nada se perde nisso. O único tom que já carregou significado era o da
        parada — azul para parada longa —, e desde que o cartão só aparece
        quando HÁ parada é a presença dele que dá o aviso, não a cor.
        """
        for w in self._valores:
            w.setParent(None)
            w.deleteLater()
        self._valores = []
        # As três PORTAS (PDF, Checklist, Campos) saem da fileira para VOLTAR
        # no fim dela: ``_Fileira`` é uma ``QLayout`` crua e não tem
        # ``insertWidget``, e elas têm de ficar depois dos cartões de dado —
        # no meio deles, um botão quebraria o ritmo que a ordem existe para
        # manter. Juntas e nesta ordem: o PDF é o gesto de sempre, e os dois
        # vizinhos são as portas que ele ganhou em 24/08/2026.
        acoes = (self.btn_pdf, self.btn_checklist, self.btn_campos)
        for b in acoes:
            self.linha_valores.removeWidget(b)
        for i, (rot, val, _tom) in enumerate(pares):
            tom = "azul" if i % 2 == 0 else "neutro"
            v = ui.Valor(rot, val or "—", tom, self._cartao_quadro)
            # SEM quebra de linha nesta fileira. ``ui.Valor`` quebra por padrão
            # — serve à Fichinha, onde o preparo é uma frase —, e aqui a
            # quebra escondia metade do dado: a segunda linha não cabe na
            # altura da fileira e o valor aparecia cortado ("Uma Vez", "2240
            # cGy de"). Sem quebra, o cartão pede a largura do que escreve.
            v.nao_quebrar()
            self.linha_valores.addWidget(v)
            self._valores.append(v)
        # As três continuam a alternância pela POSIÇÃO, como os cartões de
        # dado: elas fecham a fileira e não podem ser a exceção que quebra o
        # "verde branco verde branco" logo no fim.
        for j, b in enumerate(acoes):
            self.linha_valores.addWidget(b)
            # ``definir_tom``, não ``tom`` + ``setStyleSheet``: a cor do VALOR
            # mora noutra folha, e mexer só na do quadro deixava as três com
            # texto azul sobre fundo neutro — a alternância quebrava justamente
            # nelas.
            b.definir_tom("azul" if (len(pares) + j) % 2 == 0 else "neutro")

    # ── O histórico ──────────────────────────────────────────────────────

    def _sessoes(self) -> ui.Cartao:
        cartao = ui.Cartao("Sessões aplicadas")
        fixa = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        # O cabeçalho das colunas fica FORA da lista. Como item dela seria
        # selecionável, entraria na rolagem e sumiria na primeira linha que se
        # desce — justamente quando a lista é longa e o rótulo faz falta.
        # ``cab_colunas``, não ``cabecalho``: este último já é o cabeçalho do
        # PACIENTE (``_Cabecalho``), e reaproveitar o nome trocaria um pelo
        # outro em ``limpar()`` — que chama ``self.cabecalho.definir(...)``.
        #
        # A faixa é um pai SEM layout, e o rótulo é posicionado à mão dentro
        # dela: a lista rola na horizontal quando a linha passa da largura
        # (PLANO longo + "TBuniverSN1002" + dois técnicos, que é a linha comum
        # desde 20/08), e o rótulo precisa rolar JUNTO. Parado, ele passa a
        # apontar para a coluna errada — que é o contrário do que existe para
        # fazer. O pai recorta o que sair dele, e é ele que entra no layout.
        self._faixa_cab = QWidget()
        self.cab_colunas = QLabel("", self._faixa_cab)
        self.cab_colunas.setFont(fixa)
        # MESMO corpo de fonte da lista (12.5px, na folha ``ui.LISTA``) e o
        # mesmo recuo dela — ``_RECUO_CAB``. Com qualquer um dos dois diferente,
        # o rótulo deixa de parar em cima da coluna, que é a única coisa que ele
        # tem de fazer. Nada de negrito nem de espaçamento de letra aqui, pelo
        # mesmo motivo. O recuo é posição, não ``padding``: o ``padding`` não
        # aceita valor negativo, e é negativo que ele fica com a lista rolada.
        st.pintar(self.cab_colunas, lambda: (
            f"color:{st.TEXTO_APAGADO}; font-size:12.5px;"))
        self._faixa_cab.hide()
        cartao.corpo.addWidget(self._faixa_cab)
        self.tabela = QListWidget()
        st.pintar(self.tabela, lambda: ui.LISTA)
        # Monoespaçada porque as colunas de ``_linha_sessao`` são feitas de
        # espaços. Com a fonte proporcional do resto do app, o preenchimento não
        # alinha nada — e uma coluna quase alinhada é pior de ler que texto
        # corrido, porque o olho tenta seguir uma grade que não existe.
        self.tabela.setFont(fixa)
        self.tabela.horizontalScrollBar().valueChanged.connect(
            self._rolar_cabecalho)
        cartao.corpo.addWidget(self.tabela)
        return cartao

    def _cartao_de_duas_imagens(self, titulo: str, esq: tuple,
                                dir_: tuple) -> tuple:
        """O molde dos dois cartões da coluna da direita.

        Um só molde porque eles são a MESMA coisa para quem lê: duas imagens
        lado a lado. Montá-los separados deixaria as larguras, o zoom e o vazio
        divergirem com o tempo — e duas colunas quase iguais na mesma tela
        leem-se pior que duas iguais.

        **Sem rodapé de procedência no rosto do cartão** (pedido do usuário em
        22/08/2026: "fica mais clean"). Ela não sumiu: viajou para a janela que
        se abre no clique, junto da imagem grande — ver ``_JanelaImagem``. Aqui
        ela era uma terceira linha de 11px sob duas miniaturas de 90px, lida de
        raspão ou não lida; lá ela chega no momento em que alguém está de fato
        olhando a imagem para decidir alguma coisa.

        ``esq``/``dir_``: ``(texto quando vazio, título da janela de zoom)``.
        Devolve ``(cartão, imagem esquerda, imagem direita)``.
        """
        cartao = ui.Cartao(titulo)
        # Largura FIXA: é ela que os cartões de valor do quadro reservam para
        # terminarem onde a lista de sessões termina.
        cartao.setFixedWidth(_LARG_IMAGENS)
        linha = QHBoxLayout()
        linha.setSpacing(10)
        img_esq = _ImagemEscalada(*esq)
        img_dir = _ImagemEscalada(*dir_)
        linha.addWidget(img_esq, 1)
        linha.addWidget(img_dir, 1)
        cartao.corpo.addLayout(linha, 1)
        return cartao, img_esq, img_dir

    def _fotos(self) -> ui.Cartao:
        """Fotos e posicionamento — o que o dosimetrista registrou na TC.

        Mesmo princípio dos cortes: esta aba não monta nada, mostra o que já
        foi registrado. A fonte é o cadastro de simulação do paciente
        (``simulacao.procurar`` + ``carregar``), o mesmo que alimenta a Capa —
        e por isso a montagem que aparece aqui é a que está impressa na capa
        que anda grampeada com a ficha.

        Duas fotos, que é o que cabe: quantas MAIS existem — para ninguém achar
        que viu tudo — vai na janela que se abre no clique, junto da foto
        grande, e não num rodapé sob as miniaturas (ver
        ``_cartao_de_duas_imagens``).
        """
        # O título é montado em DUAS partes — "FOTOS E" + "POSICIONAMENTO" —
        # porque a segunda é clicável e abre a nota. Lê-se como um título só.
        cartao, self.foto_a, self.foto_b = \
            self._cartao_de_duas_imagens(
                "Fotos e",
                ("sem foto", "Posicionamento"),
                ("sem foto", "Posicionamento"))
        self.nota = _Nota()
        # Índice 1: logo depois do rótulo do cartão e ANTES do esticador que o
        # ``ui.Cartao`` já pôs — no fim da linha ela iria parar do outro lado,
        # separada da palavra que completa.
        cartao.linha_titulo.insertWidget(1, self.nota)
        # O SELETOR de posicionamento, no título do cartão. Ele lista o que
        # existe como dado — as montagens registradas, nomeadas pela NOTA
        # ("TORAX", "META", "CRÂNIO") —, e não os nomes de plano do TPS
        # ("_sTORAX_D1"): casar os dois por semelhança de nome erraria em
        # silêncio, e errar de montagem é pôr o paciente na mesa do jeito
        # errado. Pedido do usuário em 21/08/2026.
        #
        # É provisório POR DECISÃO, não por descuido: quando o cadastro da
        # simulação passar a ser feito pelo dosimetrista dentro do app, o
        # vínculo nota↔plano nasce na elaboração da CAPA, e aí este seletor
        # passa a oferecer o plano tratado em vez do nome da nota (dito pelo
        # usuário em 21/08/2026). Até lá, escolher a montagem à mão é o único
        # jeito honesto.
        self.combo_setup = QComboBox()
        self.combo_setup.setMaximumWidth(190)
        st.pintar(self.combo_setup, self._folha_combo)
        self.combo_setup.activated.connect(self._trocar_setup)
        self.combo_setup.hide()
        cartao.linha_titulo.addWidget(self.combo_setup)
        self._setups: list = []
        return cartao

    def definir_fotos(self, setups=(), origem: str = "") -> None:
        """Os posicionamentos deste paciente. ``setups``: ``(nome, fotos, nota)``.

        Com mais de um, o seletor aparece — é o caso de quem tem crânio e
        metástase na mesma simulação, montagens diferentes com notas
        diferentes. Com um só não há escolha a oferecer, e um combo de item
        único é uma pergunta que já tem resposta.
        """
        self._setups = [s for s in (setups or []) if s[1]]
        self.combo_setup.blockSignals(True)
        self.combo_setup.clear()
        for nome, fotos, _nota in self._setups:
            self.combo_setup.addItem(f"{nome or 'Posicionamento'}"
                                     f"  ({len(fotos)})")
        self.combo_setup.blockSignals(False)
        # Sem isto o pop-up abria com a altura que o Qt calcula pelo estilo, e
        # o segundo item ("CRÂNIO (2)") saía cortado no meio da linha — o mesmo
        # defeito dos seletores de curso e de plano.
        _popup_legivel(self.combo_setup)
        self.combo_setup.setVisible(len(self._setups) > 1)
        self._origem_fotos = origem
        self._tem_fotos = bool(self._setups)
        self._cartao_fotos.setVisible(self._tem_fotos)
        self._ajustar_vao()
        self._trocar_setup(0)

    def _trocar_setup(self, indice: int) -> None:
        """Põe na tela o posicionamento escolhido."""
        if not self._setups:
            self.foto_a.definir(None)
            self.foto_b.definir(None)
            self.nota.definir("")
            self.procedencia_fotos("")
            return
        indice = max(0, min(int(indice or 0), len(self._setups) - 1))
        self.combo_setup.setCurrentIndex(indice)
        nome, fotos, nota = self._setups[indice]
        self.foto_a.definir(fotos[0] if fotos else None)
        self.foto_b.definir(fotos[1] if len(fotos) > 1 else None)
        # A nota entra na PALAVRA do título, não na tela: ver ``_Nota``.
        self.nota.definir(nota)
        # A procedência NÃO repete o nome da montagem (pedido do usuário em
        # 21/08/2026): ele já está no seletor quando há mais de uma, e com uma
        # só o nome da nota não acrescenta nada ao que as fotos mostram. Fica o
        # que elas não dizem — quantas ficaram de fora e de onde vieram.
        sobram = len(fotos) - 2
        partes = []
        if sobram > 0:
            partes.append(f"+{sobram} foto{'s' if sobram > 1 else ''}")
        if getattr(self, "_origem_fotos", ""):
            partes.append(self._origem_fotos)
        self.procedencia_fotos("  ·  ".join(partes))

    def procedencia_fotos(self, texto: str = "") -> None:
        """O mesmo texto nas duas fotos e na nota — elas são a MESMA montagem.

        Guardado também em ``_procedencia_fotos`` porque o cartão não o mostra
        mais (ver ``_cartao_de_duas_imagens``): sem um lugar onde lê-lo, o
        teste teria de abrir a janela modal, que trava a suíte.
        """
        self._procedencia_fotos = texto or ""
        self.foto_a.definir_procedencia(self._procedencia_fotos)
        self.foto_b.definir_procedencia(self._procedencia_fotos)
        self.nota.definir_procedencia(self._procedencia_fotos)

    def _imagens(self) -> ui.Cartao:
        """Cortes e DVH — os da FICHA JÁ ELABORADA, não recalculados aqui.

        Esta aba lê o data warehouse e não tem DICOM nenhum: as duas imagens
        vêm dos PNG que a ficha daquele paciente gravou (índice central,
        ``indice.listar_versoes``). Recalculá-las exigiria a TC inteira, que
        não está aqui — e, mais importante, o que se quer conferir é o que foi
        IMPRESSO e foi para a sala.

        Por isso elas dizem de QUE ficha vieram, com a data: um replanejamento
        gera ficha nova, e um corte de duas versões atrás mostra um alvo que já
        não é o do tratamento em curso. Imagem sem procedência é a pior espécie
        de imagem numa tela de conferência — o que mudou em 22/08/2026 é ONDE
        ela é dita: na janela do clique, junto da imagem grande, e não num
        rodapé sob as miniaturas.
        """
        cartao, self.img_cortes, self.img_dvh = \
            self._cartao_de_duas_imagens(
                "Cortes e DVH",
                ("sem cortes", "Cortes ortogonais"),
                ("sem DVH", "DVH"))
        return cartao

    def definir_imagens(self, cortes: Optional[bytes] = None,
                        dvh: Optional[bytes] = None, origem: str = "") -> None:
        """As imagens da ficha deste paciente, e de onde elas vieram.

        Sem nenhuma das duas, o cartão inteiro SOME — não fica um par de
        molduras vazias prometendo imagem que não existe. Paciente cuja ficha
        nunca foi elaborada por este programa é o caso comum, não o excepcional.
        """
        self.img_cortes.definir(cortes)
        self.img_dvh.definir(dvh)
        # As duas vieram da MESMA ficha: a procedência é uma só, e vai nas duas
        # janelas de zoom (ver ``_JanelaImagem``), não no rosto do cartão.
        self._procedencia_imagens = origem or ""
        self.img_cortes.definir_procedencia(self._procedencia_imagens)
        self.img_dvh.definir_procedencia(self._procedencia_imagens)
        self._tem_imagens = bool(cortes or dvh)
        self._cartao_imagens.setVisible(self._tem_imagens)
        self._ajustar_vao()

    def _rolar_cabecalho(self, valor: int = 0) -> None:
        """Põe o rótulo das colunas na mesma horizontal em que a lista está."""
        self.cab_colunas.move(_RECUO_CAB - int(valor or 0), 0)

    def _mostrar_cab_colunas(self, texto: str, visivel: bool) -> None:
        """Refaz o rótulo e devolve à faixa a altura dele.

        ``adjustSize`` antes de medir: o rótulo não está em layout nenhum (ver o
        ``_sessoes``), então ninguém o dimensiona por ele — sem isto a faixa
        nasce com a altura de um rótulo vazio e o cabeçalho não aparece.
        """
        self.cab_colunas.setText(texto)
        self.cab_colunas.adjustSize()
        self._faixa_cab.setFixedHeight(self.cab_colunas.height())
        self._rolar_cabecalho(self.tabela.horizontalScrollBar().value())
        self._faixa_cab.setVisible(visivel)

    @staticmethod
    def _rotulo_plano(s, plano_por_ordem) -> str:
        """O NOME do plano, não "P2": é como ele é chamado no serviço. O número
        por ordem só entra quando o banco não deu nome nenhum."""
        if not plano_por_ordem:
            return ""
        return (s.plano_nome or f"P{plano_por_ordem.get(s.plano, '?')}")[:16]

    @classmethod
    def _colunas(cls, sessoes, plano_por_ordem=None) -> tuple:
        """``(largura do plano, largura da máquina)`` medidas na lista INTEIRA.

        Número fixo não serve: a coluna da máquina já foi de 10 para 12 por
        causa de "TBuniverSN", e "TBuniverSN1002" — 14 — voltou a colar o nome
        de quem tratou na máquina. E medir por linha desalinharia a coluna
        seguinte, que é o que a fonte monoespaçada existe para evitar aqui.

        A máquina é medida pelo nome que a linha DESENHA (o do serviço), não
        pelo que o banco entrega (o de fábrica). Hoje o de exibição é o mais
        curto dos dois e só sobraria folga; mas a linha tem guarda de largura e
        o cabeçalho não, então um rótulo mais longo que a chave traria de volta,
        calado, o desalinhamento de 20/08/2026.
        """
        plano = max([len(cls._rotulo_plano(s, plano_por_ordem))
                     for s in sessoes] + [len(_CAB_PLANO)]) if plano_por_ordem \
            else 0
        maquina = max([len(constantes.rotulo_maquina(s.maquina or ""))
                       for s in sessoes] + [len(_CAB_MAQUINA)])
        return plano, maquina

    @classmethod
    def _cabecalho_sessoes(cls, col_plano=0, col_maquina=0) -> str:
        """A linha de rótulos, montada pelas MESMAS larguras das linhas."""
        cols = [f"{_CAB_FRACAO:>{_COL_FRACAO}}"]
        if col_plano:
            cols.append(f"{_CAB_PLANO:<{col_plano}}")
        cols += [f"{_CAB_DATA:<{_COL_DATA}}", f"{_CAB_HORA:<{_COL_HORA}}",
                 f"{_CAB_MAQUINA:<{col_maquina}}", _CAB_QUEM]
        return _SEP.join(cols)

    @classmethod
    def _linha_sessao(cls, s, plano_por_ordem=None, col_plano=0,
                      col_maquina=0) -> str:
        """Uma sessão em texto de largura fixa — colunas sem tabela.

        ``QListWidget`` com texto alinhado à mão, e não ``QTableWidget``: a
        tabela do Qt traz cabeçalho, grade e seleção de célula, três coisas que
        aqui não servem para nada e roubam altura da lista.
        """
        # A fração primeiro, o plano depois: sem o plano na linha, duas delas se
        # chamam "fração 8" — a do plano de agora e a do plano anterior — e não
        # há como saber qual é qual.
        cols = [f"{s.fracao if s.fracao else '·':>{_COL_FRACAO}}"]
        if plano_por_ordem:
            rotulo = cls._rotulo_plano(s, plano_por_ordem)
            cols.append(f"{rotulo:<{max(col_plano, len(rotulo))}}")
        # Sem fonte no banco, o campo fica VAZIO e diz que está vazio: é a regra
        # do projeto, e aqui ela importa mais que em qualquer outra tela —
        # atribuir a sessão a quem não a fez é pior que não dizer quem fez.
        maquina = constantes.rotulo_maquina(s.maquina or "")
        cols += [f"{s.data_br():<{_COL_DATA}}", f"{s.hora or '—':<{_COL_HORA}}",
                 f"{maquina:<{max(int(col_maquina or 0), len(maquina))}}",
                 s.quem_tratou() or "(não informado)"]
        return _SEP.join(cols)

    # ── Estados da tela ──────────────────────────────────────────────────

    def limpar(self) -> None:
        """Nenhum paciente escolhido — o estado em que a aba abre."""
        self._registro = ""
        self._foto = None
        self.cabecalho.definir("—", [])
        self.fracao.definir("—", "")
        self.barra.definir(0)
        self.pct.setText("")
        self._pintar_valores([])
        self.tabela.clear()
        # Cabeçalho de coluna sobre lista vazia é espaço reservado "por via das
        # dúvidas" — e ainda promete uma tabela que não está ali.
        self._faixa_cab.hide()
        self.busca.clear()
        self.lista.clearSelection()
        self._curso_na_tela = None
        self._curso_antigo = False
        self.curso_rot.setText("")
        self.rx.setText("")
        self.rx.hide()
        # Pelo mesmo motivo da 3×4: imagem do paciente ANTERIOR sobrevivendo à
        # troca mente com mais força que qualquer campo desta tela.
        self.definir_imagens()
        self.definir_fotos()
        # As três portas voltam apagadas: elas falam da ficha de UM paciente, e
        # botão aceso apontando para a ficha do anterior é a versão mais cara
        # deste erro — abre o documento de outra pessoa.
        self.definir_pdf("")
        self.definir_checklist(disponivel=False)
        self.definir_campos(False)
        self.cursos.clear()
        # O seletor de PLANO e o quadro guardado saem junto com o resto: um
        # seletor com os planos do paciente ANTERIOR é a versão desta tela do
        # erro mais caro que ela pode cometer — oferecer, com o nome certo no
        # topo, o tratamento de outra pessoa.
        self.plano_sel.clear()
        self._t = None
        self._grupos = []
        self._grupo_na_tela = None
        if not tratamento_db.disponivel():
            self._so_aviso("Tratamento indisponível",
                           tratamento_db.motivo_indisponivel())
            return
        self._estado(aviso=False, busca=True, paciente=False)
        self.mostrar_status("Procure o paciente pelo nome ou pelo registro.")

    def sem_conexao(self) -> None:
        """O banco está apontado, mas não respondeu a lista de pacientes.

        Estado próprio, e não "nenhum paciente encontrado": a diferença entre
        "não há" e "não consegui perguntar" é a diferença entre desistir e
        chamar a TI.
        """
        self._so_aviso(
            "Sem resposta do sistema",
            "O banco está apontado, mas não respondeu. Esta aba lê o "
            "tratamento direto do sistema e não tem reserva — sem ele não há o "
            "que mostrar.\n\nSe o problema persistir, o botão “Atualizar dos "
            "relatórios” na aba Capa força uma nova tentativa de conexão.")

    def _so_aviso(self, titulo: str, texto: str) -> None:
        """A tela inteira vira o recado — ver o comentário no ``__init__``."""
        self.aviso_titulo.setText(titulo)
        self.aviso_texto.setText(texto)
        self._estado(aviso=True, busca=False, paciente=False)
        self.mostrar_status("")

    def _folha_combo(self) -> str:
        """A mesma do seletor de médicos — dois combos com cara diferente na
        mesma tela leem-se como coisas de naturezas diferentes, e não são."""
        return (
            f"QComboBox {{ background:{st.FUNDO_CAMPO}; color:{st.TEXTO};"
            f"  border:1px solid {st.BORDA}; border-radius:7px;"
            "   padding:0 8px; font-size:12.5px; combobox-popup:0; }"
            "QComboBox::drop-down { border:none; width:18px; }"
            # BORDA_FORTE, e não a borda comum: o pop-up abre POR CIMA do
            # cartão, e com a mesma linha do resto ele não se separava do fundo
            # — a lista parecia texto solto no meio da tela.
            f"QComboBox QAbstractItemView {{ background:{st.FUNDO_BLOCO};"
            f"  color:{st.TEXTO}; selection-background-color:{st.ACAO_FUNDO};"
            f"  selection-color:{st.TEXTO};"
            f"  border:1px solid {st.BORDA_FORTE}; border-radius:7px;"
            "   outline:none; padding:3px; font-size:12.5px; }"
            # ``min-height`` continua aqui para o item PINTADO acompanhar a
            # altura reservada em ``_popup_legivel`` — as duas coisas são
            # necessárias, e nenhuma das duas sozinha resolve.
            f"QComboBox QAbstractItemView::item {{ min-height:{_ALTURA_ITEM}px;"
            "  padding:0 8px; border-radius:5px; }"
            f"QComboBox QAbstractItemView::item:hover {{"
            f"  background:{st.ACAO_FUNDO}; }}")

    def _folha_pct(self) -> str:
        """Âmbar quando o total informado pelo sistema NÃO fecha com o aplicado.

        Âmbar e não vermelho, pela mesma razão do aviso de curso antigo: não é
        erro de ninguém que se possa consertar aqui — é um número do sistema
        que fala de outra coisa. O que não pode é passar despercebido, cinza,
        no lugar onde antes havia um "/ 4".
        """
        cor = st.AMBAR if self._pct_alerta else st.TEXTO_FRACO
        return f"color:{cor}; font-size:13px; font-weight:600;"

    def _folha_curso(self) -> str:
        """Âmbar quando o que está na tela NÃO é o curso de agora.

        Âmbar e não vermelho: olhar um curso antigo não é erro, é consulta. O
        que não pode é olhar sem saber que é antigo.
        """
        cor = st.AMBAR if self._curso_antigo else st.TEXTO_FRACO
        return f"color:{cor}; font-size:12.5px; font-weight:700;"

    def _estado(self, aviso: bool, busca: bool, paciente: bool) -> None:
        """Os três blocos da tela, ligados e desligados de um lugar só.

        Antes cada método mexia no que lembrava, e sobrava um cabeçalho vazio
        de "—" com foto tracejada por cima do aviso de banco desligado.
        """
        self._cartao_aviso.setVisible(aviso)
        # O cabeçalho é a IDENTIDADE do paciente: sem paciente escolhido ele era
        # uma faixa alta com "—" e uma moldura tracejada de "sem foto", ocupando
        # o topo da tela para não dizer nada. Só aparece quando há de quem
        # falar.
        self.cabecalho.setVisible(paciente)
        self.cartao_busca.setVisible(busca)
        # O painel só existe enquanto ele estiver conferido (ver
        # ``tratamento_db.LISTA_VERIFICADA_EM``); sem ele a aba é a busca, que
        # está conferida e funciona.
        self.cartao_painel.setVisible(busca and tratamento_db.lista_disponivel())
        self.aviso_lista.setVisible(not tratamento_db.lista_conferida())
        # O espaçador só faz falta quando NADA estica: com o painel na tela, é
        # ele quem toma a sobra.
        self._espaco.setVisible(
            not paciente and not self.cartao_painel.isVisible())
        self.btn_trocar.setVisible(paciente)
        self._cartao_quadro.setVisible(paciente)
        self._cartao_sessoes.setVisible(paciente)
        # O cartão de imagens só aparece com paciente E com imagem: sem elas
        # ele seria uma moldura vazia roubando metade da faixa das sessões.
        self._cartao_imagens.setVisible(paciente and self._tem_imagens)
        self._cartao_fotos.setVisible(paciente and self._tem_fotos)

    def definir_foto(self, dados) -> None:
        """A 3×4 do banco. Confere de relance que a tela é do paciente certo."""
        # GUARDADA, e não só entregue ao retrato: ``CabecalhoPaciente.definir``
        # repõe a foto junto com o nome e os chips, e quem a chama depois — o
        # médico chegando com o quadro — apagava a 3×4 passando ``None``. A foto
        # sumia da tela sem que nada no caminho parecesse errado.
        self._foto = dados
        self.cabecalho.retrato.definir(dados)

    def mostrar(self, t: Optional[tratamento_db.Tratamento]) -> None:
        """Põe o tratamento na tela. ``None`` = não deu para saber.

        "Não deu para saber" e "não há sessões" precisam de recados DIFERENTES:
        o primeiro é problema de banco e a pessoa deve tentar de novo; o segundo
        é um paciente que ainda não começou, e insistir não muda nada.
        """
        if t is None:
            self._estado(aviso=False, busca=True, paciente=False)
            self.mostrar_status(
                tratamento_db.motivo_indisponivel()
                or "Não consegui ler o tratamento deste paciente no sistema — "
                   "ou ele ainda não iniciou.",
                erro=True)
            return
        self._estado(aviso=False, busca=False, paciente=True)
        # A identificação chega com o quadro; a faixa foi pintada só com o
        # registro no clique. Repintar com o nome do paciente que já está lá:
        # ``mostrar`` também é chamada ao trocar de curso, e reler o nome de
        # ``t`` traria vazio.
        ultima_sessao = t.ultima()
        if t.medico or t.nascimento or t.convenio or ultima_sessao:
            self._pintar_cabecalho(
                t.registro or self._registro, self.cabecalho.nome.text(),
                t.medico, t.nascimento, t.convenio,
                ultima_sessao.maquina if ultima_sessao else "")
        self._curso_na_tela = t.curso.id if t.curso else None
        self._pintar_cursos(t.cursos, self._curso_na_tela)
        # O quadro fica guardado: é dele que o seletor de PLANO repinta, sem
        # pedir nada ao banco.
        self._t = t
        self._pintar_planos(t)

        # O rótulo abaixo do seletor NÃO repete a identidade do curso — isso o
        # próprio seletor já diz, e ler a mesma coisa duas vezes em duas linhas
        # seguidas é ruído. Ele carrega só o AVISO de curso antigo, que é o que
        # o seletor não consegue gritar.
        self._curso_antigo = bool(t.curso and not t.curso.atual)
        self.curso_rot.setText(
            "⟵ este é um curso ANTERIOR; o atual é o primeiro do seletor"
            if self._curso_antigo else "")
        self.curso_rot.setStyleSheet(self._folha_curso())
        self.curso_rot.setVisible(bool(self.curso_rot.text()))

        # A prescrição só aparece quando existe. Rótulo "Rx" vazio ao lado de
        # nada é campo que promete dado e não entrega — e nesta tela vazio tem
        # significado: é "não há prescrição casada com este curso".
        self.rx.setText(f"Rx   {t.prescricao}" if t.prescricao else "")
        self.rx.setVisible(bool(t.prescricao))
        self._pintar_quadro()

    def _pintar_quadro(self) -> None:
        """Os números, os cartões e a lista — do CURSO ou de um PLANO dele.

        Separado de ``mostrar`` porque trocar de plano no seletor repinta só
        isto: a identidade do paciente, o seletor de cursos e a prescrição são
        do CURSO e não mudam com a escolha. Repintá-los faria a faixa do topo
        piscar a cada clique, e o nome do paciente é o último lugar da tela onde
        se quer movimento.
        """
        t = self._t
        if t is None:
            return
        entregues, previstas, sessoes, doses, escopo = self._escopo()
        # O rótulo vai ao PLURAL quando há mais de um plano no que está na
        # tela: "PLANO cMAMA + cFSC" faria o olho ler um nome composto onde há
        # dois planos no sistema. Segue o escopo, e não o curso — com um dos
        # planos escolhido, o plural teria de falar de planos que a tela deixou
        # de mostrar.
        varios = (len({x.plano for x in sessoes if x.plano}) > 1
                  if escopo == "curso"
                  else len(self._grupos[self._grupo_na_tela].planos) > 1)
        self.plano_rot.setText("PLANOS" if varios else "PLANO")
        # Denominador que NÃO cobre o que já foi aplicado não é denominador
        # deste escopo (ver ``tratamento_db.cobre``): ele some, e a linha abaixo
        # diz por quê. "9 / 4" em corpo 64 é pior que "9" sozinho, porque tem a
        # FORMA de uma conta — e quem lê de longe lê a forma.
        confere = tratamento_db.cobre(entregues, previstas)
        total = previstas if confere else 0
        self.fracao.definir(str(entregues), f"/ {total}" if total else "")
        pct = min(100, round(100 * entregues / total)) if total else 0
        self.barra.definir(pct)
        # Barra sem denominador é uma afirmação sobre o andamento feita sem
        # saber o andamento: vazia, ela diz "não começou" de um paciente com
        # nove frações aplicadas.
        self.barra.setVisible(bool(total))
        alvo = "tratamento" if escopo == "curso" else "plano"
        if total:
            # "faltam 0 frações" era o que aparecia num curso terminado — a
            # frase existe para dizer quanto falta, e quando não falta nada ela
            # tem de dizer OUTRA coisa, não zero.
            faltam = max(0, total - entregues)
            if faltam == 0:
                self.pct.setText(f"{total} de {total} frações — "
                                 f"{alvo} concluído")
            else:
                self.pct.setText(
                    f"{pct}% do {alvo} — "
                    + (f"falta {faltam} fração" if faltam == 1
                       else f"faltam {faltam} frações"))
        elif previstas:
            # O caso que trouxe o seletor de plano: o sistema informa um total
            # que é de UM plano, e as frações contadas são as do curso inteiro.
            # A tela não escolhe entre os dois números — diz que eles não falam
            # da mesma coisa e aponta onde ver cada um.
            self.pct.setText(
                f"O sistema informa {previstas} frações previstas, menos que "
                f"as {entregues} já aplicadas"
                + (" — este total é de um dos planos. Escolha o plano no "
                   "seletor para ver o número dele."
                   if escopo == "curso" else "."))
        else:
            # Sem o total prescrito, "48%" seria inventado. O que se sabe é
            # quantas foram; é só isso que a tela diz.
            self.pct.setText("Total de frações não informado pelo sistema.")
        self._pct_alerta = bool(previstas and not confere)
        self.pct.setStyleSheet(self._folha_pct())

        self.planos.setText(self._linha_de_contexto(escopo))
        self.planos.setVisible(bool(self.planos.text()))

        ultima = sessoes[0] if sessoes else None
        quando = (f"{ultima.data_br()}  {ultima.hora}".strip()
                  if ultima else "")
        intervalos = tratamento_db.intervalos_das_sessoes(sessoes)
        longos = [i for i in intervalos if i.dias_uteis >= _INTERVALO_ATENCAO]
        texto_int = ""
        if intervalos:
            texto_int = intervalos[0].texto()
            if len(intervalos) > 1:
                texto_int += f"  (+{len(intervalos) - 1})"
        tom_int = "azul" if longos else "neutro"
        # A dose QUEBRADA POR PLANO quando os planos declaram doses diferentes
        # (pedido do usuário em 21/08/2026). Dois planos simultâneos são alvos
        # DIFERENTES — "sMEDIAST_DB" e "sHILO-D_DIB" —, e um número só de dose
        # entregue ali não quer dizer nada: dose a alvos diferentes não se soma.
        # Quando o banco devolve o mesmo número para todos, esse número é do
        # CURSO e o cartão continua um só (ver ``tratamento_db.doses_distintas``).
        if tratamento_db.doses_distintas(doses):
            cartoes_dose = [(f"Dose {d.nome}"[:22], d.texto(), "azul")
                            for d in doses if d.texto()]
        elif escopo == "curso":
            dose = (f"{t.dose_entregue_cgy:.0f} cGy"
                    if t.dose_entregue_cgy else "")
            if dose and t.dose_prescrita_cgy:
                dose += f"  de {t.dose_prescrita_cgy:.0f}"
            cartoes_dose = [("Dose entregue", dose, "azul")]
        else:
            # Com um plano na tela, a dose do CURSO não serve: ela inclui o que
            # os outros planos entregaram a outros alvos, e escrevê-la sob o
            # nome deste plano é atribuir a ele a dose do vizinho. Sem número
            # por plano, o cartão não aparece — vazio aqui é "não sei", e é o
            # que a tela tem a dizer.
            texto_dose = doses[0].texto() if doses else ""
            cartoes_dose = ([("Dose entregue", texto_dose, "azul")]
                            if texto_dose else [])
        # O cartão de parada SÓ quando houve parada (pedido do usuário em
        # 21/08/2026). "Sem paradas" é a resposta na maioria dos tratamentos, e
        # um cartão que quase sempre diz a mesma coisa deixa de ser lido — ele
        # só ocupa a largura que os outros três precisam. Ausência aqui é
        # informação: sem cartão, não houve parada.
        cartao_parada = [("Maior parada" if len(intervalos) > 1 else "Parada",
                          texto_int, tom_int)] if intervalos else []
        # FREQUÊNCIA em cartão próprio (pedido do usuário em 21/08/2026): ela
        # já estava na linha da prescrição, mas some no meio dela — e é o
        # campo que responde "o paciente vem amanhã?", que é a pergunta de
        # quem organiza a agenda da máquina.
        cartao_freq = [("Frequência", t.frequencia, "neutro")] \
            if t.frequencia else []
        # CONTROLE RESPIRATÓRIO só quando há: DIBH e gating mudam a montagem na
        # mesa e o tempo da sessão, e não aparecer é a resposta para a maioria.
        cartao_resp = [("Controle respiratório", t.respiratorio, "azul")] \
            if t.respiratorio else []
        # "Quem tratou" SAIU da fileira (pedido do usuário em 21/08/2026): o
        # nome já está na coluna da lista de sessões, linha a linha, e ali ele
        # diz mais — quem tratou CADA fração, não só a última. Repetido aqui,
        # gastava a largura de um cartão para dizer de novo o que a tabela logo
        # abaixo já dizia melhor.
        cartao_dose_dia = [("Dose/dia", f"{t.dose_dia} cGy", "neutro")] \
            if t.dose_dia else []
        # TÉRMINO PREVISTO (pedido do usuário em 21/08/2026): a mesma conta da
        # faixa "terminam esta semana" do painel, agora com a data escrita. Não
        # aparece no que já acabou — prever o fim do que terminou é ruído — nem
        # sem denominador, porque aí não há data, só chute.
        fim = (tratamento_db.prever_fim(ultima.data if ultima else None,
                                        total - entregues, t.frequencia)
               if total and entregues < total else None)
        cartao_fim = [("Término previsto", fim.strftime("%d/%m/%Y"), "neutro")] \
            if fim else []
        self._pintar_valores([
            ("Última sessão", quando, "azul"),
            *cartao_fim,
            *cartoes_dose,
            *cartao_dose_dia,
            *cartao_freq,
            *cartao_resp,
            *cartao_parada,
        ])

        self.tabela.clear()
        # Numera os planos por ORDEM CRONOLÓGICA (P1 é o primeiro), não pelo
        # DimPlanID: o id do banco é um número de seis dígitos que não diz nada
        # a quem lê, e o que importa é qual veio antes.
        #
        # A numeração sai do CURSO INTEIRO mesmo quando a lista mostra um plano
        # só: assim "P3" continua sendo P3 ao trocar de item no seletor. Rótulo
        # que muda de significado conforme o filtro é pior que rótulo nenhum.
        #
        # A coluna aparece por haver MAIS DE UM PLANO no que está na tela, não
        # por replanejamento: com mama + FSC não houve replanejamento nenhum, e
        # ainda assim são duas linhas de "fração 7" no mesmo dia — sem a coluna,
        # nada diz que elas são de planos diferentes.
        ordem = {}
        if len({s.plano for s in sessoes if s.plano}) > 1:
            for i, plano in enumerate(dict.fromkeys(
                    s.plano for s in reversed(t.sessoes) if s.plano), start=1):
                ordem[plano] = i
        col_plano, col_maquina = self._colunas(sessoes, ordem)
        self._mostrar_cab_colunas(
            self._cabecalho_sessoes(col_plano, col_maquina), bool(sessoes))
        for s in sessoes:
            self.tabela.addItem(
                self._linha_sessao(s, ordem, col_plano, col_maquina))
        if longos:
            self.mostrar_status(
                f"Atenção: {len(longos)} "
                + ("parada" if len(longos) == 1 else "paradas")
                + f" de {_INTERVALO_ATENCAO} dias úteis ou mais no meio do "
                  "tratamento.")
        else:
            self.mostrar_status("")

    def _linha_de_contexto(self, escopo: str) -> str:
        """A linha miúda sob o número grande: o que ele NÃO está contando.

        O número grande fala de uma coisa só, e é sempre a outra que explica o
        que se vê logo abaixo: sem esta linha, "21 de 30" não diz que 8 frações
        são do plano de agora e 13 vieram de antes, nem que as duas linhas de
        "fração 7" do mesmo dia são uma sessão só.

        Com um PLANO na tela ela muda de lado: o que falta dizer, aí, é que
        existe curso em volta dele — e quanto o curso somou.
        """
        t = self._t
        partes = []
        if escopo == "plano":
            i = self._grupo_na_tela
            g = self._grupos[i]
            # Contados do mais ANTIGO para o mais recente: os grupos vêm do
            # mais recente para trás (é o que a tela precisa oferecer primeiro),
            # mas "plano 1" é o que tratou primeiro — numerar ao contrário do
            # tempo é o que faz "plano 2" ser lido como o segundo tratamento
            # quando ele foi o primeiro.
            partes.append(f"plano {len(self._grupos) - i} de "
                          f"{len(self._grupos)} deste curso")
            partes.append(f"o curso somou {t.entregues} "
                          + ("fração" if t.entregues == 1 else "frações"))
            if len(g.planos) > 1:
                partes.append(f"{len(g.planos)} planos tratam juntos — cada "
                              "dia é UMA fração")
            return "   ·   ".join(partes)
        # Escopo do curso: o que veio ANTES do plano de agora (replanejamento) e
        # o que trata JUNTO com ele (mama + FSC). Cada metade só aparece quando
        # é o caso.
        if t.replanejado():
            antes, anteriores = t.antes_do_plano_atual(), t.planos - 1
            partes.append(
                f"plano atual{f' ({t.plano_nome})' if t.plano_nome else ''}: "
                f"{t.plano_entregues} de {t.plano_previstas or '?'}")
            partes.append(
                f"antes dele: {antes}"
                f" {'fração' if antes == 1 else 'frações'}"
                + (f" em {anteriores} planos anteriores" if anteriores > 1
                   else ""))
        if t.simultaneos():
            partes.append(f"{t.juntos} planos tratam juntos — cada dia é UMA "
                          "fração")
        return "   ·   ".join(partes)

    def _folha_status(self) -> str:
        return (f"color:{st.VERMELHO if self._status_erro else st.TEXTO_FRACO};"
                " font-size:12px;")

    def mostrar_status(self, msg: str, erro: bool = False) -> None:
        self._status_erro = erro
        self.status.setText(msg or "")
        self.status.setVisible(bool(msg))
        self.status.setStyleSheet(self._folha_status())
