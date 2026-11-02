"""ISOCENTRO — Interface desktop (PySide6; PyQt5 até a R-23).

Visualizador em grade 2×2: Axial | Sagital / Coronal | 3D corpo.
Colorwash de isodose (intervalo configurável) e seleção de estruturas em todos
os planos. Carregamento da TC, plano e pasta em threads de fundo.
"""

from __future__ import annotations

import contextlib
import datetime
import logging
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (Qt, QTimer)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from isocentro.interface.ajustes import ajustes
from isocentro.dominio import agendamento as ag
from isocentro.dominio import aprendizado
from isocentro.banco import atividades_db
from isocentro.interface import capa as capa_tela
from isocentro.interface.caso import Caso
from isocentro.dados import datas_relevantes
from isocentro.banco import capa_dados
from isocentro.papel import capa_pdf
from isocentro.interface import agenda_tela
from isocentro.interface import controle_agenda
from isocentro.interface import controle_radioteradados
from isocentro.interface import radioteradados_tela
from isocentro.interface import torre
from isocentro.interface import controle_capa
from isocentro.interface import controle_ficha
from isocentro.interface import controle_viewer
from isocentro.interface import controle_virtual
from isocentro.dicom import ct_series
from isocentro.dicom import dicom_rt
from isocentro.dicom import dose3d
from isocentro.adaptadores.dicom import leitura
from isocentro.interface import fichinha
from isocentro.dominio import gatilho_registro
from isocentro.dados import historico
from isocentro.dados import indice
from isocentro.interface import portao_ficha
from isocentro.interface import qualidade_tela
from isocentro.interface import documentacao_tela
from isocentro.interface import simulacao
from isocentro.dados import registro_json
from isocentro.dados import sessao
from isocentro.interface import tratamento
from isocentro.interface import ui
from isocentro.interface import estilo
# As FUNÇÕES podem vir por nome — elas leem a paleta na hora em que são
# chamadas. As CORES, não: ``from estilo import ACAO`` congelaria o valor do
# modo em vigor no momento do import, e a troca dia↔noite não chegaria aqui.
# Cor sempre por ``estilo.NOME``.

_LOG = logging.getLogger(__name__)

# A frase de "ficha em andamento" mora com quem gera a ficha (corte 6c).
from isocentro.interface.controle_ficha import _FICHA_EM_ANDAMENTO  # noqa: E402

# O arquivo de log, a lista de quem chega ao histórico compartilhado e o
# handler que faz a ponte moravam AQUI até 14/09/2026. Foram para o
# ``dados/log_app.py`` porque a exportação automática ganhou porta de entrada
# própria — o executável sem tela da concentradora —, e ela não pode importar a
# interface só para deixar rastro. Duas cópias da lista se afastariam em
# silêncio, que é o mesmo motivo de o ``DENTRO_DO_PACOTE`` ser lista única.


# ── Persistência de equipe (médicos e físicos) ───────────────────────────────
# As listas canônicas moram em ``equipe``; o arquivo guarda o DELTA do usuário sobre
# elas — quem ele acrescentou, quem ele removeu e as unidades que escolheu —, e
# a lista é remontada a cada leitura.
#
# O cadastro de equipe mora em ``equipe.py`` desde 25/08/2026: o painel de
# Equipe das Configurações e o formulário da bancada usam os MESMOS acessos, e
# de dentro do ``gui`` o módulo de administração não teria como alcançá-los sem
# importar o ``gui`` de volta.
#
# Os dois internos (``_cadastro_equipe``, ``_salvar_cadastro``) vêm junto de
# propósito: mudar de ARQUIVO e mudar de ENDEREÇO ao mesmo tempo são duas
# mudanças, e só uma delas é conferível pela suíte que já existe. Quando os
# testes de equipe migrarem para um ``test_equipe`` próprio, estes dois saem.
from isocentro.dados.equipe import (  # noqa: E402,F401
    _cadastro_equipe, _carregar_fisicos, _carregar_medicos, _salvar_cadastro,
    _salvar_fisicos, _salvar_medicos)


# As cargas em segundo plano moram em ``carregadores.py`` desde 27/08/2026 —
# mesmo motivo do ``administracao.py``. Reimportadas AQUI porque
# ``gui._CarregarTudo`` é o endereço que a suíte já usa.
from isocentro.interface.carregadores import (  # noqa: E402,F401
    _CarregarCorpo3d, _CarregarTudo, _norm_registro, _rd_com_fallback,
    pacientes_na_pasta)


# Os estilos de botão (_estilo_btn, _estilo_btn_sel, _estilo_btn_menu e
# _marcar_ativo) moram em ``estilo.py`` — a Fichinha e o agendamento usam os
# mesmos, e um módulo neutro evita o ciclo de import entre eles e o gui. Desde
# 27/08/2026 quem os importa é ``agendamento_tela.py``; aqui não sobrou uso.


# O painel de formulário mora em ``formulario.py`` desde 27/08/2026 — mesmo
# motivo do ``administracao.py``. Reimportado AQUI porque ``gui.PainelFormulario``
# e ``gui._AbaPlano`` são o endereço que a suíte já usa.
from isocentro.interface.formulario import (  # noqa: E402,F401
    DialogGerenciarNomes, DialogImagemDias, PainelFormulario, _AbaPlano,
    _frac_inicial, _grupo_form, _VAZIO_SPIN)


# O visualizador mora em ``visualizador.py`` desde 27/08/2026 — mesmo motivo do
# ``administracao.py``. Reimportado AQUI porque ``gui.PainelVisualizador`` é o
# endereço que a suíte já usa.
from isocentro.interface.visualizador import PainelVisualizador, _PainelCorte  # noqa: E402,F401


# ── Qual paciente, quando a pasta tem mais de um ─────────────────────────────


class DialogEscolherPaciente(ui.Dialogo):
    """A pasta tem DICOM de mais de uma pessoa: de quem é a ficha?

    Existe por um defeito medido em 31/08/2026. A varredura é recursiva, e uma
    pasta-pai com vários pacientes virava **uma ficha só**: nome e registro do
    primeiro, planos de todos, sem aviso nenhum na tela. Na pasta de teste do
    Elekta saía uma ficha em nome de uma paciente com planos de outras duas.

    O ``_excluir_arquivos_pasta`` já filtrava por ``PatientID`` para não apagar
    o DICOM de quem nunca foi aberto — o programa sabia do risco na hora de
    APAGAR e não sabia na hora de CARREGAR.

    Escolher aqui não é conveniência: é o que faz a ficha ter um dono. A lista
    traz o registro junto do nome porque **homônimo existe**, e é o registro
    que casa com o sistema.
    """

    def __init__(self, achados: dict, pai=None):
        # 520x520 e não menos: com a fonte em 15 px cada item pede 53 px, e
        # sete pacientes — o caso real medido na pasta do Elekta — só cabem
        # sem rolar a partir desta altura. Rolar para ver o sétimo é atrito
        # num diálogo que já interrompe o trabalho.
        super().__init__("De quem é esta pasta?", pai, 520, 520)
        self.setWindowFlags(self.windowFlags() | Qt.WindowContextHelpButtonHint)
        self._escolhido = ""

        # QLabel com quebra de linha, e não ``ui.rotulo``: aquele é o rótulo
        # miúdo que fica ACIMA de um campo e NÃO quebra — com esta frase inteira
        # numa linha só, o diálogo esticava para 2000 px de largura (visto no
        # render offscreen, antes de qualquer pessoa ver).
        aviso = QLabel(
            f"Esta pasta tem DICOM de {len(achados)} pacientes diferentes. "
            "Escolha de quem é a ficha — só os arquivos dele serão carregados.")
        aviso.setWordWrap(True)
        estilo.pintar(aviso, lambda: f"color:{estilo.TEXTO}; font-size:13px;")
        self.corpo.addWidget(aviso)

        self.lista = QListWidget()
        # Ordem por NOME, não por registro: quem procura na lista procura o
        # nome que leu na requisição.
        for registro, (nome, quantos) in sorted(
                achados.items(), key=lambda kv: (kv[1][0] or "", kv[0])):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, registro)
            self.lista.addItem(item)
            self.lista.setItemWidget(
                item, self._linha(nome or "(sem nome)", registro, quantos))
            # Sem isto o item nasce com a altura de UMA linha de texto e o
            # widget de duas linhas sai cortado pela metade — o Qt não mede o
            # que entra por ``setItemWidget``.
            #
            # A folga de 6 px não é estética: MEDIDO, o item pedia 39 px e o
            # widget recebia 33, porque o espaçamento da lista e a borda do
            # ``::item`` saem de dentro do que foi pedido. A diferença comia
            # justamente a segunda linha, que é onde está o registro.
            pedido = self.lista.itemWidget(item).sizeHint()
            pedido.setHeight(pedido.height() + 6)
            item.setSizeHint(pedido)
        self.lista.setCurrentRow(0)
        self.lista.itemDoubleClicked.connect(lambda _i: self._confirmar())
        self.lista.setSpacing(2)
        estilo.pintar(self.lista, lambda: (
            f"QListWidget{{background:{estilo.FUNDO_BLOCO};"
            f" border:1px solid {estilo.BORDA}; border-radius:6px;"
            f" padding:4px;}}"
            f"QListWidget::item{{border-radius:5px;}}"
            # O hover TEM de ser mais fraco que a seleção. Com os dois iguais,
            # o item sob o cursor ficava idêntico ao que vai ser aberto — e
            # aqui o que está selecionado decide DE QUEM É A FICHA. Passar o
            # mouse pela lista não pode parecer escolher.
            f"QListWidget::item:hover{{background:{estilo.FUNDO_TELA};}}"
            f"QListWidget::item:selected{{background:{estilo.ACAO_FUNDO};}}"
            f"QListWidget::item:selected:hover{{background:{estilo.ACAO_FUNDO};}}"))
        self.corpo.addWidget(self.lista, 1)

        botoes = self.rodape(confirmar="Abrir este paciente")
        self._btn_ok = botoes.get("Abrir este paciente")

    @staticmethod
    def _linha(nome: str, registro: str, quantos: int):
        """Um item da lista: o nome em cima, o resto abaixo e mais fraco.

        Dois QLabel num widget, e não uma string com ``\\n``: com o texto
        corrido os dois pedaços saíam do mesmo tamanho e mesma cor, e o
        registro competia com o nome pela leitura. Quem procura na lista
        procura o NOME; o registro está ali para confirmar, porque homônimo
        existe.
        """
        # ``transparente``: o widget de um item entra POR CIMA da pintura da
        # lista, e um fundo próprio tapa a cor de seleção — o item escolhido
        # ficava com uma borda fina em vez do bloco cheio, e a lista deixava de
        # dizer qual paciente está prestes a ser aberto. Visto no render
        # offscreen, antes de qualquer pessoa ver.
        caixa = ui.transparente(QWidget())
        lay = QVBoxLayout(caixa)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(1)

        lb_nome = QLabel(nome)
        estilo.pintar(lb_nome, lambda: (
            f"color:{estilo.TEXTO}; font-size:15px; font-weight:600;"))

        lb_dado = QLabel(f"{registro} · {quantos} arquivos")
        estilo.pintar(lb_dado, lambda: (
            f"color:{estilo.TEXTO_APAGADO}; font-size:12.5px;"))

        lay.addWidget(lb_nome)
        lay.addWidget(lb_dado)
        return caixa

    def _confirmar(self) -> None:
        self.accept()

    def escolhido(self) -> str:
        """O registro escolhido, ou "" se a pessoa desistiu."""
        item = self.lista.currentItem()
        return str(item.data(Qt.UserRole)) if item is not None else ""


# A busca de pacientes e as ações sobre uma ficha pronta moram em
# ``busca_ficha.py`` desde 31/08/2026 — mesmo motivo do ``administracao.py``.
# Reimportadas AQUI porque ``gui.AcoesDeFicha`` e ``gui.DialogBuscaPacientes``
# são o endereço que a suíte já usa. ``_limpar_temp_zip`` vem junto: foi com
# elas, e a ``JanelaPrincipal`` continua chamando.
from isocentro.interface.busca_ficha import (  # noqa: E402,F401
    AcoesDeFicha, DialogBuscaPacientes, _limpar_temp_zip)


# De quanto em quanto tempo a estação pergunta se a sessão ainda é dela. Meio
# minuto: é uma leitura de um JSON pequeno numa pasta de rede, e é o atraso
# máximo entre alguém entrar na outra máquina e esta travar. Mais curto pesa na
# rede sem ninguém notar a diferença; mais longo deixa as duas abertas tempo
# demais, que é justamente o que a regra veio impedir.
_SESSAO_INTERVALO_MS = 30_000


def _hora_do_acesso(iso) -> str:
    """O trecho " às 14:32" a partir do ISO da sessão; vazio se não der.

    A hora é o que transforma o aviso em resposta: "entrou em CT-02" pode ser a
    própria pessoa, de manhã; "entrou em CT-02 às 14:32", enquanto ela está
    aqui às 14:33, é outra conversa.
    """
    try:
        return datetime.datetime.fromisoformat(str(iso)).strftime(" às %H:%M")
    except (TypeError, ValueError):
        return ""


# ── Janela principal ─────────────────────────────────────────────────────────


