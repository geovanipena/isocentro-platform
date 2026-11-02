"""Tela **Fichinha**: cinco listas, e o caso nasce de uma linha.

O modo Ficha Total é a bancada — formulário, cortes, 3D, agendamento — e é onde
o caso difícil se resolve. Mas a maioria dos casos não é difícil: é pegar o
paciente que a automação já preparou e imprimir. Para esses, a bancada inteira é
atrito. Esta tela é o mesmo motor com a superfície reduzida ao que o fluxo
simples precisa.

**A v8 (23/09/2026) trocou a forma da tela**, depois de o usuário rodar a v8.0
com banco e recusar: *"não quero botões visíveis… mais moderno, mais elegante e
extremamente funcional"*. O que saiu e o que entrou:

* **saiu o cartão central** — título, campo do caminho, botão ⚡ ISOCENTRO
  e a trilha 2×2. Apontar pasta à mão saiu desta tela; o que restou dele é a
  faixa de status do topo, que só existe enquanto há caso em elaboração;
* **entraram cinco cartões** (``_Bloco``): Documentação disponível na coluna
  larga, "Suas últimas fichas", Histórico e Altas Prontas empilhados à direita,
  e Datas Relevantes atravessando a base;
* **a ação virou ícone no hover da LINHA** (``_Linha``), e não mais uma fileira
  de botões por bloco — cinco fileiras faziam a tela ler como painel de
  controle. De quebra, a ação de linha responde "agir sobre quem?" sem a pessoa
  ter de conferir qual linha está marcada antes de clicar.

**A trilha agora são três ícones da linha de Documentação**, na ordem pedida:

    👁 Visualizar · ✏ Editar · 🖨 Imprimir

**Visualizar e Editar acendem com a linha**, mesmo sem ficha montada: os dois
montam o caso quando ele ainda não está montado, e o que muda é onde ele é
entregue — na prévia ou na bancada. Montar leva segundos e acontece noutra
thread, então o destino viaja na entrada (``apos``) e quem o cumpre é a janela,
no fim da carga.

**A Impressão espera a Visualização** — a única regra da trilha que não se
negocia —, e espera a visualização DESTA linha: imprimir com o caso anterior
montado sairia com o nome do paciente novo na tela e o documento do antigo na
bandeja. Por isso editar depois de ver **apaga** a visualização: o que foi
conferido deixou de ser o que sairia impresso.

**Editar abre a bancada**: desde 08/09/2026 a Ficha Total saiu da faixa de abas
e virou o destino desse ícone — a tela se transforma nela. A bancada não é uma
aba concorrente desta; é o lugar para onde se vai quando o caso não fecha aqui,
e voltar é um clique em "Fichinha". A Total também tem aba na faixa.

Os outros quatro blocos: **suas últimas fichas** (as do usuário logado) responde
de graça "já fiz este paciente hoje?"; **Histórico** são as dez últimas do
serviço inteiro, com a lupa do cabeçalho abrindo a busca no índice; **Altas
Prontas** lista as altas a imprimir, com seleção múltipla e chip por unidade; e
**Datas Relevantes** é o calendário do serviço, criado à mão.

Este módulo é só a superfície. Quem carrega DICOM, monta e gera o PDF continua
sendo a ``JanelaPrincipal``; aqui só saem sinais e entram estados.
"""
from __future__ import annotations

import datetime
import os
from typing import Iterable, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import (QBoxLayout, QFrame,
                             QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QPushButton, QScrollArea, QVBoxLayout, QWidget)

from isocentro.interface.ajustes import ajustes
from isocentro.dominio import constantes
from isocentro.dominio import gatilho_registro
from isocentro.interface import estilo as st
from isocentro.interface import ui

# Estados da trilha. Strings em vez de Enum porque só este módulo os lê, e o
# nome legível ajuda mais no depurador do que um inteiro.
INICIAL = "inicial"
CARREGANDO = "carregando"
PRONTA = "pronta"
VISTA = "vista"

# Escala tipográfica da tela — fonte única, para acertar o conjunto num lugar
# só. Ela é maior que a da bancada de propósito: a Ficha Total é um formulário
# denso, lido sentado e de perto; esta tela é lida de longe, muitas vezes de pé,
# e tem espaço de sobra para gastar em legibilidade. Mexer aqui reescala tudo.
FONTE_TITULO = 25
FONTE_SECAO = 19     # "Suas últimas fichas" — abre um bloco, não é rodapé
FONTE_CAMPO = 17     # o que se digita e o botão que dispara
FONTE_CORPO = 16     # status, avisos, trilha, nomes da lista
FONTE_MIUDA = 14     # apoio: registro, data, dica, ações da lista
FONTE_ETIQUETA = 12  # a legenda do bloco e o rodapé — leitura de canto de olho
FONTE_ICONE = 22     # os símbolos de ação que aparecem no hover da linha

# Lado do ícone de ação. Subiu de 26 para 30 em 23/09/2026, com o usuário
# vendo a tela rodando: "os ícones ao lado dos nomes devem ser maiores, mais
# vivos". Cabe porque a linha cresce junto — o que não cabe é ícone que se
# procura.
_ICONE = 34

# Altura de TODO botão grande da tela — o ISOCENTRO e os quatro da trilha.
# Igual de propósito: são todos alvos da mesma mão, clicados na mesma sequência,
# e alturas diferentes faziam a fileira de cima parecer de outra tela. O que
# distingue o ISOCENTRO é a cor e o brilho, não o tamanho.
_ALT_BOTAO = 52

# Altura reservada para a faixa de ações da lista de recentes. Fixa e declarada
# aqui em vez de medida: a faixa aparece e some conforme a seleção, e o espaço
# dela tem de existir nos dois casos — é isso que impede o bloco de saltar a
# cada clique. Cabe um botão de ``_ESTILO_ACAO`` (fonte ``FONTE_MIUDA`` mais
# 6 pt de folga em cima e embaixo) com um respiro.
_ALT_FAIXA_ACOES = 36

# Largura mínima de UM bloco para ele ainda valer a pena lado a lado. Abaixo
# disso a linha inteira passa a empilhar (ver ``_ajustar_faixa``).
#
# Herda a medida da v7, onde o limiar era 1.100 para DUAS listas — 550 por
# lista. Com três blocos na linha de cima, 550 exigiria 1.650 px de janela, e
# numa estação de 1.366 os três empilhariam: a tela nova ficaria PIOR que a
# antiga justamente na largura mais comum da clínica. 420 põe os três lado a
# lado em 1.366 e os dois de baixo em 840.
#
# É a medida que mais pede conferência desenhada: o corte real acontece quando
# o nome do paciente deixa de caber, e isso depende da fonte da estação. NÃO
# confundir com o que se vê num ``grab()`` sem ``show()`` — ali o
# ``_RotuloElidido`` corta com a largura que tinha ANTES de o layout esticar, e
# o mesmo "Fulano de ..." aparece igual em qualquer janela (medido em
# 02/09/2026). É artefato da conferência offscreen, não falta de espaço.
_LARG_MIN_COLUNA = 420

# Altura do rodapé do quadro de Documentação: UMA linha de ``FONTE_MIUDA``.
# Fixa para o rótulo poder alternar entre vazio e uma linha sem a lista pular,
# e pequena porque é só isso que mora ali.
_ALT_RODAPE_DOC = 22

# Teto da caixa de conferência. Ela cresce com o conteúdo e some quando não há
# nada — uma moldura vazia reservada "por via das dúvidas" é o tipo de peso que
# esta tela existe para não ter.
_ALT_MAX_AVISOS = 132

# Quantas fichas recentes cabem na lista de baixo. Dez é o que se lembra de ter
# feito: acima disso a lista vira consulta, e consulta é o Histórico.
MAX_RECENTES = 10

# Ações oferecidas sobre uma ficha já escolhida, na ordem em que aparecem — as
# MESMAS da tela de Histórico, e nenhuma a mais. Houve aqui um "Refazer" (montar
# de novo a partir dos DICOM) que saiu: na pasta com ficha anterior ele abria a
# pergunta "reabrir ou elaborar nova?", que é a pergunta que o próprio botão já
# tinha respondido — e, quando os DICOM já tinham sido apagados (o que o app
# oferece depois de gerar), virava o Carregar por um caminho mais longo. Quem
# quer recomeçar do DICOM aponta a pasta no campo acima, que é a tela inteira.
CARREGAR = "carregar"
VERSOES = "versoes"
PDF = "pdf"
PASTA = "pasta"

_ACOES: tuple[tuple[str, str, str], ...] = (
    (CARREGAR, "📥",
     "Carregar: traz o caso inteiro de volta para a bancada — formulário, "
     "cortes e agendamento — a partir do registro salvo."),
    (VERSOES, "🕓",
     "Versões: compara as versões desta ficha e mostra o que mudou entre elas."),
    (PDF, "📄",
     "PDF: abre a ficha como ela foi impressa. Se o arquivo sumiu, é regerado "
     "a partir do registro."),
    (PASTA, "📂",
     "Pasta: abre a pasta do paciente no Explorador de Arquivos."),
)

# ── A trilha, que na v8 mora na faixa da Documentação disponível ────────────
#
# Ela deixou de ser a grade 2×2 do cartão e virou a faixa de ações DESTA lista,
# porque é de uma linha dela que o caso agora nasce: escolher o paciente e
# montar a ficha deixaram de ser dois gestos em lugares diferentes da tela.
#
# A ordem é a da trilha, e foi pedida assim: Editar ENTRE Visualizar e
# Imprimir.
VISUALIZAR = "visualizar"
EDITAR = "editar"
IMPRIMIR = "imprimir"

_ACOES_DOC: tuple[tuple[str, str, str], ...] = (
    (VISUALIZAR, "👁️",
     "Visualizar: monta a ficha técnica com os arquivos da pasta preparada e "
     "abre a visualização."),
    (EDITAR, "✏️",
     "Editar: abre a bancada (Ficha Total) — formulário completo, "
     "agendamento, cortes e 3D."),
    (IMPRIMIR, "🖨️",
     "Imprimir a ficha que você acabou de conferir."),
)

# A dica de cada ícone pela chave, para quem precisa VOLTAR ao texto padrão
# depois de tê-lo trocado — é o caso da Impressão, que vira liberação quando o
# caso veio da pasta temporária (ver ``_dica_da_impressao``).
_DICAS_DOC = {chave: dica for chave, _simbolo, dica in _ACOES_DOC}

# ── Altas Prontas ───────────────────────────────────────────────────────────
ABRIR_ALTA = "abrir_alta"
PASTA_ALTA = "pasta_alta"

_ACOES_ALTAS: tuple[tuple[str, str, str], ...] = (
    (ABRIR_ALTA, "📄",
     "Abre o Relatório de Alta gravado na pasta do paciente. Com vários "
     "escolhidos, abre todos."),
    (PASTA_ALTA, "📂",
     "Abre a pasta do paciente no Explorador de Arquivos."),
)

# Quantas altas dá para abrir de uma vez sem perguntar. Acima disto o programa
# confirma: cada PDF abre um leitor, e quarenta leitores de uma vez é a estação
# parada por minutos — sem que nada na tela diga que foi o clique que fez isso.
MAX_ALTAS_SEM_PERGUNTAR = 10

# A quinta ação do bloco Histórico, e a única que não age sobre uma ficha
# escolhida: abre a tela de busca no índice central. Ela existe porque o botão
# «Histórico» da trilha sumiu com o cartão, e com ele o único caminho até
# aquela tela — dez linhas respondem "o que saiu hoje", não "ache o caso de
# março".
BUSCAR = "buscar"

# ── Datas Relevantes ────────────────────────────────────────────────────────
#
# Os tipos, na ordem em que aparecem no filtro. Lista fechada de propósito: com
# tipo livre, o mesmo assunto vira "Serviço", "serviço" e "SERVIÇO" em três
# estações, e o filtro deixa de filtrar.
TIPO_PESSOAL = "Pessoais"
TIPO_SERVICO = "Serviço"
TIPO_COMEMORATIVA = "Comemorativas"
TIPOS_DE_DATA = (TIPO_PESSOAL, TIPO_SERVICO, TIPO_COMEMORATIVA)

NOVA_DATA = "nova_data"
EDITAR_DATA = "editar_data"
EXCLUIR_DATA = "excluir_data"

_ACOES_DATAS: tuple[tuple[str, str, str], ...] = (
    (EDITAR_DATA, "✏️", "Altera este evento."),
    (EXCLUIR_DATA, "🗑️", "Apaga este evento do quadro do serviço."),
)

# O «+» do cabeçalho das Datas e a lupa do Histórico: ações do BLOCO, que não
# agem sobre linha nenhuma e por isso não cabiam no hover de uma linha.
ICONE_NOVA = "➕"
# O ícone do cabeçalho das Altas: abre TODAS as marcadas de uma vez.
ICONE_ABRIR_TODAS = "🖨️"
ICONE_BUSCAR = "🔍"

# Quantas fichas do SERVIÇO inteiro aparecem no bloco Histórico. O mesmo dez de
# ``MAX_RECENTES``, e pela mesma razão: dez é o que se lembra de ter visto
# passar. Quem procura um caso de março usa a busca, que é outra tela.
MAX_HISTORICO = 10

# Teto de altura das listas dos blocos. Cinco listas numa tela só: sem teto, a
# mais cheia empurra as outras para fora do campo de visão, e a rolagem da
# página inteira passa a ser o único jeito de ver a de baixo.
_ALT_MAX_LISTA = 400

# Quantas linhas a lista reserva mesmo vazia. Não é espaço "por via das
# dúvidas": é o que impede o bloco de nascer como uma tira de uma linha e
# depois pular de tamanho quando a primeira resposta do banco chega — e as
# cinco chegam em momentos diferentes, então a tela dançaria por alguns
# segundos a cada abertura.
#
# UMA, e não quatro (09/10/2026, em dois passos): com quatro, os três blocos da
# coluna da direita mais as Datas passavam da altura útil de uma tela de
# 1366×768, e as Altas e as Datas sumiam para baixo da dobra. Com dois ainda
# sobravam ~20 px de Datas cortados na tela do usuário (1536×864 lógicos, a
# janela maximizada dá ~755 px à Fichinha; os mínimos somavam ~776). É só o
# PISO: havendo altura, o peso do layout estica cada lista, e a que tiver mais
# linhas que o espaço rola por dentro — ver ``_Bloco.ajustar_altura``.
_LINHAS_MINIMAS = 1

