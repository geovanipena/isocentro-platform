"""A ``PortaDeGravacao`` do motor em PostgreSQL, com a execução vigente (R-20).

Fonte: AD-28 (idempotência, execução vigente), AD-5 (nada se edita) e AD-27
(grava só pelo ``nucleo.gravar``) da espinha; CAP-8 da spec Fundação; FR-39.

A chave da vigente é (verificação, origem, objeto, versão do objeto). Para
cada execução nova com a mesma chave:

- igual à vigente (mesma versão da verificação, mesmo resultado, motivo,
  evidência, estado, severidade e a mesma proveniência) → nada é gravado, e a
  vigente volta. É o caso da concentradora e da estação rodando a mesma
  verificação sobre o mesmo plano: sem isto, o log crescia uma linha por
  varredura e saíam dois alertas do mesmo fato;
- diferente → registro NOVO que substitui a vigente (``substitui`` no log). A
  anterior continua lá, para quem quiser ver que a carga de ontem dava
  ``indeterminado`` e a de hoje deu ``conforme``.

A semente separa: ``semeado`` nunca substitui ``producao`` (CAP-11).

Por que a trava consultiva: as duas pontas podem achar "nenhuma vigente" ao
mesmo tempo e gravar duas execuções novas, ambas vigentes. A trava é por
chave e dura a transação, então só serializa quem disputa o mesmo plano.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

import psycopg
from psycopg.types.json import Jsonb

from isocentro.adaptadores.postgres.porta import PortaPostgres
from isocentro.nucleo.gravacao import GravacaoRecusada, gravar
from isocentro.nucleo.verificacao import Execucao, falta_proveniencia

TABELA = "nucleo.execucao"

_COLUNAS = ("id", "verificacao_id", "verificacao_versao", "estado",
            "severidade", "origem", "objeto", "objeto_versao", "degrau",
            "data_origem", "arquivo", "checksum", "resultado", "motivo",
            "evidencia", "quando")

# O que decide se a execução nova repete a vigente. ``quando`` fica de fora
# de propósito: é a única coisa que sempre muda.
_COMPARADAS = ("verificacao_versao", "estado", "severidade", "degrau",
               "data_origem", "arquivo", "checksum", "resultado", "motivo",
               "evidencia")


@dataclass(frozen=True)
class ExecucaoGravada:
    """Uma linha de ``nucleo.execucao``. Os dados lidos não são guardados:
    a proveniência (degrau, data, arquivo, checksum) é o que permite relê-los."""
    id: str
    verificacao_id: str
    verificacao_versao: str
    estado: str
    severidade: str
    origem: str
    objeto: str
    objeto_versao: str
    degrau: str
    data_origem: Optional[str]
    arquivo: Optional[str]
    checksum: Optional[str]
    resultado: str
    motivo: str
    evidencia: Mapping[str, Any]
    quando: datetime


def _ou_nulo(texto: str) -> Optional[str]:
    texto = texto.strip() if isinstance(texto, str) else ""
    return texto or None


def _linha(execucao: Execucao) -> dict:
    e = execucao.entrada
    try:
        # Ida e volta pelo JSON: é a forma em que a evidência volta do banco,
        # e é contra ela que a vigente é comparada (tupla vira lista, e uma
        # tupla igual à lista gravada não pode parecer execução diferente).
        # ``allow_nan=False``: o jsonb recusa NaN, e a recusa aqui tem motivo.
        evidencia = json.loads(json.dumps(dict(execucao.evidencia),
                                          allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise GravacaoRecusada(f"evidência que não vira JSON: {exc}") from exc
    return {
        "verificacao_id": execucao.verificacao_id,
        "verificacao_versao": execucao.verificacao_versao,
        "estado": execucao.estado.value,
        "severidade": execucao.severidade.value,
        "origem": execucao.origem.value,
        "objeto": e.objeto.strip(),
        "objeto_versao": e.versao.strip() if isinstance(e.versao, str) else "",
        "degrau": e.degrau.strip(),
        "data_origem": _ou_nulo(e.data),
        "arquivo": _ou_nulo(e.arquivo),
        "checksum": _ou_nulo(e.checksum),
        "resultado": execucao.resultado.value,
        "motivo": execucao.motivo,
        "evidencia": evidencia,
        "quando": execucao.quando,
    }


class PortaDeExecucoes:
    """Grava a execução do motor como ``quem`` (a pessoa da sessão, ou a
    concentradora), sobre uma conexão em autocommit com o papel do app."""

    def __init__(self, conexao: psycopg.Connection, quem: str):
        self._conexao = conexao
        self._porta = PortaPostgres(conexao)
        self._quem = quem

    def gravar_execucao(self, execucao: Execucao) -> ExecucaoGravada:
        """Grava (ou reconhece) a execução e devolve a vigente da chave dela."""
        motivo = falta_proveniencia(execucao.entrada)
        if motivo:
            raise GravacaoRecusada(f"execução sem proveniência: {motivo}")
        linha = _linha(execucao)
        chave = (linha["verificacao_id"], linha["origem"], linha["objeto"],
                 linha["objeto_versao"])
        # A transação de fora segura a trava até o fim; a do ``nucleo.gravar``
        # vira um savepoint dentro dela, e qualquer falha desfaz as duas.
        with self._conexao.transaction():
            self._conexao.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (json.dumps(chave),))
            vigente = self.vigente(*chave)
            if vigente is not None and all(
                    getattr(vigente, c) == linha[c] for c in _COMPARADAS):
                return vigente
            dados = dict(linha, evidencia=Jsonb(linha["evidencia"]))
            gravado = gravar(
                self._porta, modulo="nucleo", tabela=TABELA, dados=dados,
                quem=self._quem,
                versao_origem=linha["objeto_versao"] or None,
                substitui=vigente.id if vigente else None)
        return self._ler(gravado.registro)

    def vigente(self, verificacao_id: str, origem: str, objeto: str,
                objeto_versao: str) -> Optional[ExecucaoGravada]:
        """A execução que nenhuma outra substitui, para esta chave (AD-28)."""
        linhas = self._conexao.execute(
            f"SELECT {', '.join(_COLUNAS)} FROM nucleo.execucao e"
            " WHERE verificacao_id = %s AND origem = %s AND objeto = %s"
            "   AND objeto_versao = %s"
            "   AND NOT EXISTS (SELECT 1 FROM nucleo.log c"
            "                    WHERE c.tabela = %s"
            "                      AND c.substitui = e.id::text)",
            (verificacao_id, origem, objeto, objeto_versao, TABELA)).fetchall()
        if len(linhas) > 1:
            # Não deveria existir (a trava e o gatilho impedem). Escolher uma
            # seria esconder a falha que produziu as duas.
            raise RuntimeError(
                f"{len(linhas)} execuções vigentes para {verificacao_id} em "
                f"{objeto} {objeto_versao!r}")
        return self._montar(linhas[0]) if linhas else None

    def historico(self, verificacao_id: str, origem: str, objeto: str,
                  objeto_versao: str) -> list[ExecucaoGravada]:
        """Todas as execuções da chave, da mais antiga à vigente."""
        return [self._montar(r) for r in self._conexao.execute(
            f"SELECT {', '.join(_COLUNAS)} FROM nucleo.execucao"
            " WHERE verificacao_id = %s AND origem = %s AND objeto = %s"
            "   AND objeto_versao = %s ORDER BY id",
            (verificacao_id, origem, objeto, objeto_versao)).fetchall()]

    def _ler(self, registro: str) -> ExecucaoGravada:
        return self._montar(self._conexao.execute(
            f"SELECT {', '.join(_COLUNAS)} FROM nucleo.execucao WHERE id = %s",
            (int(registro),)).fetchone())

    @staticmethod
    def _montar(r) -> ExecucaoGravada:
        return ExecucaoGravada(str(r[0]), *r[1:])
