"""O contrato da verificação e o motor que a executa, sem gravar (R-77).

Fonte do contrato: AD-14 (resultado, severidade, estado, origem), AD-15
(avaliador puro), AD-28 (execução vigente — a idempotência fica na R-20) e
AD-31 (id ``<modulo>.<nome>``) da espinha; CAP-7, CAP-8, CAP-10 e CAP-11 da
spec Fundação.

Por que um só lugar: sem ele, cada módulo inventaria o seu resultado, a sua
severidade e o seu "sem dado", e o dia em que um deles contasse um
``indeterminado`` como aprovado não teria onde ser pego. Aqui o motor é o
único que monta a ``Execucao``: o avaliador só devolve uma ``Avaliacao``, e o
que ele devolver fora do contrato (ou lançar) vira ``erro`` com a mensagem, e
nunca ``conforme``.

Sem Qt, banco, rede nem arquivo. A gravação é a ``PortaDeGravacao``; a
implementação no PostgreSQL pelo ``nucleo.gravar`` é da R-20, e a de memória
mora nos testes. Resolver a fonte contra o ``conhecimento/`` também fica fora:
aqui se recusa a fonte AUSENTE, não a que não resolve.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol


class Resultado(str, Enum):
    CONFORME = "conforme"
    NAO_CONFORME = "nao_conforme"
    NAO_APLICAVEL = "nao_aplicavel"
    INDETERMINADO = "indeterminado"
    ERRO = "erro"


class Severidade(str, Enum):
    """Nenhuma bloqueia (decisão de 13/10/2026: o motor é só advisory)."""
    ALTA = "alta"
    ATENCAO = "atencao"
    INFORMATIVO = "informativo"


class Estado(str, Enum):
    SOMBRA = "sombra"
    ATIVA = "ativa"
    PODADA = "podada"


class Origem(str, Enum):
    PRODUCAO = "producao"
    SEMEADO = "semeado"


class Gatilho(str, Enum):
    EVENTO = "evento"
    CALENDARIO = "calendario"
    PRAZO = "prazo"
    ESTADO = "estado"


class OrigemTolerancia(str, Enum):
    LITERATURA = "literatura"
    SERVICO = "servico"
    # Regra de decisão (26/10/2026): sem referência no acervo, o software usa
    # a opção conservadora até a discussão, e diz que é provisória (R-82).
    PROVISORIA = "provisoria"


# Os que pedem motivo (AD-14). Um ``indeterminado`` mudo é indistinguível de
# um avaliador que esqueceu de olhar, e quem lê a fila não tem como saber qual.
PEDEM_MOTIVO = frozenset({Resultado.INDETERMINADO, Resultado.ERRO})
# Os que viram alerta numa verificação ativa (CAP-12). ``nao_aplicavel`` não:
# é a verificação dizendo que o caso não é dela, com conhecimento de causa.
VIRAM_ALERTA = frozenset({Resultado.NAO_CONFORME, Resultado.INDETERMINADO,
                          Resultado.ERRO})

# Minúsculas, dígitos e sublinhado, um ponto só: o prefixo é o módulo dono
# (AD-31). Dois pontos ou maiúscula deixariam ``plano.Indice`` e
# ``plano.indice`` coexistirem no catálogo como coisas diferentes.
_ID = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")


class CadastroRecusado(ValueError):
    """A verificação (ou a tolerância dela) não entra no catálogo."""


class VerificacaoPodada(RuntimeError):
    """Podada é retirada: executá-la produziria resultado de regra que o físico
    já descartou, e ninguém o leria."""


def _enum(tipo, valor, campo):
    try:
        return tipo(valor)
    except ValueError:
        validos = ", ".join(m.value for m in tipo)
        raise CadastroRecusado(
            f"{campo} {valor!r} não existe (valem: {validos})") from None


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _preenchido(valor) -> bool:
    """Texto com algo além de espaço, ou qualquer outro valor não vazio."""
    if isinstance(valor, str):
        return bool(valor.strip())
    return bool(valor)


def _textos(valor) -> tuple:
    """Uma string solta vira tupla de UM: iterada, ``"C05.md"`` passaria como
    seis "fontes" de um caractere cada. O que não é texto vira ``""``, para
    quem chama recusar."""
    itens = (valor,) if isinstance(valor, str) else tuple(valor or ())
    return tuple(_texto(i) for i in itens)


@dataclass(frozen=True)
class Tolerancia:
    """O limite e de onde ele vem (CAP-7, TG-218).

    ``literatura`` exige a referência; ``servico`` exige a data e o método da
    derivação. Sem isso, um 3% copiado de um protocolo e um 3% derivado da
    base histórica do serviço seriam o mesmo número na tela — e o primeiro não
    reprova plano enquanto não for derivado (regra do ``qualidade.CALIBRADO``).

    ``provisoria`` exige ``decisao``, o número do item de
    ``docs/planejamento/sistema-global/decisoes-sem-base.md`` que a sustenta:
    sem ele, um provisório não teria como ser achado no dia em que o físico
    decidir, e ficaria provisório para sempre. Aqui se recusa o número
    AUSENTE; conferir que o item existe no arquivo é de quem lê o arquivo.
    """
    limite: str
    origem: Any
    referencia: str = ""
    data: Optional[date] = None
    metodo: str = ""
    decisao: Optional[int] = None

    def __post_init__(self):
        if not _texto(self.limite):
            raise CadastroRecusado("tolerância sem limite")
        if self.origem in (None, ""):
            validas = ", ".join(m.value for m in OrigemTolerancia)
            raise CadastroRecusado(
                f"tolerância {self.limite!r} sem origem ({validas})")
        origem = _enum(OrigemTolerancia, self.origem, "origem da tolerância")
        object.__setattr__(self, "origem", origem)
        if origem is OrigemTolerancia.LITERATURA and not _texto(self.referencia):
            raise CadastroRecusado(
                f"tolerância {self.limite!r} de literatura sem referência")
        if origem is OrigemTolerancia.SERVICO:
            # ``datetime`` é subclasse de ``date``: aceitá-la seria gravar uma
            # hora que ninguém mediu.
            if not isinstance(self.data, date) or isinstance(self.data, datetime):
                raise CadastroRecusado(
                    f"tolerância {self.limite!r} do serviço sem data da derivação")
            if not _texto(self.metodo):
                raise CadastroRecusado(
                    f"tolerância {self.limite!r} do serviço sem método da derivação")
        if origem is OrigemTolerancia.PROVISORIA:
            # Inteiro e nada mais: ``True`` é ``int`` e viraria o item 1, e
            # "6" ou "#6" abririam a porta para "6a", "seis" e "ver nota".
            if self.decisao is None:
                raise CadastroRecusado(
                    f"tolerância {self.limite!r} provisória sem o número do "
                    "item de decisoes-sem-base.md")
            if (not isinstance(self.decisao, int)
                    or isinstance(self.decisao, bool) or self.decisao < 1):
                raise CadastroRecusado(
                    f"tolerância {self.limite!r} provisória: item "
                    f"{self.decisao!r} de decisoes-sem-base.md não é inteiro "
                    "positivo")
            # Provisória é a que NÃO tem base: com referência, ou com data e
            # método de derivação, a tela mostraria um provisório com cara de
            # literatura ou de serviço. Sem ``_texto`` nos dois: ele devolve ""
            # para o que não é str, e ``referencia=["TG-142"]`` passaria vazia.
            if (_preenchido(self.referencia) or self.data is not None
                    or _preenchido(self.metodo)):
                raise CadastroRecusado(
                    f"tolerância {self.limite!r} provisória com referência, "
                    "data ou método (então ela não é provisória)")
        elif self.decisao is not None:
            # Literatura ou serviço que aponta decisão em aberto: a tela não a
            # marcaria provisória, e o número diria que ela é.
            nome = ("da literatura" if origem is OrigemTolerancia.LITERATURA
                    else "do serviço")
            raise CadastroRecusado(
                f"tolerância {self.limite!r} {nome} com item de "
                "decisoes-sem-base.md (só a provisória aponta decisão)")


@dataclass(frozen=True)
class Avaliacao:
    """O que o avaliador devolve. Não é a execução: quem a monta é o motor."""
    resultado: Resultado
    motivo: str = ""
    evidencia: Mapping[str, Any] = field(default_factory=dict)


Avaliador = Callable[[Mapping[str, Any]], Avaliacao]


@dataclass(frozen=True)
class Verificacao:
    """O objeto do catálogo (CAP-7): regra, proveniência, gatilho, responsável,
    avaliador, severidade e estado.

    ``fontes`` são as fichas da base que justificam a verificação; sem nenhuma,
    o cadastro é recusado. ``requer`` são as chaves que o avaliador precisa
    nos dados: faltando alguma, o motor nem o chama e devolve
    ``indeterminado`` dizendo qual. Sem ``requer``, a garantia de "sem dado"
    é do avaliador (que devolve ``indeterminado`` com motivo).

    O ``estado`` padrão é ``sombra`` (CAP-10). O construtor aceita ``ativa``
    porque é por ele que a R-20 relê o catálogo do banco; quem garante que a
    promoção passou pelo físico, com quem, quando e o resumo do período, é a
    gravação dela, e não este tipo.
    """
    id: str
    versao: str
    regra: str
    fontes: tuple
    gatilho: Any
    responsavel: str
    avaliador: Avaliador
    severidade: Any
    estado: Any = Estado.SOMBRA
    tolerancia: Optional[Tolerancia] = None
    requer: tuple = ()

    def __post_init__(self):
        if not isinstance(self.id, str) or not _ID.fullmatch(self.id):
            raise CadastroRecusado(
                f"id {self.id!r} fora do formato <modulo>.<nome> (minúsculas)")
        # Aparado ao entrar: " 1.0.0" e "1.0.0" seriam duas versões da mesma
        # verificação para a execução vigente da R-20.
        for campo in ("versao", "regra", "responsavel"):
            valor = _texto(getattr(self, campo))
            if not valor:
                raise CadastroRecusado(f"{self.id}: sem {campo}")
            object.__setattr__(self, campo, valor)
        fontes = _textos(self.fontes)
        if not fontes or not all(fontes):
            raise CadastroRecusado(
                f"{self.id}: sem fonte (a proveniência é obrigatória)")
        object.__setattr__(self, "fontes", fontes)
        object.__setattr__(self, "gatilho",
                           _enum(Gatilho, self.gatilho, f"{self.id}: gatilho"))
        object.__setattr__(self, "severidade",
                           _enum(Severidade, self.severidade,
                                 f"{self.id}: severidade"))
        object.__setattr__(self, "estado",
                           _enum(Estado, self.estado, f"{self.id}: estado"))
        if not callable(self.avaliador):
            raise CadastroRecusado(f"{self.id}: avaliador não é chamável")
        if self.tolerancia is not None and not isinstance(self.tolerancia,
                                                          Tolerancia):
            raise CadastroRecusado(
                f"{self.id}: tolerância tem de ser Tolerancia, com origem")
        requer = _textos(self.requer)
        if not all(requer):
            raise CadastroRecusado(
                f"{self.id}: chave requerida vazia ou que não é texto")
        object.__setattr__(self, "requer", requer)

    @property
    def modulo(self) -> str:
        return self.id.split(".", 1)[0]


@dataclass(frozen=True)
class Entrada:
    """O que o motor recebeu para avaliar, já lido pelos adaptadores.

    ``objeto`` e ``versao`` são o que a R-20 usa para a execução vigente
    (AD-28); ``degrau``, ``data``, ``arquivo`` e ``checksum`` dizem de onde
    veio o dado (CAP-8, FR-39): ``data`` é a da carga do ``variandw`` (ou do
    espelho, ou da exportação do CSV) e ``arquivo`` o identificador do arquivo
    lido (RT Plan, JSON ESAPI), com o SHA-256 dele em ``checksum``. Nenhum é
    preenchido aqui: campo sem fonte fica vazio, e versão vazia faz o motor
    devolver ``indeterminado``. A falta de proveniência não impede avaliar,
    mas impede GRAVAR (``falta_proveniencia``).
    """
    objeto: str
    versao: str
    dados: Optional[Mapping[str, Any]]
    degrau: str = ""
    data: str = ""
    checksum: str = ""
    arquivo: str = ""

    def __post_init__(self):
        # Sem objeto não há a quem a execução se refere: é erro de quem chama,
        # não um caso a avaliar.
        if not _texto(self.objeto):
            raise ValueError("entrada sem objeto")


@dataclass(frozen=True)
class Execucao:
    verificacao_id: str
    verificacao_versao: str
    # O estado e a severidade NO MOMENTO da execução: promover a verificação
    # depois não pode fazer uma execução de sombra passar a ter alertado.
    estado: Estado
    severidade: Severidade
    origem: Origem
    entrada: Entrada
    resultado: Resultado
    motivo: str
    evidencia: Mapping[str, Any]
    quando: datetime

    @property
    def conta_como_conforme(self) -> bool:
        return self.resultado is Resultado.CONFORME

    @property
    def vira_alerta(self) -> bool:
        """Só verificação ativa, só produção (CAP-10, CAP-11, CAP-12)."""
        return (self.estado is Estado.ATIVA
                and self.origem is Origem.PRODUCAO
                and self.resultado in VIRAM_ALERTA)

    @property
    def entra_em_indicador(self) -> bool:
        """Semeado nunca (CAP-11); sombra também não, porque não entra em
        contador (CAP-10) — o resumo da promoção a lê por fora."""
        return self.estado is Estado.ATIVA and self.origem is Origem.PRODUCAO


# Os degraus de fonte (AD-16, AD-17) e o que cada um tem de declarar para a
# execução ser gravada (FR-39). Degrau de banco diz a data do dado; degrau de
# arquivo diz QUAL arquivo e o hash dele. Degrau novo entra aqui e na
# restrição da ``nucleo.execucao`` (migração), nunca por texto livre: um
# "manual" ou um "ARIA" escrito à mão seria proveniência que ninguém confere.
DEGRAUS_DE_BANCO = frozenset({"variandw", "espelho", "csv"})
DEGRAUS_DE_ARQUIVO = frozenset({"dicom", "esapi_json"})
_SHA256 = re.compile(r"[0-9a-f]{64}")


def falta_proveniencia(entrada: Entrada) -> str:
    """O que falta para a execução dizer de onde partiu; ``""`` se nada falta.

    Sem isto, uma execução ``conforme`` gravada não diria se avaliou o RT Plan
    que foi tratado ou um anterior, nem de que carga do ``variandw`` saiu a
    prescrição — e a evidência não se sustentaria na auditoria (FR-39).
    """
    degrau = _texto(entrada.degrau)
    if not degrau:
        return "sem degrau de fonte"
    if degrau not in DEGRAUS_DE_BANCO | DEGRAUS_DE_ARQUIVO:
        validos = ", ".join(sorted(DEGRAUS_DE_BANCO | DEGRAUS_DE_ARQUIVO))
        return f"degrau {degrau!r} não existe (valem: {validos})"
    arquivo, checksum = _texto(entrada.arquivo), _texto(entrada.checksum)
    # Um sem o outro não prova nada: o nome sem hash não diz se o arquivo é o
    # mesmo; o hash sem nome não diz onde procurar o arquivo para conferir.
    if bool(arquivo) != bool(checksum):
        return "arquivo e checksum andam juntos"
    if checksum and not _SHA256.fullmatch(checksum):
        return "checksum fora do SHA-256 em hexadecimal minúsculo"
    if degrau in DEGRAUS_DE_ARQUIVO and not arquivo:
        return f"degrau {degrau} sem o arquivo lido e o checksum dele"
    if degrau in DEGRAUS_DE_BANCO and not _texto(entrada.data):
        return f"degrau {degrau} sem a data da carga"
    return ""


class PortaDeGravacao(Protocol):
    """Onde a execução vai parar. Quem implementa no banco é a R-20."""

    def gravar_execucao(self, execucao: Execucao) -> None: ...


def _avaliar(verificacao: Verificacao, entrada: Entrada) -> Avaliacao:
    if entrada.dados is None:
        return Avaliacao(Resultado.INDETERMINADO, "sem dado para avaliar")
    if not isinstance(entrada.dados, Mapping):
        return Avaliacao(Resultado.ERRO,
                         f"dados chegaram como {type(entrada.dados).__name__}, "
                         "e não como mapa")
    # Sem a versão do objeto, a R-20 não tem como dizer a que versão do plano
    # o resultado vale, e um resultado do plano antigo valeria para o novo.
    if not _texto(entrada.versao):
        return Avaliacao(Resultado.INDETERMINADO,
                         f"sem versão de {entrada.objeto}")
    faltam = [c for c in verificacao.requer if entrada.dados.get(c) is None]
    if faltam:
        return Avaliacao(Resultado.INDETERMINADO,
                         "falta dado: " + ", ".join(faltam))
    try:
        # Só leitura para o avaliador: o que ele mudasse no mapa mudaria
        # também a entrada registrada, e a execução diria ter lido o que o
        # adaptador nunca leu (CAP-8).
        avaliacao = verificacao.avaliador(MappingProxyType(dict(entrada.dados)))
    except Exception as exc:   # noqa: BLE001 — o contrato é transformar em ``erro``
        return Avaliacao(Resultado.ERRO, f"{type(exc).__name__}: {exc}")
    if not isinstance(avaliacao, Avaliacao):
        return Avaliacao(Resultado.ERRO,
                         f"avaliador devolveu {type(avaliacao).__name__}, "
                         "e não Avaliacao")
    try:
        resultado = Resultado(avaliacao.resultado)
    except ValueError:
        return Avaliacao(Resultado.ERRO,
                         f"avaliador devolveu resultado {avaliacao.resultado!r}, "
                         "fora dos cinco")
    # Motivo que não é texto (uma exceção, uma lista) ainda é motivo: zerá-lo
    # transformaria uma falta de dado explicada em "erro sem motivo".
    motivo = "" if avaliacao.motivo is None else str(avaliacao.motivo).strip()
    if resultado in PEDEM_MOTIVO and not motivo:
        # O ``erro`` aqui não é do caso, é do avaliador: um ``indeterminado``
        # sem motivo é contrato quebrado, e passar adiante seria esconder isso.
        return Avaliacao(Resultado.ERRO,
                         f"avaliador devolveu {resultado.value} sem motivo")
    # Mapa e nada mais: ``dict(["ab", "cd"])`` vira ``{"a": "b", "c": "d"}``
    # calado, e lixo gravado como evidência de um ``conforme``.
    if avaliacao.evidencia is None:
        evidencia = {}
    elif isinstance(avaliacao.evidencia, Mapping):
        try:
            evidencia = dict(avaliacao.evidencia)
        except Exception as exc:   # noqa: BLE001
            return Avaliacao(Resultado.ERRO,
                             f"evidência ilegível: {type(exc).__name__}: {exc}")
    else:
        return Avaliacao(Resultado.ERRO,
                         "avaliador devolveu evidência que não é um mapa")
    return Avaliacao(resultado, motivo, evidencia)


def _agora() -> datetime:
    """Com fuso: estações e concentradora gravam no mesmo banco, e a R-20
    ordena por esta hora para achar a execução vigente."""
    return datetime.now(timezone.utc).astimezone()


def executar(verificacao: Verificacao, entrada: Entrada, porta: PortaDeGravacao,
             *, origem=Origem.PRODUCAO,
             agora: Callable[[], datetime] = _agora) -> Execucao:
    """Avalia, monta a execução e a entrega à porta. Devolve a execução.

    Falha da PORTA sobe: o resultado que não foi gravado não pode parecer
    gravado. Falha do AVALIADOR não sobe: vira ``erro`` com a mensagem.
    """
    if verificacao.estado is Estado.PODADA:
        raise VerificacaoPodada(f"{verificacao.id} está podada")
    origem = Origem(origem)
    avaliacao = _avaliar(verificacao, entrada)
    execucao = Execucao(
        verificacao_id=verificacao.id,
        verificacao_versao=verificacao.versao,
        estado=verificacao.estado,
        severidade=verificacao.severidade,
        origem=origem,
        entrada=entrada,
        resultado=avaliacao.resultado,
        motivo=avaliacao.motivo,
        evidencia=avaliacao.evidencia,
        quando=agora(),
    )
    porta.gravar_execucao(execucao)
    return execucao


def alertas(execucoes: Iterable[Execucao]) -> list:
    return [e for e in execucoes if e.vira_alerta]


def para_indicador(execucoes: Iterable[Execucao]) -> list:
    return [e for e in execucoes if e.entra_em_indicador]
