"""A isodose não pode aparecer fora do paciente.

A grade de dose do TPS não para na pele: ela cobre uma caixa em volta do alvo,
com valores no ar. Desenhada como está, a ficha mostrava colorwash flutuando ao
lado do corpo. O recorte é pela máscara do paciente — que inclui o BÓLUS, porque
ali a dose fora do contorno externo é real.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.desenho import corte  # noqa: E402
from isocentro.dicom import ct_series  # noqa: E402


def _img_cinza(n: int = 20) -> Image.Image:
    return Image.fromarray(np.full((n, n, 3), 128, dtype=np.uint8), "RGB")


def _pintados(img: Image.Image, base: Image.Image) -> np.ndarray:
    """Máscara dos pixels que o colorwash mexeu."""
    return np.any(np.asarray(img, dtype=int) != np.asarray(base, dtype=int), axis=2)


class TestRecorteDoColorwash(unittest.TestCase):

    def setUp(self):
        self.base = _img_cinza()
        # Dose alta em TODO o corte — o pior caso: sem recorte, pinta tudo.
        self.dose = np.full((20, 20), 90.0, dtype=float)
        self.corpo = np.zeros((20, 20), dtype=bool)
        self.corpo[5:15, 5:15] = True

    def test_sem_mascara_pinta_o_corte_inteiro(self):
        out = corte._aplicar_colorwash(self.base, self.dose, (50.0, 100.0))
        self.assertTrue(_pintados(out, self.base).all())

    def test_com_mascara_nao_pinta_fora_do_corpo(self):
        out = corte._aplicar_colorwash(self.base, self.dose, (50.0, 100.0),
                                           dentro=self.corpo)
        pint = _pintados(out, self.base)
        self.assertFalse(pint[~self.corpo].any(), "isodose vazou para fora do corpo")
        self.assertTrue(pint[self.corpo].all(), "isodose sumiu de dentro do corpo")

    def test_dose_abaixo_do_limiar_continua_sem_overlay(self):
        baixa = np.full((20, 20), 10.0)
        out = corte._aplicar_colorwash(self.base, baixa, (50.0, 100.0),
                                           dentro=self.corpo)
        self.assertFalse(_pintados(out, self.base).any())

    def test_mascara_de_forma_errada_e_ignorada(self):
        # Proteção: máscara de outro plano não pode apagar a isodose inteira.
        out = corte._aplicar_colorwash(self.base, self.dose, (50.0, 100.0),
                                           dentro=np.zeros((3, 3), dtype=bool))
        self.assertTrue(_pintados(out, self.base).all())


def _roi(nome: str, tipo: str) -> dict:
    return {"nome": nome, "tipo": tipo}


class TestBolusEntraNaMascara(unittest.TestCase):
    """Onde há bólus a dose fora do contorno externo é real, e tem de aparecer."""

    def test_reconhece_pelo_tipo_dicom(self):
        self.assertTrue(ct_series._eh_bolus(_roi("B1", "BOLUS")))

    def test_reconhece_pelo_nome_quando_o_tps_nao_marca_o_tipo(self):
        # O Monaco só usa EXTERNAL/ORGAN/PTV/SUPPORT/MARKER.
        for nome in ("Bolus", "BOLUS 5mm", "bólus mama", "bolus_pele"):
            self.assertTrue(ct_series._eh_bolus(_roi(nome, "ORGAN")), nome)

    def test_nao_confunde_com_anatomia(self):
        for nome, tipo in (("BEXIGA", "ORGAN"), ("PTV 30Gy", "PTV"),
                           ("Foam Core", "SUPPORT"), ("CORPO", "EXTERNAL")):
            self.assertFalse(ct_series._eh_bolus(_roi(nome, tipo)), nome)


class TestMascaraDoCorpo(unittest.TestCase):
    """A máscara é EXTERNAL ∪ bólus, e some quando o corpo não está contornado."""

    NZ, N, PS, DZ = 4, 40, 4.0, 4.0

    def setUp(self):
        from tests.test_cortes_axial import _ct_slice  # reusa a TC sintética
        self.ct = ct_series.CTSerie([_ct_slice(i * self.DZ) for i in range(self.NZ)])

    def _rs(self, com_bolus: bool) -> Dataset:
        rs = Dataset()
        rois, obs, contornos = [], [], []
        partes = [(1, "BODY", "EXTERNAL", [(20, 20), (100, 20), (100, 100), (20, 100)])]
        if com_bolus:
            partes.append((2, "Bolus", "ORGAN",
                           [(100, 20), (140, 20), (140, 100), (100, 100)]))
        for num, nome, tipo, quad in partes:
            r = Dataset(); r.ROINumber = num; r.ROIName = nome; rois.append(r)
            o = Dataset(); o.ReferencedROINumber = num
            o.RTROIInterpretedType = tipo; obs.append(o)
            rc = Dataset(); rc.ReferencedROINumber = num
            rc.ROIDisplayColor = [0, 255, 0]
            c = Dataset(); c.ContourGeometricType = "CLOSED_PLANAR"
            c.ContourData = [float(v) for xy in quad for v in (xy[0], xy[1], 0.0)]
            c.NumberOfContourPoints = len(quad)
            rc.ContourSequence = Sequence([c])
            contornos.append(rc)
        rs.StructureSetROISequence = Sequence(rois)
        rs.RTROIObservationsSequence = Sequence(obs)
        rs.ROIContourSequence = Sequence(contornos)
        return rs

    def test_bolus_amplia_a_area_liberada(self):
        so_corpo = self.ct._mascara_corpo("Axial", 0, self._rs(False), 0.0)
        com_bolus = self.ct._mascara_corpo("Axial", 0, self._rs(True), 0.0)
        self.assertIsNotNone(so_corpo)
        self.assertGreater(com_bolus.sum(), so_corpo.sum())
        # Tudo que era corpo continua liberado; o bólus só acrescenta.
        self.assertTrue(com_bolus[so_corpo].all())

    def test_fatia_sem_contorno_nao_recorta_nada(self):
        # Sem máscara a TC sai crua e a dose sai inteira — melhor que fatia vazia.
        self.assertIsNone(self.ct._mascara_corpo("Axial", 3, self._rs(False),
                                                 3 * self.DZ))

    def test_bolus_sozinho_na_fatia_nao_vale_como_corpo(self):
        # O bólus está em TODAS as fatias, o corpo só na primeira (é assim que o
        # TPS entrega: o BODY não vai de ponta a ponta). Uma máscara de bólus
        # sozinho pintaria de fundo o corte quase inteiro — "o axial sumia".
        rs = self._rs(True)
        rs.ROIContourSequence[1].ContourSequence[0].ContourData = [
            100.0, 20.0, 12.0, 140.0, 20.0, 12.0,
            140.0, 100.0, 12.0, 100.0, 100.0, 12.0]
        self.assertIsNone(self.ct._mascara_corpo("Axial", 3, rs, 3 * self.DZ))

    def test_indice_fora_da_faixa_nao_escapa_do_corte(self):
        # Máscara de um plano que não está na tela apagaria a isodose da que está.
        m = self.ct._mascara_corpo("Sagital", 10_000, self._rs(False), None)
        igual = self.ct._mascara_corpo("Sagital", self.N - 1, self._rs(False), None)
        if m is None:
            self.assertIsNone(igual)
        else:
            self.assertTrue(np.array_equal(m, igual))


class TestBuracosEmZ(unittest.TestCase):
    """BODY sem contorno em toda fatia (no Monaco há buracos de até 15 mm em z)
    não pode deixar a máscara listrada: recortando a isodose com ela, o colorwash
    saía em faixas horizontais no sagital e no coronal."""

    NZ, PS, DZ = 8, 4.0, 4.0

    def setUp(self):
        from tests.test_cortes_axial import _ct_slice
        self.ct = ct_series.CTSerie([_ct_slice(i * self.DZ)
                                     for i in range(self.NZ)])

    def _rs_com_buracos(self, zs) -> Dataset:
        rs = Dataset()
        r = Dataset(); r.ROINumber = 1; r.ROIName = "BODY"
        o = Dataset(); o.ReferencedROINumber = 1; o.RTROIInterpretedType = "EXTERNAL"
        rc = Dataset(); rc.ReferencedROINumber = 1; rc.ROIDisplayColor = [0, 255, 0]
        cs = []
        for z in zs:
            c = Dataset(); c.ContourGeometricType = "CLOSED_PLANAR"
            quad = [(20, 20), (100, 20), (100, 100), (20, 100)]
            c.ContourData = [float(v) for xy in quad
                             for v in (xy[0], xy[1], float(z))]
            c.NumberOfContourPoints = len(quad)
            cs.append(c)
        rc.ContourSequence = Sequence(cs)
        rs.StructureSetROISequence = Sequence([r])
        rs.RTROIObservationsSequence = Sequence([o])
        rs.ROIContourSequence = Sequence([rc])
        return rs

    def test_fatia_sem_contorno_herda_a_vizinha(self):
        # Contornado só nas fatias pares: nenhuma linha ENTRE elas pode sair vazia.
        rs = self._rs_com_buracos([i * self.DZ for i in range(0, self.NZ, 2)])
        for plano in ("Sagital", "Coronal"):
            with self.subTest(plano=plano):
                m = self.ct._mascara_corpo(plano, 15, rs, None)
                self.assertIsNotNone(m)
                cheias = [r for r in range(m.shape[0]) if m[r].any()]
                self.assertEqual(cheias, list(range(min(cheias), max(cheias) + 1)),
                                 "máscara listrada: fatia sem contorno ficou vazia")

    # Corpo contornado em z=0 e z=20 apenas: com fatias de 4 mm, os cortes de
    # z=8 e z=12 ficam a mais de meia fatia de qualquer contorno — é o buraco
    # de verdade (o do Monaco pula até 15 mm). Acima de z=20 é ar.
    _SO_NAS_PONTAS = [0.0, 20.0]

    def test_axial_no_buraco_herda_a_fatia_vizinha(self):
        # Sem remendo o corte devolvia None, e None significa "não recorta
        # nada": a isodose voltava a aparecer no ar justamente ali.
        rs = self._rs_com_buracos(self._SO_NAS_PONTAS)
        for i in range(6):                      # z = 0…20, dentro do corpo
            with self.subTest(fatia=i, z=i * self.DZ):
                m = self.ct._mascara_corpo("Axial", i, rs, i * self.DZ)
                self.assertIsNotNone(m, "corte sem máscara: isodose vaza no ar")
                self.assertTrue(m.any())

    def test_axial_fora_da_extensao_do_corpo_segue_sem_mascara(self):
        # Acima do corpo é ar de verdade: não há fatia para herdar, e a TC crua
        # (sem recorte) é o comportamento certo. O corte de z=24 ainda está a
        # meia fatia do último contorno (z=20) e segue recortado — é a tolerância
        # de sempre, que dá ao último corte a espessura dele.
        rs = self._rs_com_buracos(self._SO_NAS_PONTAS)
        self.assertIsNotNone(self.ct._mascara_corpo("Axial", 6, rs, 24.0))
        self.assertIsNone(self.ct._mascara_corpo("Axial", 7, rs, 28.0))

    def test_fora_da_extensao_do_corpo_segue_vazio(self):
        # Só as duas primeiras fatias têm corpo: acima delas é ar de verdade e a
        # máscara não pode esticar o paciente até o fim da imagem.
        rs = self._rs_com_buracos([0.0, self.DZ])
        m = self.ct._mascara_corpo("Sagital", 15, rs, None)
        self.assertIsNotNone(m)
        self.assertEqual(sorted(r for r in range(m.shape[0]) if m[r].any()),
                         [self.NZ - 2, self.NZ - 1])   # linha 0 = último z


if __name__ == "__main__":
    unittest.main()
