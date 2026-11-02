r"""Falar DICOM com o DB Daemon do ARIA — trazer imagem e plano.

A outra metade da exportação automática. O ``gatilho_db`` diz QUAL plano sair,
pelo ``PlanUID`` que o data warehouse entrega; este módulo é quem vai buscar os
arquivos.

**Só leitura**, como o resto: nada aqui escreve no sistema clínico. As três
operações usadas são C-ECHO (verificar), C-FIND (perguntar) e C-GET/C-MOVE
(trazer).

**C-GET antes de C-MOVE, e por quê.** As duas trazem os mesmos objetos, e a
diferença é operacional, não clínica:

* no **C-GET** os arquivos voltam pela MESMA conexão que pediu. Não é preciso
  ouvir porta nenhuma, nem liberar entrada no firewall, nem registrar um AE de
  destino na configuração do ARIA;
* no **C-MOVE** o servidor abre uma conexão NOVA para um AE de destino que
  precisa estar cadastrado no ARIA. É mais configuração, feita por outra
  equipe, e cada estação nova repete o pedido.

Nem todo servidor implementa C-GET — historicamente o DB Daemon da Varian é
forte em C-FIND/C-MOVE. Por isso os dois estão aqui e :func:`sondar` descobre,
contra o servidor de verdade, qual funciona. **Escolher no chute qual usar era
a mesma armadilha das consultas montadas sobre nome de tabela adivinhado.**

**E a sonda respondeu, em 10/09/2026: este ARIA não faz C-GET.** Seis variantes
de associação contra o servidor de verdade — o daemon aceita os 4 contextos de
storage e NÃO aceita o do Get (``1.2.840.10008.5.1.4.1.2.1.3``); ``GET`` sozinho
é recusado por não sobrar contexto nenhum, e daí saía o "No reason given" que
parecia mudo. O caminho é o C-MOVE, com :func:`receber` ouvindo desta ponta. O
C-GET fica para um servidor que o tenha — não como reserva deste, porque
reserva que não funciona é pior que reserva nenhuma.

Configuração, em DOIS degraus desde 14/09/2026 — **variável da estação →
configuração do serviço** (:mod:`config_servico`), a mesma escada do
``gatilho.pasta_destino``:

| variável | chave do serviço | o quê |
|---|---|---|
| ``ISOCENTRO_DICOM_SERVIDOR`` | ``dicom_servidor`` | ``host:porta`` do DB Daemon |
| ``ISOCENTRO_DICOM_AE_REMOTO`` | ``dicom_ae_remoto`` | o AE Title do ARIA |
| ``ISOCENTRO_DICOM_AE_LOCAL``  | ``dicom_ae_local`` | o AE Title desta estação, cadastrado no ARIA |
| ``ISOCENTRO_DICOM_AE_DESTINO``| ``dicom_ae_destino`` | só para C-MOVE: para onde o ARIA manda |
| ``ISOCENTRO_DICOM_PORTA_ESCUTA`` | — | só para C-MOVE: a porta em que esta ponta ouve |

**Por que o segundo degrau existe**, e não é simetria: a varredura passou a
poder rodar por TAREFA AGENDADA na concentradora, e tarefa agendada roda com
OUTRA conta do Windows. ``ambiente.ler`` é ``os.environ`` puro, e variável de
usuário não atravessa conta — com os ``ISOCENTRO_DICOM_*`` no usuário
interativo, a tarefa chamaria :func:`configurado` → falso e não exportaria
nada, com o Agendador verde. A configuração do serviço vale para qualquer
conta da máquina.

A ``PORTA_ESCUTA`` ficou de fora de propósito: o padrão 104 é a porta que a TI
liberou em 10/09/2026, e chave que ninguém preenche é campo a mais na tela do
admin. Se um dia a porta mudar, ela entra pelo mesmo caminho das outras.

Sem nenhum dos dois degraus o módulo não tenta adivinhar: :func:`configurado` é
falso e :func:`motivo_indisponivel` diz qual falta, pela mesma regra do
``capa_db``.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from isocentro.dados import ambiente

_LOG = logging.getLogger(__name__)

ENV_SERVIDOR = "ISOCENTRO_DICOM_SERVIDOR"
ENV_AE_REMOTO = "ISOCENTRO_DICOM_AE_REMOTO"
ENV_AE_LOCAL = "ISOCENTRO_DICOM_AE_LOCAL"
ENV_AE_DESTINO = "ISOCENTRO_DICOM_AE_DESTINO"
ENV_PORTA_ESCUTA = "ISOCENTRO_DICOM_PORTA_ESCUTA"

# 104 é a porta registrada do DICOM; a literatura dá 51402 como a do DB Daemon
# da Varian. Não há padrão que sirva para as duas, então o padrão aqui é só a
# porta oficial e quem configura escreve a de verdade — chutar 51402 faria "não
# respondeu" parecer servidor fora do ar.
#
# E o chute teria mentido: MEDIDO no CLINICA em 04/09/2026, a 51402 nem está
# ouvindo. O serviço de consulta é o "Varian DB Service ARIA", em
# ``srvariadb.clinica.example:51404``, com AE Title ``ARIA`` — descoberto pelas
# regras de FIREWALL do servidor, que nomeiam o serviço de cada porta. Fica
# escrito aqui como referência, não como padrão: é configuração desta clínica,
# e o dia em que ela mudar, o valor no código estaria mentindo de novo.
PORTA_PADRAO = 104

# Prazo de uma operação. Generoso de propósito: trazer uma série de CT inteira
# por rede de clínica leva minutos, e cortar no meio deixa o conjunto
# incompleto na pasta — que é o desfecho que a marca d'água não pode registrar
# como sucesso.
SEGUNDOS = 600

# Prazo só do APERTO DE MÃO, e por isso separado do de cima: o A-ASSOCIATE se
# resolve em milissegundos quando há um DICOM do outro lado, e esperar os 600 s
# da transferência por ele só adiaria a má notícia. O VALOR não mudou em
# 14/09/2026 — o que ganhou nome foi o 60 que estava cravado na linha do
# ``ae.acse_timeout``, para o teste poder apertá-lo: uma porta que aceita TCP e
# não fala DICOM deixa o cronômetro correr inteiro, e ``PortaQueNaoFalaDicom``
# sozinho custava 60,1 s dos 270 s da suíte.
ACSE_SEGUNDOS = 60

# O que se vai buscar, e a ordem. O RTPLAN primeiro porque é dele que saem as
# referências para o resto; a CT por último porque é a maior.
CLASSES = ("RTPLAN", "RTSTRUCT", "RTDOSE", "CT")


class FalhaDeRede(Exception):
    """Não deu para falar com o servidor, ou ele recusou.

    Separada de "não achei nada": as duas dão zero arquivos e pedem
    providências opostas — chamar a TI, ou conferir se o plano é esse mesmo.
    Confundi-las faria a automação parar em silêncio, que é o modo de falha que
    este projeto inteiro tenta evitar.
    """


@dataclass
class Resultado:
    """O que voltou de uma operação de transferência."""
    arquivos: list = field(default_factory=list)
    falhas: int = 0
    avisos: int = 0
    modo: str = ""              # "C-GET" ou "C-MOVE"

    @property
    def completo(self) -> bool:
        """Chegou inteiro?

        ``falhas`` zero E pelo menos um arquivo. As duas condições: uma
        transferência que não falhou e não trouxe nada é tão incompleta quanto
        uma que falhou, e só a segunda tem contador diferente de zero.
        """
        return bool(self.arquivos) and self.falhas == 0


def _do_servico(env: str) -> str:
    """O que o admin gravou para esta variável, no ``config_servico``.

    Import TARDIO pelo mesmo motivo do ``gatilho.pasta_destino``: o que sobra
    de erro aqui é ``ImportError``, isto é, o módulo fora do pacote na clínica
    — e o ``valor()`` já engole ``OSError`` e ``ValueError`` sozinho. Cair
    calado faria a estação parecer desconfigurada quando o defeito é de
    empacotamento, que pede outra providência.

    O mapa está AQUI, num lugar só. A chave repetida em cada acessor seria a
    armadilha das duas grafias: o admin preenche o campo e o app lê outro nome,
    sem erro nenhum na tela.
    """
    try:
        from isocentro.dados import config_servico
        chave = {
            ENV_SERVIDOR: config_servico.DICOM_SERVIDOR,
            ENV_AE_REMOTO: config_servico.DICOM_AE_REMOTO,
            ENV_AE_LOCAL: config_servico.DICOM_AE_LOCAL,
            ENV_AE_DESTINO: config_servico.DICOM_AE_DESTINO,
        }.get(env, "")
        return config_servico.valor(chave) if chave else ""
    except Exception:  # noqa: BLE001
        _LOG.exception("Não deu para ler a configuração DICOM do serviço (%s)",
                       env)
        return ""


def _valor(env: str) -> str:
    """Variável da estação → configuração do serviço. Ver a docstring do módulo."""
    return ambiente.ler(env) or _do_servico(env)


def origem_da_configuracao() -> str:
    """Qual degrau está valendo — para a tela e para o ``--conferir`` dizerem.

    Mesma razão do ``gatilho.origem_da_pasta``: quem aponta o servidor na tela
    do admin e não vê efeito não tem como descobrir que uma variável local está
    mandando nele. Na concentradora isso é pior, porque o degrau que vale muda
    com a CONTA que roda — e o sintoma dos dois casos é o mesmo silêncio.
    """
    # As QUATRO, e cada uma pelo nome que valeu. Até 18/09/2026 o teste olhava
    # só as três primeiras e o texto nomeava sempre a do servidor: um
    # ``ISOCENTRO_DICOM_AE_DESTINO`` na conta da tarefa — justamente o que decide
    # para onde o ARIA manda os arquivos — não aparecia, e o ``--conferir``
    # dizia "configuração do serviço" com o destino vindo de outro lugar.
    locais = [ambiente.qual_valeu(e) for e in _ENVS_REDE if ambiente.ler(e)]
    servico = bool(_do_servico(ENV_SERVIDOR) or _do_servico(ENV_AE_REMOTO))
    if locais:
        texto = (f"variável {locais[0]}" if len(locais) == 1 else
                 f"variáveis {', '.join(locais)}")
        texto += " desta estação (vale só para esta conta do Windows)"
        if servico and not configurado_pela_estacao():
            texto += "; o resto, da configuração do serviço"
        return texto
    if servico:
        return "configuração do serviço (vale para qualquer conta)"
    return "nenhum dos dois — a rede DICOM não está configurada"


# As variáveis da rede, na ordem em que a tela e o ``--conferir`` as nomeiam.
_ENVS_REDE = (ENV_SERVIDOR, ENV_AE_REMOTO, ENV_AE_LOCAL, ENV_AE_DESTINO)


def configurado_pela_estacao() -> bool:
    """As três peças sem as quais nada sai vêm TODAS de variável desta conta?

    É a pergunta do ``gatilho`` para decidir quem varre (18/09/2026): a rede
    configurada só por variável é decisão de instalação de UMA máquina — o
    regime de 11/09, em que "só a concentradora tem ``ISOCENTRO_DICOM_*``" bastava
    para só ela varrer. Basta UMA das três vir do ``config_servico``, que é o
    mesmo arquivo para todas as estações, e a decisão deixa de ser da máquina.

    O destino fica de fora: sem ele o C-MOVE não tem para onde mandar, mas
    :func:`configurado` também não o exige, e a pergunta aqui é a mesma dele.
    """
    return all(ambiente.ler(e) for e in (ENV_SERVIDOR, ENV_AE_REMOTO,
                                         ENV_AE_LOCAL))


def servidor() -> tuple:
    """``(host, porta)``, ou ``("", 0)`` se não houver."""
    bruto = _valor(ENV_SERVIDOR)
    if not bruto:
        return "", 0
    host, _, porta = bruto.partition(":")
    try:
        return host.strip(), int(porta) if porta.strip() else PORTA_PADRAO
    except ValueError:
        # Porta com lixo não vira o padrão calado: viraria "não respondeu" numa
        # porta que ninguém pediu.
        return host.strip(), 0


def ae_remoto() -> str:
    return _valor(ENV_AE_REMOTO)


def ae_local() -> str:
    return _valor(ENV_AE_LOCAL)


def ae_destino() -> str:
    return _valor(ENV_AE_DESTINO)


def porta_escuta() -> int:
    """A porta em que ESTA ponta ouve o C-MOVE.

    104 por padrão porque é a porta registrada do DICOM e foi a que a TI
    liberou em 10/09/2026. Fica configurável porque o número entra em três
    lugares que outra equipe controla — o cadastro do AE de destino no ARIA, a
    regra de firewall de ENTRADA e este processo — e um desencontro entre eles
    aparece como ``0 objeto(s), 1 falha`` depois de 21 s de espera, que é o
    sintoma mais mudo do circuito inteiro.
    """
    return int(ambiente.ler(ENV_PORTA_ESCUTA, "") or PORTA_PADRAO)


def configurado() -> bool:
    host, porta = servidor()
    return bool(host and porta and ae_remoto() and ae_local())


def motivo_indisponivel() -> str:
    """Qual peça falta, nomeando a variável — não "configuração incompleta".

    Quem lê isto vai pedir a informação para a TI, e o pedido precisa dizer o
    que é. Cada uma destas quatro vem de uma pessoa diferente.
    """
    host, porta = servidor()
    if not host:
        return (f"Falta o endereço do servidor DICOM do ARIA "
                f"({ENV_SERVIDOR}, no formato servidor:porta, ou o campo "
                "correspondente em Configurações → Serviço).")
    if not porta:
        return (f"A porta em {ENV_SERVIDOR} não é um número: "
                f"{_valor(ENV_SERVIDOR)!r}.")
    if not ae_remoto():
        return f"Falta o AE Title do ARIA ({ENV_AE_REMOTO})."
    if not ae_local():
        return (f"Falta o AE Title desta estação ({ENV_AE_LOCAL}). Ele precisa "
                "estar cadastrado no ARIA, senão a conexão é recusada.")
    return ""


def _pynetdicom():
    """Importa na hora de usar, e explica a ausência.

    Import tardio de propósito: o ``pynetdicom`` é opcional, como o ``pyodbc``,
    e o app inteiro tem de subir sem ele. **Mas import tardio é justamente o
    que some do executável em silêncio** (ver CLAUDE.md) — por isso ele está
    nomeado no ``tools/gerar_executavel.py``, e a falha aqui diz o que fazer em
    vez de aparecer como ``ModuleNotFoundError`` cru na tela da clínica.
    """
    try:
        import pynetdicom
    except ImportError as exc:
        raise FalhaDeRede(
            "A biblioteca de rede DICOM (pynetdicom) não está instalada nesta "
            "estação. Sem ela não dá para buscar imagem nem plano no ARIA."
        ) from exc
    return pynetdicom


def motivo_da_recusa(assoc) -> str:
    """O que o servidor respondeu no A-ASSOCIATE-RJ, em palavras.

    O DICOM distingue "called AE title not recognised" (o AE de LÁ está errado
    — é chute nosso, e se conserta aqui trocando um parâmetro) de "calling AE
    title not recognised" (o NOSSO não está cadastrado, e só a Varian resolve).
    **As duas pedem providências opostas**, e quem lê "recusou a associação"
    não tem como saber qual delas abrir.

    Custou uma ida em 10/09/2026: a TI subiu o serviço na 51405 e a sondagem
    disse "Costuma ser AE Title não cadastrado no ARIA, ou porta bloqueada" —
    um palpite, com as duas metades do problema empacotadas na mesma frase.
    Foi o ``--varrer``, que já lia o motivo, que soube dizer que o AE DELES
    tinha sido reconhecido e o nosso não. A leitura morava na ferramenta; quem
    associa de verdade é este módulo, e é ele que fala com a clínica.

    Defensivo de propósito: são atributos internos do ``pynetdicom``, e uma
    versão que os mova não pode derrubar a associação — perder o motivo é ruim,
    trocar um diagnóstico por um ``AttributeError`` é pior.
    """
    prim = getattr(getattr(assoc, "acceptor", None), "primitive", None)
    razao = str(getattr(prim, "reason_str", "") or "").strip()
    fonte = str(getattr(prim, "source_str", "") or "").strip()
    if not razao:
        return "sem motivo declarado pelo servidor"
    baixo = razao.lower()
    # A mensagem nomeia a COISA ("o AE do ARIA", "o AE desta estação") e não a
    # variável nem a opção de linha de comando: ela é lida na tela da clínica e
    # no console da sondagem, e cada um desses leitores ajusta o valor por um
    # caminho diferente. Nome de knob aqui estaria errado para metade deles.
    if "called" in baixo:
        return (f"{razao} — quem está errado é o AE do ARIA, não o desta "
                "estação; e esse se corrige aqui")
    if "calling" in baixo:
        return (f"{razao} — o AE DESTA estação não está cadastrado no ARIA; "
                "é a Varian/TI que cadastra")
    if fonte:
        return f"{razao} (de: {fonte})"
    return razao


def _associar(contextos, papel_scp=(), handlers=()):
    """Abre a associação com o ARIA, ou levanta :class:`FalhaDeRede`.

    ``papel_scp`` são as classes em que ESTA ponta também age como servidor —
    é o que o C-GET exige, porque os objetos voltam pela mesma conexão e quem
    pediu precisa saber recebê-los. ``handlers`` vai junto na associação, e não
    depois: ligado depois, o primeiro objeto pode chegar antes do ``bind`` e
    cair no handler padrão, que descarta.
    """
    if not configurado():
        raise FalhaDeRede(motivo_indisponivel())
    _pynetdicom()
    from pynetdicom import AE
    from pynetdicom.presentation import build_role

    host, porta = servidor()
    ae = AE(ae_title=ae_local())
    ae.acse_timeout = ACSE_SEGUNDOS
    ae.dimse_timeout = SEGUNDOS
    ae.network_timeout = SEGUNDOS
    for ctx in contextos:
        ae.add_requested_context(ctx)
    # ``scp_role=True`` e SÓ ele. Propondo os dois papéis, o servidor pode
    # aceitar o de SCU — e num C-GET quem pede é justamente quem RECEBE, então
    # o papel de SCU não serve para nada. Medido contra um servidor de teste em
    # 02/09/2026: com os dois propostos, o acordo saiu "Accepted Role: SCU" e
    # todas as suboperações falharam com "no presentation context ... for the
    # SCU role" — mensagem que aponta para o lado errado do problema.
    papeis = [build_role(c, scp_role=True) for c in papel_scp]
    _LOG.info("Associando a %s:%s (AE %s) como %s",
              host, porta, ae_remoto(), ae_local())
    assoc = ae.associate(host, porta, ae_title=ae_remoto(), ext_neg=papeis,
                         evt_handlers=list(handlers))
    if not assoc.is_established:
        # Sem ``abort()`` aqui, e é decisão, não esquecimento: a associação nem
        # chegou a existir. O ``ResourceWarning`` de socket que aparece na
        # suíte vem do próprio pynetdicom (``transport.py``: ele faz
        # ``_shutdown_socket()`` e depois ``self.socket = None``, sem
        # ``close()``), e quem fecha o descritor é a contagem de referências do
        # CPython. É ruído da dependência, não vazamento nosso — e um
        # ``abort()`` de enfeite aqui daria a impressão de resolver algo.
        onde = (f"{ae_remoto()} em {host}:{porta}, chamando como "
                f"{ae_local()}")
        # RECUSA e SILÊNCIO não são a mesma coisa. Só quem fala o protocolo
        # devolve um A-ASSOCIATE-RJ; porta de outro programa aborta ou emudece,
        # e chamar as duas de "recusou" manda procurar AE Title onde o que há é
        # endereço errado.
        if getattr(assoc, "is_rejected", False):
            raise FalhaDeRede(
                f"{onde}: associação RECUSADA — {motivo_da_recusa(assoc)}")
        raise FalhaDeRede(
            f"{onde}: a porta respondeu, mas não falou DICOM. O endereço ou a "
            f"porta estão errados, ou o firewall barra a SAÍDA para ela.")
    return assoc


def verificar() -> str:
    """C-ECHO: o servidor está lá e aceita esta estação?

    O primeiro degrau, e o que separa "a rede está errada" de "a consulta está
    errada". Devolve texto para a tela; levanta :class:`FalhaDeRede` se nem
    associou.
    """
    from pynetdicom.sop_class import Verification  # noqa: PLC0415

    assoc = _associar([Verification])
    try:
        resposta = assoc.send_c_echo()
    finally:
        assoc.release()
    if not resposta:
        raise FalhaDeRede("O servidor associou mas não respondeu ao C-ECHO.")
    estado = resposta.get("Status", None)
    if estado != 0x0000:
        raise FalhaDeRede(f"C-ECHO devolveu estado 0x{estado:04X}.")
    host, porta = servidor()
    return f"{ae_remoto()} em {host}:{porta} respondeu ao C-ECHO."


def _consulta_do_plano(plan_uid: str):
    """O identificador do C-FIND, no nível de INSTÂNCIA.

    ``QueryRetrieveLevel = IMAGE`` com ``SOPInstanceUID``: é a consulta mais
    estreita que existe, e é possível porque o ``PlanUID`` do data warehouse é
    exatamente esse UID. Sem ele seria preciso casar por paciente e data, que
    é como se traz o plano do curso errado.
    """
    from pydicom.dataset import Dataset  # noqa: PLC0415

    ds = Dataset()
    ds.QueryRetrieveLevel = "IMAGE"
    ds.SOPInstanceUID = plan_uid
    ds.PatientID = ""
    ds.StudyInstanceUID = ""
    ds.SeriesInstanceUID = ""
    ds.Modality = ""
    return ds


def _consulta_da_serie(series_uid: str):
    """O identificador do C-FIND/C-MOVE no nível de SÉRIE.

    A CT não se pede objeto a objeto: são centenas de instâncias, e um C-MOVE
    por instância seria uma associação por corte. No nível de série o pedido é
    um só e o servidor manda a série inteira pela conexão que ELE abre.
    """
    from pydicom.dataset import Dataset  # noqa: PLC0415

    ds = Dataset()
    ds.QueryRetrieveLevel = "SERIES"
    ds.SeriesInstanceUID = series_uid
    return ds


def censo_do_estudo(study_uid: str) -> list:
    """O que o estudo TEM, série por série, sem trazer nada.

    Devolve dicionários com ``modalidade``, ``serie``, ``instancias`` e
    ``descricao``. É a medida que separa "a CT é a próxima frente" de "a CT é
    a próxima frente e custa 400 objetos por paciente": pedir a contagem custa
    uma associação, e trazer para descobrir custa a transferência inteira.

    ``NumberOfSeriesRelatedInstances`` é opcional no padrão — servidor que não
    o preencha devolve ``instancias`` em ``-1``, e isso é diferente de zero.
    Zero seria a afirmação de que a série está vazia; ``-1`` é o servidor não
    tendo dito.
    """
    from pydicom.dataset import Dataset  # noqa: PLC0415
    from pynetdicom.sop_class import (  # noqa: PLC0415
        PatientRootQueryRetrieveInformationModelFind as Find)

    if not study_uid:
        return []
    ds = Dataset()
    ds.QueryRetrieveLevel = "SERIES"
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = ""
    ds.Modality = ""
    ds.SeriesDescription = ""
    ds.NumberOfSeriesRelatedInstances = ""
    assoc = _associar([Find])
    series = []
    try:
        for estado, ident in assoc.send_c_find(ds, Find):
            if not estado:
                raise FalhaDeRede("A conexão caiu durante o censo do estudo.")
            if ident is None:
                continue
            quantas = getattr(ident, "NumberOfSeriesRelatedInstances", None)
            series.append({
                "modalidade": str(getattr(ident, "Modality", "") or "?"),
                "serie": str(getattr(ident, "SeriesInstanceUID", "") or ""),
                "descricao": str(getattr(ident, "SeriesDescription", "") or ""),
                "instancias": int(quantas) if quantas not in (None, "") else -1,
            })
    finally:
        assoc.release()
    return series


def contar_instancias(series_uid: str, limite: int = 2000) -> int:
    """Conta os objetos de uma série perguntando um a um. Devolve -1 se não deu.

    Existe porque **o ARIA desta clínica não preenche**
    ``NumberOfSeriesRelatedInstances`` — medido no ``clinica-python01`` em
    10/09/2026, onde o censo devolveu sete modalidades e a contagem vazia em
    todas. O campo é opcional no padrão, e sem ele a única forma de saber o
    tamanho da CT é listar as instâncias.

    Custa uma associação e N respostas de metadado — não traz pixel nenhum. É
    caro o bastante para não se fazer por série do estudo inteiro, e barato o
    bastante para valer nas de CT, que são as que decidem o orçamento da
    próxima frente.

    O ``limite`` existe para o caso de uma série absurda (uma 4D com dezenas de
    fases): passar dele devolve o que contou, e quem lê sabe que é piso.
    """
    from pydicom.dataset import Dataset  # noqa: PLC0415
    from pynetdicom.sop_class import (  # noqa: PLC0415
        PatientRootQueryRetrieveInformationModelFind as Find)

    if not series_uid:
        return -1
    ds = Dataset()
    ds.QueryRetrieveLevel = "IMAGE"
    ds.SeriesInstanceUID = series_uid
    ds.SOPInstanceUID = ""
    assoc = _associar([Find])
    quantas = 0
    try:
        for estado, ident in assoc.send_c_find(ds, Find):
            if not estado:
                return -1
            if ident is not None:
                quantas += 1
                if quantas >= limite:
                    break
    except Exception:  # noqa: BLE001
        _LOG.exception("Não deu para contar as instâncias de %s", series_uid)
        return -1
    finally:
        assoc.release()
    return quantas


def achar_plano(plan_uid: str) -> list:
    """C-FIND pelo UID do plano. Lista vazia significa "não existe lá".

    Levanta :class:`FalhaDeRede` só quando não deu para perguntar — a distinção
    do ``FalhaDeLeitura`` do ``capa_db``, e pela mesma razão.
    """
    from pynetdicom.sop_class import (  # noqa: PLC0415
        PatientRootQueryRetrieveInformationModelFind as Find)

    assoc = _associar([Find])
    achados = []
    try:
        for estado, ident in assoc.send_c_find(_consulta_do_plano(plan_uid),
                                               Find):
            if not estado:
                raise FalhaDeRede("A conexão caiu durante o C-FIND.")
            if ident is not None:
                achados.append(ident)
    finally:
        assoc.release()
    return achados


def _guardar(ds, pasta: Path) -> Path:
    """Grava um objeto recebido. O nome é o UID: é único e não colide.

    Nome legível ("plano.dcm") pareceria mais amigável e sobrescreveria o
    segundo objeto da mesma classe — e um conjunto com um arquivo a menos não
    se distingue, de fora, de um conjunto completo.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    uid = getattr(ds, "SOPInstanceUID", "") or "sem-uid"
    alvo = pasta / f"{uid}.dcm"
    ds.save_as(alvo, enforce_file_format=True)
    return alvo


