"""Ficha personalizada: os planos FORA do subconjunto combinado mantêm os seus
próprios cortes (bug do TC6 — planos de outra TC sumiam da ficha).

Personalizado = os planos escolhidos compõem UMA página combinada; cada plano
não-escolhido continua com a sua página individual. Sintético (CT + RD gerados)
para não depender de export de TPS.

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

from isocentro.dicom import ct_series  # noqa: E402
from isocentro.papel import ficha_pdf  # noqa: E402

NZ, NY, NX, PS, DZ = 4, 24, 24, 5.0, 5.0


def _ct_slice(z, frame):
    ds = Dataset()
    ds.Modality = "CT"
    ds.Rows, ds.Columns = NY, NX
    ds.PixelSpacing = [PS, PS]
    ds.ImagePositionPatient = [0.0, 0.0, float(z)]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.FrameOfReferenceUID = frame
    ds.RescaleSlope, ds.RescaleIntercept = 1, 0
    ds.WindowCenter, ds.WindowWidth = 40, 400
    ds.SliceThickness = DZ
    ds.BitsAllocated = 16; ds.BitsStored = 16; ds.HighBit = 15
    ds.PixelRepresentation = 1; ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    arr = np.full((NY, NX), 50, dtype=np.int16); arr[6:18, 6:18] = 200
    ds.PixelData = arr.tobytes()
    fm = FileMetaDataset(); fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.MediaStorageSOPClassUID = generate_uid(); fm.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta = fm; ds.is_little_endian = True; ds.is_implicit_VR = False
    return ds


def _rd(frame, gy=2.0):
    ds = Dataset()
    ds.Modality = "RTDOSE"
    ds.Rows, ds.Columns, ds.NumberOfFrames = NY, NX, NZ
    ds.PixelSpacing = [PS, PS]
    ds.ImagePositionPatient = [0.0, 0.0, 0.0]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.GridFrameOffsetVector = [float(i * DZ) for i in range(NZ)]
    ds.FrameOfReferenceUID = frame
    ds.DoseGridScaling = 0.01
    ds.BitsAllocated = 32; ds.BitsStored = 32; ds.HighBit = 31
    ds.PixelRepresentation = 0; ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = np.full((NZ, NY, NX), int(gy * 100), dtype=np.uint32).tobytes()
    fm = FileMetaDataset(); fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.MediaStorageSOPClassUID = generate_uid(); fm.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta = fm; ds.is_little_endian = True; ds.is_implicit_VR = False
    return ds


def _plano(rot, ct, rd):
    rec = {"ct": ct, "rs": None, "rd": rd, "estruturas_dvh": None,
           "mostrar_isodose": True, "isodose_range": (50.0, 100.0),
           "mostrar_estruturas": False, "estruturas_visiveis": None,
           "idx_axial": 2, "idx_sagital": 12, "idx_coronal": 12, "png_3d": None}
    return {"dados": {"pac_nome": "X", "proto_imagem": "MV",
                      "proto_frequencia": "Diária", "rx_fracoes": 12},
            "store": {"RP": {"rotulo_plano": rot, "num_fracoes": 12,
                             "dose_fracao": 2.0, "n_isocentros": 1,
                             "feixes": [{"gantry": 0, "um": 100}]}},
            "recursos": rec}


class TestCortesPersonalizado(unittest.TestCase):
    def setUp(self):
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("pymupdf ausente")
        fa, fb = generate_uid(), generate_uid()
        self.ct_a = ct_series.CTSerie([_ct_slice(i * DZ, fa) for i in range(NZ)])
        self.ct_b = ct_series.CTSerie([_ct_slice(i * DZ, fb) for i in range(NZ)])
        # 3 planos na TC A, 1 plano na TC B (como o TC6).
        self.planos = [
            _plano("1 A", self.ct_a, _rd(fa)),
            _plano("2 A", self.ct_a, _rd(fa)),
            _plano("3 A", self.ct_a, _rd(fa)),
            _plano("4 B", self.ct_b, _rd(fb)),
        ]

    def _paginas(self, pdf):
        import fitz
        return fitz.open(stream=pdf, filetype="pdf").page_count

    def test_personalizado_gera_cortes_dos_planos_de_fora(self):
        # Combina os 3 da TC A; o 4º (TC B) precisa manter a SUA página de cortes.
        seq = [[0, 1, 2, 3]] * 12
        pdf, imagens, _dvhs = ficha_pdf.gerar_ficha_multiplano(
            self.planos, "personalizado", sequencia=seq,
            rotulos=["1 A", "2 A", "3 A", "4 B"], planos_ficha=[0, 1, 2])
        # cortes: 1 combinada (TC A) + 1 individual (plano 4) = 2 páginas de cortes.
        self.assertEqual(len(imagens), 2)
        # páginas totais: 2 cortes + ficha (pág. 2) = 3. São 4 campos somados, e
        # com poucos campos o mapa das 12 frações entra na própria pág. 2.
        self.assertEqual(self._paginas(pdf), 3)

    def test_ficha_separada_so_com_o_subconjunto(self):
        # "Separar Ficha": a GUI entrega só os planos escolhidos (já remapeados).
        # A ficha sai inteira sobre eles — nada do plano deixado de fora.
        sub = self.planos[:2]
        pdf, imagens, _dvhs = ficha_pdf.gerar_ficha_multiplano(
            sub, "soma", sequencia=[[0, 1]] * 12, rotulos=["1 A", "2 A"])
        self.assertEqual(len(imagens), 1)          # os 2 combinados
        self.assertGreaterEqual(self._paginas(pdf), 2)

    def test_ficha_separada_de_um_unico_plano(self):
        # Separar até sobrar UM plano: cai na página clássica de plano único. Com
        # 1 campo, o mapa das 12 frações cabe ao lado/abaixo → cortes + pág. 2.
        pdf, imagens, _dvhs = ficha_pdf.gerar_ficha_multiplano(
            [self.planos[0]], "individual", rotulos=["1 A"])
        self.assertEqual(len(imagens), 1)
        self.assertEqual(self._paginas(pdf), 2)

    def test_ficha_separada_de_um_plano_curto_cabe_na_pagina_2(self):
        # Um plano só e tratamento curto (fígado, 3 frações): o mapa embute na
        # pág. 2 e não sai página 3 — cortes + ficha = 2 páginas.
        p = _plano("1 FIGADO", self.ct_a, _rd(generate_uid()))
        p["dados"]["rx_fracoes"] = 3
        p["store"]["RP"]["num_fracoes"] = 3
        pdf, imagens, _dvhs = ficha_pdf.gerar_ficha_multiplano(
            [p], "individual", rotulos=["1 FIGADO"])
        self.assertEqual(len(imagens), 1)
        self.assertEqual(self._paginas(pdf), 2)

    def test_combinada_usa_a_visao_do_plano_ativo(self):
        # A página combinada (Soma/Personalizado) tem que sair com os cortes,
        # estruturas e 3D da ABA ABERTA — não com os do primeiro plano do
        # subconjunto. Aparece ao separar a ficha: separado [3, 4] e ajustada a
        # visão na aba do 4, a ficha saía com a visão do 3.
        a, b = self.planos[0], self.planos[1]
        a["recursos"]["mostrar_isodose"] = False
        b["recursos"]["mostrar_isodose"] = True
        b["recursos"]["_ativo"] = True              # aba aberta = 2º plano
        cortes_ativo, _dvh = ficha_pdf._pagina1_soma([a, b])
        # Mesma montagem que sairia com o plano ativo em primeiro lugar…
        b["recursos"].pop("_ativo")
        self.assertEqual(cortes_ativo, ficha_pdf._pagina1_soma([b, a])[0])
        # …e diferente da que sai caindo no primeiro plano (isodose desligada).
        self.assertNotEqual(cortes_ativo, ficha_pdf._pagina1_soma([a, b])[0])

    def test_combinada_usa_a_rs_unificada_da_tela(self):
        # Na visão combinada a tela desenha estruturas/3D da RS unificada; a
        # ficha precisa usar a MESMA (recursos["rs_soma"]), não a RS do plano.
        a = self.planos[0]
        a["recursos"]["_ativo"] = True
        a["recursos"]["rs_soma"] = "RS-UNIFICADA"
        vistos = {}
        orig = ficha_pdf.montar_imagem_pagina1
        ficha_pdf.montar_imagem_pagina1 = lambda d, rec: vistos.setdefault("rs", rec.get("rs"))
        try:
            ficha_pdf._pagina1_soma([a, self.planos[1]])
        finally:
            ficha_pdf.montar_imagem_pagina1 = orig
        self.assertEqual(vistos["rs"], "RS-UNIFICADA")

    def test_soma_uma_unica_pagina_de_cortes(self):
        # Modo soma continua com UMA página combinada (todos).
        seq = [[0, 1, 2, 3]] * 12
        pdf, imagens, _dvhs = ficha_pdf.gerar_ficha_multiplano(
            self.planos, "soma", sequencia=seq,
            rotulos=["1 A", "2 A", "3 A", "4 B"])
        self.assertEqual(len(imagens), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
