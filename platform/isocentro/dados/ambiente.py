"""Variáveis de ambiente do app — pelos TRÊS nomes que ele já teve.

O programa se chamou ficha-py (variáveis ``FICHAPY_*``), depois Radioteraficha
(``RADIOTERAFICHA_*``) e, desde 15/10/2026, ISOCENTRO (``ISOCENTRO_*``). As
variáveis acompanham o nome, só que elas não são detalhe interno: são o que a
TI já configurou nas estações, às vezes há anos, em script de implantação que
ninguém vai reler.

Renomear e pronto quebraria em SILÊNCIO — o app não acharia o valor, cairia no
padrão, a capa nasceria vazia naquela máquina e nada ligaria uma coisa à outra.
É a pior forma de quebrar: sem erro, sem aviso, com aparência de funcionamento.

Então valem os três. O nome mais novo tem precedência (é para onde as
instalações caminham); os antigos continuam servindo enquanto existirem.
Ninguém precisa correr para trocar nada, e quem trocar não perde o que já
estava lá.
"""
from __future__ import annotations

import os

PREFIXO_NOVO = "ISOCENTRO_"
# Do mais novo para o mais velho: é a ordem em que se procura.
PREFIXOS_ANTIGOS = ("RADIOTERAFICHA_", "FICHAPY_")


def _sufixo(variavel: str) -> str:
    """``CAPA_DIR`` de qualquer um dos três nomes; o nome inteiro se for outro."""
    for prefixo in (PREFIXO_NOVO, *PREFIXOS_ANTIGOS):
        if variavel.startswith(prefixo):
            return variavel[len(prefixo):]
    return ""


def nomes(variavel: str) -> list[str]:
    """Os três nomes da variável, na ordem de precedência.

    Variável fora da convenção (sem nenhum dos prefixos) tem um nome só.
    """
    sufixo = _sufixo(variavel)
    if not sufixo:
        return [variavel]
    return [p + sufixo for p in (PREFIXO_NOVO, *PREFIXOS_ANTIGOS)]


def nome_novo(variavel: str) -> str:
    """``FICHAPY_CAPA_DIR`` (ou qualquer um dos três) → ``ISOCENTRO_CAPA_DIR``."""
    return nomes(variavel)[0]


def nomes_antigos(variavel: str) -> list[str]:
    """Os nomes de antes do ISOCENTRO — para teste limpar e para doc citar."""
    return nomes(variavel)[1:]


def ler(variavel: str, padrao: str = "") -> str:
    """O valor da variável pelo primeiro dos três nomes que estiver definido.

    Aceita qualquer um dos três nomes: quem chama não precisa saber que há
    mais de um.
    """
    for nome in nomes(variavel):
        valor = os.environ.get(nome, "").strip()
        if valor:
            return valor
    return padrao


def qual_valeu(variavel: str) -> str:
    """Qual dos nomes está valendo ("" se nenhum) — para a tela dizer.

    Sem isto, quem definiu a variável nova numa estação onde a antiga também
    existe não tem como saber qual venceu.
    """
    for nome in nomes(variavel):
        if os.environ.get(nome, "").strip():
            return nome
    return ""