def _gravador(destino: Resultado, pasta: Path):
    """O handler de ``EVT_C_STORE``, compartilhado pelo C-GET e pelo C-MOVE.

    Devolver o ESTADO é o que faz o servidor contar a suboperação como falha.
    Sem isso, um disco cheio no meio da transferência sairia como "pronto", e a
    marca d'água registraria como exportado um conjunto incompleto — que é
    exatamente o que ``Resultado.completo`` existe para impedir.
    """
    def _ao_receber(evento):
        try:
            ds = evento.dataset
            ds.file_meta = evento.file_meta
            destino.arquivos.append(_guardar(ds, pasta))
        except Exception:  # noqa: BLE001
            _LOG.exception("Não deu para gravar um objeto recebido")
            return 0xA700
        return 0x0000

    return _ao_receber


def baixar(plan_uid: str, pasta) -> Resultado:
    """C-GET: traz os objetos pela MESMA conexão. Sem porta de entrada.

    É o caminho preferido quando o servidor o implementa — não exige AE de
    destino cadastrado nem firewall aberto para dentro. :func:`sondar` diz se
    este ARIA o implementa.
    """
    from pynetdicom.sop_class import (  # noqa: PLC0415
        CTImageStorage, PatientRootQueryRetrieveInformationModelGet as Get,
        RTDoseStorage, RTPlanStorage, RTStructureSetStorage)

    from pynetdicom import evt  # noqa: PLC0415

    pasta = Path(pasta)
    guardados = Resultado(modo="C-GET")
    classes = [RTPlanStorage, RTStructureSetStorage, RTDoseStorage,
               CTImageStorage]

    assoc = _associar([Get, *classes], papel_scp=classes,
                      handlers=[(evt.EVT_C_STORE, _gravador(guardados, pasta))])
    try:
        for estado, _ident in assoc.send_c_get(_consulta_do_plano(plan_uid),
                                               Get):
            if not estado:
                raise FalhaDeRede("A conexão caiu durante o C-GET.")
            guardados.falhas = int(getattr(estado, "NumberOfFailedSuboperations",
                                           0) or 0)
            guardados.avisos = int(getattr(estado, "NumberOfWarningSuboperations",
                                           0) or 0)
    finally:
        assoc.release()
    return guardados


