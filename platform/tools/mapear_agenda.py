r"""Mapeia a AGENDA do ARIA no data warehouse — o que a aba Agenda precisa.

Os dois mapeadores anteriores foram atrás do que já existe no papel e no
prontuário: o ``mapear_dw.py`` buscou o que sai na CAPA (cadastro, prescrição,
foto) e o ``mapear_tratamento.py``, o que ACONTECEU (frações entregues, quem
tratou). Este vai atrás do que **está marcado**: quem tem hora em qual máquina,
em qual dia.

É outra metade do banco, e nenhuma coluna dela está conferida. O risco aqui tem
a forma já conhecida — o erro que não estoura:

* ``ctrResourceSer`` é o recurso da marcação, e recurso no ARIA é máquina OU
  pessoa OU sala. Listar "a agenda do TrueBeam1" pegando o recurso errado
  devolve uma lista plausível de nomes, no dia certo, de outra coisa;
* ``AppointmentDateTime`` × ``ActivityStartDateTime`` × ``DerivedAppointment
  TaskDate``: três datas na mesma linha. A que o ARIA mostra na agenda é UMA
  delas, e as outras duas devolvem listas parecidas — deslocadas em horas ou em
  dias;
* ``AppointmentStatus`` tem os cancelados dentro. Uma agenda que mostra quem
  desmarcou é uma agenda que a sala aprende a não usar.

Enquanto esta saída não existir, o SQL da aba não deve ser escrito — mesma
regra do portão ``VERIFICADO_EM`` dos outros módulos de banco.

Rodar, de uma máquina fora do domínio:
    runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\mapear_agenda.bat"

Com um DIA de agenda cheia (a amostra que PROVA o mapeamento — um dia útil, de
preferência o de hoje ou o de ontem):
    ... "C:\...\tools\mapear_agenda.bat --dia 2026-09-23"

Sem ``--dia``, só metadados e o catálogo de recursos: nenhuma linha de paciente
é lida. Com ele, lê-se um dia — o suficiente para conferir contra o que o ARIA
mostra na tela de agenda, marcação por marcação.

Nada aqui escreve no banco.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

sys.path.insert(0, __file__.rsplit("tools", 1)[0])
sys.path.insert(0, __file__.rsplit("mapear_agenda", 1)[0])

from diagnostico_db import (  # noqa: E402
    BANCO_PADRAO, PORTA_PADRAO, SERVIDOR_PADRAO, _conectar, _quem_sou,
    passo_drivers, passo_identidade, passo_pyodbc, passo_rede)
from mapear_dw import colunas_de  # noqa: E402

# Rede larga pelo NOME da tabela. Cada padrão é uma hipótese de onde a marcação
# mora; listar trinta tabelas custa uma consulta, e descobrir na clínica que
# faltou uma custa outra ida.
PADROES_TABELA = ("%Appointment%", "%Schedul%", "%Activity%", "%Resource%",
                  "%Machine%", "%Calendar%", "%Booking%", "%Visit%")

# As mais prováveis, em ordem de suspeita. A ``DimActivityTransaction`` já é
# lida pelo ``atividades_db`` (as tarefas de Documentação), e o levantamento de
# 01/09/2026 mostrou que ela carrega recurso, paciente, hora e estado — ou seja,
# é candidata a ser a agenda inteira. A ``DimResource`` é a que diz se aquele
# recurso é uma MÁQUINA; sem ela, não há "agenda por máquina".
TABELAS_SUSPEITAS = [
    "DWH.DimActivityTransaction",
    "DWH.DimActivity",
    "DWH.DimResource",
    "DWH.DimResourceGroup",
    "DWH.DimMachine",
    "DWH.DimHospitalDepartment",
    "DWH.DimClinic",
]

# Nomes de COLUNA que responderiam cada pergunta da tela. O nome da tabela
# engana; o da coluna costuma dizer o que ela é.
TERMOS_COLUNA = [
    "ResourceType",     # é máquina ou é gente? esta é A pergunta
    "ResourceName",
    "MachineId",
    "MachineName",
    "TreatmentMachine",
    "AppointmentDate",
    "ScheduledStart",
    "ScheduledEnd",
    "Duration",         # a sessão ocupa quantos minutos
    "AppointmentStatus",
    "CheckedIn",
    "Department",
]


def _cur(cx):
    return cx.cursor()


def tabelas_candidatas(cx) -> list[str]:
    """Toda tabela cujo NOME sugere marcação, recurso ou máquina."""
    print(f"\n{'=' * 70}\nTabelas cujo nome sugere AGENDA\n{'=' * 70}")
    achadas: list[str] = []
    cur = _cur(cx)
    for padrao in PADROES_TABELA:
        try:
            cur.execute(
                "SELECT s.name + '.' + o.name FROM sys.objects o "
                "JOIN sys.schemas s ON s.schema_id = o.schema_id "
                "WHERE o.type = 'U' AND o.name LIKE ? "
                "  AND o.name NOT LIKE 'stg%' AND o.name NOT LIKE '%bkp%' "
                "ORDER BY o.name", padrao)
            nomes = [r[0] for r in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            print(f"\n  {padrao}: erro — {str(exc)[:100]}")
            continue
        print(f"\n  {padrao}  ({len(nomes)}):")
        for n in nomes:
            print(f"    {n}")
            if n not in achadas:
                achadas.append(n)
        if not nomes:
            print("    (nada)")
    return achadas


def contagens(cx, tabelas: list[str]) -> None:
    """Quantas linhas em cada uma — é o que separa a tabela viva da vazia.

    Um data warehouse tem tabelas de recurso que nunca foram alimentadas. Nome
    bom com zero linha é caminho sem saída, e saber disso aqui custa uma
    consulta; saber depois custa a tela inteira.
    """
    print(f"\n{'=' * 70}\nQuantas linhas em cada candidata\n{'=' * 70}")
    cur = _cur(cx)
    for t in tabelas:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"  {t:52} {cur.fetchone()[0]:>10} linhas")
        except Exception as exc:  # noqa: BLE001
            print(f"  {t:52} (não deu: {str(exc)[:50]})")


def procurar_colunas(cx) -> None:
    print(f"\n{'=' * 70}\nProcura por nome de coluna (recurso, hora, estado…)"
          f"\n{'=' * 70}")
    cur = _cur(cx)
    for termo in TERMOS_COLUNA:
        try:
            cur.execute(
                "SELECT TOP 20 s.name + '.' + o.name, c.name "
                "FROM sys.columns c "
                "JOIN sys.objects o ON o.object_id = c.object_id "
                "JOIN sys.schemas s ON s.schema_id = o.schema_id "
                "WHERE o.type = 'U' AND c.name LIKE ? "
                "  AND o.name NOT LIKE 'stg%' AND o.name NOT LIKE '%bkp%' "
                "ORDER BY o.name", f"%{termo}%")
            achados = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            print(f"\n  {termo}: erro — {str(exc)[:90]}")
            continue
        print(f"\n  {termo}  ({len(achados)}):")
        for tabela, coluna in achados:
            print(f"    {tabela}.{coluna}")
        if not achados:
            print("    (nada)")


def colunas_das_suspeitas(cx) -> None:
    """Todas as colunas das tabelas mais prováveis, sem filtrar.

    Sem filtro de propósito: filtrar por palavra-chave é o que faz perder a
    coluna de nome inesperado, e é exatamente ela que se está procurando — foi
    assim que ``DerivedAppointmentTaskDate`` apareceu no mapeamento das
    atividades.
    """
    print(f"\n{'=' * 70}\nColunas das tabelas suspeitas\n{'=' * 70}")
    for t in TABELAS_SUSPEITAS:
        print(f"\n--- {t} ---")
        try:
            cols = colunas_de(cx, t)
        except Exception as exc:  # noqa: BLE001
            print(f"  (não consegui ler: {str(exc)[:110]})")
            continue
        if not cols:
            print("  (não existe neste banco)")
            continue
        for nome, tipo, tam, nulo in cols:
            print(f"  {nome:46} {tipo}({tam}){'' if nulo else '  NOT NULL'}")


def recursos_que_sao_maquina(cx) -> None:
    """**A pergunta central desta ferramenta**: quais recursos são máquinas.

    "Agenda por máquina" só existe se houver como separar, entre os recursos, os
    aceleradores das pessoas e das salas. Três caminhos, e o que responder
    primeiro é o que a aba vai usar:

    1. ``DimResource`` com uma coluna de TIPO ("Machine", "Treatment Unit");
    2. o nome do recurso batendo com ``DimMachine.MachineId`` — que já é o nome
       que a Ficha Virtual mostra na coluna "máquina", então bate com o que o
       usuário já lê na tela;
    3. nenhum dos dois, e aí a lista de máquinas é configuração do serviço, não
       descoberta do banco.

    Casar por PARECENÇA de nome não entra na lista. É a armadilha do
    ``paralelo.maquina_do_plano``: "TrueBeam" pegando "TrueBeamSN1001" faz o
    programa mostrar a agenda de outra sala em silêncio.
    """
    print(f"\n{'=' * 70}\nQuais recursos são MÁQUINA (a pergunta central)"
          f"\n{'=' * 70}")
    cur = _cur(cx)

    print("\n--- [1] DimMachine: os aceleradores que o DW conhece ---")
    try:
        cur.execute("SELECT TOP 40 * FROM DWH.DimMachine")
        cols = [d[0] for d in cur.description]
        for linha in cur.fetchall():
            campos = [f"{c}={v}" for c, v in zip(cols, linha)
                      if v is not None and str(v) not in ("", "0", "NA")]
            print("    " + " | ".join(campos[:8]))
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")

    print("\n--- [2] DimResource: tipo de cada recurso ---")
    try:
        cur.execute("SELECT TOP 60 * FROM DWH.DimResource")
        cols = [d[0] for d in cur.description]
        print(f"    colunas: {', '.join(cols)}")
        for linha in cur.fetchall():
            campos = [f"{c}={v}" for c, v in zip(cols, linha)
                      if v is not None and str(v) not in ("", "0", "NA")]
            print("    " + " | ".join(campos[:8]))
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")

    print("\n--- [3] Os recursos que MAIS aparecem em marcações ---")
    print("    (a máquina de tratamento tem uma marcação por paciente por dia:")
    print("     ela está no topo desta lista, e é assim que se reconhece)")
    try:
        cur.execute("""
