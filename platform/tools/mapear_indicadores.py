r"""Mapeia no data warehouse o que o Radioteradados (aba de indicadores) precisa.

O PRD do Radioteradados (``docs/planejamento/sistema-global/radioteradados/``) deixou
quatro perguntas que nenhuma leitura de código responde — só o banco da
clínica:

1. **Onde mora o motivo de encerramento do curso.** O abandono (RDC 20/2006,
   6.11b) exclui alta antecipada, óbito e mudança de conduta. Sem saber onde o
   ARIA guarda isso, todo curso que parou antes do prescrito vira "abandono" —
   o número sai inflado e com cara de certo;
2. **Onde mora a frequência prescrita.** A interrupção depende dela: no regime
   semanal, sete dias sem fração é o normal; no diário, é interrupção. Tratar
   os dois pelo mesmo limiar pinta de vermelho todo paciente semanal;
3. **Se a TC de simulação e a consulta são atividades registradas.** A taxa de
   simulação (6.11c) e o percurso consulta → simulação → início dependem disso;
4. **Se a braquiterapia está no ARIA.** O indicador ESGO/ESTRO do colo do útero
   (tempo total ≤ 50 dias) mede teleterapia + braquiterapia; com só metade no
   banco, ele mente para menos.

**Nenhuma linha de paciente é lida.** Tudo aqui é catálogo (colunas, códigos,
estados) ou contagem agregada: a saída pode ser lida, guardada e mandada sem
virar documento com dado de paciente. É a diferença para o ``mapear_agenda``,
que precisa de um dia de pacientes para PROVAR o mapeamento — aqui a pergunta
é "onde está", e contagem responde.

Rodar, de uma máquina fora do domínio:
    runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\mapear_indicadores.bat"

Nada aqui escreve no banco.
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, __file__.rsplit("tools", 1)[0])
sys.path.insert(0, __file__.rsplit("mapear_indicadores", 1)[0])

from diagnostico_db import (  # noqa: E402
    BANCO_PADRAO, PORTA_PADRAO, SERVIDOR_PADRAO, _conectar, _quem_sou,
    passo_drivers, passo_identidade, passo_pyodbc, passo_rede)
from mapear_dw import colunas_de  # noqa: E402

# Um PropertyType com mais valores distintos do que isto é texto livre e NÃO é
# amostrado: texto livre é onde o nome do paciente aparece sem ninguém ter
# pedido. Corrigido em 13/10/2026: a primeira versão excluía também o tipo 7,
# suposto "a nota da prescrição" — mas a nota mora em ``DimPrescription.Notes``
# e o tipo 7 é a FREQUÊNCIA (``capa_db._SQL_FREQUENCIA``, conferido contra o
# banco), com 7 valores distintos. A exclusão escondeu justamente a resposta da
# pergunta 2, e o PRD saiu apontando o ``DimPlan.FractionPattern``.
_MAX_DISTINTOS_AMOSTRA = 30

# Nomes de coluna que responderiam cada pergunta. Rede larga de propósito: o
# nome da tabela engana, e a coluna de nome inesperado é exatamente a que se
# procura (foi assim que ``DerivedAppointmentTaskDate`` apareceu na agenda).
TERMOS = {
    "encerramento": ("Reason", "Complet", "Discontin", "Terminat", "Deceas",
                     "Death", "Expired", "Closed", "EndDate"),
    "frequência": ("Frequen", "Regimen", "Pattern", "PerWeek", "Interval",
                   "BID", "Schedule"),
    "braquiterapia": ("Brachy", "HDR", "Afterload", "Technique", "Modality",
                      "TreatmentType"),
}


def _secao(titulo: str) -> None:
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}")


def _consultar(cx, sql: str, *params):
    cur = cx.cursor()
    cur.execute(sql, *params)
    return cur.fetchall()


def _colunas(cx, tabela: str) -> None:
    """Todas as colunas, sem filtro — filtrar é o que perde a de nome estranho."""
    print(f"\n--- {tabela} ---")
    try:
        cols = colunas_de(cx, tabela)
    except Exception as exc:  # noqa: BLE001
        print(f"  (não consegui ler: {str(exc)[:110]})")
        return
    if not cols:
        print("  (não existe neste banco)")
        return
    for nome, tipo, tam, nulo in cols:
        print(f"  {nome:46} {tipo}({tam}){'' if nulo else '  NOT NULL'}")


def _procurar_colunas(cx, termos) -> None:
    for termo in termos:
        try:
            achados = _consultar(cx, (
                "SELECT TOP 25 s.name + '.' + o.name, c.name "
                "FROM sys.columns c "
                "JOIN sys.objects o ON o.object_id = c.object_id "
                "JOIN sys.schemas s ON s.schema_id = o.schema_id "
                "WHERE o.type = 'U' AND c.name LIKE ? "
                "  AND o.name NOT LIKE 'stg%' AND o.name NOT LIKE '%bkp%' "
                "ORDER BY o.name"), f"%{termo}%")
        except Exception as exc:  # noqa: BLE001
            print(f"\n  {termo}: erro — {str(exc)[:90]}")
            continue
        print(f"\n  coluna ~ {termo}  ({len(achados)}):")
        for tabela, coluna in achados:
            print(f"    {tabela}.{coluna}")
        if not achados:
            print("    (nada)")


def pergunta_encerramento(cx) -> None:
    """1. O motivo de o curso ter parado antes do prescrito.

    A contagem cruzada é a que decide: dos cursos que entregaram MENOS frações
    que as planejadas, quantos estão em cada ``ClinicalStatus``. Se todos caem
    em "Completed" ou num estado só, o status não separa alta de abandono e o
    motivo tem de estar em outro lugar (ou não existe — e aí o PRD precisa de
    "encerramento sem motivo", não de abandono).
    """
    _secao("1. MOTIVO DE ENCERRAMENTO DO CURSO")
    _colunas(cx, "DWH.DimCourse")

    print("\n  Cursos por ClinicalStatus (todos):")
    try:
        for estado, n in _consultar(cx, """
