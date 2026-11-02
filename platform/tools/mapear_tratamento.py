r"""Mapeia o TRATAMENTO ENTREGUE no data warehouse — o que a aba Ficha Virtual
precisa e que o mapeamento de 18/08/2026 não cobriu.

O ``mapear_dw.py`` foi atrás do que sai na CAPA: cadastro, prescrição, foto.
Tudo aquilo é o que se planeja. A aba Ficha Virtual pergunta outra coisa — o
que ACONTECEU: em que fração o paciente está, quem tratou cada uma, a que horas,
em qual acelerador, quanta dose já foi entregue.

Isso vive em outras tabelas, e nenhuma delas está verificada. É o mesmo risco
que motivou o primeiro mapeador, e aqui ele é maior: ``PatientId`` × ``PatientID``
devolve erro na hora, mas "número de frações planejado" no lugar de "frações
ENTREGUES" devolve um número plausível e errado — e é justamente o número que o
médico vai ler grande no meio da tela para decidir sobre o paciente.

Enquanto esta saída não existir, o SQL da aba não deve ser escrito.

Rodar, de uma máquina fora do domínio:
    runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\mapear_tratamento.bat"

Com um paciente que ESTÁ EM TRATAMENTO (não um que já teve alta — o interesse
aqui é a fração em curso):
    ... "C:\...\tools\mapear_tratamento.bat --paciente 9000001CEL"

Conferir a LISTA do painel — o que a consulta RESPONDE, e não o que existe no
DW — é outro modo, e é o único que serve ao ``LISTA_VERIFICADA_EM``:
    ... "C:\...\tools\mapear_tratamento.bat --consulta"

Nada aqui escreve no banco. Sem ``--paciente`` e sem ``--consulta``, nenhuma
linha de paciente é lida — o ``--consulta`` LÊ, e imprime nome e registro de
quem está em tratamento, porque a conferência contra o ARIA é nome por nome.
"""
from __future__ import annotations

import argparse
import logging
import sys

sys.path.insert(0, __file__.rsplit("tools", 1)[0])
# O próprio ``tools`` também: o ``--consulta`` usa o ``atividades`` (a conexão
# do app), e rodar este script de outra pasta não acharia o irmão.
sys.path.insert(0, __file__.rsplit("mapear_tratamento", 1)[0])

from diagnostico_db import (  # noqa: E402
    BANCO_PADRAO, PORTA_PADRAO, SERVIDOR_PADRAO, _conectar, _quem_sou,
    passo_drivers, passo_identidade, passo_pyodbc, passo_rede)
from mapear_dw import colunas_de  # noqa: E402

# Como se acha uma tabela que não se conhece: pelo NOME, com rede larga. Cada
# padrão aqui é uma hipótese de onde a sessão de tratamento mora, e é mais
# barato listar 40 tabelas do que descobrir na clínica que faltou uma.
PADROES_TABELA = ("%Treatment%", "%Session%", "%Fraction%", "%Delivered%",
                  "%Delivery%", "%Record%", "%Activity%", "%Appointment%",
                  "%Schedul%")

# Nomes de COLUNA que responderiam cada pergunta da tela. O nome da coluna
# costuma dizer o que ela é; o da tabela nem sempre.
TERMOS_COLUNA = [
    "Fraction",      # em que fração está / quantas foram entregues
    "Delivered",     # dose entregue × dose planejada
    "Treatment",     # datas, status, sessão
    "SessionNumber",
    "Therapist",     # QUEM tratou — pode estar como Operator/User/Staff
    "Operator",
    "Staff",
    "UserName",
    "PerformedBy",
    "ApprovedBy",
    "StartTime",     # horário — a tela precisa de hora, não só data
    "EndTime",
    "TreatmentTime",
    "Machine",
    "MetersetDose",  # UM entregues
    "Meterset",
    "Status",
]

# As tabelas mais prováveis, em ordem de suspeita. ``FactTreatmentHistory`` já é
# usada pelo ``capa_db`` (para a máquina), então ao menos essa existe.
TABELAS_SUSPEITAS = [
    "DWH.FactTreatmentHistory",
    "DWH.FactTreatmentSession",
    "DWH.FactTreatmentRecord",
    "DWH.DimTreatmentSession",
    "DWH.FactRadiationTreatment",
    "DWH.DimPlan",
    "DWH.DimCourse",
    "DWH.DimStaff",
    "DWH.DimUser",
]


def _cur(cx):
    return cx.cursor()


def tabelas_candidatas(cx) -> list[str]:
    """Toda tabela cujo NOME sugere tratamento entregue."""
    print(f"\n{'=' * 70}\nTabelas cujo nome sugere tratamento entregue"
          f"\n{'=' * 70}")
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

    Um data warehouse costuma ter tabelas de recurso que nunca foram
    alimentadas. Nome bom com zero linha é caminho sem saída, e descobrir isso
    aqui custa uma consulta; descobrir depois custa a tela inteira.
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
    print(f"\n{'=' * 70}\nProcura por nome de coluna (fração, quem tratou, hora…)"
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


def colunas_das_suspeitas(cx, extras: list[str]) -> None:
    """Todas as colunas das tabelas mais prováveis, sem filtrar.

    Sem filtro de propósito: o filtro por palavra-chave é o que faz perder a
    coluna com nome inesperado, e é exatamente ela que se está procurando.
    """
    print(f"\n{'=' * 70}\nColunas das tabelas suspeitas\n{'=' * 70}")
    vistas = set()
    for t in TABELAS_SUSPEITAS + [e for e in extras
                                  if "Treatment" in e or "Session" in e]:
        if t in vistas:
            continue
        vistas.add(t)
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


def sessoes_do_paciente(cx, registro: str) -> None:
    """As sessões de UM paciente — a prova de que a tabela é a certa.

    Metadado diz que a coluna existe; só o VALOR diz que ela quer dizer o que o
    nome promete. "TreatmentDate" pode ser a data da sessão ou a data de
    aprovação do plano, e as duas parecem iguais numa lista de colunas.
    """
    print(f"\n{'=' * 70}\nSessões de {registro} — o que realmente aconteceu"
          f"\n{'=' * 70}")
    tentativas = [
        ("FactTreatmentHistory (tudo, por data)",
         "SELECT TOP 30 th.* FROM DWH.FactTreatmentHistory th "
         "JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
         "WHERE p.PatientId = ? "
         "ORDER BY th.LastTreatmentDate DESC"),
        ("FactTreatmentSession",
         "SELECT TOP 30 ts.* FROM DWH.FactTreatmentSession ts "
         "JOIN DWH.DimPatient p ON p.DimPatientID = ts.DimPatientID "
         "WHERE p.PatientId = ?"),
        ("FactTreatmentRecord",
         "SELECT TOP 30 tr.* FROM DWH.FactTreatmentRecord tr "
         "JOIN DWH.DimPatient p ON p.DimPatientID = tr.DimPatientID "
         "WHERE p.PatientId = ?"),
    ]
    for rotulo, sql in tentativas:
        print(f"\n--- [{rotulo}] ---")
        try:
            cur = _cur(cx)
            cur.execute(sql, registro)
            cols = [d[0] for d in cur.description]
            linhas = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            print(f"  falhou: {str(exc)[:170]}")
            continue
        if not linhas:
            print("  (nenhuma linha para este paciente)")
            continue
        print(f"  {len(linhas)} linha(s). As 3 primeiras, campo a campo:")
        for i, linha in enumerate(linhas[:3]):
            print(f"\n  linha {i + 1}:")
            for coluna, valor in zip(cols, linha):
                texto = str(valor)
                if len(texto) > 70:
                    texto = texto[:67] + "…"
                if texto and texto not in ("None", "NA", "0"):
                    print(f"    {coluna:44} {texto}")
        if len(linhas) > 3:
            print(f"\n  (mais {len(linhas) - 3} linha(s) — se cada uma for uma "
                  "SESSÃO, é esta a tabela que a aba precisa)")


def quem_tratou(cx, registro: str) -> None:
    """A pergunta que mais provavelmente NÃO tem resposta no DW.

    O nome de quem operou a sessão pode não ter sido levado do ARIA clínico
    (``variansystem``) para o data warehouse — e, se não estiver aqui, a tela
    tem de dizer "não informado" em vez de mostrar outro nome qualquer. Vale a
    regra do projeto: campo sem fonte nasce vazio.
    """
    print(f"\n{'=' * 70}\nQuem tratou: existe no DW?\n{'=' * 70}")
    cur = _cur(cx)
    try:
        cur.execute(
            "SELECT s.name + '.' + o.name, c.name FROM sys.columns c "
            "JOIN sys.objects o ON o.object_id = c.object_id "
            "JOIN sys.schemas s ON s.schema_id = o.schema_id "
            "WHERE o.type = 'U' AND o.name NOT LIKE 'stg%' "
            "  AND (c.name LIKE '%Therapist%' OR c.name LIKE '%Operator%' "
            "       OR c.name LIKE '%PerformedBy%' OR c.name LIKE '%TreatedBy%' "
            "       OR c.name LIKE '%RecordedBy%' OR c.name LIKE '%Technologist%')"
            " ORDER BY o.name")
        achados = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:150]}")
        return
    if not achados:
        print("  NADA. Se confirmado, 'quem tratou' NÃO vem do variandw — a")
        print("  tela deve deixar o campo vazio e dizer que não há fonte, ou")
        print("  o dado tem de vir do ARIA clínico (variansystem), que é outra")
        print("  decisão (outro banco, outra permissão).")
        return
    for tabela, coluna in achados:
        print(f"  {tabela}.{coluna}")
    if not registro:
        return
    print(f"\n  --- valores para {registro} ---")
    for tabela, coluna in achados[:6]:
        try:
            cur = _cur(cx)
            cur.execute(
                f"SELECT DISTINCT TOP 5 t.{coluna} FROM {tabela} t "
                "JOIN DWH.DimPatient p ON p.DimPatientID = t.DimPatientID "
                "WHERE p.PatientId = ?", registro)
            valores = [str(r[0]) for r in cur.fetchall() if r[0] not in (None, "")]
            print(f"    {tabela}.{coluna}: "
                  f"{', '.join(valores) if valores else '(vazio)'}")
        except Exception as exc:  # noqa: BLE001
            print(f"    {tabela}.{coluna}: não deu ({str(exc)[:70]})")


