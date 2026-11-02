"""Observações do tratamento (digitadas em Edição da Ficha) na caixa da pág. 2.

O texto vai na caixa "Observações gerais do tratamento" nos dois layouts (página
inteira e compacto, com o mapa embutido); o trecho entre ``**`` sai destacado, e
o que não couber é aparado em vez de estourar a caixa.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.papel import ficha_pdf as fp  # noqa: E402


def _canvas():
    from reportlab.pdfgen import canvas
    return canvas.Canvas(io.BytesIO())


def _dados(nfr: int, obs: str) -> tuple[dict, dict]:
    d = {"pac_nome": "X", "pac_registro": "1", "rx_fracoes": nfr,
         "proto_imagem": "MV", "proto_frequencia": "Diária", "observacoes": obs}
    rp = {"num_fracoes": nfr, "dose_fracao": 2.0, "n_isocentros": 1,
          "rotulo_plano": "P", "feixes": [{"gantry": 0, "um": 100}]}
    return d, rp


def _texto_pagina(pdf: bytes, pagina: int = 0) -> str:
    from pypdf import PdfReader
    return PdfReader(io.BytesIO(pdf)).pages[pagina].extract_text()


class TestSegmentos(unittest.TestCase):
    def test_par_de_marcadores_destaca(self):
        self.assertEqual(fp._obs_segmentos("a **b** c"),
                         [("a ", False), ("b", True), (" c", False)])

    def test_marcador_sem_fechar_nao_destaca(self):
        self.assertEqual([hl for _t, hl in fp._obs_segmentos("a ** b")], [False, False])

    def test_linha_toda_destacada(self):
        self.assertEqual(fp._obs_segmentos("**tudo**"), [("tudo", True)])


class TestQuebra(unittest.TestCase):
    def test_respeita_as_quebras_digitadas(self):
        linhas = fp._obs_quebrar(_canvas(), "a\nb\nc", 200, 8)
        self.assertEqual([[t for t, *_ in l] for l in linhas], [["a"], ["b"], ["c"]])

    def test_quebra_por_largura(self):
        linhas = fp._obs_quebrar(_canvas(), "palavra " * 40, 120, 8)
        self.assertGreater(len(linhas), 1)
        for l in linhas:
            self.assertLessEqual(sum(w for *_r, w in l), 120)

    def test_palavra_maior_que_a_caixa_e_partida(self):
        linhas = fp._obs_quebrar(_canvas(), "A" * 300, 100, 8)
        self.assertGreater(len(linhas), 1)
        self.assertEqual("".join(t for l in linhas for t, *_ in l), "A" * 300)

    def test_destaque_sobrevive_a_quebra(self):
        linhas = fp._obs_quebrar(_canvas(), "**" + "destacado " * 30 + "**", 120, 8)
        self.assertTrue(all(hl for l in linhas for t, hl, *_ in l if t.strip()))


class TestNaFicha(unittest.TestCase):
    """A observação aparece no PDF nos dois layouts da pág. 2."""

    def _gerar(self, nfr, obs):
        d, rp = _dados(nfr, obs)
        return fp.gerar_ficha(d, {"RP": rp}, {})

    def setUp(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest("pypdf ausente")

    def test_compacto_e_pagina_inteira(self):
        for nfr in (5, 30):     # 5 = mapa embutido (caixa baixa); 30 = pág. cheia
            with self.subTest(fracoes=nfr):
                txt = _texto_pagina(self._gerar(nfr, "Bolus de 1 cm"))
                self.assertIn("Bolus de 1 cm", txt.replace("\n", " "))

    def test_marcadores_nao_saem_impressos(self):
        txt = _texto_pagina(self._gerar(5, "Conferir **SSD** sempre"))
        self.assertNotIn("**", txt)
        self.assertIn("SSD", txt)

    def test_texto_longo_nao_estoura_a_pagina(self):
        # Muito mais texto do que cabe: é aparado, e a ficha continua de 1 página
        # com o mapa embutido (a caixa não empurra nem deforma o resto).
        pdf = self._gerar(5, "palavra " * 4000)
        from pypdf import PdfReader
        self.assertEqual(len(PdfReader(io.BytesIO(pdf)).pages), 1)

    def test_sem_observacao_a_caixa_fica_vazia(self):
        d, rp = _dados(5, "")
        limpa = _texto_pagina(fp.gerar_ficha(d, {"RP": rp}, {}))
        self.assertIn("Observações", limpa)


class TestMultiplano(unittest.TestCase):
    """Pág. 2 combinada: as observações dos planos vão para a mesma caixa."""

    @staticmethod
    def _plano(rot, nfr, obs):
        return {"dados": {"pac_nome": "X", "proto_imagem": "MV",
                          "proto_frequencia": "Diária", "observacoes": obs},
                "store": {"RP": {"rotulo_plano": rot, "num_fracoes": nfr,
                                 "dose_fracao": 8.0, "n_isocentros": 1,
                                 "feixes": [{"gantry": 0, "um": 100}]}},
                "recursos": {}}

    def test_um_plano_anotado_sai_sem_rotulo(self):
        planos = [self._plano("1 A", 3, ""), self._plano("2 B", 2, "So este")]
        self.assertEqual(fp._obs_dos_planos(planos, ["1 A", "2 B"]), "So este")

    def test_observacao_do_caso_sai_uma_vez(self):
        # O texto é do caso: vem repetido em todos os planos e a caixa é uma só.
        planos = [self._plano(r, 3, "Do caso") for r in ("1 A", "2 B", "3 C", "4 D")]
        self.assertEqual(fp._obs_dos_planos(planos, ["1 A", "2 B", "3 C", "4 D"]),
                         "Do caso")

    def test_varios_planos_saem_rotulados(self):
        planos = [self._plano("1 A", 3, "um"), self._plano("2 B", 2, "dois")]
        self.assertEqual(fp._obs_dos_planos(planos, ["1 A", "2 B"]),
                         "1 A: um\n2 B: dois")

    def test_nenhum_anotado(self):
        planos = [self._plano("1 A", 3, ""), self._plano("2 B", 2, "  ")]
        self.assertEqual(fp._obs_dos_planos(planos, ["1 A", "2 B"]), "")


if __name__ == "__main__":
    unittest.main()
