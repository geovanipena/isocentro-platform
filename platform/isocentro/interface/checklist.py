"""Checklist Pré-Tratamento conferido NA TELA — o mesmo que vai na contracapa.

O checklist nasceu no papel: seis itens e quatro colunas de marcação, no pé da
folha 2 da capa, conferidos por quem posiciona o paciente na mesa (ver
``capa_pdf.CHECKLIST_ITENS``). Ele continua saindo impresso e continua sendo
assinado ali — este módulo não substitui a folha, guarda o que foi conferido
para que a Ficha Virtual possa RESPONDER, de outra estação e sem a folha na
mão, se aquele paciente já passou pela conferência.

**Os itens vêm de ``capa_pdf``, nunca copiados.** Duas listas divergem na
primeira vez que alguém acrescentar um item ao papel, e um checklist de tela
que não é o da contracapa é a pior espécie de conferência: passa a atestar
coisa diferente da que foi assinada.

Um checklist **por CURSO** (decidido com o usuário em 24/08/2026). É
"Pré-Tratamento": confere-se antes de começar, e replanejamento ou curso novo
pede conferência nova. Um por paciente abriria já marcado num retratamento dois
anos depois — e ninguém reconfere o que a tela diz que está conferido.

Um JSON por serviço, ao lado do índice central, com uma entrada por
paciente+curso:

    {"conferencias": {"9000005CEL|1": {
        "itens": {"Nome, D.N, RGH, Foto": {"marca": "C",
                                           "por": "ivone",
                                           "em": "2026-08-24T10:12:00"}}}}}

**Quem marcou e quando ficam POR ITEM.** A folha de papel tem um carimbo só no
pé, mas ali as seis linhas são preenchidas de uma sentada; aqui a conferência
pode ser retomada, e "quem conferiu a lateralidade" é justamente a pergunta que
se faz quando algo deu errado. Guardar uma assinatura só para a lista inteira
atribuiria a última pessoa itens que outra marcou — a mesma regra que vale para
quem tratou cada fração (ver ``tratamento_db.Sessao.quem``).

Na pasta do caso isto não podia morar: **arquivar é o caminho NORMAL** e a
pasta vira um zip. Ao lado do índice ele está sempre alcançável, e a
conferência vale para o SERVIÇO — quem confere numa estação tem de ver o efeito
na outra.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from contextlib import contextmanager, nullcontext
from pathlib import Path

from isocentro.dados import ambiente
from isocentro.papel import capa_pdf

_LOG = logging.getLogger(__name__)

# Os itens e as marcas SÃO os do papel. Reexportados aqui só para quem usa o
# checklist não precisar conhecer o módulo do PDF.
ITENS = capa_pdf.CHECKLIST_ITENS
MARCAS = capa_pdf.CHECKLIST_COLUNAS          # ("C", "N/C", "N/A", "Cor.")
LEGENDA = capa_pdf.CHECKLIST_LEGENDA

# A marca que significa "conferido e conforme". As outras três são respostas
# legítimas e também contam como ITEM RESPONDIDO — o que não pode é a tela
# tratar "não conforme" como se fosse pendência de conferência: alguém olhou,
# viu que estava errado e registrou isso, que é o oposto de não ter olhado.
CONFORME = MARCAS[0]

_ENV = "ISOCENTRO_CHECKLIST"
_ARQUIVO = "checklist_pre_tratamento.json"
_SCHEMA = "isocentro/checklist-pre-tratamento"


@contextmanager
def _travado():
    """Trava o arquivo durante ler→alterar→gravar.

    Mesmo problema do índice central e das correções da capa, mesma solução:
    duas estações conferindo pacientes DIFERENTES ao mesmo tempo leem o mesmo
    JSON e gravam por cima uma da outra — a escrita atômica não salva, porque
    cada uma grava um arquivo íntegro, só que sem a marcação da outra, e a que
    perde some sem aviso.

    Sem o ``indice`` por perto, grava sem exclusão em vez de recusar: perder a
    corrida é raro, não gravar é certo.
    """
    try:
        from isocentro.dados import indice
        trava = indice.travar_arquivo(caminho().with_suffix(".json.lock"))
    except Exception:  # noqa: BLE001
        trava = nullcontext()
    with trava:
        yield


def caminho() -> Path:
    """Arquivo do checklist: ``ISOCENTRO_CHECKLIST`` ou ao lado do índice."""
    env = ambiente.ler(_ENV)
    if env:
        return Path(env) / _ARQUIVO
    try:
        from isocentro.dados import indice
        return indice._app_dir() / _ARQUIVO
    except Exception:  # noqa: BLE001
        return Path(".") / _ARQUIVO


def chave(registro: str, curso) -> str:
    """``REGISTRO|curso`` — a identidade de UMA conferência.

    Precisa dos DOIS. Sem registro é um checklist órfão; sem curso é um
    checklist que não se sabe de qual tratamento — e o paciente cujo curso o
    banco não devolveu não é "o curso vazio": guardá-lo assim juntaria numa
    entrada só o tratamento de hoje e o retratamento de dois anos depois, que
    é exatamente o que a chave por curso existe para separar.

    A janela já não oferece o checklist sem curso (o cartão fica apagado, com o
    motivo no tooltip). A recusa é repetida aqui porque quem grava é este
    módulo: uma tela nova amanhã não pode reabrir o buraco em silêncio.
    """
    try:
        from isocentro.banco import capa_dados
        reg = capa_dados.normalizar_id(registro)
    except Exception:  # noqa: BLE001
        reg = str(registro or "").strip().upper()
    curso = str("" if curso is None else curso).strip()
    if not reg or not curso:
        return ""
    return f"{reg}|{curso}"


def _carregar() -> dict:
    p = caminho()
    if not p.exists():
        return {"schema": _SCHEMA, "conferencias": {}}
    try:
        dados = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            dados.setdefault("conferencias", {})
            return dados
    except Exception:  # noqa: BLE001 — arquivo corrompido não derruba a aba
        _LOG.exception("Checklist ilegível em %s", p)
    return {"schema": _SCHEMA, "conferencias": {}}


def _salvar_tudo(dados: dict) -> None:
    """Grava de forma ATÔMICA: temporário na mesma pasta + ``os.replace``.

    Escrever direto deixava uma janela em que o arquivo estava pela metade, e
    ``_carregar`` cai em silêncio para "nenhuma conferência" — o checklist de
    todos os pacientes sumiria sem erro nenhum na tela.
    """
    p = caminho()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ler(registro: str, curso=None) -> dict:
    """O que já foi marcado nesta conferência.

    Devolve ``{item: {"marca", "por", "em"}}``, só com os itens que EXISTEM no
    papel de hoje: um item retirado de ``capa_pdf.CHECKLIST_ITENS`` não pode
    continuar contando como conferido numa lista onde ele nem aparece.
    """
    k = chave(registro, curso)
    if not k:
        return {}
    itens = (_carregar()["conferencias"].get(k) or {}).get("itens") or {}
    return {i: dict(itens[i]) for i in ITENS
            if isinstance(itens.get(i), dict) and itens[i].get("marca")}


def marcar(registro: str, curso, item: str, marca: str,
           usuario: str = "") -> dict:
    """Marca (ou DESMARCA) um item. Devolve a conferência inteira, já gravada.

    ``marca`` vazia apaga o item — é como se desfaz um clique errado, e sem
    isso a única saída seria deixar no papel uma marcação que ninguém quis
    fazer. Marca fora de ``MARCAS`` é ignorada em silêncio: ela só pode vir de
    um erro de programação, e levantar aqui derrubaria a janela no meio de uma
    conferência já feita pela metade.
    """
    k = chave(registro, curso)
    if not k or item not in ITENS:
        return ler(registro, curso)
    marca = str(marca or "").strip()
    if marca and marca not in MARCAS:
        return ler(registro, curso)
    # Ler DENTRO da trava: entre ler e gravar cabe a gravação de outra estação,
    # e o que se grava aqui é o arquivo inteiro.
    with _travado():
        dados = _carregar()
        entrada = dict(dados["conferencias"].get(k) or {})
        itens = dict(entrada.get("itens") or {})
        if marca:
            itens[item] = {
                "marca": marca,
                "por": str(usuario or ""),
                "em": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        else:
            itens.pop(item, None)
        if itens:
            entrada["itens"] = itens
            dados["conferencias"][k] = entrada
        else:
            # Conferência sem nenhum item marcado não fica no arquivo: entrada
            # vazia se leria como "alguém abriu e não conferiu nada", que é
            # afirmar mais do que se sabe.
            dados["conferencias"].pop(k, None)
        try:
            _salvar_tudo(dados)
        except OSError:
            _LOG.exception("Não consegui gravar o checklist em %s", caminho())
    return ler(registro, curso)


def andamento(marcas: dict) -> tuple[int, int]:
    """``(respondidos, total)`` — o que o cartão da Ficha Virtual mostra.

    Conta item RESPONDIDO, não item conforme: "não conforme" e "não se aplica"
    são respostas de quem olhou. Misturá-las com o que ninguém olhou faria o
    cartão pedir uma conferência que já foi feita — e aviso que aparece sem
    motivo deixa de ser lido.
    """
    marcados = sum(1 for i in ITENS if (marcas or {}).get(i, {}).get("marca"))
    return marcados, len(ITENS)


def completo(marcas: dict) -> bool:
    """Todos os itens foram respondidos?"""
    feitos, total = andamento(marcas)
    return total > 0 and feitos >= total


def divergencias(marcas: dict) -> list:
    """Os itens marcados como NÃO CONFORME, ainda sem "corrigido".

    É o que a tela precisa para não dizer "conferido" sobre uma lista em que
    alguém registrou um erro: seis de seis respondidos com um "N/C" no meio é
    uma conferência COMPLETA e um paciente que não pode subir na mesa.
    """
    nao_conforme = MARCAS[1] if len(MARCAS) > 1 else ""
    return [i for i in ITENS
            if (marcas or {}).get(i, {}).get("marca") == nao_conforme]
