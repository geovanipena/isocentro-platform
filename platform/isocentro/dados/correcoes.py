"""Correções de cadastro feitas à mão na Capa — e que precisam durar.

Os três relatórios que alimentam a capa (ver :mod:`capa_dados`) são **lidos,
nunca escritos**: são retratos do dia em que foram exportados. Quando o
cadastro traz o sexo errado, o convênio antigo ou o nome grafado de outro jeito,
quem corrige é a pessoa que está montando a ficha — e, até aqui, essa correção
morria no fechamento da tela. O paciente reaberto amanhã voltava errado, e
alguém corrigia de novo. Toda vez.

Este módulo é onde a correção fica. Um JSON por serviço, ao lado do índice
central, com uma entrada por paciente:

    {"pacientes": {"9000016BET": {"campos": {"sexo": "Feminino"},
                                  "por": "geovani", "em": "2026-08-13T14:07:00"}}}

**Só o que foi realmente mudado entra.** Guardar a linha inteira do relatório
transformaria a correção num segundo cadastro, que envelheceria em silêncio: o
convênio mudaria na fonte e a capa continuaria imprimindo o de um ano atrás
porque alguém, um dia, corrigiu o sexo. Guardando só o campo tocado, tudo o
mais continua vindo do relatório e acompanhando as atualizações dele.

Quem fez e quando ficam junto — é dado de paciente que sobrescreve o sistema
oficial, e isso não pode ser anônimo.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from contextlib import contextmanager, nullcontext
from pathlib import Path
from isocentro.dados import ambiente

_LOG = logging.getLogger(__name__)

# Campos que a tela deixa corrigir. O REGISTRO não entra: ele é a chave da
# entrada, e "corrigir" a chave seria criar outra pessoa.
CAMPOS = ("nome", "nascimento", "sexo", "convenio", "contato", "medico",
          "maquina")

_ENV = "ISOCENTRO_CORRECOES"
_ARQUIVO = "correcoes_capa.json"


@contextmanager
def _travado():
    """Trava o arquivo de correções durante ler→alterar→gravar.

    Mesmo problema do índice central, mesma solução: duas estações corrigindo
    pacientes DIFERENTES ao mesmo tempo liam o mesmo JSON e gravavam por cima
    uma da outra — a escrita atômica não salva, porque cada uma grava um arquivo
    íntegro, só que sem a correção da outra, e a que perde some sem aviso.

    Reaproveita ``indice.travar_arquivo`` (lock do SO sobre um ``.lock`` que
    nunca é apagado; ver a explicação lá). Sem o ``indice`` por perto, grava sem
    exclusão em vez de recusar: perder a corrida é raro, não gravar é certo.
    """
    try:
        from isocentro.dados import indice
        trava = indice.travar_arquivo(caminho().with_suffix(".json.lock"))
    except Exception:  # noqa: BLE001
        trava = nullcontext()
    with trava:
        yield


def caminho() -> Path:
    """Arquivo das correções: ``ISOCENTRO_CORRECOES`` ou ao lado do índice.

    Mesma convenção do histórico de uso: a correção vale para o SERVIÇO, não
    para a estação em que foi digitada — quem corrigir numa máquina tem de ver
    o efeito na outra.
    """
    env = ambiente.ler(_ENV)
    if env:
        return Path(env) / _ARQUIVO
    try:
        from isocentro.dados import indice
        return indice._app_dir() / _ARQUIVO
    except Exception:  # noqa: BLE001
        return Path(".") / _ARQUIVO


def _chave(registro: str) -> str:
    try:
        from isocentro.banco import capa_dados
        return capa_dados.normalizar_id(registro)
    except Exception:  # noqa: BLE001
        return str(registro or "").strip().upper()


def _carregar() -> dict:
    p = caminho()
    if not p.exists():
        return {"schema": "isocentro/correcoes-capa", "pacientes": {}}
    try:
        dados = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            dados.setdefault("pacientes", {})
            return dados
    except Exception:  # noqa: BLE001 — arquivo corrompido não derruba a capa
        _LOG.exception("Correções da capa ilegíveis em %s", p)
    return {"schema": "isocentro/correcoes-capa", "pacientes": {}}


def _salvar_tudo(dados: dict) -> None:
    """Grava de forma ATÔMICA: temporário na mesma pasta + ``os.replace``.

    Escrever direto deixava uma janela em que o arquivo estava pela metade, e
    ``_carregar`` cai em silêncio para "nenhuma correção" — as correções de
    todos os pacientes sumiriam sem erro nenhum na tela.
    """
    p = caminho()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ler(registro: str) -> dict:
    """As correções gravadas para este paciente ({} se não houver)."""
    chave = _chave(registro)
    if not chave:
        return {}
    entrada = _carregar()["pacientes"].get(chave) or {}
    campos = entrada.get("campos") or {}
    return {k: v for k, v in campos.items() if k in CAMPOS}


def autoria(registro: str) -> tuple[str, str]:
    """``(quem, quando)`` da última correção deste paciente."""
    entrada = _carregar()["pacientes"].get(_chave(registro)) or {}
    return str(entrada.get("por", "")), str(entrada.get("em", ""))


def salvar(registro: str, campos: dict, usuario: str = "") -> dict:
    """Grava as correções deste paciente. Devolve o que ficou gravado.

    ``campos`` traz SÓ o que diverge do relatório — quem decide isso é a tela,
    que tem as duas versões à mão. Campo com valor vazio APAGA a correção: é
    assim que se desfaz uma correção errada, voltando ao que o relatório diz.
    """
    chave = _chave(registro)
    if not chave:
        return {}
    # Ler DENTRO da trava: entre ler e gravar cabe a gravação de outra estação,
    # e o que se grava aqui é o arquivo inteiro.
    with _travado():
        dados = _carregar()
        atual = dict((dados["pacientes"].get(chave) or {}).get("campos") or {})
        for nome, valor in (campos or {}).items():
            if nome not in CAMPOS:
                continue
            valor = str(valor or "").strip()
            if valor:
                atual[nome] = valor
            else:
                atual.pop(nome, None)
        if atual:
            dados["pacientes"][chave] = {
                "campos": atual,
                "por": str(usuario or ""),
                "em": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        else:
            # Sem nenhuma divergência, a entrada some: paciente sem correção não
            # deve deixar rastro num arquivo que se lê a cada capa.
            dados["pacientes"].pop(chave, None)
        _salvar_tudo(dados)
    return atual


def aplicar(capa) -> list[str]:
    """Escreve as correções deste paciente por cima da capa. Devolve os campos.

    Chamada logo depois de a capa nascer do relatório: o que a pessoa corrigiu
    vale mais que o retrato exportado, que é justamente o que estava errado.
    """
    corr = ler(getattr(capa, "registro", ""))
    aplicados = []
    for nome, valor in corr.items():
        if getattr(capa, nome, None) != valor:
            setattr(capa, nome, valor)
            aplicados.append(nome)
    return aplicados
