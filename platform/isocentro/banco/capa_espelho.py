"""Espelho local do que o banco já respondeu, por paciente.

A fonte da capa passou a ser o data warehouse. Isso resolve o agendador e a
janela de período, mas cria uma dependência nova: se o banco não responde, não
há capa — e paciente na mesa não espera a rede voltar.

A reserva **não podem ser os relatórios exportados**. Ninguém vai reexportá-los
depois da migração: eles congelam no dia em que foram gerados e envelhecem
juntos, de modo que a emergência de daqui a um mês serviria um retrato de um mês
atrás — convênio que mudou, prescrição que foi revista. Reserva que mente é pior
que reserva nenhuma, porque ela sai impressa com cara de dado bom.

O espelho é outra coisa: **cada paciente é gravado no instante em que o banco o
entregou**. Quem foi aberto hoje tem espelho de hoje. E a idade é *daquele*
paciente, não de um arquivo global — então a tela consegue dizer "este cadastro
é de terça" em vez de "os relatórios são de três semanas atrás".

Fica ao lado do índice central, como os usuários e as correções: espelhado numa
estação, serve às outras.

Nada aqui é fonte de verdade. É cópia do que o banco disse, com a data em que
disse, e a tela sempre avisa quando a capa saiu daqui.
"""
from __future__ import annotations

import base64
import dataclasses
import datetime
import json
import logging
import os
from pathlib import Path
from typing import Optional

from isocentro.banco import capa_dados
from isocentro.dados import ambiente

_LOG = logging.getLogger(__name__)

_ENV = "ISOCENTRO_ESPELHO"
_PASTA = "espelho_capa"

# Formato do arquivo. Se um dia a estrutura mudar, o espelho antigo é
# descartado em vez de lido errado — dado de paciente não se adivinha.
VERSAO = 1

# Depois de quantos dias um espelho deixa de servir e é apagado.
#
# Ele guarda dado de paciente (nome, nascimento, convênio, contato, CID,
# diagnóstico e a 3×4). Em JSON claro, como o resto do que o app grava ao lado
# do índice (``registro_fichas.json``, ``correcoes_capa.json``,
# ``cadastro_sus.json``) — a proteção é a da pasta compartilhada, e criptografar
# só este arquivo daria sensação de segurança sem mudar quem alcança a pasta.
#
# O que faltava era FIM. Reserva sem prazo vira arquivo permanente de dado
# clínico numa pasta de rede, e um espelho de seis meses atrás é pior que
# nenhum: sai impresso com aviso, mas sai. Sessenta dias cobre com folga a
# janela em que um paciente volta ao aparelho.
DIAS_PARA_EXPIRAR = 60


def pasta() -> Path:
    """Onde o espelho mora: ``ISOCENTRO_ESPELHO`` ou ao lado do índice."""
    env = ambiente.ler(_ENV)
    if env:
        return Path(env)
    try:
        from isocentro.dados import indice
        return indice._app_dir() / _PASTA
    except Exception:  # noqa: BLE001
        return Path(".") / _PASTA


def _arquivo(registro: str) -> Path:
    # Pelo ID NORMALIZADO: o mesmo registro chega grafado de vários jeitos
    # ("9000001CEL", " 9000001-cel "), e cada grafia viraria um espelho
    # diferente — o paciente pareceria não ter reserva justo na emergência.
    chave = capa_dados.normalizar_id(registro)
    # O ID é alfanumérico depois de normalizado, mas o arquivo é criado a partir
    # de dado externo: filtrar o que não for alfanumérico impede que um registro
    # estranho escreva fora da pasta.
    seguro = "".join(c for c in chave if c.isalnum())
    return pasta() / f"{seguro}.json"


def _serializar(cad, prescricoes, foto) -> dict:
    return {
        "versao": VERSAO,
        "em": datetime.datetime.now().isoformat(timespec="seconds"),
        "cadastro": dataclasses.asdict(cad),
        "prescricoes": [dataclasses.asdict(p) for p in prescricoes],
        # A 3×4 vai junto: é ela que confirma, na sala, que o paciente é o da
        # folha. Uma capa de emergência sem foto perde justamente a conferência
        # que não depende de ninguém saber ler o cadastro.
        "foto": base64.b64encode(foto).decode("ascii") if foto else "",
    }


