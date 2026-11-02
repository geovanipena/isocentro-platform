r"""A varredura chamada de FORA do app — a porta de entrada da concentradora.

O relógio da exportação morou dentro do app aberto (``gatilho_relogio``, decisão
de 02/09/2026) até a R-21 (28/10/2026), que o tirou: gatilho de tempo é só da
concentradora (AD-28). Esta ferramenta é a porta única — uma passada, sem
tela, chamada pela Tarefa Agendada do Windows. Desde a R-21 ela também roda
a passada do núcleo: prazos viram alertas e a âncora do dia é gravada.

**O trabalho é o mesmo**, e de propósito: quem decide o que sai, o que fecha e o
que se limpa continua sendo o :func:`gatilho.rodar`. Aqui só há o que a linha de
comando precisa — console em UTF-8, o rastro no lugar certo e um código de saída
que o Agendador saiba mostrar.

**Códigos de saída**, que é o que aparece no Agendador como "último resultado":

| código | o quê | o que fazer |
|---|---|---|
| 0 | rodou (inclusive sem nada a exportar, e inclusive PULADA por outra em curso) | nada |
| 1 | começou e foi interrompida — rede fora, AE recusado; ou a passada do núcleo (prazos, âncora) falhou | ler o motivo impresso |
| 2 | **não rodou**: portão fechado (banco ou DICOM sem configuração, ou esta máquina não é a concentradora) | Configurações → Serviço, ou a TI |
| 4 | exceção inesperada — isto é defeito nosso | o traceback está no log |

**Por que "pulada por outra em curso" é 0 e não erro:** é a trava fazendo o que
deve. Uma tarefa que fica vermelha toda vez que duas rodadas se cruzam ensina a
ignorar o Agendador, e aí o dia em que ele ficar vermelho de verdade não vai
significar nada. O rastro dela é o log — varredura sempre pulada quer dizer que
o intervalo ficou curto para esta clínica, e isso se lê no histórico, não no
código de saída.

**Não grava relatório em arquivo**, ao contrário do checkup: isto roda de cinco
em cinco minutos, e um arquivo por rodada seria um cemitério. O rastro é o
``~/.isocentro.log`` da conta que rodou (ver ``log_app.configurar``) mais o
histórico compartilhado, que é onde o admin enxerga todas as estações juntas.

Rodar:
    python tools/varredura_cli.py                 # uma passada
    python tools/varredura_cli.py --conferir      # só o portão, não exporta nada
    python tools/varredura_cli.py --pasta D:\x    # outra raiz (teste)
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    RAIZ = Path(__file__).resolve().parent.parent
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))

from isocentro.dados import config_servico, log_app  # noqa: E402
from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: E402
from isocentro.dominio import gatilho, gatilho_registro  # noqa: E402

# Os códigos, como constantes: número solto no meio do código vira dois
# significados para o mesmo valor, e quem lê o Agendador não tem onde conferir.
SAIU_OK = 0
SAIU_INTERROMPIDA = 1
SAIU_PORTAO = 2
SAIU_ERRO = 4


def _console_em_utf8() -> None:
    """Sem isto, a saída morre no meio — e morre justamente no acento.

    Gêmeo do ``checkup_clinica._console_em_utf8``, e a duplicação é
    deliberada: unificar os dois significaria mexer no binário do checkup e
    reconferir aquele pacote, que é outra frente. O defeito que os dois evitam
    foi medido em 10/09/2026 no executável recém-gerado — o console do Windows
    abre em code page 850, o Python escolhe cp1252 para a saída, e três blocos
    saíram como ``UnicodeEncodeError``. O ``.bat`` resolvia com ``chcp 65001``,
    e o ``.bat`` é justamente o que não existe quando o Agendador chama o exe.
    """
    if os.name == "nt":
        try:
            import ctypes  # noqa: PLC0415

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:  # noqa: BLE001
            pass
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            # Saída redirecionada para um objeto que não é TextIOWrapper (é o
            # que a suíte faz). Ali a codificação já é a do teste.
            pass


def _cabecalho() -> None:
    print("=" * 72)
    print("  ISOCENTRO — varredura da exportação automática")
    print(f"  {datetime.datetime.now():%d/%m/%Y %H:%M:%S}")
    print("=" * 72)


def _arquivo(p: Path) -> str:
    """O caminho E se ele está lá: a ausência é metade do diagnóstico."""
    try:
        existe = p.exists()
    except OSError:
        # Caminho de rede fora do ar responde ERRO, não "não existe", e a
        # diferença entre as duas coisas é justamente o que se foi conferir:
        # uma é instalação no lugar errado, a outra é o share que caiu.
        return f"{p} (NÃO DEU PARA OLHAR — o caminho responde erro)"
    return f"{p} ({'existe' if existe else 'NÃO EXISTE'})"


def _onde_e_de_onde(raiz: Path) -> None:
    """A pasta e QUAL degrau a escolheu, sempre — nas duas ações.

    Numa Tarefa Agendada isto vale mais que na tela: o degrau que vence muda
    com a CONTA que roda, e "não exportou nada" tem cara igual em qualquer um
    dos casos. Impresso, o desencontro aparece na primeira linha.

    **As duas linhas de arquivo são de 14/09/2026**, e dizem onde ESTE processo
    foi procurar o que é do serviço. As duas saem de ``raiz.pasta_do_app()``,
    que empacotado é **a pasta do próprio .exe** — então instalar este binário
    fora da pasta compartilhada do app (aquela de onde as estações rodam)
    quebra duas coisas de uma vez, e as duas em silêncio: ele passa a ler um
    ``config_servico.json`` vazio, e as quatro chaves do DICOM que o admin
    apontou pela tela não chegam nele; e grava o ``gatilho_registro.json`` num
    canto que NENHUMA estação enxerga, de modo que a Fichinha não mostra caso
    pronto nenhum. Os dois desfechos têm a mesma cara de "não havia nada para
    exportar" — que é o motivo de o caminho ser impresso e não deduzido.
    """
    print(f"Pasta da exportação : {raiz}")
    print(f"  escolhida por     : {gatilho.origem_da_pasta()}")
    print(f"Rede DICOM          : {dicom_rede.origem_da_configuracao()}")
    # Quem varre, desde 18/09/2026 (``gatilho.motivo_da_maquina``). Os dois
    # nomes lado a lado: o desencontro mais provável é de GRAFIA (IP no lugar
    # do nome, a máquina errada), e ele só se vê comparando.
    print(f"Concentradora       : {gatilho.concentradora() or '(não apontada)'}"
          f" — esta máquina: {gatilho.nome_desta_maquina() or '?'}")
    print(f"Configuração        : {_arquivo(config_servico.caminho())}")
    print(f"Estado da automação : {_arquivo(gatilho_registro.caminho())}")
    print(f"Conta do Windows    : {os.environ.get('USERNAME') or '?'}")


def _conferir(raiz: Path) -> int:
    """Só olha o portão. Não abre associação, não grava, não apaga.

    É o que se roda depois de configurar a máquina, antes de cadastrar a
    tarefa: sem isto, a primeira notícia de que a conta do serviço não enxerga
    a configuração seria a ausência de arquivos, dias depois.
    """
    _onde_e_de_onde(raiz)
    print()
    if gatilho.disponivel():
        print("PORTÃO ABERTO — a varredura roda nesta máquina e nesta conta.")
        return SAIU_OK
    print("PORTÃO FECHADO — nada seria exportado:")
    print(f"  {gatilho.motivo_indisponivel()}")
    return SAIU_PORTAO


def _relatar(rel) -> int:
    """Imprime o que a passada fez e escolhe o código de saída."""
    if rel.portao:
        if rel.portao == gatilho.MOTIVO_OCUPADA:
            # Não é erro: é a trava funcionando. Ver a docstring do módulo.
            print(f"PULADA: {rel.portao}")
            return SAIU_OK
        print(f"NÃO RODOU: {rel.portao}")
        return SAIU_PORTAO

    for pronto in rel.exportados:
        print(f"  exportado   {pronto.registro}  {pronto.curso}  {pronto.plano}")
    for pronto, motivo in rel.incompletos:
        print(f"  incompleto  {pronto.registro}  {pronto.plano} — {motivo}")
    for alvo in rel.limpos:
        print(f"  limpo       instância {alvo['instancia']} — {alvo['motivo']}")
    print()
    print(rel.resumo())
    if rel.interrompida:
        return SAIU_INTERROMPIDA
    return SAIU_OK


# Quem a concentradora é no log: a linha de alerta aberto por prazo diz que
# ninguém o abriu à mão (CAP-14).
QUEM_CONCENTRADORA = "isocentro_concentradora"

# As fontes de prazo dos módulos, por nome (``nucleo.concentradora``). Vazia
# até o primeiro módulo existir: cada spec de módulo (Documentação, GQ, Plano)
# registra a sua aqui.
FONTES_DE_PRAZO: dict = {}


def _passada_do_nucleo() -> int:
    """Os prazos viram alertas e a âncora do dia é gravada (R-21, AD-28, AD-32).

    Roda só com ``ISOCENTRO_PG_CONCENTRADORA`` definida, e é isso que a faz
    rodar só na concentradora: as estações não têm a credencial dela. A
    conferência do portão DICOM não vale aqui — prazo e âncora não dependem
    do AE Title, e a exportação parada não pode parar também os alertas.
    """
    from isocentro.dados import ambiente  # noqa: PLC0415
    conexao = ambiente.ler("ISOCENTRO_PG_CONCENTRADORA").strip()
    if not conexao:
        print("Núcleo              : ISOCENTRO_PG_CONCENTRADORA não definida —"
              " prazos e âncora não rodam nesta máquina")
        return SAIU_OK
    # Importado aqui: o executável ainda não leva o psycopg (NOTAS, R-18), e
    # a exportação não pode morrer no import por causa do núcleo.
    import psycopg  # noqa: PLC0415

    from isocentro.adaptadores.ancora import pasta as pasta_ancora  # noqa: PLC0415
    from isocentro.adaptadores.postgres import esquema  # noqa: PLC0415
    from isocentro.adaptadores.postgres.alertas import PortaDeAlertas  # noqa: PLC0415
    from isocentro.adaptadores.postgres.porta import PortaPostgres  # noqa: PLC0415
    from isocentro.nucleo import concentradora  # noqa: PLC0415

    pasta = pasta_ancora.pasta_configurada()
    try:
        # connect_timeout: no Windows, conectar com o banco central fora
        # fica pendurado para sempre, e a varredura agendada nunca mais
        # terminaria (medido em 29/10/2026; ARMADILHAS).
        with psycopg.connect(conexao, autocommit=True,
                             connect_timeout=5) as c:
            situacao = esquema.conferir(c)
            if situacao.somente_leitura:
                print(f"Núcleo NÃO RODOU    : {situacao.aviso}")
                return SAIU_PORTAO
            rel = concentradora.passada(
                FONTES_DE_PRAZO, PortaDeAlertas(c, QUEM_CONCENTRADORA),
                PortaPostgres(c),
                pasta_ancora.PastaDeAncoras(pasta) if pasta else None)
    except psycopg.OperationalError as exc:
        # Banco fora não é defeito nosso (4): é o "rodou pela metade" (1), e
        # a próxima passada tenta de novo.
        print(f"Núcleo NÃO RODOU    : banco central inacessível ({exc})")
        return SAIU_INTERROMPIDA
    print(f"Núcleo              : {len(rel.alertas)} alerta(s) de prazo")
    if rel.ancora_gravada:
        print(f"  âncora do dia     : posição {rel.ancora.posicao}")
    for falha in rel.falhas:
        print(f"  FALHA             : {falha}")
    return SAIU_INTERROMPIDA if rel.falhas else SAIU_OK


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Uma passada da exportação automática, sem abrir o app. "
                    "É o que a Tarefa Agendada da concentradora chama.")
    p.add_argument("--conferir", action="store_true",
                   help="só diz se o portão está aberto; não exporta nada")
    p.add_argument("--uma-vez", action="store_true",
                   help="(padrão) uma passada e sai — explícito na linha da "
                        "Tarefa Agendada, para quem for ler depois")
    p.add_argument("--pasta", default="",
                   help="raiz da exportação; o padrão é a do serviço")
    a = p.parse_args(argv)

    _console_em_utf8()
    log_app.configurar()
    _cabecalho()

    try:
        raiz = Path(a.pasta) if a.pasta else gatilho.pasta_destino()
        if a.conferir:
            return _conferir(raiz)
        _onde_e_de_onde(raiz)
        print()
        codigo = _relatar(gatilho.rodar(raiz))
        print()
        # O núcleo roda mesmo com a exportação parada (ver
        # ``_passada_do_nucleo``). O código da exportação vence: é o que o
        # Agendador sempre mostrou, e o do núcleo só aparece quando ela foi bem.
        nucleo = _passada_do_nucleo()
        return codigo or nucleo
    except Exception as exc:  # noqa: BLE001
        # O ``rodar`` promete não levantar; se levantou, é defeito nosso. O
        # traceback vai para o LOG, e a tela do Agendador recebe uma linha que
        # se lê — traceback no "último resultado" de uma tarefa não é lido por
        # ninguém, e o código 4 é o que distingue isto de "não rodou".
        import logging  # noqa: PLC0415

        # O logger é o do ``gatilho``, de propósito, e é a única exceção à regra
        # que o ``tests/test_loggers_app.py`` guarda (``getLogger(__name__)``,
        # sempre). O motivo: aquela regra existe para a ORIGEM no histórico não
        # mentir, e o que ela protege é a lista ``log_app.LOGGERS_APP`` — onde
        # este módulo NÃO está, por ser ferramenta. Logando com o nome próprio,
        # a falha da varredura agendada seria filtrada e não chegaria ao admin,
        # que é justamente quem precisa saber que a concentradora parou. O que
        # levantou aqui é trabalho do ``gatilho``; o nome diz a verdade.
        logging.getLogger("gatilho").exception("A varredura levantou")
        print(f"ERRO INESPERADO: {exc}")
        print("O traceback está em ~/.isocentro.log (conta que rodou).")
        return SAIU_ERRO


if __name__ == "__main__":
    raise SystemExit(main())