def conferir_hipoteses(cx, registro: str) -> None:
    """As TRÊS perguntas que sobraram — e só o banco desta clínica responde.

    A Data Lineage Tool 15.6 já resolveu os nomes e o significado das colunas
    (ver ``tratamento_db``), então não se procura mais coluna aqui. O que resta é
    empírico:

    1. o filtro de "tratado" (``TreatmentStartTime IS NOT NULL`` e
       ``FractionNumber > 0``) separa mesmo as linhas tratadas das de plano?
       A documentação avisa que ``FactTreatmentHistory`` guarda as duas coisas;
    2. ``SUM(DoseDeliveredPerFraction)`` por fração dá a dose do dia, ou repete
       o mesmo valor em cada campo? (é dose a um RefPoint, não ao campo);
    3. ``TreatmentSignOffUser1`` está preenchido? A coluna existe em toda
       instalação — quem a preenche é a máquina de tratamento.
    """
    print(f"\n{'=' * 70}\nAs três hipóteses do tratamento_db\n{'=' * 70}")
    if not registro:
        print("  (precisa de --paciente para responder; são perguntas sobre "
              "DADO, não sobre esquema)")
        return

    print("\n--- 1. linhas por fração, e quantas ficam de fora do filtro ---")
    # O de fora importa tanto quanto o de dentro: se o filtro derrubar frações
    # de verdade, a tela dirá "12 de 25" para quem está na 15ª.
    for rotulo, sql in (
        ("TODAS as linhas",
         "SELECT COUNT(*) FROM DWH.FactTreatmentHistory th "
         "JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
         "WHERE p.PatientId = ?"),
        ("com o filtro de tratado",
         "SELECT COUNT(*) FROM DWH.FactTreatmentHistory th "
         "JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
         "WHERE p.PatientId = ? AND th.TreatmentStartTime IS NOT NULL "
         "  AND th.FractionNumber > 0"),
        ("frações DISTINTAS com o filtro",
         "SELECT COUNT(DISTINCT th.FractionNumber) "
         "FROM DWH.FactTreatmentHistory th "
         "JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
         "WHERE p.PatientId = ? AND th.TreatmentStartTime IS NOT NULL "
         "  AND th.FractionNumber > 0"),
        ("o que o DW diz (FractionsDelivered)",
         "SELECT MAX(th.FractionsDelivered) FROM DWH.FactTreatmentHistory th "
         "JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
         "WHERE p.PatientId = ?"),
        ("planejadas (FractionsPlanned)",
         "SELECT MAX(th.FractionsPlanned) FROM DWH.FactTreatmentHistory th "
         "JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
         "WHERE p.PatientId = ?"),
    ):
        try:
            cur = _cur(cx)
            cur.execute(sql, registro)
            print(f"  {rotulo:42} {cur.fetchone()[0]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {rotulo:42} falhou: {str(exc)[:80]}")
    print("\n  LEITURA: 'frações DISTINTAS' tem de bater com 'FractionsDelivered'.")
    print("  Se não bater, o filtro está errado — e é o número grande da tela.")

    print("\n--- 1b. QUANTOS CURSOS tem este paciente? ---")
    # A primeira rodada (19/08/2026) mostrou um paciente com dois cursos, um de
    # 2024 e um de 2026 — e o GROUP BY sem curso FUNDIA as frações dos dois.
    try:
        cur = _cur(cx)
        cur.execute(
            "SELECT th.DimCourseID, COUNT(DISTINCT th.FractionNumber), "
            "       MIN(th.TreatmentStartTime), MAX(th.TreatmentStartTime), "
            "       MAX(th.FractionsPlanned) "
            "  FROM DWH.FactTreatmentHistory th "
            "  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
            " WHERE p.PatientId = ? AND th.TreatmentStartTime IS NOT NULL "
            "   AND th.FractionNumber > 0 "
            " GROUP BY th.DimCourseID ORDER BY MAX(th.TreatmentStartTime) DESC",
            registro)
        print("  curso | frações | primeira | última | planejadas")
        for c, n, ini, fim, plan in cur.fetchall():
            print(f"   {c:>6} | {n:>7} | {str(ini)[:10]} | {str(fim)[:10]} | {plan}")
        print("\n  LEITURA: mais de uma linha = o filtro por curso é obrigatório.")
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:200]}")

    print("\n--- 2. a consulta REAL CORRIGIDA (por curso, PrimaryFlag) ---")
    sql = ("SELECT TOP 10 th.FractionNumber, MIN(th.TreatmentStartTime), "
           "       MAX(m.MachineId), MAX(th.TreatmentSignOffUser1), "
           "       SUM(th.DoseDeliveredPerFraction), COUNT(*) "
           "  FROM DWH.FactTreatmentHistory th "
           "  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
           "  LEFT JOIN DWH.DimMachine m ON m.DimMachineID = th.DimActualMachineID "
           " WHERE p.PatientId = ? AND th.TreatmentStartTime IS NOT NULL "
           "   AND th.FractionNumber > 0 AND th.PrimaryFlag = 1 "
           "   AND th.DimCourseID = (SELECT TOP 1 t2.DimCourseID "
           "        FROM DWH.FactTreatmentHistory t2 "
           "        JOIN DWH.DimPatient p2 ON p2.DimPatientID = t2.DimPatientID "
           "       WHERE p2.PatientId = ? AND t2.TreatmentStartTime IS NOT NULL "
           "       ORDER BY t2.TreatmentStartTime DESC) "
           " GROUP BY th.FractionNumber "
           " ORDER BY MIN(th.TreatmentStartTime) DESC")
    try:
        cur = _cur(cx)
        cur.execute(sql, registro, registro)
        print("  fração | início | máquina | quem tratou | dose Gy | nº linhas")
        for fr, ini, maq, quem, dose, n in cur.fetchall():
            print(f"   {fr:>5} | {str(ini)[:16]} | {str(maq)[:10]:<10} | "
                  f"{str(quem)[:22]:<22} | {dose} | {n}")
        print("\n  LEITURA, três coisas de uma vez:")
        print("   · as DATAS têm de ser todas do MESMO curso (não pular anos);")
        print("   · a 'dose Gy' de cada fração tem de bater com a dose por")
        print("     fração da prescrição — se der ~nº linhas × ela, a soma")
        print("     ainda conta duas vezes e o certo é MAX();")
        print("   · a fração mais alta tem de ser a de cima (a mais recente).")
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:200]}")

    print("\n--- 2b. o resumo do curso, e a UNIDADE da dose ---")
    try:
        cur = _cur(cx)
        cur.execute(
            "SELECT TOP 3 th.FractionsDelivered, th.FractionsPlanned, "
            "       th.DosePerFraction, th.CourseDoseDelivered, "
            "       th.CourseDosePlanned, th.RefPointId "
            "  FROM DWH.FactTreatmentHistory th "
            "  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
            " WHERE p.PatientId = ? AND th.PrimaryFlag = 1 "
            "   AND th.FractionsPlanned > 0 "
            " ORDER BY th.LastTreatmentDate DESC", registro)
        print("  entregues | planejadas | dose/fração | entregue | planejada | RefPoint")
        for e, pl, dpf, cd, cp, rp in cur.fetchall():
            print(f"   {e:>9} | {pl:>10} | {dpf:>11} | {cd} | {cp} | {rp}")
        print("\n  LEITURA: 'dose/fração' perto de 2 ou 4 = GRAY (o app converte")
        print("  ×100 para cGy). Perto de 200 ou 400 = já é cGy, e a conversão")
        print("  em ``_GY_PARA_CGY`` tem de virar 1.")
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:200]}")

    print("\n--- 3. quem tratou está preenchido? ---")
    try:
        cur = _cur(cx)
        cur.execute(
            "SELECT COUNT(*), COUNT(NULLIF(LTRIM(RTRIM("
            "  ISNULL(th.TreatmentSignOffUser1, ''))), '')) "
            "  FROM DWH.FactTreatmentHistory th "
            "  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
            " WHERE p.PatientId = ? AND th.TreatmentStartTime IS NOT NULL",
            registro)
        total, com_nome = cur.fetchone()
        print(f"  linhas tratadas: {total} | com nome de operador: {com_nome}")
        if not com_nome:
            print("  VAZIO. A máquina de tratamento não assina neste banco — a")
            print("  tela vai dizer '(não informado)', e a alternativa é o ARIA")
            print("  clínico (variansystem): outro banco, outra permissão.")
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:200]}")


