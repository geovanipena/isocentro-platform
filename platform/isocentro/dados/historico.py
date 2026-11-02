"""Histórico de uso do app (trilha de eventos): quem fez o quê e quando.

Registro append-only em JSON Lines (um evento JSON por linha) num arquivo
COMPARTILHADO — ``ISOCENTRO_LOG_DIR`` (ex.: caminho de rede) ou, sem ela, ao lado
do índice central. O formato por linha torna o append seguro sob concorrência
(várias estações escrevendo) e evita reescrever o arquivo inteiro a cada evento.

O usuário logado é definido uma vez (``definir_usuario``) e usado por padrão em
todos os ``registrar``, para não precisar passá-lo em cada chamada. Tudo é
best-effort: uma falha ao registrar NUNCA interrompe o app.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional
from isocentro.dados import ambiente
from isocentro.dados.nomes import como_nome_proprio

_USUARIO_ATUAL: Optional[dict] = None


def definir_usuario(usuario: Optional[dict]) -> None:
    """Fixa o usuário logado como autor padrão dos próximos eventos."""
    global _USUARIO_ATUAL
    _USUARIO_ATUAL = usuario


def caminho_log() -> Path:
    """Arquivo do histórico: ``ISOCENTRO_LOG_DIR`` ou ao lado do índice central."""
    env = ambiente.ler("ISOCENTRO_LOG_DIR")
    if env:
        base = Path(env)
    else:
        try:
            from isocentro.dados import indice
            base = indice._app_dir()
        except Exception:  # noqa: BLE001
            base = Path(".")
    return base / "historico_uso.jsonl"


def _nome_usuario(usuario) -> str:
    if isinstance(usuario, dict):
        return usuario.get("usuario") or ""
    return str(usuario or "")


def _norm_usuario(usuario) -> str:
    return _nome_usuario(usuario).strip().lower()


def registrar(evento: str, detalhes: Optional[dict] = None,
              usuario=None) -> None:
    """Acrescenta um evento ao histórico (best-effort; nunca levanta)."""
    try:
        u = usuario if usuario is not None else _USUARIO_ATUAL
        linha = {
            "em": datetime.datetime.now().isoformat(timespec="seconds"),
            "usuario": _nome_usuario(u),
            "evento": evento,
        }
        if detalhes:
            linha["detalhes"] = detalhes
        p = caminho_log()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — o histórico é acessório
        pass


def ler(limite: int = 1000) -> list[dict]:
    """Últimos eventos do histórico, dos mais recentes para os mais antigos."""
    p = caminho_log()
    if not p.exists():
        return []
    linhas: list[dict] = []
    try:
        with open(p, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    linhas.append(json.loads(ln))
                except Exception:  # noqa: BLE001 — pula linha corrompida
                    continue
    except Exception:  # noqa: BLE001
        return []
    linhas.reverse()
    return linhas[:limite]


# O que conta como "documentação feita": a ficha DEFINITIVA, gravada e
# versionada. ``ficha_automatica`` (a montagem) e ``ficha_visualizada`` (a
# prévia) ficam de fora de propósito — montar e conferir não é ter entregado, e
# uma lista que mistura os três não responde mais "o que eu já fiz hoje".
EVENTO_FICHA = "ficha_gerada"


def fichas_do_usuario(usuario=None, limite: int = 10,
                      eventos: int = 4000) -> dict:
    """Últimas fichas geradas POR ESTE usuário, e quantas ele fez hoje.

    Uma linha por PACIENTE, na geração mais recente: quem gerou v1, v2 e v3 do
    mesmo caso fez um trabalho só, e três linhas iguais empurrariam para fora da
    lista os outros pacientes do dia — que é justamente o que se quer ver.

    O log é compartilhado por todas as estações; o filtro por usuário é o que
    torna a lista útil na tela de trabalho — a ficha do colega ao lado não
    ajuda a responder "já fiz este paciente?". O panorama geral continua na
    tela de Histórico.

    Devolve ``{"recentes": [...], "hoje": n}``, onde ``hoje`` conta TODOS os
    pacientes do dia, inclusive os que não couberam em ``limite``.
    """
    u = usuario if usuario is not None else _USUARIO_ATUAL
    alvo = _norm_usuario(u)
    hoje_iso = datetime.date.today().isoformat()
    recentes: list[dict] = []
    vistos: set[str] = set()
    de_hoje: set[str] = set()
    for e in ler(limite=eventos):     # já vem do mais recente para o mais antigo
        if e.get("evento") != EVENTO_FICHA:
            continue
        if alvo and _norm_usuario(e.get("usuario")) != alvo:
            continue
        det = e.get("detalhes") or {}
        chave = (det.get("registro") or det.get("paciente") or "").strip().lower()
        if not chave:
            # Sem registro nem nome não há linha possível: ela sairia
            # "(sem nome)", com as quatro ações apagadas, ocupando uma das dez
            # vagas. E, como o contador do dia exige chave, ela também não
            # somaria em "N fichas hoje" — duas contas discordando da mesma
            # lista.
            continue
        em = e.get("em", "") or ""
        if em[:10] == hoje_iso:
            de_hoje.add(chave)
        if chave in vistos:
            continue
        vistos.add(chave)
        if len(recentes) < limite:
            recentes.append({
                "em": em,
                # Grafia canônica só AQUI: o evento gravado é registro de
                # auditoria e continua com o nome exatamente como a ficha o
                # tinha. Quem monta a lista é que uniformiza — os eventos de
                # antes de 25/08/2026 têm o nome como cada TPS o grafou.
                "paciente": como_nome_proprio(det.get("paciente", "")),
                "registro": det.get("registro", ""),
                "versao": det.get("versao"),
                "maquina": det.get("maquina", ""),
                # Gravada desde a versão que criou esta lista; nos eventos
                # antigos vem vazia e quem exibe resolve pelo índice central.
                "pasta": det.get("pasta", ""),
                # De QUEM é a ficha. Sem uso enquanto a lista era só do usuário
                # logado — repetiria o mesmo nome em dez linhas —, e necessário
                # desde que o bloco Histórico da v8 passou a mostrar o serviço
                # inteiro: é a coluna que distingue as duas listas vizinhas.
                "usuario": _nome_usuario(e.get("usuario")),
            })
    return {"recentes": recentes, "hoje": len(de_hoje)}
