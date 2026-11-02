"""A AGENDA por máquina: quem está marcado, em qual acelerador, em qual dia —
a fonte da aba **Agenda**.

O :mod:`tratamento_db` lê o que ACONTECEU (frações entregues); este lê o que
está MARCADO, independente de já ter sido tratado hoje ou ainda estar por vir.
É outra metade do banco, e o risco de sempre: o silencioso. Recurso errado não
dá erro — devolve uma lista plausível de nomes, no dia certo, de OUTRA sala.

**O PORTÃO** — ``VERIFICADO_EM``

Enquanto vazio, tudo aqui devolve vazio e a tela diz que o mapeamento não foi
conferido. Ver o mesmo portão em :mod:`tratamento_db`.

O que está resolvido, e não por adivinhação — mapeado em 23/09/2026 com
``tools/mapear_agenda.py`` contra o banco real (1.698 marcações do dia
23/09/2026), por DUAS fontes independentes que bateram uma com a outra:

* **``DWH.InSightiveResourceMachine``** é o catálogo dedicado de
  recurso↔máquina: já traz ``ctrResourceSer``, ``MachineId`` (o mesmo texto
  que a Ficha Virtual mostra na coluna "máquina") e ``ResourceObjectStatus``
  ("Active"/"Deleted" — e ela já marca "NAO USAR" e "600CVELHO" como
  ``Deleted`` sozinha, sem precisar de lista própria). **Não é
  ``DWH.DimMachine`` sozinha**: lá o ``ctrResourceSer`` veio vazio nas 24
  linhas lidas, e não dá para juntar com a marcação por ali.
* Bateu com a contagem de marcações do dia: os quatro ``ctrResourceSer`` mais
  marcados no dia conferido (1035, 1046, 1252, 1499) são justamente os quatro
  aceleradores ativos do catálogo, com conteúdo de agenda real — pacientes em
  blocos de 12 minutos, atividade nomeada pelo SÍTIO tratado.
* **``AppointmentDateTime`` é a data/hora AGENDADA** — bateu com
  ``DerivedAppointmentTaskDate`` nas 1.698 linhas lidas. ``ActivityStart
  DateTime`` é quando a marcação foi de fato aberta no ARIA (minutos ou horas
  depois, ou vazia se cancelada) e NÃO serve à tela.
* **A sessão de tratamento não tem UM código.** É uma atividade por SÍTIO
  (``PELVE``, ``MAMA``, ``CP``, ``PROSTATA``, ``ABDOMEN``, ``PALIATIVO``,
  ``EXTREMIDADE``, ``PELE``, e ``Tomografia`` para a simulação) — todas na
  categoria ``05 Tratamento``/``04 Tratamento`` do catálogo, mas o código muda
  por sítio. Por isso a agenda **não filtra por atividade**: mostra tudo o que
  está marcado naquela máquina, do estado que interessa.
* **Os estados reais do serviço** (medidos, não do manual): ``Completed``,
  ``Open``, ``Deleted``, ``Cancelled``, ``Manually Completed``,
  ``In Progress``, ``Cancelled - Patient No-Show``, ``Pt. CompltFinish``. Só
  os três primeiros da lista negativa (:data:`ESTADOS_FORA`) somem da agenda —
  o resto fica, porque a agenda do DIA mostra o dia inteiro, passado e futuro,
  e "Completed" de manhã é tão real quanto "Open" à tarde.

O que NÃO está aqui: **a fração atual do paciente** ("12/25"). Ela vive no
:mod:`tratamento_db`, atrás do portão ``LISTA_VERIFICADA_EM`` — que ainda está
VAZIO. Juntar sobre um portão fechado seria herdar o "não conferido" em
silêncio; a agenda mostra hora, paciente e médico, e a fração fica para quando
aquele portão abrir.

Só LEITURA, pela mesma conexão do :mod:`capa_db`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from isocentro.banco import capa_dados
from isocentro.banco import capa_db

_LOG = logging.getLogger(__name__)

# Data em que o SQL deste módulo foi conferido contra o banco real, no formato
# DD/MM/AAAA. Ver o portão no docstring do módulo e a rodada completa no
# ``NOTAS.md`` de 23/09/2026.
VERIFICADO_EM = "23/09/2026"


def disponivel() -> bool:
    """Dá para mostrar a agenda nesta instalação?"""
    return bool(VERIFICADO_EM) and capa_db.configurado()


def motivo_indisponivel() -> str:
    """Por que a aba não mostra nada — em palavras de quem está na frente dela."""
    if not capa_db.configurado():
        return ("O sistema (banco de dados) não está apontado nesta instalação. "
                "Configurações → Serviço, campo “Sistema”.")
    if not VERIFICADO_EM:
        return ("A leitura da agenda ainda não foi conferida contra este "
                "banco. Enquanto isso, esta aba não mostra números — uma "
                "agenda plausível e errada é pior que nenhuma.")
    return ""


# ── Estados ──────────────────────────────────────────────────────────────

# Os três que a agenda NÃO mostra. Lista NEGATIVA de propósito, como a
# ``atividades_db.FECHADOS``: um estado novo do ARIA tem de APARECER — sumir
# em silêncio é o erro que este painel não pode cometer.
ESTADOS_FORA: tuple[str, ...] = (
    "Deleted", "Cancelled", "Cancelled - Patient No-Show",
)


# ── Máquinas ─────────────────────────────────────────────────────────────

@dataclass
class Maquina:
    """Um acelerador (ou braquiterapia/ortovoltagem) agendável.

    ``nome`` é o de EXIBIÇÃO (ver :func:`_nome_exibicao`) — não é mais o
    ``MachineId`` cru desde 23/09/2026: o médico lê "Braquiterapia", não
    "GammaMed Plus". ``machine_id`` guarda o original, para quem precisar
    casar com outra tela (a Ficha Virtual mostra o ``MachineId`` cru).
    """
    nome: str = ""
    ctr_resource_ser: int = 0
    machine_id: str = ""


# Só "Dispositivo de radiação": os aceleradores, a braquiterapia
# (``GammaMed Plus``) e a ortovoltagem (``Ortovoltagem``/Dermopan) — decisão do
# usuário em 23/09/2026, depois de ver a lista real. Ficam DE FORA os
# tomógrafos de simulação (``Tomo UNI/BUE/ANA``, "Dispositivo de imagens") e os
# subsistemas de imagem portal de cada acelerador (``MV_...``, ``KV_...``,
# ``MVCBCT_...`` — o mesmo acelerador aparecendo três vezes na lista, uma por
# componente técnico, não por sala).
_SQL_MAQUINAS = """
SELECT rm.MachineId, rm.MachineFullName, rm.ctrResourceSer
  FROM DWH.InSightiveResourceMachine rm
 WHERE rm.ResourceObjectStatus = 'Active'
   AND rm.MachineType = N'Dispositivo de radiação'
   AND rm.MachineId NOT IN ({excluidas})
 ORDER BY rm.MachineId
