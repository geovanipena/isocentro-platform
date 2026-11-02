#!/usr/bin/env python
"""O robô: percorre as frentes `classe: robo` do DESTINO.md, uma sessão por vez.

    python tools/robo.py              # anda até a fila acabar ou algo reprovar
    python tools/robo.py --uma        # uma frente e para
    python tools/robo.py --simular    # mostra a próxima frente e o prompt; não chama o claude

Por que existe: o usuário quer o app andando para o DESTINO.md sem estar na
frente — `/clear`, `/code-review`, `/fechar` e as autorizações sem ninguém
clicar, parando quando o limite de uso bate e voltando quando ele libera.

Como cada peça do pedido virou mecanismo:

- **o `/clear`** é cada frente ser uma sessão `claude -p` nova. Não há conversa
  para limpar: a próxima nasce com o CLAUDE.md e o checkpoint, e só.
- **dizer sim** é `--permission-mode dontAsk` com a lista do
  `tools/robo_settings.json`: o que está nela passa, o resto é RECUSADO sem
  perguntar. `bypassPermissions` também não travaria, mas deixaria passar o
  que ninguém autorizou — e aqui do lado mora um banco clínico.
- **parar quando os tokens acabam e voltar** é reconhecer a mensagem de limite
  na saída, dormir até a hora que ela diz (ou 30 min, se não disser) e repetir
  a MESMA frente. A sessão nova retoma do checkpoint no NOTAS.md, que é
  exatamente como uma queda de conexão já se resolve neste projeto.

E o que o pedido não disse, mas o CLAUDE.md exige:

- **ninguém confia no relato da sessão.** Depois de cada uma, este script mede:
  o diff tocou `papel/`, `interface/`, `dominio/` ou a configuração do robô?
  alguma `classe:` do DESTINO.md mudou? o checkout do usuário mudou? a suíte
  está verde? o `varrer_identidade` está limpo? Qualquer "sim" errado PARA o
  robô inteiro, sem push. O gancho `robo_trava.py` recusa a edição na hora,
  mas um `python -c` passa por baixo dele — o diff não tem por onde passar.
- **o push é deste script**, só depois da conferência, e só da branch `robo`.
- **o robô trabalha num worktree** ao lado (`..\\isocentro-robo`), para não
  trocar de branch debaixo do VSCode do usuário.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

import raio  # noqa: E402
import robo_trava  # noqa: E402

WORKTREE = RAIZ.parent / "isocentro-robo"
BRANCH = "robo"
# A branch de onde o robô parte e para onde o usuário junta. Quando o usuário
# junta a `robo` na `main` e segue trabalhando, a `robo` fica para trás; o
# avanço rápido a traz de volta (ver `preparar`). Era a `v7` até 13/10/2026,
# quando a `main` voltou a ser a linha de trabalho e a versão virou TAG — a
# `v7` já carregava a v8 inteira, e o nome da branch mentia sobre o conteúdo.
BASE = "main"
# Os relatórios das sessões: `relatorios_ferramentas/` é ignorado inteiro pelo
# git, porque ferramenta nova escreve nome novo.
LOGS = RAIZ / "relatorios_ferramentas" / "robo"
PARTIDA = LOGS / "partida.json"

# Uma frente que termina sem marca (ou com PAROU) ganha mais uma chance; na
# segunda o robô desiste dela NESTA rodada. Sem teto, uma frente que sempre
# quebra consumiria o limite de uso inteiro repetindo a mesma tentativa.
TENTATIVAS_POR_FRENTE = 2
# Queda de rede não é culpa da frente e não conta tentativa — mas também não
# pode girar para sempre com a máquina desconectada.
QUEDAS_SEGUIDAS = 10
ESPERA_QUEDA_S = 120
# Quando a mensagem de limite não diz a hora, tenta-se de novo nesse intervalo.
ESPERA_LIMITE_S = 30 * 60
# Uma sessão inteira (frente + code-review + suíte) cabe com folga; passar
# disso é sessão pendurada, não trabalho.
SESSAO_MAX_S = 4 * 3600
# A suíte da CONFERÊNCIA é a ordem aleatória, e a da sessão é a alfabética. Até
# 15/09/2026 as duas rodavam na sessão e a alfabética rodava de novo aqui: três
# passes (~8 min) por frente, um deles repetido. Assim são dois, e a cobertura é
# a mesma — e a aleatória fica justamente com quem não confia no relato.
SUITE_DA_CONFERENCIA = ["tests/ordem_aleatoria.py"]
# Frente só de documento (raio "nenhum", ver `tools/raio.py`) não muda o
# executável: a aleatória inteira (~4 min) não testaria nada que o recorte dos
# testes que LEEM o documento não teste. Os questionários R-71..R-75 pagaram
# a suíte inteira cada um, em 23/10/2026.
SUITE_DE_DOCUMENTO = ["tools/testar.py", "--raio", "--ref"]


# ---------------------------------------------------------------- a fila

@dataclass
class Frente:
    id: str
    titulo: str
    classe: str
    estado: str
    bloco: str


_CABECALHO = re.compile(r"^### (R-\d+) — (.+?)\s*$")
_CAMPO = re.compile(r"^- (classe|estado):\s*(.+?)\s*$")


def ler_fila(texto: str) -> list[Frente]:
    """As frentes do DESTINO.md, na ordem do arquivo.

    O bloco vai inteiro no prompt: o "pronto quando" e o "fora" são o contrato
    da sessão, e resumi-los aqui seria o script decidir o escopo.
    """
    frentes: list[Frente] = []
    atual: dict | None = None
    linhas: list[str] = []

    def fecha():
        if atual is not None:
            frentes.append(Frente(atual["id"], atual["titulo"],
                                  atual.get("classe", ""), atual.get("estado", ""),
                                  "\n".join(linhas).strip()))

    for linha in texto.splitlines():
        cab = _CABECALHO.match(linha)
        if cab or linha.startswith("## "):
            fecha()
            atual, linhas = None, []
            if cab:
                atual = {"id": cab.group(1), "titulo": cab.group(2)}
        if atual is None:
            continue
        linhas.append(linha)
        campo = _CAMPO.match(linha)
        if campo:
            atual.setdefault(campo.group(1), campo.group(2))
    fecha()
    return frentes


def proxima(fila: list[Frente], desistidas: set[str]) -> Frente | None:
    for f in fila:
        if f.classe == "robo" and f.estado == "pendente" and f.id not in desistidas:
            return f
    return None


def classes(fila: list[Frente]) -> dict[str, str]:
    return {f.id: f.classe for f in fila}


def classes_mudadas(antes: dict[str, str], depois: dict[str, str]) -> list[str]:
    """Frentes cuja classe mudou, apareceram ou sumiram.

    Frente NOVA com classe `robo` também conta: o robô escrevendo a própria
    fila é o mesmo que reclassificar, e escolher o escopo é do usuário.
    """
    return sorted(i for i in set(antes) | set(depois) if antes.get(i) != depois.get(i))


# ---------------------------------------------------------------- a saída

_MARCA = re.compile(r"^ROBO: (FEITA|ESTACIONADA|PAROU) (R-\d+)(?::\s*(.*))?$", re.M)
_LIMITE_EPOCH = re.compile(r"limit reached\|(\d{10})", re.I)
_LIMITE_HORA = re.compile(r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.I)
# "hit your SESSION limit" (15/09/2026) não casava com "hit your limit": o robô
# leu o limite como fim sem marca, reprovou pela árvore suja e parou às 10:50 em
# vez de dormir até 14:20. A palavra do meio muda; o 429 do `result` é o que
# decide primeiro (ver `classificar`), e a regex fica para o texto sem JSON.
_LIMITE = re.compile(r"usage limit|hit your (?:\w+ )?limit|limit reached|out of (?:extra )?usage|"
                     r"rate[ _-]?limit", re.I)
_QUEDA = re.compile(r"connection refused|ECONNRESET|ETIMEDOUT|socket hang up|overloaded|"
                    r"API Error: 5\d\d|fetch failed|network error", re.I)


@dataclass
class Saida:
    tipo: str               # "limite" | "queda" | "fim"
    espera_s: float = 0.0
    marca: str = ""         # FEITA | ESTACIONADA | PAROU | ""
    frente: str = ""
    motivo: str = ""


def espera_do_limite(texto: str, agora: datetime) -> float:
    """Segundos até a hora que a mensagem de limite anuncia, com um minuto de folga.

    Dois formatos já existiram: o antigo trazia o instante em época Unix depois
    de uma barra, o novo diz "resets 3pm". Sem nenhum dos dois, espera-se o
    intervalo padrão — acordar cedo demais só custa uma tentativa que volta a
    dormir.
    """
    m = _LIMITE_EPOCH.search(texto)
    if m:
        return max(60.0, int(m.group(1)) - agora.timestamp() + 60)
    m = _LIMITE_HORA.search(texto)
    if m:
        hora, minuto, meio = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
        if meio == "pm" and hora < 12:
            hora += 12
        if meio == "am" and hora == 12:
            hora = 0
        if 0 <= hora < 24 and 0 <= minuto < 60:
            alvo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if alvo <= agora:
                alvo += timedelta(days=1)
            return (alvo - agora).total_seconds() + 60
    return float(ESPERA_LIMITE_S)


def classificar(bruto: str, agora: datetime) -> Saida:
    """O que a sessão devolveu: fim (com ou sem marca), limite ou queda.

    A MARCA vence o resto: uma sessão que terminou a frente e cita "rate limit"
    num comentário de código não pode ser posta para dormir. E sessão que
    devolveu JSON sem `is_error` TERMINOU, com ou sem marca: procurar "limite"
    no texto dela é ler o trabalho como se fosse o erro.
    """
    bruto = _sem_eventos(bruto)
    do_json = _resultado_json(bruto)
    texto = bruto if do_json is None else str(do_json.get("result", ""))
    marcas = _MARCA.findall(texto)
    if marcas:
        marca, frente, motivo = marcas[-1]
        return Saida("fim", marca=marca, frente=frente, motivo=motivo.strip())
    if do_json is not None and not do_json.get("is_error"):
        return Saida("fim")
    # O código HTTP do `result` antes do texto: a frase da mensagem já mudou
    # uma vez sem aviso, o 429 não.
    status = do_json.get("api_error_status") if do_json is not None else None
    if status == 429 or _LIMITE.search(bruto):
        return Saida("limite", espera_s=espera_do_limite(texto + "\n" + bruto, agora))
    if (isinstance(status, int) and status >= 500) or _QUEDA.search(bruto):
        return Saida("queda", espera_s=ESPERA_QUEDA_S)
    return Saida("fim")


def _sem_eventos(bruto: str) -> str:
    """O bruto sem os eventos do `stream-json`, menos o `result`.

    Desde que o robô mede o custo por etapa, a saída é o transcript inteiro: a
    resposta do gancho de abertura (com o texto do NOTAS.md), cada arquivo lido
    pela sessão — o próprio `robo.py`, que tem "rate limit" escrito na regex.
    Procurar a mensagem de limite nisso tudo poria para dormir uma sessão que
    só caiu. O que decide é o que decidia com o `json`: o `result` e o stderr.
    """
    fica = []
    for linha in bruto.splitlines():
        texto = linha.strip()
        if texto.startswith("{"):
            try:
                evento = json.loads(texto)
            except json.JSONDecodeError:
                evento = None
            if isinstance(evento, dict) and evento.get("type") not in (None, "result"):
                continue
        fica.append(linha)
    return "\n".join(fica)


# ---------------------------------------------------------------- o custo

# As etapas da sessão, na ordem do prompt. A troca de etapa é a chamada da
# skill: tudo o que vem antes do `code-review` é a frente.
ETAPAS = ("frente", "code-review", "fechar")


def _peso(uso: dict) -> float:
    """O uso de uma resposta em "tokens de entrada equivalentes".

    Proporções da tabela de preços, iguais nos modelos atuais: saída 5×, cache
    lido 0,1×, cache gravado 1,25× (5 min) ou 2× (1 h). Conferido em 15/09/2026
    na sessão vazia: 50.944 tokens gravados em 1 h deram US$ 0,5096 no Opus 5,
    que é 50.944 × US$ 10/M — o dobro dos US$ 5 da entrada.
    """
    gravado = uso.get("cache_creation") or {}
    if gravado:
        escrita = (1.25 * gravado.get("ephemeral_5m_input_tokens", 0)
                   + 2.0 * gravado.get("ephemeral_1h_input_tokens", 0))
    else:
        escrita = 1.25 * uso.get("cache_creation_input_tokens", 0)
    return (uso.get("input_tokens", 0) + escrita
            + 0.1 * uso.get("cache_read_input_tokens", 0) + 5.0 * uso.get("output_tokens", 0))


def custo_por_etapa(bruto: str) -> tuple[float, dict[str, float]]:
    """(US$ da sessão, {etapa: US$}), do `stream-json`.

    O total é o `total_cost_usd` do `result`, exato. A divisão é REPARTIÇÃO
    pelo peso dos tokens de cada resposta, não fatura: subagente num modelo
    mais barato sai com mais do que custou. Serve ao que se quer saber — se é a
    revisão que pesa, antes de cortar o nível dela no escuro.

    A mesma resposta pode vir em vários eventos (um por bloco), com o mesmo
    `id`: conta-se uma vez, com o último `usage`, na etapa em que apareceu.
    """
    etapa, total = ETAPAS[0], 0.0
    respostas: dict[str, tuple[str, float]] = {}
    for linha in bruto.splitlines():
        texto = linha.strip()
        if not texto.startswith("{"):
            continue
        try:
            evento = json.loads(texto)
        except json.JSONDecodeError:
            continue
        if not isinstance(evento, dict):
            continue
        if evento.get("type") == "result":
            total = float(evento.get("total_cost_usd") or 0)
        if evento.get("type") != "assistant":
            continue
        msg = evento.get("message") or {}
        ident = msg.get("id") or f"sem_id_{len(respostas)}"
        onde = respostas[ident][0] if ident in respostas else etapa
        respostas[ident] = (onde, _peso(msg.get("usage") or {}))
        for bloco in msg.get("content") or []:
            if isinstance(bloco, dict) and bloco.get("type") == "tool_use" and bloco.get("name") == "Skill":
                nome = str((bloco.get("input") or {}).get("skill", "")).split(":")[-1]
                if nome in ETAPAS:
                    etapa = nome
    pesos = {e: 0.0 for e in ETAPAS}
    for onde, peso in respostas.values():
        pesos[onde] += peso
    soma = sum(pesos.values())
    if not total or not soma:
        return total, {}
    return total, {e: total * p / soma for e, p in pesos.items()}


def recusas(bruto: str) -> list[str]:
    """As chamadas que o `dontAsk` recusou, uma por linha, do `result`.

    Cada recusa é um turno pago para nada, e a sessão tenta de outro jeito. Nas
    7 sessões de 15/09/2026 foram 15, e só se viam abrindo o JSON à mão: `git
    ls-files`, `git rev-parse`, `git -C` e escrita em `%TEMP%` — leitura
    inofensiva que a lista não previa. No `robo.log` a lista se ajusta pela
    medida, e não pelo palpite.
    """
    do_json = _resultado_json(_sem_eventos(bruto)) or {}
    linhas = []
    for recusa in do_json.get("permission_denials") or []:
        if not isinstance(recusa, dict):
            continue
        entrada = recusa.get("tool_input") or {}
        alvo = entrada.get("command") or entrada.get("file_path") or ""
        alvo = " ".join(str(alvo).split())
        linhas.append(f"{recusa.get('tool_name', '?')}: {alvo[:120]}")
    return linhas


def _resultado_json(bruto: str) -> dict | None:
    """O objeto do `--output-format json` (a última linha que é JSON), ou None."""
    for linha in reversed(bruto.strip().splitlines()):
        linha = linha.strip()
        if linha.startswith("{"):
            try:
                objeto = json.loads(linha)
            except json.JSONDecodeError:
                return None
            return objeto if isinstance(objeto, dict) else None
    return None


# ---------------------------------------------------------------- o prompt

# A cópia do checkout do usuário, por caminho absoluto: a `robo` só ganha o
# `tools/suite.py` quando o usuário junta. Barra normal, e com a letra do disco:
# `/c/Users/...` (o jeito do Git Bash) não existe para o Python no Windows.
_SUITE = (RAIZ / "tools" / "suite.py").as_posix()

def montar_prompt(frente: Frente, retomada: bool, hoje: str, partida: str = "HEAD") -> str:
    retomar = (
        "\n**Esta é uma RETOMADA**: a sessão anterior desta frente foi cortada (limite "
        "de uso, rede, ou terminou antes de fechar). Comece por `git status`, `git diff` "
        "e pelo topo do NOTAS.md: o que está na árvore NÃO foi conferido — revise "
        "antes de aproveitar, e continue do que já está feito.\n" if retomada else ""
    )
    return f"""Você é o robô do ISOCENTRO: uma sessão SEM ninguém na frente, aberta
