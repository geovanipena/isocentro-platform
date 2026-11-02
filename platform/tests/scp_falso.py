"""Um ARIA de mentira que fala DICOM de verdade, para os testes.

Não é um dublê de objeto: é um SCP que sobe em ``127.0.0.1`` e negocia
associação, contexto e PAPEL como o servidor da clínica negocia. Existe porque
o defeito que custou a primeira versão do ``dicom_rede`` — propor os papéis SCP
e SCU e receber só o de SCU — não aparece de outro jeito. Objeto falso responde
o que se mandou responder; o protocolo responde o que ele quer.

Vive fora de ``test_*.py`` de propósito: é usado por mais de um arquivo de
teste, e o ``discover`` não o coleta.
"""

from __future__ import annotations

import contextlib
import os
import socket

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian
from pydicom.uid import RTPlanStorage as RTPlanUID
from pynetdicom import AE, evt
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind as Find,
)
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelGet as Get,
)
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelMove as Move,
)
from pynetdicom.sop_class import (
    CTImageStorage,
    RTDoseStorage,
    RTPlanStorage,
    RTStructureSetStorage,
    Verification,
)

# O UID real do plano do 9000019ANA, medido em 02/09/2026. Usar o de verdade
# não é enfeite: UID do ARIA tem 51 caracteres, e um "1.2.3" curto esconderia
# um limite de campo que só apareceria na clínica.
UID = "1.2.246.352.71.5.642399144380.534255.20260902085106"

# Um segundo plano, para exercitar mais de um por rodada.
UID2 = "1.2.246.352.71.5.642399144380.534336.20260902112642"

# Um UID que NÃO existe no servidor, e sintaticamente válido: só dígitos e
# pontos. Escrito por extenso ("...INEXISTENTE"), fazia o pydicom emitir aviso
# de VR inválida no meio da suíte — e aviso rotineiro é o que ensina a ignorar
# aviso.
UID_AUSENTE = "1.2.246.352.71.5.900002699999.999999.29990101000000"

# O RTSTRUCT que o plano aponta, e as duas RTDOSE do MESMO estudo: a do plano e
# a do vizinho. A vizinha existe aqui porque é o caso que o C-FIND por estudo
# devolve e que ninguém veria: a dose não referencia o plano de volta por
# acaso, e uma ficha calculada sobre a dose do plano ao lado não tem sintoma.
UID_STRUCT = "1.2.246.352.71.4.642399144380.534255.20260902085106"
UID_DOSE = "1.2.246.352.71.7.642399144380.534255.20260902085107"
UID_DOSE_VIZINHA = "1.2.246.352.71.7.642399144380.534336.20260902112643"
ESTUDO = "1.2.3.4.5"

# A série onde moram as RTDOSE — as duas, a do plano e a vizinha, na MESMA
# série: é o pior caso para o receptor, que pede a série inteira e só pode
# ficar com a dose que aponta para o plano dele.
SERIE_DOSE = "1.2.3.4.8"

# A série de CT do mesmo estudo. O número de cortes é pequeno de propósito —
# o que se exercita é o CAMINHO (pedido por série, não por instância), e uma
# série de 300 objetos faria a suíte pagar 300 associações para provar o mesmo.
SERIE_CT = "1.2.3.4.9"

# Uma segunda CT no MESMO estudo — a de reposicionamento, que um estudo real
# tem (16 séries no do clinica-python01, 10/09/2026). É a que o receptor NÃO
# pode trazer: o RTSTRUCT não a contorna.
SERIE_CT_OUTRA = "1.2.3.4.10"


