r"""Diagnóstico da conexão com o data warehouse da Varian (``variandw``).

Hoje a capa é alimentada por três relatórios exportados por um agendador. Quando
o agendador falha, a capa nasce vazia e ninguém sabe em qual degrau parou. Ler o
banco direto tira o agendador do caminho — mas antes disso é preciso saber se a
estação **consegue** chegar lá, e é para isso que este arquivo existe.

Rodar (com o usuário de REDE que vai usar o app):

    python tools/diagnostico_db.py

De uma máquina FORA do domínio, a autenticação integrada falha em SSPI antes de
tocar em permissão — a estação não consegue provar quem é. Nesse caso, emprestar
a identidade de rede só para a conexão (pede a senha no console; ela não passa
por lugar nenhum além do Windows):

    runas /netonly /user:CLINICA\geovani.pena "python tools/diagnostico_db.py"

Conferido em 18/08/2026: SRVINSIGHT resolve para 192.0.2.3 e a porta 1433
responde. Se um dia o nome não resolver, ``--servidor 192.0.2.3``.

Cada degrau responde SIM ou NÃO e, no NÃO, diz o que fazer. É o oposto de
"não funciona": sem separar driver de rede, de autenticação e de permissão,
a conversa com a TI vira adivinhação de três dias.

Nada aqui escreve no banco. O acesso pedido é de LEITURA, e este arquivo não
pode ser a exceção que justifica pedir mais do que isso.
"""
from __future__ import annotations

import argparse
import getpass
import os
import socket
import sys

# O servidor do Report Server que publica os relatórios de hoje
# (ver criar_shared_dataset.ps1). O SQL costuma ser a mesma máquina; quando não
# for, passar --servidor.
SERVIDOR_PADRAO = "SRVINSIGHT"
BANCO_PADRAO = "variandw"
PORTA_PADRAO = 1433

# Objetos que as consultas de hoje usam — tirados dos RDL e de
# consulta_prescricoes.sql. Se o login enxerga estes, enxerga o que o app
# precisa; se enxerga o banco mas não estes, a permissão veio pela metade.
OBJETOS = [
    "DWH.vp_PrescriptionModel",
    "DWH.DimPatient",
    "DWH.DimPrescription",
    "DWH.DimCourse",
    "DWH.FactPatientPrescription",
    "DWH.DimPrescriptionAnatomy",
    "DWH.DimPrescriptionProperty",
]

# Preferência de driver. O "SQL Server" cru é o que vem com o Windows desde os
# anos 2000: conecta, mas é depreciado, tropeça em TLS novo e não fala UTF-8 —
# e todo diagnóstico daqui tem acento ("Neoplasia maligna do encéfalo").
DRIVERS_BONS = ("ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server",
                "SQL Server Native Client 11.0")

_OK, _FALHA, _AVISO = "  [ OK ]", "  [FALHA]", "  [AVISO]"


def _titulo(n, texto: str) -> None:
    print(f"\n{n}. {texto}")


def _dizer(marca: str, texto: str) -> None:
    print(f"{marca} {texto}")


def _quem_sou() -> str:
    dominio = os.environ.get("USERDOMAIN", "")
    try:
        usuario = getpass.getuser()
    except Exception:  # noqa: BLE001
        usuario = os.environ.get("USERNAME", "?")
    return f"{dominio}\\{usuario}" if dominio else usuario


def passo_identidade() -> None:
    _titulo(1, "Quem está rodando")
    _dizer(_OK, f"Usuário do Windows: {_quem_sou()}")
    print("         É esta identidade que o SQL vai receber — a autenticação é")
    print("         integrada, não há senha em lugar nenhum.")


def passo_pyodbc():
    """Devolve o módulo pyodbc, ou None."""
    _titulo(2, "Biblioteca de acesso (pyodbc)")
    try:
        import pyodbc
    except ImportError:
        _dizer(_FALHA, "pyodbc não está instalado neste Python.")
        print("         Instale com:  pip install pyodbc")
        print("         (ainda não entrou no requirements.txt: entra junto com")
        print("          o módulo de leitura, quando o acesso existir)")
        return None
    _dizer(_OK, f"pyodbc {pyodbc.version}")
    return pyodbc


def passo_drivers(pyodbc) -> str:
    """Melhor driver disponível ("" se nenhum servir)."""
    _titulo(3, "Driver ODBC instalado na estação")
    instalados = [d for d in pyodbc.drivers() if "SQL Server" in d]
    if not instalados:
        _dizer(_FALHA, "Nenhum driver de SQL Server instalado.")
        print("         Peça à TI: ODBC Driver 18 for SQL Server (download da")
        print("         Microsoft, instalação de máquina).")
        return ""
    for d in instalados:
        print(f"         · {d}")
    for preferido in DRIVERS_BONS:
        if preferido in instalados:
            _dizer(_OK, f"Vou usar: {preferido}")
            return preferido
    _dizer(_AVISO, f"Só há o driver antigo ({instalados[0]}).")
    print("         Conecta, mas é depreciado e erra acentuação. Peça o")
    print("         ODBC Driver 18 for SQL Server no MESMO chamado do acesso —")
    print("         senão vira um segundo chamado depois.")
    return instalados[0]