# Estilo das ações da lista: contorno, não preenchimento. Elas agem sobre um
# documento que JÁ SAIU; os verdes cheios continuam sendo os da trilha, que é o
# trabalho de agora. Mesmo verde, peso menor — hierarquia sem cor nova.
def _estilo_acao() -> str:
    return (
        "QPushButton{"
        "  background:transparent;"
        f" color:{st.ACAO}; font-size:{FONTE_MIUDA}px; font-weight:600;"
        f" border:1px solid {st.ACAO_LINHA}; border-radius:6px;"
        "  padding:6px 10px; }"
        f"QPushButton:hover{{ background:{st.ACAO_FUNDO}; color:{st.ACAO};"
        f" border-color:{st.ACAO}; }}"
        f"QPushButton:pressed{{ background:{st.ACAO}; color:{st.SOBRE_ACAO}; }}"
        f"QPushButton:disabled{{ background:transparent;"
        f" color:{st.TEXTO_APAGADO}; border-color:{st.BORDA}; }}"
    )


# O filtro por tipo das Datas Relevantes. NÃO usa a cor de ação: ele não age
# sobre nada — só esconde e mostra —, e um botão verde ao lado dos verdes que
# fazem coisas ensinaria que os dois pesos significam a mesma coisa. O marcado
# se distingue pelo fundo, não por matiz nova.
def _estilo_filtro() -> str:
    return (
        "QPushButton{"
        "  background:transparent;"
        f" color:{st.TEXTO_FRACO}; font-size:{FONTE_MIUDA}px;"
        f" border:1px solid {st.BORDA}; border-radius:10px;"
        # Folga LATERAL maior que a de cima e de baixo: com 10 px o "T" de
        # "Todas" encostava na borda arredondada e lia-se "odas".
        "  padding:4px 16px; }"
        f"QPushButton:hover{{ color:{st.TEXTO}; border-color:{st.AZUL}; }}"
        f"QPushButton:checked{{ background:{st.AZUL_FUNDO}; color:{st.TEXTO};"
        f" border-color:{st.AZUL}; }}"
    )


def _quando(iso: str) -> str:
    """A data como se fala: "hoje 14:32", "ontem 09:15", "08/08 16:40".

    Data absoluta em toda linha faz a lista parecer um log; o que a pessoa quer
    saber é a distância até hoje. A data cheia continua no tooltip.
    """
    try:
        t = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    hoje = datetime.date.today()
    dias = (hoje - t.date()).days
    if dias == 0:
        return f"hoje {t:%H:%M}"
    if dias == 1:
        return f"ontem {t:%H:%M}"
    if t.year == hoje.year:
        return f"{t:%d/%m %H:%M}"
    return f"{t:%d/%m/%Y}"


def _data_hora(iso) -> str:
    """"11/09 14:02" de um carimbo ISO; vazio se não houver carimbo legível."""
    try:
        return datetime.datetime.fromisoformat(str(iso)).strftime("%d/%m %H:%M")
    except (TypeError, ValueError):
        return ""


def _data_curta(iso: str) -> str:
    """"12/10" de uma data ISO. Data ilegível devolve o que veio, não vazio.

    Devolver vazio esconderia que alguém gravou um evento com data estranha, e
    o cartão apareceria sem data nenhuma como se não tivesse sido preenchido.
    """
    try:
        return datetime.date.fromisoformat(str(iso)).strftime("%d/%m")
    except (TypeError, ValueError):
        return str(iso or "")


def _data_br(iso: str) -> str:
    """ISO → "03/10/2026", para o campo do diálogo. Vazio continua vazio."""
    try:
        return datetime.date.fromisoformat(str(iso)).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return ""


def _data_iso(texto: str) -> str:
    """"03/10/2026" → ISO. Devolve vazio quando não dá para entender.

    Vazio é o sinal de recusa, e quem chama PERGUNTA de novo em vez de gravar:
    uma data que não vira ISO ficaria para sempre no fim da lista (a ordenação
    manda o ilegível para o fim), e ninguém entenderia por quê.
    """
    texto = (texto or "").strip()
    for formato in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return ""


def _dias_ate(iso: str) -> Optional[int]:
    """Quantos dias faltam para a data (negativo = já passou).

    ``None`` quando a data não é legível — e quem usa isto pinta de cor neutra
    nesse caso, em vez de escolher entre "vencido" e "futuro" no escuro.
    """
    try:
        return (datetime.date.fromisoformat(str(iso))
                - datetime.date.today()).days
    except (TypeError, ValueError):
        return None


def _primeiro_nome(nome) -> str:
    """"Ana Fatima Albuquerque (AC)" → "Ana". Vazio vira "(sem responsável)".

    Só para o RESPONSÁVEL da linha, nunca para o paciente: o dono está ali para
    responder "tem alguma minha?", e para isso o primeiro nome basta. O nome
    inteiro continua a um passe de mouse, no tooltip da linha.

    **Primeiro nome e não as iniciais**, que o ``FullName`` já traz entre
    parênteses — e foi medido, não escolhido: nos 50 responsáveis cadastrados
    (relatórios do ARIA de 22/09/2026) há **48 primeiros nomes distintos e só
    45 conjuntos de iniciais**. As iniciais colidem em cinco pares — "MH" é o
    Mauricio Henrique e o Mario Hayashi, "RC" é a Renata Carneiro e o Ronaldo
    Castilho —, e uma sigla que aponta duas pessoas responde errado justamente a
    pergunta que a coluna existe para responder. O primeiro nome repete em dois
    pares (duas Nathalia, duas Thais), e aí o tooltip desempata.
    """
    return str(nome or "").split()[0] if str(nome or "").strip() \
        else "(sem responsável)"


class _RotuloElidido(QLabel):
    """Rótulo que termina em "…" quando não cabe, em vez de sumir na borda.

    O nome do paciente é o dado mais largo da linha e o mais variável.
    Cortado à força, "CLEUDIMAR NUNES DE MOURA BRITO" virava "…MOURA BRIT" sem
    marca nenhuma de que continuava — lia-se como se fosse o nome inteiro, que
    num documento de identificação é o erro que não pode acontecer.

    A fonte é posta no WIDGET, não na folha de estilo: o Qt mede com a fonte do
    widget e pinta com a da folha, então declarar o tamanho só no estilo faria
    a conta do "cabe?" sair com uma fonte e o texto aparecer com outra.
    """

    def __init__(self, texto: str = "", parent=None):
        super().__init__(parent)
        self._inteiro = texto or ""
        self.setMinimumWidth(1)   # senão o layout reserva o nome inteiro
        super().setText(self._inteiro)

    def setText(self, texto: str) -> None:  # noqa: N802 - assinatura do Qt
        self._inteiro = texto or ""
        self._reduzir()

    def resizeEvent(self, e):  # noqa: N802 - assinatura do Qt
        super().resizeEvent(e)
        self._reduzir()

    def _reduzir(self) -> None:
        largura = max(0, self.width() - 2)
        super().setText(QFontMetrics(self.font()).elidedText(
            self._inteiro, Qt.ElideRight, largura) if largura else self._inteiro)


def _botao_icone(simbolo: str, dica: str,
                 maior: bool = False) -> QPushButton:
    """Um ícone clicável, sem cara de botão.

    Sem moldura, sem preenchimento e sem cor de ação em repouso: ele só existe
    enquanto o cursor está sobre a linha, e uma fileira de botões desenhados
    dentro de cada linha de lista seria mais pesada que a faixa de botões que
    a v8.1 saiu para eliminar. A moldura aparece no hover do próprio ícone, que
    é quando ela responde a uma pergunta ("é aqui que eu clico?").
    """
    b = QPushButton(simbolo)
    b.setCursor(Qt.PointingHandCursor)
    b.setToolTip(dica)
    b.setFixedSize(_ICONE, _ICONE)
    corpo = FONTE_ICONE + (3 if maior else 0)
    b.setFocusPolicy(Qt.NoFocus)
    # O ícone é EMOJI, e emoji colorido ignora ``color`` — a fonte de emoji
    # desenha a própria paleta. Então o que o dá presença é o TAMANHO e o
    # realce do fundo no hover, não a tinta. A cor fica declarada mesmo assim
    # para o dia em que um símbolo monocromático entrar na lista.
    st.pintar(b, lambda: (
        "QPushButton{background:transparent; border:none; border-radius:8px;"
        f" color:{st.ACAO}; font-size:{corpo}px; padding:0;}}"
        f"QPushButton:hover{{background:{st.ACAO_FUNDO};}}"
        f"QPushButton:disabled{{color:{st.TEXTO_APAGADO};}}"))
    return b


class _Linha(QWidget):
    """Uma linha de lista com as ações escondidas até o cursor chegar.

    **Por que as ações moram aqui e não numa faixa embaixo da lista.** Até a
    v8.0 cada bloco tinha uma fileira de botões, e cinco blocos viraram cinco
    fileiras: a tela lia como um painel de controle, e o usuário recusou em
    23/09/2026 ("não quero botões visíveis"). A ação agora pertence à LINHA, o
    que também responde "agir sobre quem?" sem a pessoa ter de conferir qual
    linha está marcada antes de clicar.

    **O clique no meio da linha sobe sozinho; o do ícone para no ícone.** O
    clique no texto tem de chegar ao ``QListWidget`` (é ele quem seleciona), e
    chega: rótulo e container não tratam mouse, e o Qt devolve o evento
    ignorado ao pai até o ``viewport`` da lista. O botão trata, e para nele.

    **NÃO usar ``WA_TransparentForMouseEvents`` no container.** Foi o que se
    fez até 07/10/2026, e matava os ícones em silêncio: o Qt, ao procurar o
    widget sob o cursor, PULA a subárvore inteira de um widget transparente —
    os botões inclusive, mesmo sem o atributo. O clique no ícone caía na lista
    e só selecionava; o duplo clique virava Visualizar. Da cadeira: "todos os
    botões em documentação somente abrem a prévia". Travado por
    ``tests/test_fichinha_icones.py``.
    """

    def __init__(self, dados: dict, parent=None):
        super().__init__(parent)
        self.dados = dados or {}
        self._lay = QHBoxLayout(self)
        # A folga vertical acompanha o ÍCONE, não o texto: com 6 px a linha
        # ficava com 31 px de altura e o botão de 34 era espremido pelo layout
        # — o emoji saía menor que o do cabeçalho, que tem a mesma fonte
        # (visto no print de 23/09/2026).
        self._lay.setContentsMargins(10, 4, 8, 4)
        self._lay.setSpacing(10)
        self.setMinimumHeight(_ICONE + 8)
        # A zona de ações entra sempre, mesmo vazia, e é a ÚLTIMA coisa da
        # linha. Altura fixa e largura reservada: aparecer e sumir não pode
        # reflowar o texto da linha debaixo do cursor — o nome do paciente
        # encolheria no instante em que a pessoa mira o ícone.
        self.acoes = QWidget()
        # ``setFixedWidth`` NÃO basta: o Qt tira do layout o widget escondido,
        # e a largura reservada só valia quando a fileira já estava à vista.
        # Medido em 23/09/2026 — o nome do paciente ia de 123 px para 1 px no
        # instante em que o cursor chegava na linha, que é exatamente o
        # reflow que este bloco existe para impedir.
        _pol = self.acoes.sizePolicy()
        _pol.setRetainSizeWhenHidden(True)
        self.acoes.setSizePolicy(_pol)
        self._lay_acoes = QHBoxLayout(self.acoes)
        self._lay_acoes.setContentsMargins(0, 0, 0, 0)
        self._lay_acoes.setSpacing(2)
        self.acoes.hide()
        self._botoes: dict = {}

    def coluna(self, widget, peso: int = 0) -> None:
        """Acrescenta uma coluna ANTES da zona de ações."""
        self._lay.insertWidget(self._lay.count(), widget, peso)

    def fechar(self) -> None:
        """Põe a zona de ações no fim. Chamar depois da última coluna."""
        self._lay.addWidget(self.acoes)

    def definir_acoes(self, acoes, ao_clicar) -> None:
        """``acoes`` são triplas ``(chave, símbolo, dica)``."""
        for chave, simbolo, dica in acoes:
            b = _botao_icone(simbolo, dica)
            b.clicked.connect(
                lambda _c=False, k=chave: ao_clicar(k, self.dados))
            self._botoes[chave] = b
            self._lay_acoes.addWidget(b)
        # Reserva a largura da fileira mesmo escondida, pelo mesmo motivo da
        # faixa de altura fixa da v8.0: o que muda de tamanho sob o cursor
        # arrasta o que a pessoa estava mirando.
        self.acoes.setFixedWidth(max(1, len(acoes) * (_ICONE + 2)))

    def mostrar_acoes(self, mostrar: bool) -> None:
        self.acoes.setVisible(bool(mostrar) and bool(self._botoes))

    def enterEvent(self, ev):  # noqa: N802 — assinatura do Qt
        """O cursor entrou na linha: avisa a lista, como o hover dela avisaria.

        Com a linha recebendo o mouse (ver o docstring da classe), o
        movimento sobre ela não chega mais ao ``viewport`` — e o
        ``itemEntered`` da lista, que é quem mostra os ícones e acende os
        certos, ficava mudo: os ícones nunca apareciam. Reemitir o MESMO sinal
        mantém um caminho só para o hover, venha o cursor de onde vier.
        """
        super().enterEvent(ev)
        lista = self.parentWidget()
        while lista is not None and not isinstance(lista, QListWidget):
            lista = lista.parentWidget()
        if lista is None:
            return
        for i in range(lista.count()):
            item = lista.item(i)
            if lista.itemWidget(item) is self:
                lista.itemEntered.emit(item)
                return

    def acender(self, possiveis) -> None:
        for chave, botao in self._botoes.items():
            botao.setEnabled(chave in possiveis)

    def definir_dica(self, chave: str, texto: str) -> None:
        """Troca a dica de UM ícone — a fixa de ``_ACOES_DOC`` não serve sempre.

        A Impressão é o caso: com o caso vindo da pasta temporária ela passa a
        ser a liberação, e apagada precisa dizer por quê. Com rótulo isso ia no
        texto do botão; com ícone, o tooltip é o único canal.
        """
        botao = self._botoes.get(chave)
        if botao is not None:
            botao.setToolTip(texto or "")