def sessoes_sumidas(cx, registro: str) -> None:
    """Por que a lista de sessões para ANTES do fim do curso?

    Visto em 20/08/2026, paciente 9000011CEL: o cabeçalho dizia
    "16/07 – 20/08" e a última sessão listada era 07/08. Duas semanas de
    tratamento não apareciam — e o "12 / 30" da tela é justamente o número que o
    médico lê para decidir.

    As duas consultas diferem em UMA linha: a dos cursos não filtra
    ``PrimaryFlag``, a das sessões filtra. A suspeita é que as frações recentes
    tenham ``PrimaryFlag`` diferente de 1 — replanejamento cria outro ponto de
    referência, e o "primário" pode ter mudado de lugar.

    Isto MEDE a suspeita em vez de acreditar nela.
    """
    print(f"\n{'=' * 70}\nSessões que somem da lista ({registro})\n{'=' * 70}")
    if not registro:
        print("  (precisa de --paciente)")
        return

    # IGUAL à de produção, inclusive o ``FractionNumber > 0``: sem ele, uma
    # linha de plano sem tratamento poderia eleger outro curso, e o diagnóstico
    # mediria um curso diferente do que a tela abre — que é o oposto de
    # diagnosticar.
    curso = ("(SELECT TOP 1 t2.DimCourseID FROM DWH.FactTreatmentHistory t2 "
             "  JOIN DWH.DimPatient p2 ON p2.DimPatientID = t2.DimPatientID "
             " WHERE p2.PatientId = ? AND t2.TreatmentStartTime IS NOT NULL "
             "   AND t2.FractionNumber > 0 "
             " ORDER BY t2.TreatmentStartTime DESC)")

    print("\n--- frações e datas, COM e SEM o filtro de PrimaryFlag ---")
    for rotulo, extra in (("COM PrimaryFlag = 1", " AND th.PrimaryFlag = 1"),
                          ("SEM o filtro", "")):
        try:
            cur = _cur(cx)
            cur.execute(
                "SELECT COUNT(DISTINCT th.FractionNumber), "
                "       MIN(th.TreatmentStartTime), MAX(th.TreatmentStartTime), "
                "       MAX(th.FractionNumber) "
                "  FROM DWH.FactTreatmentHistory th "
                "  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
                " WHERE p.PatientId = ? AND th.DimCourseID = " + curso +
                "   AND th.TreatmentStartTime IS NOT NULL "
                "   AND th.FractionNumber > 0" + extra,
                registro, registro)
            n, ini, fim, maior = cur.fetchone()
            print(f"  {rotulo:22} frações={n:<4} de {str(ini)[:10]} "
                  f"a {str(fim)[:10]}   maior fração={maior}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {rotulo:22} falhou: {str(exc)[:90]}")
    print("\n  LEITURA: se os dois números diferirem, o PrimaryFlag está")
    print("  escondendo tratamento — e a tela mostra fração a MENOS.")

    print("\n--- as 12 frações mais recentes: RefPoint e PrimaryFlag ---")
    # É aqui que se vê o que mudou: se as frações novas trocaram de RefPoint, ou
    # se o "primário" deixou de ser marcado.
    try:
        cur = _cur(cx)
        cur.execute(
            "SELECT TOP 40 th.FractionNumber, th.TreatmentStartTime, "
            "       th.RefPointId, th.PrimaryFlag, th.DimPlanID, "
            "       th.FractionsDelivered, th.FractionsPlanned "
            "  FROM DWH.FactTreatmentHistory th "
            "  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
            " WHERE p.PatientId = ? AND th.DimCourseID = " + curso +
            "   AND th.TreatmentStartTime IS NOT NULL AND th.FractionNumber > 0 "
            " ORDER BY th.TreatmentStartTime DESC, th.FractionNumber DESC",
            registro, registro)
        print("  fração | quando           | RefPoint          | Prim | plano | entr/plan")
        vistos = set()
        for fr, quando, rp, prim, plano, ent, plan in cur.fetchall():
            chave = (fr, rp, prim)
            if chave in vistos:
                continue
            vistos.add(chave)
            # str() ANTES de formatar: PrimaryFlag e DimPlanID vêm NULL em
            # parte das linhas, e ">4" sobre None levanta TypeError — que o
            # except externo engoliria, cortando a listagem exatamente no caso
            # que esta função existe para investigar.
            print(f"   {fr!s:>5} | {str(quando)[:16]} | {str(rp)[:17]:<17} | "
                  f"{prim!s:>4} | {plano!s:>5} | {ent}/{plan}")
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:200]}")
    print("\n  LEITURA: se as frações recentes tiverem Prim=0, ou outro")
    print("  RefPoint, ou outro plano — é o replanejamento, e o filtro precisa")
    print("  deixar de ser 'PrimaryFlag = 1' para ser 'o RefPoint principal DE")
    print("  CADA PLANO'.")