def sondar(plan_uid: str, pasta=None) -> dict:
    """Descobre, contra o servidor de VERDADE, o que ele implementa.

    Existe pela mesma razão do ``tools/mapear_gatilho.py``: escolher entre
    C-GET e C-MOVE no chute é decidir sobre o que não se mediu. O manual diz
    que o DB Daemon da Varian é forte em C-FIND/C-MOVE; se ele também fizer
    C-GET, some a exigência de AE de destino cadastrado e de porta aberta para
    dentro — e isso vale uma conversa a menos com a TI.

    Cada degrau é tentado mesmo que o anterior falhe, e a falha entra no
    relatório em vez de interromper: é o mapa do que funciona que se quer, não
    o primeiro erro.
    """
    import tempfile

    achados = {"configurado": configurado(), "motivo": motivo_indisponivel(),
               "echo": "", "find": "", "get": "", "move": ""}
    if not configurado():
        return achados
    for nome, funcao in (("echo", lambda: verificar()),
                         ("find", lambda: _resumo_find(plan_uid))):
        try:
            achados[nome] = funcao()
        except Exception as exc:  # noqa: BLE001
            achados[nome] = f"FALHOU: {exc}"
    destino = Path(pasta) if pasta else Path(tempfile.mkdtemp())
    try:
        r = baixar(plan_uid, destino)
        achados["get"] = (f"{len(r.arquivos)} arquivo(s), {r.falhas} falha(s), "
                          f"completo={r.completo}, em {destino}")
    except Exception as exc:  # noqa: BLE001
        achados["get"] = f"FALHOU: {exc}"
    if ae_destino():
        try:
            achados["move"] = _sondar_move(plan_uid, destino)
        except Exception as exc:  # noqa: BLE001
            achados["move"] = f"FALHOU: {exc}"
    else:
        # Até 11/09/2026 dizia "só faz sentido se o C-GET não funcionar" — e em
        # 10/09 o C-GET foi medido e NÃO existe no daemon do ARIA. O recado
        # mandava o leitor esperar por um degrau que nunca vai responder.
        achados["move"] = (f"não tentado: sem {ENV_AE_DESTINO}. É o C-MOVE que "
                           "exporta — o C-GET não existe no daemon do ARIA "
                           "(medido em 10/09/2026).")
    return achados


