"""Agendamento multi-plano por ETAPAS → sequência de frações (página 3).

O tratamento é uma lista ordenada de **etapas**. Cada etapa entrega um ou mais
planos por um número de frações. Uma única mecânica cobre os cenários reais da
radioterapia:

- **Sequencial** (fase → boost): uma etapa por plano.
- **Simultâneo/concorrente**: uma etapa com vários planos juntos.
- **Concorrente + boost**: etapa com os planos concomitantes, depois a etapa
  do boost (ex.: Mama+FSC por 25 fx, depois Boost por 8 fx).

Formato de uma etapa::

    {"planos": [idx, ...], "fracoes": int}
"""

from __future__ import annotations


def sequencia_de_etapas(etapas: list) -> list:
    """``sequencia[i]`` = lista de índices de planos tratados na fração i+1.

    Etapas na ordem dada; numa etapa todos os planos marcados entram juntos em
    cada fração.
    """
    seq: list = []
    for et in etapas or []:
        planos = [int(p) for p in (et.get("planos") or [])]
        n = int(et.get("fracoes") or 0)
        if not planos or n <= 0:
            continue
        for _ in range(n):
            seq.append(list(planos))
    return seq


def fracoes_por_plano(etapas: list, n_planos: int) -> list:
    """Total de frações que cada plano recebe ao longo de todas as etapas."""
    cont = [0] * n_planos
    for linha in sequencia_de_etapas(etapas):
        for p in linha:
            if 0 <= p < n_planos:
                cont[p] += 1
    return cont


# ── Modelos prontos (seeds dos cenários comuns) ──────────────────────────────

def ordem_por_numero(rotulos: list) -> list:
    """Índices dos planos na ordem do número do rótulo (ex.: '1 iSNC…' antes de
    '2 iSNC…'). Rótulos sem número vão ao fim, preservando a ordem original."""
    import re

    def chave(i):
        m = re.match(r"\s*(\d+)", str(rotulos[i] if i < len(rotulos) else ""))
        return (int(m.group(1)) if m else 10 ** 9, i)

    return sorted(range(len(rotulos)), key=chave)


def modelo_sequencial(fracoes: list, ordem: list | None = None) -> list:
    """Um plano após o outro, cada um com suas frações.

    ``ordem`` (opcional): índices de plano na sequência desejada — por padrão a
    fase (plano nº 1, base) vem antes do boost (nº 2). Sem ela, ordem natural.
    """
    idx = list(ordem) if ordem is not None else list(range(len(fracoes)))
    return [{"planos": [i], "fracoes": int((fracoes[i] if i < len(fracoes) else 0) or 0) or 1}
            for i in idx]


def modelo_simultaneo(fracoes: list) -> list:
    """Todos os planos juntos em toda fração (nº = maior nº de frações)."""
    n = max((int(f or 0) for f in fracoes), default=0) or 1
    return [{"planos": list(range(len(fracoes))), "fracoes": n}]


# Mama + FSC (fossa supraclavicular) é irradiada JUNTA, na mesma sessão: são
# campos de um mesmo tratamento, não fases que se seguem. O padrão sequencial —
# que serve para fase→boost — descrevia esse caso errado, e alguém tinha de
# corrigir à mão toda vez.
#
# O casamento é por TOKEN, não por "contém": "fsc" dentro de outra palavra, ou
# uma "mama" que seja parte de outro rótulo, não valem. Mesmo critério do
# ``dicom_rt.mama_direita``, e pela mesma razão — rótulo é texto digitado.
_MAMA = frozenset({"mama", "mamas", "breast"})
_FSC = frozenset({"fsc", "supra", "supraclavicular", "fossa"})


def _fichas(rotulo: str) -> set:
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", str(rotulo or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return set(re.findall(r"[a-z]+", t))


def mama_com_fsc(rotulos: list) -> bool:
    """Há um plano de mama E um de FSC entre os rótulos?

    Dois planos distintos: uma prescrição que já traga "Mama + FSC" num rótulo
    só não precisa de agendamento simultâneo — ela já é um plano.
    """
    com_mama, com_fsc = set(), set()
    for i, rotulo in enumerate(rotulos or []):
        palavras = _fichas(rotulo)
        if palavras & _MAMA:
            com_mama.add(i)
        if palavras & _FSC:
            com_fsc.add(i)
    # Em planos DIFERENTES. Um plano só chamado "Mama + FSC 40Gy" traz as duas
    # palavras e não precisa de agendamento nenhum: ele já é uma sessão.
    return any(i != j for i in com_mama for j in com_fsc)


_BOOST = frozenset({"boost", "reforco", "sobreimpressao"})


def mama_com_boost(rotulos: list) -> bool:
    """Há um plano de mama E um de boost, em planos DIFERENTES?

    Fase e boost são fases que se SEGUEM — o oposto da mama com FSC, que é uma
    sessão só. Mas a dose é do mesmo alvo, e o que interessa conferir é o
    acumulado: por isso sequencial no agendamento e SOMA na ficha, com os dois
    no mesmo grupo de "Somar dose".
    """
    com_mama, com_boost = set(), set()
    for i, rotulo in enumerate(rotulos or []):
        palavras = _fichas(rotulo)
        if palavras & _MAMA:
            com_mama.add(i)
        if palavras & _BOOST:
            com_boost.add(i)
    return any(i != j for i in com_mama for j in com_boost)