def dose_por_plano(cx, registro: str) -> None:
    """A dose é do CURSO ou de cada PLANO? E por que ela some da tela?

    Duas perguntas que só o banco responde, e as duas apareceram em 21/08/2026:

    1. **Por plano ou por curso.** Com dois planos tratando juntos
       (``sMEDIAST_DB`` + ``sHILO-D_DIB``, paciente 9000010CEL) um número só de
       "dose entregue" não quer dizer nada: são alvos DIFERENTES, e dose a
       alvos diferentes não se soma. A tela já sabe quebrar por plano, mas só
       quebra quando os números DIFEREM — se ``CourseDoseDelivered`` for do
       curso, ele vem igual em todo plano e repeti-lo seria afirmar que cada
       alvo recebeu o total.

    2. **Por que a dose vem VAZIA** nesse mesmo paciente. A suspeita é o
       ``PrimaryFlag = 1`` que o ``_SQL_RESUMO`` exige — a mesma armadilha que
       já escondeu sessões (ver :func:`sessoes_sumidas`). A prova indireta está
       na tela: o total de frações veio da PRESCRIÇÃO, não do banco, o que só
       acontece quando aquela consulta não devolve linha nenhuma.

    Isto MEDE as duas em vez de acreditar em qualquer uma.
    """
    print(f"\n{'=' * 70}\nDose: por curso ou por plano? ({registro})\n{'=' * 70}")
    if not registro:
        print("  (precisa de --paciente)")
        return

    curso = ("(SELECT TOP 1 t2.DimCourseID FROM DWH.FactTreatmentHistory t2 "
             "  JOIN DWH.DimPatient p2 ON p2.DimPatientID = t2.DimPatientID "
             " WHERE p2.PatientId = ? AND t2.TreatmentStartTime IS NOT NULL "
             "   AND t2.FractionNumber > 0 "
             " ORDER BY t2.TreatmentStartTime DESC)")

    print("\n--- 1. uma linha por PLANO × RefPoint (o grão da dose) ---")
    try:
        cur = _cur(cx)
        cur.execute(
            "SELECT TOP 40 th.DimPlanID, MAX(pl.PlanSetupId), th.RefPointId, "
            "       th.PrimaryFlag, MAX(th.CourseDoseDelivered), "
            "       MAX(th.CourseDosePlanned), MAX(th.DosePerFraction), "
            "       MAX(th.FractionsDelivered), MAX(th.FractionsPlanned) "
            "  FROM DWH.FactTreatmentHistory th "
            "  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
            "  LEFT JOIN DWH.DimPlan pl ON pl.DimPlanID = th.DimPlanID "
            " WHERE p.PatientId = ? AND th.DimCourseID = " + curso +
            "   AND th.TreatmentStartTime IS NOT NULL AND th.FractionNumber > 0 "
            " GROUP BY th.DimPlanID, th.RefPointId, th.PrimaryFlag "
            " ORDER BY th.DimPlanID, th.RefPointId",
            registro, registro)
        print("  plano  | nome do plano    | RefPoint          | Prim | "
              "entregue | planejada | /fração | fr")
        for (pid, nome, rp, prim, cd, cp, dpf, fe, fp) in cur.fetchall():
            # ``str()`` ANTES de formatar: PrimaryFlag e DimPlanID vêm NULL em
            # parte das linhas, e um ">4" sobre None levanta TypeError que o
            # ``except`` engoliria — cortando justamente a listagem que
            # interessa. Armadilha já paga em ``sessoes_sumidas``.
            print(f"  {pid!s:>6} | {str(nome)[:16]:<16} | {str(rp)[:17]:<17} | "
                  f"{prim!s:>4} | {cd!s:>8} | {cp!s:>9} | {dpf!s:>7} | "
                  f"{fe}/{fp}")
        print("\n  LEITURA, e é a decisão inteira:")
        print("   · 'entregue' DIFERENTE entre planos = a dose é POR PLANO, e a")
        print("     tela deve quebrar o cartão (é o que ela já faz sozinha);")
        print("   · 'entregue' IGUAL em todos = a dose é do CURSO, e um cartão")
        print("     só está certo — repetir por plano afirmaria que cada alvo")
        print("     recebeu o total;")
        print("   · se as linhas com dose tiverem Prim=0 ou NULL, é ESTE o")
        print("     motivo de a dose sumir da tela.")
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:200]}")

    print("\n--- 2. o resumo COM e SEM o filtro de PrimaryFlag ---")
    # A consulta de produção é esta, com ``PrimaryFlag = 1``. Se a versão SEM o
    # filtro devolver linha e a COM não devolver nada, o defeito está medido.
    for rotulo, extra in (("COM PrimaryFlag = 1", " AND th.PrimaryFlag = 1"),
                          ("SEM o filtro", "")):
        try:
            cur = _cur(cx)
            cur.execute(
                "SELECT TOP 1 th.FractionsDelivered, th.FractionsPlanned, "
                "       th.CourseDoseDelivered, th.CourseDosePlanned, "
                "       th.RefPointId "
                "  FROM DWH.FactTreatmentHistory th "
                "  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID "
                " WHERE p.PatientId = ? AND th.DimCourseID = " + curso +
                "   AND th.FractionsPlanned > 0" + extra +
                " ORDER BY th.LastTreatmentDate DESC",
                registro, registro)
            linha = cur.fetchone()
            print(f"  {rotulo:22} {linha if linha else 'NADA — nenhuma linha'}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {rotulo:22} falhou: {str(exc)[:90]}")
    print("\n  LEITURA: 'NADA' na primeira e linha na segunda = o PrimaryFlag")
    print("  está apagando a dose do quadro, e o filtro tem de sair das DUAS")
    print("  consultas de dose (nenhuma delas soma: uma é TOP 1, a outra MAX).")


# Quantos médicos o passo da conferência consulta, um por um. Cada nome é uma
# consulta a mais no servidor clínico em expediente, e a pergunta que o laço
# responde ("a soma dos médicos dá a lista inteira?") já se responde com a
# equipe de um serviço — não é varredura, é conferência.
MAX_MEDICOS = 40


class _Calados(logging.Handler):
    """Guarda os avisos que o ``tratamento_db`` solta quando desiste em silêncio.

    As três auxiliares da lista (``_corrigir_entregues``, ``_marcar_frequencia``
    e ``_contar_cursos``) falham de propósito sem derrubar nada: sem elas a
    lista continua de pé, com o número do DW. Isso é certo na TELA e é veneno
    numa CONFERÊNCIA — o relatório sairia com a coluna do banco parecendo a
    recontada, e a divergência contra o ARIA seria atribuída ao SQL errado.
    Elas avisam pelo ``logging``, e sem alguém escutando o aviso morre no ar.
    """

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.ditos: list = []

    def emit(self, registro) -> None:      # noqa: D102
        self.ditos.append(self.format(registro))


