"""Servidor LOCAL: o data warehouse SIMULADO, consultado de verdade, sem rede.

É o segundo modo do arquivo apontado por ``ISOCENTRO_BANCO_LOCAL``. O primeiro, o
de sempre (:mod:`banco_local`), REPRODUZ respostas gravadas: casa a pergunta
pelo texto exato do SQL e devolve as linhas que o servidor deu naquele dia. Ele
serve para conferir o app contra dado real, e tem dois limites que o impedem de
servir a uma DEMONSTRAÇÃO fora da rede:

* só responde o que foi gravado — Agenda, atividades, gatilho e resumo do mês
  nunca foram, e qualquer data, máquina ou médico diferente do dia da gravação
  cai em "consulta não gravada";
* mexer num SQL invalida a gravação dele, e o SQL deste projeto muda toda
  semana.

Aqui o arquivo guarda as TABELAS (``DimPatient``, ``FactTreatmentHistory``,
``DimActivityTransaction``…, com os nomes de coluna do DW), e o SQL do app é
EXECUTADO sobre elas. Qualquer consulta, com qualquer parâmetro, responde — e
as respostas batem umas com as outras, porque vêm das mesmas linhas.

**A tradução de T-SQL é pequena de propósito.** O ``banco_local`` recusou esta
ideia por um motivo certo — traduzir SQL é fabricar a resposta plausível e
diferente da do servidor —, e o motivo continua valendo para CONFERIR dado.
Para demonstrar, o risco se inverte: melhor uma tela que funciona com dado
anunciado como simulação do que uma tela vazia. Por isso a tradução cobre só o
que o app usa (medido em 29/09/2026 sobre as 45 consultas): ``TOP n``,
``ISNULL``, ``N'…'``, ``DWH.``, ``CONVERT(char(8), x, 112)``,
``CAST(x AS date)``, ``DATEDIFF``/``DATEADD`` por ano e ``GETDATE()``. Consulta
que usar algo fora disso FALHA (``FalhaDeLeitura``), e o teste
``tests/test_servidor_local.py`` roda todas as consultas do app para isso ser
descoberto na suíte, não na frente de quem assiste.

**Datas viajam como texto** ``AAAA-MM-DD HH:MM:SS`` no SQLite: é o formato que
compara certo por ordem de texto contra os parâmetros ``AAAA-MM-DD`` que o app
manda. Na volta, texto com essa cara vira ``datetime`` — o tipo que o pyodbc
entrega e que o app chama ``.date()``/``strftime`` em cima.
"""
from __future__ import annotations

import datetime
import logging
import re
import sqlite3
from pathlib import Path
from typing import Optional

_LOG = logging.getLogger(__name__)

# O que o ``sobre.tipo`` diz quando o arquivo é um servidor local, e não uma
# gravação. Sem a chave, o arquivo é tratado como gravação — o formato antigo
# continua valendo sem ninguém mexer nele.
TIPO = "servidor_local"

# Mudou o esquema das tabelas, o arquivo velho é RECUSADO em vez de lido errado.
VERSAO = 1

_FORMATO_DATA_HORA = "%Y-%m-%d %H:%M:%S"
_CARA_DE_DATA_HORA = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d{1,6})?$")


def tipo_do_arquivo(caminho) -> str:
    """``"servidor_local"``, ``"gravacao"`` ou ``""`` (ilegível / não existe).

    Nunca levanta: quem pergunta está decidindo que conexão abrir, e um arquivo
    estragado tem de virar "sem banco local", não um traceback no arranque.
    """
    try:
        alvo = Path(caminho)
        if not alvo.is_file():
            return ""
        cx = sqlite3.connect(f"file:{alvo.as_posix()}?mode=ro", uri=True)
    except (OSError, sqlite3.Error, TypeError):
        return ""
    try:
        linha = cx.execute(
            "SELECT valor FROM sobre WHERE chave = 'tipo'").fetchone()
        return (linha[0] if linha else "") or "gravacao"
    except sqlite3.Error:
        return ""
    finally:
        cx.close()


# ── A tradução ──────────────────────────────────────────────────────────────

def _fechamento(texto: str, abre: int) -> int:
    """Índice do ``)`` que fecha o ``(`` em ``abre``, pulando texto entre aspas."""
    nivel = 0
    i = abre
    em_aspas = False
    while i < len(texto):
        c = texto[i]
        if em_aspas:
            if c == "'":
                em_aspas = False
        elif c == "'":
            em_aspas = True
        elif c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
            if nivel == 0:
                return i
        i += 1
    raise ValueError("parêntese sem fechamento no SQL")


