"""Ponto de entrada do executável da VARREDURA — o que roda na concentradora.

Existe separado do ``run_gui.py`` pelo mesmo motivo do ``run_checkup.py``: na
clínica não há Python nem o repositório, só chega executável. E separado do
app porque o ``ISOCENTRO.exe`` é ``console=False`` — uma rodada agendada
não mostraria nada — e porque subir a interface inteira para não abrir janela
nenhuma é peso puro numa tarefa que roda de cinco em cinco minutos.

Fino de propósito: o trabalho está em ``tools/varredura_cli.py``, que é
ferramenta e mora com as outras. O que ele acrescenta é o caminho de import —
do fonte, ``tools/`` não está no ``sys.path``; empacotado, o PyInstaller já pôs
o módulo dentro do pacote (ver ``Varredura.spec``, que o alcança pelo
``pathex``).
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from varredura_cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
