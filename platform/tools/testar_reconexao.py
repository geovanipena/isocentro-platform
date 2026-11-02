r"""Exercita a MÁQUINA DE ESTADOS da conexão contra o servidor de verdade.

Não é o ``diagnostico_db``, que responde "por que não conecta" em camadas. Este
responde outra pergunta: **o app volta sozinho depois que a conexão cai?**

Foi escrito depois do relato da clínica de que, perdida a conexão, só voltava
entrando como admin e salvando a configuração — porque ``_salvar`` chama
``capa_db.esquecer()`` de passagem. A trava de então era permanente no
processo; hoje é um prazo que CRESCE a cada falha seguida
(``capa_db.ESPERAS_APOS_FALHA_S``).

Roda os quatro momentos, na ordem em que acontecem na sala:

1. conectar com a identidade de quem está rodando;
2. a queda — e o que a tela DIZ (tem de nomear a causa, não "sem conexão");
3. a espera — segunda tentativa não pode custar o tempo-limite de novo;
4. a volta, automática pelo prazo e manual pelo "Reconectar agora".

Precisa da identidade de rede, como o resto: numa máquina fora do domínio,
abra o console com ``runas /netonly /user:DOMINIO\usuario cmd`` e rode o .bat
DENTRO dele. Sem isso, o passo 1 falha por SSPI — e o próprio teste vai dizer
isso com essas palavras, que é justamente o que se quer conferir.

NÃO grava nada: o servidor vem por variável de ambiente, que tem precedência
sobre o ``config_servico.json``. Rodar aqui não mexe na configuração de
estação nenhuma.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.banco import capa_db  # noqa: E402

# Cala o log do ``capa_db`` NESTA ferramenta. Sem handler configurado, o
# ``logging`` joga todo WARNING no stderr pelo "último recurso", e o despejo
# cru do driver ODBC saía encavalado no relatório — logo ACIMA de cada recado
# que este teste existe para mostrar. Quem lê fica com as duas versões da mesma
# falha, e a pior das duas vem primeiro.
#
# Só aqui, e só por isso: no app o mesmo WARNING é o rastro de quem abre
# chamado, e continua indo para o ~/.isocentro.log.
logging.getLogger("capa_db").addHandler(logging.NullHandler())
logging.getLogger("capa_db").propagate = False


LINHA = "─" * 74


def passo(n: int, titulo: str) -> None:
    print(f"\n{LINHA}\n  {n}. {titulo}\n{LINHA}")


def estado(prefixo: str = "") -> str:
    situacao, recado = capa_db.estado()
    print(f"  {prefixo}[{situacao}] {recado}")
    return situacao


def main() -> int:
    alvo = capa_db.servidor()
    quem = f"{os.environ.get('USERDOMAIN', '?')}\\{os.environ.get('USERNAME', '?')}"
    print(f"\n  Servidor : {alvo or '(nenhum apontado)'}")
    print(f"  Identidade: {quem}   <- é esta que o servidor vai receber")
    if not alvo:
        print("\n  Sem servidor apontado. Defina ISOCENTRO_DB_SERVIDOR e repita.")
        return 2

    passo(1, "Conectar com a identidade de quem está rodando")
    capa_db.esquecer()
    t0 = time.monotonic()
    conectou = capa_db.conexao() is not None
    print(f"  conectou = {conectou}   ({time.monotonic() - t0:.1f}s)")
    situacao = estado()
    if not conectou:
        print("\n  A conexão não fechou. O recado acima já diz QUAL das quatro")
        print("  coisas falhou — rede, identidade, driver ou permissão. Se for")
        print("  identidade/SSPI, abra o console com runas e repita:")
        print("     runas /netonly /user:CLINICA\\geovani.pena cmd")
        print("\n  O resto do teste (queda e volta) roda mesmo assim, porque não")
        print("  depende de ter conectado.")

    passo(2, "A queda: o que a tela DIZ")
    real = capa_db.servidor()
    os.environ["ISOCENTRO_DB_SERVIDOR"] = "SERVIDOR-QUE-NAO-EXISTE"
    capa_db.esquecer()
    t0 = time.monotonic()
    capa_db.conexao()
    espera_1a = time.monotonic() - t0
    estado()
    print(f"\n  (1ª tentativa custou {espera_1a:.1f}s — é o tempo-limite)")
    print("  O recado tem de NOMEAR a causa. 'Sem conexão' para tudo manda")
    print("  abrir o chamado errado e esperar dias pela resposta que não serve.")

    passo(3, "A espera: a 2ª tentativa não repete o tempo-limite")
    t0 = time.monotonic()
    capa_db.conexao()
    espera_2a = time.monotonic() - t0
    print(f"  2ª tentativa custou {espera_2a:.2f}s")
    if espera_2a < 0.5:
        print("  OK — dentro do prazo ele nem tenta; a tela não trava campo a campo.")
    else:
        print("  *** FALHOU: repetiu o tempo-limite. O prazo não está segurando.")

    passo(4, "A volta")
    os.environ["ISOCENTRO_DB_SERVIDOR"] = real
    print("  a) automática — o prazo vencendo sozinho:")
    capa_db._sem_tentar_ate = time.monotonic() + 1.0
    estado("     durante:  ")
    time.sleep(1.2)
    situacao = estado("     vencido:  ")
    if situacao != "esperando":
        print("     OK — passado o prazo o app tenta de novo sem ninguém mandar.")
    else:
        print("     *** FALHOU: continua esperando depois do prazo.")

    print('\n  b) manual — o botão "Reconectar agora" (Configurações → Serviço):')
    capa_db.esquecer()
    conectou = capa_db.conexao() is not None
    print(f"     conectou = {conectou}")
    estado("     ")

    print(f"\n{LINHA}")
    print("  Fim. Nada foi gravado: o servidor veio por variável de ambiente.")
    print(LINHA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
