"""Ficha com mais campos do que a pág. 2 comporta.

A tabela de campos tem ``N_CAMPOS`` (21) colunas. Somando os campos de todos os
planos e passando disso, a ficha sai em blocos "pág. 2 + pág. 3": cada pág. 2
leva os planos INTEIROS que couberem e a sua pág. 3 traz o mapa só desses
planos; os que sobraram vão para o bloco seguinte.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isocentro.papel import ficha_pdf as fp  # noqa: E402


def _plano(rotulo: str, n_campos: int, nfr: int = 10) -> dict:
    return {"dados": {"pac_nome": "X", "proto_imagem": "MV",
                      "proto_frequencia": "Diária"},
            "store": {"RP": {"rotulo_plano": rotulo, "num_fracoes": nfr,
                             "dose_fracao": 2.0, "n_isocentros": 1,
                             "feixes": [{"gantry": 10 * i, "um": 100}
                                        for i in range(n_campos)]}},
            "recursos": {}}


class TestLayoutLateral(unittest.TestCase):
    """Com poucos campos, Observações e Checklist vão para a faixa livre AO LADO
    da tabela de campos, e o mapa de frações ocupa a metade de baixo da folha."""

    def _ficha(self, n_campos: int, nfr: int) -> str:
        from pypdf import PdfReader
        d = {"pac_nome": "X", "pac_registro": "1", "rx_fracoes": nfr,
             "proto_imagem": "MV", "proto_frequencia": "Diária"}
        rp = {"num_fracoes": nfr, "dose_fracao": 2.0, "n_isocentros": 1,
              "rotulo_plano": "P",
              "feixes": [{"gantry": 0, "um": 100} for _ in range(n_campos)]}
        r = PdfReader(io.BytesIO(fp.gerar_ficha(d, {"RP": rp}, {})))
        self.assertEqual(len(r.pages), 1, "mapa não embutiu")
        return r.pages[0].extract_text().replace(" ", "")

    def test_uma_folha_com_tudo(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest("pypdf ausente")
        txt = self._ficha(4, 15)
        for esperado in ("Mapadefrações", "Observaçõesgeraisdotratamento",
                         "Impressoem"):
            self.assertIn(esperado, txt)
        self.assertNotIn("Checklist", txt)   # mudou-se para a contracapa

    def test_largura_da_tabela_deixa_faixa_para_o_resto(self):
        # É o que torna o layout possível: a coluna tem a largura da folha cheia,
        # então poucos campos ocupam pouco mais de um quarto da página.
        from reportlab.lib.pagesizes import A4, landscape
        W, _H = landscape(A4)
        t = fp.Tela(None, W, _H)
        larg = fp._largura_campos(t, fp._MAX_CAMPOS_LADO)
        self.assertLess(larg, 0.35 * W)
        self.assertGreater(fp._largura_campos(t, fp.N_CAMPOS), 0.9 * (W - 28))

    def test_decide_por_campos_e_por_caber(self):
        H = 595.0
        y = 320.0                       # fim típico da tabela de campos
        self.assertTrue(fp._cabe_mapa_ao_lado(y, 15, H))
        self.assertFalse(fp._cabe_mapa_ao_lado(y, 30, H))


class TestGruposPorCampos(unittest.TestCase):

    def test_cabendo_tudo_sai_um_grupo_so(self):
        planos = [_plano("1 A", 8), _plano("2 B", 8)]      # 16 ≤ 21
        self.assertEqual(fp._grupos_por_campos(planos), [[0, 1]])

    def test_limite_exato_nao_divide(self):
        planos = [_plano("1 A", 12), _plano("2 B", 9)]     # 21 = N_CAMPOS
        self.assertEqual(fp._grupos_por_campos(planos), [[0, 1]])

    def test_enche_a_pagina_antes_de_abrir_outra(self):
        # 8+8 = 16 cabem; com o 3º seriam 24 → ele abre a página seguinte, e o
        # 4º ainda cabe junto dele (8+5 = 13).
        planos = [_plano("1 A", 8), _plano("2 B", 8), _plano("3 C", 8),
                  _plano("4 D", 5)]
        self.assertEqual(fp._grupos_por_campos(planos), [[0, 1], [2, 3]])

    def test_plano_maior_que_a_pagina_fica_sozinho(self):
        planos = [_plano("1 A", 25), _plano("2 B", 3)]
        self.assertEqual(fp._grupos_por_campos(planos), [[0], [1]])


class TestSequenciaDoGrupo(unittest.TestCase):

    def test_filtra_dias_e_renumera_indices(self):
        seq = [[0]] * 3 + [[1, 2]] * 2 + [[2]]
        # Grupo com os planos 1 e 2 (índices globais): só os dias deles.
        sub, num = fp._sequencia_do_grupo(seq, [1, 2])
        self.assertEqual(sub, [[0, 1], [0, 1], [1]])
        self.assertEqual(num, [4, 5, 6])   # nº da fração NO TRATAMENTO

    def test_grupo_do_comeco_mantem_a_numeracao(self):
        seq = [[0]] * 3 + [[1]] * 2
        sub, num = fp._sequencia_do_grupo(seq, [0])
        self.assertEqual(sub, [[0], [0], [0]])
        self.assertEqual(num, [1, 2, 3])


class TestFichaDividida(unittest.TestCase):

    def _paginas(self, planos, seq):
        import fitz
        rot = [p["store"]["RP"]["rotulo_plano"] for p in planos]
        pdf, _i, _d = fp.gerar_ficha_multiplano(planos, "individual",
                                                sequencia=seq, rotulos=rot)
        doc = fitz.open(stream=pdf, filetype="pdf")
        return [doc[i].get_text() for i in range(doc.page_count)]

    def test_dois_blocos_pagina2_mais_pagina3(self):
        planos = [_plano("1 A", 8), _plano("2 B", 8), _plano("3 C", 8)]
        seq = [[0]] * 10 + [[1]] * 10 + [[2]] * 10
        pgs = self._paginas(planos, seq)
        # Bloco 1 (planos 1 e 2) + bloco 2 (plano 3), cada um pág. 2 + pág. 3.
        self.assertEqual(len(pgs), 4)
        self.assertIn("Ficha Técnica", pgs[0])
        self.assertIn("Ficha Técnica", pgs[2])

    def test_fase_cor_e_numeracao_seguem_o_caso(self):
        planos = [_plano("1 A", 8), _plano("2 B", 8), _plano("3 C", 8)]
        seq = [[0]] * 10 + [[1]] * 10 + [[2]] * 10
        pgs = self._paginas(planos, seq)
        # A pág. 2 do 2º bloco numera o plano como 3 (não recomeça em 1): a
        # tabela de campos tem a linha "Fase" preenchida com 3.
        self.assertIn("3 C", pgs[2])
        self.assertNotIn("1 A", pgs[2])
        # A pág. 3 do 2º bloco continua a contagem de frações do tratamento.
        self.assertIn("21", pgs[3])
        self.assertIn("30", pgs[3])
        self.assertIn("3-1", pgs[3])       # rótulo fase-campo pelo nº do caso
        self.assertIn(fp._FIM_TTO, pgs[3])   # a última fração é a do tratamento
        self.assertNotIn(fp._FIM_TTO, pgs[1])

    def test_um_grupo_so_mantem_a_ficha_de_sempre(self):
        planos = [_plano("1 A", 8), _plano("2 B", 8)]
        seq = [[0]] * 10 + [[1]] * 10
        pgs = self._paginas(planos, seq)
        self.assertEqual(len(pgs), 2)      # pág. 2 + pág. 3
        self.assertIn(fp._FIM_TTO, pgs[1])


class TestGruposDeDose(unittest.TestCase):
    """Planos sequenciais da mesma região somam a dose num total contínuo na
    coluna Dose da pág. 3; os de outra região acumulam sozinhos."""

    def _acumuladores(self, **kw):
        kw.setdefault("grupos_dose", None)
        kw.setdefault("acc_ini", None)
        kw.setdefault("replan", 0)
        kw.setdefault("dose_replan", 0)
        return fp._acumuladores_de_dose(**kw)

    def test_sem_grupos_cada_plano_acumula_sozinho(self):
        grupos, acc = self._acumuladores(n_planos=3)
        self.assertEqual(grupos, [[0], [1], [2]])
        self.assertEqual(acc, [0.0, 0.0, 0.0])

    def test_planos_de_fora_viram_grupos_avulsos(self):
        grupos, acc = self._acumuladores(n_planos=4, grupos_dose=[[0, 1, 2]])
        self.assertEqual(grupos, [[0, 1, 2], [3]])
        self.assertEqual(acc, [0.0, 0.0])

    def test_replan_manda_e_junta_todos(self):
        grupos, acc = self._acumuladores(n_planos=3, grupos_dose=[[0, 1]],
                                         replan=5, dose_replan=200)
        self.assertEqual(grupos, [[0, 1, 2]])
        self.assertEqual(acc, [1000])

    def test_acc_ini_por_grupo(self):
        grupos, acc = self._acumuladores(n_planos=2, grupos_dose=[[0, 1]],
                                         acc_ini=[4000.0])
        self.assertEqual(grupos, [[0, 1]])
        self.assertEqual(acc, [4000.0])

    def _texto_mapa(self, planos, seq, grupos_dose):
        import fitz
        rot = [p["store"]["RP"]["rotulo_plano"] for p in planos]
        pdf, _i, _d = fp.gerar_ficha_multiplano(
            planos, "individual", sequencia=seq, rotulos=rot,
            grupos_dose=grupos_dose)
        doc = fitz.open(stream=pdf, filetype="pdf")
        return [doc[i].get_text() for i in range(doc.page_count)]

    def test_soma_continua_entre_planos_sequenciais(self):
        planos = [_plano("1 A", 4), _plano("2 B", 4)]
        seq = [[0]] * 3 + [[1]] * 3          # 2 Gy/fx em cada
        sem = self._texto_mapa(planos, seq, None)[-1]
        com = self._texto_mapa(planos, seq, [[0, 1]])[-1]
        # Sem somar: cada plano vai até 600 cGy (3 × 200).
        self.assertIn("600,0", sem)
        self.assertNotIn("1200,0", sem)
        # Somando: o boost continua de onde a fase parou, até 1200 cGy.
        self.assertIn("1200,0", com)
        self.assertIn("800,0", com)

    def test_soma_continua_mesmo_com_a_ficha_partida(self):
        # 3 × 8 campos = 24 > 21 → dois blocos; o grupo de dose atravessa eles.
        planos = [_plano("1 A", 8), _plano("2 B", 8), _plano("3 C", 8)]
        seq = [[0]] * 10 + [[1]] * 10 + [[2]] * 10
        pgs = self._texto_mapa(planos, seq, [[0, 1, 2]])
        self.assertEqual(len(pgs), 4)
        self.assertIn("4000,0", pgs[1])   # fim do 1º bloco (planos 1 e 2)
        self.assertIn("4200,0", pgs[3])   # o 2º bloco continua daí
        self.assertIn("6000,0", pgs[3])


if __name__ == "__main__":
    unittest.main()
