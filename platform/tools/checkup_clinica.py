r"""Mede, numa rodada só, **tudo o que o ISOCENTRO precisa da rede** — e
devolve o pedido à TI já escrito.

**Por que ela existe.** Cada pergunta à infraestrutura virou, até aqui, um
chamado próprio: o AE Title num, a porta noutro, a permissão do banco num
terceiro. A resposta de um chegava depois de o outro estar fechado, e a ida
seguinte descobria a pergunta que faltava fazer. Em 10/09/2026 o C-MOVE fechou
o circuito **nesta** estação — e a pergunta que decide o custo de produção
("o cadastro do AE amarra IP?") não tinha sido feita, porque ninguém tinha uma
lista do que perguntar.

**São DOIS ambientes, e é essa a razão de o relatório começar dizendo quem ele
é:**

* **desenvolvimento** — esta máquina, fora do domínio (SSPI recusado), rodando
  do fonte, com o ``.venv`` e as ferramentas do ``tools/``;
* **clínica** — o ``.exe`` do share, aberto por cada estação, com identidade de
  domínio e sem Python nenhum.

"Funciona aqui" nunca disse o que vai funcionar lá: o banco só responde lá, o
firewall é de cada estação, e o AE Title é cadastrado por endereço. Um
relatório que não diga de **qual máquina, com qual IP e com qual conta** ele
saiu não se compara com o da outra ponta — e comparar as duas pontas é a coisa
toda.

**Só leitura, e isso é a característica principal.** Não altera firewall, nem
registro, nem serviço, nem configuração de estação. Escreve em exatamente dois
lugares, e os dois se apagam: um arquivo de teste em cada pasta que precisa
aceitar escrita (criado e removido na hora) e a pasta temporária onde o DICOM
que chegar é gravado — que o relatório NOMEIA, porque é dado de paciente e
alguém tem de apagá-lo.

**Cada bloco falha isolado.** O que se quer é o mapa do que funciona, não o
primeiro erro: banco fora do ar não pode impedir a medida do DICOM, que é
justamente a que exige a ida à clínica. E cada achado que gera pendência
carrega junto o **item de chamado** — o bloco final junta todos num texto
pronto para copiar, separado por ambiente e por fase.

Os blocos:

===  ===========================  ==================================
 #   bloco                        a pergunta que ele fecha
===  ===========================  ==================================
 1   identidade                   de qual máquina/IP/conta isto saiu
 2   configuração                 que variáveis valem, e de onde vieram
 3   pastas                       cada share: existe, lê, ESCREVE
 4   banco                        DNS->porta->driver->SSPI->tabela a tabela
 5   DICOM: associação            o C-ECHO passa? o cadastro amarrou IP?
 6   DICOM: consulta              acha o plano, e o que o estudo TEM
 7   DICOM: receptor              porta livre, firewall de entrada
 8   DICOM: o circuito            ``trazer()`` de verdade, ponta a ponta
 9   DICOM: a CT (``--ct``)       uma série: objetos, MB, segundos
10   DICOM: carga (``--carga``)   duas estações pedindo junto
11   impressão                    as impressoras que a estação enxerga
12   o pedido                     o chamado, montado do que falhou
===  ===========================  ==================================

Rodar pelo ``tools\checkup_clinica.bat``, sempre — o console do ``runas`` fecha
ao terminar, e o relatório que mais importa é o da rodada que deu errado.
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# EMPACOTADO, o ``__file__`` aponta para dentro do pacote e ``tools/`` não
# existe: o PyInstaller já montou o ``sys.path``, e mexer nele aqui só faria
# estrago. Do fonte, é este bloco que deixa o módulo achar o pacote e as outras
# ferramentas. A distinção é a mesma do ``isocentro/raiz.py``, e pelo
# mesmo motivo: caminho de arquivo não sai de ``__file__``.
EMPACOTADO = getattr(sys, "frozen", False)
if not EMPACOTADO:
    RAIZ = Path(__file__).resolve().parent.parent
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    sys.path.insert(0, str(RAIZ / "tools"))

from isocentro.dados import ambiente  # noqa: E402

# Os valores que a TI deu, MEDIDOS em 10/09/2026. Eles moravam no ``.bat``, que
# não existe na clínica: lá não há Python nem repositório, só o executável.
# Ficam aqui por necessidade, e com três travas contra virarem mentira calada:
# valem só quando a variável está VAZIA, o relatório ANUNCIA que está usando o
# padrão embutido, e a data sai junto — para que o dia em que a clínica mudar o
# endereço apareça na leitura, e não num "não respondeu" que parece servidor
# fora do ar.
#
# Isto NÃO é padrão no ``dicom_rede``, e a diferença é de propósito: o módulo
# do produto continua sem chutar endereço nenhum. Aqui é uma sonda de campo,
# e sonda que exige três parâmetros antes do primeiro diagnóstico é sonda que
# ninguém roda.
PADRAO_DA_CLINICA = {
    "ISOCENTRO_DICOM_SERVIDOR": "192.0.2.9:51405",
    "ISOCENTRO_DICOM_AE_REMOTO": "radioteraficha",
    "ISOCENTRO_DICOM_AE_LOCAL": "RADIOTERAFICHA",
    "ISOCENTRO_DB_SERVIDOR": "SRVINSIGHT",
}
MEDIDO_EM = "10/09/2026"

# O AE de destino que a TI JÁ cadastrou, e que o C-MOVE fechou em 10/09/2026.
# Mora só no TEXTO, não no ``PADRAO_DA_CLINICA``, e a diferença é de propósito:
# com ele lá, a rodada sem argumentos passaria a rodar os blocos 8 e 9, que
# trazem dado de paciente para uma pasta temporária — isso se pede na linha de
# comando, não acontece por padrão. Até 15/09/2026 a rodada sem argumentos
# pedia à TI para "cadastrar o AE de destino" (python01, 11/09): um item de
# chamado para o que existia havia um dia, e item que a TI já fez faz duvidar
# dos outros da mesma lista.
#
# Mas o cadastro amarra IP e porta: ele entrega numa máquina SÓ (em 10/09, a de
# desenvolvimento). O texto tem de dizer isso, porque a repetição disparada de
# outra estação é aceita e manda o dado do paciente para a cadastrada. O pedido
# que sobra — "para onde ele aponta?" — sai do bloco 8 dessa repetição, com o
# IP desta máquina na mensagem; sem argumentos não há como perguntá-lo direito.
AE_DESTINO_CADASTRADO = "RADIOTERAFICHA"

OK = "ok"
FALHA = "FALHOU"
AVISO = "aviso"
NAO = "--"

# As fases, e é por elas que o pedido à TI se divide. Pedir tudo de uma vez
# num chamado só faz o item mais caro segurar o mais barato; pedir na ordem
# do uso faz o chamado 2 chegar quando o 1 já estiver medido.
AGORA = "agora"          # sem isto o app não funciona hoje
PRODUCAO = "produção"    # sem isto ele funciona aqui e não na clínica inteira
DEPOIS = "depois"        # as frentes que já se sabe que virão


@dataclass
class Achado:
    """Uma medida, e — quando ela falta — o item de chamado que ela gera.

    O ``pedido`` viaja junto com a medida de propósito. Na primeira versão
    havia uma lista de pendências escrita à mão no fim do arquivo, e ela
    envelheceu em duas semanas: o degrau passou a medir outra coisa e o texto
    do chamado continuou pedindo a antiga. Item que não nasce da medida é item
    que um dia discorda dela.
    """

    rotulo: str
    estado: str
    detalhe: str = ""
    pedido: str = ""
    fase: str = AGORA


@dataclass
class Relatorio:
    linhas: list = field(default_factory=list)
    achados: list = field(default_factory=list)
    bloco: str = ""

    def diga(self, texto: str = "") -> None:
        print(texto)
        self.linhas.append(texto)

    def titulo(self, numero: int, texto: str) -> None:
        self.bloco = texto
        self.diga("")
        self.diga(f"===== {numero}. {texto} " + "=" * max(2, 46 - len(texto)))

    def medir(self, rotulo: str, estado: str, detalhe: str = "",
              pedido: str = "", fase: str = AGORA) -> Achado:
        a = Achado(rotulo, estado, detalhe, pedido, fase)
        self.achados.append(a)
        marca = {OK: " ok ", FALHA: "FALHA", AVISO: "AVISO", NAO: " -- "}[estado]
        self.diga(f"  [{marca:^5}] {rotulo:<34} {detalhe}")
        return a

    def nota(self, texto: str) -> None:
        for linha in texto.strip().splitlines():
            self.diga(f"          {linha.strip()}")

    @property
    def falhou(self) -> bool:
        return any(a.estado == FALHA for a in self.achados)


def _console_em_utf8() -> None:
    """Sem isto, o relatório MORRE no meio, e cada bloco morre sozinho.

    Medido em 10/09/2026, rodando o executável recém-gerado: três blocos
    saíram como ``estourou: UnicodeEncodeError`` porque o console do Windows
    abre em code page 850 e o Python escolhe cp1252 para a saída. O ``.bat``
    resolvia com ``chcp 65001`` e ``PYTHONIOENCODING`` — e o ``.bat`` é
    justamente o que não existe na clínica.

    ``errors="replace"`` é o cinto de segurança: mesmo que a troca de code page
    falhe (console redirecionado, terminal antigo), um caractere impossível
    vira "?" em vez de derrubar o bloco. Relatório com um "?" no meio ainda é
    relatório; relatório que para na linha 40 custa a ida.
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
            # que a suíte faz). Não é problema: ali a codificação já é a do
            # teste, e o que importa é não estourar tentando.
            pass


