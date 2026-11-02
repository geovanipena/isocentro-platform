"""Banco LOCAL: o que o data warehouse respondeu, gravado para reproduzir.

Trabalhar no programa fora da clínica custa o banco inteiro. Esta máquina está
fora do domínio: a rede alcança o servidor, mas a identidade é recusada (SSPI),
e sem ``runas /netonly`` o :mod:`capa_db` devolve ``None`` para tudo — a Capa
cai no espelho/CSV e a **Ficha Virtual não existe**, porque ela não tem reserva
nenhuma. Fica-se conferindo tela com dado de mentira, que é o jeito de não
descobrir o defeito que só o dado real mostra.

Este módulo grava as RESPOSTAS do banco e as reproduz depois, sem rede.

**Não é o espelho** (:mod:`capa_espelho`), e a diferença importa. O espelho é
reserva de EMERGÊNCIA para a sala de tratamento: vence em 60 dias, sai anunciado
como emergência e guarda o resultado já traduzido (cadastro, prescrição, foto) —
nada dele serve ao :mod:`tratamento_db`. Aqui é ferramenta de trabalho: guarda a
LINHA CRUA que o servidor devolveu, para qualquer consulta de qualquer módulo.

**Por que no nível da linha.** Todo o diálogo com o servidor passa por um
gargalo só, ``capa_db._consultar``. Gravando ali, a Capa e a Ficha Virtual
funcionam offline sem que nenhum dos dois módulos mude de lógica: ``conexao()``
devolve uma conexão de mentira que lê este arquivo. Gravar no nível traduzido
exigiria um gravador por função — e o ``tratamento_db`` tem doze.

**Por que não um SQLite com as tabelas do DW.** O T-SQL das consultas
(``ISNULL``, ``TOP``, ``CONVERT(..., 112)``) não roda em SQLite; traduzir cada
consulta seria criar, com as próprias mãos, a fonte do erro silencioso — a
resposta plausível e diferente da do servidor.

**Consulta que não foi gravada não inventa resposta**: levanta a
``FalhaDeLeitura`` de sempre, que é o que o app já sabe tratar (a Capa cai para
o espelho, a lista diz "não deu para perguntar"). Mexer no SQL de uma consulta
invalida a gravação dela — e é para invalidar mesmo: a linha gravada responde à
pergunta antiga.

Liga-se apontando ``ISOCENTRO_BANCO_LOCAL`` para o arquivo. Sem a variável, este
módulo inteiro fica fora do caminho e nada muda. Gravar é
``tools/gravar_banco.py``, que precisa da identidade de rede.
"""
from __future__ import annotations

import base64
import datetime
import decimal
import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Optional

from isocentro.banco import servidor_local
from isocentro.dados import ambiente

_LOG = logging.getLogger(__name__)


def _e_servidor_local(caminho) -> bool:
    return servidor_local.tipo_do_arquivo(caminho) == servidor_local.TIPO

ENV = "ISOCENTRO_BANCO_LOCAL"

# Formato do arquivo. Mudou a estrutura, a gravação velha é RECUSADA em vez de
# lida errado — mesma regra do espelho: dado de paciente não se adivinha.
VERSAO = 1


def arquivo() -> Optional[Path]:
    """O arquivo apontado, ou ``None`` se ninguém apontou nenhum."""
    valor = ambiente.ler(ENV)
    return Path(valor) if valor else None


def ligado() -> bool:
    """Há banco local valendo AGORA?

    Exige o arquivo existindo, e não só a variável definida: variável apontando
    para arquivo que não existe é o caso comum de quem copiou o ``.bat`` de
    outra estação, e devolver ``True`` ali faria o app anunciar "banco local" e
    não responder consulta nenhuma.
    """
    alvo = arquivo()
    return bool(alvo and alvo.is_file())


# -- A chave: (SQL, parâmetros) ----------------------------------------------

_COMENTARIO = re.compile(r"--[^\n]*")
_ESPACOS = re.compile(r"\s+")