class _Bloco(QWidget):
    """Um cartão da tela: fundo próprio, sem borda, sem fileira de botões.

    Nasceu na v8, quando a tela passou de dois quadros para cinco — os dois que
    existiam tinham o mesmo desenho escrito duas vezes, com as diferenças que
    ninguém pediu. Foi redesenhado na v8.1, depois de o usuário ver a tela
    rodando na clínica: saem a moldura (linha de contorno em cinco caixas
    empilhadas desenha uma grade, e a grade é o que fazia a tela parecer um
    formulário) e a faixa de botões, que virou ação de linha.

    O título vira etiqueta: miúdo, em versal, alinhado à esquerda e na cor mais
    fraca da paleta. Ele não é conteúdo — é a legenda do que está embaixo —, e
    o teal grande e centrado da v8.0 pesava mais que os nomes dos pacientes.
    """

    def __init__(self, titulo: str, parent=None):
        super().__init__(parent)
        # ``WA_StyledBackground`` + ``objectName``: sem os dois, a folha de
        # estilo de um QWidget nu não pinta fundo nenhum, e o cartão sai
        # invisível — sem erro nenhum na tela.
        self.setObjectName("cartao")
        self.setAttribute(Qt.WA_StyledBackground, True)
        st.pintar(self, lambda: (
            f"#cartao{{background:{st.FUNDO_BLOCO}; border-radius:14px;}}"))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 10)
        lay.setSpacing(8)

        cab = QHBoxLayout()
        cab.setSpacing(8)
        self.titulo = QLabel(titulo.upper())
        st.pintar(self.titulo, lambda: (
            f"font-size:{FONTE_ETIQUETA}px; font-weight:bold;"
            f" letter-spacing:1.2px; color:{st.TEXTO_APAGADO};"))
        self.cracha = QLabel("")
        st.pintar(self.cracha, lambda: (
            f"font-size:{FONTE_ETIQUETA}px; font-weight:bold;"
            f" color:{st.ACAO};"))
        self.cracha.hide()
        cab.addWidget(self.titulo)
        cab.addWidget(self.cracha)
        cab.addStretch(1)
        # As ações do BLOCO (o «+» das Datas, a lupa do Histórico) ficam aqui,
        # no canto do cabeçalho: elas não agem sobre linha nenhuma, então não
        # podiam ir para o hover da linha, e uma fileira embaixo da lista é
        # justamente o que saiu.
        self._lay_cab_acoes = QHBoxLayout()
        self._lay_cab_acoes.setContentsMargins(0, 0, 0, 0)
        self._lay_cab_acoes.setSpacing(2)
        cab.addLayout(self._lay_cab_acoes)
        lay.addLayout(cab)

        # Entre o cabeçalho e a lista, para quem precisar (o filtro por tipo
        # das Datas). Vazio não ocupa altura: é um layout sem itens, e não uma
        # faixa reservada.
        self._acima = QVBoxLayout()
        self._acima.setContentsMargins(0, 0, 0, 0)
        self._acima.setSpacing(4)
        lay.addLayout(self._acima)

        self.lista = QListWidget()
        self.lista.setFocusPolicy(Qt.NoFocus)
        self.lista.setWordWrap(True)   # o convite do estado vazio é longo
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista.setMouseTracking(True)   # sem isto não há hover de linha
        self.lista.setFrameShape(QFrame.NoFrame)
        st.pintar(self.lista, lambda: (
            # Transparente sobre o cartão: a lista não é uma caixa dentro de
            # outra caixa, é o conteúdo do cartão.
            "QListWidget{background:transparent; border:none; padding:0;"
            f" font-size:{FONTE_MIUDA}px;}}"
            "QListWidget::item{border-radius:7px; padding:0;}"
            f"QListWidget::item:hover{{background:{st.FUNDO_CAMPO};}}"
            f"QListWidget::item:selected{{background:{st.ACAO_FUNDO};}}"
            "QScrollBar:vertical{background:transparent; width:6px; margin:0;}"
            f"QScrollBar::handle:vertical{{background:{st.BORDA};"
            "  border-radius:3px; min-height:24px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{"
            "  height:0; border:none;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{"
            "  background:transparent;}"))
        lay.addWidget(self.lista, 1)

        self.rodape = _RotuloElidido("")
        st.pintar(self.rodape, lambda: (
            f"font-size:{FONTE_ETIQUETA}px; color:{st.TEXTO_APAGADO};"))
        lay.addWidget(self.rodape)

    # ── Montagem ─────────────────────────────────────────────────────────

    def acao_de_bloco(self, simbolo: str, dica: str, ao_clicar) -> QPushButton:
        """Um ícone no canto do cabeçalho (ver o comentário lá em cima).

        Desenhado um ponto maior que os da linha: o da linha aparece dentro de
        uma faixa destacada e com o cursor já em cima dele, este fica parado
        num canto e precisa ser ACHADO.
        """
        b = _botao_icone(simbolo, dica, maior=True)
        b.clicked.connect(lambda _c=False: ao_clicar())
        self._lay_cab_acoes.addWidget(b)
        return b

    def acima_da_lista(self, widget) -> None:
        self._acima.addWidget(widget)

    def definir_cracha(self, texto: str) -> None:
        self.cracha.setText(texto or "")
        self.cracha.setVisible(bool(texto))

    def definir_rodape(self, texto: str) -> None:
        self.rodape.setText(texto or "")
        self.rodape.setVisible(bool(texto))

    # ── Hover ────────────────────────────────────────────────────────────

    def linha_sob_o_cursor(self, item) -> None:
        """Mostra as ações da linha apontada e esconde as das outras.

        Percorrer a lista inteira a cada movimento parece caro e não é: são no
        máximo dez linhas, e o alternativo — guardar a última e apagar só ela —
        deixa ações acesas para sempre quando a lista é redesenhada com o
        cursor parado em cima dela.
        """
        alvo = self.lista.itemWidget(item) if item is not None else None
        for i in range(self.lista.count()):
            w = self.lista.itemWidget(self.lista.item(i))
            if isinstance(w, _Linha):
                w.mostrar_acoes(w is alvo)

    def ajustar_altura(self, maximo: int = 0) -> None:
        """Mínimo colado ao conteúdo; o resto é a janela que decide.

        Na v7 isto era ``setFixedHeight``, certo para duas listas no rodapé de
        um cartão. Com cinco blocos ocupando a tela, o mesmo cálculo dava uma
        tira de uma linha em cada um e 500 px de vazio embaixo — medido na
        primeira conferência desenhada da v8.
        """
        # O mínimo é FIXO, e não o número de linhas: com ele acompanhando a
        # lista ("todas, até dez"), Suas últimas fichas e Histórico cheios
        # exigiam mais de 1.000 px só os dois, e as Altas Prontas e as Datas
        # Relevantes iam para baixo da dobra — numa tela de 1366×768 elas não
        # apareciam sem rolar a página, e o relato foi "a Fichinha não tem
        # Altas Prontas nem Datas Relevantes" (09/10/2026). Com o mínimo fixo a
        # lista cheia rola por dentro e os cinco blocos cabem; havendo altura,
        # o peso do layout estica cada um.
        n = self.lista.count()
        linha = self.lista.sizeHintForRow(0) if n else 0
        self.lista.setMinimumHeight(_LINHAS_MINIMAS * (linha or 32) + 8)


