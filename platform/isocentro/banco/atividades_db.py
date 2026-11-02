r"""Atividades do ARIA: o que está pendente, e de quem.

O que a tela quer saber é uma pergunta só — *quais atividades de Documentação
esperam por mim?* — e o data warehouse responde em quatro pedaços:

* ``DWH.DimActivity`` (1.577 linhas) é o CATÁLOGO: que atividades existem, com
  código, categoria e nome em nove línguas. É onde mora a palavra
  "Documentação", como valor de ``ActivityCode``;
* ``DWH.DimActivityTransaction`` (1,89 milhão) é o FATO: uma linha por
  instância — o paciente, o recurso, o estado e as datas;
* ``DWH.GetTaskOwnerName`` diz de QUEM é a tarefa;
* ``DWH.GetActivityStatus`` traduz o estado (``Open``, ``Completed``…).

**Nada aqui foi conferido contra o banco.** As colunas vieram do
``INFORMATION_SCHEMA`` em 01/09/2026 (ver ``NOTAS.md``), não de uma consulta que
tenha rodado e voltado com linhas. Por isso o portão ``VERIFICADO_EM`` nasce
vazio, como o do :mod:`tratamento_db`: enquanto ele estiver vazio, a tela não
mostra número nenhum. Uma lista plausível e errada de "o que falta fazer" é pior
que lista nenhuma — quem a lê fecha o programa achando que está em dia.

**Só leitura**, como todo o resto: este banco é o sistema clínico.

**O dono é o ``ctrResourceSer``, não o nome.** ``GetTaskOwnerName`` não guarda
login: guarda ``FullName``, as iniciais (``GP``, ``MH``) e o ``ctrResourceSer``.
Casar por nome seria a armadilha do ``paralelo.maquina_do_plano`` de novo, e o
banco tem "Nathalia bittencourt Bittencourt" e "Danilelle Teles Teles" cadastrados assim.
O número entra no cadastro do usuário uma vez, escolhido pelo admin na lista que
:func:`donos` devolve.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from isocentro.dados import ambiente
from isocentro.dados import nomes
from isocentro.banco import capa_db

_LOG = logging.getLogger(__name__)

# Quando estas consultas foram medidas contra o banco de verdade — resultado E
# tempo. Vazio: nunca. Enquanto estiver vazio, ``disponivel()`` é falso e a tela
# diz por quê, em vez de mostrar uma lista que ninguém conferiu.
#
# Para preencher: rodar contra o servidor, comparar o que sai com o que o ARIA
# mostra para a MESMA pessoa, e anotar a data aqui.
VERIFICADO_EM = "02/09/2026"

# O que foi medido nesse dia, para quem vier depois saber o que a data cobre:
#
# * **resultado**: a consulta devolveu DUAS Documentações disponíveis no
#   serviço (pacientes 9000017ANA e 9000019ANA, ambas de Leonardo Quintela), e
#   são exatamente as duas que o ARIA mostrava na mesma hora, olhando o serviço
#   inteiro. Bateu depois de dois defeitos que só o dado real mostrou — a
#   tarefa repetida uma vez por recurso, e o "alguma predecessora pronta" no
#   lugar de "todas prontas";
# * **tempo**: 0,3 s, contra o limite de 6 s do ``capa_db``. Cabe na thread da
#   tela com folga de vinte vezes.
#
# O que a data NÃO cobre: a defasagem da carga do DW. Que os dois lados tenham
# batido no mesmo instante é indício de que ela é curta, não medida dela.

# Liga antes de conferir, para poder olhar. Mesmo impasse honesto do
# ``ISOCENTRO_LISTA_EXPERIMENTAL``: sem conferir não se mostra, e sem mostrar não
# dá para conferir contra o que o ARIA diz. Quem liga assume que os números
# podem estar errados — e a tela ANUNCIA isso, em vez de deixar a suposição na
# cabeça de quem ligou.
ENV_EXPERIMENTAL = "ISOCENTRO_ATIVIDADES_EXPERIMENTAL"

# O que o painel mostra: a atividade "Documentação", e SÓ ela — decidido em
# 02/09/2026, olhando a lista que a :func:`catalogo` trouxe do banco.
#
# Ficou de fora "Review Patient Document" / "Revisar a documentação do
# paciente" (categoria "Atividades especiais de revisão"), que a busca por
# palavra pegava junto. Por isso o filtro daqui é o CÓDIGO exato e não um
# ``LIKE``: "documentação" aparece no nome de atividades que são outra coisa, e
# uma lista de pendências com item que não é seu ensina a ignorar a lista.
#
# Acrescentar um código aqui é decisão de quem conhece o fluxo do serviço, não
# minha — a :func:`catalogo` existe para essa conversa ter uma lista na frente.
CODIGOS = ("Documentação",)

# O que alimenta o quadro **Altas Prontas** da Fichinha (v8).
#
# O parâmetro é a atividade "Verificar Programação {unidade}" — a que fica
# disponível no care path —, decisão do usuário em 22/09/2026. NÃO é a "Alta
# Pronta ANA/BET/CEL" que o catálogo revelou no mesmo dia: o quadro se CHAMA
# Altas Prontas e mostra a alta, mas quem diz que há trabalho é a outra.
#
# Os três códigos vieram do catálogo em 22/09/2026
# (``relatorios_ferramentas/atividades_achadas_20260922-101139.txt``), e eles
# NÃO são o que qualquer um escreveria de cabeça:
#
#     ActivityCode                  │ ActivityNamePTB
#     ──────────────────────────────┼──────────────────────────
#     Verificar Programação         │ Verificar Programação BET
#     Verificar Programação ANA     │ Verificar Programação ANA
#     Verificar Programação UNI     │ Verificar Programação CEL
#
# O código de **BET não tem sufixo nenhum** e o de **CEL termina em UNI**. Não
# é engano de digitação do catálogo: é a nomenclatura ANTIGA das unidades
# sobrevivendo no código enquanto o nome em português acompanhou a atual. A
# mesma troca aparece nas três outras famílias da categoria — "Alta Pronta
# UNI"→CEL, "Altas Prontas BUE"→BET, "Imprimir Alta UNI"→CEL.
#
# **Daí a regra que vale para sempre aqui: filtrar pelo CÓDIGO, exibir pelo
# NOME.** Ver ``Atividade.unidade``.
# **Duas famílias, o mesmo valor** (decisão do usuário em 23/09/2026): ter a
# "Verificar Programação CEL" aberta ou a "Imprimir Alta CEL" quer dizer a
# mesma coisa para este quadro — há alta daquele paciente esperando. A segunda
# família repete a troca de nomenclatura da primeira:
#
#     Imprimir Alta ANA  │ Imprimir Alta ANA
#     Imprimir Alta BUE  │ Imprimir Alta BET
#     Imprimir Alta UNI  │ Imprimir Alta CEL
#
# **Até CONCLUIR**, e não até começar (também decisão dele, no mesmo dia): a
# atividade vale enquanto estiver *disponível ou em andamento*. É o que
# ``FECHADOS`` já fazia — "In Progress" nunca esteve lá —, e agora está travado
# por ``tests/test_atividades_db.AtePeloMenosConcluir``.
CODIGOS_ALTA = ("Verificar Programação",
                "Verificar Programação ANA",
                "Verificar Programação UNI",
                "Imprimir Alta ANA",
                "Imprimir Alta BUE",
                "Imprimir Alta UNI")

# As unidades do serviço, como o NOME em português as escreve. "UNI" e "BUE"
# são as antigas e aparecem só no código — pôr as duas aqui faria a tela
# anunciar "UNI" para um paciente do CEL.
UNIDADES = ("ANA", "BET", "CEL")

# A palavra larga, usada SÓ pela :func:`catalogo`. Ali ser larga é a virtude:
# é a consulta que mostra o que existe no banco para alguém decidir o que entra
# em ``CODIGOS``. Sem o Ç e sem o Ã casa "Documentação", "Documentacao" e
# "Documentation" de uma vez, sem depender do acento.
#
# **Do collation ela depende, e muito** — medido em 22/09/2026, na busca pelas
# atividades de alta. O ``variandw`` deste serviço é CASE-SENSITIVE: procurar
# "alta" devolveu "Malta", "Kaltag" e "Falta de Ar", e NÃO devolveu "Alta
# Pronta CEL", que estava lá. Esta palavra escapa por acidente feliz — começa
# no miolo minúsculo de "Documentação" —, e quem escrever a próxima precisa
# escolher o pedaço com a caixa CERTA. Ver ``ARMADILHAS.md``.
PALAVRA = "ocumenta"

# Estados que NÃO são pendência. Lista negativa de propósito, e é uma decisão
# de segurança: com lista positiva ("Open", "Active"…), um estado novo no ARIA
# sumiria da tela em silêncio, e sumir é justamente o erro que este painel não
# pode cometer — some da lista, a pessoa conclui que está em dia. Assim, o
# desconhecido APARECE, com o nome do estado do lado, e alguém pergunta.
FECHADOS = ("Completed", "Manually Completed", "Cancelled",
            "Cancelled - Patient No-Show", "Deleted", "InActive",
            "Reschedule Activity (In-Active)", "Rescheduled Linked Activity")

# Existe, está aberta, e NÃO está disponível: espera a predecessora do care
# path terminar. É a diferença entre "não fechada" e "dá para fazer agora", e
# ela não aparece no ``AppointmentStatus`` do fato — só no
# ``DerivedActivityStatus`` da view de predecessora.
#
# Medido em 02/09/2026, e foi o usuário quem viu: a consulta devolvia OITO
# tarefas, todas com ``AppointmentStatus = 'Open'``, e no ARIA só DUAS estavam
# disponíveis. As outras seis esperavam a etapa anterior. Uma lista de
# pendências com seis itens que ninguém pode fazer ensina a ignorar a lista —
# e é pior que não ter lista, porque parece trabalho atrasado.
BLOQUEADAS = ("Pending",)

# Os estados que o quadro de ALTAS aceita — e aqui a lista é POSITIVA, ao
# contrário da ``FECHADOS``.
#
# Decisão do usuário em 23/09/2026, depois de comparar a consulta com a aba
# "Disponível" do ARIA: *"status da atividade tem que ser disponível ou em
# andamento — não existe isso de pendente"*. São os dois estados que o ARIA
# mostra como trabalho a fazer, e `Open`/`In Progress` é como eles chegam no
# `AppointmentStatus` do fato (visto no despejo cru dos dois pacientes que
# faltavam).
#
# **Por que positiva aqui e negativa lá.** A ``FECHADOS`` é negativa de
# propósito: na Documentação, um estado novo do ARIA tem de APARECER, porque
# sumir da lista faz a pessoa concluir que está em dia. Nas altas o problema é
# o inverso e foi medido — sem fechar a lista, 116 atividades passavam o filtro
# de estado contra 13 que o ARIA mostra: o resto vinha de estados que não são
# trabalho nenhum e que ninguém tinha catalogado. Lista de pendências com 103
# itens que não são pendência ensina a ignorar a lista.
#
# E é esta lista que substitui o filtro de predecessora nas altas: o
# ``DerivedActivityStatus`` marcava como ``Pending`` as quatro atividades que o
# ARIA mostrava como disponíveis (despejo de 23/09/2026 — a Imprimir Alta
# esperando a Verificar Programação do mesmo paciente). A view serve à
# Documentação, que bate 10 em 10 com ela; não serve a esta categoria.
ESTADOS_ABERTOS = ("Open", "In Progress")

# Janela de tempo da consulta. O fato tem 1,89 milhão de linhas e a tela
# consulta com prazo curto: sem recorte de data isto é varredura no servidor
# clínico em expediente. 180 dias é palpite deliberado — quando alguém medir o
# tempo real, este número se ajusta com a medida, não com o palpite.
DIAS_PARA_TRAS = 180


def conferido() -> bool:
    """As consultas foram medidas contra o banco? Diferente de estar LIGADO."""
    return bool(VERIFICADO_EM)


def disponivel() -> bool:
    """Dá para mostrar atividade pendente nesta instalação?"""
    if not capa_db.configurado():
        return False
    return conferido() or bool(ambiente.ler(ENV_EXPERIMENTAL))


def motivo_indisponivel() -> str:
    """Por que o painel não mostra nada — em palavras de quem está na frente.

    Duas causas, e elas pedem providências opostas: sem banco apontado é
    configuração, que o admin resolve; sem conferência é trabalho meu que não
    terminou. Um aviso só para as duas ensina a ignorar o aviso.
    """
    if not capa_db.configurado():
        return ("O sistema (banco de dados) não está apontado nesta "
                "instalação. Configurações → Serviço, campo “Sistema”.")
    if not conferido():
        return ("A leitura das atividades ainda não foi conferida contra este "
                "banco. Enquanto isso, o painel não mostra nada — uma lista "
                "de pendências plausível e errada é pior que lista nenhuma.")
    return ""


# ── O que a tela consome ────────────────────────────────────────────────────

@dataclass
class Dono:
    """Uma pessoa do ARIA, como o DW a conhece. Sem login: ele não está lá."""
    ctr_resource_ser: int = 0
    nome: str = ""          # "Geovani Pena" — ``FullName``, já desinvertido
    iniciais: str = ""      # "GP" — como a tarefa aparece na agenda do ARIA

    def rotulo(self) -> str:
        """"Geovani Pena (GP)" — as iniciais entram porque é por elas que a
        pessoa se reconhece na agenda, e há nomes parecidos no cadastro."""
        return f"{self.nome} ({self.iniciais})" if self.iniciais else self.nome


@dataclass
class Atividade:
    """Uma atividade pendente. Campo sem fonte no banco fica VAZIO."""
    # ``ctrActivityInstanceSer``: a identidade da TAREFA no ARIA. Entra por
    # necessidade da consulta (é ele que faz o ``DISTINCT`` colapsar a linha
    # repetida sem juntar duas tarefas iguais de verdade), e fica porque é o
    # único jeito de a tela dizer "esta linha e aquela são a mesma coisa".
    instancia: int = 0
    codigo: str = ""            # ``ActivityCode`` — "Documentação"
    nome: str = ""              # ``ActivityNamePTB``, quando houver
    categoria: str = ""         # ``ActivityCategoryPTB`` ou o código
    estado: str = ""            # "Open", "In Progress"… como o banco escreveu
    registro: str = ""          # o registro do paciente
    paciente: str = ""
    quando: Optional[date] = None
    dono: str = ""              # quem é o responsável, como o DW o nomeia
    marcas: list = field(default_factory=list)

    @property
    def unidade(self) -> str:
        """"CEL" de "Verificar Programação CEL" — vazio quando não casa.

        **Do NOME em português, nunca do código.** Os dois divergem no catálogo
        deste serviço, e não por pouco: o código de CEL termina em "UNI" e o de
        BET não tem sufixo nenhum (ver ``CODIGOS_ALTA``). Lido do código, este
        campo diria "UNI" para um paciente do CEL e vazio para todo o BET — uma
        etiqueta errada na tela, que é pior que etiqueta nenhuma.

        Sufixo desconhecido devolve vazio em vez de arriscar um palpite: a
        linha aparece sem a pílula da unidade, o que é honesto.
        """
        fim = (self.nome or "").strip().upper()[-3:]
        return fim if fim in UNIDADES else ""

    def data_br(self) -> str:
        return self.quando.strftime("%d/%m/%Y") if self.quando else ""

    def titulo(self) -> str:
        """O nome em português quando existe; o código quando não.

        Nunca os dois grudados: "Documentação — Documentação" foi o que saiu no
        primeiro rascunho, porque no ARIA o código de várias atividades É o nome
        delas.
        """
        if self.nome and self.nome.strip().lower() != self.codigo.strip().lower():
            return self.nome
        return self.codigo


# ── As consultas ────────────────────────────────────────────────────────────
#
# Os quatro pedaços, e por que cada junção é assim:
#
# ``GetTaskOwnerName`` casa por ``ctrActivityInstanceSer`` — a INSTÂNCIA, não a
# atividade: a mesma atividade do catálogo pertence a pessoas diferentes em
# pacientes diferentes. ``ActivityOwnerFlag = 1`` porque a view também traz
# participantes que não são donos; sem isso a mesma tarefa aparece duas vezes,
# uma para cada pessoa da sala.
#
# ``DimPatient`` entra por LEFT JOIN: atividade sem paciente existe (reunião,
# QA de máquina), e um INNER as apagaria da lista sem dizer nada.

_SQL_DONOS = """
SELECT DISTINCT o.ctrResourceSer, o.FullName, o.OwnerName
  FROM DWH.GetTaskOwnerName o
 WHERE o.ctrResourceSer IS NOT NULL
   AND LTRIM(RTRIM(COALESCE(o.FullName, ''))) <> ''
 ORDER BY o.FullName