def _onde_gravar(nome: str) -> Path:
    """O relatório cai ao lado de QUEM RODOU, e nunca por cima do anterior.

    Empacotado, é a pasta do executável (``raiz.pasta_do_app``) — quem rodou o
    exe numa estação procura o arquivo ali, não numa subpasta que ele não sabe
    que existe. Do fonte, é ``relatorios_ferramentas/``, que é onde as outras
    ferramentas do projeto já escrevem e que o ``.gitignore`` cobre.

    O nome ganha data e hora quando já existe um: uma segunda ida à clínica é
    barata, e o relatório da primeira, não. Custou o de 01/09/2026 — a rodada
    boa foi apagada vinte minutos depois por uma que só conseguiu escrever a
    recusa de SSPI.
    """
    from isocentro import raiz  # noqa: PLC0415

    caminho = Path(nome)
    if caminho.parent == Path("."):
        pasta = (Path(raiz.pasta_do_app()) if EMPACOTADO
                 else Path(raiz.raiz_do_projeto()) / "relatorios_ferramentas")
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / caminho.name
    if not caminho.exists():
        return caminho
    quando = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return caminho.with_name(f"{caminho.stem}_{quando}{caminho.suffix}")


def _ps(comando: str, prazo: int = 25) -> str:
    """Uma pergunta ao PowerShell. Erro vira texto, nunca exceção.

    Tudo o que este arquivo pergunta ao Windows é opcional: perfil de rede,
    firewall e impressora são contexto para ler o resto, e nenhum deles vale
    derrubar a medida do DICOM, que é a que exigiu a ida até a clínica.
    """
    if os.name != "nt":
        return "(não é Windows)"
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True, text=True, timeout=prazo,
            encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return f"(não deu para perguntar ao Windows: {exc})"
    return (r.stdout or r.stderr or "").strip()