SELECT TOP 30 t.ctrResourceSer, COUNT(*) AS Marcacoes,
       MIN(t.AppointmentDateTime), MAX(t.AppointmentDateTime)
  FROM DWH.DimActivityTransaction t
 WHERE t.AppointmentDateTime >= DATEADD(day, -30, GETDATE())
 GROUP BY t.ctrResourceSer
 ORDER BY COUNT(*) DESC
""")
        for ser, quantas, primeira, ultima in cur.fetchall():
            print(f"    ctrResourceSer={ser!s:<10} {quantas:>6} marcações  "
                  f"{primeira} → {ultima}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")

    print("\n--- [4] Esses recursos têm NOME? (GetTaskOwnerName é de gente) ---")
    print("    Se a máquina aparecer aqui, o nome dela sai pelo mesmo caminho")
    print("    do dono de tarefa; se não, o nome vem de outra tabela.")
    try:
        cur.execute("""
SELECT TOP 40 o.ctrResourceSer, o.FullName, o.OwnerName
  FROM DWH.GetTaskOwnerName o
 WHERE o.ctrResourceSer IN (
       SELECT TOP 20 t.ctrResourceSer
         FROM DWH.DimActivityTransaction t
        WHERE t.AppointmentDateTime >= DATEADD(day, -30, GETDATE())
        GROUP BY t.ctrResourceSer
        ORDER BY COUNT(*) DESC)
