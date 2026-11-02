"""Leitura direta do data warehouse da Varian (``variandw``), para a capa.

Hoje a capa nasce de três relatórios exportados por um agendador. Quando o
agendador falha — e falhou —, a capa nasce vazia. Pior: os dois CSV saem com
janelas de período independentes, e numa exportação real o de cadastro veio com
599 pacientes contra 13 080 do de prescrições. Os 12 481 do meio chegavam à tela
sem sexo, convênio, contato, CID nem intenção, e não havia o que fazer na
estação.

Lendo o banco, os dois problemas somem de uma vez: não há agendador no caminho e
não há janela de período, porque se consulta **por paciente**.

Este módulo devolve exatamente os mesmos objetos de :mod:`capa_dados`
(``Cadastro``, ``Prescricao``, ``Volume``) — quem chama não sabe de onde veio, e
por isso nada mais do app precisou mudar.

**O banco não é obrigatório.** Sem servidor configurado, ou com o servidor fora
do ar, tudo aqui devolve ``None``/vazio e o app segue nos CSV, como antes. Um
documento que vai para a sala de tratamento não pode depender de a rede estar
boa; ter duas fontes é o ponto, não trocar uma dependência frágil por outra.

Só LEITURA. Nunca há ``INSERT``/``UPDATE`` aqui, e a conexão é aberta em modo
somente-leitura — este banco é o sistema clínico, não um rascunho nosso.

Mapeamento verificado contra o banco real em 18/08/2026 (ver NOTAS.md).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

from isocentro.dados import ambiente
from isocentro.banco import banco_local
from isocentro.banco import capa_dados

_LOG = logging.getLogger(__name__)

# Onde o admin aponta o servidor. Mesma lógica das pastas: variável de ambiente
# manda (decisão de instalação), configuração do serviço vale para todas as
# estações, e sem nenhuma das duas o banco simplesmente não é usado.
#
# Os nomes ficam no formato ANTIGO de propósito: quem lê é o ``ambiente.ler``,
# que tenta primeiro o ``ISOCENTRO_*`` e só depois este. Reescrever a
# constante aqui não ligaria o nome novo e desligaria as estações que a TI já
# configurou com o antigo.
ENV_SERVIDOR = "ISOCENTRO_DB_SERVIDOR"
ENV_BANCO = "ISOCENTRO_DB_BANCO"
BANCO_PADRAO = "variandw"
PORTA_PADRAO = 1433

# Curto de propósito: se o banco não responde rápido, o certo é cair no CSV e
# seguir, não deixar quem está montando a ficha olhando para uma tela travada.
TEMPO_LIMITE_S = 6

# O driver moderno não vai ser instalado nas estações — e, medido contra o banco
# real, o antigo devolve acentuação correta ("Cólera devida a Vibrio cholerae 01,
# biótipo cholerae"). Fica a preferência, mas o de 2000 serve.
DRIVERS = ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server",
           "SQL Server Native Client 11.0", "SQL Server")

# Quanto tempo esperar antes de tentar de novo, depois de uma falha de REDE.
#
# Existiu aqui uma trava booleana (``_falhou``) que, uma vez ligada, valia para
# o resto do processo. Ela protegia o certo — montar uma capa faz várias
# consultas, e esperar o tempo-limite em cada campo travaria a tela — mas
# cobrava caro demais: uma oscilação de rede NO MOMENTO DO CONNECT prendia o
# app no espelho até alguém fechar o programa. Na clínica, o contorno virou
# entrar como admin e salvar a configuração, que por acaso chama ``esquecer``.
#
# (Falha na CONSULTA, com a conexão já viva, nunca teve esse problema: o
# ``_consultar`` solta a conexão e a chamada seguinte reconecta sozinha.)
#
# Um minuto é o meio-termo medido pelo uso: dentro de uma mesma capa ninguém
# espera o tempo-limite duas vezes, e o próximo paciente já tenta de novo.
# A espera CRESCE a cada falha seguida, e o motivo é medido: numa estação que
# nunca vai conectar (fora do domínio, sem liberação), a espera fixa de um
# minuto fazia o app tentar sessenta vezes por hora, cada tentativa custando o
# TEMPO_LIMITE_S inteiro NA THREAD DA INTERFACE — dezenas de travadas de ~8 s
# por manhã, todas garantidamente inúteis.
#
# A primeira espera continua sendo um minuto: quem só teve uma oscilação de
# rede volta rápido igual. Quem está quebrado de verdade é que vai sendo
# deixado em paz. Zera ao conectar e no "Reconectar agora".
#
# É também o que dispensa caso especial para a falha de IDENTIDADE (SSPI): ela
# é permanente na prática, mas não dá para marcá-la como impedimento — uma
# queda momentânea do controlador de domínio dá o mesmo erro, e isso prenderia
# uma estação boa.
ESPERAS_APOS_FALHA_S = (60, 120, 300, 900)
_falhas_seguidas = 0

_trava = threading.Lock()
_conexao = None
# Instante (relógio monotônico) antes do qual não se tenta de novo. Zero = pode
# tentar agora. É o substituto da trava permanente.
_sem_tentar_ate = 0.0
# Falha que NOVA TENTATIVA NÃO RESOLVE nesta estação: sem pyodbc, sem driver
# ODBC. Insistir nelas só gasta o tempo-limite de novo, e a providência é outra
# — instalar software, abrir chamado. Guardar o motivo em texto deixa a tela
# dizer QUAL é, em vez de repetir "sem conexão" para tudo.
_impedimento = ""
# Recado curto do ÚLTIMO connect que falhou. Guardado porque "não respondeu" e
# "respondeu e recusou você" são diagnósticos opostos, e a tela dizia o
# primeiro para os dois — inclusive para o caso medido na clínica, em que a
# rede está OK e o que falha é a identidade.
_ultima_falha = ""


def _traduzir_falha(exc, alvo: str) -> str:
    """Uma frase que diz o que REALMENTE falhou, a partir do SQLSTATE.

    Pelo SQLSTATE, e não pelo texto do driver: o texto vem traduzido para o
    idioma do Windows da estação, e casar por palavra quebraria numa máquina em
    inglês. "SSPI" é exceção — é sigla e sobrevive à tradução.

    Os quatro casos pedem providências OPOSTAS: esperar a rede, entrar no
    domínio, pedir liberação ao DBA, instalar driver. Um "sem conexão" para
    todos manda a pessoa abrir o chamado errado e esperar dias por uma resposta
    que não resolve.
    """
    estado_sql = str(exc.args[0]) if getattr(exc, "args", None) else ""
    texto = str(exc)
    quem = os.environ.get("USERDOMAIN", "?") + '\\' + os.environ.get("USERNAME", "?")
    if estado_sql.startswith(("08", "HYT")):
        return f"{alvo} não respondeu (rede, VPN ou servidor fora do ar)."
    if estado_sql.startswith("28"):
        return (f"{alvo} respondeu e RECUSOU a identidade {quem}. "
                "Não é liberação de acesso — é a conta de rede.")
    if "SSPI" in texto:
        return (f"{alvo} respondeu, mas não deu para negociar a identidade "
                f"{quem} (SSPI). É o que acontece quando a estação está fora "
                "do domínio da clínica.")
    if estado_sql.startswith("IM"):
        return f"Problema no driver ODBC desta estação: {texto[:120]}"
    return f"{alvo} recusou a conexão: {texto[:120]}"


def _config(chave_env: str, chave_servico: str, padrao: str = "") -> str:
    # Por ``ambiente.ler``, NUNCA por ``os.environ.get``: até 09/09/2026 este
    # era o único lugar do app que lia a variável direto, e o efeito era o pior
    # possível — numa estação apontada pelo nome novo
    # (``ISOCENTRO_DB_SERVIDOR``) o valor não tinha efeito NENHUM, o app
    # caía no ``config_servico.json`` ou nos relatórios exportados, e nada
    # ligava a capa vazia à variável que alguém tinha acabado de definir.
    valor = ambiente.ler(chave_env)
    if valor:
        return valor
    try:
        from isocentro.dados import config_servico
        return config_servico.valor(chave_servico) or padrao
    except Exception:  # noqa: BLE001
        return padrao


def servidor() -> str:
    return _config(ENV_SERVIDOR, "db_servidor")


def banco() -> str:
    return _config(ENV_BANCO, "db_banco", BANCO_PADRAO)


def origem_do_servidor() -> str:
    """De ONDE veio o servidor em uso — para a tela poder dizer.

    Mesma razão do ``capa_dados.origem_da_pasta``: o admin salva o servidor na
    tela de Serviço, lê "vale para todas as estações" e, nesta máquina, uma
    variável de ambiente continua mandando — em silêncio. Aqui o silêncio custa
    mais que numa pasta de relatórios: a capa passa a nascer de OUTRO banco, e
    o papel não diz de qual.

    Devolve o NOME que venceu, não o nome antigo genérico: numa estação com as
    duas variáveis definidas, dizer "ISOCENTRO_DB_SERVIDOR" mandaria o admin
    conferir a errada.
    """
    qual = ambiente.qual_valeu(ENV_SERVIDOR)
    if qual:
        return f"variável {qual} desta estação"
    if servidor():
        return "configuração do serviço"
    return "não apontado"


def configurado() -> bool:
    """Há servidor apontado? Sem isto o módulo inteiro fica fora do caminho.

    O banco LOCAL conta como configurado: ele responde às mesmas consultas, e
    sem isto a Ficha Virtual continuaria dizendo "o sistema não está apontado"
    numa máquina que tem o dado gravado na mão. Ver :mod:`banco_local`.
    """
    return bool(servidor()) or banco_local.ligado()


def aquecer() -> None:
    """Abre a conexão numa thread de fundo, para a interface não pagar por ela.

    O ``connect`` custa até ``TEMPO_LIMITE_S`` e roda onde for chamado. Como a
    capa é montada na thread da interface, a PRIMEIRA capa de cada sessão
    pagava esse tempo com a tela parada — o recuo de ``ESPERAS_APOS_FALHA_S``
    diminui a frequência das travadas seguintes, mas nunca a primeira.

    Chamado no arranque, durante o login: enquanto a pessoa digita usuário e
    senha, o banco responde (ou não) sem ninguém olhando para uma tela
    congelada. Quando a janela abre, ``conexao()`` já devolve o resultado
    pronto — ou o prazo já está marcado e a capa sai do espelho na hora, com o
    aviso de sempre.

    **Não muda a semântica de nada.** Quem chama ``conexao()`` continua
    síncrono e recebe o mesmo que receberia; o ``_trava`` garante que uma
    chamada que chegue no meio do aquecimento espere aquele connect em vez de
    abrir um segundo. O que muda é só QUEM paga o tempo, e quando.

    Silencioso de propósito: é adiantamento de trabalho, não uma operação que
    alguém pediu. O que houver de errado aparece pela via de sempre — o estado
    na tela e o registro do ``conexao()``.
    """
    if not configurado():
        return   # sem servidor apontado, o módulo inteiro fica fora do caminho

    def _tentar() -> None:
        try:
            conexao()
        except Exception:  # noqa: BLE001 — ver o teste: é o stderr que se protege
            # Não é o app que se protege aqui: exceção em thread não derruba o
            # processo, e a rede de segurança do ``gui`` é ``sys.excepthook``,
            # que não cobre thread nenhuma. O que se evita é o traceback cru no
            # stderr — o mesmo despejo que o ``tools/testar_reconexao.py`` tem
            # de calar para o relatório dele ficar legível.
            pass

    # ``daemon``: uma estação que fecha o programa durante o tempo-limite não
    # pode ficar presa esperando esta thread terminar.
    threading.Thread(target=_tentar, name="capa_db.aquecer",
                     daemon=True).start()


def esquecer() -> None:
    """Solta a conexão e zera QUALQUER espera — tentativa limpa, agora.

    É o "acabei de consertar a rede, tenta de novo" e é o único caminho que
    também limpa o ``_impedimento``: driver ODBC instalado com o programa
    aberto é raro, mas quem clica em reconectar espera uma tentativa de
    verdade, não a repetição de um diagnóstico velho.

    A espera automática (``ESPERAS_APOS_FALHA_S``) cobre a falha passageira
    sozinha; isto aqui é para quem não quer esperar por ela.
    """
    global _sem_tentar_ate, _impedimento, _ultima_falha, _falhas_seguidas
    _soltar_conexao()
    # Também a de reprodução: o "Reconectar agora" tem de reler o arquivo, que
    # pode ter sido regravado com o app aberto.
    banco_local.esquecer()
    with _trava:
        _sem_tentar_ate = 0.0
        _impedimento = ""
        _ultima_falha = ""
        _falhas_seguidas = 0


def _soltar_conexao() -> None:
    """Descarta a conexão e nada mais.

    Separado do ``esquecer`` porque são coisas diferentes, e misturá-las já
    tinha efeito errado: o ``_consultar`` chama isto quando a conexão morre no
    meio do expediente, e usar o ``esquecer`` ali apagava também o
    ``_impedimento`` — o diagnóstico de "esta estação não tem driver ODBC"
    sumia por causa de uma consulta que falhou.

    Aqui não se mexe no prazo de propósito: com a conexão viva o prazo está
    zerado, então a próxima chamada já reconecta, que é o que o ``_consultar``
    quer.
    """
    global _conexao
    with _trava:
        if _conexao is not None:
            try:
                _conexao.close()
            except Exception:  # noqa: BLE001
                pass
        _conexao = None


def _quanto(segundos: float) -> str:
    """"45 s", "3 min" — porque "em 900 s" ninguém converte de cabeça."""
    if segundos < 90:
        return f"{int(segundos) + 1} s"
    return f"{round(segundos / 60)} min"


def estado() -> tuple[str, str]:
    """``(situação, recado)`` — para a tela dizer O QUE está acontecendo.

    Situações: ``"local"`` (o banco GRAVADO está valendo — simulação, ver
    :mod:`banco_local`), ``"sem_servidor"`` (ninguém apontou o banco), ``"impedida"``
    (falta driver ou pyodbc nesta estação — chamado para a TI), ``"esperando"``
    (a rede falhou e a próxima tentativa é automática) e ``"ok"``.

    Existe porque "reserva usada é reserva anunciada" não basta: a tela dizia
    "o sistema não respondeu" tanto para a rede que cai por um minuto quanto
    para a estação que nunca vai conectar. As duas pedem providências opostas —
    esperar, ou abrir chamado — e um aviso só ensinava a ignorar os dois.
    """
    if banco_local.ligado():
        # Situação PRÓPRIA, e não "ok": a tela não pode dizer "Servidor
        # SRVINSIGHT" para um arquivo gravado semana passada. Mesma regra da
        # capa que sai do espelho — reserva usada é reserva anunciada, e
        # simulação silenciosa vira o normal em duas semanas.
        return ("local", banco_local.resumo())
    if not configurado():
        return ("sem_servidor", "Nenhum servidor apontado em "
                                "Configurações → Serviço.")
    if _impedimento:
        return ("impedida", f"{_impedimento} — nova tentativa não resolve; "
                            "isto é chamado para a TI.")
    faltam = _sem_tentar_ate - time.monotonic()
    if faltam > 0:
        return ("esperando",
                f"{_ultima_falha} Tento de novo sozinho em {_quanto(faltam)}"
                " — ou use \"Reconectar agora\" em Configurações → Serviço.")
    return ("ok", f"Servidor {servidor()}.")


def _driver(pyodbc) -> str:
    instalados = set(pyodbc.drivers())
    for d in DRIVERS:
        if d in instalados:
            return d
    return ""


def conexao():
    """A conexão viva, ou ``None`` se não dá para usar o banco agora.

    Guardada entre chamadas: montar a capa faz várias consultas seguidas, e
    reconectar em cada uma custaria mais que todas elas somadas.
    """
    global _conexao, _sem_tentar_ate, _impedimento, _ultima_falha
    global _falhas_seguidas
    # Banco LOCAL antes de tudo, inclusive antes do ``configurado()``: quando
    # ele está ligado não há servidor para apontar, e é ele quem responde. Não
    # é reserva nem queda — é substituição declarada, e a tela anuncia.
    local = banco_local.conexao()
    if local is not None:
        return local
    # ``_impedimento`` é definitivo nesta estação; a espera é passageira e se
    # esgota sozinha — é ela que faz o app voltar sem ninguém intervir.
    if not configurado() or _impedimento:
        return None
    if time.monotonic() < _sem_tentar_ate:
        return None
    with _trava:
        if _conexao is not None:
            return _conexao
        try:
            import pyodbc
        except ImportError:
            _LOG.info("pyodbc não instalado — a capa segue pelos relatórios.")
            _impedimento = "pyodbc não está instalado nesta estação"
            return None
        drv = _driver(pyodbc)
        if not drv:
            _LOG.warning("Nenhum driver ODBC de SQL Server nesta estação.")
            _impedimento = "Nenhum driver ODBC de SQL Server nesta estação"
            return None
        alvo = servidor()
        partes = [
            f"DRIVER={{{drv}}}",
            # Instância nomeada (SERVIDOR\INSTANCIA) não leva porta.
            f"SERVER={alvo}" if "\\" in alvo else f"SERVER={alvo},{PORTA_PADRAO}",
            f"DATABASE={banco()}",
            "Trusted_Connection=yes",
            "APP=ISOCENTRO",
        ]
        if drv != "SQL Server":
            # O driver de 2000 rejeita estes dois com "atributo inválido", e o
            # erro chega misturado ao de autenticação — já custou um
            # diagnóstico lido errado.
            partes += ["TrustServerCertificate=yes", "ApplicationIntent=ReadOnly"]
        try:
            _conexao = pyodbc.connect(";".join(partes),
                                      timeout=TEMPO_LIMITE_S, readonly=True)
            # ``timeout`` no connect é só o LOGIN. O tempo da CONSULTA é este
            # atributo — sem ele, uma consulta lenta (servidor carregado, tabela
            # sem índice) trava a tela para sempre, porque a capa é montada na
            # thread da interface. Melhor desistir em segundos e cair no
            # espelho, com aviso, do que deixar alguém olhando para uma janela
            # congelada sem saber se pode fechar.
            _conexao.timeout = TEMPO_LIMITE_S
            # Conectou: o recuo volta ao início. A próxima queda merece a
            # espera curta de novo — o recuo pune a falha SEGUIDA, não a
            # estação que já provou que consegue.
            _falhas_seguidas = 0
            _ultima_falha = ""
        except Exception as exc:  # noqa: BLE001 — a capa sai pelos CSV
            # Rede, login, servidor fora do ar: tudo passageiro. Marca a espera
            # em vez de desistir — é esta linha que devolve o app sozinho
            # quando a rede volta.
            _ultima_falha = _traduzir_falha(exc, alvo)
            espera = ESPERAS_APOS_FALHA_S[min(_falhas_seguidas,
                                              len(ESPERAS_APOS_FALHA_S) - 1)]
            _falhas_seguidas += 1
            _LOG.warning("Sem conexão com %s: %s (%dª falha seguida; tento de "
                         "novo em %d s)", alvo, exc, _falhas_seguidas, espera)
            _sem_tentar_ate = time.monotonic() + espera
            return None
        return _conexao


def diagnosticar(alvo: str = "", porta: int = PORTA_PADRAO) -> list:
    """Por que o banco não conecta — em camadas, na ordem em que elas falham.

    Devolve ``[(passo, ok, recado)]``, parando no primeiro que falha.

    ``ok`` tem TRÊS estados, não dois: ``None`` é "sondei e não concluí nada",
    que hoje só acontece na camada de rede contra instância nomeada. Sem esse
    terceiro estado, uma sonda inconclusiva teria de mentir para um dos lados —
    "OK" escondendo uma rede fechada, ou "FALHA" mandando abrir chamado de
    firewall para um servidor em que o app entra normalmente.

    Existe DENTRO do app, e não só no ``tools/diagnostico_db.py``, porque a
    pasta ``tools/`` não vai no pacote: a caixa de erro mandava quem está na
    clínica rodar um arquivo que não existe naquela máquina. Ferramenta de
    diagnóstico que não chega onde o problema acontece não é ferramenta.

    A separação é o ponto. Driver ausente, rede fechada, identidade recusada e
    falta de permissão dão mensagens PARECIDAS no driver ODBC — e exigem
    providências opostas: instalar software, abrir firewall, entrar no domínio,
    abrir chamado de liberação. Quem lê "SQL Server inexistente ou acesso
    negado" pede liberação quando o problema é a VPN, e espera dias por uma
    resposta que não resolve.
    """
    import getpass
    import socket

    alvo = alvo or servidor()
    passos = []
    quem = f"{os.environ.get('USERDOMAIN', '?')}\\{getpass.getuser()}"
    passos.append(("Quem está rodando", True,
                   f"{quem} — é esta conta que o servidor vai receber; "
                   "não há senha guardada em lugar nenhum."))
    if banco_local.ligado():
        # Primeiro passo, e não no fim: sem isto o diagnóstico fala do servidor
        # enquanto o app inteiro está lendo um arquivo — e quem lê conclui que
        # está conectado ao que não está.
        passos.append(("Banco local", None, banco_local.resumo()
                       + f"  Arquivo: {banco_local.arquivo()}.  O diagnóstico "
                         "abaixo é do SERVIDOR, que o app NÃO está usando."))
    if not alvo:
        passos.append(("Servidor apontado", False,
                       "O campo Sistema está vazio. Sem servidor, o app lê os "
                       "relatórios exportados, como antes."))
        return passos
    try:
        import pyodbc
    except ImportError:
        passos.append(("Biblioteca de acesso", False,
                       "O pyodbc não está nesta instalação — é falha de "
                       "empacotamento, não da estação."))
        return passos
    passos.append(("Biblioteca de acesso", True, f"pyodbc {pyodbc.version}"))

    drv = _driver(pyodbc)
    if not drv:
        passos.append(("Driver ODBC", False,
                       "Nenhum driver de SQL Server nesta estação. Peça à TI o "
                       "ODBC Driver 18 for SQL Server."))
        return passos
    passos.append(("Driver ODBC", True, drv + (
        "  — é o antigo; conecta, mas erra acentuação e não conhece o tipo "
        "DATE. Vale pedir o Driver 18." if drv == "SQL Server" else "")))

    # A REDE antes do login: é o que separa "não alcancei" de "não me aceitou".
    s = socket.socket()
    s.settimeout(TEMPO_LIMITE_S)
    maquina, _, instancia = alvo.partition("\\")
    try:
        s.connect((maquina, porta))
        passos.append(("Rede", True, f"{maquina}:{porta} responde."))
    except Exception as exc:  # noqa: BLE001
        if instancia:
            # Instância NOMEADA não fala necessariamente na 1433: a porta é
            # dinâmica e quem a resolve é o SQL Browser — tanto que ``conexao()``
            # não manda porta nenhuma quando o alvo tem barra invertida. Aqui a
            # sonda não conclui NADA, e dar "FALHA" mandaria abrir chamado de
            # firewall para um servidor em que o app entra sem tropeço, além de
            # esconder o login e a permissão, que é onde a resposta está.
            passos.append(("Rede", None,
                           f"Não alcancei {maquina}:{porta} ({exc}) — mas o "
                           f"alvo é a instância nomeada {maquina}\\{instancia}, "
                           "que costuma usar porta dinâmica. Isto não diz nada: "
                           "quem decide é a entrada no banco, logo abaixo."))
        else:
            passos.append(("Rede", False,
                           f"Não alcancei {maquina}:{porta} ({exc}). Isto é "
                           "REDE — VPN, firewall ou o servidor fora do ar. Não "
                           "é senha nem permissão."))
            return passos
    finally:
        s.close()

    try:
        cx = pyodbc.connect(_texto_de_conexao(drv, alvo), timeout=TEMPO_LIMITE_S,
                            readonly=True)
    except Exception as exc:  # noqa: BLE001
        passos.append(("Entrada no banco", False, _explicar_recusa(str(exc), quem)))
        return passos
    passos.append(("Entrada no banco", True, f"Conectado a {alvo}."))

    try:
        cur = cx.cursor()
        cur.execute("SELECT TOP 1 PatientId FROM DWH.DimPatient")
        cur.fetchall()
        passos.append(("Leitura dos dados", True,
                       "As tabelas da capa respondem."))
    except Exception as exc:  # noqa: BLE001
        passos.append(("Leitura dos dados", False,
                       f"Entrei no banco mas não li DWH.DimPatient ({exc}). "
                       "AGORA sim é permissão: peça db_datareader em variandw."))
    finally:
        try:
            cx.close()
        except Exception:  # noqa: BLE001
            pass
    return passos


def _explicar_recusa(erro: str, quem: str) -> str:
    """Traduz a recusa do driver para o que a pessoa tem de FAZER."""
    if "SSPI" in erro or "18452" in erro or "untrusted domain" in erro:
        return (f"O servidor foi alcançado, mas recusou a identidade {quem}. "
                "Isto é IDENTIDADE, não permissão: a estação precisa estar no "
                "domínio da clínica, e quem está logado precisa ser o usuário "
                "de rede.\n\nNuma máquina fora do domínio, isto vai falhar "
                "sempre — e não diz nada sobre a liberação do acesso.")
    if "4060" in erro or "Cannot open database" in erro:
        return ("O servidor aceitou a conta, mas ela não pode abrir o banco. "
                "AGORA é permissão: peça db_datareader em variandw.")
    if "Login failed" in erro or "18456" in erro:
        # Medido na clínica em 19-20/08/2026: era esta a falha real, e ela é o
        # OPOSTO do SSPI. A identidade chegou inteira; o servidor leu quem é e
        # recusou. Confundir as duas fez procurar problema de domínio durante
        # dois dias quando o que faltava era uma linha no chamado.
        return (f"O servidor LEU a identidade {quem} e recusou o login.\n\n"
                "Isto é AUTORIZAÇÃO, não identidade nem rede: a conta não tem "
                "acesso ao banco. Peça no chamado:\n\n"
                f"   login no servidor para {quem}\n"
                "   com db_datareader no banco variandw\n\n"
                "Vale pedir para um GRUPO do domínio em vez de uma conta: "
                "senão cada pessoa que abrir o app precisará de um chamado "
                "novo, e verá a capa cair na reserva sem entender por quê.")
    return f"O servidor recusou a conexão: {erro}"


def _texto_de_conexao(drv: str, alvo: str) -> str:
    """A MESMA string que ``conexao()`` monta — testar outra coisa não serve."""
    partes = [
        f"DRIVER={{{drv}}}",
        f"SERVER={alvo}" if "\\" in alvo else f"SERVER={alvo},{PORTA_PADRAO}",
        f"DATABASE={banco()}",
        "Trusted_Connection=yes",
        "APP=ISOCENTRO",
    ]
    if drv != "SQL Server":
        partes += ["TrustServerCertificate=yes", "ApplicationIntent=ReadOnly"]
    return ";".join(partes)


class FalhaDeLeitura(Exception):
    """A consulta não pôde ser feita — que NÃO é o mesmo que não achar nada.

    Sem essa distinção, uma consulta que explode devolvia lista vazia e a capa
    saía dizendo "nenhuma prescrição aprovada" para um paciente que tem cinco.
    Pior: essa capa pela metade era gravada no espelho e virava a reserva de
    emergência daquele paciente, com aparência de dado bom.
    """


def _consultar(sql: str, *params) -> list:
    """Executa e devolve as linhas.

    Levanta :class:`FalhaDeLeitura` quando não deu para consultar. Lista vazia
    significa uma coisa só: o banco respondeu e não havia nada.
    """
    cx = conexao()
    if cx is None:
        raise FalhaDeLeitura("sem conexão")
    try:
        cur = cx.cursor()
        cur.execute(sql, *params)
        return cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("Consulta falhou: %s", exc)
        # Conexão derrubada no meio do expediente é o caso comum; soltar aqui
        # faz a próxima tentativa reconectar em vez de repetir o erro. SOLTAR,
        # e não ``esquecer``: este não é o botão de reconectar, e não deve
        # apagar o impedimento nem o recuo já acumulado.
        _soltar_conexao()
        raise FalhaDeLeitura(str(exc)) from exc


def _txt(valor) -> str:
    """Texto limpo. O DW usa a string ``NA`` como 'não informado' em toda parte,
    e imprimir "NA" na capa seria pior que deixar o campo vazio."""
    t = str(valor if valor is not None else "").strip()
    return "" if t.upper() in ("NA", "NONE") else t


def _data(valor) -> str:
    """``datetime`` do banco → ``DD/MM/AAAA``, que é o formato da capa."""
    if valor is None:
        return ""
    try:
        return valor.strftime("%d/%m/%Y")
    except AttributeError:
        return _txt(valor)


# ── Cadastro ────────────────────────────────────────────────────────────────
# Sexo e intenção NÃO estão em texto nas tabelas: são ponteiros para
# ``DimLookup``, que traz a descrição em vários idiomas. ``LookupDescriptionPTB``
# já devolve "Feminino"/"Masculino" e "Curativa"/"Paliativa"/"Pós-op." — o mesmo
# vocabulário da tela, sem tradução a escrever no app.
#
# ``DimLookupID = 0`` é o "NA" do DW: paciente sem sexo informado. Precisa
# continuar chegando VAZIO, para a tela pedir que alguém confira — inventar
# aqui seria a capa afirmar um sexo que ninguém verificou.
_SQL_CADASTRO = """
SELECT TOP 1
       p.PatientId,
       p.PatientFullName,
       p.PatientDateOfBirth,
       lsexo.LookupDescriptionPTB,
       COALESCE(NULLIF(p.PatientMobilePhone, 'NA'),
                NULLIF(p.PatientHomePhone, 'NA'),
                NULLIF(p.PatientWorkPhone, 'NA')),
       p.DimPatientID
  FROM DWH.DimPatient p
  LEFT JOIN DWH.FactPatient fp ON fp.DimPatientID = p.DimPatientID
  LEFT JOIN DWH.DimLookup lsexo
         ON lsexo.DimLookupID = fp.DimLookupID_Gender
        AND lsexo.DimLookupID <> 0
 WHERE p.PatientId = ?
