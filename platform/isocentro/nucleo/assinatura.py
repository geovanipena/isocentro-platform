"""A assinatura presa à versão do objeto (R-21).

Fonte: AD-30 da espinha; CAP-13 da spec Fundação; FR-8 e FR-20 do PRD.

Por que a versão é parte da assinatura e não um detalhe: o Duplo Check de
segunda-feira foi sobre um RT Plan; se o plano foi reotimizado na terça, o
que está no ARIA já não é o que o segundo físico conferiu. Sem a versão, a
tela mostraria "assinado" sobre um plano que ninguém conferiu. Com ela, o
item volta sozinho a pendente — sem ninguém precisar lembrar de "desassinar".

Quem assina não é um campo daqui: é o ``quem`` do log, que só a sessão
preenche (FR-8, não há assinatura em nome de outro). As travas de PERFIL —
só o físico assina Aprovação Física e Duplo Check, e o do Duplo Check nunca é
o da Aprovação — são do módulo Plano.

Sem Qt, banco, rede nem arquivo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def versao_do_plano(ser, sop_instance_uid, hstry_date_time,
                    status) -> str:
    """A versão de um plano (AD-30): ``Ser`` + SOPInstanceUID +
    ``HstryDateTime`` + status de aprovação, ou ``""`` se faltar qualquer um.

    Vazia, e não parcial: uma versão sem o ``HstryDateTime`` casaria o plano
    reaprovado com o de antes (o SOPInstanceUID nem sempre muda quando o
    status muda), e a assinatura antiga passaria a valer para o novo.
    """
    def parte(p) -> str:
        if isinstance(p, datetime):
            return p.isoformat()
        # ``bool`` é ``int`` em Python: um ``True`` virando "True" seria uma
        # versão inventada a partir de um campo errado.
        if isinstance(p, int) and not isinstance(p, bool):
            return str(p)
        return _texto(p)
    partes = [parte(p)
              for p in (ser, sop_instance_uid, hstry_date_time, status)]
    if not all(partes):
        return ""
    return "|".join(partes)


@dataclass(frozen=True)
class Assinatura:
    id: str
    tipo: str
    objeto: str
    objeto_versao: str
    perfil: str
    pessoa: str
    quando: datetime


@dataclass(frozen=True)
class Situacao:
    """``assinatura`` é a que vale para a versão atual; ``None`` se pendente."""
    assinado: bool
    assinatura: Optional[Assinatura]
    motivo: str


def situacao(assinaturas: Iterable[Assinatura],
             versao_atual: str) -> Situacao:
    """Assinado na versão atual, ou pendente com o porquê."""
    versao_atual = _texto(versao_atual)
    todas = sorted(assinaturas, key=lambda a: a.quando)
    if not versao_atual:
        # Sem a versão de agora não há como dizer que a assinatura vale para
        # ela: pendente, e a tela diz que é por falta de dado.
        return Situacao(False, None, "sem a versão atual do objeto")
    validas = [a for a in todas if a.objeto_versao == versao_atual]
    if validas:
        return Situacao(True, validas[-1], "")
    if todas:
        return Situacao(False, None,
                        f"assinado na versão {todas[-1].objeto_versao}; "
                        "o objeto mudou depois")
    return Situacao(False, None, "sem assinatura")