SELECT COALESCE(lc.LookupDescriptionENU, '(sem estado)'), COUNT(*)
  FROM DWH.DimCourse c
  LEFT JOIN DWH.DimLookup lc ON lc.DimLookupID = c.DimLookupID_ClinicalStatus
 GROUP BY lc.LookupDescriptionENU
 ORDER BY COUNT(*) DESC"""):
            print(f"    {n:>8}  {estado}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")

    # A linha-resumo do curso é a de FractionNumber = 0 (ver NOTAS, servidor
    # local de 29/09/2026): é ela que traz planejadas × entregues do CURSO.
    print("\n  Cursos dos últimos 18 meses que entregaram MENOS que o planejado,")
    print("  por ClinicalStatus (é isto que diz se o status separa alta de abandono):")
    try:
        for estado, n, faltando in _consultar(cx, """
SELECT COALESCE(lc.LookupDescriptionENU, '(sem estado)'),
       COUNT(*),
       AVG(CAST(th.FractionsPlanned - th.FractionsDelivered AS float))
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimCourse c ON c.DimCourseID = th.DimCourseID
  LEFT JOIN DWH.DimLookup lc ON lc.DimLookupID = c.DimLookupID_ClinicalStatus
 WHERE th.FractionNumber = 0
   AND th.FractionsDelivered < th.FractionsPlanned
   AND th.LastTreatmentDate >= DATEADD(month, -18, GETDATE())
 GROUP BY lc.LookupDescriptionENU
 ORDER BY COUNT(*) DESC"""):
            print(f"    {n:>8}  {estado:<30} faltavam em média {faltando or 0:.1f} fração(ões)")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")

    print("\n  Colunas com cara de motivo / óbito / encerramento, no banco todo:")
    _procurar_colunas(cx, TERMOS["encerramento"])


def pergunta_frequencia(cx) -> None:
    """2. A frequência prescrita (diário, alternado, 2x/semana, semanal).

    Duas frentes, porque uma pode não existir: o campo na prescrição, e o
    padrão REAL das pausas entre frações. Se o campo não existir, o histograma
    é o que mostra se dá para inferir a frequência pelo próprio tratamento —
    um curso cuja pausa típica é 7 dias é semanal, diga o campo o que disser.
    """
    _secao("2. FREQUÊNCIA PRESCRITA")
    _colunas(cx, "DWH.DimPrescription")
    _colunas(cx, "DWH.DimPrescriptionProperty")

    print("\n  PropertyType da prescrição: quantos valores distintos cada um tem")
    print(f"  (só os com até {_MAX_DISTINTOS_AMOSTRA} valores são amostrados — o resto é texto livre):")
    try:
        tipos = _consultar(cx, """
SELECT pp.PropertyType, COUNT(*), COUNT(DISTINCT pp.PropertyValue)
  FROM DWH.DimPrescriptionProperty pp
 GROUP BY pp.PropertyType
 ORDER BY pp.PropertyType""")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:170]}")
        tipos = []
    for tipo, linhas, distintos in tipos:
        print(f"\n    PropertyType {tipo}: {linhas} linha(s), {distintos} valor(es) distinto(s)")
        if distintos > _MAX_DISTINTOS_AMOSTRA:
            print("      (não amostrado: texto livre)")
            continue
        try:
            for valor, n in _consultar(cx, """
