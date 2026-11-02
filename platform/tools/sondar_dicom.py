r"""Pergunta ao DB Daemon do ARIA **o que ele implementa** — só leitura.

A última peça da exportação automática é a rede, e ela tem uma pergunta que não
se responde por manual: **o servidor faz C-GET?**

- se fizer, os arquivos voltam pela MESMA conexão. Não é preciso porta ouvindo,
  regra de firewall para dentro, nem AE de destino cadastrado — o pedido à TI
  encolhe para "cadastrem este AE Title";
- se não fizer, é C-MOVE, e aí vem a conversa maior.

Historicamente o DB Daemon da Varian é forte em C-FIND/C-MOVE e o C-GET é
incerto **na versão instalada**. Escolher no chute é a armadilha do
``tools/mapear_gatilho.py`` outra vez: decidir sobre o que não se mediu. Por
isso os dois estão implementados e esta ferramenta pergunta ao servidor.

**Os quatro degraus são tentados mesmo que um falhe.** O que se quer é o mapa
do que funciona, não o primeiro erro:

1. **C-ECHO** — o servidor está lá e aceita este AE Title? É aqui que aparece a
   recusa por AE não cadastrado, que é o motivo mais provável de tudo falhar;
2. **C-FIND** por ``SOPInstanceUID`` — ele acha o plano exato? É a consulta
   mais estreita que existe, e ela é possível porque o ``PlanUID`` do data
   warehouse é justamente esse UID;
3. **C-GET** — ele entrega pela mesma conexão? É a pergunta que decide o
   desenho;
4. **C-MOVE** — só se houver AE de destino configurado, e só faz sentido se o
   C-GET não funcionar.

**O UID vem do banco, não de um palpite.** Um UID inventado faz o C-FIND
responder "0 achados" com toda a legitimidade, e isso se parece com servidor
quebrado. Por isso a ferramenta pergunta ao ``gatilho_db`` qual plano está
pronto agora e sonda com ELE — o mesmo que a automação buscaria. Quem já tem um
UID na mão passa ``--uid`` e dispensa o banco.

**Duas identidades diferentes, e é bom saber disso antes de rodar.** O DICOM se
autentica por AE Title, e não pela conta do Windows: a sondagem em si não
precisa de ``runas``. Quem precisa é o passo do UID, que fala com o
``variandw``. Rodando pelo ``.bat`` com ``runas /netonly``, os dois funcionam
de uma vez; sem ele, use ``--uid``.

**O arquivo que o C-GET trouxer é DADO DE PACIENTE.** Cai numa pasta temporária
do sistema, nunca no repositório, e o relatório diz onde para poder ser
apagado.
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools"))

from isocentro.dados import ambiente  # noqa: E402
from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: E402
from atividades import _destino_livre  # noqa: E402


def _aplicar_argumentos(a) -> None:
    """Os valores da linha de comando viram variáveis DESTE processo.

    Serve à primeira conversa com a TI: eles dizem "a porta é 51402", e se
    testa na hora sem gravar nada em estação nenhuma. Uma configuração que
    ficou meio feita atrás de um teste é pior que nenhuma — e aqui ela não
    sobrevive ao fim do processo.
    """
    for valor, nome in ((a.servidor, dicom_rede.ENV_SERVIDOR),
                        (a.ae_remoto, dicom_rede.ENV_AE_REMOTO),
                        (a.ae_local, dicom_rede.ENV_AE_LOCAL),
                        (a.ae_destino, dicom_rede.ENV_AE_DESTINO)):
        if valor:
            os.environ[ambiente.nome_novo(nome)] = valor


def _mostrar_configuracao(saida) -> None:
    """O que está valendo, e de ONDE veio.

    Sem isto, "não respondeu" não distingue servidor fora do ar de variável que
    ninguém definiu nesta máquina — e as duas mandam ligar para pessoas
    diferentes. É a mesma razão do ``origem_da_pasta`` na tela.
    """
    saida("\n===== A configuração desta máquina =====")
    for nome in (dicom_rede.ENV_SERVIDOR, dicom_rede.ENV_AE_REMOTO,
                 dicom_rede.ENV_AE_LOCAL, dicom_rede.ENV_AE_DESTINO):
        valor = ambiente.ler(nome)
        veio = ambiente.qual_valeu(nome)
        saida(f"  {nome:<26} {valor or '(vazio)'}"
              + (f"   [por {veio}]" if veio else ""))
    host, porta = dicom_rede.servidor()
    saida(f"\n  alvo: {host or '?'}:{porta or '?'}"
          f"   (a registrada do DICOM é {dicom_rede.PORTA_PADRAO}. No "
          "CLINICA, MEDIDO em 04/09/2026: o DB Service ARIA atende em "
          "srvariadb.clinica.example:51404, AE 'ARIA' — e a 51402 da literatura "
          "não existe lá)")
    if not dicom_rede.configurado():
        saida(f"\n  FALTA: {dicom_rede.motivo_indisponivel()}")


def _uid_do_banco(saida) -> str:
    """Um ``PlanUID`` de verdade, tirado da fila que a automação exportaria.

    Falha aqui não interrompe: sem UID a sondagem ainda faz o C-ECHO, que é o
    degrau que responde a pergunta mais provável de todas — "o ARIA aceita este
    AE Title?".
    """
    try:
        from isocentro.banco import gatilho_db
    except Exception as exc:  # noqa: BLE001
        saida(f"  não deu para carregar o gatilho_db: {exc}")
        return ""
    try:
        prontos = gatilho_db.prontos()
    except Exception as exc:  # noqa: BLE001
        saida(f"  não deu para perguntar ao variandw: {exc}")
        saida("  (o UID vem do banco; de máquina fora do domínio, rode pelo "
              "sondar_dicom.bat com runas /netonly — ou passe --uid)")
        return ""
    if not prontos:
        saida("  o gatilho_db não tem plano pronto agora — nada a sondar com "
              "dado real. Passe --uid de um plano conhecido.")
        return ""
    p = prontos[0]
    saida(f"  usando o plano de {p.registro} — {p.plano} ({p.estado}), "
          f"curso {p.curso}")
    saida(f"  PlanUID  {p.plan_uid}")
    if len(prontos) > 1:
        saida(f"  (há {len(prontos)} planos prontos; sondar com um basta)")
    return p.plan_uid


def _linha(saida, rotulo: str, valor: str) -> None:
    marca = "FALHOU" if valor.startswith("FALHOU") else "ok"
    if not valor:
        marca = "--"
    saida(f"  {rotulo:<8} [{marca:^6}]  {valor or '(não tentado)'}")


def _veredito(saida, achados: dict) -> None:
    """A conclusão em uma frase — que é o que se leva para a conversa com a TI.

    O relatório inteiro é para quem for depurar; quem vai abrir o chamado
    precisa de uma linha, e ela muda conforme o degrau que quebrou.
    """
    saida("\n===== O que isto quer dizer =====")
    if not achados.get("configurado"):
        saida("  Nada foi tentado: a configuração está incompleta (acima).")
        # O comando pronto, e não só o diagnóstico: quem chegou aqui já gastou
        # uma ida: e a varredura NÃO precisa de nada do que está faltando — é
        # ela que descobre a porta, e ela responde mesmo sem o AE cadastrado.
        saida("")
        saida("  Mas dá para descobrir a porta AGORA, sem nada disso:")
        saida("      tools\\sondar_dicom.bat --varrer --servidor SRVARIADB")
        return
    echo = achados.get("echo", "")
    if echo.startswith("FALHOU"):
        saida("  O primeiro degrau já falhou. As duas causas prováveis, nesta "
              "ordem:")
        saida("   1. o AE Title desta estação NÃO está cadastrado no ARIA — é "
              "a Varian/TI que cadastra, e sem isso o servidor recusa a "
              "associação antes de qualquer outra coisa;")
        saida("   2. o endereço ou a porta estão errados, ou o firewall barra "
              "a SAÍDA para essa porta.")
        return
    if achados.get("get", "").startswith("FALHOU"):
        movimento = achados.get("move", "")
        if movimento.startswith("FUNCIONA"):
            saida("  O C-GET não existe neste daemon, e o C-MOVE ENTREGOU: o "
                  "circuito está fechado nesta estação. É a resposta boa que "
                  "sobrou — o preço é a porta ouvindo e a regra de firewall de "
                  "ENTRADA, e as duas já estão de pé aqui.")
            saida("  Próximo passo: repetir isto em cada estação que for "
                  "exportar, ou concentrar o recebimento numa máquina só.")
            return
        if movimento.startswith("NADA CHEGOU"):
            saida("  O C-GET não existe neste daemon e o C-MOVE não entregou. "
                  "O pedido foi ACEITO, então o servidor está bem: o que falta "
                  "é desta ponta, e está escrito no degrau C-MOVE acima.")
            saida("  Medido em 10/09/2026: a causa mais provável é regra de "
                  "firewall de ENTRADA. Regra de BLOQUEIO vence regra de "
                  "permissão no Windows, então uma regra nova para a porta "
                  "pode não bastar se houver um bloqueio para o python.exe.")
            return
        # Até 11/09/2026 isto era hipótese ("é o cenário esperado se...") e
        # mandava PEDIR o AE de destino à TI. As duas coisas venceram em 10/09:
        # o C-GET foi medido morto e o destino RADIOTERAFICHA foi cadastrado.
        # Quem chega aqui só esqueceu de passar o destino — e abrir chamado
        # por isso seria gastar uma ida à toa.
        saida("  C-ECHO respondeu e o C-GET não — como medido em 10/09/2026: "
              "o C-GET não existe neste daemon, e a exportação é por C-MOVE.")
        saida("  O C-MOVE não foi tentado porque falta o AE de destino. Ele "
              "JÁ está cadastrado (RADIOTERAFICHA, apontando para a "
              "198.51.100.57): rodar de novo com --ae-destino RADIOTERAFICHA, "
              "ou pelo tools\\sondar_exportacao.bat, que já o passa.")
        return
    if achados.get("get"):
        saida("  C-GET FUNCIONA. É a melhor resposta possível: os arquivos "
              "voltam pela mesma conexão, e a exportação NÃO precisa de porta "
              "ouvindo, de regra de firewall para dentro, nem de AE de destino "
              "cadastrado.")
        saida("  Falta só apontar as variáveis nas estações que vão exportar.")


# As portas DICOM medidas no SRVARIADB em 04/09/2026, mais as do padrão. NÃO é
# palpite: saiu do ``descobrir_dicom.ps1``, que perguntou ao Windows quem
# ouvia o quê. E ela derrubou o palpite da literatura — 51402, dada como a do
# DB Daemon da Varian, não estava ouvindo naquela instalação.
#
# A 51405 entrou em 10/09/2026, e o motivo é o que esta lista tem de mais
# perigoso: medida NÃO quer dizer perene. A TI subiu naquele dia um serviço
# novo para o ISOCENTRO nessa porta, e a varredura rodada às 10:48 —
# depois do serviço estar no ar — passou por doze portas sem tocar na única
# que existe por nossa causa. Lista medida também vence; quando a TI disser
# uma porta nova, ela entra AQUI, senão a ferramenta que procura o daemon de
# consulta é cega para ele.
PORTAS_CANDIDATAS = (104, 106, 11112, 50501, 50502, 50503, 50504, 51402,
                     51403, 51404, 51405, 51601, 57345)

# Os AE Titles candidatos, e eles NÃO são chute: saíram das regras de firewall
# do SRVARIADB, lidas pelo ``descobrir_dicom.ps1`` em 04/09/2026. Cada regra
# nomeia o serviço da sua porta ("Varian DICOM Service ARIA" na 51404), e o
# nome bate com a lista de serviços do Windows ("Varian DB Service ARIA").
#
# A hipótese que eles testam é que o AE Title é esse sufixo — e testar é o
# ponto: `VMSDBD`, que a literatura dá como o AE do DB Daemon da Varian, foi
# recusado pelas nove portas com "Called AE title not recognised".
#
#   106   VMSFSD          file service        51601  HGS2677_RGSC  db
#   51403 ARIA2           file service        50501  H51B448       treatment
#   51404 ARIA            DB service  <== o de consulta
#   50502 TB_H194045      treatment           50503  H181196       treatment
#   50504 H194199         treatment           57345  VMSITD        treatment
#
# E ``isocentro`` (10/09/2026) é o AE que a TI deu para o serviço da
# 51405. Está aqui em minúsculas de propósito: AE Title é *case-sensitive*, e
# foi assim que eles escreveram. Sem ele, a varredura bateria na 51405 com seis
# nomes errados e relataria "Called AE title not recognised" — mandando
# corrigir aqui um nome que já estava certo.
AES_CANDIDATOS = ("ARIA", "ARIA2", "VMSFSD", "VMSITD", "HGS2677_RGSC",
                  "VMSDBD", "isocentro")


def _tcp_aberta(host: str, porta: int, prazo: float = 2.0) -> bool:
    """A porta aceita conexão? É o degrau de baixo, e ele é barato.

    Separado do DICOM de propósito: "não abriu" e "abriu e recusou a
    associação" são respostas diferentes — a primeira é firewall ou serviço
    parado, a segunda quer dizer que se achou um serviço DICOM.
    """
    import socket

    s = socket.socket()
    s.settimeout(prazo)
    try:
        s.connect((host, porta))
        return True
    except OSError:
        return False
    finally:
        s.close()


# A leitura do A-ASSOCIATE-RJ mora no ``dicom_rede``, não aqui. Ela nasceu
# nesta ferramenta e ficou só nela — e em 10/09/2026 isso cobrou: o app, que é
# quem fala com a clínica, devolvia "costuma ser AE Title ou porta bloqueada"
# enquanto a varredura, ao lado, sabia dizer QUAL dos dois AE o servidor tinha
# recusado. Regra escrita em dois lugares é regra que um dia discorda de si;
# aqui o risco era pior, porque a cópia boa era a que ninguém via.
_motivo_da_recusa = dicom_rede.motivo_da_recusa


def _falar_dicom(host: str, porta: int, ae_remoto: str, ae_local: str) -> str:
    """Propõe Verification E Query/Retrieve-Find, e conta o que foi aceito.

    **Os dois contextos juntos são o que identifica o DB Daemon.** As oito
    portas do SRVARIADB são do MESMO processo, e o nome do serviço não diz qual
    é qual: armazenamento, worklist, impressão e consulta moram lado a lado. Só
    o daemon de consulta aceita o contexto de Find — então a porta que aceitar
    Find é a que a exportação procura.

    Não transfere nada: abre a associação, lê o que foi acordado e libera.
    """
    from pynetdicom import AE
    from pynetdicom.sop_class import (
        PatientRootQueryRetrieveInformationModelFind as Find)
    from pynetdicom.sop_class import Verification

    ae = AE(ae_title=ae_local)
    ae.acse_timeout = 10
    ae.dimse_timeout = 10
    ae.network_timeout = 10
    ae.add_requested_context(Verification)
    ae.add_requested_context(Find)
    assoc = ae.associate(host, porta, ae_title=ae_remoto)
    if not assoc.is_established:
        # RECUSA e SILÊNCIO não são a mesma coisa, e confundi-los foi um
        # defeito de verdade: a primeira versão chamava toda associação
        # malsucedida de "fala DICOM", e num servidor cheio de porta aberta
        # (o SRVARIADB tem setenta) isso apontaria serviço DICOM em qualquer
        # uma. Pego no teste em 04/09/2026, quando a porta vizinha do SCP
        # falso estava ocupada por outro programa.
        #
        # ``is_rejected`` é o A-ASSOCIATE-RJ: só quem fala o protocolo o
        # devolve. Abortar ou emudecer é o que faz uma porta qualquer.
        if getattr(assoc, "is_rejected", False):
            # O MOTIVO da recusa, e não só "recusou". O DICOM distingue
            # "called AE title not recognized" (o AE de LÁ está errado — foi o
            # nosso chute) de "calling AE title not recognized" (o NOSSO não
            # está cadastrado), e as duas coisas pedem providências opostas:
            # a primeira eu resolvo aqui trocando um parâmetro, a segunda só a
            # Varian resolve. Sem ler isto, "recusou em todas" mandaria abrir
            # chamado que talvez nem fosse preciso.
            return "associação RECUSADA — " + _motivo_da_recusa(assoc)
        return "porta aberta, mas NÃO respondeu DICOM (não é serviço DICOM)"
    try:
        aceitos = [c.abstract_syntax for c in assoc.accepted_contexts]
        tem_find = any("1.2.840.10008.5.1.4.1.2.1.1" in (a or "")
                       for a in aceitos)
        if tem_find:
            return "ACEITOU Find — é um daemon de CONSULTA (candidato ao Q/R)"
        return (f"associação aceita, {len(aceitos)} contexto(s), SEM Find — "
                "armazenamento/worklist/impressão, não é o de consulta")
    finally:
        assoc.release()


def varrer(saida, host: str, portas, ae_remoto, ae_local: str) -> None:
    """Pergunta a cada porta o que ela é. Só abre e fecha associação.

    Existe porque a descoberta no servidor respondeu METADE: mostrou oito
    portas do mesmo processo da Varian, e nenhuma pista de qual delas é o DB
    Daemon. Ler mais arquivo não resolveria — a configuração dos serviços DICOM
    da Varian mora no banco do ARIA, não em disco.
    """
    # Um AE só ou vários: com vários, cada porta é tentada com cada um até
    # passar. Foi o que a rodada de 04/09/2026 pediu — as nove portas recusaram
    # o AE chamado, e descobrir QUAL nome cada uma aceita, uma rodada por nome,
    # seriam nove idas.
    aes = ([ae_remoto] if isinstance(ae_remoto, str)
           else [a for a in ae_remoto if a])
    saida("\n===== Varredura das portas =====")
    saida(f"  alvo {host}, como {ae_local!r}")
    saida(f"  AE remoto testado(s): {', '.join(aes)}")
    saida("  Só abre e fecha associação — nenhum dado é pedido nem trazido.")
    saida("")
    candidatas = []
    for porta in portas:
        if not _tcp_aberta(host, porta):
            saida(f"  {porta:<7} fechada")
            continue
        veredito, quem = "", ""
        for ae in aes:
            try:
                veredito = _falar_dicom(host, porta, ae, ae_local)
            except Exception as exc:  # noqa: BLE001
                veredito = f"abriu, mas falhou ao falar DICOM: {exc}"
            quem = ae
            # "Called ... not recognised" quer dizer que ESTE nome não é o
            # dela; qualquer outra resposta já é sobre a porta, e vale parar.
            if "Called AE title" not in veredito:
                break
        rotulo = f"[{quem}] " if len(aes) > 1 else ""
        saida(f"  {porta:<7} {rotulo}{veredito}")
        if "ACEITOU Find" in veredito:
            candidatas.append((porta, quem))
    saida("")
    if candidatas:
        for porta, ae in candidatas:
            saida(f"  CONSULTA em {porta}, com o AE {ae!r}")
        porta, ae = candidatas[0]
        saida("")
        saida("  O comando da sondagem completa:")
        saida(f"      tools\\sondar_dicom.bat --servidor {host}:{porta} "
              f"--ae-remoto {ae} --ae-local {ae_local}")
    else:
        saida("  Nenhuma aceitou Find. Leia a coluna da direita, porque as")
        saida("  três respostas pedem coisas diferentes:")
        saida("   * RECUSADA em todas — achou-se o servidor, e falta um AE")
        saida("     Title. QUAL deles a própria linha diz: 'called' é o do")
        saida("     ARIA (troque o --ae-remoto e rode de novo, resolve aqui);")
        saida("     'calling' é o NOSSO, e esse só a Varian cadastra;")
        saida("   * aceita mas SEM Find — o serviço de consulta está noutra")
        saida("     porta, ou parado;")
        saida("   * 'não respondeu DICOM' — a porta é de outro programa, e a")
        saida("     lista de candidatas precisa vir do descobrir_dicom.")


def sondar(saida, uid: str, pasta: str = "") -> int:
    saida("\n===== A sondagem =====")
    if not uid:
        saida("  Sem UID: só o C-ECHO tem resposta útil, e ele é o degrau que "
              "responde a pergunta mais provável (o AE Title é aceito?).")
    destino = Path(pasta) if pasta else Path(tempfile.mkdtemp(
        prefix="sonda_dicom_"))
    inicio = time.perf_counter()
    achados = dicom_rede.sondar(uid, destino)
    gasto = time.perf_counter() - inicio

    _linha(saida, "C-ECHO", achados.get("echo", ""))
    _linha(saida, "C-FIND", achados.get("find", ""))
    _linha(saida, "C-GET", achados.get("get", ""))
    _linha(saida, "C-MOVE", achados.get("move", ""))
    saida(f"\n  em {gasto:.1f} s")
    if achados.get("get", "").startswith(("0", "1", "2", "3", "4", "5", "6",
                                          "7", "8", "9")):
        # O arquivo é DADO DE PACIENTE. Dizer onde ele caiu é o que permite
        # apagá-lo — e a pasta temporária do sistema não é lugar que alguém
        # revise sozinho.
        saida(f"\n  ATENÇÃO: o C-GET gravou arquivo de paciente em {destino}")
        saida("  Apague depois de conferir. É dado clínico fora do ARIA.")
    _veredito(saida, achados)
    return 0 if achados.get("echo", "").startswith("ok") else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Descobre o que o DB Daemon do ARIA implementa "
                    "(C-ECHO/C-FIND/C-GET/C-MOVE). Só leitura.")
    p.add_argument("--servidor", default="",
                   help="host:porta do DB Daemon, só para esta execução")
    p.add_argument("--ae-remoto", default="",
                   help="AE Title do ARIA. Na varredura aceita vários, "
                        "separados por vírgula — cada porta é tentada com "
                        "cada um até passar")
    p.add_argument("--ae-local", default="",
                   help="AE Title desta estação (cadastrado no ARIA)")
    p.add_argument("--ae-destino", default="",
                   help="AE de destino do C-MOVE; sem ele o C-MOVE não é "
                        "tentado")
    p.add_argument("--uid", default="",
                   help="o SOPInstanceUID do plano a sondar. Sem isto, o "
                        "primeiro plano pronto do gatilho_db (exige o banco)")
    p.add_argument("--pasta", default="",
                   help="onde o C-GET grava; padrão é pasta temporária do "
                        "sistema — NUNCA o repositório")
    p.add_argument("--varrer", action="store_true",
                   help="pergunta a CADA porta candidata o que ela é, em vez "
                        "de sondar uma só — é o que identifica o daemon de "
                        "consulta quando o servidor tem oito portas DICOM")
    p.add_argument("--portas", default="",
                   help="as portas da varredura, separadas por vírgula "
                        "(padrão: as medidas no SRVARIADB mais as do padrão)")
    p.add_argument("-o", "--saida", default="",
                   help="grava o relatório neste arquivo, além de imprimir")
    a = p.parse_args(argv)

    linhas: list = []

    def saida(texto=""):
        print(texto)
        linhas.append(texto)

    codigo = 2
    try:
        saida(f"Sondagem do DICOM do ARIA — "
              f"{datetime.datetime.now():%d/%m/%Y %H:%M:%S}")
        _aplicar_argumentos(a)
        _mostrar_configuracao(saida)
        uid = a.uid.strip()
        if not uid:
            # O C-ECHO ANTES do banco, e é conserto de defeito medido em
            # 10/09/2026: o passo do UID fala com o variandw, e sem identidade
            # de rede ele falha e come o tempo da rodada. O C-ECHO não precisa
            # de conta do Windows nenhuma — o DICOM autentica por AE Title —,
            # e é ele que responde a pergunta mais provável ("cadastraram
            # nosso AE?"). Perguntando o banco primeiro, quem dava dois
            # cliques no sondar_exportacao.bat nunca chegava até aqui, e o
            # cabeçalho daquele arquivo prometia exatamente isso.
            if dicom_rede.configurado():
                saida("\n===== O degrau que não depende do banco =====")
                try:
                    saida(f"  C-ECHO: {dicom_rede.verificar()}")
                except Exception as exc:  # noqa: BLE001
                    saida(f"  C-ECHO: FALHOU — {exc}")
            saida("\n===== De onde sai o UID =====")
            uid = _uid_do_banco(saida)
        if a.varrer:
            # A varredura NÃO exige a porta: é ela que a descobre. Exigir o
            # ``configurado()`` aqui seria pedir a resposta como condição para
            # fazer a pergunta.
            host = (dicom_rede.servidor()[0]
                    or a.servidor.split(":")[0].strip())
            if not host:
                saida("\n  Falta o servidor: --servidor SRVARIADB")
                return 2
            portas = ([int(x) for x in a.portas.replace(";", ",").split(",")
                       if x.strip()] if a.portas else PORTAS_CANDIDATAS)
            if a.ae_remoto:
                aes = [x.strip() for x in a.ae_remoto.split(",") if x.strip()]
            else:
                aes = list(AES_CANDIDATOS)
            varrer(saida, host, portas, aes,
                   dicom_rede.ae_local() or "RADIOTERAFICHA")
            codigo = 0
        elif dicom_rede.configurado():
            codigo = sondar(saida, uid, a.pasta)
        else:
            saida("\n  Sondagem NÃO tentada — configure o que falta acima.")
            _veredito(saida, {"configurado": False})
        return codigo
    finally:
        # O arquivo é gravado ACONTEÇA O QUE ACONTECER: o console do runas
        # fecha, e o relatório que mais importa é justamente o da rodada que
        # deu errado. Mesma regra do mapear_gatilho.bat.
        if a.saida:
            destino = _destino_livre(Path(a.saida))
            destino.write_text("\n".join(linhas), encoding="utf-8")
            print(f"\nGravado em {destino}")


if __name__ == "__main__":
    raise SystemExit(main())
