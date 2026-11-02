"""Gravar e ler as âncoras diárias numa pasta (AD-32, R-21).

Uma linha por arquivo: ``<posição> <hash em hexadecimal> <hora ISO>``. Sem
dado de paciente — a âncora é um número e um hash (AD-32), e a pasta é da TI,
fora do controle de acesso do ISOCENTRO.

A pasta vem de ``ISOCENTRO_PASTA_ANCORA`` (``docs/AMBIENTE.md``); o caminho
na clínica é da R-17.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from isocentro.dados import ambiente
from isocentro.nucleo.integridade import Ancora

VARIAVEL = "ISOCENTRO_PASTA_ANCORA"
_NOME = re.compile(r"^ancora-(\d{4}-\d{2}-\d{2})\.txt$")
_LINHA = re.compile(r"^([1-9]\d*) ([0-9a-f]{64}) (\S+)$")


def pasta_configurada() -> Optional[Path]:
    """A pasta da variável, ou ``None`` se ela não estiver definida.

    Sem padrão ao lado do programa, de propósito: uma âncora gravada na pasta
    do próprio app estaria ao alcance de quem ela existe para vigiar.
    """
    valor = ambiente.ler(VARIAVEL).strip()
    return Path(valor) if valor else None


def nome_do_dia(dia: date) -> str:
    return f"ancora-{dia.isoformat()}.txt"


class PastaDeAncoras:
    """A ``GuardaDeAncoras`` da ``nucleo.concentradora`` sobre uma pasta."""

    def __init__(self, pasta: Path):
        self.pasta = Path(pasta)

    def gravar_do_dia(self, ancora: Ancora, dia: date,
                      quando: datetime) -> bool:
        """Cria o arquivo do dia; ``False`` se ele já existia (não reescreve).

        Modo ``x``: a criação falha se o arquivo existe. É o que garante que a
        âncora de manhã não é trocada pela da tarde — e numa pasta
        só-acrescentar, abrir para escrita o que já existe seria recusado de
        qualquer jeito.
        """
        if quando.tzinfo is None:
            raise ValueError("hora da âncora sem fuso horário")
        linha = f"{ancora.posicao} {bytes(ancora.hash).hex()} {quando.isoformat()}\n"
        try:
            with open(self.pasta / nome_do_dia(dia), "x", encoding="ascii",
                      newline="\n") as arq:
                arq.write(linha)
        except FileExistsError:
            return False
        return True

    def ler(self) -> tuple[list[Ancora], list[str]]:
        """As âncoras da pasta e os problemas dos arquivos que não se leem.

        Arquivo ilegível não é pulado em silêncio: âncora corrompida é achado
        de auditoria por si, e o verificador tem de dizer que conferiu MENOS
        do que a pasta prometia.
        """
        ancoras: list[Ancora] = []
        problemas: list[str] = []
        for arq in sorted(self.pasta.iterdir()):
            if not _NOME.match(arq.name):
                continue
            try:
                texto = arq.read_text(encoding="ascii").strip()
            except (OSError, UnicodeDecodeError) as exc:
                problemas.append(f"{arq.name}: ilegível ({exc})")
                continue
            casou = _LINHA.match(texto)
            if not casou:
                problemas.append(f"{arq.name}: fora do formato")
                continue
            ancoras.append(Ancora(int(casou.group(1)),
                                  bytes.fromhex(casou.group(2))))
        return ancoras, problemas