def _ip_de_saida(host: str, porta: int) -> str:
    """Por qual IP esta máquina sairia para falar com aquele host.

    **É o número que a TI cadastra**, e ele não é "o IP da máquina": estação
    com VPN, com duas placas ou com Hyper-V tem vários, e quem sai para o ARIA
    é um só. Perguntar ao Windows qual é a interface de saída responde o que
    ``ipconfig`` não responde sem interpretação.

    ``SOCK_DGRAM`` + ``connect`` não põe pacote nenhum na rede — só faz o
    sistema escolher a rota. Funciona com o serviço no ar ou fora dele.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, porta or 80))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


def _tcp_aberta(host: str, porta: int, prazo: float = 3.0) -> tuple[bool, str]:
    """A porta aceita conexão? Separa firewall de serviço parado.

    "Não abriu" e "abriu e recusou a associação" são respostas diferentes e
    mandam ligar para pessoas diferentes: a primeira é rota/firewall/serviço, a
    segunda já é conversa DICOM.
    """
    s = socket.socket()
    s.settimeout(prazo)
    inicio = time.perf_counter()
    try:
        s.connect((host, porta))
        return True, f"aberta em {time.perf_counter() - inicio:.2f} s"
    except OSError as exc:
        gasto = time.perf_counter() - inicio
        # Recusa e silêncio são causas diferentes: a primeira é o sistema do
        # outro lado dizendo "não há nada nesta porta"; a segunda é pacote
        # sumindo no caminho, que é a assinatura do firewall. Sem esta
        # distinção as duas saíam como "fechada", e a providência de cada uma
        # é oposta.
        #
        # Separadas pelo TIPO da exceção, não pelo relógio. A primeira versão
        # chamava de recusa o que voltasse antes de 80% do prazo — mas a recusa
        # no Windows NÃO é imediata: a pilha repete o SYN depois do RST e leva
        # 2,04 s (medido em 15/09/2026), contra um corte de 2,4 s. Com a
        # latência de uma VPN por cima, porta sem serviço sairia como firewall.
        # E qualquer outro OSError (nome que não resolve, rede inalcançável)
        # não é nenhum dos dois: sai com a mensagem dele, sem palpite.
        if isinstance(exc, ConnectionRefusedError):
            jeito = (f"recusada em {gasto:.1f} s "
                     "(não há serviço nessa porta)")
        elif isinstance(exc, TimeoutError):
            jeito = f"sem resposta em {gasto:.1f} s (assinatura de firewall)"
        else:
            jeito = f"não abriu em {gasto:.1f} s: {exc}"
        return False, f"{jeito} — {type(exc).__name__}"
    finally:
        s.close()


# ---------------------------------------------------------------- bloco 1

def bloco_identidade(rel: Relatorio, cfg) -> None:
    """Quem está rodando isto, de onde, e como.

    Primeiro bloco porque é o que torna o relatório comparável com o da outra
    estação. Sem o IP de saída e a conta, "o C-ECHO passou" não diz se passou
    porque o AE está cadastrado para todo mundo ou porque **esta** máquina foi
    liberada na mão — e essa é a diferença entre um chamado e vinte.
    """
    rel.titulo(1, "Quem sou eu, e de onde estou falando")

    from isocentro import raiz  # noqa: PLC0415

    maquina = socket.gethostname()
    conta = getpass.getuser()
    dominio = os.environ.get("USERDNSDOMAIN") or os.environ.get("USERDOMAIN") or ""
    empacotado = raiz.empacotado()

    rel.medir("máquina", OK, maquina)
    rel.medir("conta do Windows", OK, f"{dominio}\\{conta}" if dominio else conta)
    rel.medir("como está rodando", OK,
              ".exe empacotado" if empacotado else f"do fonte, Python {sys.version.split()[0]}")
    rel.medir("pasta do app (grava aqui)", OK, str(raiz.pasta_do_app()))

    host, porta = cfg.dicom_host, cfg.dicom_porta
    if host:
        ip = _ip_de_saida(host, porta)
        rel.medir("IP de saída para o ARIA", OK if ip else AVISO,
                  f"{ip or '(não deu para determinar)'}  -> falando com {host}")
        rel.nota("""
            É ESTE número que a TI cadastra, e não "o IP da máquina": estação
            com VPN ou segunda placa tem vários, e para o ARIA sai um só.
            Comparar este campo entre duas estações é o que responde se o
            cadastro do AE amarrou endereço.
        """)
    else:
        rel.medir("IP de saída para o ARIA", NAO, "sem servidor DICOM configurado")

    perfil = _ps("Get-NetConnectionProfile | "
                 "Select-Object -ExpandProperty NetworkCategory")
    publico = "Public" in perfil
    rel.medir("perfil da rede do Windows", AVISO if publico else OK,
              perfil.replace("\n", ", ") or "(não respondeu)")
    if publico:
        rel.nota("""
            Perfil Público é o mais restritivo, e foi ele que escondeu o
            problema em 10/09/2026: as regras de ENTRADA que valem são as
            desse perfil. Regra criada só para Privado não vale aqui.
        """)

    for modulo in ("pydicom", "pynetdicom", "pyodbc"):
        try:
            m = __import__(modulo)
            rel.medir(f"biblioteca {modulo}", OK,
                      getattr(m, "__version__", None)
                      or getattr(m, "version", "(sem versão)"))
        except Exception as exc:  # noqa: BLE001
            # No .exe as três viajam dentro do pacote; do fonte, no .venv. Falta
            # aqui quer dizer coisas diferentes em cada ambiente, e as duas são
            # nossas — nunca da TI.
            rel.medir(f"biblioteca {modulo}", FALHA, str(exc)[:80],
                      pedido="" if empacotado else "")


# ---------------------------------------------------------------- bloco 2

# As variáveis que decidem com quem o app fala. A lista é a do
# ``docs/AMBIENTE.md``; o que muda aqui é a coluna do meio — se a ausência
# dela é falha, aviso ou indiferente —, porque nem toda variável vazia é
# problema: quase todas têm padrão ao lado do programa, e só as de REDE não
# têm como ter.
# Quais valores desta rodada vieram do padrão embutido, e não da estação. O
# bloco 2 marca cada um: variável que "está preenchida" sem ninguém a ter
# configurado é a origem clássica do chamado que não existe — alguém aponta a
# estação para outro servidor e não entende por que nada muda.
_DO_PADRAO_EMBUTIDO: set = set()


def _aplicar_padrao_da_clinica() -> None:
    """Só onde está VAZIO, e sempre anunciado no relatório.

    Existe porque o executável não tem `.bat` ao lado para definir estas quatro
    variáveis, e sonda que exige três parâmetros antes do primeiro diagnóstico
    é sonda que ninguém roda numa estação da clínica. Quem já tiver a estação
    configurada vence isto — e quem quiser medir a estação CRUA passa
    ``--sem-padrao``.
    """
    for nome, valor in PADRAO_DA_CLINICA.items():
        if not ambiente.ler(nome):
            os.environ[ambiente.nome_novo(nome)] = valor
            _DO_PADRAO_EMBUTIDO.add(nome)


VARIAVEIS = (
    ("ISOCENTRO_DICOM_SERVIDOR", FALHA, "host:porta do DB Daemon do ARIA"),
    ("ISOCENTRO_DICOM_AE_REMOTO", FALHA, "AE Title do ARIA"),
    ("ISOCENTRO_DICOM_AE_LOCAL", FALHA, "AE Title DESTA estação, cadastrado lá"),
    ("ISOCENTRO_DICOM_AE_DESTINO", AVISO, "destino do C-MOVE (sem ele, C-GET)"),
    ("ISOCENTRO_DICOM_PORTA_ESCUTA", AVISO, "porta em que esta ponta ouve"),
    ("ISOCENTRO_DB_SERVIDOR", AVISO, "data warehouse (vazio = só relatórios)"),
    ("ISOCENTRO_DB_BANCO", AVISO, "o banco (padrão variandw)"),
    ("ISOCENTRO_EXPORTACAO", AVISO, "onde a varredura grava os planos"),
    ("ISOCENTRO_CAPA_DIR", AVISO, "relatórios exportados (reserva da capa)"),
    ("ISOCENTRO_ESPELHO", AVISO, "espelho local do banco"),
    ("ISOCENTRO_CONFIG", AVISO, "configuração do serviço"),
    ("ISOCENTRO_USERS_DIR", AVISO, "usuários e senhas"),
    ("ISOCENTRO_LOG_DIR", AVISO, "histórico de uso (compartilhado)"),
    ("ISOCENTRO_CORRECOES", AVISO, "correções de cadastro (compartilhado)"),
    ("ISOCENTRO_BACKUP_DIR", AVISO, "backups"),
    ("ISOCENTRO_SIMULACOES", AVISO, "raiz das simulações"),
    ("ISOCENTRO_DADOS_FEIXE", AVISO, "tabelas de TMR/Scp do cálculo paralelo"),
    ("ISOCENTRO_BANCO_LOCAL", NAO, "banco gravado — só em máquina de trabalho"),
)


def bloco_configuracao(rel: Relatorio, cfg) -> None:
    """O que está valendo, e **de onde veio**.

    A segunda coluna é a que resolve o chamado que não existe: "apontei a
    pasta e não mudou nada" é quase sempre uma variável de estação vencendo a
    configuração do serviço, e sem a origem escrita não há como descobrir isso
    de fora. É a mesma razão do ``origem_da_pasta`` na tela.
    """
    rel.titulo(2, "A configuração desta máquina, e quem venceu")
    faltando = []
    for nome, gravidade, para_que in VARIAVEIS:
        valor = ambiente.ler(nome)
        veio = ambiente.qual_valeu(nome)
        if valor:
            if nome in _DO_PADRAO_EMBUTIDO:
                rel.medir(nome, AVISO,
                          f"{valor}   [PADRÃO EMBUTIDO, medido em {MEDIDO_EM} "
                          "— esta estação não define]")
                continue
            rel.medir(nome, OK, f"{valor}   [por {veio}]" if veio else valor)
            continue
        if gravidade == NAO:
            rel.medir(nome, NAO, f"vazio — {para_que}")
            continue
        faltando.append(nome)
        rel.medir(nome, gravidade, f"vazio — {para_que}")
    if _DO_PADRAO_EMBUTIDO:
        rel.nota(f"""
            {len(_DO_PADRAO_EMBUTIDO)} valor(es) vieram do padrão EMBUTIDO no
            executável, medido em {MEDIDO_EM}: nenhuma estação os define. Se a
            TI tiver mudado endereço ou AE Title desde então, é aqui que o
            relatório mente — e o sintoma seria um "não respondeu" com cara de
            servidor fora do ar. Para medir a estação crua: --sem-padrao.
        """)
    if faltando:
        rel.nota(f"""
            {len(faltando)} vazia(s). As de DICOM não têm padrão possível —
            endereço e AE Title são desta clínica, e chutar faria "não
            respondeu" parecer servidor fora do ar. As demais caem no padrão
            ao lado do programa, e vazio ali quer dizer "cada estação guarda
            a sua" — que é o que a aba Serviço existe para resolver.
        """)


# ---------------------------------------------------------------- bloco 3

def _pastas_do_app() -> list:
    """Cada pasta que o app usa, pelo caminho que o PRÓPRIO app calcula.

    Nunca por caminho remontado aqui: a precedência (sessão -> variável ->
    serviço -> padrão) mora nos módulos, e uma segunda cópia dela nesta
    ferramenta acabaria discordando da primeira justamente na estação em que
    alguém configurou algo diferente — que é a única em que isto importa.
    """
    pastas = []

    def tentar(rotulo, funcao, escrita: bool):
        try:
            alvo = Path(str(funcao()))
        except Exception as exc:  # noqa: BLE001
            pastas.append((rotulo, None, escrita, str(exc)[:90]))
            return
        pastas.append((rotulo, alvo, escrita, ""))

    from isocentro.banco import capa_dados, capa_espelho  # noqa: PLC0415
    from isocentro.dados import (auth, config_servico,  # noqa: PLC0415
                                      correcoes, historico)
    from isocentro.dominio import gatilho  # noqa: PLC0415

    tentar("relatórios da capa (lê)", capa_dados.pasta_dados, False)
    tentar("exportação automática (grava)", gatilho.pasta_destino, True)
    tentar("espelho do banco (grava)", capa_espelho.pasta, True)
    tentar("usuários e senhas (grava)",
           lambda: auth.caminho_usuarios().parent, True)
    tentar("histórico de uso (grava)",
           lambda: historico.caminho_log().parent, True)
    tentar("correções de cadastro (grava)",
           lambda: correcoes.caminho().parent, True)
    tentar("config. do serviço (grava)",
           lambda: config_servico.caminho().parent, True)
    return pastas


def bloco_pastas(rel: Relatorio, cfg) -> None:
    """Existe, lê e — onde precisa — **escreve**.

    Escrever de verdade, e não só olhar o atributo: em share do Windows a
    permissão efetiva não se lê do lado do cliente. A pasta pode listar,
    parecer aberta, e recusar a criação do arquivo — e o primeiro a descobrir
    isso seria o físico salvando a ficha do paciente na frente dele.

    O arquivo de teste nasce e morre nesta função. Se ele sobreviver a uma
    queda no meio, o nome diz de quem é e pode ser apagado à mão.
    """
    rel.titulo(3, "As pastas: existe, lê, escreve")
    for rotulo, alvo, precisa_escrever, erro in _pastas_do_app():
        if alvo is None:
            rel.medir(rotulo, FALHA, f"não deu para calcular o caminho: {erro}")
            continue
        unc = str(alvo).startswith("\\\\")
        etiqueta = f"{alvo}{'  [share de rede]' if unc else ''}"
        if not alvo.exists():
            # Pasta que não existe NÃO é falha por si: quase todas nascem no
            # primeiro uso. Falha é a que está apontada para um share que não
            # responde — e essas duas se distinguem pelo caminho ser UNC.
            rel.medir(rotulo, FALHA if unc else AVISO,
                      f"não existe: {etiqueta}",
                      pedido=(f"criar e liberar a pasta {alvo} para os "
                              "usuários do ISOCENTRO" if unc else ""),
                      fase=PRODUCAO)
            continue
        try:
            list(alvo.iterdir())
        except Exception as exc:  # noqa: BLE001
            rel.medir(rotulo, FALHA, f"existe e NÃO deixa listar: {exc}"[:110],
                      pedido=f"dar permissão de LEITURA em {alvo}",
                      fase=PRODUCAO)
            continue
        if not precisa_escrever:
            rel.medir(rotulo, OK, f"lê — {etiqueta}")
            continue
        teste = alvo / ".checkup_isocentro.tmp"
        try:
            teste.write_text("checkup", encoding="utf-8")
            teste.read_text(encoding="utf-8")
            teste.unlink()
        except Exception as exc:  # noqa: BLE001
            rel.medir(rotulo, FALHA, f"lê mas NÃO escreve: {exc}"[:110],
                      pedido=(f"dar permissão de ESCRITA em {alvo} para quem "
                              "usa o ISOCENTRO"),
                      fase=PRODUCAO)
            continue
        try:
            livre = shutil.disk_usage(alvo).free / 1e9
            espaco = f", {livre:.0f} GB livres"
        except Exception:  # noqa: BLE001
            espaco = ""
        rel.medir(rotulo, OK, f"lê e escreve — {etiqueta}{espaco}")
        _escrita_de_verdade(rel, rotulo, alvo, unc)


def _escrita_de_verdade(rel: Relatorio, rotulo: str, alvo: Path,
                        unc: bool) -> None:
    """Escrever um arquivo não é o mesmo que o app conseguir gravar ali.

    O app não escreve por cima: escreve num temporário ao lado e **substitui**
    (``os.replace``), que é o que impede um índice pela metade quando alguém
    desliga a estação no meio. Em SMB essa substituição é a operação que falha
    quando falha — permissão de criar sem permissão de **apagar** é uma
    combinação comum em share, e ela deixa escrever o temporário e recusa a
    troca. O sintoma seria um `registro_fichas.json.tmp` acumulando ao lado do
    índice, sem erro nenhum na tela.

    A latência entra junto porque é medida gratuita aqui e cara depois: o
    índice é lido a cada ficha, e share lento vira tela travada — que chega
    como "o programa está pesado", não como "a rede está lenta".
    """
    alvo_final = alvo / ".checkup_isocentro.json"
    temporario = alvo / ".checkup_isocentro.json.tmp"
    try:
        alvo_final.write_text("{}", encoding="utf-8")
        temporario.write_text('{"novo": 1}', encoding="utf-8")
        inicio = time.perf_counter()
        os.replace(temporario, alvo_final)
        gasto = time.perf_counter() - inicio
        alvo_final.read_text(encoding="utf-8")
        rel.medir("  -> substituição atômica", OK,
                  f"{gasto * 1000:.0f} ms" +
                  ("  (share: é o número que decide se a tela trava)"
                   if unc else ""))
    except Exception as exc:  # noqa: BLE001
        rel.medir("  -> substituição atômica", FALHA, str(exc)[:90],
                  pedido=(f"em {alvo}, a conta precisa poder CRIAR e APAGAR "
                          "arquivo, não só criar: o app grava num temporário e "
                          "substitui, para não deixar índice pela metade"),
                  fase=PRODUCAO)
    finally:
        temporario.unlink(missing_ok=True)
        alvo_final.unlink(missing_ok=True)

    # MAX_PATH: pasta de simulação leva nome de paciente, e em UNC o prefixo já
    # come 60 caracteres antes de o nome começar. Estourar 260 dá "caminho não
    # encontrado" numa pasta que existe — e só para ALGUNS pacientes, que é o
    # defeito mais difícil de acreditar.
    if unc and len(str(alvo)) > 150:
        rel.medir("  -> comprimento do caminho", AVISO,
                  f"{len(str(alvo))} caracteres — sobram "
                  f"{260 - len(str(alvo))} para nome de paciente e arquivo",
                  pedido=("encurtar o caminho do share, ou habilitar caminhos "
                          "longos na política de grupo: em UNC o limite de 260 "
                          "caracteres aparece só para os nomes mais compridos"),
                  fase=PRODUCAO)


# ---------------------------------------------------------------- bloco 4

# As tabelas que o app lê HOJE, e as que ele vai ler. A divisão importa: a
# primeira lista bloqueia a Capa, que está em produção; a segunda bloqueia as
# duas frentes paradas desde 19/08/2026 (a aba do radioterapeuta e o painel de
# estado), e nenhuma linha de SQL delas deve ser escrita antes de a permissão
# existir — consulta montada sem poder rodar é consulta que ninguém conferiu.
#
# Tiradas do próprio código (``grep FROM/JOIN`` em capa_db, gatilho_db e
# tratamento_db), não de memória: lista escrita à mão envelhece na primeira
# consulta nova, e o sintoma seria uma permissão faltando que o checkup jura
# que está sobrando.
TABELAS_HOJE = (
    "DWH.DimPatient",
    "DWH.DimCourse",
    "DWH.DimPlan",
    "DWH.DimPrescription",
    "DWH.DimPrescriptionAnatomy",
    "DWH.DimPrescriptionProperty",
    "DWH.FactPatientPrescription",
    "DWH.FactPatientDiagnosis",
    "DWH.DimDiagnosisCode",
    "DWH.DimDoctor",
    "DWH.DimPatientDoctor",
    "DWH.DimPatientPhoto",
    "DWH.FactPatientPayor",
    "DWH.DimPayor",
    "DWH.DimLookup",
)
TABELAS_DEPOIS = (
    ("DWH.FactTreatmentHistory", "a fração entregue — aba Ficha Virtual"),
    ("DWH.DimMachine", "em qual acelerador tratou"),
    ("DWH.DimActivity", "as atividades/tarefas do ARIA"),
    ("DWH.FactActivity", "idem — o fato das atividades"),
    ("DWH.DimUser", "quem tratou, quem liberou"),
)


def _conexao_banco(rel: Relatorio, cfg):
    """Os degraus até a conexão, cada um com a cara da própria falha.

    Ordem deliberada e ela é o diagnóstico: DNS antes de porta, porta antes de
    driver, driver antes de login. Sem isso, "não conecta" chega à TI como uma
    frase só, e as quatro causas pedem quatro pessoas diferentes.
    """
    try:
        import pyodbc  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        rel.medir("pyodbc", FALHA, str(exc)[:90])
        return None
    import diagnostico_db as ddb  # noqa: PLC0415

    servidor = cfg.db_servidor or ddb.SERVIDOR_PADRAO
    banco = cfg.db_banco or ddb.BANCO_PADRAO

    try:
        ip = socket.gethostbyname(servidor.split("\\")[0])
        rel.medir("DNS do servidor", OK, f"{servidor} -> {ip}")
    except Exception as exc:  # noqa: BLE001
        rel.medir("DNS do servidor", FALHA, f"{servidor}: {exc}"[:90],
                  pedido=(f"confirmar o nome do servidor do data warehouse "
                          f"(tentei {servidor}) e se esta estação o resolve"))
        return None

    aberta, jeito = _tcp_aberta(servidor.split("\\")[0], cfg.db_porta)
    rel.medir(f"porta {cfg.db_porta} (SQL Server)", OK if aberta else FALHA,
              jeito,
              pedido=("" if aberta else
                      f"liberar a saída TCP {cfg.db_porta} desta estação para "
                      f"{servidor}"))
    if not aberta:
        return None

    # A lista é a DO APP (``capa_db.DRIVERS``), e não uma cópia daqui. Medido no
    # clinica-python01 em 10/09/2026: só havia o "SQL Server" cru, este bloco
    # desistiu por não achar um dos "bons" — e o gatilho_db, três blocos
    # abaixo, conectou e achou dois planos pelo mesmo banco. O inventário de
    # permissões, que é a medida mais cara de conseguir, foi perdido numa
    # máquina que TINHA acesso. Duas listas de driver se afastam do mesmo jeito
    # que duas listas de hiddenimports.
    from isocentro.banco import capa_db  # noqa: PLC0415

    instalados = set(pyodbc.drivers())
    drivers = [d for d in capa_db.DRIVERS if d in instalados]
    if not drivers:
        rel.medir("driver ODBC", FALHA,
                  f"nenhum instalado; há: {', '.join(instalados) or 'nenhum'}"[:110],
                  pedido="instalar o ODBC Driver 18 for SQL Server na estação",
                  fase=PRODUCAO)
        return None
    if drivers[0] in ddb.DRIVERS_BONS:
        rel.medir("driver ODBC", OK, drivers[0])
    else:
        # O antigo CONECTA, e com acentuação correta — medido contra o banco
        # real. Não é impedimento; é dívida: ele é depreciado e tropeça em TLS
        # novo. Vira pedido, e a medição continua.
        rel.medir("driver ODBC", AVISO,
                  f"só o antigo: {drivers[0]} — conecta, mas é depreciado",
                  pedido=("instalar o ODBC Driver 18 for SQL Server: o app "
                          "funciona com o 'SQL Server' de 2000, que é o que há "
                          "hoje, mas ele é depreciado e tropeça em TLS novo"),
                  fase=PRODUCAO)

    try:
        cx = ddb._conectar(pyodbc, drivers[0], servidor, banco, cfg.db_porta)
    except Exception as exc:  # noqa: BLE001
        texto = str(exc)
        # Os três desfechos são problemas DIFERENTES, e confundi-los é o que
        # faz a conversa com a TI durar dias. SSPI não é falta de permissão: é
        # a estação não conseguir provar QUEM é — e nesta máquina de
        # desenvolvimento, fora do domínio, é o desfecho ESPERADO.
        if "SSPI" in texto or "Kerberos" in texto:
            rel.medir("autenticação (SSPI)", AVISO, texto.strip()[:100])
            rel.nota("""
                Isto NÃO é falta de permissão, é identidade — e numa máquina
                fora do domínio é o resultado normal. Nada aqui diz sobre a
                liberação do chamado: refazer de uma estação da clínica, ou
                pelo .bat com runas /netonly.
            """)
        elif "Login failed" in texto:
            rel.medir("autenticação", FALHA, texto.strip()[:100],
                      pedido=(f"liberar LEITURA no banco {banco} de {servidor} "
                              "para os usuários do ISOCENTRO (de "
                              "preferência por grupo do AD, não conta a conta)"))
        elif "Cannot open database" in texto:
            rel.medir("acesso ao banco", FALHA, texto.strip()[:100],
                      pedido=(f"a liberação precisa ser no '{banco}' (o data "
                              "warehouse), não só no ARIA clínico"))
        else:
            rel.medir("conexão", FALHA, texto.strip()[:110])
        return None
    return cx


def bloco_banco(rel: Relatorio, cfg) -> None:
    """Do DNS até a permissão, tabela a tabela.

    O inventário por tabela existe porque permissão no banco costuma vir pela
    metade: o login abre, a Capa funciona, e a consulta da fração entregue
    devolve "Invalid object name" meses depois — que se parece com erro de
    nome de tabela e não com falta de acesso. Perguntando uma a uma, o chamado
    já sai com a lista.
    """
    rel.titulo(4, "O banco: da rota à permissão, tabela a tabela")
    cx = _conexao_banco(rel, cfg)
    if cx is None:
        rel.medir("inventário de tabelas", NAO, "sem conexão — nada perguntado")
        return
    try:
        cur = cx.cursor()
        try:
            cur.execute("SELECT SUSER_SNAME(), DB_NAME()")
            login, db = cur.fetchone()
            rel.medir("conectado", OK, f"o servidor me vê como {login}, em {db}")
        except Exception as exc:  # noqa: BLE001
            rel.medir("conectado", AVISO, f"não consegui me identificar: {exc}"[:90])

        # O RELÓGIO. A varredura do gatilho pergunta "o que ficou pronto
        # desde ontem", e a data de corte é montada com a hora DESTA máquina
        # contra dados carimbados pela do servidor. Estação atrasada meia hora
        # não dá erro nenhum: ela simplesmente deixa de ver o plano que acabou
        # de ficar pronto, e o físico conclui que a exportação automática não
        # funciona.
        try:
            cur.execute("SELECT GETDATE()")
            do_servidor = cur.fetchone()[0]
            daqui = datetime.datetime.now()
            diferenca = abs((do_servidor - daqui).total_seconds())
            rel.medir("relógio contra o do servidor",
                      OK if diferenca < 120 else AVISO,
                      f"{diferenca:.0f} s de diferença",
                      pedido=("" if diferenca < 120 else
                              f"o relógio desta estação está {diferenca:.0f} s "
                              "fora do servidor — conferir a sincronização de "
                              "hora (NTP) do domínio"),
                      fase=PRODUCAO)
        except Exception as exc:  # noqa: BLE001
            rel.medir("relógio contra o do servidor", AVISO, str(exc)[:80])

        negadas = []
        for tabela in TABELAS_HOJE:
            try:
                cur.execute(f"SELECT TOP 1 1 FROM {tabela}")
                cur.fetchall()
                rel.medir(tabela, OK, "lê")
            except Exception as exc:  # noqa: BLE001
                negadas.append(tabela)
                rel.medir(tabela, FALHA, str(exc).strip()[:90])
        if negadas:
            rel.medir("as tabelas de HOJE", FALHA,
                      f"{len(negadas)} sem acesso",
                      pedido=("dar SELECT nas tabelas do schema DWH que a capa "
                              "usa: " + ", ".join(negadas)))

        faltam_depois = []
        for tabela, para_que in TABELAS_DEPOIS:
            try:
                cur.execute(f"SELECT TOP 1 1 FROM {tabela}")
                cur.fetchall()
                rel.medir(tabela, OK, f"lê — {para_que}")
            except Exception as exc:  # noqa: BLE001
                faltam_depois.append(tabela)
                rel.medir(tabela, AVISO, f"{para_que}: {str(exc).strip()[:60]}")
        if faltam_depois:
            rel.medir("as tabelas das PRÓXIMAS frentes", AVISO,
                      f"{len(faltam_depois)} sem acesso",
                      pedido=("dar SELECT também em: " + ", ".join(faltam_depois)
                              + " — é o que a aba Ficha Virtual (fração "
                              "entregue, acelerador, quem tratou) vai ler"),
                      fase=DEPOIS)

        try:
            cur.execute("SELECT DISTINCT permission_name "
                        "FROM fn_my_permissions(NULL, 'DATABASE') "
                        "WHERE permission_name IN "
                        "('SELECT','INSERT','UPDATE','DELETE','EXECUTE','ALTER')")
            tem = sorted(p[0] for p in cur.fetchall())
            escrita = [p for p in tem if p != "SELECT"]
            # Acesso a MAIS é achado, não conforto. O app nunca escreve neste
            # banco — é regra do projeto —, e um login com UPDATE no sistema
            # clínico é risco que alguém aceitou sem saber que aceitou.
            rel.medir("é somente leitura?", AVISO if escrita else OK,
                      ", ".join(tem) or "(nenhuma no nível do banco)",
                      pedido=("reduzir a permissão a SELECT — o app nunca "
                              "escreve no data warehouse" if escrita else ""),
                      fase=PRODUCAO)
        except Exception as exc:  # noqa: BLE001
            rel.medir("é somente leitura?", AVISO, str(exc)[:90])
    finally:
        cx.close()


# ---------------------------------------------------------------- bloco 5

def bloco_dicom_associacao(rel: Relatorio, cfg) -> None:
    """O C-ECHO, e a pergunta que decide o custo de produção.

    O C-ECHO responde "o ARIA aceita este AE Title vindo daqui?". O que ele
    **não** responde sozinho é se o cadastro amarrou endereço — e isso decide
    entre um chamado e um por estação. A medida é comparar este bloco entre
    duas máquinas; o relatório escreve a instrução para que a comparação
    aconteça em vez de ser lembrada.
    """
    from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: PLC0415

    rel.titulo(5, "DICOM: a associação (C-ECHO)")
    if not dicom_rede.configurado():
        rel.medir("configuração do DICOM", FALHA,
                  dicom_rede.motivo_indisponivel()[:100])
        return
    host, porta = dicom_rede.servidor()
    aberta, jeito = _tcp_aberta(host, porta)
    rel.medir(f"porta {porta} de {host}", OK if aberta else FALHA, jeito,
              pedido=("" if aberta else
                      f"liberar a SAÍDA TCP {porta} desta estação para {host} "
                      "(o serviço de consulta DICOM do ARIA)"))
    if not aberta:
        return
    try:
        rel.medir("C-ECHO", OK, dicom_rede.verificar())
    except Exception as exc:  # noqa: BLE001
        texto = str(exc)
        # "Calling" e "called" pedem providências OPOSTAS: o primeiro é o
        # NOSSO AE não cadastrado (só a Varian/TI resolve), o segundo é o nome
        # do ARIA errado do nosso lado (resolve-se aqui, trocando um
        # parâmetro). Sem esta distinção, abre-se chamado para corrigir o que
        # está na nossa mão.
        if "alling AE" in texto:
            rel.medir("C-ECHO", FALHA, texto[:100],
                      pedido=(f"cadastrar o AE Title chamador "
                              f"'{dicom_rede.ae_local()}' no ARIA, SEM amarrar "
                              "a um IP — todas as estações abrem o mesmo .exe "
                              "de um share, e cada uma chama do próprio IP"))
        elif "alled AE" in texto:
            rel.medir("C-ECHO", FALHA, texto[:100],
                      pedido=(f"confirmar o AE Title do serviço em {host}:{porta} "
                              f"— tentei '{dicom_rede.ae_remoto()}' e ele "
                              "recusou o nome CHAMADO"))
        else:
            rel.medir("C-ECHO", FALHA, texto[:110])
        return
    rel.nota(f"""
        Passou como '{dicom_rede.ae_local()}' de {_ip_de_saida(host, porta)}.
        A pergunta que ISTO NÃO responde: o cadastro amarrou o IP? Rodar este
        mesmo bloco de OUTRA estação e comparar. Se lá recusar com 'calling AE
        title not recognised', o cadastro é por endereço — e aí é um chamado
        por estação, para sempre, ou a topologia de concentrador.
    """)


# ---------------------------------------------------------------- bloco 6

def bloco_dicom_consulta(rel: Relatorio, cfg) -> None:
    """Acha o plano — e conta o que o estudo tem, sem trazer nada.

    O censo é a peça que faltava para orçar a frente da CT. Trazer para
    descobrir o tamanho custa a transferência inteira; perguntar custa uma
    associação. E o número muda a decisão: 150 objetos por paciente é um
    C-MOVE de segundos, 900 é uma conversa sobre banda e sobre quando a
    exportação roda.
    """
    from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: PLC0415

    rel.titulo(6, "DICOM: a consulta (C-FIND) e o censo do estudo")
    if not cfg.uid:
        rel.medir("C-FIND do plano", NAO,
                  "sem UID — passe --uid, ou rode com identidade de rede")
        return
    try:
        achados = dicom_rede.achar_plano(cfg.uid)
    except Exception as exc:  # noqa: BLE001
        rel.medir("C-FIND do plano", FALHA, str(exc)[:110])
        return
    if not achados:
        rel.medir("C-FIND do plano", FALHA,
                  "0 achados — o servidor não tem esse SOPInstanceUID")
        rel.nota("""
            UID que não existe responde "0 achados" com toda a legitimidade, e
            isso se parece com servidor quebrado. Conferir o UID antes de
            concluir qualquer coisa deste bloco.
        """)
        return
    ds = achados[0]
    estudo = str(getattr(ds, "StudyInstanceUID", "") or "")
    # Sem PatientID no relatório, e é deliberado: o arquivo vai para a pasta
    # de relatórios e já esteve num repositório público uma vez. A modalidade
    # e a contagem respondem tudo o que este bloco precisa responder.
    rel.medir("C-FIND do plano", OK,
              f"{len(achados)} achado(s), modalidade "
              f"{getattr(ds, 'Modality', '?')}")

    try:
        series = dicom_rede.censo_do_estudo(estudo)
    except Exception as exc:  # noqa: BLE001
        rel.medir("censo do estudo", FALHA, str(exc)[:110])
        return
    if not series:
        rel.medir("censo do estudo", AVISO, "o estudo não devolveu séries")
        return
    por_modalidade: dict = {}
    contou = False
    for s in series:
        m = s["modalidade"]
        atual = por_modalidade.setdefault(m, [0, 0])
        atual[0] += 1
        if s["instancias"] >= 0:
            atual[1] += s["instancias"]
            contou = True
    # "0 objeto(s)" e "o servidor não disse" são coisas diferentes, e escrever
    # zero para as duas foi o que o relatório do clinica-python01 mostrou em
    # 10/09/2026: sete modalidades, todas com "0 objeto(s)" — lido de fora,
    # um estudo vazio. O ARIA daqui simplesmente não preenche o campo.
    resumo = ", ".join(
        f"{m}: {n[0]} série(s)" + (f"/{n[1]} objeto(s)" if n[1] else "")
        for m, n in sorted(por_modalidade.items()))
    rel.medir("censo do estudo", OK, resumo)
    if not contou:
        rel.nota("""
            O servidor NÃO informou a contagem por série
            (NumberOfSeriesRelatedInstances é opcional no padrão). Isso não
            quer dizer série vazia — quer dizer que ele não disse. Quem conta
            é o passo abaixo, perguntando instância por instância.
        """)

    ct = [s for s in series if s["modalidade"] == "CT"]
    if ct:
        objetos = sum(s["instancias"] for s in ct if s["instancias"] >= 0)
        if not objetos:
            # Contar custa uma associação e N respostas de metadado — nenhum
            # pixel. É o preço de saber o tamanho da CT sem trazê-la, e é o
            # número que decide se a próxima frente cabe no clique do usuário.
            objetos = sum(max(dicom_rede.contar_instancias(s["serie"]), 0)
                          for s in ct)
            medido_como = "contados um a um (o servidor não informa)"
        else:
            medido_como = "informados pelo servidor"
        if objetos:
            rel.medir("o tamanho da CT", OK if objetos < 600 else AVISO,
                      f"{objetos} objeto(s) em {len(ct)} série(s) "
                      f"~ {objetos * 0.52:.0f} MB — {medido_como}")
            rel.nota("""
                A conta usa ~520 KB por corte de CT (512x512, 16 bits, sem
                compressão), que é o tamanho típico da Varian. É estimativa: o
                número medido sai do bloco 9, com --ct.
            """)
        else:
            rel.medir("o tamanho da CT", AVISO,
                      f"{len(ct)} série(s) de CT, e não deu para contar")
    cfg.series_do_estudo = series


# ---------------------------------------------------------------- bloco 7

def bloco_dicom_receptor(rel: Relatorio, cfg) -> None:
    """A porta que ESTA ponta abre — e o firewall que a fecha em silêncio.

    O C-MOVE não devolve os objetos pela conexão que pediu: o ARIA abre uma
    nova, de volta. Sem ninguém ouvindo, o pedido é ACEITO e a resposta chega
    como ``0 objeto(s), 1 falha`` depois de 21 s — indistinguível, de fora, de
    um destino errado. Este bloco mede as três coisas que produzem esse mesmo
    silêncio: a porta ocupada, a regra de entrada, e o perfil da rede.
    """
    from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: PLC0415

    rel.titulo(7, "DICOM: o receptor desta ponta")
    escuta = cfg.porta_escuta or dicom_rede.porta_escuta()
    destino = dicom_rede.ae_destino()

    # Vazio aqui é configuração NOSSA, não chamado: o destino existe no ARIA
    # desde 10/09/2026. Por isso sem ``pedido`` — ver AE_DESTINO_CADASTRADO.
    rel.medir("AE de destino do C-MOVE", OK if destino else AVISO,
              destino or "vazio — sem ele o produto tenta C-GET, que este "
                         "ARIA não faz. O destino já está cadastrado no "
                         "ARIA: repetir com --ae-destino "
                         f"{AE_DESTINO_CADASTRADO} (ver a nota do bloco 8)")

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", escuta))
        rel.medir(f"porta {escuta} livre para ouvir", OK, "o bind passou")
    except OSError as exc:
        # Porta ocupada é achado, não detalhe: a 104 é a registrada do DICOM e
        # há software clínico que a toma. Descobrir isso agora é escolher
        # outra porta no pedido; descobrir depois é o mesmo silêncio do
        # firewall, procurado no lugar errado.
        rel.medir(f"porta {escuta} livre para ouvir", FALHA,
                  f"o bind falhou: {exc}"[:100],
                  pedido=(f"a porta {escuta} está ocupada nesta máquina — "
                          "escolher outra para o receptor DICOM e cadastrá-la "
                          "no AE de destino"))
    finally:
        s.close()

    host, _porta = dicom_rede.servidor()
    ip = _ip_de_saida(host, _porta) if host else ""
    regras = _ps(
        "Get-NetFirewallRule -Direction Inbound -Enabled True -ErrorAction "
        "SilentlyContinue | Where-Object { $_.Action -eq 'Block' -and "
        "($_.DisplayName -match 'python|radiotera|ficha') } | "
        "Select-Object -First 8 -ExpandProperty DisplayName")
    bloqueios = [linha for linha in regras.splitlines() if linha.strip()
                 and not linha.startswith("(")]
    rel.medir("regras de ENTRADA que BLOQUEIAM", AVISO if bloqueios else OK,
              ", ".join(bloqueios)[:100] if bloqueios else "nenhuma para nós")
    if bloqueios:
        rel.nota("""
            No Windows, regra de BLOQUEIO vence regra de permissão. Foi este o
            caso de 10/09/2026: duas regras de entrada para python.exe,
            nascidas de um "Cancelar" num aviso, e uma regra allow nova para a
            porta não bastava. Desabilitar é reversível:
              netsh advfirewall firewall set rule name="python.exe" dir=in new enable=no
        """)

    liberacao = _ps(
        f"$p = Get-NetFirewallPortFilter -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.LocalPort -eq '{escuta}' }}; "
        "$p | Get-NetFirewallRule -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Direction -eq 'Inbound' -and $_.Enabled -eq 'True' "
        "-and $_.Action -eq 'Allow' } | Select-Object -First 5 "
        "-ExpandProperty DisplayName")
    permite = [x for x in liberacao.splitlines() if x.strip()
               and not x.startswith("(")]
    rel.medir(f"entrada liberada na {escuta}", OK if permite else AVISO,
              ", ".join(permite)[:100] if permite else
              "nenhuma regra allow — quem decide é o bloco 8",
              pedido=("" if permite else
                      f"liberar a ENTRADA TCP {escuta} nesta máquina, vinda de "
                      f"{host or 'o servidor do ARIA'} — é por ela que o "
                      "C-MOVE devolve os arquivos"),
              fase=PRODUCAO)
    if ip:
        rel.nota(f"""
            O AE de destino tem de estar cadastrado apontando para {ip}:{escuta}.
            Endereço e porta são do CADASTRO no ARIA, não da nossa
            configuração: se um dos dois divergir, o pedido é aceito e nada
            chega — o silêncio que custou a manhã de 10/09/2026.
        """)


# ---------------------------------------------------------------- bloco 8

def _tamanho(quantos_bytes: float) -> str:
    """KB abaixo de um mega. "0.0 MB" num relatório parece nada ter chegado."""
    if quantos_bytes < 1e6:
        return f"{quantos_bytes / 1e3:.0f} KB"
    return f"{quantos_bytes / 1e6:.1f} MB"


def _resumo_dos_arquivos(arquivos) -> str:
    """Quantos, de que tipo e quantos MB — sem nome de paciente nenhum."""
    import pydicom  # noqa: PLC0415

    por_modalidade: dict = {}
    bytes_totais = 0
    for caminho in arquivos:
        try:
            bytes_totais += caminho.stat().st_size
            ds = pydicom.dcmread(caminho, stop_before_pixels=True)
            m = str(getattr(ds, "Modality", "?"))
        except Exception:  # noqa: BLE001
            m = "(ilegível)"
        por_modalidade[m] = por_modalidade.get(m, 0) + 1
    tipos = ", ".join(f"{m}×{n}" for m, n in sorted(por_modalidade.items()))
    return f"{len(arquivos)} arquivo(s) — {tipos} — {_tamanho(bytes_totais)}"


def bloco_dicom_circuito(rel: Relatorio, cfg) -> None:
    """``trazer()`` de verdade: o que o produto faz, ponta a ponta.

    **É o teste que nunca tinha rodado.** A medida de 10/09/2026 foi feita com
    um Storage SCP avulso e um C-MOVE à mão — não com este código. O que ele
    exercita, e nenhum teste contra o SCP falso pode exercitar, é o servidor
    de verdade: se as referências do plano existem naquele ARIA, se as RTDOSE
    aparecem no C-FIND por estudo, e se o conjunto fecha.
    """
    from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: PLC0415

    rel.titulo(8, "DICOM: o circuito inteiro (o que o produto faz)")
    if not cfg.uid:
        rel.medir("trazer o conjunto", NAO, "sem UID")
        return
    if not dicom_rede.ae_destino():
        # Sem AE de destino, ``trazer`` cai no C-GET — que ESTE daemon não
        # implementa, medido em 10/09/2026 com seis variantes de associação. A
        # recusa vem como "No reason given", que não diz nada, e no relatório
        # do clinica-python01 apareceu como FALHA enigmática no lugar da
        # explicação que já se tinha. Melhor dizer o que se sabe.
        # Sem ``pedido``: o destino já existe no ARIA (AE_DESTINO_CADASTRADO),
        # e o que falta é a linha de comando, não a TI.
        rel.medir("trazer o conjunto", NAO,
                  "sem AE de destino: o caminho seria C-GET, e este ARIA não "
                  "faz C-GET (medido em 10/09/2026)")
        rel.nota(f"""
            Repetir com --ae-destino {AE_DESTINO_CADASTRADO}, o destino que já
            está cadastrado no ARIA. Sem isso, este bloco e o da CT ficam de
            fora, e são os dois que provam o circuito.
            O cadastro aponta para UMA máquina (IP e porta). Se não for esta,
            o C-MOVE é aceito e os arquivos do paciente chegam na outra: a
            repetição diz "NADA chegou" e pede à TI para conferir o cadastro.
        """)
        return
    pasta = Path(cfg.pasta or tempfile.mkdtemp(prefix="checkup_dicom_"))
    inicio = time.perf_counter()
    try:
        r = dicom_rede.trazer(cfg.uid, pasta)
    except Exception as exc:  # noqa: BLE001
        rel.medir("trazer o conjunto", FALHA, str(exc)[:110])
        return
    gasto = time.perf_counter() - inicio
    if not r.arquivos:
        # "Nada chegou" tem TRÊS causas, e elas mandam procurar em lugares
        # diferentes. A que mais engana é a terceira: um AE de destino
        # cadastrado e funcionando, só que apontando para OUTRA máquina — aí o
        # C-MOVE entrega direitinho, num computador que não é este, e daqui o
        # desfecho é indistinguível de firewall fechado. Medido em 10/09/2026:
        # o destino `RADIOTERAFICHA` desta clínica aponta para a máquina de
        # desenvolvimento, então o mesmo comando disparado de qualquer outra
        # traz zero — e o arquivo chega, íntegro, na máquina errada.
        #
        # Por isso o IP local sai NA MENSAGEM: sem ele, a conferência do
        # cadastro é uma pergunta sem resposta do outro lado do telefone.
        from isocentro.adaptadores.dicom import rede as dr  # noqa: PLC0415

        host_ar, porta_ar = dr.servidor()
        meu_ip = _ip_de_saida(host_ar, porta_ar) or "(não determinado)"
        rel.medir("trazer o conjunto", FALHA,
                  f"NADA chegou em {gasto:.1f} s, {r.falhas} falha(s)",
                  pedido=(f"o C-MOVE foi aceito e nada chegou. O AE de destino "
                          f"'{dicom_rede.ae_destino()}' aponta para qual IP e "
                          f"porta no cadastro do ARIA? Esta máquina é "
                          f"{meu_ip}:{dicom_rede.porta_escuta()}. Se o cadastro "
                          "apontar para outra, o arquivo chegou lá — íntegro, e "
                          "na máquina errada"),
                  fase=PRODUCAO)
        rel.nota(f"""
            As três causas, e cada uma manda procurar noutro lugar:
            1. o cadastro do destino aponta para outra máquina (é o caso quando
               se roda de um servidor a mais, e o destino foi cadastrado para a
               estação de teste);
            2. o firewall de ENTRADA desta máquina barra a volta;
            3. a porta {dicom_rede.porta_escuta()} não estava ouvindo.
            O bloco 7 acima separa a 2 da 3. A 1 só o cadastro do ARIA responde.
        """)
        return
    rel.medir("trazer o conjunto", OK if r.completo else AVISO,
              f"{_resumo_dos_arquivos(r.arquivos)}, em {gasto:.1f} s, "
              f"{r.falhas} falha(s), completo={r.completo}")
    for anterior in rel.achados:
        if anterior.rotulo.startswith("entrada liberada na"):
            anterior.estado = OK
            anterior.pedido = ""
            anterior.detalhe = ("o bloco 8 entregou — a regra existe, ou esta "
                                "origem não precisa dela")
    rel.diga("")
    rel.diga(f"  ATENÇÃO: são DADOS DE PACIENTE, gravados em {pasta}")
    rel.diga("  Apagar depois de conferir — é dado clínico fora do ARIA.")
    cfg.pasta_usada = pasta


# ---------------------------------------------------------------- bloco 9

def bloco_dicom_ct(rel: Relatorio, cfg) -> None:
    """Uma série de CT, medida: objetos, MB e segundos.

    Desde 11/09/2026 o ``trazer()`` do bloco 8 já traz a CT — a série que o
    RTSTRUCT contorna. Este bloco continua porque responde outra pergunta,
    que só a rede responde: **quanto tempo** custa a MAIOR série do estudo.
    Uma série de 300 cortes é o mesmo C-MOVE do plano em forma, e nada
    parecido em custo: se levar dez minutos, a exportação automática não pode
    rodar no clique do usuário, e isso muda o desenho, não a implementação.

    Traz **uma** série, a maior — que pode não ser a do contorno.
    """
    from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: PLC0415

    rel.titulo(9, "DICOM: quanto custa a CT (uma série)")
    series = [s for s in (cfg.series_do_estudo or [])
              if s["modalidade"] == "CT"]
    if not series:
        rel.medir("uma série de CT", NAO,
                  "o censo não achou CT neste estudo (bloco 6)")
        return
    if not dicom_rede.ae_destino():
        rel.medir("uma série de CT", NAO,
                  "sem AE de destino: o C-MOVE não tem para onde mandar")
        return
    escolhida = max(series, key=lambda s: s["instancias"])
    pasta = Path(tempfile.mkdtemp(prefix="checkup_ct_"))
    inicio = time.perf_counter()
    try:
        with dicom_rede.receber(pasta) as recebido:
            concluidas, falhas = dicom_rede._mover_contando(
                escolhida["serie"], dicom_rede.ae_destino(), nivel="SERIES")
    except Exception as exc:  # noqa: BLE001
        rel.medir("uma série de CT", FALHA, str(exc)[:110])
        return
    gasto = time.perf_counter() - inicio
    chegaram = len(recebido.arquivos)
    if not chegaram:
        rel.medir("uma série de CT", FALHA,
                  f"o servidor diz {concluidas} concluída(s) e nada chegou, "
                  f"em {gasto:.1f} s")
        return
    bytes_totais = sum(c.stat().st_size for c in recebido.arquivos)
    mb = bytes_totais / 1e6
    rel.medir("uma série de CT", OK,
              f"{chegaram} objeto(s), {_tamanho(bytes_totais)} em {gasto:.1f} s "
              f"({mb / max(gasto, 0.01):.2f} MB/s), {falhas} falha(s)")
    rel.diga("")
    rel.diga(f"  ATENÇÃO: DADOS DE PACIENTE em {pasta} — apagar depois.")
    total = sum(max(s["instancias"], 0) for s in series)
    if total and chegaram:
        estimado = gasto / chegaram * total
        plural = "s" if len(series) > 1 else ""
        rel.nota(f"""
            Extrapolando para as {len(series)} série{plural} de CT do estudo
            ({total} objetos): ~{estimado:.0f} s,
            ~{_tamanho(bytes_totais / chegaram * total)}.
            É a conta que decide se a CT entra no clique do usuário ou numa
            varredura de fundo.
        """)


# ---------------------------------------------------------------- bloco 10

def bloco_dicom_carga(rel: Relatorio, cfg) -> None:
    """Duas (ou N) estações pedindo ao mesmo tempo. O ARIA aceita?

    Em produção não há uma estação: há a sala de física, o comando de cada
    acelerador e a sala médica, todas abrindo o mesmo ``.exe``. Servidor DICOM
    tem limite de associações simultâneas, e ele costuma ser configurável —
    quer dizer, é item de chamado. Descobrir o limite com quatro C-ECHO custa
    segundos; descobrir em produção custa uma exportação que falha na hora em
    que duas pessoas trabalham juntas.
    """
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: PLC0415

    rel.titulo(10, f"DICOM: {cfg.carga} associações simultâneas")

    def um(_n):
        try:
            dicom_rede.verificar()
            return ""
        except Exception as exc:  # noqa: BLE001
            return str(exc)[:80]

    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=cfg.carga) as pool:
        erros = [e for e in pool.map(um, range(cfg.carga)) if e]
    gasto = time.perf_counter() - inicio
    if not erros:
        rel.medir(f"{cfg.carga} C-ECHO ao mesmo tempo", OK,
                  f"todas aceitas, em {gasto:.1f} s")
        return
    rel.medir(f"{cfg.carga} C-ECHO ao mesmo tempo", AVISO,
              f"{len(erros)} recusada(s) de {cfg.carga}, em {gasto:.1f} s — "
              f"ex.: {erros[0]}",
              pedido=(f"o serviço DICOM recusou {len(erros)} de {cfg.carga} "
                      "associações simultâneas: conferir o limite configurado "
                      "no daemon — em produção várias estações pedem junto"),
              fase=PRODUCAO)


# ---------------------------------------------------------------- bloco 11

def bloco_impressao(rel: Relatorio, cfg) -> None:
    """As impressoras que a estação enxerga.

    A ficha e a capa são documentos que vão GRAMPEADOS para a sala de
    tratamento: sem impressora, o app não entrega nada. É o degrau mais banal
    da lista e o mais fácil de descobrir tarde, porque ele só aparece na
    primeira ficha de verdade — que costuma ser numa estação nova, num dia
    cheio.
    """
    rel.titulo(11, "A impressão")
    saida = _ps("Get-Printer -ErrorAction SilentlyContinue | "
                "Select-Object -ExpandProperty Name")
    nomes = [x.strip() for x in saida.splitlines() if x.strip()
             and not x.startswith("(")]
    # Sem pedido automático: no clinica-python01, que é máquina de apoio e não
    # imprime ficha nenhuma, "instalar a impressora da sala" entrou na lista do
    # chamado. Item que a TI lê e não entende é item que faz duvidar dos
    # outros da mesma lista — e quem sabe se ESTA máquina imprime é quem está
    # rodando, não a sonda.
    rel.medir("impressoras visíveis", OK if nomes else AVISO,
              f"{len(nomes)}: " + ", ".join(nomes[:6]) if nomes
              else "nenhuma — se esta máquina for imprimir ficha, falta a "
                   "impressora da sala")


# ---------------------------------------------------------------- bloco 12

def bloco_pedido(rel: Relatorio, cfg) -> None:
    """O chamado, montado do que falhou. Nada escrito à mão.

    Separado por fase porque pedir tudo junto faz o item mais caro segurar o
    mais barato: o cadastro de um AE Title sai no mesmo dia, a permissão de um
    banco clínico passa por aprovação. E a fase diz à TI o que é urgente sem
    que seja preciso marcar tudo como urgente.
    """
    rel.titulo(12, "O que falta — e de quem é cada parte")
    pendentes = [a for a in rel.achados if a.pedido]
    # Falha SEM pedido é falha NOSSA: variável não apontada, biblioteca
    # faltando, caminho errado. Ela precisa sair aqui, e separada — a primeira
    # versão listava só o que gerava chamado, e o relatório saía "nada a pedir"
    # com três FALHA na tela logo acima. Relatório que se contradiz é o que faz
    # alguém abrir chamado para consertar o que estava na própria mão.
    nossas = [a for a in rel.achados if a.estado == FALHA and not a.pedido]

    if nossas:
        rel.diga("")
        rel.diga("  --- NOSSO (configuração desta máquina, não é chamado) ---")
        for n, a in enumerate(nossas, 1):
            rel.diga(f"   {n}. {a.rotulo}: {a.detalhe[:90]}")

    if not pendentes:
        rel.diga("")
        rel.diga("  Nada a pedir à TI: o que foi medido nesta máquina, e que")
        rel.diga("  depende deles, passou.")
        rel.diga("  O que este relatório NÃO prova está no bloco 5: se o")
        rel.diga("  cadastro do AE amarrou IP, só se descobre rodando isto de")
        rel.diga("  OUTRA estação e comparando o campo 'IP de saída'.")
        return

    rel.diga("")
    rel.diga("  --- PARA A TI (copiar daqui para o chamado) ---")
    for fase, cabecalho in ((AGORA, "sem isto o app não funciona hoje"),
                            (PRODUCAO, "sem isto ele não roda na clínica toda"),
                            (DEPOIS, "as frentes que já se sabe que vêm")):
        itens = [a for a in pendentes if a.fase == fase]
        if not itens:
            continue
        rel.diga("")
        rel.diga(f"  [{fase.upper()}] {cabecalho}")
        for n, a in enumerate(itens, 1):
            rel.diga(f"   {n}. {a.pedido}")
            rel.diga(f"      (medido em: {a.rotulo} — {a.detalhe[:70]})")


BLOCOS = (
    ("identidade", bloco_identidade),
    ("config", bloco_configuracao),
    ("pastas", bloco_pastas),
    ("banco", bloco_banco),
    ("dicom", bloco_dicom_associacao),
    ("dicom", bloco_dicom_consulta),
    ("dicom", bloco_dicom_receptor),
    ("dicom", bloco_dicom_circuito),
)


@dataclass
class Config:
    """O que a linha de comando pediu, e o que os blocos foram descobrindo."""

    uid: str = ""
    pasta: str = ""
    porta_escuta: int = 0
    carga: int = 0
    ct: bool = False
    db_servidor: str = ""
    db_banco: str = ""
    db_porta: int = 1433
    dicom_host: str = ""
    dicom_porta: int = 0
    series_do_estudo: list = field(default_factory=list)
    pasta_usada: Path | None = None


def _aplicar_argumentos(a) -> None:
    """Os valores da linha de comando viram variáveis DESTE processo.

    Serve à conversa com a TI: eles dizem "a porta é 51405", e se testa na
    hora sem gravar nada em estação nenhuma. Configuração meio feita atrás de
    um teste é pior que nenhuma — e aqui ela não sobrevive ao fim do processo.
    """
    from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: PLC0415

    for valor, nome in ((a.servidor, dicom_rede.ENV_SERVIDOR),
                        (a.ae_remoto, dicom_rede.ENV_AE_REMOTO),
                        (a.ae_local, dicom_rede.ENV_AE_LOCAL),
                        (a.ae_destino, dicom_rede.ENV_AE_DESTINO),
                        (str(a.porta_escuta or ""), dicom_rede.ENV_PORTA_ESCUTA),
                        (a.db_servidor, "ISOCENTRO_DB_SERVIDOR")):
        if valor:
            os.environ[ambiente.nome_novo(nome)] = valor


def _uid_do_banco(rel: Relatorio) -> str:
    """Um ``PlanUID`` de verdade, tirado da fila que a automação exportaria.

    **Este passo é o ÚLTIMO a ser tentado, e é de propósito.** Até 10/09/2026 o
    ``sondar_exportacao.bat`` perguntava ao banco primeiro: sem ``runas``, o
    SSPI falhava e o programa caía no laço de reconexão de 60 em 60 segundos —
    e o C-ECHO, que não precisa de identidade de rede nenhuma, nunca chegava a
    ser tentado. O arquivo prometia dois cliques e mentia.
    """
    rel.diga("")
    rel.diga("  Sem --uid: perguntando ao variandw qual plano está pronto.")
    try:
        from isocentro.banco import gatilho_db  # noqa: PLC0415
        prontos = gatilho_db.prontos()
    except Exception as exc:  # noqa: BLE001
        rel.diga(f"  não deu: {str(exc)[:100]}")
        rel.diga("  (de máquina fora do domínio isto é o esperado — passe "
                 "--uid, ou rode pelo .bat com runas /netonly)")
        return ""
    if not prontos:
        rel.diga("  o gatilho_db não tem plano pronto agora. Passe --uid.")
        return ""
    # O registro do paciente NÃO entra no relatório: ele vai para arquivo, e
    # este repositório já esteve público uma vez.
    rel.diga(f"  achei {len(prontos)} plano(s) pronto(s); sondando com o "
             "primeiro.")
    return prontos[0].plan_uid


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Mede, numa rodada, tudo o que o ISOCENTRO precisa "
                    "da rede — e escreve o pedido à TI. Só leitura.")
    p.add_argument("--servidor", default="", help="host:porta do DB Daemon")
    p.add_argument("--ae-remoto", default="", help="AE Title do ARIA")
    p.add_argument("--ae-local", default="", help="AE Title desta estação")
    p.add_argument("--ae-destino", default="", help="AE de destino do C-MOVE")
    p.add_argument("--porta-escuta", type=int, default=0,
                   help="porta em que esta ponta ouve o C-MOVE")
    p.add_argument("--db-servidor", default="", help="host do data warehouse")
    p.add_argument("--db-banco", default="", help="banco (padrão variandw)")
    p.add_argument("--uid", default="",
                   help="SOPInstanceUID do plano. Sem isto, pergunta ao "
                        "gatilho_db — o que exige identidade de rede")
    p.add_argument("--pasta", default="",
                   help="onde gravar o que o DICOM trouxer; padrão é pasta "
                        "temporária do sistema, NUNCA o repositório")
    p.add_argument("--ct", action="store_true",
                   help="traz UMA série de CT e mede tempo e MB (bloco 9)")
    p.add_argument("--carga", type=int, default=0,
                   help="N associações simultâneas (bloco 10); 0 = não testa")
    p.add_argument("--sem-padrao", action="store_true",
                   help="não usar os valores embutidos da clínica; mede o que "
                        "ESTA estação tem configurado, e só")
    p.add_argument("--pular", default="",
                   help="blocos a não rodar: banco, dicom, pastas, identidade")
    p.add_argument("-o", "--saida", default="checkup_clinica.txt",
                   help="grava o relatório neste arquivo, além de imprimir")
    a = p.parse_args(argv)

    _console_em_utf8()
    rel = Relatorio()
    pular = {x.strip().lower() for x in a.pular.replace(";", ",").split(",")
             if x.strip()}
    try:
        rel.diga("=" * 72)
        rel.diga("  ISOCENTRO — checkup da clínica (SÓ LEITURA)")
        rel.diga(f"  {datetime.datetime.now():%d/%m/%Y %H:%M:%S}")
        rel.diga("=" * 72)

        _aplicar_argumentos(a)
        if not a.sem_padrao:
            _aplicar_padrao_da_clinica()
        from isocentro.adaptadores.dicom import rede as dicom_rede  # noqa: PLC0415

        host, porta = dicom_rede.servidor()
        cfg = Config(uid=a.uid.strip(), pasta=a.pasta,
                     porta_escuta=a.porta_escuta, carga=a.carga, ct=a.ct,
                     db_servidor=a.db_servidor or ambiente.ler("ISOCENTRO_DB_SERVIDOR"),
                     db_banco=a.db_banco or ambiente.ler("ISOCENTRO_DB_BANCO"),
                     dicom_host=host, dicom_porta=porta)

        for nome, funcao in BLOCOS:
            if nome in pular:
                continue
            # Um bloco que estoure NÃO derruba os outros: o que se quer é o
            # mapa do que funciona, e o bloco caro (o DICOM) vem depois do
            # frágil (o banco). Antes disto, um SSPI recusado nesta máquina
            # levava junto a medida que exigia a ida à clínica.
            try:
                if (funcao is bloco_dicom_consulta and not cfg.uid
                        and "banco" not in pular):
                    # ``--pular banco`` vale AQUI também: quem pulou o banco
                    # não quer que a rodada gaste tempo com o variandw por uma
                    # porta lateral. Sem esta condição, pular o bloco 4 numa
                    # máquina sem identidade de rede ainda pagava a espera do
                    # SSPI — no meio da parte que a pessoa queria medir.
                    cfg.uid = _uid_do_banco(rel)
                funcao(rel, cfg)
            except Exception as exc:  # noqa: BLE001
                rel.medir(f"(bloco {nome})", FALHA,
                          f"estourou: {type(exc).__name__}: {exc}"[:100])
        if a.ct and "dicom" not in pular:
            try:
                bloco_dicom_ct(rel, cfg)
            except Exception as exc:  # noqa: BLE001
                rel.medir("(bloco CT)", FALHA, str(exc)[:100])
        if a.carga and "dicom" not in pular:
            try:
                bloco_dicom_carga(rel, cfg)
            except Exception as exc:  # noqa: BLE001
                rel.medir("(bloco carga)", FALHA, str(exc)[:100])
        if "impressao" not in pular:
            bloco_impressao(rel, cfg)
        bloco_pedido(rel, cfg)

        rel.diga("")
        rel.diga("=" * 72)
        contagem = {}
        for achado in rel.achados:
            contagem[achado.estado] = contagem.get(achado.estado, 0) + 1
        rel.diga("  " + ", ".join(f"{n} {e}" for e, n in contagem.items()))
        rel.diga("=" * 72)
        return 1 if rel.falhou else 0
    finally:
        # Gravado ACONTEÇA O QUE ACONTECER: o console do runas fecha, e o
        # relatório que mais importa é justamente o da rodada que deu errado.
        if a.saida:
            destino = _onde_gravar(a.saida)
            # ``utf-8-sig``: o Bloco de Notas de Windows antigo assume a code
            # page da máquina sem o BOM, e o relatório do clinica-python01
            # chegou com "clÃ­nica" no lugar de "clínica". Texto ilegível é
            # texto que não vai para o chamado.
            destino.write_text("\n".join(rel.linhas), encoding="utf-8-sig")
            print(f"\nGravado em {destino}")
        if EMPACOTADO and sys.stdin and sys.stdin.isatty():
            # Dois cliques no exe abrem um console que se fecha ao terminar, e
            # leva a tela junto. O arquivo já está gravado — mas quem clicou
            # está olhando para a janela, não para a pasta.
            print("\nLeia o bloco 12 acima. Enter para fechar.")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass


if __name__ == "__main__":
    raise SystemExit(main())