def _sondar_move(plan_uid: str, pasta: Path) -> str:
    """C-MOVE **com o receptor de pé** — é o circuito inteiro, não meia medida.

    A versão antiga chamava :func:`mover`, que não recebe nada: o relatório
    saía como "N objeto(s), conferir na pasta do destino", e não havia destino
    nenhum para conferir. Pior, o desfecho de firewall fechado (21 s e
    ``0 objeto(s), 1 falha``) saía idêntico ao de sucesso visto de fora.

    O que interessa é a DIFERENÇA entre o que o servidor diz ter mandado e o
    que chegou ao disco: iguais, o circuito está fechado; ele diz que mandou e
    nada chegou, o problema é desta ponta — porta ouvindo, regra de firewall de
    ENTRADA, ou o AE de destino cadastrado apontando para outra máquina.
    """
    with receber(pasta) as recebido:
        concluidas, falhas = _mover_contando(plan_uid, ae_destino())
    chegaram = len(recebido.arquivos)
    resumo = (f"o servidor diz {concluidas} concluída(s) e {falhas} falha(s); "
              f"chegaram {chegaram} arquivo(s) na porta {porta_escuta()}")
    if chegaram:
        return f"FUNCIONA — {resumo}, em {pasta}"
    return (f"NADA CHEGOU — {resumo}. Conferir, nesta ordem: a porta está "
            f"ouvindo, o firewall de ENTRADA libera o ARIA, e o AE "
            f"{ae_destino()} está cadastrado apontando para ESTA máquina.")


