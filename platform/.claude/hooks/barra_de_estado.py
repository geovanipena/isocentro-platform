"""Barra de estado: quanto do contexto já foi gasto, e se há checkpoint pendente.

"Conferir medindo, não lendo" vale também para a própria sessão. A regra
"uma frente por sessão, depois `/clear`" existia sem instrumento: a hora de
fechar era adivinhada, e adivinhar erra para o lado caro — a sessão arrasta,
e cada turno arrastado paga o contexto inteiro de novo.

O número sai do próprio transcript (`usage` da última resposta), que é a
medida real do que o servidor recebeu, não uma estimativa minha. Lê só o FIM
do arquivo: o transcript de uma sessão longa passa de 8 MB e isto roda a cada
atualização de tela.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contexto import LIMIAR, percentual  # noqa: E402

VERDE, AMARELO, VERMELHO, CINZA, NEGRITO, FIM = (
    "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[1m", "\033[0m",
)


def _git(raiz: str, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=raiz, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def main() -> int:
    try:
        d = json.load(sys.stdin)
    except Exception:
        d = {}

    raiz = (d.get("workspace") or {}).get("project_dir") or os.getcwd()
    # Caminho que não existe (formato POSIX vindo de um shell Git Bash, sessão
    # remota) faria todo `git` daqui falhar em silêncio, e a barra apareceria
    # sem branch — parecendo repositório limpo, que é a leitura errada.
    if not os.path.isdir(raiz):
        raiz = os.getcwd()
    peças: list[str] = []

    branch = _git(raiz, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        peças.append(f"{NEGRITO}{branch}{FIM}")

    sujos = [ln for ln in _git(raiz, "status", "--porcelain").splitlines() if ln.strip()]
    if sujos:
        peças.append(f"{AMARELO}✎{len(sujos)}{FIM}")

    ctx, pct = percentual(d.get("transcript_path", ""))
    if ctx:
        # O limiar (75% por padrão, em `contexto.LIMIAR`) é onde ainda dá
        # para fechar com calma: rodar a suíte, gravar o
        # checkpoint e commitar cabem no que sobra. Acima disso o fechamento
        # começa a competir com o trabalho.
        cor = VERDE if pct < 50 else (AMARELO if pct < LIMIAR else VERMELHO)
        peças.append(f"{cor}ctx {ctx // 1000}k · {pct}%{FIM}")
        if pct >= LIMIAR:
            peças.append(f"{VERMELHO}{NEGRITO}→ /fechar{FIM}")

    # Trabalho na árvore sem o NOTAS.md tocado: é o estado que a queda de
    # conexão converte em prejuízo, e o único que a barra pode acusar sozinha.
    if sujos and not any(ln.endswith("NOTAS.md") for ln in sujos):
        peças.append(f"{CINZA}sem checkpoint{FIM}")

    print(f" {CINZA}·{FIM} ".join(peças) or f"{CINZA}—{FIM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