"""

# Convênio: o principal, quando há marcação; senão o primeiro que aparecer.
_SQL_CONVENIO = """
SELECT TOP 1 py.PayorCompanyName,
       COALESCE(NULLIF(fp.PayorPolicyNumber, 'NA'),
                NULLIF(fp.PayorCurrentAccountNumber, 'NA'),
                NULLIF(py.PayorPlanNumber, 'NA'))
  FROM DWH.FactPatientPayor fp
  JOIN DWH.DimPayor py ON py.DimPayorID = fp.DimPayorID
 WHERE fp.DimPatientID = ?
 ORDER BY fp.IsPrimaryPayor DESC, fp.FactPatientPayorID DESC
"""

# Curso mais recente e a intenção dele. Cursos de QA ("C1-QA NAO TRATAR") vêm
# com intenção vazia; ficam por último para não roubarem o lugar do curso real.
_SQL_CURSO = """
SELECT TOP 1 c.DimCourseID, c.CourseId, lint.LookupDescriptionPTB
  FROM DWH.DimCourse c
  LEFT JOIN DWH.DimLookup lint
         ON lint.DimLookupID = c.DimLookupID_TreatmentIntentType
        AND lint.DimLookupID <> 0
 WHERE c.DimPatientID = ?
 ORDER BY CASE WHEN lint.LookupDescriptionPTB IS NULL THEN 1 ELSE 0 END,
          c.CourseStartDateTime DESC