def _resumo_find(plan_uid: str) -> str:
    achados = achar_plano(plan_uid)
    if not achados:
        return "0 — o servidor não tem esse SOPInstanceUID."
    ds = achados[0]
    return (f"{len(achados)} — paciente {getattr(ds, 'PatientID', '?')}, "
            f"modalidade {getattr(ds, 'Modality', '?')}")


def mover(plan_uid: str, destino: str = "") -> str:
    """C-MOVE: o ARIA abre conexão NOVA para um AE cadastrado.

    Não grava nada aqui — quem recebe é o AE de destino. Devolve o resumo do
    que o servidor disse ter mandado, que é tudo o que esta ponta sabe.
    """
    alvo = destino or ae_destino()
    if not alvo:
        raise FalhaDeRede(
            f"C-MOVE precisa do AE de destino ({ENV_AE_DESTINO}) — é para onde "
            "o ARIA manda os arquivos, e ele tem de estar cadastrado lá.")
    concluidas, falhas = _mover_contando(plan_uid, alvo)
    return (f"C-MOVE para {alvo}: {concluidas} objeto(s), {falhas} falha(s). "
            f"Conferir na pasta do destino — esta ponta não recebe nada.")


@contextmanager
def receber(pasta, porta: int | None = None, modo: str = "C-MOVE"):
    """Sobe o Storage SCP desta ponta, cede o :class:`Resultado`, e o derruba.

    O C-MOVE não devolve os objetos pela conexão que pediu: o ARIA abre uma
    conexão NOVA para o AE de destino cadastrado nele. Sem ninguém ouvindo
    aqui, o pedido é aceito, o servidor tenta conectar e a resposta chega como
    ``0 objeto(s), 1 falha`` depois de 21 s — medido em 10/09/2026, e é
    indistinguível, para quem lê só o resumo, de destino desconhecido (que na
    verdade falha na hora, com ``Move destination unknown``).

    **Efêmero de propósito.** Abre pelos segundos da transferência e fecha. A
    máquina concentradora não precisa de um serviço com ciclo de vida próprio
    — nem da pergunta "e quando ela cair?" — e a porta não fica aberta ociosa
    fora do uso. Quem precisar dela de pé o tempo todo segura este mesmo
    gerenciador aberto: é a única diferença entre as duas topologias.

    Abrir e fechar a mesma porta uma vez por plano é seguro: o ``pynetdicom``
    liga ``SO_REUSEADDR`` no servidor (``transport.py``), então o ``bind`` não
    esbarra no ``TIME_WAIT`` do anterior. Sem isso, uma varredura com vinte
    pendentes falharia a partir do segundo — e falharia como "nada chegou",
    que é o sintoma que aponta para o firewall.
    """
    _pynetdicom()
    from pynetdicom import AE, evt  # noqa: PLC0415
    from pynetdicom.sop_class import (  # noqa: PLC0415
        CTImageStorage, RTDoseStorage, RTPlanStorage, RTStructureSetStorage)

    pasta = Path(pasta)
    recebido = Resultado(modo=modo)
    ae = AE(ae_title=ae_destino() or ae_local())
    for classe in (RTPlanStorage, RTStructureSetStorage, RTDoseStorage,
                   CTImageStorage):
        ae.add_supported_context(classe)
    ae.network_timeout = SEGUNDOS
    escuta = porta if porta is not None else porta_escuta()
    _LOG.info("Ouvindo C-MOVE na porta %s como AE %s", escuta, ae.ae_title)
    # ``0.0.0.0`` e não ``127.0.0.1``: quem conecta é o ARIA, de outra máquina.
    # Com o laço local o ``bind`` passa igual e o servidor continua sem achar
    # ninguém — o mesmo desfecho mudo do firewall fechado, e a mesma manhã
    # perdida procurando no lugar errado.
    servico = ae.start_server(("0.0.0.0", escuta), block=False,
                              evt_handlers=[(evt.EVT_C_STORE,
                                             _gravador(recebido, pasta))])
    try:
        yield recebido
    finally:
        servico.shutdown()


