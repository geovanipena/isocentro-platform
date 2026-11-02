"""O cache do render 3D do corpo: o mesmo PNG, sem desenhar de novo.

O que quebrou no uso: o clique na Documentação PRONTA de um caso de quatro
planos deixou a janela "Não respondendo" por 87 s (07/10/2026) — cinco renders
de 14 a 22 s cada, na thread da tela, e de novo a cada Visualizar/Impressão. O
cache só vale se NUNCA devolver o corpo de outro contorno, nem um desenho feito
com outra iluminação: é isso que estes testes travam.
"""
from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np

from isocentro.desenho import corpo
from isocentro.dicom import corpo3d


def _cortes(raio: float = 100.0) -> dict:
    ang = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    return {float(z): [np.column_stack([raio * np.cos(ang), raio * np.sin(ang),
                                        np.full_like(ang, z)])]
            for z in (0.0, 3.0, 6.0, 9.0)}


class TestCacheDoRender(unittest.TestCase):

    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self._env = os.environ.get(corpo.ENV_CACHE)
        os.environ[corpo.ENV_CACHE] = self._pasta.name
        self._desenhar = corpo._desenhar
        self.chamadas = []

        def falso(cortes, elev, azim, passo):
            self.chamadas.append((len(cortes), elev, azim))
            return f"PNG-{len(self.chamadas)}".encode()

        corpo._desenhar = falso
        corpo._memoria.clear()
        corpo._assinatura.clear()

    def tearDown(self):
        corpo._desenhar = self._desenhar
        corpo._memoria.clear()
        corpo._assinatura.clear()
        if self._env is None:
            os.environ.pop(corpo.ENV_CACHE, None)
        else:
            os.environ[corpo.ENV_CACHE] = self._env
        self._pasta.cleanup()

    def test_mesmo_contorno_nao_desenha_de_novo(self):
        a = corpo._com_cache(_cortes(), 10, -30, None)
        b = corpo._com_cache(_cortes(), 10, -30, None)
        self.assertEqual(a, b)
        self.assertEqual(len(self.chamadas), 1)

    def test_outro_contorno_desenha(self):
        corpo._com_cache(_cortes(100.0), 10, -30, None)
        corpo._com_cache(_cortes(101.0), 10, -30, None)
        self.assertEqual(len(self.chamadas), 2)

    def test_angulo_da_ficha_sobrevive_ao_processo_pelo_disco(self):
        primeiro = corpo._com_cache(_cortes(), 10, -30, None)
        corpo._memoria.clear()           # "outro dia, app reaberto"
        segundo = corpo._com_cache(_cortes(), 10, -30, None)
        self.assertEqual(primeiro, segundo)
        self.assertEqual(len(self.chamadas), 1)

    def test_angulo_girado_nao_vai_para_o_disco(self):
        corpo._com_cache(_cortes(), 25, 40, None)
        self.assertEqual(list(os.scandir(self._pasta.name)), [])

    def test_mudar_a_iluminacao_invalida_o_cache(self):
        corpo._com_cache(_cortes(), 10, -30, None)
        base = corpo._BASE
        try:
            corpo._BASE = (0.5, 0.5, 0.5)
            corpo._assinatura.clear()
            corpo._memoria.clear()
            corpo._com_cache(_cortes(), 10, -30, None)
        finally:
            corpo._BASE = base
        self.assertEqual(len(self.chamadas), 2)

    def test_mudar_a_malha_invalida_o_cache(self):
        """Desde a R-58 a malha mora em ``dicom/corpo3d`` e o desenho aqui. Com a
        assinatura cobrindo só este módulo, um passo de voxel novo continuava
        achando no disco o PNG da malha antiga — e era ele que ia para o papel."""
        corpo._com_cache(_cortes(), 10, -30, None)
        passo = corpo3d._PASSO_VOXEL_MM
        try:
            corpo3d._PASSO_VOXEL_MM = passo + 1.0
            corpo._assinatura.clear()
            corpo._memoria.clear()
            corpo._com_cache(_cortes(), 10, -30, None)
        finally:
            corpo3d._PASSO_VOXEL_MM = passo
        self.assertEqual(len(self.chamadas), 2)

    def test_assinatura_e_estavel_entre_calculos(self):
        """Sem isto o cache de disco nunca bateria entre execuções: o ``repr``
        de função interna traz endereço de memória."""
        a = corpo._assinatura_do_codigo()
        corpo._assinatura.clear()
        self.assertEqual(a, corpo._assinatura_do_codigo())


if __name__ == "__main__":
    unittest.main()