"""

# CID e diagnóstico vêm em colunas SEPARADAS — melhor que o CSV, que colava os
# dois ("C61 Neoplasia maligna da próstata") e obrigava a desfazer com regex.
# Paciente com mais de um diagnóstico: vale o MAIS RECENTE — decisão do serviço
# (18/08/2026), não minha. Cheguei a preferir o diagnóstico vinculado ao curso
# em tratamento; o médico é quem sabe qual dos dois a capa deve mostrar, e a
# resposta foi o mais recente.
#
# O comparador achou 2 casos em 200 (C50.9 × C50.4, C34.8 × C34.3): é onde essa
# escolha aparece, e por isso ela fica escrita aqui em vez de implícita no
# ORDER BY.
_SQL_DIAGNOSTICO = """
SELECT TOP 1 dc.DiagnosisCode,
       COALESCE(NULLIF(dc.DiagnosisFullTitlePTB, 'NA'),
                NULLIF(fd.DiagnosisDescription, 'NA'),
                NULLIF(dc.DiagnosisClinicalDescriptionPTB, 'NA'))
  FROM DWH.FactPatientDiagnosis fd
  JOIN DWH.DimDiagnosisCode dc
    ON dc.DimDiagnosisCodeID = fd.DimDiagnosisCodeID
 WHERE fd.DimPatientID = ?
 ORDER BY fd.DiagnosisStatusDate DESC, fd.FactPatientDiagnosisID DESC