def _linha_da_lista(e, hoje) -> str:
    """Uma linha da lista, do jeito que se compara com o quadro do ARIA.

    Registro e nome PRIMEIRO, porque a comparação é nome por nome contra a tela
    do ARIA e quem confere lê com o dedo. As marcas vão no fim, entre colchetes:
    elas são o que o painel ACRESCENTA, e o que o ARIA não tem para conferir.
    """
    fracoes = f"{e.entregues}/{e.previstas}" if e.previstas else f"{e.entregues}/?"
    ultima = f"{e.ultima:%d/%m}" if e.ultima else "sem sessão"
    marcas = " ".join(f"{s} {t}" for s, t in e.marcas(hoje))
    freq = e.frequencia or "SEM FREQUÊNCIA"
    cursos = f"{e.cursos_total}º curso" if e.cursos_total else "cursos ?"
    return (f"    {e.registro:<12} {e.nome[:34]:<34} curso {e.curso_id:<7} "
            f"{fracoes:>8}  última {ultima}  {freq} · {cursos}"
            + (f"  [{marcas}]" if marcas else ""))


def _sem_auxiliar(linhas) -> list:
    """O que ficou VAZIO em toda a lista — a auxiliar não respondeu.

    Mesma armadilha da taxa de preenchimento do ``mapear_gatilho``: coluna
    inteira vazia não se distingue de "este banco não tem esse dado" olhando
    uma linha. E aqui há um jeito de ela ficar vazia sem erro nenhum — a lista
    passar de ``_MAX_NA_CONTAGEM``, quando as três auxiliares simplesmente
    voltam sem consultar.
    """
    fora = []
    if linhas and not any(e.frequencia for e in linhas):
        fora.append("frequencia (as marcas de interrupção contam como diária)")
    if linhas and not any(e.cursos_total for e in linhas):
        fora.append("cursos_total (o retratamento não aparece)")
    return fora


def _em_blocos_de_registro(linhas, teto: int) -> list:
    """A lista partida em blocos de até ``teto`` registros DISTINTOS.

    Por registro, e não por linha: é o registro que vira parâmetro no
    ``IN (...)`` da recontagem e é ele que o ``_MAX_NA_CONTAGEM`` conta. E as
    linhas de um mesmo paciente ficam no mesmo bloco, para o retratamento (dois
    cursos, um registro) não ir ao servidor duas vezes.
    """
    por_registro: dict = {}
    for e in linhas:
        por_registro.setdefault(e.registro, []).append(e)
    chaves = list(por_registro)
    passo = max(teto, 1)
    return [[e for r in chaves[i:i + passo] for e in por_registro[r]]
            for i in range(0, len(chaves), passo)]


# Plano a plano, para decidir a regra do "concluído" com o número na mão.
#
# Na rodada de 11/09/2026, 48 cursos da lista larga saíram "N/M" com N > M
# ("34/1", "36/10", muitos "9/5"). As duas pontas medem coisas diferentes: a
# recontagem soma os dias do CURSO inteiro, e o ``previstas`` é o
# ``MAX(FractionsPlanned)`` só dos planos com sessão nos últimos 30 dias. O
# curso que ontem era "33/33" virou "34/1" porque a última sessão do plano de
# 33 caiu fora da janela e sobrou um plano de uma fração.
#
# A regra decidida é comparar por PLANO. Mas os planos avulsos que a recontagem
# existe para absorver — a fração da máquina reserva, o replanejamento
# "13 + 1 + 1" de 21/08 — só se comportam bem nessa regra se declararem o
# PRÓPRIO total (1, e não 20). Esse número ninguém mediu, e é o que este bloco
# mede. Sem ``PrimaryFlag`` no filtro, como a recontagem; a coluna sai ao lado
# para se ver o que o filtro da consulta principal esconde.
_SQL_PLANOS_DO_CURSO = """
SELECT p.PatientId,
       th.DimCourseID,
       th.DimPlanID,
       MAX(pl.PlanSetupId),
       CONVERT(char(8), MIN(th.TreatmentStartTime), 112),
       CONVERT(char(8), MAX(th.TreatmentStartTime), 112),
       COUNT(DISTINCT th.FractionNumber),
       MAX(th.FractionsPlanned),
       MAX(th.FractionsDelivered),
       MAX(CAST(th.PrimaryFlag AS int)),
       MAX(m.MachineId)
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
  LEFT JOIN DWH.DimPlan pl ON pl.DimPlanID = th.DimPlanID
  LEFT JOIN DWH.DimMachine m ON m.DimMachineID = th.DimActualMachineID
 WHERE p.PatientId IN ({})
   AND th.TreatmentStartTime IS NOT NULL
   AND th.FractionNumber > 0
 GROUP BY p.PatientId, th.DimCourseID, th.DimPlanID
"""


def _planos_dos_cursos(capa_db, td, registros) -> dict:
    """``{(registro, curso): [plano, ...]}``, do plano mais antigo ao mais novo.

    Em blocos abaixo do teto pela mesma razão da recontagem: o ``IN (...)``
    leva um parâmetro por registro, e a lista larga passa de 400. A falha
    SOBE: quem chama é que sabe dizer "não deu" sem derrubar o resto.
    """
    registros = sorted({r for r in registros if r})
    passo = max(td._MAX_NA_CONTAGEM, 1)
    fora: dict = {}
    for i in range(0, len(registros), passo):
        parte = registros[i:i + passo]
        marcas = ", ".join("?" for _ in parte)
        achado = capa_db._consultar(_SQL_PLANOS_DO_CURSO.format(marcas), *parte)
        for (pid, curso, plano, nome, de, ate, fracoes, previstas, dw,
             primario, maquina) in achado:
            fora.setdefault((capa_db._txt(pid), int(curso or 0)), []).append({
                "plano": int(plano or 0), "nome": capa_db._txt(nome),
                "de": capa_db._txt(de), "ate": capa_db._txt(ate),
                "fracoes": int(fracoes or 0), "previstas": int(previstas or 0),
                "dw": int(dw or 0), "primario": int(primario or 0),
                "maquina": capa_db._txt(maquina)})
    for planos in fora.values():
        planos.sort(key=lambda p: (p["de"], p["ate"]))
    return fora


# O que o ARIA usa para dizer "terminou" é o total de frações da PRESCRIÇÃO
# (conferido pelo usuário em 11/09/2026), e não o do plano: o serviço desconta
# a fração da máquina reserva do plano seguinte num caso (29737: 8 + 1 + 21 =
# 30) e não no outro (29854: 9 + 11 = 20, a reserva dentro dos 20). Nenhuma
# regra que olhe só o total dos planos acerta os dois.
#
# O vínculo é o ``ctrPrescriptionSer`` de cada linha da ``FactTreatmentHistory``
# (medido na rodada de 11/09 08:25) — a mesma chave pela qual a capa chega ao
# ``NumberOfFractions``. Consulta À PARTE da de planos: ela é nova, e se falhar
# na estação o bloco já medido tem de sair inteiro do mesmo jeito.
#
# ``COUNT(DISTINCT rx.DimPrescriptionID)`` está aí porque a ``DimPrescription``
# pode guardar mais de uma linha por prescrição, e o ``MAX`` do total
# esconderia isso — pegaria o maior sem avisar.
_SQL_PRESCRICAO_DOS_PLANOS = """
SELECT p.PatientId,
       th.DimCourseID,
       th.DimPlanID,
       COUNT(DISTINCT th.ctrPrescriptionSer),
       MAX(th.ctrPrescriptionSer),
       MAX(rx.PrescriptionName),
       MAX(rx.NumberOfFractions),
       COUNT(DISTINCT rx.DimPrescriptionID),
       MAX(th.NoTxSessionDelivered),
       MAX(th.NoTxSessionPlanned),
       MAX(th.DimDateID_CourseCompletedDateTime)
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimPatient p ON p.DimPatientID = th.DimPatientID
  LEFT JOIN DWH.DimPrescription rx
    ON rx.ctrPrescriptionSer = th.ctrPrescriptionSer
 WHERE p.PatientId IN ({})
   AND th.TreatmentStartTime IS NOT NULL
   AND th.FractionNumber > 0
 GROUP BY p.PatientId, th.DimCourseID, th.DimPlanID
"""


