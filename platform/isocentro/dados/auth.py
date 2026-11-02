"""Autenticação de usuários do ISOCENTRO.

A lista de usuários vive num JSON COMPARTILHADO — apontado por
``ISOCENTRO_USERS_DIR`` (ex.: um caminho de rede) ou, sem isso, ao lado do índice
central. Assim o admin gerencia uma lista única para todas as estações.

Senhas nunca são guardadas em texto: usa-se PBKDF2-HMAC-SHA256 com salt por
usuário. Papéis: ``admin`` (gerencia usuários) e ``fisico`` (usa o app).

Módulo de lógica pura (sem Qt), para poder ser testado isoladamente.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Optional
from isocentro.dados import ambiente

SCHEMA = "isocentro/usuarios"
_ITERACOES = 200_000
# As funções do serviço, na ordem em que aparecem na tela. A CHAVE é sem acento
# e minúscula porque vai para o JSON de usuários e para o histórico de uso, que
# são lidos por gente e por script; o rótulo bonito fica na tela (ver
# ``administracao._FUNCAO_LABEL``).
#
# A função decide DUAS coisas, e só duas:
#
# * as Configurações, que são de "admin" e de mais ninguém (ver ``gui``);
# * QUAIS ABAS a pessoa vê, pelo ``fichinha.modos_do_papel`` — o médico vê só a
#   Virtual, o dosimetrista vê Capa-Up e Virtual, e assim por diante.
#
# Fora isso, papel não barra nada: quem alcança uma tela faz nela tudo o que a
# tela faz. Recortar a faixa não é controle de acesso — é tirar da frente o que
# aquela função não usa.
#
# ACRESCENTAR UM PAPEL AQUI NÃO O ENSINA A NINGUÉM: sem entrada no
# ``fichinha.MODOS_POR_PAPEL`` ele cai no padrão, e sem rótulo no
# ``administracao._FUNCAO_LABEL`` aparece com a chave crua na tela. São três
# lugares, de propósito — quais abas alguém vê é decisão que se toma, não
# efeito colateral de cadastrar uma função.
PAPEIS = ("admin", "fisico", "medico", "dosimetrista", "tecnico",
          "enfermeiro", "recepcionista")


# ── Localização e IO ─────────────────────────────────────────────────────────

def caminho_usuarios() -> Path:
    """JSON de usuários: ``ISOCENTRO_USERS_DIR`` ou ao lado do índice central."""
    env = ambiente.ler("ISOCENTRO_USERS_DIR")
    if env:
        base = Path(env)
    else:
        try:
            from isocentro.dados import indice
            base = indice._app_dir()
        except Exception:  # noqa: BLE001
            base = Path(".")
    return base / "usuarios.json"


def _carregar() -> dict:
    p = caminho_usuarios()
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("usuarios", [])
                return d
        except Exception:  # noqa: BLE001
            pass
    return {"schema": SCHEMA, "usuarios": []}


def _salvar(reg: dict) -> None:
    p = caminho_usuarios()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


# ── Hash de senha ────────────────────────────────────────────────────────────

def _hash(senha: str, salt_hex: str, iters: int = _ITERACOES) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", (senha or "").encode("utf-8"),
                             bytes.fromhex(salt_hex), iters)
    return dk.hex()


def _novo_segredo(senha: str) -> dict:
    salt = secrets.token_hex(16)
    return {"salt": salt, "hash": _hash(senha, salt), "iteracoes": _ITERACOES}


# ── Consulta ─────────────────────────────────────────────────────────────────

def _norm(usuario: str) -> str:
    return (usuario or "").strip().lower()


def _achar(reg: dict, usuario: str) -> Optional[dict]:
    alvo = _norm(usuario)
    return next((u for u in reg["usuarios"] if _norm(u.get("usuario")) == alvo), None)


def listar() -> list[dict]:
    """Usuários (sem os campos de senha), ordenados por nome de usuário."""
    reg = _carregar()
    saida = [{"usuario": u.get("usuario"), "nome": u.get("nome", ""),
              "papel": u.get("papel", "fisico"), "ativo": u.get("ativo", True),
              "trocar_senha": u.get("trocar_senha", False)}
             for u in reg["usuarios"]]
    return sorted(saida, key=lambda u: _norm(u["usuario"]))


def existe(usuario: str) -> bool:
    return _achar(_carregar(), usuario) is not None


# ── Mutação ──────────────────────────────────────────────────────────────────

def criar(usuario: str, nome: str, senha: str, papel: str = "fisico",
          trocar_senha: bool = False) -> None:
    if not _norm(usuario):
        raise ValueError("Usuário vazio.")
    if papel not in PAPEIS:
        raise ValueError(f"Papel inválido: {papel!r}")
    reg = _carregar()
    if _achar(reg, usuario) is not None:
        raise ValueError(f"Usuário já existe: {usuario}")
    novo = {"usuario": usuario.strip(), "nome": (nome or "").strip(),
            "papel": papel, "ativo": True, "trocar_senha": bool(trocar_senha)}
    novo.update(_novo_segredo(senha))
    reg["usuarios"].append(novo)
    _salvar(reg)


class SemAdministrador(ValueError):
    """A ação deixaria o serviço sem nenhum administrador ativo."""


def _seria_o_ultimo_admin(reg: dict, usuario: str) -> bool:
    """A ação sobre ``usuario`` apagaria o ÚLTIMO administrador ativo?"""
    admins = [u for u in reg["usuarios"]
              if u.get("papel") == "admin" and u.get("ativo", True)]
    return len(admins) == 1 and _norm(admins[0].get("usuario")) == _norm(usuario)


def _guardar_o_ultimo_admin(reg: dict, usuario: str, acao: str) -> None:
    """Recusa a ação se ela deixaria o serviço sem administrador.

    Fica AQUI, e não na tela, porque é invariante do serviço e não regra de
    interface: três caminhos levavam ao mesmo buraco — rebaixar a função,
    desativar e remover — e proteger só o que tem botão deixaria os outros dois
    abertos para qualquer chamador.

    O programa não ficava inutilizável sem admin: o ``semear_admin_se_vazio``
    recria ``admin/admin`` na abertura seguinte. Mas isso é uma REGRESSÃO DE
    SEGURANÇA — volta a senha trivial num sistema que guarda dado de paciente —
    e acontecia calado, na próxima vez que alguém abrisse o programa, longe do
    clique que causou. Com duas funções errar era difícil; com sete, não é.
    """
    if _seria_o_ultimo_admin(reg, usuario):
        raise SemAdministrador(
            f"{usuario} é o único administrador ativo. {acao} deixaria o "
            "serviço sem ninguém para abrir as Configurações. Promova outra "
            "pessoa a Administrador antes.")


def remover(usuario: str) -> None:
    reg = _carregar()
    _guardar_o_ultimo_admin(reg, usuario, "Remover")
    antes = len(reg["usuarios"])
    reg["usuarios"] = [u for u in reg["usuarios"]
                       if _norm(u.get("usuario")) != _norm(usuario)]
    if len(reg["usuarios"]) != antes:
        _salvar(reg)


def redefinir_senha(usuario: str, nova: str, trocar_senha: bool = False) -> None:
    reg = _carregar()
    u = _achar(reg, usuario)
    if u is None:
        raise ValueError(f"Usuário não encontrado: {usuario}")
    u.update(_novo_segredo(nova))
    u["trocar_senha"] = bool(trocar_senha)
    _salvar(reg)


def definir_ativo(usuario: str, ativo: bool) -> None:
    reg = _carregar()
    u = _achar(reg, usuario)
    if u is None:
        raise ValueError(f"Usuário não encontrado: {usuario}")
    if not ativo:
        _guardar_o_ultimo_admin(reg, usuario, "Desativar")
    u["ativo"] = bool(ativo)
    _salvar(reg)


def definir_papel(usuario: str, papel: str) -> None:
    if papel not in PAPEIS:
        raise ValueError(f"Papel inválido: {papel!r}")
    reg = _carregar()
    u = _achar(reg, usuario)
    if u is None:
        raise ValueError(f"Usuário não encontrado: {usuario}")
    if papel != "admin":
        _guardar_o_ultimo_admin(reg, usuario, f"Passar para {papel}")
    u["papel"] = papel
    _salvar(reg)


# ── Autenticação ─────────────────────────────────────────────────────────────

def verificar(usuario: str, senha: str) -> Optional[dict]:
    """Devolve o usuário (sem senha) se as credenciais baterem e estiver ativo."""
    u = _achar(_carregar(), usuario)
    if u is None or not u.get("ativo", True):
        return None
    esperado = u.get("hash", "")
    calc = _hash(senha, u.get("salt", ""), int(u.get("iteracoes", _ITERACOES)))
    if not esperado or not hmac.compare_digest(esperado, calc):
        return None
    return {"usuario": u.get("usuario"), "nome": u.get("nome", ""),
            "papel": u.get("papel", "fisico"),
            "trocar_senha": u.get("trocar_senha", False)}


def ha_admin_ativo() -> bool:
    return any(u.get("papel") == "admin" and u.get("ativo", True)
               for u in _carregar()["usuarios"])


def semear_admin_se_vazio() -> bool:
    """Cria o admin inicial (admin/admin, troca obrigatória) se não houver admin.

    Devolve True se semeou. A senha padrão é intencionalmente trivial e o
    ``trocar_senha`` força a troca no 1º login.
    """
    if ha_admin_ativo():
        return False
    if existe("admin"):
        # há um 'admin' inativo/sem papel admin — reativa como admin.
        redefinir_senha("admin", "admin", trocar_senha=True)
        definir_papel("admin", "admin")
        definir_ativo("admin", True)
    else:
        criar("admin", "Administrador", "admin", papel="admin", trocar_senha=True)
    return True
