"""O ``QSettings`` da estação — com o que ficou gravado no nome antigo.

O ``QSettings`` guarda, por usuário do Windows, o modo dia/noite, a geometria
das janelas e as escolhas antigas que o ``controle_virtual`` ainda adota. Ele
mora numa chave do registro com o NOME do app: até 15/10/2026 era
``Radioteraficha``; desde então é ``Isocentro``. Trocar o nome e pronto abriria
o app de toda estação no modo e no tamanho de fábrica, sem explicação — então,
na primeira vez que a chave nova aparece vazia, ela recebe uma cópia da antiga.

Cópia, e não movimentação: quem voltar para a versão anterior (acontece)
encontra o que era dele.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

ORGANIZACAO = APLICATIVO = "Isocentro"
_ANTIGO = ("Radioteraficha", "Radioteraficha")


def _abrir(organizacao: str, aplicativo: str) -> QSettings:
    """A chave do registro daquele nome.

    Função à parte para o teste trocar por um ``.ini`` descartável: o
    construtor ``QSettings(organização, aplicativo)`` vai SEMPRE ao registro —
    ele ignora o ``setDefaultFormat`` —, e um teste que o chamasse direto
    gravaria no registro de quem roda a suíte (aconteceu em 15/10/2026).
    """
    return QSettings(organizacao, aplicativo)


def ajustes() -> QSettings:
    """O ``QSettings`` do ISOCENTRO, já com o que havia no nome antigo."""
    novo = _abrir(ORGANIZACAO, APLICATIVO)
    if not novo.allKeys():
        antigo = _abrir(*_ANTIGO)
        for chave in antigo.allKeys():
            novo.setValue(chave, antigo.value(chave))
        novo.sync()
    return novo