def plano(uid: str = UID, registro: str = "9000019ANA",
          rotulo: str = "cCRANIO_20Gy") -> Dataset:
    ds = Dataset()
    ds.PatientID = registro
    ds.PatientName = "Oliveira^Joao"
    ds.SOPClassUID = RTPlanUID
    ds.SOPInstanceUID = uid
    ds.StudyInstanceUID = "1.2.3.4.5"
    ds.SeriesInstanceUID = "1.2.3.4.6"
    ds.Modality = "RTPLAN"
    ds.RTPlanLabel = rotulo
    # É por esta sequência que o receptor acha o RTSTRUCT: o C-MOVE pelo UID do
    # plano traz UM objeto, e o resto do conjunto sai das referências dele.
    referencia = Dataset()
    referencia.ReferencedSOPClassUID = RTStructureSetStorage
    referencia.ReferencedSOPInstanceUID = UID_STRUCT
    ds.ReferencedStructureSetSequence = [referencia]
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = RTPlanUID
    ds.file_meta.MediaStorageSOPInstanceUID = uid
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    return ds


def _meta(ds, classe):
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = classe
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    return ds


def estrutura(uid: str = UID_STRUCT, registro: str = "9000019ANA",
              series=(SERIE_CT,)) -> Dataset:
    """O RTSTRUCT, com a série de imagem que ele contorna.

    É por ``ReferencedFrameOfReferenceSequence`` que o receptor acha a CT, na
    profundidade em que o TPS a grava (quadro → estudo → série). ``series=()``
    monta a estrutura que não aponta imagem nenhuma: sem ela não há CT a pedir,
    e o conjunto não pode sair como pronto.
    """
    ds = Dataset()
    ds.PatientID = registro
    ds.SOPClassUID = RTStructureSetStorage
    ds.SOPInstanceUID = uid
    ds.StudyInstanceUID = ESTUDO
    ds.SeriesInstanceUID = "1.2.3.4.7"
    ds.Modality = "RTSTRUCT"
    if series:
        estudo = Dataset()
        estudo.ReferencedSOPInstanceUID = ESTUDO
        estudo.RTReferencedSeriesSequence = []
        for serie in series:
            item = Dataset()
            item.SeriesInstanceUID = serie
            estudo.RTReferencedSeriesSequence.append(item)
        quadro = Dataset()
        quadro.FrameOfReferenceUID = "1.2.3.4.11"
        quadro.RTReferencedStudySequence = [estudo]
        ds.ReferencedFrameOfReferenceSequence = [quadro]
    return _meta(ds, RTStructureSetStorage)


def dose(uid: str = UID_DOSE, do_plano: str = UID,
         registro: str = "9000019ANA") -> Dataset:
    """Uma RTDOSE que diz de QUAL plano é — a seta aponta daqui para lá.

    ``do_plano=""`` monta a dose sem referência nenhuma, que é como chega a
    dose de composição de curso: o receptor não pode descartá-la só por não
    saber de quem ela é.
    """
    ds = Dataset()
    ds.PatientID = registro
    ds.SOPClassUID = RTDoseStorage
    ds.SOPInstanceUID = uid
    ds.StudyInstanceUID = ESTUDO
    ds.SeriesInstanceUID = SERIE_DOSE
    ds.Modality = "RTDOSE"
    if do_plano:
        referencia = Dataset()
        referencia.ReferencedSOPClassUID = RTPlanUID
        referencia.ReferencedSOPInstanceUID = do_plano
        ds.ReferencedRTPlanSequence = [referencia]
    return _meta(ds, RTDoseStorage)


def imagem_ct(uid: str, serie: str = SERIE_CT) -> Dataset:
    ds = Dataset()
    ds.PatientID = "9000019ANA"
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = uid
    ds.StudyInstanceUID = ESTUDO
    ds.SeriesInstanceUID = serie
    ds.Modality = "CT"
    return _meta(ds, CTImageStorage)


def porta_livre() -> int:
    """Porta efêmera do sistema, e não um número fixo.

    Porta fixa em teste falha quando alguém tem o programa aberto, e falha de
    um jeito que parece defeito do código.
    """
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