def _mover_contando(plan_uid: str, alvo: str,
                    nivel: str = "IMAGE") -> tuple[int, int]:
    """Dispara o C-MOVE e devolve (concluídas, falhas) do que o SERVIDOR diz.

    O que ele diz e o que chegou aqui são coisas diferentes — e é na diferença
    entre as duas que mora a exportação pela metade. Quem confere é
    :func:`trazer`; esta função não tem como saber.

    ``nivel="SERIES"`` troca o identificador: aí o ``plan_uid`` é lido como
    ``SeriesInstanceUID`` e vem a série inteira. É como a CT tem de ser pedida
    — no nível de instância seriam centenas de associações para o mesmo
    conjunto.
    """
    from pynetdicom.sop_class import (  # noqa: PLC0415
        PatientRootQueryRetrieveInformationModelMove as Move)

    assoc = _associar([Move])
    concluidas = falhas = 0
    try:
        consulta = (_consulta_da_serie(plan_uid) if nivel == "SERIES"
                    else _consulta_do_plano(plan_uid))
        for estado, _ident in assoc.send_c_move(consulta, alvo, Move):
            if not estado:
                raise FalhaDeRede("A conexão caiu durante o C-MOVE.")
            concluidas = int(getattr(estado, "NumberOfCompletedSuboperations",
                                     0) or 0)
            falhas = int(getattr(estado, "NumberOfFailedSuboperations", 0) or 0)
    finally:
        assoc.release()
    return concluidas, falhas