def modelo_alternado(fracoes: list, ordem: list | None = None) -> list:
    """Planos em dias ALTERNADOS: cada dia trata UM plano, revezando na ``ordem``
    dada (round-robin), até esgotar as frações de cada um. Ex.: dois planos de
    3 fx → 1, 2, 1, 2, 1, 2. Um plano que esgota sai do rodízio; com um só plano
    equivale ao sequencial.
    """
    idx = list(ordem) if ordem is not None else list(range(len(fracoes)))
    restantes = {i: int((fracoes[i] if i < len(fracoes) else 0) or 0) for i in idx}
    etapas = []
    while any(restantes[i] > 0 for i in idx):
        for i in idx:
            if restantes[i] > 0:
                etapas.append({"planos": [i], "fracoes": 1})
                restantes[i] -= 1
    return etapas or [{"planos": [idx[0]] if idx else [0], "fracoes": 1}]


def espaco_fracionamento(frac: str) -> int:
    """Dias entre frações consecutivas conforme o fracionamento.

    "Dias alter." → 2 (dia sim, dia não); "2x sem." → 3 (aprox.); "1x dia" /
    "Única" / desconhecido → 1 (dias consecutivos).
    """
    f = (frac or "").strip().lower()
    if "alter" in f:
        return 2
    if "2x" in f or "sem" in f:
        return 3
    return 1


def montar_por_dia_inicio(planos: list) -> list:
    """Etapas dia-a-dia a partir do dia de início e do fracionamento de cada plano.

    ``planos`` = ``[{"fracoes": int, "dia_inicio": int, "fracionamento": str}]``.
    Cada plano ocupa os dias ``inicio, inicio+esp, inicio+2·esp, …`` (uma vez por
    fração, ``esp`` vindo de :func:`espaco_fracionamento`). Planos que caem no
    mesmo dia entram juntos; dias sem plano são lacunas (não geram fração).
    Retorna ``[{"planos":[...], "fracoes":1}]`` em ordem de dia.
    """
    dias: dict = {}
    for i, p in enumerate(planos):
        inicio = int(p.get("dia_inicio") or 1)
        esp = espaco_fracionamento(p.get("fracionamento"))
        n = int(p.get("fracoes") or 0)
        for k in range(n):
            dias.setdefault(inicio + k * esp, []).append(i)
    return [{"planos": sorted(dias[d]), "fracoes": 1} for d in sorted(dias)]


def modelo_concorrente_boost(fracoes: list) -> list:
    """Todos menos o último juntos (fase concomitante), depois o último (boost)."""
    if len(fracoes) < 2:
        return modelo_sequencial(fracoes)
    base = list(range(len(fracoes) - 1))
    n_fase = max((int(fracoes[i] or 0) for i in base), default=0) or 1
    boost = len(fracoes) - 1
    return [
        {"planos": base, "fracoes": n_fase},
        {"planos": [boost], "fracoes": int(fracoes[boost] or 0) or 1},
    ]


def expandir_dias(etapas: list) -> list:
    """Uma etapa por DIA (1 fração), preservando os planos de cada dia.

    Para o modo dia-a-dia: transforma os blocos em uma linha por dia, que o
    usuário ajusta individualmente.
    """
    return [{"planos": list(dia), "fracoes": 1}
            for dia in sequencia_de_etapas(etapas)]


def colapsar_dias(etapas: list) -> list:
    """Agrupa dias consecutivos com o MESMO conjunto de planos num bloco.

    Inverso prático de ``expandir_dias``: ao sair do modo dia-a-dia, volta os
    dias iguais em sequência para blocos "planos × N frações".
    """
    blocos: list = []
    for dia in sequencia_de_etapas(etapas):
        chave = sorted(dia)
        if blocos and blocos[-1]["planos"] == chave:
            blocos[-1]["fracoes"] += 1
        else:
            blocos.append({"planos": chave, "fracoes": 1})
    return blocos


def aplicar_modelo_em(etapas_atuais: list, etapas_modelo: list,
                      selecionados) -> list:
    """Sobrepõe um modelo (só dos planos SELECIONADOS) ao agendamento atual,
    preservando os planos NÃO selecionados na sequência.

    Cada dia do resultado une os planos não selecionados que já estavam nele com
    os planos selecionados que o modelo pôs no mesmo dia (dia 1 do modelo → dia 1,
    e assim por diante). Se o modelo encurta a ocupação de um plano selecionado e
    sobra um dia SEM nenhum plano no meio, esse dia vazio é removido (um cronograma
    não tem dia de tratamento vazio) — o que pode adiantar um plano não selecionado
    de um dia; a ordem relativa entre os não selecionados é mantida. Devolve blocos
    (dias iguais consecutivos agrupados).
    """
    sel = set(int(i) for i in selecionados)
    dias_mant = [[p for p in dia if p not in sel]
                 for dia in sequencia_de_etapas(etapas_atuais)]
    dias_mod = sequencia_de_etapas(etapas_modelo)
    n = max(len(dias_mant), len(dias_mod))
    dias = []
    for i in range(n):
        base = dias_mant[i] if i < len(dias_mant) else []
        novo = dias_mod[i] if i < len(dias_mod) else []
        dias.append(sorted(set(base) | set(novo)))
    # Dias vazios somem naturalmente em colapsar_dias (sequencia ignora planos=[]).
    return colapsar_dias([{"planos": d, "fracoes": 1} for d in dias])


def resumo_etapas(etapas: list, rotulos: list) -> str:
    """Texto curto do agendamento (cabeçalho/legenda / status)."""
    partes = []
    for et in etapas or []:
        planos = [p for p in (et.get("planos") or []) if p < len(rotulos)]
        if not planos:
            continue
        nomes = " + ".join(rotulos[p] for p in planos)
        partes.append(f"{nomes} ({et.get('fracoes', 0)} fx)")
    return "  →  ".join(partes)