@contextlib.contextmanager
def conexao_que_falha(exc: OSError):
    """Todo ``connect`` levanta ``exc``, sem ir à pilha TCP.

    Porta fechada em ``127.0.0.1`` não recusa "na hora" no Windows: a pilha
    repete o SYN duas vezes mesmo depois do RST, e cada ``connect`` custa
    2,04 s (medido em 15/09/2026, igual nas duas tentativas). Eram cinco testes
    pagando isso — os do diagnóstico do banco, o do degrau TCP do checkup e dois
    da varredura do ``sondar_dicom`` — e nenhum deles prova a pilha: provam o que
    se DIZ com a recusa. E o firewall, que é a outra metade da distinção, nem
    tinha teste, porque imitá-lo de verdade custa o prazo inteiro.

    Os leitores separam as causas pelo TIPO da exceção, então o dublê levanta o
    mesmo tipo que a pilha levantou na medida. É subclasse do socket de verdade
    para que ``settimeout``, ``bind`` e ``close`` continuem sendo os reais.

    A troca é no módulo ``socket``, e não no de quem chama: o ``sondar_dicom`` e
    o ``capa_db`` fazem ``import socket`` DENTRO da função. Guardar e devolver,
    nunca ``del``.
    """
    class _Falha(socket.socket):
        def connect(self, endereco):
            raise exc

    original = socket.socket
    socket.socket = _Falha
    try:
        yield
    finally:
        socket.socket = original


