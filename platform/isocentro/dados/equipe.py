"""Cadastro de **médicos e físicos** do serviço: ler, unificar e gravar.

Saiu do ``gui.py`` em 25/08/2026, e não por tamanho: o painel de Equipe das
Configurações e o formulário da bancada precisam dos MESMOS quatro acessos, e
com eles dentro do ``gui`` o módulo de administração não teria como usá-los sem
importar o ``gui`` de volta — um ciclo.

As listas canônicas moram aqui desde a R-58 (22/10/2026); de :mod:`dicom_rt`
vem só o algoritmo de casar grafias da mesma pessoa.
O arquivo é por ESTAÇÃO (``~/.isocentro_*.json``) e guarda apenas o que
DIVERGE do padrão — ver ``_cadastro_equipe``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from isocentro.dicom import dicom_rt
from isocentro.dominio import constantes

_LOG = logging.getLogger(__name__)


# ── As listas canônicas ──────────────────────────────────────────────────────
# Moravam no ``dicom_rt`` até a R-58 (22/10/2026), e este módulo importava o
# leitor de DICOM só para saber quem é da equipe.
#
# Campos DICOM como ReviewerName/OperatorsName frequentemente trazem o médico
# que aprovou o plano, não o físico. Para não popular "Físico" com nome de
# médico, casamos o nome do DICOM contra estas listas canônicas e só aceitamos
# um candidato que realmente pertença à equipe correspondente.
FISICOS = (
    "Adriano Henrique Dal Moro",
    "Geovani Pires Pena",
    "Isabela Lacerda",
    "Leonardo de Teles Quintela",
    "Marcelo Assef Valadares",
    "Mario Sergio",
    "Nathalia Bittencourt",
)

MEDICOS = (
    "Ana Fatima Albuquerque",
    "Barbara Fontes Moura Peixoto",
    "Camila Sampaio",
    "Carolina Monteverde Furtado",
    "Fernando Batista Rezende",
    "Jean Teixeira de Prado",
    "Keiko Harumi Sato Nakamura",
    "Lais Toscano Mayer João",
    "Luciana Pessanha de Paula Alencar Cardoso",
    "Luiz Otavio de Castro e Souza",
    "Nathalia Ramalho Ogawa",
    "Nicole Mayer Arruda Falcao",
    "Paula Monteiro Aragao",
    "Rubens Augusto Leal Júnior",
    "Thaís de Toledo Lima Saldanha",
    "Thaís Franco Sartori",
)

# Como cada médico é tratado por escrito. É uma TABELA, e não uma dedução do
# primeiro nome, porque dedução erra: "Lais", "Thaís", "Jean" e "Keiko" caem de
# qualquer lado, e regra por terminação em "a" tropeça em "Luciana" × "Jean". E
# "Dr." fixo — que foi o pedido original — erraria com a maioria desta equipe.
#
# Nome que não estiver aqui sai SEM prefixo: prefixo errado é pior que prefixo
# nenhum, e uma médica tratada por "Dr." na faixa de identidade do paciente é
# exatamente o tipo de descuido que faz duvidar do resto da tela.
TRATAMENTO_MEDICO = {
    "Ana Fatima Albuquerque": "Dra.",
    "Barbara Fontes Moura Peixoto": "Dra.",
    "Camila Sampaio": "Dra.",
    "Carolina Monteverde Furtado": "Dra.",
    "Fernando Batista Rezende": "Dr.",
    "Jean Teixeira de Prado": "Dr.",
    "Keiko Harumi Sato Nakamura": "Dra.",
    "Lais Toscano Mayer João": "Dra.",
    "Luciana Pessanha de Paula Alencar Cardoso": "Dra.",
    "Luiz Otavio de Castro e Souza": "Dr.",
    "Nathalia Ramalho Ogawa": "Dra.",
    "Nicole Mayer Arruda Falcao": "Dra.",
    "Paula Monteiro Aragao": "Dra.",
    "Rubens Augusto Leal Júnior": "Dr.",
    "Thaís de Toledo Lima Saldanha": "Dra.",
    "Thaís Franco Sartori": "Dra.",
}


def tratamento_do_medico(nome: str) -> str:
    """``"Dra."``, ``"Dr."`` ou ``""`` para ``nome``.

    Casa também a grafia do banco contra a canônica (``mesma_pessoa``): o DW
    devolve "Ana Fátima de Paula Brandao Albuquerque" onde a lista tem "Ana Fatima
    Albuquerque", e sem isso o prefixo sumiria justamente nos nomes completos.
    """
    n = str(nome or "").strip()
    if not n:
        return ""
    if n in TRATAMENTO_MEDICO:
        return TRATAMENTO_MEDICO[n]
    return TRATAMENTO_MEDICO.get(dicom_rt.mesma_pessoa(n, MEDICOS) or "", "")


def medico_por_extenso(nome: str) -> str:
    """``"Nicole Mayer Arruda Falcao"`` → ``"Dra. Nicole Mayer Arruda Falcao"``.

    Sem prefixo quando não se sabe, e sem sobra de espaço quando não há prefixo.
    """
    n = str(nome or "").strip()
    return f"{tratamento_do_medico(n)} {n}".strip()


# Quem atende no SAT (Synergy). Os demais nomes das listas canônicas são da
# Clinica (TrueBeam/VitalBeam, 6EX, 600CD). Isto é só o PADRÃO de fábrica: a
# unidade de cada pessoa é editável em Configurações → Equipe e o que estiver
# gravado lá tem prioridade (ver ``unidade_da_pessoa``) — assim contratar alguém
# não exige mexer no código nem republicar o executável.
EQUIPE_SAT = (
    "Adriano Henrique Dal Moro",
    "Camila Sampaio",
    "Fernando Batista Rezende",
    "Isabela Lacerda",
)


def unidade_da_pessoa(nome: str, unidades=None) -> str:
    """Unidade em que ``nome`` atende: "Clinica", "SAT" ou "" (todas).

    ``unidades``: o que o cadastro do usuário gravou ({nome: unidade}), que vem
    na frente do padrão de fábrica. Nome que não está em lista nenhuma foi
    acrescentado por quem usa o app e ainda não tem unidade escolhida: sai como
    "" e aparece em TODAS as máquinas — melhor oferecer demais do que esconder o
    nome de quem vai assinar. Quem quiser precisão marca a unidade no cadastro.
    """
    if unidades and nome in unidades:
        return str(unidades[nome] or "")
    if nome in EQUIPE_SAT:
        return "SAT"
    if nome in MEDICOS or nome in FISICOS:
        return constantes.UNIDADE_PADRAO
    # Mesma pessoa com outra grafia ("Ana Fátima de Paula Brandao Albuquerque" para
    # "Ana Fatima Albuquerque"): herda a unidade dela, senão o cadastro de cada
    # serviço — que costuma trazer o nome completo — escaparia do filtro.
    canonico = dicom_rt.mesma_pessoa(nome, MEDICOS + FISICOS)
    if canonico:
        return "SAT" if canonico in EQUIPE_SAT else constantes.UNIDADE_PADRAO
    return ""


def equipe_da_maquina(nomes, maquina: str | None, unidades=None) -> list:
    """Filtra uma lista de médicos/físicos para a ``maquina`` dada.

    Cada máquina é de uma unidade (``constantes.unidade_da_maquina``) e cada
    pessoa atende numa delas (``unidade_da_pessoa``): a ficha oferece quem é da
    unidade da máquina, mais quem não tem unidade definida. Sem máquina (ficha
    ainda sem plano carregado) ou com máquina desconhecida, devolve a lista
    inteira — é melhor oferecer demais do que esconder o nome de quem vai
    assinar.

    ``nomes`` é a lista do cadastro, que já vem com a lista canônica mesclada
    (``_cadastro_equipe``). Esta função NÃO repõe nome nenhum a partir da
    canônica: depois da mesclagem, um nome que falta ali é um nome que o usuário
    apagou em Configurações → Equipe, e repor desfaria a remoção — a 🗑 não
    surtia efeito nenhum nos combos da ficha.

    ``unidades``: unidades gravadas no cadastro ({nome: unidade}).

    Sai sempre em ordem alfabética (ver ``ordem_alfabetica``).
    """
    alvo = constantes.unidade_da_maquina(maquina) if maquina else ""
    if not alvo:
        return dicom_rt.ordem_alfabetica(nomes)
    return dicom_rt.ordem_alfabetica(n for n in nomes
                            if unidade_da_pessoa(n, unidades) in (alvo, ""))


# O formato antigo (a lista inteira, fonte de verdade) fazia o cadastro
# CONGELAR: uma vez gravado o arquivo, nome novo em MEDICOS nunca mais
# chegava naquela instalação. Foi assim que a equipe do SAT nasceu invisível em
# toda máquina que já tinha o app instalado.
_MEDICOS_ARQUIVO = Path.home() / ".isocentro_medicos.json"
_FISICOS_ARQUIVO = Path.home() / ".isocentro_fisicos.json"
# Os nomes de antes do app se chamar ISOCENTRO (15/10/2026): Radioteraficha e,
# antes dele, ficha-py — do mais novo para o mais velho. Estão em toda estação
# que já tinha o programa; renomear sem trazer o conteúdo apagaria a lista de
# médicos e físicos de cada máquina — e ninguém ligaria uma coisa à outra.
_MEDICOS_ANTIGOS = (Path.home() / ".radioteraficha_medicos.json",
                    Path.home() / ".ficha_py_medicos.json")
_FISICOS_ANTIGOS = (Path.home() / ".radioteraficha_fisicos.json",
                    Path.home() / ".ficha_py_fisicos.json")


def _migrar_nome_antigo(novo: Path, antigos) -> None:
    """Adota o arquivo do nome antigo mais novo, uma vez, se o novo não existe.

    Cópia, não movimentação: se o usuário voltar para a versão anterior do
    programa (acontece), ela ainda encontra o dela.
    """
    try:
        if novo.exists():
            return
        for antigo in antigos:
            if antigo.exists():
                novo.write_bytes(antigo.read_bytes())
                return
    except OSError:
        pass   # lista de equipe é conveniência; falhar aqui não impede nada


_migrar_nome_antigo(_MEDICOS_ARQUIVO, _MEDICOS_ANTIGOS)
_migrar_nome_antigo(_FISICOS_ARQUIVO, _FISICOS_ANTIGOS)


def _ler_json(arquivo: Path):
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — sem arquivo, ilegível ou inválido
        return None


def _cadastro_equipe(arquivo: Path, padrao) -> tuple[list, dict]:
    """``(nomes, unidades)`` do cadastro: a lista canônica com o delta aplicado.

    Arquivo no formato atual: ``{"acrescentados": [...], "removidos": [...],
    "unidades": {nome: unidade}}``.

    Arquivo no formato ANTIGO (uma lista de nomes) é migrado na leitura, e só o
    que ele tem A MAIS vira acréscimo: não dá para distinguir "o usuário apagou
    a Camila" de "a Camila ainda não existia quando este arquivo foi gravado", e
    entre repor um nome apagado e sumir com quem vai assinar a ficha, repor é o
    erro barato. Quem quiser mesmo tirá-lo, tira uma vez mais — aí fica gravado
    como remoção.

    Remover TODO MUNDO deixaria o combo permanentemente vazio: neste caso o
    delta é ignorado e a lista canônica volta.
    """
    dados = _ler_json(arquivo)
    migrando = isinstance(dados, list)
    if migrando:                                    # formato antigo
        extras = [n for n in dados if isinstance(n, str) and n.strip()]
        dados = {"acrescentados": extras, "removidos": [], "unidades": {}}
    if not isinstance(dados, dict):
        dados = {}

    def _limpos(chave) -> list:
        return [n.strip() for n in (dados.get(chave) or [])
                if isinstance(n, str) and n.strip()]

    acrescentados = _limpos("acrescentados")
    removidos = set(_limpos("removidos"))
    nomes, vistos = [], set()
    for nome in list(padrao) + acrescentados:
        if nome not in vistos and nome not in removidos:
            vistos.add(nome); nomes.append(nome)
    if not nomes:
        nomes = list(padrao)
    # O cadastro do serviço traz a MESMA pessoa com outra grafia ("Ana Fátima de
    # Paula Brandao Albuquerque" para "Ana Fatima Albuquerque"): uma entrada só,
    # com o nome mais completo (ver dicom_rt.unificar_grafias).
    nomes = dicom_rt.unificar_grafias(nomes)
    unidades = {str(n): str(u or "") for n, u in (dados.get("unidades") or {}).items()
                if isinstance(n, str) and n.strip()}
    return dicom_rt.ordem_alfabetica(nomes), unidades


def _salvar_cadastro(arquivo: Path, nomes, unidades, padrao) -> None:
    """Grava o DELTA de ``nomes``/``unidades`` sobre a lista canônica ``padrao``.

    Só o que difere do padrão é gravado — inclusive as unidades: assim mudar a
    unidade de alguém no código (ou acrescentar um nome canônico) continua
    valendo para quem já tem cadastro."""
    atuais = list(nomes)
    dados = {
        "acrescentados": [n for n in atuais if n not in padrao],
        "removidos": [n for n in padrao if n not in atuais],
        "unidades": {n: u for n, u in (unidades or {}).items()
                     if n in atuais and u != unidade_da_pessoa(n)},
    }
    try:
        arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    except OSError:
        # Não bloqueia o uso: o nome vale para esta sessão, só não persiste.
        _LOG.exception("Não foi possível salvar a lista de equipe em %s", arquivo)


def _carregar_medicos() -> tuple[list, dict]:
    return _cadastro_equipe(_MEDICOS_ARQUIVO, MEDICOS)


def _carregar_fisicos() -> tuple[list, dict]:
    return _cadastro_equipe(_FISICOS_ARQUIVO, FISICOS)


def _salvar_medicos(nomes, unidades=None) -> None:
    _salvar_cadastro(_MEDICOS_ARQUIVO, nomes, unidades, MEDICOS)


def _salvar_fisicos(nomes, unidades=None) -> None:
    _salvar_cadastro(_FISICOS_ARQUIVO, nomes, unidades, FISICOS)
