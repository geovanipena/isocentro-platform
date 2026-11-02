"""Versão do esquema (AD-19) e as migrações numeradas de ``migracoes/``.

Duas pontas, que não se misturam:

- o APP só confere (``conferir``): versão do banco diferente da que ele
  conhece → somente leitura com o aviso. Ele nunca aplica nada — o papel
  ``isocentro_app`` nem tem direito de DDL.
- o DONO aplica (``aplicar``, pelo ``tools/migrar_banco.py``): cada arquivo
  numa transação, com a linha de ``nucleo.versao_esquema`` dentro dela.
  Arquivo que falha no meio não deixa nem metade do esquema nem a versão.

Sem Alembic (AD-19): ``.sql`` numerado e a tabela de versão bastam, e o
físico consegue ler o que mudou no banco sem saber Python.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psycopg

# A versão que ESTE código sabe usar. Sobe junto com o arquivo novo em
# ``migracoes/``; o ``test_postgres`` reprova se os dois se desencontrarem.
ESQUEMA_DO_APP = 4

PAPEIS = ("isocentro_dono", "isocentro_app", "isocentro_concentradora")

_ARQUIVO = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


@dataclass(frozen=True)
class SituacaoDoEsquema:
    versao_do_banco: Optional[int]
    somente_leitura: bool
    aviso: Optional[str]


def versao_do_banco(conexao: psycopg.Connection) -> Optional[int]:
    """A maior versão aplicada, ``0`` sem nenhuma, ``None`` se o banco não é do ISOCENTRO."""
    existe = conexao.execute(
        "SELECT to_regclass('nucleo.versao_esquema') IS NOT NULL").fetchone()[0]
    if not existe:
        return None
    return conexao.execute(
        "SELECT coalesce(max(versao), 0) FROM nucleo.versao_esquema"
    ).fetchone()[0]


def conferir(conexao: psycopg.Connection,
             esperada: int = ESQUEMA_DO_APP) -> SituacaoDoEsquema:
    """O que o app faz ao abrir: grava só se o banco estiver na versão dele."""
    versao = versao_do_banco(conexao)
    if versao == esperada:
        return SituacaoDoEsquema(versao, False, None)
    if versao is None or versao == 0:
        aviso = ("O banco central não tem o esquema do ISOCENTRO: "
                 "nada será gravado. Peça a atualização do banco.")
    elif versao > esperada:
        # App velho em banco novo: gravar com o modelo antigo poderia deixar
        # de preencher o que o esquema novo exige.
        aviso = (f"O banco central está na versão {versao} e este ISOCENTRO "
                 f"conhece a {esperada}: atualize o ISOCENTRO. "
                 "Nada será gravado até lá.")
    else:
        aviso = (f"O banco central está na versão {versao} e este ISOCENTRO "
                 f"espera a {esperada}: peça a atualização do banco. "
                 "Nada será gravado até lá.")
    return SituacaoDoEsquema(versao, True, aviso)


def migracoes(pasta: Path) -> list[tuple[int, Path]]:
    """Os arquivos numerados, em ordem, conferidos: de 1 em diante, sem pular."""
    achados = []
    for arquivo in sorted(Path(pasta).glob("*.sql")):
        m = _ARQUIVO.match(arquivo.name)
        if not m:
            raise ValueError(f"migração fora do formato NNNN_nome.sql: {arquivo.name}")
        achados.append((int(m.group(1)), arquivo))
    numeros = [n for n, _ in achados]
    if numeros != list(range(1, len(numeros) + 1)):
        # Um buraco na numeração seria um arquivo que nunca roda em banco
        # novo, mas que rodou no de quem o escreveu.
        raise ValueError(f"migrações fora da sequência 1, 2, 3…: {numeros}")
    return achados


def criar_papeis(conexao: psycopg.Connection) -> list[str]:
    """Os três papéis do AD-6, sem login (é preciso superusuário). Devolve os criados.

    Sem LOGIN de propósito: a senha e o TLS de cada um são da R-19 e da
    instalação na clínica. Aqui eles existem para receber os GRANTs.
    """
    criados = []
    for papel in PAPEIS:
        existe = conexao.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (papel,)).fetchone()
        if not existe:
            conexao.execute(f"CREATE ROLE {papel} NOLOGIN")
            criados.append(papel)
    return criados


def aplicar(conexao: psycopg.Connection, pasta: Path) -> list[int]:
    """Aplica, como ``isocentro_dono``, as migrações que o banco ainda não tem."""
    if not conexao.autocommit:
        # Mesmo motivo da ``PortaPostgres``: sem autocommit, cada arquivo
        # seria um savepoint de uma transação que ninguém confirma.
        raise ValueError("as migrações precisam de conexão em autocommit")
    pendentes = []
    conexao.execute("SET ROLE isocentro_dono")
    try:
        atual = versao_do_banco(conexao) or 0
        for numero, arquivo in migracoes(pasta):
            if numero <= atual:
                continue
            with conexao.transaction():
                conexao.execute(arquivo.read_text(encoding="utf-8"))
                conexao.execute(
                    "INSERT INTO nucleo.versao_esquema (versao, arquivo)"
                    " VALUES (%s, %s)", (numero, arquivo.name))
            pendentes.append(numero)
    finally:
        conexao.execute("RESET ROLE")
    return pendentes