class Servidor:
    """Responde C-ECHO, C-FIND e C-GET pelos UIDs que lhe deram.

    ``aceita_get=False`` faz toda suboperação falhar — é como se comporta um
    servidor sem espaço, ou um objeto que ele não consegue ler. ``derruba``
    recusa a associação, que é o que acontece com AE Title não cadastrado.

    ``exige_ae`` faz o servidor conferir o AE Title CHAMADO e recusar quem
    errar — que é como o ARIA se comporta, e é o único jeito de exercitar a
    leitura do motivo da recusa. Por padrão o ``pynetdicom`` aceita qualquer
    AE chamado, e com isso um teste de "recusou porque o AE está errado"
    passaria sem nunca ter havido recusa.

    ``escuta`` liga o **C-MOVE**, e é o que separa este dublê dos outros: o
    servidor abre uma conexão NOVA para o AE de destino, exatamente como o DB
    Daemon faz. Um receptor que não sobe, que sobe em ``127.0.0.1`` só, ou que
    é derrubado antes da hora falha aqui do mesmo jeito que falharia na
    clínica — e na clínica o sintoma é ``0 objeto(s), 1 falha`` depois de 21 s,
    que não diz nada. ``doses`` são as RTDOSE do estudo, como
    ``[(uid, uid_do_plano)]``, todas na ``SERIE_DOSE``.

    O C-FIND responde **como o ARIA desta clínica**, medido em 11/09/2026: no
    nível ``SERIES`` respeita ``Modality``; no nível ``IMAGE`` a ignora e
    devolve o estudo inteiro. O dublê filtrava nos dois, e por isso a suíte
    passou com um receptor que, contra o servidor real, trazia 223 objetos e
    deixava o RTPLAN de outro plano na pasta.
    """

    def __init__(self, uids=(UID,), aceita_get=True, derruba=False,
                 exige_ae=False, escuta=0, ae_destino="RTF_SCP", doses=(),
                 series=(), cortes=(), series_da_estrutura=(SERIE_CT,)):
        self.uids = tuple(uids)
        self.series_da_estrutura = tuple(series_da_estrutura)
        self.aceita_get = aceita_get
        self.derruba = derruba
        self.exige_ae = exige_ae
        self.escuta = escuta
        self.ae_destino = ae_destino
        self.doses = tuple(doses)
        # ``series`` é o que o censo por estudo devolve: (modalidade, uid da
        # série, nº de instâncias). ``cortes`` são os SOPInstanceUID que o
        # C-MOVE por SÉRIE entrega — separados de propósito, porque servidor
        # que ANUNCIA 300 e entrega 2 é justamente o desfecho que o checkup
        # precisa saber distinguir.
        self.series = tuple(series)
        self.cortes = tuple(cortes)
        self.pedidos: list = []

    def __enter__(self):
        self._antes = dict(os.environ)
        porta = porta_livre()
        if self.derruba:
            # Sem servidor nenhum na porta: a associação falha como falha
            # quando o ARIA recusa o AE Title. Levantar um servidor que recusa
            # daria a mesma mensagem por um caminho mais frágil.
            self._servidor = None
        else:
            ae = AE(ae_title="ARIA_FALSO")
            ae.require_called_aet = self.exige_ae
            ae.add_supported_context(Verification)
            ae.add_supported_context(Find)
            ae.add_supported_context(Get)
            # ``scp_role=True``: é o acordo que deixa quem PEDE o C-GET receber
            # os objetos. Com ``scu_role=True`` no lugar, o cliente fica com o
            # papel errado e toda suboperação falha — o defeito de 02/09/2026.
            ae.add_supported_context(RTPlanStorage, scu_role=False,
                                     scp_role=True)
            ae.add_supported_context(Move)
            # ``add_requested_context`` e não ``supported``: a subassociação do
            # C-MOVE é montada pelo pynetdicom com os contextos PEDIDOS deste
            # AE (``service_class.py``, ``self.ae.associate(...)``). Sem eles o
            # servidor associa com o receptor e não tem em que contexto mandar.
            for classe in (RTPlanStorage, RTStructureSetStorage, RTDoseStorage,
                           CTImageStorage):
                ae.add_requested_context(classe)
            self._servidor = ae.start_server(
                ("127.0.0.1", porta), block=False,
                evt_handlers=[(evt.EVT_C_FIND, self._find),
                              (evt.EVT_C_GET, self._get),
                              (evt.EVT_C_MOVE, self._move)])
        os.environ["ISOCENTRO_DICOM_SERVIDOR"] = f"127.0.0.1:{porta}"
        os.environ["ISOCENTRO_DICOM_AE_REMOTO"] = "ARIA_FALSO"
        os.environ["ISOCENTRO_DICOM_AE_LOCAL"] = "RADIOTERAFICHA"
        os.environ.pop("ISOCENTRO_DICOM_AE_DESTINO", None)
        os.environ.pop("ISOCENTRO_DICOM_AE_DESTINO", None)
        os.environ.pop("ISOCENTRO_DICOM_PORTA_ESCUTA", None)
        os.environ.pop("ISOCENTRO_DICOM_PORTA_ESCUTA", None)
        if self.escuta:
            # Só com ``escuta`` posto: é a PRESENÇA do AE de destino que faz o
            # ``dicom_rede.trazer`` escolher o C-MOVE, e deixá-la ligada por
            # padrão mudaria o caminho de todos os testes de C-GET que já
            # existem.
            os.environ["ISOCENTRO_DICOM_AE_DESTINO"] = self.ae_destino
            os.environ["ISOCENTRO_DICOM_PORTA_ESCUTA"] = str(self.escuta)
        return self

    def __exit__(self, *_):
        os.environ.clear()
        os.environ.update(self._antes)
        if self._servidor is not None:
            self._servidor.shutdown()
        return False

    def _find(self, evento):
        uid = getattr(evento.identifier, "SOPInstanceUID", None)
        self.pedidos.append(("find", uid))
        nivel = str(getattr(evento.identifier, "QueryRetrieveLevel", "") or "")
        if nivel == "SERIES":
            # O censo: o que o ESTUDO tem, série por série. É como se pergunta
            # o tamanho da CT sem trazê-la — e ``NumberOfSeriesRelatedInstances``
            # é opcional no padrão, então o dublê devolve séries com e sem ele
            # quando o teste pedir. Neste nível o ARIA RESPEITA ``Modality``.
            series = list(self.series)
            if self.doses:
                series.append(("RTDOSE", SERIE_DOSE, len(self.doses)))
            pedida = str(getattr(evento.identifier, "Modality", "") or "")
            for modalidade, serie_uid, instancias in series:
                if pedida and modalidade != pedida:
                    continue
                achado = Dataset()
                achado.QueryRetrieveLevel = "SERIES"
                achado.StudyInstanceUID = ESTUDO
                achado.SeriesInstanceUID = serie_uid
                achado.Modality = modalidade
                achado.SeriesDescription = f"serie {modalidade}"
                if instancias is not None:
                    achado.NumberOfSeriesRelatedInstances = instancias
                yield (0xFF00, achado)
            return
        serie_pedida = getattr(evento.identifier, "SeriesInstanceUID", "")
        if nivel == "IMAGE" and serie_pedida and not uid:
            # A contagem instância a instância: é assim que se descobre o
            # tamanho de uma série num servidor que não preenche o
            # ``NumberOfSeriesRelatedInstances`` — que é o caso do ARIA desta
            # clínica, medido em 10/09/2026. Devolve só os identificadores;
            # nenhum pixel viaja.
            for corte in self.cortes:
                achado = Dataset()
                achado.QueryRetrieveLevel = "IMAGE"
                achado.SeriesInstanceUID = serie_pedida
                achado.SOPInstanceUID = corte
                yield (0xFF00, achado)
            return
        if nivel == "IMAGE" and not uid:
            # Consulta de instância por ESTUDO: o ARIA ignora ``Modality``
            # aqui (é atributo de série) e devolve TUDO — medido em 11/09/2026,
            # 223 UIDs para um pedido de RTDOSE. O dublê faz o mesmo, e é de
            # propósito: filtrar aqui foi o que escondeu o defeito da suíte.
            objetos = [*self.uids, UID_STRUCT, *(d for d, _ in self.doses),
                       *self.cortes]
            for objeto_uid in objetos:
                achado = Dataset()
                achado.QueryRetrieveLevel = "IMAGE"
                achado.StudyInstanceUID = ESTUDO
                achado.SOPInstanceUID = objeto_uid
                yield (0xFF00, achado)
            return
        if uid not in self.uids:
            return
        yield (0xFF00, plano(uid))

    def _objeto(self, uid):
        if uid in self.uids:
            return plano(uid)
        if uid == UID_STRUCT:
            return estrutura(series=self.series_da_estrutura)
        for dose_uid, do_plano in self.doses:
            if uid == dose_uid:
                return dose(dose_uid, do_plano)
        return None

    def _move(self, evento):
        uid = getattr(evento.identifier, "SOPInstanceUID", None)
        serie = getattr(evento.identifier, "SeriesInstanceUID", None)
        self.pedidos.append(("move", uid or f"serie:{serie}"))
        destino = (("127.0.0.1", self.escuta)
                   if evento.move_destination == self.ae_destino else None)
        if destino is None:
            # Destino desconhecido falha NA HORA, e é por isso que ele não se
            # confunde com firewall fechado: aquele gasta 21 s e devolve
            # "0 objeto(s), 1 falha". Medido em 10/09/2026.
            yield (None, None)
            return
        yield destino
        if serie == SERIE_DOSE and not uid:
            doses = [dose(d, do_plano) for d, do_plano in self.doses]
            yield len(doses)
            for objeto in doses:
                yield (0xFF00, objeto)
            return
        if serie and not uid:
            # Pedido por SÉRIE: vem a série inteira numa associação só. É como
            # a CT tem de ser pedida — no nível de instância seriam centenas
            # de associações para o mesmo conjunto.
            cortes = [imagem_ct(c, serie) for c in self.cortes]
            yield len(cortes)
            for corte in cortes:
                yield (0xFF00, corte)
            return
        objeto = self._objeto(uid)
        if objeto is None:
            yield 0
            return
        yield 1
        yield (0xFF00, objeto)

    def _get(self, evento):
        uid = getattr(evento.identifier, "SOPInstanceUID", None)
        self.pedidos.append(("get", uid))
        if uid not in self.uids:
            yield 0
            return
        if not self.aceita_get:
            yield 1
            yield (0xA702, None)     # "unable to perform sub-operations"
            return
        yield 1
        yield (0xFF00, plano(uid))
