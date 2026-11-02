r"""A memória do gatilho: o que já se viu disponível, e o que já saiu.

**Por que existe.** O ``gatilho_db`` pergunta ao banco o que vale AGORA, e isso
não basta para automatizar, porque o estado da atividade é passageiro. Visto no
ARIA em 02/09/2026, no espaço de duas horas: a Documentação do 9000019ANA
passou de *disponível* a *em andamento*, e um dia chegará a *Completed* — que
sai da janela e não volta. Quem sonda só o estado atual perde o gatilho sempre
que a mudança cai entre duas sondagens, e perde **em silêncio**: não há erro,
há um paciente a menos na lista.

Então a disponibilidade é ANOTADA quando é vista, e a janela daquele paciente
fica aberta até o plano sair — mesmo que a atividade já tenha mudado de estado.
Foi o desenho que o usuário propôs no primeiro dia ("um log que registra quando
a documentação se tornou disponível"), e que eu descartei dizendo que o log já
existia no ARIA. Existia o **estado**; o que não existe lá é o **histórico das
transições**, e é ele que a automação precisa.

**Duas memórias, um arquivo, um lock:**

* a **janela** — instância da Documentação → quando foi vista disponível pela
  primeira vez. Não se apaga quando a atividade muda de estado;
* a **marca d'água** — ``PlanUID`` + estado → quando aquele plano saiu. É por
  plano, e não por atividade, porque o plano nasce DEPOIS: no 9000019ANA a
  Documentação abriu doze horas antes do primeiro plano existir.

O arquivo é compartilhado entre estações, como o índice central, e usa o mesmo
lock de sistema operacional (:func:`indice.travar_arquivo`) para o ciclo
ler→alterar→gravar. Sem ele, duas estações sondando ao mesmo tempo gravam uma
por cima da outra e um plano sai duas vezes — ou nenhuma.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from isocentro.dados import ambiente
from isocentro.dados import indice
from isocentro.dados import registro_json

_LOG = logging.getLogger(__name__)

# Onde a memória mora. Ao lado do índice central, porque é da mesma natureza:
# estado do SERVIÇO, compartilhado por todas as estações, e não configuração de
# estação. Ver a regra da pasta do serviço no CLAUDE.md.
ENV_ARQUIVO = "ISOCENTRO_GATILHO_REGISTRO"
NOME_PADRAO = "gatilho_registro.json"

# Quanto tempo uma janela anotada continua valendo sem o plano aparecer.
#
# Não é zelo de limpeza: é o prazo depois do qual insistir vira ruído. Uma
# Documentação que abriu e cujo plano nunca foi aprovado em 30 dias não vai ser
# aprovada — o caso mudou, o paciente não veio, o curso foi refeito. Sem prazo,
# a lista de espera cresce para sempre e ninguém mais a lê.
#
# 30 dias é palpite deliberado, como os 180 do ``atividades_db.DIAS_PARA_TRAS``:
# quando alguém medir quanto tempo leva de fato entre a Documentação abrir e o
# plano ser aprovado, este número se ajusta com a medida.
DIAS_DE_JANELA = 30

# Quanto tempo a pasta da temporária sobrevive DEPOIS de a ficha ser liberada.
#
# Não é zero porque liberar não encerra o caso: uma correção no dia seguinte
# reabre o mesmo paciente, e apagar na mesma rodada obrigaria a pedir tudo ao
# ARIA outra vez — o conjunto medido em 11/09/2026 tem 205 arquivos e 103 MB.
# Sete dias cobrem a semana de trabalho em que a v2 ainda acontece.
DIAS_PARA_LIMPAR_LIBERADA = 7

# E quanto tempo sobrevive o caso que NUNCA foi liberado: plano que travou,
# paciente que não veio, curso refeito.
#
# Prazo próprio, e maior, porque os dois desfechos são opostos: um entregou a
# ficha para a sala, o outro ficou pelo caminho — e é justamente o segundo que
# alguém ainda vai abrir para entender o que houve. Conta da ÚLTIMA saída, não
# da janela: o que interessa é há quanto tempo os arquivos estão parados.
DIAS_PARA_LIMPAR_PARADA = 60

_VERSAO = 1


def caminho() -> Path:
    """O arquivo, pela precedência do projeto: variável → serviço → padrão."""
    escolhido = ambiente.ler(ENV_ARQUIVO)
    if escolhido:
        return Path(escolhido)
    return Path(indice.REGISTRO_PATH).with_name(NOME_PADRAO)


def _vazio() -> dict:
    return {"versao": _VERSAO, "janela": {}, "exportados": {},
            "incompletos": {}, "liberados": {}, "limpos": {}}


def ler() -> dict:
    """A memória como está no disco. Arquivo ilegível NÃO vira memória vazia.

    Vazio significa "nunca vi nada", e sob esse significado a automação
    reexportaria tudo o que já saiu. Um JSON truncado (queda no meio da
    escrita, disco cheio) tem de gritar, não virar folha em branco — por isso a
    exceção sobe.
    """
    alvo = caminho()
    if not alvo.exists():
        return _vazio()
    with open(alvo, encoding="utf-8") as f:
        dados = json.load(f)
    if not isinstance(dados, dict):
        raise ValueError(f"{alvo} não contém um objeto JSON")
    dados.setdefault("versao", _VERSAO)
    dados.setdefault("janela", {})
    dados.setdefault("exportados", {})
    # Chave nova em 11/09/2026, sem subir a ``_VERSAO``: arquivo gravado antes
    # dela simplesmente não tem incompleto nenhum anotado, que é a verdade.
    dados.setdefault("incompletos", {})
    # Idem, 11/09/2026 (frente 3): caso liberado para impressão pelo físico.
    dados.setdefault("liberados", {})
    # Idem, 14/09/2026 (frente 4): temporária daquele caso já apagada.
    dados.setdefault("limpos", {})
    return dados


def _gravar(dados: dict) -> None:
    alvo = caminho()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    # A gravação atômica do ``registro_json``, pelo mesmo motivo dela: escrita
    # interrompida não pode deixar a memória truncada, porque é ela que impede
    # a reexportação.
    registro_json._gravar_json(alvo, dados)


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def anotar(atividades) -> list:
    """Anota as Documentações vistas disponíveis. Devolve as NOVAS.

    É esta a linha do log que o desenho pedia: "fulano ficou disponível às
    tantas". As já anotadas só têm o último estado atualizado — a primeira
    vista nunca se reescreve, porque é ela que marca o começo da janela.
    """
    novas: list = []
    mudou = False
    with indice.travar_arquivo(_lock()):
        dados = ler()
        janela = dados["janela"]
        for a in atividades:
            chave = str(a.instancia)
            if not chave or chave == "0":
                continue
            entrada = janela.get(chave)
            if entrada is None:
                janela[chave] = {"registro": a.registro, "paciente": a.paciente,
                                 "visto_em": _agora(), "ultimo_estado": a.estado,
                                 "estado_em": _agora(),
                                 "fechado_em": "", "motivo": ""}
                novas.append(a)
                mudou = True
                _LOG.info("Documentação disponível: %s (%s), instância %s",
                          a.paciente, a.registro, a.instancia)
                continue
            # Só grava quando o estado MUDOU. Uma marca de "visto agora" a cada
            # sondagem faria uma escrita em disco de rede por rodada, para
            # registrar que nada aconteceu.
            if entrada.get("ultimo_estado") != a.estado:
                _LOG.info("Documentação de %s: %s -> %s", a.registro,
                          entrada.get("ultimo_estado"), a.estado)
                entrada["ultimo_estado"] = a.estado
                entrada["estado_em"] = _agora()
                mudou = True
        if mudou:
            _gravar(dados)
    return novas


def abertas(agora: datetime | None = None) -> dict:
    """A janela: registro do paciente → o que se sabe dele.

    Inclui quem já saiu do estado "disponível" no ARIA — é o ponto do módulo.
    Não inclui quem foi fechado nem quem passou do prazo.

    Quando o mesmo paciente tem mais de uma Documentação anotada, vale a mais
    ANTIGA ainda aberta: é ela que espera há mais tempo, e a janela é do
    paciente, não da tarefa.
    """
    agora = agora or datetime.now()
    limite = agora - timedelta(days=DIAS_DE_JANELA)
    saida: dict = {}
    for chave, e in ler()["janela"].items():
        if e.get("fechado_em"):
            continue
        visto = _quando(e.get("visto_em"))
        if visto is not None and visto < limite:
            continue
        reg = e.get("registro") or ""
        if not reg:
            continue
        anterior = saida.get(reg)
        if anterior is not None and _quando(anterior["visto_em"]) <= (
                visto or agora):
            continue
        saida[reg] = {"instancia": int(chave), "paciente": e.get("paciente", ""),
                      "visto_em": e.get("visto_em", ""),
                      "ultimo_estado": e.get("ultimo_estado", "")}
    return saida


def fechar(instancia: int, motivo: str) -> None:
    """Tira uma Documentação da janela, com o motivo escrito.

    O motivo não é enfeite: "exportado" e "expirou sem plano" são desfechos
    opostos, e sem distingui-los ninguém descobre que um caso ficou pelo
    caminho — que é exatamente o defeito silencioso que este módulo existe para
    evitar.
    """
    with indice.travar_arquivo(_lock()):
        dados = ler()
        entrada = dados["janela"].get(str(instancia))
        if entrada is None or entrada.get("fechado_em"):
            return
        entrada["fechado_em"] = _agora()
        entrada["motivo"] = motivo
        _gravar(dados)
    _LOG.info("Janela fechada (instância %s): %s", instancia, motivo)


def ja_saiu(pronto) -> bool:
    """Este plano, NESTE estado, já foi exportado?"""
    return _chave(pronto) in ler()["exportados"]


def anotar_saida(pronto, destino: str = "", preparo: dict | None = None) -> None:
    """Grava que o plano saiu. Chamar DEPOIS de o arquivo chegar inteiro.

    Antes seria marcar como feito o que ainda pode falhar no meio: um C-MOVE
    parcial deixaria a marca gravada e o conjunto incompleto na pasta, e a
    próxima rodada não voltaria para terminar.

    ``preparo`` é o que :func:`gatilho._preparar` conferiu — onde está o
    cadastro de simulação e os avisos. Mora AQUI, e não só no recibo da pasta,
    porque quem mostra o estado é a Fichinha de qualquer estação, e só a
    concentradora varre: este arquivo é o que as duas pontas enxergam.
    """
    with indice.travar_arquivo(_lock()):
        dados = ler()
        dados["exportados"][_chave(pronto)] = {
            "quando": _agora(), "registro": pronto.registro,
            "paciente": pronto.paciente, "curso": pronto.curso,
            "plano": pronto.plano, "estado": pronto.estado,
            "instancia": pronto.instancia, "destino": destino,
            "preparo": dict(preparo or {})}
        # Saiu inteiro: o incompleto de uma rodada anterior deixou de ser
        # verdade. Ficando, a tela mostraria o mesmo plano pronto E incompleto.
        dados["incompletos"].pop(_chave(pronto), None)
        _gravar(dados)
    _LOG.info("Plano exportado: %s de %s (%s), UID %s",
              pronto.plano, pronto.paciente, pronto.estado, pronto.plan_uid)


def anotar_incompleto(pronto, motivo: str) -> None:
    """Grava que o plano ficou pela metade nesta rodada, e por quê.

    O ``Relatorio`` da varredura morre com a rodada, e ele mora na
    concentradora — a Fichinha da estação do físico nunca o vê. Sem isto, o
    ``⚠ incompleta`` da lista não teria de onde tirar o motivo, e um plano
    travado por falha de C-MOVE pareceria só "ainda preparando" para sempre.

    Só grava quando é novo ou o motivo MUDOU, pela mesma razão do
    :func:`anotar`: uma escrita em disco de rede a cada rodada para registrar
    que nada aconteceu. O ``desde`` nunca se reescreve — é ele que diz há
    quanto tempo o plano está travado.
    """
    chave = _chave(pronto)
    with indice.travar_arquivo(_lock()):
        dados = ler()
        anterior = dados["incompletos"].get(chave)
        if anterior is not None and anterior.get("motivo") == motivo:
            return
        dados["incompletos"][chave] = {
            "desde": (anterior or {}).get("desde") or _agora(),
            "motivo_em": _agora(), "motivo": motivo,
            "registro": pronto.registro, "paciente": pronto.paciente,
            "curso": pronto.curso, "plano": pronto.plano,
            "estado": pronto.estado, "instancia": pronto.instancia}
        _gravar(dados)
    _LOG.info("Plano incompleto: %s de %s — %s", pronto.plano,
              pronto.registro, motivo)


# O que a Fichinha mostra ao lado de cada Documentação. Constantes, e não
# texto solto nas duas pontas, pelo mesmo motivo das do ``gatilho``: quem grava
# e quem lê têm de concordar na palavra, e a divergência não dá erro — dá uma
# linha sem estado.
def anotar_liberada(instancia: int, por: str, pasta: str) -> None:
    """Grava que o caso daquela Documentação foi liberado para impressão.

    Sem esta marca a linha continuaria ``● PRONTA`` depois da liberação, e o
    próximo físico a passar por ela liberaria de novo — uma v2 da ficha sem
    mudança nenhuma. É também o sinal de que a temporária daquele caso já pode
    ser limpa. Liberar outra vez (plano reaprovado e trazido de novo) reescreve
    a marca: vale a liberação mais recente, que é a da ficha que está na sala.
    """
    chave = str(_instancia(instancia))
    if chave == "0":
        return
    with indice.travar_arquivo(_lock()):
        dados = ler()
        dados["liberados"][chave] = {"quando": _agora(), "por": por,
                                     "pasta": pasta}
        _gravar(dados)
    _LOG.info("Caso liberado para impressão (instância %s) por %s em %s",
              instancia, por, pasta)


def anotar_limpeza(instancia: int, pastas: list, motivo: str) -> None:
    """Grava que a temporária daquele caso foi apagada, e por quê.

    Apagar é irreversível, e o que sobra do caso é o que se escreveu aqui: sem
    esta marca, ninguém descobre depois para onde foram os arquivos de um caso
    que ficou pelo caminho — só a pasta some. É também o que impede a limpeza
    de reconsiderar o mesmo caso a cada rodada.

    Grava mesmo quando a pasta já não existia (apagada à mão, share remontado):
    o desfecho é o mesmo, e reconsiderar para sempre um caso que ninguém vai
    apagar de novo é a mesma insistência que o ``DIAS_DE_JANELA`` evita.
    """
    chave = str(_instancia(instancia))
    if chave == "0":
        return
    with indice.travar_arquivo(_lock()):
        dados = ler()
        dados["limpos"][chave] = {"quando": _agora(), "motivo": motivo,
                                  "pastas": [str(p) for p in pastas]}
        _gravar(dados)
    _LOG.info("Temporária apagada (instância %s): %s — %s", instancia,
              motivo, ", ".join(str(p) for p in pastas) or "(nenhuma pasta)")


PRONTA = "pronta"
PREPARANDO = "preparando"
INCOMPLETA = "incompleta"
LIBERADA = "liberada"

AVISO_SEM_PREPARO = ("exportado antes de a preparação existir: o cadastro de "
                     "simulação não foi conferido")


def estados_da_documentacao(dados: dict | None = None,
                            agora: datetime | None = None) -> dict:
    """Instância da Documentação → o que a automação sabe do caso dela.

    A tela DEDUZ o estado; nada novo é gravado. Cada entrada é um dict com
    ``estado`` e o que o tooltip precisa (``avisos``, ``motivos``, ``desde``,
    ``planos``). Instância ausente = a automação não sabe nada dela, e a linha
    fica sem estado — que é diferente de "preparando".

    **Incompleta vence pronta.** Um curso com dois planos, um exportado e o
    outro travado, NÃO está pronto: a ficha precisa dos dois. Mostrado como
    pronto, o físico abriria um caso pela metade.

    **Incompleto superado não conta.** O ``anotar_saida`` só apaga o
    incompleto da MESMA chave (UID + estado). Um plano que travou em Planning
    Approved e saiu depois em Treatment Approved deixaria o incompleto antigo
    para sempre, e a linha diria "incompleta" de um caso que chegou inteiro.

    ``preparando`` é a janela aberta sem saída nem incompleto. Inclui o caso
    cujo plano ainda nem foi aprovado — daqui não se distingue um do outro sem
    perguntar ao banco, e é o tooltip que diz isso, não o rótulo.

    **Liberada só enquanto é a última palavra.** Um plano reaprovado e trazido
    DEPOIS da liberação é ficha nova para conferir: a linha volta a ``pronta``,
    com aviso de que já houve liberação. Mantida "liberada", a ficha do plano
    novo ficaria escondida atrás da impressão do antigo. A pronta leva ``pasta``
    — a do curso na temporária, mãe das pastas dos planos —, que é o que o
    clique abre.

    **Pasta limpa não convida ao clique.** O caso nunca liberado que a
    :func:`a_limpar` apagou continua ``pronta`` — ele nunca deixou de estar
    pronto —, mas sem ``pasta`` e com o aviso em primeiro lugar.
    """
    dados = dados if dados is not None else ler()
    agora = agora or datetime.now()
    limite = agora - timedelta(days=DIAS_DE_JANELA)

    saidas: dict = {}
    for e in dados.get("exportados", {}).values():
        inst = _instancia(e.get("instancia"))
        if inst:
            saidas.setdefault(inst, []).append(e)

    travados: dict = {}
    for e in dados.get("incompletos", {}).values():
        inst = _instancia(e.get("instancia"))
        if not inst:
            continue
        travou = _quando(e.get("motivo_em")) or datetime.min
        if any(_mesmo_plano(s, e) and (_quando(s.get("quando")) or datetime.min)
               >= travou for s in saidas.get(inst, [])):
            continue
        travados.setdefault(inst, []).append(e)

    estados: dict = {}
    for inst, lista in travados.items():
        estados[inst] = {
            "estado": INCOMPLETA,
            "desde": min((e.get("desde") or "") for e in lista),
            "motivos": [f"{e.get('plano') or '(plano sem nome)'}: "
                        f"{e.get('motivo') or '(sem motivo anotado)'}"
                        for e in lista]}
    for inst, lista in saidas.items():
        if inst in estados:
            continue
        avisos: list = []
        planos: list = []
        for s in lista:
            preparo = s.get("preparo")
            # Saída gravada antes de 11/09/2026 não tem ``preparo``: saiu sem
            # ninguém procurar a simulação. Pronta sem aviso afirmaria uma
            # conferência que não houve.
            novos = (preparo.get("avisos") or []) if preparo else [AVISO_SEM_PREPARO]
            avisos += [a for a in novos if a not in avisos]
            if s.get("plano") and s["plano"] not in planos:
                planos.append(s["plano"])
        # A pasta do CURSO, e não a de um plano: a ficha precisa de todos, e a
        # carga varre subpastas. Mães diferentes (curso renomeado entre duas
        # saídas) não se adivinham — sem pasta, a linha não abre nada.
        maes = {os.path.dirname(str(s.get("destino") or "").rstrip("/\\"))
                for s in lista}
        maes.discard("")
        if len(maes) > 1:
            # Em primeiro: é o que impede o clique de abrir o caso.
            avisos.insert(0, "os planos saíram em pastas diferentes: "
                          + ", ".join(sorted(maes)))
        desde = max((s.get("quando") or "") for s in lista)
        liberado = dados.get("liberados", {}).get(str(inst))
        if liberado and (liberado.get("quando") or "") >= desde:
            estados[inst] = {"estado": LIBERADA,
                             "desde": liberado.get("quando", ""),
                             "por": liberado.get("por", ""),
                             "pasta": liberado.get("pasta", ""),
                             "planos": planos}
            continue
        if liberado:
            avisos.insert(0, "já liberada em " + str(liberado.get("quando"))
                          + "; o plano saiu de novo depois")
        pasta = maes.pop() if len(maes) == 1 else ""
        limpo = dados.get("limpos", {}).get(str(inst))
        if limpo and (limpo.get("quando") or "") >= desde:
            # Os arquivos já não estão lá. Mantida a pasta, a linha continuaria
            # convidando ao clique e a carga diria "a pasta não é alcançada
            # desta máquina" — recado que manda conferir a REDE, quando o que
            # houve foi a limpeza fazendo o que devia.
            avisos.insert(0, "a pasta temporária foi apagada em "
                          + str(limpo.get("quando")) + ": "
                          + str(limpo.get("motivo") or "sem motivo anotado"))
            pasta = ""
        estados[inst] = {"estado": PRONTA, "avisos": avisos, "planos": planos,
                         "desde": desde, "pasta": pasta}
    for chave, e in dados.get("janela", {}).items():
        inst = _instancia(chave)
        if not inst or inst in estados or e.get("fechado_em"):
            continue
        visto = _quando(e.get("visto_em"))
        if visto is not None and visto < limite:
            continue
        estados[inst] = {"estado": PREPARANDO, "desde": e.get("visto_em", "")}
    return estados


def a_limpar(dados: dict | None = None, agora: datetime | None = None) -> list:
    """O que a temporária já não precisa guardar: ``[{instancia, pastas, motivo}]``.

    Só entra o que tem ``destino`` anotado — as pastas dos PLANOS que saíram
    inteiros. O plano que travou no meio não tem pasta anotada em lugar nenhum,
    e apagar por palpite o que a marca não registra é o contrário da regra da
    casa: na dúvida, mantém.

    Dois desfechos, dois prazos (decisão do usuário em 14/09/2026):

    * **liberada** há mais de :data:`DIAS_PARA_LIMPAR_LIBERADA` — a ficha já
      está na pasta do paciente e na sala; a temporária cumpriu o papel;
    * **parada** há mais de :data:`DIAS_PARA_LIMPAR_PARADA` sem liberação
      nenhuma. Sem este segundo prazo a temporária cresce para sempre, porque o
      caso que ninguém libera é justamente o que ninguém volta para limpar.

    Não entram: o caso recém-exportado, o **incompleto** — um plano do curso
    ainda pode chegar, e apagar os que vieram obrigaria a trazer tudo de novo —
    e o que já foi limpo. Este último volta a entrar se um plano sair DEPOIS da
    limpeza, pela mesma regra que faz a liberação deixar de valer.
    """
    dados = dados if dados is not None else ler()
    agora = agora or datetime.now()
    estados = estados_da_documentacao(dados, agora)

    saidas: dict = {}
    for e in dados.get("exportados", {}).values():
        inst = _instancia(e.get("instancia"))
        if inst:
            saidas.setdefault(inst, []).append(e)

    alvos: list = []
    for inst, lista in saidas.items():
        ultima = max((s.get("quando") or "") for s in lista)
        limpo = dados.get("limpos", {}).get(str(inst))
        # Empate conta como LIMPO. O carimbo tem resolução de segundo, e das
        # duas leituras possíveis de "saiu no mesmo segundo em que se limpou",
        # esta é a que não apaga uma pasta recém-trazida — o erro que não se
        # desfaz. A pior consequência da escolha é uma pasta ficar até a
        # próxima saída; a da outra, o conjunto sumir debaixo do físico.
        if limpo and (limpo.get("quando") or "") >= ultima:
            continue
        estado = (estados.get(inst) or {}).get("estado")
        if estado == INCOMPLETA:
            continue
        if estado == LIBERADA:
            desde = (estados.get(inst) or {}).get("desde") or ""
            quando, prazo = _quando(desde), DIAS_PARA_LIMPAR_LIBERADA
            motivo = f"liberada em {desde or '(sem data)'}"
        else:
            quando, prazo = _quando(ultima), DIAS_PARA_LIMPAR_PARADA
            motivo = f"parada desde {ultima or '(sem data)'} sem liberação"
        if quando is None or quando > agora - timedelta(days=prazo):
            continue
        pastas = sorted({str(s.get("destino") or "") for s in lista} - {""})
        if not pastas:
            # Saída anotada sem destino (antes de ele existir): não há o que
            # apagar, e marcar como limpo diria que se apagou algo.
            continue
        alvos.append({"instancia": inst, "pastas": pastas, "motivo": motivo})
    return alvos


def _instancia(valor) -> int:
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def _mesmo_plano(a: dict, b: dict) -> bool:
    return ((a.get("curso") or "") == (b.get("curso") or "")
            and (a.get("plano") or "") == (b.get("plano") or ""))


def _chave(pronto) -> str:
    """``PlanUID`` **com** o estado — ver :meth:`gatilho_db.Pronto.chave`."""
    uid, estado = pronto.chave()
    return f"{uid}|{estado}"


def _lock() -> Path:
    return caminho().with_name(caminho().name + ".lock")


def _quando(texto):
    if not texto:
        return None
    try:
        return datetime.fromisoformat(str(texto))
    except ValueError:
        return None


def pendentes(desde=None) -> list:
    """O que exportar agora: a janela ANOTADA cruzada com os planos aprovados.

    A ordem importa e é esta:

    1. pergunta ao banco quem está disponível **agora** e ANOTA — é o log;
    2. monta a janela com tudo o que está anotado e aberto, inclusive quem já
       saiu de "disponível" no ARIA;
    3. pergunta os planos aprovados dessa janela inteira;
    4. descarta o que a marca d'água já registra como exportado.

    Fazer (1) antes de (3) é o que garante que uma Documentação que abriu e
    mudou de estado na mesma sondagem ainda entre na janela desta vez.
    """
    from isocentro.banco import atividades_db
    from isocentro.banco import gatilho_db

    anotar(atividades_db.todas(desde))
    janela = abertas()
    if not janela:
        return []
    # O ``prontos_de`` quer objetos com ``paciente`` e ``instancia``; a
    # lembrança anotada tem os dois, e é ela que vale quando o ARIA já não
    # devolve mais a atividade.
    por_registro = {reg: _Lembranca(e["instancia"], e["paciente"])
                    for reg, e in janela.items()}
    return [p for p in gatilho_db.prontos_de(por_registro) if not ja_saiu(p)]


class _Lembranca:
    """O mínimo que o ``prontos_de`` pede, vindo da memória e não do banco."""

    __slots__ = ("instancia", "paciente")

    def __init__(self, instancia: int, paciente: str):
        self.instancia = instancia
        self.paciente = paciente


def resumo() -> dict:
    """Números para a tela: quantas janelas abertas, quantos planos já saíram.

    Uma automação silenciosa precisa de um lugar onde se veja que ela está
    viva. "Zero exportados hoje" e "zero exportados desde sempre" são coisas
    diferentes, e só a segunda é defeito.
    """
    dados = ler()
    abertas_ = [e for e in dados["janela"].values() if not e.get("fechado_em")]
    return {"janelas_abertas": len(abertas_),
            "janelas_fechadas": len(dados["janela"]) - len(abertas_),
            "planos_exportados": len(dados["exportados"]),
            "planos_incompletos": len(dados["incompletos"]),
            "arquivo": str(caminho()),
            "existe": os.path.exists(caminho())}
