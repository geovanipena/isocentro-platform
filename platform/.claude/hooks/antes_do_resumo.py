"""Grava o estado CRU em disco antes de o contexto ser resumido.

O resumo automático guarda a conclusão e descarta o porquê — que é justamente
o que este projeto anota: "o que quebrou quando era de outro jeito". Depois de
um `/compact` no meio de uma frente, o que sobra é o veredito sem a armadilha,
e o registro vencido nasce assim: parece certo.

Duas defesas, porque uma delas depende de eu obedecer e a outra não:

1. **Em disco, sempre** — `.claude/estado/antes_do_resumo.md` com o `git status`
   e o `git diff --stat` da hora. Não é bonito, mas sobrevive a qualquer resumo
   e a qualquer queda, que é o requisito.
2. **No contexto** — o pedido de gravar o checkpoint de verdade no `NOTAS.md`,
   com as quatro partes do `/checkpoint`. Este é o que envelhece bem; o outro é
   a rede de segurança embaixo dele.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / ".claude" / "estado" / "antes_do_resumo.md"


def _git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=RAIZ, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    # "auto" = o contexto encheu; "manual" = alguém digitou /compact.
    gatilho = payload.get("trigger", "?")

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    status = _git("status", "--short")
    stat = _git("diff", "--stat")
    stat_cache = _git("diff", "--cached", "--stat")

    try:
        DESTINO.parent.mkdir(parents=True, exist_ok=True)
        DESTINO.write_text(
            f"# Estado em {agora} (antes do resumo — gatilho: {gatilho})\n\n"
            f"Branch `{branch}`.\n\n"
            f"## git status --short\n\n```\n{status or '(limpa)'}\n```\n\n"
            f"## git diff --stat\n\n```\n{stat or '(nada)'}\n```\n\n"
            f"## git diff --cached --stat\n\n```\n{stat_cache or '(nada)'}\n```\n\n"
            "Arquivo sobrescrito a cada resumo. Serve para responder "
            "*o que eu estava mexendo* quando o resumo apagou o detalhe.\n",
            encoding="utf-8",
        )
        gravado = str(DESTINO.relative_to(RAIZ))
    except Exception as erro:  # gancho não derruba sessão
        gravado = f"(falhou: {erro})"

    aviso = (
        "## Antes de resumir (gancho `antes_do_resumo.py`)\n\n"
        f"O estado cru foi gravado em `{gravado}`.\n\n"
        "**Agora grave o checkpoint de verdade no `NOTAS.md`**, no topo, com as "
        "quatro partes do `/checkpoint`: o que está feito, o que falta (o próximo "
        "passo concreto, não \"continuar\"), as decisões já tomadas e por quê, e as "
        "armadilhas pagas nesta etapa. O resumo que vem a seguir guarda a conclusão "
        "e perde o porquê — e o porquê é o que este projeto anota.\n\n"
        "Se a frente já fechou e a suíte passou, o certo não é resumir: é `/fechar` "
        "e `/clear`. Retomar de um checkpoint bom custa uns 3 mil tokens."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreCompact",
            "additionalContext": aviso,
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
