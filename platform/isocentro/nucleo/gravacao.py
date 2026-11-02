"""``gravar``: a única porta de gravação do ISOCENTRO (R-18).

Fonte: AD-3 (dono único), AD-4 (dado e log na mesma transação), AD-5 (nada se
apaga nem se edita: correção é registro novo) e AD-27 (registro tabela →
dono) da espinha; CAP-4 da spec Fundação.

Por que tudo passa por aqui: com cada módulo abrindo a própria transação no
adaptador, bastaria um esquecer a linha de log para existir dado sem autoria
— e ninguém notaria, porque o dado aparece na tela igualzinho. Aqui o módulo
entrega o registro e o núcleo devolve "gravado" ou "não gravado, com motivo";
quem abre a transação é a porta, e quem garante o tudo-ou-nada é o banco.

As conferências daqui (dono, nomes, autoria) são para o motivo sair legível
antes de abrir transação. Não são a garantia: o banco repete a do dono no
gatilho do log, e só dá ao app INSERT e SELECT. Quem chama sem passar por
aqui continua sem conseguir apagar, editar ou gravar em tabela alheia.

Sem Qt, banco, rede nem arquivo: o banco entra pela ``PortaDoBanco``, que o
``adaptadores/postgres`` implementa. Capacidade, clínica e sessão da pessoa
são da R-19: por enquanto o ``quem`` vem de quem chama.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional, Protocol

# Os mesmos padrões das restrições de ``nucleo.dono_tabela``: nome em
# minúsculas sem acento (Convenções da espinha). Coluna fora disso não é
# recusada só por estilo — é o que impede um nome de coluna de carregar SQL.
_NOME = r"[a-z][a-z0-9_]*"
_MODULO = re.compile(rf"^{_NOME}$")
_TABELA = re.compile(rf"^{_NOME}\.{_NOME}$")
_COLUNA = re.compile(rf"^{_NOME}$")

# Colunas que o registro não escolhe: o ``id`` é do banco (e é o que vai para
# o log); a correção anda pelo log, e não por uma coluna que cada módulo
# chamaria de um jeito.
COLUNAS_RESERVADAS = frozenset({"id", "substitui"})


class GravacaoRecusada(Exception):
    """Não gravado, com o motivo. Nada foi escrito: nem dado, nem log."""


@dataclass(frozen=True)
class LinhaNova:
    """O que o módulo informa à linha de log; o resto é do gatilho do banco."""
    quem: str
    modulo: str
    tabela: str
    substitui: Optional[str]
    versao_origem: Optional[str]


@dataclass(frozen=True)
class Gravado:
    tabela: str
    registro: str
    posicao: int


class PortaDoBanco(Protocol):
    """O que o núcleo precisa do banco para gravar."""

    def dono_de(self, tabela: str) -> Optional[str]:
        """O módulo dono da tabela no registro, ou ``None`` se ela não consta."""
        ...

    def inserir_com_log(self, tabela: str, dados: Mapping[str, Any],
                        linha: LinhaNova) -> Gravado:
        """O registro e a linha de log numa transação só, tudo ou nada.

        Qualquer falha desfaz as duas coisas e levanta ``GravacaoRecusada``.
        """
        ...


def _texto_opcional(valor: Optional[str], nome: str) -> Optional[str]:
    if valor is None:
        return None
    if not isinstance(valor, str) or not valor.strip():
        raise GravacaoRecusada(f"{nome} vazio: sem ele, informe None")
    return valor


def gravar(porta: PortaDoBanco, *, modulo: str, tabela: str,
           dados: Mapping[str, Any], quem: str,
           versao_origem: Optional[str] = None,
           substitui: Optional[str] = None) -> Gravado:
    """Grava ``dados`` em ``tabela`` e a linha de log, na mesma transação.

    ``substitui`` é o id do registro que este corrige (AD-5): o anterior
    continua lá, e o vigente é o que ninguém substitui.
    ``versao_origem`` é a versão do dado de onde este saiu (AD-4) — o RT Plan,
    a carga do ``variandw`` —, ou ``None`` se ele nasceu aqui.
    """
    if not isinstance(modulo, str) or not _MODULO.match(modulo):
        raise GravacaoRecusada(f"nome de módulo inválido: {modulo!r}")
    if not isinstance(tabela, str) or not _TABELA.match(tabela):
        raise GravacaoRecusada(
            f"tabela {tabela!r} fora do formato <modulo>.<tabela>")
    if not isinstance(quem, str) or not quem.strip():
        # Linha de log sem autoria é exatamente o que o log existe para não
        # ter (AD-4).
        raise GravacaoRecusada("gravação sem autor")
    versao_origem = _texto_opcional(versao_origem, "versao_origem")
    substitui = _texto_opcional(substitui, "substitui")
    if not isinstance(dados, Mapping) or not dados:
        raise GravacaoRecusada("registro sem nenhum campo")
    for coluna in dados:
        if not isinstance(coluna, str) or not _COLUNA.match(coluna):
            raise GravacaoRecusada(f"nome de coluna inválido: {coluna!r}")
        if coluna in COLUNAS_RESERVADAS:
            raise GravacaoRecusada(
                f"a coluna {coluna!r} não é do registro: o id é do banco e a "
                "correção vai em 'substitui'")

    dono = porta.dono_de(tabela)
    if dono is None:
        raise GravacaoRecusada(
            f"a tabela {tabela} não está no registro tabela → dono")
    if dono != modulo:
        raise GravacaoRecusada(
            f"a tabela {tabela} é do módulo {dono}, não de {modulo} (AD-3)")

    linha = LinhaNova(quem=quem, modulo=modulo, tabela=tabela,
                      substitui=substitui, versao_origem=versao_origem)
    # Cópia somente leitura: a porta não deve poder mudar o dicionário de quem
    # chamou, e quem chamou não deve mudá-lo enquanto a porta grava.
    return porta.inserir_com_log(tabela, MappingProxyType(dict(dados)), linha)