def _referencias_do_plano(caminho: Path) -> tuple[str, list]:
    """Lê o RTPLAN que chegou e devolve (StudyInstanceUID, UIDs a buscar).

    O C-MOVE pelo ``SOPInstanceUID`` do plano traz **exatamente um objeto**: o
    plano. Medido em 10/09/2026, e não é limitação de configuração — a consulta
    é de instância, então só pode vir um. Quem monta o conjunto é esta ponta,
    seguindo o que o plano aponta.
    """
    import pydicom  # noqa: PLC0415

    ds = pydicom.dcmread(caminho, stop_before_pixels=True)
    uids = []
    for item in getattr(ds, "ReferencedStructureSetSequence", None) or []:
        uid = getattr(item, "ReferencedSOPInstanceUID", "")
        if uid:
            uids.append(uid)
    return getattr(ds, "StudyInstanceUID", ""), uids


def _series_de_imagem(caminho: Path) -> list:
    """Lê um objeto que chegou e, se for RTSTRUCT, devolve as séries que ele contorna.

    É o fio para a CT: ``ReferencedFrameOfReferenceSequence →
    RTReferencedStudySequence → RTReferencedSeriesSequence``. O caminho óbvio
    seria pedir as CT do ESTUDO, e ele traz a série errada sem aviso: o estudo
    de um plano real tem 16 séries (medido no ``clinica-python01`` em
    10/09/2026), com REG, PLAN e mais de uma CT — a de simulação e as de
    reposicionamento. A ficha sobre a CT que não é a do contorno não tem
    sintoma nenhum: os cortes aparecem, e as isodoses caem fora do lugar.

    Objeto que não é RTSTRUCT, ou ilegível, devolve lista vazia — quem decide
    se isso deixa o conjunto incompleto é :func:`trazer`.
    """
    import pydicom  # noqa: PLC0415

    try:
        ds = pydicom.dcmread(caminho, stop_before_pixels=True)
    except Exception:  # noqa: BLE001
        _LOG.exception("Não deu para reler o objeto recebido em %s", caminho)
        return []
    if getattr(ds, "Modality", "") != "RTSTRUCT":
        return []
    series = []
    for quadro in getattr(ds, "ReferencedFrameOfReferenceSequence", None) or []:
        for estudo in getattr(quadro, "RTReferencedStudySequence", None) or []:
            for serie in (getattr(estudo, "RTReferencedSeriesSequence", None)
                          or []):
                uid = getattr(serie, "SeriesInstanceUID", "")
                if uid and uid not in series:
                    series.append(uid)
    return series


def _series_de_dose(study_uid: str) -> list:
    """C-FIND das séries de RTDOSE do estudo, no nível de SÉRIE.

    A dose **não é referenciada pelo plano**: a seta aponta ao contrário, do
    RTDOSE para o RTPLAN. Não há como segui-la para baixo, então o caminho é
    perguntar o que o estudo tem e conferir a referência DEPOIS que o objeto
    chega — é o que :func:`trazer` faz com :func:`_pertence_ao_conjunto`.

    No nível de SÉRIE, e não de instância: ``Modality`` é atributo de série, e
    o ARIA desta clínica o **ignora** numa consulta ``IMAGE``. Medido em
    11/09/2026: o C-FIND ``IMAGE`` + ``Modality=RTDOSE`` devolveu 223 UIDs, o
    estudo inteiro — a CT veio duas vezes, REG e RTIMAGE falharam no receptor,
    e o RTPLAN de outro plano ficou na pasta. No nível de série o mesmo
    servidor respeita a modalidade (o censo contou "RTDOSE: 2 série(s)").

    E ainda assim a modalidade de cada resposta é conferida aqui: o defeito
    que isto conserta foi justamente confiar que o servidor filtrou.
    """
    from pydicom.dataset import Dataset  # noqa: PLC0415
    from pynetdicom.sop_class import (  # noqa: PLC0415
        PatientRootQueryRetrieveInformationModelFind as Find)

    if not study_uid:
        return []
    ds = Dataset()
    ds.QueryRetrieveLevel = "SERIES"
    ds.StudyInstanceUID = study_uid
    ds.Modality = "RTDOSE"
    ds.SeriesInstanceUID = ""
    assoc = _associar([Find])
    achados = []
    try:
        for estado, ident in assoc.send_c_find(ds, Find):
            if not estado:
                raise FalhaDeRede("A conexão caiu durante o C-FIND das doses.")
            if not ident:
                continue
            modalidade = str(getattr(ident, "Modality", "") or "")
            if modalidade and modalidade != "RTDOSE":
                _LOG.warning("O servidor devolveu uma série %s na consulta de "
                             "RTDOSE: ignorada", modalidade)
                continue
            uid = getattr(ident, "SeriesInstanceUID", "")
            if uid and uid not in achados:
                achados.append(uid)
    finally:
        assoc.release()
    return achados


def _pertence_ao_conjunto(caminho: Path, plan_uid: str, estruturas,
                          series=None) -> bool:
    """Só descarta o que TEM CERTEZA de que não é deste plano.

    - RTPLAN: só o próprio plano. Pasta com dois planos é a ficha do plano
      errado sem sintoma — e foi o que a consulta de 10/09 deixou na pasta;
    - RTSTRUCT: só o que o plano aponta em ``ReferencedStructureSetSequence``;
    - RTDOSE: a que aponta de volta para o plano. Dose sem referência fica —
      é como chega a dose de composição de curso;
    - CT: só a das ``series`` que o RTSTRUCT contorna. ``series=None`` é "ainda
      não se sabe" (a estrutura não foi lida), e aí a CT passa.

    Qualquer outra modalidade passa, e objeto ilegível também: apagar o que não
    se conseguiu ler seria decidir por falta de informação, e nesta pasta o
    custo de sobrar um arquivo é bem menor que o de faltar um.
    """
    import pydicom  # noqa: PLC0415

    try:
        ds = pydicom.dcmread(caminho, stop_before_pixels=True)
    except Exception:  # noqa: BLE001
        _LOG.exception("Não deu para reler o objeto recebido em %s", caminho)
        return True
    modalidade = getattr(ds, "Modality", "")
    uid = getattr(ds, "SOPInstanceUID", "")
    if modalidade == "RTPLAN":
        return uid == plan_uid
    if modalidade == "RTSTRUCT":
        return uid in estruturas
    if modalidade == "CT":
        return series is None or getattr(ds, "SeriesInstanceUID", "") in series
    if modalidade != "RTDOSE":
        return True
    referencias = getattr(ds, "ReferencedRTPlanSequence", None) or []
    if not referencias:
        return True
    return any(getattr(item, "ReferencedSOPInstanceUID", "") == plan_uid
               for item in referencias)