def guardar(registro: str, cadastro, prescricoes=(), foto=None) -> bool:
    """Grava o que o banco acabou de responder. Devolve se conseguiu.

    **Nunca levanta.** Falhar aqui não pode atrapalhar a capa que está saindo
    agora: o espelho é para depois. Escrita atômica, porque a pasta é
    compartilhada e duas estações podem espelhar o mesmo paciente ao mesmo
    tempo — e um JSON pela metade seria lido como cadastro na emergência.
    """
    if not registro or cadastro is None:
        return False
    _limpar_vencidos()
    alvo = _arquivo(registro)
    tmp = str(alvo) + f".{os.getpid()}.tmp"
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_serializar(cadastro, list(prescricoes), foto), fh,
                      ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, alvo)
        return True
    except Exception:  # noqa: BLE001
        _LOG.warning("Não consegui espelhar %s", registro, exc_info=True)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False


def _limpar_vencidos() -> int:
    """Apaga os espelhos vencidos. Devolve quantos saíram.

    Roda na GRAVAÇÃO, não num temporizador: é o momento em que já se está
    mexendo na pasta, e uma instalação parada não precisa de faxina. Falhar
    aqui é irrelevante para quem está montando a capa agora.
    """
    limite = datetime.datetime.now() - datetime.timedelta(days=DIAS_PARA_EXPIRAR)
    saíram = 0
    try:
        arquivos = list(pasta().glob("*.json"))
    except OSError:
        return 0
    for arq in arquivos:
        try:
            if datetime.datetime.fromtimestamp(arq.stat().st_mtime) < limite:
                arq.unlink()
                saíram += 1
        except OSError:
            continue
    if saíram:
        _LOG.info("Espelho: %d paciente(s) vencido(s) removido(s).", saíram)
    return saíram


def _volume(d: dict):
    return capa_dados.Volume(**{k: v for k, v in d.items()
                                if k in {f.name for f in
                                         dataclasses.fields(capa_dados.Volume)}})


def _de_dict(classe, d: dict):
    """Reconstrói ignorando campo que não existe mais.

    Espelho gravado por uma versão anterior do app não pode derrubar a atual —
    ele é justamente o que se lê quando as coisas já não estão bem.
    """
    campos = {f.name for f in dataclasses.fields(classe)}
    return classe(**{k: v for k, v in d.items() if k in campos})


def ler(registro: str):
    """``(cadastro, prescricoes, foto, quando)`` do espelho, ou ``None``.

    ``quando`` é um ``datetime`` — a tela precisa dele para dizer a IDADE deste
    paciente, que é a única informação que separa "espelho de hoje" de "espelho
    de um mês atrás".
    """
    alvo = _arquivo(registro)
    try:
        with open(alvo, encoding="utf-8") as fh:
            dados = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        _LOG.warning("Espelho ilegível: %s", alvo)
        return None
    if dados.get("versao") != VERSAO:
        return None
    # Vencido não se lê nem por emergência: passou do prazo, o dado clínico já
    # não é confiável o bastante para virar papel, mesmo com aviso.
    try:
        if (datetime.datetime.now()
                - datetime.datetime.fromisoformat(dados["em"])
                ).days > DIAS_PARA_EXPIRAR:
            return None
    except (KeyError, ValueError):
        return None
    try:
        cad = _de_dict(capa_dados.Cadastro, dados.get("cadastro") or {})
        prescricoes = []
        for d in dados.get("prescricoes") or []:
            p = _de_dict(capa_dados.Prescricao, d)
            p.volumes = [_volume(v) for v in (d.get("volumes") or [])]
            prescricoes.append(p)
        foto = base64.b64decode(dados["foto"]) if dados.get("foto") else None
        quando = datetime.datetime.fromisoformat(dados["em"])
    except Exception:  # noqa: BLE001
        _LOG.warning("Espelho corrompido: %s", alvo, exc_info=True)
        return None
    return cad, prescricoes, foto, quando


def idade_em_dias(registro: str) -> Optional[int]:
    lido = ler(registro)
    if lido is None:
        return None
    return max(0, (datetime.datetime.now() - lido[3]).days)


def quantos() -> int:
    """Quantos pacientes há espelhados — para a tela poder informar."""
    try:
        return sum(1 for _ in pasta().glob("*.json"))
    except OSError:
        return 0
