"""O PostgreSQL de desenvolvimento para os testes: banco descartável e papéis.

Sem ``test_`` no nome de propósito: importado por mais de um arquivo de teste,
um módulo ``test_*`` teria as classes rodadas uma vez por importador.
Roteiro do banco e a variável ``ISOCENTRO_PG_TESTE``: ``docs/AMBIENTE.md``.
"""
from __future__ import annotations

import functools
import itertools
import os
import unittest
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from isocentro.adaptadores.postgres import esquema
from isocentro.adaptadores.postgres.porta import PortaPostgres
from isocentro.dados import ambiente
from isocentro.nucleo.gravacao import gravar

RAIZ = Path(__file__).resolve().parents[1]
MIGRACOES = RAIZ / "migracoes"
CONEXAO = ambiente.ler("ISOCENTRO_PG_TESTE")
# Sem tempo-limite, conectar no servidor desligado fica pendurado para
# sempre no Windows: em 28–29/10/2026 a suíte inteira parou no primeiro
# teste de banco, horas a fio, depois de a máquina reiniciar.
if CONEXAO and "connect_timeout" not in conninfo_to_dict(CONEXAO):
    CONEXAO = make_conninfo(CONEXAO, connect_timeout=3)
_LOCAIS = {"localhost", "127.0.0.1", "::1"}
_contador = itertools.count(1)

precisa_do_postgres = unittest.skipUnless(
    CONEXAO,
    "ISOCENTRO_PG_TESTE não definida: os testes em PostgreSQL ficam de fora "
    "nesta estação")


@functools.lru_cache(maxsize=1)
def servidor_fora() -> str:
    """O motivo, se o servidor de teste não responde; ``""`` se responde.

    Uma sondagem por processo: com o servidor fora, cada teste de banco
    pagaria o tempo-limite (6 s, IPv6 e IPv4) — uns 10 minutos de suíte para
    dizer a mesma coisa cem vezes.
    """
    try:
        with psycopg.connect(CONEXAO, autocommit=True):
            return ""
    except psycopg.Error as erro:
        return (f"o PostgreSQL de teste não responde ({erro.__class__.__name__}). "
                "Ele não sobe sozinho depois de reiniciar a máquina: ver "
                "docs/AMBIENTE.md, 'Não sobe sozinho'.")


class BancoDescartavel:
    """Um banco novo, do ``isocentro_dono``, com as migrações aplicadas."""

    def __init__(self):
        motivo = servidor_fora()
        if motivo:
            # Falha, e não pula: quem definiu a variável quer saber que o
            # servidor caiu (docs/AMBIENTE.md).
            raise AssertionError(motivo)
        host = conninfo_to_dict(CONEXAO).get("host", "")
        if host not in _LOCAIS:
            # Os testes criam e APAGAM bancos como superusuário. Apontados
            # por engano para o servidor da clínica, seriam um desastre.
            raise RuntimeError(
                f"ISOCENTRO_PG_TESTE aponta para {host!r}: só cluster local "
                "de desenvolvimento")
        self.nome = f"isocentro_teste_{os.getpid()}_{next(_contador)}"
        self.conninfo = make_conninfo(CONEXAO, dbname=self.nome)
        with psycopg.connect(CONEXAO, autocommit=True) as admin:
            esquema.criar_papeis(admin)
            admin.execute(f"CREATE DATABASE {self.nome} OWNER isocentro_dono")
        with self.conectar() as c:
            esquema.aplicar(c, MIGRACOES)
            # O módulo de mentira dos testes, criado como o dono criaria o
            # de um módulo de verdade numa migração.
            c.execute("SET ROLE isocentro_dono")
            c.execute(
                "CREATE SCHEMA teste;"
                " GRANT USAGE ON SCHEMA teste"
                "  TO isocentro_app, isocentro_concentradora;"
                " CREATE TABLE teste.coisa ("
                "  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"
                "  valor text NOT NULL CHECK (valor <> 'falha'));"
                " INSERT INTO nucleo.dono_tabela VALUES ('teste.coisa', 'teste');"
                " CREATE SCHEMA outro;"
                " GRANT USAGE ON SCHEMA outro TO isocentro_app;"
                " CREATE TABLE outro.coisa ("
                "  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"
                "  valor text);"
                " INSERT INTO nucleo.dono_tabela VALUES ('outro.coisa', 'outro')")

    def conectar(self, papel: str | None = None) -> "psycopg.Connection":
        c = psycopg.connect(self.conninfo, autocommit=True)
        if papel:
            c.execute(f"SET ROLE {papel}")
        return c

    def apagar(self):
        with psycopg.connect(CONEXAO, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {self.nome} WITH (FORCE)")


class ComBanco(unittest.TestCase):
    """Banco por TESTE: os que adulteram o log não podem sujar o vizinho."""

    def setUp(self):
        self.banco = BancoDescartavel()
        self.addCleanup(self.banco.apagar)
        self.app = self.banco.conectar("isocentro_app")
        self.addCleanup(self.app.close)
        self.porta = PortaPostgres(self.app)

    def _gravar(self, valor="a", **kw):
        return gravar(self.porta, modulo="teste", tabela="teste.coisa",
                      dados={"valor": valor}, quem="geovani.pena", **kw)

    def _conta(self, consulta):
        with self.banco.conectar() as c:
            return c.execute(consulta).fetchone()[0]
