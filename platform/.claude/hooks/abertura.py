"""Injeta a abertura da sessão: branch, árvore, checkpoint vivo e as armadilhas.

Existe porque toda sessão começava com uma leitura do `NOTAS.md` inteiro só
para achar onde o trabalho parou. São 25 KB — uns 6 mil tokens — e um turno
gasto, sempre, para responder a mesma pergunta. Aqui sai a PRIMEIRA seção (a
que está viva, por construção: a nova entra no topo) por uns 500 tokens e sem
turno nenhum.

Não substitui ler o resto do arquivo quando o assunto for outro: substitui a
leitura CEGA de abertura, que era a cara.

Desde 08/09/2026 injeta também os **títulos** do `ARMADILHAS.md`. O arquivo é
declaradamente permanente e é a parte mais consultada do registro, mas o único
caminho até ele era eu lembrar de dar um `grep` — e regra que depende de eu
lembrar dela falha um dia, que é a razão de existir de todos os ganchos daqui.
Só os títulos, de propósito: o corpo inteiro custaria ~1.200 tokens e a maior
parte não tem a ver com a frente do dia. O título basta para saber que a
entrada EXISTE; sabendo disso, abrir o arquivo e ler aquela entrada é barato.
Foi o que permitiu encolher a lista resumida do `CLAUDE.md`, que era paga em
toda requisição.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Teto de linhas da seção viva. Uma seção maior que isto não é checkpoint, é
# história — e história mora em `notas/AAAA-MM.md`. Cortar aqui em vez de
# deixar passar mantém honesto o custo que este gancho promete.
MAX_LINHAS_SECAO = 70
MAX_ARQUIVOS_SUJOS = 15

# O `NOTAS.md` cabe numa leitura (~400 linhas) — é essa a promessa dos três
# arquivos. O `/fechar` é quem a mantém, descendo a seção encerrada para o
# `notas/AAAA-MM.md`, e o `NOTAS.md` de 08/09/2026 deixou a verificação para o
# uso: "se em duas semanas o arquivo estiver com 1.500 linhas de novo, o ritual
# não pegou". Medir isso a cada abertura custa uma contagem de linhas; descobrir
# tarde custa o arquivo de 7.873 linhas que já existiu aqui uma vez.
ALVO_NOTAS = 400
TETO_NOTAS = 500
ORCAMENTO_CLAUDE = 360
TAMANHOS = RAIZ / ".claude" / "estado" / "tamanho_notas.tsv"

# A manutenção do AMBIENTE (`tools/manutencao.py`) — transcripts, build,
# ganchos órfãos, extensão que sumiu, seção que devia ter descido. Aqui só a
# marca: quando foi a última vez. O número está repetido do
# `manutencao.DIAS_ENTRE_EXECUCOES` de propósito — importar de `tools/` dentro
# de um gancho faria a abertura da sessão depender de um import que pode
# quebrar, e a abertura é justamente o que não pode falhar em silêncio.
DIAS_ENTRE_MANUTENCOES = 7
MANUTENCAO = RAIZ / ".claude" / "estado" / "manutencao.tsv"
RELATORIO = RAIZ / ".claude" / "estado" / "manutencao_ultima.md"
ANUNCIADO = RAIZ / ".claude" / "estado" / "manutencao_anunciada.txt"
TRAVA = RAIZ / ".claude" / "estado" / "manutencao.trava"

# Gancho rodado como teste — pela `tools/manutencao.py` ou pela suíte — lê e
# relata, mas não muda nada nem abre processo: não desce o NOTAS.md, não
# dispara a manutenção, não sobe o PostgreSQL. Um gancho que age quando é só
# conferido foi como nasceu a cascata de 28–29/10/2026.
SEM_EFEITO = bool(os.environ.get("ISOCENTRO_GANCHO_SEM_EFEITO"))

# Os prefixos das variáveis do app (`ambiente.ler` aceita os três nomes).
_PREFIXOS = ("ISOCENTRO_", "RADIOTERAFICHA_", "FICHAPY_")
_LOCAIS = {"localhost", "127.0.0.1", "::1"}


# Outra sessão no MESMO checkout divide o índice do git com esta (ARMADILHAS:
# em 15/09/2026 um commit levou o código de duas frentes e deixou de fora a
# seção do NOTAS.md da primeira, sem erro nenhum). Uma sessão viva se vê pelo
# transcript dela: modificado há pouco e SEM o registro `cost-state` que o
# Claude Code grava ao encerrar — inclusive no `/clear`, que senão faria a
# sessão anterior desta mesma janela passar por concorrente (conferido em
# 22/10/2026; o formato não é documentado, e se mudar o aviso só deixa de
# aparecer). 30 min: uma sessão parada há mais que isso já perdeu o cache e,
# na prática, foi abandonada; a que caiu com a conexão também não escreve
# `cost-state`, e é a janela que a aposenta.
JANELA_CONCORRENTE_S = 30 * 60


def _git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=RAIZ, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=8,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _secao_viva() -> str:
    """A primeira seção `##` do NOTAS.md, que é o que está em andamento."""
    notas = RAIZ / "NOTAS.md"
    if not notas.exists():
        return ""
    linhas = notas.read_text(encoding="utf-8", errors="replace").splitlines()

    # O cabeçalho do arquivo explica o próprio arquivo e já está no CLAUDE.md:
    # pular até o primeiro `## `, que é onde começa o checkpoint de verdade.
    inicio = next((i for i, ln in enumerate(linhas) if ln.startswith("## ")), None)
    if inicio is None:
        return ""
    fim = next(
        (i for i in range(inicio + 1, len(linhas)) if linhas[i].startswith("## ")),
        len(linhas),
    )
    corpo = linhas[inicio:fim]
    if len(corpo) > MAX_LINHAS_SECAO:
        corpo = corpo[:MAX_LINHAS_SECAO] + [
            f"…(seção cortada em {MAX_LINHAS_SECAO} linhas; o resto está no NOTAS.md)"
        ]
    return "\n".join(corpo).rstrip()


def _tamanho_do_notas() -> str:
    """Anota o tamanho do `NOTAS.md` e avisa quando ele passou do teto.

    A anotação é o que transforma "acho que está crescendo" em série: a data e o
    número de cada abertura, uma linha por dia em que mudou.
    """
    notas = RAIZ / "NOTAS.md"
    if not notas.exists():
        return ""
    try:
        with notas.open("rb") as fh:
            linhas = sum(1 for _ in fh)
    except Exception:
        return ""

    try:
        TAMANHOS.parent.mkdir(parents=True, exist_ok=True)
        hoje = date.today().isoformat()
        anterior = ""
        if TAMANHOS.is_file():
            registros = [ln for ln in
                         TAMANHOS.read_text(encoding="utf-8").splitlines() if ln.strip()]
            anterior = registros[-1] if registros else ""
        if anterior != f"{hoje}\t{linhas}":
            with TAMANHOS.open("a", encoding="utf-8") as fh:
                fh.write(f"{hoje}\t{linhas}\n")
    except Exception:
        pass  # a série é útil, mas não ao preço de derrubar a abertura

    if linhas <= ALVO_NOTAS or SEM_EFEITO:
        return ""
    # Desde 22/10/2026 a abertura DESCE, não avisa: o aviso repetiu de 15/10 a
    # 22/10 que o arquivo tinha 1.900 linhas e ninguém desceu nada. Aviso que
    # depende de alguém agir não é regra; `tools/notas.py` é a regra em código.
    try:
        r = subprocess.run(
            [sys.executable, str(RAIZ / "tools" / "notas.py"), "descer"],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10,
        )
        relato = r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        relato = ""
    if not relato or relato == "nada a descer":
        if linhas <= TETO_NOTAS:
            return ""
        return (
            f"> **`NOTAS.md` com {linhas} linhas** (teto: {TETO_NOTAS}) e o "
            "`tools/notas.py descer` não conseguiu baixar: seções sem data no "
            "título ou ferramenta com erro. Resolver nesta sessão."
        )
    return (
        f"> **O `NOTAS.md` passou de {ALVO_NOTAS} linhas e a abertura desceu, "
        "sozinha, o que já não estava em andamento** (`tools/notas.py`; entra "
        "no próximo commit):\n>\n> ```\n> "
        + relato.replace("\n", "\n> ") + "\n> ```"
    )


def _relatorio_novo() -> str:
    """O placar do relatório que terminou e ainda não foi anunciado."""
    if not RELATORIO.is_file():
        return ""
    try:
        feito = RELATORIO.stat().st_mtime
        anunciado = ANUNCIADO.stat().st_mtime if ANUNCIADO.is_file() else 0
    except OSError:
        return ""
    if feito <= anunciado:
        return ""
    relatorio = RELATORIO.read_text(encoding="utf-8", errors="replace")
    try:
        ANUNCIADO.write_text(str(feito), encoding="utf-8")
    except OSError:
        pass
    placar = next((ln.strip("* ") for ln in relatorio.splitlines()
                   if "para decidir agora" in ln), "")
    graves = [ln.strip("* !") for ln in relatorio.splitlines() if ln.startswith("**! ")]
    if not graves:
        return ""
    return (
        f"> **Manutenção semanal rodou sozinha** — {placar} Relatório em "
        "`.claude/estado/manutencao_ultima.md`. Para decidir agora:\n"
        + "".join(f"> - {g}\n" for g in graves)
        + "> Resolver nesta sessão o que não depende do usuário; o resto, "
        "perguntar uma vez."
    )


def _presa() -> str:
    """Aviso quando uma manutenção segura a trava há mais de 30 min."""
    try:
        pid, desde = TRAVA.read_text(encoding="utf-8").split("\t")
        inicio = datetime.fromisoformat(desde.strip())
    except (OSError, ValueError):
        return ""
    if (datetime.now() - inicio).total_seconds() < 30 * 60:
        return ""
    fd = None
    try:
        fd = os.open(TRAVA, os.O_RDWR)
        import msvcrt  # noqa: PLC0415
        # O mesmo byte da `manutencao.BYTE_DA_TRAVA` (repetido: gancho não
        # importa de `tools/`).
        os.lseek(fd, 1 << 20, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        os.lseek(fd, 1 << 20, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return ""  # a trava estava livre: o processo morreu, nada preso
    except OSError:
        return (f"> **Manutenção presa** desde {inicio:%d/%m %H:%M} (PID "
                f"{pid}): nenhuma outra roda enquanto ela não sair. Ver o "
                "processo antes de qualquer coisa.")
    except Exception:
        return ""
    finally:
        if fd is not None:
            os.close(fd)


def _manutencao() -> str:
    """Uma linha, e só quando há o que dizer.

    O eixo que esta ferramenta cobre — a bancada em volta do código — não muda
    por hora, muda por semana: um build de 200 MB, um gancho que saiu do
    `settings.json` e ficou em disco, uma extensão que sumiu da estação sem dar
    erro. Medir isso a cada abertura custaria o relatório inteiro no contexto
    todo dia para ler "nada mudou"; medir NUNCA é como se chega aos 7.873
    linhas do `NOTAS.md`. A marca resolve os dois: custa uma leitura de arquivo
    e só fala quando vale a pena olhar.

    Desde 22/10/2026 RODA a ferramenta quando vence, em vez de sugerir: a
    sugestão ficou sem resposta de 09/09 a 22/10.

    Desde 29/10/2026 roda em SEGUNDO PLANO e o placar sai na abertura
    seguinte. Esperando por ela (20 s), a manutenção nunca terminava — só a
    contagem de testes leva até 60 s —, a marca da semana nunca era gravada e
    TODA abertura a disparava de novo; somado a ela rodar este gancho ao
    testá-lo, virou cascata de 80 processos (ARMADILHAS, 29/10).
    """
    # Rodado como TESTE (pela manutenção ou pela suíte), este gancho não
    # dispara nada: era a manutenção rodando este gancho que rodava a
    # manutenção (ARMADILHAS, 29/10/2026).
    if SEM_EFEITO:
        return ""
    avisos = [a for a in (_relatorio_novo(), _presa()) if a]
    if MANUTENCAO.is_file():
        try:
            registros = [ln for ln in
                         MANUTENCAO.read_text(encoding="utf-8").splitlines() if ln.strip()]
            ultima = date.fromisoformat(registros[-1].split("\t")[0])
        except Exception:
            return "\n".join(avisos)
        if (date.today() - ultima).days < DIAS_ENTRE_MANUTENCOES:
            return "\n".join(avisos)
    try:
        RELATORIO.parent.mkdir(parents=True, exist_ok=True)
        # Destacada da sessão (sem janela, grupo próprio): o gancho sai na
        # hora e a manutenção termina quando terminar. Outra rodando, a
        # trava dela faz esta sair sem escrever nada além do aviso.
        flags = 0
        if os.name == "nt":
            flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                     | subprocess.CREATE_NO_WINDOW)
        subprocess.Popen(
            [sys.executable, str(RAIZ / "tools" / "manutencao.py"),
             "--relatorio", str(RELATORIO)],
            cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except Exception:
        return "\n".join(avisos)
    return "\n".join(avisos + [
        "> Manutenção semanal vencida: rodando em segundo plano; o placar "
        "sai na próxima abertura."])


def _variaveis_defasadas() -> list:
    """Variáveis do app mudadas no Windows DEPOIS que esta sessão nasceu.

    O VS Code (e tudo o que ele abre: esta sessão, o app pelo F5, a suíte)
    herda o ambiente de quando ELE abriu. Em 28/10/2026 a ISOCENTRO_PG_APP foi
    criada com o VS Code aberto, e a aba PPR seguiu "sem dado" para o
    usuário sem ninguém entender por quê.
    """
    try:
        import winreg  # noqa: PLC0415
        chave = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
    except Exception:
        return []
    defasadas = []
    i = 0
    while True:
        try:
            nome, valor, _tipo = winreg.EnumValue(chave, i)
        except OSError:
            break
        i += 1
        if nome.upper().startswith(_PREFIXOS) and \
                os.environ.get(nome, "") != str(valor):
            defasadas.append(nome)
    return sorted(defasadas)


def _porta_aberta(porta: int) -> bool:
    import socket  # noqa: PLC0415
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=0.5):
            return True
    except OSError:
        return False


def _postgres_local() -> str:
    """Sobe o PostgreSQL local se ele está fora, e diz que subiu.

    Sem perguntar: subir o banco de desenvolvimento não é decisão, é o
    estado em que a sessão precisa estar (a suíte tem testes de banco, a aba
    PPR lê dele). Destacado, para a abertura não esperar; pelo mesmo módulo
    que o app usa ao abrir (`adaptadores/postgres/local.py`).
    """
    import re  # noqa: PLC0415
    conninfo = (os.environ.get("ISOCENTRO_PG_APP")
                or os.environ.get("ISOCENTRO_PG_TESTE") or "")
    campos = dict(re.findall(r"(\w+)\s*=\s*'?([^'\s]+)'?", conninfo))
    if campos.get("host", "") not in _LOCAIS:
        return ""
    porta = int(campos.get("port", "5432"))
    if _porta_aberta(porta) or SEM_EFEITO:
        return ""
    try:
        flags = 0
        if os.name == "nt":
            flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                     | subprocess.CREATE_NO_WINDOW)
        subprocess.Popen(
            [sys.executable, "-c",
             "from isocentro.adaptadores.postgres import local;"
             "local.subir_se_preciso()"],
            cwd=RAIZ, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True,
            env={**os.environ, "ISOCENTRO_PG_APP": conninfo})
    except Exception:
        return (f"> **PostgreSQL local fora** (porta {porta}) e não consegui "
                "subir: os testes de banco vão falhar e a aba PPR fica sem "
                "dado. Ver `docs/AMBIENTE.md`, \"Não sobe sozinho\".")
    return (f"> PostgreSQL local estava fora (porta {porta}): subindo em "
            "segundo plano.")


def _ambiente() -> str:
    """O que no ambiente impede o trabalho, dito antes de virar sintoma."""
    avisos = []
    defasadas = _variaveis_defasadas()
    if defasadas:
        avisos.append(
            "> **Variável mudada depois que o VS Code abriu**: "
            + ", ".join(f"`{n}`" for n in defasadas)
            + ". Esta sessão, o app aberto pelo VS Code e a suíte usam o valor "
            "ANTIGO até o VS Code ser fechado e aberto de novo. Dizer isso ao "
            "usuário antes de qualquer conferência que dependa delas.")
    pg = _postgres_local()
    if pg:
        avisos.append(pg)
    return "\n".join(avisos)


def _orcamento_claude() -> str:
    """O `CLAUDE.md` entra em TODA requisição: cada linha a mais é paga sempre.

    Enxugar exige julgamento (o que é situacional, e para onde muda), então
    aqui não se corta nada: avisa-se, e a regra do próprio `CLAUDE.md` manda
    resolver na mesma sessão. Em 22/10/2026 ele tinha 394 linhas e foi a 352.
    """
    try:
        with (RAIZ / "CLAUDE.md").open("rb") as fh:
            linhas = sum(1 for _ in fh)
    except Exception:
        return ""
    if linhas <= ORCAMENTO_CLAUDE:
        return ""
    return (
        f"> **`CLAUDE.md` com {linhas} linhas** (orçamento: {ORCAMENTO_CLAUDE}). "
        "Mover o que é situacional para `docs/AMBIENTE.md` ou "
        "`tools/LEIAME_CLINICA.md` nesta sessão, sem esperar pedido."
    )


def _encerrada(transcript: Path) -> bool:
    """Lê só o fim do arquivo: o transcript de uma sessão longa passa de 4 MB."""
    try:
        with transcript.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 4096))
            ultima = fh.read().decode("utf-8", "replace").strip().splitlines()[-1]
        return json.loads(ultima).get("type") == "cost-state"
    except Exception:
        return False


def _sessoes_concorrentes(payload: dict) -> str:
    """Avisa se outra sessão está viva neste checkout.

    A pasta dos transcripts sai do `transcript_path` do próprio payload, e não
    de reconstruir o nome a partir do caminho do projeto: a regra de troca de
    caracteres é do Claude Code, e adivinhá-la é um aviso que falha calado.
    O worktree do robô tem pasta própria, então ele não conta aqui — e nem
    deveria: worktree separado é justamente o remédio.
    """
    atual = payload.get("transcript_path") or ""
    if not atual:
        return ""
    atual = Path(atual)
    agora = time.time()
    vivas = []
    try:
        candidatos = list(atual.parent.glob("*.jsonl"))
    except Exception:
        return ""
    for t in candidatos:
        if t.name == atual.name:
            continue
        try:
            idade = agora - t.stat().st_mtime
        except OSError:
            continue
        if idade <= JANELA_CONCORRENTE_S and not _encerrada(t):
            vivas.append((int(idade // 60), t.stem[:8]))
    if not vivas:
        return ""
    lista = ", ".join(f"`{s}` (há {m} min)" for m, s in sorted(vivas))
    return (
        f"> **Outra sessão viva neste checkout**: {lista}. As duas dividem o "
        "índice do git — um `git add` de lá entra no commit de cá. Frente "
        "paralela vai para worktree separado; se for ficar aqui mesmo, commit "
        "parcial por `GIT_INDEX_FILE` (ver `ARMADILHAS.md`)."
    )


def _armadilhas() -> str:
    """Os títulos do ARMADILHAS.md — o índice, não o corpo.

    Cada entrada do arquivo abre com o título em negrito (``- **assim.**``), que
    é justamente a frase curta que diz do que se trata. É o que se quer aqui:
    saber que a armadilha existe custa uma linha; saber o porquê dela custa o
    parágrafo, e esse só interessa quando o sintoma aparece.
    """
    arq = RAIZ / "ARMADILHAS.md"
    if not arq.exists():
        return ""
    titulos = [
        m.group(1).strip()
        for m in re.finditer(
            r"^- \*\*(.+?)\*\*",
            arq.read_text(encoding="utf-8", errors="replace"),
            re.MULTILINE,
        )
    ]
    if not titulos:
        # Silêncio seria pior que o aviso: o `CLAUDE.md` encolheu a lista dele
        # CONTANDO com esta injeção. Se o formato do arquivo mudar, quem lê
        # precisa saber que a rede de proteção caiu — não descobrir pisando.
        return (
            "> **`ARMADILHAS.md` não rendeu título nenhum** — o formato das "
            "entradas (`- **título.**`) mudou. O `CLAUDE.md` conta com esta "
            "lista; enquanto ela não voltar, ler o arquivo inteiro."
        )
    return "\n".join([
        f"**Armadilhas já pagas** ({len(titulos)}) — o título só; o porquê está "
        "no `ARMADILHAS.md`, entrada por entrada:",
        "",
        *(f"- {t}" for t in titulos),
    ])


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}  # sem payload o gancho ainda tem o que dizer

    # Na sessão do robô (`tools/robo.py` põe a variável) o checkpoint vivo, o
    # aviso de tamanho do NOTAS.md e o da manutenção ficam de fora. O prompt
    # dele já leva a frente; a seção do topo é de outra (em 15/09/2026, a do
    # próprio robô), e o aviso "`NOTAS.md` acima do teto — mover antes de abrir
    # frente nova" convidava a sessão a podar o arquivo fora do escopo dela.
    # Branch, commits e armadilhas ficam: servem a quem escreve código.
    robo = os.environ.get("ISOCENTRO_ROBO") == "1"

    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    sujo = [ln for ln in _git("status", "--short").splitlines() if ln.strip()]
    ultimos = _git("log", "-3", "--format=%h %s")

    partes = [
        "## Abertura da sessão (gancho `abertura.py`, não é pedido do usuário)",
        "",
        f"**Branch** `{branch}` — **{len(sujo)}** arquivo(s) modificado(s).",
    ]
    if sujo:
        amostra = sujo[:MAX_ARQUIVOS_SUJOS]
        partes += ["", "```", *amostra]
        if len(sujo) > len(amostra):
            partes.append(f"…e mais {len(sujo) - len(amostra)}")
        partes.append("```")
        # Árvore suja sem o NOTAS.md mexido = trabalho feito e não gravado. É
        # exatamente o estado que a queda de conexão transforma em prejuízo.
        if not any(ln.endswith("NOTAS.md") for ln in sujo):
            partes += [
                "",
                "> **Checkpoint possivelmente pendente**: há trabalho na árvore e o "
                "`NOTAS.md` não foi tocado. Conferir antes de abrir frente nova.",
            ]
    if ultimos:
        partes += ["", "**Últimos commits**", "```", ultimos, "```"]

    # Antes do checkpoint, e também na sessão do robô: é sobre o índice do
    # git, que vale para quem for commitar, seja quem for.
    concorrente = _sessoes_concorrentes(payload)
    if concorrente:
        partes += ["", concorrente]

    secao = "" if robo else _secao_viva()
    if secao:
        partes += [
            "",
            "**Checkpoint vivo — primeira seção do `NOTAS.md`:**",
            "",
            secao,
            "",
            "_(o resto do `NOTAS.md`, o índice e o `notas/AAAA-MM.md` continuam em "
            "disco: ler sob demanda, com `grep`, não inteiros.)_",
        ]

    armadilhas = _armadilhas()
    if armadilhas:
        partes += ["", armadilhas]

    if robo:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n".join(partes),
            }
        }, ensure_ascii=False))
        return 0

    aviso = _tamanho_do_notas()
    if aviso:
        partes += ["", aviso]

    manut = _manutencao()
    if manut:
        partes += ["", manut]

    ambiente = _ambiente()
    if ambiente:
        partes += ["", ambiente]

    orcamento = _orcamento_claude()
    if orcamento:
        partes += ["", orcamento]

    partes += [
        "",
        "**Um commit por frente.** O `/clear` é para pausa longa, assunto novo "
        "ou contexto grande (ver \"Economia de contexto\" no `CLAUDE.md`).",
    ]

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(partes),
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