"""

# Médico: ``DimPatientDoctor`` liga por ctrResourceSer, NÃO por DimDoctorID —
# essa coluna não existe lá, e supor que existia foi o único erro de join do
# mapeamento. ``OncologistFlag`` separa o radio-oncologista do resto da equipe.
_SQL_MEDICO = """
SELECT TOP 1 d.DoctorFullName
  FROM DWH.DimPatientDoctor pd
  JOIN DWH.DimDoctor d ON d.ctrResourceSer = pd.ctrResourceSer
 WHERE pd.DimPatientID = ?
 ORDER BY pd.OncologistFlag DESC, pd.PrimaryFlag DESC
"""


# O NOME da máquina em ``DWH.DimMachine`` não é sempre ``MachineId`` puro —
# várias linhas têm ``MachineId = 'NA'``, e o nome de verdade só está em
# ``MachineAliasName`` ou ``MachineFullName``. Fragmento ÚNICO (assume o
# alias ``m`` para ``DimMachine`` no FROM de quem usa) para toda consulta
# que precisa casar ou exibir o nome da máquina a partir de ``DimMachine`` —
# ``tratamento_db`` usa o mesmo, para não divergir se a regra mudar de novo.
SQL_NOME_MAQUINA = ("COALESCE(NULLIF(m.MachineId, 'NA'), "
                    "NULLIF(m.MachineAliasName, 'NA'), "
                    "NULLIF(m.MachineFullName, 'NA'))")

# Máquina: chega ao paciente por ``FactTreatmentHistory``, não pelo plano —
# ``DimPlan`` não tem coluna de máquina. As colunas certas são
# ``DimPlanMachineID`` (a planejada) e ``DimActualMachineID`` (onde a sessão foi
# de fato aplicada); minhas duas primeiras tentativas erraram esses nomes, e o
# banco respondeu "Invalid column name" — que é o erro bom, o que aparece na
# hora.
#
# Vale a PLANEJADA: a capa é conferida antes do tratamento, e diz em que
# acelerador o paciente deve ser posicionado. A "atual" varia por sessão quando
# há remanejamento, e imprimir isso faria a folha discordar do plano.
#
# E vale a máquina DO CURSO da capa, não a do paciente. Um paciente pode ter
# mais de um curso ATIVO ao mesmo tempo (o usuário, 31/08/2026), e a consulta
# por paciente devolvia a máquina da última sessão TRATADA — que é a do curso
# antigo enquanto o curso novo não começou. A capa do curso novo saía mandando
# posicionar no acelerador do outro tratamento.
#
# ``FactTreatmentHistory.DimCourseID`` é a coluna que amarra as duas coisas; ela
# já é o filtro da aba Tratamento, conferida contra o banco em 19/08/2026 (ver
# ``tratamento_db._SQL_CURSOS``), então não é palpite de esquema.
_SQL_MAQUINA_DO_CURSO = f"""
SELECT TOP 1 {SQL_NOME_MAQUINA}
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimMachine m
    ON m.DimMachineID = COALESCE(NULLIF(th.DimPlanMachineID, 0),
                                 th.DimActualMachineID)
 WHERE th.DimPatientID = ? AND th.DimCourseID = ?
 ORDER BY th.LastTreatmentDate DESC, th.FirstTreatmentDate DESC
