"""Desce do `NOTAS.md` as seções que já não são o que está em andamento.

O `NOTAS.md` promete caber numa leitura (~400 linhas). A regra de manter isso
existia desde 08/09/2026 — "a seção que deixa de estar em andamento desce para
o `notas/AAAA-MM.md` do mês dela" —, mas dependia de alguém fazer, e o aviso da
abertura repetiu todo dia, de 15/10 a 22/10/2026, que o arquivo tinha 1.900
linhas. Aviso que depende de alguém agir não é regra. Esta ferramenta é a regra
em forma de código: a abertura (`.claude/hooks/abertura.py`) e o `/fechar` a
chamam sozinhos.

O que desce, nesta ordem:

1. toda seção cuja data (a última `dd/mm/aaaa` do título) tem mais de
   `--dias` dias;
2. se o arquivo ainda passa de `--alvo` linhas, as mais antigas que sobraram.

A **primeira** seção nunca desce (é o checkpoint vivo, por construção), e
seção sem data no título fica — não se adivinha o mês de quem não diz.

Descer é **mover, não resumir**: o bloco vai byte a byte para o topo do
`notas/AAAA-MM.md` (criado se não existir), ganha uma linha no índice e, se o
título se declara aberto (EM ANDAMENTO, EM ABERTO, ESTACIONADA...), também uma
linha em "O que está aberto" — sair da frente não pode ser sumir.

    python tools/notas.py descer            # aplica e relata
    python tools/notas.py descer --simular  # só relata
"""

from __future__ import annotations

import argparse
import re
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

ALVO = 400
DIAS = 14

ABERTO = re.compile(r"EM ANDAMENTO|EM ABERTO|ESTACIONAD|PENDENTE|BLOQUEAD", re.I)
DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

MARCA_ABERTO = "## O que está aberto"
MARCA_INDICE = "## Índice do que já foi"


def _data_do_titulo(titulo: str) -> date | None:
    achadas = DATA.findall(titulo)
    if not achadas:
        return None
    d, m, a = achadas[-1]
    try:
        return date(int(a), int(m), int(d))
    except ValueError:
        return None


def _titulo_curto(titulo: str) -> str:
    """O título sem a data do fim, que no índice já vai na frente."""
    return re.sub(r"\s*[—,-]\s*\d{2}/\d{2}/\d{4}\s*$", "", titulo).strip()


def _secoes(texto: str) -> tuple[str, list[str], str]:
    """(cabeçalho, seções vivas, resto a partir de "O que está aberto")."""
    fim = texto.index("\n" + MARCA_ABERTO) + 1
    corpo, resto = texto[:fim], texto[fim:]
    partes = re.split(r"(?m)^(?=## )", corpo)
    return partes[0], partes[1:], resto


def _cabecalho_do_mes(d: date) -> str:
    return (
        f"# Notas de trabalho — {MESES[d.month - 1]} de {d.year}\n\n"
        "História **congelada**: as seções que saíram do `NOTAS.md` quando\n"
        "deixaram de ser o que está em andamento. Nada foi resumido — o texto é o\n"
        "mesmo, byte a byte. O índice de tudo está no `NOTAS.md`, que é o arquivo\n"
        "que se lê. Quem desce as seções é o `tools/notas.py`.\n\n---\n\n"
    )


def _arquivar(raiz: Path, mes: date, blocos: list[str]) -> None:
    """Põe os blocos no topo do `notas/AAAA-MM.md`, na ordem em que vieram."""
    caminho = raiz / "notas" / f"{mes:%Y-%m}.md"
    if caminho.exists():
        atual = caminho.read_bytes().decode("utf-8")
    else:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        atual = _cabecalho_do_mes(mes)
    nl = "\r\n" if "\r\n" in atual else "\n"
    sep = f"{nl}---{nl}{nl}"
    k = atual.index(sep) + len(sep)
    novo = "".join(b if b.endswith("\n\n") else b.rstrip("\n") + "\n\n" for b in blocos)
    novo = novo.replace("\r\n", "\n").replace("\n", nl)
    caminho.write_bytes((atual[:k] + novo + atual[k:]).encode("utf-8"))


