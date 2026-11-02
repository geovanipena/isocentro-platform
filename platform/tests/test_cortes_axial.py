"""Corte axial não pode SUMIR quando a fatia não tem contorno do corpo.

A máscara EXTERNAL do axial embranquece o fundo (fora do corpo). Ela casava o
contorno do BODY com o z do corte fatia a fatia; quando NENHUM contorno casava
— BODY não contornado naquela fatia, ou o índice escolhido cai fora da extensão
do corpo (típico da ficha soma/personalizada, que renderiza os cortes de um
plano usando um índice que pode não bater com a estrutura) — a máscara ficava
vazia e ``rgb[~mask]`` pintava a fatia INTEIRA de branco: o axial não saía.

Sintético: um cilindro contornado só em algumas fatias tem resposta conhecida
(fatia com contorno → fundo branco + corpo visível; fatia sem contorno → TC
crua, nunca tudo branco).

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.desenho import corte  # noqa: E402
from isocentro.dicom import ct_series  # noqa: E402

FRAME = generate_uid()
NZ, NY, NX = 6, 40, 40
PS = 4.0
DZ = 4.0
Z_COM_BODY = (0, 1, 2)   # índices de corte com contorno do EXTERNAL


def _ct_slice(z: float) -> Dataset:
    ds = Dataset()
    ds.Modality = "CT"
    ds.Rows, ds.Columns = NY, NX
    ds.PixelSpacing = [PS, PS]
    ds.ImagePositionPatient = [0.0, 0.0, float(z)]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.FrameOfReferenceUID = FRAME
    ds.RescaleSlope = 1
    ds.RescaleIntercept = 0
    ds.WindowCenter = 40
    ds.WindowWidth = 400
    ds.SliceThickness = DZ
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 1
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    arr = np.full((NY, NX), 50, dtype=np.int16)
    arr[8:32, 8:32] = 200            # "corpo" no centro
    ds.PixelData = arr.tobytes()
    fm = FileMetaDataset()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.MediaStorageSOPClassUID = generate_uid()
    fm.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta = fm
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    return ds


def _rs_external_parcial() -> Dataset:
    """RT Struct com EXTERNAL contornado só nas fatias ``Z_COM_BODY``."""
    rs = Dataset()
    roi = Dataset(); roi.ROINumber = 1; roi.ROIName = "BODY"
    rs.StructureSetROISequence = Sequence([roi])
    obs = Dataset(); obs.ReferencedROINumber = 1; obs.RTROIInterpretedType = "EXTERNAL"
    rs.RTROIObservationsSequence = Sequence([obs])
    rc = Dataset(); rc.ReferencedROINumber = 1; rc.ROIDisplayColor = [0, 255, 0]
    contornos = []
    for zi in Z_COM_BODY:
        c = Dataset(); c.ContourGeometricType = "CLOSED_PLANAR"
        z = zi * DZ
        quad = [(20, 20), (120, 20), (120, 120), (20, 120)]
        c.ContourData = [float(v) for xy in quad for v in (xy[0], xy[1], z)]
        c.NumberOfContourPoints = 4
        contornos.append(c)
    rc.ContourSequence = Sequence(contornos)
    rs.ROIContourSequence = Sequence([rc])
    return rs


def _frac_branco(png: bytes) -> float:
    from PIL import Image
    a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    return float(np.all(a >= 250, axis=2).mean())


class TestAxialNaoSome(unittest.TestCase):
    def setUp(self):
        self.ct = ct_series.CTSerie([_ct_slice(i * DZ) for i in range(NZ)])
        self.rs = _rs_external_parcial()

    def _axial(self, idx):
        return corte.renderizar_corte(self.ct, "Axial", idx, janela="Mama", rs=self.rs,
                                      mostrar_estruturas=True)

    def test_fatia_sem_contorno_mostra_a_tc(self):
        # idx=4 não tem contorno do BODY: antes saía 100% branco (sumia).
        idx = 4
        self.assertNotIn(idx, Z_COM_BODY)
        self.assertLess(_frac_branco(self._axial(idx)), 0.95,
                        "axial sem contorno do corpo não pode sair todo branco")

    def test_fatia_com_contorno_ainda_mascara_o_fundo(self):
        # A correção não pode desligar a máscara onde ELA FAZ sentido: numa fatia
        # contornada, o fundo fora do corpo continua branco (parte da imagem
        # branca, parte não).
        f = _frac_branco(self._axial(Z_COM_BODY[1]))
        self.assertGreater(f, 0.3)     # há fundo branco (máscara ativa)
        self.assertLess(f, 1.0)        # mas não é tudo branco

    def test_sem_rs_renderiza(self):
        png = corte.renderizar_corte(self.ct, "Axial", 4, janela="Mama")
        self.assertLess(_frac_branco(png), 0.95)


class TestCorpoPorNome(unittest.TestCase):
    """O corpo é reconhecido pelo NOME (independe da caixa) mesmo sem a tag
    DICOM EXTERNAL — "Body"/"body"/"BODY"/"Corpo" mascaram o fundo do axial."""

    def _rs(self, nome_corpo: str, tipo: str = "") -> Dataset:
        rs = Dataset()
        roi = Dataset(); roi.ROINumber = 1; roi.ROIName = nome_corpo
        rs.StructureSetROISequence = Sequence([roi])
        obs = Dataset(); obs.ReferencedROINumber = 1
        obs.RTROIInterpretedType = tipo
        rs.RTROIObservationsSequence = Sequence([obs])
        rc = Dataset(); rc.ReferencedROINumber = 1; rc.ROIDisplayColor = [0, 255, 0]
        c = Dataset(); c.ContourGeometricType = "CLOSED_PLANAR"
        c.ContourData = [20., 20., 0., 120., 20., 0., 120., 120., 0., 20., 120., 0.]
        c.NumberOfContourPoints = 4
        rc.ContourSequence = Sequence([c])
        rs.ROIContourSequence = Sequence([rc])
        return rs

    def test_corpo_por_nome_vira_external(self):
        for nome in ("Body", "body", "BODY", "Corpo", "External", "outer_contour"):
            with self.subTest(nome=nome):
                rois = ct_series._contornos_por_roi(self._rs(nome))
                self.assertEqual(rois[1]["tipo"], "EXTERNAL")

    def test_nao_corpo_mantem_tipo(self):
        # Estrutura que não é corpo NÃO deve ser reclassificada como EXTERNAL.
        rois = ct_series._contornos_por_roi(self._rs("PTV", "PTV"))
        self.assertEqual(rois[1]["tipo"], "PTV")

    def test_tag_external_sem_nome_de_corpo(self):
        # Tag EXTERNAL vale mesmo com nome fora da lista (ex.: "Pele do Zé").
        rois = ct_series._contornos_por_roi(self._rs("Pele do Ze", "EXTERNAL"))
        self.assertEqual(rois[1]["tipo"], "EXTERNAL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
