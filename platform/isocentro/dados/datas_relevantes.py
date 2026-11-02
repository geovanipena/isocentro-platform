r"""O quadro de **Datas Relevantes** da Fichinha: eventos escritos à mão.

**Por que existe.** É o único dado desta tela que ninguém mais guarda. A
Documentação e as altas vêm do ARIA, as fichas vêm do índice central — mas
"auditoria da CQ no dia 3", "férias do Fulano" e "recesso de Natal" não estão
em sistema nenhum, e hoje moram num papel colado no monitor de quem lembrou de
colar. Pedido pelo usuário em 22/09/2026, junto com a reforma da tela.

**É do SERVIÇO, não da estação** (decisão dele): o arquivo fica ao lado do
índice central e todas as estações leem o mesmo quadro. Um quadro por máquina
seria três quadros divergentes numa clínica com três estações, e o evento que
importa é justamente o que todo mundo precisa ver.

**Nada vem do banco.** Os eventos nascem do "Nova" e só de lá — foi o que se
pediu, contra a alternativa de puxar datas de tratamento do ARIA. Quem escreve
é quem sabe.

O ciclo ler→alterar→gravar vai sob o mesmo lock de sistema operacional do
``gatilho_registro``: duas estações editando ao mesmo tempo gravam uma por cima
da outra, e some o evento que a outra pessoa acabou de criar.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from isocentro.dados import ambiente
from isocentro.dados import indice
from isocentro.dados import registro_json

_LOG = logging.getLogger(__name__)

# Onde o quadro mora. Ao lado do índice central, porque é da mesma natureza:
# estado do SERVIÇO, e não configuração de estação (ver a regra da pasta do
# serviço no CLAUDE.md).
ENV_ARQUIVO = "ISOCENTRO_DATAS_RELEVANTES"
NOME_PADRAO = "datas_relevantes.json"

_VERSAO = 1


def caminho() -> Path:
    """O arquivo, pela precedência do projeto: variável → serviço → padrão."""
    escolhido = ambiente.ler(ENV_ARQUIVO)
    if escolhido:
        return Path(escolhido)
    return Path(indice.REGISTRO_PATH).with_name(NOME_PADRAO)


def _lock() -> Path:
    return caminho().with_name(caminho().name + ".lock")


def _vazio() -> dict:
    return {"versao": _VERSAO, "eventos": []}


def ler() -> list:
    """Os eventos do quadro. Arquivo ausente é quadro vazio; ilegível NÃO é.

    A diferença importa: "ninguém criou evento ainda" é verdade e vira lista
    vazia; um JSON truncado (queda no meio da escrita, disco cheio) tem de
    GRITAR. Virando lista vazia em silêncio, a primeira gravação depois dele
    apagaria o quadro inteiro do serviço — e ninguém desconfia de uma tela que
    diz "nenhum evento".
    """
    alvo = caminho()
    if not alvo.exists():
        return []
    dados = json.loads(alvo.read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError(f"{alvo} não contém um objeto JSON")
    eventos = dados.get("eventos")
    if not isinstance(eventos, list):
        raise ValueError(f"{alvo} não tem a lista de eventos")
    return [e for e in eventos if isinstance(e, dict)]


def _gravar(eventos: list) -> None:
    alvo = caminho()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    # A gravação atômica do ``registro_json``, pelo mesmo motivo do
    # ``gatilho_registro``: escrita interrompida não pode deixar o arquivo
    # truncado, porque um arquivo truncado é o quadro do serviço inteiro.
    registro_json._gravar_json(alvo, {"versao": _VERSAO, "eventos": eventos})


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def criar(data: str, titulo: str, tipo: str = "", nota: str = "",
          por: str = "") -> dict:
    """Põe um evento no quadro e devolve o que foi gravado.

    O ``id`` é sorteado aqui e não derivado do título: dois eventos com o mesmo
    nome em datas diferentes ("Férias") são coisas diferentes, e uma chave
    derivada faria o segundo sobrescrever o primeiro.
    """
    evento = {
        "id": uuid.uuid4().hex,
        "data": str(data or "").strip(),
        "titulo": str(titulo or "").strip(),
        "tipo": str(tipo or "").strip(),
        "nota": str(nota or "").strip(),
        "por": str(por or "").strip(),
        "em": _agora(),
    }
    with indice.travar_arquivo(_lock()):
        eventos = ler()
        eventos.append(evento)
        _gravar(eventos)
    _LOG.info("Data relevante criada: %s (%s)", evento["titulo"],
              evento["data"])
    return evento


def alterar(identificador: str, **campos) -> bool:
    """Altera um evento. Devolve ``False`` quando ele já não existe.

    Relê dentro do lock em vez de gravar a lista que a tela tinha: entre a tela
    ter sido desenhada e o clique em Editar, alguém na outra estação pode ter
    criado um evento — e gravar a lista da tela o apagaria.
    """
    with indice.travar_arquivo(_lock()):
        eventos = ler()
        for e in eventos:
            if e.get("id") != identificador:
                continue
            for chave in ("data", "titulo", "tipo", "nota"):
                if chave in campos:
                    e[chave] = str(campos[chave] or "").strip()
            e["em"] = _agora()
            _gravar(eventos)
            return True
    return False


def excluir(identificador: str) -> bool:
    """Tira um evento do quadro. ``False`` quando ele já não estava lá."""
    with indice.travar_arquivo(_lock()):
        eventos = ler()
        restantes = [e for e in eventos if e.get("id") != identificador]
        if len(restantes) == len(eventos):
            return False
        _gravar(restantes)
    _LOG.info("Data relevante excluída: %s", identificador)
    return True