""")
        achados = cur.fetchall()
        if not achados:
            print("    (nenhum — o recurso da marcação NÃO é dono de tarefa)")
        for ser, nome, dono in achados:
            print(f"    {ser!s:<10} {str(nome)[:40]:<42} {dono}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")

    # A 1ª rodada (23/09/2026) mostrou os recursos mais marcados sem nome de
    # DONO (ctrResourceSer 1000, 1035, 1046, 1252, 1499) todos com
    # ``DimLookupID_ResourceType = 3`` em ``DimResource``, e — só nesse tipo —
    # ``ActualResourceID`` igual ao ``DimResourceID`` (1 a 24, a mesma faixa de
    # ``DimMachineID``). Isso é uma COINCIDÊNCIA NUMÉRICA até aqui, não um
    # vínculo documentado: casar por parecença de número é a mesma armadilha
    # do ``paralelo.maquina_do_plano`` por nome, só que com dígitos. Este
    # bloco TESTA a hipótese — ``ActualResourceID = DimMachineID`` — contra a
    # tabela de máquinas, para o nome de cada acelerador sair daqui em vez de
    # adivinhado.
    print("\n--- [5] TESTE: ActualResourceID (tipo 3) = DimMachineID? ---")
    print("    (hipótese a confirmar contra o volume de marcações do bloco 3 —")
    print("     não é vínculo documentado, é o número batendo)")
    try:
        cur.execute("""
