r"""O gatilho da exportação: que planos estão prontos para sair do ARIA.

Três condições ao mesmo tempo, decididas em 02/09/2026 e medidas contra o
``variandw`` antes de virarem consulta (ver ``NOTAS.md`` e
``tools/mapear_gatilho.py``):

1. **Documentação disponível** — a atividade do care path aberta e não
   bloqueada por predecessora. Não é reescrita aqui: vem do
   :func:`atividades_db.todas`, que já tem ``VERIFICADO_EM`` preenchido. Aquela
   consulta custou dois defeitos que só o dado real mostrou (a tarefa repetida
   por recurso, e o "alguma predecessora pronta" no lugar de "todas prontas") —
   reescrevê-la aqui seria pagar os dois de novo;
2. **Curso mais recente ATIVO** — ``DimCourse.DimLookupID_ClinicalStatus``. A
   coluna tem **exatamente dois** valores em 30.677 linhas (``ACTIVE`` e
   ``COMPLETED``, medido em 02/09/2026), então não há terceiro estado
   esperando para surpreender;
3. **Plano aprovado** — ``DimPlan.DimLookupID_PlanStatus``, ver
   :data:`APROVADOS`.

**O que NÃO liga estas três coisas: a atividade.** ``DimActivityTransaction``
não tem coluna de curso nenhuma nas 56, e nenhuma tabela do DW sabe de atividade
e de curso ao mesmo tempo — só as de faturamento, que suporiam que toda
Documentação gera captura de cobrança. Por isso a atividade entra aqui apenas
como **janela** ("este paciente tem trabalho pendente"), e quem escolhe o curso
é o ``ClinicalStatus``, não o vínculo que não existe.

**A ordem no tempo é a razão de a marca d'água não morar aqui.** Medido no caso
9000019ANA: a Documentação abriu em 01/09 às 20:03 e o primeiro plano nasceu em
02/09 às 08:32 — doze horas depois. Marcar a atividade como processada na
primeira vez que ela aparece exportaria NADA e nunca mais voltaria àquele
paciente. A atividade é a janela; o **plano** é o evento, e é o ``PlanUID`` com
o estado ao lado que a marca d'água guarda.

**Só leitura**, como todo o resto: este banco é o sistema clínico.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from isocentro.dados import ambiente
from isocentro.banco import atividades_db
from isocentro.banco import capa_db

_LOG = logging.getLogger(__name__)

# Quando esta consulta foi medida contra o banco de verdade — resultado E
# tempo. Vazio: nunca. Enquanto estiver vazio, ``disponivel()`` é falso e a
# tela diz por quê, em vez de mostrar uma lista de "prontos para exportar" que
# ninguém conferiu. Exportar o plano errado é pior que não exportar.
#
# Para preencher: rodar contra o servidor, comparar plano a plano com o que o
# ARIA mostra para os MESMOS pacientes, e anotar a data aqui.
VERIFICADO_EM = "04/09/2026"

# O que foi medido nesse dia, para quem vier depois saber o que a data cobre:
#
# * **resultado**: a consulta devolveu QUATRO Documentações abertas e SEIS
#   planos, e o usuário confirmou, olhando o ARIA na mesma manhã, que são
#   exatamente esses quatro pacientes os disponíveis. Bateu depois de dois
#   defeitos que só o dado real mostrou — o curso anterior ainda ABERTO
#   roubando o lugar do novo, e o curso de QA roubando o do tratamento;
# * **o filtro de estado foi visto excluindo**: três planos ``Rejected`` do
#   9000014BET ficaram de fora ao lado dos dois aprovados do mesmo curso;
# * **as fases foram vistas saindo juntas**: ``1F_gPULMAO_E`` (22 frações) e
#   ``2F_gPULMAO_E`` (8), do mesmo curso — o ``UM_PLANO_POR_CURSO = False``
#   valendo num caso real;
# * **o retratamento foi exercitado**: o 9000014BET tem 14 cursos, treze
#   ``COMPLETED`` desde 2023, e o filtro pegou o único ``ACTIVE``;
# * **tempo**: 0,8 s, contra o limite de 6 s do ``capa_db``.
#
# O que a data NÃO cobre, e é preciso ter na cabeça:
#
# * **a janela muda ao longo do dia.** A rodada das 08:11 do MESMO dia teria
#   passado na conferência: os dois pacientes com curso de QA ainda não
#   estavam nela. Uma rodada boa não é prova; foi por isso que este bloco
#   demorou dois consertos para existir;
# * **a defasagem da carga do DW.** Planos criados na véspera já apareciam pela
#   manhã, o que descarta a hipótese de um dia de atraso — mas indício não é
#   medida.

# Liga antes de conferir, para poder olhar — mesmo impasse honesto do
# ``atividades_db``: sem conferir não se mostra, e sem mostrar não dá para
# conferir contra o que o ARIA diz.
ENV_EXPERIMENTAL = "ISOCENTRO_GATILHO_EXPERIMENTAL"

# O que conta como "plano aprovado" — decisão do serviço, 02/09/2026.
#
# ``Planning Approved`` e NÃO ``Treatment Approved``: o segundo só vem **depois
# do controle de qualidade**, e é justamente a exportação que alimenta esse
# controle. Esperar por ele seria esperar o resultado do trabalho para entregar
# o material do trabalho.
#
# O caso 9000019ANA confirma que a escolha é a única que funciona hoje: com a
# Documentação aberta, o plano bom estava em ``Planning Approved`` e nenhum
# havia chegado a ``Treatment Approved``.
#
# A escada inteira do Eclipse, medida em 74.171 linhas: Unapproved, Planning
# Approved, Treatment Approved, Reviewed, 3rd Party Approval, Rejected,
# Retired, Completed, Completed Early, Unplanned Treatment. Acrescentar um
# valor aqui é decisão de quem conhece o fluxo, não minha.
APROVADOS = ("Planning Approved",)

# O curso vale? ``ACTIVE`` em maiúsculas é como o banco escreveu — a
# comparação vai como veio, sem confiar no collation do servidor para ignorar
# caixa.
CURSO_ATIVO = "ACTIVE"

# TODOS os planos aprovados do curso — decisão do serviço, 02/09/2026.
#
# A primeira resposta foi "um por curso, o mais recente", e ela foi revista na
# mesma conversa pela razão que a derruba: tratamento de FASES. Primário e
# boost são dois planos aprovados do mesmo curso, os dois tratam, e os dois têm
# de chegar à sala — com um por curso, o boost aprovado depois faria o primário
# nunca ser exportado, em silêncio.
#
# Continua sendo uma constante, e não uma decisão espalhada pelo código: se um
# dia o serviço quiser o contrário, é aqui.
UM_PLANO_POR_CURSO = False


def conferido() -> bool:
    """A consulta foi medida contra o banco? Diferente de estar LIGADA."""
    return bool(VERIFICADO_EM)


def disponivel() -> bool:
    """Dá para confiar nesta lista nesta instalação?"""
    if not capa_db.configurado():
        return False
    if not atividades_db.disponivel():
        return False
    return conferido() or bool(ambiente.ler(ENV_EXPERIMENTAL))


def motivo_indisponivel() -> str:
    """Por que a lista não aparece — em palavras de quem está na frente.

    Três causas, e elas pedem providências diferentes: sem banco é configuração
    do admin; sem a atividade conferida é o degrau de baixo que falta; sem esta
    conferida é trabalho meu que não terminou. Um aviso só para as três ensina
    a ignorar o aviso.
    """
    if not capa_db.configurado():
        return ("O sistema (banco de dados) não está apontado nesta "
                "instalação. Configurações → Serviço, campo “Sistema”.")
    if not atividades_db.disponivel():
        return atividades_db.motivo_indisponivel()
    if not conferido():
        return ("A escolha de quais planos exportar ainda não foi conferida "
                "contra este banco. Enquanto isso, nada é exportado — mandar "
                "o plano errado para a sala é pior que não mandar nada.")
    return ""


@dataclass
class Pronto:
    """Um plano pronto para exportar. Campo sem fonte no banco fica VAZIO."""
    registro: str = ""          # o registro do paciente, como no papel
    paciente: str = ""
    instancia: int = 0          # a Documentação que abriu a janela
    dim_curso: int = 0
    curso: str = ""             # "C1 SETEMBRO 2026"
    plano: str = ""             # ``PlanSetupId`` — "cCRANIO_20Gy".
    # ``PlanSetupName`` NÃO entra: veio vazio nos dois planos do caso real de
    # 02/09/2026. Quem identifica o plano é o ``PlanSetupId``.
    plan_uid: str = ""          # o SOPInstanceUID do RTPLAN — é o que vai no
                                # C-MOVE, e é a identidade na marca d'água
    estado: str = ""            # "Planning Approved", como o banco escreveu
    revisao: int = 0
    fracoes: int = 0
    aprovado_por: str = ""      # ``StatusUserName`` — quem pôs o estado
    criado_em: Optional[datetime] = None

    def chave(self) -> tuple:
        """A identidade na marca d'água: o UID **com o estado**.

        Só o UID não basta. Um plano que sobe de ``Planning Approved`` para
        ``Treatment Approved``, ou que ganha revisão, é um evento NOVO — com a
        chave só no UID, a segunda versão seria vista como já exportada e a
        sala receberia a primeira para sempre.
        """
        return (self.plan_uid, self.estado)


def prontos(desde: Optional[date] = None) -> list:
    """Os planos prontos para os pacientes com Documentação na janela AGORA.

    Levanta :class:`capa_db.FalhaDeLeitura` quando não deu para perguntar —
    **não** devolve lista vazia. A diferença é tudo: vazio significa "nada a
    exportar", e é assim que uma automação silenciosamente para de funcionar.

    **Isto sozinho não basta para automatizar**, e a razão foi vista no ARIA em
    02/09/2026: o estado da atividade é PASSAGEIRO. A Documentação do
    9000019ANA passou de "disponível" a "em andamento" entre duas rodadas, e um
    dia chegará a "Completed" — que sai da janela e não volta. Quem sonda o
    estado ATUAL perde o gatilho sempre que a mudança cai entre duas sondagens.
    Por isso quem manda na janela é o ``gatilho_registro``, que ANOTA a
    disponibilidade quando a vê; esta função é a fotografia do banco, e
    :func:`prontos_de` é a que ele chama.
    """
    janela = atividades_db.todas(desde)
    if not janela:
        return []
    # Um registro pode ter mais de uma Documentação aberta; a janela é do
    # PACIENTE, e o que interessa é a primeira (a mais recente, que é como o
    # ``atividades_db`` já ordena).
    por_registro: dict = {}
    for a in janela:
        if a.registro and a.registro not in por_registro:
            por_registro[a.registro] = a
    return prontos_de(por_registro)


def prontos_de(por_registro: dict) -> list:
    """Os planos aprovados dos pacientes desta janela, venha ela de onde vier.

    ``por_registro`` mapeia o registro do paciente para algo com ``paciente`` e
    ``instancia`` — a :class:`atividades_db.Atividade` de agora, ou a lembrança
    que o ``gatilho_registro`` guardou de quando ela ainda estava disponível.
    Aceitar as duas é o ponto: o plano pode ser aprovado DEPOIS de a atividade
    mudar de estado, e nesse caso a única memória de que houve janela é a
    anotada.
    """
    if not por_registro:
        return []
    # O curso escolhido vem da tabela de CURSOS, e essa consulta é separada por
    # um motivo medido: até 04/09/2026 o curso saía das próprias linhas de
    # plano — a primeira de cada paciente, já ordenadas por início decrescente.
    # Mas ``_planos_aprovados`` só devolve curso que JÁ TEM plano aprovado.
    # Num retratamento em que o curso anterior ficou ABERTO (ninguém o
    # concluiu) e o novo ainda não tem plano aprovado, o "primeiro" era o
    # ANTIGO: a automação exportaria o tratamento passado do paciente, calada,
    # e a lista teria cara de certa. É a família do ``paralelo.maquina_do_plano``
    # — filtro que, na falta do alvo, cai em cima do vizinho em vez de dizer
    # que não achou.
    escolhido = _curso_de_cada(list(por_registro))
    linhas = _planos_aprovados(list(por_registro))
    achados: list = []
    visto_plano: set = set()
    visto_uid: set = set()
    for linha in linhas:
        (reg, dim_curso, curso, _inicio, setup, uid, revisao, fracoes,
         estado, quem, criado) = linha
        reg = capa_db._txt(reg)
        atividade = por_registro.get(reg)
        if atividade is None:
            continue
        dim_curso = int(dim_curso or 0)
        if dim_curso != escolhido.get(reg):
            continue
        if UM_PLANO_POR_CURSO and dim_curso in visto_plano:
            continue
        visto_plano.add(dim_curso)
        # Sem o corte por curso, o desempate que sobra é o do UID: a consulta
        # pode devolver o mesmo plano duas vezes se um paciente aparecer em
        # mais de uma Documentação aberta, e plano repetido na pasta é
        # exatamente o tipo de coisa que ninguém confere.
        if uid and uid in visto_uid:
            continue
        visto_uid.add(uid)
        achados.append(Pronto(
            registro=reg, paciente=atividade.paciente,
            instancia=atividade.instancia,
            dim_curso=dim_curso, curso=capa_db._txt(curso),
            plano=capa_db._txt(setup), plan_uid=capa_db._txt(uid),
            estado=capa_db._txt(estado),
            revisao=int(revisao or 0), fracoes=int(fracoes or 0),
            aprovado_por=capa_db._txt(quem), criado_em=criado))
    return achados


# ── A consulta ──────────────────────────────────────────────────────────────
#
# Duas junções com ``DimLookup``, uma para cada estado: o DW da Varian guarda
# quase todo vocabulário por chave, e comparar o inteiro seria escrever na
# consulta um número que muda de instalação para instalação.
#
# ``GetPatientPlan`` é o caminho do paciente ao plano que NÃO passa por sessão
# aplicada — são duas colunas, ``DimPatientID`` e ``DimPlanID``, uma linha por
# plano (74.298 contra 74.171 da ``DimPlan``). Ir por ``FactTreatmentHistory``,
# que é o caminho que o ``tratamento_db`` usa, enxergaria só quem já tratou —
# e o caso que esta automação existe para pegar é justamente o que ainda não
# tratou.
#
# O ``pl.DimCourseID = c.DimCourseID`` no ON, e não no WHERE: sem ele o produto
# casaria todo plano do paciente com todo curso dele, e o retratamento sairia
# com o plano do curso anterior pendurado no curso novo.
_SQL_PLANOS = """
SELECT p.PatientId,
       c.DimCourseID,
       c.CourseId,
       c.CourseStartDateTime,
       pl.PlanSetupId,
       pl.PlanUID,
       pl.PlanRevision,
       pl.NoFractionsPlanned,
       lp.LookupDescriptionENU,
       pl.StatusUserName,
       pl.CreationDate
  FROM DWH.DimPatient p
  JOIN DWH.DimCourse c
    ON c.DimPatientID = p.DimPatientID
  JOIN DWH.DimLookup lc
    ON lc.DimLookupID = c.DimLookupID_ClinicalStatus
   AND lc.DimLookupID <> 0
  JOIN DWH.GetPatientPlan gp
    ON gp.DimPatientID = p.DimPatientID
  JOIN DWH.DimPlan pl
    ON pl.DimPlanID = gp.DimPlanID
   AND pl.DimCourseID = c.DimCourseID
  JOIN DWH.DimLookup lp
    ON lp.DimLookupID = pl.DimLookupID_PlanStatus
   AND lp.DimLookupID <> 0
 WHERE lc.LookupDescriptionENU = ?
