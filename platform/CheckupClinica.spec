# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller para o **checkup da clínica** — o segundo executável.

Ele existe porque na clínica não há Python nem o repositório: o
`tools\\checkup_clinica.bat` funciona aqui e não funciona lá, e a medida que
importa é justamente a de lá. Um binário próprio foi a escolha do usuário em
10/09/2026, contra as alternativas de embutir no app (tela nova, e o produto
carregando uma ferramenta de campo) e de reescrever tudo em PowerShell (que
perderia o `trazer()` do produto — e é ele que se quer medir).

**Três diferenças em relação ao `Isocentro.spec`, e todas têm motivo:**

* `console=True`. O app de sala esconde o console porque a janela preta assusta
  quem está com o paciente na mesa; aqui o console **é** a saída. Sem ele, dois
  cliques não mostrariam nada e o relatório existiria só em arquivo — que é
  exatamente o modo de perder a ida;
* `pathex` inclui `tools/`. O trabalho mora em `tools/checkup_clinica.py`, que
  não é pacote instalável: sem esta linha o Analysis não acha o módulo que o
  `run_checkup.py` importa, e o build sai com um exe que morre no primeiro
  `import`;
* sem `assets/`. O checkup não desenha nada — não há logo, ícone de PDF nem
  semente de notas para levar. São ~4 MB a menos para copiar até a estação.

A lista de imports tardios vem do `tools/gerar_checkup.py`, e não copiada para
cá: é ele que CONFERE, depois do build, que cada nome entrou no pacote. Duas
listas se afastariam em silêncio, e a conferência aprovaria o que o build nunca
recebeu.
"""
import sys
from pathlib import Path

RAIZ = Path(SPECPATH).resolve()
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

from gerar_checkup import DENTRO_DO_PACOTE  # noqa: E402

a = Analysis(
    ["run_checkup.py"],
    # `tools/` no caminho: é lá que mora o checkup_clinica e o diagnostico_db,
    # que ele importa dentro de função.
    pathex=[str(RAIZ), str(RAIZ / "tools")],
    binaries=[],
    datas=[],
    hiddenimports=list(DENTRO_DO_PACOTE),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # A interface inteira fica de fora, e é o que faz este exe ser pequeno: o
    # checkup não abre janela nenhuma. `tests` pelo mesmo motivo do outro spec.
    excludes=["tests", "pytest", "matplotlib", "PySide6", "isocentro.interface"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CheckupClinica",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CheckupClinica",
)