"""

# A mesma pergunta sem o curso. Continua existindo como RESERVA: curso recém
# criado pode ainda não ter linha de máquina, e capa sem máquina é pior que
# capa com a máquina do curso anterior — ali pelo menos há o que conferir.
_SQL_MAQUINA = f"""
SELECT TOP 1 {SQL_NOME_MAQUINA}
  FROM DWH.FactTreatmentHistory th
  JOIN DWH.DimMachine m
    ON m.DimMachineID = COALESCE(NULLIF(th.DimPlanMachineID, 0),
                                 th.DimActualMachineID)
 WHERE th.DimPatientID = ?
 ORDER BY th.LastTreatmentDate DESC, th.FirstTreatmentDate DESC
"""


def cadastro_do_paciente(registro: str) -> Optional[capa_dados.Cadastro]:
    """O cadastro deste paciente vindo do banco, ou ``None``.

    ``None`` quer dizer "não deu para saber" — banco desligado, fora do ar ou
    paciente ausente — e é o sinal para quem chamou cair nos relatórios. Não é
    a mesma coisa que um cadastro com campos vazios.
    """
    alvo = str(registro or "").strip()
    if not alvo:
        return None
    try:
        linhas = _consultar(_SQL_CADASTRO, alvo)
    except FalhaDeLeitura:
        return None
    if not linhas:
        return None
    pid, nome, ddn, sexo, fone, chave = linhas[0]

    cad = capa_dados.Cadastro(
        registro=_txt(pid),
        # Vem invertido E em caixa alta ("SICRANA, JOANA HELENA"), igual ao CSV.
        nome=capa_dados.de_pessoa(_txt(nome)),
        nascimento=_data(ddn),
        sexo=_txt(sexo),
        contato=_txt(fone),
    )
    conv = _consultar(_SQL_CONVENIO, chave)
    if conv:
        empresa, numero = _txt(conv[0][0]), _txt(conv[0][1])
        # Quando não há carteirinha, o banco repete o nome do convênio no campo
        # do número — e a capa saía "Fusex - Fusex". Número que é o próprio nome
        # não é número.
        if numero.strip().lower() == empresa.strip().lower():
            numero = ""
        cad.convenio = capa_dados._convenio(empresa, numero)
    curso = _consultar(_SQL_CURSO, chave)
    curso_id = None
    if curso:
        curso_id = curso[0][0]
        cad.curso = _txt(curso[0][1])
        cad.intencao = _txt(curso[0][2])
    diag = _consultar(_SQL_DIAGNOSTICO, chave)
    if diag:
        cad.cid = _txt(diag[0][0])
        cad.descricao = _txt(diag[0][1])
    # A máquina DO CURSO que a capa está mostrando; sem ela, a do paciente.
    maq = (_consultar(_SQL_MAQUINA_DO_CURSO, chave, curso_id)
           if curso_id is not None else [])
    if not maq:
        maq = _consultar(_SQL_MAQUINA, chave)
    if maq:
        cad.maquina = _txt(maq[0][0])
    med = _consultar(_SQL_MEDICO, chave)
    if med:
        # ``DoctorFullName`` vem invertido ("Monteiro, Paula Monteiro Aragao"),
        # como o nome do paciente. O comparador pegou: 200 de 200 divergiram do
        # CSV por isto, e era o MESMO médico em todas.
        cad.medico = capa_dados.de_pessoa(_txt(med[0][0]))
    # ``status`` fica vazio: o DW não tem o "ATIVO/ALTA" do relatório, e
    # preencher com palpite faria ``curso_ativo()`` mentir.
    return cad


# ── Prescrições ─────────────────────────────────────────────────────────────
# Mesma consulta do relatório (consulta_prescricoes.sql), com o filtro de
# período trocado pelo paciente — é justamente a janela de período que fazia a
# capa nascer pela metade.
_SQL_PRESCRICOES = """
SELECT DISTINCT
       rx.PrescriptionName, rx.Site, crs.CourseId, rx.NumberOfFractions,
       CASE WHEN rx.ApprovedOn < '99990101' THEN rx.ApprovedOn END,
       CASE WHEN CHARINDEX('\\', rx.ApprovedBy) > 0
            THEN SUBSTRING(rx.ApprovedBy, CHARINDEX('\\', rx.ApprovedBy) + 1, 200)
            ELSE NULLIF(rx.ApprovedBy, 'NA') END,
       rx.ctrPrescriptionSer,
       pac.PatientId, pac.PatientFullName
  FROM (SELECT DISTINCT DimPrescriptionID, DimPatientID, DimCourseID
          FROM DWH.FactPatientPrescription) f
  JOIN DWH.DimPrescription rx ON rx.DimPrescriptionID = f.DimPrescriptionID
  JOIN DWH.DimPatient      pac ON pac.DimPatientID    = f.DimPatientID
  LEFT JOIN DWH.DimCourse  crs ON crs.DimCourseID     = f.DimCourseID
 WHERE pac.PatientId = ?
   AND rx.Status <> 'NA'
   AND rx.ApprovedOn IS NOT NULL AND rx.ApprovedOn < '99990101'
 ORDER BY 5 DESC