SELECT TOP 15 pp.PropertyValue, COUNT(*)
  FROM DWH.DimPrescriptionProperty pp
 WHERE pp.PropertyType = ?
 GROUP BY pp.PropertyValue
 ORDER BY COUNT(*) DESC""", tipo):
                print(f"      {n:>7}  {str(valor)[:60]}")
        except Exception as exc:  # noqa: BLE001
            print(f"      falhou: {str(exc)[:120]}")

    print("\n  Colunas com cara de frequência / regime, no banco todo:")
    _procurar_colunas(cx, TERMOS["frequência"])

    # Um dia de tratamento por curso (DISTINCT na data): o histórico pode ter
    # mais de uma linha por sessão, e contar linhas faria a pausa "zero" dominar
    # o histograma.
    print("\n  Pausas REAIS entre dias de tratamento consecutivos do mesmo curso,")
    print("  últimos 6 meses (dias corridos):")
    try:
        for faixa, n in _consultar(cx, """
WITH dias AS (
    SELECT DISTINCT th.DimCourseID, CAST(th.TreatmentStartTime AS date) AS dia
      FROM DWH.FactTreatmentHistory th
     WHERE th.FractionNumber > 0
       AND th.TreatmentStartTime >= DATEADD(month, -6, GETDATE())
), pausas AS (
    SELECT DATEDIFF(day, LAG(dia) OVER (PARTITION BY DimCourseID ORDER BY dia), dia) AS p
      FROM dias
)
SELECT CASE WHEN p <= 7 THEN RIGHT('0' + CAST(p AS varchar(2)), 2) + ' dia(s)'
            WHEN p <= 14 THEN '08-14 dias'
            ELSE '15+ dias' END AS faixa,
       COUNT(*)
  FROM pausas
 WHERE p IS NOT NULL
 GROUP BY CASE WHEN p <= 7 THEN RIGHT('0' + CAST(p AS varchar(2)), 2) + ' dia(s)'
               WHEN p <= 14 THEN '08-14 dias'
               ELSE '15+ dias' END
 ORDER BY faixa"""):
            print(f"    {faixa:<12} {n:>8}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:200]}")

    print("\n  Cursos dos últimos 6 meses pela pausa MEDIANA (≥ 6 dias sugere regime semanal):")
    try:
        for faixa, n in _consultar(cx, """
WITH dias AS (
    SELECT DISTINCT th.DimCourseID, CAST(th.TreatmentStartTime AS date) AS dia
      FROM DWH.FactTreatmentHistory th
     WHERE th.FractionNumber > 0
       AND th.TreatmentStartTime >= DATEADD(month, -6, GETDATE())
), pausas AS (
    SELECT DimCourseID,
           DATEDIFF(day, LAG(dia) OVER (PARTITION BY DimCourseID ORDER BY dia), dia) AS p
      FROM dias
), medianas AS (
    SELECT DISTINCT DimCourseID,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p)
               OVER (PARTITION BY DimCourseID) AS med
      FROM pausas
     WHERE p IS NOT NULL
)
SELECT CASE WHEN med < 2 THEN 'diário (<2)'
            WHEN med < 4 THEN 'alternado / 2-3x semana (2-4)'
            WHEN med < 6 THEN '4-6 dias'
            ELSE 'semanal ou mais espaçado (6+)' END,
       COUNT(*)
  FROM medianas
 GROUP BY CASE WHEN med < 2 THEN 'diário (<2)'
               WHEN med < 4 THEN 'alternado / 2-3x semana (2-4)'
               WHEN med < 6 THEN '4-6 dias'
               ELSE 'semanal ou mais espaçado (6+)' END
 ORDER BY COUNT(*) DESC"""):
            print(f"    {n:>7}  {faixa}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:200]}")


def pergunta_atividades(cx) -> None:
    """3. A TC de simulação e a consulta, como atividades do ARIA.

    Lista os códigos com quantas vezes apareceram no último ano, filtrando por
    palavra — e também as 40 mais frequentes sem filtro, porque o serviço pode
    chamar a simulação de um nome que nenhuma palavra daqui pega.
    """
    _secao("3. SIMULAÇÃO E CONSULTA COMO ATIVIDADES")
    termos = ("%SIMUL%", "%TOMOG%", "%TC %", "% TC%", "%CT %", "%CONSULT%",
              "%PLANEJ%", "%PRIMEIRA%", "%INICIO%", "%REVIS%")
    print("\n  Atividades do último ano cujo código ou nome contém um destes termos:")
    print(f"  {', '.join(t.strip('%') for t in termos)}")
    filtro = " OR ".join(["a.ActivityCode LIKE ? OR a.ActivityNamePTB LIKE ?"] * len(termos))
    params = [t for t in termos for _ in (0, 1)]
    try:
        for codigo, nome, n in _consultar(cx, f"""
