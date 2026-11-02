"""Achar o ARQUIVO de um módulo do app pelo nome solto.

Vários testes deste repositório leem o próprio código-fonte — as exceções do
padrão visual, os nomes de logger, o import que a ferramenta usa. Todos
escreviam ``RAIZ / "gui.py"``, e isso valia enquanto os módulos moravam na raiz.

Em 09/09/2026 eles viraram o pacote ``isocentro`` e os 16 testes que fazem
isso quebraram de uma vez. A saída NÃO foi escrever
``RAIZ / "isocentro" / "interface" / "gui.py"`` em cada um: as listas de
exceção do ``test_padrao_visual`` são lidas por pessoas, e ``"gui.py:_Janela"``
diz o que ``"isocentro/interface/gui.py:_Janela"`` esconde. Além disso a
lista passaria a codificar o subpacote, e o próximo remanejo quebraria os
mesmos 16 testes de novo.

Nome ambíguo levanta erro em vez de escolher: apontar para o arquivo errado
faria o teste conferir a exceção de outro módulo e passar.
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_IGNORAR = {".venv", ".git", "build", "dist", "__pycache__", "TCs_Teste"}
_CACHE: dict[str, Path] = {}


def caminho(nome: str) -> Path:
    """O arquivo de ``nome`` ("gui.py", ou um caminho relativo já resolvido)."""
    if nome in _CACHE:
        return _CACHE[nome]
    direto = RAIZ / nome
    if direto.is_file():
        _CACHE[nome] = direto
        return direto
    achados = [p for p in RAIZ.rglob(Path(nome).name)
               if p.is_file() and not set(p.parts) & _IGNORAR]
    assert achados, f"não achei {nome} sob {RAIZ}"
    assert len(achados) == 1, (
        f"{nome} existe em {len(achados)} lugares: "
        + ", ".join(p.relative_to(RAIZ).as_posix() for p in sorted(achados)))
    _CACHE[nome] = achados[0]
    return achados[0]


def texto(nome: str) -> str:
    """O fonte de ``nome``. ``utf-8-sig`` porque um dos arquivos tem BOM."""
    return caminho(nome).read_text(encoding="utf-8-sig", errors="replace")