"""

# ``DISTINCT`` porque ``DimActivity`` é dimensão HISTÓRICA: a mesma atividade
# tem uma linha por revisão (``ActivityRevCount``, ``EffectiveStartDate`` e
# ``EffectiveEndDate`` estão lá). Medido em 01/09/2026: "Documentação" voltou
# QUATRO vezes, idêntica nas três colunas, e uma lista de escolha com o mesmo
# item repetido quatro vezes faz quem escolhe procurar a diferença que não
# existe.
#
# O ``pendentes`` NÃO precisa disto: ele casa por ``DimActivityID``, que é da
# revisão — o fato aponta para a versão vigente quando a tarefa foi criada, que
# é justamente a certa.
_SQL_CATALOGO = """
SELECT DISTINCT a.ActivityCode, a.ActivityNamePTB,
       COALESCE(NULLIF(LTRIM(RTRIM(a.ActivityCategoryPTB)), ''),
                a.ActivityCategoryCode)
  FROM DWH.DimActivity a
 WHERE a.ActivityCode LIKE ? OR a.ActivityNamePTB LIKE ?
    OR a.ActivityCategoryPTB LIKE ? OR a.ActivityCategoryCode LIKE ?
 ORDER BY a.ActivityCode
"""

# O ``?`` do estado é montado em ``pendentes`` — são N valores, e o número de
# estados fechados pode mudar sem que a consulta mude de forma.
# ``DISTINCT`` **com o ``ctrActivityInstanceSer`` dentro da lista**, e as duas
# metades importam.
#
# Medido em 02/09/2026: cada tarefa voltava TRÊS vezes, idêntica em tudo — a
# mesma instância tem mais de uma linha no fato (uma por recurso envolvido), e
# todas casam com a mesma linha de dono. Uma lista de pendências que mostra a
# mesma tarefa três vezes é lida como três tarefas.
#
# O ``ctrActivityInstanceSer`` no SELECT é o que impede o remédio de ser pior
# que a doença: sem ele, um ``DISTINCT`` nas colunas visíveis também juntaria
# duas tarefas DIFERENTES do mesmo paciente, na mesma atividade e no mesmo dia
# — que existem, e que somem sem deixar rastro. Com ele, o que é a mesma
# instância colapsa e o que é outra sobrevive.
_SQL_PENDENTES = """
SELECT DISTINCT
       t.ctrActivityInstanceSer,
       a.ActivityCode,
       a.ActivityNamePTB,
       COALESCE(NULLIF(LTRIM(RTRIM(a.ActivityCategoryPTB)), ''),
                a.ActivityCategoryCode),
       t.AppointmentStatus,
       p.PatientId,
       p.PatientFullName,
       COALESCE(t.DerivedAppointmentTaskDate, t.AppointmentDateTime),
       o.FullName
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
  {JUNCAO_DONO} DWH.GetTaskOwnerName o
    ON o.ctrActivityInstanceSer = t.ctrActivityInstanceSer
   AND o.ActivityOwnerFlag = 1
  {JUNCAO_PREDECESSORA}
  LEFT JOIN DWH.DimPatient p ON p.DimPatientID = t.DimPatientID
 WHERE COALESCE(t.DerivedAppointmentTaskDate, t.AppointmentDateTime) >= ?
