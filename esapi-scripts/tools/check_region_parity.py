#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_region_parity.py — verifica que a #region PADRÃO CLINICA é byte-a-byte
idêntica em todos os scripts/*.cs.

Extrai o bloco entre os delimitadores-comentário:
    //  #region  PADRÃO CLINICA  —  bloco compartilhado (NÃO EDITAR AQUI)
    //  #endregion  PADRÃO CLINICA
e compara MD5 + SHA-256. Saída não-zero se houver divergência (uso em pre-commit).

Uso:
    python3 tools/check_region_parity.py [--scripts DIR]
"""
import argparse
import glob
import hashlib
import os
import sys

START = "//  #region  PADRÃO CLINICA"
END = "//  #endregion  PADRÃO CLINICA"

# A região só é exigida nos scripts single-file. Pasta com .csproj é plug-in DLL
# (cria/edita estruturas, automação do ARIA...), que não usa a região: informa, não falha.
def no_region_expected(path):
    return bool(glob.glob(os.path.join(os.path.dirname(path), "*.csproj")))

# Referência v3.1 (atualizar deliberadamente ao evoluir a identidade visual).
REF_MD5 = "a5f117bdfb8fc62aec4a22d56ae2506f"
REF_SHA256 = "7e14d3ae26d4d52818e92ae2840ceb16d7cabf82b89be35ce39c6e2c65684503"


def extract_region(path):
    """Retorna (bloco_bytes, linha_ini, linha_fim) ou (None, None, None)."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    s = e = None
    for i, l in enumerate(lines):
        stripped = l.lstrip()
        if s is None and stripped.startswith(START):
            s = i
        elif s is not None and stripped.startswith(END):
            e = i
            break
    if s is None or e is None:
        return None, None, None
    block = "\n".join(lines[s:e + 1]).encode("utf-8")
    return block, s + 1, e + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", default=None,
                    help="Diretório dos .cs (padrão: <repo>/scripts)")
    args = ap.parse_args()

    scripts_dir = args.scripts or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
    files = sorted(glob.glob(os.path.join(scripts_dir, "*", "*.cs")))
    if not files:
        print("ERRO: nenhum .cs em", scripts_dir)
        return 2

    print("Região PADRÃO CLINICA — verificação de paridade")
    print("=" * 70)
    results = {}
    missing = []
    for f in files:
        block, a, b = extract_region(f)
        name = os.path.basename(f)
        if block is None:
            if no_region_expected(f):
                print("  %-38s  SEM REGIÃO (esperado)" % name)
            else:
                print("  %-38s  SEM REGIÃO" % name)
                missing.append(name)
            continue
        md5 = hashlib.md5(block).hexdigest()
        sha = hashlib.sha256(block).hexdigest()
        results[name] = (md5, sha, a, b)
        print("  %-38s  linhas %d-%d  md5=%s" % (name, a, b, md5[:12]))

    print("=" * 70)
    ok = True

    # 1) todos os presentes têm o mesmo hash?
    md5s = set(v[0] for v in results.values())
    if len(md5s) > 1:
        ok = False
        print("FALHA: regiões DIVERGENTES entre arquivos (MD5 distintos).")
        for name, (md5, _sha, _a, _b) in results.items():
            print("   %-38s md5=%s" % (name, md5))
    elif results:
        print("OK: todos os arquivos com região presente compartilham o mesmo hash.")

    # 2) bate com a referência v3?
    if results:
        cur_md5, cur_sha = next(iter(results.values()))[:2]
        if cur_md5 == REF_MD5 and cur_sha == REF_SHA256:
            print("OK: hash confere com a referência v3.")
        else:
            print("AVISO: hash atual difere da referência v3 registrada.")
            print("   atual: md5=%s" % cur_md5)
            print("   ref  : md5=%s" % REF_MD5)
            print("   -> Se a mudança foi deliberada, atualize REF_MD5/REF_SHA256 neste script.")

    # 3) algum arquivo sem região?
    if missing:
        ok = False
        print("FALHA: arquivos sem a #region PADRÃO CLINICA:", ", ".join(missing))

    print("=" * 70)
    print("RESULTADO:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
