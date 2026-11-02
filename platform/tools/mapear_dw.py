r"""Mapeia as COLUNAS do data warehouse que a capa precisa.

O diagnóstico (``diagnostico_db.py``) provou que dá para ler o banco e listou os
nomes das tabelas. Isto vai um passo adiante: descobre em qual coluna de qual
tabela mora cada campo que sai impresso na capa.

Existe para eu não escrever ``capa_db.py`` por adivinhação. Nome de coluna
inventado dá erro na hora — o que é bom —, mas coluna PARECIDA com a certa
(``PatientId`` × ``PatientID`` × ``ctrPatientSer``) devolve dado plausível e
errado, e isso vira número errado numa folha grampeada na ficha.

Rodar:
    runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\mapear_dw.bat"

Com um paciente real, para conferir o mapeamento de ponta a ponta:
    ... "C:\...\mapear_dw.bat --paciente 9000001CEL"

Sem ``--paciente``, só metadados: nenhuma linha de paciente é lida. Com ele,
lê-se UM paciente — o suficiente para conferir, e nada além disso.

Nada aqui escreve no banco.
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, __file__.rsplit("tools", 1)[0])

from diagnostico_db import (  # noqa: E402
    BANCO_PADRAO, PORTA_PADRAO, SERVIDOR_PADRAO, _conectar, _quem_sou,
    passo_drivers, passo_identidade, passo_pyodbc)

# As tabelas que interessam à capa, e por quê. A ordem é a da folha impressa.
TABELAS = [
    ("DWH.DimPatient", "nome, registro, nascimento, sexo, contato"),
    ("DWH.DimPatientPhoto", "a foto 3×4 (hoje vem de um MHTML de 190 MB)"),
    ("DWH.DimCourse", "curso"),
    ("DWH.DimPrescription", "prescrição: dose, fracionamento, técnica"),
    ("DWH.FactPatientDiagnosis", "diagnóstico do paciente"),
    ("DWH.DimDiagnosisCode", "CID e a descrição que sai na capa"),
    ("DWH.DimPatientDoctor", "vínculo paciente↔médico"),
    ("DWH.DimDoctor", "nome do médico"),
    ("DWH.DimMachine", "acelerador"),
]

# Convênio no ARIA é "Payor", não "Insurance" — foi o que o inventário mostrou
# (vp_DeleteDuplicatePayors). Estes termos são procurados no banco inteiro.
TERMOS_PROCURA = ["Payor", "Insurance", "Coverage", "Phone", "Telephone",
                  "Contact", "Gender", "Sex", "Birth", "Intent"]


def nota_da_prescricao(cx) -> None:
    """Onde mora a NOTA que o radioterapeuta escreve na prescrição.

    A capa imprime essa nota ao lado do bloco da prescrição (estadiamento,
    "após QT", o que condiciona o tratamento), mas hoje ela só pode ser
    digitada na tela: o relatório CSV não tem essa coluna e o ``capa_db`` não a
    busca. Qual coluna do DW a guarda **não se adivinha** — o esquema não é
    público (procurado em 23/09/2026), e coluna parecida com a certa devolve
    texto plausível e errado numa folha que vai para a sala.

    Três perguntas, nesta ordem: as colunas das três tabelas de prescrição, os
    ``PropertyType`` que existem de fato (a frequência já mora num deles, o
    tipo 7) e, no banco inteiro, toda coluna cujo NOME cheira a nota. Só
    metadados e contagens; nenhum texto de paciente é lido aqui.
    """
    print(f"\n{'=' * 70}\nNota da prescrição — onde ela mora\n{'=' * 70}")
    for tabela in ("DWH.DimPrescription", "DWH.DimPrescriptionAnatomy",
                   "DWH.DimPrescriptionProperty"):
        print(f"\n  {tabela}")
        try:
            cols = colunas_de(cx, tabela)
        except Exception as exc:  # noqa: BLE001
            print(f"    (não consegui ler: {str(exc)[:110]})")
            continue
        if not cols:
            print("    (tabela não encontrada neste banco)")
            continue
        for nome, tipo, tam, _nulo in cols:
            print(f"    {nome:42} {tipo}({tam})")

    # Os tipos de propriedade que existem. A frequência é o 7 (ver
    # ``capa_db._SQL_FREQUENCIA``); a nota, se for propriedade, é outro deles —
    # e é a CONTAGEM que diz qual vale a pena olhar.
    print("\n  DimPrescriptionProperty — PropertyType em uso:")
    try:
        cur = _cur(cx)
        cur.execute("SELECT PropertyType, COUNT(*) "
                    "FROM DWH.DimPrescriptionProperty "
                    "GROUP BY PropertyType ORDER BY PropertyType")
        for tipo, quantas in cur.fetchall():
            print(f"    tipo {str(tipo):>4}  —  {quantas} linhas")
    except Exception as exc:  # noqa: BLE001
        print(f"    (não consegui contar: {str(exc)[:110]})")

    print("\n  Colunas do banco cujo nome cheira a nota:")
    cur = _cur(cx)
    for termo in ("Note", "Comment", "Remark", "Instruction", "Description"):
        try:
            cur.execute(
                "SELECT TOP 12 s.name + '.' + o.name, c.name "
                "FROM sys.columns c "
                "JOIN sys.objects o ON o.object_id = c.object_id "
                "JOIN sys.schemas s ON s.schema_id = o.schema_id "
                "WHERE o.type = 'U' AND c.name LIKE ? "
                "  AND o.name LIKE '%Prescription%' "
                "ORDER BY o.name", f"%{termo}%")
            achados = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            print(f"    {termo}: erro — {str(exc)[:90]}")
            continue
        print(f"    {termo} ({len(achados)}):")
        for tabela, coluna in achados:
            print(f"      {tabela}.{coluna}")
        if not achados:
            print("      (nada)")


def _cur(cx):
    return cx.cursor()


def colunas_de(cx, tabela: str) -> list[tuple]:
    schema, nome = tabela.split(".", 1)
    cur = _cur(cx)
    cur.execute(
        "SELECT c.name, t.name, c.max_length, c.is_nullable "
        "FROM sys.columns c "
        "JOIN sys.types t ON t.user_type_id = c.user_type_id "
        "JOIN sys.objects o ON o.object_id = c.object_id "
        "JOIN sys.schemas s ON s.schema_id = o.schema_id "
        "WHERE s.name = ? AND o.name = ? ORDER BY c.column_id", schema, nome)
    return cur.fetchall()


def mostrar_tabelas(cx) -> None:
    for tabela, porque in TABELAS:
        print(f"\n{'=' * 70}\n{tabela}  —  {porque}\n{'=' * 70}")
        try:
            cols = colunas_de(cx, tabela)
        except Exception as exc:  # noqa: BLE001
            print(f"  (não consegui ler: {str(exc)[:120]})")
            continue
        if not cols:
            print("  (tabela não encontrada neste banco)")
            continue
        for nome, tipo, tam, nulo in cols:
            marca = "" if nulo else "  NOT NULL"
            print(f"  {nome:42} {tipo}({tam}){marca}")
        try:
            cur = _cur(cx)
            cur.execute(f"SELECT COUNT(*) FROM {tabela}")
            print(f"  → {cur.fetchone()[0]} linhas")
        except Exception:  # noqa: BLE001
            pass


def procurar_termos(cx) -> None:
    """Onde estão convênio, contato, sexo, nascimento e intenção.

    Procura por NOME DE COLUNA em todo o banco. É mais confiável que adivinhar
    a tabela: o nome da coluna costuma dizer o que ela é, o da tabela nem
    sempre.
    """
    print(f"\n{'=' * 70}\nProcura por nome de coluna (convênio, contato, sexo…)"
          f"\n{'=' * 70}")
    cur = _cur(cx)
    for termo in TERMOS_PROCURA:
        try:
            cur.execute(
                "SELECT TOP 12 s.name + '.' + o.name, c.name "
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


def amostra_do_paciente(cx, registro: str) -> None:
    """Um paciente de verdade, para conferir o mapeamento de ponta a ponta.

    UM. O objetivo é validar em qual coluna está cada campo — para isso basta
    uma linha, e ler mais que isso seria despejar dado de paciente numa saída
    de diagnóstico sem necessidade.
    """
    print(f"\n{'=' * 70}\nPaciente {registro} — conferência do mapeamento"
          f"\n{'=' * 70}")
    cur = _cur(cx)
    try:
        cur.execute("SELECT TOP 1 * FROM DWH.DimPatient WHERE PatientId = ?",
                    registro)
        linha = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        print(f"  Falhou: {str(exc)[:160]}")
        return
    if linha is None:
        print("  Não achei esse registro em DimPatient.")
        return
    for coluna, valor in zip([d[0] for d in cur.description], linha):
        texto = str(valor)
        if len(texto) > 60:
            texto = texto[:57] + "…"
        # Coluna vazia não ensina nada sobre onde o dado mora.
        if texto and texto not in ("None", "NA", ""):
            print(f"  {coluna:42} {texto}")

    print("\n  --- foto ---")
    try:
        cur.execute(
            "SELECT TOP 1 * FROM DWH.DimPatientPhoto ph "
            "JOIN DWH.DimPatient p ON p.DimPatientID = ph.DimPatientID "
            "WHERE p.PatientId = ?", registro)
        foto = cur.fetchone()
        if foto is None:
            print("  (sem foto para este paciente)")
        else:
            for coluna, valor in zip([d[0] for d in cur.description], foto):
                tamanho = (f"<{len(valor)} bytes>" if isinstance(valor, (bytes, bytearray))
                           else str(valor)[:60])
                print(f"  {coluna:42} {tamanho}")
    except Exception as exc:  # noqa: BLE001
        print(f"  Falhou: {str(exc)[:160]}")


def _tabelas_como(cx, padrao: str) -> list[str]:
    cur = _cur(cx)
    cur.execute(
        "SELECT s.name + '.' + o.name FROM sys.objects o "
        "JOIN sys.schemas s ON s.schema_id = o.schema_id "
        "WHERE o.type = 'U' AND o.name LIKE ? ORDER BY o.name", padrao)
    return [r[0] for r in cur.fetchall()]


def fechar_lacunas(cx, registro: str = "") -> None:
    """Sexo, intenção e convênio — os três que não estão em texto na tabela.

    Sexo e intenção são ``DimLookupID_*``: ponteiros para uma tabela de
    domínio. Convênio mora em ``DimPayor``, ligado ao paciente por um fato.
    Sem resolver os três, a capa sairia com número de série no lugar de
    "Feminino", "Paliativa" e "Unimed".
    """
    print(f"\n{'=' * 70}\nAs três lacunas: sexo, intenção e convênio\n{'=' * 70}")

    print("\n--- a tabela de domínio (DimLookup*) ---")
    lookups = _tabelas_como(cx, "DimLookup%")
    for t in lookups:
        print(f"  {t}")
    if lookups:
        for nome, tipo, tam, _ in colunas_de(cx, lookups[0]):
            print(f"      {nome:38} {tipo}({tam})")

    print("\n--- FactPatient (onde mora o sexo) ---")
    try:
        for nome, tipo, tam, _ in colunas_de(cx, "DWH.FactPatient"):
            if "Lookup" in nome or "DimPatient" in nome or "Gender" in nome:
                print(f"  {nome:40} {tipo}({tam})")
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:120]}")

    # O teste de verdade: os VALORES. Se vierem "Female"/"Male", a tradução
    # para "Feminino"/"Masculino" é do app; se vierem em português, melhor.
    print("\n--- valores distintos de sexo ---")
    for tentativa in (
        "SELECT TOP 10 l.*, COUNT(*) OVER (PARTITION BY l.DimLookupID) "
        "FROM DWH.FactPatient f JOIN DWH.DimLookup l "
        "  ON l.DimLookupID = f.DimLookupID_Gender",
        "SELECT DISTINCT TOP 10 l.* FROM DWH.FactPatient f "
        "JOIN DWH.DimLookup l ON l.DimLookupID = f.DimLookupID_Gender",
    ):
        try:
            cur = _cur(cx)
            cur.execute(tentativa)
            cols = [d[0] for d in cur.description]
            for linha in cur.fetchall():
                print("  " + " | ".join(f"{c}={v}" for c, v in zip(cols, linha)
                                        if v not in (None, "")))
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  (tentativa falhou: {str(exc)[:110]})")

    print("\n--- valores distintos de intenção (curso) ---")
    try:
        cur = _cur(cx)
        cur.execute("SELECT DISTINCT TOP 10 l.* FROM DWH.DimCourse c "
                    "JOIN DWH.DimLookup l "
                    "  ON l.DimLookupID = c.DimLookupID_TreatmentIntentType")
        cols = [d[0] for d in cur.description]
        for linha in cur.fetchall():
            print("  " + " | ".join(f"{c}={v}" for c, v in zip(cols, linha)
                                    if v not in (None, "")))
    except Exception as exc:  # noqa: BLE001
        print(f"  falhou: {str(exc)[:140]}")

    print("\n--- máquina: por onde ela chega ao paciente ---")
    # O CSV trazia "TBuniverSN1002" por paciente; no banco a máquina está a
    # alguns saltos de distância (curso → plano → tratamento). Adivinhar o
    # caminho foi o que já me custou o join do médico — melhor perguntar.
    for tabela in ("DWH.DimMachine", "DWH.DimPlan", "DWH.FactTreatmentHistory"):
        try:
            cols = colunas_de(cx, tabela)
            print(f"  {tabela}  ({len(cols)} colunas):")
            for nome, tipo, tam, _ in cols:
                if ("Machine" in nome or "DimPatientID" in nome
                        or "DimCourseID" in nome or "DimPlanID" in nome
                        or nome.endswith("Id") or nome.endswith("Name")
                        or "Date" in nome):
                    print(f"      {nome:40} {tipo}({tam})")
        except Exception as exc:  # noqa: BLE001
            print(f"  {tabela}: {str(exc)[:110]}")

    if registro:
        print(f"\n  máquinas de {registro}:")
        for rotulo, sql in (
            ("FactTreatmentHistory",
             "SELECT TOP 5 m.* FROM DWH.DimPatient p "
             "JOIN DWH.FactTreatmentHistory th ON th.DimPatientID = p.DimPatientID "
             "JOIN DWH.DimMachine m "
             "  ON m.DimMachineID = th.DimMachineID_PlanMachine "
             "WHERE p.PatientId = ?"),
            ("DimPlan",
             "SELECT TOP 5 m.* FROM DWH.DimPatient p "
             "JOIN DWH.DimCourse c ON c.DimPatientID = p.DimPatientID "
             "JOIN DWH.DimPlan pl ON pl.DimCourseID = c.DimCourseID "
             "JOIN DWH.DimMachine m ON m.DimMachineID = pl.DimMachineID "
             "WHERE p.PatientId = ?"),
        ):
            try:
                cur = _cur(cx)
                cur.execute(sql, registro)
                cols = [d[0] for d in cur.description]
                linhas = cur.fetchall()
                if not linhas:
                    print(f"    [{rotulo}] (nada)")
                for linha in linhas[:2]:
                    partes = [f"{c}={str(v)[:32]}" for c, v in zip(cols, linha)
                              if v not in (None, "", "NA")]
                    print(f"    [{rotulo}] " + " | ".join(partes[:8]))
            except Exception as exc:  # noqa: BLE001
                print(f"    [{rotulo}] falhou: {str(exc)[:130]}")

    print("\n--- convênio: FactPatientPayor + DimPayor ---")
    for tabela in ("DWH.FactPatientPayor", "DWH.DimPayor"):
        try:
            print(f"  {tabela}:")
            for nome, tipo, tam, _ in colunas_de(cx, tabela):
                print(f"      {nome:38} {tipo}({tam})")
        except Exception as exc:  # noqa: BLE001
            print(f"      falhou: {str(exc)[:110]}")

    if not registro:
        return
    print(f"\n--- os três valores para {registro} ---")
    consultas = [
        ("sexo",
         "SELECT TOP 1 l.* FROM DWH.DimPatient p "
         "JOIN DWH.FactPatient f ON f.DimPatientID = p.DimPatientID "
         "JOIN DWH.DimLookup l ON l.DimLookupID = f.DimLookupID_Gender "
         "WHERE p.PatientId = ?"),
        ("curso/intenção",
         "SELECT TOP 5 c.CourseId, l.* FROM DWH.DimPatient p "
         "JOIN DWH.DimCourse c ON c.DimPatientID = p.DimPatientID "
         "LEFT JOIN DWH.DimLookup l "
         "  ON l.DimLookupID = c.DimLookupID_TreatmentIntentType "
         "WHERE p.PatientId = ?"),
        ("convênio",
         "SELECT TOP 3 py.PayorCompanyName, py.PayorPlanNumber, "
         "       py.PayorPlanType FROM DWH.DimPatient p "
         "JOIN DWH.FactPatientPayor fp ON fp.DimPatientID = p.DimPatientID "
         "JOIN DWH.DimPayor py ON py.DimPayorID = fp.DimPayorID "
         "WHERE p.PatientId = ?"),
        ("CID e diagnóstico",
         "SELECT TOP 3 dc.*, fd.DiagnosisDescription FROM DWH.DimPatient p "
         "JOIN DWH.FactPatientDiagnosis fd ON fd.DimPatientID = p.DimPatientID "
         "JOIN DWH.DimDiagnosisCode dc "
         "  ON dc.DimDiagnosisCodeID = fd.DimDiagnosisCodeID "
         "WHERE p.PatientId = ?"),
        ("médico",
         "SELECT TOP 3 d.* FROM DWH.DimPatient p "
         "JOIN DWH.DimPatientDoctor pd ON pd.DimPatientID = p.DimPatientID "
         "JOIN DWH.DimDoctor d ON d.DimDoctorID = pd.DimDoctorID "
         "WHERE p.PatientId = ?"),
    ]
    for rotulo, sql in consultas:
        print(f"\n  [{rotulo}]")
        try:
            cur = _cur(cx)
            cur.execute(sql, registro)
            cols = [d[0] for d in cur.description]
            linhas = cur.fetchall()
            if not linhas:
                print("    (nada)")
            for linha in linhas:
                partes = [f"{c}={str(v)[:44]}" for c, v in zip(cols, linha)
                          if v not in (None, "", "NA")]
                print("    " + " | ".join(partes))
        except Exception as exc:  # noqa: BLE001
            print(f"    falhou: {str(exc)[:190]}")


def _colunas_texto(cx, tabela: str) -> list[str]:
    return [c[0] for c in colunas_de(cx, tabela)
            if str(c[1]).lower() in ("nvarchar", "varchar", "nchar", "char")
            or "STRING" in str(c[1]).upper()]


def passo_acentos(cx, pyodbc) -> None:
    """O driver antigo devolve acento correto? MEDIR, não supor.

    O ODBC Driver 18 não vai ser instalado, então a pergunta deixa de ser
    "qual driver pedir" e passa a ser "o driver que existe entrega o texto
    certo?". Há três desfechos, e só um deles justifica tirar acento:

    * vem certo → nada a fazer, e a capa continua imprimindo "encéfalo";
    * vem torto mas conserta com ``setdecoding`` → configuração, não perda;
    * vem realmente truncado/perdido → aí sim se discute normalizar.

    Tirar acento de "Neoplasia maligna do encéfalo" num documento que vai para
    a sala é degradação de verdade. Só se aceita provando que não há saída.
    """
    print(f"\n{'=' * 70}\nAcentuação com o driver instalado\n{'=' * 70}")
    # Onde há texto em português neste banco: a descrição do diagnóstico é a
    # que sai impressa na capa, então é a que importa.
    alvos = [("DWH.DimDiagnosisCode", None),
             ("DWH.FactPatientDiagnosis", "DiagnosisDescription"),
             ("DWH.DimPatient", "PatientFullName")]

    achou_texto = False
    for tabela, coluna in alvos:
        try:
            colunas = [coluna] if coluna else _colunas_texto(cx, tabela)
        except Exception as exc:  # noqa: BLE001
            print(f"  {tabela}: {str(exc)[:100]}")
            continue
        for col in colunas[:6]:
            try:
                cur = _cur(cx)
                # Collation do SQL costuma ser acento-insensível: comparar com
                # os caracteres crus acharia qualquer coisa. O COLLATE força a
                # comparação a enxergar o acento.
                cur.execute(
                    f"SELECT TOP 3 {col} FROM {tabela} "
                    f"WHERE {col} COLLATE Latin1_General_BIN LIKE "
                    f"'%[áéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]%'")
                linhas = [r[0] for r in cur.fetchall() if r[0]]
            except Exception:  # noqa: BLE001
                continue
            if not linhas:
                continue
            achou_texto = True
            print(f"\n  {tabela}.{col}")
            for valor in linhas:
                # repr() de propósito: mojibake ("encÃ©falo") e perda real
                # ("encfalo") são indistinguíveis a olho na saída bonita.
                print(f"    {valor}")
                print(f"      repr: {valor!r}")
            break
        if achou_texto:
            break

    if not achou_texto:
        print("  Não achei texto acentuado para testar. Pode ser que este banco")
        print("  guarde as descrições em inglês — nesse caso o problema de")
        print("  acentuação não existe, e não há o que adaptar.")
        return

    # A correção padrão para driver legado: dizer ao pyodbc como decodificar.
    print("\n  --- e com setdecoding(SQL_WCHAR, utf-16le)? ---")
    try:
        cx.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        cx.setdecoding(pyodbc.SQL_CHAR, encoding="latin-1")
        cur = _cur(cx)
        cur.execute(
            "SELECT TOP 3 DiagnosisDescription FROM DWH.FactPatientDiagnosis "
            "WHERE DiagnosisDescription COLLATE Latin1_General_BIN LIKE "
            "'%[áéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]%'")
        for (valor,) in cur.fetchall():
            print(f"    {valor!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"    não deu para testar: {str(exc)[:150]}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--servidor", default=SERVIDOR_PADRAO)
    p.add_argument("--banco", default=BANCO_PADRAO)
    p.add_argument("--porta", type=int, default=PORTA_PADRAO)
    p.add_argument("--paciente", default="",
                   help="registro de UM paciente, para conferir o mapeamento")
    args = p.parse_args(argv)

    # QUEM está rodando, sempre e primeiro: sem isto, do lado de cá não há
    # como distinguir 'sem runas' de 'sem permissão'.
    passo_identidade()
    pyodbc = passo_pyodbc()
    if pyodbc is None:
        return 1
    driver = passo_drivers(pyodbc)
    if not driver:
        return 1
    try:
        cx = _conectar(pyodbc, driver, args.servidor, args.banco, args.porta)
    except Exception as exc:  # noqa: BLE001
        texto = str(exc)
        print(f"\nNão conectei: {texto[:250]}")
        if "untrusted domain" in texto or "18452" in texto:
            print()
            print("  Isto é IDENTIDADE, não permissão: o servidor foi alcançado")
            print(f"  e viu um usuário local ({_quem_sou()}), não o de rede.")
            print("  Esta execução saiu SEM o runas /netonly — ou a senha")
            print("  digitada nele não foi aceita. O comando INTEIRO, com o")
            print("  caminho e os argumentos dentro das mesmas aspas:")
            print()
            print(r'    runas /netonly /user:CLINICA\geovani.pena '
                  r'"C:\...\isocentro\tools\mapear_dw.bat --paciente 9000001CEL"')
        else:
            print("Rode antes o diagnostico_db.py — ele separa rede, identidade "
                  "e permissão.")
        return 1
    try:
        mostrar_tabelas(cx)
        procurar_termos(cx)
        nota_da_prescricao(cx)
        fechar_lacunas(cx, args.paciente.strip())
        passo_acentos(cx, pyodbc)
        if args.paciente:
            amostra_do_paciente(cx, args.paciente.strip())
        else:
            print("\n(sem --paciente: nenhuma linha de paciente foi lida)")
    finally:
        cx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
