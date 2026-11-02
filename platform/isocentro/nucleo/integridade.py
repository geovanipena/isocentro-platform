"""O verificador de integridade do log: refaz a corrente e aponta onde ela quebra (R-18).

Fonte: AD-6 (corrente global, ``sha256(hash_anterior || linha)``) e AD-32
(âncora e verificador) da espinha; CAP-5 da spec Fundação.

Por que a conta é refeita AQUI, em Python, e não pedida ao banco: no dia em
que alguém com DDL alterar uma linha do log, a mesma pessoa pode trocar a
função ``nucleo.hash_da_linha`` para que ela "confirme" a linha nova. O
verificador só confia no que ele mesmo calcula, a partir das colunas cruas.
A regra de montar a linha tem de ser a MESMA do ``migracoes/0001_nucleo.sql``;
o teste em PostgreSQL prova que as duas batem.

O que ele pega sozinho, sem âncora: linha alterada (o hash não fecha), linha
apagada no meio (buraco na posição) e corrente religada (``hash_anterior``
que não é o hash da linha de antes). O que só a âncora pega: a corrente
reescrita inteira de um ponto em diante, com todos os hashes refeitos, e as
últimas linhas apagadas (a ponta encolhe sem buraco). Por isso a concentradora
grava a âncora diária fora do banco (R-21).

Sem Qt, banco, rede nem arquivo: recebe as linhas já lidas.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

# O ``hash_anterior`` da posição 1: 32 bytes zero, os mesmos que a migração
# põe na ``nucleo.ponta`` vazia.
GENESE = bytes(32)

_EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MICRO = timedelta(microseconds=1)


@dataclass(frozen=True)
class LinhaDeLog:
    """Uma linha de ``nucleo.log`` como o banco a guarda."""
    posicao: int
    quando: datetime
    quem: str
    modulo: str
    tabela: str
    registro: str
    substitui: Optional[str]
    versao_origem: Optional[str]
    hash_anterior: bytes
    hash: bytes


@dataclass(frozen=True)
class Ancora:
    """O hash da ponta numa posição, gravado fora do banco (AD-32)."""
    posicao: int
    hash: bytes


@dataclass(frozen=True)
class Divergencia:
    """Onde a corrente não fecha. ``registro`` é ``None`` quando a linha sumiu."""
    posicao: int
    tabela: Optional[str]
    registro: Optional[str]
    motivo: str


def _campo(valor: Optional[str]) -> str:
    # ``len`` conta pontos de código, como o ``length`` do PostgreSQL num
    # banco UTF8; contar bytes aqui faria todo nome com acento divergir.
    return "-" if valor is None else f"{len(valor)}:{valor}"


def _microssegundos(quando: datetime) -> int:
    if quando.tzinfo is None:
        # Hora sem fuso não tem instante: adivinhar o fuso seria inventar o
        # dado que o hash protege.
        raise ValueError("quando sem fuso horário")
    # Divisão inteira de timedelta: exata. O ``timestamp()`` passa por float e
    # erra o último microssegundo em datas que o banco grava certo.
    return (quando - _EPOCA) // _MICRO


def hash_da_linha(linha: LinhaDeLog, hash_anterior: bytes) -> bytes:
    """A mesma conta do ``nucleo.hash_da_linha`` do banco."""
    texto = "".join((
        _campo(str(linha.posicao)),
        _campo(str(_microssegundos(linha.quando))),
        _campo(linha.quem),
        _campo(linha.modulo),
        _campo(linha.tabela),
        _campo(linha.registro),
        _campo(linha.substitui),
        _campo(linha.versao_origem),
    ))
    return hashlib.sha256(bytes(hash_anterior) + texto.encode("utf-8")).digest()


def verificar(linhas: Iterable[LinhaDeLog],
              ancoras: Iterable[Ancora] = ()) -> list[Divergencia]:
    """Todas as divergências, na ordem da posição; lista vazia = corrente íntegra.

    Devolve TODAS, e não só a primeira: uma linha alterada não contamina as
    seguintes (cada uma guarda o próprio ``hash_anterior``), então a lista
    aponta exatamente as linhas mexidas — que é o que o físico precisa levar
    à investigação.
    """
    achados: list[Divergencia] = []
    por_posicao: dict[int, LinhaDeLog] = {}
    esperada = 1
    anterior = GENESE
    for linha in sorted(linhas, key=lambda l: l.posicao):
        if linha.posicao > esperada:
            achados.append(Divergencia(
                esperada, None, None,
                f"faltam as posições {esperada} a {linha.posicao - 1}: "
                "linha apagada"
                if linha.posicao - 1 > esperada
                else f"falta a posição {esperada}: linha apagada"))
        elif linha.posicao < esperada:
            achados.append(Divergencia(
                linha.posicao, linha.tabela, linha.registro,
                "posição repetida"))
            continue
        if bytes(linha.hash_anterior) != anterior:
            achados.append(Divergencia(
                linha.posicao, linha.tabela, linha.registro,
                "o hash anterior não é o da linha de antes: corrente religada"))
        if hash_da_linha(linha, linha.hash_anterior) != bytes(linha.hash):
            achados.append(Divergencia(
                linha.posicao, linha.tabela, linha.registro,
                "o conteúdo não bate com o hash: linha alterada"))
        por_posicao[linha.posicao] = linha
        anterior = bytes(linha.hash)
        esperada = linha.posicao + 1

    for ancora in sorted(ancoras, key=lambda a: a.posicao):
        linha = por_posicao.get(ancora.posicao)
        if linha is None:
            achados.append(Divergencia(
                ancora.posicao, None, None,
                "a linha da âncora não está no log: linhas apagadas"))
        elif bytes(linha.hash) != bytes(ancora.hash):
            achados.append(Divergencia(
                ancora.posicao, linha.tabela, linha.registro,
                "não bate com a âncora: corrente reescrita até aqui"))
    return sorted(achados, key=lambda d: d.posicao)