def _prescricoes_dos_planos(capa_db, td, registros) -> dict:
    """``{(registro, curso, plano): prescrição}`` — a que cada plano toca.

    Em blocos abaixo do teto, como ``_planos_dos_cursos``, e pela mesma razão.
    A falha SOBE: quem chama decide o que dizer.
    """
    registros = sorted({r for r in registros if r})
    passo = max(td._MAX_NA_CONTAGEM, 1)
    fora: dict = {}
    for i in range(0, len(registros), passo):
        parte = registros[i:i + passo]
        marcas = ", ".join("?" for _ in parte)
        achado = capa_db._consultar(
            _SQL_PRESCRICAO_DOS_PLANOS.format(marcas), *parte)
        for (pid, curso, plano, n, rx, nome, total, versoes, sessoes,
             sessoes_previstas, concluido) in achado:
            fora[(capa_db._txt(pid), int(curso or 0), int(plano or 0))] = {
                "n": int(n or 0), "rx": int(rx or 0),
                "nome": capa_db._txt(nome), "total": int(total or 0),
                "versoes": int(versoes or 0), "sessoes": int(sessoes or 0),
                "sessoes_previstas": int(sessoes_previstas or 0),
                "concluido": concluido}
    return fora


def _data_de_conclusao(dim_date) -> str:
    """``DimDateID`` 20260814 → "14/08/2026". O DW grava 18000101 no lugar de
    nulo (medido na amostra de 11/09 08:25), e isso quer dizer "nunca"."""
    try:
        t = str(int(dim_date or 0))
    except (TypeError, ValueError):
        return ""
    if len(t) != 8 or t.startswith("1800"):
        return ""
    return f"{t[6:8]}/{t[4:6]}/{t[:4]}"


def _linha_da_prescricao(rx: dict) -> str:
    """O que se compara com a tela de prescrição do ARIA, plano a plano."""
    if rx["n"] == 0:
        texto = "sem prescrição no DW"
    else:
        texto = f"prescrição {rx['rx']} \"{rx['nome'][:24]}\" {rx['total']} fr"
        if rx["n"] > 1:
            texto += f"  ⚠ {rx['n']} prescrições no mesmo plano"
        if rx["versoes"] > 1:
            texto += f"  ({rx['versoes']} linhas na DimPrescription)"
    texto += f" · sessões do DW {rx['sessoes']}/{rx['sessoes_previstas']}"
    fim = _data_de_conclusao(rx["concluido"])
    return texto + (f" · curso concluído {fim}" if fim
                    else " · curso não concluído")


def _dia(aaaammdd: str) -> str:
    """"20260811" → "11/08". O ``CONVERT(..., 112)`` devolve TEXTO: o driver
    ODBC antigo da estação não conhece o tipo ``DATE``."""
    t = (aaaammdd or "").strip()
    return f"{t[6:8]}/{t[4:6]}" if len(t) == 8 else "??/??"


def _bloco_plano_a_plano(td, capa_db, todos) -> None:
    """Os cursos em que "concluído" depende de QUAIS planos se comparam.

    Entram os de mais de um plano e os em que o total não cobre as frações
    recontadas; estes vêm primeiro, porque são os que a regra por plano muda.
    """
    print("\n  -- plano a plano: curso com mais de um plano, ou cujo total "
          "não cobre --")
    try:
        planos = _planos_dos_cursos(capa_db, td, [e.registro for e in todos])
    except Exception as exc:  # noqa: BLE001
        print(f"    NÃO deu: {str(exc)[:80]}")
        return
    try:
        prescricoes = _prescricoes_dos_planos(
            capa_db, td, [e.registro for e in todos])
    except Exception as exc:  # noqa: BLE001
        prescricoes = {}
        print(f"    prescrição: NÃO deu: {str(exc)[:80]}")
    alvo = [e for e in todos
            if len(planos.get((e.registro, e.curso_id), [])) > 1
            or not td.cobre(e.entregues, e.previstas)]
    alvo.sort(key=lambda e: td.cobre(e.entregues, e.previstas))
    sem_cobrir = sum(1 for e in alvo if not td.cobre(e.entregues, e.previstas))
    print(f"    {len(alvo)} curso(s); em {sem_cobrir} o total não cobre as "
          f"frações recontadas")
    for e in alvo:
        marca = ("" if td.cobre(e.entregues, e.previstas)
                 else "  ⚠ o total não cobre")
        print(f"      {e.registro:<12} {e.nome[:34]:<34} curso {e.curso_id:<7} "
              f"{e.entregues}/{e.previstas}{marca}")
        por_prescricao: dict = {}
        for p in planos.get((e.registro, e.curso_id), []):
            print(f"          {p['nome'][:22]:<22} "
                  f"{_dia(p['de'])}–{_dia(p['ate'])}  "
                  f"{p['fracoes']:>3} fração(ões), total do plano "
                  f"{p['previstas']:<3} (DW {p['dw']})  "
                  f"{p['maquina'][:14]:<14} primário={p['primario']}")
            rx = prescricoes.get((e.registro, e.curso_id, p["plano"]))
            if rx is None:
                continue
            print(f"              {_linha_da_prescricao(rx)}")
            if rx["n"] == 1:
                soma = por_prescricao.setdefault(rx["rx"], [rx["total"], 0])
                soma[1] += p["fracoes"]
        # A SOMA das frações dos planos da mesma prescrição é a candidata a
        # regra: 9 + 1 + 10 = 20 de 20 no caso que terminou. Frações partidas
        # entre dois planos no mesmo dia contam duas vezes aqui — por isso as
        # sessões do DW saem ao lado, para comparar as duas contas com o ARIA.
        for numero, (total, soma) in por_prescricao.items():
            print(f"          ⇒ prescrição {numero}: {soma} fração(ões) nos "
                  f"planos, de {total}")


