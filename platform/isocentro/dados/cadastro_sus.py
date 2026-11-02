"""Cadastro de convênio SUS por paciente.

Guarda, por paciente, se ele é SUS e o número do Cartão SUS, num JSON único na
pasta do app (ou em ``ISOCENTRO_SUS_DIR`` para compartilhar entre estações). Assim,
num tratamento futuro do MESMO paciente, o app já lembra o número e só pergunta
se quer **manter ou alterar**, em vez de digitar de novo.

O paciente é identificado por **nome + data de nascimento + registro (ID)** — os
três precisam bater para ser considerado o mesmo. Só o registro não basta: um
erro de digitação de ID não pode fazer o número SUS de um paciente cair em outro.

Módulo de lógica pura (sem Qt), para ser testado isoladamente.
"""
from __future__ import annotations

import datetime
import json
import os
import unicodedata
from pathlib import Path
from isocentro.dados import ambiente

SCHEMA = "isocentro/cadastro-sus"


# ── Localização e IO ─────────────────────────────────────────────────────────

def caminho() -> Path:
    """JSON do cadastro SUS: ``ISOCENTRO_SUS_DIR`` (rede) ou a pasta do app."""
    env = ambiente.ler("ISOCENTRO_SUS_DIR")
    if env:
        base = Path(env)
    else:
        try:
            from isocentro.dados import indice
            base = indice._app_dir()
        except Exception:  # noqa: BLE001
            base = Path(".")
    return base / "cadastro_sus.json"


def _carregar() -> dict:
    p = caminho()
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("pacientes", {})
                return d
        except Exception:  # noqa: BLE001
            pass
    return {"schema": SCHEMA, "pacientes": {}}


def _salvar(reg: dict) -> None:
    p = caminho()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)   # troca atômica — não corrompe se duas estações salvarem


# ── Identidade do paciente ───────────────────────────────────────────────────

