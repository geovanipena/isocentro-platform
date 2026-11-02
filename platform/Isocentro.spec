# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller para o ISOCENTRO.

**Este arquivo é versionado, e isso é o ponto.** Ele não existia em 09/09/2026:
o `.gitignore` mandava `*.spec` fora (conselho genérico de projeto PyInstaller,
onde o spec é gerado e descartável) e o `tools/manutencao.py` ainda listava
`*.spec` como "saída solta" — quer dizer, como lixo a apagar. Só que aqui o
spec NÃO é descartável: ele carrega os `hiddenimports`, que são a lista dos
imports tardios sem os quais o app abre na clínica e falha calado. Perdido o
arquivo, `tools/gerar_executavel.py` parava no passo 2 e ninguém empacotava.

A lista de imports tardios vem do próprio `gerar_executavel.py`, e não copiada
para cá: a ferramenta CONFERE, depois do build, que cada nome dela entrou no
pacote. Duas listas se afastariam em silêncio — a conferência aprovaria o que
o build nunca recebeu, que é a pior combinação possível das duas.

Layout `onedir` (uma pasta com o exe e `_internal/`), e não `onefile`, por três
razões medidas: o `migrar.ps1` copia arquivo a arquivo, o app grava ao lado do
executável (`_app_dir`), e `assets/` precisa cair em `_internal/assets/` —
é de lá que `ficha_pdf` e `capa_pdf` leem os logos, e é esse caminho que o
`gerar_executavel.conferir_semente` exige.
"""
import sys
from pathlib import Path

RAIZ = Path(SPECPATH).resolve()
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

from gerar_executavel import DENTRO_DO_PACOTE  # noqa: E402

# `pyodbc` e `pynetdicom` são BIBLIOTECAS, e entram pelo mesmo motivo dos
# módulos do app: os dois são importados dentro de função, para o programa
# subir mesmo sem eles instalados.
OCULTOS = list(DENTRO_DO_PACOTE)

a = Analysis(
    ["run_gui.py"],
    pathex=[str(RAIZ)],
    binaries=[],
    # ('origem', 'destino DENTRO do pacote'). O destino é "assets" e não
    # "_internal/assets": no modo onedir o PyInstaller já põe os dados sob
    # `_internal/`, e escrever o prefixo aqui daria `_internal/_internal/`.
    datas=[("assets", "assets")],
    hiddenimports=OCULTOS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # A suíte não vai para a clínica, e o `tests/` importa o app inteiro: sem
    # isto ele entraria de carona no pacote.
    excludes=["tests", "pytest", "matplotlib.tests"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    # O nome do EXE é o do produto; o do spec é Isocentro porque é dele que sai
    # `build/Isocentro/Analysis-00.toc`, que o `conferir_modulos` lê.
    name="ISOCENTRO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Sem console: é app de sala, e a janela preta atrás dele assusta quem
    # está com o paciente na mesa. O rastro de erro vai para
    # ~/.isocentro.log — ver `gui._configurar_log`.
    console=False,
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
    name="ISOCENTRO",
)