"""

# O join do dono é INNER numa lista e LEFT na outra, e a diferença NÃO é
# estilo: ela decide quem aparece.
#
# Medido em 23/09/2026, com as "Imprimir Alta" (janela de 180 dias): 720 linhas
# exigindo dono contra 2.732 sem exigir — o INNER comia 74% delas. Aplicado o
# filtro real (não fechadas e não bloqueadas), sobravam ZERO com dono e QUINZE
# sem, e o usuário sabia de doze disponíveis no ARIA. Estas atividades
# simplesmente não têm responsável com ``ActivityOwnerFlag = 1``.
#
# Então: **quadro de Documentação exige dono; quadro de Altas não.** Não é
# incoerência — é que o dono significa coisas diferentes nos dois. Na
# Documentação ele é a informação principal ("tem alguma minha?", a pergunta
# que fez a lista ser do serviço inteiro) e tarefa sem responsável ali seria
# uma linha que ninguém reconhece como sua. Nas Altas o que importa é o
# PACIENTE: a alta está pronta para ser impressa, com ou sem alguém marcado.
#
# O INNER da Documentação fica como está de propósito: aquela consulta foi
# conferida contra o ARIA em 02/09/2026, linha a linha, e trocar o join
# mudaria a lista que está medida.
JUNCAO_EXIGINDO_DONO = "JOIN"
JUNCAO_SEM_EXIGIR_DONO = "LEFT JOIN"

# Atividade ÓRFÃ: existe no fato e não tem linha nenhuma na view de
# predecessora do care path.
#
# Medido em 23/09/2026, comparando dois pacientes ANA lado a lado. O de abril
# tem a "Verificar Programação ANA" e a "Imprimir Alta ANA" abertas há cinco
# meses, as duas com ``ctrPredecessorSer`` NULO — e o ARIA não as mostra em
# aba nenhuma. São resíduo de um care path que não existe mais, e passavam
# justamente por não terem o que bloquear: o ``NOT EXISTS`` do filtro de
# predecessora não encontra linha e deixa passar.
#
# Só vale para as ALTAS, e por uma razão do domínio: nem a Verificar
# Programação nem a Imprimir Alta são a PRIMEIRA etapa de nada — as duas vêm
# depois do tratamento. Sem predecessora registrada, não são trabalho de
# ninguém. Numa lista onde a primeira etapa do care path pudesse entrar, esta
# exigência apagaria caso legítimo.
# Uma passada só na view, agrupada por instância — e é por TEMPO.
#
# A primeira versão usava ``NOT EXISTS`` (não bloqueada) mais ``EXISTS`` (não
# órfã), duas subconsultas correlacionadas sobre a mesma view: medido em
# 23/09/2026, a consulta foi de 0,4 s para **30,5 s**, cinco vezes o limite de
# 6 s do ``capa_db`` — e ela roda na thread da tela.
#
# Agrupada, a view é lida uma vez: o ``JOIN`` já garante que a atividade TEM
# predecessora (a órfã não tem linha e cai fora do INNER), e ``bloqueadas = 0``
# garante que nenhuma delas está pendente. As duas perguntas, uma varredura.
#
# É o mesmo remédio da coluna do médico no ``tratamento_db``, e pela mesma
# razão: subconsulta agrupada com junção, em vez de correlacionada por linha.
_SQL_PREDECESSORA_AGRUPADA = """
  JOIN (SELECT c.ctrActivityInstanceSer AS inst,
               SUM(CASE WHEN COALESCE(c.DerivedActivityStatus, '') IN ({})
                        THEN 1 ELSE 0 END) AS bloqueadas
          FROM DWH.GetPredeccesorAndCurrentActivityStatus c
         GROUP BY c.ctrActivityInstanceSer) pred
    ON pred.inst = t.ctrActivityInstanceSer
   AND pred.bloqueadas = 0