"""


def _planos_aprovados(registros: list, so_aprovados: bool = True) -> list:
    """As linhas cruas, ordenadas para o desempate do :func:`prontos`.

    A ordenação é parte da consulta e não do Python de propósito: é o
    ``ORDER BY`` que define qual curso é "o mais recente" e qual plano é "o
    mais novo", e deixar isso implícito num ``sorted`` daria a mesma lista até
    o dia em que o banco devolvesse a ordem natural diferente.

    ``so_aprovados`` falso solta o filtro de estado do PLANO — e só ele; o
    curso continua tendo de estar ativo. Serve ao :func:`porque_vazio`, que
    precisa distinguir "nenhum curso ativo" de "curso ativo sem plano
    aprovado": as duas coisas dão lista vazia e pedem providências opostas.
    """
    if not registros:
        return []
    alvos = ",".join(["?"] * len(registros))
    partes = [_SQL_PLANOS, f"   AND p.PatientId IN ({alvos})"]
    params = [CURSO_ATIVO, *registros]
    if so_aprovados:
        aprovados = ",".join(["?"] * len(APROVADOS))
        partes.append(f"   AND lp.LookupDescriptionENU IN ({aprovados})")
        params += list(APROVADOS)
    partes.append(" ORDER BY p.PatientId,"
                  "          c.CourseStartDateTime DESC,"
                  "          pl.CreationDate DESC,"
                  "          pl.PlanRevision DESC")
    return capa_db._consultar("\n".join(partes), *params)


_SQL_CURSO_ATIVO = """
SELECT DISTINCT p.PatientId
  FROM DWH.DimPatient p
  JOIN DWH.DimCourse c
    ON c.DimPatientID = p.DimPatientID
  JOIN DWH.DimLookup lc
    ON lc.DimLookupID = c.DimLookupID_ClinicalStatus
   AND lc.DimLookupID <> 0
 WHERE lc.LookupDescriptionENU = ?