def _norm(s) -> str:
    """Minúsculas, sem acento e sem espaço extra, para comparar identidade."""
    t = unicodedata.normalize("NFKD", str(s or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().split())


def _chave(nome, nascimento, registro) -> str:
    """Chave do paciente = registro + nome + nascimento normalizados."""
    return "|".join((_norm(registro), _norm(nome), _norm(nascimento)))


# ── Consulta / gravação ──────────────────────────────────────────────────────

def consultar(nome, nascimento, registro) -> dict | None:
    """Cadastro SUS do paciente (mesmo nome+nascimento+registro), ou ``None``.

    Sem registro não há como identificar com segurança → devolve ``None``.
    """
    if not _norm(registro):
        return None
    reg = _carregar()
    return reg["pacientes"].get(_chave(nome, nascimento, registro))


def registrar(nome, nascimento, registro, pac_sus: bool, numero_sus: str) -> bool:
    """Grava/atualiza o cadastro SUS do paciente. Devolve ``True`` se gravou.

    Sem registro (ID), não grava — não há chave estável. Falhas de escrita são
    engolidas (o cadastro é uma conveniência, não pode travar a geração).
    """
    if not _norm(registro):
        return False
    try:
        reg = _carregar()
        reg["pacientes"][_chave(nome, nascimento, registro)] = {
            "nome": str(nome or ""),
            "nascimento": str(nascimento or ""),
            "registro": str(registro or ""),
            "pac_sus": bool(pac_sus),
            "numero_sus": str(numero_sus or "") if pac_sus else "",
            "atualizado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        _salvar(reg)
        return True
    except Exception:  # noqa: BLE001
        return False


# ── O convênio do sistema responde por "é SUS?" ──────────────────────────────
#
# Desde 18/08/2026 a fonte do cadastro é o BANCO, e o convênio vem de lá com o
# número da carteirinha ("SUS - 700000000000000", ver ``capa_dados._convenio``).
# Para quem é SUS, a carteirinha É o Cartão Nacional de Saúde — que é o número
# que o popup pedia para digitar a cada ficha. Perguntar o que o sistema já
# respondeu é pedir para errar de digitação num número de quinze dígitos.

ORIGEM_CORRECAO = "correção do cadastro"

# Quinze dígitos é o Cartão Nacional de Saúde. A validação existe porque o campo
# do número no banco é a CARTEIRINHA, e nem todo convênio guarda ali um número:
# já se viu o nome do plano repetido nesse campo (ver ``capa_db``, o caso
# "Fusex - Fusex"). Um "número" que não tem cara de cartão não vai para o papel
# — a ficha volta a perguntar, que é o pedido do usuário: "se o campo estiver em
# branco ou sem o número, perguntar".
_DIGITOS_CARTAO_SUS = 15

# E não basta CONTAR os dígitos. O número do banco sai de um ``COALESCE`` de
# três colunas (ver ``capa_db._SQL_CONVENIO``): a carteirinha, o número da conta
# e, por último, o número do PLANO — que é o mesmo para todo paciente daquele
# convênio. Um plano com quinze dígitos imprimiria o MESMO número na folha de
# Registro de Tratamento de todos os pacientes do SUS, sem perguntar nada a
# ninguém. O dígito verificador separa os dois casos, e é barato.
#
# A regra do CNS: primeiro dígito 1 ou 2 (definitivo) ou 7, 8, 9 (provisório), e
# a soma dos quinze dígitos pelos pesos 15, 14, … 1 divisível por 11. As duas
# famílias fecham na mesma conta — o dígito verificador do definitivo é
# escolhido justamente para isso.
_INICIOS_CARTAO_SUS = "12789"


def _e_sus(nome: str) -> bool:
    """O nome do convênio é o SUS? Compara por PALAVRA, não por trecho.

    ``"SUS" in nome`` casaria "SUSEP" e "SUSPENSO"; e o serviço escreve o
    convênio de mais de um jeito ("SUS", "SUS/AIH", "SUS - MUNICIPAL").
    """
    palavras = "".join(c if c.isalnum() else " " for c in _norm(nome)).split()
    return "sus" in palavras


def cartao_sus_valido(digitos: str) -> bool:
    """Estes dígitos são um Cartão Nacional de Saúde?

    Não é preciosismo de formato: é a diferença entre imprimir o cartão do
    paciente e imprimir o número do plano do convênio na folha que vai para a
    sala. Ver ``_INICIOS_CARTAO_SUS``.
    """
    d = str(digitos or "")
    if len(d) != _DIGITOS_CARTAO_SUS or not d.isdigit():
        return False
    if d[0] not in _INICIOS_CARTAO_SUS:
        return False
    return sum(int(d[i]) * (15 - i) for i in range(15)) % 11 == 0


def sus_do_convenio(convenio: str) -> tuple:
    """``(é SUS?, número do cartão)`` a partir do texto de convênio do sistema.

    ``é SUS`` vem ``None`` quando NÃO DEU PARA SABER (convênio em branco) — que
    não é a mesma coisa que "não é SUS", e é a diferença entre decidir sozinho e
    perguntar.

    Sem número, ou com um número que não passa por Cartão SUS (ver
    ``cartao_sus_valido``), devolve ``(True, "")``: sabe-se que é SUS, falta o
    número. Quem chama pergunta só o que falta.
    """
    texto = str(convenio or "").strip()
    if not texto:
        return (None, "")
    # O nome é o que vem ANTES do primeiro " - " — a mesma leitura que a Capa já
    # faz para o chip do convênio (``capa.py``). Convênio com hífen no nome
    # ("SUS - MUNICIPAL") cai no lado do número e é descartado pela validação
    # de dígitos, que é o resultado certo: não há cartão ali.
    nome, _, numero = texto.partition(" - ")
    if not _e_sus(nome):
        return (False, "")
    digitos = "".join(c for c in numero if c.isdigit())
    return (True, digitos if cartao_sus_valido(digitos) else "")


def sus_do_paciente(registro: str) -> tuple:
    """``(é SUS?, número, origem, convênio)`` pelo convênio que o SISTEMA tem.

    O texto do convênio volta junto porque quem chama precisa DIZER de onde veio
    a decisão: "convênio Unimed (banco): a ficha sai sem as folhas do SUS" é um
    recado que a pessoa confere de relance; "não é SUS" ela só pode acreditar.

    Só o BANCO e a CORREÇÃO MANUAL respondem aqui — nesta ordem inversa, que a
    correção é a última palavra (existe justamente porque o cadastro erra).

    O espelho e os relatórios exportados ficam de fora **de propósito**: eles são
    retrato de outro dia, e um convênio velho decidiria sozinho se a folha de
    Registro de Tratamento sai ou não sai no maço. Reserva que decide calada é o
    contrário da regra da casa — sem o banco, ``None``, e o popup pergunta como
    sempre perguntou.
    """
    alvo = str(registro or "").strip()
    if not alvo:
        return (None, "", "", "")
    convenio, origem = "", ""
    try:
        from isocentro.banco import capa_db
        from isocentro.banco import capa_dados
        if capa_db.configurado():
            cad = capa_db.cadastro_do_paciente(alvo)
            if cad is not None and str(cad.convenio or "").strip():
                convenio, origem = cad.convenio, capa_dados.ORIGEM_BANCO
    except Exception:  # noqa: BLE001 — sem banco, quem pergunta é o popup
        pass
    try:
        from isocentro.dados import correcoes
        corrigido = str(correcoes.ler(alvo).get("convenio", "") or "").strip()
        if corrigido:
            convenio, origem = corrigido, ORIGEM_CORRECAO
    except Exception:  # noqa: BLE001
        pass
    if not convenio:
        return (None, "", origem, "")
    e_sus, numero = sus_do_convenio(convenio)
    return (e_sus, numero, origem, convenio)
