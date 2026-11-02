"""Do arquivo JSON do ESAPI à execução gravada, pelo mesmo motor (R-20; AD-15, CAP-9).

O ``validacao`` (R-76) decide o que o JSON vale; aqui ele vira EXECUÇÃO:
a verificação vem do catálogo pelo id que o JSON declara, o objeto é o plano,
a versão é a que o ISOCENTRO leu agora, e a proveniência é o nome e o
SHA-256 do arquivo (FR-39). Quem grava é a porta do motor, como para qualquer
avaliador Python — o resultado ESAPI não tem caminho próprio até o banco.

JSON quebrado também vira execução (``erro`` com motivo), desde que dê para
saber de que verificação e de que plano ele fala: um ``erro`` que ninguém vê
é um plano sem a checagem que todos acham que rodou. Quando nem isso dá
(não é JSON, ou não diz verificação e plano), ou a verificação não está no
catálogo, não há execução a montar: ``ImportacaoRecusada``, e quem lê a pasta
(a concentradora, R-21) põe o arquivo de lado e avisa.

Sem arquivo, banco nem rede: recebe os bytes já lidos e a porta pronta.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from typing import Callable, Mapping, Optional

from isocentro.adaptadores.esapi_json.esquema import (
    DocumentoInvalido, ler)
from isocentro.adaptadores.esapi_json.validacao import ItemInventario, validar
from isocentro.nucleo.verificacao import (
    Entrada, Execucao, Origem, PortaDeGravacao, Verificacao, executar)

DEGRAU = "esapi_json"


class ImportacaoRecusada(ValueError):
    """Não há execução a gravar: o arquivo não diz a que verificação ou plano
    pertence, ou a verificação não está no catálogo."""


def _atribuir(conteudo: bytes) -> tuple[str, str]:
    """Verificação e objeto de um JSON que não é v1, se ele ainda os disser."""
    try:
        bruto = json.loads(conteudo)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ImportacaoRecusada(f"não é JSON: {exc}") from exc
    plano = bruto.get("plano") if isinstance(bruto, dict) else None
    partes = ([bruto.get("verificacao")]
              + [plano.get(c) for c in ("paciente", "curso", "id")]
              if isinstance(plano, dict) else [])
    if len(partes) != 4 or not all(isinstance(p, str) and p.strip()
                                   for p in partes):
        raise ImportacaoRecusada(
            "o JSON não diz a verificação e o plano (paciente, curso, id)")
    verificacao, paciente, curso, plano_id = (p.strip() for p in partes)
    # O mesmo formato do ``DocumentoV1.objeto``: o erro tem de cair na mesma
    # chave da execução que o JSON certo teria gerado.
    return verificacao, f"{paciente}/{curso}/{plano_id}"


def importar(conteudo: bytes, *, arquivo: str,
             catalogo: Mapping[str, Verificacao],
             versao_atual: Callable[[str], Optional[str]],
             inventario: Mapping[str, ItemInventario],
             porta: PortaDeGravacao,
             origem=Origem.PRODUCAO,
             agora: Optional[Callable[[], datetime]] = None) -> Execucao:
    """Monta e grava a execução do arquivo ``arquivo`` (os ``conteudo`` bytes).

    ``versao_atual(objeto)`` é a versão do plano que o ISOCENTRO lê agora
    (``None`` se não conseguiu ler). Bytes, e não texto: o checksum gravado
    tem de bater com o do arquivo no disco.
    """
    if not isinstance(conteudo, bytes):
        raise TypeError("o conteúdo vai como bytes, do jeito que foi lido")
    try:
        doc = ler(conteudo)
        verificacao_id, objeto = doc.verificacao, doc.objeto
    except DocumentoInvalido:
        doc = None
        verificacao_id, objeto = _atribuir(conteudo)
    verificacao = catalogo.get(verificacao_id)
    if verificacao is None:
        raise ImportacaoRecusada(
            f"a verificação {verificacao_id} não está no catálogo")

    atual = versao_atual(objeto)
    importacao = validar(conteudo, versao_plano_atual=atual,
                         inventario=inventario)
    # A versão da execução é a ATUAL: um resultado do plano antigo vira
    # ``indeterminado`` na chave do plano de hoje, que é onde alguém olha.
    versao = (atual or "").strip() or (doc.plano_versao if doc else "")
    entrada = Entrada(objeto=objeto, versao=versao,
                      dados={"arquivo": arquivo}, degrau=DEGRAU,
                      arquivo=arquivo, checksum=importacao.checksum)
    # O avaliador desta execução é o próprio JSON: o motor monta a execução
    # como a de qualquer avaliador, com a mesma conferência de contrato.
    pelo_json = replace(verificacao, avaliador=lambda _d: importacao.avaliacao,
                        requer=())
    extras = {"agora": agora} if agora is not None else {}
    return executar(pelo_json, entrada, porta, origem=origem, **extras)