pelo `tools/robo.py`. Ninguém vai responder pergunta; decisão que não é sua
se estaciona. O CLAUDE.md vale inteiro, com as regras abaixo por cima.
{retomar}
## A frente

{frente.bloco}

## Regras desta sessão

1. **Esta frente e só ela.** Nada além do "pronto quando"; o "fora" não se toca.
2. **`isocentro/papel/`, `interface/` e `dominio/` estão travados** (o
   gancho recusa, e o robo.py confere o diff depois). Se a frente precisar
   deles, ou de decisão do usuário, da clínica ou da TI, ou de dado que não
   está nesta máquina: **não invente e não contorne — estacione.**
3. **Não mude nenhuma linha `- classe:`** nem crie frente no DESTINO.md. Isso
   reprova a conferência inteira.
4. **Não faça push.** O `/git` e o `/fechar` mandam empurrar: aqui, pare no
   commit — o robo.py empurra depois de conferir.
5. **Termine com a árvore limpa**: tudo commitado, ou descartado com
   `git restore`. Árvore suja reprova a conferência.
6. **Nada em segundo plano, nada redirecionado, nada encadeado.** Esta sessão
   termina quando a sua resposta termina: `run_in_background` é resultado que
   ninguém volta para ler. E `> arquivo`, `2>&1`, `;`, `&&` e `|` fazem o
   comando inteiro ser RECUSADO. Isto vale POR CIMA do `/pronto` e do
   `/fechar`, que mandam o contrário. A suíte é sempre, da raiz do worktree,
   em primeiro plano e com `timeout` de 600000:
   `python {_SUITE}` (a completa, ~3 min)
   Ele grava a saída em arquivo e devolve só o veredito e o caminho. (O
   caminho é absoluto de propósito: roda os testes da pasta atual.)
   **A ordem aleatória NÃO é sua**, mesmo que o `/pronto` e o `/fechar` a
   peçam: o robo.py a roda na conferência, depois da sessão.
