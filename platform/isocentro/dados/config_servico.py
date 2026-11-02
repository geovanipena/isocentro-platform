"""Configuração do SERVIÇO — o que o admin decide uma vez, para todo mundo.

Onde ficam os relatórios exportados e onde as simulações são gravadas não são
preferências de quem está sentado na estação: são endereços do serviço. Um
técnico que aponte a pasta errada na máquina dele faz a capa nascer vazia ali —
e ninguém mais vê o que mudou.

Até aqui essa escolha morava no ``QSettings``, que no Windows é
``HKEY_CURRENT_USER``: valia para **um usuário do Windows, numa máquina**. O
admin apontava a pasta certa, e a estação ao lado — ou o mesmo computador com
outro login — continuava sem achar relatório nenhum. É o problema que este
módulo resolve: a escolha vira um arquivo ao lado do índice central, no mesmo
lugar em que já moram os usuários e as correções de cadastro, e vale para todas
as estações que compartilham essa pasta.

Quem escolheu e quando ficam junto. Apontar a pasta de onde sai um documento de
paciente não pode ser anônimo.

A variável de ambiente correspondente (``ISOCENTRO_CAPA_DIR``, ``ISOCENTRO_SIMULACOES``)
continua tendo precedência sobre o que está aqui: ela é decisão de instalação,
posta por quem montou a estação, e não deve ser desfeita à distância.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import time
import uuid
from pathlib import Path
from isocentro.dados import ambiente

_LOG = logging.getLogger(__name__)

_ENV = "ISOCENTRO_CONFIG"
_ARQUIVO = "config_servico.json"

# As chaves que este arquivo guarda. Fora desta lista nada entra: o arquivo é
# lido por todas as estações e não é lugar para despejo de estado de tela.
PASTA_RELATORIOS = "capa_pasta_relatorios"
RAIZ_SIMULACOES = "simulacoes_raiz"
# Servidor do data warehouse da Varian (ver :mod:`capa_db`). Vazio = o app lê
# só os relatórios exportados, como sempre leu. Não há senha aqui: a conexão é
# por autenticação Windows, e é por isso que este arquivo pode ser um JSON
# legível na pasta compartilhada.
DB_SERVIDOR = "db_servidor"
DB_BANCO = "db_banco"
# Onde a exportação automática grava os planos que traz do ARIA (ver
# :mod:`gatilho`). Entra aqui pelo mesmo motivo das outras: é decisão de
# SERVIÇO, não de estação. Configurada por máquina, cada uma gravaria num
# lugar, e a estação esquecida gravaria na pasta do programa sem reclamar —
# quem administra precisa poder afirmar que tudo cai no servidor.
PASTA_EXPORTACAO = "exportacao_pasta"
# A rede DICOM do ARIA (ver :mod:`isocentro.adaptadores.dicom.rede`). Entraram em 14/09/2026, e não
# por simetria com as de cima: a varredura passou a poder rodar por TAREFA
# AGENDADA, e tarefa agendada roda com OUTRA conta do Windows.
#
# ``ambiente.ler`` é ``os.environ`` puro, e variável de USUÁRIO não atravessa
# conta: com os ``ISOCENTRO_DICOM_*`` definidos no usuário interativo da
# concentradora, a tarefa agendada chamaria ``dicom_rede.configurado()`` →
# falso e não exportaria NADA — com o Agendador do Windows verde, porque o
# processo terminaria sem erro. É a falha silenciosa de sempre, agora sem
# ninguém olhando a tela.
#
# Aqui a configuração vale para qualquer conta da máquina, o admin a aponta
# pela tela, e a variável da estação continua vencendo quando existe.
DICOM_SERVIDOR = "dicom_servidor"
DICOM_AE_REMOTO = "dicom_ae_remoto"
DICOM_AE_LOCAL = "dicom_ae_local"
DICOM_AE_DESTINO = "dicom_ae_destino"
# QUAL máquina varre (ver ``gatilho.disponivel``). Entrou em 18/09/2026 como
# consequência direta das quatro de cima: com a rede DICOM neste arquivo, que é
# o MESMO para todas as estações, o relógio de cada app aberto encontrava o
# portão aberto — e todas varriam, disputando a trava da pasta e pedindo C-MOVE
# que o ARIA entrega só na máquina cadastrada no destino. A decisão de 11/09
# ("só a concentradora varre") valia enquanto a rede DICOM era variável de UMA
# máquina; no arquivo, alguém tem de dizer o nome dela.
CONCENTRADORA = "concentradora"
CHAVES = (PASTA_RELATORIOS, RAIZ_SIMULACOES, DB_SERVIDOR, DB_BANCO,
          PASTA_EXPORTACAO, DICOM_SERVIDOR, DICOM_AE_REMOTO, DICOM_AE_LOCAL,
          DICOM_AE_DESTINO, CONCENTRADORA)


def caminho() -> Path:
    """Arquivo da configuração: ``ISOCENTRO_CONFIG`` ou ao lado do índice.

    Mesma convenção de ``usuarios.json`` e das correções de cadastro — se a
    pasta do programa é compartilhada, a configuração acompanha sozinha.
    """
    env = ambiente.ler(_ENV)
    if env:
        return Path(env) / _ARQUIVO
    try:
        from isocentro.dados import indice
        return indice._app_dir() / _ARQUIVO
    except Exception:  # noqa: BLE001
        return Path(".") / _ARQUIVO


def ler() -> dict:
    """A configuração gravada ({} se não houver, ou se estiver ilegível).

    Ilegível não derruba nada: sem configuração o programa cai nos padrões e na
    procura automática, que é como ele já funcionava antes de existir admin.
    """
    p = caminho()
    try:
        with open(p, encoding="utf-8") as fh:
            dados = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        _LOG.exception("Configuração do serviço ilegível em %s", p)
        return {}
    return dados if isinstance(dados, dict) else {}


def valor(chave: str) -> str:
    """O que está gravado para ``chave`` ("" se nada)."""
    if chave not in CHAVES:
        return ""
    return str((ler().get(chave) or {}).get("valor", "") or "")


def autoria(chave: str) -> tuple[str, str]:
    """``(quem, quando)`` da última mudança desta chave."""
    entrada = ler().get(chave) or {}
    return str(entrada.get("por", "")), str(entrada.get("em", ""))


def definir(chave: str, caminho_novo: str, usuario: str = "") -> bool:
    """Grava a escolha do admin. Devolve se conseguiu gravar.

    Falhar aqui **não** é fatal e não levanta: a pasta compartilhada pode estar
    somente-leitura ou fora do ar, e nesse caso a escolha ainda vale para esta
    sessão — só não vai durar nem chegar às outras estações. Quem chamou avisa.
    """
    if chave not in CHAVES:
        return False
    dados = ler()
    novo = str(caminho_novo or "").strip()
    if novo:
        dados[chave] = {
            "valor": novo,
            "por": str(usuario or ""),
            "em": datetime.datetime.now().isoformat(timespec="seconds"),
        }
    else:
        # "" devolve o serviço ao padrão (procura automática): é assim que se
        # desfaz um apontamento errado sem ter de adivinhar o valor anterior.
        dados.pop(chave, None)
    return _gravar(dados)


def _substituir(tmp: str, destino) -> None:
    """``os.replace`` que insiste enquanto o Windows disser "acesso negado".

    No Windows, arquivo recém-apagado fica em *delete pending*: o próximo
    acesso recebe ``PermissionError`` em vez de "não existe" — o mesmo
    comportamento que a docstring de ``indice.travar_arquivo`` já documenta,
    onde ele fazia perder 32 fichas em 1600.

    Aqui ele aparecia como falha de gravação da configuração do serviço: a
    suíte em ordem ALEATÓRIA acusava de 2 a 12 ocorrências por rodada, com a
    mesma semente e a mesma ordem, todas neste ``os.replace``. Não é
    dependência de ordem, é corrida — e a repetição resolve porque a disputa
    passa em milissegundos. Sem ela, o admin levava um "não consegui gravar"
    por algo que já teria dado certo na tentativa seguinte.

    Só ``PermissionError`` é repetido: pasta somente-leitura ou fora do ar
    devolve outro erro, e insistir nesse caso só faria a tela demorar para
    dizer o que já se sabe.
    """
    for tentativa in range(_REPLACE_TENTATIVAS):
        try:
            os.replace(tmp, destino)
            return
        except PermissionError:
            if tentativa == _REPLACE_TENTATIVAS - 1:
                raise
            time.sleep(_REPLACE_ESPERA_S)


# Quantas vezes insistir no ``os.replace`` e o intervalo entre as tentativas.
# Cinco × 50 ms = 250 ms no pior caso, que é invisível para quem clicou em
# salvar e sobra para a disputa passar (ver ``_gravar``).
_REPLACE_TENTATIVAS = 5
_REPLACE_ESPERA_S = 0.05


def _gravar(dados: dict) -> bool:
    """Escrita atômica, sob a mesma trava do índice central.

    Duas estações gravando o arquivo inteiro ao mesmo tempo se apagariam — o
    mesmo problema já medido nas correções de cadastro.
    """
    p = caminho()
    try:
        from isocentro.dados import indice
        trava = indice.travar_arquivo(p.with_suffix(".json.lock"))
    except Exception:  # noqa: BLE001
        from contextlib import nullcontext
        trava = nullcontext()
    # Só o PID no nome não basta: duas gravações do MESMO processo (a tela de
    # admin e uma reentrada pelo Qt) escreveriam no mesmo temporário, e a
    # segunda truncaria o que a primeira ainda estava usando.
    tmp = str(p) + f".{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        with trava:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(dados, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            _substituir(tmp, p)
        return True
    except OSError:
        _LOG.exception("Não consegui gravar a configuração do serviço em %s", p)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False