def passo_rede(servidor: str, porta: int) -> bool:
    _titulo(4, f"O servidor responde ({servidor}:{porta})")
    try:
        with socket.create_connection((servidor, porta), timeout=5):
            pass
    except OSError as exc:
        _dizer(_FALHA, f"Não consegui abrir a porta: {exc}")
        print("         Pode ser nome errado do servidor, instância nomeada")
        print("         (tente --servidor SERVIDOR\\INSTANCIA), porta diferente")
        print("         (--porta) ou firewall. É problema de rede, não de")
        print("         permissão: o login nem chegou a ser testado.")
        return False
    _dizer(_OK, "Porta aberta.")
    return True


def _moderno(driver: str) -> bool:
    """O driver entende os atributos que só existem do Native Client para cá?

    O "SQL Server" cru rejeita ``TrustServerCertificate`` e ``ApplicationIntent``
    com "Atributo de cadeia de conexão inválido" — e esse erro chega MISTURADO
    ao de autenticação, fazendo parecer problema de permissão. Medido nesta
    estação, e foi o que quase me fez ler errado o próprio diagnóstico.
    """
    return driver != "SQL Server"


def _conectar(pyodbc, driver: str, servidor: str, banco: str, porta: int):
    """Conexão de LEITURA, autenticação integrada, com tempo curto.

    ``TrustServerCertificate`` porque o Driver 18 exige criptografia por padrão
    e o certificado destes servidores costuma ser interno — sem isto a conexão
    falha por certificado e o recado engana quem está diagnosticando permissão.
    """
    partes = [
        f"DRIVER={{{driver}}}",
        f"SERVER={servidor},{porta}" if "\\" not in servidor else f"SERVER={servidor}",
        f"DATABASE={banco}",
        "Trusted_Connection=yes",
        "APP=ISOCENTRO (diagnóstico)",
    ]
    if _moderno(driver):
        partes += ["TrustServerCertificate=yes", "ApplicationIntent=ReadOnly"]
    return pyodbc.connect(";".join(partes), timeout=8, readonly=True)


def passo_login(pyodbc, driver: str, servidor: str, banco: str, porta: int):
    _titulo(5, f"Autenticação e acesso ao banco ({banco})")
    try:
        cx = _conectar(pyodbc, driver, servidor, banco, porta)
    except Exception as exc:  # noqa: BLE001 — a mensagem do driver é o diagnóstico
        texto = str(exc)
        _dizer(_FALHA, texto.strip()[:300])
        # Os três desfechos são problemas DIFERENTES, e confundi-los é o que
        # faz a conversa com a TI durar dias. SSPI não é falta de permissão:
        # é a estação não conseguir provar QUEM é.
        if "SSPI" in texto or "Kerberos" in texto:
            print()
            print("         Isto NÃO é falta de permissão — é identidade.")
            print(f"         Esta máquina roda como {_quem_sou()}; para a")
            print("         autenticação integrada funcionar, ela precisa estar")
            print("         no domínio e o usuário ser o de rede. Dois caminhos:")
            print("           · rodar de uma estação do domínio (as da clínica); ou")
            print(r'           · runas /netonly /user:DOMINIO\usuario "python ..."')
            print("         Enquanto for máquina fora do domínio, este teste não")
            print("         diz nada sobre a liberação do chamado.")
        elif "Login failed" in texto:
            print("         O servidor foi alcançado e RECUSOU o usuário: falta")
            print("         a liberação. É exatamente o que o chamado pede.")
        elif "Cannot open database" in texto:
            print("         O login existe, mas não tem acesso a ESTE banco.")
            print(f"         Confirme que a liberação é no '{banco}' (o data")
            print("         warehouse), não só no ARIA clínico (variansystem).")
        return None
    _dizer(_OK, "Conectado.")
    try:
        cur = cx.cursor()
        cur.execute("SELECT SUSER_SNAME(), DB_NAME(), @@VERSION")
        login, db, versao = cur.fetchone()
        print(f"         O servidor me vê como: {login}")
        print(f"         Banco em uso: {db}")
        print(f"         {versao.splitlines()[0].strip()}")
    except Exception as exc:  # noqa: BLE001
        _dizer(_AVISO, f"Conectou, mas não consegui me identificar: {exc}")
    return cx


