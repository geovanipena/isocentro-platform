r"""Compara, campo a campo, o que o BANCO diz e o que os RELATÓRIOS dizem.

A capa vai grampeada na ficha e é conferida por quem posiciona o paciente na
mesa. Trocar a fonte dos dados dela sem comparar as duas seria confiar em
leitura de esquema — e o erro que assusta não é o que quebra, é o que devolve
valor **plausível e errado**: uma coluna parecida com a certa, uma junção que
pega o convênio antigo, um diagnóstico que não é o do curso em tratamento.
Nada disso aparece em teste; aparece no papel, semanas depois.

Este arquivo lê os MESMOS pacientes pelos dois caminhos e mostra onde diverge.

Rodar (precisa dos relatórios exportados na pasta configurada E do banco):

    runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\comparar_fontes.bat"
    ... "C:\...\comparar_fontes.bat --quantos 200"

Divergência não é necessariamente erro do banco: o CSV é o retrato do dia da
exportação, e o banco é agora. Convênio que mudou ontem DEVE divergir. Por isso
a saída separa o que é esperado do que precisa de explicação.
"""
from __future__ import annotations

import argparse
import sys
import unicodedata

sys.path.insert(0, __file__.rsplit("tools", 1)[0])

from isocentro.banco import capa_dados  # noqa: E402
from isocentro.banco import capa_db  # noqa: E402

# Os campos que SAEM IMPRESSOS. Comparar o resto seria ruído: o que não vai ao
# papel não muda o que a técnica confere na sala.
CAMPOS = ("nome", "nascimento", "sexo", "contato", "convenio", "curso",
          "intencao", "cid", "descricao", "medico", "maquina")

# Campos que mudam com o tempo por natureza. Divergir aqui é o banco estando
# mais novo que o CSV — que é justamente o motivo de migrar.
#
# CID e diagnóstico entram por outra razão: os dois lados escolhem por REGRAS
# DIFERENTES quando o paciente tem mais de um diagnóstico. O app usa o mais
# recente (decisão do serviço, 18/08/2026); o relatório usava outro critério.
# Os dois casos que apareceram em 200 pacientes — 9000006CEL (C50.4) e
# 9000007CEL (C34.3) — foram conferidos pelo médico: o banco está certo.
#
# Isto não cega o comparador para erro de mapeamento. Engano de coluna ou de
# junção aparece em DEZENAS de pacientes, não em dois; é a ordem de grandeza
# que denuncia, e ela continua visível na coluna DIFEREM.
ESPERADO_DIVERGIR = ("convenio", "contato", "curso", "intencao",
                     "cid", "descricao")


def _chave(texto: str) -> str:
    """Texto comparável: sem acento, sem caixa, sem pontuação de telefone.

    O CSV escreve "(62) 99973-0126" e o banco "62 99973-0126"; são o MESMO
    telefone, e contar isso como divergência esconderia as de verdade no meio
    do ruído.
    """
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return "".join(c for c in t.lower() if c.isalnum())


def _valor(cadastro, campo: str) -> str:
    """O valor COMO SAI IMPRESSO — não o campo cru.

    O médico passa pela lista canônica da equipe antes de chegar ao papel
    (``capa_pdf.medico_completo``): "Monteiro, Paula Monteiro Aragao" e
    "Paula Monteiro Aragao Monteiro" viram os dois "Paula Monteiro Aragao".
    Comparar o campo cru acusava 200 divergências que não existem no documento
    — e divergência falsa esconde a verdadeira.
    """
    bruto = getattr(cadastro, campo, "")
    if campo == "medico":
        from isocentro.papel import capa_pdf
        return capa_pdf.medico_completo(bruto)
    return bruto


def comparar(registros: list) -> dict:
    total = {c: 0 for c in CAMPOS}
    divergencias = {c: [] for c in CAMPOS}
    so_no_banco = {c: 0 for c in CAMPOS}
    so_no_csv = {c: 0 for c in CAMPOS}
    sem_cadastro_csv = sem_cadastro_banco = 0
    fotos = {"ambos": 0, "so_banco": 0, "so_csv": 0, "nenhum": 0, "iguais": 0}

    csv_cadastro = capa_dados.carregar_cadastro()

    for i, registro in enumerate(registros, 1):
        if i % 25 == 0:
            print(f"  … {i}/{len(registros)}", flush=True)
        do_banco = capa_db.cadastro_do_paciente(registro)
        do_csv = csv_cadastro.get(capa_dados.normalizar_id(registro))
        if do_banco is None:
            sem_cadastro_banco += 1
            continue
        if do_csv is None:
            sem_cadastro_csv += 1
            continue

        for campo in CAMPOS:
            b, c = (_valor(do_banco, campo), _valor(do_csv, campo))
            b, c = _chave(b), _chave(c)
            total[campo] += 1
            if b == c:
                continue
            if b and not c:
                so_no_banco[campo] += 1
            elif c and not b:
                so_no_csv[campo] += 1
            else:
                divergencias[campo].append(
                    (registro, getattr(do_csv, campo, ""),
                     getattr(do_banco, campo, "")))

        fb = capa_db.foto_do_paciente(registro)
        fc = capa_dados.foto_do_paciente(do_csv.registro, do_csv.nome)
        if fb and fc:
            fotos["ambos"] += 1
            fotos["iguais"] += int(fb == fc)
        elif fb:
            fotos["so_banco"] += 1
        elif fc:
            fotos["so_csv"] += 1
        else:
            fotos["nenhum"] += 1

    return {"total": total, "divergencias": divergencias,
            "so_no_banco": so_no_banco, "so_no_csv": so_no_csv,
            "fotos": fotos, "sem_cadastro_csv": sem_cadastro_csv,
            "sem_cadastro_banco": sem_cadastro_banco}