"""

# Volume, dose e dose/fração são LINHAS em DimPrescriptionAnatomy, uma por alvo.
# A ordem importa: é ela que casa "PTV mama" com a dose dele.
_SQL_ANATOMIA = """
SELECT ItemType, ItemValue, ItemValueUnit
  FROM DWH.DimPrescriptionAnatomy
 WHERE ctrPrescriptionSer = ?
 ORDER BY ctrPrescriptionAnatomySer
"""

_SQL_FREQUENCIA = """
SELECT DISTINCT PropertyValue
  FROM DWH.DimPrescriptionProperty
 WHERE ctrPrescriptionSer = ? AND PropertyType = 7 AND PropertyValue <> 'NA'
"""

# A nota que o radioterapeuta escreveu na prescrição — estadiamento, "após QT",
# o que condiciona o tratamento. Mora em ``DimPrescription.Notes``
# (``VDT_STRING1024``), a ÚNICA coluna do banco com esse nome; medido pela sonda
# do ``tools/mapear_dw.py`` em 23/09/2026, porque o esquema do DWH não é público
# e coluna parecida devolveria texto plausível e errado numa folha que vai para
# a sala.
#
# Em consulta própria, e não junto do ``_SQL_PRESCRICOES``: aquele é um SELECT
# DISTINCT, e uma coluna a mais nele passaria a distinguir revisões que hoje
# colapsam numa linha só — a mesma prescrição apareceria duas vezes na lista de
# escolha da capa. Aqui a linha é escolhida: a nota NÃO VAZIA mais recente.
_SQL_NOTAS = """
SELECT TOP 1 Notes
  FROM DWH.DimPrescription
 WHERE ctrPrescriptionSer = ?
   AND NULLIF(LTRIM(RTRIM(Notes)), '') IS NOT NULL
 ORDER BY HstryDateTime DESC
