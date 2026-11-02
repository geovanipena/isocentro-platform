"""Quanto do contexto já foi gasto, medido no transcript da própria sessão.

Mora aqui porque dois ganchos precisam da MESMA conta: a `barra_de_estado.py`
(que mostra ao usuário) e o `limite_de_contexto.py` (que avisa a mim). Duas
cópias da mesma leitura envelheceriam separadas — e o dia em que os dois números
discordassem seria o dia em que ninguém confiaria em nenhum dos dois.

O número sai do `usage` da última resposta: é a medida do que o servidor
recebeu, não uma estimativa. Lê só o FIM do arquivo, porque o transcript de uma
sessão longa passa de 8 MB e a barra roda a cada atualização de tela.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Um ORÇAMENTO, não a janela do modelo: a do Opus 5 é de 1 milhão (o
# `modelUsage.contextWindow` da sessão de 15/09/2026). Os 200 mil ficam porque
# o que pesa não é caber — é reler: com cache, 150 mil de contexto custam o
# equivalente a 15 mil de entrada POR TURNO, e a atenção dilui antes de a
# janela acabar. O "%" da barra é deste orçamento.
JANELA = int(os.environ.get("ISOCENTRO_CTX_MAX", "200000"))
CAUDA = 400_000  # bytes do fim do transcript

# 75% é onde ainda dá para fechar com calma: a suíte, o checkpoint e o commit
# cabem no que sobra. Acima disso o fechamento começa a competir com o trabalho.
LIMIAR = int(os.environ.get("ISOCENTRO_CTX_LIMIAR", "75"))


def tokens_vivos(transcript: str) -> int:
    """Entrada + cache lido + cache criado da última resposta com `usage`."""
    try:
        caminho = Path(transcript)
        tamanho = caminho.stat().st_size
        with caminho.open("rb") as fh:
            if tamanho > CAUDA:
                fh.seek(tamanho - CAUDA)
                fh.readline()  # descarta a linha partida pelo seek
            bruto = fh.read().decode("utf-8", errors="replace")
    except Exception:
        return 0

    ultimo = 0
    for linha in bruto.splitlines():
        if '"usage"' not in linha:
            continue
        try:
            uso = (json.loads(linha).get("message") or {}).get("usage") or {}
        except Exception:
            continue
        soma = (
            uso.get("input_tokens", 0)
            + uso.get("cache_read_input_tokens", 0)
            + uso.get("cache_creation_input_tokens", 0)
        )
        if soma:
            ultimo = soma
    return ultimo


def percentual(transcript: str) -> tuple[int, int]:
    """(tokens, % da janela). Zero quando ainda não há resposta medida."""
    ctx = tokens_vivos(transcript)
    return ctx, (ctx * 100 // JANELA if ctx else 0)
