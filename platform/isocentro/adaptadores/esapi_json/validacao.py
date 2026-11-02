"""Do JSON do avaliador ESAPI à ``Avaliacao`` do núcleo (R-76; AD-15, AD-41).

Duas camadas, e a diferença entre elas é a diferença entre ``erro`` e
``indeterminado``:

- o documento não é v1 (esquema desconhecido, hash malformado, campo faltando)
  → ``erro``: o que veio está quebrado, e o motivo diz onde;
- o documento é v1, mas não se pode confiar nele PARA ESTE PLANO AGORA (o plano
  mudou depois que o script rodou; o script não está no inventário, está em
  outra versão ou não foi validado) → ``indeterminado``: o resultado pode até
  estar certo, mas não vale como evidência.

O inventário é parâmetro e não tem padrão: quem o preenche é o físico, pelo
futuro ``modulos/software`` (R-61). Um inventário embutido aqui seria
justamente o "script validado" que ninguém validou.

Puro: sem arquivo, banco nem rede. Quem lê a pasta e grava a execução é a
concentradora.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Mapping, Optional, Union

from isocentro.adaptadores.esapi_json.esquema import (
    DocumentoInvalido, DocumentoV1, checksum, ler)
from isocentro.nucleo.verificacao import Avaliacao, Resultado


@dataclass(frozen=True)
class ItemInventario:
    """Uma linha do inventário de scripts ESAPI (AD-41, item 3)."""
    id: str
    versao: str
    hash_dll: str
    validado: bool


@dataclass(frozen=True)
class Importacao:
    """O que a concentradora precisa para montar a execução.

    ``documento`` é ``None`` quando o JSON nem chegou a ser v1; ``checksum``
    existe sempre, porque até o arquivo recusado tem de ser identificável.
    """
    avaliacao: Avaliacao
    documento: Optional[DocumentoV1]
    checksum: str


def _motivo_inventario(doc: DocumentoV1,
                       inventario: Mapping[str, ItemInventario]) -> str:
    item = inventario.get(doc.script_id)
    if item is None:
        return f"script {doc.script_id} ausente do inventário"
    # Linha vinda de planilha pode ter célula vazia (None, NaN): sem isto, o
    # ``.strip()`` estouraria e a pasta inteira cairia por uma linha.
    campos = [getattr(item, c, None) for c in ("id", "versao", "hash_dll")]
    if not all(isinstance(c, str) for c in campos):
        return f"linha do inventário de {doc.script_id} malformada"
    item_id, item_versao, item_hash = (c.strip() for c in campos)
    # A chave do mapa não basta: montado com a chave trocada, o inventário
    # validaria um script com a linha de outro.
    if item_id != doc.script_id:
        return (f"inventário de {doc.script_id} aponta para a linha de "
                f"{item_id}")
    # A versão escrita pode não mudar numa recompilação; o hash muda. Os dois
    # têm de bater para ser a DLL que foi validada.
    if (item_versao != doc.script_versao
            or item_hash.lower() != doc.hash_dll):
        return (f"script {doc.script_id} {doc.script_versao} (DLL "
                f"{doc.hash_dll[:12]}…) não é a versão inventariada")
    # ``is True``: um "sim" ou um 1 vindos de planilha não são validação.
    if item.validado is not True:
        return f"script {doc.script_id} {doc.script_versao} não validado"
    return ""


def validar(conteudo: Union[bytes, str], *,
            versao_plano_atual: Optional[str],
            inventario: Mapping[str, ItemInventario]) -> Importacao:
    """Lê o JSON e decide o que ele vale como resultado.

    ``versao_plano_atual`` é a versão do plano ``documento.objeto`` (paciente,
    curso e plano) que o ISOCENTRO leu agora;
    vazia, não há com o que comparar, e o resultado é ``indeterminado``.
    Os motivos de ``indeterminado`` se somam: corrigir um e descobrir o outro
    só na importação seguinte custaria uma volta.
    """
    soma = checksum(conteudo) if isinstance(conteudo, (bytes, str)) else ""
    try:
        doc = ler(conteudo)
    except DocumentoInvalido as exc:
        return Importacao(Avaliacao(Resultado.ERRO, str(exc)), None, soma)

    motivos = []
    atual = versao_plano_atual.strip() if isinstance(versao_plano_atual, str) else ""
    if not atual:
        motivos.append(f"sem versão atual do plano {doc.plano_id} para comparar")
    elif atual != doc.plano_versao:
        # O plano mudou depois que o script rodou: o resultado é do plano
        # antigo, e valer para o novo é o erro que o AD-15 existe para evitar.
        motivos.append(f"plano {doc.plano_id}: o script avaliou a versão "
                       f"{doc.plano_versao}, a atual é {atual}")
    motivo_inv = _motivo_inventario(doc, inventario)
    if motivo_inv:
        motivos.append(motivo_inv)
    if motivos:
        return Importacao(Avaliacao(Resultado.INDETERMINADO, "; ".join(motivos)),
                          doc, soma)

    # Cópia profunda: a evidência segue para a ``Execucao`` e para o banco, e
    # quem mexesse numa lista dela mudaria também o documento importado.
    return Importacao(Avaliacao(doc.resultado, doc.motivo,
                                copy.deepcopy(dict(doc.evidencia))),
                      doc, soma)