class PainelFichinha(QWidget):
    """A tela simplificada. Emite pedidos; a janela principal os executa."""

    gerar = Signal(str)      # caminho da pasta do paciente
    fechar_caso = Signal(str)  # o × do campo: este caso não é mais o meu
                                   # (leva o estado de onde a trilha estava)
    abrir_historico = Signal()
    abrir_edicao = Signal()
    pedir_visualizacao = Signal()
    pedir_impressao = Signal()
    # Ação pedida sobre uma ficha da lista de recentes: (ação, ficha). Um sinal
    # só, com o nome da ação, em vez de cinco — quem trata é sempre o mesmo
    # método da janela, e cinco fios até ele seriam cinco chances de esquecer um.
    acao_recente = Signal(str, dict)
    # Clique numa Documentação ``● PRONTA``: leva a entrada inteira, com a
    # ``automacao`` (a pasta do curso na temporária e a instância) e, na v8, a
    # chave ``apos`` — o passo que a janela deve dar quando a carga terminar
    # ("visualizar" ou "editar"). Ver ``_pedir_acao_doc``.
    abrir_documentacao = Signal(dict)
    # Ação sobre um evento do quadro de Datas Relevantes: (ação, evento). O
    # evento vem vazio no "Nova", que é o único que não age sobre um existente.
    acao_data = Signal(str, dict)
    # Ação sobre as Altas Prontas: (ação, lista de entradas). LISTA, e não uma
    # entrada: abrir várias de uma vez é o pedido, e um sinal por paciente
    # faria a janela perguntar N vezes o que ela precisa perguntar uma só.
    acao_alta = Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._estado = INICIAL
        # Trabalho bloqueante em curso (ver ``bloquear``). Separado do estado
        # porque é transitório: ao terminar, a trilha volta exatamente para
        # onde estava, sem passar por CARREGANDO.
        self._travado = False
        # O PDF de prévia chegou a ser elaborado? Separado do estado porque a
        # ficha pode estar montada e a prévia NÃO — o caso multi-plano sem
        # agendamento é exatamente isso (ver ``definir_previa``).
        self._previa = False
        # Caso aberto da pasta TEMPORÁRIA: ``None`` é a Impressão de sempre;
        # dict é a liberação (ver ``definir_liberacao``).
        self._liberacao = None
        # A pasta do caso que está na tela. Era o texto do campo até a v7; com
        # o campo fora, é a janela que põe e tira (``definir_caminho``), e esta
        # é a única memória dele.
        self._caminho = ""
        # De qual pasta é a ficha que está montada. Guardado para reconhecer
        # quando o caso da tela passa a ser OUTRO.
        self._caminho_ficha = ""
        # Há fichas na lista de baixo? (a faixa de ações só faz sentido se sim)
        self._tem_recentes = False
        # O quadro de Datas INTEIRO, antes do filtro por tipo: trocar de tipo
        # redesenha daqui, sem reler o arquivo do serviço.
        self._datas = []
        self._settings = ajustes()

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)

        # Rolagem: são CINCO blocos, e num monitor de 768 px a linha de baixo
        # ficaria fora da tela sem aviso nenhum — e um bloco que não existe não
        # se procura. Quando cabe, a barra não aparece e nada muda.
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # A barra vem clara do sistema e, sobre este fundo, é a coisa mais
        # brilhante da tela — mais que o botão que se quer clicar. Aqui ela é
        # só um traço, e some quando não há o que rolar.
        st.pintar(rolagem, lambda: (
            "QScrollArea{background:transparent; border:none;}"
            "QScrollArea > QWidget > QWidget{background:transparent;}"
            "QScrollBar:vertical{background:transparent; width:8px; margin:0;}"
            f"QScrollBar::handle:vertical{{background:{st.BORDA};"
            "  border-radius:4px; min-height:28px;}"
            f"QScrollBar::handle:vertical:hover{{background:{st.AZUL};}}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{"
            "  height:0; border:none;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{"
            "  background:transparent;}"))
        interno = QWidget()
        rolagem.setWidget(interno)
        raiz.addWidget(rolagem)
        fora = QVBoxLayout(interno)
        fora.setContentsMargins(12, 10, 12, 10)
        fora.setSpacing(6)

        # ── A faixa do caso em elaboração ────────────────────────────────
        #
        # O cartão que saiu na v8 levava junto o único lugar onde o status da
        # ficha e as pendências apareciam. Eles não pertencem a bloco nenhum —
        # falam do caso que está sendo montado AGORA, não de uma lista —, então
        # moram numa faixa larga no topo.
        #
        # Ela só existe enquanto há o que dizer: sem caso aberto, a tela é só
        # as listas. Aparecer e sumir empurra o resto para baixo, o que aqui é
        # aceitável porque só acontece quando a pessoa está olhando exatamente
        # para o que apareceu — diferente das faixas de ação dentro dos blocos,
        # que saltariam sob o cursor que acabou de clicar.
        self._faixa_caso = QWidget()
        lay_caso = QVBoxLayout(self._faixa_caso)
        lay_caso.setContentsMargins(0, 0, 0, 4)
        lay_caso.setSpacing(6)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self._status_erro = False
        self._pintar_status()
        st.ao_trocar(self._pintar_status)
        lay_caso.addWidget(self.lbl_status)

        # Pendências e alertas do caso montado.
        self.lista = QListWidget()
        self.lista.setFocusPolicy(Qt.NoFocus)
        self.lista.setSelectionMode(QListWidget.NoSelection)
        self.lista.setWordWrap(True)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        st.pintar(self.lista, lambda: (
            f"QListWidget{{background:{st.FUNDO_FUNDO};"
            f" border:1px solid {st.BORDA}; border-radius:8px;"
            f" padding:6px; font-size:{FONTE_CORPO}px; }}"
            "QListWidget::item{padding:3px 4px;}"))
        self.lista.hide()
        lay_caso.addWidget(self.lista)

        self._faixa_caso.hide()
        fora.addWidget(self._faixa_caso)

        # ── Os cinco cartões ─────────────────────────────────────────────
        #
        # A Documentação ocupa a COLUNA LARGA da esquerda, e as outras três
        # empilham estreitas à direita — decisão do usuário em 23/09/2026,
        # olhando a tela rodando na clínica. O peso segue o uso: a Documentação
        # chega com dez linhas todo dia e é de onde o caso nasce; "Suas
        # últimas" e "Histórico" costumam ter poucas, e Altas quase sempre
        # nenhuma. Três colunas iguais davam à lista cheia o mesmo espaço das
        # vazias.
        #
        # As Datas Relevantes atravessam a base: elas não têm nada a ver com o
        # caso que está sendo montado — são o calendário do serviço —, e na
        # base ficam à vista sem disputar o olho com a coluna de trabalho.
        self.b_doc = _Bloco("Documentação disponível")
        self.b_recentes = _Bloco("Suas últimas fichas")
        self.b_historico = _Bloco("Histórico")
        self.b_altas = _Bloco("Altas Prontas")
        self.b_datas = _Bloco("Datas Relevantes")

        self._coluna_direita = QVBoxLayout()
        self._coluna_direita.setContentsMargins(0, 0, 0, 0)
        self._coluna_direita.setSpacing(10)
        for _b in (self.b_recentes, self.b_historico, self.b_altas):
            self._coluna_direita.addWidget(_b, 1)

        self._meio = QHBoxLayout()
        self._meio.setContentsMargins(0, 0, 0, 0)
        self._meio.setSpacing(10)
        self._meio.addWidget(self.b_doc, 5)
        self._meio.addLayout(self._coluna_direita, 4)
        fora.addLayout(self._meio, 5)
        fora.addWidget(self.b_datas, 2)

        # ── Documentação disponível: a lista de onde o caso nasce ────────
        #
        # O quadro do SERVIÇO, não o de quem está logado: foi assim que se
        # pediu, e é o que dispensa casar o login do app com o recurso do ARIA
        # — o DW não guarda login, e o casamento teria de ser por nome.
        #
        # A seleção entrou na v8. Até a v7 o clique numa linha ``● PRONTA``
        # DISPARAVA a carga na hora; agora ele escolhe, e quem carrega é o
        # ``▷`` que aparece sobre a linha. Foi pedido assim, e tem um ganho que
        # não estava no pedido: clicar na linha errada deixou de montar a ficha
        # do paciente errado.
        self.atividades = self.b_doc.lista
        self.atividades.setSelectionMode(QListWidget.SingleSelection)
        self.atividades.itemEntered.connect(self._hover_doc)
        self.lbl_doc_rodape = self.b_doc.rodape
        self._recado_doc = ""

        # ── Suas últimas fichas ──────────────────────────────────────────
        self.recentes = self.b_recentes.lista
        self.recentes.setSelectionMode(QListWidget.SingleSelection)
        self.recentes.itemEntered.connect(self.b_recentes.linha_sob_o_cursor)
        # Contador do dia: o número que a pessoa procura no fim do plantão, e
        # que sozinho já justifica olhar para cá.
        self.lbl_hoje = self.b_recentes.cracha

        # ── Histórico: as últimas do SERVIÇO inteiro ─────────────────────
        #
        # Era um botão da trilha que abria outra tela; virou lista na v8. As
        # duas listas vizinhas respondem perguntas diferentes e por isso não se
        # fundem: uma é "o que EU fiz", esta é "o que saiu aqui". Num plantão
        # com três pessoas, a segunda não se deduz da primeira.
        self.historico = self.b_historico.lista
        self.historico.setSelectionMode(QListWidget.SingleSelection)
        self.historico.itemEntered.connect(self.b_historico.linha_sob_o_cursor)
        self.b_historico.acao_de_bloco(
            ICONE_BUSCAR, "Buscar no índice central, com todas as fichas do "
                          "serviço.", self.abrir_historico.emit)

        # ── Altas Prontas ────────────────────────────────────────────────
        #
        # Seleção MÚLTIPLA, que é o pedido: escolher vários pacientes e abrir
        # todas as altas de uma vez. É a única lista em que o ícone da linha
        # age sobre a SELEÇÃO e não só sobre a linha apontada — ver
        # ``_pedir_acao_alta``.
        self.altas = self.b_altas.lista
        self.altas.setSelectionMode(QListWidget.ExtendedSelection)
        self.altas.itemEntered.connect(self.b_altas.linha_sob_o_cursor)
        # Marcar por UNIDADE: o físico escolhe "CEL" e leva as doze de uma vez
        # para a impressora (pedido de 23/09/2026). Os chips são montados a
        # cada leitura, com as unidades que REALMENTE têm alta — um chip "BET"
        # que nunca tem nada é um alvo que ensina a não clicar.
        self._chips_unidade = {}
        self._faixa_unidades = QWidget()
        self._lay_unidades = QHBoxLayout(self._faixa_unidades)
        self._lay_unidades.setContentsMargins(0, 0, 0, 0)
        self._lay_unidades.setSpacing(2)
        self._lay_unidades.addStretch(1)
        self.b_altas.acima_da_lista(self._faixa_unidades)
        self._faixa_unidades.hide()
        # E o ícone que ABRE o que está marcado. Mora no cabeçalho porque age
        # sobre a seleção inteira, não sobre a linha que está sob o cursor.
        self._btn_abrir_altas = self.b_altas.acao_de_bloco(
            ICONE_ABRIR_TODAS, "Abrir as altas marcadas.",
            lambda: self._pedir_acao_alta(ABRIR_ALTA, {}))
        self._btn_abrir_altas.hide()

        # ── Datas Relevantes ─────────────────────────────────────────────
        #
        # Uma lista só, ordenada por data, com a etiqueta do tipo em cada
        # cartão e um filtro por tipo em cima — decisão do usuário, contra as
        # colunas de trello.
        self.datas = self.b_datas.lista
        self.datas.setSelectionMode(QListWidget.SingleSelection)
        self.datas.itemEntered.connect(self.b_datas.linha_sob_o_cursor)
        self.b_datas.acao_de_bloco(
            ICONE_NOVA, "Novo evento no quadro do serviço.",
            lambda: self._pedir_acao_data(NOVA_DATA, {}))
        self._filtro_datas = ""
        self._btns_filtro = {}
        _filtro = QWidget()
        _lay_filtro = QHBoxLayout(_filtro)
        _lay_filtro.setContentsMargins(0, 0, 0, 0)
        _lay_filtro.setSpacing(2)
        for _chave, _rotulo in (("", "Todas"),) + tuple(
                (t, t) for t in TIPOS_DE_DATA):
            _b = QPushButton(_rotulo)
            _b.setCheckable(True)
            _b.setCursor(Qt.PointingHandCursor)
            _b.setFocusPolicy(Qt.NoFocus)
            _b.setChecked(_chave == "")
            st.pintar(_b, _estilo_filtro)
            _b.clicked.connect(
                lambda _c=False, k=_chave: self._filtrar_datas(k))
            self._btns_filtro[_chave] = _b
            _lay_filtro.addWidget(_b)
        _lay_filtro.addStretch(1)
        self.b_datas.acima_da_lista(_filtro)

        # Conexões
        self.recentes.itemSelectionChanged.connect(self._selecao_mudou)
        # Duplo clique = Carregar, como na tela de Histórico: o mesmo gesto no
        # mesmo tipo de lista tem de fazer a mesma coisa nos dois lugares.
        # O duplo clique leva a ENTRADA junto, como o ícone leva: desde a v8.1
        # os pedidos recebem ``(ação, dados)``, e o lambda de um argumento só
        # que havia aqui estourava DENTRO de um slot do Qt — que não propaga
        # exceção, derruba o processo com exit 127 e nenhum traceback.
        self.recentes.itemDoubleClicked.connect(
            lambda i: self._pedir_acao(CARREGAR, self._entrada(i) or {}))
        self.historico.itemSelectionChanged.connect(self._selecao_mudou)
        self.historico.itemDoubleClicked.connect(
            lambda i: self._pedir_acao_historico(CARREGAR,
                                                 self._entrada(i) or {}))
        self.atividades.itemSelectionChanged.connect(self._selecao_mudou)
        # Duplo clique na Documentação = Visualizar, que é o primeiro passo da
        # trilha — o mesmo espírito do duplo clique das outras listas: o gesto
        # faz a ação mais provável, não uma quarta coisa.
        self.atividades.itemDoubleClicked.connect(
            lambda i: self._pedir_acao_doc(VISUALIZAR, self._entrada(i) or {}))
        self.datas.itemSelectionChanged.connect(self._selecao_mudou)
        self.datas.itemDoubleClicked.connect(
            lambda i: self._pedir_acao_data(EDITAR_DATA,
                                            self._entrada(i) or {}))
        self.altas.itemSelectionChanged.connect(self._selecao_mudou)
        self.altas.itemDoubleClicked.connect(
            lambda i: self._pedir_acao_alta(ABRIR_ALTA, self._entrada(i) or {}))

        self.definir_estado(INICIAL)
        self.definir_recentes([])   # estado vazio já na primeira abertura
        self.definir_historico([])
        self.definir_datas([])
        # "Consultando", e não vazio: a resposta do banco leva um instante, e
        # uma lista vazia nesse instante já é uma AFIRMAÇÃO — a de que não há
        # documentação a fazer. Essa é a leitura errada mais cara desta tela.
        self.definir_atividades(None, "Consultando o sistema…")
        self.definir_altas(None, "Consultando o sistema…")

    # ── API usada pela janela principal ──────────────────────────────────

    def caminho(self) -> str:
        """A pasta do caso que está na tela.

        Era o texto do campo até a v7; na v8 o campo não existe e isto é
        memória, não widget. A janela continua perguntando e respondendo pelos
        mesmos dois métodos — é o que manteve o ``gui.py`` inteiro de pé numa
        troca que apagou o cartão.
        """
        return (self._caminho or "").strip().strip('"')

    def definir_caminho(self, caminho: str) -> None:
        self._caminho = caminho or ""
        self._atualizar_botoes()

    def mostrar_status(self, msg: str, erro: bool = False) -> None:
        # Guarda o TIPO da mensagem, não a cor: a folha é remontada a cada
        # troca de dia↔noite, e um vermelho de modo claro sobre fundo escuro
        # some. Ver ``_pintar_status``.
        self._status_erro = bool(erro)
        self._pintar_status()
        self.lbl_status.setText(msg or "")
        self.lbl_status.setVisible(bool(msg))
        self._ajustar_faixa_caso()

    def _ajustar_faixa_caso(self) -> None:
        """A faixa do topo só existe quando tem o que dizer.

        Sem isto ela ficaria como uma tira vazia acima dos blocos o tempo todo
        — e esta tela não reserva espaço vazio. Ela pode empurrar as listas
        para baixo ao aparecer, e aqui isso é aceitável: quem a faz aparecer é
        o próprio trabalho da pessoa, que está olhando para ela nesse instante.
        """
        self._faixa_caso.setVisible(bool(self.lbl_status.text())
                                    or self.lista.count() > 0)

    def _pintar_status(self) -> None:
        cor = st.VERMELHO if getattr(self, "_status_erro", False) else st.TEXTO_FRACO
        self.lbl_status.setStyleSheet(f"font-size:{FONTE_CORPO}px; color:{cor};")

    def definir_estado(self, estado: str) -> None:
        """Acende/apaga a trilha conforme onde o caso está."""
        self._estado = estado
        if estado in (INICIAL, CARREGANDO):
            self._previa = False     # caso novo: a prévia anterior não vale
        if estado in (PRONTA, VISTA):
            self._caminho_ficha = self.caminho()
        self._atualizar_botoes()

    def definir_previa(self, pronta: bool) -> None:
        """Diz se o PDF de prévia existe agora — é o que acende a Visualização.

        Ficha montada e prévia pronta são coisas diferentes: um caso
        multi-plano fica montado sem que o documento possa ser fechado, porque
        falta o agendamento. Nesse intervalo a trilha tem de mostrar que ainda
        não é hora de conferir.
        """
        self._previa = bool(pronta)
        self._atualizar_botoes()

    def previa_pronta(self) -> bool:
        return self._previa

    def estado(self) -> str:
        return self._estado

    def limpar_avisos(self) -> None:
        self.lista.clear()
        self.lista.hide()
        self._ajustar_faixa_caso()

    def _ajustar_altura_lista(self) -> None:
        """Altura colada ao conteúdo, com teto e rolagem só quando passa dele."""
        n = self.lista.count()
        if n == 0:
            self.lista.hide()
            return
        linha = self.lista.sizeHintForRow(0) or 22
        alto = min(n * linha + 12, _ALT_MAX_AVISOS)
        self.lista.setFixedHeight(alto)
        self.lista.show()
        self._ajustar_faixa_caso()

    def mostrar_avisos(self, pendencias: Iterable[str],
                       alertas: Iterable = ()) -> None:
        """Pinta pendências (âmbar) e alertas de padrão (azul) na mesma lista.

        Pendência é o que a ficha está devendo agora; alerta é o que destoa do
        histórico. Cores diferentes porque exigem reações diferentes: a primeira
        se corrige, a segunda se confere.
        """
        self.lista.clear()
        for p in pendencias:
            it = QListWidgetItem(f"⚠   {p}")
            it.setForeground(QColor(st.AMBAR))
            self.lista.addItem(it)
        for a in alertas:
            texto = f"{a.campo}: {a.mensagem}" if hasattr(a, "campo") else str(a)
            it = QListWidgetItem(f"◆   {texto}")
            it.setForeground(QColor(st.AZUL_CLARO))
            it.setToolTip("Comparação com as fichas já geradas — confira, "
                          "não é necessariamente um erro.")
            self.lista.addItem(it)
        self._ajustar_altura_lista()

    # ── Suas últimas fichas ──────────────────────────────────────────────

    def definir_recentes(self, entradas: Iterable[dict],
                         hoje: int = 0) -> None:
        """Preenche a lista com as fichas do usuário logado.

        Quem lê o histórico e filtra pelo usuário é a janela; aqui só se
        desenha. Sem nenhuma entrada, a lista continua na tela com o convite em
        vez de sumir: escondê-la faria a tela mudar de forma entre um dia e
        outro, e ninguém descobriria que ela existe.
        """
        self.recentes.clear()
        entradas = list(entradas or [])
        for e in entradas:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, e)
            item.setToolTip(self._tooltip_recente(e))
            linha = self._linha_recente(e)
            # Largura ZERO no palpite de tamanho: o que interessa é a altura.
            # Com a largura NATURAL da linha (que inclui o nome inteiro, antes
            # de elidir), o item ficava mais largo que a área visível — e, com
            # a barra horizontal desligada, o excedente era simplesmente
            # cortado: a data do lado direito saía pela metade. Zerando, a
            # lista dá ao item a largura que ela tem, e o nome é que cede.
            item.setSizeHint(QSize(0, linha.sizeHint().height()))
            self.recentes.addItem(item)
            self.recentes.setItemWidget(item, linha)
        if not entradas:
            vazio = QListWidgetItem(
                "Nenhuma ficha sua ainda — a primeira aparece aqui depois da "
                "Impressão.")
            vazio.setForeground(QColor(st.TEXTO_APAGADO))
            vazio.setFlags(Qt.NoItemFlags)     # não é clicável nem selecionável
            self.recentes.addItem(vazio)
        self.lbl_hoje.setText(
            "1 ficha hoje" if hoje == 1 else f"{hoje} fichas hoje")
        self.lbl_hoje.setVisible(hoje > 0)
        self._tem_recentes = bool(entradas)
        self._ajustar_altura_recentes()
        self._selecao_mudou()   # nada escolhido: a dica volta no lugar da faixa

    # ── O arranjo, quando a janela encolhe ───────────────────────────────

    def resizeEvent(self, e):   # noqa: N802 — assinatura do Qt
        super().resizeEvent(e)
        self._ajustar_faixa()

    def _ajustar_faixa(self) -> None:
        """Coluna larga + coluna estreita quando cabe; tudo empilhado quando não.

        Lado a lado é o pedido, e é o certo na tela da clínica. Mas em janela
        estreita a divisão deixa cada lado com pouco mais de 300 px e o nome do
        paciente passa a ser cortado numa lista que cabia inteira — medido pelo
        ``test_nome_que_cabe_fica_inteiro``, com janela de 700: "ANA LIMA"
        virava "ANA L…".

        Virar a DIREÇÃO do mesmo layout, em vez de remontar os widgets: são as
        mesmas caixas, na mesma ordem, e nada é criado nem destruído a cada
        arrasto de borda.
        """
        deitado = self.width() >= _LARG_MIN_COLUNA * 2
        direcao = (QBoxLayout.LeftToRight if deitado
                   else QBoxLayout.TopToBottom)
        if self._meio.direction() == direcao:
            return
        self._meio.setDirection(direcao)
        # ``invalidate`` + ``activate``, e não só o ``setDirection``: sem eles
        # o layout guarda o mínimo calculado para a direção ANTERIOR até algo
        # forçar um relayout — e o próximo relayout é, tipicamente, o clique da
        # pessoa numa ficha. O mínimo então saltava (medido: 534 → 639), o vão
        # de cima encolhia para caber, e a lista subia 45 px debaixo do cursor
        # que acabou de clicar. É o que o
        # ``test_escolher_uma_ficha_nao_move_a_lista`` impede, e foi ele que
        # pegou.
        self._meio.invalidate()
        self._meio.activate()

    # ── Documentação disponível ──────────────────────────────────────────

    def definir_atividades(self, entradas, recado: str = "") -> None:
        """Preenche o quadro de Documentação. ``None`` é "não perguntei ainda".

        Os três estados são DIFERENTES na tela, e essa é a única coisa que este
        método realmente protege:

        * ``None`` — ninguém respondeu ainda (ou não deu para perguntar). A
          lista não afirma nada; quem fala é o ``recado``;
        * lista vazia — o banco respondeu e **não há** documentação a fazer;
        * lista cheia — o quadro.

        Sem essa separação, "o servidor não respondeu" e "está tudo em dia"
        saem idênticos, e a segunda leitura é a que a pessoa leva para casa.

        **Caso LIBERADO sai do quadro** — pedido do usuário em 09/10/2026:
        "ficha liberada sai da documentação disponível". Até então a linha
        ficava, marcada "✓ liberada", até alguém concluir a atividade no ARIA;
        o trabalho da linha acabou na liberação, e ela só ocupava lugar. Não
        some para sempre: um plano reaprovado e trazido DEPOIS da liberação
        volta a ``pronta`` no ``gatilho_registro.estados_da_documentacao``, e
        a linha reaparece — é ficha nova para conferir.
        """
        if entradas:
            entradas = [e for e in entradas
                        if ((e.get("automacao") or {}).get("estado")
                            != gatilho_registro.LIBERADA)]
        self.atividades.clear()
        if entradas is None:
            item = QListWidgetItem(recado or "Não deu para perguntar ao "
                                             "sistema agora.")
            item.setForeground(QColor(st.TEXTO_APAGADO))
            item.setFlags(Qt.NoItemFlags)
            self.atividades.addItem(item)
        elif not entradas:
            vazio = QListWidgetItem("Nenhuma documentação em aberto no "
                                    "serviço.")
            vazio.setForeground(QColor(st.TEXTO_APAGADO))
            vazio.setFlags(Qt.NoItemFlags)
            self.atividades.addItem(vazio)
        else:
            for e in entradas:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, e)
                item.setToolTip(self._tooltip_atividade(e))
                linha = self._linha_atividade(e)
                item.setSizeHint(QSize(0, linha.sizeHint().height()))
                self.atividades.addItem(item)
                self.atividades.setItemWidget(item, linha)
        self._recado_doc = recado if entradas is not None else ""
        self._pintar_rodape_doc()
        self._ajustar_altura_atividades()

    def _pintar_rodape_doc(self) -> None:
        texto = self._recado_doc
        self.lbl_doc_rodape.setText(texto)
        # SOME quando não há recado. Antes o rodapé sempre tinha o que dizer (a
        # hora da leitura), e o rótulo vazio nunca acontecia; sem o carimbo, o
        # caso normal passou a ser vazio — e rótulo vazio visível é vão
        # reservado, que esta tela não tem.
        self.lbl_doc_rodape.setVisible(bool(texto))

    def _linha_atividade(self, e: dict) -> QWidget:
        """Dono, paciente e data — o dono PRIMEIRO, e só o PRIMEIRO NOME dele.

        A lista é do serviço inteiro, então a primeira pergunta de quem olha é
        "tem alguma minha?". Com o nome do responsável no fim da linha, isso se
        responde lendo a linha toda, uma por uma.

        **O paciente sai INTEIRO, e é ele que leva a coluna maior** (decisão do
        usuário, 23/09/2026: "nome completo do paciente, usar iniciais para o
        físico, ou somente o primeiro nome"). Até aqui o responsável ocupava a
        coluna maior com o nome completo mais as iniciais entre parênteses —
        "Ana Fatima Albuquerque (AC)" — e ao paciente sobrava o que desse, que
        era "Joao Carlos de Ol…".
        """
        w = _Linha(e)
        dono = _RotuloElidido(_primeiro_nome(e.get("dono")))
        _f = dono.font()
        _f.setPixelSize(FONTE_CORPO)
        dono.setFont(_f)
        st.pintar(dono, lambda: f"color:{st.TEXTO};")
        paciente = _RotuloElidido(e.get("paciente") or "")
        st.pintar(paciente, lambda: (
            f"font-size:{FONTE_MIUDA}px; color:{st.TEXTO_FRACO};"))
        quando = QLabel(e.get("data") or "")
        st.pintar(quando, lambda: (
            f"font-size:{FONTE_MIUDA}px; color:{st.TEXTO_APAGADO};"))
        # O PACIENTE leva a coluna maior. A regra antiga (5 para o dono, 4 para
        # o paciente) é de 02/09/2026, quando o dono aparecia completo: cortar o
        # nome dele derrubava o "tem alguma minha?", e por isso ele ficou com a
        # maior. Com só o primeiro nome, ele cabe em qualquer largura — e o peso
        # pode ir para o único dado da linha que precisa ser lido por inteiro.
        w.coluna(dono, 2)
        w.coluna(paciente, 7)
        w.coluna(quando)
        # O estado no FIM da linha, e não no começo (decisão do usuário em
        # 11/09/2026): o dono continua sendo a primeira coisa lida.
        w.coluna(self._rotulo_estado(e.get("automacao")))
        w.definir_acoes(_ACOES_DOC, self._pedir_acao_doc)
        w.fechar()
        return w

    # Texto, tinta e peso de cada estado da preparação. PRONTA na tinta mais
    # forte, e NÃO na cor de ação: a cor de ação da tela é a do sólido, e uma
    # lista com várias linhas nela competiria com ele. O convite ao clique é a
    # mão sobre a linha e a última frase do tooltip. LIBERADA apagada: o caso
    # já saiu, e a linha só fica para ninguém liberar de novo.
    _ESTADOS = {
        gatilho_registro.PRONTA: ("● PRONTA", "TEXTO", True),
        gatilho_registro.PREPARANDO: ("◌ preparando", "TEXTO_APAGADO", False),
        gatilho_registro.INCOMPLETA: ("⚠ incompleta", "AMBAR", False),
        gatilho_registro.LIBERADA: ("✓ liberada", "TEXTO_APAGADO", False),
    }

    def _rotulo_estado(self, automacao) -> QLabel:
        """A coluna do estado, de largura FIXA mesmo vazia.

        Colada ao texto, a data andaria de lugar de uma linha para a outra — a
        de um caso pronto mais para a esquerda que a de um sem estado —, e a
        coluna de datas, que se lê passando o olho na vertical, deixaria de ser
        coluna. A largura é a do rótulo mais largo, em negrito.
        """
        texto, tinta, negrito = self._ESTADOS.get(
            (automacao or {}).get("estado"), ("", "TEXTO_APAGADO", False))
        rot = QLabel(texto)
        rot.setObjectName("estado_automacao")
        f = rot.font()
        f.setPixelSize(FONTE_MIUDA)
        largo = rot.font()
        largo.setPixelSize(FONTE_MIUDA)
        largo.setBold(True)
        f.setBold(negrito)
        rot.setFont(f)
        medida = QFontMetrics(largo)
        rot.setFixedWidth(max(medida.horizontalAdvance(t)
                              for t, _, _ in self._ESTADOS.values()) + 6)
        st.pintar(rot, lambda: f"color:{getattr(st, tinta)};")
        return rot

    @staticmethod
    def _tooltip_automacao(automacao) -> list:
        """O estado da preparação, em PRIMEIRO lugar, com os avisos à frente.

        Mesma regra da capa que veio de reserva: o que muda o gesto do físico
        (montar o posicionamento à mão, esperar a próxima varredura) é o que
        se lê antes de tudo, não depois do nome do dono.
        """
        if not automacao:
            return []
        estado = automacao.get("estado")
        desde = _data_hora(automacao.get("desde"))
        if estado == gatilho_registro.PRONTA:
            linhas = [f"⚠ {a}" for a in automacao.get("avisos") or []]
            planos = ", ".join(automacao.get("planos") or [])
            linhas.append("Caso preparado" + (f" em {desde}" if desde else "")
                          + (f" — {planos}" if planos else "") + ".")
            if automacao.get("pasta"):
                linhas.append("Clique para abrir o caso e conferir.")
        elif estado == gatilho_registro.LIBERADA:
            por = automacao.get("por")
            linhas = ["Liberada para impressão"
                      + (f" em {desde}" if desde else "")
                      + (f" por {por}" if por else "") + "."]
            if automacao.get("pasta"):
                linhas.append(f"Pasta do paciente: {automacao['pasta']}")
        elif estado == gatilho_registro.INCOMPLETA:
            linhas = ["Incompleta" + (f" desde {desde}" if desde else "") + ":"]
            linhas += [f"  {m}" for m in automacao.get("motivos") or []]
        elif estado == gatilho_registro.PREPARANDO:
            # Não "está sendo trazido": daqui não se sabe se o plano já foi
            # aprovado. Afirmar trabalho em andamento de um caso que espera a
            # aprovação faria o físico esperar a automação em vez do médico.
            linhas = ["Preparando: o caso é trazido quando todos os planos do "
                      "curso estiverem aprovados e a varredura passar."]
            if desde:
                linhas.append(f"Documentação vista pela automação em {desde}.")
        else:
            return []
        return linhas + [""]

    @staticmethod
    def _tooltip_atividade(e: dict) -> str:
        partes = PainelFichinha._tooltip_automacao(e.get("automacao"))
        partes.append(e.get("dono") or "(sem responsável)")
        if e.get("paciente") or e.get("registro"):
            partes.append(" · ".join(t for t in (e.get("paciente"),
                                                 e.get("registro")) if t))
        detalhe = [t for t in (e.get("titulo"), e.get("estado"),
                               e.get("data")) if t]
        if detalhe:
            partes.append(" · ".join(detalhe))
        return "\n".join(partes)

    @staticmethod
    def _clicavel(e) -> bool:
        """Só o ``● PRONTA`` com pasta abre alguma coisa.

        Pronta SEM pasta é a de planos que saíram em pastas diferentes: abrir
        uma delas carregaria parte do curso, e a ficha sairia pela metade.
        """
        a = (e or {}).get("automacao") or {}
        return a.get("estado") == gatilho_registro.PRONTA and bool(a.get("pasta"))

    def documentacao_escolhida(self) -> Optional[dict]:
        """A linha marcada na Documentação, se ela for de um caso preparado.

        Linha que não é ``● PRONTA`` com pasta devolve ``None`` mesmo estando
        marcada: o Qt deixa marcar qualquer uma, e sem este filtro o
        «Visualizar» acenderia sobre uma Documentação que ainda não virou
        arquivo nenhum.
        """
        e = self._entrada(self.atividades.currentItem())
        return e if self._clicavel(e) else None

    def _cursor_atividade(self, item) -> None:
        clicavel = item is not None and self._clicavel(item.data(Qt.UserRole))
        self.atividades.viewport().setCursor(
            Qt.PointingHandCursor if clicavel else Qt.ArrowCursor)

    def definir_liberacao(self, liberacao) -> None:
        """O caso veio da temporária: a Impressão da linha passa a liberar.

        ``None`` volta à Impressão de sempre. Com ``{"permitido": False}`` o
        ícone continua dizendo o que faria, apagado e com o motivo no tooltip —
        ícone aceso significa pronto, e aqui "pronto" inclui quem clica.

        **Até 23/09/2026 este método escrevia em ``self.btn_imprimir``**, que a
        v8 apagou junto com a trilha de botões: ele levantava ``AttributeError``
        em TODA carga de pasta (``gui.py`` chama ``definir_liberacao(None)``
        sempre que um caso nasce), e a suíte quebrada da Fichinha escondia
        isso. O que dizia o texto do botão agora é o tooltip do ícone da linha,
        que é o único canal que sobrou — ícone não tem rótulo.
        """
        self._liberacao = dict(liberacao) if liberacao else None
        self._atualizar_botoes()

    def _dica_da_impressao(self) -> str:
        """O tooltip do ícone 🖨 da Documentação, conforme a liberação."""
        if self._liberacao is None:
            return _DICAS_DOC[IMPRIMIR]
        if self._liberacao.get("permitido"):
            return ("Liberar para impressão: grava a ficha, o registro e o "
                    "RTPLAN na pasta do paciente — não na pasta temporária — "
                    "e marca o caso como liberado.")
        return "Liberar para impressão é do físico ou do administrador."

    def _ajustar_altura_atividades(self) -> None:
        """A mesma regra dos outros quatro blocos (ver ``_Bloco.ajustar_altura``).

        Era um cálculo próprio, de quando esta lista tinha uma única vizinha e
        as duas precisavam terminar na mesma altura à mão. Com cinco blocos, a
        regra passou a morar no ``_Bloco`` — e foi isso que sumiu com as tiras
        de uma linha que a primeira conferência desenhada da v8 mostrou.
        """
        self.b_doc.ajustar_altura()

    def _linha_recente(self, e: dict) -> QWidget:
        """Uma linha em três colunas: paciente, registro, quando.

        Colunas de verdade (e não um texto único com separadores) porque a
        lista é lida de relance na vertical: o registro alinhado à direita se
        confere passando o olho, encaixado no meio da frase não.

        Transparente ao mouse para o clique chegar inteiro na lista — quem
        trata o clique é o ``QListWidget``, não os rótulos.
        """
        w = _Linha(e)
        nome = _RotuloElidido(e.get("paciente") or "(sem nome)")
        _f = nome.font()
        _f.setPixelSize(FONTE_CORPO)
        nome.setFont(_f)
        st.pintar(nome, lambda: f"color:{st.TEXTO};")
        reg = QLabel(str(e.get("registro") or ""))
        st.pintar(reg, lambda: f"font-size:{FONTE_MIUDA}px;"
                  f" color:{st.TEXTO_FRACO};")
        quando = QLabel(_quando(e.get("em", "")))
        st.pintar(quando, lambda: (
            f"font-size:{FONTE_MIUDA}px; color:{st.TEXTO_APAGADO};"))
        w.coluna(nome, 1)
        w.coluna(reg)
        w.coluna(quando)
        w.definir_acoes(_ACOES, self._pedir_acao)
        w.acender(self._acoes_possiveis(e))
        w.fechar()
        return w

    @staticmethod
    def _tooltip_recente(e: dict) -> str:
        partes = [e.get("paciente") or "(sem nome)"]
        detalhe = [t for t in (
            f"Registro {e['registro']}" if e.get("registro") else "",
            f"versão {e['versao']}" if e.get("versao") else "",
            constantes.rotulo_maquina(e.get("maquina") or "")) if t]
        if detalhe:
            partes.append(" · ".join(detalhe))
        try:
            t = datetime.datetime.fromisoformat(e.get("em", ""))
            partes.append(t.strftime("%d/%m/%Y às %H:%M"))
        except (TypeError, ValueError):
            pass
        if e.get("pasta"):
            partes.append(e["pasta"])
        return "\n".join(partes)

    def _ajustar_altura_recentes(self) -> None:
        """A mesma regra dos outros quatro blocos (ver ``_Bloco.ajustar_altura``)."""
        self.b_recentes.ajustar_altura()

    # ── Histórico: as últimas do serviço inteiro ─────────────────────────

    def definir_historico(self, entradas) -> None:
        """Preenche o bloco Histórico com as fichas do serviço.

        Mesmo formato de linha das recentes — são linhas do mesmo índice —, com
        uma coluna a mais: **de quem** é a ficha. É ela que justifica o bloco
        existir ao lado de "Suas últimas fichas"; sem o dono, as duas listas
        pareceriam a mesma coisa repetida.
        """
        self.historico.clear()
        entradas = list(entradas or [])[:MAX_HISTORICO]
        if not entradas:
            item = QListWidgetItem(
                "Nenhuma ficha gerada ainda. As últimas do serviço aparecem "
                "aqui.")
            item.setForeground(QColor(st.TEXTO_APAGADO))
            item.setFlags(Qt.NoItemFlags)
            self.historico.addItem(item)
            self.b_historico.ajustar_altura()
            self._selecao_mudou()
            return
        for e in entradas:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, e)
            item.setToolTip(self._tooltip_recente(e))
            linha = self._linha_historico(e)
            item.setSizeHint(linha.sizeHint())
            self.historico.addItem(item)
            self.historico.setItemWidget(item, linha)
        self.b_historico.ajustar_altura()
        self._selecao_mudou()

    def _linha_historico(self, e: dict) -> QWidget:
        """Paciente, dono, quando — em colunas, como a das recentes."""
        w = _Linha(e)
        nome = _RotuloElidido(e.get("paciente") or "(sem nome)")
        _f = nome.font()
        _f.setPixelSize(FONTE_CORPO)
        nome.setFont(_f)
        st.pintar(nome, lambda: f"color:{st.TEXTO};")
        dono = QLabel(str(e.get("usuario") or e.get("dono") or ""))
        st.pintar(dono, lambda: f"font-size:{FONTE_MIUDA}px;"
                  f" color:{st.TEXTO_FRACO};")
        quando = QLabel(_quando(e.get("em", "")))
        st.pintar(quando, lambda: (
            f"font-size:{FONTE_MIUDA}px; color:{st.TEXTO_APAGADO};"))
        w.coluna(nome, 1)
        w.coluna(dono)
        w.coluna(quando)
        w.definir_acoes(_ACOES, self._pedir_acao_historico)
        w.acender(self._acoes_possiveis(e))
        w.fechar()
        return w

    # ── Datas Relevantes ─────────────────────────────────────────────────

    def definir_datas(self, eventos) -> None:
        """Preenche o quadro de eventos, já filtrado e em ordem de data.

        Guarda a lista INTEIRA em ``self._datas`` e desenha só o que passa pelo
        filtro: trocar de tipo é redesenhar, não reler o arquivo do serviço.
        """
        self._datas = list(eventos or [])
        self.datas.clear()
        visiveis = [ev for ev in self._datas
                    if not self._filtro_datas
                    or (ev.get("tipo") or "") == self._filtro_datas]
        # Ordem de DATA, não de criação: um quadro de datas lido de cima para
        # baixo tem de responder "o que vem primeiro". Evento sem data vai para
        # o fim em vez de sumir — campo sem fonte nasce vazio e a tela mostra.
        visiveis.sort(key=lambda ev: (ev.get("data") or "9999-99-99"))
        if not visiveis:
            texto = ("Nenhum evento neste quadro ainda. Use «Nova»."
                     if not self._filtro_datas
                     else f"Nenhum evento de {self._filtro_datas}.")
            item = QListWidgetItem(texto)
            item.setForeground(QColor(st.TEXTO_APAGADO))
            item.setFlags(Qt.NoItemFlags)
            self.datas.addItem(item)
            self.b_datas.ajustar_altura()
            self._selecao_mudou()
            return
        for ev in visiveis:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, ev)
            if ev.get("nota"):
                item.setToolTip(str(ev["nota"]))
            linha = self._linha_data(ev)
            item.setSizeHint(linha.sizeHint())
            self.datas.addItem(item)
            self.datas.setItemWidget(item, linha)
        self.b_datas.ajustar_altura()
        self._selecao_mudou()

    def _linha_data(self, ev: dict) -> QWidget:
        """Um cartão: data, título e a etiqueta do tipo.

        A data vem PRIMEIRO e em negrito porque é por ela que a lista se lê, e
        a cor dela conta quanto falta: vencida em vermelho, hoje na cor de
        ação, o resto no texto comum. É a única informação da linha que muda
        sozinha com o passar dos dias.
        """
        w = _Linha(ev)
        dias = _dias_ate(ev.get("data") or "")
        data = QLabel(_data_curta(ev.get("data") or ""))
        st.pintar(data, lambda d=dias: (
            f"font-size:{FONTE_MIUDA}px; font-weight:bold; color:"
            + (st.VERMELHO if d is not None and d < 0
               else st.ACAO if d == 0 else st.TEXTO_FRACO) + ";"))
        titulo = QLabel(ev.get("titulo") or "(sem título)")
        st.pintar(titulo, lambda: f"font-size:{FONTE_CORPO}px; color:{st.TEXTO};")
        etiqueta = QLabel(ev.get("tipo") or "")
        st.pintar(etiqueta, lambda: (
            f"font-size:{FONTE_MIUDA}px; color:{st.TEXTO_FRACO};"
            f" background:{st.FUNDO_FUNDO}; border:1px solid {st.BORDA};"
            "  border-radius:9px; padding:2px 8px;"))
        etiqueta.setVisible(bool(ev.get("tipo")))
        w.coluna(data)
        w.coluna(titulo)
        w.coluna(etiqueta)
        # O vão fica DEPOIS da etiqueta: na faixa larga da base, mandá-la para
        # a borda direita deixava o par título/etiqueta a meia tela de
        # distância, e os dois paravam de se ler como uma coisa só.
        w.coluna(QWidget(), 1)
        w.definir_acoes(_ACOES_DATAS, self._pedir_acao_data)
        w.acender({EDITAR_DATA, EXCLUIR_DATA})
        w.fechar()
        return w

    # ── Altas Prontas ────────────────────────────────────────────────────

    def definir_altas(self, entradas, recado: str = "") -> None:
        """O quadro das altas a imprimir, com a unidade de cada paciente.

        ``None`` é "não deu para perguntar", e é diferente de ``[]``: lista
        vazia AFIRMA que não há alta a fazer, e é a leitura errada mais cara
        deste bloco — a mesma regra do quadro de Documentação.
        """
        self.altas.clear()
        # O recado vai para a lista OU para o rodapé, nunca para os dois: sem
        # resposta do sistema, o motivo é o conteúdo da lista, e repeti-lo
        # embaixo lia como se fossem dois problemas.
        self.b_altas.definir_rodape("" if entradas is None else recado)
        if entradas is None:
            item = QListWidgetItem(recado or "Sem resposta do sistema.")
            item.setForeground(QColor(st.TEXTO_APAGADO))
            item.setFlags(Qt.NoItemFlags)
            self.altas.addItem(item)
            self._montar_chips_unidade([])
            self.b_altas.ajustar_altura()
            self._selecao_mudou()
            return
        entradas = list(entradas)
        if not entradas:
            item = QListWidgetItem("Nenhuma alta pendente agora.")
            item.setForeground(QColor(st.TEXTO_APAGADO))
            item.setFlags(Qt.NoItemFlags)
            self.altas.addItem(item)
            self._montar_chips_unidade([])
            self.b_altas.ajustar_altura()
            self._selecao_mudou()
            return
        for e in entradas:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, e)
            linha = self._linha_alta(e)
            item.setSizeHint(linha.sizeHint())
            self.altas.addItem(item)
            self.altas.setItemWidget(item, linha)
        self.b_altas.definir_cracha(f"{len(entradas)}")
        self._montar_chips_unidade(entradas)
        self.b_altas.ajustar_altura()
        self._selecao_mudou()

    def _montar_chips_unidade(self, entradas) -> None:
        """Um chip por unidade PRESENTE na lista, com quantas ela tem.

        Recriados a cada leitura em vez de fixos: a lista de unidades muda com
        o serviço, e um chip que nunca tem nada é um alvo que ensina a não
        clicar. O número ao lado é o que o físico confere antes de mandar
        imprimir — doze altas e doze folhas.
        """
        for chip in self._chips_unidade.values():
            self._lay_unidades.removeWidget(chip)
            chip.deleteLater()
        self._chips_unidade = {}
        contagem: dict = {}
        for e in entradas or []:
            unidade = (e.get("unidade") or "").strip()
            if unidade:
                contagem[unidade] = contagem.get(unidade, 0) + 1
        for unidade in sorted(contagem):
            chip = QPushButton(f"{unidade}  {contagem[unidade]}")
            chip.setCursor(Qt.PointingHandCursor)
            chip.setFocusPolicy(Qt.NoFocus)
            # Alternável para PODER ficar marcado; quem decide o estado é o
            # ``_selecao_mudou``, olhando a seleção real da lista. Sem isto o
            # chip alternava sozinho e mentia quando a pessoa desmarcava uma
            # linha à mão.
            chip.setCheckable(True)
            chip.setToolTip(f"Marcar as {contagem[unidade]} altas de "
                            f"{unidade}.")
            st.pintar(chip, _estilo_filtro)
            chip.clicked.connect(
                lambda _c=False, u=unidade: self._marcar_unidade(u))
            self._chips_unidade[unidade] = chip
            # Antes do vão, que é o último item da faixa.
            self._lay_unidades.insertWidget(
                self._lay_unidades.count() - 1, chip)
        self._faixa_unidades.setVisible(bool(self._chips_unidade))

    def _marcar_unidade(self, unidade: str) -> None:
        """Marca todas as altas de uma unidade — e desmarca se já estavam.

        Clicar de novo no mesmo chip DESMARCA: sem isso, o único jeito de
        desfazer seria clicar numa linha qualquer, e quem marcou doze por
        engano não adivinha esse gesto.
        """
        itens = [self.altas.item(i) for i in range(self.altas.count())]
        da_unidade = [it for it in itens
                      if ((self._entrada(it) or {}).get("unidade") or "")
                      == unidade]
        ja_marcadas = all(it.isSelected() for it in da_unidade)
        for it in da_unidade:
            it.setSelected(not ja_marcadas)
        self._selecao_mudou()

    def _linha_alta(self, e: dict) -> QWidget:
        """Paciente, unidade, data — e se a alta já está em disco.

        A marca do PDF não é enfeite: sem ela, escolher cinco pacientes e
        clicar em «Abrir alta» abriria três arquivos e daria erro em dois, e o
        erro chegaria DEPOIS do clique. Com a marca, quem escolhe já sabe.
        """
        w = _Linha(e)
        # Sem marca de "achei/não achei o PDF" na linha: o usuário mandou
        # tirar em 23/09/2026, e ela estava em TODAS as linhas — estes
        # pacientes não têm ficha gerada por este app, então o aviso não
        # distinguia nada. Quem continua dizendo é o ÍCONE de abrir, que só
        # acende quando o arquivo existe.
        nome = _RotuloElidido(e.get("paciente") or "(sem nome)")
        _f = nome.font()
        _f.setPixelSize(FONTE_CORPO)
        nome.setFont(_f)
        st.pintar(nome, lambda: f"color:{st.TEXTO};")
        unidade = QLabel(str(e.get("unidade") or ""))
        st.pintar(unidade, lambda: (
            f"font-size:{FONTE_MIUDA}px; color:{st.TEXTO_FRACO};"
            f" background:{st.FUNDO_FUNDO}; border:1px solid {st.BORDA};"
            "  border-radius:9px; padding:2px 8px;"))
        unidade.setVisible(bool(e.get("unidade")))
        quando = QLabel(str(e.get("data") or ""))
        st.pintar(quando, lambda: (
            f"font-size:{FONTE_MIUDA}px; color:{st.TEXTO_APAGADO};"))
        w.coluna(nome, 1)
        w.coluna(unidade)
        w.coluna(quando)
        w.definir_acoes(_ACOES_ALTAS, self._pedir_acao_alta)
        # O ícone do PDF só acende quando o arquivo existe; a pasta, quando a
        # pasta existe. Aceso e sem arquivo, o clique só teria como avisar que
        # não deu — e o aviso chegaria depois do clique.
        w.acender({k for k, campo in ((ABRIR_ALTA, "pdf"),
                                      (PASTA_ALTA, "pasta")) if e.get(campo)})
        w.fechar()
        return w

    def _entrada(self, item) -> Optional[dict]:
        dados = item.data(Qt.UserRole) if item is not None else None
        return dados if isinstance(dados, dict) else None

    def ficha_escolhida(self) -> Optional[dict]:
        """A ficha selecionada na lista de recentes, ou ``None``."""
        return self._entrada(self.recentes.currentItem())

    @staticmethod
    def _acoes_possiveis(e: dict) -> set:
        """Quais ações fazem sentido para ESTA ficha.

        A ficha existe em dois lugares independentes, e nem sempre nos dois: o
        **índice** (de onde saem o registro salvo, as versões e o PDF) e a
        **pasta** do paciente. Índice limpo, pasta movida, ficha antiga sem
        pasta anotada — cada combinação apaga um conjunto diferente de botões,
        e apagar é melhor que deixar aceso para responder "não deu".
        """
        no_indice = bool(e.get("json_path"))
        versoes = e.get("n_versoes") or 0
        acoes = set()
        if no_indice:
            acoes.update({CARREGAR, PDF})
        if no_indice and versoes >= 2:
            acoes.add(VERSOES)
        if e.get("pasta") or e.get("json_path"):
            acoes.add(PASTA)
        return acoes

    def _selecao_mudou(self) -> None:
        """Reavalia o que depende de haver linha escolhida.

        Encolheu na v8.1: as faixas de botões que este método mostrava e
        escondia não existem mais, e o que cada ícone permite é decidido no
        hover da linha (ver ``_hover_doc`` e ``_Linha.acender``). Ficou o que é
        de fato consequência da seleção.
        """
        self._atualizar_trilha()

        # ── Altas Prontas ──
        # O ícone do cabeçalho só existe quando há o que abrir, e só ACENDE se
        # alguma das marcadas tiver PDF em disco — aceso e sem arquivo, o
        # clique só teria como avisar que não deu, depois do clique.
        escolhidas = self.altas_escolhidas()
        self._btn_abrir_altas.setVisible(bool(escolhidas))
        self._btn_abrir_altas.setEnabled(
            not self._travado and any(e.get("pdf") for e in escolhidas))
        # O chip fica MARCADO quando a unidade inteira está na seleção: é o
        # retorno de quem clicou nele, e o que distingue "marquei o CEL" de
        # "marquei três pacientes que por acaso são do CEL".
        todas = self._entradas_das_altas()
        for unidade, chip in self._chips_unidade.items():
            na_unidade = sum(1 for e in todas
                             if (e.get("unidade") or "") == unidade)
            marcadas = sum(1 for e in escolhidas
                           if (e.get("unidade") or "") == unidade)
            chip.setChecked(bool(na_unidade) and marcadas == na_unidade)

    # ── O que cada linha permite ─────────────────────────────────────────

    def _hover_doc(self, item) -> None:
        """Mostra os ícones da linha apontada, acesos conforme o caso.

        Os três ícones da Documentação não valem sempre: a Impressão depende
        de a ficha DESTA linha estar montada e conferida, e não de a linha
        existir. Como a ficha muda de estado enquanto o cursor passeia pela
        lista, o cálculo é feito no hover — não na montagem da linha, que
        aconteceu antes de tudo isso.
        """
        self.b_doc.linha_sob_o_cursor(item)
        self._acender_linha_doc(item)
        self._cursor_atividade(item)

    def _acender_linha_doc(self, item) -> None:
        """Acende os ícones de UMA linha da Documentação e ajusta as dicas.

        Um lugar só porque são dois os caminhos que precisam disto — o cursor
        chegando na linha (``_hover_doc``) e a ficha mudando de estado com o
        cursor parado nela (``_atualizar_trilha``) — e porque a dica da
        Impressão, esquecida num deles, mentiria exatamente no caso em que ela
        é a única coisa a explicar o ícone apagado.
        """
        linha = self.atividades.itemWidget(item) if item is not None else None
        if not isinstance(linha, _Linha):
            return
        linha.acender(self._acoes_da_documentacao(self._entrada(item)))
        linha.definir_dica(IMPRIMIR, self._dica_da_impressao())

    def _acoes_da_documentacao(self, e) -> set:
        """Quais dos três ícones fazem sentido nesta linha, agora.

        **Visualizar e Editar acendem com a LINHA** — decisão do usuário em
        22/09/2026: os dois montam o caso se ele ainda não estiver montado, e o
        que muda é onde ele é entregue (na prévia ou na bancada). Exigir a
        ficha pronta obrigaria a passar pela visualização para poder editar.

        **A Impressão espera a Visualização**, que é a única regra da trilha
        que não se negocia — e espera a visualização DESTA linha: imprimir com
        o caso anterior montado sairia com o nome do paciente novo na tela e o
        documento do antigo na bandeja.
        """
        if not self._clicavel(e) or self._travado or self._estado == CARREGANDO:
            return set()
        acoes = {VISUALIZAR, EDITAR}
        pasta = ((e.get("automacao") or {}).get("pasta")) or ""
        e_esta = (self._estado in (PRONTA, VISTA)
                  and self._mesma_pasta(pasta, self._caminho_ficha))
        permitido = (self._liberacao is None
                     or bool(self._liberacao.get("permitido")))
        if (self._estado == VISTA and e_esta and self._previa and permitido):
            acoes.add(IMPRIMIR)
        return acoes

    def _atualizar_trilha(self) -> None:
        """Reacende os ícones da linha que está sob o cursor agora.

        Sem isto, terminar a montagem de uma ficha com o cursor parado sobre a
        linha deixaria a Impressão apagada até a pessoa mover o mouse — e ela
        moveria o mouse para clicar justamente ali.
        """
        self._acender_linha_doc(self.atividades.currentItem())

    # ── Os pedidos ───────────────────────────────────────────────────────

    def _pedir_acao(self, acao: str, e: dict) -> None:
        if e and acao in self._acoes_possiveis(e):
            self.acao_recente.emit(acao, e)

    def _pedir_acao_historico(self, acao: str, e: dict) -> None:
        """As mesmas ações das recentes, sobre a lista do serviço inteiro.

        Mesmo sinal (``acao_recente``), porque a janela faz exatamente a mesma
        coisa com as duas: as linhas são do mesmo formato — do índice central —
        e um segundo sinal seria um segundo lugar para esquecer de tratar uma
        ação nova.
        """
        if e and acao in self._acoes_possiveis(e):
            self.acao_recente.emit(acao, e)

    def _pedir_acao_doc(self, acao: str, e: dict) -> None:
        """A trilha: Visualizar → Editar → Impressão, sobre a linha apontada.

        **Visualizar faz duas coisas conforme o caso já estar montado ou não**,
        e é de propósito: quem clica quer ver a ficha daquele paciente, e se
        ela ainda não existe o passo de montá-la não é uma decisão a tomar — é
        trabalho no caminho.
        """
        if acao not in self._acoes_da_documentacao(e):
            return
        if acao == IMPRIMIR:
            self.pedir_impressao.emit()
            return
        pasta = ((e.get("automacao") or {}).get("pasta")) or ""
        montada = (self._estado in (PRONTA, VISTA)
                   and self._mesma_pasta(pasta, self._caminho_ficha))
        if montada and (acao == EDITAR or self._previa):
            # O caso desta linha já está na tela: o ícone faz só o seu passo.
            (self.abrir_edicao if acao == EDITAR
             else self.pedir_visualizacao).emit()
            return
        # Ainda não está montado. O pedido leva o DESTINO junto, e é a janela
        # que o cumpre quando a carga termina: montar leva segundos e acontece
        # noutra thread, então não há como decidir aqui o que fazer depois.
        pedido = dict(e)
        pedido["apos"] = acao
        self.abrir_documentacao.emit(pedido)

    def _pedir_acao_data(self, acao: str, ev: dict) -> None:
        self.acao_data.emit(acao, ev or {})

    def _pedir_acao_alta(self, acao: str, e: dict) -> None:
        """O ícone da linha age sobre a SELEÇÃO, quando há uma.

        É a única lista assim, e a razão é o pedido: escolher vários pacientes
        e abrir todas as altas de uma vez. Clicar no ícone de uma linha que não
        está na seleção age sobre ELA — senão o clique faria uma coisa
        invisível, longe de onde o cursor está.
        """
        escolhidas = self.altas_escolhidas()
        if e and e not in escolhidas:
            escolhidas = [e]
        if escolhidas:
            self.acao_alta.emit(acao, escolhidas)

    def _entradas_das_altas(self) -> list:
        """Todas as entradas da lista de altas, marcadas ou não."""
        return [e for e in (self._entrada(self.altas.item(i))
                            for i in range(self.altas.count())) if e]

    def altas_escolhidas(self) -> list:
        """As linhas marcadas em Altas Prontas — pode ser mais de uma."""
        return [x for x in (self._entrada(i)
                            for i in self.altas.selectedItems()) if x]

    def _filtrar_datas(self, tipo: str) -> None:
        """Mostra só um tipo de evento (ou todos, com ``""``)."""
        self._filtro_datas = tipo or ""
        for chave, btn in self._btns_filtro.items():
            btn.setChecked(chave == self._filtro_datas)
        self.definir_datas(self._datas)

    def limpar_selecao_recente(self) -> None:
        """Solta a ficha escolhida — a faixa de ações some junto.

        Usado quando a ação escolhida trocou o caso da tela: manter a linha
        anterior marcada faria a faixa continuar oferecendo ações sobre uma
        ficha que não é mais a que está aberta.
        """
        self.recentes.clearSelection()
        self.recentes.setCurrentItem(None)
        self._selecao_mudou()

    def bloquear(self, travado: bool) -> None:
        """Trava os controles enquanto um trabalho bloqueante roda.

        Substitui o modal de progresso neste modo: a mensagem vai para a linha
        de status e os botões apagam, então não há o que clicar por engano. Sem
        isto, o clique dado durante a geração ficaria na fila e dispararia uma
        segunda geração assim que a primeira soltasse a interface.
        """
        self._travado = travado
        self._atualizar_botoes()

    def invalidar_visualizacao(self) -> None:
        """Volta de VISTA para PRONTA — usado depois de uma edição.

        Sem isto, editar a ficha depois de vê-la deixaria a Impressão acesa
        apontando para um documento que ninguém conferiu. A prévia também cai:
        o PDF em disco é da versão anterior à edição.
        """
        self._previa = False
        if self._estado == VISTA:
            self.definir_estado(PRONTA)
            self.mostrar_status("Ficha alterada — visualize de novo antes de "
                                "imprimir.")
        else:
            self._atualizar_botoes()

    # ── Interno ──────────────────────────────────────────────────────────

    def _atualizar_botoes(self, *_) -> None:
        ocupado = self._estado == CARREGANDO or self._travado
        # As listas apagam durante o trabalho: o clique dado no meio de uma
        # carga ficaria na fila e trocaria o paciente assim que ela soltasse.
        for lista in (self.recentes, self.historico, self.atividades,
                      self.datas, self.altas):
            lista.setEnabled(not ocupado)
        self._selecao_mudou()

    @staticmethod
    def _mesma_pasta(a: str, b: str) -> bool:
        """Dois caminhos apontam a mesma pasta? (barra, maiúscula, ``.``)

        **O ``@staticmethod`` sumiu na v8 e custou caro**: chamada como método,
        ela recebia três argumentos para dois e levantava ``TypeError`` DENTRO
        de um slot do Qt — que não propaga exceção. O processo caía com exit
        127 e nenhum traceback, e o caminho afetado era justamente o da
        Impressão (o único que compara pastas). Não tirar de novo.
        """
        def _n(c: str) -> str:
            c = (c or "").strip().strip('"')
            return os.path.normcase(os.path.abspath(c)) if c else ""
        return _n(a) == _n(b)

    def limpar_caso(self) -> None:
        """Tira o caso da tela e volta a trilha ao começo.

        Herdeira do ``×`` do campo, que sumiu com ele na v8. Continua existindo
        porque a janela precisa de um jeito de dizer "este caso não está mais
        aqui" quando ela própria o descarta — sem isto, a faixa do caso
        continuaria falando de um paciente que saiu da bancada.
        """
        anterior = self._estado
        self._caminho = ""
        self._caminho_ficha = ""
        self.definir_estado(INICIAL)
        self.limpar_avisos()
        self.mostrar_status("")
        if anterior in (PRONTA, VISTA):
            self.fechar_caso.emit(anterior)


