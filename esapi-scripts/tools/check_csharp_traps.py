#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Linter das armadilhas do compilador single-file ESAPI (CLAUDE.md §5).

Pega justamente o que hoje só apareceria ao levar o script pro Eclipse e custa
ida-e-volta. Alta precisão (evita falso-positivo com lambdas): só reporta o que é
quase certamente erro no single-file C# 5 com warnings-as-error.

Checagens (cada uma = FALHA):
  1. `const`            -> deve ser `static readonly` (const gera CS0162/CS0429).
  2. interpolação `$"`  -> C# 5 não suporta.
  3. membro corpo-expr  -> `Tipo Nome(...) => ...;` a nível de membro (lambdas OK).
  4. entidades HTML ≤/≥ -> usar Unicode ≤/≥ direto (evita duplo-escape via Esc()).

Uso:
  python tools/check_csharp_traps.py                # todos os scripts/<pasta>/*.cs single-file
  python tools/check_csharp_traps.py <arquivo.cs>   # só o(s) informado(s)
"""
import sys, os, re, glob

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
RE_CONST   = re.compile(r"\bconst\b")
# interpolação = $" (ou $@") ABRINDO uma string. Exclui o anchor $ de regex no
# fim de strings verbatim (ex.: @"^...(%|cc)$"), onde $ vem após conteúdo de padrão.
RE_INTERP  = re.compile(r'(?<![\w).\]])\$@?"')
RE_EXPRMEM = re.compile(r"^\s*(?:public|private|protected|internal)\b[^;{]*\)\s*=>")
RE_HTMLOPS = re.compile(r"&(?:le|ge|#8804|#8805|#x2264|#x2265);", re.IGNORECASE)


def strip_line_comment(line):
    # remove // ... ; ingênuo mas seguro p/ estes arquivos (sem URLs em código).
    i = line.find("//")
    return line[:i] if i >= 0 else line


def scan(path):
    problems = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return [(0, "não foi possível ler: %s" % e)]

    # neutraliza comentários de bloco preservando as quebras de linha (p/ nº de linha)
    text = BLOCK_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)

    for n, raw in enumerate(text.splitlines(), 1):
        code = strip_line_comment(raw)
        if RE_INTERP.search(code):
            problems.append((n, "interpolação de string ($\"...\") — não existe em C# 5"))
        if RE_CONST.search(code):
            problems.append((n, "`const` — use `static readonly` (const gera CS0162/CS0429)"))
        if RE_EXPRMEM.search(code):
            problems.append((n, "membro de corpo-expressão (=>) — não existe em C# 5"))
        if RE_HTMLOPS.search(raw):
            problems.append((n, "entidade HTML ≤/≥ — use Unicode ≤ (\\u2264) / ≥ (\\u2265) direto"))
    return problems


def main(argv):
    if argv:
        files = argv
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(here)
        # só os single-file: pasta com .csproj é plug-in DLL, compilado com a própria LangVersion
        files = sorted(f for f in glob.glob(os.path.join(root, "scripts", "*", "*.cs"))
                       if not glob.glob(os.path.join(os.path.dirname(f), "*.csproj")))

    total = 0
    for path in files:
        probs = scan(path)
        if probs:
            print(os.path.basename(path))
            for n, msg in probs:
                print("  L%-5d %s" % (n, msg))
            total += len(probs)

    print("=" * 60)
    if total:
        print("RESULTADO: FALHA — %d ocorrência(s)" % total)
        return 1
    print("RESULTADO: PASS — nenhuma armadilha C# 5")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