"""


def _volumes(ctr_ser) -> list:
    """Os alvos de uma prescrição, em cGy — a unidade que a capa imprime."""
    nomes, doses, fracoes = [], [], []
    for tipo, valor, unidade in _consultar(_SQL_ANATOMIA, ctr_ser):  # pode levantar
        tipo = _txt(tipo).upper()
        texto = _txt(valor) + (f" {_txt(unidade)}" if _txt(unidade) else "")
        if tipo == "VOLUME ID":
            nomes.append(_txt(valor))
        elif tipo == "TOTAL DOSE":
            doses.append(texto)
        elif tipo.startswith("DOSE PER FRA"):
            fracoes.append(texto)
    return [capa_dados.Volume(
                nome=n,
                dose_cgy=capa_dados._gy_para_cgy(doses[i] if i < len(doses) else ""),
                dose_frac_cgy=capa_dados._gy_para_cgy(
                    fracoes[i] if i < len(fracoes) else ""))
            for i, n in enumerate(nomes)]


def _notas(ctr_ser) -> str:
    """A nota desta prescrição, ou "" — nunca um erro que derrube a capa.

    Falha aqui devolve vazio de propósito: a nota é um complemento do bloco, e
    perder a capa inteira por causa dela seria trocar um campo em branco por
    nenhuma folha. Quem lê continua vendo a prescrição, a dose e os volumes.
    """
    try:
        linhas = _consultar(_SQL_NOTAS, ctr_ser)
    except FalhaDeLeitura:
        _LOG.warning("Não consegui ler a nota da prescrição %s", ctr_ser)
        return ""
    return _txt(linhas[0][0]) if linhas else ""


def prescricoes_do_paciente(registro: str) -> list:
    """As prescrições APROVADAS deste paciente. Lista vazia se não deu."""
    alvo = str(registro or "").strip()
    if not alvo:
        return []
    fora = []
    for linha in _consultar(_SQL_PRESCRICOES, alvo):   # pode levantar
        (nome_rx, site, curso, fracoes, aprovado_em, aprovador, ctr_ser,
         pid, pnome) = linha
        freq = _consultar(_SQL_FREQUENCIA, ctr_ser)   # pode levantar
        fora.append(capa_dados.Prescricao(
            site=capa_dados.traduzir_site(_txt(site)),
            descricao=_txt(nome_rx),
            volumes=_volumes(ctr_ser),
            fracoes=_txt(fracoes),
            frequencia=capa_dados.traduzir_frequencia(
                _txt(freq[0][0]) if freq else ""),
            notas=_notas(ctr_ser),
            aprovador=_txt(aprovador),
            data_aprovacao=_data(aprovado_em),
            curso=_txt(curso),
            registro_bruto=_txt(pid),
            nome_bruto=_txt(pnome),
        ))
    return fora


# ── Foto 3×4 ────────────────────────────────────────────────────────────────
# O JPEG está em blob, alcançável por paciente. Substitui o relatório .mhtml de
# 190 MB, que além do tamanho cobria 3 979 pacientes — a tabela tem 18 657.
_SQL_FOTO = """
SELECT TOP 1 ph.Picture
  FROM DWH.DimPatientPhoto ph
  JOIN DWH.DimPatient p ON p.DimPatientID = ph.DimPatientID
 WHERE p.PatientId = ? AND ph.Picture IS NOT NULL
 ORDER BY ph.DimPatientPhotoID DESC
