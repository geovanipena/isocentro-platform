"""Varre o que vai para o commit atrás de identificador REAL de paciente.

Por que existe: em 31/08/2026 este repositório era público e tinha 13 registros
reais em 22 arquivos, alguns casados com NOME e dois com CID. Desfazer isso
custou fechar o repositório e reescrever o histórico inteiro do git — e nem
assim desfaz o que já esteve público. A troca por pseudônimo (`900NNNN`,
`Amostro/Amostra/...`) resolveu o passado; esta ferramenta é o que impede o
próximo. O relatório de uso de 09/09/2026 pediu exatamente isto: varrer o diff
antes do push, e **abortar** se achar.

O que ela olha são as **linhas ADICIONADAS** do diff — o que está entrando.
Linha removida não interessa: tirar dado sensível é o conserto, não a falta.

Três verificações, da mais específica para a mais ampla:

1. **Registro colado num sufixo de unidade** — `CEL`, `BET` ou `ANA` —, em
   qualquer das grafias que o acervo usa (`NNNNNNNCBR`, `-CEL`, `-cel`,
   ` CEL`, ` cel`). Pseudônimo começa em `900`; sete dígitos com qualquer outro
   prefixo ao lado de um desses sufixos é registro de verdade. Esta não depende
   de arquivo nenhum: vale em estação nova, onde o mapa não existe.

   O `BET` e o `ANA` entraram em 10/09/2026, na primeira execução: a varredura
   de 31/08 tinha procurado só por `CEL` e, por isso, não viu **nove** outros
   registros reais que já estavam versionados.
2. **Os valores reais do `.identidades.json`** — registro (inclusive o número
   PURO, sem `CEL`, que é a grafia que some numa busca por `[0-9]+CEL`) e nome
   inteiro. O mapa é o único lugar onde o vínculo pseudônimo→real existe e fica
   FORA do git; é por isso que aqui a varredura é exata, e não palpite.
3. **Cada palavra do nome real, isolada** (4 letras ou mais). Foi assim que a
   segunda varredura de 31/08 achou as sete sobras que a primeira perdeu: o
   mapa trocou a primeira metade do nome e a segunda estava na LINHA SEGUINTE,
   fora do alcance de qualquer busca pelo nome inteiro.

   Palavra que também aparece no PSEUDÔNIMO não conta. "Joana Helena Felipe de
   Sicrana" é nome inventado, e acusar o "Helena" dele seria acusar a solução —
   achado falso é defeito da ferramenta, e ferramenta que grita à toa é
   ferramenta que se aprende a pular.

**Ela nunca imprime por inteiro o que achou**: sai o começo, o tamanho e o
`arquivo:linha`. Relatório que ecoa o registro do paciente vaza o dado no lugar
onde ele mais viaja — a saída do terminal, que vira transcript e relatório de
uso. Para ver o que é, abre-se o arquivo na linha.

Saída **0** = nada achado; **1** = achado, não commitar; **2** = o git falhou.

Sem o `.identidades.json` (estação nova, ou outra pessoa) só a verificação 1
roda, e o relatório diz isso em voz alta: varredura que se anuncia completa sem
ser é pior que varredura nenhuma.

Uso:

    python tools/varrer_identidade.py                 # o que está no índice
    python tools/varrer_identidade.py --arvore        # índice + árvore suja
    python tools/varrer_identidade.py --intervalo origin/main..main   # antes do push
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple

RAIZ = Path(__file__).resolve().parent.parent
MAPA = RAIZ / ".identidades.json"

# O prefixo que a convenção de 31/08/2026 reservou para o pseudônimo. Ele não
# existe no acervo real, e é isso que deixa o número sintético reconhecível.
PREFIXO_SINTETICO = "900"

# Os três sufixos de unidade que aparecem no acervo. A lista é FECHADA de
# propósito: `[A-Z]{3}` acenderia nos marcadores sintéticos que os testes já
# usam aos montes — 62 ocorrências de `NNNNNNNAAA`, 26 de `BBB`, 7 de `XXX`
# (medido em 10/09/2026 sobre os arquivos versionados). Sufixo novo entra aqui,
# com a data em que apareceu.
SUFIXOS = ("CEL", "BET", "ANA")

# As grafias do registro no acervo: `NNNNNNNCBR`, `NNNNNNN-CEL`, `NNNNNNN cel`.
# O `(?<!\d)` impede que um número de 8 dígitos entre pelos 7 últimos.
RE_REGISTRO_CEL = re.compile(
    r"(?<!\d)(\d{7})\s*[-_ ]?\s*(?:" + "|".join(SUFIXOS) + r")\b", re.IGNORECASE
)

# Palavra com menos de 4 letras não distingue ninguém ("de", "dos", "Sá") e
# acenderia em qualquer linha de texto.
MINIMO_DA_PALAVRA = 4

# Palavras que VIERAM de nome real e mesmo assim não distinguem ninguém. Cada
# uma entra com a data e o caso que a pôs aqui — lista de exceção é como um
# nome real acaba liberado por engano, então a regra é estreita: só PRIMEIRO
# nome comum o bastante para ser marcador de teste, nunca sobrenome.
#
# - "maria" (10/09/2026): acendia em `Retratamento, Maria`, que é o marcador
#   inventado da fixture de retratamento do `test_mapear_gatilho.py`.
PALAVRAS_COMUNS = frozenset({"maria"})


class Achado(NamedTuple):
    arquivo: str
    linha: int
    tipo: str
    amostra: str


def _mascarar(valor: str) -> str:
    """Duas primeiras letras e o tamanho — o bastante para reconhecer, não para vazar.

    O `arquivo:linha` do achado é que leva ao dado; a amostra serve só para
    quem lê saber se é registro ou nome, sem que o transcript guarde nenhum dos
    dois por inteiro.
    """
    if len(valor) <= 2:
        return "*" * len(valor)
    return valor[:2] + "*" * (len(valor) - 2)


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _palavras(nome: str) -> set[str]:
    """As palavras de um nome, sem acento e em minúscula.

    Sem acento porque o mesmo nome aparece nas duas formas — o banco devolve em
    caixa alta e sem acento, o cadastro à mão vem acentuado, e uma busca literal
    perderia metade das ocorrências.
    """
    return {
        p for p in re.split(r"[^0-9A-Za-zÀ-ÿ]+", _sem_acento(nome).lower()) if p
    }


def carregar_mapa(caminho: Path = MAPA) -> dict | None:
    """O `.identidades.json`, ou `None` se ele não existe nesta estação.

    Não é erro não existir: o arquivo está fora do git de propósito. Quem
    chama é que precisa dizer, no relatório, que a varredura foi parcial.
    """
    if not caminho.is_file():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def linhas_adicionadas(diff: str) -> list[tuple[str, int, str]]:
    """As linhas que ENTRAM, com o arquivo e o número delas no arquivo novo.

    Percorrer o `@@` em vez de só contar `+` é o que dá o número de linha certo
    no relatório — achado sem linha manda o leitor procurar o dado sensível de
    olho, no arquivo inteiro.
    """
    saida: list[tuple[str, int, str]] = []
    arquivo = "?"
    numero = 0
    for linha in diff.splitlines():
        if linha.startswith("+++ "):
            alvo = linha[4:].strip()
            arquivo = alvo[2:] if alvo.startswith("b/") else alvo
            continue
        if linha.startswith("@@"):
            m = re.search(r"\+(\d+)", linha)
            numero = int(m.group(1)) if m else 0
            continue
        if linha.startswith("+"):
            saida.append((arquivo, numero, linha[1:]))
            numero += 1
        elif not linha.startswith("-"):
            numero += 1
    return saida


def varrer(diff: str, mapa: dict | None) -> list[Achado]:
    """Os achados do diff, na ordem em que aparecem.

    Recebe o TEXTO do diff, não o repositório: é o que deixa o teste provar
    cada uma das três verificações sem inventar um git no disco.
    """
    registros_reais: set[str] = set()
    nomes_reais: dict[str, set[str]] = {}
    palavras_do_pseudonimo: set[str] = set()

    if mapa:
        registros_reais = {str(k) for k in mapa.get("registros", {})}
        for real, falso in mapa.get("nomes", {}).items():
            nomes_reais[real] = _palavras(real)
            palavras_do_pseudonimo |= _palavras(str(falso))

    achados: list[Achado] = []
    for arquivo, numero, texto in linhas_adicionadas(diff):
        vistos: set[str] = set()

        for registro in RE_REGISTRO_CEL.findall(texto):
            if not registro.startswith(PREFIXO_SINTETICO) and registro not in vistos:
                vistos.add(registro)
                achados.append(
                    Achado(arquivo, numero, "registro", _mascarar(registro))
                )

        for registro in registros_reais:
            if re.search(rf"(?<!\d){re.escape(registro)}(?!\d)", texto):
                if registro not in vistos:
                    vistos.add(registro)
                    achados.append(
                        Achado(arquivo, numero, "registro", _mascarar(registro))
                    )

        if not nomes_reais:
            continue

        planificada = _sem_acento(texto).lower()
        do_texto = _palavras(texto)
        for real, palavras in nomes_reais.items():
            if _sem_acento(real).lower() in planificada:
                achados.append(Achado(arquivo, numero, "nome", _mascarar(real)))
                continue
            # A palavra isolada: o nome partido por fim de linha, que a busca
            # pelo nome inteiro nunca vê.
            candidatas = palavras - palavras_do_pseudonimo - PALAVRAS_COMUNS
            for palavra in sorted(candidatas):
                if len(palavra) >= MINIMO_DA_PALAVRA and palavra in do_texto:
                    achados.append(
                        Achado(arquivo, numero, "nome (palavra)", _mascarar(palavra))
                    )
                    break

    return achados


def diff_dos_nao_rastreados(paths: list[str], raiz: Path = RAIZ) -> str:
    """Os arquivos NOVOS, ainda fora do git, como se fossem diff de adição.

    Existe porque `git diff` não os enxerga, e foi por esse buraco que o próprio
    `tests/test_varrer_identidade.py` entrou, em 10/09/2026, com um registro e um
    nome reais copiados do `.identidades.json` para servir de fixture: o
    `--arvore` disse "nada" enquanto o arquivo estava por adicionar. Arquivo novo
    é justamente onde o dado colado à mão aparece primeiro.
    """
    pedacos: list[str] = []
    for rel in paths:
        p = raiz / rel
        if not p.is_file():
            continue
        try:
            linhas = p.read_bytes().decode("utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue  # binário não guarda nome de paciente em texto.
        if not linhas:
            continue
        corpo = "\n".join("+" + linha for linha in linhas)
        pedacos.append(f"+++ b/{rel}\n@@ -0,0 +1,{len(linhas)} @@\n{corpo}")
    return "\n".join(pedacos)


def _nao_rastreados() -> list[str]:
    saida = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=RAIZ,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if saida.returncode != 0:
        return []
    return [
        linha[3:].strip().strip('"')
        for linha in saida.stdout.splitlines() if linha.startswith("??")
    ]


def _diff(args: argparse.Namespace) -> str:
    if args.intervalo:
        comando = ["git", "diff", "-U0", args.intervalo]
    elif args.arvore:
        comando = ["git", "diff", "-U0", "HEAD"]
    else:
        comando = ["git", "diff", "-U0", "--cached"]
    saida = subprocess.run(
        comando, cwd=RAIZ, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if saida.returncode != 0:
        print(f"git falhou: {saida.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    texto = saida.stdout
    if args.arvore:
        novos = diff_dos_nao_rastreados(_nao_rastreados())
        if novos:
            texto += "\n" + novos
    return texto


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--arvore", action="store_true",
                   help="índice + árvore suja (git diff HEAD)")
    p.add_argument("--intervalo", metavar="A..B",
                   help="um intervalo de commits, p. ex. origin/main..main")
    args = p.parse_args(argv)

    mapa = carregar_mapa()
    achados = varrer(_diff(args), mapa)

    if mapa is None:
        print(
            "AVISO: sem `.identidades.json` nesta estação — só a verificação "
            "do registro colado ao sufixo de unidade rodou. Nome real e número "
            "puro NÃO foram conferidos."
        )

    if not achados:
        print("Nada de paciente real nas linhas que entram.")
        return 0

    print(f"{len(achados)} achado(s) — NÃO commitar antes de olhar:\n")
    for a in achados:
        print(f"  {a.arquivo}:{a.linha}  {a.tipo}: {a.amostra}")
    print(
        "\nAbra o arquivo na linha. Se for dado real, troque pelo pseudônimo "
        "(`900NNNN`, e o nome do `.identidades.json`) antes de seguir."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
