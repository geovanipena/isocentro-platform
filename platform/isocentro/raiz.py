"""Onde o app mora em disco — uma resposta só para as três perguntas de caminho.

Este módulo nasceu em 09/09/2026, no dia em que os 60 módulos soltos da raiz
viraram o pacote ``isocentro``. Antes dele, **onze** lugares respondiam
sozinhos a alguma variação de "onde eu estou?", todos por
``os.path.dirname(__file__)``, e todos apoiados na mesma coincidência: o módulo
ficava na raiz do projeto, então a pasta dele ERA a pasta do app.

A coincidência acabou. Um módulo em ``isocentro/banco/`` responderia
``raiz/isocentro/banco`` — e nenhum dos onze levantaria erro por isso. O
``usuarios.json`` do serviço nasceria na pasta errada, a capa sairia sem logo, o
``paralelo`` diria "sem tabela desta máquina" e viraria DEMONSTRAÇÃO calado. É a
pior forma de quebrar que existe neste projeto: com aparência de funcionamento,
e no papel que vai para a sala de tratamento.

As três perguntas são diferentes entre si, e é por isso que são três funções e
não uma constante:

- **A pasta do app** é onde se GRAVA. Empacotado, é a pasta do ``.exe`` — não a
  do bundle, onde ninguém conseguiria largar um relatório novo e de onde o
  ``migrar.ps1`` não copiaria nada.
- **A pasta de recursos** é de onde se LÊ o que veio no pacote (os logos, a
  semente de notas). Empacotado, é o ``_internal/``, um nível ABAIXO do
  executável — é para lá que o PyInstaller desdobra os ``datas``.
- **A raiz do projeto** só existe fora do pacote, e serve a ferramenta, não ao
  app.

Fora do pacote as três coincidem de novo, que é o que mantém o comportamento
idêntico ao de antes desta mudança em desenvolvimento e em teste.

A exceção, desde 21/10/2026 (frente R-57): fora do pacote, a variável
``ISOCENTRO_PASTA_APP`` muda a pasta do app. Na estação de desenvolvimento ela
aponta para ``_restrito/estacao/``, e o dado de paciente que o app grava
(``registro_fichas.json``, ``correcoes_capa.json``, ``notas_posicionamento.json``
e os outros) sai da árvore do repositório. Empacotado ela é ignorada: o
executável grava ao lado de si, como sempre, porque é lá que o ``migrar.ps1``
procura.
"""
from __future__ import annotations

import sys
from pathlib import Path

from isocentro.dados import ambiente

# ``parent`` é ``isocentro/``; ``parent.parent`` é a raiz do projeto. Este
# módulo mora no PRIMEIRO nível do pacote de propósito: assim a conta é fixa e
# não muda se um subpacote for renomeado ou ganhar um nível.
_RAIZ = Path(__file__).resolve().parent.parent


def empacotado() -> bool:
    """Está rodando de dentro do executável do PyInstaller?"""
    return bool(getattr(sys, "frozen", False))


def pasta_do_app() -> Path:
    """Onde o app grava os arquivos do serviço (``usuarios.json`` e os outros).

    Empacotado, é a pasta do executável, e **não** ``sys._MEIPASS``: os arquivos
    daqui são dado de execução, o ``migrar.ps1`` os procura ao lado do ``.exe``,
    e o bundle é descartado a cada arranque.

    Fora do pacote, ``ISOCENTRO_PASTA_APP`` (por qualquer dos três nomes do
    ``ambiente``) tem precedência sobre a raiz do projeto. Ela muda TUDO o que
    sai daqui, inclusive o ``dados_feixe/`` do paralelo: quem a define define
    também ``ISOCENTRO_DADOS_FEIXE``, ou o cálculo paralelo vira DEMONSTRAÇÃO.
    """
    if empacotado():
        return Path(sys.executable).resolve().parent
    escolhida = ambiente.ler("ISOCENTRO_PASTA_APP")
    if escolhida:
        return Path(escolhida)
    return _RAIZ


def pasta_assets() -> Path:
    """Onde estão os recursos que viajaram no pacote — os logos e a semente.

    Empacotado, é ``_internal/assets``: o ``Isocentro.spec`` declara
    ``datas=[("assets", "assets")]`` e o PyInstaller no modo ``onedir`` desdobra
    os ``datas`` dentro de ``sys._MEIPASS``, que é o próprio ``_internal/``.
    Usar ``pasta_do_app()`` aqui daria um nível acima e a ficha sairia sem logo.
    """
    if empacotado():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / "assets"
    return _RAIZ / "assets"


def raiz_do_projeto() -> Path:
    """A raiz do repositório. Só faz sentido FORA do pacote.

    É para ferramenta (``tools/``) e teste, que precisam achar ``tests/``,
    ``dados_feixe/`` ou o ``Isocentro.spec``. O app não deve chamar isto: dentro
    do executável não existe repositório nenhum, e o valor devolvido seria a
    pasta do bundle, que some no arranque seguinte.
    """
    return _RAIZ