SELECT dr.ctrResourceSer, dr.ActualResourceID, dm.DimMachineID,
       dm.MachineId, dm.MachineFullName, dm.MachineType, dm.Schedulable
  FROM DWH.DimResource dr
  JOIN DWH.DimMachine dm ON dm.DimMachineID = dr.ActualResourceID
 WHERE dr.DimLookupID_ResourceType = 3
 ORDER BY dr.ctrResourceSer
""")
        achados = cur.fetchall()
        if not achados:
            print("    (nada casou — a hipótese caiu)")
        for ser, ari, dmid, mid, mfull, mtype, sched in achados:
            print(f"    ctrResourceSer={ser!s:<8} ActualResourceID={ari!s:<5} "
                  f"→ DimMachineID={dmid!s:<5} MachineId={str(mid)[:20]:<22} "
                  f"({mfull}) {mtype} agendável={sched}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")

    # Segunda fonte, independente da hipótese acima: se existir uma tabela
    # dedicada a ligar recurso e máquina, ela vale mais que a coincidência de
    # número. Achada pelo nome na varredura de tabelas (24 linhas — bate com
    # a contagem de ``DimMachine``).
    print("\n--- [6] DWH.InSightiveResourceMachine: catálogo dedicado? ---")
    try:
        cur.execute("SELECT * FROM DWH.InSightiveResourceMachine")
        cols = [d[0] for d in cur.description]
        print(f"    colunas: {', '.join(cols)}")
        for linha in cur.fetchall():
            campos = [f"{c}={v}" for c, v in zip(cols, linha)
                      if v is not None and str(v) not in ("", "0", "NA")]
            print("    " + " | ".join(campos))
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")

    # E o que ``ResourceTypeNum``/``DimLookupID_ResourceType = 3`` QUER DIZER,
    # se houver uma tabela de constantes que decodifique o número.
    print("\n--- [7] DWH.DimConstantResource: o que é o tipo 3? ---")
    try:
        cur.execute("SELECT * FROM DWH.DimConstantResource")
        cols = [d[0] for d in cur.description]
        print(f"    colunas: {', '.join(cols)}")
        for linha in cur.fetchall():
            campos = [f"{c}={v}" for c, v in zip(cols, linha)
                      if v is not None and str(v) not in ("", "0", "NA")]
            print("    " + " | ".join(campos))
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")


def atividades_de_tratamento(cx) -> None:
    """Qual ``ActivityCode`` é a SESSÃO na máquina.

    O catálogo das atividades de alta (22/09/2026) mostrou que o código não é o
    que qualquer um escreveria de cabeça — "Verificar Programação BET" tem o
    código ``Verificar Programação``, sem sufixo, e o do CEL termina em ``UNI``.
    A sessão de tratamento não tem razão nenhuma para ser mais bem comportada,
    então ela se DESCOBRE aqui, e o filtro da aba será pelo código exato.

    A busca é pelo miolo minúsculo das palavras: este ``variandw`` é
    CASE-SENSITIVE (ver ``ARMADILHAS.md``), e procurar "Tratamento" com T
    maiúsculo deixaria de fora justamente o que se procura.
    """
    print(f"\n{'=' * 70}\nQue atividade é a SESSÃO de tratamento\n{'=' * 70}")
    cur = _cur(cx)
    # ``ActivityCategoryPTB``, não ``...Name``: a coluna errada estourou
    # ("Invalid column name") na 1ª rodada de 23/09/2026 — só o
    # ``ActivityCategoryCode`` e as ``ActivityCategoryXXX`` por língua existem
    # em ``DimActivity``, e a que interessa é a ...PTB.
    for palavra in ("ratamen", "reatmen", "essão", "ession", "adiot", "eleroter"):
        try:
            cur.execute("""