"""

# "Eclipse CAP" está Ativa e é "Dispositivo de radiação" no banco, mas não é
# uma máquina de verdade da sala: o usuário viu a agenda real de 23/09/2026 e
# pediu para tirá-la — zero marcações no dia inteiro, ao lado de quatro
# aceleradores com 38 a 59 cada. Lista POSITIVA de exclusão, e não um filtro
# por volume: o banco não diz "isto é fantasma", só o uso real disse, e é
# decisão de quem conhece o serviço, não desta consulta.
MAQUINAS_EXCLUIDAS: tuple[str, ...] = ("Eclipse CAP",)

# O nome que a CLÍNICA usa, quando diverge do que o ARIA guarda em
# ``MachineFullName``. Pedido do usuário em 23/09/2026, depois de ver a
# agenda real: só ``TBuniverSN1002`` precisa de troca — o ARIA chama
# "TB Universitario", a clínica chama "TrueBeam". Os outros três já batem
# sozinhos (``GammaMed Plus`` → "Braquiterapia", ``Ortovoltagem`` →
# "Dermopan", ``TrueBeamSN1001`` → "VitalBeam") e não precisam de entrada
# aqui — ``_nome_exibicao`` só troca o que este dicionário lista.
NOMES_MAQUINA: dict[str, str] = {
    "TBuniverSN1002": "TrueBeam",
}


# ── Ocupação e disponibilidade ──────────────────────────────────────────────

# Horário de funcionamento (abre, fecha) de cada máquina — ditado pelo
# usuário em 28/09/2026, para a Taxa de Ocupação e o Índice de
# Disponibilidade (ver :func:`minutos_uteis_do_mes`). Só as quatro que ele
# informou: uma máquina fora daqui não entra em nenhum dos dois — nunca
# inventar expediente para "Braquiterapia"/"Dermopan", que não foram
# citadas.
HORAS_MAQUINA: dict[str, tuple[int, int]] = {
    "600CD": (8, 18),
    "VitalBeam": (7, 16),
    "6EX": (8, 18),
    "TrueBeam": (7, 20),
}

# Intervalo (almoço) SEM paciente, descontado do expediente de
# :data:`HORAS_MAQUINA` — pedido do usuário em 28/09/2026: "na 600cd, entre
# as 12h e as 14h não tem paciente, aí é só 8h por dia". Só a 600CD tem
# entrada aqui — as outras três não têm intervalo relatado, e inventar um
# igual faria o mesmo erro que ``HORAS_MAQUINA`` evita: afirmar uma folga
# que ninguém confirmou.
PAUSA_MAQUINA: dict[str, tuple[int, int]] = {
    "600CD": (12, 14),
}

# Minutos por sessão de tratamento — bloco FIXO, pedido do usuário em
# 28/09/2026 ("considere... blocos de 12 minutos"), o mesmo valor medido no
# mapeamento de 23/09/2026 (ver o docstring do módulo: "pacientes em blocos
# de 12 minutos"). Usado para transformar uma CONTAGEM de sessões em
# minutos — não é uma duração real por marcação (o ARIA não guarda fim de
# atividade aqui), é a mesma aproximação que o usuário pediu para a Taxa de
# Ocupação.
MINUTOS_POR_SESSAO = 12


def minutos_uteis_do_mes(nome_maquina: str, referencia: date,
                         ate: date | None = None) -> int | None:
    """Minutos de expediente de ``nome_maquina`` no mês de ``referencia``
    (dias ÚTEIS — segunda a sexta, mesmo critério de
    ``tratamento_db.dias_uteis_entre``: sem feriado, porque a lista de
    feriados do serviço não está no app e inventar um calendário afirmaria
    uma folga que não houve).

    ``None`` quando ``nome_maquina`` não tem horário em
    :data:`HORAS_MAQUINA` — nunca um número calculado sobre um expediente
    inventado. É o denominador da Taxa de Ocupação e do Índice de
    Disponibilidade; os dois olham o MESMO mês calendário (ver
    :func:`capa_dados.limites_do_mes`).

    Desconta o intervalo de :data:`PAUSA_MAQUINA`, quando a máquina tem um
    relatado (hoje só a 600CD).

    ``ate``: conta só os dias até ``ate`` (inclusive) — o expediente que JÁ
    PASSOU, denominador certo para comparar com sessões já feitas no mês
    corrente. Um mês inteiro no passado não muda; um mês que ainda não
    começou dá 0.
    """
    horas = HORAS_MAQUINA.get(nome_maquina)
    if horas is None:
        return None
    abre, fecha = horas
    minutos_por_dia = (fecha - abre) * 60
    pausa = PAUSA_MAQUINA.get(nome_maquina)
    if pausa is not None:
        pausa_inicio, pausa_fim = pausa
        minutos_por_dia -= (pausa_fim - pausa_inicio) * 60
    inicio_mes, fim_mes = capa_dados.limites_do_mes(referencia)
    if ate is not None:
        fim_mes = min(fim_mes, ate + timedelta(days=1))
    dias_uteis = 0
    dia = inicio_mes
    while dia < fim_mes:
        if dia.weekday() < 5:  # 5 = sábado, 6 = domingo
            dias_uteis += 1
        dia += timedelta(days=1)
    return dias_uteis * minutos_por_dia


def _nome_exibicao(machine_id: str, machine_full_name: str = "") -> str:
    """O nome que a TELA mostra: a troca da clínica, senão o nome completo do
    ARIA, senão o ``MachineId`` cru — nunca vazio enquanto ``machine_id`` não
    for."""
    machine_id = capa_db._txt(machine_id)
    base = capa_db._txt(machine_full_name) or machine_id
    return NOMES_MAQUINA.get(machine_id, base)


def maquinas() -> list:
    """As máquinas de TRATAMENTO ativas — a lista de checkboxes da tela."""
    if not disponivel():
        return []
    # ``NOT IN ()`` vazio é erro de sintaxe no SQL Server — a string vazia
    # como único valor mantém a cláusula válida sem excluir máquina nenhuma,
    # se um dia ``MAQUINAS_EXCLUIDAS`` ficar vazia.
    excluidas = MAQUINAS_EXCLUIDAS or ("",)
    marcas = ",".join("?" for _ in excluidas)
    sql = _SQL_MAQUINAS.format(excluidas=marcas)
    try:
        linhas = capa_db._consultar(sql, *excluidas)
    except capa_db.FalhaDeLeitura:
        return []
    fora = []
    for machine_id, nome_completo, ctr in linhas:
        machine_id = capa_db._txt(machine_id)
        if machine_id and ctr:
            fora.append(Maquina(
                nome=_nome_exibicao(machine_id, nome_completo),
                ctr_resource_ser=int(ctr), machine_id=machine_id))
    return fora


# ── Médicos (o filtro que ESMAECE) ──────────────────────────────────────

def medicos() -> list:
    """Os radio-oncologistas da equipe — a MESMA lista do :mod:`tratamento_db`
    (mesmo casamento de nome, mesmo filtro pela equipe configurada), atrás do
    portão DESTA aba, não do da Virtual.

    A Virtual tem o próprio portão (``tratamento_db.LISTA_VERIFICADA_EM``) e
    ele pode estar fechado — ainda está, em 23/09/2026 — sem que isso deva
    esvaziar o seletor de médico daqui: a Agenda não lê nada daquele portão, só
    o nome de quem já está vinculado ao paciente.
    """
    if not disponivel():
        return []
    from isocentro.banco import tratamento_db
    return tratamento_db._medicos_do_banco()


# ── A agenda do dia ──────────────────────────────────────────────────────

@dataclass
class Marcacao:
    """Uma linha da agenda: um paciente, numa máquina, numa hora.

    ``medico`` vem do vínculo do paciente (``DimPatientDoctor``), não de quem
    marcou a atividade — é o mesmo médico que a Ficha Virtual mostra.
    ``mais_de_um_medico`` avisa quando o paciente tem mais de um oncologista
    vinculado, para a tela não escolher um dos dois em silêncio.

    O FILTRO por médico é da TELA, não desta consulta: ela sempre traz o dia
    inteiro da máquina, e quem decide apagar ou não uma linha é quem monta a
    coluna — decisão do usuário em 23/09/2026, para a máquina continuar
    mostrando que está ocupada mesmo fora do filtro escolhido.
    """
    hora: Optional[datetime] = None
    maquina: str = ""
    registro: str = ""
    paciente: str = ""
    atividade: str = ""
    estado: str = ""
    medico: str = ""
    medico_bruto: str = ""
    mais_de_um_medico: bool = False


_SQL_AGENDA_DO_DIA = """
SELECT t.AppointmentDateTime,
       rm.MachineId,
       rm.MachineFullName,
       p.PatientId,
       p.PatientFullName,
       a.ActivityNamePTB,
       t.AppointmentStatus,
       md.DoctorFullName,
       md.Quantos
  FROM DWH.DimActivityTransaction t
  JOIN DWH.InSightiveResourceMachine rm ON rm.ctrResourceSer = t.ctrResourceSer
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
  LEFT JOIN DWH.DimPatient p ON p.DimPatientID = t.DimPatientID
  -- Subconsulta JÁ AGRUPADA por paciente, como em ``tratamento_db``: o
  -- paciente pode ter mais de um vínculo de médico, e um JOIN direto
  -- multiplicaria a linha da marcação — uma sessão viraria duas na tela.
  LEFT JOIN (SELECT pd.DimPatientID,
                    MIN(d.DoctorFullName) AS DoctorFullName,
                    COUNT(DISTINCT d.DoctorFullName) AS Quantos
               FROM DWH.DimPatientDoctor pd
               JOIN DWH.DimDoctor d ON d.ctrResourceSer = pd.ctrResourceSer
              WHERE pd.OncologistFlag = 1
              GROUP BY pd.DimPatientID) md
         ON md.DimPatientID = t.DimPatientID
 WHERE CAST(t.AppointmentDateTime AS date) = ?
   AND t.ctrResourceSer IN ({marcas})
   AND t.AppointmentStatus NOT IN ({estados})
   AND ISNULL(p.IsMOTestPatient, 0) = 0
 ORDER BY rm.MachineId, t.AppointmentDateTime