"""


def _com_curso_ativo(registros: list) -> list:
    """Quem tem curso ativo — SEM tocar em plano.

    Separada da consulta grande de propósito. Aquela junta ``GetPatientPlan``
    por dentro, e junção interna some com o paciente que tem curso ativo e
    **nenhum plano ainda** — que é o estado mais comum de todos, e foi o do
    9000019ANA por doze horas. Contando por lá, "o plano ainda não existe"
    sairia no diagnóstico como "o curso fechou", que manda procurar no lugar
    errado.
    """
    if not registros:
        return []
    alvos = ",".join(["?"] * len(registros))
    sql = _SQL_CURSO_ATIVO + f"   AND p.PatientId IN ({alvos})"
    return capa_db._consultar(sql, CURSO_ATIVO, *registros)


# A intenção entra por LEFT JOIN, e a ordem dela é a regra: curso de QA
# ("QA_C1_SET_2026", "C1-QA NAO TRATAR") vem com intenção VAZIA, e vai para o
# fim para não roubar o lugar do curso real. É a mesma cláusula do
# ``capa_db._SQL_CURSO``, e não por simetria — foi medida contra o banco em
# 04/09/2026 e o gatilho estava errando exatamente ali (ver abaixo).
_SQL_CURSOS = """
SELECT p.PatientId,
       c.DimCourseID,
       c.CourseId,
       c.CourseStartDateTime,
       lc.LookupDescriptionENU,
       lint.LookupDescriptionPTB
  FROM DWH.DimPatient p
  JOIN DWH.DimCourse c
    ON c.DimPatientID = p.DimPatientID
  JOIN DWH.DimLookup lc
    ON lc.DimLookupID = c.DimLookupID_ClinicalStatus
   AND lc.DimLookupID <> 0
  LEFT JOIN DWH.DimLookup lint
         ON lint.DimLookupID = c.DimLookupID_TreatmentIntentType
        AND lint.DimLookupID <> 0
