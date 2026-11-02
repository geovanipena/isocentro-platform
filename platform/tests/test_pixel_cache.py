"""Blinda o contrato interno do pydicom em que ``soltar_cache_pixels`` se apoia.

O pydicom não expõe API pública para invalidar o ``pixel_array`` decodificado
mantendo o ``PixelData`` cru. ``dicom_rt.soltar_cache_pixels`` faz isso zerando
o atributo privado ``_pixel_array`` — o que corta centenas de MB por RT Dose nos
pacientes multi-plano.

Se uma versão futura do pydicom renomear esse atributo, o clear vira um no-op e
o vazamento de memória volta EM SILÊNCIO. Estes testes transformam essa quebra
num teste vermelho na hora de subir a dependência, em vez de um app que come
memória sem ninguém saber por quê.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dicom import dicom_rt  # noqa: E402


def _rd_sintetico(nz=2, ny=4, nx=4) -> Dataset:
    """RT Dose mínimo com PixelData real, para exercitar o cache de pixels."""
    ds = Dataset()
    ds.Modality = "RTDOSE"
    ds.Rows, ds.Columns, ds.NumberOfFrames = ny, nx, nz
    ds.BitsAllocated = 32
    ds.BitsStored = 32
    ds.HighBit = 31
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    arr = (np.arange(nz * ny * nx, dtype=np.uint32) + 1).reshape(nz, ny, nx)
    ds.PixelData = arr.tobytes()
    fm = FileMetaDataset()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.MediaStorageSOPClassUID = generate_uid()
    fm.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta = fm
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    return ds


class TestContratoPydicom(unittest.TestCase):
    """O atributo privado que soltar_cache_pixels usa precisa existir."""

    def test_dataset_expoe_pixel_array_privado(self):
        # Se este teste falhar ao subir o pydicom, soltar_cache_pixels virou
        # no-op e a memória volta a vazar — ver o docstring do módulo.
        ds = _rd_sintetico()
        self.assertTrue(
            hasattr(ds, "_pixel_array"),
            "pydicom %s não tem Dataset._pixel_array — reveja "
            "dicom_rt.soltar_cache_pixels()" % pydicom.__version__,
        )

    def test_acesso_preenche_o_cache(self):
        ds = _rd_sintetico()
        _ = ds.pixel_array
        self.assertIsNotNone(ds._pixel_array)


class TestSoltarCachePixels(unittest.TestCase):
    def test_zera_o_cache_decodificado(self):
        ds = _rd_sintetico()
        _ = ds.pixel_array
        dicom_rt.soltar_cache_pixels(ds)
        self.assertIsNone(ds._pixel_array)

    def test_pixeldata_cru_permanece_e_redecodifica(self):
        ds = _rd_sintetico()
        antes = ds.pixel_array.copy()
        dicom_rt.soltar_cache_pixels(ds)
        self.assertIn("PixelData", ds)          # o dado cru continua lá
        depois = ds.pixel_array                  # re-decodifica do PixelData
        self.assertTrue(np.array_equal(antes, depois))

    def test_sem_o_atributo_avisa_e_nao_quebra(self):
        class SemCache:
            pass
        with self.assertLogs(dicom_rt._LOG, level="WARNING"):
            dicom_rt.soltar_cache_pixels(SemCache())   # não levanta

    def test_idempotente(self):
        ds = _rd_sintetico()
        _ = ds.pixel_array
        dicom_rt.soltar_cache_pixels(ds)
        dicom_rt.soltar_cache_pixels(ds)   # segunda vez não quebra
        self.assertIsNone(ds._pixel_array)


if __name__ == "__main__":
    unittest.main(verbosity=2)