"""


def _linhas_para_marcacoes(linhas) -> list:
    """As colunas cruas do SQL (mesma forma em ``_SQL_AGENDA_DO_DIA`` e
    ``_SQL_AGENDA_DO_PERIODO``) viram :class:`Marcacao` — extraído para as
    duas consultas não divergirem no dia em que uma ganhar um campo e a
    outra não."""
    fora = []
    for (hora, maquina, maquina_completa, registro, paciente, atividade,
        estado, medico_bruto, quantos) in linhas:
        fora.append(Marcacao(
            hora=hora,
            maquina=_nome_exibicao(maquina, maquina_completa),
            registro=capa_db._txt(registro),
            paciente=capa_dados.de_pessoa(capa_db._txt(paciente)),
            atividade=capa_db._txt(atividade),
            estado=capa_db._txt(estado),
            medico=capa_dados.de_pessoa(capa_db._txt(medico_bruto)),
            medico_bruto=capa_db._txt(medico_bruto),
            mais_de_um_medico=bool(quantos and int(quantos) > 1)))
    return fora


def agenda_do_dia(dia: date, maquinas_marcadas: list) -> list:
    """A agenda de ``dia``, nas máquinas de ``maquinas_marcadas``.

    ``maquinas_marcadas``: :class:`Maquina` (ou o ``ctr_resource_ser`` cru).
    Vazio devolve lista vazia sem consultar — é o estado "nenhuma máquina
    marcada" da tela, não um erro.

    Devolve ``None`` quando NÃO DEU para perguntar ao banco, e ``[]`` quando o
    banco respondeu que não há marcação nenhuma naquele dia — a mesma
    distinção do ``tratamento_db.em_tratamento``.
    """
    if not disponivel():
        return None
    ctrs = [m.ctr_resource_ser if isinstance(m, Maquina) else int(m or 0)
           for m in (maquinas_marcadas or [])]
    ctrs = [c for c in ctrs if c]
    if not ctrs:
        return []
    marcas_maquina = ",".join("?" for _ in ctrs)
    marcas_estado = ",".join("?" for _ in ESTADOS_FORA)
    sql = _SQL_AGENDA_DO_DIA.format(marcas=marcas_maquina, estados=marcas_estado)
    try:
        linhas = capa_db._consultar(
            sql, dia.strftime("%Y-%m-%d"), *ctrs, *ESTADOS_FORA)
    except capa_db.FalhaDeLeitura:
        return None
    return _linhas_para_marcacoes(linhas)


# A mesma consulta de ``_SQL_AGENDA_DO_DIA``, MESMO ``VERIFICADO_EM`` (só o
# filtro de data virou intervalo) — pedido do usuário em 25/09/2026:
# "adicione intervalo de data pra ser possivel ver a agenda de multiplos
# dias". ``>= ? AND < ?`` em vez de ``CAST(...) = ?``: o mesmo padrão de
# ``tratamento_db.resumo_mensal_por_maquina`` para não incluir a meia-noite
# do dia seguinte por um ``<=`` folgado.
_SQL_AGENDA_DO_PERIODO = """
SELECT t.AppointmentDateTime,
       rm.MachineId,
       rm.MachineFullName,
       p.PatientId,
       p.PatientFullName,
       a.ActivityNamePTB,
       t.AppointmentStatus,
       md.DoctorFullName,
       md.Quantos
  FROM DWH.DimActivityTransaction t
  JOIN DWH.InSightiveResourceMachine rm ON rm.ctrResourceSer = t.ctrResourceSer
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
  LEFT JOIN DWH.DimPatient p ON p.DimPatientID = t.DimPatientID
  LEFT JOIN (SELECT pd.DimPatientID,
                    MIN(d.DoctorFullName) AS DoctorFullName,
                    COUNT(DISTINCT d.DoctorFullName) AS Quantos
               FROM DWH.DimPatientDoctor pd
               JOIN DWH.DimDoctor d ON d.ctrResourceSer = pd.ctrResourceSer
              WHERE pd.OncologistFlag = 1
              GROUP BY pd.DimPatientID) md
         ON md.DimPatientID = t.DimPatientID
 WHERE t.AppointmentDateTime >= ? AND t.AppointmentDateTime < ?
   AND t.ctrResourceSer IN ({marcas})
   AND t.AppointmentStatus NOT IN ({estados})
   AND ISNULL(p.IsMOTestPatient, 0) = 0
 ORDER BY rm.MachineId, t.AppointmentDateTime
