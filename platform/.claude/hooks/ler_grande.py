"""Barra a leitura CEGA de arquivo grande — a armadilha mais cara desta base.

O `CLAUDE.md` manda usar o `tools/mapa.py` antes de qualquer arquivo com mais
de mil linhas, e a regra é boa: `mapa.py gui.py --buscar trocar_modo` devolve
70 linhas em vez de 5.653. Só que ela dependia de eu LEMBRAR, e o preço de
esquecer não é o de uma leitura: cada turno reenvia o contexto inteiro, então
abrir o `gui.py` no quinto turno custa ~60 mil tokens VEZES todos os turnos que
vierem depois. Em 08/09/2026 uma manhã rendeu pouco e gastou muito exatamente
por isso.

Cobre os dois caminhos por onde o deslize acontece: a ferramenta `Read` sem
recorte e o `cat` no Bash. Não bloqueia o que já vem recortado (`offset`/`limit`,
`sed -n`, qualquer coisa com cano) — só a leitura inteira e cega.

Não é proibição: é a pergunta "você quer mesmo 60 mil tokens?" feita ANTES,
que é a única hora em que ela ainda é barata.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Toda recusa vira uma linha aqui. Existe porque o teto de 800 foi ESCOLHIDO,
# não medido — e o `NOTAS.md` de 08/09/2026 deixou a conferência por conta do
# uso ("se o `ler_grande.py` recusar algo legítimo com frequência, o teto é que
# está errado"). Uso que ninguém anota vira impressão, e impressão não corrige
# número: `python .claude/hooks/ler_grande.py --relatorio` lê este arquivo e
# responde com a contagem por arquivo recusado.
REGISTRO = RAIZ / ".claude" / "estado" / "recusas_leitura.tsv"

# Abaixo disto a leitura inteira é mais barata que a conversa sobre ela.
# 800 põe o `NOTAS.md` (451) e o `ui.py` de folga do lado de fora, e pega o
# `gui.py`, o `ficha_pdf.py`, o `tratamento.py` e os `notas/AAAA-MM.md`.
LIMITE_LINHAS = 800

# Recorte pedido acima disto já não é recorte.
LIMITE_RECORTE = 600

SUFIXOS = {".py", ".md", ".json", ".txt", ".csv", ".ps1", ".bat"}


def _linhas(caminho: Path) -> int:
    try:
        with caminho.open("rb") as fh:
            return sum(1 for _ in fh)
    except Exception:
        return 0


def _receita(caminho: Path, total: int) -> str:
    """O comando pronto, não o conselho genérico: conselho a gente contorna."""
    rel = caminho.relative_to(RAIZ) if caminho.is_relative_to(RAIZ) else caminho
    if caminho.suffix == ".py":
        return (
            f"`python tools/mapa.py {rel}` imprime o esqueleto (classe, método, "
            f"intervalo de linhas) e `python tools/mapa.py {rel} --buscar TEXTO` "
            "já leva ao trecho. Depois, ler SÓ o intervalo (`offset`/`limit`, ou "
            "`sed -n 'A,Bp'`)."
        )
    return (
        f"`grep -n PADRAO {rel}` para achar a linha e `sed -n 'A,Bp' {rel}` para "
        "ler só o trecho. Em nota antiga, o assunto se procura: o índice do "
        "`NOTAS.md` devolve o título **e** o arquivo."
    )


def _registrar(ferramenta: str, alvo: Path, total: int) -> None:
    """Grava a recusa.

    Falha em silêncio de propósito: gancho que derruba o turno por causa da
    própria estatística custa mais do que a estatística vale.
    """
    try:
        REGISTRO.parent.mkdir(parents=True, exist_ok=True)
        rel = alvo.relative_to(RAIZ) if alvo.is_relative_to(RAIZ) else alvo
        campos = [date.today().isoformat(), ferramenta, str(rel), str(total)]
        with REGISTRO.open("a", encoding="utf-8") as fh:
            fh.write("\t".join(campos) + "\n")
    except Exception:
        pass


def _relatorio() -> int:
    """O que o USO já disse sobre o teto de linhas."""
    if not REGISTRO.is_file():
        print("nenhuma recusa registrada ainda "
              f"(o registro nasce em {REGISTRO.relative_to(RAIZ)})")
        return 0
    linhas = [ln.split("\t") for ln in
              REGISTRO.read_text(encoding="utf-8").splitlines() if ln.strip()]
    linhas = [ln for ln in linhas if len(ln) >= 4]
    if not linhas:
        print("o registro existe mas está vazio")
        return 0
    por_arquivo: dict[str, list[int]] = {}
    for ln in linhas:
        por_arquivo.setdefault(ln[2], []).append(int(ln[3]))
    print(f"{len(linhas)} recusa(s) desde {linhas[0][0]}, "
          f"com o teto em {LIMITE_LINHAS} linhas:")
    for arquivo, tamanhos in sorted(por_arquivo.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(tamanhos):>3}x  {arquivo}  ({tamanhos[0]} linhas)")
    print()
    print("Ler assim: arquivo que aparece muito E foi lido inteiro mesmo assim é")
    print("sinal de teto apertado demais PARA ELE — e a saída costuma ser fatiar")
    print("o arquivo, não subir o teto para todos.")
    return 0


def _negar(motivo: str) -> int:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        }
    }, ensure_ascii=False))
    return 0


def _alvo(bruto: str) -> Path | None:
    try:
        p = Path(bruto.strip().strip('"').strip("'"))
        if not p.is_absolute():
            p = RAIZ / p
        p = p.resolve()
    except Exception:
        return None
    if p.suffix.lower() not in SUFIXOS or not p.is_file():
        return None
    return p


def main() -> int:
    if "--relatorio" in sys.argv[1:]:
        return _relatorio()

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    ferramenta = payload.get("tool_name", "")
    entrada = payload.get("tool_input") or {}

    if ferramenta == "Read":
        alvo = _alvo(str(entrada.get("file_path", "")))
        if alvo is None:
            return 0
        limite = entrada.get("limit")
        if isinstance(limite, int) and 0 < limite <= LIMITE_RECORTE:
            return 0
        total = _linhas(alvo)
        if total <= LIMITE_LINHAS:
            return 0
        pedido = (
            f"com `limit={limite}`, que já é o arquivo"
            if limite else "inteiro, sem `offset`/`limit`"
        )
        _registrar("Read", alvo, total)
        return _negar(
            f"`{alvo.name}` tem {total} linhas e foi pedido {pedido}. Isso entra no "
            f"contexto e é REENVIADO a cada turno seguinte — ~{total * 12 // 1000} mil "
            "tokens, multiplicados pelo resto da sessão.\n\n"
            f"{_receita(alvo, total)}\n\n"
            f"Se o arquivo inteiro for mesmo necessário, ler em fatias de até "
            f"{LIMITE_RECORTE} linhas — a fatia passa."
        )

    if ferramenta == "Bash":
        comando = str(entrada.get("command", ""))
        # Cano, redirecionamento ou heredoc = já há recorte ou não é leitura.
        if "|" in comando or "<<" in comando or ">" in comando:
            return 0
        m = re.search(r"(?:^|;|&&)\s*(?:cat|type)\s+(\S+)\s*$", comando.strip())
        if not m:
            return 0
        alvo = _alvo(m.group(1))
        if alvo is None:
            return 0
        total = _linhas(alvo)
        if total <= LIMITE_LINHAS:
            return 0
        _registrar("Bash", alvo, total)
        return _negar(
            f"`cat {alvo.name}` traria {total} linhas para o contexto, e o contexto "
            f"é reenviado a cada turno. {_receita(alvo, total)}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