class _DialogoEvento(ui.Dialogo):
    """Criar ou alterar um evento do quadro de Datas Relevantes.

    Data em campo de texto no formato do país (``dd/mm/aaaa``) e não num
    ``QDateEdit``: o calendário do Qt abre no mês de hoje e obriga a navegar
    até o mês do evento, e a maioria destes eventos é digitada de cabeça — "3
    de outubro" se escreve mais rápido do que se acha. O que volta é sempre
    ISO; a conversão é aqui, num lugar só.
    """

    def __init__(self, pai=None, evento=None):
        evento = evento or {}
        novo = not evento.get("id")
        super().__init__("Novo evento" if novo else "Alterar evento", pai, 420, 0)
        self._id = evento.get("id") or ""

        self.campo_data = ui.entrada(dica="dd/mm/aaaa")
        self.campo_data.setText(_data_br(evento.get("data") or ""))
        self.corpo.addWidget(ui.campo("Data", self.campo_data))

        self.campo_titulo = ui.entrada(dica="o que acontece nesse dia")
        self.campo_titulo.setText(evento.get("titulo") or "")
        self.corpo.addWidget(ui.campo("Evento", self.campo_titulo))

        self.campo_tipo = ui.escolha(TIPOS_DE_DATA)
        atual = evento.get("tipo") or TIPOS_DE_DATA[0]
        if atual in TIPOS_DE_DATA:
            self.campo_tipo.setCurrentIndex(TIPOS_DE_DATA.index(atual))
        self.corpo.addWidget(ui.campo("Tipo", self.campo_tipo))

        self.campo_nota = ui.entrada(dica="opcional")
        self.campo_nota.setText(evento.get("nota") or "")
        self.corpo.addWidget(ui.campo("Nota", self.campo_nota))

        self.rodape(confirmar="Salvar")

    def valores(self) -> dict:
        return {"id": self._id,
                "data": _data_iso(self.campo_data.text()),
                "titulo": self.campo_titulo.text().strip(),
                "tipo": self.campo_tipo.currentText(),
                "nota": self.campo_nota.text().strip()}


