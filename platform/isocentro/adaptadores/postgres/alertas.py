"""Os alertas do núcleo em PostgreSQL: abrir, ver, resolver e a fila (R-21).

Fonte: AD-28 (só da execução vigente), AD-29 (eventos acrescentados) e AD-5
(nada se edita) da espinha; CAP-12 da spec Fundação; FR-41.

Tudo grava pelo ``nucleo.gravar``: o alerta, cada evento e a troca do aviso
pelo vencido (registro novo que ``substitui`` o anterior no log). Quem viu ou
resolveu é o ``quem`` da linha de log — a porta nasce com ele, e nenhum método
aceita outra pessoa.

O que sai da fila sem evento nenhum:
- o alerta de uma execução que deixou de ser a vigente (o plano foi
  reavaliado e a nova execução deu ``conforme``, ou deu outro alerta): o AD-28
  manda alerta só da vigente, e resolver à mão um alerta de um resultado que
  já não vale seria trabalho sem objeto;
- o aviso de um prazo que venceu: o alerta ``alta`` o substitui.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional, Sequence

import psycopg

from isocentro.adaptadores.postgres.execucoes import ExecucaoGravada
from isocentro.adaptadores.postgres.porta import PortaPostgres
from isocentro.nucleo import alerta as nucleo_alerta
from isocentro.nucleo.alerta import (AlertaRecusado, EstadoAlerta, Evento,
                                     Prazo)
from isocentro.nucleo.gravacao import gravar
from isocentro.nucleo.verificacao import Severidade, VIRAM_ALERTA

TABELA = "nucleo.alerta"
TABELA_EVENTO = "nucleo.alerta_evento"

_COLUNAS = ("id", "origem", "execucao_id", "prazo_chave", "objeto", "clinica",
            "responsavel", "severidade", "motivo", "vence_em", "quando")

# O alerta que nenhum outro substitui e cuja execução (se vier de uma) é a
# vigente. ``a`` é o alias do alerta nas consultas abaixo.
_VIGENTE = (
    " NOT EXISTS (SELECT 1 FROM nucleo.log c"
    "              WHERE c.tabela = 'nucleo.alerta'"
    "                AND c.substitui = a.id::text)"
    " AND (a.execucao_id IS NULL OR NOT EXISTS ("
    "        SELECT 1 FROM nucleo.log c"
    "         WHERE c.tabela = 'nucleo.execucao'"
    "           AND c.substitui = a.execucao_id::text))")


@dataclass(frozen=True)
class EventoGravado:
    evento: str
    quem: str
    quando: datetime
    justificativa: Optional[str]


@dataclass(frozen=True)
class AlertaGravado:
    id: str
    origem: str
    execucao_id: Optional[str]
    prazo_chave: Optional[str]
    objeto: str
    clinica: str
    responsavel: str
    severidade: str
    motivo: str
    vence_em: Optional[datetime]
    quando: datetime
    eventos: tuple = ()

    @property
    def estado(self) -> EstadoAlerta:
        return nucleo_alerta.estado(e.evento for e in self.eventos)

    @property
    def vistos(self) -> list:
        """Quem viu e quando (U8: ver é ação explícita, nunca abrir a tela)."""
        return [(e.quem, e.quando) for e in self.eventos
                if e.evento == Evento.VISTO.value]


class PortaDeAlertas:
    """Os alertas como ``quem`` (a pessoa da sessão, ou a concentradora)."""

    def __init__(self, conexao: psycopg.Connection, quem: str):
        self._conexao = conexao
        self._porta = PortaPostgres(conexao)
        self._quem = quem

    # ── Abrir ───────────────────────────────────────────────────────────────

    def abrir_da_execucao(self, execucao: ExecucaoGravada, *, clinica: str,
                          responsavel: str) -> Optional[AlertaGravado]:
        """O alerta da execução, ou ``None`` se ela não vira alerta.

        Só ativa, só produção, só ``nao_conforme``/``indeterminado``/``erro``
        (CAP-10, CAP-11, CAP-12) — as mesmas regras do
        ``Execucao.vira_alerta``, aplicadas ao que FOI gravado. Repetir devolve
        o mesmo alerta.
        """
        if not (execucao.estado == "ativa" and execucao.origem == "producao"
                and execucao.resultado in {r.value for r in VIRAM_ALERTA}):
            return None
        if clinica not in nucleo_alerta.CLINICAS:
            raise AlertaRecusado(f"clínica {clinica!r} não existe")
        with self._conexao.transaction():
            self._travar("execucao", execucao.id)
            ja = self._um("a.execucao_id = %s", (int(execucao.id),))
            if ja is not None:
                return ja
            gravado = gravar(
                self._porta, modulo="nucleo", tabela=TABELA, quem=self._quem,
                versao_origem=execucao.objeto_versao or None,
                dados={"origem": "execucao", "execucao_id": int(execucao.id),
                       "objeto": execucao.objeto, "clinica": clinica,
                       "responsavel": responsavel,
                       "severidade": execucao.severidade,
                       # ``nao_conforme`` pode vir sem motivo (só os outros
                       # dois o exigem), e alerta mudo não diz o que olhar.
                       "motivo": execucao.motivo or
                       f"{execucao.verificacao_id}: {execucao.resultado}"})
        return self._um("a.id = %s", (int(gravado.registro),), vigente=False)

    def abrir_do_prazo(self, prazo: Prazo,
                       agora: datetime) -> Optional[AlertaGravado]:
        """O alerta do prazo no degrau de agora, ou ``None`` se em dia.

        O vencido substitui o aviso (AD-5): o aviso não some do histórico, só
        da fila. Prazo já resolvido no degrau de agora não reabre — quem
        resolveu disse que tratou, e reabrir a cada cinco minutos ensinaria a
        fila a ser ignorada.
        """
        severidade = nucleo_alerta.severidade_do_prazo(prazo, agora)
        if severidade is None:
            return None
        with self._conexao.transaction():
            self._travar("prazo", prazo.chave)
            do_prazo = [self._montar(r) for r in self._conexao.execute(
                f"SELECT {self._campos()} FROM nucleo.alerta a"
                " WHERE a.prazo_chave = %s AND" + _VIGENTE,
                (prazo.chave,)).fetchall()]
            if self._conexao.execute(
                    "SELECT 1 FROM nucleo.alerta"
                    " WHERE prazo_chave = %s AND severidade = %s",
                    (prazo.chave, severidade.value)).fetchone():
                mesmo = [a for a in do_prazo
                         if a.severidade == severidade.value]
                return self._com_eventos(mesmo)[0] if mesmo else None
            if any(a.severidade == Severidade.ALTA.value for a in do_prazo):
                # Já está vencido e a conta de agora diz aviso: o aviso foi
                # empurrado para depois na fonte. O vencido continua valendo
                # até alguém resolver; um aviso novo o esconderia.
                return self._com_eventos(do_prazo)[0]
            anterior = do_prazo[0].id if do_prazo else None
            gravado = gravar(
                self._porta, modulo="nucleo", tabela=TABELA, quem=self._quem,
                substitui=anterior,
                dados={"origem": "prazo", "prazo_chave": prazo.chave,
                       "objeto": prazo.objeto, "clinica": prazo.clinica,
                       "responsavel": prazo.responsavel,
                       "severidade": severidade.value,
                       "motivo": prazo.motivo, "vence_em": prazo.vence_em})
        return self._um("a.id = %s", (int(gravado.registro),), vigente=False)

    # ── Ciclo de vida ───────────────────────────────────────────────────────

    def ver(self, alerta_id: str) -> AlertaGravado:
        return self._evento(alerta_id, Evento.VISTO, None)

    def resolver(self, alerta_id: str,
                 justificativa: Optional[str] = None) -> AlertaGravado:
        return self._evento(alerta_id, Evento.RESOLVIDO, justificativa)

    def _evento(self, alerta_id, evento: Evento,
                justificativa: Optional[str]) -> AlertaGravado:
        alerta = self._um("a.id = %s", (int(alerta_id),), vigente=False)
        if alerta is None:
            raise AlertaRecusado(f"o alerta {alerta_id} não existe")
        justificativa = nucleo_alerta.conferir_evento(
            alerta.severidade, [e.evento for e in alerta.eventos], evento,
            justificativa)
        dados = {"alerta_id": int(alerta.id), "evento": evento.value}
        if justificativa:
            dados["justificativa"] = justificativa
        gravar(self._porta, modulo="nucleo", tabela=TABELA_EVENTO,
               quem=self._quem, dados=dados)
        return self._um("a.id = %s", (int(alerta.id),), vigente=False)

    # ── A fila ──────────────────────────────────────────────────────────────

    def abertos(self, clinicas: Sequence[str],
                responsaveis: Optional[Iterable[str]] = None
                ) -> list[AlertaGravado]:
        """A fila "o que precisa de ação": vigentes e não resolvidos, em ordem.

        ``clinicas`` é o que a sessão enxerga (o físico responsável passa as
        três); ``responsaveis`` os perfis da pessoa, ou ``None`` para todos.
        O filtro por clínica de verdade é do RLS (R-19); este é o da tela.
        """
        filtro = " a.clinica = ANY(%s)"
        params: list = [list(clinicas)]
        if responsaveis is not None:
            filtro += " AND a.responsavel = ANY(%s)"
            params.append(list(responsaveis))
        linhas = self._conexao.execute(
            f"SELECT {self._campos()} FROM nucleo.alerta a WHERE" + filtro +
            " AND NOT EXISTS (SELECT 1 FROM nucleo.alerta_evento e"
            "                  WHERE e.alerta_id = a.id"
            "                    AND e.evento = 'resolvido') AND" + _VIGENTE,
            params).fetchall()
        return nucleo_alerta.ordenar(
            self._com_eventos([self._montar(r) for r in linhas]))

    # ── Leitura ─────────────────────────────────────────────────────────────

    def _travar(self, tipo: str, chave) -> None:
        # Por chave e só pela transação: a concentradora e a estação abrindo o
        # mesmo alerta ao mesmo tempo veriam "nenhum" as duas, e o UNIQUE
        # devolveria erro a uma delas em vez do alerta que já existe.
        self._conexao.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (json.dumps(["alerta", tipo, str(chave)]),))

    @staticmethod
    def _campos() -> str:
        return ", ".join(f"a.{c}" for c in _COLUNAS)

    def _um(self, filtro: str, params, *, vigente: bool = True
            ) -> Optional[AlertaGravado]:
        consulta = (f"SELECT {self._campos()} FROM nucleo.alerta a"
                    f" WHERE {filtro}")
        if vigente:
            consulta += " AND" + _VIGENTE
        linha = self._conexao.execute(consulta, params).fetchone()
        return self._com_eventos([self._montar(linha)])[0] if linha else None

    def _com_eventos(self, alertas: list) -> list:
        if not alertas:
            return alertas
        por_id: dict = {a.id: [] for a in alertas}
        for alerta_id, evento, quem, quando, just in self._conexao.execute(
                "SELECT e.alerta_id::text, e.evento, l.quem, e.quando,"
                "       e.justificativa"
                "  FROM nucleo.alerta_evento e"
                "  JOIN nucleo.log l ON l.tabela = 'nucleo.alerta_evento'"
                "                   AND l.registro = e.id::text"
                " WHERE e.alerta_id = ANY(%s) ORDER BY e.id",
                ([int(i) for i in por_id],)).fetchall():
            por_id[alerta_id].append(EventoGravado(evento, quem, quando, just))
        return [AlertaGravado(**{**a.__dict__, "eventos": tuple(por_id[a.id])})
                for a in alertas]

    @staticmethod
    def _montar(r) -> AlertaGravado:
        valores = dict(zip(_COLUNAS, r))
        valores["id"] = str(valores["id"])
        if valores["execucao_id"] is not None:
            valores["execucao_id"] = str(valores["execucao_id"])
        return AlertaGravado(**valores)
