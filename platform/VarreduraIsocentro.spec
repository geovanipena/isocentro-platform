# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller para a **varredura da concentradora** — o 3º executável.

Ele existe porque o relógio da exportação mora dentro do app aberto (decisão de
02/09/2026), e na concentradora isso exigiria alguém mantendo o programa aberto
e logado num servidor. Este binário é a outra porta: uma passada, sem tela,
chamada pela Tarefa Agendada do Windows.

**Quatro diferenças em relação ao `Isocentro.spec`, e todas têm motivo:**

* `console=True`, como no checkup. A rodada é agendada e o que sobra dela para
  quem for olhar é a saída — com `console=False` não haveria nem isso;
* `pathex` inclui `tools/`, porque o trabalho mora em `tools/varredura_cli.py`,
  que não é pacote instalável. Sem esta linha o Analysis não acha o módulo que
  o `run_varredura.py` importa, e o build sai com um exe que morre no primeiro
  `import`;
* sem `assets/`: a varredura não desenha nada. Não há logo nem semente de notas
  para levar;
* **`isocentro.interface` NÃO é excluído** — e aqui está a diferença que
  mais custaria. O `CheckupClinica.spec` exclui o pacote inteiro da interface,
  e para ele isso é certo. Aqui não: o `gatilho._preparar` chama
  `simulacao.procurar`, e o `simulacao` mora em `interface/` **sem importar Qt
  nenhum** (medido em 14/09/2026). Excluindo o pacote, todo caso preparado
  sairia com "sem cadastro de simulação" — que é uma resposta legítima do
  domínio, então ninguém desconfiaria de defeito de empacotamento.

O `PySide6` (o `PyQt5` até a R-23) continua excluído: é o que faz este exe ser pequeno, e nada no
caminho da varredura fala com a tela.

A lista de imports tardios vem do `tools/gerar_varredura.py`, e não copiada
para cá: é ele que CONFERE, depois do build, que cada nome entrou no pacote.
Duas listas se afastariam em silêncio, e a conferência aprovaria o que o build
nunca recebeu.

**Um nome só em tudo** (spec, `build/`, `dist/` e exe): o `Isocentro.spec` gera o
`ISOCENTRO.exe` e o `build/Isocentro/Analysis-00.toc`, e essa divergência
obriga a lembrar de onde sai o TOC toda vez que alguém mexe na conferência.
"""
import sys
from pathlib import Path

RAIZ = Path(SPECPATH).resolve()
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

from gerar_varredura import DENTRO_DO_PACOTE  # noqa: E402

a = Analysis(
    ["run_varredura.py"],
    # `tools/` no caminho: é lá que mora o `varredura_cli`.
    pathex=[str(RAIZ), str(RAIZ / "tools")],
    binaries=[],
    datas=[],
    hiddenimports=list(DENTRO_DO_PACOTE),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # A interface de TELA fica de fora pelo PySide6, não pelo pacote: ver a
    # docstring acima. `tests` pelo mesmo motivo dos outros specs.
    excludes=["tests", "pytest", "matplotlib", "PySide6"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VarreduraIsocentro",
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
    name="VarreduraIsocentro",
)
