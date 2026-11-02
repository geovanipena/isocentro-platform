r"""Servidor DICOM LOCAL: faz as vezes do DB Daemon do ARIA, servindo ``TCs_Teste``.

Uso::

    python tools\servidor_dicom_local.py                 (porta 11112)
    python tools\servidor_dicom_local.py --porta 11112 --destino 127.0.0.1:11113

É a outra metade do servidor local de demonstração (ver
``tools\montar_servidor_local.py``): o banco simulado diz QUAL plano sair pelo
``PlanUID``, e este processo entrega os arquivos — pelo mesmo protocolo que o
``dicom_rede`` usa contra o ARIA:

* **C-ECHO** — a verificação da tela de Serviço;
* **C-FIND** (Patient Root e Study Root) nos níveis PATIENT, STUDY, SERIES e
  IMAGE, com ``NumberOfSeriesRelatedInstances`` preenchido (o ARIA desta
  clínica NÃO preenche; aqui preencher não esconde nada, só poupa a contagem);
* **C-MOVE** para o AE de destino (o app sobe o receptor em ``receber``);
* **C-GET**, que o ARIA não tem — fica aqui para o caminho do ``baixar`` também
  poder ser mostrado.

O índice é o ``TCs_Teste\servidor_local\indice_dicom.json`` que o montador
grava; sem ele, este processo indexa sozinho.

**Só leitura**: nenhum C-STORE é aceito. É o mesmo contrato do ARIA para o app.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

PASTA_TCS = RAIZ / "TCs_Teste"
INDICE = PASTA_TCS / "servidor_local" / "indice_dicom.json"

AE_PADRAO = "ARIA_LOCAL"
PORTA_PADRAO = 11112
DESTINO_PADRAO = ("ISOCENTRO_DEST", "127.0.0.1", 11113)

_LOG = logging.getLogger("servidor_dicom_local")

# Os atributos de cada nível, na ordem da hierarquia. Uma chave de nível MAIS
# BAIXO que o pedido não entra na resposta — é o que o padrão manda, e o
# ``censo_do_estudo`` do app lê as séries sem esperar atributo de instância.
_NIVEIS = {
    "PATIENT": ("PatientID", "PatientName", "PatientBirthDate", "PatientSex"),
    "STUDY": ("StudyInstanceUID", "StudyDate"),
    "SERIES": ("SeriesInstanceUID", "Modality", "SeriesDescription"),
    "IMAGE": ("SOPInstanceUID", "SOPClassUID"),
}
_ORDEM = ("PATIENT", "STUDY", "SERIES", "IMAGE")


def carregar_indice() -> list:
    if not INDICE.is_file():
        from tools import montar_servidor_local
        return montar_servidor_local.indexar_dicom()
    return json.loads(INDICE.read_text(encoding="utf-8"))["objetos"]


def _casa(valor: str, pedido) -> bool:
    """Casamento DICOM: vazio casa tudo, ``*``/``?`` é curinga, lista é "um de"."""
    if pedido is None:
        return True
    if isinstance(pedido, (list, tuple)):
        itens = [str(x) for x in pedido if str(x)]
        return not itens or valor in itens
    pedido = str(pedido)
    if not pedido:
        return True
    if "*" in pedido or "?" in pedido:
        return fnmatch.fnmatchcase(valor.upper(), pedido.upper())
    if "\\" in pedido:
        return valor in pedido.split("\\")
    return valor == pedido


class Acervo:
    """O que o servidor tem, e as perguntas que ele sabe responder."""

    def __init__(self, objetos: list):
        self.objetos = objetos

    def procurar(self, ident) -> tuple:
        """``(nível, [objetos que casam])`` para um identificador de C-FIND."""
        nivel = str(getattr(ident, "QueryRetrieveLevel", "") or "IMAGE").upper()
        if nivel not in _ORDEM:
            nivel = "IMAGE"
        chaves = [k for n in _ORDEM for k in _NIVEIS[n]]
        achados = []
        for o in self.objetos:
            if all(_casa(o.get(k, ""), getattr(ident, k, None))
                   for k in chaves if k in ident):
                achados.append(o)
        return nivel, achados

    def respostas(self, ident):
        """Os identificadores de resposta do C-FIND, um por entidade do nível."""
        from pydicom.dataset import Dataset

        nivel, achados = self.procurar(ident)
        chave_nivel = {"PATIENT": "PatientID", "STUDY": "StudyInstanceUID",
                       "SERIES": "SeriesInstanceUID",
                       "IMAGE": "SOPInstanceUID"}[nivel]
        por_entidade: dict = {}
        for o in achados:
            por_entidade.setdefault(o.get(chave_nivel, ""), []).append(o)
        ate = _ORDEM.index(nivel)
        for _chave, grupo in por_entidade.items():
            o = grupo[0]
            ds = Dataset()
            ds.QueryRetrieveLevel = nivel
            for n in _ORDEM[:ate + 1]:
                for k in _NIVEIS[n]:
                    if k in ident or k == chave_nivel or n == nivel:
                        setattr(ds, k, o.get(k, ""))
            if nivel == "SERIES":
                ds.NumberOfSeriesRelatedInstances = str(len(grupo))
            if nivel == "STUDY":
                ds.NumberOfStudyRelatedInstances = str(len(grupo))
            yield ds

    def arquivos(self, ident) -> list:
        _nivel, achados = self.procurar(ident)
        return [PASTA_TCS / o["caminho"] for o in achados]


def _ler(caminho: Path):
    """Lê o objeto para enviar — e garante que ele diga a própria codificação.

    Os arquivos exportados pelo Monaco (pasta Elekta) vêm SEM o cabeçalho de
    arquivo DICOM (sem ``file_meta``), e o pynetdicom se recusa a mandar um
    dataset que não declara ``TransferSyntaxUID``: a suboperação falhava, e o
    gatilho registrava o plano como "0 arquivo(s), 1 falha" — o mesmo sintoma
    do firewall fechado, com a causa do lado de cá.
    """
    import pydicom
    from pydicom.dataset import FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian

    ds = pydicom.dcmread(caminho, force=True)
    meta = getattr(ds, "file_meta", None)
    if meta is None or "TransferSyntaxUID" not in meta:
        meta = meta or FileMetaDataset()
        implicito = True
        codificacao = getattr(ds, "original_encoding", None)
        if codificacao and codificacao[0] is not None:
            implicito = bool(codificacao[0])
        meta.TransferSyntaxUID = (ImplicitVRLittleEndian if implicito
                                  else ExplicitVRLittleEndian)
        meta.MediaStorageSOPClassUID = ds.SOPClassUID
        meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        ds.file_meta = meta
    return ds


def servir(porta: int, ae_titulo: str, destinos: dict) -> None:
    from pynetdicom import AE, StoragePresentationContexts, evt
    from pynetdicom.sop_class import (
        PatientRootQueryRetrieveInformationModelFind,
        PatientRootQueryRetrieveInformationModelGet,
        PatientRootQueryRetrieveInformationModelMove,
        StudyRootQueryRetrieveInformationModelFind,
        StudyRootQueryRetrieveInformationModelGet,
        StudyRootQueryRetrieveInformationModelMove, Verification)

    acervo = Acervo(carregar_indice())
    print(f"Acervo: {len(acervo.objetos)} objeto(s) DICOM de {PASTA_TCS}")

    def ao_find(evento):
        ident = evento.identifier
        n = 0
        for ds in acervo.respostas(ident):
            if evento.is_cancelled:
                yield (0xFE00, None)
                return
            n += 1
            yield (0xFF00, ds)
        _LOG.info("C-FIND %s: %d resposta(s)",
                  getattr(ident, "QueryRetrieveLevel", "?"), n)

    def ao_move(evento):
        alvo = destinos.get(str(evento.move_destination).strip())
        if alvo is None:
            _LOG.warning("C-MOVE para AE desconhecido: %r", evento.move_destination)
            yield (None, None)
            return
        arquivos = acervo.arquivos(evento.identifier)
        _LOG.info("C-MOVE de %d objeto(s) para %s", len(arquivos),
                  evento.move_destination)
        yield alvo
        yield len(arquivos)
        for caminho in arquivos:
            if evento.is_cancelled:
                yield (0xFE00, None)
                return
            yield (0xFF00, _ler(caminho))

    def ao_get(evento):
        arquivos = acervo.arquivos(evento.identifier)
        _LOG.info("C-GET de %d objeto(s)", len(arquivos))
        yield len(arquivos)
        for caminho in arquivos:
            if evento.is_cancelled:
                yield (0xFE00, None)
                return
            yield (0xFF00, _ler(caminho))

    ae = AE(ae_title=ae_titulo)
    ae.add_supported_context(Verification)
    for classe in (PatientRootQueryRetrieveInformationModelFind,
                   StudyRootQueryRetrieveInformationModelFind,
                   PatientRootQueryRetrieveInformationModelMove,
                   StudyRootQueryRetrieveInformationModelMove,
                   PatientRootQueryRetrieveInformationModelGet,
                   StudyRootQueryRetrieveInformationModelGet):
        ae.add_supported_context(classe)
    # O C-MOVE ABRE associação para o destino, e nela este lado é quem pede o
    # armazenamento. O C-GET devolve pela mesma conexão, e aí este lado precisa
    # ACEITAR que o cliente seja o SCP de storage — é o papel que o
    # ``dicom_rede.baixar`` propõe (``scp_role=True``, e só ele).
    for ctx in StoragePresentationContexts:
        ae.add_requested_context(ctx.abstract_syntax)
        ae.add_supported_context(ctx.abstract_syntax, scu_role=False,
                                 scp_role=True)
    ae.maximum_associations = 20
    manipuladores = [(evt.EVT_C_FIND, ao_find), (evt.EVT_C_MOVE, ao_move),
                     (evt.EVT_C_GET, ao_get)]
    print(f"Servidor DICOM local: AE {ae_titulo} em 0.0.0.0:{porta}")
    for nome, (host, p) in destinos.items():
        print(f"  destino de C-MOVE: {nome} -> {host}:{p}")
    print("Ctrl+C para parar.")
    ae.start_server(("0.0.0.0", porta), block=True, evt_handlers=manipuladores)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--porta", type=int, default=PORTA_PADRAO)
    ap.add_argument("--ae", default=AE_PADRAO)
    ap.add_argument("--destino", action="append", default=[],
                    help="AE=host:porta, pode repetir (padrão "
                         f"{DESTINO_PADRAO[0]}={DESTINO_PADRAO[1]}:{DESTINO_PADRAO[2]})")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("pynetdicom").setLevel(logging.WARNING)
    destinos = {DESTINO_PADRAO[0]: (DESTINO_PADRAO[1], DESTINO_PADRAO[2])}
    for d in args.destino:
        nome, _, onde = d.partition("=")
        host, _, porta = onde.partition(":")
        destinos[nome.strip()] = (host.strip() or "127.0.0.1", int(porta))
    try:
        servir(args.porta, args.ae, destinos)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