def passo_consulta(medico_forcado: str = "") -> None:
    """Roda o ``tratamento_db`` de verdade — é o teste dele contra o banco.

    Os passos de cima descobrem o que EXISTE no DW; este pergunta o que a
    consulta RESPONDE. É a saída daqui que se compara, nome por nome, com o
    quadro de pacientes em tratamento do ARIA, e é dessa comparação que sai a
    data do ``tratamento_db.LISTA_VERIFICADA_EM``.

    Em 10/09/2026 o TEMPO já foi medido na estação (0,19 s, 0,10 s e 0,18 s
    contra o limite de 6 s), mas colando o SQL do módulo no prompt. Isso mede
    três consultas; ``em_tratamento`` faz SEIS — as três auxiliares acima
    entram depois, e nenhuma delas estava na conta. O tempo que interessa para
    a thread da tela é o da FUNÇÃO, e é ele que sai daqui.
    """
    import os

    from isocentro.banco import capa_db
    from isocentro.banco import tratamento_db as td

    print("\n\n===== A consulta da lista (tratamento_db) =====")
    print(f"  DIAS_DA_JANELA      {td.DIAS_DA_JANELA}")
    print(f"  _DIAS_PARADO        {td._DIAS_PARADO}")
    print(f"  _FALTAM_POUCAS      {td._FALTAM_POUCAS}")
    print(f"  _MAX_NA_CONTAGEM    {td._MAX_NA_CONTAGEM}")
    print(f"  VERIFICADO_EM       {td.VERIFICADO_EM or '(nunca)'}  "
          f"(a consulta POR PACIENTE)")
    print(f"  LISTA_VERIFICADA_EM {td.LISTA_VERIFICADA_EM or '(nunca)'}  "
          f"(a LISTA — é o que esta rodada existe para destravar)")
    print(f"  limite de tempo     {capa_db.TEMPO_LIMITE_S} s (capa_db)")

    # O portão fecha a lista NA ORIGEM: ``em_tratamento`` devolve ``None`` sem
    # perguntar nada ao banco enquanto ``lista_disponivel()`` for falso. Sem
    # ligar o experimental aqui, o relatório inteiro sairia vazio — e vazio por
    # decisão nossa, que é a pior forma de "não deu".
    antes = os.environ.get(td.ENV_EXPERIMENTAL, "")
    os.environ[td.ENV_EXPERIMENTAL] = "1"
    escuta = _Calados()
    escuta.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    logging.getLogger("isocentro").addHandler(escuta)
    try:
        if not td.lista_conferida():
            print(f"\n  portão da LISTA fechado; ligado nesta rodada por "
                  f"{td.ENV_EXPERIMENTAL}.")
            print("  Os números abaixo são o que o app MOSTRARIA, não o que "
                  "ele mostra hoje.")
        if not td.lista_disponivel():
            # A variável experimental é só METADE do portão: ``lista_disponivel``
            # exige antes o ``disponivel()``, que pede banco apontado e o
            # ``VERIFICADO_EM`` da consulta por paciente. Sem este aviso, o
            # relatório sairia com zero curso em toda linha — e zero curso lê-se
            # como "ninguém em tratamento", que é a resposta oposta.
            print(f"\n  ATENÇÃO: o portão continuou FECHADO mesmo com "
                  f"{td.ENV_EXPERIMENTAL} ligada.")
            print(f"  {td.motivo_indisponivel() or 'a consulta por paciente '
                       'não está conferida (VERIFICADO_EM vazio).'}")
            print("  Tudo abaixo vai sair vazio, e vazio AQUI não quer dizer "
                  "'ninguém em tratamento'.")
        _consulta_medida(td, medico_forcado)
    finally:
        logging.getLogger("isocentro").removeHandler(escuta)
        if antes:
            os.environ[td.ENV_EXPERIMENTAL] = antes
        else:
            os.environ.pop(td.ENV_EXPERIMENTAL, None)

    # Por último, e não junto de cada passo: são avisos de coisa que NÃO
    # derrubou nada, e intercalados eles pareceriam erro da consulta ao lado.
    print("\n  -- o que falhou calado --")
    for dito in escuta.ditos:
        print(f"    {dito}")
    if not escuta.ditos:
        print("    nada. As três auxiliares responderam (ou nem foram "
              "chamadas — ver as colunas vazias acima).")

    # O relatório termina dizendo o que fazer com ele. A rodada de 02/09/2026
    # do gatilho voltou com a saída certa e a conferência parada mais dois
    # dias: quem lê na estação, com o ARIA aberto ao lado, precisa da lista do
    # que conferir no papel — e não de lembrar dela.
    print("\n  -- o que fecha a conferência (com o ARIA aberto ao lado) --")
    print("    (a) cada nome acima está no quadro de pacientes em tratamento;")
    print("    (b) NENHUM nome do quadro do ARIA falta aqui. É esta que decide,")
    print("        e ausência não aparece numa lista: quando faltar alguém, ele")
    print("        costuma estar no bloco 'DEIXOU DE FORA', com o motivo;")
    print("    (c) a fração N/M bate, paciente por paciente — o que se confere")
    print("        aí é a RECONTAGEM por dia, não o número do DW;")
    print("    (d) o filtro do médico: os pacientes de cada um são os dele;")
    print("    (e) plano a plano: o total de cada plano bate com o do ARIA —")
    print("        sobretudo o dos planos de poucas frações (máquina reserva,")
    print("        replanejamento);")
    print("    (f) a prescrição: o 'N de M' de cada prescrição bate com a tela")
    print("        de prescrição do ARIA — é ELE que decide o 'concluído'. Qual")
    print("        conta acerta: a soma dos planos ou as sessões do DW?")
    print("    Batendo, a data entra no tratamento_db.LISTA_VERIFICADA_EM, com")
    print("    o resultado E o tempo ao lado — como no atividades_db.")