"""

# Bloqueada é a tarefa que tem ALGUMA predecessora pendente — e é por isso que
# isto é ``NOT EXISTS``, e não uma junção com filtro.
#
# Medido em 02/09/2026, com o despejo cru de dois casos lado a lado: a view dá
# uma linha POR PREDECESSORA, e o ``DerivedActivityStatus`` é calculado por
# par, não por tarefa. A Documentação do paciente 9000015CEL tem duas
# predecessoras — uma ``Completed`` (par derivado ``Open``) e uma ``Open`` (par
# derivado ``Pending``). Com junção + filtro por linha, a linha boa passava e a
# tarefa aparecia como disponível: o filtro perguntava "existe predecessora
# pronta?" quando a pergunta é "todas estão prontas?".
#
# O caso que funcionava por acaso era o de uma predecessora só — que é a
# maioria, e é assim que este erro chega à sala sem ninguém ver.
_SQL_NAO_BLOQUEADA = """
   AND NOT EXISTS (SELECT 1
                     FROM DWH.GetPredeccesorAndCurrentActivityStatus b
                    WHERE b.ctrActivityInstanceSer = t.ctrActivityInstanceSer
                      AND COALESCE(b.DerivedActivityStatus, '') IN ({}))
"""


# Tudo o que o banco sabe sobre as Documentações de UM paciente, sem filtro
# nenhum além do código da atividade. Existe para comparar uma linha que DEVE
# aparecer com uma que NÃO deve: quando a lista traz uma tarefa a mais, a
# diferença entre as duas está em alguma destas colunas, e olhar as duas lado a
# lado acha em minutos o que adivinhar filtro não acha em uma tarde.
#
# Sem ``DISTINCT`` de propósito: aqui as linhas repetidas são informação — são
# elas que mostram quantos recursos e quantas predecessoras a instância tem.
_SQL_DETALHE = """
SELECT t.ctrActivityInstanceSer,
       a.ActivityCode,
       t.AppointmentStatus,
       v.DerivedActivityStatus,
       v.PredecessorAppointmentStatus,
       v.ctrPredecessorSer,
       v.IsScheduled,
       t.IsScheduled,
       t.WaitListedFlag,
       COALESCE(t.DerivedAppointmentTaskDate, t.AppointmentDateTime),
       o.FullName,
       o.ActivityOwnerFlag
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
  JOIN DWH.DimPatient p ON p.DimPatientID = t.DimPatientID
  LEFT JOIN DWH.GetTaskOwnerName o
    ON o.ctrActivityInstanceSer = t.ctrActivityInstanceSer
  LEFT JOIN DWH.GetPredeccesorAndCurrentActivityStatus v
    ON v.ctrActivityInstanceSer = t.ctrActivityInstanceSer
 WHERE p.PatientId = ?
 ORDER BY t.ctrActivityInstanceSer
