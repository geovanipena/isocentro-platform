"""``leitura.cortes_de_tc`` + ``ct_series.montar_series`` soltam os bytes crus enquanto monta as tomografias.

O caso Elekta do acervo (1.399 cortes) chegava a 4,4 GB de pico, com os bytes
de todos os cortes vivos ao lado dos datasets e do volume; com a memória no fim,
o DVH da ficha caía calado em "DVH não disponível." (22/10/2026).
"""
import io
import unittest

import numpy as np
from pydicom import dcmwrite
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from isocentro.adaptadores.dicom import leitura
from isocentro.dicom import ct_series

N = 8


def _bytes_do_corte(z: float, frame: str, valor: int) -> bytes:
    ds = Dataset()
    ds.Modality = "CT"
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.SOPInstanceUID = generate_uid()
    ds.Rows, ds.Columns = N, N
    ds.PixelSpacing = [1.0, 1.0]
    ds.ImagePositionPatient = [0.0, 0.0, float(z)]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.FrameOfReferenceUID = frame
    ds.RescaleSlope = 1
    ds.RescaleIntercept = 0
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 1
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = np.full((N, N), valor, dtype=np.int16).tobytes()
    fm = FileMetaDataset()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.MediaStorageSOPClassUID = ds.SOPClassUID
    fm.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta = fm
    buf = io.BytesIO()
    dcmwrite(buf, ds, enforce_file_format=True)
    return buf.getvalue()


class TestCarregarSeriesSoltaOsBytes(unittest.TestCase):
    def setUp(self):
        # Duas TCs, a "A" chegando primeiro, com os cortes fora de ordem de z.
        self.arquivos = (
            [_bytes_do_corte(z, "1.2.3.A", 100) for z in (2.0, 0.0, 1.0)]
            + [_bytes_do_corte(z, "1.2.3.B", 300) for z in (5.0, 4.0)]
        )

    def test_lista_recebida_sai_vazia(self):
        ct_series.montar_series(leitura.cortes_de_tc(self.arquivos))
        self.assertEqual(self.arquivos, [])

    def test_grupos_saem_do_dicionario_ao_virar_serie(self):
        """Os datasets da TC já montada não esperam as outras (R-58 partiu a função em duas)."""
        grupos = leitura.cortes_de_tc(self.arquivos)
        self.assertEqual(list(grupos), ["1.2.3.A", "1.2.3.B"])
        ct_series.montar_series(grupos)
        self.assertEqual(grupos, {})

    def test_a_primeira_tc_a_chegar_continua_sendo_a_primeira(self):
        """Esvaziar pelo fim não pode trocar a TC que a tela mostra primeiro."""
        series = ct_series.montar_series(leitura.cortes_de_tc(self.arquivos))
        self.assertEqual([s.frame_uid for s in series], ["1.2.3.A", "1.2.3.B"])

    def test_volume_ordenado_pelo_z_e_em_hu(self):
        series = ct_series.montar_series(leitura.cortes_de_tc(self.arquivos))
        self.assertEqual(list(series[0].zs), [0.0, 1.0, 2.0])
        self.assertEqual(series[0].volume.shape, (3, N, N))
        self.assertTrue((series[0].volume == 100).all())
        self.assertTrue((series[1].volume == 300).all())


if __name__ == "__main__":
    unittest.main()
