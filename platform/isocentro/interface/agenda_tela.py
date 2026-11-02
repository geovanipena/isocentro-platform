"""A aba **Agenda**: quem está marcado em cada máquina, num dia.

As outras abas montam ou consultam UM paciente. Esta responde outra
pergunta, para outra pessoa — quem está de pé perto da sala e precisa saber
"quem vem agora nesta máquina, e na de do lado": a agenda de HOJE (ou de
outro dia escolhido), lida por MÁQUINA, com mais de uma coluna ao mesmo tempo
para comparar salas.

Decisões de tela tomadas com o usuário em 23/09/2026, e que não se parecem
com o resto do app:

**Colunas por máquina, não uma lista única.** Cada máquina do par marcado
vira uma coluna, lado a lado, com as marcações em ordem de hora — é assim
que se enxerga a ocupação de CADA sala, e não só "o que vem a seguir no
serviço". As colunas DIVIDEM a largura inteira da aba, igualmente — sem
largura fixa e sem vão sobrando à direita; o texto que não cabe corta com
reticências na largura de cada momento.

**Três PARES fixos, um de cada vez** (:data:`PARES_MAQUINA`) — pedido do
usuário em 24/09/2026: ``6EX``+``TrueBeam``, ``Braquiterapia``+``Dermopan``,
``600CD``+``VitalBeam`` são olhadas juntas, nunca uma sozinha nem misturada
com a de outro par. A escolha é excludente (clicar num par troca do outro,
como um seletor de opção) — sempre exatamente duas colunas, e nunca a rolagem
horizontal sem se comparar com nada que a versão de checkboxes livres (até
23/09/2026) deixava acontecer com quatro ou mais marcadas. Uma máquina que não
está em nenhum par definido (nova no banco) não some: vira um par sozinha, no
fim da lista — ver :func:`_montar_pares`.

**O filtro de médico tem DOIS modos, e quem escolhe é o usuário** (o padrão
segue sendo esmaecer — o escolhido pela primeira conversa, em 23/09/2026, e
o segundo pedido veio depois de ver a tela real): **esmaecer** mantém o dia
inteiro da máquina na coluna, com quem não é do médico escolhido apagado; ou
**esconder**, que tira as outras linhas da coluna. Em qualquer um dos dois a
consulta ao banco (ver :mod:`agenda_db`) já trouxe o dia inteiro — o
esconder é um filtro de EXIBIÇÃO, não uma consulta nova, e a contagem do
cabeçalho continua dizendo "3 de 38" para não esconder que a máquina está
cheia o dia inteiro.

**Nada aqui é editável, e não há impressão** — mesma regra da Ficha Virtual:
é consulta do sistema clínico, ponta a ponta.

Dois ajustes de 24/09/2026, depois de ver a tela real de novo (a agenda cheia
de texto do mesmo peso, e depois mais dois recuos no MESMO dia, vendo a
tela de novo cada vez — este módulo tentou mais do que ficou):

**A hora vira crachá — só texto, sem caixa.** Antes hora e nome eram um
texto só; agora a hora é um bloco próprio, largura fixa e negrito (o que se
compara primeiro entre linhas). Teve um FUNDO cinza atrás dela também, e
saiu no mesmo dia: uma caixinha por linha, coluna abaixo, destoava do resto
da tela, que não tem caixa nenhuma.

**O ponto por sítio — duas tentativas, uma fonte que faltava e depois
apareceu.** A primeira (mesmo dia) era uma paleta inventada, e voltou atrás
na hora: sem legenda na tela, "por que este paciente é roxo e aquele é
laranja" não tinha resposta, e o `atividades_achadas` de 24/09 confirmou que
o `variandw` não guarda cor de atividade em tabela nenhuma — não dava para
puxar do banco. A cor de :data:`_CORES_ATIVIDADE` não é palpite: é a que o
usuário já vê no ARIA, ditada de cabeça na conversa — o "porquê" que faltava
antes é a mesma pergunta respondida em outro lugar, não uma pergunta nova.

**A régua ``AGORA`` marca a costura, sem apagar quem já passou.** Só quando
o dia em cena é hoje: uma linha fina com "AGORA · HH:MM" separa o que já
aconteceu do que vem a seguir — nunca no topo nem no fim, onde não diria
nada que a ordem já não dissesse. Esmaecer o texto de quem já passou (o
mesmo cinza do filtro de médico) foi tentado junto e saiu: a coluna inteira
acinzentada, sem ninguém em destaque, lia como tela apagada, não como tela
de quem já foi atendido.

**O resumo do dia** vivia numa faixa própria acima das colunas, com um
cartão por máquina — e o cartão repetia o NOME da máquina que o cabeçalho da
coluna, uma linha abaixo, já mostrava. Saiu em 25/09/2026 ("o nome da
máquina se repete duas vezes na coluna, desnecessário"): o que ele tinha de
único — primeiro "quantas marcações e o maior vão", depois (mesmo dia) o
ACUMULADO DO MÊS — mudou para DENTRO do cabeçalho da própria coluna (ver o
docstring de :class:`_ColunaMaquina`), numa linha própria abaixo do nome.

O acumulado do mês cresceu ao longo do mesmo dia: pacientes tratados,
sessões executadas, a média de frações por paciente e, por fim, a idade
média dos pacientes ("adicione também idade média dos pacientes"; a idade
some da frase, não vira "0 anos", quando ninguém do grupo tem data de
nascimento no cadastro). Pede DUAS consultas novas: pacientes e inícios vêm
do :mod:`agenda_db` (``pacientes_do_mes_por_maquina``, pela agenda —
``DimActivityTransaction``), sessões e idade continuam do
:mod:`tratamento_db` (``FactTreatmentHistory``, frações de fato
entregues) — não estão conferidas contra o banco real por conta própria
ainda (mesma ressalva de ``EmTratamento.inicio``). "Pacientes tratados" foi
redefinido em 25/09/2026, depois de ver "24 tratados" no mês contra "44
pacientes" no dia (mesma máquina, mesmo médico em foco), impossível de o
mês ser menor: "para saber o número de pacientes tratados é só pegar o
número distinto de pacientes agendados na máquina no período" — daí a
troca de fonte. A mesma comparação achou uma SEGUNDA inconsistência: a
contagem do CABEÇALHO do dia nunca respeitava o médico em foco (sempre o
dia inteiro), enquanto o resumo do mês já respeitava — com médico
escolhido, "44" e "24" eram números de populações diferentes, não o mesmo
grupo em dois recortes de tempo. Por isso o cabeçalho do dia (ver
``_ColunaMaquina.definir``) também passou a contar só as marcações do
médico em foco quando há um. Os valores do resumo do mês mudam com o
médico em foco (pedido do mesmo dia: "os valores devem ser atualizados a
depender do filtro de tempo e de médico") — ver
``PainelAgenda.atualizar_resumo_mensal``.

**Máquinas em PARES fixos**, também 24/09/2026: ``6EX``+``TrueBeam``,
``Braquiterapia``+``Dermopan``, ``600CD``+``VitalBeam`` (:data:`PARES_MAQUINA`)
— sempre as duas juntas, nunca uma sozinha nem misturada com a de outro par.
Trocou os checkboxes livres (até três quaisquer, de 23/09) por um seletor
excludente: sempre exatamente duas colunas, mais largas — o que abriu espaço
para o ajuste seguinte.

**Fonte maior, e o rodapé em duas colunas.** Com o par fixo, cada coluna
ficou bem mais larga que os três checkboxes livres de antes deixavam, e o
texto curto sobrava num vão vazio à direita. A fonte subiu (nome 13→15px, crachá 12→13px, rodapé 11→12px) e o rodapé —
antes "registro · sítio · médico"
num texto só — virou DUAS colunas: sítio/registro à esquerda, médico à
direita, sem precisar ler a linha inteira para achar quem é.

**Um segundo ponto, para o STATUS da consulta** — pedido do usuário em
24/09/2026: "considere o status da consulta, coloque indicativo visual das
diferenças". Ao lado do ponto de sítio, em três grupos (:data:`_GRUPOS_STATUS`):
Tratado (azul), Em andamento (amarelo), Aberto (verde) — cobrindo os cinco
estados reais que sobram depois do filtro de ``agenda_db.ESTADOS_FORA``. Cores
ditadas pelo usuário no mesmo dia, não do tema (``st.ACAO`` serve para "verde"
e "azul" ao mesmo tempo — ver ``estilo._APELIDOS`` — e não daria para
distinguir os grupos) nem do ARIA (diferente do sítio, aqui não havia uma cor
real de lá para copiar).

**A legenda dos três status, ao lado dos botões de par de máquina** — pedido
do usuário no mesmo dia, logo depois: o ponto sozinho na linha repetia o
problema que a cor de sítio já teve (cor sem explicação nenhuma na tela). Ver
:meth:`PainelAgenda._criar_legenda_status`.

**Os dois pontos viraram selos, depois de ver a tela real de novo** (mesmo
24/09/2026): o de STATUS virou um RETÂNGULO, maior, na mesma posição de antes
(antes do nome); o de SÍTIO saiu de perto do nome e virou um selo LARGO no
fim da linha, com a PALAVRA do sítio escrita dentro (ex.: "MAMA" em fundo
rosa) — não só a cor, como antes. Largura fixa para todos
(:data:`_LinhaMarcacao._LARGURA_SELO_SITIO`): "CP" e "EXTREMIDADE" ocupam o
mesmo espaço, para a coluna de selos ficar alinhada à direita em toda linha.
A cor do texto dentro do selo (:func:`_texto_sobre`) segue a luminância do
fundo — preto sobre o amarelo do PALIATIVO, branco sobre o roxo da PELE — a
mesma cautela de "texto apagado por cima da cor" que fez o fundo tingido da
linha inteira sair de cena (ver a nota de 25/09/2026, abaixo). O selo do
sítio também ganhou altura da linha inteira (pedido do usuário no mesmo dia:
"aumentar vertical de mama rosa, pra ficar da mesma altura do campo do
nome") — sem alinhamento vertical explícito no ``addWidget``, igual a
``cracha`` e ao nome.

**A legenda virou FILTRO** — pedido do usuário em 24/09/2026: "ao clicar em
Tratado, Em Andamento e Aberto deve aplicar filtro na agenda". Cada selo
(:class:`_SeloLegendaStatus`) é clicável: clicar tira o grupo da vista em
TODAS as colunas (``PainelAgenda._status_escondidos``), com o mesmo "X de N"
no cabeçalho que o modo ESCONDER do médico já usa — SEMPRE esconde, nunca
esmaece (é filtro, não destaque). Clicar de novo traz o grupo de volta.

**A fração TRATADO/TOTAL, e início/previsão de término** — pedido do usuário
em 24/09/2026, em duas partes: primeiro "adicione a fração tratado/total em
agenda na linha do nome paciente", depois "mostrar também data de início e
data prevista de término depois da fração". Este módulo (ver
:class:`_LinhaMarcacao`) só DESENHA o que ``ControleAgenda`` entrega — quem
calcula é o :mod:`tratamento_db` (``EmTratamento``, já usado pela Ficha
Virtual). O dado é EXPERIMENTAL: a lista de frações está atrás do portão
``tratamento_db.LISTA_VERIFICADA_EM``, ainda fechado (ver o docstring de
:mod:`agenda_db`) — por isso só aparece com ``ISOCENTRO_LISTA_EXPERIMENTAL``
ligada. Sem faixa de aviso na tela (tirada em 25/09/2026, a pedido do
usuário: "a gente tá na versão teste, não preciso de aviso").

**O fundo tingido da linha inteira SAIU, em 25/09/2026** — era a cor do
sítio (pedido do usuário em 24/09/2026: "a cor pode pegar toda a linha"),
tingida a 12%. Na tela real, com o tema escuro e o selo do sítio já escrito
por extenso, virou redundância: quase todo tom tingido lia como o mesmo
verde-acinzentado, e "PELVE" (laranja) e "PELE" (roxo) não se distinguiam
pelo fundo. O usuário viu o print e voltou atrás: "não sei se o fundo verde
no nome do paciente... é a melhor layout". :func:`_fundo_linha` agora só
pinta o destaque de médico (:data:`DESTACADO`) — o resto fica transparente,
e quem carrega a cor do sítio é só o selo (:func:`_token_sitio`).

**Intervalo de datas — dia único ainda é o padrão** — pedido do usuário em
25/09/2026: "adicione intervalo de data pra ser possivel ver a agenda de
multiplos dias". Um segundo ``QDateEdit`` ("até", ver
:meth:`PainelAgenda.dia_final_atual`) ao lado do de sempre; enquanto os
dois têm a MESMA data (o estado inicial, e o que "Hoje" sempre repõe), a
tela se comporta como antes — duas colunas, um dia. Só quando "até" fica
DEPOIS de "de" ("período de vários dias") é que:

* a faixa de máquinas troca de PARES fixos (:func:`_montar_pares`) para
  UMA MÁQUINA de cada vez (:func:`_montar_individuais`) — pedido do MESMO
  dia: "ao selecionar multiplos dias deixar somente uma maquina por vez"
  (ver :meth:`PainelAgenda._reconstruir_maquinas_se_o_modo_mudou`);
* a coluna (uma só, na prática) ganha um CABEÇALHO DE DATA
  (:func:`_cabecalho_data`) toda vez que o dia muda dentro da lista —
  decisão do usuário sobre o layout: "uma coluna, dias empilhados", e não
  uma coluna por dia;
* o resumo do MÊS e a fração por paciente (pensados para "o dia em cena")
  somem — ``ControleAgenda._atualizar_periodo`` não os pede.

◄/► andam o INTERVALO inteiro (os dois campos, mesma distância entre eles),
não só o início — ver :meth:`PainelAgenda._andar_dia`. A consulta ao banco
é nova (:func:`agenda_db.agenda_do_periodo`), mas é a MESMA de
``agenda_do_dia`` com o filtro de data trocado por um intervalo — não
conferida contra o banco real por conta própria ainda (mesma ressalva do
resto deste módulo).

**Auto-atualização** — pedido do usuário em 25/09/2026: "o que fazer pra
maquina ficar mais sincronizada (tempo real de tratamento)... ainda delay
longo". A causa principal do atraso é a carga periódica do PRÓPRIO DW, fora
do alcance deste app (ver o comentário de ``gatilho_db.py`` sobre a
"defasagem da carga do DW" — nunca medida por aqui); o que dava para
resolver NESTA tela era o segundo atraso, de cima: com a aba parada e
aberta, o dia só era relido quando alguém trocava data/máquina/médico à
mão. Agora um ``QTimer`` (:data:`_INTERVALO_AUTO_ATUALIZACAO_MS`, 2
minutos) reemite o mesmo ``dia_mudou`` de sempre enquanto a aba está NA
FRENTE (liga em :meth:`PainelAgenda.showEvent`, desliga em
:meth:`PainelAgenda.hideEvent` — ``QStackedWidget`` dispara os dois ao
trocar de aba, sem precisar de nada em :mod:`gui`).
"""
from __future__ import annotations