SELECT a.ActivityCode, a.ActivityNamePTB, COUNT(*)
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
 WHERE t.AppointmentDateTime >= DATEADD(year, -1, GETDATE())
   AND ({filtro})
 GROUP BY a.ActivityCode, a.ActivityNamePTB
 ORDER BY COUNT(*) DESC""", *params):
            print(f"    {n:>7}  {str(codigo)[:30]:<32} {nome}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:200]}")

    print("\n  As 40 atividades mais frequentes do último ano, sem filtro:")
    try:
        for codigo, nome, n in _consultar(cx, """
SELECT TOP 40 a.ActivityCode, a.ActivityNamePTB, COUNT(*)
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
 WHERE t.AppointmentDateTime >= DATEADD(year, -1, GETDATE())
 GROUP BY a.ActivityCode, a.ActivityNamePTB
 ORDER BY COUNT(*) DESC"""):
            print(f"    {n:>7}  {str(codigo)[:30]:<32} {nome}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:200]}")


def pergunta_braquiterapia(cx) -> None:
    """4. A braquiterapia está no ARIA?

    As máquinas com tratamento entregue no último ano dizem quase tudo: se um
    afterloader (HDR) aparece com sessões, a braquiterapia está no banco. O
    cruzamento com CID C53 (colo do útero) diz se ESSES cursos chegam nele.
    """
    _secao("4. BRAQUITERAPIA NO ARIA")
    print("\n  Máquinas com fração entregue no último ano (dias de tratamento):")
    try:
        for mid, nome, n in _consultar(cx, """
SELECT m.MachineId, m.MachineFullName, COUNT(DISTINCT CONCAT(th.DimCourseID, '|', CAST(th.TreatmentStartTime AS date)))
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimMachine m ON m.DimMachineID = th.DimActualMachineID
 WHERE th.FractionNumber > 0
   AND th.TreatmentStartTime >= DATEADD(year, -1, GETDATE())
 GROUP BY m.MachineId, m.MachineFullName
 ORDER BY COUNT(*) DESC"""):
            print(f"    {n:>7}  {str(mid)[:24]:<26} {nome}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:200]}")

    print("\n  Cursos com diagnóstico C53 (colo do útero), último ano, por máquina:")
    try:
        for nome, n in _consultar(cx, """
SELECT m.MachineFullName, COUNT(DISTINCT th.DimCourseID)
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimMachine m ON m.DimMachineID = th.DimActualMachineID
  JOIN DWH.FactPatientDiagnosis fd ON fd.DimPatientID = th.DimPatientID
  JOIN DWH.DimDiagnosisCode dc ON dc.DimDiagnosisCodeID = fd.DimDiagnosisCodeID
 WHERE th.FractionNumber > 0
   AND th.TreatmentStartTime >= DATEADD(year, -1, GETDATE())
   AND dc.DiagnosisCode LIKE 'C53%'
 GROUP BY m.MachineFullName
 ORDER BY COUNT(DISTINCT th.DimCourseID) DESC"""):
            print(f"    {n:>7} curso(s)  {nome}")
    except Exception as exc:  # noqa: BLE001
        print(f"    falhou: {str(exc)[:200]}")

    print("\n  Colunas com cara de técnica / braquiterapia, no banco todo:")
    _procurar_colunas(cx, TERMOS["braquiterapia"])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--servidor", default=SERVIDOR_PADRAO)
    p.add_argument("--banco", default=BANCO_PADRAO)
    p.add_argument("--porta", type=int, default=PORTA_PADRAO)
    args = p.parse_args(argv)

    passo_identidade()
    pyodbc = passo_pyodbc()
    if pyodbc is None:
        return 1
    driver = passo_drivers(pyodbc)
    if not driver:
        return 1
    # A REDE antes do login, como nos outros mapeadores: "SQL Server inexistente
    # ou acesso negado" mistura VPN caída com permissão e manda olhar o errado.
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
                  r'"C:\...\isocentro\tools\mapear_indicadores.bat"')
        return 1
    try:
        # Cada pergunta isolada: uma que falhe (tabela que não existe nesta
        # versão do ARIA) não pode levar as outras junto — meio relatório vale
        # mais que nenhum, e diz o que refazer.
        for pergunta in (pergunta_encerramento, pergunta_frequencia,
                         pergunta_atividades, pergunta_braquiterapia):
            try:
                pergunta(cx)
            except Exception as exc:  # noqa: BLE001
                print(f"\n  ({pergunta.__name__} parou: {str(exc)[:200]})")
    finally:
        cx.close()
    print("\n(nenhuma linha de paciente foi lida: só catálogos e contagens)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