7. **Recusa custa um turno.** O git roda da raiz do worktree, sem `-C`.
   Arquivo temporário vai em `relatorios_ferramentas/tmp_robo/` (ignorado
   pelo git), nunca em `%TEMP%`, que fica fora do worktree e é recusado.
   Recusado uma vez, não tente o mesmo por outro caminho: o robo.py registra
   cada recusa, e a lista se ajusta por elas.

## A ordem

1. Checkpoint no topo do NOTAS.md antes da etapa longa (a sessão pode cair).
2. Fazer a frente, com `python tools/testar.py` durante.
3. `python tools/raio.py {partida}`. **Se o "Raio total" for "nenhum"** (só
   documento), pule o passo 4 e, no 5, troque a suíte completa por
   `python tools/testar.py --raio --ref {partida}` — os testes que leem o
   documento. Qualquer outro raio: os passos 4 e 5 inteiros.
4. Skill `code-review` (nível high) sobre o diff da frente; corrigir o que for
   confirmado.
5. Skill `fechar` com o argumento "{frente.id}": a suíte completa (pela regra
   6, sem a aleatória), checkpoint, commit. Sem push.
6. No DESTINO.md, a linha `- estado:` desta frente vira `feita ({hoje})`, ou
   `estacionada (motivo)` com uma linha no topo de "Esperando você". Commit.