def perguntar_evento(pai, evento=None) -> Optional[dict]:
    """Abre o diálogo e devolve o evento, ou ``None`` se desistiram.

    Recusa data ilegível e evento sem título em vez de gravar: um cartão sem
    título é uma linha em branco no quadro do serviço, e data que não vira ISO
    iria para o fim da lista para sempre, sem ninguém entender por quê.
    """
    while True:
        dlg = _DialogoEvento(pai, evento)
        if not dlg.exec():
            return None
        valores = dlg.valores()
        if not valores["titulo"]:
            ui.alertar(pai, "Falta o evento", "Escreva o que acontece nesse dia.")
            evento = valores
            continue
        if not valores["data"]:
            ui.alertar(pai, "Data não entendida",
                       "Escreva a data como dd/mm/aaaa — por exemplo, "
                       "03/10/2026.")
            evento = valores
            continue
        return valores


# Estilo próprio do seletor de modo — NÃO reusa ``btn_contorno``, que é
# dimensionado para botão de ação: a folga vertical dele não cabe numa faixa de
# 38 px e cortava o texto. Aqui a borda tem a mesma espessura nos dois estados,
# para o botão não pular de tamanho ao ser marcado.
#
# É uma FUNÇÃO, e não uma constante: constante vira texto no momento do import e
# ficaria com as cores do modo que estava em vigor ali.
def _estilo_modo() -> str:
    return (
        "QPushButton{"
        "  background:transparent;"
        f" color:{st.ACAO}; font-size:12px; font-weight:600;"
        f" border:1px solid {st.ACAO_LINHA}; border-radius:7px;"
        "  padding:2px 14px; }"
        f"QPushButton:hover{{ border-color:{st.ACAO}; background:{st.ACAO_FUNDO}; }}"
        "QPushButton:checked{"
        f" background:{st.ACAO}; color:{st.SOBRE_ACAO};"
        f" border:1px solid {st.ACAO}; }}"
    )


