"""Preferências de tela guardadas POR USUÁRIO DO APP, não por estação.

O que a pessoa escolhe e não quer reescolher — hoje, os médicos do painel da
Ficha Virtual (o Grupo Médico) — vive num JSON ao lado do ``usuarios.json``,
que já é compartilhado por todas as estações. Assim a escolha viaja com o
LOGIN: o médico monta o grupo no consultório e o encontra pronto na sala de
comando, porque quem é lido é ele, não a máquina.

Antes isso era ``QSettings``, e ``QSettings`` no Windows é
``HKEY_CURRENT_USER``: valia para um usuário do Windows, numa máquina só. Duas
pessoas que dividem a mesma estação dividiam a mesma escolha, e a mesma pessoa
em duas estações tinha duas. É a armadilha que já tinha tirado a pasta do
serviço de lá (ver ``config_servico``).

**Isto não é configuração do serviço.** Nada aqui muda o que o app faz para os
outros; se o arquivo sumir, a pessoa reescolhe e segue. Por isso toda falha de
leitura ou de escrita é engolida com registro no log — preferência que não
persiste é um aborrecimento, preferência que impede de trabalhar é um defeito.

Módulo de lógica pura (sem Qt), para poder ser testado isoladamente.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA = "isocentro/preferencias"

# Quantas vezes insistir no ``os.replace`` e o intervalo entre as tentativas —
# os mesmos números de ``config_servico``, e pelo mesmo motivo medido lá: no
# Windows, arquivo recém-apagado fica em *delete pending* e o acesso seguinte
# recebe ``PermissionError`` em vez de "não existe". A disputa passa em
# milissegundos.
_REPLACE_TENTATIVAS = 5
_REPLACE_ESPERA_S = 0.05

_LOG = logging.getLogger(__name__)


def caminho() -> Path:
    """O JSON das preferências: sempre ao lado do ``usuarios.json``.

    Derivado do caminho do ``auth``, e não com uma cópia da regra dele: os dois
    arquivos falam do mesmo usuário e têm de morar juntos. Com a regra
    duplicada, apontar ``ISOCENTRO_USERS_DIR`` para a rede levaria a lista de
    usuários e deixaria as preferências para trás — sem erro nenhum na tela.
    """
    from isocentro.dados import auth
    return auth.caminho_usuarios().with_name("preferencias.json")


def _norm(usuario) -> str:
    """A chave do usuário no JSON: minúscula e sem espaços, como no ``auth``."""
    if isinstance(usuario, dict):
        usuario = usuario.get("usuario")
    return str(usuario or "").strip().lower()


def _carregar() -> dict:
    p = caminho()
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("usuarios"), dict):
            return d
    except FileNotFoundError:
        pass
    except Exception:  # noqa: BLE001 — ilegível ou inválido: começa do zero
        _LOG.exception("Preferências ilegíveis em %s", p)
    return {"schema": SCHEMA, "usuarios": {}}


def _salvar(reg: dict) -> None:
    """Escrita atômica: o arquivo é compartilhado e nunca pode ficar truncado.

    Só o PID no nome do temporário não basta — duas gravações do MESMO processo
    escreveriam no mesmo arquivo, e a segunda truncaria o que a primeira ainda
    está usando (medido em ``config_servico._gravar``).
    """
    p = caminho()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(p) + f".{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        for tentativa in range(_REPLACE_TENTATIVAS):
            try:
                os.replace(tmp, p)
                return
            except PermissionError:
                if tentativa == _REPLACE_TENTATIVAS - 1:
                    raise
                time.sleep(_REPLACE_ESPERA_S)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def ler(usuario, chave: str, padrao: Any = None) -> Any:
    """A preferência de ``usuario``, ou ``padrao`` se ele nunca escolheu."""
    chave_u = _norm(usuario)
    if not chave_u:
        return padrao
    dele = _carregar()["usuarios"].get(chave_u)
    if not isinstance(dele, dict) or chave not in dele:
        return padrao
    return dele[chave]


def gravar(usuario, chave: str, valor: Any) -> None:
    """Grava a preferência de ``usuario`` (best-effort; nunca levanta).

    Leitura e escrita acontecem DENTRO do lock de arquivo, e não em volta dele:
    o arquivo é um só para o serviço inteiro, e duas estações gravando
    preferências diferentes no mesmo segundo — o que acontece de manhã, quando
    todo mundo abre o programa — sobrescreveriam uma à outra se cada uma
    gravasse por cima do que leu antes de esperar a vez.
    """
    chave_u = _norm(usuario)
    if not chave_u:
        return
    from isocentro.dados import indice
    # A trava é um arquivo SEPARADO (``.lock``), como em todo JSON
    # compartilhado daqui. Travar o próprio JSON quebraria o ``os.replace`` da
    # gravação: no Windows não se substitui um arquivo que está aberto.
    p = caminho()
    try:
        with indice.travar_arquivo(p.with_name(p.name + ".lock")):
            reg = _carregar()
            dele = reg["usuarios"].setdefault(chave_u, {})
            if chave in dele and dele[chave] == valor:
                return          # nada mudou: não paga a escrita na rede
            dele[chave] = valor
            _salvar(reg)
    except Exception:  # noqa: BLE001
        # Pasta somente-leitura, rede fora do ar, disco cheio: a escolha vale
        # para esta sessão e só não sobrevive a ela.
        _LOG.exception("Não foi possível gravar a preferência %r de %s",
                       chave, chave_u)
