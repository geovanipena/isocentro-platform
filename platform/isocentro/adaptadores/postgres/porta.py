"""A ``PortaDoBanco`` em PostgreSQL: registro e linha de log numa transação só.

O tudo-ou-nada é do banco, não deste código: os dois INSERT correm dentro de
``conexao.transaction()``, e qualquer exceção — do registro, do gatilho do
log, da rede — desfaz os dois. Por isso a porta não tenta "limpar" nada
depois de uma falha: não há o que limpar.

Convenção das tabelas de módulo: chave ``id`` gerada pelo banco
(``bigint GENERATED ALWAYS AS IDENTITY``). É o ``id`` que vai para o log como
``registro``; tabela sem ele é recusada no primeiro INSERT.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

import psycopg
from psycopg import sql

from isocentro.nucleo.gravacao import GravacaoRecusada, Gravado, LinhaNova
from isocentro.nucleo.integridade import Ancora, LinhaDeLog


def _motivo(erro: psycopg.Error) -> str:
    diag = getattr(erro, "diag", None)
    primario = getattr(diag, "message_primary", None) if diag else None
    return primario or str(erro).strip() or type(erro).__name__


class PortaPostgres:
    """A porta sobre uma conexão aberta, já com o papel do app."""

    def __init__(self, conexao: psycopg.Connection):
        if not conexao.autocommit:
            # Fora do autocommit, a primeira consulta abre uma transação
            # implícita e o ``transaction()`` vira só um savepoint dentro
            # dela: o "gravado" voltaria, e nada seria confirmado.
            raise ValueError("a porta precisa de conexão em autocommit")
        self._conexao = conexao

    def dono_de(self, tabela: str) -> Optional[str]:
        linha = self._conexao.execute(
            "SELECT modulo FROM nucleo.dono_tabela WHERE tabela = %s",
            (tabela,)).fetchone()
        return linha[0] if linha else None

    def inserir_com_log(self, tabela: str, dados: Mapping[str, Any],
                        linha: LinhaNova) -> Gravado:
        esquema, nome = tabela.split(".")
        colunas = list(dados)
        insercao = sql.SQL(
            "INSERT INTO {} ({}) VALUES ({}) RETURNING id::text").format(
                sql.Identifier(esquema, nome),
                sql.SQL(", ").join(sql.Identifier(c) for c in colunas),
                sql.SQL(", ").join(sql.Placeholder() * len(colunas)))
        try:
            with self._conexao.transaction():
                registro = self._conexao.execute(
                    insercao, [dados[c] for c in colunas]).fetchone()[0]
                posicao = self._conexao.execute(
                    "INSERT INTO nucleo.log (quem, modulo, tabela, registro,"
                    " substitui, versao_origem)"
                    " VALUES (%s, %s, %s, %s, %s, %s) RETURNING posicao",
                    (linha.quem, linha.modulo, linha.tabela, registro,
                     linha.substitui, linha.versao_origem)).fetchone()[0]
        except psycopg.Error as erro:
            raise GravacaoRecusada(_motivo(erro)) from erro
        return Gravado(tabela=tabela, registro=registro, posicao=posicao)

    def vigentes(self, tabela: str) -> list[str]:
        """Os ids de ``tabela`` que nenhum registro substitui (AD-5), na ordem do log.

        Calculado do log, e não de uma coluna "substituído" no registro: marcar
        o anterior seria um UPDATE, que é justamente o que o AD-5 proíbe.
        """
        return [r[0] for r in self._conexao.execute(
            "SELECT l.registro FROM nucleo.log l"
            " WHERE l.tabela = %s AND NOT EXISTS ("
            "   SELECT 1 FROM nucleo.log c"
            "    WHERE c.tabela = l.tabela AND c.substitui = l.registro)"
            " ORDER BY l.posicao", (tabela,)).fetchall()]

    def agora(self) -> datetime:
        """A hora do banco: a mesma para as três clínicas e a concentradora."""
        return self._conexao.execute("SELECT clock_timestamp()").fetchone()[0]

    def ponta(self) -> Optional[Ancora]:
        """Posição e hash da última linha do log, para a âncora do dia (AD-32).

        Da ÚLTIMA LINHA, e não da ``nucleo.ponta``: o app e a concentradora
        não leem a ponta (só o gatilho), e a âncora tem de ser um hash que o
        verificador acha numa linha do log.
        """
        linha = self._conexao.execute(
            "SELECT posicao, hash FROM nucleo.log"
            " ORDER BY posicao DESC LIMIT 1").fetchone()
        return Ancora(linha[0], bytes(linha[1])) if linha else None

    def linhas_do_log(self) -> list[LinhaDeLog]:
        """O log inteiro, cru, para o ``nucleo.integridade.verificar``."""
        return [LinhaDeLog(*r) for r in self._conexao.execute(
            "SELECT posicao, quando, quem, modulo, tabela, registro, substitui,"
            " versao_origem, hash_anterior, hash"
            " FROM nucleo.log ORDER BY posicao").fetchall()]
