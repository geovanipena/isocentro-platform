r"""Gera ``assets/notas_modelo.json`` — a semente da biblioteca de notas.

Por que existe uma semente separada do arquivo de trabalho:

O arquivo que o app usa em produção é ``notas_posicionamento.json``, ao lado do
programa, e ele **não pode viajar no zip**: o ``migrar.ps1`` nunca sobrescreve,
então uma cópia dele no pacote faria a migração PULAR a biblioteca real do
serviço — as notas que o técnico criou sumiriam sem aviso (é o erro nº 2
catalogado no ``gerar_executavel.py``).

Mas sem NADA no pacote, instalação nova abre com o seletor de notas vazio: o
acervo ``.docx`` de onde ``semear()` lê também não é empacotado. Foi o que
aconteceu na clínica.

A semente resolve os dois: nome diferente, então o ``migrar.ps1`` a ignora e ela
pode ser empacotada; e ``notas_setup.semear()`` lê dela quando não há acervo.

Gerar à mão (copiar o ``notas_posicionamento.json`` de uma estação) traria junto
as notas de PACIENTE que alguém criou ali. Daí o script: ele lê o acervo,
descarta o que não é modelo e ordena — sempre o mesmo resultado.

Rodar:
    python tools/gerar_notas_modelo.py
    python tools/gerar_notas_modelo.py --conferir   (CI: só acusa desatualizado)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from isocentro.dados import notas_setup  # noqa: E402

DESTINO = RAIZ / "assets" / notas_setup.ARQUIVO_SEMENTE


def montar() -> str:
    """O conteúdo da semente, do acervo ``.docx``. Erro se não houver acervo."""
    pasta = notas_setup.pasta_do_acervo()
    assert pasta, ("nenhum acervo .docx encontrado — a semente só pode ser "
                   f"gerada onde estiver uma das pastas {notas_setup._ACERVOS}")
    notas = [n for n in notas_setup.semear() if n.modelo]
    assert notas, f"o acervo em {pasta} não rendeu nenhuma nota"
    corpo = {"versao": 1, "notas": [asdict(n) for n in
                                    sorted(notas, key=lambda n: n.nome.upper())]}
    # ``indent`` e ``ensure_ascii`` fixos: a semente é versionada, e um diff de
    # arquivo inteiro a cada regeração esconde a nota que realmente mudou.
    return json.dumps(corpo, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--conferir", action="store_true",
                   help="não grava; sai com 1 se a semente estiver desatualizada")
    args = p.parse_args()

    novo = montar()
    if args.conferir:
        atual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if atual != novo:
            print(f"DESATUALIZADA: {DESTINO}\n"
                  "rode: python tools/gerar_notas_modelo.py")
            return 1
        print(f"em dia: {DESTINO}")
        return 0

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    # ``newline=""`` para o \n do json.dumps não virar \r\n no Windows: a
    # semente é comparada byte a byte pelo --conferir.
    with open(DESTINO, "w", encoding="utf-8", newline="") as fh:
        fh.write(novo)
    print(f"{len(json.loads(novo)['notas'])} modelos gravados em {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