SELECT DISTINCT a.ActivityCode, a.ActivityNamePTB, a.ActivityCategoryPTB
  FROM DWH.DimActivity a
 WHERE a.ActivityCode LIKE ? OR a.ActivityNamePTB LIKE ?
 ORDER BY a.ActivityCode
""", f"%{palavra}%", f"%{palavra}%")
            achados = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            print(f"\n  {palavra}: erro — {str(exc)[:110]}")
            continue
        print(f"\n  '{palavra}'  ({len(achados)}):")
        for codigo, nome, categoria in achados:
            print(f"    {str(codigo)[:32]:<34} | {str(nome)[:32]:<34} | "
                  f"{categoria}")
        if not achados:
            print("    (nada)")

    # A 1ª rodada mostrou algo que a busca por palavra não previa: as
    # atividades mais marcadas do serviço não se chamam "Tratamento" — se
    # chamam pelo SÍTIO ("PELVE", "MAMA", "CP", "PROSTATA"…). A sessão diária
    # na máquina parece ser uma atividade por REGIÃO, não uma atividade única.
    # Esta consulta traz a CATEGORIA de cada uma: se todas caírem na mesma
    # categoria, é ela — não o código — que filtra a sessão.
    print("\n--- A categoria das atividades por SÍTIO (achadas na 1ª rodada) ---")
    sitios = ("PELVE", "MAMA", "CP", "PROSTATA", "ABDOMEN", "PALIATIVO",
             "EXTREMIDADE", "PELE", "TOMOGRAFIA")
    try:
        marcas = ",".join("?" for _ in sitios)
        cur.execute(f"""
SELECT a.ActivityCode, a.ActivityNamePTB, a.ActivityCategoryCode,
       a.ActivityCategoryPTB, a.DefaultDuration
  FROM DWH.DimActivity a
 WHERE a.ActivityCode IN ({marcas})
 ORDER BY a.ActivityCode
""", *sitios)
        for codigo, nome, cat_codigo, cat_ptb, duracao in cur.fetchall():
            print(f"    {str(codigo)[:20]:<22} | {str(nome)[:24]:<26} | "
                  f"cat={cat_codigo} ({cat_ptb}) | duração={duracao}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")

    print("\n--- As atividades MAIS marcadas nos últimos 30 dias ---")
    print("    (a sessão de tratamento é, de longe, a mais frequente do")
    print("     serviço: se uma delas domina esta lista, é ela)")
    try:
        cur.execute("""