# O símbolo de dia/noite. Sem moldura de botão a pedido: é um caractere que
# muda de estado, não um controle a mais numa faixa que já tem três.
_SIMBOLO_MODO = {"noite": "☾", "dia": "☀"}


class _AlternarModo(QLabel):
    """O símbolo dia/noite do canto superior direito.

    Um rótulo clicável em vez de um ``QPushButton``: a faixa já carrega os três
    seletores de tela, e um quarto retângulo ali competiria com eles. O símbolo
    mostra **o modo em vigor**, não o destino do clique — é o mesmo que o
    relógio da bandeja faz.
    """

    def __init__(self, ao_alternar, parent=None):
        super().__init__(parent)
        self._ao_alternar = ao_alternar
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedWidth(30)
        st.pintar(self, lambda: (
            f"QLabel{{ color:{st.TEXTO_FRACO}; font-size:17px;"
            "  background:transparent; border:none; }"
            f"QLabel:hover{{ color:{st.ACAO}; }}"))
        self.atualizar()
        st.ao_trocar(self.atualizar)

    def atualizar(self) -> None:
        modo = st.modo()
        self.setText(_SIMBOLO_MODO.get(modo, "☾"))
        self.setToolTip("Modo noturno — clique para o modo claro"
                        if modo == "noite" else
                        "Modo claro — clique para o modo noturno")

    def mousePressEvent(self, e):  # noqa: N802 - assinatura do Qt
        if e.button() == Qt.LeftButton:
            self._ao_alternar()
            e.accept()
            return
        super().mousePressEvent(e)


