r"""Confere as hipóteses 2 e 3 do Índice de Disponibilidade (``agenda_db.py``).

A hipótese 1 já fechou em 28/09/2026 (ver ``NOTAS.md``): as duas atividades
de manutenção são **"Serviço"** e **"Calibração"** (``ActivityNamePTB``,
categoria "09 Manutenção") — não "Atividade de Serviço"/"Parada Não
Programada", como ``agenda_db._ATIVIDADES_PARADA`` ainda supõe. Faltam:

* **Hipótese 2** — elas aparecem em ``DWH.DimActivityTransaction`` SEM
  paciente vinculado (``DimPatientID`` nulo ou zero)?
* **Hipótese 3** — cada instância dura os mesmos ~12 min de uma sessão de
  tratamento, ou dura muito mais (hora(s), como manutenção costuma durar)?
  Esse é o ponto mais fraco da hipótese original.

Só leitura, mesma conexão de ``diagnostico_db._conectar``. Não traz nome de
paciente nenhum — só se ``DimPatientID`` veio vazio, e a duração em
minutos de cada instância.

Rodar, de uma máquina fora do domínio:
    runas /netonly /user:CLINICA\geovani.pena "C:\...\isocentro\tools\checar_parada.bat"

Com uma janela maior, se 90 dias não trouxer nada (manutenção é rara):
    ... "C:\...\tools\checar_parada.bat --dias 365"

Nada aqui escreve no banco.
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, __file__.rsplit("tools", 1)[0])
sys.path.insert(0, __file__.rsplit("checar_parada", 1)[0])

from diagnostico_db import (  # noqa: E402
    BANCO_PADRAO, PORTA_PADRAO, SERVIDOR_PADRAO, _conectar, _quem_sou,
    passo_drivers, passo_identidade, passo_pyodbc, passo_rede)

# Os nomes reais, achados em 28/09/2026 (tools/atividades.py --palavra Manuten
# --consulta) — não os que agenda_db._ATIVIDADES_PARADA ainda tem.
ATIVIDADES = ("Serviço", "Calibração")

_SQL = """
SELECT TOP 50
       a.ActivityNamePTB,
       t.DimPatientID,
       t.ActivityStartDateTime,
       t.ActivityEndDateTime,
       DATEDIFF(minute, t.ActivityStartDateTime, t.ActivityEndDateTime)
  FROM DWH.DimActivityTransaction t
  JOIN DWH.DimActivity a ON a.DimActivityID = t.DimActivityID
 WHERE a.ActivityNamePTB IN ({marcas})
   AND t.ActivityStartDateTime >= DATEADD(day, -?, GETDATE())
 ORDER BY t.ActivityStartDateTime DESC
"""


def checar(cx, dias: int) -> None:
    print(f"\n{'=' * 70}\nInstâncias de {' / '.join(ATIVIDADES)} "
          f"nos últimos {dias} dias\n{'=' * 70}")
    cur = cx.cursor()
    marcas = ",".join("?" for _ in ATIVIDADES)
    try:
        cur.execute(_SQL.format(marcas=marcas), *ATIVIDADES, dias)
        linhas = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        print(f"\nFalhou: {str(exc)[:200]}")
        return
    if not linhas:
        print(f"\n0 instância(s) em {dias} dias — as duas existem no "
              f"catálogo, mas ninguém lançou nenhuma nesta janela. Tente "
              f"--dias maior (365, por exemplo).")
        return
    print(f"\n{len(linhas)} instância(s), mais recente primeiro:\n")
    print(f"  {'Atividade':<12} {'Paciente?':<10} {'Início':<20} "
          f"{'Fim':<20} {'Min.':>5}")
    com_paciente = 0
    minutos_validos: list[int] = []
    for nome, pac_id, inicio, fim, minutos in linhas:
        tem = bool(pac_id)
        com_paciente += int(tem)
        if minutos is not None:
            minutos_validos.append(minutos)
        print(f"  {str(nome):<12} {'sim' if tem else 'NÃO':<10} "
              f"{str(inicio):<20} {str(fim):<20} {str(minutos):>5}")

    print(f"\n  Hipótese 2 (sem paciente): {len(linhas) - com_paciente} SEM "
          f"paciente, {com_paciente} COM paciente vinculado, de "
          f"{len(linhas)} instância(s).")
    if minutos_validos:
        media = sum(minutos_validos) / len(minutos_validos)
        print(f"  Hipótese 3 (duração): min={min(minutos_validos)} min | "
              f"max={max(minutos_validos)} min | média={media:.1f} min")
    else:
        print("  Hipótese 3 (duração): nenhuma instância tinha Início E Fim "
              "preenchidos — sem como medir.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--servidor", default=SERVIDOR_PADRAO)
    p.add_argument("--banco", default=BANCO_PADRAO)
    p.add_argument("--porta", type=int, default=PORTA_PADRAO)
    p.add_argument("--dias", type=int, default=90,
                   help="janela pra trás, em dias (padrão: 90)")
    args = p.parse_args(argv)

    passo_identidade()
    pyodbc = passo_pyodbc()
    if pyodbc is None:
        return 1
    driver = passo_drivers(pyodbc)
    if not driver:
        return 1
    if not passo_rede(args.servidor, args.porta):
        print("\n  A porta não respondeu. Isto é REDE — não é senha nem")
        print("  permissão. VPN conectada? Cabo? Depois tente de novo.")
        return 1
    try:
        cx = _conectar(pyodbc, driver, args.servidor, args.banco, args.porta)
    except Exception as exc:  # noqa: BLE001
        texto = str(exc)
        print(f"\nNão conectei: {texto[:250]}")
        if "SSPI" in texto or "untrusted domain" in texto or "18452" in texto:
            print()
            print("  Isto é IDENTIDADE, não permissão: o servidor viu um")
            print(f"  usuário local ({_quem_sou()}), não o de rede. Faltou o")
            print("  runas /netonly — o comando INTEIRO dentro das mesmas aspas:")
            print()
            print(r'    runas /netonly /user:CLINICA\geovani.pena '
                  r'"C:\...\isocentro\tools\checar_parada.bat"')
        return 1
    try:
        checar(cx, args.dias)
    finally:
        cx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