SELECT TOP 25 a.ActivityCode, a.ActivityNamePTB, COUNT(*) AS Marcacoes
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
 WHERE t.AppointmentDateTime >= DATEADD(day, -30, GETDATE())
 GROUP BY a.ActivityCode, a.ActivityNamePTB
 ORDER BY COUNT(*) DESC
""")
        for codigo, nome, quantas in cur.fetchall():
            print(f"    {quantas:>7}  {str(codigo)[:34]:<36} {nome}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")


def estados_da_marcacao(cx) -> None:
    """Os ``AppointmentStatus`` que existem, com quantos de cada.

    A aba precisa saber o que NÃO mostrar. Cancelado e faltou têm de sair da
    coluna da máquina — ou ficar marcados como tal —, e a lista negativa só se
    escreve depois de ver os nomes que este banco usa.
    """
    print(f"\n{'=' * 70}\nEstados da marcação (o que a agenda NÃO mostra)"
          f"\n{'=' * 70}")
    cur = _cur(cx)
    try:
        cur.execute("""
SELECT COALESCE(t.AppointmentStatus, '(sem estado)'), COUNT(*)
  FROM DWH.DimActivityTransaction t
 WHERE t.AppointmentDateTime >= DATEADD(day, -30, GETDATE())
 GROUP BY t.AppointmentStatus
 ORDER BY COUNT(*) DESC
""")
        for estado, quantas in cur.fetchall():
            print(f"    {quantas:>8}  {estado}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")


def agenda_do_dia(cx, dia: str) -> None:
    """**A prova**: o dia inteiro, marcação por marcação, para conferir na tela.

    Metadado diz que a coluna existe; só o valor diz que ela quer dizer o que o
    nome promete. Esta saída se lê ao lado da agenda do ARIA aberta no mesmo
    dia: mesma máquina, mesma hora, mesmo paciente, mesma quantidade de linhas.
    Faltar um paciente é tão grave quanto sobrar — a sala usa esta lista para
    saber quem vem.

    As TRÊS datas saem juntas de propósito. Se elas divergirem, é aqui que se vê
    qual delas é a que o ARIA mostra.
    """
    print(f"\n{'=' * 70}\nAGENDA DE {dia} — a prova do mapeamento\n{'=' * 70}")
    cur = _cur(cx)
    try:
        cur.execute("""
SELECT t.AppointmentDateTime,
       t.ActivityStartDateTime,
       t.DerivedAppointmentTaskDate,
       t.ScheduledEndTime,
       t.ctrResourceSer,
       a.ActivityCode,
       a.ActivityNamePTB,
       p.PatientId,
       p.PatientFullName,
       t.AppointmentStatus,
       t.CheckedIn,
       t.IsScheduled,
       md.DoctorFullName
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
  LEFT JOIN DWH.DimPatient p ON p.DimPatientID = t.DimPatientID
  LEFT JOIN (SELECT pd.DimPatientID,
                    MIN(d.DoctorFullName) AS DoctorFullName
               FROM DWH.DimPatientDoctor pd
               JOIN DWH.DimDoctor d ON d.ctrResourceSer = pd.ctrResourceSer
              WHERE pd.OncologistFlag = 1
              GROUP BY pd.DimPatientID) md
         ON md.DimPatientID = t.DimPatientID
 WHERE CAST(t.AppointmentDateTime AS date) = ?
   AND ISNULL(p.IsMOTestPatient, 0) = 0
 ORDER BY t.ctrResourceSer, t.AppointmentDateTime
