"""Tamanho do gráfico do DVH: a legenda se acomoda, o gráfico não encolhe.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.desenho import grafico_dvh as dvh  # noqa: E402


def _curvas(n: int, prefixo: str = "Estrutura") -> dict:
    bins = np.linspace(0, 80, 50)
    return {
        f"{prefixo} {i + 1}": {
            "dose": bins,
            "volume": 100.0 / (1 + np.exp((bins - (10 + i * 60 / max(n - 1, 1))) * 0.5)),
            "d_max": 80.0, "d_media": 40.0, "d_min": 0.0,
        }
        for i in range(n)
    }


def _tamanho(png: bytes) -> tuple[int, int]:
    from PIL import Image
    return Image.open(io.BytesIO(png)).size


class TestTamanhoDoGrafico(unittest.TestCase):
    """Um caso de cabeça e pescoço traz 30+ estruturas. Com a legenda de coluna
    única e ``bbox_inches="tight"``, era ELA que definia o tamanho do PNG: o
    gráfico saía como uma tira espremida num canto da folha."""

    def test_png_tem_sempre_o_mesmo_tamanho(self):
        base = _tamanho(dvh.plotar_dvh(_curvas(5)))
        for n in (1, 12, 20, 33, 50):
            with self.subTest(estruturas=n):
                self.assertEqual(_tamanho(dvh.plotar_dvh(_curvas(n))), base)

    def test_nomes_compridos_nao_esticam_o_png(self):
        curto = _tamanho(dvh.plotar_dvh(_curvas(30)))
        longo = _tamanho(dvh.plotar_dvh(
            _curvas(30, "Estrutura Muito Comprida Numero")))
        self.assertEqual(curto, longo)

    def test_proporcao_e_a_da_vaga_na_ficha(self):
        larg, alt = _tamanho(dvh.plotar_dvh(_curvas(33)))
        self.assertAlmostEqual(larg / alt, dvh._FIG_L / dvh._FIG_A, places=2)

    def test_o_grafico_fica_com_a_maior_parte_da_figura(self):
        # A faixa da legenda é fixa: sobra para o gráfico mais da metade da
        # largura, com 5 estruturas ou com 50.
        _esq, _base, larg, _alt = dvh._CAIXA_EIXOS
        self.assertGreater(larg, 0.5)


class TestLegendaQueCabe(unittest.TestCase):
    def test_ganha_coluna_quando_a_lista_e_longa(self):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        def colunas(n: int) -> int:
            fig = Figure(figsize=(dvh._FIG_L, dvh._FIG_A), dpi=150)
            FigureCanvasAgg(fig)
            ax = fig.add_axes(dvh._CAIXA_EIXOS)
            for nome, c in _curvas(n).items():
                ax.plot(c["dose"], c["volume"], label=nome)
            esq, base, larg, _alt = dvh._CAIXA_EIXOS
            leg = dvh._legenda_que_cabe(
                fig, ax,
                larg_pol=(1.0 - esq - larg - dvh._FOLGA_LEGENDA * larg) * dvh._FIG_L,
                alt_pol=(1.0 - base * 0.5) * dvh._FIG_A)
            return leg._ncols

        self.assertEqual(colunas(6), 1)      # cabe de sobra numa coluna
        self.assertGreater(colunas(40), 1)   # não cabe: reparte em colunas


if __name__ == "__main__":
    unittest.main()