def _argumentos(texto: str) -> list:
    """Divide ``a, f(b, c), 'x,y'`` pelas vírgulas de NÍVEL ZERO."""
    partes, nivel, atual, em_aspas = [], 0, [], False
    for c in texto:
        if em_aspas:
            atual.append(c)
            if c == "'":
                em_aspas = False
            continue
        if c == "'":
            em_aspas = True
        elif c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        elif c == "," and nivel == 0:
            partes.append("".join(atual).strip())
            atual = []
            continue
        atual.append(c)
    partes.append("".join(atual).strip())
    return partes


def _trocar_chamadas(sql: str, nome: str, reescrever) -> str:
    """Troca cada ``NOME(...)`` por ``reescrever(argumentos)``, de dentro pra fora
    não — da ESQUERDA para a direita, reprocessando o resultado, o que cobre o
    caso aninhado (``DATEADD(YEAR, DATEDIFF(YEAR, …), …)``)."""
    padrao = re.compile(rf"\b{nome}\s*\(", re.IGNORECASE)
    inicio = 0
    while True:
        m = padrao.search(sql, inicio)
        if not m:
            return sql
        abre = m.end() - 1
        fecha = _fechamento(sql, abre)
        novo = reescrever(_argumentos(sql[abre + 1:fecha]))
        sql = sql[:m.start()] + novo + sql[fecha + 1:]
        inicio = m.start() + 1


def _convert(args: list) -> str:
    # Só o estilo 112 (AAAAMMDD) é usado pelo app. Outro estilo não vira um
    # palpite: levanta, e o teste que roda todas as consultas acusa.
    if len(args) != 3 or args[2].strip() != "112":
        raise ValueError(f"CONVERT não suportado: {args}")
    return f"strftime('%Y%m%d', {args[1]})"


def _parte_de_data(args: list, nome: str) -> str:
    parte = args[0].strip().upper()
    if parte not in ("YEAR", "YY", "YYYY", "DAY", "DD", "D"):
        raise ValueError(f"{nome} com parte não suportada: {parte}")
    resto = ", ".join(args[1:])
    return f"{nome}('{parte}', {resto})"


_TOP = re.compile(r"^(\s*SELECT\s+(?:DISTINCT\s+)?)TOP\s+(\d+)\s+",
                  re.IGNORECASE)
_CAST_DATE = re.compile(r"\bCAST\s*\(", re.IGNORECASE)


def traduzir(sql: str) -> str:
    """O T-SQL do app no dialeto do SQLite. Ver o docstring do módulo."""
    s = sql
    # ``--`` de comentário fica: o SQLite o entende igual. Mas um comentário
    # com aspas ou parênteses desalinharia o ``_fechamento``, então sai antes.
    s = "\n".join(re.sub(r"--[^\n]*", "", linha) for linha in s.splitlines())
    s = re.sub(r"\bDWH\.", "", s)
    s = re.sub(r"(?<![A-Za-z0-9_'])N'", "'", s)
    s = re.sub(r"\bISNULL\s*\(", "IFNULL(", s, flags=re.IGNORECASE)
    s = re.sub(r"\bGETDATE\s*\(\s*\)", "GETDATE_()", s, flags=re.IGNORECASE)
    s = _trocar_chamadas(s, "CONVERT", _convert)
    s = _trocar_chamadas(s, "DATEDIFF",
                         lambda a: _parte_de_data(a, "DATEDIFF_"))
    s = _trocar_chamadas(s, "DATEADD",
                         lambda a: _parte_de_data(a, "DATEADD_"))

    def _cast(args):
        # ``CAST(x AS date)`` → ``date(x)``; qualquer outro CAST passa igual
        # (o SQLite entende ``AS float``/``AS int`` pela afinidade).
        corpo = args[0]
        m = re.match(r"^(.*)\s+AS\s+(\w+)\s*$", corpo,
                     re.IGNORECASE | re.DOTALL)
        if m and m.group(2).lower() == "date":
            return f"date({m.group(1)})"
        return f"CAST_KEEP({corpo})"

    s = _trocar_chamadas(s, "CAST", _cast)
    s = s.replace("CAST_KEEP(", "CAST(")
    m = _TOP.match(s)
    if m:
        s = m.group(1) + s[m.end():]
        s = s.rstrip().rstrip(";") + f"\n LIMIT {m.group(2)}"
    return s


# ── As funções que o T-SQL tem e o SQLite não ───────────────────────────────

def _como_data(valor) -> Optional[datetime.datetime]:
    if valor is None:
        return None
    if isinstance(valor, datetime.datetime):
        return valor
    texto = str(valor).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", _FORMATO_DATA_HORA, "%Y-%m-%d",
                "%Y%m%d"):
        try:
            return datetime.datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


def _datediff(parte, a, b):
    da, db = _como_data(a), _como_data(b)
    if da is None or db is None:
        return None
    if parte in ("YEAR", "YY", "YYYY"):
        # O SQL Server conta FRONTEIRAS de ano, não anos completos — é por isso
        # que a consulta de idade do app corrige pelo aniversário depois.
        return db.year - da.year
    return (db.date() - da.date()).days


