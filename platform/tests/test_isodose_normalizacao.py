"""Isodose: 100% é a dose PRESCRITA, não o ponto quente da grade.

Normalizar pelo máximo da grade fazia a referência mudar sozinha: cada plano
tinha o seu 100%, e a dose combinada tinha um terceiro. A mesma faixa "50-100%"
valia 22,8 Gy num plano e 34,0 Gy na soma, então clicar em Soma ENCOLHIA o
colorwash e parecia que a soma não tinha sido aplicada (visto no TC12: plano de
40 Gy com 23.742 px coloridos contra 20.258 px da soma dos dois).

Com o 100% na prescrição a referência é estável e comparável — e, como o ponto
quente passa dos 100% (≈115%), o topo da faixa precisou passar a SATURAR no
vermelho em vez de descartar o pixel, senão abriria um buraco transparente
exatamente no meio do alvo.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.desenho import corte  # noqa: E402
from isocentro.dicom import ct_series  # noqa: E402
from isocentro.dicom import dose3d  # noqa: E402
from isocentro.papel import ficha_pdf  # noqa: E402

NZ, NY, NX = 2, 4, 4


def _rd(dose_max_gy: float) -> Dataset:
    """RT Dose uniforme com o valor de pico ``dose_max_gy``."""
    ds = Dataset()
    ds.Modality = "RTDOSE"
    ds.Rows, ds.Columns, ds.NumberOfFrames = NY, NX, NZ
    ds.PixelSpacing = [2.0, 2.0]
    ds.ImagePositionPatient = [0.0, 0.0, 0.0]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.GridFrameOffsetVector = [0.0, 2.0]
    ds.FrameOfReferenceUID = generate_uid()
    ds.DoseGridScaling = 0.01
    ds.BitsAllocated = 32
    ds.BitsStored = 32
    ds.HighBit = 31
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    arr = np.full((NZ, NY, NX), int(dose_max_gy * 100), dtype=np.uint32)
    ds.PixelData = arr.tobytes()
    fm = FileMetaDataset()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.MediaStorageSOPClassUID = generate_uid()
    fm.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta = fm
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    return ds


class TestNormalizacaoPelaPrescricao(unittest.TestCase):
    def test_rd_usa_a_prescricao_como_100(self):
        # Pico de 46 Gy numa prescrição de 40 Gy → o pico vale 115%, não 100%.
        grade = ct_series._dose_pct_grade(_rd(46.0), dose_ref=40.0)
        self.assertAlmostEqual(float(grade[0].max()), 115.0, places=3)

    def test_sem_prescricao_cai_no_maximo_da_grade(self):
        grade = ct_series._dose_pct_grade(_rd(46.0))
        self.assertAlmostEqual(float(grade[0].max()), 100.0, places=3)

    def test_cache_respeita_a_referencia(self):
        # O cache mora no próprio RD; trocar a referência não pode devolver a
        # grade normalizada pela anterior.
        rd = _rd(46.0)
        self.assertAlmostEqual(float(ct_series._dose_pct_grade(rd, 40.0)[0].max()),
                               115.0, places=3)
        self.assertAlmostEqual(float(ct_series._dose_pct_grade(rd, 46.0)[0].max()),
                               100.0, places=3)
        self.assertAlmostEqual(float(ct_series._dose_pct_grade(rd, 40.0)[0].max()),
                               115.0, places=3)

    def test_dose_somada_usa_a_soma_das_prescricoes(self):
        soma = dose3d.somar_rds([_rd(23.0), _rd(46.0)])   # pico 69 Gy
        # 60 = 20 + 40, o acumulado de um grupo de "Somar dose" (mesma região).
        grade = ct_series.tupla_dose(soma, dose_ref=60.0)
        self.assertAlmostEqual(float(grade[0].max()), 115.0, places=3)
        # Sem referência, o 100% volta a ser o ponto quente da soma.
        self.assertAlmostEqual(float(ct_series.tupla_dose(soma)[0].max()),
                               100.0, places=3)

    def test_dose_ref_total_e_a_maior_prescricao_acumulada(self):
        # Sem grupo de "Somar dose", cada plano trata a sua região: a dose não
        # se acumula no mesmo alvo, e o 100% é a MAIOR prescrição. Somar todas
        # (mama + FSC) fazia a escala cair pela metade — o ponto quente real de
        # 113% da prescrição aparecia como 57%.
        planos = [{"recursos": {"dose_ref": 20.0}, "dados": {}, "store": {}},
                  {"recursos": {}, "dados": {"rx_dose_total": 40.0}, "store": {}},
                  {"recursos": {}, "dados": {},
                   "store": {"RP": {"dose_total": 6.0}}}]
        self.assertEqual(ficha_pdf._dose_ref_total(planos), 40.0)

    def test_dose_ref_total_soma_dentro_do_grupo(self):
        # Fase → boost na MESMA região: aí a dose acumula e as prescrições somam.
        planos = [{"recursos": {"dose_ref": 20.0}, "dados": {}, "store": {}},
                  {"recursos": {}, "dados": {"rx_dose_total": 40.0}, "store": {}},
                  {"recursos": {}, "dados": {},
                   "store": {"RP": {"dose_total": 6.0}}}]
        self.assertEqual(ficha_pdf._dose_ref_total(planos, [[0, 1]]), 60.0)
        # O plano de fora não entra na conta do grupo, e sozinho não supera 60.
        self.assertEqual(ficha_pdf._dose_ref_total(planos, [[0, 2]]), 40.0)

    def test_dose_ref_total_sem_prescricao_e_zero(self):
        # Zero = "não sei": quem chama cai no máximo da grade, como antes.
        self.assertEqual(
            ficha_pdf._dose_ref_total([{"recursos": {}, "dados": {}, "store": {}}]),
            0.0)


class TestTopoDaFaixaSatura(unittest.TestCase):
    """Acima do topo da faixa o pixel fica VERMELHO, não transparente."""

    @staticmethod
    def _wash(pcts):
        from PIL import Image
        img = Image.new("RGB", (len(pcts), 1), (0, 0, 0))
        dose = np.array([pcts], dtype=np.float32)
        out = corte._aplicar_colorwash(img, dose, (50.0, 100.0))
        return np.asarray(out)[0]

    def test_acima_do_topo_nao_fica_sem_overlay(self):
        # 115% (ponto quente sobre a prescrição) tem de sair pintado.
        px = self._wash([10.0, 75.0, 100.0, 115.0])
        self.assertTrue((px[0] == 0).all(), "abaixo do piso: sem overlay")
        self.assertTrue((px[3] > 0).any(), "acima do topo sumiu — buraco no alvo")

    def test_acima_do_topo_usa_a_mesma_cor_do_topo(self):
        px = self._wash([100.0, 115.0, 400.0])
        self.assertTrue(np.array_equal(px[0], px[1]))
        self.assertTrue(np.array_equal(px[0], px[2]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