# Posição de cada tela no QStackedWidget da janela. O número é o contrato com a
# ``JanelaPrincipal`` — a ORDEM em que as telas foram empilhadas lá —, e não a
# ordem em que elas aparecem na faixa. São coisas diferentes de propósito:
# reordenar a faixa é decisão de tela, e renumerar aqui exigiria mexer no
# empilhamento. Tela nova entra no FIM, nunca no meio.
MODO_TOTAL = 0
MODO_FICHINHA = 1
MODO_CAPA = 2
MODO_FICHA_VIRTUAL = 3
MODO_QUALIDADE = 4
MODO_AGENDA = 5
# Protótipo de 13/10/2026 (docs/planejamento/sistema-global/radioteradados/).
MODO_RADIOTERADADOS = 6

# A tela em que o programa abre. A Fichinha é a porta: a maioria dos casos é
# apontar a pasta e imprimir, e quem precisa da bancada troca num clique — o
# contrário (abrir no formulário denso e ter de sair dele) cobra de todo mundo
# o preço do caso difícil.
#
# Desde 09/10/2026 ela NÃO é a primeira da faixa (a Capa-Up é), e o usuário
# pediu assim mesmo: "manter abrindo primeiro fichinha, mesmo que fique
# diferente". Ver ``modo_inicial``.
MODO_INICIAL = MODO_FICHINHA

# Os modos na ORDEM DA FAIXA — e, portanto, na ordem em que o Ctrl+Tab os
# percorre. Fonte única: a faixa é montada a partir daqui.
#
# Capa-Up primeiro desde 09/10/2026, a pedido do usuário: "deixar a aba capa-up
# primeiro, depois seguir normalmente" — Capa-Up, Fichinha, Total, Qualidade,
# Virtual e Agenda. O programa continua abrindo na Fichinha (``MODO_INICIAL``).
#
# Rótulos CURTOS desde 26/08/2026, a pedido do usuário: "Ficha Total" e "Ficha
# Virtual" repetiam "Ficha" numa faixa onde tudo é ficha, e a palavra repetida
# três vezes é a que o olho tem de pular para achar o que distingue uma aba da
# outra. O nome longo continua valendo na conversa e no resto do código.
ROTULOS_MODO: tuple[tuple[int, str], ...] = (
    (MODO_CAPA, "Capa-Up"),
    (MODO_FICHINHA, "Fichinha"),
    (MODO_TOTAL, "Total"),
    # A ordem pedida pelo usuário em 23/09/2026. A Qualidade subiu do fim para
    # cá: ela CONFERE o que o TPS mandou, e conferir vem antes de montar o
    # documento — a faixa passa a ler na ordem do trabalho (conferir o plano →
    # montar a capa), e não na ordem em que as telas foram escritas.
    # Rótulo "CQ Plano" (era "Qualidade") desde 13/10/2026, a pedido do usuário.
    (MODO_QUALIDADE, "CQ Plano"),
    # Separada em espírito das anteriores: aquelas montam o documento do
    # paciente que está sendo preparado; esta consulta o que já aconteceu com um
    # paciente qualquer. Quem trabalha nas primeiras raramente precisa dela, e
    # vice-versa.
    (MODO_FICHA_VIRTUAL, "Virtual"),
    # Por último, e nova em 23/09/2026: a agenda por máquina, de leitura como
    # a Virtual, mas de outro assunto — quem tem hora marcada, não o que já
    # aconteceu. Ao lado da Virtual porque as duas são de consulta, não de
    # montagem de documento.
    (MODO_AGENDA, "Agenda"),
    # Os indicadores do serviço (protótipo, 13/10/2026). Por último: não é do
    # paciente, é do mês. Fica só para físico e admin pelo ``MODOS_POR_PAPEL``
    # (entram pelo ``MODOS``); o médico e a gestão entram quando o filtro "só os
    # meus" e o papel ``gestao`` existirem (AD-8 da arquitetura).
    (MODO_RADIOTERADADOS, "Radioteradados"),
)
MODOS: tuple[int, ...] = tuple(m for m, _r in ROTULOS_MODO)

# As abas cujo botão nasce ESCONDIDO e só aparece com a tela na frente (ver
# ``gui.JanelaPrincipal._trocar_modo``). De 08/09/2026 a 09/10/2026 era a Ficha
# Total, alcançada pela Edição da Fichinha; voltou a ficar à mostra a pedido do
# usuário ("pode deixar a aba Total mostrando"). A Edição continua levando a ela.
MODOS_OCULTOS: tuple[int, ...] = ()

# ── Quem vê o quê ────────────────────────────────────────────────────────
# As abas por FUNÇÃO (pedido do usuário em 26/08/2026). Não é segurança — é
# tirar da frente a tela que aquela função não usa: o médico abre o programa
# para consultar o que aconteceu com um paciente, e três abas de montagem de
# documento no caminho são três lugares onde ele pode se perder.
#
# O ADMIN vê tudo junto com o físico: é quem configura o serviço e precisa
# poder conferir qualquer tela para responder por ela.
#
# Quem não está no mapa fica com o PADRÃO — dosimetrista, técnico, enfermeiro,
# recepcionista, e qualquer função que venha a existir. Um papel novo aparecer
# com acesso a tudo por descuido é pior que aparecer com acesso de menos: o de
# menos alguém reclama no mesmo dia, o de mais ninguém percebe.
MODOS_POR_PAPEL: dict[str, tuple[int, ...]] = {
    "admin": MODOS,
    "fisico": MODOS,
    "medico": (MODO_FICHA_VIRTUAL, MODO_AGENDA),
}
# A Qualidade fica FORA do padrão de propósito: os índices e a complexidade são
# a conferência do físico sobre o plano do TPS, e uma reprovação ali é decisão
# de física médica, não de quem monta a ficha. Quem não é físico nem admin não
# vê a aba — e não vê justamente para não ter de responder por um "fora da
# faixa" que ainda nem está calibrado (ver ``qualidade.CALIBRADO``).
#
# A Agenda fica DENTRO do padrão, ao contrário da Qualidade (decisão do
# usuário em 23/09/2026): é informação de serviço — quem tem hora marcada em
# qual máquina —, não decisão clínica. Todas as funções a veem.
MODOS_PADRAO: tuple[int, ...] = (MODO_CAPA, MODO_FICHA_VIRTUAL, MODO_AGENDA)


def modos_do_papel(papel: str = "") -> tuple[int, ...]:
    """As abas desta função, NA ORDEM DA FAIXA.

    A ordem sai sempre de ``ROTULOS_MODO``, e não da tupla do mapa: escrever a
    ordem duas vezes é escrevê-la errado na segunda, e a faixa passaria a ler
    diferente conforme quem entrou.

    Papel DESCONHECIDO cai no padrão (ver ``MODOS_POR_PAPEL``). Papel VAZIO
    não: sem ninguém identificado não há função para recortar, e esconder aba
    de quem o programa não sabe quem é seria esconder por engano. É o caso da
    janela aberta sem login — em teste e em qualquer fluxo que não passe pela
    tela de entrada.
    """
    papel = str(papel or "").strip().lower()
    if not papel:
        return MODOS
    permitidos = MODOS_POR_PAPEL.get(papel, MODOS_PADRAO)
    return tuple(m for m in MODOS if m in permitidos)


# Quem libera para impressão o caso que a automação preparou. Físico e admin
# (decisão do usuário em 11/09/2026). Papel VAZIO libera pela mesma regra do
# ``modos_do_papel``: é a janela montada sem login (testes, ferramentas), e não
# um usuário de função desconhecida — este cai no "não".
PAPEIS_QUE_LIBERAM: tuple[str, ...] = ("fisico", "admin")


def pode_liberar(papel: str = "") -> bool:
    papel = str(papel or "").strip().lower()
    return not papel or papel in PAPEIS_QUE_LIBERAM


def modo_inicial(papel: str = "") -> int:
    """A aba em que o programa abre para esta função: a PRIMEIRA que ela vê.

    Para o físico é a Fichinha (``MODO_INICIAL``), mesmo não sendo a primeira
    da faixa; para o
    médico é a Virtual, a única que ele tem. Abrir numa aba que a função não
    enxerga deixaria a faixa sem botão aceso e o miolo mostrando uma tela que
    ninguém pode escolher de volta.
    """
    disponiveis = modos_do_papel(papel)
    if not disponiveis or MODO_INICIAL in disponiveis:
        return MODO_INICIAL
    return disponiveis[0]


def barra_de_modo(ao_trocar, ao_alternar_modo=None,
                  papel: str = "") -> tuple[QWidget, dict[int, QPushButton]]:
    """Seletor de modo da faixa superior.

    Os dois juntos, à esquerda: **Fichinha** (o painel das listas) e **Capa-Up**
    (do posicionamento à impressão). São o mesmo seletor e trocam a mesma coisa
    — a tela do caso —, então ficam lado a lado em vez de separados por um vão.
    A **Total** também tem botão; ver ``MODOS_OCULTOS``.

    A faixa fica **fora** das telas, para valer em todas — a troca de volta tem
    de estar disponível de dentro de qualquer uma, senão ela vira um beco. Azul
    porque é estrutura, não ação.

    ``papel`` recorta a faixa por FUNÇÃO (ver ``modos_do_papel``): o que não
    aparece aqui não tem como ser aberto, porque é desta lista que saem o botão,
    o modo inicial e o ciclo do Ctrl+Tab.

    Devolve (faixa, {índice do modo: botão}); quem chama liga o resto. O
    dicionário só traz os modos que aquela função vê — quem procura um botão
    fixo tem de usar ``.get``.
    """
    faixa = QWidget()
    faixa.setFixedHeight(38)
    st.pintar(faixa, lambda: (
        f"background:{st.FUNDO_FUNDO};"
        f"border-bottom:1px solid {st.BORDA};"))
    lay = QHBoxLayout(faixa)
    lay.setContentsMargins(10, 4, 10, 4)
    lay.setSpacing(8)

    botoes: dict[int, QPushButton] = {}

    def _botao(texto: str, modo: int) -> QPushButton:
        b = QPushButton(texto)
        b.setCheckable(True)
        # Um grupo exclusivo só: escolher a Capa tem de APAGAR a Ficha Total.
        b.setAutoExclusive(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(28)
        b.setMinimumWidth(108)
        # O botão existe para todos os modos, mas o dos OCULTOS só aparece
        # quando a tela dele está na frente (ver ``MODOS_OCULTOS``). Escondido
        # ele continua no grupo exclusivo, e é isso que faz a Fichinha APAGAR
        # quando a bancada abre pela Edição.
        b.setVisible(modo not in MODOS_OCULTOS)
        st.pintar(b, _estilo_modo)
        b.clicked.connect(lambda _c=False, m=modo: ao_trocar(m))
        botoes[modo] = b
        lay.addWidget(b)
        return b

    # Sem rótulos de grupo: os nomes já dizem o que são.
    permitidos = modos_do_papel(papel)
    for modo, rotulo in ROTULOS_MODO:
        if modo in permitidos:
            _botao(rotulo, modo)
    # Já nasce marcada a tela em que o programa abre: a faixa não pode apontar
    # uma tela e o miolo mostrar outra, nem por um instante. Para a função de
    # uma aba só, é essa aba — e aí a faixa é um botão aceso sozinho, que é a
    # leitura certa: não há para onde trocar.
    botoes[modo_inicial(papel)].setChecked(True)
    lay.addStretch(1)
    # No canto oposto ao dos seletores: ele não escolhe TELA, escolhe como a
    # tela se vê. Junto dos três, seria lido como uma quarta tela.
    if ao_alternar_modo is not None:
        lay.addWidget(_AlternarModo(ao_alternar_modo))
    return faixa, botoes
