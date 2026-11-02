"""Filtros de estruturas (ocultar/desmarcar), decisão de imagem por fração e a
folha de Registro SUS.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.papel import ficha_pdf as fp  # noqa: E402


class TestEstruturaOculta(unittest.TestCase):
    def test_ocultas(self):
        for nome in ("_Ring", "_Body", "GTV", "GTVp", "GTV 60",
                     "PRV Medula", "Medula PRV", "PRV_Tronco", "prv medula"):
            self.assertTrue(fp.estrutura_oculta(nome), nome)

    def test_visiveis(self):
        for nome in ("PTV", "Medula", "Pulmao D", "Coracao", "CTV", "anel 1"):
            self.assertFalse(fp.estrutura_oculta(nome), nome)

    def test_vazio(self):
        self.assertFalse(fp.estrutura_oculta(""))
        self.assertFalse(fp.estrutura_oculta(None))


class TestEstruturaAuxiliar(unittest.TestCase):
    def test_auxiliares(self):
        for nome in ("anel 1", "CTV", "ctv boost", "Dose 95%", "z_aux",
                     "minuscula", "3mm", "Z_ring"):
            self.assertTrue(fp.estrutura_auxiliar(nome), nome)

    def test_alvos_e_oars(self):
        for nome in ("PTV", "Medula", "Pulmao D", "Coracao", "Parotida E"):
            self.assertFalse(fp.estrutura_auxiliar(nome), nome)


class TestFracTemImagem(unittest.TestCase):
    def test_sem_imagem(self):
        self.assertFalse(fp.frac_tem_imagem(0, "", "Diária", set()))

    def test_diaria(self):
        self.assertTrue(all(fp.frac_tem_imagem(i, "CBCT", "Diária", set())
                            for i in range(30)))

    def test_semanal(self):
        marc = [i for i in range(30) if fp.frac_tem_imagem(i, "MV", "Semanal", set())]
        # 0,1 e depois a cada 5 a partir do índice 5
        self.assertEqual(marc, [0, 1, 5, 10, 15, 20, 25])

    def test_personalizado(self):
        dias = {1, 4, 8}   # 1-based
        marc = [i + 1 for i in range(10)
                if fp.frac_tem_imagem(i, "CBCT", "Personalizado", dias)]
        self.assertEqual(marc, [1, 4, 8])

    def test_frequencia_desconhecida(self):
        self.assertFalse(fp.frac_tem_imagem(0, "CBCT", "Qualquer", set()))


class TestImagemPorFracao(unittest.TestCase):
    """Mapa combinado (pág. 3): cada plano dita a imagem das SUAS frações."""

    def test_boost_nao_herda_protocolo_da_fase(self):
        # Fase: MV semanal (frações 1,2,6,11,…). Boost: CBCT diário (toda fração).
        protos = [("MV", "Semanal", set()), ("CBCT", "Diária", set())]
        seq = [[0]] * 8 + [[1]] * 3          # 8 da fase, 3 do boost (sequencial)
        img = fp.imagem_por_fracao(protos, seq)
        # Fase segue o Semanal na numeração DELA (0,1 e a 6ª = índice 5).
        self.assertEqual([i for i, v in enumerate(img[:8]) if v], [0, 1, 5])
        # Boost inteiro tem CBCT — não herdou o Semanal da fase.
        self.assertEqual(img[8:], ["CBCT", "CBCT", "CBCT"])

    def test_personalizado_conta_a_partir_da_fracao_do_plano(self):
        # Boost personalizado nos dias 1 e 3 DELE, começando na 11ª fração global.
        protos = [("MV", "Diária", set()), ("CBCT", "Personalizado", {1, 3})]
        seq = [[0]] * 10 + [[1]] * 4
        img = fp.imagem_por_fracao(protos, seq)
        marcadas_boost = [i - 10 + 1 for i in range(10, 14) if img[i]]  # 1-based no boost
        self.assertEqual(marcadas_boost, [1, 3])

    def test_concomitante_junta_modalidades_distintas(self):
        protos = [("MV", "Diária", set()), ("CBCT", "Diária", set())]
        seq = [[0, 1]]                        # dois planos no mesmo dia
        self.assertEqual(fp.imagem_por_fracao(protos, seq), ["MV/CBCT"])

    def test_concomitante_mesma_modalidade_nao_duplica(self):
        protos = [("MV", "Diária", set()), ("MV", "Diária", set())]
        self.assertEqual(fp.imagem_por_fracao(protos, [[0, 1]]), ["MV"])

    def test_fracao_vazia_sem_imagem(self):
        protos = [("MV", "Semanal", set())]
        img = fp.imagem_por_fracao(protos, [[0], [0], [0]])   # índices 0,1,2
        self.assertEqual(img, ["MV", "MV", ""])               # 3ª fração sem imagem


def _fake_rs(estruturas):
    """RS mínimo (pydicom) a partir de [(num, nome, tipo, tem_contorno)]."""
    from pydicom.dataset import Dataset
    from pydicom.sequence import Sequence
    rs = Dataset()
    rois, contornos, obs = [], [], []
    for num, nome, tipo, tem in estruturas:
        r = Dataset(); r.ROINumber = num; r.ROIName = nome; rois.append(r)
        rc = Dataset(); rc.ReferencedROINumber = num
        rc.ContourSequence = Sequence([Dataset()]) if tem else Sequence([])
        contornos.append(rc)
        o = Dataset(); o.ReferencedROINumber = num
        o.RTROIInterpretedType = tipo; obs.append(o)
    rs.StructureSetROISequence = Sequence(rois)
    rs.ROIContourSequence = Sequence(contornos)
    rs.RTROIObservationsSequence = Sequence(obs)
    return rs


class TestEstruturasParaDvh(unittest.TestCase):
    def test_filtra_oculta_auxiliar_external_e_sem_contorno(self):
        rs = _fake_rs([
            (1, "PTV", "PTV", True),
            (2, "Medula", "ORGAN", True),
            (3, "GTV", "GTV", True),        # oculta
            (4, "CTV", "CTV", True),        # auxiliar
            (5, "BODY", "EXTERNAL", True),  # external
            (6, "Rim D", "ORGAN", False),   # sem contorno
            (7, "_Ring", "ORGAN", True),    # oculta
        ])
        self.assertEqual(fp._estruturas_para_dvh(rs), ["PTV", "Medula"])

    def test_respeita_limite(self):
        rs = _fake_rs([(i, f"OAR{i}", "ORGAN", True) for i in range(1, 20)])
        self.assertEqual(len(fp._estruturas_para_dvh(rs, limite=8)), 8)


class TestOrdemDoDvh(unittest.TestCase):
    """A escolha da tela chega como ``set``: a ordem dele mudava a cada processo,
    e com ela a legenda e a cor de cada curva na ficha impressa (TC8, 22/10/2026)."""

    RS = [
        (1, "Medula", "ORGAN", True),
        (2, "Coracao", "ORGAN", True),
        (3, "PTV_Mama", "PTV", True),
        (4, "Pulmao E", "ORGAN", True),
    ]

    def test_mesma_escolha_em_qualquer_ordem_da_a_mesma_lista(self):
        rs = _fake_rs(self.RS)
        a = fp._ordem_do_dvh(rs, ["Pulmao E", "Coracao", "PTV_Mama"])
        b = fp._ordem_do_dvh(rs, ["PTV_Mama", "Pulmao E", "Coracao"])
        self.assertEqual(a, b)

    def test_alvo_primeiro_depois_a_ordem_do_rt_struct(self):
        rs = _fake_rs(self.RS)
        self.assertEqual(fp._ordem_do_dvh(rs, {"Pulmao E", "Medula", "PTV_Mama", "Coracao"}),
                         ["PTV_Mama", "Medula", "Coracao", "Pulmao E"])

    def test_nome_fora_do_rt_struct_cai(self):
        rs = _fake_rs(self.RS)
        self.assertEqual(fp._ordem_do_dvh(rs, ["Medula", "Inexistente"]), ["Medula"])


class TestPaginaRegistroSus(unittest.TestCase):
    def _fracoes_presentes(self, total):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import landscape, A4
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        dados = {"pac_nome": "X", "pac_registro": "1", "eq_medico": "M",
                 "pac_nascimento": "", "numero_sus": "123"}
        fp.pagina_registro_sus(c, dados, total)
        c.showPage(); c.save()
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf ausente")
        import re
        txt = PdfReader(io.BytesIO(buf.getvalue())).pages[0].extract_text()
        return {int(m) for m in re.findall(r"\b(\d+)\b", txt)
                if m.isdigit() and 1 <= int(m) <= total}

    def test_todas_as_fracoes_presentes(self):
        for total in (1, 2, 5, 10, 39, 40):
            self.assertEqual(self._fracoes_presentes(total),
                             set(range(1, total + 1)), f"total={total}")


class TestTempoFracao(unittest.TestCase):
    def test_por_isocentro(self):
        # 24 min/iso no 1º dia, 12 min/iso nos demais.
        self.assertEqual(fp.tempo_fracao(1, True), 24)
        self.assertEqual(fp.tempo_fracao(1, False), 12)
        self.assertEqual(fp.tempo_fracao(2, True), 48)   # 2 isos no mesmo dia
        self.assertEqual(fp.tempo_fracao(2, False), 24)
        self.assertEqual(fp.tempo_fracao(3, True), 72)

    def test_sem_iso_no_dia(self):
        self.assertEqual(fp.tempo_fracao(0, True), 0)


class TestReplanejamento(unittest.TestCase):
    def _pdf(self, replan, dose_replan=0):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import landscape, A4
        planos = [{"dados": {"pac_nome": "X"},
                   "store": {"RP": {"feixes": [{"gantry": 0}],
                                    "n_isocentros": 1, "dose_fracao": 2.0}}}]
        seq = [[0]] * 3   # 3 frações de 1 plano
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        fp.pagina_fracoes_multi(c, planos, seq, ["1 P"], replan=replan,
                                dose_replan=dose_replan)
        c.showPage(); c.save()
        return buf.getvalue()

    def test_replan_renderiza_e_reserva_linhas(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf ausente")
        # Renderiza sem erro com e sem replanejamento; a dose final (3×200) sai.
        for replan in (0, 2, 5):
            pdf = self._pdf(replan)
            r = PdfReader(io.BytesIO(pdf))
            self.assertEqual(len(r.pages), 1)
            self.assertIn("600", r.pages[0].extract_text(), f"replan={replan}")

    def test_replan_dose_anterior_e_rotulo(self):
        from pypdf import PdfReader
        # 3 frações rasuradas × 200 cGy → dose acumulada 200/400/600 e o rótulo…
        txt = PdfReader(io.BytesIO(self._pdf(3, dose_replan=200))).pages[0].extract_text()
        for cum in ("200", "400", "600"):
            self.assertIn(cum, txt)
        self.assertIn("REPLANEJAMENTO", txt.replace(" ", ""))
        # …e o plano CONTINUA da dose anterior (600 + 200 = 800 na 1ª fração).
        self.assertIn("800", txt)

    def test_rotulo_diz_quantas_fracoes_e_a_que_dose(self):
        """O rótulo era só "REPLANEJAMENTO", centrado nas sub-colunas de campo.

        Com dois campos essa faixa tem ~34 pt e a palavra pede o triplo: ela
        saía por cima de Imagem e das Observações (medido no PDF em
        23/09/2026). Agora vai inteiro na coluna larga, e leva o dado que
        justifica a folha não começar na fração 1.
        """
        from pypdf import PdfReader
        txt = PdfReader(io.BytesIO(self._pdf(3, dose_replan=200))
                        ).pages[0].extract_text().replace(" ", "")
        self.assertIn("3fraçõesjátratadas", txt)
        self.assertIn("600,0cGy", txt)      # 3 × 200, o total já entregue

    def test_uma_fracao_tratada_fala_no_singular(self):
        from pypdf import PdfReader
        txt = PdfReader(io.BytesIO(self._pdf(1, dose_replan=200))
                        ).pages[0].extract_text().replace(" ", "")
        self.assertIn("1fraçãojátratada", txt)

    def test_sem_dose_informada_o_rotulo_nao_inventa_numero(self):
        """Dose/fração anterior em branco: diz as frações e cala sobre a dose."""
        from pypdf import PdfReader
        txt = PdfReader(io.BytesIO(self._pdf(4))).pages[0].extract_text()
        self.assertIn("REPLANEJAMENTO", txt.replace(" ", ""))
        self.assertNotIn("cGy", txt.split("REPLANEJAMENTO")[1][:60])

    def test_replan_negativo_nao_quebra(self):
        # replan negativo é tratado como 0 (clamp) — só não pode estourar.
        from pypdf import PdfReader
        self.assertEqual(len(PdfReader(io.BytesIO(self._pdf(-3))).pages), 1)

    def _pdf2(self, replan, dose_replan):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import landscape, A4
        pl = {"dados": {"pac_nome": "X"},
              "store": {"RP": {"feixes": [{"gantry": 0}],
                               "n_isocentros": 1, "dose_fracao": 2.0}}}
        planos = [dict(pl), dict(pl)]
        seq = [[0]] * 3 + [[1]] * 3   # base 3 fx, depois boost 3 fx (sequencial)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        fp.pagina_fracoes_multi(c, planos, seq, ["1 A", "2 B"],
                                replan=replan, dose_replan=dose_replan)
        c.showPage(); c.save()
        return buf.getvalue()

    def test_boost_continua_no_replan(self):
        from pypdf import PdfReader
        # replan 2×200=400; base 600/800/1000; boost CONTINUA 1200/1400/1600.
        txt = PdfReader(io.BytesIO(self._pdf2(2, 200))).pages[0].extract_text()
        self.assertIn("1600", txt)        # só aparece se o boost NÃO reinicia
        # sem replan os planos ficam separados (boost reinicia; sem 1200).
        txt0 = PdfReader(io.BytesIO(self._pdf2(0, 0))).pages[0].extract_text()
        self.assertNotIn("1200", txt0)

    def test_replan_no_plano_unico(self):
        # pagina_fracoes (single) também rasura, acumula a dose anterior e rotula.
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import landscape, A4
        from pypdf import PdfReader
        dados = {"pac_nome": "X", "rx_fracoes": 5, "rx_dose_fracao": 2.0}
        store = {"RP": {"feixes": [{"gantry": 0, "fase": 1}],
                        "n_isocentros": 1, "num_fracoes": 5, "dose_fracao": 2.0}}
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        fp.pagina_fracoes(c, dados, store, replan=3, dose_replan=180)
        c.showPage(); c.save()
        txt = PdfReader(io.BytesIO(buf.getvalue())).pages[0].extract_text()
        for cum in ("180", "360", "540"):   # 1..3 × 180 (rasuradas)
            self.assertIn(cum, txt)
        self.assertIn("REPLANEJAMENTO", txt.replace(" ", ""))
        # Continuação: plano parte de 540 → 1ª fração 740, total final 1540.
        self.assertIn("740", txt)
        self.assertIn("1540", txt)


class TestGradeSemLinhasVazias(unittest.TestCase):
    """A grade do mapa de frações não desce por linhas vazias: são exatamente as
    frações (antes o mínimo era 39, enchendo a folha de linhas em branco)."""

    def _single(self, nfr):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import landscape, A4
        from pypdf import PdfReader
        dados = {"pac_nome": "X", "rx_fracoes": nfr, "proto_imagem": "MV",
                 "proto_frequencia": "Semanal"}
        store = {"RP": {"num_fracoes": nfr, "dose_fracao": 2.0, "n_isocentros": 1,
                        "feixes": [{"gantry": 0, "um": 1}, {"gantry": 90, "um": 1},
                                   {"gantry": 180, "um": 1}]}}
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        fp.pagina_fracoes(c, dados, store)
        c.showPage(); c.save()
        return PdfReader(io.BytesIO(buf.getvalue())).pages[0].extract_text()

    def test_single_para_nas_fracoes(self):
        # 7 frações, dose máx 1400 (nenhum "39" possível no texto): antes a folha
        # tinha 39 linhas e o rótulo de fração "39" aparecia.
        txt = self._single(7)
        self.assertIn("1400", txt)          # última fração renderizada
        self.assertNotIn("39", txt)         # sem padding de linhas vazias

    def test_multi_para_nas_fracoes(self):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import landscape, A4
        from pypdf import PdfReader
        pl = {"dados": {"pac_nome": "X"},
              "store": {"RP": {"feixes": [{"gantry": 0}], "n_isocentros": 1,
                               "dose_fracao": 2.0}}}
        planos = [dict(pl), dict(pl)]
        seq = [[0]] * 3 + [[1]] * 3         # 6 frações no total
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        fp.pagina_fracoes_multi(c, planos, seq, ["1 A", "2 B"])
        c.showPage(); c.save()
        txt = PdfReader(io.BytesIO(buf.getvalue())).pages[0].extract_text()
        self.assertIn("600", txt)           # doses das 6 frações presentes
        self.assertNotIn("39", txt)         # sem as linhas 7..39 vazias


class TestOrdemPlanos(unittest.TestCase):
    """A ordem dos planos nas págs 2 e 3 segue ``ordem_planos`` (chips do
    agendamento); sem ela, o número do rótulo."""

    def _plano(self, rot, um):
        return {"dados": {"pac_nome": "X", "proto_imagem": "MV",
                          "proto_frequencia": "Diária", "rx_fracoes": 5},
                "store": {"RP": {"rotulo_plano": rot, "num_fracoes": 5,
                                 "dose_fracao": 2.0, "n_isocentros": 1,
                                 "feixes": [{"gantry": 0, "um": um}]}},
                "recursos": {}}

    def _pos_rotulos(self, ordem):
        from pypdf import PdfReader
        planos = [self._plano("1 ESTERNO", 111), self._plano("2 PULMAO", 222)]
        seq = [[0, 1]] * 5
        pdf, _i, _d = fp.gerar_ficha_multiplano(
            planos, "individual", sequencia=seq,
            rotulos=["1 ESTERNO", "2 PULMAO"], ordem_planos=ordem)
        # Página da ficha (págs de cortes não saem sem TC): 1ª página.
        txt = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
        return txt.find("ESTERNO"), txt.find("PULMAO")

    def test_default_por_numero(self):
        pe, pp = self._pos_rotulos(None)
        self.assertLess(pe, pp)   # ESTERNO (nº 1) antes de PULMAO (nº 2)

    def test_ordem_invertida(self):
        pe, pp = self._pos_rotulos([1, 0])
        self.assertLess(pp, pe)   # PULMAO primeiro quando ordem_planos = [1,0]

    def test_ordem_incompleta_cai_no_padrao(self):
        # Ordem inválida (falta um índice) → volta ao número do rótulo.
        pe, pp = self._pos_rotulos([1])
        self.assertLess(pe, pp)


class TestFracoesEmbutidas(unittest.TestCase):
    """Quando o mapa cabe na própria pág. 2, a pág. 3 separada não é emitida.

    São dois caminhos: com POUCOS CAMPOS (≤ ``_MAX_CAMPOS_LADO``) Observações e
    Checklist vão para a faixa livre ao lado da tabela de campos e o mapa ganha a
    metade de baixo da folha inteira; com muitos campos não há faixa livre, e aí
    só tratamento curto (≤ ``_MAX_FRAC_EMBUTIR``) cabe.
    """

    def _n_pag_single(self, nfr, n_campos=1):
        import fitz
        d = {"pac_nome": "X", "pac_registro": "1", "rx_fracoes": nfr,
             "proto_imagem": "MV", "proto_frequencia": "Semanal"}
        rp = {"num_fracoes": nfr, "dose_fracao": 2.0, "n_isocentros": 1,
              "rotulo_plano": "P",
              "feixes": [{"gantry": 0, "um": 100} for _ in range(n_campos)]}
        pdf = fp.gerar_ficha(d, {"RP": rp}, {})
        return fitz.open(stream=pdf, filetype="pdf").page_count

    def test_poucos_campos_embutem_o_tratamento_inteiro(self):
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("pymupdf ausente")
        # 15 frações é o caso comum de mama/próstata e não cabia antes.
        for n_campos in (1, fp._MAX_CAMPOS_LADO):
            with self.subTest(campos=n_campos):
                self.assertEqual(self._n_pag_single(15, n_campos), 1)
                self.assertEqual(self._n_pag_single(3, n_campos), 1)

    def test_muitos_campos_voltam_a_regra_curta(self):
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("pymupdf ausente")
        n = fp._MAX_CAMPOS_LADO + 1        # já não sobra faixa ao lado
        self.assertEqual(self._n_pag_single(5, n), 1)    # curto, embute
        self.assertEqual(self._n_pag_single(6, n), 2)    # pág. 3 separada
        self.assertEqual(self._n_pag_single(15, n), 2)

    def test_tratamento_longo_vai_para_a_pagina_propria(self):
        # Nem com poucos campos o mapa é espremido: passando do que cabe abaixo
        # da tabela, ele volta para a página dele.
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("pymupdf ausente")
        self.assertEqual(self._n_pag_single(30), 2)

    def test_embutida_tem_mapa_e_observacoes(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf ausente")
        d = {"pac_nome": "X", "pac_registro": "1", "rx_fracoes": 5,
             "proto_imagem": "MV", "proto_frequencia": "Diária"}
        rp = {"num_fracoes": 5, "dose_fracao": 2.0, "n_isocentros": 1,
              "rotulo_plano": "P", "feixes": [{"gantry": 0, "um": 100}]}
        r = PdfReader(io.BytesIO(fp.gerar_ficha(d, {"RP": rp}, {})))
        self.assertEqual(len(r.pages), 1)
        txt = r.pages[0].extract_text().replace(" ", "")
        for esperado in ("Mapadefrações", "Observações"):
            self.assertIn(esperado, txt)
        # O Checklist mudou-se para a contracapa (ver capa_pdf).
        self.assertNotIn("Checklist", txt)

    def test_multi_embute_ate_5(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("pymupdf ausente")

        def _plano(rot, nfr):
            return {"dados": {"pac_nome": "X", "proto_imagem": "MV",
                              "proto_frequencia": "Diária"},
                    "store": {"RP": {"rotulo_plano": rot, "num_fracoes": nfr,
                                     "dose_fracao": 8.0, "n_isocentros": 1,
                                     "feixes": [{"gantry": 0, "um": 100}]}},
                    "recursos": {}}
        # Dois planos de 1 campo cada: 2 colunas, sobra faixa ao lado.
        planos = [_plano("1 A", 3), _plano("2 B", 2)]
        pdf5, _i, _d = fp.gerar_ficha_multiplano(
            planos, "individual", sequencia=[[0]] * 3 + [[1]] * 2,
            rotulos=["1 A", "2 B"])
        self.assertEqual(fitz.open(stream=pdf5, filetype="pdf").page_count, 1)
        pdf14, _i, _d = fp.gerar_ficha_multiplano(
            planos, "individual", sequencia=[[0]] * 7 + [[1]] * 7,
            rotulos=["1 A", "2 B"])
        self.assertEqual(fitz.open(stream=pdf14, filetype="pdf").page_count, 1)

    def test_multi_com_muitos_campos_volta_a_regra_curta(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("pymupdf ausente")

        def _plano(rot, n_campos):
            return {"dados": {"pac_nome": "X", "proto_imagem": "MV",
                              "proto_frequencia": "Diária"},
                    "store": {"RP": {"rotulo_plano": rot, "num_fracoes": 10,
                                     "dose_fracao": 2.0, "n_isocentros": 1,
                                     "feixes": [{"gantry": 0, "um": 100}
                                                for _ in range(n_campos)]}},
                    "recursos": {}}
        planos = [_plano("1 A", 4), _plano("2 B", 4)]      # 8 colunas somadas
        pdf, _i, _d = fp.gerar_ficha_multiplano(
            planos, "individual", sequencia=[[0]] * 5 + [[1]] * 5,
            rotulos=["1 A", "2 B"])
        self.assertEqual(fitz.open(stream=pdf, filetype="pdf").page_count, 2)


class TestMapaEmbutidoGeometria(unittest.TestCase):
    """O mapa embutido na pág. 2 sai com a MESMA geometria da pág. 3 (linha de
    ``_HLIN_MAPA``, sem esticar) e respeitando a margem inferior de impressão.
    Quando não cabe assim, vai para a página própria em vez de espremer."""

    def _grade(self, n_planos, nfr):
        """Desenha a pág. 2 e devolve ``(embutiu, y0, y_fim, H)`` da grade."""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, landscape
        planos = [{"dados": {"pac_nome": "X", "proto_imagem": "MV",
                             "proto_frequencia": "Diária"},
                   "store": {"RP": {"rotulo_plano": f"{i + 1} F",
                                    "num_fracoes": nfr, "dose_fracao": 2.0,
                                    "n_isocentros": 1,
                                    "feixes": [{"gantry": 0, "um": 100},
                                               {"gantry": 30, "um": 100}]}},
                   "recursos": {}}
                  for i in range(n_planos)]
        capturado = {}
        orig = fp._grade_fracoes_multi

        def espiao(t, *a, **kw):
            fim = orig(t, *a, **kw)
            capturado.update(y0=a[3], fim=fim, H=t.H)
            return fim

        fp._grade_fracoes_multi = espiao
        try:
            c = canvas.Canvas(io.BytesIO(), pagesize=landscape(A4))
            emb = fp.pagina_ficha_multi(c, planos, [list(range(n_planos))] * nfr,
                                        [f"{i + 1} F" for i in range(n_planos)])
        finally:
            fp._grade_fracoes_multi = orig
        return emb, capturado

    def test_linha_fixa_e_margem_inferior(self):
        for n_planos in (1, 2, 3, 4):
            for nfr in (1, 3, 5):
                with self.subTest(planos=n_planos, fracoes=nfr):
                    emb, g = self._grade(n_planos, nfr)
                    if not emb:
                        continue   # foi para a pág. 3 (ver teste abaixo)
                    hlin = (g["fim"] - g["y0"] - fp._HCAB_MAPA) / nfr
                    self.assertAlmostEqual(hlin, fp._HLIN_MAPA, places=6)
                    self.assertGreaterEqual(g["H"] - g["fim"],
                                            fp._MARGEM_INFERIOR)

    def test_quatro_planos_cinco_fracoes_embutem(self):
        # Caso real (ficha de 4 fases × 5 frações): tem que caber na pág. 2.
        emb, g = self._grade(4, 5)
        self.assertTrue(emb)
        self.assertAlmostEqual((g["fim"] - g["y0"] - fp._HCAB_MAPA) / 5,
                               fp._HLIN_MAPA, places=6)
        self.assertGreaterEqual(g["H"] - g["fim"], fp._MARGEM_INFERIOR)

    def test_nao_espreme_manda_para_pagina_propria(self):
        # 5 planos × 5 frações não cabem na pág. 2 → mapa em folha própria.
        emb, _ = self._grade(5, 5)
        self.assertFalse(emb)


class TestFonteTabelas(unittest.TestCase):
    """As tabelas da pág. 2 usam UM tamanho para valores e um para cabeçalhos; o
    que não couber na célula encolhe sozinho em vez de vazar para a vizinha."""

    def _larguras(self):
        """Larguras reais das colunas mais apertadas da tabela do plano."""
        W = 841.8897637795277 - 28
        col = [40, 61, 62, 96, 46, 46, 46, 50]        # ver _tabela_plano
        return {"Fracionamento": 50, "Modalidade": 61,
                "sub": (W - sum(col)) / 9, "campo": (W - 50) / fp.N_CAMPOS}

    def test_conteudo_real_cabe_no_tamanho_nominal(self):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        larg = self._larguras()
        casos = [
            ("Fracionamento", ["1x dia", "Dias alter.", "2x sem.", "Única"],
             "Helvetica", fp._FONTE_VAL_TABELA),
            ("sub", ["-123,5", "100,0", "-99,9"], "Helvetica", fp._FONTE_VAL_TABELA),
            ("campo", ["10FFF", "1234,5", "SBRT"], "Helvetica", fp._FONTE_VAL_TABELA),
            ("Modalidade", ["Modalidade"], "Helvetica-Bold", fp._FONTE_CAB_TABELA),
        ]
        for col, textos, fonte, tam in casos:
            for s in textos:
                with self.subTest(coluna=col, texto=s):
                    self.assertLessEqual(stringWidth(s, fonte, tam),
                                         larg[col] - fp._PAD_CELULA)

    def test_texto_largo_demais_encolhe_e_nao_vaza(self):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, landscape
        c = canvas.Canvas(io.BytesIO(), pagesize=landscape(A4))
        t = fp.Tela(c, *landscape(A4))
        usados = []
        original = c.setFont
        c.setFont = lambda f, s, *a, **k: (usados.append(s), original(f, s, *a, **k))[1]
        # "Fase (30-70%)" não cabe em 61pt a 9,5 — tem que sair menor, não vazar.
        t.txt(0, 0, "Fase (30-70%)", size=fp._FONTE_VAL_TABELA, align="c", w=61, h=15)
        c.setFont = original
        self.assertLess(usados[-1], fp._FONTE_VAL_TABELA)
        self.assertGreaterEqual(usados[-1], fp._FONTE_MIN)
        self.assertLessEqual(
            c.stringWidth("Fase (30-70%)", "Helvetica", usados[-1]),
            61 - fp._PAD_CELULA + 0.01)

    def test_texto_que_cabe_mantem_o_tamanho_nominal(self):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, landscape
        c = canvas.Canvas(io.BytesIO(), pagesize=landscape(A4))
        t = fp.Tela(c, *landscape(A4))
        usados = []
        original = c.setFont
        c.setFont = lambda f, s, *a, **k: (usados.append(s), original(f, s, *a, **k))[1]
        t.txt(0, 0, "1x dia", size=fp._FONTE_VAL_TABELA, align="c", w=50, h=15)
        c.setFont = original
        self.assertEqual(usados[-1], fp._FONTE_VAL_TABELA)


class TestMapaPaginaPropriaAte39(unittest.TestCase):
    """Na página própria a linha do mapa não comprime até ``_MAX_LINHAS_MAPA``
    (39) frações — o teto real do serviço. É o que dimensiona ``_HLIN_MAPA``."""

    def _hlin(self, nfr):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, landscape
        d = {"pac_nome": "X", "pac_registro": "1", "rx_fracoes": nfr,
             "proto_imagem": "MV", "proto_frequencia": "Diária"}
        rp = {"num_fracoes": nfr, "dose_fracao": 2.0, "n_isocentros": 1,
              "rotulo_plano": "P", "feixes": [{"gantry": 0, "um": 100}]}
        c = canvas.Canvas(io.BytesIO(), pagesize=landscape(A4))
        t = fp.Tela(c, *landscape(A4))
        y0 = 40
        fim = fp._grade_fracoes(t, d, {"RP": rp}, y0, 0, 0, t.H - 24 - y0)
        return (fim - y0 - fp._HCAB_MAPA) / nfr, t.H - fim

    def test_ate_39_fracoes_sem_comprimir(self):
        for nfr in (1, 20, 30, fp._MAX_LINHAS_MAPA):
            with self.subTest(fracoes=nfr):
                hlin, margem = self._hlin(nfr)
                self.assertAlmostEqual(hlin, fp._HLIN_MAPA, places=6)
                self.assertGreaterEqual(margem, fp._MARGEM_INFERIOR)

    def test_acima_de_39_ainda_cabe_na_folha(self):
        # Não é o caso real do serviço, mas a grade não pode estourar a folha.
        hlin, margem = self._hlin(fp._MAX_LINHAS_MAPA + 5)
        self.assertLess(hlin, fp._HLIN_MAPA)
        self.assertGreaterEqual(margem, fp._MARGEM_INFERIOR - 0.5)


class TestMapaPaginaPropriaCentralizado(unittest.TestCase):
    """A pág. 3, quando é emitida, sai centralizada na vertical: a sobra que a
    grade não usa fica metade acima e metade abaixo, e não toda embaixo."""

    @staticmethod
    def _medir(fn, *args, **kw):
        """Emite a página própria e devolve ``(topo, baixo, vao)``: a sobra acima
        e abaixo da grade, e a distância do cabeçalho até o topo dela."""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, landscape
        H = landscape(A4)[1]
        visto = {}
        alvo = "_grade_fracoes_multi" if "multi" in fn.__name__ else "_grade_fracoes"
        original = getattr(fp, alvo)
        logo_original = fp._logo

        def espiao(t, *a, **k):
            # y0 e altura são os 4º/7º posicionais nas duas grades.
            fim = original(t, *a, **k)
            visto.update(y0=a[2] if alvo == "_grade_fracoes" else a[3], fim=fim)
            return fim

        def espiao_logo(c, x, y, w, h, **k):
            visto["topo_logo"] = H - y - h     # y do logo medido a partir do topo
            return logo_original(c, x, y, w, h, **k)

        setattr(fp, alvo, espiao)
        fp._logo = espiao_logo
        try:
            fn(canvas.Canvas(io.BytesIO(), pagesize=landscape(A4)), *args, **kw)
        finally:
            setattr(fp, alvo, original)
            fp._logo = logo_original
        return (visto["y0"] - fp._Y0_MAPA,
                H - fp._MARGEM_INFERIOR - visto["fim"],
                visto["y0"] - visto["topo_logo"])

    @staticmethod
    def _rp(nfr, n_feixes=1):
        return {"num_fracoes": nfr, "dose_fracao": 2.0, "n_isocentros": 1,
                "rotulo_plano": "P",
                "feixes": [{"numero": i + 1, "fase": 1, "gantry": 0, "um": 100}
                           for i in range(n_feixes)]}

    # Cabeçalho (logo + paciente) até o topo da grade, na folha cheia.
    _VAO = fp._Y0_MAPA - fp._Y_CAB_MAPA

    def test_plano_unico(self):
        d = {"pac_nome": "X", "pac_registro": "1", "proto_imagem": "MV"}
        for nfr in (6, 12, 25, fp._MAX_LINHAS_MAPA):
            with self.subTest(fracoes=nfr):
                topo, baixo, vao = self._medir(fp.pagina_fracoes, d,
                                               {"RP": self._rp(nfr)})
                self.assertAlmostEqual(topo, baixo, places=6)
                self.assertGreaterEqual(topo, 0)
                self.assertAlmostEqual(vao, self._VAO, places=6)

    def test_multi_plano(self):
        planos = [{"dados": {"pac_nome": "X"}, "store": {"RP": self._rp(10, 3)}},
                  {"dados": {"pac_nome": "X"}, "store": {"RP": self._rp(10, 3)}}]
        topo, baixo, vao = self._medir(fp.pagina_fracoes_multi, planos,
                                       [[0, 1]] * 10, ["1 A", "2 B"])
        self.assertAlmostEqual(topo, baixo, places=6)
        self.assertGreater(topo, 0)
        self.assertAlmostEqual(vao, self._VAO, places=6)

    def test_grade_cheia_nao_sai_do_lugar(self):
        # Mais linhas do que a faixa comporta: a linha comprime, a sobra é zero e
        # a grade continua começando no topo de sempre.
        from reportlab.lib.pagesizes import A4, landscape
        H = landscape(A4)[1]
        y0, alt = fp._faixa_mapa_centrado(fp._MAX_LINHAS_MAPA + 20, H)
        self.assertEqual(y0, 40)
        self.assertAlmostEqual(alt, H - fp._MARGEM_INFERIOR - 40, places=6)


class TestMesaNaoZero(unittest.TestCase):
    def test_deteccao(self):
        self.assertTrue(fp._mesa_nao_zero({"mesa": 45}))
        self.assertTrue(fp._mesa_nao_zero({"mesa": "315"}))
        self.assertFalse(fp._mesa_nao_zero({"mesa": 0}))
        self.assertFalse(fp._mesa_nao_zero({"mesa": "0"}))
        self.assertFalse(fp._mesa_nao_zero({}))
        self.assertFalse(fp._mesa_nao_zero({"mesa": None}))
        self.assertFalse(fp._mesa_nao_zero({"mesa": "x"}))


class TestFormatacaoBr(unittest.TestCase):
    """Nenhum valor da ficha pode ser arredondado: sempre 1 casa decimal."""

    def test_sempre_uma_casa_decimal(self):
        self.assertEqual(fp.br(7.5), "7,5")
        self.assertEqual(fp.br(352.5), "352,5")
        self.assertEqual(fp.br(98), "98,0")
        self.assertEqual(fp.br(0), "0,0")
        self.assertEqual(fp.br(-0.1), "-0,1")
        self.assertEqual(fp.br(181.49000026999997), "181,5")   # 1,815 Gy × 100

    def test_vazio_e_texto(self):
        self.assertEqual(fp.br(None), "")
        self.assertEqual(fp.br(""), "")
        self.assertEqual(fp.br("-"), "-")

    def test_nao_imprime_menos_zero(self):
        # "-0,0" na ficha sugere um lado que não existe.
        self.assertEqual(fp.br(-0.04), "0,0")
        self.assertEqual(fp.br(-0.0), "0,0")

    def test_valores_do_plano_saem_sem_arredondar(self):
        # Regressão: mesa 7,5° saía "8" e colimador 352,5° saía "352" (br com
        # 0 casas + arredondamento bancário do Python).
        feixe = {"gantry": 7.5, "colimador": 352.5, "mesa": 7.5}
        for chave in feixe:
            self.assertEqual(fp.br(feixe[chave], 1).replace(",", "."),
                             f"{feixe[chave]:.1f}", chave)


if __name__ == "__main__":
    unittest.main()


class TestRodapeImpressoEm(unittest.TestCase):
    """O "Impresso em …" é rodapé de TODA página emitida, em todos os PDFs.

    Antes ele saía em corpo 7/8 só em algumas — ora solto na margem, ora dentro
    da caixa de Observações — e a pág. 3 e as folhas de DRR não tinham nenhum.
    O carimbo entra no ``showPage`` (ver ``rodape.em_todas``), então o teste vale
    também para qualquer página que venha a existir depois.
    """

    @staticmethod
    def _rp(nfr, n_campos=4):
        return {"num_fracoes": nfr, "dose_fracao": 2.0, "n_isocentros": 1,
                "rotulo_plano": "P",
                "feixes": [{"gantry": 0, "um": 100} for _ in range(n_campos)]}

    def _sem_rodape(self, pdf: bytes) -> list[int]:
        """Nº das páginas que saíram SEM o rodapé."""
        from isocentro.papel import rodape
        from pypdf import PdfReader
        paginas = PdfReader(io.BytesIO(pdf)).pages
        self.assertGreater(len(paginas), 0)
        return [i + 1 for i, p in enumerate(paginas)
                if rodape.texto() not in (p.extract_text() or "")]

    def test_em_todas_as_paginas(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest("pypdf ausente")
        d = {"pac_nome": "X", "pac_registro": "1", "proto_imagem": "MV",
             "proto_frequencia": "Diária", "maquina": "TrueBeamSN1001"}
        planos = [{"dados": d, "store": {"RP": self._rp(20, 8)}, "recursos": {}},
                  {"dados": d, "store": {"RP": self._rp(20, 8)}, "recursos": {}}]
        casos = {
            # Uma folha só (mapa embutido na pág. 2) e duas (mapa na pág. 3).
            "ficha 1 folha": fp.gerar_ficha(d, {"RP": self._rp(15, 4)}, {}),
            "ficha com pág. 3": fp.gerar_ficha(d, {"RP": self._rp(30, 21)}, {}),
            "ficha arquivada": fp.gerar_ficha_arquivada(d, {"RP": self._rp(30, 21)}),
            # Multi-plano devolve (pdf, imagens, dvhs).
            "ficha multi-plano": fp.gerar_ficha_multiplano(planos)[0],
            "alta": fp.gerar_alta(d, {}),
        }
        for nome, pdf in casos.items():
            with self.subTest(pdf=nome):
                self.assertEqual(self._sem_rodape(pdf), [])


class TestDDNNosCortesEDVH(unittest.TestCase):
    """A folha de cortes+DVH circula SOLTA — é o que o físico confere fora da
    ficha —, e nome com ID não distingue homônimo.

    A data de nascimento tinha entrado só no renderizador da primeira impressão.
    A reimpressão de uma ficha reaberta usa outro (``_pagina_cortes_dvh_arquivada``,
    que remonta a folha dos PNGs salvos) e continuava sem a DDN: o mesmo paciente
    saía com dois cabeçalhos diferentes, e quem confere não sabe de qual caminho
    a folha na mão veio.
    """

    def _texto_pagina_1(self, pdf: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf ausente")
        return PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or ""

    def test_reimpressao_da_ficha_arquivada_traz_a_ddn(self):
        d = {"pac_nome": "AMOSTRA DE BELTRANA", "pac_registro": "99887",
             "pac_nascimento": "14/03/1962", "maquina": "TrueBeamSN1001"}
        # Um PNG qualquer serve: o que importa é o cabeçalho, e a página 1 só
        # existe quando há imagem salva.
        pdf = fp.gerar_ficha_arquivada(d, {"RP": self._rp()},
                                       imagem_png=_png_1x1())
        texto = self._texto_pagina_1(pdf)
        self.assertIn("Cortes Ortogonais e DVH", texto)
        self.assertIn("14/03/1962", texto)

    def test_a_ddn_fica_entre_o_nome_e_o_id(self):
        # Mesma ordem dos dois renderizadores: nome, nascimento, ID. Trocar a
        # ordem em um só faria as duas folhas se lerem diferente.
        d = {"pac_nome": "AMOSTRA DE BELTRANA", "pac_registro": "99887",
             "pac_nascimento": "14/03/1962", "maquina": "TrueBeamSN1001"}
        texto = self._texto_pagina_1(
            fp.gerar_ficha_arquivada(d, {"RP": self._rp()},
                                     imagem_png=_png_1x1()))
        self.assertLess(texto.find("AMOSTRA DE BELTRANA"), texto.find("14/03/1962"))
        self.assertLess(texto.find("14/03/1962"), texto.find("99887"))

    @staticmethod
    def _rp():
        return {"num_fracoes": 15, "dose_total": 30.0, "dose_fracao": 2.0}


def _png_1x1() -> bytes:
    """PNG mínimo válido — o conteúdo da imagem não importa aqui."""
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
        "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


class TestLinhaPacienteDoMapa(unittest.TestCase):
    """Nome longo empurra RGH e Data em vez de escrever por cima deles.

    O modelo tem "Lauri Jose de Paula"; a realidade tem "AMOSTRA DE BELTRANA
    SÍCRANA DO NASCIMENTO", que passava por baixo do "RGH:" e apagava as duas
    coisas. Nome de paciente é o último a ceder — quem cede é a posição do resto.
    """

    @staticmethod
    def _desenhado(nome: str) -> list[tuple[float, str]]:
        """(x, texto) de tudo que a linha do paciente escreveu, na ordem."""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, landscape
        W, H = landscape(A4)
        t = fp.Tela(canvas.Canvas(io.BytesIO(), pagesize=(W, H)), W, H)
        saida: list[tuple[float, str]] = []
        original = fp.Tela.txt

        def espiao(self, x, y, s, **k):
            saida.append((x + 3 + self.c.stringWidth(
                str(s), k.get("font", "Helvetica"), k.get("size", 8.5)), str(s)))
            return original(self, x, y, s, **k)

        fp.Tela.txt = espiao
        try:
            fp._cabecalho_mapa(t, {"pac_nome": nome, "pac_registro": "9000016BET",
                                   "pac_nascimento": "14/07/1966"}, fp._Y0_MAPA)
        finally:
            fp.Tela.txt = original
        return saida

    def test_nada_escreve_por_cima_do_vizinho(self):
        from reportlab.lib.pagesizes import A4, landscape
        limite = landscape(A4)[0] - 14
        for nome in ("Lauri Jose de Paula",
                     "AMOSTRA DE BELTRANA SÍCRANA DO NASCIMENTO",
                     "AMOSTRA DE BELTRANA SICRANA DO NASCIMENTO E SILVA "
                     "JUNQUEIRA DE ALBUQUERQUE", ""):
            with self.subTest(nome=nome[:24]):
                pecas = self._desenhado(nome)
                # O nome saiu inteiro (só é aparado em último caso).
                self.assertIn(nome, [s for _x, s in pecas] if nome else [nome, ""])
                # Cada peça termina antes de a seguinte começar, e a última
                # cabe na margem.
                fins = [x for x, _s in pecas]
                self.assertEqual(fins, sorted(fins))
                self.assertLessEqual(max(fins), limite)

    def test_nome_curto_mantem_as_posicoes_do_modelo(self):
        pecas = self._desenhado("Lauri Jose de Paula")
        rotulos = {s: x for x, s in pecas}
        # "RGH:" e "Data de Nascimento:" não se mexeram: o nome cabia na vaga.
        self.assertIn("RGH:", rotulos)
        self.assertIn("Data de Nascimento:", rotulos)
        curto = self._desenhado("Ana")
        self.assertEqual([s for _x, s in pecas if s.startswith(("RGH", "Data"))],
                         [s for _x, s in curto if s.startswith(("RGH", "Data"))])