"""


def _cursos(registros: list) -> list:
    """TODOS os cursos destes pacientes, ativos ou não, do mais novo ao antigo.

    Sem filtro de estado de propósito: é ele que se está conferindo. Um
    relatório que já chega filtrado não permite ver o curso que ficou de fora —
    e "ficou de fora" é justamente o que não aparece numa lista.
    """
    if not registros:
        return []
    alvos = ",".join(["?"] * len(registros))
    sql = (_SQL_CURSOS + f" WHERE p.PatientId IN ({alvos})"
           " ORDER BY p.PatientId,"
           "          CASE WHEN lint.LookupDescriptionPTB IS NULL"
           "               THEN 1 ELSE 0 END,"
           "          c.CourseStartDateTime DESC")
    return capa_db._consultar(sql, *registros)


def _curso_de_cada(registros: list) -> dict:
    """Registro → o ``DimCourseID`` do curso de TRATAMENTO ativo mais recente.

    Zero quando não há nenhum. A regra inteira do degrau 2 mora aqui, e ela é
    deliberadamente burra: entre os ativos, o de tratamento mais recente,
    ponto. Sem plano nele a resposta é "nenhum plano ainda" — nunca o curso
    anterior, nunca o de QA. Filtro que procura outro alvo quando não acha o
    seu devolve lista plausível e errada.

    **Quem separa tratamento de QA é o ``ORDER BY`` do :func:`_cursos`**, pela
    intenção vazia. Isto aqui só pega o primeiro que o banco devolver, e é de
    propósito: com a regra escrita nos dois lugares, um dia eles discordam.
    """
    escolhido: dict = {}
    for linha in _cursos(registros):
        reg, dim_curso, _curso, _inicio, estado, _intencao = linha
        reg = capa_db._txt(reg)
        # Comparação sem caixa: o SQL Server casa ``= 'ACTIVE'`` sem olhar
        # caixa (collation padrão), e uma comparação estrita AQUI seria mais
        # apertada que a da consulta — o paciente passaria pelo filtro do banco
        # e desapareceria no Python, sem erro nenhum. É a armadilha que o
        # ``test_o_curso_ativo_vai_por_PARAMETRO`` já guardava do outro lado.
        if capa_db._txt(estado).upper() != CURSO_ATIVO.upper():
            continue
        if reg in escolhido:
            continue
        escolhido[reg] = int(dim_curso or 0)
    return escolhido


def porque_vazio(desde: Optional[date] = None) -> dict:
    """Onde a lista morreu — para "nada a exportar" não se confundir com bug.

    Uma automação que para de funcionar é silenciosa por natureza: ninguém
    percebe a ausência de um arquivo. Isto conta os degraus para que a tela
    possa dizer QUAL deles zerou — mesma ideia do ``atividades_db``.
    """
    janela = atividades_db.todas(desde)
    registros = sorted({a.registro for a in janela if a.registro})
    conta = {"documentacoes": len(janela), "pacientes": len(registros),
             "com_curso_ativo": 0, "com_algum_plano": 0,
             "com_plano_aprovado": 0, "prontos": 0}
    if not registros:
        return conta
    # Três consultas, e são as DIFERENÇAS entre elas que diagnosticam. Os três
    # degraus falham do mesmo jeito — lista vazia — e pedem providências
    # opostas:
    #
    # * caiu de ``pacientes`` para ``com_curso_ativo``: o curso fechou (ou a
    #   Documentação é de um curso antigo);
    # * caiu para ``com_algum_plano``: o plano ainda não foi criado. É o estado
    #   mais comum, e durou doze horas no 9000019ANA;
    # * caiu para ``com_plano_aprovado``: o plano existe e está em rascunho ou
    #   rejeitado — é espera legítima, não defeito.
    #
    # A FalhaDeLeitura sobe: aqui vazio é resposta, e "não consegui perguntar"
    # não pode virar zero.
    conta["com_curso_ativo"] = len(
        {linha[0] for linha in _com_curso_ativo(registros)})
    conta["com_algum_plano"] = len(
        {linha[0] for linha in _planos_aprovados(registros, False)})
    conta["com_plano_aprovado"] = len(
        {linha[0] for linha in _planos_aprovados(registros)})
    conta["prontos"] = len(prontos(desde))
    return conta


# ── A conferência ───────────────────────────────────────────────────────────


@dataclass
class Dossie:
    """O que aconteceu com UMA Documentação aberta, do começo ao fim.

    Existe para a conferência contra o ARIA, e o motivo é o defeito da primeira
    rodada (02/09/2026): o relatório listava os planos que SAÍRAM, e uma lista
    de vencedores não deixa ver quem não concorreu. "Faltou o fulano" e "o
    fulano não tinha plano aprovado" são a mesma tela em branco, e só o segundo
    é resposta.

    Por isso aqui entra uma linha por paciente da janela, tenha ele saído ou
    não, com os cursos que ficaram de fora e os planos que o filtro recusou.
    """
    registro: str = ""
    paciente: str = ""
    instancia: int = 0
    cursos: list = field(default_factory=list)   # (dim, id, inicio, estado, intencao, escolhido)
    planos: list = field(default_factory=list)   # (setup, uid, rev, estado, quem, criado, sai)
    degrau: str = ""            # onde a corrente parou, em palavras

    @property
    def saiu(self) -> bool:
        return any(p[6] for p in self.planos)


def conferencia(desde: Optional[date] = None) -> list:
    """Um :class:`Dossie` por paciente da janela — a saída que se compara.

    Não é a consulta da automação: é a MESMA corrente, aberta passo a passo
    para poder ser lida ao lado do ARIA. As decisões saem daqui idênticas às do
    :func:`prontos_de` porque vêm das mesmas funções, e não de uma segunda
    versão da regra escrita para o relatório — régua de conferência que copia a
    regra envelhece calada e passa a aprovar o que a de verdade recusa.
    """
    janela = atividades_db.todas(desde)
    por_registro: dict = {}
    for a in janela:
        if a.registro and a.registro not in por_registro:
            por_registro[a.registro] = a
    if not por_registro:
        return []

    registros = list(por_registro)
    escolhido = _curso_de_cada(registros)
    # Todos os estados de plano: o rejeitado no relatório é metade da prova de
    # que o filtro funciona — foi assim que se viu, em 02/09/2026, o ``1``
    # (Rejected) ficar de fora do curso 30658 sem ninguém precisar notar.
    linhas = _planos_aprovados(registros, False)
    saindo = {(p.registro, p.plan_uid) for p in prontos_de(por_registro)}

    por_curso: dict = {}
    for linha in _cursos(registros):
        reg, dim, curso, inicio, estado, intencao = linha
        reg = capa_db._txt(reg)
        dim = int(dim or 0)
        # A INTENÇÃO no relatório não é enfeite: é ela que explica por que um
        # curso ganhou do outro. Sem ela, "escolheu o de 03/09 e não o de
        # 01/09" parece a regra da data — e foi assim que o curso de QA passou
        # despercebido até 04/09/2026.
        por_curso.setdefault(reg, []).append(
            (dim, capa_db._txt(curso), inicio, capa_db._txt(estado),
             capa_db._txt(intencao), dim == escolhido.get(reg)))

    por_plano: dict = {}
    for linha in linhas:
        (reg, dim, _curso, _inicio, setup, uid, revisao, _fr, estado, quem,
         criado) = linha
        reg = capa_db._txt(reg)
        if int(dim or 0) != escolhido.get(reg):
            continue        # curso antigo: não é candidato, e não confunde
        uid = capa_db._txt(uid)
        por_plano.setdefault(reg, []).append(
            (capa_db._txt(setup), uid, int(revisao or 0),
             capa_db._txt(estado), capa_db._txt(quem), criado,
             (reg, uid) in saindo))

    dossies = []
    for reg, atividade in por_registro.items():
        cursos = por_curso.get(reg, [])
        planos = por_plano.get(reg, [])
        if not escolhido.get(reg):
            degrau = ("nenhum curso ATIVO" if cursos else
                      "o paciente não tem curso nenhum no banco")
        elif not planos:
            degrau = "curso ativo, nenhum plano ainda"
        elif not any(p[6] for p in planos):
            degrau = f"plano existe, nenhum em {' / '.join(APROVADOS)}"
        else:
            degrau = "pronto"
        dossies.append(Dossie(
            registro=reg, paciente=atividade.paciente,
            instancia=atividade.instancia, cursos=cursos, planos=planos,
            degrau=degrau))
    return dossies