def _tipos_do_schema(cx) -> dict:
    """``{nome_minusculo: (tipo, descrição)}`` de tudo que existe em DWH.

    Perguntar ao catálogo antes de tentar ler resolve a confusão entre "não
    tenho permissão", "não existe" e "existe, mas não é tabela". Os três dão
    erro parecido no SELECT, e só o catálogo separa.
    """
    fora = {}
    try:
        cur = cx.cursor()
        cur.execute(
            "SELECT o.name, o.type_desc FROM sys.objects o "
            "JOIN sys.schemas s ON s.schema_id = o.schema_id "
            "WHERE s.name = 'DWH'")
        for nome, tipo in cur.fetchall():
            fora[nome.lower()] = tipo
    except Exception:  # noqa: BLE001 — sem catálogo, seguimos pelo SELECT
        pass
    return fora


def passo_objetos(cx) -> list[str]:
    """Quais objetos o login enxerga. Devolve os que faltaram de verdade."""
    _titulo(6, "Os objetos que as consultas usam")
    catalogo = _tipos_do_schema(cx)
    faltando = []
    cur = cx.cursor()
    for obj in OBJETOS:
        curto = obj.split(".", 1)[1].lower()
        tipo = catalogo.get(curto, "")
        # Procedure não se lê com SELECT ... FROM: o erro seria "Invalid object
        # name", idêntico ao de objeto inexistente. Foi assim que eu li errado o
        # vp_PrescriptionModel na primeira rodada.
        if tipo and "PROCEDURE" in tipo:
            _dizer(_OK, f"{obj} — é PROCEDURE (chamada com EXEC, não SELECT)")
            continue
        try:
            cur.execute(f"SELECT TOP 1 1 FROM {obj}")
            cur.fetchall()
            _dizer(_OK, f"{obj}{f' ({tipo})' if tipo else ''}")
        except Exception as exc:  # noqa: BLE001
            faltando.append(obj)
            if not tipo:
                _dizer(_FALHA, f"{obj} — não existe no schema DWH deste banco")
            else:
                _dizer(_FALHA, f"{obj} ({tipo}) — {str(exc).strip()[:120]}")
    if faltando:
        print("\n         Os que dizem 'não existe' são erro de NOME meu, não")
        print("         falta de permissão — veja a lista do passo 6b. Os que")
        print("         trazem mensagem do servidor é que são permissão.")
    return faltando


def passo_inventario(cx) -> None:
    """O que o schema DWH oferece — é daqui que sai o módulo de leitura.

    Sem isto eu escreveria as consultas do app por adivinhação, a partir dos
    nomes que apareciam nos RDL. Melhor perguntar ao banco.
    """
    _titulo("6b", "O que existe no schema DWH (para escrever as consultas)")
    try:
        cur = cx.cursor()
        cur.execute(
            "SELECT o.type_desc, COUNT(*) FROM sys.objects o "
            "JOIN sys.schemas s ON s.schema_id = o.schema_id "
            "WHERE s.name = 'DWH' GROUP BY o.type_desc ORDER BY 2 DESC")
        for tipo, n in cur.fetchall():
            print(f"         {n:5}  {tipo}")
        # Os vp_* são a camada de relatório da Varian: é o que os datasets
        # compartilhados usam, e o caminho mais curto para a capa.
        cur.execute(
            "SELECT TOP 40 o.name, o.type_desc FROM sys.objects o "
            "JOIN sys.schemas s ON s.schema_id = o.schema_id "
            "WHERE s.name = 'DWH' AND o.name LIKE 'vp[_]%' ORDER BY o.name")
        linhas = cur.fetchall()
        print(f"\n         Objetos vp_* ({len(linhas)} primeiros):")
        for nome, tipo in linhas:
            print(f"           DWH.{nome}  [{tipo}]")
        # E o que tem cara de paciente/foto/diagnóstico, que é o que falta
        # para a capa sair completa sem depender do CSV de cadastro.
        cur.execute(
            "SELECT o.name, o.type_desc FROM sys.objects o "
            "JOIN sys.schemas s ON s.schema_id = o.schema_id "
            "WHERE s.name = 'DWH' AND (o.name LIKE '%Photo%' "
            "   OR o.name LIKE '%Diagnos%' OR o.name LIKE '%Insurance%' "
            "   OR o.name LIKE '%Machine%' OR o.name LIKE '%Doctor%' "
            "   OR o.name LIKE '%Physician%') ORDER BY o.name")
        linhas = cur.fetchall()
        print(f"\n         Foto, diagnóstico, convênio, máquina e médico "
              f"({len(linhas)}):")
        for nome, tipo in linhas:
            print(f"           DWH.{nome}  [{tipo}]")
    except Exception as exc:  # noqa: BLE001
        _dizer(_AVISO, f"Não consegui inventariar o schema: {str(exc)[:140]}")


