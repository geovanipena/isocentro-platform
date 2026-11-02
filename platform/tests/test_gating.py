"""Detecção de gating no RT Plan (dicom_rt._gating_do_plano).

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dicom import dicom_rt  # noqa: E402


def _plano(tecnica, com_setup=True, com_msq=True):
    """RT Plan mínimo com PatientSetupSequence → MotionSynchronizationSequence."""
    from pydicom.dataset import Dataset
    from pydicom.sequence import Sequence
    ds = Dataset()
    if not com_setup:
        return ds
    ps = Dataset()
    if com_msq:
        msq = Dataset()
        if tecnica is not None:
            msq.RespiratoryMotionCompensationTechnique = tecnica
        ps.MotionSynchronizationSequence = Sequence([msq])
    ds.PatientSetupSequence = Sequence([ps])
    return ds


class TestGatingDoPlano(unittest.TestCase):
    def test_gating(self):
        self.assertEqual(dicom_rt._gating_do_plano(_plano("GATING")), (True, "GATING"))

    def test_breath_hold(self):
        self.assertEqual(dicom_rt._gating_do_plano(_plano("BREATH_HOLD")),
                         (True, "BREATH_HOLD"))

    def test_minuscula_normaliza(self):
        self.assertEqual(dicom_rt._gating_do_plano(_plano("gating")), (True, "GATING"))

    def test_none_nao_conta(self):
        self.assertEqual(dicom_rt._gating_do_plano(_plano("NONE")), (False, ""))

    def test_sem_tecnica(self):
        self.assertEqual(dicom_rt._gating_do_plano(_plano(None)), (False, ""))

    def test_sem_sequencia_de_sincronizacao(self):
        self.assertEqual(dicom_rt._gating_do_plano(_plano("GATING", com_msq=False)),
                         (False, ""))

    def test_sem_patient_setup(self):
        self.assertEqual(dicom_rt._gating_do_plano(_plano(None, com_setup=False)),
                         (False, ""))

    def test_segundo_setup_tem_gating(self):
        from pydicom.dataset import Dataset
        from pydicom.sequence import Sequence
        ds = Dataset()
        ps_sem = Dataset()   # 1º setup sem gating
        ps_com = Dataset()
        msq = Dataset(); msq.RespiratoryMotionCompensationTechnique = "GATING"
        ps_com.MotionSynchronizationSequence = Sequence([msq])
        ds.PatientSetupSequence = Sequence([ps_sem, ps_com])
        self.assertEqual(dicom_rt._gating_do_plano(ds), (True, "GATING"))


class TestJanelaFaseDeTexto(unittest.TestCase):
    def test_serie_4dct(self):
        self.assertEqual(
            dicom_rt.janela_fase_de_texto("Ave(7) 20%_30%_40%_50%_60%_70%_80%_"),
            (20, 80))

    def test_duas_fases(self):
        self.assertEqual(dicom_rt.janela_fase_de_texto("Gated 30%_70%"), (30, 70))

    def test_uma_fase_nao_e_janela(self):
        self.assertIsNone(dicom_rt.janela_fase_de_texto("CT 40%"))

    def test_sem_fase(self):
        self.assertIsNone(dicom_rt.janela_fase_de_texto("Abdome helicoidal"))
        self.assertIsNone(dicom_rt.janela_fase_de_texto(""))

    def test_ignora_percentuais_invalidos(self):
        # 150% não é fase; sobra só 40% → não forma janela
        self.assertIsNone(dicom_rt.janela_fase_de_texto("dose 150% em 40%"))


def _mp(*textos):
    """MOTIONMTPROTOCOL mínimo: um elemento privado com o texto do gate."""
    from pydicom.dataset import Dataset
    ds = Dataset()
    # Bloco privado da Varian; o valor cru concatena o vocabulário do gate.
    blk = ds.private_block(0x3283, "Varian Medical Systems VISION 3283",
                           create=True)
    blk.add_new(0x10, "UN", (" ".join(textos)).encode("latin1"))
    return ds


# Fragmentos representativos do que cada protocolo real traz.
_MP_FASE = _mp("Phase", "deg", "degree", "Value denotes the phase of specified property")
_MP_AMPLITUDE = _mp("Ant.-Post.", "millimeter", "Target Position", "CALCMAX", "Threshold")


class TestModalidadeGatingDoMp(unittest.TestCase):
    def test_fase(self):
        self.assertEqual(dicom_rt.modalidade_gating_do_mp(_MP_FASE), "Fase")

    def test_amplitude(self):
        self.assertEqual(dicom_rt.modalidade_gating_do_mp(_MP_AMPLITUDE), "Amplitude")

    def test_ambiguo_fica_em_branco(self):
        self.assertEqual(dicom_rt.modalidade_gating_do_mp(_mp("curve", "freebreathing")), "")


class TestDescricaoBreathHold(unittest.TestCase):
    def test_indica_dibh(self):
        for s in ("INSP FORCADA   INSP FORCADA  Vol 2.0", "DIBH", "dibh insp",
                  "Breath Hold", "BreathHold", "Apneia inspiratoria",
                  "Inspiração forçada"):
            self.assertTrue(dicom_rt.descricao_indica_breath_hold(s), s)

    def test_nao_confunde_com_4dct_nem_generico(self):
        for s in ("Ave(7) 20%_30%_40%_50%_60%_70%_80%", "Gated 30%_70%",
                  "TC Torax Vol 2.0", "", "MIP", "helical",
                  # Fases 4DCT em inglês NÃO são breath-hold (só "inspir" solto).
                  "Inspiration 4DCT phase", "Inspiratory phase 0-50%"):
            self.assertFalse(dicom_rt.descricao_indica_breath_hold(s), s)


class TestEnriquecerGating(unittest.TestCase):
    def test_dibh_do_texto_quando_gating_sem_mp(self):
        # TC7: técnica GATING (não BREATH_HOLD), sem MOTIONMTPROTOCOL, série de
        # apneia inspiratória → DIBH deduzido da descrição.
        rp = {"gating_plano": True, "gating_tecnica": "GATING"}
        dicom_rt.enriquecer_gating(rp, "INSP FORCADA  Vol 2.0", None)
        self.assertEqual(rp["gating_modalidade"], "Breath-Hold")

    def test_gating_sem_mp_e_sem_dica_fica_em_branco(self):
        rp = {"gating_plano": True, "gating_tecnica": "GATING"}
        dicom_rt.enriquecer_gating(rp, "TC Torax Vol 2.0", None)
        self.assertNotIn("gating_modalidade", rp)

    def test_a_descricao_de_apneia_vence_o_amplitude_do_MP(self):
        """Caso real de 04/09/2026: paciente em DIBH, ficha saindo "Amplitude".

        A regra anterior era "o MP amplitude manda", e ela estava invertida. O
        MP **não distingue** os dois: no RPM da Varian o DIBH É uma janela de
        amplitude no marcador externo, então "amplitude" no protocolo é o que o
        DIBH parece nesse nível — não é prova contra ele. Quem separa DIBH de
        gating por amplitude em respiração livre é a descrição da série, que
        diz como a imagem foi ADQUIRIDA.
        """
        rp = {"gating_plano": True, "gating_tecnica": "GATING"}
        dicom_rt.enriquecer_gating(rp, "INSP FORCADA", _MP_AMPLITUDE)
        self.assertEqual(rp["gating_modalidade"], "Breath-Hold")

    def test_amplitude_continua_amplitude_sem_dica_de_apneia(self):
        """Gating por amplitude em respiração livre não pode virar DIBH: a
        descrição é que decide, e quando ela não diz nada o MP manda."""
        rp = {"gating_plano": True, "gating_tecnica": "GATING"}
        dicom_rt.enriquecer_gating(rp, "TC Torax Vol 2.0", _MP_AMPLITUDE)
        self.assertEqual(rp["gating_modalidade"], "Amplitude")

    def test_a_FASE_continua_vencendo_a_descricao(self):
        """Fase é distinguível no MP — 4DCT é outra aquisição, com as fases em
        % na própria descrição. Só o par amplitude×DIBH era ambíguo."""
        rp = {"gating_plano": True, "gating_tecnica": "GATING"}
        dicom_rt.enriquecer_gating(rp, "INSP FORCADA 20%_80%", _MP_FASE)
        self.assertEqual(rp["gating_modalidade"], "Fase")


    def test_fase_do_mp_com_janela_da_serie(self):
        rp = {"gating_plano": True, "gating_tecnica": "GATING"}
        dicom_rt.enriquecer_gating(rp, "Ave(7) 20%_30%_40%_50%_60%_70%_80%_", _MP_FASE)
        self.assertEqual(rp["gating_modalidade"], "Fase")
        self.assertEqual(rp["gating_fase"], "20-80")

    def test_amplitude_do_mp_nao_usa_janela_da_serie(self):
        # Série 4DCT do ciclo inteiro (0-90%) NÃO deve virar janela de fase.
        rp = {"gating_plano": True, "gating_tecnica": "GATING"}
        dicom_rt.enriquecer_gating(
            rp, "Ave(10) 0%_10%_20%_30%_40%_50%_60%_70%_80%_90%_", _MP_AMPLITUDE)
        self.assertEqual(rp["gating_modalidade"], "Amplitude")
        self.assertNotIn("gating_fase", rp)

    def test_breath_hold_do_plano(self):
        rp = {"gating_plano": True, "gating_tecnica": "BREATH_HOLD"}
        dicom_rt.enriquecer_gating(rp, "", None)
        self.assertEqual(rp["gating_modalidade"], "Breath-Hold")

    def test_gating_sem_mp_fica_em_branco(self):
        # Sem protocolo, a série sozinha não decide amplitude×fase.
        rp = {"gating_plano": True, "gating_tecnica": "GATING"}
        dicom_rt.enriquecer_gating(rp, "Ave(7) 20%_80%", None)
        self.assertNotIn("gating_modalidade", rp)

    def test_sem_gating_nao_toca(self):
        rp = {"gating_plano": False, "gating_tecnica": ""}
        dicom_rt.enriquecer_gating(rp, "Ave(7) 20%_80%", _MP_FASE)
        self.assertNotIn("gating_modalidade", rp)

    def test_nao_sobrescreve_modalidade_existente(self):
        rp = {"gating_plano": True, "gating_tecnica": "GATING",
              "gating_modalidade": "Amplitude"}
        dicom_rt.enriquecer_gating(rp, "Ave(7) 20%_80%", _MP_FASE)
        self.assertEqual(rp["gating_modalidade"], "Amplitude")
        self.assertNotIn("gating_fase", rp)


if __name__ == "__main__":
    unittest.main()
