"""A assinatura do núcleo em PostgreSQL (R-21).

Fonte: AD-30 da espinha; CAP-13 da spec Fundação; FR-8.

A porta nasce com ``quem`` (a pessoa da sessão) e o ``assinar`` não aceita
outra pessoa: assinar em nome de outro não é recusado por uma conferência, é
algo que esta porta não sabe fazer. A pessoa que volta na leitura é o
``quem`` da linha de log, não uma coluna que se pudesse preencher à mão.
"""
from __future__ import annotations

import re

import psycopg

from isocentro.adaptadores.postgres.porta import PortaPostgres
from isocentro.nucleo import assinatura as nucleo_assinatura
from isocentro.nucleo.assinatura import Assinatura, Situacao
from isocentro.nucleo.gravacao import GravacaoRecusada, gravar

TABELA = "nucleo.assinatura"
_TIPO = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")


class PortaDeAssinaturas:
    def __init__(self, conexao: psycopg.Connection, quem: str):
        self._conexao = conexao
        self._porta = PortaPostgres(conexao)
        self._quem = quem

    def assinar(self, tipo: str, objeto: str, versao: str,
                perfil: str) -> Assinatura:
        """Assina ``objeto`` na ``versao`` como a pessoa da porta."""
        if not isinstance(tipo, str) or not _TIPO.fullmatch(tipo):
            raise GravacaoRecusada(
                f"tipo {tipo!r} fora do formato <modulo>.<nome>")
        versao = versao.strip() if isinstance(versao, str) else ""
        if not versao:
            # A versão vazia é o que ``versao_do_plano`` devolve quando falta
            # dado: assinar assim valeria para qualquer versão (AD-30).
            raise GravacaoRecusada(
                f"assinatura de {objeto} sem versão: falta dado do plano")
        gravado = gravar(
            self._porta, modulo="nucleo", tabela=TABELA, quem=self._quem,
            versao_origem=versao,
            dados={"tipo": tipo, "objeto": objeto, "objeto_versao": versao,
                   "perfil": perfil})
        return next(a for a in self.assinaturas(tipo, objeto)
                    if a.id == gravado.registro)

    def assinaturas(self, tipo: str, objeto: str) -> list[Assinatura]:
        """Todas as assinaturas do objeto, de todas as versões, em ordem."""
        return [Assinatura(str(r[0]), *r[1:]) for r in self._conexao.execute(
            "SELECT s.id, s.tipo, s.objeto, s.objeto_versao, s.perfil,"
            "       l.quem, s.quando"
            "  FROM nucleo.assinatura s"
            "  JOIN nucleo.log l ON l.tabela = %s AND l.registro = s.id::text"
            " WHERE s.tipo = %s AND s.objeto = %s ORDER BY s.id",
            (TABELA, tipo, objeto)).fetchall()]

    def situacao(self, tipo: str, objeto: str, versao_atual: str) -> Situacao:
        """Assinado na versão atual, ou pendente com o porquê (AD-30)."""
        return nucleo_assinatura.situacao(self.assinaturas(tipo, objeto),
                                          versao_atual)