def passo_amostra(cx) -> None:
    """Uma leitura de verdade — inclusive para conferir acentuação."""
    _titulo(7, "Leitura de amostra")
    cur = cx.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM DWH.DimPatient WHERE PatientId <> 'NA'")
        print(f"         Pacientes em DimPatient: {cur.fetchone()[0]}")
    except Exception as exc:  # noqa: BLE001
        _dizer(_AVISO, f"Não consegui contar pacientes: {str(exc)[:120]}")
        return
    try:
        # Acentuação: se o driver/codificação estiver errado, é aqui que
        # aparece — e é o que decide se a capa sai com "encéfalo" ou "encÃ©falo".
        cur.execute("SELECT TOP 3 PatientId, PatientFullName FROM DWH.DimPatient "
                    "WHERE PatientFullName LIKE '%ç%' OR PatientFullName LIKE '%é%'")
        linhas = cur.fetchall()
        if linhas:
            for pid, nome in linhas:
                print(f"         {pid}  {nome}")
            _dizer(_OK, "Acentuação legível acima? Se vier 'Ã', o driver está errado.")
        else:
            _dizer(_AVISO, "Nenhum nome acentuado na amostra — não deu para "
                           "conferir a codificação.")
    except Exception as exc:  # noqa: BLE001
        _dizer(_AVISO, f"Amostra falhou: {str(exc)[:140]}")


def passo_permissoes(cx) -> None:
    """Confere que o acesso é mesmo só de leitura."""
    _titulo(8, "O acesso é somente leitura?")
    try:
        cur = cx.cursor()
        cur.execute("SELECT DISTINCT permission_name "
                    "FROM fn_my_permissions(NULL, 'DATABASE') "
                    "WHERE permission_name IN "
                    "('SELECT','INSERT','UPDATE','DELETE','EXECUTE','ALTER')")
        tem = sorted(p[0] for p in cur.fetchall())
    except Exception as exc:  # noqa: BLE001
        _dizer(_AVISO, f"Não consegui listar permissões: {str(exc)[:120]}")
        return
    print(f"         No banco: {', '.join(tem) or '(nenhuma no nível do banco)'}"),
    escrita = [p for p in tem if p != "SELECT"]
    if escrita:
        _dizer(_AVISO, f"Há permissão de escrita ({', '.join(escrita)}).")
        print("         O app nunca escreve neste banco — é regra do projeto —,")
        print("         mas acesso a mais é risco à toa. Vale pedir só leitura.")
    else:
        _dizer(_OK, "Somente leitura, como pedido.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Diagnóstico da conexão com o data warehouse da Varian.")
    p.add_argument("--servidor", default=SERVIDOR_PADRAO,
                   help=f"host do SQL (padrão: {SERVIDOR_PADRAO}). Para instância "
                        "nomeada: SERVIDOR\\INSTANCIA")
    p.add_argument("--banco", default=BANCO_PADRAO,
                   help=f"banco a consultar (padrão: {BANCO_PADRAO})")
    p.add_argument("--porta", type=int, default=PORTA_PADRAO)
    args = p.parse_args(argv)

    print("=" * 72)
    print("  ISOCENTRO — diagnóstico de acesso ao banco da Varian")
    print(f"  Alvo: {args.servidor}:{args.porta}, banco {args.banco}")
    print("=" * 72)

    passo_identidade()
    pyodbc = passo_pyodbc()
    if pyodbc is None:
        return _fim(False, "instale o pyodbc e rode de novo")
    driver = passo_drivers(pyodbc)
    if not driver:
        return _fim(False, "peça o ODBC Driver 18 for SQL Server à TI")
    if not passo_rede(args.servidor, args.porta):
        return _fim(False, "confirme o nome/porta do servidor com a TI")
    cx = passo_login(pyodbc, driver, args.servidor, args.banco, args.porta)
    if cx is None:
        return _fim(False, "veja o recado do passo 5 — nem toda falha ali é "
                           "falta de liberação")
    try:
        faltando = passo_objetos(cx)
        passo_inventario(cx)
        passo_amostra(cx)
        passo_permissoes(cx)
    finally:
        cx.close()
    if faltando:
        return _fim(False, f"faltam {len(faltando)} objeto(s) — lista acima")
    return _fim(True, "dá para ler o banco desta estação")


def _fim(ok: bool, recado: str) -> int:
    print("\n" + "=" * 72)
    print(("  RESULTADO: " + ("PASSOU — " if ok else "PAROU AQUI — ")) + recado)
    print("=" * 72)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
