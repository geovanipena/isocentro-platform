"""Margem CTV→PTV medida pela geometria (`isocentro/rt/margem.py`, R-62).

Os casos sintéticos têm margem CONHECIDA, porque foram construídos com ela:
o número esperado não vem de outro programa, vem da expansão que gerou o PTV.
O erro admitido é a precisão que o próprio módulo declara — se ele errar mais
que isso, a precisão impressa ao lado do número estaria mentindo.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

import numpy as np

from isocentro.rt import margem
from isocentro.rt.margem import DIRECOES, medir_margem, pares_por_contencao

RAIZ = Path(__file__).resolve().parent.parent
ACERVO = RAIZ.parents[1] / "dicom-teste"


def _retangulo(x0, x1, y0, y1, z):
    return np.array([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]], float)


def _caixa(x0, x1, y0, y1, z0, z1, zs):
    return [_retangulo(x0, x1, y0, y1, z) for z in zs if z0 <= z <= z1]


def _circulo(cx, cy, r, z, n=128):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.column_stack([cx + r * np.cos(t), cy + r * np.sin(t), np.full(n, z)])


def _esfera(r, zs):
    return [_circulo(0, 0, np.sqrt(r * r - z * z), z) for z in zs if abs(z) < r]


def _cortes(passo, z0=-45.0, z1=45.0):
    return [round(z, 3) for z in np.arange(z0, z1 + 1e-9, passo)]


class MargemConhecida(unittest.TestCase):

    def _confere(self, m, esperado):
        for direcao, valor in esperado.items():
            medido = m.margens_mm[direcao]
            self.assertIsNotNone(medido, direcao)
            self.assertLessEqual(abs(medido - valor), m.precisao_mm[direcao] + 1e-9,
                                 f"{direcao}: medido {medido}, esperado {valor}")

    def test_anisotropica_7_lateral_5_ap_10_si_em_cortes_de_2_5_e_3_mm(self):
        """Protocolo de próstata típico tem margem diferente por eixo. Se o
        módulo trocasse x por y (ou lesse +y como anterior), o 7 lateral
        sairia como AP e o físico conferiria a margem errada contra o
        protocolo — com o número parecendo plausível."""
        for esp in (2.5, 3.0):
            with self.subTest(espessura=esp):
                zs = _cortes(esp)
                ctv = _caixa(-20, 20, -15, 15, -20, 20, zs)
                ptv = _caixa(-27, 27, -20, 20, -30, 30, zs)
                m = medir_margem(ctv, ptv)
                self.assertTrue(m.contida)
                self.assertEqual(m.fracao_fora, 0.0)
                self.assertEqual(m.espessura_corte_mm, esp)
                self._confere(m, {"direita": 7, "esquerda": 7, "anterior": 5,
                                  "posterior": 5, "superior": 10, "inferior": 10})
                self.assertLessEqual(abs(m.minima_3d_mm - 5), m.precisao_mm["3d"])

    def test_precisao_em_si_e_a_espessura_de_corte_e_a_saida_avisa(self):
        """Com corte de 3 mm, um "10 mm" superior pode ser 9 ou 12 na rede.
        Se a saída declarasse a resolução do plano (1 mm) também em SI, a
        pessoa leria uma certeza que o exame não tem."""
        zs = _cortes(3.0)
        m = medir_margem(_caixa(-20, 20, -15, 15, -20, 20, zs),
                         _caixa(-27, 27, -20, 20, -30, 30, zs))
        self.assertEqual(m.precisao_mm["superior"], 3.0)
        self.assertEqual(m.precisao_mm["inferior"], 3.0)
        self.assertEqual(m.precisao_mm["esquerda"], 1.0)
        self.assertTrue(any("espessura de corte" in a for a in m.avisos))

    def test_isotropica_esfera_7_mm(self):
        """Margem isotrópica em ROI redonda: as bordas não caem na grade, e o
        erro de rasterização tem de ficar dentro da precisão declarada em
        todas as seis direções, não só nas que coincidem com a rede."""
        zs = _cortes(2.5)
        m = medir_margem(_esfera(20, zs), _esfera(27, zs))
        self.assertTrue(m.contida)
        self._confere(m, {d: 7 for d in DIRECOES})
        self.assertLessEqual(abs(m.minima_3d_mm - 7), m.precisao_mm["3d"])

    def test_deslocada_parcialmente_fora_da_fracao_e_nao_margem_negativa(self):
        """CTV deslocado 10 mm para a esquerda num PTV de 7 mm: vaza 3 mm.
        Uma margem "−3" na esquerda, ou pior, só o mínimo positivo das outras
        direções, esconderia que parte do alvo clínico está fora do PTV."""
        zs = _cortes(2.5)
        ctv = _caixa(-10, 30, -15, 15, -20, 20, zs)
        ptv = _caixa(-27, 27, -20, 20, -30, 30, zs)
        m = medir_margem(ctv, ptv)
        self.assertFalse(m.contida)
        self.assertAlmostEqual(m.fracao_fora, 3 / 40, delta=1 / 40)
        self.assertIsNone(m.margens_mm["esquerda"])
        self.assertIsNone(m.minima_3d_mm)
        self.assertLessEqual(abs(m.margens_mm["direita"] - 17), 1.0)
        for d, v in m.margens_mm.items():
            if v is not None:
                self.assertGreaterEqual(v, 0, d)
        self.assertIn("esquerda", m.avisos[0])

    def test_varios_poligonos_e_buraco_no_mesmo_corte(self):
        """PTV em anel (buraco no meio, no mesmo corte) com duas ilhas de CTV,
        cada uma a 3 mm do buraco e a 7 mm da borda de fora. Se o buraco fosse
        preenchido como polígono comum, a margem para o lado do buraco sairia
        7 em vez de 3 — e o PTV que poupa o órgão do meio seria medido como
        se não o poupasse, com a margem mais estreita escondida."""
        zs = _cortes(2.5)
        ptv = ([_retangulo(-40, 40, -40, 40, z) for z in zs if -20 <= z <= 20]
               + [_retangulo(-10, 10, -38, 38, z)[::-1]
                  for z in zs if -20 <= z <= 20])
        ctv = (_caixa(-33, -13, -35, 35, -10, 10, zs)
               + _caixa(13, 33, -35, 35, -10, 10, zs))
        m = medir_margem(ctv, ptv)
        self.assertTrue(m.contida)
        self._confere(m, {"direita": 3, "esquerda": 3, "anterior": 5,
                          "posterior": 5, "superior": 10, "inferior": 10})

    def test_ctv_atravessando_o_buraco_do_ptv_avisa_sem_direcao_vazada(self):
        """CTV inteiro cruzando o buraco do anel: a borda está dentro do PTV em
        toda direção, mas o meio não. O aviso tinha saído "sem margem em: " com
        a lista vazia — a pessoa não saberia onde está o vazamento."""
        zs = _cortes(2.5)
        ptv = ([_retangulo(-40, 40, -40, 40, z) for z in zs if -20 <= z <= 20]
               # Cavidade fechada: o buraco só nos cortes do meio, senão
               # seria um túnel e a borda SI do CTV cairia nele.
               + [_retangulo(-10, 10, -10, 10, z) for z in zs if -5 <= z <= 5])
        ctv = _caixa(-30, 30, -30, 30, -10, 10, zs)
        m = medir_margem(ctv, ptv)
        self.assertFalse(m.contida)
        self.assertTrue(all(v is not None for v in m.margens_mm.values()))
        self.assertIn("buraco", m.avisos[0])

    def test_espacamento_misto_recusa_ou_avisa_em_vez_de_calar(self):
        """TC com 1,25 mm num trecho e 2,5 no outro. Um corte fora da rede
        cairia no plano de outro e o par-ímpar apagaria os dois (margem SI
        zero, volume pela metade, sem erro na tela): recusa. O trecho de 2,5
        sozinho deixa planos vazios entre cortes — não dá para saber se é a TC
        ou a ROI que pula, e então o número sai com o aviso ao lado."""
        mista = ([round(z, 3) for z in np.arange(-40, 0, 2.5)]
                 + [round(z, 3) for z in np.arange(0, 40.01, 1.25)])
        with self.assertRaises(ValueError):
            zs = mista + [1.9]
            medir_margem(_caixa(-20, 20, -15, 15, -20, 20, zs),
                         _caixa(-27, 27, -20, 20, -30, 30, zs))
        m = medir_margem(_caixa(-20, 20, -15, 15, -20, 20, mista),
                         _caixa(-27, 27, -20, 20, -30, 30, mista))
        self.assertTrue(any("plano(s) sem contorno" in a for a in m.avisos))

    def test_espessura_informada_que_nao_bate_com_os_cortes_e_recusada(self):
        """A `SliceThickness` da TC (3 mm) não é o espaçamento dos contornos
        (2,5): com ela, z=5 e z=7,5 cairiam no mesmo plano e se apagariam."""
        zs = _cortes(2.5)
        with self.assertRaises(ValueError):
            medir_margem(_caixa(-20, 20, -15, 15, -20, 20, zs),
                         _caixa(-27, 27, -20, 20, -30, 30, zs), espessura_mm=3.0)

    def test_plano_vazio_no_meio_e_avisado(self):
        """Plano sem contorno de nenhuma das duas no meio da extensão: se a TC
        mudou de espaçamento ali, a margem SI sai errada. O número continua,
        mas o aviso diz onde olhar."""
        zs = [z for z in _cortes(2.5) if z != 0.0]
        m = medir_margem(_caixa(-20, 20, -15, 15, -20, 20, zs),
                         _caixa(-27, 27, -20, 20, -30, 30, zs))
        self.assertTrue(any("plano(s) sem contorno" in a for a in m.avisos))

    def test_plano_unico_pede_espessura_em_vez_de_inventar(self):
        """Com um corte só não há espaçamento de onde tirar a espessura. Um
        "1 mm" padrão faria a margem SI parecer medida — campo sem fonte nasce
        vazio, e aqui a conta não sai."""
        ctv = [_retangulo(-5, 5, -5, 5, 0.0)]
        ptv = [_retangulo(-10, 10, -10, 10, 0.0)]
        with self.assertRaises(ValueError):
            medir_margem(ctv, ptv)
        m = medir_margem(ctv, ptv, espessura_mm=3.0)
        self.assertEqual(m.margens_mm["esquerda"], 5.0)
        # E, com a espessura dada, SI e 3D continuam sem número: um plano só
        # não tem extensão em z, e "0 mm" diria que o CTV encosta no PTV.
        self.assertIsNone(m.margens_mm["superior"])
        self.assertIsNone(m.margens_mm["inferior"])
        self.assertIsNone(m.minima_3d_mm)
        self.assertIn("plano só", m.avisos[0])


class ParesPorContencao(unittest.TestCase):

    def test_par_vem_da_geometria_mesmo_com_os_nomes_trocados(self):
        """Nomes digitados à mão mentem: aqui a ROI chamada "PTV" é a pequena.
        Casar por nome mediria a margem ao contrário; a contenção acha o par
        certo e só usa o nome para mostrar."""
        zs = _cortes(2.5)
        rois = {
            "PTV": _caixa(-20, 20, -15, 15, -20, 20, zs),
            "CTV": _caixa(-27, 27, -20, 20, -30, 30, zs),
            "Reto": _caixa(15, 45, -10, 10, -10, 10, zs),
            "BODY": _caixa(-100, 100, -80, 80, -45, 45, zs),
        }
        pares = [(p.interna, p.externa) for p in pares_por_contencao(rois)]
        self.assertIn(("PTV", "CTV"), pares)
        self.assertNotIn(("CTV", "PTV"), pares)
        self.assertNotIn(("Reto", "CTV"), pares)
        self.assertIn(("Reto", "BODY"), pares)
        # A externa mais justa vem antes: o CTV (maior) antes do BODY.
        do_ptv = [e for i, e in pares if i == "PTV"]
        self.assertEqual(do_ptv, ["CTV", "BODY"])

    def test_copia_identica_nao_vira_par(self):
        """PTV e "PTV_eval" idênticos se contêm mutuamente; como par, dariam
        margem zero e encheriam a lista de falsos candidatos."""
        zs = _cortes(2.5)
        caixa = _caixa(-20, 20, -15, 15, -20, 20, zs)
        self.assertEqual(pares_por_contencao({"A": caixa, "B": list(caixa)}), [])


class FronteiraDaCamadaRt(unittest.TestCase):

    def test_rt_so_importa_numpy_e_a_biblioteca_padrao(self):
        """AD-38: o `rt` é importado por todo módulo. Um `import PIL` ou um
        `from isocentro.dicom import dvh` em QUALQUER arquivo da camada
        arrastaria desenho ou leitura de arquivo para dentro dela, e a junção
        com `dicom/` é da R-58."""
        permitidos = {"__future__", "math", "dataclasses", "types", "typing",
                      "numpy"}
        arquivos = sorted(Path(margem.__file__).parent.glob("*.py"))
        self.assertGreaterEqual(len(arquivos), 2)
        for arquivo in arquivos:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    nomes = [a.name for a in no.names]
                elif isinstance(no, ast.ImportFrom):
                    nomes = ["." if no.level else (no.module or "")]
                else:
                    continue
                for nome in nomes:
                    raiz = nome.split(".")[0]
                    self.assertTrue(raiz in permitidos or nome == "."
                                    or nome.startswith("isocentro.rt"),
                                    f"import proibido em rt/{arquivo.name}: {nome}")


def _ler_rois(rs_caminho):
    import pydicom
    ds = pydicom.dcmread(rs_caminho)
    nomes = {int(r.ROINumber): str(r.ROIName) for r in ds.StructureSetROISequence}
    rois = {}
    for rc in ds.ROIContourSequence:
        contornos = [np.array(c.ContourData, float).reshape(-1, 3)
                     for c in getattr(rc, "ContourSequence", [])]
        if contornos:
            rois[nomes[int(rc.ReferencedROINumber)]] = contornos
    return rois


def _rois_do_caso(caso):
    return _ler_rois(sorted((ACERVO / caso).glob("RTSTRUCT*.dcm"))[0])


@unittest.skipUnless((ACERVO / "TC5").is_dir() and (ACERVO / "TC10").is_dir(),
                     "sem o acervo pseudonimizado dicom-teste/ (CI ou outra estação)")
class CasoReal(unittest.TestCase):
    """Casos do acervo pseudonimizado que têm ROIs `CTV` e `PTV`.

    Só coerência: nenhum número aqui foi conferido no TPS, e fixar um seria
    transformar o palpite de hoje em referência."""

    def test_tc5_ctv_contido_achado_pela_contencao_e_margem_coerente(self):
        """O par tem de sair da geometria, e a margem medida não pode ser
        negativa nem a mínima 3D passar da menor direcional (seria a mesma
        distância medida de dois jeitos dando números incompatíveis)."""
        rois = _rois_do_caso("TC5")
        pares = [(p.interna, p.externa) for p in pares_por_contencao(rois)]
        self.assertIn(("CTV", "PTV"), pares)
        m = medir_margem(rois["CTV"], rois["PTV"])
        self.assertTrue(m.contida, m.avisos)
        for d in DIRECOES:
            self.assertGreaterEqual(m.margens_mm[d], 0, d)
        self.assertGreaterEqual(m.minima_3d_mm, 0)
        self.assertLessEqual(m.minima_3d_mm, min(m.margens_mm.values()))

    def test_tc10_vazamento_real_vira_fracao_e_nao_margem_negativa(self):
        """No TC10 uma faixa fina do CTV fica fora do PTV em vários cortes
        (medido em 22/10/2026, em 1 e 0,5 mm de rede). Seja o que for no TPS,
        a saída não pode trazer número negativo nem mínima 3D: traz a fração
        e o aviso. E a contenção ainda acha o par, com o limiar de 95%."""
        rois = _rois_do_caso("TC10")
        pares = [(p.interna, p.externa) for p in pares_por_contencao(rois)]
        self.assertIn(("CTV", "PTV"), pares)
        m = medir_margem(rois["CTV"], rois["PTV"])
        for d in DIRECOES:
            v = m.margens_mm[d]
            self.assertTrue(v is None or v >= 0, d)
        self.assertFalse(m.contida)
        self.assertGreater(m.fracao_fora, 0)
        self.assertIsNone(m.minima_3d_mm)
        self.assertIn("fica fora", m.avisos[0])


if __name__ == "__main__":
    unittest.main()
