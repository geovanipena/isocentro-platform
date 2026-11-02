"""Avisa quando a sessão passou do ponto de fechar — a mim, não só à barra.

A decisão de 08/09/2026 continua de pé: **não existe `/clear` automático**. O
que dá para automatizar é *saber a hora*, e a `barra_de_estado.py` já mostra o
percentual e o `→ /fechar` em vermelho. Só que a barra é uma linha na tela do
usuário: ela avisa quem está olhando para ela. Quem arrasta a sessão sem
perceber é o assistente — e a barra não fala comigo.

Este gancho fala. No `UserPromptSubmit`, quando o contexto cruza o limiar, ele
injeta UMA linha pedindo que eu proponha o `/fechar` antes de abrir frente
nova. Não bloqueia nada e não fecha nada: a decisão continua sendo do usuário,
que é quem sabe se o trabalho da vez cabe no que sobra.

Custo: zero token abaixo do limiar (não imprime nada) e ~60 tokens no aviso, uma
vez por faixa. É o contrário de repetir a regra em todo turno no `CLAUDE.md`,
que era a alternativa — aquela se paga sempre, esta se paga quando importa.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contexto import JANELA, LIMIAR, percentual  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
ESTADO = RAIZ / ".claude" / "estado"

# Duas faixas, e não uma: no limiar o fechamento ainda é escolha; perto do fim
# ele é a única coisa que ainda cabe. Avisar de novo aos 90% não é insistência,
# é outra mensagem.
FAIXAS = (LIMIAR, 90)


def _ja_avisado(sessao: str) -> set[int]:
    marca = ESTADO / f"ctx_{sessao}.txt"
    if not marca.is_file():
        return set()
    try:
        return {int(n) for n in marca.read_text(encoding="utf-8").split()}
    except Exception:
        return set()


def _limpar_marcas_velhas() -> None:
    """Uma marca por sessão fica para sempre, e sessão nasce todo dia. Sete dias
    é mais do que qualquer sessão viva e menos do que um diretório entulhado."""
    try:
        limite = time.time() - 7 * 86400
        for marca in ESTADO.glob("ctx_*.txt"):
            if marca.stat().st_mtime < limite:
                marca.unlink()
    except Exception:
        pass


def _marcar(sessao: str, faixas: set[int]) -> None:
    try:
        ESTADO.mkdir(parents=True, exist_ok=True)
        _limpar_marcas_velhas()
        (ESTADO / f"ctx_{sessao}.txt").write_text(
            " ".join(str(f) for f in sorted(faixas)), encoding="utf-8")
    except Exception:
        pass  # aviso perdido é barato; gancho que derruba o turno, não


def _arvore_suja() -> tuple[int, int]:
    """(arquivos modificados, minutos do mais antigo) — ou (0, 0) se não der.

    O aviso de contexto sabia a hora de fechar e não sabia o que havia a perder,
    e é isso que muda a decisão: fechar com a árvore limpa é `/clear`, fechar
    com nove arquivos conferidos e não commitados é o trabalho da sessão inteira
    pendurado num turno que pode não vir. Quatro sessões de agosto e setembro
    acabaram exatamente assim — teto de uso ou erro 529 com o commit inacabado,
    uma delas com a suíte já rodada.
    """
    try:
        saida = subprocess.run(
            ["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True,
            text=True, timeout=5,
        )
        if saida.returncode != 0:
            return 0, 0
        arquivos = [
            linha[3:].strip().strip('"')
            for linha in saida.stdout.splitlines() if linha.strip()
        ]
        if not arquivos:
            return 0, 0
        agora = time.time()
        idades = [
            agora - (RAIZ / a).stat().st_mtime
            for a in arquivos if (RAIZ / a).is_file()
        ]
        return len(arquivos), int(max(idades) // 60) if idades else 0
    except Exception:
        return 0, 0  # medida perdida é barata; gancho que derruba o turno, não


def main() -> int:
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0

    sessao = str(d.get("session_id") or "sem_id")
    ctx, pct = percentual(str(d.get("transcript_path", "")))
    if not ctx:
        return 0

    avisadas = _ja_avisado(sessao)
    cruzadas = {f for f in FAIXAS if pct >= f}
    novas = cruzadas - avisadas
    if not novas:
        return 0
    _marcar(sessao, cruzadas | avisadas)

    faixa = max(novas)
    if faixa >= 90:
        texto = (
            f"**Contexto em {pct}%** ({ctx // 1000}k de {JANELA // 1000}k). Acima "
            "de 90% a suíte, o checkpoint e o commit já disputam espaço com o "
            "trabalho: propor o `/fechar` AGORA, antes do próximo arquivo aberto."
        )
    else:
        texto = (
            f"**Contexto em {pct}%** ({ctx // 1000}k de {JANELA // 1000}k). É a "
            "faixa em que fechar ainda é barato. Se a frente da sessão já está "
            "conferida, propor o `/fechar` (suíte → checkpoint → commit) e o "
            "`/clear` em vez de abrir assunto novo: daqui para cima cada turno "
            "relê o equivalente a 15 mil tokens de entrada, só de contexto. A "
            "decisão é do usuário — isto é um lembrete, não um bloqueio."
        )

    sujos, minutos = _arvore_suja()
    if sujos:
        idade = f", o mais antigo há {minutos} min" if minutos >= 5 else ""
        texto += (
            f"\n\n**E há {sujos} arquivo(s) modificados na árvore**{idade}. "
            "Commitar o que já está conferido ANTES de seguir: quatro sessões "
            "morreram no limite com o commit inacabado, uma delas com a suíte "
            "já rodada. Commit em checkpoint custa um minuto; refazer o "
            "contexto custa a sessão."
        )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                "## Aviso do gancho `limite_de_contexto.py` (não é pedido do usuário)\n\n"
                + texto
            ),
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
