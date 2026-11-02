"""Uma sessão por usuário: entrar numa estação encerra a sessão na outra.

Pedido do usuário em 23/09/2026. A mesma conta aberta em duas máquinas é um
problema de rastro antes de ser de segurança: o histórico de uso grava QUEM
marcou o checklist e QUEM gerou a ficha, e com a conta emprestada em duas salas
ao mesmo tempo o nome no registro deixa de responder "quem foi".

O modelo é **o último login vence**, e não "recusar o segundo acesso":

* quem está na frente da máquina nova é quem está trabalhando AGORA, e barrá-lo
  por causa de uma sessão que ficou aberta na sala de comando o deixaria de
  fora do programa sem ter como resolver dali;
* sessão fantasma (queda de energia, app morto no gerenciador de tarefas) não
  tranca ninguém, então este módulo não precisa de heurística de "sessão velha
  demais" nem de batimento de vida para limpá-la.

A estação derrubada **não fecha sozinha**: ela trava e volta ao login (ver
``gui.JanelaPrincipal._conferir_sessao``). Fechar seria o mais fiel ao pedido e
perderia o caso carregado na bancada — e um app que fecha sozinho com trabalho
na tela é exatamente o que a rede de segurança do ``arranque`` veio evitar.

**O admin é isento** (decidido com o usuário): quem configura o serviço precisa
das Configurações abertas numa estação enquanto confere o efeito em outra, e
seria ele mesmo a se derrubar. O modo desenvolvimento (``ISOCENTRO_DEV``) fica de
fora por não passar pelo login.

Módulo de lógica pura (sem Qt), para poder ser testado isoladamente.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import platform
import secrets
import time
import uuid
from pathlib import Path
from typing import Optional

SCHEMA = "isocentro/sessoes"

# Funções que podem ficar abertas em mais de uma estação ao mesmo tempo.
PAPEIS_ISENTOS = ("admin",)

# Ver ``preferencias`` — o mesmo *delete pending* do Windows, os mesmos números.
_REPLACE_TENTATIVAS = 5
_REPLACE_ESPERA_S = 0.05

# A sessão DESTE processo: ``{"usuario": ..., "token": ...}``. ``None`` quando
# ninguém entrou por aqui (modo dev) ou quando o usuário é isento — e é o que
# faz ``minha_vez`` devolver True sem sequer ler o arquivo.
_ATUAL: Optional[dict] = None

_LOG = logging.getLogger(__name__)


def caminho() -> Path:
    """O JSON das sessões: ao lado do ``usuarios.json``, pelo motivo de sempre.

    A lista de usuários já é o arquivo que todas as estações enxergam; uma
    sessão que só a máquina local visse não seria sessão nenhuma.
    """
    from isocentro.dados import auth
    return auth.caminho_usuarios().with_name("sessoes.json")


def _norm(usuario) -> str:
    if isinstance(usuario, dict):
        usuario = usuario.get("usuario")
    return str(usuario or "").strip().lower()


def _papel(usuario) -> str:
    if isinstance(usuario, dict):
        return str(usuario.get("papel") or "").strip().lower()
    return ""


def isento(usuario) -> bool:
    """Este usuário pode ficar aberto em duas estações?

    Decide pelo PAPEL, que só existe no dicionário do login. Um nome solto
    ("geovani.pena") não é isento — e não poderia ser: daria para contornar a
    regra chamando com a string em vez do usuário autenticado.
    """
    return _papel(usuario) in PAPEIS_ISENTOS


def _ler() -> Optional[dict]:
    """O registro de sessões, ou ``None`` quando não deu para saber.

    ``None`` é "não sei", e não "não há": arquivo ausente, ilegível ou rede fora
    do ar caem todos aqui, e ``minha_vez`` trata isso como sessão válida. A
    alternativa — assumir que a sessão acabou — trancaria o serviço inteiro
    fora do programa no dia em que o compartilhamento de rede piscasse, e a
    pessoa na sala de comando não teria o que fazer com esse aviso.
    """
    try:
        d = json.loads(caminho().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        _LOG.exception("Sessões ilegíveis em %s", caminho())
        return None
    if not isinstance(d, dict) or not isinstance(d.get("sessoes"), dict):
        return None
    return d


def _salvar(reg: dict) -> None:
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


def _alterar(fn) -> bool:
    """Roda ``fn(registro)`` e grava, tudo DENTRO da trava entre processos.

    Ler fora da trava e gravar dentro dela é o mesmo que não ter trava: duas
    estações entrando no mesmo segundo leriam o arquivo sem a sessão uma da
    outra e a segunda gravaria por cima — o registro de sessão do primeiro
    sumiria, e ele seria derrubado por um login que nem era dele.
    """
    from isocentro.dados import indice
    p = caminho()
    try:
        with indice.travar_arquivo(p.with_name(p.name + ".lock")):
            reg = _ler() or {"schema": SCHEMA, "sessoes": {}}
            if fn(reg) is False:
                return True          # nada a gravar, e não é falha
            _salvar(reg)
        return True
    except Exception:  # noqa: BLE001
        _LOG.exception("Não foi possível gravar %s", p.name)
        return False


def abrir(usuario) -> str:
    """Torna ESTE processo o dono da sessão de ``usuario``. Devolve o token.

    Devolve string vazia — e desliga a vigilância — quando o usuário é isento
    ou quando a gravação falhou. Falha de escrita não pode virar vigilância:
    sem registro no arquivo, a conferência seguinte não acharia o token deste
    processo e a estação se trancaria sozinha a cada meio minuto.
    """
    global _ATUAL
    nome = _norm(usuario)
    if not nome or isento(usuario):
        _ATUAL = None
        return ""
    token = secrets.token_hex(16)
    entrada = {
        "token": token,
        "maquina": platform.node() or "",
        "pid": os.getpid(),
        "desde": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    def _por(reg: dict) -> None:
        reg["sessoes"][nome] = entrada

    ok = _alterar(_por)
    _ATUAL = {"usuario": nome, "token": token} if ok else None
    return token if ok else ""


def vigilancia_ativa() -> bool:
    """Há uma sessão deste processo para conferir? (isento e dev não têm.)"""
    return bool(_ATUAL and _ATUAL.get("token"))


def minha_vez() -> bool:
    """A sessão registrada ainda é a deste processo?

    ``False`` quer dizer que a conta entrou em outro lugar — é o único
    resultado que derruba a estação, e por isso todo caso duvidoso devolve
    ``True`` (ver ``_ler``).
    """
    if not vigilancia_ativa():
        return True
    reg = _ler()
    if reg is None:
        return True
    dele = reg["sessoes"].get(_ATUAL["usuario"])
    if not isinstance(dele, dict):
        # A entrada existia (este processo a gravou) e não existe mais: outra
        # estação entrou e já saiu. A sessão daqui acabou no primeiro evento.
        return False
    return dele.get("token") == _ATUAL["token"]


def dono(usuario) -> Optional[dict]:
    """Quem está com a sessão: ``{"maquina", "desde", ...}``, ou ``None``.

    É o que a tela de bloqueio mostra. Sem a máquina e a hora, o aviso diz
    apenas que a sessão acabou — e quem o lê não tem como distinguir "entrei na
    sala de comando e esqueci" de "alguém está usando minha conta".
    """
    reg = _ler()
    if reg is None:
        return None
    dele = reg["sessoes"].get(_norm(usuario))
    return dele if isinstance(dele, dict) else None


def fechar() -> None:
    """Encerra a sessão deste processo (no fechamento do app).

    Só apaga se o token no arquivo ainda for o nosso: a estação que JÁ foi
    derrubada também passa por aqui ao fechar, e apagar a entrada alheia
    derrubaria de volta quem acabou de entrar.
    """
    global _ATUAL
    if not vigilancia_ativa():
        _ATUAL = None
        return
    nome, token = _ATUAL["usuario"], _ATUAL["token"]

    def _tirar(reg: dict):
        dele = reg["sessoes"].get(nome)
        if not isinstance(dele, dict) or dele.get("token") != token:
            return False
        reg["sessoes"].pop(nome, None)
        return None

    _alterar(_tirar)
    _ATUAL = None