def _consulta_medida(td, medico_forcado: str) -> None:
    """As quatro perguntas, cada uma com o seu cronômetro."""
    import time
    from datetime import date

    from isocentro.banco import capa_db

    hoje = date.today()

    print("\n  -- os médicos (o seletor do painel) --")
    inicio = time.perf_counter()
    try:
        equipe = td.medicos()
    except Exception as exc:  # noqa: BLE001
        print(f"    NÃO deu: {exc}")
        equipe = []
    print(f"    {len(equipe)} radio-oncologista(s) em "
          f"{time.perf_counter() - inicio:.2f} s")

    print("\n  -- a janela: em_tratamento() --")
    print("     (compare ESTA lista com o quadro do ARIA: nome por nome)")
    inicio = time.perf_counter()
    try:
        lista = td.em_tratamento()
    except Exception as exc:  # noqa: BLE001
        print(f"    NÃO deu: {exc}")
        return
    gasto = time.perf_counter() - inicio
    if lista is None:
        # ``None`` é "não consegui perguntar", e é o único caso em que insistir
        # adianta. Distinguir isto de lista vazia é a razão de a função devolver
        # os dois.
        print("    NÃO DEU para perguntar (o banco recusou ou caiu). "
              "Isto NÃO é 'ninguém em tratamento'.")
        return
    print(f"    {len(lista)} curso(s) em {gasto:.2f} s "
          f"(limite {capa_db.TEMPO_LIMITE_S} s — e este é o tempo da FUNÇÃO, "
          f"com as três auxiliares dentro)")
    faltando = _sem_auxiliar(lista)
    for coluna in faltando:
        print(f"    COLUNA VAZIA em todas as linhas: {coluna}")
    registros = {e.registro for e in lista if e.registro}
    if len(registros) > td._MAX_NA_CONTAGEM:
        print(f"    {len(registros)} registros > _MAX_NA_CONTAGEM "
              f"({td._MAX_NA_CONTAGEM}): as auxiliares NEM RODARAM, e as "
              f"frações acima são as do DW, sem a recontagem por dia.")
    for e in lista:
        print(_linha_da_lista(e, hoje))

    # A pergunta que decide o VERIFICADO_EM não é "estes estão certos?", é
    # "faltou alguém?" — e ausência não aparece numa lista. A lista larga
    # responde: quem o ARIA mostra e a janela não, tem de estar AQUI, com o
    # motivo da exclusão escrito.
    print("\n  -- quem a janela DEIXOU DE FORA: em_tratamento(todos) --")
    inicio = time.perf_counter()
    try:
        todos = td.em_tratamento(incluir_concluidos=True)
    except Exception as exc:  # noqa: BLE001
        print(f"    NÃO deu: {exc}")
        todos = None
    if todos is None:
        print("    NÃO DEU para perguntar.")
    else:
        gasto = time.perf_counter() - inicio
        print(f"    {len(todos)} curso(s) em {gasto:.2f} s")
        # O teto vale para ESTA lista também, e aqui ele quase sempre estoura:
        # a janela teve 165 cursos e a larga, 414. Acima dele o app nem
        # reconta, e o "concluído" logo abaixo sairia do ``entregues`` CRU do
        # DW — ``concluido()`` compara entregues com previstas.
        #
        # É o que acontece com quem teve uma fração na máquina RESERVA: ela
        # entra num plano próprio, o DW conta por plano, e o MAX devolve 19/20
        # de quem terminou as 20. Na rodada de 10/09/2026 foram sete assim, e o
        # bloco que decide o portão os mostrou como "parou de tratar" — o
        # usuário reconheceu cinco pelo nome (a máquina tinha parado). Com isso
        # a conferência (b) virava descontar de cabeça, nome por nome.
        #
        # Aqui é diagnóstico, não a thread da tela: recontar em blocos abaixo
        # do teto custa uma consulta por bloco e deixa o motivo certo. Se a
        # recontagem falhar, ela avisa pelo ``logging`` e o bloco "o que falhou
        # calado" diz. A JANELA acima não passa por isto: ela mostra o que o
        # app mostra, com teto e tudo.
        blocos = _em_blocos_de_registro(todos, td._MAX_NA_CONTAGEM)
        for bloco in blocos:
            td._corrigir_entregues(bloco)
        if len(blocos) > 1:
            print(f"    recontada por dia em {len(blocos)} blocos de até "
                  f"{td._MAX_NA_CONTAGEM} registros — o app, acima do teto, "
                  f"não reconta, e quem teve fração na máquina reserva "
                  f"sairia N-1/N")
        na_janela = {(e.registro, e.curso_id) for e in lista}
        fora = [e for e in todos if (e.registro, e.curso_id) not in na_janela]
        print(f"    {len(fora)} fora da janela:")
        for e in fora:
            # O motivo tem de vir junto: "concluído" e "parou de tratar e
            # sumiu" são as duas saídas possíveis, e só uma delas é notícia.
            #
            # A data vai também no "concluído": a fase 2 de um tratamento
            # sequencial sai daqui como concluída (o total da fase 1 já foi
            # alcançado), e só uma última sessão de ONTEM a denuncia. Até
            # 11/09/2026 o concluído saía sem data, e o bloco não deixava ver
            # justamente o caso que decide o portão.
            if e.concluido():
                motivo = (f"concluído · última {e.ultima:%d/%m}"
                          if e.ultima else "concluído")
            else:
                motivo = (f"última sessão {e.ultima:%d/%m}"
                          if e.ultima else "sem sessão")
            print(f"      {e.registro:<12} {e.nome[:34]:<34} "
                  f"curso {e.curso_id:<7} {e.entregues}/{e.previstas} — {motivo}")
        _bloco_plano_a_plano(td, capa_db, todos)

    print("\n  -- o filtro por médico --")
    alvos = ([m for m in equipe if medico_forcado.upper() in m.nome.upper()]
             if medico_forcado else equipe)
    if medico_forcado and not alvos:
        print(f"    nenhum médico casa com {medico_forcado!r}. Os nomes saem "
              f"do banco — confira no seletor do painel.")
    soma: set = set()
    for m in alvos[:MAX_MEDICOS]:
        inicio = time.perf_counter()
        try:
            dele = td.em_tratamento(medicos_alvo=[m])
        except Exception as exc:  # noqa: BLE001
            print(f"    {m.nome[:34]:<34} NÃO deu: {str(exc)[:60]}")
            continue
        gasto = time.perf_counter() - inicio
        if dele is None:
            print(f"    {m.nome[:34]:<34} NÃO deu para perguntar")
            continue
        chaves = {(e.registro, e.curso_id) for e in dele}
        soma |= chaves
        # Subconjunto ou não é a QUARTA chance de a granularidade campo × fração
        # morder este módulo: se o ``EXISTS`` do médico virasse ``JOIN``, a
        # lista dele traria linhas que a janela não tem, ou a mesma duas vezes.
        sobra = chaves - {(e.registro, e.curso_id) for e in lista}
        aviso = "" if not sobra else f"  ⚠ {len(sobra)} FORA da janela"
        repete = len(dele) - len(chaves)
        if repete:
            aviso += f"  ⚠ {repete} linha(s) REPETIDA(s)"
        print(f"    {m.nome[:34]:<34} {len(dele):>4} em {gasto:.2f} s{aviso}")
    if len(alvos) > MAX_MEDICOS:
        print(f"    (parei em {MAX_MEDICOS} de {len(alvos)} — cada nome é uma "
              f"consulta no servidor clínico)")

    # E o outro lado da mesma pergunta: o curso que não é de médico NENHUM é
    # invisível para quem usa o seletor, e é o modo silencioso de um paciente
    # sumir do painel sem sumir do ARIA.
    if not medico_forcado and len(alvos) <= MAX_MEDICOS:
        orfaos = [e for e in lista
                  if (e.registro, e.curso_id) not in soma]
        print(f"\n    {len(orfaos)} curso(s) da janela não aparecem em médico "
              f"nenhum:")
        for e in orfaos:
            print(f"      {e.registro:<12} {e.nome[:34]}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--servidor", default=SERVIDOR_PADRAO)
    p.add_argument("--banco", default=BANCO_PADRAO)
    p.add_argument("--porta", type=int, default=PORTA_PADRAO)
    p.add_argument("--paciente", default="",
                   help="registro de UM paciente EM TRATAMENTO")
    p.add_argument("--consulta", action="store_true",
                   help="roda o tratamento_db de verdade (o que a LISTA do "
                        "painel responde) em vez de descobrir o que existe no "
                        "DW — é o teste dela contra o banco")
    p.add_argument("--medico", default="",
                   help="com --consulta: mede o filtro só deste médico "
                        "(pedaço do nome basta). Sem ele, todos, e a soma é "
                        "comparada com a lista inteira")
    args = p.parse_args(argv)

    if args.consulta:
        # Caminho curto de propósito: os passos de descoberta abrem a conexão
        # CRUA do pyodbc, e o que se quer medir aqui é a do APP — com o prazo
        # dela, o driver dela e o servidor que ela escolheu. Medir a consulta
        # por outra conexão mediria outra coisa.
        import atividades as _at
        if _at._conectar(print, "mapear_tratamento.bat") is None:
            return 2
        print(f"Servidor : {_at.capa_db.servidor()}")
        passo_consulta(args.medico.strip())
        return 0

    passo_identidade()
    pyodbc = passo_pyodbc()
    if pyodbc is None:
        return 1
    driver = passo_drivers(pyodbc)
    if not driver:
        return 1
    # A REDE antes do login. Sem este passo, a falha de alcance chega como
    # "SQL Server inexistente ou acesso negado" — uma frase que mistura servidor
    # fora do ar, VPN caída e falta de permissão, e manda quem lê investigar a
    # coisa errada. Aconteceu em 20/08/2026: a saída acusou o banco, e o
    # servidor estava alcançável um minuto depois.
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
                  r'"C:\...\isocentro\tools\mapear_tratamento.bat '
                  r'--paciente 9000001CEL"')
        return 1
    try:
        # O que está DOENDO agora vem primeiro (``sessoes_sumidas``), depois as
        # hipóteses que decidem se o portão abre. O resto é rede de segurança,
        # para o caso de este banco estar numa versão diferente da documentada
        # (15.6).
        # O que a tela mostrou errado vem PRIMEIRO — é o que está
        # doendo agora.
        sessoes_sumidas(cx, args.paciente.strip())
        # A dose logo depois: é a segunda coisa que a tela está mostrando
        # errado (vazia num paciente que tratou), e a resposta dela decide se o
        # cartão quebra por plano — ver ``dose_por_plano``.
        dose_por_plano(cx, args.paciente.strip())
        conferir_hipoteses(cx, args.paciente.strip())
        achadas = tabelas_candidatas(cx)
        contagens(cx, achadas)
        procurar_colunas(cx)
        colunas_das_suspeitas(cx, achadas)
        quem_tratou(cx, args.paciente.strip())
        if args.paciente:
            sessoes_do_paciente(cx, args.paciente.strip())
        else:
            print("\n(sem --paciente: nenhuma linha de paciente foi lida — mas "
                  "é a amostra que PROVA qual tabela é a certa; vale rodar de "
                  "novo com um paciente em tratamento)")
    finally:
        cx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