"""


def foto_do_paciente(registro: str) -> Optional[bytes]:
    """A 3×4 deste paciente, ou ``None``."""
    alvo = str(registro or "").strip()
    if not alvo:
        return None
    try:
        linhas = _consultar(_SQL_FOTO, alvo)
    except FalhaDeLeitura:
        return None
    if not linhas or not linhas[0][0]:
        return None
    dados = bytes(linhas[0][0])
    # Assinatura JPEG/PNG: blob truncado ou lixo vira "sem foto" em vez de um
    # retângulo quebrado na capa impressa.
    if not (dados.startswith(b"\xff\xd8") or dados.startswith(b"\x89PNG")):
        _LOG.warning("Foto de %s não parece imagem (%d bytes).", alvo, len(dados))
        return None
    return dados


# ── Lista de pacientes (busca da tela) ──────────────────────────────────────
_SQL_PACIENTES = """
SELECT p.PatientId, p.PatientFullName, p.PatientDateOfBirth
  FROM DWH.DimPatient p
 WHERE p.PatientId <> 'NA' AND p.PatientId IS NOT NULL
   AND ISNULL(p.IsMOTestPatient, 0) = 0
"""


def pacientes() -> list:
    """Todos os pacientes, para a busca da tela. Vazio se o banco não deu.

    ``IsMOTestPatient`` fora: o banco tem pacientes de teste ("teste2",
    "Eclipse CAP") que não são gente, e oferecê-los na busca de quem está
    montando uma ficha é convite a erro.
    """
    fora = []
    try:
        linhas = _consultar(_SQL_PACIENTES)
    except FalhaDeLeitura:
        return []
    for pid, nome, ddn in linhas:
        fora.append(capa_dados.PacienteRef(
            nome=capa_dados.de_pessoa(_txt(nome)),
            registro=_txt(pid),
            nascimento=_data(ddn)))
    return fora