def _dateadd(parte, n, d):
    base = _como_data(d)
    if base is None or n is None:
        return None
    n = int(n)
    if parte in ("YEAR", "YY", "YYYY"):
        try:
            novo = base.replace(year=base.year + n)
        except ValueError:          # 29/02 num ano que não é bissexto
            novo = base.replace(year=base.year + n, day=28)
    else:
        novo = base + datetime.timedelta(days=n)
    return novo.strftime(_FORMATO_DATA_HORA)


def _charindex(procurado, texto):
    if procurado is None or texto is None:
        return 0
    return str(texto).find(str(procurado)) + 1


def _getdate():
    return datetime.datetime.now().strftime(_FORMATO_DATA_HORA)


def _parametro(p):
    """O parâmetro no formato em que a data está GUARDADA — ver o módulo."""
    if isinstance(p, datetime.datetime):
        return p.strftime(_FORMATO_DATA_HORA)
    if isinstance(p, datetime.date):
        return p.isoformat()
    return p


def _valor_de_volta(v):
    if isinstance(v, str) and _CARA_DE_DATA_HORA.match(v):
        texto = v if "." in v else v + ".0"
        return datetime.datetime.strptime(texto, "%Y-%m-%d %H:%M:%S.%f")
    return v


# ── A conexão ───────────────────────────────────────────────────────────────

class _Cursor:
    """Só o que o ``capa_db._consultar`` usa: ``execute`` e ``fetchall``."""

    def __init__(self, cx: sqlite3.Connection):
        self._cx = cx
        self._linhas: list = []

    def execute(self, sql, *params):
        try:
            traduzido = traduzir(sql)
            cur = self._cx.execute(traduzido, [_parametro(p) for p in params])
            self._linhas = [tuple(_valor_de_volta(c) for c in linha)
                            for linha in cur.fetchall()]
        except (sqlite3.Error, ValueError):
            # Em WARNING, com o começo do SQL: é o sinal de que o app passou a
            # usar T-SQL que a tradução não cobre — e sem esta linha a tela só
            # diria "não deu para perguntar".
            _LOG.warning("Servidor local: consulta falhou (%s...)",
                         " ".join(sql.split())[:90], exc_info=True)
            raise
        return self

    def fetchall(self):
        return self._linhas

    def fetchone(self):
        return self._linhas[0] if self._linhas else None

    def close(self):
        pass


class Conexao:
    """Faz as vezes da conexão do pyodbc, EXECUTANDO o SQL no arquivo."""

    def __init__(self, caminho):
        # Somente-leitura, como a de verdade: este arquivo é o "sistema
        # clínico" da demonstração, e nada no app escreve no DW.
        self._cx = sqlite3.connect(
            f"file:{Path(caminho).as_posix()}?mode=ro", uri=True,
            check_same_thread=False)
        self._cx.create_function("DATEDIFF_", 3, _datediff,
                                 deterministic=True)
        self._cx.create_function("DATEADD_", 3, _dateadd, deterministic=True)
        self._cx.create_function("CHARINDEX", 2, _charindex,
                                 deterministic=True)
        self._cx.create_function("GETDATE_", 0, _getdate)
        self.timeout = 0

    def cursor(self):
        return _Cursor(self._cx)

    def close(self):
        try:
            self._cx.close()
        except sqlite3.Error:
            pass


def sobre(caminho) -> dict:
    """O ``sobre`` do arquivo, com a contagem de pacientes. ``{}`` se não der."""
    try:
        cx = sqlite3.connect(f"file:{Path(caminho).as_posix()}?mode=ro",
                             uri=True)
    except (sqlite3.Error, OSError):
        return {}
    try:
        campos = dict(cx.execute("SELECT chave, valor FROM sobre").fetchall())
        if campos.get("tipo") != TIPO or campos.get("versao") != str(VERSAO):
            return {}
        campos["pacientes"] = cx.execute(
            "SELECT COUNT(*) FROM DimPatient").fetchone()[0]
        return campos
    except sqlite3.Error:
        return {}
    finally:
        cx.close()


def resumo(caminho) -> str:
    """A linha que a tela mostra — é SIMULAÇÃO, e diz."""
    s = sobre(caminho)
    if not s:
        return ""
    quando = str(s.get("montado_em", ""))[:10]
    try:
        quando = datetime.date.fromisoformat(quando).strftime("%d/%m/%Y")
    except ValueError:
        pass
    deslocado = s.get("deslocamento", "")
    extra = f" Datas deslocadas para hoje ({deslocado})." if deslocado else ""
    return (f"SERVIDOR LOCAL (demonstração): {s.get('pacientes', 0)} "
            f"paciente(s), montado em {quando or '?'} a partir de "
            f"{s.get('origem') or 'pastas de TC'}.{extra} "
            "Não é o servidor da clínica.")