def relatar(r: dict) -> int:
    print(f"\n{'=' * 78}\nCAMPO A CAMPO\n{'=' * 78}")
    print(f"{'campo':12} {'comparados':>10} {'iguais':>8} {'DIFEREM':>8} "
          f"{'só banco':>9} {'só CSV':>8}")
    graves = 0
    for campo in CAMPOS:
        n = r["total"][campo]
        dif = len(r["divergencias"][campo])
        iguais = n - dif - r["so_no_banco"][campo] - r["so_no_csv"][campo]
        print(f"{campo:12} {n:10} {iguais:8} {dif:8} "
              f"{r['so_no_banco'][campo]:9} {r['so_no_csv'][campo]:8}")
        if dif and campo not in ESPERADO_DIVERGIR:
            graves += dif

    print(f"\n{'=' * 78}\nONDE DIVERGE (até 5 por campo)\n{'=' * 78}")
    for campo in CAMPOS:
        exemplos = r["divergencias"][campo]
        if not exemplos:
            continue
        if campo in ("cid", "descricao"):
            aviso = ("  (esperado: o app usa o diagnóstico MAIS RECENTE; o "
                     "relatório usava outro critério)")
        elif campo in ESPERADO_DIVERGIR:
            aviso = "  (esperado: o CSV é do dia da exportação)"
        else:
            aviso = "  ← PRECISA DE EXPLICAÇÃO"
        print(f"\n{campo}{aviso}")
        for registro, csv, banco in exemplos[:5]:
            print(f"  {registro}")
            print(f"      CSV   : {str(csv)[:66]}")
            print(f"      banco : {str(banco)[:66]}")

    f = r["fotos"]
    print(f"\n{'=' * 78}\nFOTO 3×4\n{'=' * 78}")
    print(f"  nos dois: {f['ambos']}   (byte a byte iguais: {f['iguais']})")
    print(f"  só no banco: {f['so_banco']}   só no MHTML: {f['so_csv']}   "
          f"em nenhum: {f['nenhum']}")
    if f["so_banco"]:
        print("  → o banco cobre pacientes que o relatório de fotos não tinha")

    print(f"\n  Pacientes fora do CSV de cadastro: {r['sem_cadastro_csv']}")
    print(f"  Pacientes fora do banco:            {r['sem_cadastro_banco']}")

    print(f"\n{'=' * 78}")
    if graves:
        print(f"  {graves} divergência(s) em campos que NÃO deveriam mudar.")
        print("  NÃO virar a chave antes de explicar cada uma.")
    else:
        print("  Nenhuma divergência inexplicada nos campos estáveis.")
    print(f"{'=' * 78}")
    return 1 if graves else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--quantos", type=int, default=200,
                   help="quantos pacientes comparar (padrão: 200)")
    p.add_argument("--servidor", default="SRVINSIGHT")
    p.add_argument("--relatorios", default="",
                   help="pasta dos relatórios a comparar. SEM isto vale a "
                        "procura automática — que já apontou para um acervo de "
                        "teste antigo e produziu uma comparação sem valor.")
    args = p.parse_args(argv)

    import os
    os.environ.setdefault(capa_db.ENV_SERVIDOR, args.servidor)
    capa_db.esquecer()
    if args.relatorios:
        capa_dados.definir_pasta_dados(args.relatorios)

    if capa_db.conexao() is None:
        print("Sem banco. Rode antes o diagnostico_db.py.")
        return 1
    cadastro = capa_dados.carregar_cadastro()
    if not cadastro:
        print(f"Sem relatórios em {capa_dados.pasta_dados()} "
              f"({capa_dados.origem_da_pasta()}). Não há o que comparar.")
        return 1

    # Os do CSV: são eles que existem nas duas pontas, e é a comparação que
    # interessa. Quem só está no banco não tem contra o que ser conferido.
    registros = [c.registro for c in cadastro.values()][:args.quantos]
    dias = capa_dados.idade_dos_relatorios()
    presentes = capa_dados.relatorios_presentes()
    print(f"Comparando {len(registros)} pacientes")
    print(f"  CSV de : {capa_dados.pasta_dados()}")
    print(f"  origem : {capa_dados.origem_da_pasta()}")
    print(f"  idade  : {dias} dia(s)" if dias is not None else "  idade  : ?")
    print(f"  arquivos presentes: {len(presentes)} de 3 — {presentes}")
    if len(presentes) < 3:
        # Já aconteceu: a procura automática pegou um acervo de teste sem o
        # relatório de fotos, e a comparação de foto deu 0×200 sem que isso
        # quisesse dizer nada sobre o banco.
        print("  ATENÇÃO: faltam relatórios nesta pasta. A comparação dos "
              "campos que vêm deles não vale. Use --relatorios.")
    print()
    return relatar(comparar(registros))


if __name__ == "__main__":
    sys.exit(main())