def _descartar_de_fora(recebido: Resultado, plan_uid: str, estruturas,
                       series=None) -> None:
    """Tira da pasta (e da lista) o que :func:`_pertence_ao_conjunto` recusa.

    De passagem, tira da lista os caminhos repetidos: o mesmo UID recebido duas
    vezes grava o mesmo arquivo, e a lista dizia 407 onde o disco tinha 206
    (medido em 11/09/2026) — número que ninguém consegue conferir.
    """
    sobrevivem = []
    for caminho in dict.fromkeys(recebido.arquivos):
        if _pertence_ao_conjunto(caminho, plan_uid, estruturas, series):
            sobrevivem.append(caminho)
        else:
            _LOG.info("Descartado %s: não é do conjunto de %s",
                      caminho.name, plan_uid)
            caminho.unlink(missing_ok=True)
    recebido.arquivos = sobrevivem


def _tem_dose(arquivos) -> bool:
    import pydicom  # noqa: PLC0415

    for caminho in arquivos:
        try:
            if pydicom.dcmread(caminho, stop_before_pixels=True).Modality \
                    == "RTDOSE":
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def trazer(plan_uid: str, pasta) -> Resultado:
    """Traz o conjunto do plano. **É esta a operação que o produto usa.**

    Escolhe o caminho pelo que está configurado, não pelo que seria mais
    cômodo: com ``ISOCENTRO_DICOM_AE_DESTINO`` posto é C-MOVE, com o receptor
    ouvindo aqui; sem ele é C-GET. Contra o ARIA desta clínica o C-GET não
    existe — ver o cabeçalho do módulo —, e por isso ele não é reserva deste
    caminho: é o caminho de um servidor diferente.

    Tudo dentro de UMA escuta só: o plano, o RTSTRUCT que ele aponta, as
    séries de RTDOSE do estudo (e delas fica só a dose que aponta de volta
    para o plano) e, por último, a série de CT que o RTSTRUCT contorna —
    pedida por SÉRIE, porque são centenas de objetos e no nível de instância
    seria uma associação por corte. Por último porque é a maior: se o plano ou
    a estrutura não vierem, não se paga a CT para descobrir que o conjunto já
    estava perdido.

    Sem dose deste plano na pasta, o conjunto é INCOMPLETO — também quando o
    estudo só tinha a dose do vizinho: o descarte a tira, e o que sobra não
    serve à ficha.
    """
    pasta = Path(pasta)
    if not ae_destino():
        return baixar(plan_uid, pasta)

    with receber(pasta) as recebido:
        concluidas, falhas = _mover_contando(plan_uid, ae_destino())
        recebido.falhas += falhas
        if not recebido.arquivos:
            # O servidor pode dizer "concluí" sem nada ter chegado: é a
            # conexão que ELE abre sendo barrada pelo firewall de entrada
            # daqui, ou o AE de destino cadastrado apontando para outra
            # máquina. Insistir nos outros dois C-MOVE gastaria minutos para
            # juntar o mesmo nada.
            recebido.falhas = max(recebido.falhas, 1)
            _LOG.warning("C-MOVE do plano: o servidor diz %s concluída(s) e "
                         "nada chegou. A porta %s está ouvindo, e o firewall "
                         "de ENTRADA está aberto para o ARIA?",
                         concluidas, porta_escuta())
            return recebido

        study_uid, estruturas = _referencias_do_plano(recebido.arquivos[0])
        for uid in estruturas:
            antes = len(recebido.arquivos)
            _, falhas = _mover_contando(uid, ae_destino())
            recebido.falhas += falhas
            if len(recebido.arquivos) == antes:
                # Conjunto sem estrutura ou sem dose NÃO pode sair como
                # pronto: quem chama decide pelo ``completo``, e meio conjunto
                # na pasta com a marca d'água de exportado é o desfecho que
                # ninguém confere depois.
                recebido.falhas += 1
                _LOG.warning("Nada chegou no C-MOVE de %s", uid)

        series_de_dose = _series_de_dose(study_uid)
        if not series_de_dose:
            recebido.falhas += 1
            _LOG.warning("O estudo de %s não tem série de RTDOSE", plan_uid)
        for serie in series_de_dose:
            antes = len(recebido.arquivos)
            _, falhas = _mover_contando(serie, ae_destino(), nivel="SERIES")
            recebido.falhas += falhas
            if len(recebido.arquivos) == antes:
                recebido.falhas += 1
                _LOG.warning("Nada chegou no C-MOVE da série de dose %s", serie)

        # Antes de ler as séries de imagem: um RTSTRUCT que não é o do plano
        # apontaria a CT de OUTRO contorno, e ela seria pedida como se fosse
        # esta.
        _descartar_de_fora(recebido, plan_uid, estruturas)
        series = []
        for caminho in list(recebido.arquivos):
            for serie in _series_de_imagem(caminho):
                if serie not in series:
                    series.append(serie)
        if not series:
            # Sem série apontada não há CT a pedir, e o conjunto sem CT não
            # serve à ficha. Adivinhar pela CT do estudo seria escolher entre
            # a de simulação e as de reposicionamento no escuro.
            recebido.falhas += 1
            _LOG.warning("O RTSTRUCT não aponta série de imagem nenhuma: o "
                         "conjunto de %s fica sem CT", plan_uid)
        for serie in series:
            antes = len(recebido.arquivos)
            concluidas, falhas = _mover_contando(serie, ae_destino(),
                                                 nivel="SERIES")
            recebido.falhas += falhas
            chegaram = len(recebido.arquivos) - antes
            if chegaram == 0 or chegaram < concluidas:
                # A CT pela metade é o pior dos casos: a ficha abre, os cortes
                # aparecem, e o que falta é justamente o do isocentro. Conta o
                # que CHEGOU contra o que o servidor diz ter mandado, que é
                # onde mora a diferença.
                recebido.falhas += 1
                _LOG.warning("CT %s: o servidor diz %s concluída(s), chegaram "
                             "%s", serie, concluidas, chegaram)

    _descartar_de_fora(recebido, plan_uid, estruturas, series)
    if not _tem_dose(recebido.arquivos):
        recebido.falhas += 1
        _LOG.warning("Nenhuma RTDOSE de %s ficou na pasta", plan_uid)
    return recebido
