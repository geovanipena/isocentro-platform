"""O alerta do núcleo: prazo, ciclo de vida e ordem da fila (R-21).

Fonte: AD-28 (alerta só da execução vigente), AD-29 (alerta como eventos) da
espinha; CAP-12 e CAP-14 da spec Fundação; FR-5 e FR-41 do PRD.

Por que é do núcleo e não de cada módulo: com o Plano marcando "visto" de um
jeito e a Documentação de outro, a fila "o que precisa de ação" do Início
juntaria coisas que não se comparam — e um alerta resolvido num módulo
continuaria aberto na fila. Aqui há um ciclo só: aberto → visto (quem e
quando) → resolvido, cada passo um evento acrescentado, e o ``alta`` só se
resolve com justificativa.

Nenhum alerta bloqueia nada (FR-5): este módulo não tem como dizer "não
pode"; ele diz "precisa de ação".

Sem Qt, banco, rede nem arquivo. A gravação é do ``adaptadores/postgres``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable, Optional, Sequence

from isocentro.nucleo.verificacao import Severidade

# Os códigos de unidade do código (``atividades_db.UNIDADES``): ANA é a DUO.
# Os mesmos da restrição de ``nucleo.alerta``.
CLINICAS = ("ANA", "BET", "CEL")


class EstadoAlerta(str, Enum):
    ABERTO = "aberto"
    VISTO = "visto"
    RESOLVIDO = "resolvido"


class Evento(str, Enum):
    VISTO = "visto"
    RESOLVIDO = "resolvido"


class AlertaRecusado(ValueError):
    """O evento (ou o prazo) não entra, com o motivo. Nada foi gravado."""


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _com_fuso(quando, campo: str) -> datetime:
    if not isinstance(quando, datetime):
        raise AlertaRecusado(f"{campo} não é data e hora")
    if quando.tzinfo is None:
        # Sem fuso, "vence às 8h" é uma hora diferente na concentradora e na
        # estação; adivinhar seria pôr o alerta adiantado ou atrasado.
        raise AlertaRecusado(f"{campo} sem fuso horário")
    return quando


@dataclass(frozen=True)
class Prazo:
    """Um prazo que um módulo entrega à concentradora (FR-41).

    ``chave`` é estável e única no módulo (``documentacao.aso:17:2027-03-01``)
    e começa pelo módulo dono (AD-31). O vencimento entra na chave de quem
    renova: o prazo renovado é outro prazo, e o alerta do antigo não se
    confunde com o do novo.
    """
    chave: str
    objeto: str
    clinica: str
    responsavel: str
    motivo: str
    aviso_em: datetime
    vence_em: datetime

    def __post_init__(self):
        for campo in ("chave", "objeto", "clinica", "responsavel", "motivo"):
            valor = _texto(getattr(self, campo))
            if not valor:
                raise AlertaRecusado(f"prazo sem {campo}")
            object.__setattr__(self, campo, valor)
        if "." not in self.chave.split(":", 1)[0]:
            raise AlertaRecusado(
                f"chave {self.chave!r} sem o módulo dono (<modulo>.<nome>...)")
        if self.clinica not in CLINICAS:
            raise AlertaRecusado(
                f"clínica {self.clinica!r} não existe (valem: "
                f"{', '.join(CLINICAS)})")
        aviso = _com_fuso(self.aviso_em, "aviso_em")
        vence = _com_fuso(self.vence_em, "vence_em")
        if aviso > vence:
            raise AlertaRecusado(
                f"{self.chave}: o aviso vem depois do vencimento")


def severidade_do_prazo(prazo: Prazo, agora: datetime) -> Optional[Severidade]:
    """``alta`` vencido, ``atencao`` no aviso, ``None`` em dia.

    A borda é do vencido: no instante exato do vencimento o prazo JÁ venceu.
    Nenhuma referência do acervo fixa a borda (``decisoes-sem-base.md`` #38),
    e a regra de decisão manda a opção mais conservadora — avisar um instante
    cedo, nunca um instante tarde.
    """
    agora = _com_fuso(agora, "agora")
    if agora >= prazo.vence_em:
        return Severidade.ALTA
    if agora >= prazo.aviso_em:
        return Severidade.ATENCAO
    return None


def estado(eventos: Iterable) -> EstadoAlerta:
    """O estado a partir dos eventos acrescentados (AD-29)."""
    vistos = False
    for e in eventos:
        if Evento(e) is Evento.RESOLVIDO:
            return EstadoAlerta.RESOLVIDO
        vistos = True
    return EstadoAlerta.VISTO if vistos else EstadoAlerta.ABERTO


def conferir_evento(severidade, eventos: Sequence, evento,
                    justificativa: Optional[str]) -> Optional[str]:
    """A justificativa aparada (ou ``None``), ou ``AlertaRecusado`` com o motivo.

    Resolver ``alta`` pede justificativa (FR-5): é o registro de quem seguiu
    adiante com um ``nao_conforme`` grave, e sem ela o "resolvido" não diz se
    alguém olhou o caso ou só limpou a fila.
    """
    evento = Evento(evento)
    if estado(eventos) is EstadoAlerta.RESOLVIDO:
        raise AlertaRecusado("o alerta já foi resolvido")
    justificativa = _texto(justificativa) or None
    if (evento is Evento.RESOLVIDO
            and Severidade(severidade) is Severidade.ALTA
            and justificativa is None):
        raise AlertaRecusado("resolver alerta alta pede justificativa")
    return justificativa


_PESO = {Severidade.ALTA: 0, Severidade.ATENCAO: 1, Severidade.INFORMATIVO: 2}


def ordenar(alertas: Iterable) -> list:
    """A ordem da fila (CAP-12): severidade, depois o prazo mais próximo.

    Alerta sem prazo (o de execução) vem depois dos que têm prazo na mesma
    severidade, e entre os iguais o mais antigo primeiro: é o que espera há
    mais tempo. Aceita qualquer objeto com ``severidade``, ``vence_em`` e
    ``quando``.
    """
    def chave(a):
        vence = a.vence_em
        return (_PESO[Severidade(a.severidade)],
                vence is None, vence or a.quando, a.quando)
    return sorted(alertas, key=chave)
