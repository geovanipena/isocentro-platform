"""A passada do núcleo na concentradora: prazos viram alertas, e a âncora do dia (R-21).

Fonte: AD-9 (concentradora em ``clinica-python01``), AD-28 (gatilho de tempo
só na concentradora) e AD-32 (âncora diária) da espinha; CAP-14 da spec
Fundação; FR-41 do PRD.

Por que os prazos rodam aqui e não na estação: o prazo vence de madrugada, no
fim de semana, com todo mundo em casa. Calculado só por quem tem o app
aberto, o alerta nasceria quando alguém abrisse — e cada estação aberta
calcularia de novo o mesmo prazo. Aqui ele nasce na hora, uma vez, e está na
fila quando a primeira pessoa abrir o app (FR-41).

A âncora é o hash da ponta do log gravado FORA do banco, uma vez por dia, numa
pasta onde o dono do banco não apaga nem edita (AD-32). É o que pega a
corrente reescrita inteira, que o verificador sozinho não pega
(``nucleo/integridade.py``).

Uma fonte de prazos que falha não para a passada: o prazo da Documentação não
deixa de vencer porque o módulo da GQ levantou exceção. A falha vai para o
relatório, com o nome da fonte.

Sem Qt, banco, rede nem arquivo: tudo entra pelas portas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, Iterable, Mapping, Optional, Protocol

from isocentro.nucleo.alerta import Prazo
from isocentro.nucleo.integridade import Ancora

FonteDePrazos = Callable[[], Iterable[Prazo]]


class PortaDeAlertasDePrazo(Protocol):
    def abrir_do_prazo(self, prazo: Prazo, agora: datetime):
        """O alerta aberto (ou o que já estava), ou ``None`` se em dia."""
        ...


class PortaDaPonta(Protocol):
    def agora(self) -> datetime:
        """A hora do banco: a referência única das três clínicas."""
        ...

    def ponta(self) -> Optional[Ancora]:
        """Posição e hash da última linha do log; ``None`` com o log vazio."""
        ...


class GuardaDeAncoras(Protocol):
    def gravar_do_dia(self, ancora: Ancora, dia: date,
                      quando: datetime) -> bool:
        """Grava a âncora do dia; ``False`` se o dia já tinha a sua."""
        ...


@dataclass
class Relatorio:
    alertas: list = field(default_factory=list)
    ancora: Optional[Ancora] = None
    # ``True`` só quando ESTA passada gravou a âncora; ``False`` também quando
    # o dia já tinha a dele, o que é o caso normal de 287 das 288 passadas.
    ancora_gravada: bool = False
    falhas: list = field(default_factory=list)


def passada(fontes: Mapping[str, FonteDePrazos],
            alertas: PortaDeAlertasDePrazo, banco: PortaDaPonta,
            guarda: Optional[GuardaDeAncoras]) -> Relatorio:
    """Uma passada: cada prazo em aviso ou vencido vira alerta; depois a âncora.

    ``guarda`` ``None`` = pasta da âncora não configurada: os prazos rodam
    assim mesmo, e a falta vai para as falhas — sem âncora a corrente fica
    sem a proteção do AD-32, e isso tem de aparecer, não sumir.
    """
    rel = Relatorio()
    agora = banco.agora()
    for nome, fonte in fontes.items():
        try:
            prazos = list(fonte())
        except Exception as exc:   # noqa: BLE001 — uma fonte não para as outras
            rel.falhas.append(f"{nome}: {type(exc).__name__}: {exc}")
            continue
        for prazo in prazos:
            try:
                alerta = alertas.abrir_do_prazo(prazo, agora)
            except Exception as exc:   # noqa: BLE001
                rel.falhas.append(
                    f"{nome}: {getattr(prazo, 'chave', prazo)!r}: "
                    f"{type(exc).__name__}: {exc}")
                continue
            if alerta is not None:
                rel.alertas.append(alerta)

    # A âncora vem DEPOIS dos prazos: assim ela já cobre os alertas desta
    # passada, e o dia fecha com o log como ficou.
    if guarda is None:
        rel.falhas.append("âncora: pasta da âncora não configurada")
        return rel
    ancora = banco.ponta()
    if ancora is None:
        return rel
    rel.ancora = ancora
    try:
        rel.ancora_gravada = guarda.gravar_do_dia(
            ancora, agora.astimezone().date(), agora)
    except OSError as exc:
        rel.falhas.append(f"âncora: {exc}")
    return rel