"""

DETALHE_COLUNAS = ("instancia", "codigo", "estado_bruto", "estado_derivado",
                   "estado_predecessora", "ctrPredecessorSer",
                   "v.IsScheduled", "t.IsScheduled", "WaitListed", "quando",
                   "dono", "OwnerFlag")


def detalhe(registro: str, codigos_alvo=None) -> list:
    """As atividades de um paciente, cruas, para comparar caso a caso.

    Devolve tuplas na ordem de :data:`DETALHE_COLUNAS`. Não filtra estado nem
    data: o que se quer aqui é ver o que o filtro escondeu.

    ``codigos_alvo`` entrou em 23/09/2026, com o usuário relatando 12 "Imprimir
    Alta CEL" disponíveis no ARIA e zero na consulta: sem ele, este despejo só
    sabia perguntar pelas Documentações, que são justamente as que NÃO estavam
    sumindo.
    """
    alvo = tuple(codigos_alvo) if codigos_alvo else CODIGOS
    codigos = ",".join(["?"] * len(alvo))
    sql = _SQL_DETALHE.replace(" ORDER BY",
                               f"   AND a.ActivityCode IN ({codigos})\n"
                               " ORDER BY")
    return capa_db._consultar(sql, str(registro), *alvo)


def donos() -> list:
    """Todo mundo que aparece como dono de tarefa, para o admin escolher.

    É por aqui que o ``ctrResourceSer`` entra no cadastro do usuário: uma lista
    para escolher, uma vez, em vez de um número digitado à mão — número digitado
    errado aponta para OUTRA pessoa, e a tela não teria como perceber.
    """
    try:
        linhas = capa_db._consultar(_SQL_DONOS)
    except capa_db.FalhaDeLeitura:
        _LOG.warning("Não deu para ler os donos de tarefa do ARIA.")
        raise
    saida = []
    for ser, nome, iniciais in linhas:
        if not ser:
            continue
        saida.append(Dono(int(ser), capa_db._txt(nome), capa_db._txt(iniciais)))
    return saida


def catalogo(palavra: str = "") -> list:
    """As atividades do CATÁLOGO que casam ``palavra`` (padrão: "Documentação").

    Serve para conferir o filtro antes de confiar nele: se esta lista vier com
    coisa que não é documentação, é o ``PALAVRA`` que está largo demais — e o
    lugar de descobrir isso é aqui, não na tela de alguém.

    O parâmetro entrou em 22/09/2026, quando foi preciso achar as atividades de
    ALTA e esta era a única consulta que devolve o trio ``código | nome |
    categoria`` **pareado**. O passo 4 do ``tools/atividades.py`` mostra os
    valores de cada coluna em listas separadas, e ali o par se perde — que é
    justamente o que importa quando o código e o nome divergem ("Alta Prontas
    ANA" contra "Alta Pronta ANA").
    """
    alvo = f"%{palavra or PALAVRA}%"
    linhas = capa_db._consultar(_SQL_CATALOGO, alvo, alvo, alvo, alvo)
    return [Atividade(codigo=capa_db._txt(c), nome=capa_db._txt(n),
                      categoria=capa_db._txt(cat)) for c, n, cat in linhas]


def todas(desde: Optional[date] = None) -> list:
    """Todas as Documentações abertas do serviço, **com o dono ao lado**.

    É a lista que a tela pediu em 02/09/2026: em vez de cada um ver a sua, todo
    mundo vê o quadro inteiro e enxerga de quem é cada pendência. Isso dispensa
    o vínculo entre o login do app e o ``ctrResourceSer`` — que era a parte
    mais frágil do desenho, porque o DW não guarda login e o casamento teria de
    ser por nome, com "Marcelo Assef" de um lado e "marcelo.valadares" do outro.

    O dono continua vindo do banco, no campo ``dono``: sem ele isto seria um
    monte de tarefa sem responsável, que é o mesmo que não ter lista.
    """
    return _pendentes(0, desde)


def altas(desde: Optional[date] = None) -> list:
    """As atividades que dizem "há alta a imprimir" — o quadro Altas Prontas.

    Mesma consulta das Documentações, com outros códigos: o que muda é o
    ``ActivityCode``, e não o que conta como pendente. Ver ``CODIGOS_ALTA``.

    Devolve lista vazia quando ninguém preencheu os códigos ainda, e é a TELA
    que anuncia isso — aqui, lista vazia sem código é literalmente verdade
    ("nenhuma das atividades que eu procuro está aberta"), e mentir com uma
    exceção obrigaria quem chama a distinguir dois tipos de falha.
    """
    if not CODIGOS_ALTA:
        return []
    return _uma_por_paciente(
        _pendentes(0, desde, CODIGOS_ALTA, exigir_dono=False,
                   estados_aceitos=ESTADOS_ABERTOS))


def _uma_por_paciente(atividades: list) -> list:
    """Uma linha por paciente, e não uma por atividade aberta.

    As duas famílias de ``CODIGOS_ALTA`` têm o mesmo valor aqui, e um paciente
    pode estar com as duas abertas ao mesmo tempo. Sem isto, ele apareceria
    duas vezes — e as duas linhas seriam IDÊNTICAS na tela (mesmo nome, mesma
    unidade, mesma pasta, mesmo PDF), porque a linha das Altas não mostra qual
    atividade é. Lista com a mesma coisa duas vezes é lida como dois pacientes.

    Fica a MAIS ANTIGA das duas, que é a que responde a pergunta do quadro: há
    quanto tempo esta alta espera. A consulta vem ordenada da mais recente para
    a mais antiga, então a última vista de cada registro é a que vale.
    """
    por_registro: dict = {}
    for a in atividades:
        chave = (a.registro or "").strip() or f"#{a.instancia}"
        por_registro[chave] = a
    # A ordem da consulta, não a do dicionário: a lista sai da mais recente
    # para a mais antiga, e reordenar aqui mudaria o quadro sem motivo.
    vistos = set()
    saida = []
    for a in atividades:
        chave = (a.registro or "").strip() or f"#{a.instancia}"
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(por_registro[chave])
    return saida


def pendentes(ctr_resource_ser: int, desde: Optional[date] = None) -> list:
    """As atividades de Documentação que esperam por UMA pessoa.

    ``desde`` recorta a janela; sem ele, ``DIAS_PARA_TRAS``. O recorte não é
    zelo: o fato tem 1,89 milhão de linhas e quem consulta é a thread da tela.

    Levanta :class:`capa_db.FalhaDeLeitura` quando não deu para perguntar —
    **não** devolve lista vazia. A diferença é o painel inteiro: vazio significa
    "nada pendente", e é assim que alguém fecha o programa achando que está em
    dia quando o banco é que não respondeu.
    """
    if not ctr_resource_ser:
        # Zero não vira "todo mundo" por acidente: quem quer a lista inteira
        # chama ``todas``, que diz isso no nome. Identificador que chegou vazio
        # por engano devolveria a agenda da clínica inteira para quem pediu a
        # sua — e ninguém desconfia de uma lista GRANDE demais.
        raise ValueError("sem ctrResourceSer: não sei quem é esta pessoa "
                         "no ARIA. Para a lista inteira, chame todas().")
    return _pendentes(int(ctr_resource_ser), desde)


def _pendentes(ctr_resource_ser: int, desde: Optional[date],
               codigos_alvo=None, exigir_dono: bool = True,
               estados_aceitos=None) -> list:
    """O corpo comum das tres. ``ctr_resource_ser`` zero significa TODO MUNDO.

    ``codigos_alvo`` entrou na v8, para o quadro de Altas Prontas reusar esta
    consulta com os codigos dele. E parametro, e nao uma copia da funcao: o
    filtro de estado, o de predecessora e o recorte de data sao os mesmos, e a
    copia divergiria no primeiro conserto.

    A ordem dos parâmetros acompanha a ordem em que os pedaços entram no texto
    — data, dono, códigos, estados. Trocar dois de lugar aqui não dá erro de
    sintaxe: dá a consulta errada, calada.
    """
    # ISO em TEXTO, e não o ``date`` do Python: o driver "SQL Server" (o de
    # 2000, que é o que está nas estações) não conhece o tipo DATE e recusa o
    # parâmetro antes de consultar — ``HYC00 ... SQLBindParameter``, medido
    # contra o banco em 02/09/2026. O SQL Server converte a string sozinho, em
    # qualquer driver; é o mesmo caminho que o ``tratamento_db.em_tratamento``
    # já usava, e que eu não segui na primeira escrita.
    corte = (desde or _dias_atras(DIAS_PARA_TRAS)).strftime("%Y-%m-%d")
    alvo = tuple(codigos_alvo) if codigos_alvo else CODIGOS
    codigos = ",".join(["?"] * len(alvo))
    # Duas listas, e agora dois filtros DIFERENTES — não é só organização.
    # "Terminou" se lê na própria tarefa; "espera a etapa anterior" só se lê
    # olhando TODAS as predecessoras dela, e por isso vira ``NOT EXISTS``.
    fechados = ",".join(["?"] * len(FECHADOS))
    bloqueadas = ",".join(["?"] * len(BLOQUEADAS))
    # Montada em PEDAÇOS e juntada com quebra de linha, em vez de concatenar
    # trechos que já trazem o "\n" no fim: o filtro do dono é opcional, e é na
    # emenda dele que a linha some ou gruda na seguinte — e SQL grudado numa
    # linha só ainda executa, só que a consulta é outra.
    # Exigir dono só quando o dono é a informação principal da lista — a
    # Documentação. Ver ``JUNCAO_EXIGINDO_DONO``: nas Altas, o INNER comia 74%
    # das linhas, e todas as doze que o usuário via no ARIA.
    juncao = (JUNCAO_EXIGINDO_DONO if exigir_dono
              else JUNCAO_SEM_EXIGIR_DONO)
    base = _SQL_PENDENTES.replace("{JUNCAO_DONO}", juncao)
    # O filtro de predecessora das ALTAS é um JOIN, e por isso entra no corpo
    # do SQL e não na lista de cláusulas: ele responde de uma vez "não está
    # bloqueada" e "não é órfã". A Documentação segue com o ``NOT EXISTS`` de
    # sempre, que está medido em 0,3 s.
    if estados_aceitos:
        base = base.replace(
            "{JUNCAO_PREDECESSORA}",
            _SQL_PREDECESSORA_AGRUPADA.format(bloqueadas).strip())
        params_pred = [*BLOQUEADAS]
    else:
        base = base.replace("{JUNCAO_PREDECESSORA}", "")
        params_pred = []
    partes = [base]
    params = [*params_pred, corte]
    if ctr_resource_ser:
        partes.append("   AND o.ctrResourceSer = ?")
        params.append(int(ctr_resource_ser))
    partes.append(f"   AND a.ActivityCode IN ({codigos})")
    if estados_aceitos:
        # Lista POSITIVA: só os estados que são trabalho a fazer. Ela SOMA-SE
        # ao filtro de predecessora, não o substitui — medido em 23/09/2026:
        # sem a predecessora vinham 216 atividades contra as 16 que o ARIA
        # mostra, quase todas agendadas para outubro e novembro.
        aceitos = ",".join(["?"] * len(estados_aceitos))
        partes.append(f"   AND COALESCE(t.AppointmentStatus, '') "
                      f"IN ({aceitos})")
        depois = [*estados_aceitos]
    else:
        partes.append(f"   AND COALESCE(t.AppointmentStatus, '') "
                      f"NOT IN ({fechados})")
        partes.append(_SQL_NAO_BLOQUEADA.format(bloqueadas))
        depois = [*FECHADOS, *BLOQUEADAS]
    partes.append(" ORDER BY COALESCE(t.DerivedAppointmentTaskDate,"
                  " t.AppointmentDateTime) DESC")
    params += [*alvo, *depois]
    linhas = capa_db._consultar("\n".join(partes), *params)
    saida = []
    for inst, cod, nome, cat, estado, reg, pac, quando, dono in linhas:
        saida.append(Atividade(
            instancia=int(inst or 0),
            codigo=capa_db._txt(cod), nome=capa_db._txt(nome),
            categoria=capa_db._txt(cat), estado=capa_db._txt(estado),
            registro=capa_db._txt(reg),
            # O DW grava o paciente INVERTIDO e em caixa alta
            # ("SOUZA SANTOS, MARIA DA"), e é assim que ele saía nos quadros de
            # Documentação e de Altas Prontas — ao lado do dono, que vem
            # gravado como se escreve. A `capa_db` e a `tratamento_db` já
            # passavam esta mesma coluna pelo `de_pessoa`; este módulo nasceu
            # depois e ficou de fora, então o MESMO paciente aparecia de dois
            # jeitos em duas telas do programa.
            paciente=nomes.de_pessoa(capa_db._txt(pac)),
            quando=_data(quando),
            # O dono NÃO passa pelo formatador: `GetTaskOwnerName.FullName` já
            # vem grafado como se escreve e carrega as iniciais entre
            # parênteses ("Ana Fatima Albuquerque (AC)"), que o
            # `como_nome_proprio` rebaixaria para "(Ac)".
            dono=capa_db._txt(dono)))
    return saida


_SQL_QUANTAS = """
SELECT COUNT(*)
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
  JOIN DWH.GetTaskOwnerName o
    ON o.ctrActivityInstanceSer = t.ctrActivityInstanceSer
   AND o.ActivityOwnerFlag = 1
 WHERE COALESCE(t.DerivedAppointmentTaskDate, t.AppointmentDateTime) >= ?
"""

# O mesmo COUNT, com o dono em LEFT JOIN. Existe para uma pergunta só, e ela
# nasceu em 23/09/2026 com o quadro de Altas vazio: o join do dono no
# ``_SQL_QUANTAS`` é INNER, então atividade sem responsável de ``OwnerFlag = 1``
# não aparece em degrau nenhum — e some da lista sem deixar rastro. Comparar os
# dois números diz, numa linha, se o culpado é o dono.
_SQL_QUANTAS_SEM_DONO = """
SELECT COUNT(*)
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
 WHERE COALESCE(t.DerivedAppointmentTaskDate, t.AppointmentDateTime) >= ?
"""

_SQL_POR_ESTADO = """
SELECT COALESCE(t.AppointmentStatus, '(sem estado)'), COUNT(*)
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
  JOIN DWH.GetTaskOwnerName o
    ON o.ctrActivityInstanceSer = t.ctrActivityInstanceSer
   AND o.ActivityOwnerFlag = 1
 WHERE COALESCE(t.DerivedAppointmentTaskDate, t.AppointmentDateTime) >= ?
"""


def porque_vazio(ctr_resource_ser: int, desde: Optional[date] = None,
                 codigos_alvo=None) -> dict:
    """Por que :func:`pendentes` não devolveu nada — qual filtro esvaziou.

    Zero é a resposta mais perigosa que este painel pode dar: "não há nada
    pendente" e "o meu filtro apagou tudo" são indistinguíveis na tela, e a
    primeira leitura faz a pessoa fechar o programa achando que está em dia.

    Então, quando dá zero, a mesma consulta é refeita afrouxando um filtro por
    vez. Onde o número deixar de ser zero, ali está o filtro culpado — e se
    todos derem zero, aí sim a resposta é "não há nada", com o que a sustenta.
    """
    corte = (desde or _dias_atras(DIAS_PARA_TRAS)).strftime("%Y-%m-%d")
    alvo = tuple(codigos_alvo) if codigos_alvo else CODIGOS
    codigos = ",".join(["?"] * len(alvo))
    fechados = ",".join(["?"] * len(FECHADOS))
    bloqueadas = ",".join(["?"] * len(BLOQUEADAS))
    degraus = []
    # Os dois primeiros degraus só existem quando há dono: com zero eles
    # perguntariam "quantas tarefas são da pessoa nenhuma", e a resposta seria
    # zero por construção — um degrau que sempre dá zero não diagnostica nada,
    # só faz o relatório parecer que investigou.
    if ctr_resource_ser:
        degraus += [
            ("tarefas SUAS, qualquer atividade e estado",
             _SQL_QUANTAS + "   AND o.ctrResourceSer = ?",
             (corte, int(ctr_resource_ser))),
            ("tarefas SUAS de " + "/".join(CODIGOS) + ", qualquer estado",
             _SQL_QUANTAS + "   AND o.ctrResourceSer = ?"
             + f"\n   AND a.ActivityCode IN ({codigos})",
             (corte, int(ctr_resource_ser), *CODIGOS)),
        ]
    degraus += [
        (" ".join(alvo) + " de QUALQUER pessoa, qualquer estado",
         _SQL_QUANTAS + f"   AND a.ActivityCode IN ({codigos})",
         (corte, *alvo)),
        # Os três degraus abaixo entraram em 23/09/2026, com o quadro de Altas
        # vazio. Eles separam os três jeitos de a lista zerar que o relatório
        # antigo não distinguia: sem DONO, FECHADA, ou BLOQUEADA pela
        # predecessora. Sem eles, os três davam "0" no mesmo degrau.
        ("… as mesmas, SEM exigir dono (o join do dono é INNER)",
         _SQL_QUANTAS_SEM_DONO + f"   AND a.ActivityCode IN ({codigos})",
         (corte, *alvo)),
        ("… sem dono e SÓ as não fechadas",
         _SQL_QUANTAS_SEM_DONO + f"   AND a.ActivityCode IN ({codigos})"
         + f"\n   AND COALESCE(t.AppointmentStatus, '') NOT IN ({fechados})",
         (corte, *alvo, *FECHADOS)),
        ("… sem dono, não fechadas e NÃO bloqueadas (o filtro real, sem dono)",
         _SQL_QUANTAS_SEM_DONO + f"   AND a.ActivityCode IN ({codigos})"
         + f"\n   AND COALESCE(t.AppointmentStatus, '') NOT IN ({fechados})"
         + _SQL_NAO_BLOQUEADA.format(bloqueadas),
         (corte, *alvo, *FECHADOS, *BLOQUEADAS)),
        ("QUALQUER atividade de qualquer pessoa (o join está de pé?)",
         _SQL_QUANTAS, (corte,)),
    ]
    contagens = []
    for rotulo, sql, params in degraus:
        try:
            linhas = capa_db._consultar(sql, *params)
            contagens.append((rotulo, int(linhas[0][0]) if linhas else 0))
        except capa_db.FalhaDeLeitura as exc:
            contagens.append((rotulo, f"falhou: {exc}"))
    # Os estados que as SUAS tarefas têm. Se aqui aparecer algo que está em
    # ``FECHADOS`` e não devia estar, é a lista de estados que está errada — e
    # ela é a única parte deste módulo que foi escrita por leitura de
    # vocabulário, sem ver uma linha real.
    sql_estados = _SQL_POR_ESTADO
    p_estados = [corte]
    if ctr_resource_ser:
        sql_estados += "   AND o.ctrResourceSer = ?"
        p_estados.append(int(ctr_resource_ser))
    sql_estados += (f"\n   AND a.ActivityCode IN ({codigos})"
                    "\n GROUP BY COALESCE(t.AppointmentStatus,"
                    " '(sem estado)')")
    try:
        estados = [(capa_db._txt(e), int(n)) for e, n in
                   capa_db._consultar(sql_estados, *p_estados, *alvo)]
    except capa_db.FalhaDeLeitura as exc:
        estados = [(f"falhou: {exc}", 0)]
    return {"degraus": contagens, "estados": estados, "desde": corte}


def _dias_atras(dias: int) -> date:
    import datetime
    return datetime.date.today() - datetime.timedelta(days=dias)


def _data(valor) -> Optional[date]:
    """``datetime`` do banco → ``date``. O que não for data vira ``None``,
    nunca hoje: uma pendência datada de hoje por engano sobe para o topo da
    lista, que é o lugar de mais destaque da tela."""
    if valor is None:
        return None
    try:
        return valor.date()
    except AttributeError:
        return valor if isinstance(valor, date) else None
