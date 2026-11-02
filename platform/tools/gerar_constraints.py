"""Gera o ``constraints.txt`` da raiz: versão exata de tudo que o
``requirements.txt`` puxa, inclusive as dependências das dependências.

O ``requirements.txt`` fixa os 11 pacotes diretos, mas o pip ainda escolhia
sozinho as 11 transitivas (contourpy, fonttools, PyQt5-Qt5, ...): o mesmo
commit podia instalar outra coisa um mês depois. O ``constraints.txt`` fecha
isso sem misturar as transitivas na lista que alguém lê para saber do que o
app depende.

Lê o ambiente em que roda (o ``.venv`` da estação), anda a árvore a partir de
cada linha do ``requirements.txt`` pelos metadados instalados e grava só o
que é alcançável dali — ``ruff``, ``pyinstaller`` e o que mais estiver no
``.venv`` por outro motivo ficam fora. Extras não pedidos e marcadores que
não valem neste Python/Windows ficam fora também.

Rodar, depois de mexer no ``requirements.txt`` e instalar:
    .venv\\Scripts\\python.exe tools\\gerar_constraints.py

Falha (código 1) se um pacote do ``requirements.txt`` não está instalado ou
está em versão diferente da fixada: constraints gerado de um ambiente que
não bate com o requirements não fixa nada.
"""
from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

RAIZ = Path(__file__).resolve().parent.parent
REQUIREMENTS = RAIZ / "requirements.txt"
CONSTRAINTS = RAIZ / "constraints.txt"

CABECALHO = """\
# ISOCENTRO — versão exata das dependências transitivas.
#
# GERADO por tools/gerar_constraints.py; não editar à mão. O requirements.txt
# diz do que o app depende; este arquivo fixa o que o pip puxa junto, para o
# mesmo commit instalar sempre o mesmo ambiente. Instalar com:
#     pip install -r requirements.txt -c constraints.txt
# Para atualizar: mudar o requirements.txt, instalar, rodar o gerador e
# commitar os dois juntos.
"""


def _diretos() -> list[Requirement]:
    reqs = []
    for linha in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            reqs.append(Requirement(linha))
    return reqs


def _vale(req: Requirement, extras: set[str]) -> bool:
    if req.marker is None:
        return True
    ambiente = default_environment()
    return any(req.marker.evaluate({**ambiente, "extra": e})
               for e in (extras or {""}))


def _arvore(diretos: list[Requirement]) -> dict[str, metadata.Distribution]:
    achados: dict[str, metadata.Distribution] = {}
    pilha = [(r, set(r.extras)) for r in diretos]
    while pilha:
        req, extras = pilha.pop()
        nome = canonicalize_name(req.name)
        if nome in achados:
            continue
        try:
            dist = metadata.distribution(req.name)
        except metadata.PackageNotFoundError:
            sys.exit(f"ERRO: {req.name} não está instalado neste ambiente.")
        achados[nome] = dist
        for texto in dist.requires or []:
            sub = Requirement(texto)
            if _vale(sub, extras):
                pilha.append((sub, set(sub.extras)))
    return achados


def conferir_diretos(diretos: list[Requirement]) -> str:
    """"" se o ambiente tem cada pacote direto na versão fixada; senão, o erro."""
    for req in diretos:
        try:
            instalada = metadata.version(req.name)
        except metadata.PackageNotFoundError:
            return f"{req.name} não está instalado neste ambiente."
        if not req.specifier.contains(instalada, prereleases=True):
            return (f"{req.name} {instalada} instalado, "
                    f"requirements.txt pede {req.specifier}.")
    return ""


def pacotes(diretos: list[Requirement]) -> list[str]:
    """`Nome==versão` de tudo que os diretos puxam, em ordem de nome."""
    arvore = _arvore(diretos)
    return [f"{arvore[n].metadata['Name']}=={arvore[n].version}"
            for n in sorted(arvore)]


def texto(linhas: list[str]) -> str:
    return CABECALHO + "\n" + "\n".join(linhas) + "\n"


def main() -> int:
    diretos = _diretos()
    erro = conferir_diretos(diretos)
    if erro:
        print("ERRO:", erro)
        return 1
    linhas = pacotes(diretos)
    CONSTRAINTS.write_text(texto(linhas), encoding="utf-8", newline="\n")
    print(f"{CONSTRAINTS.name}: {len(linhas)} pacotes "
          f"({len(diretos)} diretos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