class JanelaPrincipal(AcoesDeFicha, QMainWindow):
    def __init__(self, usuario: dict | None = None):
        super().__init__()
        self._usuario = usuario or {}
        # Preferências da estação (registro do Windows): lembra a última pasta
        # aberta, para o seletor já abrir onde o usuário costuma trabalhar.
        self._settings = ajustes()
        self.setAcceptDrops(True)   # arrastar uma pasta de DICOM para a janela
        _nome_u = self._usuario.get("nome") or self._usuario.get("usuario") or ""
        self.setWindowTitle("ISOCENTRO"
                            + (f"  —  {_nome_u}" if _nome_u else ""))
        # Janela MAXIMIZADA: o formulário tem altura fixa, então toda a altura
        # extra vira altura dos cortes (imagem maior, menos achatada), e a faixa
        # de identidade da Capa só usa a largura que tiver.
        #
        # O tamanho abaixo continua valendo — é o que a janela assume quando
        # alguém a restaura do maximizado, e sem ele ela voltaria ao tamanho
        # mínimo do conteúdo. Limitado à tela para não estourar em notebooks.
        _tela = QApplication.primaryScreen()
        if _tela is not None:
            _scr = _tela.availableGeometry()
            _w = min(1340, int(_scr.width() * 0.92))
            _h = min(1000, int(_scr.height() * 0.94))
            self.resize(_w, _h)
            self.move(_scr.left() + (_scr.width() - _w) // 2,
                      _scr.top() + (_scr.height() - _h) // 2)
        else:  # sem tela primária (headless/RDP inicial): tamanho fixo seguro
            self.resize(1180, 740)
        self.setWindowState(self.windowState() | Qt.WindowMaximized)

        # O paciente carregado — ver ``caso.py``. Tudo o que a troca de
        # paciente tem de esquecer mora nele, e a limpeza o troca inteiro.
        self.caso = Caso()
        self._worker_tudo: Optional[_CarregarTudo] = None
        # O que decide se a ficha pode sair (conferência, gating, SUS, 600CD).
        # Construído antes de o formulário existir e de os sinais dele serem
        # ligados: o ``_atualizar_btn_pdf``, que é um desses sinais, o consulta.
        self.portao = portao_ficha.PortaoDaFicha(self)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.form = PainelFormulario()
        self.viewer = PainelVisualizador()
        self.controle_viewer = controle_viewer.ControleViewer(self)
        self.controle_ficha = controle_ficha.ControleFicha(self)

        # Barra de ações — botões empilhados na coluna livre à direita dos cortes.
        self.btn_pasta = QPushButton("📁  Abrir pasta")
        self.btn_edicao = QPushButton("📝  Edição")
        self.btn_tratados = QPushButton("📋  Histórico")
        self.btn_limpar = QPushButton("🗑  Limpar")
        self.btn_pdf = QPushButton("🖨  Impressão")

        # Escala de verde do escuro (topo) ao claro (base), na ordem da trilha.
        # Duas famílias com um vão entre elas (ver a ordem em ``_acoes``):
        # DE ONDE VEM o caso — abrir a pasta, consultar o histórico, descartar —
        # em peso baixo, e O QUE SE FAZ com ele embaixo. Limpar é o único
        # destrutivo e sai em contorno vermelho: preenchido, ele atrai
        # justamente o clique de que avisa. Um sólido só, a Impressão.
        estilo.pintar(self.btn_pasta, self._folha_btn_pasta)
        estilo.pintar(self.btn_tratados, estilo.btn_fantasma)
        estilo.pintar(self.btn_limpar, estilo.btn_perigo)
        estilo.pintar(self.btn_edicao, estilo.btn_contorno)
        estilo.pintar(self.form.btn_agendamento, estilo.btn_contorno)
        estilo.pintar(self.btn_pdf, self._folha_btn_pdf)

        self.btn_edicao.setEnabled(False)
        self.btn_limpar.setEnabled(False)
        # Ficha Técnica só com paciente carregado: segue o campo Nome, que o
        # plano preenche ao carregar e a limpeza esvazia (também vale se o
        # usuário digitar manualmente).
        self.btn_pdf.setEnabled(False)

        for b in (self.btn_pasta, self.btn_edicao, self.btn_tratados,
                  self.btn_limpar, self.form.btn_agendamento, self.btn_pdf):
            b.setMinimumHeight(46)
            b.setMaximumWidth(360)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)

        # Botões espalhados VERTICALMENTE (folga igual entre eles), preenchendo
        # a coluna; Agendamento abaixo de Limpar (só multi-plano); Ficha Técnica
        # embaixo, com brilho azul de ação primária.
        _acoes = (self.btn_pasta, self.btn_edicao, self.btn_tratados,
                  self.btn_limpar, self.form.btn_agendamento, self.btn_pdf)
        self.viewer.lay_acoes.addStretch(1)
        for b in _acoes:
            self.viewer.lay_acoes.addWidget(b)
            self.viewer.lay_acoes.addStretch(1)

        # ── Dois modos na mesma janela ───────────────────────────────────
        # Total (a bancada de sempre) e Fichinha (o painel das listas).
        # A faixa do seletor fica ACIMA das duas, para a volta estar sempre à
        # mão; as telas trocam num QStackedWidget, sem recriar nada — o estado
        # do paciente carregado é o mesmo dos dois lados.
        self.pag_total = QWidget()
        lay_total = QVBoxLayout(self.pag_total)
        lay_total.setContentsMargins(0, 0, 0, 0)
        lay_total.setSpacing(0)
        lay_total.addWidget(self.form)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        estilo.pintar(sep, lambda: f"background:{estilo.BORDA};"
                      " max-height:1px; margin:0 0;")
        lay_total.addWidget(sep)
        lay_total.addWidget(self.viewer, 1)

        self.fichinha = fichinha.PainelFichinha()
        self.capa = capa_tela.PainelCapa()
        self.controle_capa = controle_capa.ControleCapa(self)
        self.ficha_virtual = tratamento.PainelFichaVirtual()
        self.controle_virtual = controle_virtual.ControleFichaVirtual(
            self.ficha_virtual, self._usuario)
        self.ficha_virtual.paciente_escolhido.connect(
            self.controle_virtual.buscar)
        # Um paciente por vez, e só com gesto EXPLÍCITO: duplo clique ou Enter.
        # Pendurado no ``paciente_escolhido``, que dispara ao navegar, isto
        # carregaria DICOM de quem o cursor pousou — ver a revisão de
        # 04/09/2026.
        self.ficha_virtual.paciente_confirmado.connect(
            self._sincronizar_bancada)
        self.ficha_virtual.curso_escolhido.connect(
            self.controle_virtual.trocar_curso)
        self.ficha_virtual.medicos_mudaram.connect(
            self.controle_virtual.painel)
        self.ficha_virtual.abrir_pdf.connect(self.controle_virtual.abrir_pdf)
        self.ficha_virtual.abrir_checklist.connect(
            self.controle_virtual.abrir_checklist)
        self.ficha_virtual.checklist_marcado.connect(
            self.controle_virtual.checklist_marcar)
        self.ficha_virtual.abrir_campos.connect(
            self.controle_virtual.abrir_campos)
        self._stack = QStackedWidget()
        self._stack.addWidget(self.pag_total)   # MODO_TOTAL
        self._stack.addWidget(self.fichinha)    # MODO_FICHINHA
        self._stack.addWidget(self.capa)        # MODO_CAPA
        # A ordem do empilhamento É o índice do modo (ver fichinha.MODO_*).
        # Tela nova entra no FIM, nunca no meio.
        self._stack.addWidget(self.ficha_virtual)   # MODO_FICHA_VIRTUAL
        self.qualidade = qualidade_tela.PainelQualidade()
        self._stack.addWidget(self.qualidade)       # MODO_QUALIDADE
        self.agenda = agenda_tela.PainelAgenda()
        self.controle_agenda = controle_agenda.ControleAgenda(
            self.agenda, self._usuario)
        self._stack.addWidget(self.agenda)          # MODO_AGENDA
        self.radioteradados = radioteradados_tela.PainelRadioteradados()
        self.controle_radioteradados = controle_radioteradados.ControleRadioteradados(
            self.radioteradados, self._usuario)
        self._stack.addWidget(self.radioteradados)  # MODO_RADIOTERADADOS

        # A faixa é recortada pela FUNÇÃO de quem entrou (ver
        # ``fichinha.modos_do_papel``): o médico vê a Virtual e a Agenda, o
        # dosimetrista vê Capa-Up, Virtual e Agenda, o físico e o admin veem
        # tudo. O ``_stack`` continua com as SEIS telas e com os mesmos
        # índices — tirar uma dali renumeraria os modos, e ``MODO_CAPA``
        # passaria a apontar para a Virtual.
        self._papel = str((self._usuario or {}).get("papel") or "")
        self._modos = fichinha.modos_do_papel(self._papel)
        self._barra_modo, self._btns_modo = fichinha.barra_de_modo(
            self._trocar_modo, self._alternar_modo_cor, self._papel)
        # ``.get``: para quem não vê a aba, o botão não existe.
        self._btn_modo_total = self._btns_modo.get(fichinha.MODO_TOTAL)
        self._btn_modo_fichinha = self._btns_modo.get(fichinha.MODO_FICHINHA)
        # ── O shell Torre (R-23) ─────────────────────────────────────────
        # Duas páginas: o Início (3 zonas) e o módulo aberto. O Radioteraficha
        # é um módulo: a faixa de abas de sempre vai para o topo do módulo,
        # depois do "◂ Início", e as telas continuam as mesmas, nos mesmos
        # índices do ``_stack``.
        self._chave_clinica = ("torre/clinica/"
                               + str((self._usuario or {}).get("usuario") or ""))
        self.inicio = torre.Inicio(
            self._usuario,
            clinica_inicial=str(self._settings.value(self._chave_clinica, "") or ""),
            ao_alternar_cor=self._alternar_modo_cor)
        self.inicio.abrir_modulo.connect(self._abrir_modulo)
        self.inicio.clinica_mudou.connect(self._clinica_mudou)
        # Os alertas do núcleo moram no PostgreSQL, e a conexão do app é da
        # R-19: até lá a Zona 2 diz que a fonte não está configurada.
        self.inicio.mostrar_alertas(None)
        self.topo_modulo = torre.TopoDoModulo()
        self.topo_modulo.voltar.connect(self._mostrar_inicio)
        # A faixa mora no topo do módulo desde já, e só se ESCONDE fora do
        # Radioteraficha: tirada dali, ela ficaria sem pai, e os testes e
        # atalhos que a consultam veriam uma janela solta.
        self.topo_modulo.definir_faixa(self._barra_modo)
        # Só depois da abertura (``_shell_pronto``) uma troca de tela leva
        # ao módulo: o programa abre no Início (EXPERIENCE.md, UJ-0).
        self._shell_pronto = False
        self.tela_em_construcao = torre.TelaEmConstrucao()
        self._conteudo_modulo = QStackedWidget()
        self._conteudo_modulo.addWidget(self._stack)
        self._conteudo_modulo.addWidget(self.tela_em_construcao)
        self.documentacao = documentacao_tela.PainelDocumentacao(
            usuario=self._usuario)
        self._conteudo_modulo.addWidget(self.documentacao)
        self.pag_modulo = QWidget()
        _lay_mod = QVBoxLayout(self.pag_modulo)
        _lay_mod.setContentsMargins(0, 0, 0, 0)
        _lay_mod.setSpacing(0)
        _lay_mod.addWidget(self.topo_modulo)
        _lay_mod.addWidget(self._conteudo_modulo, 1)
        self._raiz = QStackedWidget()
        self._raiz.addWidget(self.inicio)
        self._raiz.addWidget(self.pag_modulo)
        root.addWidget(self._raiz, 1)
        self._modulo_aberto = ""
        _inicio = QShortcut(QKeySequence("Alt+Home"), self)
        _inicio.setContext(Qt.WindowShortcut)
        _inicio.activated.connect(self._mostrar_inicio)

        # Ctrl+Tab circula os modos da faixa (Total → Fichinha → Capa-Up →
        # volta), e Ctrl+Shift+Tab volta — o gesto que navegador e editor
        # ensinaram. Shift+Tab sozinho NÃO serve: é o "voltar um campo" do Qt, e
        # a bancada é um formulário denso onde ele faz falta.
        for _seq, _passo in (("Ctrl+Tab", 1), ("Ctrl+Shift+Tab", -1)):
            _atalho = QShortcut(QKeySequence(_seq), self)
            # Do JANELA, não do widget com foco: senão as abas de plano (um
            # QTabWidget, que trata Ctrl+Tab por conta própria) comeriam o atalho.
            _atalho.setContext(Qt.WindowShortcut)
            _atalho.activated.connect(
                lambda p=_passo: self._modo_vizinho(p))
        self._montar_atalhos()

        # Pedido de ficha semiautomática em curso (modo Fichinha): guarda a pasta
        # entre o disparo e o fim do worker, que é quem sabe se deu certo.
        self._auto_pendente: Optional[str] = None
        # Para onde ir quando a carga vinda da Documentação terminar:
        # "visualizar", "editar" ou vazio. Ver
        # ``_cumprir_destino_da_documentacao``.
        self._destino_documentacao: str = ""
        # A última prévia chegou a ser montada? (ver _fichinha_visualizar)
        self._previa_ok: bool = False
        # PDF de prévia já elaborado e guardado em disco, pronto para abrir.
        self._previa_caminho: Optional[str] = None

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        # "Geova · físico · Todas" (DESIGN.md, Barra de status). No módulo,
        # a clínica é a do contexto. PERMANENTE, e por isso à direita: à
        # esquerda ele dividia o lugar com as mensagens temporárias, que são
        # muitas, e as duas linhas saíam uma por cima da outra.
        self.lbl_identidade = QLabel()
        estilo.pintar(self.lbl_identidade,
                      lambda: f"color:{estilo.TEXTO_SECUNDARIO}; font-size:12px;"
                              " padding:0 8px;")
        self.status.addPermanentWidget(self.lbl_identidade)
        self._atualizar_identidade()
        self.status.showMessage("Pronto. Abra a pasta — ou arraste-a para a "
                                "janela — para começar.")
        # Configurações (Usuários/Equipe/Máquinas) — SOMENTE admin.
        if (self._usuario or {}).get("papel") == "admin":
            _btn_cfg = QPushButton("⚙  Configurações")
            _btn_cfg.setStyleSheet("padding:2px 10px;")
            _btn_cfg.setCursor(Qt.PointingHandCursor)
            _btn_cfg.clicked.connect(self._abrir_configuracoes)
            self.status.addPermanentWidget(_btn_cfg)

        # Conexões
        self.btn_pasta.clicked.connect(self._abrir_pasta)
        self.btn_edicao.clicked.connect(self._abrir_edicao)
        self.btn_tratados.clicked.connect(self._abrir_busca)
        self.btn_limpar.clicked.connect(self._limpar_tudo)
        self.btn_pdf.clicked.connect(self._escolher_ficha)
        self.form.pac_nome.textChanged.connect(self._atualizar_btn_pdf)
        # Editar o nº de frações de um plano reavalia a Ficha Técnica (o
        # agendamento pode ter deixado de cobrir todas as frações).
        self.form.fracoes_mudou.connect(self._atualizar_btn_pdf)
        self.form.planos_reordenados.connect(self.controle_viewer.reordenar_planos_estado)
        # Trocar de aba de plano = ativar aquele plano (bridge RP/RS/RD).
        self.form.abas.currentChanged.connect(self.controle_viewer.ativar_plano)
        self.form.btn_agendamento.clicked.connect(self._abrir_agendamento)

        # Modo Fichinha: a tela só pede; quem executa é esta janela, com os
        # mesmos métodos do modo Ficha Total (nenhum caminho paralelo de
        # geração — a ficha semiautomática é a ficha de sempre, sem as paradas).
        self.fichinha.gerar.connect(self._fichinha_gerar)
        self.fichinha.fechar_caso.connect(self._fichinha_fechar_caso)
        self.fichinha.abrir_historico.connect(self._abrir_busca)
        self.fichinha.abrir_edicao.connect(self._fichinha_edicao)
        self.fichinha.pedir_visualizacao.connect(self._fichinha_visualizar)
        self.fichinha.pedir_impressao.connect(self._fichinha_imprimir)
        self.fichinha.acao_recente.connect(self._fichinha_acao_recente)
        self.fichinha.abrir_documentacao.connect(
            self._fichinha_abrir_documentacao)
        self.fichinha.acao_data.connect(self._fichinha_acao_data)
        self.fichinha.acao_alta.connect(self._fichinha_acao_alta)

        # Modo Capa: mesmo desenho da Fichinha — a tela pede, esta janela busca
        # nos relatórios, monta o PDF e o entrega ao leitor ou à impressora.
        # Escolher o paciente na busca é o gesto de "é este": puxa a capa
        # inteira dos relatórios, foto 3×4 inclusive.
        self.capa.paciente_escolhido.connect(self.controle_capa.esquecer_modo_completa)
        self.capa.paciente_escolhido.connect(self.controle_capa.paciente_escolhido)
        self.capa.paciente_fechado.connect(self._fechar_na_ficha_virtual)
        self.capa.pedir_visualizacao.connect(self.controle_capa.visualizar)
        self.capa.pedir_salvar.connect(self.controle_capa.salvar)
        self.capa.pedir_impressao.connect(self.controle_capa.imprimir)

        # Quem é o paciente DA VEZ. As duas telas que estabelecem um paciente
        # avisam por aqui, e o último a falar é o que a Ficha Virtual segue.
        # ``textChanged`` do campo, e não um gancho em cada caminho que carrega
        # caso: há meia dúzia deles (pasta solta, histórico, Fichinha, reabrir
        # versão), e o que esqueceu de avisar é o que quebra em silêncio — o
        # campo é o único lugar por onde todos passam.
        self.form.pac_registro.textChanged.connect(
            lambda t: self.controle_virtual.focar_paciente(t))
        self.capa.f_registro.textChanged.connect(
            lambda t: self.controle_virtual.focar_paciente(t))
        # Modo Simulação: o cadastro da TC, primeiro elo da corrente.
        self.capa.cadastrar_simulacao.connect(self.controle_capa.cadastrar_simulacao)
        self.capa.definir_usuario((self._usuario or {}).get("usuario", ""))
        self.capa.correcao_salva.connect(self.controle_capa.correcao_salva)
        self.capa.pasta_escolhida.connect(self.controle_capa.da_pasta)
        self.capa.paciente_confirmado.connect(self._sincronizar_bancada)
        self.capa.mudou.connect(self._capa_mudou)
        self.capa.permitir_escolher_pastas(
            (self._usuario or {}).get("papel") == "admin")
        # O paciente cuja sincronia automática foi RECUSADA. Estado
        # explícito e não ``getattr`` com padrão: quem lê o ``__init__``
        # tem de encontrar tudo o que a janela guarda, senão o campo só
        # existe depois do primeiro uso e some da leitura de quem procura.
        self._sync_recusado = ""


        # O programa abre na PRIMEIRA aba que a função enxerga (ver
        # ``fichinha.modo_inicial``): a Fichinha para o físico, a Virtual para
        # o médico, que só tem essa.
        #
        # Antes ele voltava ao último modo usado, na ideia de que a estação tem
        # um dono. Com a Fichinha promovida a porta de entrada isso passou a
        # atrapalhar: quem precisou da bancada num caso difícil ontem abria nela
        # hoje, e a tela de dois cliques — que serve para a maioria dos casos —
        # dependia de alguém lembrar de voltar para ela.
        self._ir_para_modo(fichinha.modo_inicial(self._papel))
        self._shell_pronto = True
        # A troca acima deixou "Modo Fichinha — ..." na barra, e quem está
        # na frente é o Início.
        self.status.clearMessage()

        # Atalho F5 (relançar o app) REMOVIDO a pedido — não funcionava de forma
        # confiável. Para reabrir o programa, feche e abra de novo.

        v = self.viewer
        # A faixa de isodose em cGy precisa da prescrição e do ponto quente, que
        # só a janela conhece (ver ``controle_viewer.dose_iso_cgy``).
        v.dose_iso_provider = self.controle_viewer.dose_iso_cgy
        v.aviso_isodose.connect(lambda msg: self.status.showMessage(msg, 6000))
        # Controles globais → todos os cortes. A troca de unidade entra DEPOIS da
        # conversão do próprio painel (conectada primeiro, no __init__ dele).
        for sig in (v.cmb_janela.currentTextChanged,
                    v.chk_estruturas.stateChanged,
                    v.chk_isodose.stateChanged,
                    v.spn_iso_min.valueChanged,
                    v.spn_iso_max.valueChanged,
                    v.cmb_iso_unid.currentTextChanged,
                    v.lst_estruturas.itemChanged):
            sig.connect(self.controle_viewer.atualizar_todos_cortes)
        # Sliders individuais → apenas o painel correspondente
        v.painel_axial.slider.valueChanged.connect(
            lambda val: self.controle_viewer.renderizar_painel(v.painel_axial, "Axial", val))
        v.painel_sagital.slider.valueChanged.connect(
            lambda val: self.controle_viewer.renderizar_painel(v.painel_sagital, "Sagital", val))
        v.painel_coronal.slider.valueChanged.connect(
            lambda val: self.controle_viewer.renderizar_painel(v.painel_coronal, "Coronal", val))
        v.painel_3d.angulos_alterados.connect(self.controle_viewer.rerender_3d_angulo)
        # Botões de seleção de estruturas
        v._btn_all.clicked.connect(lambda: self.controle_viewer.marcar_estruturas(Qt.Checked))
        v._btn_none.clicked.connect(lambda: self.controle_viewer.marcar_estruturas(Qt.Unchecked))

        # Sem caso carregado, a janela nasce inerte (ver _atualizar_edicao_habilitada).
        self._atualizar_edicao_habilitada()

        # Barra de título nativa combinando com o app — e acompanhando a troca
        # de dia↔noite, senão ela é a única superfície que fica no modo antigo.
        _titlebar_escura(self)
        estilo.ao_trocar(lambda: _titlebar_escura(self))

        # A varredura da exportação não roda mais aqui: gatilho de tempo é
        # só da concentradora (AD-28, R-21), pela Tarefa Agendada.

        # A conferência da sessão (ver ``dados/sessao.py``). Só existe quando
        # há sessão para conferir: admin e modo dev não têm, e um relógio
        # batendo à toa custaria uma leitura de rede por minuto em cada
        # estação.
        self._sessao_travada = False
        # A sessão foi tomada por outra estação? Então o fechamento não
        # pergunta mais nada — ver ``_conferir_sessao`` e ``closeEvent``.
        self._sessao_perdida = False
        self._relogio_sessao = None
        if sessao.vigilancia_ativa():
            self._relogio_sessao = QTimer(self)
            self._relogio_sessao.setInterval(_SESSAO_INTERVALO_MS)
            self._relogio_sessao.timeout.connect(self._conferir_sessao)
            self._relogio_sessao.start()

    def _conferir_sessao(self) -> None:
        """A conta entrou em outra estação? Então este programa FECHA.

        Decidido com o usuário em 23/09/2026, depois de uma primeira versão que
        travava a janela e esperava um novo login: fechar mesmo que se perca o
        caso carregado na bancada. A razão é que trancar a tela deixa o programa
        DE PÉ na estação de onde a pessoa saiu — e uma janela travada a que
        ninguém volta não encerra acesso nenhum, só parece.

        O aviso é um modal de UM botão, e a pessoa que clica nele já não está
        mais nesta estação: quem precisa lê-lo é quem passar por aqui depois e
        encontrar o programa fechado sem saber por quê.

        É a ÚNICA porta de saída do app que não pergunta pelo caso na tela (ver
        ``closeEvent``). Perguntar devolveria o buraco que este caminho veio
        fechar: "Continuar trabalhando" manteria aberta uma sessão que já é de
        outra máquina.
        """
        if self._sessao_travada or sessao.minha_vez():
            return
        self._sessao_travada = True
        if self._relogio_sessao is not None:
            # Parado ANTES do modal: o ``exec_`` roda o laço de eventos, e o
            # relógio continuaria batendo por baixo da caixa aberta.
            self._relogio_sessao.stop()
        outra = sessao.dono(self._usuario) or {}
        onde = outra.get("maquina") or "outra estação"
        historico.registrar("sessao_encerrada", {"maquina": onde})
        # A flag ANTES do modal: o X da caixa, ou um fechamento vindo de fora
        # enquanto ela está aberta, tem de pegar o ``closeEvent`` já sabendo
        # que esta sessão acabou — senão volta a pergunta do caso perdido.
        self._sessao_perdida = True
        ui.alertar(
            self, "Sessão encerrada",
            f"Sua conta entrou em {onde}"
            f"{_hora_do_acesso(outra.get('desde'))}, e cada pessoa fica em uma "
            "estação por vez.\n\nEste programa vai fechar.",
            detalhe="O caso que estava na tela não foi salvo.")
        self.close()

    def closeEvent(self, event):
        # Sessão tomada por outra estação: fecha direto. A pergunta abaixo tem
        # uma saída "Continuar trabalhando", e ela manteria de pé justamente a
        # sessão que acabou de ser encerrada.
        if not self._sessao_perdida and (self.caso.dados
                                         or self.caso.ct is not None):
            if not ui.confirmar(
                    self, "Sair do programa",
                    "Deseja realmente fechar o programa?",
                    acao="Fechar e perder o caso",
                    recusa="Continuar trabalhando",
                    detalhe="Há dados carregados que serão perdidos.",
                    perigo=True):
                event.ignore()
                return
        # Encerra o worker de carregamento antes de destruir a janela; sem isso
        # a QThread (filha de self) seria destruída em execução → qFatal.
        if self._worker_tudo is not None and self._worker_tudo.isRunning():
            self._worker_tudo._parar = True
            self._worker_tudo.wait(3000)
        _limpar_temp_zip(self.caso.tmp_extraido)
        self.caso.tmp_extraido = None
        historico.registrar("app_fechado")
        # Solta a sessão para este usuário poder abrir em outra estação sem
        # derrubar ninguém — e sem esperar o próximo login dele.
        sessao.fechar()
        event.accept()

    # ── Abertura de arquivos ─────────────────────────────────────────────────

    def dragEnterEvent(self, e):
        """Aceita arrastar UMA pasta (ou um arquivo, cuja pasta será usada) para
        a janela — atalho para carregar sem passar pelo seletor de pastas."""
        md = e.mimeData()
        if md.hasUrls() and any(u.isLocalFile() for u in md.urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = [u for u in e.mimeData().urls() if u.isLocalFile()]
        if not urls:
            return
        e.acceptProposedAction()
        alvo = urls[0].toLocalFile()
        # Soltar um arquivo (ou vários) usa a PASTA que os contém — é lá que estão
        # os DICOM do paciente.
        pasta = alvo if os.path.isdir(alvo) else os.path.dirname(alvo)
        # No modo Fichinha a pasta solta preenche o campo e já dispara a ficha:
        # soltar ali é o mesmo gesto de colar o caminho e clicar.
        if self._stack.currentIndex() == 1:
            self.fichinha.definir_caminho(pasta)
            self._fichinha_gerar(pasta)
            return
        self._carregar_pasta(pasta)

    # ── Modo Fichinha ────────────────────────────────────────────────────
    # A tela simplificada não tem lógica de ficha nenhuma: ela pede, e estes
    # métodos traduzem o pedido para o mesmo caminho do modo Ficha Total.

    # ── Atalhos ──────────────────────────────────────────────────────────
    # Antes havia DOIS (Ctrl+Tab e Ctrl+Shift+Tab) e nenhuma barra de menus,
    # num programa usado com o paciente na mesa. Duas regras, vindas do que já
    # estava escrito no projeto:
    #
    # * **o atalho segue o botão sólido** ("o sólido anda com o trabalho"):
    #   Ctrl+Enter faz o que o sólido faz AGORA. Um atalho só, que nunca
    #   precisa ser reaprendido porque acompanha a tela;
    # * **atalho nenhum em ação destrutiva.** Limpar e Fechar o caso ficam
    #   fora: atalho não pergunta, e a mão erra a tecla.
    #
    # Todos são anunciados no tooltip do botão (ver ``ui.atalho``) — atalho que
    # não aparece em lugar nenhum não é descoberto.

    def _montar_atalhos(self) -> None:
        for seq, acao, botao in (
                ("Ctrl+O", self._abrir_pasta, self.btn_pasta),
                ("Ctrl+P", self._acao_principal, self.btn_pdf),
                ("Ctrl+Return", self._acao_principal, None),
                ("Ctrl+E", self._abrir_edicao, self.btn_edicao),
                ("Ctrl+H", self._abrir_busca, self.btn_tratados),
                ("Ctrl+G", self._abrir_agendamento,
                 self.form.btn_agendamento)):
            # Escopo do módulo, não globais (EXPERIENCE.md): no Início o
            # Ctrl+O abriria um seletor de pasta de uma tela que não está lá.
            ui.atalho(seq, self,
                      lambda a=acao: None if self._no_inicio() else a(),
                      botao)

    def _acao_principal(self) -> None:
        """O que o botão SÓLIDO da tela faria agora.

        Um atalho só para o passo principal, seja ele qual for: com a bancada
        vazia é abrir a pasta, com o caso carregado é a impressão. Amarrar
        Ctrl+P a "gerar PDF" e Ctrl+O a "abrir" daria dois atalhos para uma
        sequência que é uma só — e o que muda entre eles é justamente o que o
        programa já sabe decidir sozinho.

        Botão apagado não dispara: botão aceso significa pronto, e o atalho não
        pode ser a porta dos fundos de um passo que a tela está negando.
        """
        if self.btn_pdf.isEnabled():
            self._escolher_ficha()
        elif self.btn_pasta.isEnabled():
            self._abrir_pasta()

    def _modo_vizinho(self, passo: int) -> None:
        """Vai para o modo seguinte (``+1``) ou anterior (``-1``) da faixa.

        Dá a volta nas pontas: da última, o próximo é a primeira. É o que o
        Ctrl+Tab chama.

        O ciclo é o da FUNÇÃO, não o da faixa inteira: circulando por todos, o
        atalho abria telas que a pessoa não tem botão para reabrir depois de
        sair — e a faixa ficava sem nenhum botão aceso.
        """
        if self._modulo_aberto != "radioteraficha":
            return
        ciclo = self._modos or fichinha.MODOS
        atual = self._stack.currentIndex()
        i = ciclo.index(atual) if atual in ciclo else 0
        self._ir_para_modo(ciclo[(i + passo) % len(ciclo)])

    def _ir_para_modo(self, indice: int) -> None:
        """Troca de modo POR CÓDIGO, deixando o botão da faixa em dia.

        Clicar no botão já chama ``_trocar_modo`` sozinho; quando quem troca é um
        atalho, o botão precisa ser marcado à parte — senão a faixa passa a
        mentir sobre qual tela está na frente.

        Modo que a FUNÇÃO não vê não abre: é por aqui que passam o atalho, a
        abertura do programa e as trocas por código (o "Confeccionar a capa" do
        cadastro de simulação, por exemplo), e uma delas caindo numa tela sem
        botão deixaria a pessoa numa aba de onde ela não sabe sair.
        """
        if self._modos and indice not in self._modos:
            return
        botao = self._btns_modo.get(indice)
        if botao is not None:
            botao.setChecked(True)
        self._trocar_modo(indice)

    def _trocar_modo(self, indice: int) -> None:
        """Troca a tela da faixa superior, preservando o paciente carregado.

        Nenhuma tela tem estado próprio de paciente: as seis olham para o
        mesmo caso e se atualizam ao aparecer, porque o que aconteceu na
        bancada enquanto elas estavam escondidas conta.
        """
        # Quem troca de tela por código com o Início na frente (soltar uma
        # pasta na janela, o histórico) leva a pessoa ao módulo: senão a tela
        # mudava por trás do Início, e o caso carregava sem ninguém ver.
        if (self._shell_pronto and indice != fichinha.MODO_RADIOTERADADOS
                and self._modulo_aberto != "radioteraficha"):
            self._abrir_modulo("radioteraficha")
        self._stack.setCurrentIndex(indice)
        # A Ficha Total não tem botão na faixa (ver ``fichinha.MODOS_OCULTOS``):
        # ela é o destino da Edição da Fichinha, não uma aba que se escolhe. O
        # botão aparece enquanto ela está na frente e some ao sair — sem isso, a
        # faixa ficaria com a Fichinha acesa e a bancada no miolo, que é
        # exatamente a mentira que ``_ir_para_modo`` existe para evitar.
        if (self._btn_modo_total is not None
                and fichinha.MODO_TOTAL in fichinha.MODOS_OCULTOS):
            na_bancada = indice == fichinha.MODO_TOTAL
            self._btn_modo_total.setVisible(na_bancada)
            # Aceso junto com o aparecer: um botão visível e apagado ao lado da
            # tela que ele nomeia é a mesma mentira ao contrário. Vale também
            # para quem chama ``_trocar_modo`` direto, sem passar pelo
            # ``_ir_para_modo`` — o grupo é exclusivo, então isto apaga a
            # Fichinha.
            if na_bancada:
                self._btn_modo_total.setChecked(True)
        # Não se guarda mais qual era o modo: o programa abre sempre na
        # Fichinha (ver o __init__), então o valor não teria leitor.
        if indice == fichinha.MODO_CAPA:
            self.controle_capa.ao_abrir()
            return
        if indice == fichinha.MODO_FICHA_VIRTUAL:
            self.controle_virtual.ao_abrir()
            return
        if indice == fichinha.MODO_QUALIDADE:
            self._qualidade_ao_abrir()
            return
        if indice == fichinha.MODO_AGENDA:
            self.controle_agenda.ao_abrir()
            return
        if indice == fichinha.MODO_RADIOTERADADOS:
            self.controle_radioteradados.ao_abrir()
            return
        if indice == fichinha.MODO_FICHINHA:
            # A lista de recentes é relida a cada abertura: o log é
            # compartilhado, e a ficha que ESTA pessoa gerou na estação ao lado
            # tem de aparecer aqui sem fechar o app.
            self._fichinha_recentes()
            # E o quadro de Documentação, pelo mesmo motivo: ele envelhece
            # sozinho enquanto a aba está escondida, e quem volta para cá volta
            # justamente para ver o que mudou.
            self._fichinha_atividades()
            # Os três blocos que a v8 acrescentou seguem a mesma regra: o
            # histórico e as altas são do SERVIÇO, e mudam por obra de quem
            # está na estação ao lado.
            self._fichinha_historico()
            self._fichinha_datas()
            self._fichinha_altas()
            # A trilha reflete o que existe agora, nos dois sentidos: sobe para
            # PRONTA se a bancada deixou um paciente carregado, e volta para
            # INICIAL se ele foi limpo enquanto a Fichinha estava escondida.
            # Só reacende a trilha se a tela AINDA aponta uma pasta: o campo
            # limpo é o gesto de "não é mais este caso" (ver
            # ``fichinha._caminho_mudou``), e voltar da bancada não o desfaz.
            if self._estado_fichinha_tem_ficha() and self.fichinha.caminho():
                if self.fichinha.estado() == fichinha.INICIAL:
                    self.fichinha.definir_estado(fichinha.PRONTA)
                    self.fichinha.mostrar_status(
                        f"Paciente carregado: {self.form.pac_nome.text().strip()}")
                # Sempre reconfere ao voltar: o que aconteceu na bancada
                # enquanto a Fichinha estava escondida — montar o agendamento,
                # preencher o físico, mudar as frações — muda a lista.
                self._fichinha_conferir()
                # E, se a prévia não tinha fechado, tenta de novo: montar o
                # agendamento na bancada é exatamente o que faltava, e a pessoa
                # volta esperando a Visualização acesa.
                if not self.fichinha.previa_pronta():
                    self._fichinha_previa_e_status(
                        self.form.pac_nome.text().strip())
            else:
                self.fichinha.definir_estado(fichinha.INICIAL)
                self.fichinha.limpar_avisos()
                self.fichinha.mostrar_status("")
        self.status.showMessage(
            "Modo Fichinha — o painel das listas."
            if indice == fichinha.MODO_FICHINHA
            # A bancada não tem mais aba na faixa: quem chega aqui vem da
            # Edição, e a linha de status é onde cabe dizer por onde se volta.
            else "Modo Total — a bancada. Volte pelo botão Fichinha.", 4000)

    def _estado_fichinha_tem_ficha(self) -> bool:
        """Há material suficiente para editar/visualizar uma ficha agora?"""
        return bool(self.form.pac_nome.text().strip())

    def _tem_caso_aberto(self) -> bool:
        """Há QUALQUER rastro de paciente aberto na bancada?

        Deliberadamente largo: para decidir se vale perguntar antes de fechar,
        errar para o lado de perguntar custa um clique; errar para o outro
        deixa metade do caso vivo — a Capa limpa e a bancada ainda com o
        paciente, que é justamente o descasamento que o fechamento existe para
        eliminar.
        """
        return bool(self.caso.dados or self.caso.ct is not None
                    or self.caso.pasta_carregada
                    or self._estado_fichinha_tem_ficha())

    def _fichinha_fechar_caso(self, anterior: str = "") -> None:
        """O × do campo apagou o caminho: fecha o caso em todas as telas.

        A pergunta é **adiada** para depois deste retorno: o pedido nasce dentro
        do ``textChanged`` do campo, e abrir um modal ali roda um laço de
        eventos aninhado enquanto o próprio campo ainda está processando a
        mudança — e a recusa ainda escreve nele de volta. Fora do sinal, é uma
        janela comum sobre um campo parado.
        """
        QTimer.singleShot(0, lambda: self._perguntar_fechar_caso(anterior))

    def _perguntar_fechar_caso(self, anterior: str = "") -> None:
        """Confirma o fechamento e o executa. Ver ``_fichinha_fechar_caso``.

        Pergunta antes, porque descartar o caso carregado não tem desfazer — e
        recusar devolve o caminho E o ponto da trilha, sem perder nada.
        """
        if not self._tem_caso_aberto():
            self.capa.limpar()
            return
        if ui.confirmar(
                self, "Fechar o paciente?", "O caminho foi apagado.",
                acao="Fechar o caso", recusa="Manter aberto",
                # SEM enumerar as telas (pedido do usuário em 27/08/2026). A
                # frase dizia "em todas as telas — bancada e Capa", e a lista
                # não ajudava em nada: quem está fechando o caso não precisa
                # saber ONDE ele estava, precisa saber que sai inteiro. Pior,
                # uma lista de telas dentro de um texto de pop-up envelhece
                # calada — a aba seguinte que entrar no app não vai lembrar de
                # aparecer aqui.
                detalhe="Fechar descarta o caso em todas as telas.",
                perigo=True):
            self._executar_limpeza()
            self.fichinha.mostrar_status("Paciente fechado. Aponte outra pasta "
                                         "para começar.")
            return
        # Manter aberto: o campo volta a apontar o caso que continua carregado,
        # e a trilha volta ao MESMO ponto — rebaixar VISTA para PRONTA apagaria
        # o Imprimir de quem só cancelou um fechamento.
        if self.caso.pasta_carregada:
            self.fichinha.definir_caminho(self.caso.pasta_carregada)
            self.fichinha.definir_estado(anterior or fichinha.PRONTA)
            self.fichinha.definir_previa(bool(
                self._previa_caminho and os.path.exists(self._previa_caminho)))
            self.fichinha.mostrar_status("Paciente mantido aberto.")

    def _fichinha_gerar(self, caminho: str) -> None:
        """Botão ISOCENTRO: carrega a pasta e monta a ficha de uma vez.

        Diferente do Abrir pasta da bancada em um ponto só: não pergunta se
        pode substituir o paciente atual. Quem digitou um caminho novo e clicou
        já disse o que quer, e o modal a mais mataria a proposta de um clique.
        """
        caminho = (caminho or "").strip().strip('"')
        if not os.path.isdir(caminho):
            self.fichinha.mostrar_status(
                "Pasta não encontrada. Confira o caminho.", erro=True)
            return
        if self._worker_tudo is not None and self._worker_tudo.isRunning():
            self.fichinha.mostrar_status(
                "Aguarde: uma pasta ainda está carregando.")
            return
        if self.caso.dados or self.caso.ct is not None:
            self._executar_limpeza()
        self._auto_pendente = caminho
        self.fichinha.limpar_avisos()
        self.fichinha.definir_estado(fichinha.CARREGANDO)
        self.fichinha.mostrar_status(_FICHA_EM_ANDAMENTO)
        self._carregar_pasta(caminho)
        # ``_carregar_pasta`` nem sempre dispara o worker: pasta com ficha
        # anterior é reaberta na hora, e há saídas antecipadas. Sem worker em
        # curso, ninguém emitiria ``finished`` e a trilha ficaria travada em
        # CARREGANDO — então o desfecho é avaliado aqui mesmo.
        if self._worker_tudo is None or not self._worker_tudo.isRunning():
            self._carga_terminou()

    def _fichinha_abrir_documentacao(self, entrada: dict) -> None:
        """Clique no ``● PRONTA``: abre o caso preparado pelo caminho de sempre.

        Pelo ``_fichinha_gerar``, e não por uma carga à parte: a trilha, a
        prévia e as perguntas da carga são as de uma pasta digitada. O que muda
        é a marca ``_origem_temporaria``, posta DEPOIS de a carga começar — a
        limpeza que a carga faz do caso anterior a apagaria —, e é ela que faz
        da Impressão uma liberação.
        """
        automacao = (entrada or {}).get("automacao") or {}
        pasta = str(automacao.get("pasta") or "")
        # O destino pedido pelo botão (ver ``_cumprir_destino_da_documentacao``).
        # Guardado ANTES de qualquer recusa, e limpo nelas: pedido que não
        # chegou a carregar nada não pode deixar destino pendurado.
        self._destino_documentacao = str((entrada or {}).get("apos") or "")
        if not os.path.isdir(pasta):
            self._destino_documentacao = ""
            self.fichinha.mostrar_status(
                "A pasta do caso preparado não é alcançada desta máquina: "
                f"{pasta or '(sem pasta)'}", erro=True)
            return
        self.fichinha.definir_caminho(pasta)
        self._fichinha_gerar(pasta)
        if self.caso.pasta_carregada != pasta:
            self._destino_documentacao = ""
            return   # a carga não começou: outra em curso, ou recusada
        self.caso.origem_temporaria = {
            "instancia": entrada.get("instancia"), "pasta": pasta,
            "paciente": entrada.get("paciente") or "",
            "registro": entrada.get("registro") or ""}
        self.fichinha.definir_liberacao(
            {"permitido": fichinha.pode_liberar(self._papel)})

    def _pasta_do_paciente_para_liberar(self, dados: dict) -> str:
        """Onde a ficha liberada fica: a pasta do cadastro de simulação.

        Procurada AGORA, e não lida da preparação (decisão de 11/09/2026): um
        recadastro depois da preparação muda a pasta, e a anotada estaria
        vencida. Sem cadastro, pergunta — nada é criado sozinho, porque um nome
        inventado aqui divergiria do que a Capa cadastrar depois. A escolha não
        pode cair na temporária: seria gravar a ficha definitiva no lugar que
        a limpeza da automação apaga.
        """
        origem = self.caso.origem_temporaria or {}
        nome = origem.get("paciente") or dados.get("pac_nome") or ""
        registro = origem.get("registro") or dados.get("pac_registro") or ""
        try:
            from isocentro.interface import simulacao
            raiz = str(simulacao.raiz())
            if not os.path.isdir(raiz):
                # Outra providência que "sem cadastro": configurar a estação,
                # não cadastrar o paciente — mesma distinção do ``_preparar``.
                motivo = (f"A pasta das simulações ({raiz}) não é alcançada "
                          "desta máquina.")
            else:
                achada = str(simulacao.procurar(nome, registro) or "")
                if achada and os.path.isdir(achada):
                    return achada
                motivo = "Este paciente não tem cadastro de simulação."
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Liberação: falhou ao procurar a simulação de %s",
                           registro)
            motivo = f"Não deu para procurar o cadastro de simulação: {exc}"
        ui.avisar(self, "Onde gravar a ficha liberada",
                  f"{motivo}\n\nEscolha a pasta do paciente. A ficha não é "
                  "gravada na pasta temporária.")
        # ``<temporária>/<registro>/<curso>``: dois níveis acima é a raiz.
        temporaria = os.path.dirname(os.path.dirname(origem.get("pasta") or ""))
        while True:
            escolhida = QFileDialog.getExistingDirectory(
                self, "Pasta do paciente")
            if not escolhida:
                return ""
            if temporaria and _dentro_de(escolhida, temporaria):
                ui.alertar(self, "Pasta temporária",
                           "Essa pasta fica dentro da pasta temporária da "
                           "automação. Escolha a pasta do paciente.")
                continue
            return escolhida

    def _anotar_liberacao(self, pasta: str, dados: dict) -> None:
        """Marca o caso como liberado e redesenha o quadro.

        Falhar aqui não desfaz nada — a ficha já está gravada —, mas tem de ser
        dito: sem a marca a linha continua ``● PRONTA``, e o próximo físico
        liberaria de novo.
        """
        origem = self.caso.origem_temporaria or {}
        u = self._usuario or {}
        try:
            gatilho_registro.anotar_liberada(
                origem.get("instancia"), u.get("nome") or u.get("usuario") or "",
                str(pasta))
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Falhou ao anotar a liberação")
            ui.alertar(self, "Liberação não anotada",
                       f"A ficha foi gravada em {pasta}, mas a marca de "
                       f"liberada não:\n\n{exc}\n\nA linha continuará PRONTA "
                       "na Fichinha — não libere de novo.")
        historico.registrar("ficha_liberada", detalhes={
            "paciente": dados.get("pac_nome", ""),
            "registro": dados.get("pac_registro", ""),
            "pasta": str(pasta), "origem": origem.get("pasta", "")})
        self._fichinha_atividades()

    def _carga_terminou(self) -> None:
        """Fim da carga da pasta, em três tempos: assentar → perguntar → prévia.

        A ordem não é decorativa, e os dois cortes têm motivo:

        **A trilha assenta ANTES das perguntas.** O diálogo subia sobre uma
        tela ainda em CARREGANDO, dizendo "Ficha em andamento": o programa se
        declarava ocupado e ao mesmo tempo pedia uma decisão. Quem estava na
        frente não sabia se devia responder ou esperar.

        **A prévia vem DEPOIS das perguntas.** Montada antes, ela saía com
        ``self.caso.agendamento`` ainda ``None`` e com o fracionamento da dose alta
        ainda por confirmar: a Visualização nascia apagada pedindo "monte o
        agendamento e volte aqui" — justamente o diálogo que estava na tela — e
        nada no aceite dele refazia a prévia. A Fichinha ficava travada pedindo
        o que já estava feito.
        """
        self._set_botoes_pasta(True)
        tem_ficha = self._fichinha_carga_assentou()
        self._remontar_a_aba_aberta()
        self._perguntar_o_que_a_carga_deixou()
        if tem_ficha:
            # A elaboração do PDF faz parte do clique, não da Visualização: se o
            # botão está aceso, a ficha tem de estar pronta para abrir na hora.
            # O "em andamento" é escrito AQUI, e não lá atrás: é agora que o
            # programa realmente trabalha, e não enquanto esperava resposta.
            self.fichinha.mostrar_status(_FICHA_EM_ANDAMENTO)
            self._fichinha_previa_e_status(self.form.pac_nome.text().strip())
        self._cumprir_destino_da_documentacao(tem_ficha)

    def _cumprir_destino_da_documentacao(self, tem_ficha: bool) -> None:
        """Dá o passo que o botão da Documentação pediu antes da carga.

        Na v8 «Visualizar» e «Editar» montam o caso quando ele ainda não está
        montado, e só então entregam o resultado — um na prévia, o outro na
        bancada. Montar leva segundos e acontece noutra thread, então o destino
        viaja na entrada (``apos``) e é cumprido aqui, no fim.

        **Consumido sempre**, inclusive quando a carga não deu em ficha: um
        destino esquecido dispararia na PRÓXIMA carga, que pode ser de outro
        paciente — e abriria a bancada sozinha, sem ninguém ter pedido.
        """
        destino, self._destino_documentacao = self._destino_documentacao, ""
        if not destino or not tem_ficha:
            return
        if destino == fichinha.EDITAR:
            self._fichinha_edicao()
        elif destino == fichinha.VISUALIZAR and self.fichinha.previa_pronta():
            self._fichinha_visualizar()

    def _remontar_a_aba_aberta(self) -> None:
        """Refaz a tela que está NA FRENTE depois de uma carga.

        Trocar de aba sempre remontou a tela que aparece (ver
        ``_trocar_modo``), e isso bastava enquanto carregar pasta era gesto da
        bancada: a pessoa carregava ali e ia para a Capa, e a ida remontava.

        Deixou de bastar em 04/09/2026, com a busca da Capa e da Virtual
        puxando a pasta (``_sincronizar_bancada``). Nesse caminho a pessoa JÁ
        está na aba, e a troca nunca acontece — mas a carga passa pelo
        ``_executar_limpeza``, que zera a Capa e fecha a Virtual de propósito,
        porque eram do paciente anterior. Resultado: buscava-se um paciente e a
        tela ficava em branco, no exato caso em que a sincronia existe para
        ajudar.

        Só remonta quando a aba está aberta, e chama o MESMO método da troca —
        uma segunda montagem escrita aqui divergiria da de lá no primeiro
        conserto que alguém fizesse só num dos dois lugares.
        """
        atual = self._stack.currentIndex()
        if atual == fichinha.MODO_CAPA:
            self.controle_capa.ao_abrir()
        elif atual == fichinha.MODO_FICHA_VIRTUAL:
            self.controle_virtual.ao_abrir()
        elif atual == fichinha.MODO_QUALIDADE:
            self._qualidade_ao_abrir()

    def _fichinha_carga_assentou(self) -> bool:
        """Tira a trilha de CARREGANDO e diz se a ficha ficou de pé.

        Metade do antigo ``_fichinha_carga_terminou``: só o que pode acontecer
        ANTES do agendamento. A prévia ficou de fora de propósito — ver
        ``_carga_terminou``.
        """
        if self._auto_pendente is None:
            return False                # carga da bancada, não da Fichinha
        self._auto_pendente = None
        if not self._estado_fichinha_tem_ficha():
            self.fichinha.definir_estado(fichinha.INICIAL)
            self.fichinha.mostrar_status(
                "Não consegui montar a ficha com esta pasta — veja se ela tem "
                "a TC e o plano (RP/RS/RD).", erro=True)
            return False
        self.fichinha.definir_estado(fichinha.PRONTA)
        nome = self.form.pac_nome.text().strip()
        self._fichinha_conferir()
        historico.registrar("ficha_automatica", detalhes={"nome": nome})
        # O que a tela diz enquanto o agendamento está por cima dela. "Ficha em
        # andamento" ali era mentira em dois sentidos: a carga acabou, e o que
        # falta não é o programa trabalhar — é o usuário responder.
        if self.caso.agendamento_pendente:
            self.fichinha.mostrar_status(
                f"Ficha de {nome} montada. Falta o agendamento das frações — "
                "ele abre agora.")
        return True

    def _fichinha_previa_e_status(self, nome: str) -> bool:
        """Elabora a prévia, acende (ou não) a Visualização e explica o porquê.

        Ficha montada não é ficha pronta: no multi-plano o documento só fecha
        depois do agendamento, e até lá a Visualização fica apagada com o motivo
        na tela — em vez de acesa, abrindo a elaboração no clique.
        """
        ok = self._preparar_previa()
        self.fichinha.definir_previa(ok)
        if ok:
            self.fichinha.mostrar_status(f"Ficha de {nome} pronta.")
            return True
        self.fichinha.mostrar_status(
            f"Ficha de {nome} montada, mas ainda não dá para conferir: "
            + self._motivo_sem_previa(), erro=True)
        return False

    def _motivo_sem_previa(self) -> str:
        """Por que o documento não fechou — na linguagem de quem vai resolver."""
        if len(self.caso.planos) >= 2 and not self.portao.agendamento_completo():
            # "em Total → Agendamento" enquanto a Ficha Total era uma aba da
            # faixa; ela saiu de lá (ver ``fichinha.MODOS_OCULTOS``), e mandar
            # procurar um botão que não existe mais é pior que não explicar.
            return (f"o caso tem {len(self.caso.planos)} planos e o agendamento não "
                    "cobre todas as frações. Monte-o em Edição → "
                    "Agendamento e volte aqui.")
        pend = self.portao.pendencias()
        if pend:
            return f"{pend[0]} Resolva em Edição e gere de novo."
        return "veja o que ficou pendente na lista acima e gere de novo."

    def _preparar_previa(self) -> bool:
        """Monta o PDF da prévia e guarda o arquivo, sem abrir o leitor.

        Sem ``_aviso_progresso`` aqui: o próprio ``controle_ficha.gerar_pdf`` já envolve a
        parte pesada nele, e envolver de novo aninharia o bloqueio (o interno
        destravaria os botões antes de o externo terminar).
        """
        self._descartar_previa()
        self._previa_ok = False
        self.controle_ficha.gerar_pdf(preview=True, abrir=False)
        return self._previa_ok

    def _fichinha_conferir(self) -> None:
        """Pendências (o que falta) + alertas de padrão (o que destoa)."""
        pend = self.portao.pendencias()
        try:
            alertas = aprendizado.avaliar(self.form.coletar(),
                                          self.caso.dados.get("RP") or {})
        except Exception:  # noqa: BLE001 - conferir nunca derruba a ficha
            logging.getLogger(__name__).exception("aprendizado: falha ao avaliar")
            alertas = []
        self.fichinha.mostrar_avisos(pend, alertas)

    def _fichinha_edicao(self) -> None:
        """Edição: a Fichinha VIRA a bancada, em vez de abrir um diálogo.

        Era o ``DialogEdicaoFicha`` — o editor consolidado, que mexe no
        formulário e no RP do plano ativo e mais nada. De fora dele ficavam o
        agendamento, os cortes, o 3D e a troca de plano, que é justamente o que
        falta quando a ficha não fecha (ver ``_motivo_sem_previa``): a saída era
        fechar o diálogo, trocar para a aba Total e refazer o caminho a pé.
        Agora o botão leva direto para lá — e a aba Total saiu da faixa, porque
        com este caminho ela deixou de ser uma tela que se escolhe: é onde se
        resolve o caso que a Fichinha não resolveu. A volta é o botão Fichinha.

        A prévia cai na IDA, não na volta: o que foi conferido não é mais o que
        sairia impresso, e a Impressão não pode continuar acesa enquanto o caso
        está sendo mexido do outro lado. Reconferir e refazer a prévia acontece
        sozinho ao voltar (ver ``_trocar_modo``), com o resultado da edição —
        aqui ainda não há edição nenhuma para conferir.
        """
        self.fichinha.invalidar_visualizacao()
        self._ir_para_modo(fichinha.MODO_TOTAL)
        self.status.showMessage("Edição na bancada. Volte à Fichinha para "
                                "visualizar e imprimir.", 6000)

    def _fichinha_visualizar(self) -> None:
        """Abre a prévia já montada. É o que libera a Impressão.

        No caminho normal o PDF foi elaborado no clique do ISOCENTRO (ou
        logo após a Edição) e aqui é só abrir o arquivo — instantâneo. O
        remonte só acontece quando alguma coisa invalidou a prévia por fora,
        por exemplo o agendamento montado na bancada; aí a mensagem de
        elaboração é honesta, porque a ficha realmente mudou.
        """
        if not (self._previa_caminho and os.path.exists(self._previa_caminho)):
            self.fichinha.mostrar_status(_FICHA_EM_ANDAMENTO)
            if not self._preparar_previa():
                self.fichinha.mostrar_status(
                    "A prévia não foi gerada — resolva o que ficou pendente e "
                    "tente de novo.", erro=True)
                return
        try:
            os.startfile(self._previa_caminho)
        except OSError as exc:
            self.fichinha.mostrar_status(
                f"Não consegui abrir a prévia: {exc}", erro=True)
            return
        self.fichinha.definir_estado(fichinha.VISTA)
        self.fichinha.mostrar_status(
            "Prévia aberta. Se estiver certa, siga para a Impressão.")

    def _fichinha_imprimir(self) -> None:
        """Ficha definitiva: grava o PDF e versiona o registro.

        Com pendência em aberto, passa pela mesma confirmação do modo Ficha
        Total — a lista na tela informa, mas não substitui o aceite explícito.
        """
        if not self.portao.confirmar_pendencias():
            return
        self.controle_ficha.gerar_pdf(preview=False)
        # A ficha recém-gerada entrou no índice e já conta para o padrão da
        # próxima: descarta o perfil em cache para a próxima conferência lê-lo
        # de novo, com esta ficha dentro.
        aprendizado.perfil(forcar=True)
        # E entra na lista de baixo na hora — é a confirmação de que a
        # impressão virou documento, no mesmo lugar onde ela será procurada
        # depois. No Histórico também: a ficha que acabou de sair é do
        # serviço tanto quanto é minha.
        self._fichinha_recentes()
        self._fichinha_historico()

    # ── Suas últimas fichas (lista da tela Fichinha) ─────────────────────

    # ── Shell Torre ─────────────────────────────────────────────────────

    def _no_inicio(self) -> bool:
        return self._raiz.currentWidget() is self.inicio

    def _mostrar_inicio(self) -> None:
        """"◂ Início" e Alt+Home: volta na clínica que estava marcada."""
        self._raiz.setCurrentWidget(self.inicio)
        self._modulo_aberto = ""
        self._atualizar_identidade()

    def _abrir_modulo(self, chave: str) -> None:
        """O bloco da doca abre o módulo em tela cheia.

        Radioteraficha: as telas de sempre, com a faixa de abas no topo do
        módulo. Indicadores: a tela do Radioteradados, sem faixa (é uma tela
        só). Documentação: a aba PPR, na clínica do Início. Os outros seis:
        a tela de "em construção".
        """
        modulo = next((m for m in torre.MODULOS if m.chave == chave), None)
        if modulo is None:
            return
        self._modulo_aberto = chave
        contexto = self.inicio.clinica()
        self.topo_modulo.definir(modulo, contexto)
        self._barra_modo.setVisible(chave == "radioteraficha")
        if chave == "radioteraficha":
            self._conteudo_modulo.setCurrentWidget(self._stack)
            if self._stack.currentIndex() == fichinha.MODO_RADIOTERADADOS:
                self._ir_para_modo(fichinha.modo_inicial(self._papel))
        elif chave == "indicadores":
            self._conteudo_modulo.setCurrentWidget(self._stack)
            self._trocar_modo(fichinha.MODO_RADIOTERADADOS)
        elif chave == "documentacao":
            # O PPR é por clínica: com "Todas" a lista de códigos tem três, e
            # a aba abre na primeira unidade, com o seletor dela para trocar.
            codigos = torre.codigos_da_escolha(contexto)
            self.documentacao.definir_clinica(
                codigos[0] if len(codigos) == 1 else "", contexto)
            self._conteudo_modulo.setCurrentWidget(self.documentacao)
        else:
            self.tela_em_construcao.definir(modulo)
            self._conteudo_modulo.setCurrentWidget(self.tela_em_construcao)
        self._raiz.setCurrentWidget(self.pag_modulo)
        self._atualizar_identidade()

    def _clinica_mudou(self, escolha: str) -> None:
        """Lembrada por usuário (EXPERIENCE.md, Clínica em contexto)."""
        self._settings.setValue(self._chave_clinica, escolha)
        self._atualizar_identidade()

    def _atualizar_identidade(self) -> None:
        if not hasattr(self, "lbl_identidade") or not hasattr(self, "inicio"):
            return
        self.lbl_identidade.setText(
            torre.texto_da_barra(self._usuario, self.inicio.clinica()))

    def _alternar_modo_cor(self) -> None:
        """O símbolo ☀/☾ da faixa: troca dia↔noite e guarda a escolha."""
        aplicar_modo("dia" if estilo.modo() == "noite" else "noite")

    def _janela_ficha(self):
        """Gancho de ``AcoesDeFicha``: aqui a janela principal é ela mesma."""
        return self

    def _fichinha_recentes(self) -> None:
        """Recarrega a lista — só o que o usuário LOGADO gerou.

        O log diz o que a pessoa fez e quando; o índice central diz o que
        ainda existe em disco (registro salvo, quantas versões, PDF). A lista
        precisa dos dois: o primeiro para o recorte por usuário, o segundo para
        saber quais ações acender em cada linha.
        """
        try:
            res = historico.fichas_do_usuario(
                self._usuario, limite=fichinha.MAX_RECENTES)
        except Exception:  # noqa: BLE001 — a lista é acessória
            _LOG.exception("Fichinha: falha ao ler as fichas recentes")
            res = {"recentes": [], "hoje": 0}
        entradas = res.get("recentes") or []
        try:
            # Uma leitura só do índice para as dez linhas (ver
            # ``indice.resumo_por_registro``).
            resumo = indice.resumo_por_registro(
                {e.get("registro") for e in entradas})
        except Exception:  # noqa: BLE001
            _LOG.exception("Fichinha: falha ao consultar o índice central")
            resumo = {}
        for e in entradas:
            r = resumo.get(e.get("registro") or "") or {}
            ultima = r.get("ultima") or {}
            e["n_versoes"] = r.get("versoes", 0)
            e["nome"] = ultima.get("nome") or e.get("paciente", "")
            e["json_path"] = ultima.get("json_path") or ""
            e["pdf_path"] = ultima.get("pdf_path") or ""
            # Ficha antiga, gerada antes de a pasta ser anotada no evento: o
            # índice sabe onde o JSON parou, e a pasta do paciente é a dele.
            if not e.get("pasta") and e["json_path"]:
                e["pasta"] = os.path.dirname(e["json_path"])
        self.fichinha.definir_recentes(entradas, res.get("hoje") or 0)

    def _fichinha_datas(self) -> None:
        """Recarrega o quadro de Datas Relevantes.

        Falha de leitura NÃO vira quadro vazio calado: o arquivo é do serviço,
        e uma lista vazia aqui diz "ninguém anotou nada" — que é exatamente o
        contrário de "não consegui ler o que anotaram".
        """
        try:
            eventos = datas_relevantes.ler()
        except Exception as exc:  # noqa: BLE001 — o quadro é acessório
            _LOG.exception("Fichinha: falha ao ler as datas relevantes")
            self.fichinha.definir_datas([])
            self.fichinha.b_datas.definir_rodape(
                f"Não deu para ler o quadro: {str(exc)[:60]}")
            return
        self.fichinha.b_datas.definir_rodape("")
        self.fichinha.definir_datas(eventos)

    def _fichinha_acao_data(self, acao: str, evento: dict) -> None:
        """Criar, alterar e excluir um evento do quadro do serviço."""
        try:
            if acao == fichinha.NOVA_DATA:
                novo = fichinha.perguntar_evento(self)
                if novo:
                    datas_relevantes.criar(
                        novo["data"], novo["titulo"], novo["tipo"],
                        novo["nota"], por=historico._nome_usuario(self._usuario))
            elif acao == fichinha.EDITAR_DATA and evento.get("id"):
                alterado = fichinha.perguntar_evento(self, evento)
                if alterado:
                    datas_relevantes.alterar(
                        evento["id"], data=alterado["data"],
                        titulo=alterado["titulo"], tipo=alterado["tipo"],
                        nota=alterado["nota"])
            elif acao == fichinha.EXCLUIR_DATA and evento.get("id"):
                if ui.confirmar(
                        self, "Excluir este evento?",
                        f"«{evento.get('titulo') or ''}» sai do quadro do "
                        "serviço, para todas as estações.",
                        acao="Excluir", recusa="Manter"):
                    datas_relevantes.excluir(evento["id"])
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Fichinha: falha ao gravar no quadro de datas")
            ui.falhar(self, "Quadro de datas",
                      f"Não deu para gravar: {exc}")
        self._fichinha_datas()

    def _fichinha_historico(self) -> None:
        """Recarrega o bloco Histórico — as últimas do SERVIÇO inteiro.

        Mesma leitura das recentes, com o filtro por usuário DESLIGADO: o
        ``fichas_do_usuario("")`` não recorta por ninguém. Passar o usuário
        vazio em vez de ``None`` é a diferença entre "todo mundo" e "o logado",
        e ela não se adivinha lendo a chamada — por isso está escrita aqui.
        """
        try:
            res = historico.fichas_do_usuario(
                "", limite=fichinha.MAX_HISTORICO)
        except Exception:  # noqa: BLE001 — a lista é acessória
            _LOG.exception("Fichinha: falha ao ler o histórico do serviço")
            self.fichinha.definir_historico([])
            return
        entradas = res.get("recentes") or []
        try:
            resumo = indice.resumo_por_registro(
                {e.get("registro") for e in entradas})
        except Exception:  # noqa: BLE001
            _LOG.exception("Fichinha: falha ao consultar o índice central")
            resumo = {}
        for e in entradas:
            r = resumo.get(e.get("registro") or "") or {}
            ultima = r.get("ultima") or {}
            e["json_path"] = ultima.get("json_path") or ""
            e["pdf_path"] = ultima.get("pdf_path") or ""
            e["n_versoes"] = r.get("n_versoes") or 0
            if not e.get("pasta") and e["json_path"]:
                e["pasta"] = os.path.dirname(e["json_path"])
        self.fichinha.definir_historico(entradas)

    def _fichinha_altas(self) -> None:
        """Recarrega o quadro de Altas Prontas.

        **Ainda sem o filtro real.** O parâmetro é a atividade "Verificar
        Programação {unidade}" do care path (decisão do usuário em
        22/09/2026), e o código dela no ARIA não é descobrível desta máquina —
        o catálogo exige identidade de rede. Enquanto
        ``atividades_db.CODIGOS_ALTA`` estiver vazio, o quadro diz isso em vez
        de mostrar lista vazia: vazio aqui AFIRMA que não há alta a imprimir, e
        é a leitura errada mais cara deste bloco.
        """
        if not atividades_db.CODIGOS_ALTA:
            self.fichinha.definir_altas(
                None, "A atividade que alimenta esta lista ainda não foi "
                      "identificada no sistema.")
            return
        if not atividades_db.disponivel():
            self.fichinha.definir_altas(
                None, atividades_db.motivo_indisponivel())
            return
        try:
            lista = atividades_db.altas()
        except Exception as exc:  # noqa: BLE001 — o quadro é acessório
            _LOG.exception("Fichinha: falha ao ler as altas do ARIA")
            self.fichinha.definir_altas(
                None, f"Não deu para perguntar ao sistema: {str(exc)[:80]}")
            return
        entradas = []
        for a in lista:
            pasta, pdf = self._alta_em_disco(a.registro)
            entradas.append({
                "paciente": a.paciente, "registro": a.registro,
                "unidade": a.unidade, "data": a.data_br(), "dono": a.dono,
                "instancia": a.instancia, "pasta": pasta, "pdf": pdf})
        # SEM a hora da leitura: o usuário mandou tirar "Do sistema, lido às…"
        # de toda a Fichinha em 23/09/2026. O rodapé fica para os RECADOS de
        # falha, que continuam — o que saiu é o carimbo de hora da leitura bem
        # sucedida.
        self.fichinha.definir_altas(entradas, "")

    def _alta_em_disco(self, registro: str) -> tuple:
        """``(pasta, pdf)`` do paciente — o Relatório de Alta mais recente.

        O PDF é procurado pelo prefixo que o ``controle_ficha.salvar_alta``
        grava (``ALTA_…``), na pasta da última ficha daquele registro. O mais
        recente por NOME e não por data de arquivo: o nome carrega a data da
        ficha, e copiar a pasta para outro disco reescreve a data do arquivo
        sem mudar qual alta é a boa.
        """
        try:
            resumo = indice.resumo_por_registro({registro}) or {}
            ultima = ((resumo.get(registro) or {}).get("ultima") or {})
            pasta = os.path.dirname(ultima.get("json_path") or "")
            if not pasta or not os.path.isdir(pasta):
                return "", ""
            altas = sorted(n for n in os.listdir(pasta)
                           if n.upper().startswith("ALTA_")
                           and n.lower().endswith(".pdf"))
            return pasta, (os.path.join(pasta, altas[-1]) if altas else "")
        except Exception:  # noqa: BLE001 — a marca é acessória
            _LOG.exception("Fichinha: falha ao procurar a alta de %s", registro)
            return "", ""

    def _fichinha_acao_alta(self, acao: str, entradas: list) -> None:
        """Abre as altas escolhidas (ou as pastas delas).

        Pergunta acima de ``MAX_ALTAS_SEM_PERGUNTAR``: cada PDF abre um leitor,
        e quarenta leitores de uma vez é a estação parada por minutos sem que
        nada na tela diga que foi o clique que fez isso.
        """
        entradas = list(entradas or [])
        campo = "pdf" if acao == fichinha.ABRIR_ALTA else "pasta"
        alvos = [e.get(campo) for e in entradas if e.get(campo)]
        faltam = len(entradas) - len(alvos)
        if not alvos:
            ui.alertar(self, "Nada para abrir",
                       "Não achei o Relatório de Alta na pasta "
                       + ("deste paciente." if len(entradas) == 1
                          else "de nenhum dos pacientes escolhidos."))
            return
        if len(alvos) > fichinha.MAX_ALTAS_SEM_PERGUNTAR and not ui.confirmar(
                self, f"Abrir {len(alvos)} arquivos?",
                "Cada um abre numa janela própria.",
                acao=f"Abrir os {len(alvos)}", recusa="Deixar para lá"):
            return
        for alvo in alvos:
            try:
                os.startfile(alvo)   # noqa: S606 — abre no leitor do Windows
            except Exception:  # noqa: BLE001
                _LOG.exception("Fichinha: falha ao abrir %s", alvo)
        if faltam:
            # Dito DEPOIS de abrir o que dava: quem escolheu cinco e viu três
            # abrirem precisa saber que os outros dois não sumiram por engano.
            ui.avisar(self, "Nem todas abriram",
                      f"{faltam} paciente(s) sem Relatório de Alta na pasta.")

    def _fichinha_atividades(self) -> None:
        """Recarrega o quadro de Documentação do ARIA.

        Mesmo desenho do ``_fichinha_recentes``: quem lê e traduz é a janela, o
        painel só desenha. E, como lá, a falha não pode derrubar a tela — mas
        aqui ela também não pode virar lista vazia, porque vazio aqui é uma
        AFIRMAÇÃO ("não há nada a documentar"). Por isso o painel recebe
        ``None`` com o motivo, e não ``[]``.

        Consulta direta, na thread da tela: medido em 02/09/2026, 0,3 s contra
        o limite de 6 s do ``capa_db``. Se um dia passar disso, o caminho é o
        do ``capa_db.aquecer`` — thread própria e a tela preenchida quando a
        resposta chega —, não aumentar o limite.
        """
        if not atividades_db.disponivel():
            self.fichinha.definir_atividades(
                None, atividades_db.motivo_indisponivel())
            return
        try:
            lista = atividades_db.todas()
        except Exception as exc:  # noqa: BLE001 — o quadro é acessório
            _LOG.exception("Fichinha: falha ao ler as atividades do ARIA")
            self.fichinha.definir_atividades(
                None, f"Não deu para perguntar ao sistema: {str(exc)[:80]}")
            return
        # O estado da preparação vem do ``gatilho_registro.json``, que a
        # concentradora grava e toda estação lê. Ilegível não vira "nenhum
        # estado" calado: a lista sai sem a coluna e o rodapé diz por quê — um
        # quadro sem nenhum PRONTA seria lido como "nada preparado ainda".
        recado_estado = ""
        try:
            estados = gatilho_registro.estados_da_documentacao()
        except Exception:  # noqa: BLE001 — o quadro continua sem o estado
            _LOG.exception("Fichinha: falha ao ler o estado da preparação")
            estados = {}
            recado_estado = " Estado da preparação ilegível."
        self.fichinha.definir_atividades(
            [{"dono": a.dono, "paciente": a.paciente, "registro": a.registro,
              "data": a.data_br(), "titulo": a.titulo(), "estado": a.estado,
              "instancia": a.instancia,
              "automacao": estados.get(a.instancia)}
             for a in lista],
            # Sem o carimbo de hora (ver ``_fichinha_altas``); o recado do
            # estado da preparação continua, porque ele diz que FALTA
            # informação na lista, e não que ela foi lida.
            recado_estado.strip())

    def _fichinha_acao_recente(self, acao: str, entrada: dict) -> None:
        """Executa a ação pedida sobre uma ficha da lista de recentes.

        São as MESMAS da tela de Histórico e chegam lá (``AcoesDeFicha``) sem
        cópia nenhuma: a linha do índice já veio embutida na entrada.
        """
        nome = (entrada or {}).get("paciente") or "a ficha"
        if acao == fichinha.PASTA:
            if self.ficha_abrir_pasta(entrada):
                self.fichinha.mostrar_status(
                    f"Pasta de {nome} aberta no Explorador de Arquivos.")
        elif acao == fichinha.VERSOES:
            self.ficha_verificar_versao(entrada)
        elif acao == fichinha.PDF:
            if self.ficha_abrir_pdf(entrada):
                self.fichinha.mostrar_status(
                    f"PDF de {nome} aberto. A ficha em elaboração continua "
                    "aqui, intacta.")
        elif acao == fichinha.CARREGAR:
            self._fichinha_carregar_registro(entrada)

    def _fichinha_carregar_registro(self, entrada: dict) -> None:
        """Traz o caso de volta do registro salvo e reacende a trilha.

        ``carregar_registro`` deixa a bancada montada, e daqui em diante a
        Fichinha tem de descrever ESSE caso: o campo aponta a pasta dele, a
        trilha volta para PRONTA e a prévia é elaborada — senão a Visualização
        ficaria apagada sobre uma ficha que está pronta para ser vista.
        """
        if not self.ficha_carregar(entrada):
            return
        self.fichinha.limpar_selecao_recente()
        if self.caso.pasta_carregada:
            self.fichinha.definir_caminho(self.caso.pasta_carregada)
        self.fichinha.definir_estado(fichinha.PRONTA)
        nome = self.form.pac_nome.text().strip()
        self._fichinha_conferir()
        self.fichinha.mostrar_status(_FICHA_EM_ANDAMENTO)
        self._fichinha_previa_e_status(nome)

    # ── Modo Ficha Virtual ──────────────────────────────────────────────
    # A aba consulta o tratamento ENTREGUE. Ela não fala com o banco: pede por
    # sinal e recebe pronto, como a Capa — assim a tela é testável sem rede, e
    # decidir o que fazer quando o banco não responde continua sendo de um lugar
    # só.

    # ── Aba Qualidade ────────────────────────────────────────────────────

    def _qualidade_ao_abrir(self) -> None:
        """Entrega à aba Qualidade o caso que está na bancada.

        A aba NÃO calcula na carga da pasta, e sim aqui: ler as grades de dose
        de um caso de quatro planos custa segundos, e pagá-los em toda abertura
        de pasta — inclusive de quem nunca abre esta aba — seria cobrar de todo
        mundo o preço de um.

        ``self.caso.planos`` é RECRIADO a cada carga (ver ``_plano_carregado``), e é
        por isso que a comparação é de identidade e não de conteúdo: dois casos
        diferentes podem ter a mesma quantidade de planos com os mesmos rótulos,
        e a aba mostraria os índices do paciente anterior sem nada na tela
        dizendo isso.
        """
        if self.caso.planos is not getattr(self, "_qualidade_planos", None):
            self._qualidade_planos = self.caso.planos
            self.qualidade.definir_planos(
                self.caso.planos,
                len(self.caso.planos) >= 2 and self._planos_mesma_tc(),
                self.form.pac_nome.text().strip())
        self.qualidade.ao_abrir()

    def _fechar_na_ficha_virtual(self) -> None:
        """Fecha o paciente na Ficha Virtual e esquece a recusa da sincronia.

        As duas coisas juntas porque as TRÊS portas de fechar (Fichinha, Total e
        Capa) passam por aqui — ver ``ControleFichaVirtual.fechar``. A recusa é
        da janela: é ela quem pergunta antes de trocar o caso da bancada.
        """
        self._sync_recusado = ""
        self.controle_virtual.fechar()

    def _capa_mudou(self) -> None:
        """A capa mudou: os PDFs já gerados nas outras telas envelheceram.

        A ficha técnica EMBUTE a capa na primeira página (ver ``_juntar_capa``).
        Corrigir o convênio aqui e clicar em Visualização na Fichinha abria o
        PDF guardado — com a capa ANTIGA — sem nada dizendo que estava velho.
        Quem confere na tela acha que corrigiu; o papel sai como estava.

        Descartar é melhor que regerar: gerar custa segundos e nem sempre a
        pessoa vai olhar de novo. Assim o próximo clique monta o que está na
        tela agora.
        """
        self._descartar_previa()
        self.controle_capa.descartar_pdf()
        # A Fichinha acende a Impressão com base na prévia CONFERIDA. Com a
        # prévia descartada não há o que imprimir, e a marca tem de cair junto —
        # senão o botão continua aceso oferecendo um PDF que não existe mais.
        self._previa_ok = False

    def _sincronizar_bancada(self, registro: str, nome: str = "") -> None:
        """O paciente escolhido no SERVIDOR passa a ser o paciente do programa.

        Pedido em 04/09/2026, e o defeito que ele fecha é o pior desta tela:
        trocar de paciente na Ficha Virtual deixava a bancada e a Fichinha no
        anterior. **Duas identidades ao mesmo tempo numa tela de conferência**
        — que era exatamente o que o comentário do ``ControleFichaVirtual.seguir_o_foco``
        já chamava de pior defeito possível, mas só evitava numa das direções.

        A divisão de trabalho que o usuário desenhou:

        * **Fichinha e Total** buscam pela PASTA do paciente;
        * **Capa-Up e Virtual** buscam por nome ou registro no SERVIDOR;
        * e a busca no servidor **puxa a pasta junto**, quando ela existe.

        Duas travas, e as duas importam:

        1. **paciente que já está na bancada não recarrega.** É o que impede o
           laço — carregar a pasta preenche ``pac_registro``, que reacende o
           foco, que chamaria isto de novo;
        2. **quem confirma a troca é o ``_carregar_pasta``**, que já pergunta
           "Substituir paciente atual?" desde sempre. Não se descarta caso
           montado por causa de um clique numa lista de busca.

        Sem pasta, a Capa e a Virtual seguem mostrando o paciente — elas vivem
        do banco. Não é erro: paciente do servidor pode não ter pasta nenhuma
        ainda, e é o caso mais comum de quem acabou de sair da tomografia.
        """
        reg = capa_dados.normalizar_id(registro)
        if not reg:
            return
        if capa_dados.normalizar_id(self.form.pac_registro.text()) == reg:
            self._sync_recusado = ""
            return
        # Recusar a troca vale para o paciente, não para o clique. Sem esta
        # memória, cada mudança de CURSO na Ficha Virtual chamava isto de novo
        # e a pergunta destrutiva voltava — e pergunta que reaparece é como se
        # ensina a clicar sem ler. Achado na revisão de 04/09/2026.
        if reg == self._sync_recusado:
            return
        # Uma carga em curso não é interrompida — mas DIZ. A saída era
        # silenciosa, e isso deixava o pedido cair no vazio: quem deu duplo
        # clique em B enquanto A carregava ficava com A na tela e nenhuma
        # explicação, que é a dupla identidade que este método existe para
        # evitar. Achado na revisão de 04/09/2026.
        if self._worker_tudo is not None and self._worker_tudo.isRunning():
            self.status.showMessage(
                f"Uma pasta ainda está carregando — repita em {nome or reg} "
                "quando ela terminar.", 6000)
            return
        pasta = ""
        try:
            # ``registro`` CRU nas duas, e não o ``reg`` normalizado: o
            # ``indice.listar_versoes`` casa por igualdade exata com o que foi
            # gravado, e os três chamadores antigos do ``pasta_da_ficha`` todos
            # passam o cru. Normalizado, a reserva do índice erraria em
            # silêncio — e silêncio aqui é "esse paciente não tem pasta".
            pasta = (simulacao.procurar(nome, registro)
                     or controle_virtual.pasta_da_ficha(registro))
        except Exception:  # noqa: BLE001 — a busca no servidor não pode cair
            _LOG.exception("Não deu para achar a pasta de %r", registro)
            return
        if not pasta:
            # Dito na barra, e não em silêncio: quem espera que a bancada
            # acompanhe precisa saber por que ela não acompanhou.
            self.status.showMessage(
                f"{nome or reg}: sem pasta de caso no serviço — a bancada "
                "ficou como estava.", 6000)
            return
        self._carregar_pasta(pasta)
        if self._worker_tudo is not None and self._worker_tudo.isRunning():
            return      # a carga segue no fundo; o ``_carga_terminou`` remonta a aba
        if capa_dados.normalizar_id(self.form.pac_registro.text()) == reg:
            # Reaberta NA HORA, pela ficha anterior da pasta — sem worker, e
            # por isso sem ``_carga_terminou``. A troca passou pela limpeza do
            # caso anterior, que FECHA a Ficha Virtual de propósito (era do
            # outro paciente), e nada a reabria: escolher um paciente na
            # Virtual com outro na bancada carregava o novo na bancada e
            # deixava a aba vazia, na lista (visto em 07/10/2026). Antes disto
            # o caso caía no ramo de baixo e ainda ficava marcado como RECUSADO.
            self._remontar_a_aba_aberta()
            return
        # Carga que não começou = a pessoa recusou substituir o paciente atual.
        # Fica anotado para não perguntar de novo pelo mesmo, e some assim que
        # a bancada mudar de paciente (acima) ou o caso for fechado.
        self._sync_recusado = reg

    def _abrir_pasta(self):
        # Reabre onde o usuário estava da última vez (nada na 1ª execução).
        ultima = self._settings.value("ultima_pasta", "", type=str)
        pasta = QFileDialog.getExistingDirectory(
            self, "Selecionar pasta com os arquivos DICOM", ultima or "")
        self._carregar_pasta(pasta)

    def _carregar_pasta(self, pasta: str) -> None:
        """Carrega uma pasta de DICOM — do botão Abrir pasta ou de arrastar-e-
        soltar. Confirma a troca de paciente, decide reabrir/nova e dispara o
        worker de leitura."""
        if not pasta:
            return
        # Uma leitura já em curso: o botão Abrir fica desabilitado, mas o
        # arrastar-e-soltar não passa por ele — sem esta trava, soltar uma pasta
        # durante o carregamento dispararia um 2º worker (callbacks duplicados e
        # a 1ª thread vazada). Ignora até a atual terminar.
        if self._worker_tudo is not None and self._worker_tudo.isRunning():
            self.status.showMessage("Aguarde: uma pasta ainda está carregando.")
            return
        if self.caso.dados or self.caso.ct is not None:
            if not ui.confirmar(
                    self, "Substituir paciente atual?",
                    "Já existe um paciente carregado.",
                    acao="Descartar e abrir a outra",
                    recusa="Continuar com o atual",
                    detalhe="Ao abrir uma nova pasta os dados atuais serão "
                            "descartados.",
                    perigo=True):
                return
            # Descarta o paciente atual por completo (encerra o worker, limpa o
            # estado E a pasta temporária/registro/SUS do tratamento reaberto).
            # Fonte única de limpeza — evita esquecer campos ao trocar de paciente.
            self._executar_limpeza()

        # Pasta com ficha de um tratamento ANTERIOR (JSON/zip do paciente): abrir
        # a ficha salva ou elaborar uma nova a partir do DICOM? Sem perguntar, o
        # scan seguia direto e nunca reaproveitava o registro salvo.
        registro_antigo = registro_json.registro_na_pasta(pasta)
        if registro_antigo is not None:
            # Só pergunta "reabrir x nova" se HÁ DICOM para elaborar uma nova. Se
            # a pasta tem só a ficha salva (sem TC/RP/RS/RD), "elaborar nova" não
            # faz sentido — avisa e reabre direto o tratamento anterior.
            if not _pasta_tem_dicom(pasta):
                ui.avisar(
                    self, "Ficha já elaborada",
                    "Esta pasta não contém uma TC para elaborar um novo "
                    "tratamento.\n\nEla guarda a ficha de um tratamento já "
                    "elaborado, que será reaberta para visualização/reimpressão.")
                self._reabrir_registro_da_pasta(registro_antigo, pasta)
                return
            if self._perguntar_reabrir_ou_novo():
                self._reabrir_registro_da_pasta(registro_antigo, pasta)
                return
        # De quem é esta pasta? A varredura é RECURSIVA, e uma pasta-pai com
        # vários pacientes virava UMA ficha: nome do primeiro, planos de todos,
        # sem aviso nenhum (medido em 31/08/2026 — uma ficha em nome de uma
        # paciente com planos de outras duas). Escolher aqui é o que dá dono à
        # ficha. A triagem lê só cabeçalhos: 0,1 s numa pasta de paciente.
        registro_alvo = ""
        achados = pacientes_na_pasta(pasta)
        if len(achados) > 1:
            escolha = DialogEscolherPaciente(achados, self)
            if escolha.exec() != QDialog.Accepted:
                return
            registro_alvo = escolha.escolhido()
            if not registro_alvo:
                return

        # A última pasta e o histórico só AQUI, onde a carga de fato começa.
        # Antes eram gravados no alto do método, e aí três saídas anteriores —
        # recusar a substituição, cancelar o seletor de paciente e escolher
        # "abrir ficha anterior" — deixavam lembrada uma pasta que ninguém
        # abriu, e uma linha de "pasta_carregada" no histórico compartilhado
        # para uma carga que não houve. Achado nas revisões de 04/09/2026, em
        # duas passadas: a primeira moveu para depois da confirmação, e ainda
        # ficavam as outras duas saídas.
        self._settings.setValue("ultima_pasta", pasta)
        self.caso.pasta_carregada = pasta
        # Toda carga nasce SEM origem temporária: só o clique no ``● PRONTA``
        # a põe, depois daqui. Esquecida de uma carga anterior, a próxima
        # pasta aberta à mão sairia como liberação de um caso que não é ela.
        self.caso.origem_temporaria = None
        self.fichinha.definir_liberacao(None)
        historico.registrar("pasta_carregada",
                            detalhes={"pasta": pasta,
                                      "varios_pacientes": len(achados) > 1,
                                      "registro": registro_alvo})
        self._set_botoes_pasta(False)
        self.status.showMessage("Varrendo pasta e carregando arquivos… aguarde.")
        self._worker_tudo = _CarregarTudo(pasta, self, registro=registro_alvo)
        self._worker_tudo.ct_pronto.connect(self._tc_carregada)
        self._worker_tudo.plano_pronto.connect(self._plano_carregado)
        self._worker_tudo.progresso.connect(self.status.showMessage)
        self._worker_tudo.falhou.connect(lambda msg: self._erro("Pasta", msg))
        # UM slot para o fim da carga, não três conexões: a ordem dos passos
        # importa (ver ``_carga_terminou``) e ficava escondida na ordem dos
        # ``connect``.
        self._worker_tudo.finished.connect(self._carga_terminou)
        self._worker_tudo.start()

    def _perguntar_reabrir_ou_novo(self) -> bool:
        """Pergunta se abre a ficha anterior (True) ou elabora uma nova (False)."""
        return ui.confirmar(
            self, "Ficha anterior encontrada",
            "Esta pasta já tem a ficha de um tratamento anterior.",
            acao="Abrir ficha anterior", recusa="Elaborar nova",
            detalhe=("• Abrir ficha anterior — carrega o tratamento salvo "
                     "para ver/regerar.\n"
                     "• Elaborar nova — lê os DICOM da pasta e começa uma "
                     "ficha nova."))

    def _reabrir_registro_da_pasta(self, registro: dict, pasta: str) -> None:
        """Carrega a ÚLTIMA versão de um registro achado na pasta (item da lista
        de tratados, mas a partir do DICOM aberto). Extrai o zip do paciente se os
        PNGs/JSON estiverem arquivados; a posse do temp passa a ``carregar_registro``.
        """
        versoes = registro.get("versoes") or []
        ver = max(versoes, key=lambda v: v.get("versao") or 0, default=None)
        if ver is None:
            ui.alertar(self, "Registro vazio",
                                "A ficha anterior não tem nenhuma versão salva.")
            return
        dmin = {"pac_nome": (registro.get("paciente") or {}).get("nome", "")
                or (ver.get("dados") or {}).get("pac_nome", ""),
                "pac_registro": (registro.get("paciente") or {}).get("registro", "")
                or (ver.get("dados") or {}).get("pac_registro", "")}
        # PNGs/JSON soltos na pasta ou dentro do zip? Se o JSON mestre não está
        # solto, extrai o zip para um temp e lê os auxiliares de lá.
        pasta_real = str(pasta)
        leitura, tmp = pasta_real, None
        json_solto = any(p.name.startswith("FICHA_") and p.suffix == ".json"
                         for p in Path(pasta_real).iterdir() if p.is_file())
        if not json_solto:
            import tempfile
            tmp = tempfile.mkdtemp(prefix="ficha_zip_")
            if registro_json.extrair_zip(pasta_real, dmin, tmp):
                leitura = tmp
            else:
                _limpar_temp_zip(tmp); tmp = None

        def _p(nome_ou_caminho: str) -> str:
            base = os.path.basename(nome_ou_caminho or "")
            return os.path.join(leitura, base) if base else ""

        imagens_paths = [_p(nm) for nm in (ver.get("imagens") or [])]
        dvhs_paths = [_p(nm) if nm else "" for nm in (ver.get("dvhs") or [])]
        _drr_nomes = ver.get("drrs") or [n for n in (ver.get("drr_ap"),
                                                     ver.get("drr_lateral")) if n]
        drrs_paths = [_p(nm) for nm in _drr_nomes]
        self.carregar_registro(
            ver.get("dados", {}), ver.get("plano_rp", {}), pasta_real,
            _p(ver.get("imagem") or ""), _p(ver.get("dvh") or ""),
            ver.get("render") or {}, planos=ver.get("planos"),
            imagens_paths=imagens_paths, dvhs_paths=dvhs_paths,
            agendamento=ver.get("agendamento"), tmp_extraido=tmp,
            drrs_paths=drrs_paths, drrs_titulos=ver.get("drrs_titulos") or [])
        historico.registrar("tratamento_reaberto", detalhes={
            "paciente": dmin["pac_nome"], "registro": dmin["pac_registro"],
            "versao": ver.get("versao"), "origem": "pasta_dicom"})
        self.status.showMessage(
            f"Ficha anterior reaberta (v{ver.get('versao')}).", 6000)

    def _set_botoes_pasta(self, habilitado: bool):
        self.btn_pasta.setEnabled(habilitado)
        if habilitado and (self.caso.dados or self.caso.ct is not None):
            self.btn_limpar.setEnabled(True)
            self.btn_edicao.setEnabled(True)
        self._atualizar_edicao_habilitada()

    def _tem_caso(self) -> bool:
        """Há alguma coisa carregada (pasta DICOM ou ficha reaberta)?"""
        return bool(self.caso.dados or self.caso.ct is not None or self.caso.planos)

    def _atualizar_edicao_habilitada(self) -> None:
        """Campos do caso só ficam vivos DEPOIS que há um caso.

        Com a janela recém-aberta não há paciente, plano nem TC: um combo de
        médico que abre a lista, um spin de dose que aceita número e uma lista de
        estruturas vazia convidam a preencher uma ficha que não existe — e o que
        for digitado ali some no primeiro carregamento, que sobrescreve o
        formulário. Só a trilha de botões (Abrir pasta, Histórico) fica de pé.
        """
        self.form.setEnabled(self._tem_caso())
        self.viewer.habilitar_controles(self._tem_caso())
        self._marcar_passo_atual()

    # As receitas leem o estado NA HORA (ver ``_marcar_passo_atual``); são
    # registradas uma vez na construção e reaplicadas a cada mudança de caso.
    def _folha_btn_pasta(self) -> str:
        return (estilo.btn_contorno() if self._tem_caso()
                else estilo.btn_solido())

    def _folha_btn_pdf(self) -> str:
        return (estilo.btn_solido() if self._tem_caso()
                else estilo.btn_contorno())

    def _marcar_passo_atual(self) -> None:
        """O botão SÓLIDO é o passo de agora — ele anda com o trabalho.

        Com a bancada vazia, o único gesto possível é abrir a pasta; deixá-lo
        em contorno enquanto a Impressão (apagada) segurava o preenchimento
        fazia a tela não ter para onde apontar. Com o caso carregado a ordem se
        inverte: abrir outra pasta vira desvio, e o passo é imprimir.

        Reaplica as folhas em vez de registrá-las de novo: este método roda a
        cada carga e a cada limpeza, e ``pintar`` a cada chamada empilharia um
        ouvinte por vez.
        """
        self.btn_pasta.setStyleSheet(self._folha_btn_pasta())
        self.btn_pdf.setStyleSheet(self._folha_btn_pdf())

    def _executar_limpeza(self):
        """Descarta todos os dados em memória (RP, RD, RS, TC) sem pedir confirmação."""
        if self._worker_tudo is not None and self._worker_tudo.isRunning():
            self._worker_tudo._parar = True
            try:
                self._worker_tudo.ct_pronto.disconnect()
                self._worker_tudo.plano_pronto.disconnect()
                self._worker_tudo.progresso.disconnect()
                self._worker_tudo.falhou.disconnect()
                self._worker_tudo.finished.disconnect()
            except RuntimeError:
                pass
            self._worker_tudo.wait(3000)
        # O caso inteiro de uma vez (R-06, corte 6a). Eram 25 atributos zerados
        # um a um, e a lista vivia em dois lugares: atributo novo que entrasse
        # só no ``__init__`` sobrevivia à troca de paciente. A pasta extraída
        # do zip é apagada ANTES — ela é a única coisa do caso que mora no disco.
        _limpar_temp_zip(self.caso.tmp_extraido)
        self.caso = Caso()
        if getattr(self, "fichinha", None) is not None:
            self.fichinha.definir_liberacao(None)

        self.form.limpar()

        v = self.viewer
        for painel in (v.painel_axial, v.painel_sagital, v.painel_coronal, v.painel_3d):
            painel.lbl_img.clear()
            painel.lbl_img.setText(painel.lbl_titulo.text())
            if painel.slider is not None:
                painel.slider.setRange(0, 0)
                painel.slider.setValue(0)

        p3d = v.painel_3d
        p3d._elev = 10
        p3d._azim = -30
        if hasattr(p3d, "_lbl_elev"):
            p3d._lbl_elev.setText("El +10°")
        if hasattr(p3d, "_lbl_azim"):
            p3d._lbl_azim.setText("Az -30°")

        v.lst_estruturas.clear()
        self.btn_limpar.setEnabled(False)
        self.btn_edicao.setEnabled(False)
        self._descartar_previa()   # a prévia era do paciente que acabou de sair
        # A capa também era dele: deixá-la na tela faria a próxima busca achar
        # "a capa deste paciente já montada" e nunca refazê-la.
        self.controle_capa.descartar_pdf()
        self.capa.carregar(capa_pdf.Capa())
        self.capa.habilitar(False)
        self.capa.mostrar_avisos(())
        self.capa.mostrar_status("")
        # Fechar o caso com a Capa aberta a deixaria sem paciente e sem busca —
        # uma tela morta, sem porta de saída.
        self.capa.mostrar_busca()
        self._atualizar_edicao_habilitada()   # sem caso: volta a ficar inerte
        # E a Ficha Virtual, que também era dele.
        self._fechar_na_ficha_virtual()
        self.status.showMessage("Pronto. Abra a pasta — ou arraste-a para a "
                                "janela — para começar.")

    def _limpar_tudo(self):
        """Descarta todos os dados importados e reinicia o programa para nova importação."""
        if not ui.confirmar(
                self, "Limpar dados atuais?",
                "Todos os dados do paciente serão descartados.",
                acao="Descartar tudo", recusa="Continuar com o caso",
                detalhe="Esta ação não pode ser desfeita.",
                perigo=True):
            return
        self._executar_limpeza()

    def _excluir_arquivos_pasta(self, pasta: str,
                                modalidades: set[str] | None = None,
                                registro: str | None = None):
        """Exclui permanentemente os DICOM de UM paciente na pasta e subpastas.

        Lê o header de cada .dcm (e de cada membro de .zip/.rar) e só exclui um
        arquivo quando TODOS os seus membros são das ``modalidades`` (padrão: TC,
        RP, RS e RD) E pertencem ao paciente ``registro`` (PatientID). A varredura
        é recursiva, então uma pasta-pai pode conter outros pacientes: sem o filtro
        por PatientID, apagar o paciente da ficha levaria junto os DICOM de quem
        nunca foi aberto. Arquivos de outros pacientes são contados e mantidos.

        Sem ``registro`` não há como confirmar de quem é cada arquivo: nada é
        excluído (a exclusão é irreversível — na dúvida, mantém).
        """
        # RI (DRRs de setup) e MP (protocolo de gating) são auxiliares do mesmo
        # tratamento — saem junto na limpeza da pasta.
        modalidades = modalidades or {"TC", "RP", "RS", "RD", "RI", "MP"}
        alvo = _norm_registro(registro)
        if not alvo:
            ui.alertar(
                self, "Arquivos mantidos",
                "O registro do paciente está vazio, então não é possível "
                "confirmar quais arquivos da pasta são dele.\n\n"
                "Nenhum arquivo foi excluído.",
            )
            return

        _EXT = {".dcm", ".zip", ".rar"}
        candidatos = [p for p in Path(pasta).rglob("*")
                      if p.is_file() and p.suffix.lower() in _EXT]

        a_excluir: list[Path] = []
        n_pulados = 0
        n_outros = 0
        outros_regs: set[str] = set()
        for arq in candidatos:
            try:
                # Triagem por cabeçalho: modalidade e paciente saem dos primeiros
                # KB. Ler o arquivo inteiro aqui chegava a puxar centenas de MB
                # por RT Dose só para descobrir de quem ele era.
                dss = list(leitura.cabecalhos_arquivo(arq))
                if not dss:
                    continue
                # Só exclui se TODOS os membros forem das modalidades permitidas
                # (evita deletar pacote misto contendo algo que se deva manter).
                if not all(dicom_rt.identificar(d) in modalidades for d in dss):
                    continue
                regs = {_norm_registro(str(getattr(d, "PatientID", "") or ""))
                        for d in dss}
                if regs == {alvo}:
                    a_excluir.append(arq)
                else:
                    # Outro paciente (ou pacote misto): mantém e reporta.
                    n_outros += 1
                    outros_regs |= {r for r in regs if r and r != alvo}
            except Exception:  # noqa: BLE001
                n_pulados += 1
                continue

        erros: list[str] = []
        excluidos_ok: list[Path] = []
        for arq in a_excluir:
            try:
                arq.unlink()
                excluidos_ok.append(arq)
            except Exception as exc:  # noqa: BLE001
                erros.append(f"{arq.name}: {exc}")

        # Só remove diretórios que ficaram vazios por causa desta exclusão — uma
        # pasta vazia que já existia antes não é lixo nosso. A raiz nunca cai.
        raiz = Path(pasta).resolve()
        tocados: set[Path] = set()
        for arq in excluidos_ok:
            d = arq.resolve().parent
            while d != raiz and raiz in d.parents:
                tocados.add(d)
                d = d.parent
        for sub in sorted(tocados, key=lambda p: len(p.parts), reverse=True):
            try:
                sub.rmdir()   # falha se não estiver vazio — é o que queremos
            except OSError:
                pass

        excluidos = len(excluidos_ok)
        ressalvas = ""
        if n_outros:
            quem = (" (registro " + ", ".join(sorted(outros_regs)) + ")"
                    if outros_regs else "")
            ressalvas += (
                f"\n\n{n_outros} arquivo(s) de outro(s) paciente(s){quem} "
                "foram mantidos na pasta."
            )
        if n_pulados:
            ressalvas += (
                f"\n\n{n_pulados} arquivo(s) ilegível(is) não puderam ser "
                "identificados e foram mantidos na pasta."
            )
        if erros:
            ui.alertar(
                self, "Exclusão parcial",
                f"{excluidos} arquivo(s) DICOM excluído(s).\n\nErros:\n"
                + "\n".join(erros) + ressalvas,
            )
        elif ressalvas:
            ui.alertar(
                self, "Exclusão com ressalvas",
                f"{excluidos} arquivo(s) DICOM excluído(s) de '{Path(pasta).name}'."
                + ressalvas,
            )
        else:
            self.status.showMessage(
                f"{excluidos} arquivo(s) DICOM excluído(s) de '{Path(pasta).name}'."
            )

    def _ler_arquivos(self, caminhos: list[str]) -> list[bytes]:
        dados = []
        for p in caminhos:
            with open(p, "rb") as f:
                dados.append(f.read())
        return dados

    # ── Callbacks dos workers ────────────────────────────────────────────────

    def _tc_carregada(self, serie: ct_series.CTSerie, msg: str):
        self.caso.ct = serie
        self._atualizar_edicao_habilitada()
        self.status.showMessage(msg)
        self.controle_viewer.configurar_ct(serie)
        self.controle_viewer.atualizar_todos_cortes()
        # Recalcula SSDs com CT (mais preciso) se o plano já foi carregado
        self.controle_viewer.recalcular_ssds()

    def _plano_carregado(self, bundles: list, msg: str):
        self.caso.planos = [_montar_plano_app(b, i)
                        for i, b in enumerate(bundles, start=1)]
        self._atualizar_edicao_habilitada()
        self.status.showMessage(msg)
        if self.caso.planos:
            self.form.montar_abas(self.caso.planos)
            self.form.preencher({"RP": self.caso.planos[0]["rp"]})   # paciente/equipe globais
            # Agendamento com ≥2 planos; Soma só na mesma tomografia.
            self.caso.agendamento = None
            self.form.definir_multiplano(len(self.caso.planos) >= 2,
                                         self._planos_mesma_tc(),
                                         tem_plano=len(self.caso.planos) >= 1)
            self.controle_viewer.ativar_plano(0)
            # NADA de modal daqui para baixo: este método é o slot de
            # ``plano_pronto``, e o worker ainda está vivo. Qualquer ``exec_()``
            # aqui roda um laço de eventos aninhado, o ``finished`` já
            # enfileirado é entregue DENTRO dele, e o fim da carga acontece com
            # a pergunta ainda na tela — inclusive a prévia, que é um PDF
            # inteiro montado em cima do modal (ver
            # ``_perguntar_o_que_a_carga_deixou``). Aqui só se MARCA; quem
            # pergunta é o fim da carga.
            #
            # O agendamento entra na mesma fila: com ≥2 planos ele tem de abrir
            # logo em seguida — a soma de dose, o DVH e os cortes dependem do
            # modo escolhido nele, e sem isso o viewer fica em individual até
            # alguém lembrar do botão.
            self.caso.perguntas_pendentes = {"deslocamento", "medico", "doses_altas"}
            self.caso.agendamento_pendente = len(self.caso.planos) >= 2
            # Reavalia a Ficha Técnica (multi-plano exige agendamento completo).
            self._atualizar_btn_pdf()

    def _frame_uid_plano(self, p) -> str:
        """FrameOfReferenceUID (identidade da TC) de um plano, ou '' se ausente."""
        ds = p.get("rd_ds") or p.get("rs_ds")
        return dose3d.frame_uid(ds) if ds is not None else ""

    def _planos_mesma_tc(self, indices=None) -> bool:
        """True só se os planos indicados referenciam a MESMA tomografia.

        Sem ``indices``, checa todos. Um plano sem frame conhecido (só RP, sem
        RD/RS) impede confirmar a mesma TC → False (a soma exige certeza da
        geometria comum).
        """
        idx = range(len(self.caso.planos)) if indices is None else indices
        uids = set()
        for i in idx:
            fu = self._frame_uid_plano(self.caso.planos[i])
            if not fu:
                return False
            uids.add(fu)
        return len(uids) == 1

    def _dose_prescrita(self, indice: int) -> float:
        """Dose PRESCRITA (Gy) do plano — é o 100% da isodose.

        O valor do formulário tem prioridade sobre o do RT Plan: é o que o
        usuário conferiu e o que sai impresso na ficha. Zero quando não há
        prescrição, e aí o colorwash cai no máximo da grade.
        """
        if not (0 <= indice < len(self.caso.planos)):
            return 0.0
        val = None
        try:
            aba = self.form.abas.widget(indice)
            val = aba.rx_dose_total.value() if aba is not None else None
        except Exception:  # noqa: BLE001 — form ainda montando: usa o RT Plan
            val = None
        if not val:
            val = (self.caso.planos[indice].get("rp") or {}).get("dose_total")
        try:
            return float(val or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _dose_prescrita_total(self, indices) -> float:
        """100% da dose combinada: a maior prescrição ACUMULADA entre os planos.

        Somar as prescrições de TODOS só vale quando todos tratam a mesma região
        — fase → boost, que é exatamente o que os grupos de "Somar dose"
        declaram. Com mama e FSC (regiões vizinhas: a dose não se acumula no
        alvo, e o app até pergunta "somar ou separado?") o 100% ia para a soma
        das duas prescrições e a escala inteira caía pela metade: o ponto quente
        real, de 113% da prescrição, aparecia como 57%, e o colorwash da visão
        combinada saía menor que o de um plano só.

        Então: dentro de cada grupo as prescrições somam; entre grupos (e entre
        planos sem grupo) vale a MAIOR — é a dose que algum ponto do paciente de
        fato recebe.
        """
        dentro = [i for i in indices]
        grupos = (self.caso.agendamento or {}).get("grupos_dose") or []
        acumulado, agrupados = 0.0, set()
        for g in grupos:
            membros = [i for i in g if i in dentro]
            if len(membros) >= 2:
                agrupados.update(membros)
                acumulado = max(acumulado,
                                sum(self._dose_prescrita(i) for i in membros))
        for i in dentro:
            if i not in agrupados:
                acumulado = max(acumulado, self._dose_prescrita(i))
        return acumulado

    def _indices_ficha(self) -> list:
        """Índices dos planos que compõem a ficha.

        Por padrão, todos os carregados; com "Separar Ficha" (agendamento), só
        o subconjunto escolhido — os demais ficam de fora do documento e podem
        virar outra ficha depois.
        """
        n = len(self.caso.planos)
        sel = (self.caso.agendamento or {}).get("planos_separados")
        idx = sorted({i for i in (sel or [])
                      if isinstance(i, int) and 0 <= i < n})
        return idx or list(range(n))

    def _agendamento_da_ficha(self, pos: dict) -> dict | None:
        """Agendamento reescrito para os planos que ficaram na ficha.

        ``pos`` mapeia índice antigo → novo. Tudo que aponta para plano por
        índice (etapas, subconjunto do Personalizado, ordem das páginas) é
        remapeado, e os dias sem nenhum plano da ficha somem do mapa de frações.
        O registro precisa ficar coerente consigo mesmo: guardar os índices
        originais faria a ficha reaberta no Histórico apontar para planos que
        não estão lá.
        """
        ag_info = self.caso.agendamento
        if not ag_info or len(pos) == len(self.caso.planos):
            return ag_info          # sem separação: nada a reescrever
        etapas = []
        for et in (ag_info.get("etapas") or []):
            ps = [pos[i] for i in (et.get("planos") or []) if i in pos]
            if ps:
                etapas.append({"planos": ps, "fracoes": et.get("fracoes", 1)})
        rot = [self.caso.planos[i].get("rotulo", f"Plano {i + 1}")
               for i in sorted(pos, key=lambda k: pos[k])]
        novo = dict(ag_info)
        novo["etapas"] = etapas
        novo["planos_separados"] = None   # já aplicada: o novo conjunto é a ficha
        novo["planos_ficha"] = ([pos[i] for i in (ag_info.get("planos_ficha") or [])
                                 if i in pos] or None)
        novo["ordem_planos"] = [pos[i] for i in (ag_info.get("ordem_planos") or [])
                                if i in pos]
        # Grupos de soma de dose: só os planos que ficaram, e só onde ainda
        # sobram 2+ (com um plano só não há o que somar).
        novo["grupos_dose"] = [g for g in
                               ([pos[i] for i in grupo if i in pos]
                                for grupo in (ag_info.get("grupos_dose") or []))
                               if len(g) >= 2]
        novo["sequencia"] = ag.sequencia_de_etapas(etapas)
        novo["resumo"] = ag.resumo_etapas(etapas, rot)
        return novo

    def _avisar_deslocamento_vazio(self, dados: dict) -> None:
        """Avisa o usuário se os deslocamentos de setup (Delta Couch) estiverem ausentes no plano."""
        rp = dados.get("RP")
        if not rp:
            return
        # Só avisa quando o plano tem isocentro (ou seja, foi realmente carregado)
        # mas não tem nenhum dos três deslocamentos.
        if not rp.get("iso_pos_mm"):
            return
        desl_ausentes = all(rp.get(k) is None for k in ("desl_lat", "desl_long", "desl_vert"))
        if desl_ausentes:
            ui.alertar(
                self, "Deslocamento de setup não encontrado",
                "O RT Plan não contém os valores de Delta Couch Shift.",
                "O campo de deslocamento ficará vazio na ficha e o SSD TP0 "
                "será calculado usando o isocentro como ponto de referência.")

    def _avisar_medico_sem_aprovacao(self) -> None:
        """Explica o campo Médico vazio quando o plano não foi aprovado no TPS.

        No Monaco quem aprova é o médico, e o nome dele só existe no DICOM
        (``ReviewerName``) DEPOIS da aprovação: plano UNAPPROVED chega sem médico
        nenhum, e o campo ficava vazio sem dizer por quê — parecia falha do app.
        Só avisa quando as duas coisas valem: sem médico E sem aprovação.
        """
        if self.form.eq_medico.currentText().strip():
            return
        sem_aprovacao = [p for p in self.caso.planos
                         if str((p.get("rp") or {}).get("aprovacao", "")).upper()
                         == "UNAPPROVED"]
        if not sem_aprovacao:
            return
        quais = ", ".join(p.get("rotulo") or "plano" for p in sem_aprovacao)
        ui.alertar(
            self, "Plano não aprovado — sem médico responsável",
            f"O plano não está aprovado no TPS ({quais}).",
            "O nome do médico só vai para o DICOM quando ele APROVA o plano — "
            "por isso o campo veio vazio.\n\nAprove o plano no TPS e recarregue "
            "a pasta, ou escolha o médico na lista antes de gerar a ficha.")

    def _erro(self, origem: str, msg: str):
        self.status.showMessage(f"Erro ({origem}): {msg}")
        ui.falhar(self, f"Erro ao carregar {origem}", msg)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.controle_viewer.atualizar_todos_cortes()

    # ── Geração de PDF ───────────────────────────────────────────────────────

    def _atualizar_btn_pdf(self, *_) -> None:
        """Libera a Ficha Técnica só com paciente carregado E, no multi-plano,
        agendamento completo (todas as frações agendadas)."""
        tem_nome = bool(self.form.pac_nome.text().strip())
        self.btn_pdf.setEnabled(tem_nome and self.portao.agendamento_completo())

    def _escolher_ficha(self):
        """Pop-up do botão Impressão: Visualizar (prévia) ou Gerar PDF."""
        if not self.portao.confirmar_pendencias():
            return
        VER = "👁  Visualizar"
        PDF = "🖨  Gerar PDF"
        # VISUALIZAR primeiro, e é ele o padrão do Enter: conferir antes de
        # imprimir é a ordem que a trilha da Fichinha já impõe, e a primeira
        # opção de ``ui.escolher`` é a que o Enter aciona.
        alvo = ui.escolher(
            self, "Impressão",
            "O que deseja fazer com o documento (capa + ficha)?",
            [VER, PDF], cancelar="Cancelar", icone=QMessageBox.Question)
        if alvo == VER:
            self.controle_ficha.gerar_pdf(preview=True)
        elif alvo == PDF:
            self.controle_ficha.gerar_pdf(preview=False)

    def _abrir_pdf_previa(self, pdf_bytes: bytes, dados: dict,
                          abrir: bool = True) -> None:
        """Grava a prévia num arquivo temporário e (por padrão) abre no leitor.

        ``abrir=False`` só monta e guarda o caminho: é o modo Fichinha
        preparando a prévia junto com a ficha, para que o clique em Visualização
        seja instantâneo em vez de disparar a elaboração ali.
        """
        import tempfile
        nome = registro_json.slug_nome(dados)
        try:
            fd, caminho = tempfile.mkstemp(prefix=f"PREVIA_{nome}_", suffix=".pdf")
            with os.fdopen(fd, "wb") as f:
                f.write(pdf_bytes)
            # A prévia anterior deste caso não serve mais: apaga para não deixar
            # um rastro de PDFs no %TEMP% a cada remontagem.
            self._descartar_previa(exceto=caminho)
            self._previa_caminho = caminho
            # Só aqui a prévia existe de fato. O modo Fichinha usa esta marca
            # para liberar a Impressão: se a geração abortou antes (validação,
            # SUS cancelado, erro de render), nada foi conferido.
            self._previa_ok = True
            if abrir:
                os.startfile(caminho)
                self.status.showMessage(
                    "Pré-visualização aberta (arquivo temporário, não salvo).")
        except Exception as exc:  # noqa: BLE001
            ui.alertar(self, "Erro na pré-visualização", str(exc))

    def _descartar_previa(self, exceto: Optional[str] = None) -> None:
        """Esquece (e apaga) o PDF de prévia guardado, se houver."""
        caminho = getattr(self, "_previa_caminho", None)
        self._previa_caminho = None
        if not caminho or caminho == exceto:
            return
        try:
            os.remove(caminho)
        except OSError:
            pass   # aberto no leitor ou já removido — o %TEMP% resolve depois

    @contextlib.contextmanager
    def _aviso_progresso(self, mensagem: str):
        """Mostra um aviso modal enquanto um trabalho bloqueante roda na UI.

        A geração do PDF é síncrona na thread da interface, então a janela é
        pintada à força (``processEvents``) antes de o trabalho começar; durante
        o processamento ela fica estática, com o cursor de espera.

        No modo Fichinha não há modal: o Qt o centraliza na janela, que é
        exatamente onde está o cartão, e ele cobria os botões. A mensagem vai
        para a linha de status do próprio cartão — mesmo lugar de todo o resto
        que a tela tem a dizer — e os controles apagam no lugar do bloqueio
        visual que o modal fazia.
        """
        if self._stack.currentIndex() == 1:
            anterior = self.fichinha.lbl_status.text()
            self.fichinha.mostrar_status(mensagem)
            self.fichinha.bloquear(True)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            QApplication.processEvents()
            try:
                yield
            finally:
                QApplication.restoreOverrideCursor()
                self.fichinha.bloquear(False)
                # Devolve o texto anterior: quem chamou costuma escrever o
                # desfecho logo em seguida, e uma mensagem de "em andamento"
                # esquecida na tela seria pior do que nenhuma.
                self.fichinha.mostrar_status(anterior)
            return

        with ui.trabalhando(self, mensagem):
            yield

    def _abrir_configuracoes(self):
        """Configurações (Usuários/Equipe/Máquinas). Ao fechar, recarrega os
        combos de equipe (podem ter sido editados na aba Equipe)."""
        DialogConfiguracoes(self._usuario, self).exec()
        self.form.recarregar_equipe()

    def _autor(self) -> dict | None:
        """Autoria para a trilha de auditoria do registro (usuário logado)."""
        u = self._usuario or {}
        if not u.get("usuario"):
            return None
        import datetime
        return {"usuario": u.get("usuario"), "nome": u.get("nome", ""),
                "em": datetime.datetime.now().isoformat(timespec="seconds")}

    def _perguntar_o_que_a_carga_deixou(self) -> None:
        """Tudo o que a carga tem a perguntar, numa fila só e FORA do worker.

        Eram dois avisos e um diálogo disparados de dentro de
        ``_plano_carregado``, que é o slot de ``plano_pronto``. O ``exec_()`` de
        cada um roda um laço de eventos aninhado com o worker ainda vivo: o
        ``finished`` que já estava na fila era entregue ali dentro, e o fim da
        carga inteiro acontecia por baixo da pergunta aberta — a prévia é um PDF
        completo, e ela ainda abre o seu PRÓPRIO modal de progresso, que toma a
        modalidade do diálogo em cima do qual nasceu. Da cadeira, o programa
        travava: a janela do fracionamento na tela, parada, sem aceitar clique.
        Reclamado em 01/09/2026, no diálogo de dose alta — que é o mais pesado
        dos três, porque o hipofracionamento vem justamente nos casos com dose
        3D e DVH para renderizar.

        E o estrago não era só a espera. O fracionamento era perguntado ANTES de
        ``_agendamento_pendente`` ser marcado, então o fim da carga entregue
        dentro do modal via a marca ainda em falso: o agendamento não abria
        nunca, e a prévia saía com o fracionamento que o usuário ainda não
        tinha confirmado.

        A ordem daqui é a do trabalho: primeiro o que só informa (deslocamento
        ausente, plano sem médico), depois o fracionamento — que é quem define o
        dia de início de cada plano — e por último o agendamento, que usa esse
        dia como semente (ver ``_abrir_agendamento``).
        """
        # Zera ANTES de perguntar: cada diálogo roda o seu laço de eventos, e um
        # segundo ``_carga_terminou`` entregue lá dentro não pode repetir a fila.
        pendentes = self.caso.perguntas_pendentes if self.caso.planos else set()
        self.caso.perguntas_pendentes = set()
        if "deslocamento" in pendentes:
            self._avisar_deslocamento_vazio({"RP": self.caso.planos[0]["rp"]})
        if "medico" in pendentes:
            self._avisar_medico_sem_aprovacao()
        if "doses_altas" in pendentes:
            # A prescrição aprovada ANTES do pop-up: o que ela já diz não se
            # pergunta. Só o registro vai na consulta — o curso do ARIA não
            # chega até aqui (o DICOM não o traz), e sem ele vale a regra de
            # prescrição única de ``tratamento_db.fracionamento_prescrito``.
            freq = self.form.aplicar_fracionamento_prescrito(
                self.form.pac_registro.text().strip())
            if freq:
                self.status.showMessage(
                    f"Fracionamento da prescrição aprovada: {freq}.", 8000)
            self.form.perguntar_doses_altas()
        self._abrir_agendamento_pendente()

    def _abrir_agendamento_pendente(self) -> None:
        """Abre o agendamento que a carga multi-plano deixou marcado.

        Fora do slot de ``plano_pronto``, e por isso só quando a carga inteira
        terminou. Chamado de lá de dentro, o ``exec_()`` do diálogo rodava um
        laço de eventos com o worker ainda vivo: o ``finished`` já enfileirado
        era entregue DENTRO do modal, e a Fichinha montava a prévia (um PDF
        inteiro, reentrante, sob o modal aberto) com o agendamento ainda vazio.

        Já se tentou também adiar com ``QTimer.singleShot(0, …)`` para o diálogo
        não subir sobre a janela em branco: não resolve nada disto — o disparo
        de tempo zero cai no primeiro laço de eventos que aparecer, que é
        exatamente o do modal. O que resolve é esperar o fim da carga.
        """
        if not self.caso.agendamento_pendente:
            return
        self.caso.agendamento_pendente = False
        self._abrir_agendamento()
        # Cancelar o diálogo deixa o multi-plano sem agendamento: a Ficha
        # Técnica volta a travar, e quem diz isso é este reexame.
        self._atualizar_btn_pdf()

    def _abrir_agendamento(self, _checked=False, *, suave=False):
        """Configura como os planos entram nas frações (aparece na página 3).

        Com ≥2 planos, arruma quais planos entram em cada dia; com 1 plano, serve
        só para o Replanejamento (frações já tratadas). ``suave``: abre com
        fade-in (usado quando o diálogo reabre logo após reordenar as abas)."""
        if not self.caso.planos:
            return
        dados_planos = self.form.coletar_planos()
        planos_info = []
        plano_dias = []       # {"fracoes","dia_inicio","fracionamento"} p/ o seed
        usar_dias = False
        for i, p in enumerate(self.caso.planos):
            dpi = dados_planos[i] if i < len(dados_planos) else {}
            nfr = int((dpi.get("rx_fracoes")) or 0)
            if not nfr:
                nfr = int(p["rp"].get("num_fracoes") or 0)
            frac = str(dpi.get("fracionamento", ""))
            aba = self.form.abas.widget(i)
            dia_ini = int(getattr(aba, "_dia_inicio", 1) or 1) if aba else 1
            if "alter" in frac.lower() or dia_ini > 1:
                usar_dias = True   # fracionamento ou dia de início pedem interligar
            plano_dias.append({"fracoes": nfr, "dia_inicio": dia_ini,
                               "fracionamento": frac})
            planos_info.append({"rotulo": p.get("rotulo", f"Plano {i + 1}"),
                                "num_fracoes": nfr,
                                "frame_uid": self._frame_uid_plano(p)})
        # "Dias alter." ou dia de início > 1 → agendamento interligado por dia
        # (dose alta em dias alternados, planos escalonados). Senão, sequencial.
        seed = (ag.colapsar_dias(ag.montar_por_dia_inicio(plano_dias))
                if usar_dias else None)
        dlg = DialogAgendamento(planos_info, self.caso.agendamento,
                                mesma_tc=self._planos_mesma_tc(),
                                seed_etapas=seed, fade_in=suave, parent=self)
        # Antes de aplicar: a soma de dose já foi decidida alguma vez? (A chave
        # só falta no primeiro agendamento — depois ela existe, mesmo vazia.)
        perguntar_dose = "grupos_dose" not in (self.caso.agendamento or {})
        if dlg.exec() == QDialog.Accepted:
            self.caso.agendamento = dlg.resultado()
            self._perguntar_soma_dose(perguntar_dose)
            # Liga/desliga a visão SOMA (dose combinada) conforme o modo escolhido.
            self.controle_viewer.recalcular_soma()
            self._atualizar_btn_pdf()   # libera a ficha só se agendou tudo
            # "Agendamento não montado" era a pendência: some agora, não só na
            # próxima vez que a Fichinha for reaberta. E a prévia guardada saiu
            # sem o mapa da pág. 3 — não serve mais.
            self._descartar_previa()
            if self._estado_fichinha_tem_ficha():
                self._fichinha_conferir()
            self.status.showMessage(
                f"Agendamento: {self.caso.agendamento.get('resumo', '')}  "
                f"({len(self.caso.agendamento['sequencia'])} frações no mapa).")

    def _perguntar_soma_dose(self, perguntar: bool) -> None:
        """Com DOIS planos sequenciais, pergunta uma única vez se a dose soma.

        Fase → boost na mesma região costumam ter dose acumulada contínua no
        mapa (pág. 3); planos de regiões diferentes, não. Com dois planos a
        resposta é sim/não; com três ou mais é preciso dizer O QUE soma COM O
        QUE, e aí quem responde é o menu "Somar dose" do agendamento.
        """
        ag_info = self.caso.agendamento or {}
        if not perguntar or ag_info.get("grupos_dose"):
            return
        seq = ag_info.get("sequencia") or []
        if len(self.caso.planos) != 2 or not seq:
            return
        if any(len(dia) > 1 for dia in seq):
            return          # concomitantes: cada plano tem a sua própria dose
        rot = [p.get("rotulo", f"Plano {i + 1}") for i, p in enumerate(self.caso.planos)]
        if ui.confirmar(
                self, "Soma de dose",
                f"“{rot[0]}” e “{rot[1]}” são tratados em sequência.",
                acao="Somar a dose", recusa="Acumular separado",
                detalhe=("Somar: o 2º plano continua o acumulado do 1º (mesma "
                         "região).\nSeparado: cada plano acumula a sua própria "
                         "dose.\n\nDá para mudar depois no menu “Somar dose” "
                         "do agendamento.")):
            self.caso.agendamento["grupos_dose"] = [[0, 1]]

    def _abrir_edicao(self):
        """Abre o editor consolidado do PLANO ATIVO (troque a aba para editar outro)."""
        dados_form = self.form.coletar()
        rp = self.caso.dados.get("RP", {}) or {}
        reg_orig = (dados_form.get("pac_registro") or "").strip()
        rotulo = ""
        if self.caso.planos and 0 <= self.caso.plano_ativo < len(self.caso.planos):
            n = len(self.caso.planos)
            rot = self.caso.planos[self.caso.plano_ativo].get("rotulo", "")
            if n > 1:
                rotulo = f"Plano {self.caso.plano_ativo + 1}/{n}: {rot}"
        dlg = DialogEdicaoFicha(dados_form, rp, self, rotulo=rotulo)
        if dlg.exec() != QDialog.Accepted:
            return
        form_edits, rp_edits = dlg.resultado()

        # O histórico versionado é indexado pelo registro; alterá-lo cria um
        # arquivo JSON separado começando em v1. Confirma antes de aplicar.
        novo_reg = (form_edits.get("pac_registro") or "").strip()
        if reg_orig and novo_reg and novo_reg != reg_orig:
            resp = ui.confirmar(
                self, "Alterar registro do paciente?",
                f"O registro mudou de '{reg_orig}' para '{novo_reg}'.",
                acao="Aplicar o novo registro",
                recusa=f"Manter '{reg_orig}'",
                detalhe=("O histórico é indexado pelo registro: com um novo "
                         "registro, um arquivo JSON separado será criado "
                         "(começando em v1), e o histórico anterior permanece "
                         "sob o registro antigo."),
                # O registro é a CHAVE do histórico: trocá-lo separa o paciente
                # em dois na busca, e ninguém percebe pelo resultado. O Enter
                # tem de recair sobre manter.
                perigo=True)
            if not resp:
                form_edits["pac_registro"] = reg_orig

        self.form.aplicar(form_edits)
        self.caso.dados["RP"] = rp_edits
        # Multi-plano: propaga a edição para o plano ativo (a geração lê dele).
        if self.caso.planos and 0 <= self.caso.plano_ativo < len(self.caso.planos):
            self.caso.planos[self.caso.plano_ativo]["rp"] = rp_edits
        historico.registrar("ficha_editada", detalhes={
            "paciente": form_edits.get("pac_nome", ""),
            "registro": form_edits.get("pac_registro", "")})
        self.status.showMessage("Edições aplicadas ao plano ativo. Gere a ficha para salvar.")

    def _abrir_busca(self):
        """Abre o diálogo de busca global de pacientes (índice central)."""
        DialogBuscaPacientes(self).exec()

    def carregar_registro(self, dados: dict, rp: dict, pasta: str = "",
                          imagem_path: str = "", dvh_path: str = "",
                          render: dict | None = None,
                          planos: list | None = None,
                          imagens_paths: list | None = None,
                          dvhs_paths: list | None = None,
                          agendamento: dict | None = None,
                          tmp_extraido: str | None = None,
                          drrs_paths: list | None = None,
                          drrs_titulos: list | None = None):
        """Popula o programa com um tratamento salvo (JSON), sem DICOM.

        Chamado pela tela de Histórico ao "Carregar Ficha". Descarta os dados
        atuais e restaura o formulário. Se ``planos`` (multi-plano) for dado,
        reconstrói TODOS os planos e suas abas; senão restaura um plano único.
        TC/estruturas não voltam (podem ter sido apagadas).
        """
        self._executar_limpeza()
        # Assume a posse do temp JÁ (a limpeza acima zerou o anterior): se algo
        # abaixo falhar, o temp fica rastreado e será limpo na próxima limpeza.
        self.caso.tmp_extraido = tmp_extraido

        if planos:
            # Restaura todos os planos (sem DICOM): rp/relação por plano.
            self.caso.planos = []
            for i, pd in enumerate(planos, start=1):
                self.caso.planos.append({
                    "rp": pd.get("plano_rp", {}) or {},
                    "rs_ds": None, "rd_ds": None, "ct": None,
                    "rotulo": pd.get("rotulo") or f"Plano {i}",
                    "prescricao": {}, "protocolo": {},
                })
            self.form.montar_abas(self.caso.planos)   # silencioso (não re-pergunta dose)
            # Globais + aba ativa (0) exatos; demais abas no laço.
            self.form.aplicar(planos[0].get("dados", {}) or {})
            for i in range(1, len(planos)):
                aba = self.form.abas.widget(i)
                if aba is not None:
                    aba.aplicar(planos[i].get("dados", {}) or {})
            self.caso.plano_ativo = 0
            self.caso.dados["RP"] = self.caso.planos[0]["rp"]
            self.caso.agendamento = agendamento
            self.form.definir_multiplano(len(self.caso.planos) >= 2, False,
                                         tem_plano=len(self.caso.planos) >= 1)
        else:
            self.form.aplicar(dados or {})
            self.caso.dados["RP"] = rp or {}
            self.caso.agendamento = agendamento   # guarda replan p/ reimprimir igual

        # SUS lembrado do registro reaberto (pré-preenche o popup ao regerar).
        _dsus = (planos[0].get("dados", {}) if planos else (dados or {})) or {}
        self.caso.sus = {"pac_sus": bool(_dsus.get("pac_sus")),
                     "numero_sus": str(_dsus.get("numero_sus", "") or "")}

        self.caso.pasta_carregada = pasta or None
        self.caso.registro_carregado = {"imagem_path": imagem_path or "",
                                    "dvh_path": dvh_path or "",
                                    "drrs_paths": drrs_paths or [],
                                    "drrs_titulos": drrs_titulos or [],
                                    "render": render or {},
                                    "imagens_paths": imagens_paths or [],
                                    "dvhs_paths": dvhs_paths or []}
        self.btn_edicao.setEnabled(True)
        self.btn_limpar.setEnabled(True)
        self._atualizar_edicao_habilitada()   # ficha reaberta: campos vivos
        self._atualizar_btn_pdf()   # multi-plano exige agendamento completo
        nome = (dados or {}).get("pac_nome", "")
        extra = f" · {len(planos)} planos" if planos else ""
        self.status.showMessage(
            f"Tratamento carregado: {nome}{extra} — TC/estruturas não incluídas. "
            "Ajuste em Edição Ficha e gere para versionar."
        )


def _pasta_tem_dicom(pasta: str) -> bool:
    """True se a pasta tem arquivos para elaborar uma ficha NOVA (DICOM).

    Mesmo critério de extensões que o ``_CarregarTudo`` (``.dcm``/``.zip``/
    ``.rar``), mas EXCLUINDO o próprio arquivo da ficha do paciente
    (``ARQUIVOS_*.zip``, que guarda JSON/PNGs, não DICOM). Sem isso, uma pasta
    só com a ficha salva era tratada como se tivesse TC e o app oferecia
    "elaborar nova" — que não tinha o que ler. Curto-circuita no 1º achado.
    """
    try:
        for p in Path(pasta).rglob("*"):
            if not p.is_file():
                continue
            suf = p.suffix.lower()
            if suf == ".dcm":
                return True
            if suf in (".zip", ".rar") and not p.name.upper().startswith("ARQUIVOS_"):
                return True
    except OSError:
        pass
    return False


# ── O que era @staticmethod da janela ─────────────────────────────────────
# Saíram da classe em 16/09/2026 (R-06, corte 1): nunca foram dela — não leem
# nem gravam nada da janela. Os da visualização foram com ela para o
# ``controle_viewer.py`` (corte 6b), e os da ficha para o ``controle_ficha.py``
# (corte 6c).


def _dentro_de(pasta: str, raiz: str) -> bool:
    try:
        a = os.path.normcase(os.path.abspath(pasta))
        r = os.path.normcase(os.path.abspath(raiz))
        return os.path.commonpath([a, r]) == r
    except ValueError:   # unidades diferentes: não está dentro
        return False


def _montar_plano_app(bundle: dict, indice: int) -> dict:
    """Cria o plano no nível do app a partir de um bundle do carregador.

    Prescrição herda os valores do RP (editáveis depois); protocolo e
    relação (simultâneo/sequencial) recebem defaults por plano.
    """
    rp = bundle.get("rp") or {}
    return {
        "rp": rp,
        # O DATASET do plano, e não só o ``rp`` já interpretado: é dele que
        # sai o nome INTEIRO do portal na folha do 600CD (ver
        # ``dicom_rt.rotulo_drr_setup``). Sem ele, o nome volta a ser o
        # rótulo de dezesseis caracteres do RT Image, que corta.
        "rp_ds": bundle.get("rp_ds"),
        "rs_ds": bundle.get("rs_ds"),
        "rd_ds": bundle.get("rd_ds"),
        "ct": bundle.get("ct"),
        "drrs_setup": bundle.get("drrs_setup") or [],
        "rp_raw": bundle.get("rp_raw"),
        "rotulo": bundle.get("rotulo") or f"Plano {indice}",
        "prescricao": {
            "dose_total":   rp.get("dose_total"),
            "dose_fracao":  rp.get("dose_fracao"),
            "num_fracoes":  rp.get("num_fracoes"),
            "fracionamento": "",
        },
        "protocolo": {"imagem": "", "frequencia": "", "gating": "Não",
                      "gating_modalidade": "", "gating_fase": ""},
        "relacao": {"tipo": "simultaneo", "fase": indice, "ordem": indice},
    }







# O diálogo de edição mora em ``edicao_ficha.py`` desde 27/08/2026 — mesmo
# motivo do ``administracao.py``. Reimportado AQUI porque ``gui.DialogEdicaoFicha``
# é o endereço que a suíte já usa.
from isocentro.interface.edicao_ficha import (  # noqa: E402,F401
    DialogEdicaoFicha, _RealceObservacoes, _TravaDuploClique)


# O diálogo de agendamento mora em ``agendamento_tela.py`` desde 27/08/2026 —
# mesmo motivo do ``administracao.py``. Reimportado AQUI porque
# ``gui.DialogAgendamento`` é o endereço que a suíte já usa em 18 lugares.
from isocentro.interface.agendamento_tela import (  # noqa: E402,F401
    DialogAgendamento, DialogSepararFicha, _ChipPlano)


# A aparência mora em ``aparencia.py`` desde 27/08/2026 — mesmo motivo do
# ``administracao.py`` logo abaixo. Reimportada AQUI porque ``gui.aplicar_modo``
# e ``gui._ESTILO`` são o endereço que o resto do programa e a suíte já usam.
from isocentro.interface.aparencia import (  # noqa: E402,F401
    _ESTILO, _icone_app, _paleta_dark, _titlebar_escura, aplicar_modo)


# As telas de administração e acesso moram em ``administracao.py`` desde
# 25/08/2026 (ver o cabeçalho de lá). Reimportadas AQUI porque ``gui.DialogLogin``
# e companhia são o endereço que o resto do programa e a suíte já usam — mudar
# o endereço junto com o arquivo seria duas mudanças de uma vez.
from isocentro.interface.administracao import (  # noqa: E402,F401
    DialogConfiguracoes, DialogHistorico, DialogLogin, DialogTrocarSenha,
    PainelEquipe, PainelMaquinas, PainelServico, PainelUsuarios, _ListaNomes)

