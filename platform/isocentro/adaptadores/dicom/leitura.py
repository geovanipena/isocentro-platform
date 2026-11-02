"""Ler DICOM do disco, de bytes ou de pacote .zip/.rar — devolve ``pydicom.Dataset``.

É a borda de arquivo do que era o ``dicom_rt`` (R-58, 22/10/2026): quem modela
(``isocentro.dicom``, depois ``isocentro.rt``) recebe o dataset já lido e não
abre arquivo. Este módulo não importa nada do pacote: adaptador entrega o dado
cru e quem chama o passa adiante (AD-38 da espinha).
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import (ExplicitVRBigEndian, ExplicitVRLittleEndian,
                         ImplicitVRLittleEndian)


def _completar_file_meta(ds: Dataset) -> Dataset:
    """Repõe o Transfer Syntax quando o arquivo não tem File Meta Information.

    O Monaco (Elekta) exporta DICOM CRU: sem o preâmbulo de 128 bytes, sem o
    marcador ``DICM`` e sem o grupo 0002. O ``force=True`` lê as tags assim
    mesmo, mas o pydicom se recusa a decodificar pixel/matriz de dose sem o
    (0002,0010) — e aí morrem TC, RT Dose e RT Image, ou seja, cortes, 3D, DVH e
    isodose. O próprio pydicom deduz a codificação ao ler (``original_encoding``);
    aqui só a gravamos onde ele vai procurar depois.
    """
    meta = getattr(ds, "file_meta", None)
    if meta is not None and getattr(meta, "TransferSyntaxUID", None):
        return ds
    implicito, little = (getattr(ds, "original_encoding", None)
                         or (True, True))
    if implicito is None:      # dataset vazio/ilegível: assume o padrão DICOM
        implicito, little = True, True
    if meta is None:
        ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = (
        ImplicitVRLittleEndian if implicito else
        ExplicitVRLittleEndian if little else ExplicitVRBigEndian)
    return ds


def carregar(conteudo: bytes, stop_before_pixels: bool = True) -> Dataset:
    """Carrega um arquivo DICOM a partir de bytes.

    Por padrão ignora os dados de pixel/matriz de dose (``stop_before_pixels``),
    que podem ter centenas de MB no RT Dose e não são necessários para a ficha.

    Prefira ``carregar_arquivo`` quando o DICOM estiver no disco: aqui o
    ``io.BytesIO`` copia o buffer, e os bytes já custaram uma leitura inteira.
    """
    return _completar_file_meta(pydicom.dcmread(
        io.BytesIO(conteudo), force=True, stop_before_pixels=stop_before_pixels))


def carregar_arquivo(caminho, stop_before_pixels: bool = True) -> Dataset:
    """Carrega um DICOM direto do disco, sem materializar o arquivo na memória.

    O caminho por bytes (``read_bytes`` + ``carregar``) paga o arquivo duas
    vezes: uma na leitura e outra na cópia que o ``io.BytesIO`` faz do buffer.
    Num RT Dose real de 445 MB isso é 890 MB contra 445 MB por aqui, para o
    mesmo dataset. Só serve para DICOM solto — membro de .zip/.rar não tem
    caminho próprio e continua indo por ``iter_dicoms`` + ``carregar``.
    """
    return _completar_file_meta(pydicom.dcmread(
        str(caminho), force=True, stop_before_pixels=stop_before_pixels))


def _eh_dicom(b: bytes) -> bool:
    """Heurística: arquivo DICOM tem o marcador 'DICM' no offset 128."""
    return len(b) > 132 and b[128:132] == b"DICM"


def iter_dicoms(raw: bytes) -> Iterator[bytes]:
    """Itera os bytes de cada DICOM contido em ``raw``.

    Aceita um DICOM solto ou um pacote ``.zip``/``.rar`` (descompactado em
    memória/temporário), entregando um membro de cada vez para manter o uso de
    memória baixo mesmo com RT Dose grande.
    """
    if raw[:4] == b"PK\x03\x04":  # ZIP
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for nome in z.namelist():
                if nome.endswith("/"):
                    continue
                yield z.read(nome)
    elif raw[:4] == b"Rar!":  # RAR
        try:
            import rarfile
        except ImportError as exc:
            raise RuntimeError("Suporte a .rar indisponível; envie um .zip.") from exc

        with tempfile.NamedTemporaryFile(suffix=".rar") as tf:
            tf.write(raw)
            tf.flush()
            try:
                with rarfile.RarFile(tf.name) as rf:
                    for info in rf.infolist():
                        if info.is_dir():
                            continue
                        yield rf.read(info)
            except rarfile.RarCannotExec as exc:
                raise RuntimeError(
                    "Para abrir .rar o servidor precisa de 'unrar'/'7z'; envie um .zip."
                ) from exc
    else:  # DICOM solto
        yield raw


# Tags que bastam para triar um arquivo: de quem é e o que é. Com
# specific_tags o pydicom para de ler assim que passa da maior tag pedida.
_TAGS_TRIAGEM = ["Modality", "PatientID", "PatientName"]


def cabecalhos_arquivo(caminho) -> Iterator[Dataset]:
    """Itera só os CABEÇALHOS de triagem dos DICOM de um arquivo do disco.

    Mesma cobertura de ``iter_dicoms`` (.dcm solto, .zip, .rar), mas sem nunca
    materializar o arquivo inteiro na memória: lê do próprio caminho e, num
    pacote, do stream de cada membro. Modalidade e paciente estão nos grupos
    0008/0010, no começo do dataset — puxar um RT Dose de 444 MB inteiro para
    ler isso custa 759 ms e 444 MB de RAM; assim custa 0,7 ms e alguns KB.

    Só serve para triagem: os datasets vêm sem pixels e sem as demais tags.
    Quem precisa do conteúdo continua com ``iter_dicoms`` + ``carregar``.
    Membros ilegíveis são pulados; erros de acesso ao arquivo sobem.
    """
    caminho = Path(caminho)
    sufixo = caminho.suffix.lower()

    def _ler(fonte) -> "Dataset | None":
        try:
            return pydicom.dcmread(fonte, force=True, stop_before_pixels=True,
                                   specific_tags=_TAGS_TRIAGEM)
        except Exception:  # noqa: BLE001 — membro não-DICOM no pacote
            return None

    def _do_stream(f) -> "Dataset | None":
        # ZipExtFile é seekable quando o zip vem do disco, e o pydicom lê só o
        # começo. Se algum stream não for seekable, cai para o membro em memória
        # (um membro, não o pacote inteiro).
        if getattr(f, "seekable", lambda: False)():
            return _ler(f)
        return _ler(io.BytesIO(f.read()))

    if sufixo == ".zip":
        with zipfile.ZipFile(caminho) as z:
            for nome in z.namelist():
                if nome.endswith("/"):
                    continue
                with z.open(nome) as f:
                    ds = _do_stream(f)
                if ds is not None:
                    yield ds
    elif sufixo == ".rar":
        try:
            import rarfile
        except ImportError as exc:
            raise RuntimeError("Suporte a .rar indisponível; instale 'rarfile'.") from exc
        try:
            with rarfile.RarFile(caminho) as rf:
                for info in rf.infolist():
                    if info.is_dir():
                        continue
                    with rf.open(info) as f:
                        ds = _do_stream(f)
                    if ds is not None:
                        yield ds
        except rarfile.RarCannotExec as exc:
            raise RuntimeError(
                "Para abrir .rar é preciso ter 'unrar'/'7z' instalado."
            ) from exc
    else:  # DICOM solto — pydicom lê do caminho e para antes dos pixels
        ds = _ler(str(caminho))
        if ds is not None:
            yield ds


def _eh_ct(ds) -> bool:
    return str(getattr(ds, "Modality", "")) == "CT"


def cortes_de_tc(arquivos: list[bytes]) -> dict[str, list[Dataset]]:
    """Os cortes de TC de ``arquivos``, por ``FrameOfReferenceUID``.

    Cai para ``SeriesInstanceUID`` se não houver frame. O dicionário guarda a
    ordem de chegada dos grupos, que decide qual TC a tela mostra primeiro.

    **Esvazia a lista recebida**: cada arquivo cru sai dela assim que vira
    dataset. Antes, os bytes de todos os cortes ficavam vivos junto com os
    datasets (outra cópia do ``PixelData``) e com o volume em montagem: o caso
    Elekta do acervo (1.399 cortes, 1,2 GB em disco) chegava a 4,4 GB de pico,
    e com a memória no fim o DVH da ficha caía calado em "DVH não disponível."
    (medido em 22/10/2026). A ordem dos cortes dentro do grupo não importa — a
    série ordena pelo z —, mas a dos GRUPOS sim, e por isso a lista é consumida
    na ordem original.
    """
    grupos: dict[str, list[Dataset]] = {}
    arquivos.reverse()          # o pop() tira do fim: assim sai na ordem de chegada
    while arquivos:
        raw = arquivos.pop()
        for membro in iter_dicoms(raw):
            try:
                ds = carregar(membro, stop_before_pixels=False)
            except Exception:  # noqa: BLE001
                continue
            if _eh_ct(ds) and hasattr(ds, "PixelData"):
                uid = (str(getattr(ds, "FrameOfReferenceUID", "") or "")
                       or str(getattr(ds, "SeriesInstanceUID", "") or ""))
                grupos.setdefault(uid, []).append(ds)
    return grupos
