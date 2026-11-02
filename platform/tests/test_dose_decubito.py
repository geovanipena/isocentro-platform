"""Grade de dose x decúbito do paciente — o caso do prono (decúbito ventral).

``PixelSpacing`` é sempre positivo; quem diz se a coordenada CRESCE ou DIMINUI
ao andar na grade é o ``ImageOrientationPatient``. Em decúbito ventral (HFP/FFP)
o IOP é [-1,0,0, 0,-1,0]: x e y DIMINUEM a partir do ``ImagePositionPatient``.

Enquanto isso era ignorado, a grade de dose ficava espelhada em torno do IPP:
todo índice calculado dava negativo, o ``clip`` prendia a amostragem na borda da
grade (dose ~0) e o colorwash simplesmente **não aparecia** no paciente prono —
sem erro, sem log, sem nada na tela.

Sintético de propósito: a resposta é analítica (sabemos em que coordenada de
paciente está o ponto quente que plantamos), então o teste mede o código, não um
export de TPS. Vale para os quatro decúbitos, não só o que quebrou.

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
from isocentro.dicom import dicom_rt  # noqa: E402
from isocentro.dicom import dose3d  # noqa: E402

# IOP de cada decúbito: (componente X da direção-linha, componente Y da direção-coluna).
IOP_POR_POSICAO = {
    "HFS": [1, 0, 0, 0, 1, 0],
    "FFS": [-1, 0, 0, 0, 1, 0],
    "HFP": [-1, 0, 0, 0, -1, 0],
    "FFP": [1, 0, 0, 0, -1, 0],
}

NZ, NY, NX = 3, 8, 8
PS = 5.0        # mm por pixel da grade de dose
QUENTE = (1, 5, 6)   # (frame, linha, coluna) onde plantamos a dose máxima


def _rd(pos: str, ipp=(0.0, 0.0, 0.0)) -> Dataset:
    """RT Dose sintético num decúbito, com UM ponto quente conhecido.

    O IPP é sempre o canto do primeiro pixel — o que muda com o decúbito é para
    que LADO a grade cresce a partir dele.
    """
    ds = Dataset()
    ds.Modality = "RTDOSE"
    ds.Rows, ds.Columns, ds.NumberOfFrames = NY, NX, NZ
    ds.BitsAllocated = 32
    ds.BitsStored = 32
    ds.HighBit = 31
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.ImagePositionPatient = [float(v) for v in ipp]
    ds.ImageOrientationPatient = [float(v) for v in IOP_POR_POSICAO[pos]]
    ds.PixelSpacing = [PS, PS]
    ds.GridFrameOffsetVector = [0.0, PS, 2 * PS]
    ds.DoseGridScaling = 0.01
    arr = np.ones((NZ, NY, NX), dtype=np.uint32)
    arr[QUENTE] = 200            # 2 Gy no ponto quente, 0,01 Gy no resto
    ds.PixelData = arr.tobytes()
    fm = FileMetaDataset()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.MediaStorageSOPClassUID = generate_uid()
    fm.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta = fm
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    return ds


def _xyz_do_quente(pos: str, ipp=(0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    """Coordenada de PACIENTE (mm) do ponto quente, pela definição do DICOM.

    O Z segue a NORMAL do plano (linha × coluna), não o eixo Z do paciente: o
    ``GridFrameOffsetVector`` é medido ao longo dela. Esta função dizia
    ``ipp[2] + PS * fz`` para os quatro decúbitos — o que é verdade só quando a
    normal aponta para +Z, e não é o caso do FFS nem do FFP. O export real
    9000021ANA (21/08/2026) mostrou o preço: estruturas em z −734…−5 mm e grade
    calculada em z −2…+733, uma grade inteira fora do paciente.
    """
    fz, ln, col = QUENTE
    sr, sc = IOP_POR_POSICAO[pos][4], IOP_POR_POSICAO[pos][0]
    sn = -1.0 if (sc < 0) != (sr < 0) else 1.0
    return (ipp[0] + sc * PS * col, ipp[1] + sr * PS * ln, ipp[2] + sn * PS * fz)


class TestSinaisIOP(unittest.TestCase):
    """O sinal de cada eixo sai do IOP, não do PixelSpacing."""

    def test_quatro_decubitos(self):
        esperado = {"HFS": (1.0, 1.0), "FFS": (1.0, -1.0),
                    "HFP": (-1.0, -1.0), "FFP": (-1.0, 1.0)}
        for pos, alvo in esperado.items():
            with self.subTest(pos=pos):
                self.assertEqual(dicom_rt.sinais_iop(_rd(pos)), alvo)

    def test_sem_iop_assume_canonico(self):
        ds = Dataset()   # dataset sem ImageOrientationPatient nenhum
        self.assertEqual(dicom_rt.sinais_iop(ds), (1.0, 1.0))

    def test_iop_invalido_nao_quebra(self):
        class _Lixo:                              # curto demais e não numérico
            ImageOrientationPatient = ["x", "y"]
        self.assertEqual(dicom_rt.sinais_iop(_Lixo()), (1.0, 1.0))


class TestSinalDaNormal(unittest.TestCase):
    """Para que lado, em Z, andam os offsets de corte do RT Dose.

    Ficou faltando quando o decúbito ventral foi corrigido em x e y: só aparece
    quando a normal do plano é invertida (FFS/FFP), e nesses casos a grade
    inteira ia parar a uma grade de distância do paciente. Sem sobreposição o
    DVH sai VAZIO e a isodose some; com sobreposição parcial sai um DVH de
    números plausíveis e errados — 1,15 Gy num tratamento de 8 Gy.
    """

    def test_quatro_decubitos(self):
        esperado = {"HFS": 1.0, "FFS": -1.0, "HFP": 1.0, "FFP": -1.0}
        for pos, alvo in esperado.items():
            with self.subTest(pos=pos):
                self.assertEqual(dicom_rt.sinal_normal_iop(_rd(pos)), alvo)

    def test_sem_iop_assume_canonico(self):
        self.assertEqual(dicom_rt.sinal_normal_iop(Dataset()), 1.0)

    def test_iop_invalido_nao_quebra(self):
        class _Lixo:
            ImageOrientationPatient = ["x", "y"]
        self.assertEqual(dicom_rt.sinal_normal_iop(_Lixo()), 1.0)

    def test_no_FFS_o_z_DECRESCE_a_partir_do_ipp(self):
        z, _y, _x = dose3d._eixos_brutos_de_rd(
            _rd("FFS", ipp=(0.0, 0.0, -2.0)))
        self.assertLess(z[-1], z[0])
        self.assertAlmostEqual(float(z[0]), -2.0)
        self.assertAlmostEqual(float(z[-1]), -2.0 - 2 * PS)

    def test_no_HFS_nada_muda(self):
        """A correção não pode mexer no decúbito da maioria das fichas."""
        z, _y, _x = dose3d._eixos_brutos_de_rd(
            _rd("HFS", ipp=(0.0, 0.0, -2.0)))
        self.assertAlmostEqual(float(z[0]), -2.0)
        self.assertAlmostEqual(float(z[-1]), -2.0 + 2 * PS)

    def test_a_isodose_usa_o_MESMO_z_que_a_grade(self):
        """O colorwash monta a grade por conta própria (``_dose_pct_grade``), e
        ela ficou com o defeito por mais tempo que a do DVH: dois caminhos para
        a mesma geometria é como um conserta e o outro não."""
        for pos in IOP_POR_POSICAO:
            with self.subTest(pos=pos):
                rd = _rd(pos, ipp=(0.0, 0.0, -2.0))
                grade = ct_series._dose_pct_grade(rd, None)
                self.assertIsNotNone(grade)
                zs_iso = np.asarray(grade[1], dtype=float)
                z_grade, _y, _x = dose3d._eixos_brutos_de_rd(
                    _rd(pos, ipp=(0.0, 0.0, -2.0)))
                self.assertTrue(np.allclose(np.sort(zs_iso),
                                            np.sort(z_grade)))


class TestGradeDose3D(unittest.TestCase):
    """dose3d.grade_de_rd põe a dose na coordenada de paciente certa."""

    def test_ponto_quente_na_coordenada_certa(self):
        for pos in IOP_POR_POSICAO:
            with self.subTest(pos=pos):
                g = dose3d.grade_de_rd(_rd(pos))
                # Eixos sempre crescentes, qualquer que seja o decúbito.
                for eixo in (g.x, g.y, g.z):
                    self.assertTrue(np.all(np.diff(eixo) > 0))
                x, y, z = _xyz_do_quente(pos)
                iz = int(np.argmin(np.abs(g.z - z)))
                iy = int(np.argmin(np.abs(g.y - y)))
                ix = int(np.argmin(np.abs(g.x - x)))
                self.assertAlmostEqual(float(g.dose[iz, iy, ix]), 2.0, places=6)
                # E o máximo do volume está nesse mesmo voxel — a dose não foi
                # parar noutro canto da grade.
                self.assertEqual(np.unravel_index(int(np.argmax(g.dose)),
                                                  g.dose.shape),
                                 (iz, iy, ix))

    def test_prono_x_e_y_decrescem_a_partir_do_ipp(self):
        # Antes da correção, x e y CRESCIAM a partir do IPP também no prono, o
        # que jogava a grade inteira para o lado oposto do paciente.
        z, y, x = dose3d._eixos_brutos_de_rd(_rd("HFP", ipp=(100.0, 50.0, 0.0)))
        self.assertLess(x[-1], x[0])
        self.assertLess(y[-1], y[0])
        self.assertAlmostEqual(x[0], 100.0)
        self.assertAlmostEqual(x[-1], 100.0 - PS * (NX - 1))

    def test_eixos_de_rd_concorda_com_a_grade(self):
        # _eixos_de_rd monta a grade união da soma sem decodificar pixel; ele e
        # grade_de_rd têm de dar exatamente os mesmos eixos, ou a soma reamostra
        # numa geometria que não é a da dose.
        for pos in IOP_POR_POSICAO:
            with self.subTest(pos=pos):
                z, y, x = dose3d._eixos_de_rd(_rd(pos))
                g = dose3d.grade_de_rd(_rd(pos))
                for a, b in ((z, g.z), (y, g.y), (x, g.x)):
                    self.assertTrue(np.allclose(a, b))


class _CTFalsa:
    """Só a geometria que ``_amostrar_axial`` usa (ipp0 + espaçamento com sinal)."""

    def __init__(self, pos: str):
        sr, sc = dicom_rt.sinais_iop(_rd(pos))
        self.rows = self.cols = 16
        self.psr = self.psc = 2.5
        self.psr_eff, self.psc_eff = self.psr * sr, self.psc * sc
        # TC centrada na mesma região da grade de dose, no mesmo sentido.
        self.ipp0 = [0.0, 0.0, 0.0]


class TestColorwashPorDecubito(unittest.TestCase):
    """O caminho do colorwash (plano individual) enxerga a dose no prono."""

    def _dose_no_corte_do_quente(self, pos: str) -> np.ndarray:
        rd = _rd(pos)
        grade = ct_series._dose_pct_grade(rd)
        self.assertIsNotNone(grade, "grade de dose não deveria ser vazia")
        ct = _CTFalsa(pos)
        _, _, z = _xyz_do_quente(pos)
        dose_2d = ct_series._amostrar_axial(grade, ct.ipp0, ct.psr_eff, ct.psc_eff,
                                            ct.rows, ct.cols, z)
        self.assertIsNotNone(dose_2d)
        return dose_2d

    def test_dose_aparece_nos_quatro_decubitos(self):
        # A regressão do prono: dose_2d vinha inteira na borda fria da grade.
        for pos in IOP_POR_POSICAO:
            with self.subTest(pos=pos):
                self.assertAlmostEqual(float(self._dose_no_corte_do_quente(pos).max()),
                                       100.0, places=4)

    def test_ponto_quente_no_pixel_certo_da_tc(self):
        """O pixel da TC que cai sobre o ponto quente recebe os 100%.

        Não se compara com o ``argmax``: a TC é mais fina que a grade de dose
        (2,5 mm x 5 mm), então DOIS pixels vizinhos amostram o mesmo voxel
        quente e o argmax pega arbitrariamente o primeiro. O que importa é que
        o pixel na coordenada certa esteja quente e o do outro lado, frio.
        """
        for pos in IOP_POR_POSICAO:
            with self.subTest(pos=pos):
                ct = _CTFalsa(pos)
                dose_2d = self._dose_no_corte_do_quente(pos)
                x, y, _ = _xyz_do_quente(pos)
                lin = int(round((y - ct.ipp0[1]) / ct.psr_eff))
                col = int(round((x - ct.ipp0[0]) / ct.psc_eff))
                self.assertAlmostEqual(float(dose_2d[lin, col]), 100.0, places=4)
                # Quatro voxels de dose ao lado: fora do ponto quente.
                self.assertLess(float(dose_2d[lin, (col + 8) % ct.cols]), 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
