"""frame_uid: identidade da TC de um RT Dose/Struct.

Regressão do TC6 (crânio): um plano só com RS (sem RD) tinha frame vazio, porque
o RT Struct não traz FrameOfReferenceUID no topo — está em
ReferencedFrameOfReferenceSequence. Com >1 TC, o plano não casava com nenhuma
série e os cortes sumiam (viewer em branco).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dicom import dose3d
from pydicom.dataset import Dataset


class TestFrameUid(unittest.TestCase):
    def test_rt_dose_usa_frame_do_topo(self):
        ds = Dataset()
        ds.FrameOfReferenceUID = "1.2.3.CRANIO"
        self.assertEqual(dose3d.frame_uid(ds), "1.2.3.CRANIO")

    def test_rt_struct_usa_frame_referenciado(self):
        # RS: sem frame no topo; está na ReferencedFrameOfReferenceSequence.
        ref = Dataset()
        ref.FrameOfReferenceUID = "1.2.3.CRANIO"
        rs = Dataset()
        rs.ReferencedFrameOfReferenceSequence = [ref]
        self.assertEqual(dose3d.frame_uid(rs), "1.2.3.CRANIO")

    def test_topo_tem_prioridade(self):
        ref = Dataset()
        ref.FrameOfReferenceUID = "1.2.3.OUTRO"
        ds = Dataset()
        ds.FrameOfReferenceUID = "1.2.3.TOPO"
        ds.ReferencedFrameOfReferenceSequence = [ref]
        self.assertEqual(dose3d.frame_uid(ds), "1.2.3.TOPO")

    def test_sem_frame_nenhum_e_vazio(self):
        self.assertEqual(dose3d.frame_uid(Dataset()), "")

    def test_sequencia_vazia_nao_quebra(self):
        rs = Dataset()
        rs.ReferencedFrameOfReferenceSequence = []
        self.assertEqual(dose3d.frame_uid(rs), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