import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta

from PySide6.QtCore import QDate, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDateEdit,
                             QFrame, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from isocentro.interface import estilo as st
from isocentro.interface import ui
# Reaproveita o seletor de médico da Ficha Virtual — mesmo widget, mesma
# regra (principal + Grupo Médico, mesmo diálogo de marcar quem entra no
# grupo). "Privado" só pelo nome: duplicá-lo aqui seria o mesmo controle em
# dois lugares, e os dois divergindo com o tempo é questão de quando, não se.
from isocentro.interface.tratamento import _SeletorMedicos


def _qdate_de(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _date_de(qd: QDate) -> date:
    return date(qd.year(), qd.month(), qd.day())


def _dia_unico(referencia: date, _deslocamento: int = 0) -> tuple[date, date]:
    """"Hoje" — um atalho de :data:`_ATALHOS_PERIODO` como os outros, só
    que de um dia só (``_deslocamento`` existe para bater a assinatura de
    :func:`_semana`/:func:`_mes`, mas não é usado)."""
    return referencia, referencia


def _semana(referencia: date, deslocamento: int = 0) -> tuple[date, date]:
    """Segunda a domingo (inclusive) da semana de ``referencia``, deslocada
    ``deslocamento`` semanas inteiras (0 = a semana de ``referencia``,
    -1 = a anterior, 1 = a seguinte) — usado pelos atalhos de período do
    combo (:data:`_ATALHOS_PERIODO`)."""
    inicio = (referencia - timedelta(days=referencia.weekday())
             + timedelta(weeks=deslocamento))
    return inicio, inicio + timedelta(days=6)


def _mes(referencia: date, deslocamento: int = 0) -> tuple[date, date]:
    """Primeiro e ÚLTIMO dia (inclusive) do mês de ``referencia``, deslocado
    ``deslocamento`` meses inteiros — mesmos atalhos do combo. Não é
    ``capa_dados.limites_do_mes`` (esse devolve o fim EXCLUSIVO, para
    filtro de SQL; aqui o "até" da tela precisa do último dia de verdade)."""
    mes_total = referencia.month - 1 + deslocamento
    ano = referencia.year + mes_total // 12
    mes = mes_total % 12 + 1
    inicio = date(ano, mes, 1)
    proximo_mes = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    return inicio, proximo_mes - timedelta(days=1)


# Os atalhos do combo único de período — pedido do usuário em 25/09/2026,
# "deixar tudo junto em hoje, os outros periodos mesmo lugar": "Hoje" (que
# antes era um botão à parte) junto com "semana atual, proxima semana,
# semana passada, mes passado, proximo mes", tudo no mesmo controle. Cada
# um já é um PERÍODO pronto (de, até), pela mesma via de
# :meth:`PainelAgenda._definir_periodo` que ◄/► usam — label, a função
# (:func:`_dia_unico`/:func:`_semana`/:func:`_mes`) e o deslocamento.
_ATALHOS_PERIODO: tuple[tuple[str, object, int], ...] = (
    ("Hoje", _dia_unico, 0),
    ("Semana atual", _semana, 0),
    ("Próxima semana", _semana, 1),
    ("Semana passada", _semana, -1),
    ("Mês atual", _mes, 0),
    ("Mês passado", _mes, -1),
    ("Próximo mês", _mes, 1),
)


def _estilo_qdateedit() -> str:
    """A folha do ``QDateEdit`` "de" e, desde 25/09/2026 (intervalo de
    datas, pedido do usuário: "adicione intervalo de data"), também do
    "até" — extraída para os dois campos não poderem divergir de estilo um
    do outro. SEM isto nenhum dos dois teve folha nenhuma — o texto saía na
    cor padrão do Qt, ilegível sobre o fundo escuro do modo noite (achado
    no print de 24/09/2026: dava para ver a moldura da seta do calendário e
    nada mais). O popup do calendário é outra janela, com os próprios
    widgets internos — ``QCalendarWidget`` por dentro —, e também precisa
    da própria receita."""
    return (
        "QDateEdit {"
        f"  background:{st.FUNDO_CAMPO}; color:{st.TEXTO};"
        f"  border:1px solid {st.BORDA_SUAVE}; border-radius:7px;"
        "   padding:6px 9px; font-size:12.5px; }"
        f"QDateEdit:hover {{ border-color:{st.BORDA}; }}"
        f"QDateEdit:focus {{ border:1px solid {st.ACAO};"
        f"  background:{st.FUNDO_CARTAO}; }}"
        "QDateEdit::drop-down { border:none; width:20px; }"
        f"QCalendarWidget QWidget {{ background:{st.FUNDO_BLOCO};"
        f"  color:{st.TEXTO}; }}"
        f"QCalendarWidget QToolButton {{ background:transparent;"
        f"  color:{st.TEXTO}; font-weight:600; }}"
        f"QCalendarWidget QAbstractItemView:enabled {{"
        f"  background:{st.FUNDO_BLOCO}; color:{st.TEXTO};"
        f"  selection-background-color:{st.ACAO};"
        f"  selection-color:{st.SOBRE_ACAO}; }}"
        f"QCalendarWidget QAbstractItemView:disabled {{"
        f"  color:{st.TEXTO_APAGADO}; }}")


# Os três estados de uma linha frente ao filtro de médico. Sem filtro (nada
# escolhido), toda linha é NORMAL — não há "os outros" para comparar com.
NORMAL = "normal"
DESTACADO = "destacado"     # do médico/Grupo Médico escolhido
ESMAECIDO = "esmaecido"     # de outro médico

# Os dois modos de EXIBIÇÃO do filtro — não muda o que se pergunta ao banco,
# só o que a coluna DESENHA com o que já chegou. Escolha do usuário, por
# usuário (``controle_agenda.CHAVE_MODO_DESTAQUE``); o padrão é o esmaecer,
# decidido na primeira conversa sobre esta aba.
MODO_ESMAECER = "esmaecer"
MODO_ESCONDER = "esconder"

# A auto-atualização — pedido do usuário em 25/09/2026: "o que fazer pra
# maquina ficar mais sincronizada (tempo real de tratamento)... ainda delay
# longo". A causa principal do atraso NÃO é esta tela: é a carga periódica
# do DW (``DWH.FactTreatmentHistory``/``DimActivityTransaction``), fora do
# alcance deste código — ver o comentário de ``gatilho_db.py`` sobre a
# "defasagem da carga do DW", nunca medida. O que ESTA tela podia mesmo
# controlar é o outro atraso, de cima: antes, com a aba já aberta, o dia
# só era relido de novo quando alguém trocava data/máquina/médico à mão —
# passar minutos parado na Agenda mostrava uma foto cada vez mais velha.
# 2 minutos: perto o bastante do bloco de 12 minutos da agenda real (uma
# marcação nova nunca fica "invisível" por mais de um sexto do próprio
# intervalo entre marcações) sem reconsultar o banco a cada poucos
# segundos por uma tela que ninguém está olhando de perto o tempo todo.
_INTERVALO_AUTO_ATUALIZACAO_MS = 2 * 60 * 1000

# Os três pares fixos — pedido do usuário em 24/09/2026, pelo NOME de
# exibição (``agenda_db._nome_exibicao``), que é estável; o ``ctrResourceSer``
# não é escrito aqui porque muda de banco para banco. Ordem = ordem dos
# botões na tela.
PARES_MAQUINA: tuple[tuple[str, str], ...] = (
    ("6EX", "TrueBeam"),
    ("Braquiterapia", "Dermopan"),
    ("600CD", "VitalBeam"),
)


def _montar_pares(maquinas: list) -> list:
    """As máquinas de ``maquinas`` (ver ``agenda_db.maquinas``), agrupadas
    pelos :data:`PARES_MAQUINA` — na ORDEM de :data:`PARES_MAQUINA`, cada
    grupo com as :class:`agenda_db.Maquina` que existirem (uma metade do par
    ausente no banco não derruba a outra: o grupo fica com uma só).

    Uma máquina fora dos três pares definidos (nova no banco, ou a lista de
    pares ainda não foi atualizada para ela) não some: vira o SEU PRÓPRIO
    grupo, de uma máquina só, no fim — sumir em silêncio é o erro que este
    módulo não pode cometer (mesmo critério de ``agenda_db.ESTADOS_FORA``).
    """
    por_nome = {m.nome: m for m in maquinas}
    grupos = []
    usadas = set()
    for a, b in PARES_MAQUINA:
        grupo = [por_nome[nome] for nome in (a, b) if nome in por_nome]
        if grupo:
            grupos.append(grupo)
            usadas.update(m.nome for m in grupo)
    for m in maquinas:
        if m.nome not in usadas:
            grupos.append([m])
            usadas.add(m.nome)
    return grupos


def _montar_individuais(maquinas: list) -> list:
    """Cada máquina de ``maquinas`` no SEU PRÓPRIO grupo, na ordem em que
    chegou (a mesma de :func:`agenda_db.maquinas` — alfabética por
    ``MachineId``) — usado em vez de :func:`_montar_pares` quando o
    intervalo de datas tem mais de um dia (pedido do usuário em
    25/09/2026: "ao selecionar multiplos dias deixar somente uma maquina
    por vez"). Mesma forma de retorno (lista de listas) que
    :func:`_montar_pares` — quem consome (``PainelAgenda.definir_maquinas``)
    não precisa saber qual dos dois montou."""
    return [[m] for m in maquinas]


def _rotulo_par(grupo: list) -> str:
    """"6EX + TrueBeam", ou só o nome quando o par ficou incompleto."""
    return " + ".join(m.nome for m in grupo)

# A margem interna de cada linha, dos dois lados.
_MARGEM_LINHA = 8

# Cor por SÍTIO — as cores REAIS do ARIA, ditadas pelo usuário em
# 24/09/2026 (não uma paleta inventada: a primeira tentativa, de cor por
# palpite, voltou atrás no mesmo dia por não ter fonte nenhuma — "por que
# este paciente é roxo e aquele é laranja" não tinha resposta. Esta tem: é a
# MESMA cor que a pessoa já vê no ARIA todo dia, então o "porquê" já é
# conhecido antes de chegar aqui). Um sítio fora desta lista (ou "Horário de
# Planejamento", sem sítio nenhum) cai no cinza do tema — não inventar é a
# regra, mesmo para o que falta.
#
# Hexadecimal cru É a decisão, não o esquecimento que ``test_padrao_
# visual.TestCorDeTela`` pega: paleta CATEGÓRICA externa (do ARIA, não do
# tema), igual nos dois modos — mesmo critério do ``dvh.py``, registrado em
# ``HEX_PERMITIDO``.
_CORES_ATIVIDADE = {
    "ABDOME": "#92603C",       # marrom
    "ABDOMEN": "#92603C",      # marrom (grafia sem acento, vista no banco)
    "CP": "#9CA3AF",           # cinza
    "CRANIO": "#22D3EE",       # ciano
    "EXTREMIDADE": "#4ADE80",  # verde
    "MAMA": "#F472B6",         # rosa
    "PROSTATA": "#60A5FA",     # azul
    "NEUROEIXO": "#6B7B3A",    # marrom-verde
    "PALIATIVO": "#FACC15",    # amarelo
    "PELE": "#A78BFA",         # roxo
    "PELVE": "#FB923C",        # laranja
    "RC": "#2DD4BF",           # verde-azul
    "SBRT": "#D946EF",         # roxo-rosa
    "TORAX": "#F87171",        # vermelho
}


# O status da consulta (``AppointmentStatus`` — ver ``agenda_db.Marcacao.
# estado``), em três grupos visuais — pedido do usuário em 24/09/2026:
# "considere o status da consulta, coloque indicativo visual das diferenças".
# Cobre os cinco estados reais que ficam na agenda depois do filtro de
# ``agenda_db.ESTADOS_FORA`` (ver o docstring de ``agenda_db``) — um estado
# fora dos três grupos (novo no ARIA) não ganha ponto de status, mas a linha
# continua: sumir a MARCAÇÃO por causa de um status desconhecido seria o erro
# silencioso que este módulo evita em outro lugar (:func:`_cor_atividade`).
STATUS_TRATADO = "tratado"
STATUS_EM_ANDAMENTO = "em_andamento"
STATUS_ABERTO = "aberto"

_GRUPOS_STATUS: dict[str, str] = {
    "Completed": STATUS_TRATADO,
    "Manually Completed": STATUS_TRATADO,
    "Pt. CompltFinish": STATUS_TRATADO,
    "In Progress": STATUS_EM_ANDAMENTO,
    "Open": STATUS_ABERTO,
}

# Em hexadecimal cru — não ``st.ACAO``/``st.VERDE``/``st.AZUL``: os três
# apontam para a MESMA cor do tema (ver ``estilo._APELIDOS``), e não dariam
# para distinguir os grupos um do outro. Não é cor do ARIA também (diferente
# de :data:`_CORES_ATIVIDADE`, ditada pelo usuário): são as cores escolhidas
# pelo usuário para esta marca (azul/amarelo/verde, 24/09/2026 — não é a
# ordem de semáforo comum, é a escolha dele). Igual nos dois modos, mesmo
# critério do resto da paleta categórica da tela.
_CORES_STATUS: dict[str, str] = {
    STATUS_TRATADO: "#3B82F6",       # azul
    STATUS_EM_ANDAMENTO: "#FACC15",  # amarelo
    STATUS_ABERTO: "#22C55E",        # verde
}

# O rótulo da legenda, na ORDEM em que aparece ao lado dos botões de par de
# máquina — pedido do usuário em 24/09/2026, com as próprias palavras dele
# ("tratado, em andamento e aberto").
_LEGENDA_STATUS: tuple[tuple[str, str], ...] = (
    (STATUS_TRATADO, "Tratado"),
    (STATUS_EM_ANDAMENTO, "Em andamento"),
    (STATUS_ABERTO, "Aberto"),
)


def _cor_status(estado: str) -> str | None:
    """A cor do ponto de status, pelo grupo de ``estado`` — ``None`` para um
    estado fora dos três grupos conhecidos (:data:`_GRUPOS_STATUS`)."""
    grupo = _GRUPOS_STATUS.get(estado)
    return _CORES_STATUS.get(grupo) if grupo else None


def _normalizar(txt: str) -> str:
    """Maiúsculo e sem acento — "TÓRAX" e "TORAX" são a mesma palavra, venha
    do banco como vier."""
    forma = unicodedata.normalize("NFKD", txt.upper())
    return "".join(c for c in forma if not unicodedata.combining(c))


def _token_sitio(atividade: str) -> str | None:
    """A PALAVRA do sítio dentro de ``atividade`` — nunca por substring: "CP"
    ou "RC" dentro de uma busca por trecho colidiriam com metade do
    vocabulário. ``None`` quando nenhum token bate (atividade sem sítio, ou
    um sítio fora da lista de :data:`_CORES_ATIVIDADE`)."""
    tokens = _normalizar(atividade).split()
    for token in tokens:
        if token in _CORES_ATIVIDADE:
            return token
    return None


def _texto_sobre(hex_cor: str) -> str:
    """Preto ou branco — o que lê melhor em cima de ``hex_cor`` sólida
    (fórmula YIQ, luminância percebida). Existe para o selo do sítio (ver
    :class:`_LinhaMarcacao`): a paleta de :data:`_CORES_ATIVIDADE` mistura
    tons claros (``PALIATIVO`` amarelo, ``EXTREMIDADE`` verde-claro) com
    escuros, e um texto de cor fixa apagaria a palavra em metade deles."""
    h = hex_cor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    yiq = (r * 299 + g * 587 + b * 114) / 1000
    return "#08191A" if yiq >= 150 else "#FFFFFF"


def _texto_contagem(n: int) -> str:
    """"nenhuma marcação" / "1 paciente" / "N pacientes" — usado pelo
    cabeçalho da coluna e pelo resumo do dia, mesma regra nos dois."""
    if not n:
        return "nenhuma marcação"
    return "1 paciente" if n == 1 else f"{n} pacientes"


class _SeloLegendaStatus(QWidget):
    """Ponto + palavra de um grupo de :data:`_LEGENDA_STATUS` — clicável, para
    ENTRAR ou SAIR do filtro de status da agenda. Pedido do usuário em
    24/09/2026: primeiro só a legenda (explicar a cor do ponto de
    :class:`_LinhaMarcacao`), depois "ao clicar em Tratado, Em Andamento e
    Aberto deve aplicar filtro na agenda" — o mesmo selo virou o controle.

    Mesmo gesto de botão do resto do app: aceita no APERTAR, age no SOLTAR
    (ver ``tratamento._ValorClicavel.mousePressEvent``) — soltar fora do selo
    desiste, sem alternar o filtro por engano.
    """

    clicado = Signal()

    def __init__(self, grupo: str, rotulo: str, parent=None):
        super().__init__(parent)
        self.grupo = grupo
        self._rotulo_base = rotulo
        self._cor = _CORES_STATUS[grupo]
        self._ativo = True
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(6)
        self._ponto = QLabel("")
        self._ponto.setFixedSize(9, 9)
        lay.addWidget(self._ponto, 0, Qt.AlignVCenter)
        self._texto = QLabel(rotulo)
        lay.addWidget(self._texto, 0, Qt.AlignVCenter)
        self.definir_ativo(True)

    def definir_contagem(self, n: int) -> None:
        """Quantas marcações do grupo há no que está em cena — pedido do
        usuário em 28/09/2026 ("quais outras... indicadores"): a legenda já
        filtrava por status, faltava dizer QUANTOS há antes de decidir
        esconder um grupo. Chamado por
        :meth:`PainelAgenda._atualizar_contagem_status`, nunca daqui — o
        selo não sabe contar sozinho, só mostrar o número que chega."""
        self._texto.setText(f"{self._rotulo_base} — {n}")

    def definir_ativo(self, ativo: bool) -> None:
        """``ativo`` = o status ENTRA na agenda (o padrão); apagado = o
        usuário tirou este grupo da vista — mesma opacidade-como-sinal de
        ``tratamento._ValorClicavel.definir_ativo``, e não um "desabilitado"
        de verdade: o selo continua clicável para trazer o grupo de volta."""
        self._ativo = ativo
        st.pintar(self._ponto, lambda: (
            f"border-radius:5px;"
            f" background:{self._cor if ativo else st.TEXTO_APAGADO};"))
        st.pintar(self._texto, lambda: (
            f"color:{st.TEXTO_FRACO if ativo else st.TEXTO_APAGADO};"
            " font-size:11.5px;"))

    def mousePressEvent(self, e):  # noqa: N802 - assinatura do Qt
        e.accept()

    def mouseReleaseEvent(self, e):  # noqa: N802 - assinatura do Qt
        if self.rect().contains(e.pos()):
            self.clicado.emit()
        else:
            super().mouseReleaseEvent(e)


# Vão mínimo entre duas marcações VISÍVEIS e CONSECUTIVAS, na mesma coluna e
# no mesmo dia, para ganhar a marca de "vaga" (:func:`_linha_vaga`) — pedido
# do usuário em 28/09/2026 ("quais outras... indicadores"): a máquina livre
# por um tempo comprido é tão relevante quanto quem já está marcado, para
# quem decide encaixar uma remarcação. 30 min (bem acima dos 12 min de bloco
# medidos no docstring do módulo, ver ``agenda_db``) para não marcar toda
# folga normal entre pacientes como se fosse um buraco na agenda.
_VAGA_MINIMA = timedelta(minutes=30)


def _linha_vaga(vao: timedelta) -> QWidget:
    """A marca "Xh Ymin livre" entre duas marcações da MESMA coluna e do
    MESMO dia, quando o vão passa de :data:`_VAGA_MINIMA` — só entra em
    :meth:`_ColunaMaquina.definir` entre duas linhas que estão as DUAS
    visíveis (nunca através de uma marcação escondida pelo filtro de
    médico/status: essa continua ocupando a máquina de verdade, e mostrar
    "vaga" ali seria inventar tempo livre que não existe)."""
    minutos_totais = int(vao.total_seconds() // 60)
    horas, minutos = divmod(minutos_totais, 60)
    if horas and minutos:
        texto = f"{horas}h{minutos:02d}min livre"
    elif horas:
        texto = f"{horas}h livre"
    else:
        texto = f"{minutos}min livre"
    linha = QWidget()
    lay = QHBoxLayout(linha)
    lay.setContentsMargins(_MARGEM_LINHA, 2, _MARGEM_LINHA, 2)
    rotulo = QLabel(f"···  {texto}  ···")
    rotulo.setAlignment(Qt.AlignCenter)
    st.pintar(rotulo, lambda: (
        f"color:{st.TEXTO_APAGADO}; font-size:10.5px; font-style:italic;"))
    lay.addWidget(rotulo)
    return linha


def _linha_agora(agora: datetime) -> QWidget:
    """A régua "AGORA · HH:MM" que separa quem já passou de quem vem a
    seguir. Só nasce dentro de :meth:`_ColunaMaquina.definir`, e só quando
    há pelo menos uma marcação dos dois lados — no topo ou no fim da coluna
    ela não diria nada que a própria ordem já não dissesse."""
    linha = QWidget()
    lay = QHBoxLayout(linha)
    lay.setContentsMargins(_MARGEM_LINHA, 4, _MARGEM_LINHA, 4)
    lay.setSpacing(8)

    def _traco() -> QFrame:
        t = QFrame()
        t.setFixedHeight(1)
        st.pintar(t, lambda: f"background:{st.ACAO_LINHA}; border:none;")
        return t

    lay.addWidget(_traco(), 1)
    rotulo = QLabel(f"AGORA · {agora:%H:%M}")
    st.pintar(rotulo, lambda: (
        f"color:{st.ACAO}; font-size:10px; font-weight:700;"
        " letter-spacing:0.6px;"))
    lay.addWidget(rotulo, 0)
    lay.addWidget(_traco(), 1)
    return linha


# Nome do dia da semana por extenso, em português — hardcoded, não
# ``strftime("%A")``: esse depende do LOCALE do sistema onde o app roda, e
# viraria inglês (ou erro) numa instalação sem locale pt-BR configurado. A
# mesma cautela de :data:`_CORES_ATIVIDADE`, que também não confia em nada
# fora do controle do módulo para um texto que a pessoa vai ler.
_DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira",
               "quinta-feira", "sexta-feira", "sábado", "domingo")


def _cabecalho_data(dia: date) -> QWidget:
    """O separador de DIA dentro da coluna, quando o intervalo em cena tem
    mais de um dia (:attr:`_ColunaMaquina._multiplos_dias`) — pedido do
    usuário em 25/09/2026: "adicione intervalo de data pra ser possivel
    ver a agenda de multiplos dias". UMA coluna, dias empilhados (decisão
    do usuário) — não uma coluna por dia."""
    linha = QWidget()
    lay = QVBoxLayout(linha)
    lay.setContentsMargins(_MARGEM_LINHA, 14, _MARGEM_LINHA, 4)
    lay.setSpacing(4)
    rotulo = QLabel(f"{_DIAS_SEMANA[dia.weekday()]}, {dia:%d/%m/%Y}".upper())
    st.pintar(rotulo, lambda: (
        f"color:{st.TEXTO}; font-size:11px; font-weight:700;"
        " letter-spacing:0.6px;"))
    lay.addWidget(rotulo)
    traco = QFrame()
    traco.setFixedHeight(1)
    st.pintar(traco, lambda: f"background:{st.BORDA}; border:none;")
    lay.addWidget(traco)
    return linha


class _LinhaMarcacao(QWidget):
    """Uma marcação: hora, paciente, sítio, médico — duas linhas de texto.

    ``destaque`` é a marca do filtro de médico (ver o docstring do módulo):
    :data:`DESTACADO` colore o nome (é o médico escolhido), :data:`ESMAECIDO`
    apaga o texto (é de outro médico) — a linha continua lá, com a mesma
    altura: sumir mudaria quantos "buracos" a coluna mostra, e é justamente a
    ocupação da máquina que a coluna existe para dizer. Pedido do usuário em
    23/09/2026, depois de ver a agenda real: destacar quem é do médico é tão
    importante quanto apagar quem não é.

    O texto que não cabe na largura da coluna termina em reticências
    (``…``) e o inteiro vai no ``tooltip`` — a largura é a REAL, que muda com a
    janela (ver :class:`_RotuloElidido`), e não um número calculado antes.

    ``fracao``: ``(entregues, previstas, inicio, previsao_fim)`` — pedido do
    usuário em 24/09/2026: primeiro "adicione a fração tratado/total em
    agenda na linha do nome paciente", depois "mostrar também data de início
    e data prevista de término depois da fração". ``inicio``/``previsao_fim``
    são ``date | None`` (podem faltar mesmo com fração presente). ``None`` no
    lugar da tupla inteira quando não há NENHUM dado — nunca "0/0" inventado.
    Vem do :mod:`tratamento_db`, atrás do portão ``LISTA_VERIFICADA_EM``
    (ainda fechado, ver o docstring do módulo): só chega até aqui no modo
    EXPERIMENTAL.

    Fica na linha do NOME, antes do selo do sítio — uma terceira linha
    própria foi tentada em 25/09/2026 e voltou atrás no mesmo dia: "o outro
    de antes tava melhor".
    """

    _ALTURA = 50
    # Teto da largura do BLOCO DO SÍTIO (rodapé) — ver o comentário junto de
    # ``sitio_bloco`` no ``__init__``. O médico não tem teto: aparece por
    # INTEIRO sempre, pedido do usuário em 24/09/2026.
    _LARGURA_MAXIMA_SITIO = 260
    # Largura FIXA do selo do sítio, no fim da linha do topo (ver o mesmo
    # ``__init__``) — pedido do usuário em 24/09/2026: "esse campo de mesmo
    # tamanho pra todos, se mama ou extremidade". Cabe "EXTREMIDADE", a
    # palavra mais longa de :data:`_CORES_ATIVIDADE`, sem cortar.
    _LARGURA_SELO_SITIO = 116

    def __init__(self, m, destaque: str, fracao: tuple | None = None,
                parent=None):
        super().__init__(parent)
        self.marcacao = m
        self.destaque = destaque
        self.setFixedHeight(self._ALTURA)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(_MARGEM_LINHA, 4, _MARGEM_LINHA, 4)
        lay.setSpacing(2)

        # A hora vira um cracha PRÓPRIO, separado do nome — antes as duas
        # eram um texto só ("08:00  Fulano"), e a hora não tinha mais peso
        # visual que o resto da linha; numa coluna de quarenta é a primeira
        # coisa que se procura ao comparar horários.
        topo_linha = QHBoxLayout()
        topo_linha.setContentsMargins(0, 0, 0, 0)
        topo_linha.setSpacing(6)

        hora_txt = m.hora.strftime("%H:%M") if m.hora else "--:--"
        cracha = QLabel(hora_txt)
        cracha.setFixedWidth(48)
        cracha.setAlignment(Qt.AlignCenter)
        topo_linha.addWidget(cracha)

        # O selo de STATUS (ver :data:`_CORES_STATUS`) — um RETÂNGULO, ao
        # lado da hora, antes do nome. Pedido do usuário em 24/09/2026, ao
        # ver a tela real: "o quadrado do status pode ficar um retângulo
        # maior ocupando do lado antes do nome" — mesma posição de antes
        # (era um ponto redondo 9×9), só maior e sem o arredondado de
        # círculo.
        cor_status = _cor_status(m.estado)
        selo_status = QLabel("")
        selo_status.setFixedSize(18, 10)
        topo_linha.addWidget(selo_status, 0, Qt.AlignVCenter)

        self._topo_txt = f"{hora_txt}  {m.paciente}"
        topo = _RotuloElidido(m.paciente)
        topo_linha.addWidget(topo, 1)

        # A fração TRATADO/TOTAL, e depois dela início/previsão de término
        # (ver o docstring da classe) — um texto SÓ, não selos separados.
        # Só aparece quando HÁ o dado; sem fração nenhuma linha reserva
        # espaço para ela, diferente do selo do sítio (que é sempre a mesma
        # pergunta, "qual sítio", e por isso sempre tem largura).
        selo_fracao = None
        if fracao is not None:
            entregues, previstas, inicio, previsao_fim = fracao
            # Sem frações PREVISTAS cadastradas não há fração a mostrar —
            # "5/0" seria o mesmo número inventado que "0/0".
            partes = [f"{entregues}/{previstas}"] if previstas else []
            # "1ª sessão" — pedido do usuário em 28/09/2026 ("quais
            # outras... indicadores"): quem está no dia 1 do curso pede mais
            # atenção (explicação, ansiedade, tempo) do que quem já é rotina
            # — mesmo dado da fração, já calculado, só faltava dizer.
            # ``entregues`` conta sessões JÁ FEITAS: antes da primeira é 0, e
            # depois dela o curso começou no próprio dia da marcação. Testar
            # ``entregues == 1`` punha o aviso no dia da SEGUNDA sessão.
            dia_marcacao = m.hora.date() if m.hora else None
            if entregues == 0 or (inicio and inicio == dia_marcacao):
                partes.append("1ª sessão")
            if inicio:
                partes.append(f"início {inicio:%d/%m}")
            if previsao_fim:
                partes.append(f"previsão {previsao_fim:%d/%m}")
            if partes:
                selo_fracao = QLabel("   ·   ".join(partes))
                topo_linha.addWidget(selo_fracao, 0, Qt.AlignVCenter)

        # O selo do SÍTIO — antes um ponto colorido ao lado do nome, agora um
        # selo LARGO no fim da linha, com a palavra escrita dentro. Pedido do
        # usuário no mesmo dia: "a cor do tipo da consulta, por exemplo mama
        # rosa, deve ficar grande... ficaria rosa dentro escrito mama, esse
        # campo de mesmo tamanho pra todos, se mama ou extremidade" — largura
        # FIXA (:data:`_LARGURA_SELO_SITIO`), igual para "CP" e para
        # "EXTREMIDADE". Sem sítio reconhecido, o selo fica sem cor e sem
        # texto (nunca inventar), mas reserva a MESMA largura — as linhas da
        # coluna continuam alinhadas à direita, tenham selo cheio ou não.
        token_sitio = _token_sitio(m.atividade)
        cor_sitio = _CORES_ATIVIDADE.get(token_sitio) if token_sitio else None
        selo_sitio = QLabel(token_sitio or "")
        selo_sitio.setFixedWidth(self._LARGURA_SELO_SITIO)
        selo_sitio.setAlignment(Qt.AlignCenter)
        # SEM alinhamento vertical explícito aqui (diferente do
        # ``selo_status``) — pedido do usuário em 24/09/2026, "aumentar
        # vertical de mama rosa, pra ficar da mesma altura do campo do
        # nome": sem ``Qt.AlignVCenter``, o ``QHBoxLayout`` estica o selo até
        # a altura da LINHA (a mesma altura de ``topo`` e ``cracha``) em vez
        # de usar só o ``sizeHint`` do texto.
        topo_linha.addWidget(selo_sitio, 0)
        lay.addLayout(topo_linha)

        # O rodapé tem sítio/registro à esquerda, médico à direita — em vez
        # de um texto corrido com pontos. O SÍTIO tem teto de largura (o
        # texto é curto e padronizado — "9000011CEL · PELVE" — e sem teto um
        # nome curto deixava um vão vazio enorme até o médico, lendo como
        # duas colunas soltas: achado no print de 24/09/2026). O MÉDICO não
        # tem teto nenhum: aparece por INTEIRO sempre, pedido do usuário no
        # mesmo dia — por isso é ``QLabel`` comum, não ``_RotuloElidido``:
        # não corta, não precisa de largura que o layout decida.
        self._rodape_txt = f"{m.registro} · {m.atividade}"
        # "sem médico vinculado" — pedido do usuário em 28/09/2026 ("quais
        # outras... indicadores"): antes o rodapé ficava mudo quando
        # ``agenda_db`` não achava nenhum ``DimPatientDoctor`` com
        # ``OncologistFlag=1`` para o paciente — o mesmo vazio de "a coluna
        # não veio", mas aqui É dado (a consulta respondeu, só não achou
        # vínculo), então vira aviso em vez de espaço em branco.
        sem_medico = not m.medico
        if m.medico:
            medico_txt = m.medico + (" (+1)" if m.mais_de_um_medico else "")
        else:
            medico_txt = "sem médico vinculado"
        self._rodape_txt += f" · {medico_txt}"

        # ``sitio_bloco`` SEM ``layout.setAlignment`` — alinhamento explícito
        # troca "esticar até o teto" por "usar só o sizeHint", e o sizeHint
        # de um rótulo ``Ignored`` é quase zero (medido com uma sonda depois
        # de quebrar isto uma vez: o bloco caiu do teto para 80px e o texto
        # sumiu). SEM alinhamento nenhum, o ``QHBoxLayout`` estica o bloco
        # até o teto sozinho.
        sitio_bloco = QWidget()
        sitio_bloco.setMaximumWidth(self._LARGURA_MAXIMA_SITIO)
        sitio_lay = QHBoxLayout(sitio_bloco)
        sitio_lay.setContentsMargins(0, 0, 0, 0)
        rodape = _RotuloElidido(f"{m.registro} · {m.atividade}")
        sitio_lay.addWidget(rodape, 1)

        rodape_medico = QLabel(medico_txt)
        # Tooltip de reserva — o médico não tem ``_RotuloElidido`` (ver o
        # comentário acima: aparece por INTEIRO, de propósito), mas numa
        # coluna estreita o ``QHBoxLayout`` ainda pode espremer o rótulo
        # abaixo do seu ``sizeHint`` e cortar o texto sem aviso nenhum; o
        # hover recupera o nome completo, mesmo padrão do resto da linha.
        rodape_medico.setToolTip(medico_txt)

        rodape_linha = QHBoxLayout()
        rodape_linha.setContentsMargins(0, 0, 0, 0)
        rodape_linha.setSpacing(14)
        rodape_linha.addWidget(sitio_bloco)
        rodape_linha.addWidget(rodape_medico)
        rodape_linha.addStretch(1)
        lay.addLayout(rodape_linha)

        self.topo, self.rodape, self.rodape_medico = topo, rodape, rodape_medico
        topo.corte_mudou.connect(self._atualizar_tooltip)
        rodape.corte_mudou.connect(self._atualizar_tooltip)

        # As cores ficam DENTRO da lambda (não numa variável pré-resolvida):
        # ``st.TEXTO``/``st.TEXTO_APAGADO``/``st.ACAO`` são reescritos na troca
        # dia↔noite, e uma variável local congelaria a cor do instante em que a
        # linha nasceu — a mesma armadilha que o comentário de ``estilo.pintar``
        # avisa.
        def _cor_hora(d=destaque):
            return st.TEXTO_APAGADO if d == ESMAECIDO else st.TEXTO_FRACO

        # ESMAECIDO no NOME usava ``TEXTO_APAGADO`` — o mesmo tom do rodapé,
        # achatado demais numa coluna inteira sem ninguém destacado (achado
        # no print de 24/09/2026: lia como tela apagada, não como "outro
        # médico"). O nome, que é a informação PRINCIPAL da linha, recua só
        # um degrau (``TEXTO_FRACO``, o mesmo do rodapé normal); o rodapé
        # esmaecido continua no ``TEXTO_APAGADO``, um degrau a mais — os dois
        # juntos ainda leem "menos importante" sem ficar ilegíveis.
        def _cor_topo(d=destaque):
            if d == DESTACADO:
                return st.ACAO
            if d == ESMAECIDO:
                return st.TEXTO_FRACO
            return st.TEXTO

        def _cor_rodape(d=destaque):
            if d == DESTACADO:
                return st.ACAO_CLARA
            if d == ESMAECIDO:
                return st.TEXTO_APAGADO
            return st.TEXTO_FRACO

        # ``font-weight:700`` na linha inteira, e não só na hora: o
        # ``<b>`` de antes era HTML dentro do QLabel, e ``elidedText`` não
        # sabe cortar rich text no meio da tag sem quebrá-la — corta o texto
        # PURO e pinta a linha toda em negrito, que já era o efeito
        # dominante (a hora + o nome são o que se lê primeiro na varredura).
        # SEM fundo próprio: uma caixa cinza em CADA linha, coluna abaixo,
        # destoava do resto da tela (achado no print de 24/09/2026) — a
        # largura fixa e o negrito já bastam para a hora se comparar rápido.
        st.pintar(cracha, lambda: (
            f"color:{_cor_hora()}; font-size:13px; font-weight:700;"))
        st.pintar(selo_status, lambda cor=cor_status: (
            f"border-radius:2px; background:{cor or 'transparent'};"))
        if selo_fracao is not None:
            # Cor SUBORDINADA (``TEXTO_FRACO``), de propósito: é dado
            # experimental (ver o docstring da classe), não fato conferido
            # como a hora ou o nome — não compete por atenção com eles.
            st.pintar(selo_fracao, lambda: (
                f"color:{st.TEXTO_FRACO}; font-size:12px; font-weight:700;"))
        st.pintar(selo_sitio, lambda cor=cor_sitio: (
            f"border-radius:4px; background:{cor or 'transparent'};"
            f" color:{_texto_sobre(cor) if cor else st.TEXTO_FRACO};"
            " font-size:10px; font-weight:700; letter-spacing:0.3px;"))
        st.pintar(topo, lambda: (
            f"color:{_cor_topo()}; font-size:15px; font-weight:700;"))
        st.pintar(rodape, lambda: f"color:{_cor_rodape()}; font-size:12px;")

        # "sem médico vinculado" fica VERMELHO — mas só quando a linha não
        # está ESMAECIDA (outro médico em foco): esmaecida ela já está
        # recuando de propósito, e um vermelho por cima brigaria com o
        # próprio recuo (mesma armadilha do comentário de ``_cor_topo``).
        def _cor_medico(d=destaque, sem=sem_medico):
            if sem and d != ESMAECIDO:
                return st.VERMELHO
            return _cor_rodape(d)

        st.pintar(rodape_medico, lambda: f"color:{_cor_medico()}; font-size:12px;")
        # O fundo da linha INTEIRA — só o destaque de médico usa (é do médico
        # escolhido: "este é meu paciente" merece um fundo, o resto não). A
        # cor do sítio tingindo a linha inteira (pedido do usuário em
        # 24/09/2026) voltou atrás em 25/09/2026: com o selo do sítio já
        # escrevendo a palavra (ver o docstring da classe), o fundo virou
        # redundância — e no tema escuro, quase todo tom tingido a 12% lê
        # como o mesmo verde-acinzentado (achado no print de 25/09/2026:
        # "não sei se o fundo verde... é a melhor layout").
        def _fundo_linha(d=destaque):
            return st.ACAO_FUNDO if d == DESTACADO else "transparent"

        st.pintar(self, lambda: (
            f"background:{_fundo_linha()};"
            f" border-bottom:1px solid {st.BORDA_SUAVE};"))

    def _atualizar_tooltip(self) -> None:
        """O texto inteiro, só enquanto sítio ou nome estão cortados — o
        médico não corta mais (aparece por inteiro sempre), e tooltip em
        linha que cabe é ruído."""
        if self.topo.cortado() or self.rodape.cortado():
            self.setToolTip(f"{self._topo_txt}\n{self._rodape_txt}")
        else:
            self.setToolTip("")


class _RotuloElidido(QLabel):
    """Um ``QLabel`` que corta o texto com "…" na largura que TEM agora.

    Existe porque as colunas dividem a largura da aba entre si (ver
    :class:`_ColunaMaquina`): a largura de cada uma muda com a janela e com
    quantas máquinas estão marcadas, então o corte não pode ser calculado uma
    vez, na criação, contra um número fixo — foi o que a versão de 480px
    fazia, e deixava uma faixa vazia à direita da tela.

    A política de tamanho é ``Ignored`` na horizontal: o texto inteiro não
    empurra a coluna para mais larga, quem manda é o layout. A fonte medida é
    a do próprio widget, DEPOIS do estilo aplicado (``ensurePolished``) — não
    uma fonte reconstruída à mão, que divergia da desenhada (pontos × pixels)
    e, no ``offscreen``, mede o dobro da real do Windows (ver ARMADILHAS.md).
    """

    corte_mudou = Signal()

    def __init__(self, texto: str, parent=None):
        super().__init__(parent)
        self._completo = texto
        self._cortado = False
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.setText(texto)

    def texto_completo(self) -> str:
        return self._completo

    def cortado(self) -> bool:
        return self._cortado

    def resizeEvent(self, ev) -> None:  # noqa: N802 - assinatura do Qt
        super().resizeEvent(ev)
        self._reelidir()

    def _reelidir(self) -> None:
        largura = self.width()
        if largura <= 0:
            return
        self.ensurePolished()
        mostrado = QFontMetrics(self.font()).elidedText(
            self._completo, Qt.ElideRight, largura)
        if mostrado != self.text():
            self.setText(mostrado)
        cortado = mostrado != self._completo
        if cortado != self._cortado:
            self._cortado = cortado
            self.corte_mudou.emit()


class _ColunaMaquina(QWidget):
    """Uma máquina: o nome no topo, a contagem, e as marcações do dia.

    SEM largura própria (pedido do usuário em 23/09/2026: "as colunas
    precisam ser fixas e ocupar todo o espaço"): cada coluna entra no layout
    com o mesmo fator de esticar, então as colunas marcadas dividem a largura
    inteira da aba igualmente — uma, duas ou três, sem faixa vazia sobrando.
    Antes eram 480px fixos, e com três máquinas sobrava um vão à direita. O
    mínimo garante que uma janela estreita não esmague o texto.
    """

    # Subiu de 280 para 340 em 24/09/2026 junto com a fonte maior e o rodapé
    # em duas colunas: o crachá da hora (48px) mais o mínimo do médico à
    # direita (70px) já somam boa parte de 280px sem sobrar nada para o
    # nome do meio.
    _LARGURA_MINIMA = 340

    def __init__(self, nome: str, resumo_mes: tuple | None = None,
                multiplos_dias: bool = False, parent=None):
        super().__init__(parent)
        self.nome = nome
        self._marcacoes: list = []
        # Separa as marcações por DIA, com um cabeçalho entre um dia e o
        # próximo (ver :func:`_cabecalho_data`, chamado por :meth:`definir`)
        # — pedido do usuário em 25/09/2026, "adicione intervalo de data
        # pra ser possivel ver a agenda de multiplos dias". Fixo na
        # construção (não muda coluna já criada): quem decide isso é
        # ``PainelAgenda.mostrar_agenda``, uma vez por consulta.
        self._multiplos_dias = multiplos_dias
        self.setMinimumWidth(self._LARGURA_MINIMA)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        cabecalho = QWidget()
        cab_lay = QVBoxLayout(cabecalho)
        cab_lay.setContentsMargins(10, 8, 10, 6)
        # Espaço entre as linhas — era 0 entre nome e contagem (achado no
        # print de 25/09/2026: "aperto desnecessário" entre os dois). 3px é
        # o mesmo respiro que outros pares rótulo/valor do app já usam.
        cab_lay.setSpacing(3)

        # Nome da máquina e a contagem de HOJE, na MESMA linha — os dois
        # falam do dia em cena. O acumulado do MÊS (ver
        # :meth:`definir_resumo_mensal`) foi para uma linha PRÓPRIA, embaixo,
        # em vez de dividir esta com o nome: pedido do usuário em 25/09/2026,
        # depois de ver o texto do mês flutuando longe, à direita do nome,
        # num vão enorme e desproporcional ("ainda dá pra melhorar esse
        # layout").
        topo_cabecalho = QHBoxLayout()
        topo_cabecalho.setContentsMargins(0, 0, 0, 0)
        topo_cabecalho.setSpacing(10)
        self.rotulo_nome = QLabel(nome)
        st.pintar(self.rotulo_nome, lambda: (
            f"color:{st.TEXTO}; font-size:19px; font-weight:700;"))
        topo_cabecalho.addWidget(self.rotulo_nome)
        topo_cabecalho.addStretch(1)
        self.rotulo_contagem = QLabel("")
        st.pintar(self.rotulo_contagem, lambda: (
            f"color:{st.TEXTO_FRACO}; font-size:14px;"))
        topo_cabecalho.addWidget(self.rotulo_contagem, 0, Qt.AlignVCenter)
        cab_lay.addLayout(topo_cabecalho)

        # O acumulado do MÊS: pacientes tratados, sessões executadas e a
        # média de frações por paciente — pedido do usuário em 25/09/2026,
        # "adicione também o número médio de frações de cada máquina".
        # Nasce ESCONDIDO (nem ``resumo_mes`` chega sempre pronto na
        # criação) e criado sempre, mesmo sem dado: o médico em foco muda
        # QUEM entra nesta conta ("os valores devem ser atualizados a
        # depender do filtro de tempo e de médico", mesmo pedido), e só dá
        # para trocar depois se o rótulo já existir — ver
        # :meth:`definir_resumo_mensal`, chamado por
        # ``PainelAgenda.atualizar_resumo_mensal`` sempre que o médico muda.
        self.rotulo_mes = QLabel("")
        self.rotulo_mes.setWordWrap(True)
        st.pintar(self.rotulo_mes, lambda: f"color:{st.TEXTO_FRACO}; font-size:11px;")
        self.rotulo_mes.setVisible(False)
        cab_lay.addWidget(self.rotulo_mes)

        st.pintar(cabecalho, lambda: (
            f"background:{st.FUNDO_BLOCO}; border-bottom:2px solid {st.BORDA};"))
        lay.addWidget(cabecalho)
        self.definir_resumo_mensal(resumo_mes)

        self._rolagem = QScrollArea()
        self._rolagem.setWidgetResizable(True)
        self._rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        st.pintar(self._rolagem, lambda: "border:none;")
        self._corpo = QWidget()
        self._corpo_lay = QVBoxLayout(self._corpo)
        self._corpo_lay.setContentsMargins(0, 0, 0, 0)
        self._corpo_lay.setSpacing(0)
        self._corpo_lay.addStretch(1)
        self._rolagem.setWidget(self._corpo)
        st.pintar(self._corpo, lambda: f"background:{st.FUNDO_CARTAO};")
        lay.addWidget(self._rolagem, 1)
        st.pintar(self, lambda: (
            f"background:{st.FUNDO_CARTAO}; border-right:1px solid {st.BORDA};"))

    def definir_resumo_mensal(self, resumo_mes: tuple | None) -> None:
        """Atualiza o acumulado do mês (rótulo abaixo do nome) — chamado na
        criação e de novo por ``PainelAgenda.atualizar_resumo_mensal`` sempre
        que o médico em foco muda, porque é o médico que decide QUEM entra
        nesta conta (pedido do usuário em 25/09/2026).

        ``resumo_mes``: ``(pacientes, inicios, sessoes, idade_media,
        fracoes_previstas_media, taxa_ocupacao, indice_disponibilidade)`` do
        mês, ou ``None`` — aí o rótulo fica escondido, nunca com um "0 · 0"
        inventado. ``idade_media`` e ``fracoes_previstas_media`` são
        ``float | None`` (ver ``tratamento_db.resumo_mensal_por_maquina``):
        sem cadastro de nascimento, ou sem ``FractionsPlanned``, em ninguém
        do grupo, a parte correspondente some da frase em vez de virar "0".
        ``inicios`` vem de ``agenda_db.pacientes_do_mes_por_maquina`` (pedido
        do usuário em 25/09/2026: "inicios (numero de atividades que
        contenham INICIO)").

        ``taxa_ocupacao``/``indice_disponibilidade`` — pedido do usuário em
        28/09/2026 — são ``float | None`` (fração 0–1, ver
        ``ControleAgenda._resumo_mensal``): ``None`` some da frase, tanto
        para uma máquina sem horário cadastrado quanto (só o segundo) com o
        portão ``agenda_db.MINUTOS_PARADA_VERIFICADO_EM`` fechado.

        ``fracoes_previstas_media`` — a "frações/paciente" da frase — NÃO é
        mais ``sessoes / pacientes`` calculado aqui: pedido do usuário em
        25/09/2026, "esse fracoes/paciente ta correto? o numero de fracoes
        no 6ex costuma ser maior". Aquela conta misturava sessões
        ENTREGUES até hoje com pacientes AGENDADOS o mês inteiro (inclusive
        dias futuros), e ficava baixa demais no meio do mês. O conceito
        certo, do usuário: a média de quanto o CURSO INTEIRO de cada
        paciente prevê — "o numero medio de fracoes eh importante pra ver
        ocupacao da maquina" —, já pronta vinda do banco (ver
        ``tratamento_db._SQL_FRACOES_PREVISTAS_MAQUINA``).
        """
        if resumo_mes is None:
            self.rotulo_mes.setVisible(False)
            return
        (pacientes_mes, inicios_mes, sessoes_mes, idade_media,
        fracoes_previstas_media, taxa_ocupacao,
        indice_disponibilidade) = resumo_mes
        # Texto CURTO — "Mês: tratados, inícios, sessões, frações/paciente,
        # anos" — pedido do usuário em 25/09/2026, depois de ver a frase
        # cheia: "tá muito texto, podia ser algo mais simples". "Tratados no
        # mês", e não "em tratamento": tentativa no mesmo dia, e voltou
        # atrás na hora — "em tratamento" lê como SÓ quem ainda não
        # terminou, e a conta sempre incluiu os DOIS grupos: "quero os
        # tratados no mês (inclui os que terminaram esse mês e os que estão
        # em tratamento)". A CONTA nunca mudou (ver
        # ``agenda_db._SQL_RESUMO_MES``: quem teve QUALQUER marcação no mês
        # entra, concluído ou não) — só a palavra foi e voltou.
        partes = [f"{pacientes_mes} tratados", f"{inicios_mes} inícios",
                 f"{sessoes_mes} sessões"]
        if fracoes_previstas_media is not None:
            media_txt = f"{fracoes_previstas_media:.1f}".replace(".", ",")
            partes.append(f"{media_txt} frações/paciente")
        if idade_media is not None:
            partes.append(f"{idade_media:.0f} anos")
        if taxa_ocupacao is not None:
            partes.append(f"{taxa_ocupacao:.0%} ocupação".replace(".", ","))
        if indice_disponibilidade is not None:
            partes.append(
                f"{indice_disponibilidade:.0%} disponibilidade".replace(".", ","))
        self.rotulo_mes.setText("Mês: " + ", ".join(partes))
        self.rotulo_mes.setVisible(True)

    def definir(self, marcacoes: list, medicos_em_foco,
               modo: str = MODO_ESMAECER, agora: datetime | None = None,
               status_escondidos: frozenset = frozenset(),
               fracoes: dict | None = None) -> None:
        """Repõe as linhas.

        ``marcacoes`` é sempre a lista INTEIRA do dia — quem chama nunca
        filtra antes de entregar (ver ``PainelAgenda.marcacoes()``, que
        devolve o que esta coluna guardou aqui, para o próximo repaint local
        continuar partindo do dia completo, mesmo depois de um ciclo no modo
        ESCONDER).

        ``medicos_em_foco``: nomes BRUTOS, ou vazio/``None`` para "sem
        filtro" — aí toda linha fica :data:`NORMAL` e ``modo`` não importa.

        ``modo``: :data:`MODO_ESMAECER` (o dia inteiro fica na coluna, quem
        não é do médico escolhido perde contraste, mas a CONTAGEM do
        cabeçalho é a do dia inteiro) ou :data:`MODO_ESCONDER` — "Só os
        meus" MARCADO — (só as linhas do médico aparecem, e a contagem
        conta só elas). Pedido do usuário em 25/09/2026, em duas voltas:
        primeiro "24 tratados" no resumo do mês (que já respeita o médico
        em foco) ao lado de "44 pacientes" no cabeçalho do dia (que nunca
        respeitava, em nenhum dos dois modos) pareceu inconsistente; a
        contagem passou a filtrar por médico sempre que ele estava em
        foco — e aí, com "Só os meus" DESMARCADO, ela caiu para números bem
        menores que o esperado mesmo sem o usuário ter pedido filtro
        nenhum: "se nao tiver ticado somente os meus deve mostrar agenda
        completa". Por isso o gatilho da contagem é o MESMO de
        ``escondendo`` (médico em foco E modo ESCONDER) — não só "há médico
        em foco": no ESMAECER o médico apenas destaca, nunca filtra
        contagem nenhuma.

        ``agora``: o instante para posicionar a régua ``AGORA`` — ``None``
        (o padrão) quer dizer "o dia em cena não é hoje", e a régua não
        aparece. Não muda a cor de nenhuma linha (só a posição da régua);
        quem decide isso é ``PainelAgenda.mostrar_agenda`` (compara com
        ``date.today()``), não esta função.

        ``status_escondidos``: os grupos de :data:`_GRUPOS_STATUS` que o
        clique na legenda (:class:`_SeloLegendaStatus`) tirou da vista —
        pedido do usuário em 24/09/2026: "ao clicar em Tratado, Em Andamento
        e Aberto deve aplicar filtro na agenda". SEMPRE esconde (nunca
        esmaece, diferente do médico): é um FILTRO, não um destaque.

        ``fracoes``: ``{registro: (entregues, previstas, inicio,
        previsao_fim)}`` — ver o docstring de :class:`_LinhaMarcacao`.
        ``None`` ou sem entrada para o ``registro`` da marcação: a linha
        nasce sem fração nenhuma, nunca
        com "0/0".
        """
        # Widgets antigos saem TODOS antes dos novos entrarem — não há reúso
        # de linha por índice, porque o número de marcações muda a cada troca
        # de dia, e reaproveitar por posição misturaria o paciente de ontem
        # com o horário de hoje por uma tela.
        while self._corpo_lay.count() > 1:
            item = self._corpo_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._marcacoes = list(marcacoes)
        escondendo = bool(medicos_em_foco) and modo == MODO_ESCONDER
        visiveis = 0
        teve_passada = False
        linha_agora_posta = False
        dia_anterior = None
        # A hora da última linha VISÍVEL, para :data:`_VAGA_MINIMA` — vira
        # ``None`` sempre que uma marcação fica de fora (destaque/status) ou o
        # dia muda: o vão até a PRÓXIMA visível não pode incluir um trecho
        # onde uma marcação ESCONDIDA ainda ocupava a máquina de verdade.
        hora_anterior = None
        for m in marcacoes:
            if not medicos_em_foco:
                destaque = NORMAL
            elif m.medico_bruto in medicos_em_foco:
                destaque = DESTACADO
            else:
                destaque = ESMAECIDO

            passada = agora is not None and m.hora is not None and m.hora < agora

            escondido_status = _GRUPOS_STATUS.get(m.estado) in status_escondidos
            if (destaque == ESMAECIDO and escondendo) or escondido_status:
                teve_passada = teve_passada or passada
                hora_anterior = None
                continue

            # A régua entra na COSTURA entre a última passada e a próxima —
            # nunca no topo (nada passou ainda) nem no fim (tudo já passou),
            # onde ela só repetiria o que a ordem das linhas já mostra. Vem
            # ANTES do cabeçalho de dia (abaixo), não depois: se HOJE não tem
            # nenhuma marcação visível, a costura cai entre ontem e amanhã, e
            # "agora" precisa aparecer ANTES do título "amanhã" — inserida
            # depois dele, dava a impressão visual de que já era o dia
            # seguinte.
            if not passada and teve_passada and not linha_agora_posta:
                self._corpo_lay.insertWidget(
                    self._corpo_lay.count() - 1, _linha_agora(agora))
                linha_agora_posta = True
            teve_passada = teve_passada or passada

            # O cabeçalho de DIA — só no modo período (:attr:`_multiplos_dias`,
            # pedido do usuário em 25/09/2026) — sempre que a data da linha
            # muda da anterior; ``marcacoes`` já chega ordenada por hora (ver
            # ``agenda_db.agenda_do_periodo``), então "mudou" é sempre
            # "avançou um dia". Só conta dias com pelo menos uma linha
            # VISÍVEL — um dia todo escondido por médico/status não ganha
            # cabeçalho vazio.
            if self._multiplos_dias and m.hora is not None:
                dia_linha = m.hora.date()
                if dia_linha != dia_anterior:
                    self._corpo_lay.insertWidget(
                        self._corpo_lay.count() - 1, _cabecalho_data(dia_linha))
                    dia_anterior = dia_linha
                    hora_anterior = None  # não comparar vão através da virada

            if (hora_anterior is not None and m.hora is not None
                    and m.hora - hora_anterior >= _VAGA_MINIMA):
                self._corpo_lay.insertWidget(
                    self._corpo_lay.count() - 1,
                    _linha_vaga(m.hora - hora_anterior))

            visiveis += 1
            fracao = fracoes.get(m.registro) if fracoes else None
            self._corpo_lay.insertWidget(
                self._corpo_lay.count() - 1,
                _LinhaMarcacao(m, destaque, fracao))
            hora_anterior = m.hora
        # Com "Só os meus" MARCADO (``escondendo``), a contagem do
        # cabeçalho é SÓ do médico em foco — mesmo número que o resumo do
        # mês usa como filtro nesse estado, para "44 pacientes" não
        # conviver com "24 tratados" no mesmo cartão (ver o docstring
        # acima). Com "Só os meus" DESMARCADO, mesmo havendo médico
        # escolhido (ele só DESTACA as linhas, sem filtrar), a contagem
        # mostra a agenda completa — pedido do usuário em 25/09/2026: "se
        # nao tiver ticado somente os meus deve mostrar agenda completa".
        n = (sum(1 for m in marcacoes if m.medico_bruto in medicos_em_foco)
            if escondendo else len(marcacoes))
        if (escondendo or status_escondidos) and visiveis != n:
            # "3 de 38": o segundo número é o que impede a máquina de
            # parecer livre nos horários que algum filtro tirou da vista.
            self.rotulo_contagem.setText(
                f"{visiveis} de {n} pacientes" if visiveis != 1
                else f"1 de {n} pacientes")
        else:
            self.rotulo_contagem.setText(_texto_contagem(n))

    def marcacoes(self) -> list:
        """O dia INTEIRO que a coluna recebeu — mesmo no modo ESCONDER, que só
        filtra o que se DESENHA. É o que o repaint local (trocar de médico,
        trocar de modo) usa para partir sempre do dado completo."""
        return list(self._marcacoes)


class PainelAgenda(QWidget):
    """A tela inteira: a faixa de comando, o seletor de par de máquina e as
    colunas. Só monta e mostra — quem BUSCA é o :mod:`controle_agenda`.
    """

    dia_mudou = Signal(date)
    maquinas_mudaram = Signal(list)     # ctrResourceSer marcados
    medicos_mudaram = Signal(list)      # nomes BRUTOS (principal + grupo)
    modo_destaque_mudou = Signal(str)   # MODO_ESMAECER ou MODO_ESCONDER
    maquina_unica_mudou = Signal(bool)  # "uma máquina só" ligado/desligado

    def __init__(self, parent=None):
        super().__init__(parent)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── Faixa de comando: data + médico ─────────────────────────────
        faixa1, lay1 = ui.faixa()
        self.btn_anterior = QPushButton("◄")
        self.btn_anterior.setCursor(Qt.PointingHandCursor)
        # SEM largura fixa: o ``btn_fantasma`` tem ``padding: 10px 16px``, e um
        # botão de um caractere só espremido em 34px cortava o glifo — a seta
        # sumia da tela sem erro nenhum (visto no ``tools/tela.py`` de
        # 23/09/2026). O tamanho natural do botão já é compacto para um
        # caractere.
        st.pintar(self.btn_anterior, lambda: st.btn_fantasma(14.0))
        self.btn_anterior.clicked.connect(lambda: self._andar_dia(-1))
        lay1.addWidget(self.btn_anterior)

        self.data = QDateEdit()
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        # Largura mínima: sem ela o "2026" saía cortado atrás da seta do
        # calendário (visto no ``tools/tela.py`` de 23/09/2026) — o Qt mede o
        # ``sizeHint`` curto e a seta some por cima do último dígito.
        self.data.setMinimumWidth(118)
        self.data.setDate(_qdate_de(date.today()))
        # O "de" de ANTES da última mudança — ver :meth:`_data_de_mudou_na_tela`.
        self._de_anterior = self.data.date()
        self.data.dateChanged.connect(self._data_de_mudou_na_tela)
        st.pintar(self.data, _estilo_qdateedit)
        lay1.addWidget(self.data)

        # "até" — o intervalo de datas (pedido do usuário em 25/09/2026:
        # "adicione intervalo de data pra ser possivel ver a agenda de
        # multiplos dias"). Nasce IGUAL a ``self.data`` (dia único, o
        # estado de sempre); mudar só este campo é o que liga o modo
        # PERÍODO — ver :meth:`_periodo_multiplo_dias` e o docstring do
        # módulo.
        rotulo_ate = QLabel("até")
        st.pintar(rotulo_ate, lambda: f"color:{st.TEXTO_FRACO}; font-size:12.5px;")
        lay1.addWidget(rotulo_ate, 0, Qt.AlignVCenter)
        self.data_ate = QDateEdit()
        self.data_ate.setCalendarPopup(True)
        self.data_ate.setDisplayFormat("dd/MM/yyyy")
        self.data_ate.setMinimumWidth(118)
        self.data_ate.setDate(_qdate_de(date.today()))
        self.data_ate.dateChanged.connect(self._periodo_mudou_na_tela)
        st.pintar(self.data_ate, _estilo_qdateedit)
        lay1.addWidget(self.data_ate)

        self.btn_seguinte = QPushButton("►")
        self.btn_seguinte.setCursor(Qt.PointingHandCursor)
        st.pintar(self.btn_seguinte, lambda: st.btn_fantasma(14.0))
        self.btn_seguinte.clicked.connect(lambda: self._andar_dia(1))
        lay1.addWidget(self.btn_seguinte)

        # Atalhos de período (:data:`_ATALHOS_PERIODO`) — "Hoje" (que antes
        # era um botão à parte) e os outros períodos, tudo no MESMO combo
        # (pedido do usuário em 25/09/2026: "deixar tudo junto em hoje, os
        # outros periodos mesmo lugar"). É um MENU de ações, não um estado
        # que persiste selecionado: o índice 0 é só o rótulo, e o combo
        # volta pra ele sozinho depois de cada escolha (ver
        # :meth:`_atalho_de_periodo_escolhido`) — escolher a MESMA opção
        # duas vezes seguidas tem de fazer o mesmo efeito as duas vezes, o
        # que não aconteceria se o combo ficasse parado no item já
        # selecionado (``currentIndexChanged`` não dispara de novo).
        # ``ui.escolha`` (não ``QComboBox`` cru): aplica a folha de estilo do
        # tema e, principalmente, a proteção de ``ui.Escolha.wheelEvent``
        # contra a roda do mouse — esta faixa vive dentro de uma
        # ``QScrollArea`` por coluna, e o combo raw trocaria de período
        # sozinho ao rolar a lista de marcações com o cursor por cima dele.
        self.combo_atalhos = ui.escolha(
            ["Período"] + [label for label, _f, _d in _ATALHOS_PERIODO])
        self.combo_atalhos.currentIndexChanged.connect(
            self._atalho_de_periodo_escolhido)
        lay1.addWidget(self.combo_atalhos)

        # Nome do período escolhido (pedido do usuário em 28/09/2026: "ao
        # selecionar periodo, exemplo semana atual, deve aparecer o nome do
        # periodo selecionado em agenda") — o combo volta pro rótulo
        # "Período" sozinho (ver acima), então sem isto a escolha não
        # deixava rastro nenhum na tela. Some de novo (:meth:`_definir_periodo`)
        # assim que o usuário mexe manualmente nas datas ou anda com ◄/►:
        # nesse ponto o período deixou de ser o do atalho.
        self._nome_periodo_atual: str | None = None
        self.rotulo_periodo_atual = QLabel("")
        st.pintar(self.rotulo_periodo_atual,
                  lambda: f"color:{st.TEXTO}; font-weight:600;")
        lay1.addWidget(self.rotulo_periodo_atual, 0, Qt.AlignVCenter)

        lay1.addStretch(1)

        # "Só os meus" — o modo ESCONDER do filtro de médico (ver o docstring
        # do módulo). Ao lado do seletor, porque só faz sentido com ele: sem
        # médico escolhido a caixa não tem o que esconder.
        self._modo_destaque = MODO_ESMAECER
        self.chk_so_meus = QCheckBox("Só os meus")
        self.chk_so_meus.setCursor(Qt.PointingHandCursor)
        st.pintar(self.chk_so_meus, lambda: f"color:{st.TEXTO};")
        self.chk_so_meus.toggled.connect(self._modo_destaque_mudou_na_tela)
        lay1.addWidget(self.chk_so_meus, 0, Qt.AlignVCenter)

        # ``horizontal=True``: combo e botão lado a lado, numa linha só —
        # achado no print de 24/09/2026, o empilhado padrão (ver
        # ``_SeletorMedicos``) deixava "Só os meus" flutuando no meio da
        # altura dupla do bloco, em vez de alinhado com o combo.
        self.medicos = _SeletorMedicos(horizontal=True)
        self.medicos.mudou.connect(self._medicos_mudaram_na_tela)
        lay1.addWidget(self.medicos, 0, Qt.AlignVCenter)
        raiz.addWidget(faixa1)

        # A fração por paciente (ver :meth:`mostrar_agenda`) — guardada aqui
        # para o repaint local (:meth:`_repintar_colunas`) não precisar
        # pedir de novo ao controlador.
        self._fracoes: dict = {}

        # ── Faixa de máquinas: um botão por PAR, excludente ─────────────
        faixa2, self._lay_maquinas = ui.faixa()
        self._lay_maquinas.setSpacing(10)
        self._grupo_maquinas = QButtonGroup(self)
        self._grupo_maquinas.setExclusive(True)
        self._grupo_maquinas.buttonToggled.connect(self._maquinas_mudaram_na_tela)
        self._pares: list = []            # índice → lista de Maquina
        self._botoes_par: list = []       # mesmo índice → QPushButton
        self._todas_maquinas: list = []   # cache p/ reconstruir a faixa
        # Modo do último ``definir_maquinas`` — PAR (dia único) ou
        # INDIVIDUAL (período de vários dias). Guardado para
        # :meth:`_reconstruir_maquinas_se_o_modo_mudou` só refazer a faixa
        # QUANDO o modo de fato virar, não a cada troca de data dentro do
        # MESMO modo.
        self._faixa_maquinas_multi: bool = False
        # "Uma máquina só" — pedido do usuário em 28/09/2026: além dos três
        # pares fixos (:data:`PARES_MAQUINA`), poder ver uma máquina
        # sozinha sem precisar abrir um período de vários dias (que já
        # força isso, ver :meth:`_periodo_multiplo_dias`). Reaproveita
        # :func:`_montar_individuais` — a MESMA função do modo período —,
        # ver :meth:`definir_maquinas`. Widget nasce dentro dela (remontado
        # a cada chamada, como a legenda de status); o flag mora aqui para
        # sobreviver ao remonte.
        self._maquina_unica: bool = False
        # O checkbox some/nasce dentro de ``definir_maquinas`` conforme o
        # modo (ver o comentário logo acima), mas o ATRIBUTO precisa existir
        # desde já — ``None`` é o estado de "ainda não montado" para quem ler
        # antes da primeira chamada.
        self.chk_maquina_unica = None
        # O filtro de STATUS (ver :class:`_SeloLegendaStatus` e
        # :meth:`_criar_legenda_status`) — os grupos que o usuário TIROU da
        # vista clicando no selo da legenda. Vazio = nenhum filtro, mostra
        # tudo (o estado de quem nunca clicou).
        self._status_escondidos: set = set()
        # Os selos da legenda (ver :meth:`_criar_legenda_status`) só nascem
        # dentro de :meth:`definir_maquinas` — vazio até a primeira chamada
        # (ou em testes que montam a tela sem passar por ela), para
        # :meth:`_atualizar_contagem_status` não achar o atributo faltando
        # se ``mostrar_agenda`` rodar antes.
        self._selos_status: dict = {}
        raiz.addWidget(faixa2)

        # ── As colunas ───────────────────────────────────────────────────
        self._rolagem = QScrollArea()
        self._rolagem.setWidgetResizable(True)
        self._rolagem.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        st.pintar(self._rolagem, lambda: f"background:{st.FUNDO_TELA}; border:none;")
        self._corpo = QWidget()
        self._lay_colunas = QHBoxLayout(self._corpo)
        self._lay_colunas.setContentsMargins(0, 0, 0, 0)
        self._lay_colunas.setSpacing(0)
        self._colunas: dict = {}          # nome da máquina → _ColunaMaquina
        self._rolagem.setWidget(self._corpo)
        raiz.addWidget(self._rolagem, 1)

        self.rotulo_status = QLabel("")
        st.pintar(self.rotulo_status, lambda: (
            f"color:{st.TEXTO_FRACO}; padding:6px 18px; font-size:12px;"))
        raiz.addWidget(self.rotulo_status)

        # A auto-atualização (ver :data:`_INTERVALO_AUTO_ATUALIZACAO_MS`) —
        # liga/desliga sozinha com :meth:`showEvent`/:meth:`hideEvent`: só
        # reconsulta o banco enquanto esta aba está de fato na FRENTE do
        # ``QStackedWidget`` (``gui._trocar_modo``), nunca escondida atrás
        # de outra aba, onde ninguém está olhando o resultado.
        self._temporizador_auto = QTimer(self)
        self._temporizador_auto.setInterval(_INTERVALO_AUTO_ATUALIZACAO_MS)
        self._temporizador_auto.timeout.connect(self._atualizar_automaticamente)

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self._temporizador_auto.start()

    def hideEvent(self, ev) -> None:
        super().hideEvent(ev)
        self._temporizador_auto.stop()

    def _atualizar_automaticamente(self) -> None:
        """Reemite ``dia_mudou`` sozinho, a cada
        :data:`_INTERVALO_AUTO_ATUALIZACAO_MS` — o MESMO sinal que
        ``ControleAgenda._atualizar`` já escuta para trocas manuais de data;
        nenhum caminho novo, só mais um gatilho para o de sempre. Reler o
        MESMO dia/máquina/médico já em cena, não uma escolha diferente."""
        self.dia_mudou.emit(self.dia_atual())

    def _adiar_auto_atualizacao(self) -> None:
        """Reinicia a contagem dos :data:`_INTERVALO_AUTO_ATUALIZACAO_MS` —
        chamado por QUALQUER troca manual (data, máquina, médico, modo de
        destaque). Sem isto, o tique automático seguia num relógio fixo
        desde que a aba abriu, podendo cair bem em cima de uma interação do
        usuário (rolando a tela, prestes a clicar) e travar a UI pela
        consulta pesada sem aviso nenhum, logo depois de uma consulta manual
        que acabou de trazer o mesmo dado. Quem acabou de mexer não precisa
        de outra leitura do banco em seguida — o próximo tique automático
        só faz sentido depois de 2 minutos de fato PARADO na tela."""
        if self._temporizador_auto.isActive():
            self._temporizador_auto.start()

    # ── O que a janela repõe ────────────────────────────────────────────

    def definir_maquinas(self, maquinas: list, marcadas=None) -> None:
        """Monta a faixa de botões, excludente — na abertura, e de novo
        sempre que o modo dia-único/período muda (ver
        :meth:`_reconstruir_maquinas_se_o_modo_mudou`).

        Um botão por PAR (:func:`_montar_pares`) em dia único, ou um botão
        por MÁQUINA (:func:`_montar_individuais`) em período de vários
        dias — pedido do usuário em 25/09/2026: "ao selecionar multiplos
        dias deixar somente uma maquina por vez". Qual dos dois usar vem de
        :meth:`_periodo_multiplo_dias`, lido AGORA (a faixa reflete o modo
        de quando foi montada, não o de quando ``maquinas`` foi lida) — OU
        de :attr:`_maquina_unica` (pedido do usuário em 28/09/2026: "opção
        de selecionar somente uma máquina"), o checkbox que liga o mesmo
        :func:`_montar_individuais` em dia único, sem precisar abrir um
        período. Em período o checkbox nem aparece: individual já está
        forçado, e um segundo controle pra a mesma coisa só confundiria.

        ``marcadas``: os ``ctrResourceSer`` do par/máquina já escolhido (a
        preferência da pessoa); ``None`` marca o PRIMEIRO grupo da lista —
        é o estado de quem nunca escolheu. Uma lista vazia é "nenhum
        marcado" e fica assim (não é o estado de quem nunca escolheu, é
        escolha de quem desmarcou tudo). Uma preferência que não bate com
        grupo nenhum de hoje por IGUALDADE (de uma sessão de checkboxes
        livres, até 23/09/2026; de uma lista de pares que mudou; ou a MESMA
        preferência de um modo lida no OUTRO — um par de 2 nunca bate um
        grupo de 1) procura o grupo que CONTÉM a máquina preferida (ex.:
        saindo de "Uma máquina só", volta para o PAR de onde ela veio, não
        para o primeiro da lista); só cai no primeiro se nem isso bater —
        não trava vazia.
        """
        self._todas_maquinas = list(maquinas)
        self._faixa_maquinas_multi = self._periodo_multiplo_dias()
        montar = (_montar_individuais
                 if (self._faixa_maquinas_multi or self._maquina_unica)
                 else _montar_pares)
        # ``takeAt`` tira TODO item, não só os widgets: o ``addStretch`` do
        # fim da faixa é um item sem widget, e deixá-lo para trás somava um
        # espaçador novo a cada remonte, empurrando os botões para o meio.
        while self._lay_maquinas.count():
            item = self._lay_maquinas.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for btn in self._botoes_par:
            self._grupo_maquinas.removeButton(btn)
        self._pares = montar(maquinas)
        self._botoes_par = []

        if marcadas is None:
            indice = 0 if self._pares else None
        else:
            alvo = set(marcadas)
            indice = next(
                (i for i, grupo in enumerate(self._pares)
                 if {m.ctr_resource_ser for m in grupo} == alvo), None)
            if indice is None and alvo:
                # Uma preferência de 1 máquina (ex.: saindo de "Uma máquina
                # só") não bate um grupo de 2 por IGUALDADE — procura o
                # grupo que CONTÉM a máquina preferida antes de desistir e
                # cair no primeiro, senão desligar o checkbox sempre voltava
                # para o primeiro par da lista, mesmo vindo de outro.
                indice = next(
                    (i for i, grupo in enumerate(self._pares)
                     if alvo & {m.ctr_resource_ser for m in grupo}), None)
            if indice is None and alvo:
                indice = 0 if self._pares else None

        # Sinal bloqueado durante o MONTE: ``setChecked`` dispararia
        # ``buttonToggled`` a cada botão, e isto é CARGA, não escolha da
        # pessoa (mesma regra de ``definir_modo_destaque``).
        self._grupo_maquinas.blockSignals(True)
        for i, grupo in enumerate(self._pares):
            btn = QPushButton(_rotulo_par(grupo))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            self._grupo_maquinas.addButton(btn)
            btn.setChecked(i == indice)
            st.pintar(btn, lambda: st._estilo_btn_sel())
            self._lay_maquinas.addWidget(btn)
            self._botoes_par.append(btn)
        self._grupo_maquinas.blockSignals(False)

        # "Uma máquina só" — só existe em dia único: em período já está
        # forçado (ver o docstring do método), e o checkbox some em vez de
        # ficar marcado e desabilitado, que confundiria mais do que ajuda.
        # Remontado aqui, junto dos botões, sempre que a faixa é refeita —
        # mesmo padrão da legenda de status logo abaixo, que também não
        # sobrevive ao remonte por identidade, só pelo VALOR guardado
        # (:attr:`_maquina_unica`).
        self.chk_maquina_unica = None
        if not self._faixa_maquinas_multi:
            self.chk_maquina_unica = QCheckBox("Uma máquina só")
            self.chk_maquina_unica.setCursor(Qt.PointingHandCursor)
            st.pintar(self.chk_maquina_unica, lambda: f"color:{st.TEXTO};")
            bloq = self.chk_maquina_unica.blockSignals(True)
            self.chk_maquina_unica.setChecked(self._maquina_unica)
            self.chk_maquina_unica.blockSignals(bloq)
            self.chk_maquina_unica.toggled.connect(self._maquina_unica_alternada)
            self._lay_maquinas.addWidget(self.chk_maquina_unica, 0, Qt.AlignVCenter)

        self._lay_maquinas.addStretch(1)
        # A legenda-filtro de status (ver :meth:`_criar_legenda_status`), ao
        # lado dos botões de par — pedido do usuário em 24/09/2026. Este
        # método remonta a faixa inteira toda vez que roda (na abertura, e
        # de novo a cada troca de modo dia-único/período — ver
        # :meth:`_reconstruir_maquinas_se_o_modo_mudou`), e a legenda não
        # muda com o par/máquina escolhido, então recriá-la aqui basta.
        self._lay_maquinas.addWidget(self._criar_legenda_status())

    def _reconstruir_maquinas_se_o_modo_mudou(self) -> None:
        """Remonta a faixa de máquinas SE dia-único/período mudou desde a
        última montagem — chamado por :meth:`_periodo_mudou_na_tela` antes
        de emitir ``dia_mudou``, pedido do usuário em 25/09/2026: "ao
        selecionar multiplos dias deixar somente uma maquina por vez".

        Tenta preservar a máquina em cena: ao entrar em período, mantém a
        PRIMEIRA máquina do par/máquina que já estava marcado (menos
        surpresa que pular pra primeira da lista); ao voltar a dia único,
        ``definir_maquinas`` já resolve sozinha (a marcação de 1 máquina só
        não bate o conjunto de nenhum par de 2 por igualdade, mas volta para
        o PAR que contém essa máquina — ver o docstring de
        :meth:`definir_maquinas`)."""
        if self._periodo_multiplo_dias() == self._faixa_maquinas_multi:
            return
        marcadas = self.maquinas_marcadas()
        preferencia = marcadas[:1] if marcadas else None
        self.definir_maquinas(self._todas_maquinas, preferencia)

    def _maquina_unica_alternada(self, ligado: bool) -> None:
        """O checkbox "Uma máquina só" — pedido do usuário em 28/09/2026.
        Remonta a faixa (mesma troca de :func:`_montar_pares` para
        :func:`_montar_individuais` de :meth:`definir_maquinas`), tentando
        preservar a PRIMEIRA máquina do par em cena (mesmo critério de
        :meth:`_reconstruir_maquinas_se_o_modo_mudou`) — trocar de par pra
        máquina avulsa não devia trocar de máquina também.

        Emite os DOIS sinais: :attr:`maquina_unica_mudou` (só a preferência
        do MODO, sem reler o banco — mesmo padrão de
        :meth:`definir_modo_destaque`/``modo_destaque_mudou``) e
        :attr:`maquinas_mudaram` (a SELEÇÃO mudou de verdade, de um par de
        2 pra 1 máquina — precisa reler)."""
        self._maquina_unica = ligado
        marcadas = self.maquinas_marcadas()
        preferencia = marcadas[:1] if marcadas else None
        self.definir_maquinas(self._todas_maquinas, preferencia)
        self.maquina_unica_mudou.emit(ligado)
        self.maquinas_mudaram.emit(self.maquinas_marcadas())

    def definir_maquina_unica(self, ligado: bool) -> None:
        """Repõe a preferência salva de "uma máquina só" — CARGA, não
        escolha feita agora (mesma regra de :meth:`definir_modo_destaque`).
        Chamado por ``ControleAgenda.ao_abrir`` ANTES de
        :meth:`definir_maquinas`, para a primeira montagem da faixa já
        nascer no modo certo — só guarda o valor aqui; o checkbox em si
        nasce dentro de :meth:`definir_maquinas` (ainda não existe na
        abertura) e lê :attr:`_maquina_unica` sozinho."""
        self._maquina_unica = ligado

    def _criar_legenda_status(self) -> QWidget:
        """Os três selos de :data:`_LEGENDA_STATUS`, já com o clique ligado
        ao filtro (:attr:`_status_escondidos`) — refletindo o que o usuário
        já tinha escondido, caso esta faixa seja remontada. Guardados em
        :attr:`_selos_status` para :meth:`_atualizar_contagem_status`
        atualizar o número de cada um sem remontar a faixa inteira."""
        caixa = QWidget()
        lay = QHBoxLayout(caixa)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        self._selos_status: dict = {}
        for grupo, rotulo in _LEGENDA_STATUS:
            selo = _SeloLegendaStatus(grupo, rotulo)
            selo.definir_ativo(grupo not in self._status_escondidos)
            selo.clicado.connect(
                lambda grupo=grupo, selo=selo: self._status_clicado(grupo, selo))
            lay.addWidget(selo)
            self._selos_status[grupo] = selo
        return caixa

    def _atualizar_contagem_status(self) -> None:
        """Quantas marcações de cada grupo (:data:`_LEGENDA_STATUS`) há no
        que está em cena — pedido do usuário em 28/09/2026 ("quais outras...
        indicadores"). Chamado depois de montar/repintar as colunas
        (:meth:`mostrar_agenda`, :meth:`_repintar_colunas`): conta o dia ou
        período INTEIRO das colunas em cena, com o MESMO filtro de médico da
        contagem do cabeçalho (``escondendo`` — ver o docstring de
        :meth:`_ColunaMaquina.definir`), mas SEM respeitar
        :attr:`_status_escondidos`: é a legenda quem diz quantos há em cada
        grupo, para ajudar a decidir esconder — zerar o número de quem já
        está escondido apagaria essa mesma informação."""
        foco = self.medicos_em_foco()
        escondendo = bool(foco) and self._modo_destaque == MODO_ESCONDER
        contagem: Counter = Counter()
        for coluna in self._colunas.values():
            for m in coluna.marcacoes():
                if escondendo and m.medico_bruto not in foco:
                    continue
                grupo = _GRUPOS_STATUS.get(m.estado)
                if grupo:
                    contagem[grupo] += 1
        for grupo, selo in self._selos_status.items():
            selo.definir_contagem(contagem[grupo])

    def _status_clicado(self, grupo: str, selo) -> None:
        """Alterna ``grupo`` dentro ou fora de :attr:`_status_escondidos` — o
        FILTRO da agenda (pedido do usuário em 24/09/2026: "ao clicar em
        Tratado, Em Andamento e Aberto deve aplicar filtro na agenda"), e
        repinta as colunas com o que já está na tela (mesmo critério de
        :meth:`_repintar_colunas`: nem isto pede o dia de novo ao banco)."""
        if grupo in self._status_escondidos:
            self._status_escondidos.discard(grupo)
            selo.definir_ativo(True)
        else:
            self._status_escondidos.add(grupo)
            selo.definir_ativo(False)
        self._repintar_colunas()

    def maquinas_marcadas(self) -> list:
        """Os ``ctrResourceSer`` do par selecionado, na ordem do par — vazio
        quando nenhum está marcado (só a carga inicial deixa assim)."""
        for grupo, btn in zip(self._pares, self._botoes_par):
            if btn.isChecked():
                return [m.ctr_resource_ser for m in grupo]
        return []

    def definir_medicos(self, medicos_disponiveis: list, marcados=()) -> None:
        self.medicos.definir(medicos_disponiveis, marcados)

    def definir_modo_destaque(self, modo: str) -> None:
        """Repõe o modo salvo (a preferência da pessoa), sem emitir sinal —
        é CARGA, não escolha feita agora na tela."""
        self._modo_destaque = modo if modo in (MODO_ESMAECER, MODO_ESCONDER) \
            else MODO_ESMAECER
        bloq = self.chk_so_meus.blockSignals(True)
        self.chk_so_meus.setChecked(self._modo_destaque == MODO_ESCONDER)
        self.chk_so_meus.blockSignals(bloq)

    def medicos_em_foco(self) -> set:
        """Os nomes BRUTOS escolhidos — vazio quer dizer "sem filtro"."""
        return {m.bruto for m in self.medicos.escolhidos()}

    def medicos_para_contagem(self) -> set:
        """Os médicos que devem FILTRAR contagens (a do cabeçalho do dia,
        em ``_ColunaMaquina.definir``, e a do resumo do mês, pedida pelo
        ``ControleAgenda``) — só com "Só os meus" MARCADO
        (:data:`MODO_ESCONDER`). Desmarcado, ``medicos_em_foco`` escolhido
        ainda DESTACA as linhas do médico (ver :meth:`_repintar_colunas`),
        mas nenhuma contagem filtra por ele — pedido do usuário em
        25/09/2026: "se nao tiver ticado somente os meus deve mostrar
        agenda completa".
        """
        return self.medicos_em_foco() if self._modo_destaque == MODO_ESCONDER \
            else set()

    def dia_atual(self) -> date:
        return _date_de(self.data.date())

    def dia_final_atual(self) -> date:
        """O fim do intervalo — igual a :meth:`dia_atual` em dia único (o
        estado de sempre), maior quando o usuário abriu um PERÍODO (pedido
        do usuário em 25/09/2026)."""
        return _date_de(self.data_ate.date())

    def _periodo_multiplo_dias(self) -> bool:
        """Mais de um dia em cena — o gatilho do modo PERÍODO: faixa de
        máquinas vira uma-de-cada-vez (ver :meth:`definir_maquinas`) e a
        coluna ganha cabeçalho de data (ver
        ``_ColunaMaquina._multiplos_dias``)."""
        return self.dia_final_atual() > self.dia_atual()

    def _agora_de_hoje(self) -> datetime | None:
        """``datetime.now()`` quando HOJE está dentro do intervalo em cena
        (um dia só, ou um período que inclui hoje), senão ``None`` — a
        régua ``AGORA`` e o esmaecido de "já passou" só valem para o dia
        que ainda está acontecendo. Generalizado em 25/09/2026 para o
        intervalo: antes só comparava ``dia_atual() == hoje``, que não
        bate mais quando hoje é o SEGUNDO dia (ou o terceiro, ...) de um
        período de vários."""
        hoje = date.today()
        return datetime.now() if self.dia_atual() <= hoje <= self.dia_final_atual() \
            else None

    def mostrar_agenda(self, por_maquina: dict, ordem: list,
                      fracoes: dict | None = None,
                      resumo_mensal: dict | None = None,
                      multiplos_dias: bool = False) -> None:
        """Repõe as colunas, na ORDEM das máquinas marcadas — não na ordem em
        que o dicionário chegou, que é a ordem em que o SQL as agrupou.

        ``fracoes``: ``{registro: (entregues, previstas, inicio,
        previsao_fim)}`` — ver o docstring de ``_LinhaMarcacao``. Quem calcula
        é o ``ControleAgenda``, não esta tela: aqui só se guarda para o
        repaint local (:meth:`_repintar_colunas`).

        ``resumo_mensal``: ``{nome_maquina: (pacientes, inicios, sessoes,
        idade_media, fracoes_previstas_media)}`` do mês em cena — vai
        direto no CABEÇALHO da coluna (ver o docstring de
        :class:`_ColunaMaquina`), não numa faixa própria: essa faixa
        repetia o nome da máquina que o cabeçalho já mostra (achado no
        print de 25/09/2026).

        ``multiplos_dias``: pedido do usuário em 25/09/2026 ("adicione
        intervalo de data pra ser possivel ver a agenda de multiplos
        dias") — quando ``True``, cada coluna separa as marcações por DIA,
        com um cabeçalho de data entre um dia e o próximo (ver
        :func:`_cabecalho_data`), dentro da MESMA coluna rolável (decisão
        do usuário: "uma coluna, dias empilhados", não uma coluna por
        dia). ``ControleAgenda`` já garante UMA máquina marcada nesse modo
        (ver ``PainelAgenda.definir_maquinas``), mas esta função não
        assume isso — funcionaria com mais de uma coluna também, só sem
        necessidade prática hoje.
        """
        # A rolagem de cada coluna sobrevive quando a tela é refeita com o
        # MESMO dia/período e as MESMAS colunas (a atualização automática a
        # cada 2 minutos é o caso comum): sem isto, quem rolou até o meio de
        # uma coluna longa voltava para o topo sem ter mexido em nada.
        chave_cena = (self.dia_atual(), self.dia_final_atual(),
                      tuple(ordem), multiplos_dias)
        rolagens = {}
        if chave_cena == getattr(self, "_chave_cena", None):
            rolagens = {nome: c._rolagem.verticalScrollBar().value()
                        for nome, c in self._colunas.items()}
        self._chave_cena = chave_cena
        for i in reversed(range(self._lay_colunas.count())):
            item = self._lay_colunas.itemAt(i)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._colunas = {}
        self._fracoes = fracoes or {}
        resumo_mensal = resumo_mensal or {}
        foco = self.medicos_em_foco()
        agora = self._agora_de_hoje()
        for nome in ordem:
            coluna = _ColunaMaquina(nome, resumo_mensal.get(nome), multiplos_dias)
            coluna.definir(por_maquina.get(nome, []), foco, self._modo_destaque,
                           agora, self._status_escondidos, self._fracoes)
            # Fator 1 em TODAS: dividem a largura da aba igualmente, e sem
            # ``addStretch`` no fim — o espaço que sobrava à direita era
            # justamente o defeito.
            self._lay_colunas.addWidget(coluna, 1)
            self._colunas[nome] = coluna
        self._atualizar_contagem_status()
        if rolagens:
            # Depois do próximo ciclo de layout: antes dele a barra ainda tem
            # alcance zero e o ``setValue`` seria cortado para 0.
            QTimer.singleShot(0, lambda r=rolagens: self._repor_rolagens(r))

    def _repor_rolagens(self, rolagens: dict) -> None:
        """Devolve cada coluna à rolagem que tinha antes de ser refeita —
        ver :meth:`mostrar_agenda`."""
        for nome, valor in rolagens.items():
            coluna = self._colunas.get(nome)
            if coluna is not None:
                coluna._rolagem.verticalScrollBar().setValue(valor)

    def atualizar_resumo_mensal(self, resumo_mensal: dict) -> None:
        """Atualiza SÓ o acumulado do mês das colunas já na tela — chamado
        pelo ``ControleAgenda`` quando o médico em foco muda (pedido do
        usuário em 25/09/2026: "os valores devem ser atualizados a depender
        do filtro de tempo e de médico"). Não refaz as linhas nem pede a
        agenda de novo: só o resumo mudou."""
        for nome, coluna in self._colunas.items():
            coluna.definir_resumo_mensal(resumo_mensal.get(nome))

    def mostrar_status(self, texto: str, erro: bool = False) -> None:
        self.rotulo_status.setText(texto)
        # ``erro`` (bool) no default do lambda, não a cor já resolvida: presa
        # a variável, ``st.VERMELHO``/``st.TEXTO_FRACO`` continuariam apontando
        # a cor de QUANDO a mensagem chegou, e um aviso de erro sobreviveria
        # trocado de noite para dia com a cor errada — mesma armadilha do
        # comentário em ``_LinhaMarcacao``.
        st.pintar(self.rotulo_status, lambda ero=erro: (
            f"color:{st.VERMELHO if ero else st.TEXTO_FRACO};"
            " padding:6px 18px; font-size:12px;"))

    # ── Gestos ───────────────────────────────────────────────────────────

    def _definir_periodo(self, de: QDate, ate: QDate,
                          nome_periodo: str | None = None) -> None:
        """Põe os dois campos de data em ``de``/``ate`` de uma vez, com os
        sinais bloqueados enquanto os dois mudam — para
        :meth:`_periodo_mudou_na_tela` disparar uma vez só, no fim, com o
        par já consistente, não duas vezes (uma por campo). Usado por
        :meth:`_andar_dia` e :meth:`_atalho_de_periodo_escolhido`, que só
        decidem QUAIS datas, não como trocá-las.

        ``nome_periodo`` é o rótulo do atalho (:data:`_ATALHOS_PERIODO`) que
        pediu esta mudança, para :attr:`rotulo_periodo_atual` mostrar —
        ``None`` (o padrão, usado por :meth:`_andar_dia`) apaga o rótulo:
        andar de um período nomeado ele deixa de ser aquele período."""
        self._nome_periodo_atual = nome_periodo
        bloq_de = self.data.blockSignals(True)
        bloq_ate = self.data_ate.blockSignals(True)
        self.data.setDate(de)
        self.data_ate.setDate(ate)
        self.data.blockSignals(bloq_de)
        self.data_ate.blockSignals(bloq_ate)
        self._periodo_mudou_na_tela()

    def _andar_dia(self, passo: int) -> None:
        """◄/► — anda ``passo`` dias, o INTERVALO inteiro junto (os dois
        campos, mesma distância entre eles): pedido do usuário em
        25/09/2026 de andar por período, não só por dia único."""
        self._definir_periodo(self.data.date().addDays(passo),
                              self.data_ate.date().addDays(passo))

    def _atalho_de_periodo_escolhido(self, indice: int) -> None:
        """Um atalho de :data:`_ATALHOS_PERIODO` (inclusive "Hoje", que
        antes era um botão à parte — agora junto dos outros períodos no
        mesmo combo). Índice 0 é só o rótulo ("Período") — não
        faz nada. O combo volta pro rótulo sozinho (sinais bloqueados, para
        não reentrar aqui) depois de cada escolha: é um MENU de ações, e
        escolher a MESMA opção duas vezes seguidas tem de funcionar as duas
        vezes."""
        if indice <= 0:
            return
        _rotulo, funcao, deslocamento = _ATALHOS_PERIODO[indice - 1]
        de, ate = funcao(date.today(), deslocamento)
        self.combo_atalhos.blockSignals(True)
        self.combo_atalhos.setCurrentIndex(0)
        self.combo_atalhos.blockSignals(False)
        self._definir_periodo(_qdate_de(de), _qdate_de(ate), nome_periodo=_rotulo)

    def _periodo_mudou_na_tela(self, _qd: QDate | None = None) -> None:
        """Chamado por QUALQUER mudança nos dois campos de data (direto no
        popup do calendário, ou por :meth:`_andar_dia`/
        :meth:`_atalho_de_periodo_escolhido`). Duas responsabilidades,
        nesta ordem:

        1. Garantir ``data_ate >= data`` — "até" nunca fica ANTES do
           início; se alguém arrastar um dos dois para além do outro, o
           campo mais atrasado é puxado até bater (nunca os dois se
           cruzam, nunca uma consulta com fim antes do começo).
        2. Reconstruir a faixa de máquinas SE o modo mudou (dia único ↔
           período — ver :meth:`_periodo_multiplo_dias`), ANTES de emitir
           ``dia_mudou``: pedido do usuário em 25/09/2026, "ao selecionar
           multiplos dias deixar somente uma maquina por vez" — quem ouve
           o sinal (``ControleAgenda._atualizar``) já precisa encontrar a
           faixa certa quando ler ``maquinas_marcadas()``.

        ``_qd`` só vem preenchido quando é o PRÓPRIO ``dateChanged`` de
        ``self.data``/``self.data_ate`` chamando (edição manual no popup do
        calendário) — :meth:`_definir_periodo` sempre chama sem argumento,
        com os sinais já religados. É o sinal de que o usuário mexeu direto
        na data, por fora de qualquer atalho: o rótulo do período nomeado
        (:attr:`rotulo_periodo_atual`) não vale mais.
        """
        if _qd is not None:
            self._nome_periodo_atual = None
        self._de_anterior = self.data.date()
        if self.data_ate.date() < self.data.date():
            bloq = self.data_ate.blockSignals(True)
            self.data_ate.setDate(self.data.date())
            self.data_ate.blockSignals(bloq)
        self._reconstruir_maquinas_se_o_modo_mudou()
        self.rotulo_periodo_atual.setText(self._nome_periodo_atual or "")
        self._adiar_auto_atualizacao()
        self.dia_mudou.emit(self.dia_atual())

    def _data_de_mudou_na_tela(self, qd: QDate) -> None:
        """O campo "de" mudou direto no calendário. Em dia único ("até" igual
        ao "de" de antes), o "até" acompanha: escolher outro dia no "de" é
        ver OUTRO DIA, não abrir um período. Sem isto, escolher ontem com os
        dois campos em hoje abria o período ontem–hoje. Com um período já
        aberto, o "até" fica onde está (mesma regra de sempre)."""
        if self.data_ate.date() == self._de_anterior:
            bloq = self.data_ate.blockSignals(True)
            self.data_ate.setDate(qd)
            self.data_ate.blockSignals(bloq)
        self._periodo_mudou_na_tela(qd)

    def _maquinas_mudaram_na_tela(self, _btn, marcado: bool) -> None:
        # ``buttonToggled`` dispara DUAS vezes por clique — o botão antigo
        # desmarcando (``marcado=False``) e o novo marcando — e as duas
        # leituras de ``maquinas_marcadas()`` já dariam o mesmo resultado
        # final; ignorar a primeira poupa o controle de repetir a mesma
        # consulta ao banco duas vezes.
        if not marcado:
            return
        self._adiar_auto_atualizacao()
        self.maquinas_mudaram.emit(self.maquinas_marcadas())

    def _medicos_mudaram_na_tela(self) -> None:
        self._adiar_auto_atualizacao()
        self.medicos_mudaram.emit([m.bruto for m in self.medicos.escolhidos()])
        self._repintar_colunas()

    def _modo_destaque_mudou_na_tela(self, escondendo: bool) -> None:
        self._modo_destaque = MODO_ESCONDER if escondendo else MODO_ESMAECER
        self._adiar_auto_atualizacao()
        self.modo_destaque_mudou.emit(self._modo_destaque)
        self._repintar_colunas()

    def _repintar_colunas(self) -> None:
        """Refaz as colunas com o que JÁ ESTÁ na tela — nem o médico, nem o
        modo esmaecer/esconder, nem o filtro de status pedem o dia de novo ao
        banco (ver o docstring do módulo): a consulta já trouxe tudo, só o
        que se DESENHA muda."""
        foco = self.medicos_em_foco()
        agora = self._agora_de_hoje()
        for coluna in self._colunas.values():
            coluna.definir(coluna.marcacoes(), foco, self._modo_destaque,
                           agora, self._status_escondidos, self._fracoes)
        self._atualizar_contagem_status()
