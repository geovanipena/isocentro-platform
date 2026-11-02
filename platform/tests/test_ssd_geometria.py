"""Testes da geometria do SSD com fantomas sintéticos de resposta analítica.

Por que sintético: a ficha do TPS não é referência confiável (a do TC8 está
errada), então validar contra ela mede o TPS, não o código. Um cilindro de raio
conhecido tem SSD fechado — SSD = SAD − raio quando o raio parte do eixo — e é
a única âncora independente disponível para as funções puras de geometria.

O que estes testes NÃO cobrem: se o contorno EXTERNAL é a superfície certa (isso
é decisão clínica, validada em 8 pacientes) — só se a matemática que opera sobre
ele está correta.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dicom import dicom_rt  # noqa: E402

SAD = dicom_rt._SAD_MM   # 1000 mm


def circulo(raio: float, cx: float = 0.0, cy: float = 0.0, n: int = 720) -> np.ndarray:
    """Polígono (n,2) aproximando um círculo. n alto → erro de corda desprezível."""
    t = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    return np.column_stack([cx + raio * np.cos(t), cy + raio * np.sin(t)])


class TestGantryDirXY(unittest.TestCase):
    """A tabela IEC do docstring de _gantry_dir_xy, verificada ângulo a ângulo."""

    TABELA = {
        # pos: {gantry: (dx, dy) esperado — DO isocentro PARA a fonte}
        "HFS": {0: (0, -1), 90: (+1, 0), 180: (0, +1), 270: (-1, 0)},
        "FFS": {0: (0, -1), 90: (-1, 0), 180: (0, +1), 270: (+1, 0)},
        "HFP": {0: (0, +1), 90: (-1, 0), 180: (0, -1), 270: (+1, 0)},
        "FFP": {0: (0, +1), 90: (+1, 0), 180: (0, -1), 270: (-1, 0)},
    }

    def test_tabela_iec(self):
        for pos, angulos in self.TABELA.items():
            for g, esperado in angulos.items():
                with self.subTest(pos=pos, gantry=g):
                    dx, dy = dicom_rt._gantry_dir_xy(g, pos)
                    self.assertAlmostEqual(dx, esperado[0], places=9)
                    self.assertAlmostEqual(dy, esperado[1], places=9)

    def test_vetor_sempre_unitario(self):
        for pos in self.TABELA:
            for g in range(0, 360, 15):
                with self.subTest(pos=pos, gantry=g):
                    dx, dy = dicom_rt._gantry_dir_xy(g, pos)
                    self.assertAlmostEqual(math.hypot(dx, dy), 1.0, places=9)

    def test_angulo_normaliza_alem_de_360(self):
        self.assertEqual(dicom_rt._gantry_dir_xy(90, "HFS"),
                         dicom_rt._gantry_dir_xy(450, "HFS"))

    def test_posicao_desconhecida_cai_para_hfs_avisando(self):
        with self.assertLogs(dicom_rt._LOG, level="WARNING"):
            d = dicom_rt._gantry_dir_xy(90, "XXX")
        self.assertEqual(d, dicom_rt._gantry_dir_xy(90, "HFS"))


class TestTP0Coords(unittest.TestCase):
    """Sinais do deslocamento de mesa (IEC 61217) → coordenadas DICOM."""

    ISO = [10.0, 20.0, 30.0]

    def test_sem_deslocamento_tp0_eh_o_iso(self):
        for pos in ("HFS", "FFS", "HFP", "FFP"):
            with self.subTest(pos=pos):
                self.assertEqual(dicom_rt._tp0_coords(self.ISO, 0, 0, 0, pos),
                                 tuple(self.ISO))

    def test_none_equivale_a_zero(self):
        self.assertEqual(dicom_rt._tp0_coords(self.ISO, None, None, None, "HFS"),
                         tuple(self.ISO))

    def test_sinais_por_decubito(self):
        # 1 cm em cada eixo → 10 mm. Sinais derivados do IEC 61217:
        #   lat : +1 (HFS, FFP), −1 (FFS, HFP)          → X
        #   vert: −1 supino (HFS, FFS), +1 prono (HFP, FFP) → Y
        #   long: +1 cabeça-primeiro (HFS, HFP), −1 pés-primeiro (FFS, FFP) → Z
        esperado = {
            "HFS": (10 + 10, 20 - 10, 30 + 10),
            "FFS": (10 - 10, 20 - 10, 30 - 10),
            "HFP": (10 - 10, 20 + 10, 30 + 10),
            "FFP": (10 + 10, 20 + 10, 30 - 10),
        }
        for pos, alvo in esperado.items():
            with self.subTest(pos=pos):
                self.assertEqual(
                    dicom_rt._tp0_coords(self.ISO, 1.0, 1.0, 1.0, pos), alvo)

    def test_cm_para_mm(self):
        x, _, _ = dicom_rt._tp0_coords([0, 0, 0], 2.5, 0, 0, "HFS")
        self.assertAlmostEqual(x, 25.0)


class TestRayDistExterna(unittest.TestCase):
    """Raycast 2D: distância até a pele MAIS EXTERNA na direção da fonte."""

    def test_do_centro_a_distancia_eh_o_raio(self):
        polys = [circulo(150.0)]
        for ang in range(0, 360, 30):
            dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            with self.subTest(ang=ang):
                d = dicom_rt._ray_dist_externa(polys, 0.0, 0.0, dx, dy)
                self.assertAlmostEqual(d, 150.0, places=2)

    def test_origem_deslocada(self):
        # Origem 40 mm à direita do centro, raio para +x: pele a R − 40.
        d = dicom_rt._ray_dist_externa([circulo(150.0)], 40.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(d, 110.0, places=2)

    def test_origem_fora_pega_a_saida_e_nao_a_entrada(self):
        # De x=−300 rumo a +x, o corpo é cruzado duas vezes (−150 e +150).
        # A fonte enxerga primeiro a pele mais distante → t = 450, não 150.
        d = dicom_rt._ray_dist_externa([circulo(150.0)], -300.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(d, 450.0, places=2)

    def test_sem_intersecao_retorna_none(self):
        # Raio apontando para longe do corpo, partindo de fora.
        d = dicom_rt._ray_dist_externa([circulo(150.0)], 400.0, 0.0, 1.0, 0.0)
        self.assertIsNone(d)

    def test_braco_separado_do_tronco_vence(self):
        # Tronco R=150 na origem; braço R=30 centrado em x=250 (gap de ar).
        # Raio lateral +x: a fonte vê a pele do braço (280), não a do tronco.
        polys = [circulo(150.0), circulo(30.0, cx=250.0)]
        d = dicom_rt._ray_dist_externa(polys, 0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(d, 280.0, places=2)

    def test_poligono_degenerado_nao_quebra(self):
        self.assertIsNone(
            dicom_rt._ray_dist_externa([np.zeros((3, 2))], 0.0, 0.0, 1.0, 0.0))


class TestSSDViaRS(unittest.TestCase):
    """SSD sobre um cilindro: resposta fechada SSD = SAD − raio."""

    def _cilindro(self, raio=150.0, zs=(-10.0, 0.0, 10.0)):
        return {z: [circulo(raio)] for z in zs}

    def test_ssd_no_eixo_do_cilindro(self):
        contornos = self._cilindro(raio=150.0)
        for ang in (0.0, 90.0, 180.0, 270.0):
            dx, dy = dicom_rt._gantry_dir_xy(ang, "HFS")
            with self.subTest(gantry=ang):
                ssd = dicom_rt._ssd_via_rs(contornos, 0.0, 0.0, 0.0, 0.0, 0.0, dx, dy)
                self.assertAlmostEqual(ssd, (SAD - 150.0) / 10.0, places=1)  # 85.0 cm

    def test_ssd_com_iso_fora_do_eixo(self):
        # ISO 40 mm à direita: para +x a pele fica a 110 mm → SSD = 89.0 cm.
        contornos = self._cilindro(raio=150.0)
        ssd = dicom_rt._ssd_via_rs(contornos, 40.0, 0.0, 40.0, 0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(ssd, (SAD - 110.0) / 10.0, places=1)

    def test_z_exato_usa_a_fatia_e_nao_interpola(self):
        contornos = {0.0: [circulo(150.0)], 10.0: [circulo(100.0)]}
        ssd = dicom_rt._ssd_via_rs(contornos, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(ssd, (SAD - 150.0) / 10.0, places=1)

    def test_z_intermediario_interpola_linearmente(self):
        # Cone entre z=0 (R=150) e z=10 (R=100); em z=5 o raio real é 125.
        contornos = {0.0: [circulo(150.0)], 10.0: [circulo(100.0)]}
        ssd = dicom_rt._ssd_via_rs(contornos, 0.0, 0.0, 0.0, 0.0, 5.0, 1.0, 0.0)
        self.assertAlmostEqual(ssd, (SAD - 125.0) / 10.0, places=1)  # 87.5 cm

    def test_z_logo_apos_a_ultima_fatia_usa_a_fatia_mais_proxima(self):
        # Dentro de uma espessura de corte: a pele da última fatia ainda vale.
        contornos = {0.0: [circulo(150.0)], 10.0: [circulo(100.0)]}
        ssd = dicom_rt._ssd_via_rs(contornos, 0.0, 0.0, 0.0, 0.0, 18.0, 1.0, 0.0)
        self.assertAlmostEqual(ssd, (SAD - 100.0) / 10.0, places=1)

    def test_z_muito_fora_do_intervalo_nao_inventa_ssd(self):
        # Além do corpo contornado não há pele: melhor nada que um número
        # plausível e errado (os limites de sanidade não pegariam).
        contornos = {0.0: [circulo(150.0)], 10.0: [circulo(100.0)]}
        with self.assertLogs(dicom_rt._LOG, level="WARNING"):
            ssd = dicom_rt._ssd_via_rs(contornos, 0.0, 0.0, 0.0, 0.0, 500.0, 1.0, 0.0)
        self.assertIsNone(ssd)


    def test_contornos_vazios(self):
        self.assertIsNone(
            dicom_rt._ssd_via_rs({}, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0))

    def test_sem_intersecao_retorna_none(self):
        contornos = self._cilindro(raio=150.0)
        ssd = dicom_rt._ssd_via_rs(contornos, 400.0, 0.0, 400.0, 0.0, 0.0, 1.0, 0.0)
        self.assertIsNone(ssd)

    def test_fora_dos_limites_de_sanidade_retorna_none(self):
        # Corpo absurdamente largo → SSD abaixo de _SSD_MIN_CM (50 cm).
        contornos = {0.0: [circulo(600.0)]}
        ssd = dicom_rt._ssd_via_rs(contornos, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        self.assertIsNone(ssd)   # SSD seria 40 cm


class TestToleranciaZ(unittest.TestCase):
    """A tolerância é uma espessura de corte, medida do próprio RS."""

    def test_usa_o_passo_mediano_das_fatias(self):
        self.assertAlmostEqual(dicom_rt._tolerancia_z([0.0, 2.0, 4.0, 6.0]), 2.0)
        self.assertAlmostEqual(dicom_rt._tolerancia_z([0.0, 5.0, 10.0]), 5.0)

    def test_passo_irregular_usa_a_mediana_e_nao_o_maior(self):
        # Um buraco no contorno não pode afrouxar a tolerância.
        self.assertAlmostEqual(
            dicom_rt._tolerancia_z([0.0, 2.0, 4.0, 40.0, 42.0]), 2.0)

    def test_fatia_unica_cai_no_padrao(self):
        self.assertAlmostEqual(dicom_rt._tolerancia_z([7.0]),
                               dicom_rt._ESPESSURA_PADRAO_MM)

    def test_fronteira_da_tolerancia(self):
        contornos = {0.0: [circulo(150.0)], 10.0: [circulo(100.0)]}   # passo 10
        # 9 mm além da última fatia: dentro da espessura → calcula.
        self.assertIsNotNone(
            dicom_rt._ssd_via_rs(contornos, 0.0, 0.0, 0.0, 0.0, 19.0, 1.0, 0.0))
        # 11 mm além: fora → None.
        self.assertIsNone(
            dicom_rt._ssd_via_rs(contornos, 0.0, 0.0, 0.0, 0.0, 21.0, 1.0, 0.0))


class TestRegraEntreFatias(unittest.TestCase):
    """Entre duas fatias: interpola a mesma superfície, mas não mistura estruturas.

    A regra é a do feixe: ele cruza primeiro o que estiver mais externo. Uma
    superfície só, mudando de tamanho em z, é interpolada (o corpo realmente
    afina entre as fatias). Uma estrutura que começa ou termina — um braço, uma
    perna — não: ali vale a pele mais externa, porque interpolar devolveria um
    ponto no vão de ar entre o braço e o tronco, onde não há pele nenhuma.

    O sinal de que uma estrutura apareceu/sumiu é o nº de polígonos que o raio
    cruza mudar entre as fatias.
    """

    def _pele(self, ssd_cm: float) -> float:
        """Inverte o SSD de volta para a distância à pele, em mm."""
        return SAD - ssd_cm * 10.0

    # ── estrutura que some entre as fatias → mais externo, sem interpolar ──

    def _cenario_braco(self):
        # Tronco R=150 na origem; braço R=30 em x=250, presente só em z=0.
        # Na direção +x: tronco a 150; braço entra em 220 e sai em 280.
        return {0.0: [circulo(150.0), circulo(30.0, cx=250.0)],
                10.0: [circulo(150.0)]}

    def test_premissas_do_cenario_braco(self):
        c = self._cenario_braco()
        d_lo, n_lo = dicom_rt._cruzamentos_externos(c[0.0], 0, 0, 1, 0)
        d_hi, n_hi = dicom_rt._cruzamentos_externos(c[10.0], 0, 0, 1, 0)
        self.assertAlmostEqual(d_lo, 280.0, places=2)   # pele do braço
        self.assertAlmostEqual(d_hi, 150.0, places=2)   # pele do tronco
        self.assertEqual((n_lo, n_hi), (2, 1))          # o braço some

    def test_braco_que_some_usa_a_pele_mais_externa(self):
        ssd = dicom_rt._ssd_via_rs(self._cenario_braco(), 0, 0, 0, 0, 5.0, 1, 0)
        self.assertAlmostEqual(self._pele(ssd), 280.0, places=1)

    def test_braco_nao_produz_pele_no_vao_de_ar(self):
        """Regressão do defeito antigo: interpolar dava 215 mm, que é ar."""
        ssd = dicom_rt._ssd_via_rs(self._cenario_braco(), 0, 0, 0, 0, 5.0, 1, 0)
        dist = self._pele(ssd)
        reais = (150.0, 220.0, 280.0)   # únicas superfícies na direção +x
        self.assertTrue(
            any(abs(dist - r) < 1.0 for r in reais),
            f"pele em {dist:.1f} mm não existe em nenhuma fatia (reais: {reais})",
        )
        self.assertFalse(150.0 < dist < 220.0, "pele caiu no vão de ar")

    def test_vale_para_qualquer_fracao_de_z(self):
        # A regra não depende de onde rz cai entre as fatias.
        for rz in (0.5, 2.0, 5.0, 8.0, 9.5):
            with self.subTest(rz=rz):
                ssd = dicom_rt._ssd_via_rs(self._cenario_braco(), 0, 0, 0, 0, rz, 1, 0)
                self.assertAlmostEqual(self._pele(ssd), 280.0, places=1)

    def test_braco_que_aparece_tambem_vale(self):
        # Mesma coisa invertida: o braço existe na fatia de cima.
        contornos = {0.0: [circulo(150.0)],
                     10.0: [circulo(150.0), circulo(30.0, cx=250.0)]}
        ssd = dicom_rt._ssd_via_rs(contornos, 0, 0, 0, 0, 5.0, 1, 0)
        self.assertAlmostEqual(self._pele(ssd), 280.0, places=1)

    def test_corpo_que_termina_entre_as_fatias(self):
        # Só a fatia de baixo cruza (o blob de cima está fora da linha do raio):
        # vale a pele que existe, não o vazio.
        contornos = {0.0: [circulo(150.0)], 10.0: [circulo(20.0, cx=0.0, cy=500.0)]}
        d_hi, n_hi = dicom_rt._cruzamentos_externos(contornos[10.0], 0, 0, 1, 0)
        self.assertEqual((d_hi, n_hi), (None, 0))   # premissa: o raio não cruza
        ssd = dicom_rt._ssd_via_rs(contornos, 0, 0, 0, 0, 5.0, 1, 0)
        self.assertAlmostEqual(self._pele(ssd), 150.0, places=1)

    # ── mesma superfície mudando de tamanho → interpola ──

    def test_cone_continua_interpolando(self):
        # Um polígono nas duas fatias: o corpo afina de verdade entre elas.
        contornos = {0.0: [circulo(150.0)], 10.0: [circulo(100.0)]}
        ssd = dicom_rt._ssd_via_rs(contornos, 0, 0, 0, 0, 5.0, 1, 0)
        self.assertAlmostEqual(self._pele(ssd), 125.0, places=1)

    def test_braco_presente_nas_duas_fatias_interpola(self):
        # O braço não some: 2 polígonos dos dois lados, e ele afina de 280 → 260.
        contornos = {0.0: [circulo(150.0), circulo(30.0, cx=250.0)],
                     10.0: [circulo(150.0), circulo(30.0, cx=230.0)]}
        ssd = dicom_rt._ssd_via_rs(contornos, 0, 0, 0, 0, 5.0, 1, 0)
        self.assertAlmostEqual(self._pele(ssd), 270.0, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