7. **A última linha da resposta é exatamente uma destas:**

   ROBO: FEITA {frente.id}
   ROBO: ESTACIONADA {frente.id}: <motivo em uma linha>
   ROBO: PAROU {frente.id}: <motivo em uma linha — suíte vermelha, travado, etc.>
"""


# ---------------------------------------------------------------- git e disco

def git(*args: str, cwd: Path | None = None, checar: bool = True) -> str:
    # `None` e não `WORKTREE` no padrão: o padrão se congela na definição, e o
    # teste que aponta `robo.WORKTREE` para um repositório temporário rodaria o
    # git no worktree de verdade.
    r = subprocess.run(["git", *args], cwd=cwd or WORKTREE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if checar and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} (em {cwd}): {r.stderr.strip()}")
    return r.stdout.strip()


def preparar() -> None:
    """O worktree existe, está na `robo`, e a `robo` não ficou para trás da base."""
    if not (WORKTREE / ".git").exists():
        existe = git("branch", "--list", BRANCH, cwd=RAIZ)
        if existe:
            git("worktree", "add", str(WORKTREE), BRANCH, cwd=RAIZ)
        else:
            git("worktree", "add", "-b", BRANCH, str(WORKTREE), BASE, cwd=RAIZ)
    if git("rev-parse", "--abbrev-ref", "HEAD") != BRANCH:
        raise RuntimeError(f"o worktree {WORKTREE} não está na branch {BRANCH}")
    # Só avanço rápido, e só quando a `robo` inteira já está dentro da base:
    # é o caso de o usuário ter juntado e seguido. Divergiu? Não se mexe — o
    # usuário ainda não revisou o que a `robo` tem.
    atras = subprocess.run(["git", "merge-base", "--is-ancestor", BRANCH, BASE],
                           cwd=WORKTREE).returncode == 0
    if atras and not git("status", "--porcelain"):
        git("merge", "--ff-only", BASE)
        # O que a `robo` tinha já está na base, revisado pelo usuário; a partida
        # velha mediria os commits DELE como se fossem da sessão (e o papel que
        # ele mexeu reprovaria a trava).
        encerrar_partida()
    _sincronizar_claude()


def ponto_de_partida(frente_id: str) -> str:
    """O HEAD de quando a frente começou, sobrevivendo ao reinício do robô.

    A conferência mede `partida..HEAD`. Com o HEAD da volta atual, uma retomada
    mediria só os commits DELA: o que a sessão cortada commitou antes do corte
    escaparia da trava do diff e da varredura. Foi o caso da R-01 de 15/09,
    relançada à mão três vezes. Uma frente aberta por vez, então o arquivo
    guarda uma só; partida que não é ancestral do HEAD não vale mais.
    """
    sha = _partida_guardada().get(frente_id)
    if sha and subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"],
                              cwd=WORKTREE, capture_output=True).returncode == 0:
        return sha
    sha = git("rev-parse", "HEAD")
    PARTIDA.parent.mkdir(parents=True, exist_ok=True)
    PARTIDA.write_text(json.dumps({frente_id: sha}), encoding="utf-8")
    return sha


def _partida_guardada() -> dict[str, str]:
    try:
        guardada = json.loads(PARTIDA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return guardada if isinstance(guardada, dict) else {}


def frente_aberta() -> str | None:
    """A frente que começou e não fechou (tem partida guardada), se houver."""
    return next(iter(_partida_guardada()), None)


def encerrar_partida() -> None:
    PARTIDA.unlink(missing_ok=True)


def _sincronizar_claude() -> None:
    """Leva comandos, ganchos e skills do `.claude/` do usuário para o worktree.

    O `.claude/` é ignorado pelo git, então o worktree nasce SEM o `/fechar`,
    o `/pronto` e os ganchos. O `settings.local.json` não vai: é permissão da
    estação, dada à mão, e não foi dada ao robô. E o `additionalDirectories`
    do `settings.json` sai, porque aponta para o checkout do usuário — com ele
    o robô poderia editar a `main` direto.
    """
    origem, destino = RAIZ / ".claude", WORKTREE / ".claude"
    for pasta in ("commands", "hooks", "skills"):
        if (origem / pasta).is_dir():
            shutil.copytree(origem / pasta, destino / pasta, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
    config = json.loads((origem / "settings.json").read_text(encoding="utf-8"))
    config.get("permissions", {}).pop("additionalDirectories", None)
    (destino / "settings.json").write_text(json.dumps(config, ensure_ascii=False, indent=2),
                                           encoding="utf-8")


def configuracao_da_sessao() -> Path:
    """O `robo_settings.json` com a trava apontando para a cópia do USUÁRIO.

    O `$CLAUDE_PROJECT_DIR` da sessão é o worktree, e a trava de lá está na
    branch que o robô edita. A do checkout do usuário ele não alcança.
    """
    config = json.loads((RAIZ / "tools" / "robo_settings.json").read_text(encoding="utf-8"))
    trava = (RAIZ / "tools" / "robo_trava.py").as_posix()
    for grupo in config["hooks"]["PreToolUse"]:
        for gancho in grupo["hooks"]:
            gancho["command"] = gancho["command"].replace(
                "$CLAUDE_PROJECT_DIR/tools/robo_trava.py", trava)
    # A base de conhecimento fica fora do worktree, e sem isto toda leitura
    # dela pelo Bash era recusada — os questionários R-72 e R-73 (23/10/2026)
    # citam o texto das normas que mora lá. Só LEITURA: a trava recusa Write
    # fora do worktree mesmo em diretório adicional.
    conhecimento = RAIZ.parent.parent / "conhecimento"
    if conhecimento.is_dir():
        config.setdefault("permissions", {})["additionalDirectories"] = [conhecimento.as_posix()]
    LOGS.mkdir(parents=True, exist_ok=True)
    caminho = LOGS / "settings_sessao.json"
    caminho.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def arquivos_tocados(antes: str, cwd: Path | None = None) -> list[str]:
    """Commitados desde `antes` + o que sobrou na árvore, sem repetição.

    Por três listas de NOMES, e não recortando o `status --porcelain`: o `git()`
    tira o espaço da ponta da saída, e o `linha[3:]` do primeiro arquivo
    modificado comia uma letra — `isocentro/papel/x.py` virava
    `adioteraficha/papel/x.py` e passava pela trava do diff.
    """
    nomes = set(git("diff", "--name-only", f"{antes}..HEAD", cwd=cwd).splitlines())
    nomes |= set(git("diff", "--name-only", "HEAD", cwd=cwd).splitlines())
    nomes |= set(git("ls-files", "--others", "--exclude-standard", cwd=cwd).splitlines())
    return sorted(n for n in nomes if n)


def travados(nomes: list[str]) -> list[str]:
    return [n for n in nomes if robo_trava.travado(n)]


# ---------------------------------------------------------------- a conferência

def conferir(antes: str, classes_antes: dict[str, str], status_usuario: str,
             python: str, interrompida: bool = False) -> list[str]:
    """O que reprova, medido. Lista vazia = pode seguir.

    `interrompida` é a sessão que acabou sem FEITA/ESTACIONADA e deixou a
    árvore suja: trabalho no meio, não mentira. Ela passa pela trava de
    segurança inteira (checkout do usuário, pastas travadas, classes), mas a
    árvore suja não reprova, e a varredura e a suíte ficam para quando a frente
    fechar — não há push de trabalho pela metade. Até 15/09/2026 isso PARAVA o
    robô, e a retomada que o `main` já sabia fazer só acontecia por
    relançamento à mão.
    """
    falhas: list[str] = []
    if git("status", "--porcelain", cwd=RAIZ) != status_usuario:
        falhas.append(f"o checkout do usuário ({RAIZ}) mudou durante a sessão")
    if git("rev-parse", "--abbrev-ref", "HEAD") != BRANCH:
        falhas.append(f"o worktree saiu da branch {BRANCH}")
        return falhas
    if git("status", "--porcelain") and not interrompida:
        falhas.append("a árvore do worktree terminou suja")
    tocados = travados(arquivos_tocados(antes))
    if tocados:
        falhas.append("tocou o que é travado: " + ", ".join(tocados))
    destino = WORKTREE / "DESTINO.md"
    depois = classes(ler_fila(destino.read_text(encoding="utf-8"))) if destino.exists() else {}
    mudadas = classes_mudadas(classes_antes, depois)
    if mudadas:
        falhas.append("mudou a classe de: " + ", ".join(mudadas))
    if falhas or interrompida or git("rev-parse", "HEAD") == antes:
        return falhas
    # A varredura é a do checkout do USUÁRIO, e roda de lá: o `.identidades.json`
    # é ignorado pelo git e só existe ali. Rodando no worktree, ela só conferia o
    # registro colado ao sufixo — nome real e número puro passavam (achado em
    # 23/10/2026, na conferência da R-76). Os commits são os mesmos: o worktree
    # divide o repositório. E é a cópia que o robô não edita, como a trava.
    varre = subprocess.run([python, str(RAIZ / "tools" / "varrer_identidade.py"),
                            "--intervalo", f"{antes}..HEAD"],
                           cwd=RAIZ, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if varre.returncode != 0:
        falhas.append("varrer_identidade achou dado de paciente:\n" + varre.stdout[-2000:])
        return falhas
    # A suíte roda aqui mesmo que a sessão diga que rodou: é o relato que se
    # está conferindo — e na ordem aleatória, que a sessão não roda (ver
    # `SUITE_DA_CONFERENCIA`). Saída em arquivo, nunca por pipe (ver `| tail`
    # no CLAUDE.md), e o veredito é o código de saída.
    comando = suite_da_conferencia(antes)
    documento = comando[0] == SUITE_DE_DOCUMENTO[0]
    relatorio = LOGS / f"{'raio' if documento else 'aleatoria'}_{datetime.now():%Y%m%d-%H%M%S}.txt"
    with relatorio.open("w", encoding="utf-8") as saida:
        suite = subprocess.run([python, *comando],
                               cwd=WORKTREE, stdout=saida, stderr=subprocess.STDOUT,
                               env=_ambiente_filho(python))
    if suite.returncode != 0 and documento:
        falhas.append(f"recorte do raio vermelho no worktree (relatório: {relatorio})")
    elif suite.returncode != 0:
        semente = re.search(r"semente (\d+)", relatorio.read_text(encoding="utf-8", errors="replace"))
        falhas.append(f"ordem aleatória vermelha no worktree, semente "
                      f"{semente.group(1) if semente else '?'} (relatório: {relatorio})")
    return falhas


def suite_da_conferencia(antes: str) -> list[str]:
    """A aleatória inteira, ou só o recorte do raio quando a frente é documento.

    O raio se mede no WORKTREE, contra a partida: é o diff inteiro da frente,
    com o que uma sessão cortada já tinha commitado.
    """
    itens = raio.avaliar(raio.arquivos_do_diff(antes, WORKTREE), raio.montar_grafo(WORKTREE))
    if itens and raio.nivel_total(itens) == raio.NENHUM:
        return [*SUITE_DE_DOCUMENTO, antes]
    return list(SUITE_DA_CONFERENCIA)


def _ambiente_filho(python: str) -> dict[str, str]:
    """O worktree não tem `.venv` (é ignorado): o `python` da sessão tem de ser
    o do checkout do usuário, senão cai no do sistema, sem PyQt."""
    env = dict(os.environ)
    env["PATH"] = str(Path(python).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    # O gancho de abertura lê isto e não injeta o checkpoint vivo: o prompt já
    # leva a frente, e as 70 linhas do topo do NOTAS.md eram de OUTRA frente
    # (ver `docs/AMBIENTE.md`, seção do robô).
    env["ISOCENTRO_ROBO"] = "1"
    return env


# ---------------------------------------------------------------- a sessão

def rodar_sessao(frente: Frente, python: str, claude: str, retomada: bool = False,
                 partida: str = "HEAD") -> Saida:
    """Uma frente, repetida através de limite e queda até terminar."""
    config = configuracao_da_sessao()
    quedas = 0
    while True:
        prompt = montar_prompt(frente, retomada, f"{datetime.now():%d/%m/%Y}", partida)
        carimbo = f"{datetime.now():%Y%m%d-%H%M%S}"
        registrar(f"sessão {frente.id}{' (retomada)' if retomada else ''}")
        try:
            r = subprocess.run(
                # `stream-json` (com `--verbose`, que ele exige) e não `json`: o
                # `json` só traz o total, e a pergunta de 15/09/2026 era QUAL
                # etapa pesa. O `result` continua sendo a última linha.
                [claude, "-p", "--output-format", "stream-json", "--verbose",
                 "--permission-mode", "dontAsk", "--settings", str(config)],
                input=prompt, cwd=WORKTREE, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=SESSAO_MAX_S,
                env=_ambiente_filho(python))
            bruto = (r.stdout or "") + "\n" + (r.stderr or "")
        except subprocess.TimeoutExpired as e:
            # No Windows o que já saiu vem em BYTES mesmo com `text=True`.
            parcial = "\n".join(p.decode("utf-8", "replace") if isinstance(p, bytes) else p
                                for p in (e.stdout, e.stderr) if p)
            bruto = f"{parcial}\nROBO: PAROU {frente.id}: sessão passou de {SESSAO_MAX_S // 3600} h"
        (LOGS / f"{carimbo}_{frente.id}.txt").write_text(bruto, encoding="utf-8")
        total, etapas = custo_por_etapa(bruto)
        if total:
            partes = " · ".join(f"{e} {v:.2f}" for e, v in etapas.items())
            registrar(f"{frente.id}: US$ {total:.2f}" + (f" — {partes} (repartido pelo peso "
                                                        "dos tokens)" if partes else ""))
        for recusa in recusas(bruto):
            registrar(f"{frente.id}: recusada — {recusa}")
        saida = classificar(bruto, datetime.now())
        if saida.tipo == "fim":
            return saida
        if saida.tipo == "queda":
            quedas += 1
            if quedas >= QUEDAS_SEGUIDAS:
                return Saida("fim", marca="PAROU", frente=frente.id,
                             motivo=f"{quedas} quedas de rede seguidas")
        else:
            quedas = 0
        acorda = datetime.now() + timedelta(seconds=saida.espera_s)
        registrar(f"{saida.tipo}: dormindo até {acorda:%d/%m %H:%M}")
        time.sleep(saida.espera_s)
        retomada = True


def registrar(texto: str) -> None:
    linha = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {texto}"
    print(linha, flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "robo.log").open("a", encoding="utf-8") as log:
        log.write(linha + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--uma", action="store_true", help="uma frente e para")
    p.add_argument("--simular", action="store_true",
                   help="mostra a próxima frente e o prompt, sem chamar o claude")
    args = p.parse_args(argv)

    python = sys.executable
    claude = shutil.which("claude")
    if not args.simular and not claude:
        print("o `claude` não está no PATH (no Windows ele fica em %USERPROFILE%\\.local\\bin)")
        return 2

    preparar()
    if not (WORKTREE / "DESTINO.md").exists():
        print(f"a branch {BRANCH} não tem DESTINO.md: commitar o destino na {BASE} "
              f"e rodar de novo (o robô avança a {BRANCH} sozinho quando ela está atrás)")
        return 2
    desistidas: set[str] = set()
    tentativas: dict[str, int] = {}
    while True:
        fila = ler_fila((WORKTREE / "DESTINO.md").read_text(encoding="utf-8"))
        frente = proxima(fila, desistidas)
        # Árvore suja é da frente que a deixou, não da primeira da fila: depois
        # de um reinício a `desistidas` volta vazia, e uma frente já desistida
        # passaria na frente e herdaria o diff da outra.
        aberta = frente_aberta()
        if aberta and git("status", "--porcelain"):
            frente = next((f for f in fila if f.id == aberta and f.classe == "robo"
                           and f.estado == "pendente"), frente)
        if frente is None:
            registrar("fila vazia: nenhuma frente `robo` pendente. Fim.")
            return 0
        if args.simular:
            print(montar_prompt(frente, False, f"{datetime.now():%d/%m/%Y}"))
            return 0

        antes = ponto_de_partida(frente.id)
        status_usuario = git("status", "--porcelain", cwd=RAIZ)
        # Árvore suja na partida é trabalho de uma sessão que não fechou (a R-01
        # de 15/09 terminou esperando uma suíte em segundo plano). Descartar
        # jogaria fora o que pode estar certo; seguir como sessão NOVA faria a
        # próxima achar, sem aviso, edição que ninguém conferiu. Retomada diz as
        # duas coisas — e a conferência do fim mede o diff inteiro do mesmo jeito.
        suja = bool(git("status", "--porcelain"))
        if suja:
            registrar(f"{frente.id}: worktree sujo na partida; a sessão começa como retomada")
        saida = rodar_sessao(frente, python, claude, retomada=suja, partida=antes)
        registrar(f"{frente.id}: {saida.marca or 'sem marca'} {saida.motivo}".rstrip())

        fechou = saida.marca in ("FEITA", "ESTACIONADA")
        interrompida = not fechou and bool(git("status", "--porcelain"))
        falhas = conferir(antes, classes(fila), status_usuario, python, interrompida)
        if falhas:
            registrar("CONFERÊNCIA REPROVOU — nada foi empurrado, o robô para aqui:")
            for f in falhas:
                registrar(f"  - {f}")
            return 1

        if not fechou:
            tentativas[frente.id] = tentativas.get(frente.id, 0) + 1
            esgotou = tentativas[frente.id] >= TENTATIVAS_POR_FRENTE
            if interrompida:
                # Desistir e seguir para outra frente seria a próxima começar
                # por cima de um diff que não é dela.
                if esgotou:
                    registrar(f"{frente.id}: {TENTATIVAS_POR_FRENTE} tentativas e a árvore continua "
                              "suja; o robô para aqui, sem push")
                    return 1
                registrar(f"{frente.id}: interrompida com a árvore suja; a próxima volta retoma")
                if args.uma:
                    return 0
                continue
            if esgotou:
                desistidas.add(frente.id)
                registrar(f"{frente.id}: {TENTATIVAS_POR_FRENTE} tentativas sem terminar; fica para o usuário")
        if git("rev-parse", "HEAD") != antes:
            git("push", "-u", "origin", BRANCH)
            registrar(f"empurrado: {git('log', '--oneline', f'{antes}..HEAD')}")
        encerrar_partida()

        if fechou:
            # A sessão diz que fechou; se o DESTINO.md não concorda, a próxima
            # volta pegaria a mesma frente para sempre.
            depois = {f.id: f.estado for f in ler_fila((WORKTREE / "DESTINO.md").read_text(encoding="utf-8"))}
            if depois.get(frente.id) == "pendente":
                desistidas.add(frente.id)
                registrar(f"{frente.id}: marcou {saida.marca} mas o estado continua pendente")
        if args.uma:
            return 0


if __name__ == "__main__":
    sys.exit(main())