""", dia)
        linhas = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:250]}")
        return
    if not linhas:
        print("  (nenhuma marcação neste dia — dia não útil? data errada?)")
        return
    print(f"  {len(linhas)} marcação(ões).\n")
    recurso_atual = None
    for (quando, inicio, derivada, fim, recurso, codigo, _nome_ativ,
         registro, nome, estado, checkin, marcada, medico) in linhas:
        if recurso != recurso_atual:
            recurso_atual = recurso
            print(f"\n  ── recurso {recurso} ──")
        hora = str(quando)[11:16] if quando else "  -  "
        print(f"    {hora}  {str(registro or '-'):<12} "
              f"{str(nome or '(sem paciente)')[:28]:<30} "
              f"{str(codigo)[:22]:<24} {estado}")
        print(f"           médico={medico}  fim={fim}  checkin={checkin}  "
              f"marcada={marcada}")
        if str(inicio) != str(quando) or (derivada and
                                          str(derivada)[:10] != str(quando)[:10]):
            print(f"           ⚠ datas DIVERGEM: appointment={quando}  "
                  f"start={inicio}  derivada={derivada}")

    print("\n  Quantas por recurso (é o número que a coluna da máquina mostra):")
    porrecurso: dict = {}
    for linha in linhas:
        porrecurso[linha[4]] = porrecurso.get(linha[4], 0) + 1
    for recurso, quantas in sorted(porrecurso.items(), key=lambda x: -x[1]):
        print(f"    recurso {recurso!s:<12} {quantas:>4} marcação(ões)")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--servidor", default=SERVIDOR_PADRAO)
    p.add_argument("--banco", default=BANCO_PADRAO)
    p.add_argument("--porta", type=int, default=PORTA_PADRAO)
    p.add_argument("--dia", default="",
                   help="AAAA-MM-DD de um dia ÚTIL com agenda cheia — a "
                        "amostra que prova o mapeamento. Sem ele, nenhuma "
                        "linha de paciente é lida")
    args = p.parse_args(argv)

    passo_identidade()
    pyodbc = passo_pyodbc()
    if pyodbc is None:
        return 1
    driver = passo_drivers(pyodbc)
    if not driver:
        return 1
    # A REDE antes do login: sem este passo, a falha de alcance chega como
    # "SQL Server inexistente ou acesso negado", frase que mistura servidor fora
    # do ar, VPN caída e falta de permissão — e manda investigar a coisa errada.
    if not passo_rede(args.servidor, args.porta):
        print("\n  A porta não respondeu. Isto é REDE — não é senha nem")
        print("  permissão. VPN conectada? Cabo? Depois tente de novo.")
        return 1
    try:
        cx = _conectar(pyodbc, driver, args.servidor, args.banco, args.porta)
    except Exception as exc:  # noqa: BLE001
        texto = str(exc)
        print(f"\nNão conectei: {texto[:250]}")
        if "SSPI" in texto or "untrusted domain" in texto or "18452" in texto:
            print()
            print("  Isto é IDENTIDADE, não permissão: o servidor viu um")
            print(f"  usuário local ({_quem_sou()}), não o de rede. Faltou o")
            print("  runas /netonly — o comando INTEIRO dentro das mesmas aspas:")
            print()
            print(r'    runas /netonly /user:CLINICA\geovani.pena '
                  r'"C:\...\isocentro\tools\mapear_agenda.bat --dia 2026-09-23"')
        return 1
    try:
        # A pergunta central primeiro: sem separar máquina de gente, não há aba
        # nenhuma a escrever, e o resto da saída é curiosidade.
        recursos_que_sao_maquina(cx)
        atividades_de_tratamento(cx)
        estados_da_marcacao(cx)
        achadas = tabelas_candidatas(cx)
        contagens(cx, achadas)
        procurar_colunas(cx)
        colunas_das_suspeitas(cx)
        if args.dia.strip():
            agenda_do_dia(cx, args.dia.strip())
        else:
            print(f"\n(sem --dia: nenhuma linha de paciente foi lida — mas é a "
                  f"agenda de um dia que PROVA o mapeamento. Vale rodar de novo "
                  f"com --dia {date.today().isoformat()} e conferir contra o "
                  f"ARIA aberto na mesma data)")
    finally:
        cx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