# Parâmetro com CARA DE DATA vira curinga. É o ``desde`` do
# ``tratamento_db.em_tratamento``, que é ``hoje - 30 dias``: gravado numa
# terça, a chave exata só casaria naquela terça, e no dia seguinte a lista de
# "em tratamento" voltaria vazia sem explicação nenhuma. O dado gravado é
# congelado de qualquer forma — a janela dele é a do dia da gravação, e é isso
# que o ``resumo()`` diz na tela.
_CARA_DE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _normalizar_sql(sql: str) -> str:
    """Tira comentário e achata espaço, para reformatar não invalidar tudo.

    O SQL deste projeto vem com comentário longo DENTRO da consulta (o
    ``_SQL_EM_TRATAMENTO`` chegou a explicar, em quinze linhas, por que só dois
    ``TerminationStatus`` contavam), e esses comentários são reescritos com
    frequência. Sem tirá-los, uma vírgula num comentário jogaria fora a
    gravação inteira.

    O corte é por LINHA, e não com o ``--`` valendo até o fim do texto: achatar
    antes de cortar transformaria o resto da consulta em comentário.
    """
    limpo = "\n".join(_COMENTARIO.sub("", linha) for linha in sql.splitlines())
    return _ESPACOS.sub(" ", limpo).strip()


def _normalizar_params(params) -> list:
    fora = []
    for p in params:
        texto = "" if p is None else str(p)
        fora.append("<DATA>" if _CARA_DE_DATA.match(texto) else texto)
    return fora


def _chave(sql: str, params) -> str:
    crua = json.dumps([_normalizar_sql(sql), _normalizar_params(params)],
                      ensure_ascii=False)
    return hashlib.sha1(crua.encode("utf-8")).hexdigest()


# -- Valores: o tipo tem de voltar como saiu ---------------------------------
#
# O que se lê do DW não é só texto. ``capa_db._data()`` chama ``strftime`` no
# valor, ``em_tratamento`` chama ``.date()``, a foto é BLOB e dose vem em
# ``Decimal``. Gravar tudo como string faria a reprodução devolver dado que
# PARECE certo e quebra (ou pior, arredonda) na tradução — então cada valor
# viaja etiquetado.

def _codificar(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, datetime.datetime):
        return {"#": "dt", "v": v.isoformat()}
    if isinstance(v, datetime.date):
        return {"#": "d", "v": v.isoformat()}
    if isinstance(v, datetime.time):
        return {"#": "h", "v": v.isoformat()}
    if isinstance(v, decimal.Decimal):
        # Em TEXTO, não em float: o DW guarda dose em ``decimal``, e passar por
        # float é justamente onde 0,1 vira 0,10000000000000001.
        return {"#": "dec", "v": str(v)}
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"#": "b", "v": base64.b64encode(bytes(v)).decode("ascii")}
    _LOG.warning("Banco local: tipo não previsto (%s), gravado como texto.",
                 type(v).__name__)
    return str(v)


def _decodificar(v):
    if not isinstance(v, dict):
        return v
    tipo, valor = v.get("#"), v.get("v")
    if tipo == "dt":
        return datetime.datetime.fromisoformat(valor)
    if tipo == "d":
        return datetime.date.fromisoformat(valor)
    if tipo == "h":
        return datetime.time.fromisoformat(valor)
    if tipo == "dec":
        return decimal.Decimal(valor)
    if tipo == "b":
        return base64.b64decode(valor)
    return valor


