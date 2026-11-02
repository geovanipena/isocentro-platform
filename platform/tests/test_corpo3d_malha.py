"""A malha 3D descarta resto de contornagem — e SÓ resto de contornagem.

O BODY do TPS vem salpicado de polígonos que não são o paciente (restos de área
~0, caroços acima dos ombros). Na malha eles viravam tubos e pratos voando. Mas o
limiar não pode ser uma única régua para o exame inteiro: num crânio-pescoço os
ombros mandam na régua e a calota do crânio ia embora com os restos — e
``_voxelizar`` a substituía pela seção vizinha, achatando o topo da cabeça.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.desenho import corpo  # noqa: E402
from isocentro.dicom import corpo3d  # noqa: E402


def _quadrado(lado: float, z: float) -> np.ndarray:
    """Polígono quadrado de ``lado`` mm centrado em (0,0), na altura ``z``."""
    h = lado / 2.0
    return np.array([[-h, -h, z], [h, -h, z], [h, h, z], [-h, h, z]], dtype=float)


def _lados_por_z(cortes: dict) -> dict:
    """{z: lado do maior polígono} — para conferir o que sobrou, em mm."""
    return {z: round(float(np.sqrt(max(corpo3d._area_xy(p) for p in polys))))
            for z, polys in cortes.items()}


def _arestas(quads) -> dict:
    """{aresta não-direcionada: quantas faces a usam}."""
    conta: dict = {}
    for q in quads:
        for a, b in zip(q, list(q[1:]) + [q[0]]):
            k = (min(int(a), int(b)), max(int(a), int(b)))
            conta[k] = conta.get(k, 0) + 1
    return conta


class TestPassoAdaptativo(unittest.TestCase):
    """O passo do voxel segue o TAMANHO do corpo, não uma constante.

    O custo do render acompanha o nº de faces, não o tamanho do paciente: com
    passo fixo, um crânio gasta um terço do orçamento de um tórax e sai com o
    rosto liso — sem nariz, sem órbita. Ele tem de gastar o mesmo e sair fino.
    """

    def _corpo(self, n_fatias, a, b, dz=3.0) -> dict:
        cortes = {}
        for i in range(n_fatias):
            z = i * dz
            t = np.linspace(0, 2 * np.pi, 90, endpoint=False)
            cortes[z] = [np.stack([a * np.cos(t), b * np.sin(t),
                                   np.full(90, z)], axis=1)]
        return cortes

    def test_cranio_ganha_o_passo_fino(self):
        cranio = self._corpo(67, 90, 75)
        self.assertEqual(corpo3d._passo_adaptativo(cranio),
                         corpo3d._PASSO_VOXEL_MIN_MM)

    def test_corpo_inteiro_fica_no_teto_de_sempre(self):
        # Nada pode ficar mais grosso (nem mais lento) do que já era.
        tronco = self._corpo(300, 180, 130)
        self.assertEqual(corpo3d._passo_adaptativo(tronco),
                         corpo3d._PASSO_VOXEL_MM)

    def test_passo_cresce_com_o_corpo_e_respeita_os_limites(self):
        tamanhos = [self._corpo(n, a, b) for n, a, b in
                    ((67, 90, 75), (100, 110, 95), (150, 170, 110),
                     (300, 180, 130))]
        passos = [corpo3d._passo_adaptativo(c) for c in tamanhos]
        self.assertEqual(passos, sorted(passos))
        for p in passos:
            self.assertLessEqual(corpo3d._PASSO_VOXEL_MIN_MM, p)
            self.assertLessEqual(p, corpo3d._PASSO_VOXEL_MM)

    def test_nenhum_render_fica_mais_pesado_que_no_passo_fixo(self):
        # A promessa do orçamento: refinar o que é pequeno NÃO pode custar mais
        # caro que o passo fixo de antes. Onde o teto de 3 mm manda (corpos
        # grandes), o resultado é o mesmo de sempre; onde não manda, o orçamento
        # segura.
        for n, a, b in ((67, 90, 75), (100, 110, 95), (150, 170, 110),
                        (300, 180, 130)):
            cortes = self._corpo(n, a, b)
            adaptativo = corpo3d.malha_do_corpo(
                cortes, corpo3d._passo_adaptativo(cortes))[1]
            fixo = corpo3d.malha_do_corpo(cortes, corpo3d._PASSO_VOXEL_MM)[1]
            with self.subTest(fatias=n):
                self.assertLessEqual(len(adaptativo),
                                     max(corpo3d._ORCAMENTO_FACES, len(fixo)))

    def test_cranio_sai_com_mais_faces_que_no_passo_fixo(self):
        cranio = self._corpo(67, 90, 75)
        fino = corpo3d.malha_do_corpo(cranio,
                                      corpo3d._passo_adaptativo(cranio))[1]
        antigo = corpo3d.malha_do_corpo(cranio, corpo3d._PASSO_VOXEL_MM)[1]
        self.assertGreater(len(fino), 1.8 * len(antigo))


class TestVoxelizar(unittest.TestCase):
    """Preenchimento dos contornos numa grade booleana."""

    PASSO = 5.0

    def _cortes(self, zs, lado=20.0) -> dict:
        return {z: [_quadrado(lado, z)] for z in zs}

    def test_grade_cobre_o_corpo_com_folga(self):
        vol, (x0, y0, z0) = corpo3d._voxelizar(
            self._cortes([0.0, 5.0, 10.0]), self.PASSO)
        self.assertEqual(vol.ndim, 3)
        self.assertTrue(vol.any())
        # A origem fica um passo ANTES do corpo: a superfície precisa de um
        # anel vazio em volta, senão o corpo encosta na borda e a face de fora
        # não é emitida.
        self.assertLessEqual(x0, -10.0 - self.PASSO)
        self.assertLessEqual(y0, -10.0 - self.PASSO)
        self.assertLessEqual(z0, -self.PASSO)
        self.assertFalse(vol[:, 0, :].any(), "corpo encostou na borda em y")
        self.assertFalse(vol[:, :, 0].any(), "corpo encostou na borda em x")

    def test_fatia_sem_contorno_herda_a_mais_proxima(self):
        # O BODY do Monaco pula até 15 mm em z; sem herdar, a malha ficaria com
        # anéis abertos no meio do corpo.
        vol, _ = corpo3d._voxelizar(self._cortes([0.0, 20.0]), self.PASSO)
        cheias = [int(v.sum()) for v in vol]
        self.assertTrue(all(c > 0 for c in cheias), cheias)
        self.assertEqual(len(set(cheias)), 1)   # seção constante: todas iguais

    def test_secao_maior_da_mais_voxels(self):
        p_peq, _ = corpo3d._voxelizar(self._cortes([0.0], 20.0), self.PASSO)
        p_gr, _ = corpo3d._voxelizar(self._cortes([0.0], 60.0), self.PASSO)
        self.assertGreater(int(p_gr.sum()), int(p_peq.sum()))


class TestFacesDaGrade(unittest.TestCase):
    """Extração da superfície: um quad em cada fronteira cheio↔vazio."""

    def test_um_voxel_da_um_cubo(self):
        vol = np.zeros((1, 1, 1), dtype=bool); vol[0, 0, 0] = True
        pts, quads = corpo3d._faces_da_grade(vol, (0.0, 0.0, 0.0), 1.0)
        self.assertEqual(len(quads), 6)         # as 6 faces do cubo
        self.assertEqual(len(pts), 8)           # e só 8 vértices: são partilhados

    def test_bloco_macico_so_tem_a_casca(self):
        # 2×2×2 voxels: 24 quads (6 faces × 4), nada do interior.
        pts, quads = corpo3d._faces_da_grade(np.ones((2, 2, 2), dtype=bool),
                                             (0.0, 0.0, 0.0), 1.0)
        self.assertEqual(len(quads), 24)
        self.assertEqual(len(pts), 26)

    def test_malha_fechada_toda_aresta_em_duas_faces(self):
        # Invariante de superfície fechada. Se cair para 1, há buraco; para 4,
        # há face duplicada — nos dois casos o render mostra o interior.
        _pts, quads = corpo3d._faces_da_grade(np.ones((3, 4, 5), dtype=bool),
                                              (0.0, 0.0, 0.0), 2.0)
        self.assertEqual(set(_arestas(quads).values()), {2})

    def test_volume_vazio_nao_gera_face(self):
        _pts, quads = corpo3d._faces_da_grade(np.zeros((2, 2, 2), dtype=bool),
                                              (0.0, 0.0, 0.0), 1.0)
        self.assertEqual(len(quads), 0)


class TestNormais(unittest.TestCase):
    """As normais têm de apontar para FORA — é o que o culling e a luz usam."""

    def _faces(self, vol, passo=1.0):
        pts, quads = corpo3d._faces_da_grade(vol, (0.0, 0.0, 0.0), passo)
        return pts, quads, [f.tolist() for f in pts[quads]]

    def test_apontam_para_fora_do_solido(self):
        pts, quads, faces = self._faces(np.ones((3, 3, 3), dtype=bool))
        centro = pts.mean(axis=0)
        fora = np.array([np.mean(f, axis=0) for f in np.asarray(pts[quads])]) - centro
        self.assertTrue(np.all(np.einsum("ij,ij->i", corpo._normais(faces), fora) > 0),
                        "há face com a normal virada para dentro")

    def test_sao_unitarias(self):
        _pts, _q, faces = self._faces(np.ones((2, 2, 2), dtype=bool))
        n = np.linalg.norm(corpo._normais(faces), axis=1)
        self.assertTrue(np.allclose(n, 1.0), n)

    def test_culling_descarta_o_lado_de_tras(self):
        # De qualquer ângulo, um sólido convexo mostra metade das faces.
        _pts, _q, faces = self._faces(np.ones((3, 3, 3), dtype=bool))
        for elev, azim in ((10, -30), (0, 0), (60, 120)):
            vis = corpo._faces_visiveis(faces, elev, azim)
            with self.subTest(elev=elev, azim=azim):
                self.assertTrue(0 < int(vis.sum()) < len(faces))


class TestMalhaDoCorpo(unittest.TestCase):
    """Ponta a ponta: contornos → malha suavizada."""

    def _cortes(self, n=6, lado=40.0, dz=3.0) -> dict:
        return {i * dz: [_quadrado(lado, i * dz)] for i in range(n)}

    def test_suavizar_nao_mexe_na_topologia(self):
        cortes = self._cortes()
        vol, origem = corpo3d._voxelizar(cortes, 3.0)
        pts, quads = corpo3d._faces_da_grade(vol, origem, 3.0)
        suave = corpo3d._suavizar_malha(pts, quads)
        self.assertEqual(suave.shape, pts.shape)
        self.assertFalse(np.allclose(suave, pts), "não suavizou nada")

    def test_malha_final_fechada_e_dentro_do_corpo(self):
        pts, quads = corpo3d.malha_do_corpo(self._cortes(), 3.0)
        self.assertGreater(len(quads), 0)
        self.assertEqual(set(_arestas(quads).values()), {2})
        # A malha fica colada no corpo: no máximo o meio-lado (20 mm) mais um
        # voxel. Sem esse teto, um resto de contorno lá longe passaria batido.
        self.assertLess(float(np.abs(pts[:, :2]).max()), 20.0 + 3.0)


class TestSemRestos(unittest.TestCase):
    """Descarte de resto de contornagem — e SÓ de resto de contornagem."""

    DZ = 3.0

    def _cortes(self, lados_por_fatia: list) -> dict:
        """``[[lado, ...], ...]`` — uma lista de lados por fatia, de baixo para cima."""
        return {i * self.DZ: [_quadrado(l, i * self.DZ) for l in lados]
                for i, lados in enumerate(lados_por_fatia)}

    def test_calota_do_cranio_sobrevive_aos_ombros(self):
        # Crânio-pescoço: 10 fatias de ombro (30 cm de lado) e a cabeça afinando
        # até 3 cm. Com a régua única (mediana do exame), as fatias do topo eram
        # jogadas fora — eram menores que 5% dos ombros.
        cabeca = [180, 163, 147, 130, 113, 97, 80, 63, 47, 30]
        cortes = self._cortes([[300]] * 10 + [[l] for l in cabeca])
        limpo = corpo3d._sem_restos(cortes)
        self.assertEqual(len(limpo), len(cortes), _lados_por_z(limpo))
        self.assertIn(min(cortes) + 19 * self.DZ, limpo)   # a fatia mais alta

    def test_caroco_acima_dos_ombros_vai_embora(self):
        # A cauda de caroços do Monaco: 16 cm² soltos acima do tronco. O tubo da
        # malha esticava do tronco até eles.
        cortes = self._cortes([[300]] * 10 + [[40]] * 3)
        limpo = corpo3d._sem_restos(cortes)
        self.assertEqual(sorted(limpo), [i * self.DZ for i in range(10)],
                         _lados_por_z(limpo))

    def test_salpico_ao_lado_do_corpo_vai_embora(self):
        # Resto pequeno numa fatia que TEM corpo: o corpo fica, o resto sai.
        cortes = self._cortes([[300, 20]] * 4)
        limpo = corpo3d._sem_restos(cortes)
        self.assertEqual(sorted(limpo), sorted(cortes))
        for z, polys in limpo.items():
            self.assertEqual(len(polys), 1, z)

    def test_fatia_ruim_no_meio_nao_leva_o_resto_do_corpo(self):
        # A fatia reprovada não interrompe a caminhada em z: o que vem depois dela
        # continua sendo comparado com a última fatia BOA.
        cortes = self._cortes([[300]] * 5 + [[20]] + [[300]] * 4)
        limpo = corpo3d._sem_restos(cortes)
        self.assertEqual(sorted(limpo),
                         [i * self.DZ for i in list(range(5)) + list(range(6, 10))],
                         _lados_por_z(limpo))

    def test_corpo_de_seccao_uniforme_fica_inteiro(self):
        cortes = self._cortes([[300]] * 6)
        self.assertEqual(sorted(corpo3d._sem_restos(cortes)), sorted(cortes))

    def test_sem_cortes_nao_quebra(self):
        self.assertEqual(corpo3d._sem_restos({}), {})


if __name__ == "__main__":
    unittest.main()
