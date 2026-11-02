"""Confere se o AMBIENTE de trabalho ainda está de pé — e não apaga nada.

Por que existe: o projeto tem ritual para o código (a suíte, o `/fechar`, os
ganchos) e não tinha nenhum para a bancada em volta dele. O resultado é o que
se mediu em 09/09/2026, sem ninguém ter feito nada de errado: 187 MB de
transcripts em 67 sessões, 208 MB de `dist/` + `build/`, dois `ctx_*.txt` de
sessões mortas, saída de ferramenta parada em `tools/` desde 04/09, e um gancho
(`contexto.py`) que ninguém chama porque saiu do `settings.json` e continuou em
disco. Nada disso dói num dia. Tudo isso dói em três meses.

É a mesma doença dos quatro registros vencidos de 08/09/2026: **o sintoma de
algo que envelheceu é que ele parece certo**. Um `NOTAS.md` que diz "100
seções" no índice não grita quando passa a ter 103; uma extensão que sumiu da
estação não dá erro, o VS Code só ignora a chave que a configurava. Só medindo.

**Esta ferramenta nunca apaga.** Ela relata e imprime o comando de limpeza
pronto para copiar. O `TCs_Teste/` e os zips de release estão no mesmo terreno
que o lixo regenerável, e um `rm` esperto acerta o paciente errado — a decisão
é de quem lê, sempre.

Uso:

    python tools/manutencao.py                 # os cinco eixos, sem rede
    python tools/manutencao.py --rede          # inclui pip list --outdated
    python tools/manutencao.py --eixo notas    # só um eixo (repetível)

O `abertura.py` lê a marca em `.claude/estado/manutencao.tsv` e cutuca quando
passa de `DIAS_ENTRE_EXECUCOES`. Não roda nada sozinho: rodar custa segundos e
um relatório inteiro no contexto, e isso é escolha do usuário, não do gancho.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESTADO = RAIZ / ".claude" / "estado"
MARCA = ESTADO / "manutencao.tsv"
# Uma manutenção por vez. Em 28–29/10/2026 o abertura.py (que roda esta
# ferramenta) era rodado POR ela ao testar os ganchos, e cada nível rodava a
# manutenção de novo: 80 processos e duas suítes derrubadas. A trava é do
# sistema (msvcrt/fcntl), e não um arquivo-bandeira: o Windows a solta
# quando o processo morre, então trava velha de execução que caiu não existe.
TRAVA = ESTADO / "manutencao.trava"
# O byte travado fica LONGE do conteúdo: no Windows a trava de um byte também
# barra a LEITURA dele por outros, e o abertura.py precisa ler quem a tem
# para dizer que uma manutenção está presa.
BYTE_DA_TRAVA = 1 << 20
EXTENSOES_ANTES = ESTADO / "extensoes.txt"
SKILLS_ANTES = ESTADO / "skills.txt"

# De quanto em quanto tempo o `abertura.py` cutuca. Sete dias porque é o que
# separa "nada mudou" de "vale a pena olhar": os eixos aqui medem coisas que se
# movem por semana (uma extensão, um build, uma seção que devia ter descido),
# não por hora.
DIAS_ENTRE_EXECUCOES = 7

# O `NOTAS.md` promete caber numa leitura. O `CLAUDE.md` diz ~400 linhas; o
# gancho `abertura.py` só grita em 500. Os dois números valem coisas
# diferentes e por isso estão os dois aqui: 400 é a hora de descer uma seção,
# 500 é a hora de parar tudo e descer várias.
ALVO_NOTAS = 400
TETO_NOTAS = 500

# Idade a partir da qual uma pendência declarada aberta merece ser CONFERIDA —
# não fechada. Em 27/08/2026 havia três "EM ABERTO" no arquivo e uma delas
# estava resolvida havia dias. Vinte e um dias é tempo de sobra para uma frente
# real continuar aberta e tempo demais para uma que já morreu.
DIAS_PENDENCIA_VELHA = 21

# Uma seção de checkpoint que passou disso sem virar história é seção que o
# `/fechar` esqueceu de descer para o `notas/AAAA-MM.md`.
DIAS_SECAO_PARADA = 14

# Um `ctx_*.txt` é escrito por sessão viva. Passado um dia, é de sessão morta.
DIAS_CTX_ORFAO = 2

# Relatório de ferramenta com mais que isto é dado CLÍNICO parado numa
# estação: os de `mapear_gatilho`, `atividades` e `sondar_dicom` trazem nome
# e registro de paciente real. Não se apagam sozinhos — nenhuma ferramenta
# sobrescreve relatório, de propósito (ver `atividades._destino_livre`) —,
# então quem não for lembrado deles guarda 2026 inteiro na pasta.
DIAS_RELATORIO_VELHO = 60

# Acima disto o lixo regenerável deixa de ser detalhe. Não é limite técnico
# nenhum: é o ponto em que vale a pena gastar um comando para recuperar espaço.
MB_REGERAVEL = 100
MB_TRANSCRIPTS = 150

REGERAVEIS = ("dist", "build", "__pycache__", ".ruff_cache")

# Um mês de simulações e correções de capa é o que se aceita perder num disco
# que morre. A manutenção roda por semana, então o aviso chega com folga.
DIAS_COPIA_RESTRITO = 30

# Padrões de SAÍDA de ferramenta — arquivo que alguma execução gravou e
# ninguém mais leu. Só entram os que o git não rastreia (ver `_rastreados`):
# arquivo versionado não é lixo, é conteúdo.
SAIDA_SOLTA = (
    "atividades_achadas*.txt",
    "dicom_servidor_*.txt",
    "*_ficha.pdf",
    "ISOCENTRO_*.zip",
)

# O `Isocentro.spec` já esteve no SAIDA_SOLTA, e foi um erro caro: ele não
# é retrato de execução nenhuma, é FONTE — a lista de imports tardios do
# pacote. Marcado como lixo, foi apagado, e com ele o empacotamento
# inteiro (o `gerar_executavel.py` para no passo 2 sem o arquivo).
# Hoje ele é versionado, então o `_rastreados` já o pouparia; o
# comentário fica para o padrão não voltar por distração.

# Payload mínimo por gancho. Rodar um gancho com `{}` provaria pouco: vários
# leem o nome do evento e sairiam por um atalho, e o teste passaria sem ter
# exercitado nada. O que interessa é que ele aguente o payload REAL.
PAYLOADS = {
    "abertura.py": {"hook_event_name": "SessionStart", "source": "startup"},
    "antes_do_resumo.py": {"hook_event_name": "PreCompact", "trigger": "auto"},
    "barra_de_estado.py": {
        "hook_event_name": "Status",
        "workspace": {"current_dir": str(RAIZ)},
        "model": {"display_name": "Opus"},
    },
    "checar_py.py": {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(RAIZ / "tools" / "mapa.py")},
    },
    "contexto.py": {"hook_event_name": "UserPromptSubmit", "prompt": "oi"},
    "ler_grande.py": {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(RAIZ / "tools" / "mapa.py")},
    },
    "limite_de_contexto.py": {"hook_event_name": "UserPromptSubmit", "prompt": "oi"},
}


@dataclass
class Achado:
    """Uma coisa medida que merece decisão. `comando` é o que se copia."""

    eixo: str
    grave: bool
    titulo: str
    detalhe: str = ""
    comando: str = ""


@dataclass
class Eixo:
    nome: str
    achados: list[Achado] = field(default_factory=list)
    medidas: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# medidas auxiliares


def _mb(n: int) -> str:
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} MB"
    return f"{max(n // 1024, 1)} KB"


def _tamanho(caminho: Path) -> tuple[int, int]:
    """(bytes, arquivos) de uma árvore. Erro de acesso não derruba a medida."""
    total = arquivos = 0
    if caminho.is_file():
        try:
            return caminho.stat().st_size, 1
        except OSError:
            return 0, 0
    for base, _dirs, nomes in os.walk(caminho, onerror=lambda _e: None):
        for nome in nomes:
            try:
                total += (Path(base) / nome).stat().st_size
                arquivos += 1
            except OSError:
                pass
    return total, arquivos


def _dias(ts: float) -> int:
    return (datetime.now() - datetime.fromtimestamp(ts)).days


def _git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=RAIZ, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def _rastreados() -> set[str]:
    """Caminhos que o git versiona — o que está aqui NÃO é candidato a lixo."""
    return {ln.strip() for ln in _git("ls-files").splitlines() if ln.strip()}


def _texto(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _pasta_transcripts() -> Path | None:
    """A pasta de transcripts DESTE projeto, dentro de `~/.claude/projects`.

    O nome é o caminho absoluto com os separadores trocados por `-`, mas a
    letra do drive entra como o cliente a viu (`c` ou `C`), e o slug calculado
    aqui erraria por essa maiúscula. Calcula-se o esperado e, se ele não
    existir, procura-se por sufixo: é a mesma pasta e o custo é uma listagem.
    """
    base = Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return None
    slug = str(RAIZ).replace(":", "-").replace("\\", "-").replace("/", "-")
    if (base / slug).is_dir():
        return base / slug
    sufixo = f"-{RAIZ.name}"
    for p in base.iterdir():
        if p.is_dir() and p.name.lower().endswith(sufixo.lower()):
            return p
    return None


# --------------------------------------------------------------------------
# eixo 1 — armazenamento e lixo


def eixo_armazenamento() -> Eixo:
    e = Eixo("Armazenamento e lixo")

    regen = 0
    detalhes = []
    for nome in REGERAVEIS:
        alvo = RAIZ / nome
        if not alvo.exists():
            continue
        n, _q = _tamanho(alvo)
        regen += n
        detalhes.append(f"`{nome}/` {_mb(n)}")
    if regen:
        e.medidas.append(f"regeráveis: {_mb(regen)} ({', '.join(detalhes)})")
    if regen > MB_REGERAVEL * 1024 ** 2:
        e.achados.append(Achado(
            e.nome, False,
            f"{_mb(regen)} de artefato regenerável na árvore",
            "Tudo isso volta com `python tools/gerar_executavel.py`. Some do "
            "backup e da busca de arquivo, e não some do disco sozinho.",
            "python -c \"import shutil,pathlib;[shutil.rmtree(p,ignore_errors=True) "
            "for p in (pathlib.Path('dist'),pathlib.Path('build'))]\"",
        ))

    trans = _pasta_transcripts()
    if trans is None:
        e.medidas.append("transcripts: pasta não encontrada")
    else:
        n, _q = _tamanho(trans)
        # Uma SESSÃO é um `.jsonl` do topo. O `_tamanho` conta a árvore inteira,
        # que inclui as subpastas de anexo — contar por ali daria 150 onde há
        # 50, e número inflado num relatório de manutenção é a própria doença
        # que esta ferramenta persegue.
        sessoes = sorted(trans.glob("*.jsonl"))
        velhos = [p for p in sessoes if _dias(p.stat().st_mtime) > 60]
        e.medidas.append(f"transcripts: {_mb(n)} em {len(sessoes)} sessões")
        if n > MB_TRANSCRIPTS * 1024 ** 2:
            e.achados.append(Achado(
                e.nome, False,
                f"{_mb(n)} de transcripts em {len(sessoes)} sessões",
                (f"{len(velhos)} com mais de 60 dias." if velhos else
                 "Nenhuma com mais de 60 dias — o volume é de uso recente, "
                 "não de acúmulo esquecido.")
                + " São eles que o `--resume` e o `--continue` leem; apagar os "
                "antigos não afeta a sessão de hoje, mas perde aquelas "
                "conversas para sempre.",
                f'ls "{trans}"',
            ))

    orfaos = [
        p for p in ESTADO.glob("ctx_*.txt")
        if _dias(p.stat().st_mtime) >= DIAS_CTX_ORFAO
    ]
    if orfaos:
        e.achados.append(Achado(
            e.nome, False,
            f"{len(orfaos)} arquivo(s) `ctx_*.txt` de sessão morta",
            "Um por sessão, escrito pelo `limite_de_contexto.py`. Ninguém os "
            "recolhe no fim, então acumulam um por `/clear`.",
            "python tools/manutencao.py --limpar-ctx",
        ))

    rastreados = _rastreados()
    soltos = []
    for padrao in SAIDA_SOLTA:
        for p in list(RAIZ.glob(padrao)) + list((RAIZ / "tools").glob(padrao)):
            rel = p.relative_to(RAIZ).as_posix()
            if rel not in rastreados and p.is_file():
                soltos.append((rel, p.stat().st_size, _dias(p.stat().st_mtime)))
    if soltos:
        soltos.sort(key=lambda t: -t[2])
        e.achados.append(Achado(
            e.nome, False,
            f"{len(soltos)} arquivo(s) de saída parados na árvore",
            "\n".join(
                f"  - `{rel}` — {_mb(n)}, {d} dia(s)" for rel, n, d in soltos[:8]
            ) + ("\n  - …" if len(soltos) > 8 else "")
            + "\n\n  Zip de release **não entra no repositório** (vai como asset "
              "de Release); o resto é retrato de uma execução que já passou.",
        ))

    relatorios = RAIZ / "relatorios_ferramentas"
    if relatorios.is_dir():
        n, q = _tamanho(relatorios)
        arquivos = [x for x in relatorios.iterdir() if x.is_file()]
        e.medidas.append(
            f"relatórios de ferramenta: {_mb(n)} em {q} arquivo(s)")
        velhos = [x for x in arquivos
                  if _dias(x.stat().st_mtime) > DIAS_RELATORIO_VELHO]
        if velhos:
            velhos.sort(key=lambda x: x.stat().st_mtime)
            idade = _dias(velhos[0].stat().st_mtime)
            e.achados.append(Achado(
                e.nome, False,
                f"{len(velhos)} relatório(s) de ferramenta com mais de "
                f"{DIAS_RELATORIO_VELHO} dias",
                "Trazem nome e registro de paciente real, e o mais antigo "
                f"tem {idade} dia(s). Conferido o que se foi buscar, o "
                "relatório não tem por que continuar na estação — e o que "
                "virou conclusão já está no `notas/AAAA-MM.md`.",
                f'ls "{relatorios}"',
            ))

    tmp = Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "claude"
    if tmp.is_dir():
        n, q = _tamanho(tmp)
        e.medidas.append(f"scratchpad: {_mb(n)} em {q} arquivo(s)")
        if n > 200 * 1024 ** 2:
            e.achados.append(Achado(
                e.nome, False, f"scratchpad com {_mb(n)}",
                "É temporário por definição e o Windows não o esvazia sozinho.",
                f'rmdir /s /q "{tmp}"',
            ))

    _conferir_copia_restrito(e)
    return e


def _conferir_copia_restrito(e: Eixo, restrito: Path | None = None) -> None:
    """Idade da última cópia cifrada do `_restrito/` fora deste disco.

    A cópia quem faz é o usuário (`tools/copiar_restrito.ps1`): é dado de
    paciente indo para mídia física, e isso não é decisão de ferramenta. Aqui
    só se lê a marca que o script grava — data, destino, tamanho, nunca o
    conteúdo. Sem pasta `_restrito/` (outra estação, a CI) não há o que
    conferir, e o silêncio é a resposta certa.
    """
    restrito = restrito or RAIZ.parents[1] / "_restrito"
    if not restrito.is_dir():
        return
    comando = (r"powershell -ExecutionPolicy Bypass -File "
               r"tools\copiar_restrito.ps1 -Destino E:\copias")
    marca = _texto(restrito / "ultima_copia.txt").strip().splitlines()
    if not marca:
        e.achados.append(Achado(
            e.nome, True, "o `_restrito/` nunca foi copiado para fora deste disco",
            "  Os backups que existem (`backup_registros`, `backups-git`) moram no "
            "mesmo disco: um SSD que falha leva junto espelho da capa, índice de "
            "fichas, simulações e os `TCs_Teste` com gabarito. Cópia cifrada "
            "(7-Zip AES-256) num disco externo; o script recusa o mesmo disco e "
            "a nuvem.",
            comando,
        ))
        return
    campos = marca[-1].split("\t")
    try:
        quando = datetime.strptime(campos[0], "%Y-%m-%d").date()
    except ValueError:
        e.achados.append(Achado(e.nome, True,
                                "`_restrito/ultima_copia.txt` ilegível", "", comando))
        return
    idade = (date.today() - quando).days
    e.medidas.append(f"última cópia do `_restrito/`: {quando.strftime('%d/%m/%Y')} "
                     f"({idade} dia(s)), {campos[-1] if len(campos) > 2 else '?'}")
    if idade > DIAS_COPIA_RESTRITO:
        e.achados.append(Achado(
            e.nome, True,
            f"a cópia do `_restrito/` tem {idade} dias",
            "  O que entrou depois dela (simulações, correções de capa, fichas "
            "registradas) só existe neste disco.",
            comando,
        ))


# --------------------------------------------------------------------------
# eixo 2 — saúde do .claude/ e da documentação


def _rodar_gancho(caminho: Path) -> tuple[int, str]:
    payload = json.dumps(PAYLOADS.get(caminho.name, {}), ensure_ascii=False)
    # Gancho conferido não age (`SEM_EFEITO` no abertura.py): sem a marca,
    # testar o abertura.py rodava a manutenção de novo, sem fim.
    amb = {**os.environ, "PYTHONIOENCODING": "utf-8",
           "ISOCENTRO_GANCHO_SEM_EFEITO": "1",
           "CLAUDE_PROJECT_DIR": str(RAIZ)}
    try:
        r = subprocess.run(
            [sys.executable, str(caminho)], input=payload, cwd=RAIZ,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, env=amb,
        )
        return r.returncode, (r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return -1, "estourou 30 s"
    except Exception as erro:  # noqa: BLE001 — qualquer falha aqui é notícia
        return -2, str(erro)


def _contar_testes() -> int | None:
    """Quantos testes o `discover` acha, sem rodar nenhum (~3 s).

    Num subprocesso, e não importando a suíte aqui: os módulos de teste mexem
    em `os.environ` e no Qt, e a manutenção roda dentro da abertura da sessão.
    """
    amb = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    try:
        r = subprocess.run(
            [sys.executable, "-c",
             "import unittest;print(unittest.TestLoader()"
             ".discover('tests').countTestCases())"],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60, env=amb,
        )
        return int(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None


def _conferir_numeros_da_suite() -> Achado | None:
    """O `CLAUDE.md` diz quantos testes há e quanto a suíte leva; isso envelhece.

    O próprio `CLAUDE.md` avisa que "este número envelhece calado": em
    22/10/2026 ele dizia 1.945 testes e 160 s, e eram 2.365 — e quem espera
    2,7 minutos e vê 3,5 não sabe se é a máquina ou um teste esperando à toa.
    Aqui só se CONTA (o tempo exigiria rodar a suíte, que é coisa do
    `/pronto`); contagem que andou mais de 10% quer dizer que o tempo também
    precisa ser medido de novo.
    """
    m = re.search(r"\((\d+) s, ([\d.]+) testes, medido em (\d\d/\d\d/\d{4})\)",
                  _texto(RAIZ / "CLAUDE.md"))
    if not m:
        return Achado(
            "Saúde do `.claude/` e da documentação", False,
            "o `CLAUDE.md` não traz mais a medida da suíte no formato conhecido",
            "  Esperado: `(160 s, 1.945 testes, medido em 14/09/2026)`. Sem ela, "
            "esta conferência não tem com o que comparar.",
        )
    declarados = int(m.group(2).replace(".", ""))
    contados = _contar_testes()
    if contados is None or abs(contados - declarados) <= declarados * 0.10:
        return None
    return Achado(
        "Saúde do `.claude/` e da documentação", False,
        f"o `CLAUDE.md` diz {m.group(2)} testes (em {m.group(3)}); hoje são "
        f"{contados:,}".replace(",", "."),
        "  O tempo da suíte cresce junto e também está vencido. Na próxima "
        "suíte completa, anotar o `Ran N` e os segundos e trocar os dois "
        "números de uma vez.",
    )


def eixo_claude() -> Eixo:
    e = Eixo("Saúde do `.claude/` e da documentação")

    ajustes = json.loads(_texto(RAIZ / ".claude" / "settings.json") or "{}")
    citados: set[str] = set()
    for evento in (ajustes.get("hooks") or {}).values():
        for grupo in evento:
            for g in grupo.get("hooks", []):
                for m in re.finditer(r"hooks[/\\]([\w.]+\.py)", g.get("command", "")):
                    citados.add(m.group(1))
    linha_barra = ((ajustes.get("statusLine") or {}).get("command") or "")
    for m in re.finditer(r"hooks[/\\]([\w.]+\.py)", linha_barra):
        citados.add(m.group(1))

    pasta_ganchos = RAIZ / ".claude" / "hooks"
    em_disco = {p.name for p in pasta_ganchos.glob("*.py")}

    # Nem todo `.py` em `hooks/` é um gancho: o `contexto.py` é o MÓDULO da
    # conta de contexto, importado pela barra de estado — "uma só, porque dois
    # números discordando não seriam consultados por ninguém". A primeira
    # versão desta ferramenta o acusou de órfão, que é o falso positivo clássico
    # de quem confunde arquivo com entrada. Módulo importado por outro gancho
    # está sendo usado; o que não está é o que ninguém cita de jeito nenhum.
    importados = set()
    fonte = "\n".join(_texto(p) for p in pasta_ganchos.glob("*.py"))
    for nome in em_disco:
        modulo = nome[:-3]
        if re.search(rf"^\s*(?:from\s+{modulo}\s+import|import\s+{modulo})\b",
                     fonte, re.MULTILINE):
            importados.add(nome)

    e.medidas.append(
        f"ganchos: {len(em_disco)} em disco, {len(citados)} ligados"
        + (f", {len(importados)} como módulo" if importados else "")
    )

    for nome in sorted(citados - em_disco):
        e.achados.append(Achado(
            e.nome, True, f"gancho `{nome}` está no settings.json e NÃO existe",
            "O Claude Code não reclama de gancho ausente: ele simplesmente não "
            "roda. É o modo de falhar que este projeto mais persegue.",
        ))
    for nome in sorted(em_disco - citados - importados):
        e.achados.append(Achado(
            e.nome, False, f"`{nome}` em `hooks/` e ninguém o chama nem o importa",
            "Ou volta para o `settings.json`, ou vira import de outro gancho, ou "
            "sai de disco. Ficar no meio é código que parece ativo e não é — e o "
            "próximo leitor acredita.",
        ))

    quebrados = []
    for nome in sorted(citados & em_disco):
        codigo, erro = _rodar_gancho(RAIZ / ".claude" / "hooks" / nome)
        # Exit 2 é o BLOQUEIO combinado com o agente (o `checar_py.py` usa), não
        # é defeito. Só interessa o que estourou de verdade.
        if codigo not in (0, 2):
            quebrados.append(f"  - `{nome}` — saiu com {codigo}: "
                             f"{(erro or '(sem stderr)').splitlines()[0][:120]}")
    if quebrados:
        e.achados.append(Achado(
            e.nome, True, f"{len(quebrados)} gancho(s) quebrado(s) na execução",
            "\n".join(quebrados) + "\n\n  Gancho que estoura some da abertura "
            "sem avisar — some justamente o aviso.",
        ))
    else:
        e.medidas.append(f"todos os {len(citados & em_disco)} ganchos ligados rodaram")

    faltando = []
    for md in sorted((RAIZ / ".claude" / "commands").glob("*.md")):
        for m in re.finditer(r"\b((?:tools|tests)[/\\][\w.]+\.py)", _texto(md)):
            alvo = RAIZ / m.group(1).replace("\\", "/")
            if not alvo.exists():
                faltando.append(f"  - `/{md.stem}` chama `{m.group(1)}`, que não existe")
    if faltando:
        e.achados.append(Achado(
            e.nome, True, "comando de sessão apontando para arquivo inexistente",
            "\n".join(sorted(set(faltando))),
        ))

    doc = "\n".join(_texto(RAIZ / p) for p in
                    ("docs/AMBIENTE.md", "tools/LEIAME_CLINICA.md", "CLAUDE.md"))
    nao_documentadas = sorted(
        p.name for p in (RAIZ / "tools").glob("*.py") if p.name not in doc
    )
    if nao_documentadas:
        e.achados.append(Achado(
            e.nome, False,
            f"{len(nao_documentadas)} ferramenta(s) fora da documentação",
            "  " + ", ".join(f"`{n}`" for n in nao_documentadas)
            + "\n\n  O `docs/AMBIENTE.md` é onde se procura o porquê e o número "
              "medido de cada uma. Ferramenta que não está lá não é encontrada.",
        ))

    achado = _conferir_numeros_da_suite()
    if achado:
        e.achados.append(achado)

    sem_doc = sorted(
        f"/{p.stem}" for p in (RAIZ / ".claude" / "commands").glob("*.md")
        if p.stem not in doc
    )
    if sem_doc:
        e.achados.append(Achado(
            e.nome, False, f"comando(s) de sessão fora da doc: {', '.join(sem_doc)}",
            "O `.claude/` é ignorado pelo git; o que o git guarda é a descrição "
            "no `docs/AMBIENTE.md`. Comando fora dela não sobrevive à estação.",
        ))
    return e


# --------------------------------------------------------------------------
# eixo 3 — notas e checkpoints


def _idade_da_marca(texto: str) -> int | None:
    """Dias desde a data `DD/MM` ou `DD/MM/AAAA` achada no texto, se houver."""
    m = re.search(r"\b(\d{2})/(\d{2})(?:/(\d{4}))?\b", texto)
    if not m:
        return None
    hoje = date.today()
    ano = int(m.group(3)) if m.group(3) else hoje.year
    try:
        d = date(ano, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    # Sem ano, uma data à frente de hoje é do ano passado (dezembro visto em
    # janeiro), não do futuro.
    if d > hoje and not m.group(3):
        d = date(ano - 1, int(m.group(2)), int(m.group(1)))
    return (hoje - d).days


_CONFERIDA = re.compile(
    r"conferid[ao]\s+em\s+(\d{2})/(\d{2})(?:/(\d{4}))?", re.IGNORECASE)


def _idade_da_conferencia(texto: str) -> int | None:
    """Dias desde o `conferida em DD/MM` da linha, se ela tiver um.

    Existe porque a data do começo e a data da última conferência são coisas
    diferentes, e a linha carrega as duas: `- 19/08 — [título] — conferida em
    09/09`. O ``_idade_da_marca`` pega a PRIMEIRA data do texto, que é a da
    abertura — o que é certo para "há quanto tempo isto está aberto" e errado
    para "há quanto tempo ninguém olha".
    """
    m = _CONFERIDA.search(texto)
    return _idade_da_marca(m.group(0)) if m else None


def _encurtar(linha: str, limite: int = 100) -> str:
    """Corta a linha sem partir o markdown no meio.

    O corte cru em 100 caracteres devolvia `[título](notas/…) — **conferida`,
    com o negrito aberto e sem fechar: o relatório saía com o resto da linha em
    negrito e o link pela metade. Cortar no último espaço antes do limite e
    largar os marcadores soltos é feio; não mostrar o rabo é honesto.
    """
    if len(linha) <= limite:
        return linha
    corte = linha[:limite].rsplit(" ", 1)[0]
    # Marcador que ficou ímpar no corte não pode viajar sozinho.
    for marca in ("**", "`", "*", "_"):
        if corte.count(marca) % 2:
            corte = corte.rsplit(marca, 1)[0].rstrip()
    return corte.rstrip(" -—[(") + "…"


def eixo_notas() -> Eixo:
    e = Eixo("Notas e checkpoints")
    notas = RAIZ / "NOTAS.md"
    texto = _texto(notas)
    if not texto:
        e.achados.append(Achado(e.nome, True, "`NOTAS.md` ausente ou ilegível"))
        return e

    linhas = texto.splitlines()
    e.medidas.append(f"`NOTAS.md`: {len(linhas)} linhas (alvo {ALVO_NOTAS})")
    if len(linhas) > TETO_NOTAS:
        e.achados.append(Achado(
            e.nome, True, f"`NOTAS.md` com {len(linhas)} linhas (teto {TETO_NOTAS})",
            "O arquivo que se lê inteiro parou de caber numa leitura. **Mover** "
            "seções encerradas para `notas/AAAA-MM.md` — não resumir.",
        ))
    elif len(linhas) > ALVO_NOTAS:
        e.achados.append(Achado(
            e.nome, False, f"`NOTAS.md` com {len(linhas)} linhas (alvo {ALVO_NOTAS})",
            "Ainda cabe, já passou do alvo. Uma seção descendo no próximo "
            "`/fechar` resolve; três meses assim reconstroem o arquivo de 7.873 "
            "linhas que já existiu aqui.",
        ))

    cabecalhos = [(i, ln[3:].strip()) for i, ln in enumerate(linhas)
                  if ln.startswith("## ")]
    paradas = []
    for i, titulo in cabecalhos:
        if titulo.startswith(("O que está aberto", "Índice")):
            continue
        idade = _idade_da_marca(titulo)
        if idade is not None and idade > DIAS_SECAO_PARADA:
            paradas.append(f"  - linha {i + 1}: {titulo} — {idade} dias")
    if paradas:
        e.achados.append(Achado(
            e.nome, False, f"{len(paradas)} seção(ões) paradas há mais de "
            f"{DIAS_SECAO_PARADA} dias no `NOTAS.md`",
            "\n".join(paradas) + "\n\n  Seção que não é mais o que está em "
            "andamento **desce** para o `notas/AAAA-MM.md` do mês em que foi "
            "escrita, e ganha uma linha no índice.",
        ))

    # A seção "O que está aberto" lista as pendências como `- DD/MM — [título]`.
    inicio = next((i for i, t in cabecalhos if t.startswith("O que está aberto")), None)
    if inicio is not None:
        fim = next((i for i, _t in cabecalhos if i > inicio), len(linhas))
        velhas, idades = [], []
        for ln in linhas[inicio:fim]:
            if not ln.strip().startswith("- "):
                continue
            idade = _idade_da_marca(ln)
            if idade is None:
                continue
            # "conferida em DD/MM" REINICIA o relógio. A idade sozinha não
            # separa nota vencida de frente bloqueada, e é essa a diferença que
            # o achado existe para achar: as duas de 19/08 foram conferidas no
            # código em 09/09 e continuam abertas de verdade — dependem de
            # consulta com identidade de rede. Sem isto, o relatório pediria a
            # mesma conferência toda semana, e o achado que se repete sem
            # motivo é o que se aprende a pular.
            idades.append(idade)
            # A marca reinicia o GATILHO, não a medida: a pendência continua
            # tendo os 21 dias que tem, e é isso que a linha de medida diz.
            # Zerar os dois faria o relatório anunciar "a mais velha de 0 dias"
            # para um arquivo com frentes de três semanas — mediria a data da
            # última conferência achando que mede idade.
            conferida = _idade_da_conferencia(ln)
            desde_olhada = idade if conferida is None else min(idade, conferida)
            if desde_olhada >= DIAS_PENDENCIA_VELHA:
                # A linha já vem com o `- ` do markdown do NOTAS.md; prefixar
                # outro daria "- - 19/08" no relatório.
                velhas.append(f"  {_encurtar(ln.strip())} — {idade} dias")
        # A medida sai mesmo quando nada dispara: relatório que só fala quando
        # há problema não deixa ver que ele OLHOU. "Nada a decidir" sem número
        # ao lado é indistinguível de um parser que parou de casar.
        if idades:
            medida = (f"pendências declaradas abertas: {len(idades)}, "
                      f"a mais velha de {max(idades)} dias")
            if not velhas and max(idades) >= DIAS_PENDENCIA_VELHA:
                medida += " — todas conferidas depois disso"
            e.medidas.append(medida)
        if velhas:
            e.achados.append(Achado(
                e.nome, True,
                f"{len(velhas)} pendência(s) declaradas abertas há mais de "
                f"{DIAS_PENDENCIA_VELHA} dias",
                "\n".join(velhas) + "\n\n  **Conferir, não fechar.** Um "
                "\"EM ABERTO\" já resolvido é pior que nota nenhuma: ninguém "
                "questiona o que está escrito.",
            ))

    quebrados = sorted({
        alvo for alvo in re.findall(r"\]\((notas/[\w.-]+\.md)\)", texto)
        if not (RAIZ / alvo).exists()
    })
    if quebrados:
        e.achados.append(Achado(
            e.nome, True, "índice apontando para arquivo que não existe",
            "  " + ", ".join(f"`{q}`" for q in quebrados),
        ))

    # O título do índice carrega uma contagem — "(100 seções)" — e contagem
    # escrita à mão é a coisa que mais silenciosamente envelhece num arquivo
    # que cresce por acréscimo.
    m = re.search(r"^## Índice do que já foi \((\d+) seções\)", texto, re.MULTILINE)
    if m:
        i_ind = next(i for i, t in cabecalhos if t.startswith("Índice"))
        f_ind = next((i for i, _t in cabecalhos if i > i_ind), len(linhas))
        reais = sum(1 for ln in linhas[i_ind:f_ind] if re.match(r"^- .*\]\(", ln))
        if reais and abs(reais - int(m.group(1))) > 0:
            e.achados.append(Achado(
                e.nome, False,
                f"índice diz {m.group(1)} seções e lista {reais}",
                "Número escrito à mão num arquivo que cresce por acréscimo. "
                "Não quebra nada — e é exatamente por isso que ninguém o "
                "confere.",
            ))

    armadilhas = _texto(RAIZ / "ARMADILHAS.md")
    n_arm = len(re.findall(r"^- \*\*(.+?)\*\*", armadilhas, re.MULTILINE))
    e.medidas.append(f"`ARMADILHAS.md`: {n_arm} entradas")
    if not n_arm:
        e.achados.append(Achado(
            e.nome, True, "`ARMADILHAS.md` não rende título nenhum",
            "O `abertura.py` injeta esses títulos e o `CLAUDE.md` encolheu a "
            "lista dele CONTANDO com isso. Sem eles, a rede caiu.",
        ))
    return e


# --------------------------------------------------------------------------
# eixo 4 — ambiente externo


def _recomendadas() -> list[str]:
    """As extensões do `.vscode/extensions.json`, que é JSONC (tem comentário).

    O `json.loads` não come comentário e o arquivo é quase todo comentário, de
    propósito: cada extensão ali tem escrito o que quebra sem ela. Tira-se a
    linha de `//` e leem-se as strings do bloco.
    """
    return _lista_de_extensoes("recommendations")


def _lista_de_extensoes(chave: str) -> list[str]:
    bruto = _texto(RAIZ / ".vscode" / "extensions.json")
    limpo = "\n".join(ln for ln in bruto.splitlines()
                      if not ln.strip().startswith("//"))
    m = re.search(rf'"{chave}"\s*:\s*\[(.*?)\]', limpo, re.DOTALL)
    return re.findall(r'"([\w.-]+)"', m.group(1)) if m else []


def _extensao_decidida(ident: str, texto: str) -> bool:
    """A extensão aparece no `extensions.json`, na lista OU no comentário.

    O comentário "Não entram, e por quê" é decisão tanto quanto a lista: a
    extensão ali citada foi olhada e ficou de fora com motivo. Sem decisão é a
    que não aparece em lugar nenhum — foi o caso da markdownlint e da de
    contêineres, instaladas sem que o arquivo dissesse nada sobre elas.
    `publisher.*` cobre a família (`ms-dotnettools.*`).
    """
    baixo = texto.lower()
    return (ident.lower() in baixo
            or f"{ident.split('.')[0].lower()}.*" in baixo)


def eixo_externo(rede: bool) -> Eixo:
    e = Eixo("Ambiente externo")

    pasta = Path.home() / ".vscode" / "extensions"
    instaladas = _extensoes_instaladas(pasta)
    e.medidas.append(f"extensões instaladas: {len(instaladas)}")
    return _eixo_externo_resto(e, instaladas, rede)


def _extensoes_instaladas(pasta: Path) -> dict[str, str]:
    """`publisher.nome → versão` do que o VS Code de fato carrega.

    A pasta de uma extensão desinstalada, e a de cada versão substituída por
    atualização, FICA em disco até o VS Code reiniciar: ele só a anota no
    `.obsolete`. Sem ler esse arquivo, a python-envs recém-desinstalada
    (22/10/2026) continuava "instalada" no relatório, e a versão registrada
    era a da pasta que viesse por último na listagem — às vezes a velha.
    """
    obsoletas = _jsonc(pasta / ".obsolete")
    instaladas: dict[str, str] = {}
    if pasta.is_dir():
        for p in sorted(pasta.iterdir()):
            if not p.is_dir() or obsoletas.get(p.name):
                continue
            # `publisher.nome-1.2.3-win32-x64` → `publisher.nome`, `1.2.3`
            m = re.match(r"^(.+?)-(\d+\.\d+\.\d+)", p.name)
            if m:
                instaladas[m.group(1)] = m.group(2)
    return instaladas


def _eixo_externo_resto(e: Eixo, instaladas: dict[str, str], rede: bool) -> Eixo:
    rec = _recomendadas()
    ausentes = [x for x in rec if x not in instaladas]
    if ausentes:
        e.achados.append(Achado(
            e.nome, True,
            f"{len(ausentes)} extensão recomendada NÃO instalada",
            "  " + ", ".join(f"`{x}`" for x in ausentes)
            + "\n\n  Configuração de extensão ausente **não dá erro**: o VS "
              "Code ignora a chave. O ruff pararia de acender os avisos e o F5 "
              "de depurar, os dois em silêncio.",
            "code --install-extension " + " --install-extension ".join(ausentes),
        ))
    elif rec:
        e.medidas.append(f"as {len(rec)} recomendadas do projeto estão instaladas")

    texto_ext = _texto(RAIZ / ".vscode" / "extensions.json")
    sem_decisao = sorted(x for x in instaladas
                         if not _extensao_decidida(x, texto_ext))
    if sem_decisao:
        e.achados.append(Achado(
            e.nome, False,
            f"{len(sem_decisao)} extensão(ões) instalada(s) sem decisão no "
            "`extensions.json`",
            "\n".join(f"  - `{x}`" for x in sem_decisao)
            + "\n\n  Ou entra em `recommendations` (o projeto depende dela), ou "
              "no comentário \"Não entram\" com o motivo, ou em "
              "`unwantedRecommendations` (atrapalha). Instalada sem decisão é "
              "a que um dia passa a disputar uma chave já fixada.",
        ))
    indesejadas = [x for x in _lista_de_extensoes("unwantedRecommendations")
                   if x in instaladas]
    if indesejadas:
        e.achados.append(Achado(
            e.nome, False,
            "extensão marcada como indesejada está instalada",
            "\n".join(f"  - `{x}`" for x in indesejadas)
            + "\n\n  O `settings.json` a neutraliza neste projeto; se outro "
              "projeto da estação não a usa, desinstalar.",
            "code --uninstall-extension "
            + " --uninstall-extension ".join(indesejadas),
        ))

    # Diff com a última execução: extensão que some não avisa, e a que aparece
    # pode ser a que passou a disputar com uma chave já fixada.
    agora = "\n".join(f"{k}\t{v}" for k, v in sorted(instaladas.items()))
    antes = _texto(EXTENSOES_ANTES)
    if antes:
        de_antes = dict(ln.split("\t") for ln in antes.splitlines() if "\t" in ln)
        sumiram = sorted(set(de_antes) - set(instaladas))
        chegaram = sorted(set(instaladas) - set(de_antes))
        mudaram = sorted(k for k in set(de_antes) & set(instaladas)
                         if de_antes[k] != instaladas[k])
        if sumiram or chegaram:
            e.achados.append(Achado(
                e.nome, bool(sumiram),
                "a lista de extensões mudou desde a última manutenção",
                "\n".join(
                    [f"  - saiu: `{x}`" for x in sumiram]
                    + [f"  - entrou: `{x}`" for x in chegaram]
                ),
            ))
        if mudaram:
            e.medidas.append(f"{len(mudaram)} extensão(ões) atualizadas desde então")
    try:
        ESTADO.mkdir(parents=True, exist_ok=True)
        EXTENSOES_ANTES.write_text(agora, encoding="utf-8")
    except OSError:
        pass

    if "anthropic.claude-code" in instaladas:
        e.medidas.append(f"Claude Code {instaladas['anthropic.claude-code']}")
    e.medidas.append(f"Python {sys.version.split()[0]}")

    if rede:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--outdated",
                 "--format=json"],
                cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=180,
            )
            pacotes = json.loads(r.stdout or "[]")
        except Exception:
            pacotes = None
        if pacotes is None:
            e.medidas.append("pip --outdated: não respondeu (rede?)")
        elif pacotes:
            linhas = [f"  - `{p['name']}` {p['version']} → {p['latest_version']}"
                      for p in pacotes[:12]]
            e.achados.append(Achado(
                e.nome, False, f"{len(pacotes)} dependência(s) desatualizadas",
                "\n".join(linhas) + ("\n  - …" if len(pacotes) > 12 else "")
                + "\n\n  Atualizar PySide6 ou pydicom muda o que sai no papel: "
                  "subir uma delas exige gerar o caso e passar o "
                  "`tools/comparar_pdf.py`, não só a suíte.",
            ))
        else:
            e.medidas.append("dependências: todas atualizadas")
    else:
        e.medidas.append("pip --outdated: pulado (use `--rede`)")
    return e


# --------------------------------------------------------------------------
# skills e comandos de sessão


def _jsonc(caminho: Path) -> dict:
    """JSON com comentário em linha própria, que é o formato dos dois arquivos
    de decisão (`extensions.json`, `skills.jsonc`). Arquivo ilegível devolve
    vazio: o eixo então diz que a lista de decisões sumiu, em vez de cair."""
    limpo = "\n".join(ln for ln in _texto(caminho).splitlines()
                      if not ln.strip().startswith("//"))
    try:
        return json.loads(limpo) if limpo.strip() else {}
    except json.JSONDecodeError:
        return {}


def _descricao(skill_md: Path) -> str:
    """O `description:` do cabeçalho — a parte da skill que entra em todo turno.

    Aceita valor na mesma linha (com ou sem aspas) e o bloco `>`/`|` das
    linhas recuadas seguintes; o corpo da skill só entra quando ela é chamada,
    e por isso não conta.
    """
    linhas = _texto(skill_md).splitlines()
    if not linhas or linhas[0].strip() != "---":
        return ""
    for i, ln in enumerate(linhas[1:], 1):
        if ln.strip() == "---":
            break
        if ln.startswith("description:"):
            valor = ln.split(":", 1)[1].strip()
            if valor in (">", "|", ">-", "|-"):
                bloco = []
                for seg in linhas[i + 1:]:
                    if not seg.startswith((" ", "\t")):
                        break
                    bloco.append(seg.strip())
                return " ".join(bloco)
            return valor.strip("'\"")
    return ""


def _skills_em(pasta: Path) -> dict[str, str]:
    """`nome → descrição` de cada subpasta com `SKILL.md`."""
    if not pasta.is_dir():
        return {}
    return {p.name: _descricao(p / "SKILL.md")
            for p in sorted(pasta.iterdir())
            if (p / "SKILL.md").is_file()}


def _sincronizadas(casa: Path) -> dict[str, str]:
    """As que o claude.ai sincroniza (`skills/synced/<conta>/<nome>/`). São
    chamadas como `anthropic-skills:<nome>`, e é assim que entram aqui."""
    raiz = casa / ".claude" / "skills" / "synced"
    achadas: dict[str, str] = {}
    if raiz.is_dir():
        for conta in raiz.iterdir():
            if conta.is_dir() and not conta.name.startswith("."):
                for nome, desc in _skills_em(conta).items():
                    achadas[f"anthropic-skills:{nome}"] = desc
    return achadas


# Orçamento do que as skills custam em TODO turno, em caracteres de descrição
# (~4 por token). Medido em 22/10/2026, depois de desligar o BMad de
# execução: 19.001 caracteres (~4,7 mil tokens). O teto dá uns 25% de folga;
# passar dele é sinal de que chegou skill nova sem ninguém decidir se ela
# serve a este projeto.
TETO_DESCRICOES = 24_000


def eixo_skills(casa: Path | None = None) -> Eixo:
    e = Eixo("Skills e comandos")
    casa = casa or Path.home()
    decisao = _jsonc(RAIZ / "tools" / "skills.jsonc")
    if not decisao:
        e.achados.append(Achado(
            e.nome, True, "`tools/skills.jsonc` ausente ou ilegível",
            "  Sem a lista de decisões, este eixo não tem com o que comparar.",
        ))
        return e
    usadas = set(decisao.get("usadas", []))
    desligadas = set(decisao.get("desligadas", []))
    bloqueadas = decisao.get("bloqueadas", [])

    de_usuario = _skills_em(casa / ".claude" / "skills")
    de_usuario.pop("synced", None)
    do_projeto = _skills_em(RAIZ / ".claude" / "skills")
    sincronizadas = _sincronizadas(casa)
    comandos = sorted(p.stem for p in (RAIZ / ".claude" / "commands").glob("*.md"))

    custo = sum(len(d) for d in (*de_usuario.values(), *do_projeto.values(),
                                 *sincronizadas.values()))
    e.medidas.append(
        f"skills: {len(de_usuario)} de usuário, {len(do_projeto)} do projeto, "
        f"{len(sincronizadas)} sincronizadas do claude.ai; "
        f"{len(comandos)} comandos de sessão")
    e.medidas.append(f"descrições: {custo:,} caracteres (~{custo // 4:,} "
                     "tokens) em todo turno".replace(",", "."))
    if custo > TETO_DESCRICOES:
        e.achados.append(Achado(
            e.nome, False,
            f"descrições de skill passaram do orçamento ({custo:,} > "
            f"{TETO_DESCRICOES:,} caracteres)".replace(",", "."),
            "  Cada uma entra em todo turno. Ver quais chegaram desde a última "
            "execução e decidir no `tools/skills.jsonc`.",
        ))

    voltaram = sorted(desligadas & set(de_usuario))
    if voltaram:
        e.achados.append(Achado(
            e.nome, True,
            "skill DESLIGADA voltou para `~/.claude/skills`",
            "\n".join(f"  - `{x}`" for x in voltaram)
            + "\n\n  Atualização do BMad reinstala o pacote inteiro. A "
              "`bmad-build` volta a se oferecer em todo pedido de mudança.",
            "\n".join(
                f'Move-Item "$env:USERPROFILE\\.claude\\skills\\{x}" '
                f'"$env:USERPROFILE\\.claude\\skills-desligadas\\{x}-novo"'
                for x in voltaram),
        ))

    sem_decisao = sorted(set(de_usuario) - usadas - desligadas)
    if sem_decisao:
        e.achados.append(Achado(
            e.nome, False,
            f"{len(sem_decisao)} skill(s) de usuário sem decisão no "
            "`tools/skills.jsonc`",
            "\n".join(f"  - `{x}`: {de_usuario[x][:110]}" for x in sem_decisao)
            + "\n\n  Ler a descrição: se ela dispara num pedido que aqui tem "
              "caminho próprio (mudança de código, tela, commit), é "
              "`desligadas`; senão, `usadas`.",
        ))

    negadas = (_jsonc(RAIZ / ".claude" / "settings.json")
               .get("permissions", {}).get("deny", []))
    sem_negacao = [x for x in bloqueadas if f"Skill({x})" not in negadas]
    if sem_negacao:
        e.achados.append(Achado(
            e.nome, True,
            "skill bloqueada sem a negação no `.claude/settings.json`",
            "\n".join(f"  - `{x}`" for x in sem_negacao)
            + "\n\n  Sincronizada do claude.ai: apagar a pasta não adianta, a "
              "sincronização a traz de volta. Acrescentar em "
              "`permissions.deny`: " + ", ".join(f'`"Skill({x})"`'
                                                 for x in sem_negacao),
        ))

    existentes = set(de_usuario) | set(do_projeto)
    faltam = [x for x in decisao.get("obrigatorias", []) if x not in existentes]
    if faltam:
        e.achados.append(Achado(
            e.nome, True, "skill citada no `CLAUDE.md` não está instalada",
            "\n".join(f"  - `{x}`" for x in faltam)
            + "\n\n  A instrução continua mandando carregá-la, e nada carrega.",
        ))

    # Comando de sessão que o `AMBIENTE.md` não lista é comando que só quem o
    # escreveu sabe que existe — e a sessão nova não o oferece a ninguém.
    ambiente = _texto(RAIZ / "docs" / "AMBIENTE.md")
    sem_doc = [c for c in comandos if f"/{c}`" not in ambiente
               and f"/{c} " not in ambiente]
    if sem_doc:
        e.achados.append(Achado(
            e.nome, False, "comando de sessão sem linha no `docs/AMBIENTE.md`",
            "\n".join(f"  - `/{c}`" for c in sem_doc),
        ))

    # Diff com a última execução, como o das extensões: skill sincronizada
    # chega do claude.ai sem pedir licença, e é por aqui que se vê.
    todas = {**de_usuario, **{f"projeto:{k}": v for k, v in do_projeto.items()},
             **sincronizadas}
    antes = _texto(SKILLS_ANTES)
    if antes:
        de_antes = set(antes.splitlines())
        chegaram = sorted(set(todas) - de_antes)
        sumiram = sorted(de_antes - set(todas))
        if chegaram or sumiram:
            e.achados.append(Achado(
                e.nome, False,
                "a lista de skills mudou desde a última manutenção",
                "\n".join([f"  - entrou: `{x}`: {todas[x][:110]}"
                           for x in chegaram]
                          + [f"  - saiu: `{x}`" for x in sumiram]),
            ))
    try:
        ESTADO.mkdir(parents=True, exist_ok=True)
        SKILLS_ANTES.write_text("\n".join(sorted(todas)), encoding="utf-8")
    except OSError:
        pass
    return e


# --------------------------------------------------------------------------
# relatório


def _limpar_ctx() -> int:
    """Única ação destrutiva, e só sob flag explícita: os `ctx_*.txt` velhos."""
    n = 0
    for p in ESTADO.glob("ctx_*.txt"):
        if _dias(p.stat().st_mtime) >= DIAS_CTX_ORFAO:
            try:
                p.unlink()
                n += 1
            except OSError:
                pass
    print(f"{n} arquivo(s) `ctx_*.txt` de sessão morta removido(s).")
    return 0


def _marcar(graves: int, brandos: int) -> None:
    try:
        ESTADO.mkdir(parents=True, exist_ok=True)
        with MARCA.open("a", encoding="utf-8") as fh:
            fh.write(f"{date.today().isoformat()}\t{graves}\t{brandos}\n")
    except OSError:
        pass  # a série é útil, não ao preço de derrubar o relatório


def travar() -> int | None:
    """O descritor com a trava, ou ``None`` se outra manutenção já a tem."""
    ESTADO.mkdir(parents=True, exist_ok=True)
    fd = os.open(TRAVA, os.O_RDWR | os.O_CREAT)
    try:
        if os.name == "nt":
            import msvcrt  # noqa: PLC0415
            os.lseek(fd, BYTE_DA_TRAVA, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl  # noqa: PLC0415
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    # Quem tem a trava e desde quando: é o que se lê para achar uma
    # manutenção presa (o abertura.py avisa quando ela passa de 30 min).
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, f"{os.getpid()}\t{datetime.now().isoformat(timespec='seconds')}\n"
             .encode("utf-8"))
    return fd


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--eixo", action="append",
                   choices=["armazenamento", "claude", "notas", "externo",
                            "skills"],
                   help="roda só este eixo (repetível); o padrão são os cinco")
    p.add_argument("--rede", action="store_true",
                   help="inclui pip list --outdated (lento, precisa de rede)")
    p.add_argument("--limpar-ctx", action="store_true",
                   help="apaga os ctx_*.txt de sessão morta e sai")
    p.add_argument("--relatorio", type=Path,
                   help="grava o relatório neste arquivo ao TERMINAR (é como "
                        "o abertura.py a roda em segundo plano)")
    args = p.parse_args()

    if args.limpar_ctx:
        return _limpar_ctx()

    trava = travar()
    if trava is None:
        # Sair calado e com sucesso: quem chegou aqui é a recursão ou uma
        # segunda sessão, e a manutenção que interessa já está rodando.
        print("Outra manutenção já está rodando; esta não roda.")
        return 0
    if args.relatorio:
        # Inteiro ou nada: escrito aos poucos, o abertura.py podia anunciar
        # a metade de um relatório ainda em andamento.
        import contextlib  # noqa: PLC0415
        import io  # noqa: PLC0415
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            codigo = _rodar(args)
        provisorio = args.relatorio.with_suffix(".parcial")
        provisorio.write_text(buffer.getvalue(), encoding="utf-8")
        os.replace(provisorio, args.relatorio)
        return codigo
    return _rodar(args)


def _rodar(args) -> int:

    pedidos = args.eixo or ["armazenamento", "claude", "notas", "externo",
                            "skills"]
    eixos = []
    if "armazenamento" in pedidos:
        eixos.append(eixo_armazenamento())
    if "claude" in pedidos:
        eixos.append(eixo_claude())
    if "notas" in pedidos:
        eixos.append(eixo_notas())
    if "externo" in pedidos:
        eixos.append(eixo_externo(args.rede))
    if "skills" in pedidos:
        eixos.append(eixo_skills())

    graves = sum(1 for e in eixos for a in e.achados if a.grave)
    brandos = sum(1 for e in eixos for a in e.achados if not a.grave)

    print(f"# Manutenção do ambiente — {date.today().strftime('%d/%m/%Y')}\n")
    ultima = _texto(MARCA).splitlines()
    if ultima:
        print(f"_Última execução: {ultima[-1].split(chr(9))[0]}._\n")
    print(f"**{graves} para decidir agora, {brandos} para saber.** "
          "Nada foi apagado.\n")

    for e in eixos:
        print(f"## {e.nome}\n")
        for m in e.medidas:
            print(f"- {m}")
        if e.medidas:
            print()
        if not e.achados:
            print("Nada a decidir.\n")
            continue
        for a in e.achados:
            print(f"**{'!' if a.grave else '·'} {a.titulo}**\n")
            if a.detalhe:
                print(f"{a.detalhe}\n")
            if a.comando:
                print(f"```\n{a.comando}\n```\n")

    _marcar(graves, brandos)
    # Sempre 0: isto é um relatório, não um portão. Fazer a manutenção reprovar
    # a sessão transformaria o aviso em obstáculo, e obstáculo se contorna.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