def _indexar(resto: str, por_mes: dict[date, list[tuple[date, str]]]) -> str:
    """Linhas novas no índice (mês mais novo primeiro) e o total atualizado."""
    for mes in sorted(por_mes, reverse=True):
        itens = por_mes[mes]
        linhas = "".join(f"- {d:%d/%m} — [{t}](notas/{mes:%Y-%m}.md)\n" for d, t in itens)
        rotulo = f"### `notas/{mes:%Y-%m}.md` — {MESES[mes.month - 1]}"
        m = re.search(re.escape(rotulo) + r" \((\d+) seções\)\n\n", resto)
        if m:
            n = int(m.group(1)) + len(itens)
            cab = f"{rotulo} ({n} seções)\n\n"
            resto = resto[:m.start()] + cab + linhas + resto[m.end():]
            continue
        cab = f"{rotulo} ({len(itens)} seções)\n\n{linhas}\n"
        # o mês novo entra antes do primeiro mês mais antigo que ele
        antes = None
        for mm in re.finditer(r"(?m)^### `notas/(\d{4})-(\d{2})\.md`", resto):
            if date(int(mm.group(1)), int(mm.group(2)), 1) < mes:
                antes = mm.start()
                break
        if antes is None:
            resto = resto.rstrip("\n") + "\n\n" + cab
        else:
            resto = resto[:antes] + cab + resto[antes:]
    total = sum(len(v) for v in por_mes.values())
    return re.sub(r"(?m)^(## Índice do que já foi \()(\d+)( seções\))",
                  lambda m: f"{m.group(1)}{int(m.group(2)) + total}{m.group(3)}", resto, count=1)


def _marcar_abertos(resto: str, abertos: list[tuple[date, str]], hoje: date) -> str:
    if not abertos:
        return resto
    linhas = "".join(
        f"- {d:%d/%m} — [{t}](notas/{d:%Y-%m}.md) — desceu sozinha em "
        f"{hoje:%d/%m/%Y}; conferir se ainda está aberta\n" for d, t in abertos)
    fim_secao = resto.find("\n## ", len(MARCA_ABERTO))
    m = re.search(r"(?m)^- ", resto[:fim_secao if fim_secao > 0 else len(resto)])
    if m:
        return resto[:m.start()] + linhas + resto[m.start():]
    k = resto.index("\n\n", resto.index(MARCA_ABERTO)) + 2
    return resto[:k] + linhas + "\n" + resto[k:]


def descer(raiz: Path = RAIZ, alvo: int = ALVO, dias: int = DIAS,
           hoje: date | None = None, simular: bool = False) -> list[str]:
    """Desce o que deve descer; devolve uma linha por seção movida."""
    hoje = hoje or date.today()
    notas = raiz / "NOTAS.md"
    bruto = notas.read_bytes().decode("utf-8")
    # o git guarda LF, mas a cópia de trabalho no Windows pode vir em CRLF:
    # trabalhar em LF e devolver no formato em que o arquivo estava
    nl = "\r\n" if "\r\n" in bruto else "\n"
    texto = bruto.replace("\r\n", "\n")
    cab, secoes, resto = _secoes(texto)

    datas = [_data_do_titulo(s.split("\n", 1)[0]) for s in secoes]
    limite = hoje - timedelta(days=dias)
    sai = {i for i in range(1, len(secoes)) if datas[i] and datas[i] < limite}

    def linhas_restantes() -> int:
        return (cab + "".join(s for i, s in enumerate(secoes) if i not in sai)
                + resto).count("\n")

    candidatas = sorted((i for i in range(1, len(secoes)) if datas[i] and i not in sai),
                        key=lambda i: (datas[i], -i))
    while linhas_restantes() > alvo and candidatas:
        sai.add(candidatas.pop(0))

    if not sai:
        return []

    por_mes: dict[date, list[tuple[date, str]]] = {}
    blocos_mes: dict[date, list[str]] = {}
    abertos: list[tuple[date, str]] = []
    relato = []
    for i in sorted(sai):                      # ordem do arquivo: mais nova primeiro
        titulo = secoes[i].split("\n", 1)[0][3:].strip()
        d = datas[i]
        mes = date(d.year, d.month, 1)
        curto = _titulo_curto(titulo)
        por_mes.setdefault(mes, []).append((d, curto))
        blocos_mes.setdefault(mes, []).append(secoes[i])
        if ABERTO.search(titulo):
            abertos.append((d, curto))
        relato.append(f"{d:%d/%m} {curto} → notas/{mes:%Y-%m}.md")

    if simular:
        return relato

    for mes, blocos in blocos_mes.items():
        _arquivar(raiz, mes, blocos)
    resto = _indexar(resto, por_mes)
    resto = _marcar_abertos(resto, abertos, hoje)
    novo = cab + "".join(s for i, s in enumerate(secoes) if i not in sai) + resto
    notas.write_bytes(novo.replace("\n", nl).encode("utf-8"))
    return relato


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("descer", help="desce as seções vencidas para notas/AAAA-MM.md")
    d.add_argument("--alvo", type=int, default=ALVO)
    d.add_argument("--dias", type=int, default=DIAS)
    d.add_argument("--simular", action="store_true")
    a = p.parse_args()
    relato = descer(alvo=a.alvo, dias=a.dias, simular=a.simular)
    verbo = "desceriam" if a.simular else "desceram"
    if not relato:
        print("nada a descer")
        return 0
    print(f"{len(relato)} seção(ões) {verbo}:")
    for ln in relato:
        print(f"  {ln}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
