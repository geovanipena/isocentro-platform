# -*- coding: utf-8 -*-
"""Raio de revisão de uma mudança, lido do diff (AD-39 da espinha).

Para cada arquivo que o git vê diferente, diz o **módulo dono** e o **raio**:

    o módulo                        arquivo interno de um módulo
    o módulo e os consumidores      fachada ``consulta.py`` ou manifesto
    tudo (a suíte inteira)          ``rt``, ``nucleo``, adaptador, migração SQL,
                                    dependência fixada, tabela de máquina e
                                    qualquer arquivo sem dono

O raio **só soma, nunca corta** (AD-39(2)): quando um arquivo cabe em duas
regras, vale a maior; quando não cabe em nenhuma, vale "tudo". O papel impresso
é dimensão À PARTE — o que alcança ``papel/`` acrescenta "comparar PDF e
avisar", qualquer que seja o raio —, porque o caminho até o paciente nem sempre
é um import: uma mudança "local" num módulo que a ficha consome muda o papel
sem que a ficha mude uma linha.

Enquanto os pacotes de hoje (``banco/``, ``dados/``, ``dicom/``, ``dominio/``,
``papel/``) existirem, o dono sai da **tabela de destino da semente**: ``papel/``
é do Radioteraficha, ``paralelo``/``qualidade`` são do Plano, ``dicom/`` vai
para ``rt`` (e portanto vale tudo), a equipe e ``constantes`` são do núcleo
(AD-26). O que a semente ainda não decidiu (a Q6) não tem dono, e arquivo sem
dono é "tudo" — é isso que impede o raio de encolher por omissão.

Rodar:
    python tools/raio.py                 # árvore + índice contra HEAD
    python tools/raio.py origin/main     # tudo o que mudou desde a ref

O ``tools/testar.py --raio [ref]`` usa este raio como recorte durante o
trabalho. Recorte não é suíte: o fechamento continua sendo a suíte inteira.
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parent.parent

NENHUM, MODULO, CONSUMIDORES, TUDO = 0, 1, 2, 3
NOME_DO_NIVEL = {
    NENHUM: "nenhum (fora do executável)",
    MODULO: "o módulo",
    CONSUMIDORES: "o módulo e os consumidores da fachada",
    TUDO: "tudo (a suíte inteira)",
}

# Tabela de destino da semente (ARCHITECTURE-SPINE.md, "Semente estrutural").
# Só o que ela JÁ decidiu; o resto dos pacotes atuais está na Q6 e cai em
# "sem dono". O ``dicom/`` inteiro vale ``rt``: a semente o DIVIDE entre rt,
# adaptador, desenho e Radioteraficha, e enquanto ele não é dividido, o pedaço
# mais largo (rt → tudo) é o que vale para o arquivo todo.
_DESTINO_ARQUIVO = {
    "isocentro/dominio/paralelo.py": ("plano", MODULO),
    "isocentro/dominio/qualidade.py": ("plano", MODULO),
    "isocentro/dominio/qualidade_metodo.py": ("plano", MODULO),
    # Listas de equipe e ``identificar_maquina``: dono do AD-26, o núcleo.
    "isocentro/dados/equipe.py": ("nucleo", TUDO),
    "isocentro/dominio/constantes.py": ("nucleo", TUDO),
}
_DESTINO_PASTA = {
    "isocentro/papel/": ("radioteraficha", MODULO),
    "isocentro/dicom/": ("rt", TUDO),
}

# Tabela de TMR/Scp: ``<MAQUINA>__<ENERGIA>MV__<TMR|SCP>.csv``
# (``paralelo.caminho_tabela``). Ela não mora no repositório hoje, mas se um
# dia entrar, é a curva de UMA máquina, e o 2º cálculo de todo plano dela muda.
_TABELA_DE_MAQUINA = re.compile(r"__[\d.,]+MV__(TMR|SCP)\.csv$", re.IGNORECASE)
_DEPENDENCIA = re.compile(
    r"^(requirements[^/]*\.txt|constraints[^/]*\.txt|pyproject\.toml|"
    r"setup\.cfg|setup\.py|[^/]+\.spec)$", re.IGNORECASE)


@dataclass(frozen=True)
class Item:
    """O raio de UM arquivo do diff."""
    arquivo: str
    dono: str
    nivel: int
    motivo: str
    papel: bool = False
    consumidores: tuple[str, ...] = field(default_factory=tuple)


def classificar_caminho(rel: str) -> tuple[str, int, str]:
    """``(dono, nível, motivo)`` só pelo caminho, sem olhar o conteúdo.

    A ordem importa: as regras de "tudo" vêm antes das de módulo, porque uma
    tabela de máquina dentro de ``modulos/plano/`` continua sendo tabela de
    máquina — e o raio só soma.
    """
    p = PurePosixPath(rel)
    rel = p.as_posix()
    nome = p.name

    if _TABELA_DE_MAQUINA.search(nome) or "dados_feixe" in p.parts:
        return "tabela de máquina", TUDO, "tabela de máquina (TMR/Scp)"
    if p.suffix.lower() == ".sql" or (p.parts and p.parts[0] == "migracoes"):
        return "migração", TUDO, "migração SQL"
    if len(p.parts) == 1 and _DEPENDENCIA.match(nome):
        return "dependência", TUDO, "dependência fixada ou empacotamento"

    partes = p.parts
    if len(partes) >= 2 and partes[0] == "isocentro":
        segundo = partes[1]
        if segundo in ("nucleo", "rt", "adaptadores"):
            return segundo, TUDO, f"`{segundo}/` vale a suíte inteira"
        if rel in ("isocentro/composicao.py",
                   "isocentro/interface/composicao.py"):
            return "composição", TUDO, "raiz de composição (o que vai no executável)"
        if segundo == "modulos" and len(partes) >= 4:
            m = partes[2]
            if partes[3] in ("consulta.py", "__init__.py") and len(partes) == 4:
                return m, CONSUMIDORES, "fachada ou manifesto do módulo"
            return m, MODULO, "arquivo interno do módulo"
        if (segundo == "interface" and len(partes) >= 5
                and partes[2] == "modulos"):
            # A tela herda o raio do módulo pelo nome (revisão clínica do
            # Update de 22/10, item 10): a tela de SSD mostra o que vai à ficha.
            return partes[3], MODULO, "tela do módulo"
        if rel in _DESTINO_ARQUIVO:
            dono, nivel = _DESTINO_ARQUIVO[rel]
            return dono, nivel, "tabela de destino da semente"
        for pasta, (dono, nivel) in _DESTINO_PASTA.items():
            if rel.startswith(pasta):
                return dono, nivel, "tabela de destino da semente"
        return "sem dono", TUDO, "pacote atual sem destino decidido (Q6)"

    if partes and partes[0] == "tests":
        if len(partes) == 2 and nome.startswith("test_") and nome.endswith(".py"):
            return rel, MODULO, "teste: roda a si mesmo"
        return "infraestrutura de teste", TUDO, "infraestrutura de teste afeta todos"
    if (len(partes) == 2 and partes[0] == "tools" and p.suffix == ".py"
            and nome != "gerar_executavel.py"):
        return rel, MODULO, "ferramenta, fora do executável"
    if partes[:2] == ("docs", "qms"):
        # O `classificacao-62304.md` é a FONTE da classe de cada módulo
        # (AD-39(1)): rebaixar uma classe ali é a mudança que o AD-39 existe
        # para não deixar passar barato, mesmo sendo "só um .md".
        return "qms", TUDO, "documento do QMS (classe e riscos)"
    if p.suffix.lower() == ".md" and partes[0] not in ("isocentro", "assets"):
        return "documentação", NENHUM, "documento, fora do executável"
    return "sem dono", TUDO, "arquivo sem dono"


# --- grafo de imports -------------------------------------------------------

def _nome_do_modulo(rel: PurePosixPath) -> str:
    partes = list(rel.with_suffix("").parts)
    if partes[-1] == "__init__":
        partes.pop()
    return ".".join(partes)


@dataclass
class Grafo:
    """Quem importa quem dentro de ``isocentro/``, por ``ast``."""
    caminho: dict[str, str]           # nome pontuado → caminho relativo
    importa: dict[str, set[str]]      # nome → nomes que ele importa
    importado_por: dict[str, set[str]]

    def nome(self, rel: str) -> str | None:
        n = _nome_do_modulo(PurePosixPath(rel))
        return n if n in self.caminho else None


def montar_grafo(raiz: Path = RAIZ) -> Grafo:
    caminho: dict[str, str] = {}
    pacote = raiz / "isocentro"
    arquivos = sorted(pacote.rglob("*.py")) if pacote.is_dir() else []
    for arq in arquivos:
        rel = PurePosixPath(arq.relative_to(raiz).as_posix())
        caminho[_nome_do_modulo(rel)] = rel.as_posix()

    importa: dict[str, set[str]] = {n: set() for n in caminho}
    for n, rel in caminho.items():
        try:
            arvore = ast.parse((raiz / rel).read_text(encoding="utf-8-sig",
                                                      errors="replace"))
        except (SyntaxError, ValueError):
            # Arquivo quebrado no meio da edição: sem arestas ele não alcança
            # o papel por import — mas o caminho dele ainda é classificado.
            continue
        e_pacote = rel.endswith("__init__.py")
        base_rel = n if e_pacote else n.rpartition(".")[0]
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                for a in no.names:
                    alvo = _mais_longo(a.name, caminho)
                    if alvo:
                        importa[n].add(alvo)
            elif isinstance(no, ast.ImportFrom):
                if no.level:
                    partes = base_rel.split(".") if base_rel else []
                    partes = partes[:len(partes) - (no.level - 1)] if no.level > 1 else partes
                    base = ".".join(partes + ([no.module] if no.module else []))
                else:
                    base = no.module or ""
                for a in no.names:
                    cand = f"{base}.{a.name}" if base else a.name
                    if cand in caminho:
                        importa[n].add(cand)
                    else:
                        alvo = _mais_longo(base, caminho)
                        if alvo:
                            importa[n].add(alvo)
        importa[n].discard(n)

    importado_por: dict[str, set[str]] = {n: set() for n in caminho}
    for n, alvos in importa.items():
        for a in alvos:
            importado_por[a].add(n)
    return Grafo(caminho, importa, importado_por)


def _mais_longo(nome: str, conhecidos) -> str | None:
    """O prefixo pontuado mais longo de ``nome`` que é um módulo conhecido."""
    partes = nome.split(".")
    for i in range(len(partes), 0, -1):
        cand = ".".join(partes[:i])
        if cand in conhecidos:
            return cand
    return None


def _fecho(inicio: set[str], arestas: dict[str, set[str]]) -> set[str]:
    visto = set(inicio)
    pilha = list(inicio)
    while pilha:
        for v in arestas.get(pilha.pop(), ()):
            if v not in visto:
                visto.add(v)
                pilha.append(v)
    return visto


def alcanca_papel(grafo: Grafo) -> set[str]:
    """Os caminhos que têm caminho de import até ``papel/``, nos DOIS sentidos.

    O que o papel importa muda o que ele imprime (o ``dicom_rt`` dá o SSD da
    ficha); quem importa o papel monta o que ele recebe (a tela de edição
    passa os valores). Os dois chegam ao paciente; conferir o PDF é barato e
    não conferir é o número errado na mesa.
    """
    papel = {n for n in grafo.caminho if n == "isocentro.papel"
             or n.startswith("isocentro.papel.")}
    nomes = _fecho(papel, grafo.importa) | _fecho(papel, grafo.importado_por)
    return {grafo.caminho[n] for n in nomes}


# --- o raio -----------------------------------------------------------------

def avaliar(arquivos: list[str], grafo: Grafo) -> list[Item]:
    papel = alcanca_papel(grafo)
    itens = []
    for rel in arquivos:
        rel = PurePosixPath(rel.replace("\\", "/")).as_posix()
        dono, nivel, motivo = classificar_caminho(rel)
        p = PurePosixPath(rel)
        toca_papel = (rel in papel or rel.startswith("isocentro/papel/")
                      or (p.parts[0] == "assets" if p.parts else False))
        consumidores: tuple[str, ...] = ()
        if nivel == CONSUMIDORES:
            consumidores = tuple(sorted(_consumidores(dono, grafo)))
        itens.append(Item(rel, dono, nivel, motivo, toca_papel, consumidores))
    return itens


def _consumidores(modulo: str, grafo: Grafo) -> set[str]:
    """Arquivos de OUTRO dono que importam qualquer coisa do módulo.

    Quem reage às verificações dele pelo motor (AD-3(3), AD-31) também é
    consumidor, mas o catálogo ainda não existe: a saída diz isso em vez de
    fingir que a lista está completa.
    """
    do_modulo = {n for n, rel in grafo.caminho.items()
                 if classificar_caminho(rel)[0] == modulo}
    fora = set()
    for n in do_modulo:
        for quem in grafo.importado_por.get(n, ()):
            rel = grafo.caminho[quem]
            if classificar_caminho(rel)[0] != modulo:
                fora.add(rel)
    return fora


def nivel_total(itens: list[Item]) -> int:
    return max((i.nivel for i in itens), default=NENHUM)


def recorte(itens: list[Item], raiz: Path = RAIZ) -> list[str] | None:
    """Arquivos ``.py`` cujo teste cobre o raio; ``None`` = a suíte inteira.

    É o que o ``testar.py --raio`` entrega ao recorte por import dele: o
    módulo INTEIRO do dono, não só o arquivo mexido — a função de outro
    arquivo do mesmo módulo que lê o valor mudado é exatamente o vizinho que
    o recorte por arquivo deixaria de fora.
    """
    if any(i.nivel == TUDO for i in itens):
        return None
    candidatos = _arquivos_com_dono(raiz)
    textos_de_teste: dict[str, str] | None = None
    escolhidos: set[str] = set()
    for i in itens:
        if i.nivel == NENHUM:
            if textos_de_teste is None:
                textos_de_teste = _textos_de_teste(raiz)
            nome = PurePosixPath(i.arquivo).name
            escolhidos |= {t for t, texto in textos_de_teste.items() if nome in texto}
            continue
        # Apagado (ou o lado velho de um renome) não entra: não há o que
        # importar, e um teste apagado no recorte vira ModuleNotFoundError.
        # Os vizinhos do mesmo dono continuam entrando logo abaixo.
        if (raiz / i.arquivo).is_file():
            escolhidos.add(i.arquivo)
        escolhidos |= {rel for rel, d in candidatos.items() if d == i.dono}
        for c in i.consumidores:
            escolhidos.add(c)
            dono_c, nivel_c, _ = classificar_caminho(c)
            if nivel_c < TUDO:
                escolhidos |= {rel for rel, d in candidatos.items() if d == dono_c}
    return sorted(e for e in escolhidos if e.endswith(".py"))


def _arquivos_com_dono(raiz: Path) -> dict[str, str]:
    saida = {}
    for pasta, padrao in (("isocentro", "**/*.py"), ("tools", "*.py")):
        base = raiz / pasta
        if base.is_dir():
            for arq in base.glob(padrao):
                rel = arq.relative_to(raiz).as_posix()
                saida[rel] = classificar_caminho(rel)[0]
    return saida


def _textos_de_teste(raiz: Path) -> dict[str, str]:
    """Documento não entra no executável, mas há teste que o LÊ (o orçamento
    do CLAUDE.md, as notas, o DESTINO do robô): os que o citam pelo nome
    rodam. Lidos uma vez só, por mais documentos que o diff tenha."""
    return {arq.relative_to(raiz).as_posix():
            arq.read_text(encoding="utf-8", errors="replace")
            for arq in sorted((raiz / "tests").glob("test_*.py"))}


# --- git e saída ------------------------------------------------------------

def arquivos_do_diff(ref: str = "HEAD", raiz: Path = RAIZ) -> list[str]:
    """O que mudou da ``ref`` até a árvore, mais os arquivos novos não
    adicionados.

    ``--no-renames``: um arquivo renomeado aparece como o velho apagado e o
    novo criado. Com a detecção de renome, só o novo aparece, e o dono do
    velho — que pode ser outro módulo — sumiria do raio.
    """
    def git(*args):
        r = subprocess.run(["git", *args], cwd=raiz, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise SystemExit(f"git {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout.splitlines()

    nomes = git("-c", "core.quotepath=false", "diff", "--name-only",
                "--no-renames", ref, "--")
    nomes += git("-c", "core.quotepath=false", "ls-files", "--others",
                 "--exclude-standard")
    return sorted({n.strip() for n in nomes if n.strip()})


def relatorio(itens: list[Item], ref: str) -> str:
    linhas = [f"Raio de revisão contra {ref} ({len(itens)} arquivo(s)):", ""]
    for i in itens:
        linhas.append(f"  {i.arquivo}")
        extra = " · papel: comparar PDF e avisar" if i.papel else ""
        linhas.append(f"      dono: {i.dono} · raio: {NOME_DO_NIVEL[i.nivel]}{extra}")
        linhas.append(f"      ({i.motivo})")
        if i.nivel == CONSUMIDORES:
            if i.consumidores:
                linhas.append("      consumidores: " + ", ".join(i.consumidores))
            linhas.append("      + quem reage às verificações dele pelo motor "
                          "(AD-3(3)): o catálogo ainda não existe, conferir à mão")
    total = nivel_total(itens)
    linhas.append("")
    if total == TUDO:
        por = sorted({i.arquivo for i in itens if i.nivel == TUDO})
        mostra = ", ".join(por[:5]) + (f" e mais {len(por) - 5}" if len(por) > 5 else "")
        linhas.append(f"Raio total: {NOME_DO_NIVEL[TUDO]} — por {mostra}")
    else:
        donos = sorted({i.dono for i in itens if i.nivel > NENHUM})
        linhas.append(f"Raio total: {NOME_DO_NIVEL[total]}"
                      + (f" — {', '.join(donos)}" if donos else ""))
    if any(i.papel for i in itens):
        linhas.append("Papel: a mudança alcança o papel impresso — gerar as "
                      "fichas (tools/caso.py), medir com tools/comparar_pdf.py "
                      "e AVISAR o usuário do que muda.")
    linhas.append("O fechamento é sempre a suíte inteira; o raio diz o que "
                  "revisar, não o que deixar de testar.")
    return "\n".join(linhas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("ref", nargs="?", default="HEAD",
                   help="ref do git contra a qual comparar (padrão: HEAD)")
    args = p.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)
    arquivos = arquivos_do_diff(args.ref)
    if not arquivos:
        print(f"Nada mudou contra {args.ref}.")
        return 0
    print(relatorio(avaliar(arquivos, montar_grafo()), args.ref))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