"""


def agenda_do_periodo(inicio: date, fim: date, maquinas_marcadas: list) -> list:
    """A agenda de ``inicio`` a ``fim`` (os DOIS dias INCLUÍDOS), nas
    máquinas de ``maquinas_marcadas`` — pedido do usuário em 25/09/2026:
    "adicione intervalo de data pra ser possivel ver a agenda de multiplos
    dias". Já vem ordenada por ``AppointmentDateTime`` (dia inteiro depois
    de dia inteiro): quem chama com UMA máquina só (ver o pedido do mesmo
    dia — "ao selecionar multiplos dias deixar somente uma maquina por
    vez" — em ``agenda_tela.PainelAgenda``) recebe a lista pronta para
    desenhar com um cabeçalho por dia.

    ``maquinas_marcadas``: :class:`Maquina` (ou o ``ctr_resource_ser`` cru).
    Vazio devolve lista vazia sem consultar. Devolve ``None`` quando NÃO DEU
    para perguntar ao banco, ``[]`` quando não há marcação nenhuma no
    período — mesma distinção de :func:`agenda_do_dia`.
    """
    if not disponivel():
        return None
    ctrs = [m.ctr_resource_ser if isinstance(m, Maquina) else int(m or 0)
           for m in (maquinas_marcadas or [])]
    ctrs = [c for c in ctrs if c]
    if not ctrs:
        return []
    marcas_maquina = ",".join("?" for _ in ctrs)
    marcas_estado = ",".join("?" for _ in ESTADOS_FORA)
    sql = _SQL_AGENDA_DO_PERIODO.format(
        marcas=marcas_maquina, estados=marcas_estado)
    fim_exclusivo = fim + timedelta(days=1)
    try:
        linhas = capa_db._consultar(
            sql, inicio.strftime("%Y-%m-%d"), fim_exclusivo.strftime("%Y-%m-%d"),
            *ctrs, *ESTADOS_FORA)
    except capa_db.FalhaDeLeitura:
        return None
    return _linhas_para_marcacoes(linhas)


# ── O resumo do MÊS: pacientes distintos agendados, e inícios ───────────

# Pedido do usuário em 25/09/2026: "para saber o número de pacientes
# tratados é só pegar o número distinto de pacientes agendados na máquina
# no período... só isso" — em vez da conta em
# ``tratamento_db.resumo_mensal_por_maquina``, que lia
# ``FactTreatmentHistory`` (frações de fato entregues) e precisava da
# COALESCE de nome de máquina que já causou um bug ali ("20 tratados no
# mês, com 44 pacientes na máquina [num dia só]?", 25/09/2026). Aqui o
# filtro é pelo MESMO ``ctrResourceSer`` que ``_SQL_AGENDA_DO_DIA`` já usa —
# a chave limpa do catálogo, sem ambiguidade de nome — e não precisa da
# subconsulta de fração: uma marcação na agenda já é uma linha por
# (máquina, paciente, atividade), sem repetir por campo/RefPoint como
# ``FactTreatmentHistory`` repete.
#
# ``INICIOS`` — mesmo pedido, na sequência: "inicios (numero de atividades
# que contenham INICIO)". É contagem de MARCAÇÃO (não ``DISTINCT``,
# diferente de pacientes): duas marcações de início no mesmo mês, do mesmo
# paciente (um curso que parou e foi reaberto), são dois inícios de
# verdade.
#
# ``ESTADOS_FORA`` filtra o mesmo trio que a agenda do dia esconde
# (Deleted/Cancelled/No-Show) — uma marcação cancelada não é um paciente
# tratado, nem um início.
#
# NÃO CONFERIDA contra o banco real: ninguém abriu o ARIA para comparar
# estes números com a agenda real de um mês inteiro ainda (mesma ressalva
# do resto deste módulo, atrás do portão ``VERIFICADO_EM``) — em
# particular, o texto "INICIO" dentro de ``ActivityNamePTB`` é o que o
# usuário descreveu, não uma grafia conferida linha a linha no catálogo
# real (ver ``atividades_db`` para como esse catálogo se parece).
_SQL_RESUMO_MES = """
SELECT t.ctrResourceSer,
       COUNT(DISTINCT t.DimPatientID),
       COUNT(CASE WHEN a.ActivityNamePTB LIKE N'%INICIO%' THEN 1 END)
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
  JOIN DWH.DimPatient p ON p.DimPatientID = t.DimPatientID
 WHERE t.ctrResourceSer IN ({marcas_maquina})
   AND t.AppointmentDateTime >= ? AND t.AppointmentDateTime < ?
   AND t.AppointmentStatus NOT IN ({estados})
   AND ISNULL(p.IsMOTestPatient, 0) = 0
 GROUP BY t.ctrResourceSer
"""

# A mesma, com o vínculo de médico — mesmo desenho do filtro de médico de
# ``tratamento_db._SQL_RESUMO_MENSAL_MAQUINA_MEDICO`` (``EXISTS``, não
# ``JOIN``, para não multiplicar a marcação de quem tem mais de um médico
# vinculado e estragar o ``COUNT(DISTINCT …)``).
_SQL_RESUMO_MES_MEDICO = """
SELECT t.ctrResourceSer,
       COUNT(DISTINCT t.DimPatientID),
       COUNT(CASE WHEN a.ActivityNamePTB LIKE N'%INICIO%' THEN 1 END)
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
  JOIN DWH.DimPatient p ON p.DimPatientID = t.DimPatientID
 WHERE t.ctrResourceSer IN ({marcas_maquina})
   AND t.AppointmentDateTime >= ? AND t.AppointmentDateTime < ?
   AND t.AppointmentStatus NOT IN ({estados})
   AND ISNULL(p.IsMOTestPatient, 0) = 0
   AND EXISTS (SELECT 1
                 FROM DWH.DimPatientDoctor pd
                 JOIN DWH.DimDoctor d
                   ON d.ctrResourceSer = pd.ctrResourceSer
                WHERE pd.DimPatientID = t.DimPatientID
                  AND d.DoctorFullName IN ({marcas_medico}))
 GROUP BY t.ctrResourceSer
"""


def pacientes_do_mes_por_maquina(maquinas_marcadas: list, referencia: date,
                                 medicos_alvo: list = ()) -> dict:
    """``{ctr_resource_ser: (pacientes_distintos, inicios)}`` do MÊS de
    ``referencia`` (do dia 1 ao último, pelo calendário do mês — não uma
    janela de 30 dias corridos), para as máquinas de ``maquinas_marcadas``.

    ``maquinas_marcadas``: :class:`Maquina` (ou o ``ctr_resource_ser`` cru).
    ``medicos_alvo``: nomes BRUTOS, vazio = todos os pacientes da máquina —
    com médico(s), só quem está vinculado a algum deles entra na conta.
    Devolve ``{}`` quando não houver máquina, quando a agenda não estiver
    disponível (:func:`disponivel`), quando esta consulta em particular não
    estiver liberada (ainda NÃO CONFERIDA contra o banco real — ver o
    docstring acima da consulta; mesmo portão
    ``tratamento_db.lista_disponivel()`` do resto do que não foi conferido)
    ou quando a consulta falhar — nunca um número inventado.
    """
    if not disponivel():
        return {}
    from isocentro.banco import tratamento_db
    if not tratamento_db.lista_disponivel():
        return {}
    ctrs = [m.ctr_resource_ser if isinstance(m, Maquina) else int(m or 0)
           for m in (maquinas_marcadas or [])]
    ctrs = [c for c in ctrs if c]
    if not ctrs:
        return {}
    inicio_mes, fim_mes = capa_dados.limites_do_mes(referencia)
    marcas_maquina = ",".join("?" for _ in ctrs)
    marcas_estado = ",".join("?" for _ in ESTADOS_FORA)
    datas = (inicio_mes.strftime("%Y-%m-%d"), fim_mes.strftime("%Y-%m-%d"))
    nomes_medico = [n for n in (medicos_alvo or []) if n]
    if nomes_medico:
        marcas_medico = ",".join("?" for _ in nomes_medico)
        sql = _SQL_RESUMO_MES_MEDICO.format(
            marcas_maquina=marcas_maquina, estados=marcas_estado,
            marcas_medico=marcas_medico)
        parametros = (*ctrs, *datas, *ESTADOS_FORA, *nomes_medico)
    else:
        sql = _SQL_RESUMO_MES.format(
            marcas_maquina=marcas_maquina, estados=marcas_estado)
        parametros = (*ctrs, *datas, *ESTADOS_FORA)
    try:
        linhas = capa_db._consultar(sql, *parametros)
    except capa_db.FalhaDeLeitura:
        return {}
    return {int(ctr): (int(pac or 0), int(ini or 0))
           for ctr, pac, ini in linhas}


# Data em que a leitura de "Atividade de Serviço"/"Parada Não Programada"
# foi conferida contra o banco real — VAZIA de propósito, o mesmo portão de
# ``VERIFICADO_EM`` no topo do módulo. Três hipóteses do usuário (28/09/2026)
# ainda sem checar contra o ARIA de verdade: (1) essas duas são o nome EXATO
# de ``ActivityNamePTB`` (grafia, maiúsculas e acento incluídos); (2)
# aparecem em ``DimActivityTransaction`` SEM paciente, pela mesma tabela da
# agenda; (3) cada bloco dura :data:`MINUTOS_POR_SESSAO` — uma duração de
# TRATAMENTO, medida para outra coisa, que pode não valer para um bloco de
# manutenção (esses costumam durar horas, não 12 minutos). Enquanto fechado,
# :func:`minutos_parada_do_mes` devolve sempre ``{}`` e o Índice de
# Disponibilidade não aparece — mesma regra do resto do módulo: "uma agenda
# plausível e errada é pior que nenhuma".
MINUTOS_PARADA_VERIFICADO_EM = ""

_ATIVIDADES_PARADA: tuple[str, ...] = (
    "Atividade de Serviço", "Parada Não Programada",
)

_SQL_MINUTOS_PARADA_MES = """
SELECT t.ctrResourceSer,
       COUNT(*)
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
 WHERE t.ctrResourceSer IN ({marcas_maquina})
   AND t.AppointmentDateTime >= ? AND t.AppointmentDateTime < ?
   AND t.AppointmentStatus NOT IN ({estados})
   AND a.ActivityNamePTB IN ({marcas_atividade})
 GROUP BY t.ctrResourceSer
"""


def minutos_parada_do_mes(maquinas_marcadas: list, referencia: date) -> dict:
    """``{ctr_resource_ser: minutos}`` de "Atividade de Serviço"/"Parada Não
    Programada" no mês de ``referencia`` — o que o Índice de Disponibilidade
    desconta de :func:`minutos_uteis_do_mes`.

    Atrás do portão :data:`MINUTOS_PARADA_VERIFICADO_EM`, ainda FECHADO:
    devolve ``{}`` sempre, até alguém conferir contra o ARIA real (mesmo
    processo de ``tools/mapear_agenda.py`` em 23/09/2026) as três hipóteses
    do comentário acima da constante.
    """
    if not MINUTOS_PARADA_VERIFICADO_EM or not disponivel():
        return {}
    ctrs = [m.ctr_resource_ser if isinstance(m, Maquina) else int(m or 0)
           for m in (maquinas_marcadas or [])]
    ctrs = [c for c in ctrs if c]
    if not ctrs:
        return {}
    inicio_mes, fim_mes = capa_dados.limites_do_mes(referencia)
    marcas_maquina = ",".join("?" for _ in ctrs)
    marcas_estado = ",".join("?" for _ in ESTADOS_FORA)
    marcas_atividade = ",".join("?" for _ in _ATIVIDADES_PARADA)
    sql = _SQL_MINUTOS_PARADA_MES.format(
        marcas_maquina=marcas_maquina, estados=marcas_estado,
        marcas_atividade=marcas_atividade)
    parametros = (*ctrs, inicio_mes.strftime("%Y-%m-%d"),
                 fim_mes.strftime("%Y-%m-%d"), *ESTADOS_FORA,
                 *_ATIVIDADES_PARADA)
    try:
        linhas = capa_db._consultar(sql, *parametros)
    except capa_db.FalhaDeLeitura:
        return {}
    return {int(ctr): int(n or 0) * MINUTOS_POR_SESSAO for ctr, n in linhas}


def por_maquina(marcacoes: list) -> dict:
    """Agrupa as marcações por nome de máquina, na ordem em que chegaram.

    ``dict`` comum, não ``defaultdict``: quem monta a coluna decide o que
    fazer com uma máquina sem marcação nenhuma (coluna vazia com aviso, e não
    uma chave ausente que o código esqueceria de checar).
    """
    agrupado: dict = {}
    for m in marcacoes or []:
        agrupado.setdefault(m.maquina, []).append(m)
    return agrupado
