#!/usr/bin/env python
"""Grava no banco central a semente do PPR de uma clínica (R-85, etapa 2).

    python tools/importar_ppr.py CEL --conexao "host=localhost port=5433 user=postgres dbname=isocentro" --quem geovani.pena
    python tools/importar_ppr.py DUO --conexao "..." --quem ... --simular

Lê ``Documents\\isocentro\\servico\\<CLINICA>\\ppr\\semente.json`` (feito pelo
``tools/semente_ppr.py``) e grava cada parte pelo módulo DONO, pela porta
``nucleo.gravar`` — com autor no log, como qualquer outra gravação. A
semente é a primeira versão de cada parte (CAP-11): o PPR vivo começa igual
ao vigente, e cada registro diz de onde veio.

Rodar de novo não duplica: parte igual à vigente é pulada, e parte que
mudou na semente entra como correção da vigente (``substitui``, AD-5). Uma
importação que gravasse tudo outra vez deixaria dois textos vigentes da
mesma parte.

O resumo é só contagem: a semente traz nome e CPF da equipe, e o conteúdo
não passa pela tela nem pelo log do terminal.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import psycopg  # noqa: E402

from isocentro.adaptadores.postgres import esquema  # noqa: E402
from isocentro.adaptadores.postgres import ppr as pg_ppr  # noqa: E402

RAIZ_SERVICO = Path.home() / "Documents" / "isocentro" / "servico"


def importar(porta: pg_ppr.PortaDoPpr, semente: dict,
             simular: bool = False) -> dict:
    """Grava o que difere do vigente. Devolve as contagens por resultado."""
    clinica = semente["clinica"]
    origem = semente.get("documento", {}).get("arquivo", "")
    contas = {"novas": 0, "corrigidas": 0, "iguais": 0}

    def contar(vigente, igual):
        if vigente is None:
            contas["novas"] += 1
        elif igual:
            contas["iguais"] += 1
        else:
            contas["corrigidas"] += 1
        return not igual

    gravadas = porta.partes(clinica)
    for chave, p in semente["partes"].items():
        # Sem fonte própria (os gabaritos da CEL), a parte veio do documento
        # inteiro: citar o arquivo é o mínimo que a CAP-11 pede.
        fonte = p.get("fonte") or origem
        atual = gravadas.get(chave)
        igual = atual is not None and (
            atual.modulo == p["modulo"] and atual.texto == p["texto"]
            and pg_ppr.igual(atual.documentos, p["documentos"])
            and atual.fonte == fonte)
        if contar(atual, igual) and not simular:
            if atual is not None and atual.modulo != p["modulo"]:
                # A correção não atravessa tabela (o log confere a mesma):
                # dono que mudou é decisão de planta, e se resolve à mão.
                raise SystemExit(
                    f"a parte {chave} já está gravada pelo módulo "
                    f"{atual.modulo}, e a semente diz {p['modulo']}")
            porta.gravar_parte(p["modulo"], clinica, chave, p["texto"],
                               p["documentos"], fonte,
                               substitui=atual.id if atual else None)

    dados = {m: dict(d) for m, d in semente.get("dados", {}).items()}
    if pg_ppr.CONDICOES in dados.get("qualidade", {}):
        raise SystemExit(f"a semente já tem um dado {pg_ppr.CONDICOES!r} na GQ")
    dados.setdefault("qualidade", {})[pg_ppr.CONDICOES] = sorted(
        semente.get("condicoes", []))
    vigentes = porta.dados(clinica)
    for modulo, por_chave in dados.items():
        for chave, conteudo in por_chave.items():
            atual = vigentes.get(modulo, {}).get(chave)
            igual = atual is not None and pg_ppr.igual(atual[1], conteudo)
            if contar(atual, igual) and not simular:
                porta.gravar_dado(modulo, clinica, chave, conteudo, origem,
                                  substitui=atual[0] if atual else None)
    return contas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("clinica", choices=("CEL", "BET", "DUO"))
    ap.add_argument("--conexao", required=True,
                    help="conninfo do psycopg de quem pode assumir isocentro_app")
    ap.add_argument("--quem", required=True,
                    help="quem importa: vai para cada linha do log")
    ap.add_argument("--simular", action="store_true",
                    help="só conta o que gravaria")
    args = ap.parse_args(argv)

    arquivo = RAIZ_SERVICO / args.clinica / "ppr" / "semente.json"
    semente = json.loads(arquivo.read_text(encoding="utf-8"))
    # connect_timeout: no Windows, conectar numa porta sem servidor NÃO
    # falha — fica pendurado para sempre (medido em 29/10/2026; ARMADILHAS).
    with psycopg.connect(args.conexao, autocommit=True,
                         connect_timeout=5) as c:
        # O papel do app, e não o de quem conecta: a importação tem de poder
        # exatamente o que o app pode — inserir —, e nada além.
        c.execute("SET ROLE isocentro_app")
        situacao = esquema.conferir(c)
        if situacao.somente_leitura:
            print(situacao.aviso)
            return 1
        contas = importar(pg_ppr.PortaDoPpr(c, args.quem), semente,
                          args.simular)
    verbo = "gravaria" if args.simular else "gravou"
    print(f"{args.clinica} ({semente['clinica']}): {verbo} "
          f"{contas['novas']} nova(s) e {contas['corrigidas']} correção(ões); "
          f"{contas['iguais']} igual(is) ao vigente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