# -- O arquivo ---------------------------------------------------------------

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS sobre (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS respostas (
    chave      TEXT PRIMARY KEY,
    sql        TEXT NOT NULL,
    params     TEXT NOT NULL,
    linhas     TEXT NOT NULL,
    quantas    INTEGER NOT NULL,
    gravado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pacientes (
    registro   TEXT PRIMARY KEY,
    pasta      TEXT NOT NULL DEFAULT '',
    achou      INTEGER NOT NULL DEFAULT 0,
    recado     TEXT NOT NULL DEFAULT '',
    gravado_em TEXT NOT NULL
);
"""


def abrir(caminho, criar: bool = False) -> sqlite3.Connection:
    """O SQLite do banco local. ``criar`` monta o esqueleto se faltar."""
    caminho = Path(caminho)
    if criar:
        caminho.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(str(caminho))
    if criar:
        cx.executescript(_ESQUEMA)
        cx.execute("INSERT OR IGNORE INTO sobre VALUES ('versao', ?)",
                   (str(VERSAO),))
        cx.commit()
    return cx


def anotar(cx: sqlite3.Connection, chave: str, valor) -> None:
    cx.execute("INSERT OR REPLACE INTO sobre VALUES (?, ?)",
               (str(chave), str(valor)))


def gravar(cx: sqlite3.Connection, sql: str, params, linhas) -> None:
    """Guarda a resposta de UMA consulta. Regravar por cima é o normal."""
    cx.execute(
        "INSERT OR REPLACE INTO respostas VALUES (?, ?, ?, ?, ?, ?)",
        (_chave(sql, params),
         _normalizar_sql(sql),
         json.dumps(_normalizar_params(params), ensure_ascii=False),
         json.dumps([[_codificar(c) for c in linha] for linha in linhas],
                    ensure_ascii=False),
         len(linhas),
         datetime.datetime.now().isoformat(timespec="seconds")))


def anotar_paciente(cx: sqlite3.Connection, registro: str, pasta: str,
                    achou: bool, recado: str = "") -> None:
    """Quem se tentou gravar, e se o banco o tinha.

    Existe para a ferramenta poder dizer, depois, QUEM ficou de fora — um
    paciente da pasta de TC que o ``variandw`` não conhece (os da Elekta, por
    exemplo) sumiria sem deixar rastro se só as respostas fossem gravadas.
    """
    cx.execute("INSERT OR REPLACE INTO pacientes VALUES (?, ?, ?, ?, ?)",
               (str(registro), str(pasta), 1 if achou else 0, str(recado),
                datetime.datetime.now().isoformat(timespec="seconds")))


def sobre() -> dict:
    """``{"gravado_em", "servidor", "pacientes", "consultas"}`` — para a tela.

    Devolve ``{}`` quando não há banco local (ou quando ele é de outra versão),
    e nunca levanta: quem chama está montando um recado de tela.
    """
    alvo = arquivo()
    if not (alvo and alvo.is_file()):
        return {}
    if _e_servidor_local(alvo):
        return servidor_local.sobre(alvo)
    try:
        cx = sqlite3.connect(f"file:{alvo.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    try:
        campos = dict(cx.execute("SELECT chave, valor FROM sobre").fetchall())
        if campos.get("versao") != str(VERSAO):
            return {}
        campos["consultas"] = cx.execute(
            "SELECT COUNT(*) FROM respostas").fetchone()[0]
        campos["pacientes"] = cx.execute(
            "SELECT COUNT(*) FROM pacientes WHERE achou = 1").fetchone()[0]
        return campos
    except sqlite3.Error:
        return {}
    finally:
        cx.close()


def resumo() -> str:
    """Uma linha dizendo o que está valendo — é o que a tela mostra."""
    alvo = arquivo()
    if alvo and _e_servidor_local(alvo):
        return servidor_local.resumo(alvo)
    s = sobre()
    if not s:
        return ""
    quando = str(s.get("gravado_em", ""))[:10]
    try:
        quando = datetime.date.fromisoformat(quando).strftime("%d/%m/%Y")
    except ValueError:
        pass
    return (f"BANCO LOCAL (simulação): {s.get('pacientes', 0)} paciente(s) "
            f"gravado(s) de {s.get('servidor') or 'servidor não anotado'} "
            f"em {quando or '?'}. Dado CONGELADO — não é o servidor.")


# -- A conexão de mentira ----------------------------------------------------

class NaoGravada(Exception):
    """A pergunta não está no arquivo. Não é "o banco respondeu vazio"."""


class _Cursor:
    """Só o que o ``capa_db._consultar`` usa: ``execute`` e ``fetchall``."""

    def __init__(self, cx: sqlite3.Connection):
        self._cx = cx
        self._linhas: list = []

    def execute(self, sql, *params):
        linha = self._cx.execute(
            "SELECT linhas FROM respostas WHERE chave = ?",
            (_chave(sql, params),)).fetchone()
        if linha is None:
            # Não devolver ``[]``: lista vazia quer dizer "o banco respondeu e
            # não havia nada", e é assim que a capa afirma "nenhuma prescrição
            # aprovada" para quem tem cinco. Aqui o fato é outro — a pergunta
            # não foi gravada — e ele tem de chegar como falha.
            _LOG.warning("Banco local: consulta não gravada (%s...) params=%r",
                         _normalizar_sql(sql)[:70], params)
            raise NaoGravada("esta consulta não está no banco local")
        self._linhas = [tuple(_decodificar(c) for c in linha_gravada)
                        for linha_gravada in json.loads(linha[0])]
        return self

    def fetchall(self):
        return self._linhas

    def fetchone(self):
        return self._linhas[0] if self._linhas else None

    def close(self):
        pass


class Conexao:
    """Faz as vezes da conexão do pyodbc, lendo o arquivo gravado."""

    def __init__(self, caminho: Path):
        # ``check_same_thread=False`` porque o ``capa_db.aquecer`` abre a
        # conexão numa thread de fundo e a interface a usa em outra — é o mesmo
        # que a conexão de verdade faz.
        self._cx = sqlite3.connect(
            f"file:{Path(caminho).as_posix()}?mode=ro", uri=True,
            check_same_thread=False)
        self.timeout = 0   # o ``capa_db`` atribui isso na conexão de verdade

    def cursor(self):
        return _Cursor(self._cx)

    def close(self):
        try:
            self._cx.close()
        except sqlite3.Error:
            pass


_conexao: Optional[Conexao] = None


def conexao() -> Optional[Conexao]:
    """A conexão de reprodução, ou ``None`` se não há banco local.

    Guardada entre chamadas pelo mesmo motivo da de verdade: montar uma capa
    faz várias consultas seguidas.
    """
    global _conexao
    if not ligado():
        return None
    if _conexao is None:
        try:
            # O MESMO arquivo apontado pode ser uma gravação (reprodução) ou um
            # servidor local (tabelas do DW, SQL executado de verdade) — ver
            # :mod:`servidor_local`. Quem decide é o próprio arquivo, e não uma
            # segunda variável: duas variáveis que podem discordar são o jeito
            # de a tela anunciar um modo e o app estar em outro.
            if _e_servidor_local(arquivo()):
                _conexao = servidor_local.Conexao(arquivo())
            else:
                _conexao = Conexao(arquivo())
        except sqlite3.Error:
            _LOG.warning("Banco local ilegível: %s", arquivo(), exc_info=True)
            return None
        # Em WARNING de propósito: quem ligou isto sem querer tem de ver a
        # linha no histórico de uso. Simulação silenciosa vira o normal.
        _LOG.warning("BANCO LOCAL LIGADO (%s). É simulação, não o servidor.",
                     arquivo())
    return _conexao


def esquecer() -> None:
    """Solta a conexão de reprodução — o ``capa_db.esquecer`` passa por aqui."""
    global _conexao
    if _conexao is not None:
        _conexao.close()
    _conexao = None


# -- O gravador --------------------------------------------------------------

class _CursorGravador:
    """Executa no banco DE VERDADE e guarda o que voltou."""

    def __init__(self, cursor_real, destino: sqlite3.Connection, filtrar=None):
        self._cur = cursor_real
        self._destino = destino
        self._filtrar = filtrar
        self._sql = ""
        self._params: tuple = ()

    def execute(self, sql, *params):
        self._sql, self._params = sql, params
        self._cur.execute(sql, *params)
        return self

    def fetchall(self):
        linhas = self._cur.fetchall()
        if self._filtrar is not None:
            # O filtro vale para o que se GRAVA **e** para o que se devolve a
            # quem perguntou, e essa segunda metade é a que importa. As
            # consultas que varrem a clínica inteira alimentam outras: o
            # ``em_tratamento`` devolve a lista, e o ``tratamento_db`` refaz a
            # contagem de frações passando ESSES registros como parâmetro. Se o
            # corte fosse feito depois, no arquivo, a gravação teria as
            # consultas auxiliares perguntadas com a lista INTEIRA — e, na
            # reprodução, a lista curta pediria uma pergunta que ninguém
            # gravou: as colunas de recontagem sumiriam da tela.
            linhas = self._filtrar(self._sql, linhas)
        # Grava no ``fetchall``, e não no ``execute``: é aqui que as linhas
        # existem. Consulta que explode no ``execute`` não chega a gravar nada,
        # que é o certo — meia resposta gravada seria pior que nenhuma.
        gravar(self._destino, self._sql, self._params, linhas)
        return linhas


class Gravador:
    """Embrulha a conexão real; tudo que passar por ela fica gravado.

    É o que deixa a ferramenta de gravação chamar as funções DE VERDADE
    (``capa_db.cadastro_do_paciente`` e companhia) em vez de reescrever o SQL
    delas: o conjunto de consultas gravado é, por construção, exatamente o que
    o app pergunta.

    ``filtrar(sql, linhas) -> linhas`` corta linhas antes de gravar e antes de
    devolvê-las. É o que restringe as consultas que varrem a clínica inteira
    aos pacientes que interessam — ver o comentário em ``_CursorGravador``.
    """

    def __init__(self, conexao_real, destino: sqlite3.Connection, filtrar=None):
        self._real = conexao_real
        self._destino = destino
        self._filtrar = filtrar
        self.timeout = getattr(conexao_real, "timeout", 0)

    def cursor(self):
        return _CursorGravador(self._real.cursor(), self._destino,
                               self._filtrar)

    def close(self):
        pass   # quem abriu a conexão real é quem a fecha
