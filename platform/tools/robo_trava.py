#!/usr/bin/env python
"""Gancho PreToolUse do robô: recusa editar o que só muda com gente olhando.

Por que existe: o `tools/robo.py` roda sessões sem ninguém na frente, e três
regras do CLAUDE.md pressupõem alguém — mudança no papel se AVISA antes,
layout novo se ACEITA antes, e cálculo chega ao paciente. Uma instrução no
prompt pedindo "não mexa em papel/" é o tipo de regra que depende de lembrar;
este gancho é o que não depende.

Ele NÃO é a única trava, e não pode ser: um `python -c` que grava arquivo passa
por baixo de qualquer gancho de Edit. A segunda trava é o `robo.py` conferir o
DIFF depois da sessão, e é por isso que o push é dele, não da sessão.

Fica em `tools/` e não em `.claude/hooks/` de propósito: o `.claude/` é
ignorado pelo git, e trava que some numa estação nova não trava nada.

Só age com `ISOCENTRO_ROBO=1` — a mesma configuração carregada numa sessão
normal não pode travar o usuário.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from isocentro.dados import ambiente  # noqa: E402

# O que muda só com gente olhando (ver o DESTINO.md, "Por que o robô não anda
# em tudo"). Prefixos relativos à raiz do repositório, em forma POSIX.
TRAVADAS = (
    "isocentro/papel/",
    "isocentro/interface/",
    "isocentro/dominio/",
)

# O robô não edita a própria coleira: nem a trava, nem o laço que o confere,
# nem a configuração da sessão. `.claude/` inclui os ganchos e os comandos.
PROPRIAS = (
    "tools/robo.py",
    "tools/robo_trava.py",
    "tools/robo_settings.json",
    ".claude/",
)

_FERRAMENTAS_DE_ESCRITA = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def relativo(caminho: str, raiz: Path) -> str | None:
    """Caminho relativo à raiz, em POSIX; None se estiver FORA dela.

    Fora da raiz é recusado por si: o worktree do robô fica ao lado do checkout
    do usuário, e um caminho absoluto para `..\\isocentro\\` editaria a `main`
    debaixo do VSCode.
    """
    try:
        alvo = Path(caminho)
        if not alvo.is_absolute():
            alvo = raiz / alvo
        rel = alvo.resolve().relative_to(raiz.resolve())
    except (ValueError, OSError):
        return None
    return str(PurePosixPath(*rel.parts))


def travado(rel: str) -> str | None:
    """O motivo, se o caminho relativo cai numa pasta travada; senão None."""
    # Comparação sem caixa: no Windows `ISOCENTRO/Papel/x.py` é o mesmo
    # arquivo, e um prefixo sensível a caixa deixaria passar a mesma edição.
    baixo = rel.lower()
    for prefixo in TRAVADAS:
        if baixo.startswith(prefixo):
            return (
                f"`{rel}` está em `{prefixo}`, que o robô não edita: papel muda "
                "com aviso, tela com aceite, cálculo chega ao paciente. "
                "Estacione a frente (ROBO: ESTACIONADA) e descreva o que "
                "precisaria mudar."
            )
    for prefixo in PROPRIAS:
        if baixo == prefixo or baixo.startswith(prefixo):
            return f"`{rel}` é a configuração do próprio robô; não se edita de dentro dele."
    return None


def ligada() -> bool:
    """A trava só vale dentro do robô (`ISOCENTRO_ROBO=1`, que o
    `tools/robo_settings.json` define para a sessão)."""
    return ambiente.ler("ISOCENTRO_ROBO") == "1"


def decidir(ferramenta: str, entrada: dict, raiz: Path) -> str | None:
    """Motivo da recusa, ou None para deixar passar."""
    if ferramenta not in _FERRAMENTAS_DE_ESCRITA:
        return None
    caminho = entrada.get("file_path") or entrada.get("notebook_path") or ""
    if not caminho:
        return None
    rel = relativo(caminho, raiz)
    if rel is None:
        return f"`{caminho}` está fora do worktree do robô ({raiz})."
    return travado(rel)


def main() -> int:
    if not ligada():
        return 0
    try:
        evento = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    raiz = Path(os.environ.get("CLAUDE_PROJECT_DIR") or evento.get("cwd") or ".")
    motivo = decidir(evento.get("tool_name", ""), evento.get("tool_input") or {}, raiz)
    if motivo:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": motivo,
            }
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
