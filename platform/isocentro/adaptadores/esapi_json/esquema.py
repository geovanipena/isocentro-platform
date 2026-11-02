"""O esquema v1 do JSON que o avaliador ESAPI grava (R-76; AD-15 e AD-41).

O esquema mora AQUI, no ISOCENTRO, e não no ``scriptsvarian``: é deste lado
que se recusa. Se cada lado tivesse a sua cópia, o C# acrescentaria um campo,
o Python o ignoraria, e o resultado entraria como se dissesse o que não diz.
Por isso o v1 é estrito: campo a mais, a menos ou do tipo errado é ``erro``, e
mudar o formato é subir ``versao_esquema``.

Formato v1 (UTF-8; o BOM que o ``File.WriteAllText`` do .NET põe é aceito)::

    {
      "versao_esquema": 1,
      "verificacao": "plano.fracoes",
      "script":  {"id": "...", "versao": "1.2.0", "hash_dll": "<sha256, 64 hex>"},
      "plano":   {"paciente": "...", "curso": "...", "id": "...", "versao": "..."},
      "resultado": "conforme" | "nao_conforme" | "nao_aplicavel"
                   | "indeterminado" | "erro",
      "motivo": "...",        (opcional; obrigatório em indeterminado e erro)
      "evidencia": {...}      (opcional; objeto)
    }

``verificacao`` segue o formato do catálogo (``<modulo>.<nome>``, AD-31).
O plano vai com paciente e curso porque, no Eclipse, o Id do plano só é único
dentro do curso: "PELVE" de dois pacientes, com versões que coincidissem,
deixaria o ``conforme`` de um valer para o outro. ``plano.versao`` é opaca: o ISOCENTRO só a compara com a versão atual que ele
mesmo leu. ``hash_dll`` é o SHA-256 do ``.esapi.dll`` que rodou, para casar com
o inventário (R-61) — a versão escrita no script pode não mudar numa
recompilação, o hash muda.

Puro: recebe o conteúdo já lido (bytes ou texto), sem arquivo, banco nem rede.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Union

# O formato do id vem do núcleo, e não de uma cópia: o dia em que o catálogo
# mudasse a regra, a cópia aceitaria ids que ele já não reconhece.
from isocentro.nucleo.verificacao import PEDEM_MOTIVO, Resultado
from isocentro.nucleo.verificacao import _ID as _ID_VERIFICACAO

VERSAO_ESQUEMA = 1
ESQUEMAS_CONHECIDOS = frozenset({VERSAO_ESQUEMA})

_CAMPOS = frozenset({"versao_esquema", "verificacao", "script", "plano",
                     "resultado", "motivo", "evidencia"})
_OBRIGATORIOS = _CAMPOS - {"motivo", "evidencia"}
_CAMPOS_SCRIPT = frozenset({"id", "versao", "hash_dll"})
_CAMPOS_PLANO = frozenset({"paciente", "curso", "id", "versao"})

# SHA-256 em hexadecimal, sem separador. Maiúscula é aceita (o
# ``BitConverter`` do .NET escreve assim) e guardada em minúscula, para o
# mesmo hash não ser dois no inventário.
_HASH = re.compile(r"[0-9a-fA-F]{64}")


class DocumentoInvalido(ValueError):
    """O JSON não é um documento v1. A mensagem é o motivo do ``erro``."""


@dataclass(frozen=True)
class DocumentoV1:
    versao_esquema: int
    verificacao: str
    script_id: str
    script_versao: str
    hash_dll: str
    paciente: str
    curso: str
    plano_id: str
    plano_versao: str
    resultado: Resultado
    motivo: str = ""
    evidencia: Mapping[str, Any] = field(default_factory=dict)

    @property
    def objeto(self) -> str:
        """O plano como objeto da ``Entrada``: único entre pacientes."""
        return f"{self.paciente}/{self.curso}/{self.plano_id}"


def checksum(conteudo: Union[bytes, str]) -> str:
    """SHA-256 do conteúdo: é o checksum da ``Entrada`` (CAP-8).

    Só bytes provam qual arquivo foi importado. Texto é recodificado em UTF-8
    (sem o BOM que o arquivo tinha), e o hash não bate com o do disco: quem
    importa deve passar os bytes como lidos.
    """
    if isinstance(conteudo, str):
        # ``surrogatepass``: texto decodificado com ``surrogateescape`` não pode
        # derrubar o checksum antes de o documento sequer ser lido.
        conteudo = conteudo.encode("utf-8", "surrogatepass")
    return hashlib.sha256(conteudo).hexdigest()


def _sem_repetidas(pares):
    # O ``json`` padrão fica com a ÚLTIMA chave repetida, calado: um
    # ``"resultado"`` duplicado teria um valor no arquivo que se lê a olho e
    # outro no que se importa.
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise DocumentoInvalido(f"chave {chave!r} repetida")
        objeto[chave] = valor
    return objeto


def _recusar_constante(nome):
    # NaN e Infinity não são JSON, mas o ``json`` do Python os aceita; numa
    # evidência, um NaN gravado compararia diferente de si mesmo.
    raise DocumentoInvalido(f"{nome} não é JSON válido")


def _float_finito(texto):
    # O ``parse_constant`` só pega os literais: ``1e400`` vira ``inf`` sem
    # passar por ele, e o PostgreSQL recusa Infinity em json longe da causa.
    valor = float(texto)
    if not math.isfinite(valor):
        raise DocumentoInvalido(f"número {texto} fora do alcance de um double")
    return valor


def _texto(objeto, campo, onde):
    valor = objeto.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise DocumentoInvalido(f"{onde}{campo} ausente, vazio ou não é texto")
    return valor.strip()


def _bloco(objeto, campo, chaves):
    valor = objeto.get(campo)
    if not isinstance(valor, dict):
        raise DocumentoInvalido(f"{campo} ausente ou não é objeto")
    _conferir_chaves(valor, chaves, chaves, f"{campo}.")
    return valor


def _conferir_chaves(objeto, permitidas, obrigatorias, onde=""):
    sobram = sorted(set(objeto) - permitidas)
    if sobram:
        raise DocumentoInvalido(
            f"campo não previsto no v1: {', '.join(onde + c for c in sobram)}")
    faltam = sorted(obrigatorias - set(objeto))
    if faltam:
        raise DocumentoInvalido(
            f"falta campo: {', '.join(onde + c for c in faltam)}")


def ler(conteudo: Union[bytes, str]) -> DocumentoV1:
    """Interpreta o conteúdo como documento v1, ou levanta ``DocumentoInvalido``.

    A versão do esquema é conferida ANTES do resto: num esquema que não se
    conhece, "falta campo" seria um motivo enganoso — o campo pode só ter
    mudado de nome.
    """
    if isinstance(conteudo, bytes):
        try:
            conteudo = conteudo.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentoInvalido(f"não é UTF-8: {exc}") from None
    elif isinstance(conteudo, str):
        conteudo = conteudo.lstrip("\ufeff")
    else:
        raise DocumentoInvalido(
            f"conteúdo chegou como {type(conteudo).__name__}")
    try:
        bruto = json.loads(conteudo, object_pairs_hook=_sem_repetidas,
                           parse_constant=_recusar_constante,
                           parse_float=_float_finito)
    except json.JSONDecodeError as exc:
        raise DocumentoInvalido(f"JSON ilegível: {exc}") from None
    except RecursionError:
        # Aninhamento fundo demais estoura a pilha do decodificador; sem isto,
        # a concentradora receberia a exceção crua e não um ``erro``.
        raise DocumentoInvalido("JSON aninhado fundo demais") from None
    if not isinstance(bruto, dict):
        raise DocumentoInvalido("o documento não é um objeto JSON")

    versao = bruto.get("versao_esquema")
    # ``bool`` é subclasse de ``int`` e ``True == 1``: sem a exclusão, um
    # ``"versao_esquema": true`` passaria por v1.
    if (not isinstance(versao, int) or isinstance(versao, bool)
            or versao not in ESQUEMAS_CONHECIDOS):
        conhecidas = ", ".join(str(v) for v in sorted(ESQUEMAS_CONHECIDOS))
        raise DocumentoInvalido(
            f"versão de esquema {versao!r} desconhecida (conhecidas: {conhecidas})")

    _conferir_chaves(bruto, _CAMPOS, _OBRIGATORIOS)
    script = _bloco(bruto, "script", _CAMPOS_SCRIPT)
    plano = _bloco(bruto, "plano", _CAMPOS_PLANO)

    hash_dll = script.get("hash_dll")
    if not isinstance(hash_dll, str) or not _HASH.fullmatch(hash_dll):
        raise DocumentoInvalido(
            f"script.hash_dll {hash_dll!r} não é SHA-256 (64 dígitos hexadecimais)")

    try:
        resultado = Resultado(bruto["resultado"])
    except (ValueError, TypeError):
        validos = ", ".join(r.value for r in Resultado)
        raise DocumentoInvalido(
            f"resultado {bruto['resultado']!r} fora dos cinco ({validos})") from None

    motivo = bruto.get("motivo", "")
    if not isinstance(motivo, str):
        raise DocumentoInvalido("motivo não é texto")
    motivo = motivo.strip()
    # Mesma regra do avaliador Python (AD-14): ``indeterminado`` mudo é
    # indistinguível de um script que esqueceu de olhar.
    if resultado in PEDEM_MOTIVO and not motivo:
        raise DocumentoInvalido(f"resultado {resultado.value} sem motivo")

    evidencia = bruto.get("evidencia", {})
    if not isinstance(evidencia, dict):
        raise DocumentoInvalido("evidencia não é objeto")

    verificacao = _texto(bruto, "verificacao", "")
    if not _ID_VERIFICACAO.fullmatch(verificacao):
        raise DocumentoInvalido(
            f"verificacao {verificacao!r} fora do formato <modulo>.<nome> (minúsculas)")

    return DocumentoV1(
        versao_esquema=versao,
        verificacao=verificacao,
        script_id=_texto(script, "id", "script."),
        script_versao=_texto(script, "versao", "script."),
        hash_dll=hash_dll.lower(),
        paciente=_texto(plano, "paciente", "plano."),
        curso=_texto(plano, "curso", "plano."),
        plano_id=_texto(plano, "id", "plano."),
        plano_versao=_texto(plano, "versao", "plano."),
        resultado=resultado,
        motivo=motivo,
        evidencia=evidencia,
    )
