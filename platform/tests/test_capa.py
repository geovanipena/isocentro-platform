"""Capa de Tratamento: leitura dos relatórios exportados e geração do PDF.

Os relatórios são montados aqui, sintéticos, com as mesmas peculiaridades dos
reais — UTF-8 com BOM, preâmbulo de três linhas antes do cabeçalho, nome
invertido (``"Souza, Antonio Carlos de"``), dose em Gy, sítio em inglês e rodapé
de totais. O que se testa é a tradução dessas peculiaridades, que é onde um erro
sai impresso na capa que alguém assina.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.banco import capa_dados  # noqa: E402
from isocentro.papel import capa_pdf  # noqa: E402

# PNG 1×1 válido: o conteúdo não importa: o que se mede é o QUADRO, e o
# desenho da imagem é espiado antes de chegar ao reportlab.
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE"
    "hQGAhKmMIQAAAABJRU5ErkJggg==")

_CADASTRO = """Periodo
Periodo de tratamento: 01/01/2026 a 31/12/2027    |    Pacientes: 2

d_0,d_1,d_2,d_3,d_Contato,d_Convenio,d_NumConvenio,d_4,d_5,d_6,d_7,d_8,d_9,\
d_10,d_11,d_12,d_13,d_14,d_15,d_16,d_17,d_18,d_19,d_20,d_21,d_22,d_23
1111111AAA,"Souza, Antonio Carlos de",21/04/1947,Masculino,(62) 90000-0000,SUS,\
700000000000000,C1_ago 2026,ATIVO,Radical,C61 Neoplasia maligna da próstata,,,\
TrueBeamSN1001,6000 6000X,300.0,20,20,0,"6,000.0","6,000.0",0.0,04/08/2026,\
05/08/2026,Medico Exemplo,Radioterapia,Tratamento aprovado
2222222BBB,"Lima, Beatriz Alves de",22/10/1965,Feminino,,Unimed,\
0060000000000000,C1 MAIO 26,ATIVO,Pós-op.,"C50.5 Neoplasia maligna do quadrante",,,\
600CD,6000 6000X,520.0,5,5,0,"2,600.0","2,600.0",0.0,05/05/2026,06/05/2026,\
Medica Exemplo,Radioterapia,Tratamento aprovado
,,,,,,,,,,,,,,,,,,,,,,,,,,Total: 2 paciente(s)
"""

_PRESCRICOES = """col0,col1,col2,col3,col4,col5,col6,col7,col8,col9,col10,col11,\
col12,col13,tot0
1111111AAA,"Souza, Antonio Carlos de",Prostata + Drenagem 60Gy@20fx,Pelvis,\
C1_ago 2026,"PTV DREANGEM, PTV PROSTATA","44 Gy, 60 Gy","2.2 Gy, 3 Gy",20,\
ONCE DAILY,IMRT,Approved (rev. R0),medico.exemplo,04/08/2026,Total: 3
2222222BBB,"Lima, Beatriz Alves de",Boost Mama 10Gy@4fx,"Breast, Right",\
C1 MAIO 26,PTV_Boost,10 Gy,2.5 Gy,4,ONCE DAILY,Conformal,Approved (rev. R0),\
medica.exemplo,05/05/2026,Total: 3
2222222BBB,"Lima, Beatriz Alves de",Mama 26Gy@5fx,"Breast, Right",\
C1 MAIO 26,PTV_Mama,26 Gy,5.2 Gy,5,Dias alternado,Conformal,Approved (rev. R0),\
medica.exemplo,03/05/2026,Total: 3
"""


class _ComRelatorios(unittest.TestCase):
    """Base: escreve os relatórios sintéticos e aponta ISOCENTRO_CAPA_DIR neles."""

    def setUp(self):
        self.pasta = tempfile.mkdtemp(prefix="capa_teste_")
        # utf-8-sig: é assim que o Reporting Services entrega, e o BOM já
        # derrubou a leitura uma vez.
        for nome, conteudo in ((capa_dados.ARQ_CADASTRO, _CADASTRO),
                               (capa_dados.ARQ_PRESCRICOES, _PRESCRICOES)):
            with open(os.path.join(self.pasta, nome), "w",
                      encoding="utf-8-sig", newline="") as fh:
                fh.write(conteudo)
        self._env = os.environ.get(capa_dados.PASTA_ENV)
        os.environ[capa_dados.PASTA_ENV] = self.pasta

    def tearDown(self):
        if self._env is None:
            os.environ.pop(capa_dados.PASTA_ENV, None)
        else:
            os.environ[capa_dados.PASTA_ENV] = self._env


class TestNormalizacao(unittest.TestCase):
    def test_desinverte_o_nome(self):
        self.assertEqual(capa_dados.desinverter("Souza, Antonio Carlos de"),
                         "Antonio Carlos de Souza")
        self.assertEqual(capa_dados.desinverter("Cher"), "Cher")

    def test_nome_comparavel_ignora_acento_e_caixa(self):
        self.assertEqual(capa_dados.normalizar_nome("João  D'Ávila"),
                         capa_dados.normalizar_nome("joao d avila"))

    def test_id_comparavel_ignora_separadores(self):
        self.assertEqual(capa_dados.normalizar_id("1111111-AAA"),
                         capa_dados.normalizar_id("1111111aaa"))

    def test_gy_vira_cgy_sem_casa_a_toa(self):
        self.assertEqual(capa_dados._gy_para_cgy("40.05 Gy"), "4005")
        self.assertEqual(capa_dados._gy_para_cgy("2.625 Gy"), "262.5")
        # O que não é dose passa intacto — melhor do que virar zero.
        self.assertEqual(capa_dados._gy_para_cgy("conforme protocolo"),
                         "conforme protocolo")

    def test_cid_separa_codigo_da_descricao(self):
        self.assertEqual(capa_dados._split_cid("C50.5 Neoplasia da mama"),
                         ("C50.5", "Neoplasia da mama"))
        # Sem código reconhecível, tudo é descrição e o CID sai vazio.
        self.assertEqual(capa_dados._split_cid("a definir"), ("", "a definir"))

    def test_idade_em_anos_completos(self):
        # Aniversário ainda não feito no ano de referência.
        self.assertEqual(capa_dados.idade("22/10/1965", date(2026, 5, 6)), "60")
        self.assertEqual(capa_dados.idade("21/04/1947", date(2026, 8, 5)), "79")
        self.assertEqual(capa_dados.idade("data ruim"), "")

    def test_data_curta_sem_zero_a_esquerda(self):
        self.assertEqual(capa_dados.data_curta("21/04/1947"), "21/4/1947")


class TestLeitura(_ComRelatorios):
    def test_cadastro_traduz_as_colunas(self):
        cad = capa_dados.carregar_cadastro()
        self.assertEqual(len(cad), 2)           # o rodapé de totais não entra
        c = cad[capa_dados.normalizar_id("1111111AAA")]
        self.assertEqual(c.nome, "Antonio Carlos de Souza")
        self.assertEqual(c.convenio, "SUS - 700000000000000")
        self.assertEqual(c.cid, "C61")
        self.assertEqual(c.descricao, "Neoplasia maligna da próstata")
        self.assertEqual(c.maquina, "TrueBeamSN1001")
        self.assertEqual(c.medico, "Medico Exemplo")

    def test_convenio_sem_numero_nao_deixa_traco_solto(self):
        self.assertEqual(capa_dados._convenio("SUS", ""), "SUS")
        self.assertEqual(capa_dados._convenio("", ""), "")

    def test_prescricao_monta_as_linhas_da_capa(self):
        pre = capa_dados.carregar_prescricoes()
        p = pre[capa_dados.normalizar_id("1111111AAA")][0]
        self.assertEqual(p.titulo(), "Pelve: Prostata + Drenagem 60Gy@20fx")
        self.assertEqual(p.linha_frequencia(), "20 frações - Uma Vez por Dia")
        self.assertEqual([v.linha() for v in p.volumes], [
            "Volume PTV DREANGEM  4400 cGy  220 cGy/Frac",
            "Volume PTV PROSTATA  6000 cGy  300 cGy/Frac",
        ])

    def test_frequencia_e_sitio_saem_em_portugues(self):
        pre = capa_dados.carregar_prescricoes()
        blocos = pre[capa_dados.normalizar_id("2222222BBB")]
        self.assertEqual(blocos[0].site, "Mama, direita")
        self.assertEqual(blocos[1].frequencia, "Dias Alternados")

    def test_sitio_desconhecido_passa_intacto(self):
        # Traduzir por adivinhação imprimiria a região errada na capa.
        self.assertEqual(capa_dados.traduzir_site("Regiao Nova XYZ"),
                         "Regiao Nova XYZ")

    def test_sitios_do_relatorio_saem_em_portugues(self):
        """O relatório grava em inglês; a capa da clínica é em português."""
        for bruto, esperado in (("Hard Palate", "Palato duro"),
                                ("Spinal Cord, Lumbar", "Medula espinhal, lombar"),
                                ("Chest Wall, Left", "Parede torácica, esquerda"),
                                ("Superficial Inguinal Nodes",
                                 "Linfonodos inguinais superficiais"),
                                # Já em português no relatório, só a acentuação:
                                ("Iliaco direito", "Ilíaco, direito"),
                                ("leito prostatico", "Leito prostático"),
                                ("Oligomets", "Oligometástases")):
            self.assertEqual(capa_dados.traduzir_site(bruto), esperado)


class TestBusca(_ComRelatorios):
    def test_acha_pelo_id(self):
        res = capa_dados.buscar("1111111AAA", "Antonio Carlos de Souza")
        self.assertTrue(res.achou)
        self.assertEqual(res.cadastro.curso, "C1_ago 2026")
        self.assertEqual(len(res.prescricoes), 1)
        self.assertEqual(res.avisos, [])

    def test_acha_pelo_nome_quando_o_id_nao_bate(self):
        res = capa_dados.buscar("999999XXX", "Antonio Carlos de Souza")
        self.assertTrue(res.achou)
        self.assertTrue(any("casei pelo nome" in a for a in res.avisos))

    def test_nome_divergente_nao_bloqueia_mas_avisa(self):
        res = capa_dados.buscar("1111111AAA", "Outro Paciente Qualquer")
        self.assertTrue(res.achou)
        self.assertTrue(any("não bate" in a for a in res.avisos))

    def test_nascimento_divergente_avisa(self):
        res = capa_dados.buscar("1111111AAA", "Antonio Carlos de Souza",
                                "01/01/1950")
        self.assertTrue(any("Nascimento" in a for a in res.avisos))

    def test_paciente_ausente_sai_vazio_e_avisado(self):
        res = capa_dados.buscar("000000ZZZ", "Ninguém de Lugar Nenhum")
        self.assertFalse(res.achou)
        self.assertEqual(res.cadastro.nome, "")
        self.assertTrue(any("não encontrado" in a for a in res.avisos))

    def test_sem_relatorios_avisa_onde_procurou(self):
        """Sem banco apontado e sem relatórios, o aviso diz ONDE se procurou e
        a quem pedir.

        O texto mudou quando os endereços saíram da aba Capa: mandava apertar
        um botão "Relatórios" que não existe mais. Aviso que manda apertar o que
        não está na tela é pior que aviso nenhum.
        """
        os.environ[capa_dados.PASTA_ENV] = tempfile.mkdtemp()
        res = capa_dados.buscar("1111111AAA", "Antonio Carlos de Souza")
        self.assertFalse(res.achou)
        texto = " ".join(res.avisos)
        self.assertIn("Configurações", texto)
        self.assertIn(capa_dados.pasta_dados(), texto)
        self.assertNotIn("botão Relatórios", texto)


class TestMontagem(_ComRelatorios):
    def test_capa_nasce_com_o_que_o_relatorio_deu(self):
        res = capa_dados.buscar("2222222BBB", "Beatriz Alves de Lima")
        capa = capa_pdf.de_resultado(res)
        # Grafia canônica, não caixa alta: a capa e a ficha andam grampeadas e
        # até 25/08/2026 a mesma pessoa saía diferente em cada uma.
        self.assertEqual(capa.nome, "Beatriz Alves de Lima")
        self.assertTrue(capa.feminino())
        self.assertEqual(len(capa.blocos), 2)
        # A data de aprovação do cabeçalho é a da prescrição MAIS RECENTE.
        self.assertEqual(capa.data_aprovacao, "5/5/2026")
        self.assertEqual(capa.preparo["BEXIGA"], capa_pdf.VAZIO)

    def test_ficha_preenche_o_que_o_relatorio_nao_trouxe(self):
        res = capa_dados.buscar("000000ZZZ", "Fulano de Tal")
        capa = capa_pdf.de_resultado(res, nome="Fulano de Tal",
                                     registro="000000ZZZ", maquina="6EX",
                                     medico="Camila Sampaio")
        self.assertEqual(capa.nome, "Fulano de Tal")
        self.assertEqual(capa.maquina, "6EX")
        self.assertEqual(capa.medico, "Camila Sampaio")

    def test_login_ganha_o_dominio(self):
        self.assertEqual(capa_pdf._com_dominio("medico.exemplo"),
                         "clinica\\medico.exemplo")
        # Login já qualificado não é qualificado duas vezes.
        self.assertEqual(capa_pdf._com_dominio("OUTRO\\jose"), "OUTRO\\jose")
        self.assertEqual(capa_pdf._com_dominio(""), "")

    def test_destaque_ambar_so_no_preparo_acionavel(self):
        self.assertTrue(capa_pdf._destacar("BEXIGA", "Cheia"))
        self.assertTrue(capa_pdf._destacar("BRAÇOS", "Sobre Tórax"))
        # N/A e vazio não são instrução para ninguém.
        self.assertFalse(capa_pdf._destacar("BEXIGA", "N/A"))
        self.assertFalse(capa_pdf._destacar("RETO", ""))
        # Decúbito descreve o setup; fica branco mesmo preenchido.
        self.assertFalse(capa_pdf._destacar("DECÚBITO", "Dorsal"))


def _texto(pdf: bytes) -> str:
    """Texto das duas páginas, para conferir o que saiu impresso de fato."""
    import io

    from pypdf import PdfReader
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)


class TestPdf(_ComRelatorios):
    def test_gera_duas_paginas(self):
        res = capa_dados.buscar("1111111AAA", "Antonio Carlos de Souza")
        pdf = capa_pdf.gerar(capa_pdf.de_resultado(res))
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(pdf.count(b"/Type /Page\n"), 2)

    def test_imprime_o_que_veio_do_relatorio(self):
        res = capa_dados.buscar("1111111AAA", "Antonio Carlos de Souza")
        capa = capa_pdf.de_resultado(res)
        texto = _texto(capa_pdf.gerar(capa))
        for esperado in ("Antonio Carlos de Souza", "1111111AAA", "21/4/1947 (79)",
                         # A máquina sai no nome do SERVIÇO, não no de fábrica
                         # que o relatório traz: a capa anda GRAMPEADA na ficha,
                         # e a ficha já imprimia o nome do serviço — as duas
                         # folhas do mesmo maço nomeavam o mesmo acelerador de
                         # dois jeitos (31/08/2026).
                         "SUS - 700000000000000", "VitalBeam",
                         "C1_ago 2026",
                         "Radical", "C61", "Pelve: Prostata + Drenagem 60Gy@20fx",
                         "Volume PTV PROSTATA  6000 cGy  300 cGy/Frac",
                         "20 frações - Uma Vez por Dia",
                         "clinica\\medico.exemplo",
                         # O relatório traz "Medico Exemplo"; a capa imprime o
                         # nome canônico da equipe — e, desde 25/08/2026, na
                         # mesma grafia do resto do app, não em caixa alta.
                         "Medico Exemplo"):
            self.assertIn(esperado, texto, f"não saiu impresso: {esperado!r}")

    def test_rodape_impresso_em_nas_duas_folhas(self):
        # Substituiu a linha "Ficha confeccionada em … por …", que saía só na
        # folha 2. Agora é rodapé, miúdo, e nas DUAS.
        from isocentro.papel import rodape
        capa = capa_pdf.de_resultado(
            capa_dados.buscar("1111111AAA", "Antonio Carlos de Souza"))
        texto = _texto(capa_pdf.gerar(capa))
        self.assertEqual(texto.count(rodape.texto()), 2)
        self.assertNotIn("confeccionada", texto)

    def test_faixa_do_nome_diz_o_sexo(self):
        # Vermelha para mulher, azul para homem — e NEUTRA quando não se sabe,
        # em vez de escolher uma das duas no chute.
        for sexo, cor in (("Feminino", capa_pdf.VERMELHO),
                          ("F", capa_pdf.VERMELHO),
                          ("Masculino", capa_pdf.AZUL_TITULO),
                          ("M", capa_pdf.AZUL_TITULO),
                          ("", capa_pdf.CINZA_SEM_SEXO),
                          ("Indeterminado", capa_pdf.CINZA_SEM_SEXO)):
            with self.subTest(sexo=sexo):
                self.assertEqual(capa_pdf.Capa(sexo=sexo).cor_da_faixa(), cor)

    def test_sexo_definido(self):
        self.assertTrue(capa_pdf.Capa(sexo="Feminino").sexo_definido())
        self.assertTrue(capa_pdf.Capa(sexo="masculino").sexo_definido())
        for sexo in ("", "   ", "Outro", None):
            self.assertFalse(capa_pdf.Capa(sexo=sexo).sexo_definido(), repr(sexo))

    def test_contracapa_nao_repete_o_que_a_capa_ja_diz(self):
        """Convênio, contato e máquina só na capa — as duas andam grampeadas."""
        import io as _io

        from pypdf import PdfReader
        capa = capa_pdf.Capa(nome="TESTE", sexo="F", medico="DR EXEMPLO",
                             convenio="SUS - 700000", contato="(62) 90000-0000",
                             maquina="TrueBeamSN1001")
        paginas = PdfReader(_io.BytesIO(capa_pdf.gerar(capa))).pages
        p1 = paginas[0].extract_text() or ""
        p2 = paginas[1].extract_text() or ""
        for sumiu in ("CONVÊNIO", "CONTATO", "SUS - 700000", "(62) 90000-0000",
                      "TrueBeamSN1001"):
            self.assertIn(sumiu, p1, f"sumiu da CAPA: {sumiu}")
            self.assertNotIn(sumiu, p2, f"não devia estar na contracapa: {sumiu}")
        # O que identifica a folha se ela se soltar do maço continua nas duas.
        for ficou in ("TESTE", "DR EXEMPLO"):
            self.assertIn(ficou, p2, ficou)

    def test_fotos_saem_com_legenda(self):
        texto = _texto(capa_pdf.gerar(capa_pdf.Capa(nome="TESTE")))
        for n in range(1, capa_pdf.fotos_impressas(1) + 1):
            self.assertIn(f"FOTO {n}", texto)

    def _quadros(self, n_fotos: int) -> list:
        """Os quadros desenhados para um setup com ``n_fotos``: ``(x0, x1)``.

        Espiona ``_quadro_de_foto`` em vez de ler o PDF: o que se quer medir é
        a POSIÇÃO, e ela não sobrevive à extração de texto.
        """
        import io as _io

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as _canvas

        f = capa_pdf._Folha(_canvas.Canvas(_io.BytesIO(), pagesize=A4))
        vistos = []
        orig = capa_pdf._quadro_de_foto
        capa_pdf._quadro_de_foto = (
            lambda ff, img, x0, y0, x1, y1, n: vistos.append((x0, x1)))
        try:
            s = capa_dados.Setup(nome="T")
            s.fotos = [_PNG_1x1] * n_fotos
            capa_pdf._grade_de_fotos(f, s, 16.2, 100.0, 579.3, 3, 1, 150.0)
        finally:
            # GUARDA E DEVOLVE — ``del capa_pdf._quadro_de_foto`` apagaria a
            # função ORIGINAL do módulo para o resto do processo.
            capa_pdf._quadro_de_foto = orig
        return vistos

    def test_menos_de_tres_fotos_ficam_CENTRADAS(self):
        """Pedido do usuário em 25/08/2026.

        A grade fixa de três desenhava dois retângulos vazios ao lado da única
        foto do paciente. Quadro vazio no papel é uma pergunta: quem confere na
        sala procura a foto que falta, ou anota nele achando que devia haver
        algo — e não havia foto nenhuma para aquele quadro.
        """
        centro = (16.2 + 579.3) / 2
        for n in (1, 2, 3):
            with self.subTest(fotos=n):
                q = self._quadros(n)
                self.assertEqual(len(q), n, "quadro vazio sobrando")
                meio = (q[0][0] + q[-1][1]) / 2
                self.assertAlmostEqual(meio, centro, delta=0.5)

    def test_a_largura_do_quadro_nao_muda_com_menos_fotos(self):
        """É ela que mantém a foto do mesmo tamanho em todos os
        posicionamentos, e é comparando setup contra setup que a montagem se
        confere. Esticar a foto única daria um retrato gigante ao lado de uma
        tira de três na montagem vizinha."""
        larguras = {round(x1 - x0, 1) for n in (1, 2, 3)
                    for x0, x1 in self._quadros(n)}
        self.assertEqual(len(larguras), 1, larguras)

    def test_SEM_foto_nenhuma_a_tira_de_tres_continua(self):
        """A capa em branco é impressa de propósito para ser preenchida à mão.

        Aí os três quadros são o espaço reservado para as fotos que ainda vão
        ser coladas — colapsá-los para um tiraria esse espaço de quem imprime
        antes de ter as fotos.
        """
        self.assertEqual(len(self._quadros(0)), 3)

    def test_acessorios_no_mesmo_corpo_do_preparo(self):
        """Lados do mesmo par: dois pesos faziam a lista de acessórios parecer
        mais importante que o preparo."""
        import io as _io

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as _canvas

        f = capa_pdf._Folha(_canvas.Canvas(_io.BytesIO(), pagesize=A4))
        vistos = {"acess": [], "prep": []}
        orig_aj = capa_pdf._Folha.txt_ajustado
        orig_ct = capa_pdf._Folha.txt_centro
        capa_pdf._Folha.txt_ajustado = lambda self, x, t, s, larg, fonte, tam, *a, **k: (
            vistos["acess"].append((fonte, tam)),
            orig_aj(self, x, t, s, larg, fonte, tam, *a, **k))[1]
        capa_pdf._Folha.txt_centro = lambda self, x0, x1, t, s, fonte=capa_pdf.FONTE, tam=9.0, *a, **k: (
            vistos["prep"].append((fonte, tam)),
            orig_ct(self, x0, x1, t, s, fonte, tam, *a, **k))[1]
        # Com preparo de verdade: sem nenhum, o quadro não desenha célula
        # nenhuma e não há o que comparar com os acessórios.
        setups = [capa_dados.Setup(nome="X", acessorios="Rampa\nApoio")]
        setups[0].preparo = {"BEXIGA": "Cheia"}
        try:
            capa_pdf._acessorios_p2(f, setups, 16.2, 330.0, 500.0, 518.0, 518.0, 600.0,
                                    len(capa_pdf.PREPARO_NA_CONTRACAPA))
            capa_pdf._preparo_p2(f, setups, 334.0, 579.3, 500.0, 518.0, 518.0, 600.0)
        finally:
            capa_pdf._Folha.txt_ajustado = orig_aj
            capa_pdf._Folha.txt_centro = orig_ct
        self.assertTrue(vistos["acess"] and vistos["prep"])
        self.assertEqual(set(vistos["acess"]), set(vistos["prep"]))

    def test_arranjo_das_fotos_por_numero_de_posicionamentos(self):
        """Um ou dois: tira de TRÊS para cada, empilhadas.

        O teto é dois (``MAX_SETUPS``). Havia um arranjo de três que virava
        colunas — cada montagem com um terço da largura —, e a foto encolhia até
        o ponto em que não se confere mais a montagem, que é a única razão de
        ela estar impressa.
        """
        self.assertEqual(capa_pdf.MAX_SETUPS, 2)
        self.assertEqual(capa_pdf.arranjo_fotos(1), (False, 3, 1))
        self.assertEqual(capa_pdf.arranjo_fotos(2), (False, 3, 1))
        # A largura do quadro é a mesma nos dois: três por linha, folha inteira.
        for n in (1, 2):
            self.assertEqual(capa_pdf.fotos_impressas(n), 3, n)
        # Acima do teto, cai no arranjo do teto.
        self.assertEqual(capa_pdf.arranjo_fotos(9), capa_pdf.arranjo_fotos(2))
        self.assertEqual(capa_pdf.arranjo_fotos(0), capa_pdf.arranjo_fotos(1))

    def test_faixa_de_fotos_encolhe_com_um_posicionamento(self):
        """A faixa tem altura VARIÁVEL: com um posicionamento ela devolve folha
        para os blocos de baixo, em vez de reservar sempre o mesmo retângulo.

        O início dela não é mais um y fixo: vem do fim do cabeçalho, que na
        contracapa termina na foto 3×4 (ver ``_cabecalho``).
        """
        import io as _io

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as _canvas

        y0 = capa_pdf._TOPO_P2 + capa_pdf._ALT_FOTO_3X4 + capa_pdf._GAP_CABECALHO_P2
        fins = []
        for n in (1, capa_pdf.MAX_SETUPS):
            f = capa_pdf._Folha(_canvas.Canvas(_io.BytesIO(), pagesize=A4))
            setups = [capa_dados.Setup(nome=f"S{i}") for i in range(n)]
            fins.append(capa_pdf._fotos_p2(f, setups, 16.2, 579.3, y0))
        self.assertLess(fins[0], fins[1], "um posicionamento devia ocupar menos")
        for fim in fins:
            self.assertLessEqual(fim - y0, capa_pdf._ALT_MAX_FOTOS + 0.5)

    def test_legenda_numera_as_fotos_de_cada_posicionamento(self):
        # A numeração recomeça em cada montagem: "a 2 do fêmur" tem de ser
        # única dentro do posicionamento, que é como se fala na sala.
        capa = capa_pdf.Capa(nome="TESTE")
        capa.setups = [capa_dados.Setup(nome="A"), capa_dados.Setup(nome="B")]
        texto = _texto(capa_pdf.gerar(capa))
        self.assertEqual(texto.count("FOTO 1"), 2)   # uma por posicionamento
        self.assertEqual(texto.count("FOTO 2"), 2)
        # Com o teto em dois setups, cada um mantém a tira de TRÊS quadros —
        # era o arranjo de três que espremia a faixa em colunas de um.
        self.assertEqual(texto.count("FOTO 3"), 2)

    def test_capa_vazia_nao_quebra(self):
        # A tela deixa imprimir capa preenchida à mão a partir do nada.
        pdf = capa_pdf.gerar(capa_pdf.Capa())
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_foto_ilegivel_nao_derruba_a_capa(self):
        capa = capa_pdf.Capa(nome="TESTE", foto=b"isto nao e uma imagem")
        capa.fotos_posicionamento = [b"nem isto"]
        self.assertTrue(capa_pdf.gerar(capa).startswith(b"%PDF"))

    def test_prescricoes_demais_sao_anunciadas_nao_escondidas(self):
        capa = capa_pdf.Capa(nome="TESTE")
        capa.blocos = [capa_pdf.Bloco(titulo=f"Plano {i}") for i in range(6)]
        texto = _texto(capa_pdf.gerar(capa))
        self.assertIn("Plano 0", texto)
        # O que não coube não some em silêncio.
        self.assertIn("não couberam nesta folha", texto)

    def test_nome_longo_encolhe_em_vez_de_vazar(self):
        # Sem o encolhimento, o nome invadiria a caixa do DDN ao lado.
        capa = capa_pdf.Capa(nome="M" * 60, registro="9000026XXX")
        texto = _texto(capa_pdf.gerar(capa))
        self.assertIn("M" * 60, texto)
        self.assertIn("9000026XXX", texto)


if __name__ == "__main__":
    unittest.main()


class TestNotaDaPrescricao(unittest.TestCase):
    """A nota que o radioterapeuta escreveu, vinda do ARIA.

    Ela saía numa altura só, ao lado da FREQUÊNCIA — herança de quando era um
    campo digitado na tela, sempre curto. Lida de ``DimPrescription.Notes``
    (23/09/2026), é o texto do médico: das nove notas do banco na primeira
    leitura, SEIS tinham de três a sete linhas, e a partir da terceira o texto
    passava POR BAIXO da caixa "Aprovado por" do bloco seguinte — ilegível numa
    folha que vai para a sala.
    """

    NOTA_LONGA = ("GLIOMA DIFUSO DE ALTO GRAU\n"
                  "PARIETAL OCCIPITAL ESQUERDO\n"
                  "SEM CONDIÇÕES DE RNM (MARCAPASSO)\n"
                  "\n"
                  "PTV = alteração na TC + 20 mm\n"
                  "60 Gy\n"
                  "30 sessões\n"
                  "IMRT")

    def test_nota_curta_sai_inteira(self):
        linhas = capa_pdf._notas_que_cabem("QT CONCOMITANTE\nEC IIA")
        self.assertEqual(linhas, ["QT CONCOMITANTE", "EC IIA"])

    def test_linha_em_branco_nao_ocupa_espaco(self):
        """A nota do ARIA vem com \\r\\n e parágrafos vazios; contar o vazio
        gastaria uma das cinco linhas com nada."""
        self.assertEqual(capa_pdf._notas_que_cabem("A\n\n\nB"), ["A", "B"])

    def test_o_que_nao_cabe_e_anunciado_e_nao_sumido(self):
        """Nota cortada em silêncio é pior que nota incompleta: quem confere
        não tem como saber que o médico escreveu mais três linhas."""
        linhas = capa_pdf._notas_que_cabem(self.NOTA_LONGA)
        self.assertEqual(len(linhas), capa_pdf._MAX_LINHAS_NOTA)
        self.assertEqual(linhas[-1], "+ 3 linha(s) — confira no sistema")
        self.assertEqual(linhas[0], "GLIOMA DIFUSO DE ALTO GRAU")

    def test_a_nota_cabe_acima_do_bloco_seguinte(self):
        """A conta que o layout tem de respeitar: a última linha da nota não
        pode alcançar o topo do próximo bloco (+86,2), onde mora a caixa
        "Aprovado por" dele."""
        ultima = (capa_pdf._NOTA_TOPO
                  + (capa_pdf._MAX_LINHAS_NOTA - 1) * capa_pdf._ALTURA_LINHA)
        self.assertLess(ultima + capa_pdf._ALTURA_LINHA, capa_pdf._PASSO_BLOCO)
        # E começa ABAIXO da caixa "Aprovado por" do próprio bloco (+21,8).
        self.assertGreater(capa_pdf._NOTA_TOPO, 21.8)

    def test_sai_impressa_no_pdf(self):
        capa = capa_pdf.Capa(nome="TESTE")
        capa.blocos = [capa_pdf.Bloco(titulo="Encéfalo: Glioma 60Gy@30fx",
                                      notas=self.NOTA_LONGA)]
        texto = _texto(capa_pdf.gerar(capa))
        self.assertIn("GLIOMA DIFUSO DE ALTO GRAU", texto)
        self.assertIn("confira no sistema", texto)
        # A sétima linha NÃO sai — é ela que iria parar debaixo do bloco 2.
        self.assertNotIn("IMRT", texto)


class TestPrescricaoSemCadastro(_ComRelatorios):
    """Os dois relatórios saem com janelas de período diferentes.

    Aconteceu de verdade: o de prescrições veio com 13 080 pacientes e o de
    cadastro, com 599. Os 12 481 do meio chegavam à capa sem convênio, contato,
    CID, diagnóstico nem intenção — e SEM UM AVISO SEQUER. Quem estava na frente
    concluía que o programa tinha quebrado.
    """

    def setUp(self):
        super().setUp()
        # Prescrição de um paciente que não tem linha no cadastro.
        with open(os.path.join(self.pasta, capa_dados.ARQ_PRESCRICOES), "a",
                  encoding="utf-8-sig", newline="") as fh:
            fh.write('3333333CCC,"Monteiro, Ivonete Teodora",Oligo PD em LID,'
                     'Oligomets,C4_AGO_2026,PTVm LID,27 Gy,9 Gy,3,'
                     'Dias alternado,VMAT/IGRT,Approved (rev. R0),'
                     'rubens.junior,17/08/2026,Total: 4\n')

    def test_avisa_que_o_cadastro_e_que_esta_faltando(self):
        res = capa_dados.buscar("3333333CCC", "")
        self.assertTrue(res.prescricoes, "a prescrição existe")
        self.assertFalse(res.achou, "cadastro não achado continua não achado")
        texto = " ".join(res.avisos)
        self.assertIn(capa_dados.ARQ_CADASTRO, texto)
        self.assertIn("período", texto)

    def test_nome_e_curso_vem_da_prescricao(self):
        """Colunas do MESMO relatório, escritas pelo mesmo sistema — usar o que
        já está ali não é palpite, e a capa deixa de sair anônima."""
        res = capa_dados.buscar("3333333CCC", "")
        self.assertEqual(res.cadastro.nome, "Ivonete Teodora Monteiro")
        self.assertEqual(res.cadastro.curso, "C4_AGO_2026")
        self.assertEqual(res.cadastro.registro, "3333333CCC")

    def test_o_que_so_o_cadastro_sabe_continua_vazio(self):
        """Preencher convênio ou CID daí seria inventar dado no papel."""
        res = capa_dados.buscar("3333333CCC", "")
        for campo in ("convenio", "contato", "cid", "descricao", "intencao",
                      "maquina", "medico", "nascimento", "sexo"):
            self.assertEqual(getattr(res.cadastro, campo), "", campo)

    def test_paciente_com_cadastro_nao_muda(self):
        res = capa_dados.buscar("1111111AAA", "")
        self.assertTrue(res.achou)
        self.assertEqual(res.cadastro.convenio, "SUS - 700000000000000")
        self.assertNotIn(capa_dados.ARQ_CADASTRO, " ".join(res.avisos))


class TestContatoNoPapel(_ComRelatorios):
    """Célula de contato vazia se lê como esquecimento, não como ausência.

    Na sala, quem precisa ligar para o paciente vai procurar o telefone em
    outro sistema — ou anotar um de memória. Dizer "Não cadastrado" encerra a
    busca. Mas só se pode dizer isso quando o relatório afirmou; sem linha de
    cadastro nenhuma, ninguém sabe se existe telefone.
    """

    def _capa(self, registro):
        res = capa_dados.buscar(registro, "")
        return capa_pdf.de_resultado(res, registro=registro)

    def test_com_telefone_imprime_o_telefone(self):
        capa = self._capa("1111111AAA")
        self.assertEqual(capa_pdf._contato_impresso(capa), "(62) 90000-0000")

    def test_cadastrado_sem_telefone_diz_nao_cadastrado(self):
        capa = self._capa("2222222BBB")
        self.assertEqual(capa.contato, "")
        self.assertEqual(capa_pdf._contato_impresso(capa),
                         capa_pdf.SEM_CONTATO)

    def test_sem_cadastro_a_celula_fica_vazia(self):
        """Afirmar "não cadastrado" sobre quem nem está no relatório seria
        inventar dado — e é dado que sai impresso."""
        with open(os.path.join(self.pasta, capa_dados.ARQ_PRESCRICOES), "a",
                  encoding="utf-8-sig", newline="") as fh:
            fh.write('4444444DDD,"Teste, Sem Cadastro",Plano,Sitio,C1,'
                     'PTV,10 Gy,2 Gy,5,ONCE DAILY,IMRT,Approved (rev. R0),'
                     'medico,17/08/2026,Total: 5\n')
        capa = self._capa("4444444DDD")
        self.assertFalse(capa.cadastro_achado)
        self.assertEqual(capa_pdf._contato_impresso(capa), "")

    def test_o_recado_sai_no_pdf(self):
        """Teste que passa não prova que o papel está certo: lê o PDF gerado."""
        pdf = capa_pdf.gerar(self._capa("2222222BBB"))
        self.assertIn(capa_pdf.SEM_CONTATO, _texto(pdf))


class TestNotasDePosicionamento(unittest.TestCase):
    """A nota que o técnico deixa na pasta — .docx quase sempre.

    Os casos são transcrições literais das notas reais das pastas de teste, com
    as variações de grafia que elas de fato têm (com e sem acento, "P/ GANTRY",
    "MÃOS NO TÓRAX").
    """

    def _interpretar(self, *linhas):
        return capa_dados.interpretar_notas("\n".join(linhas))

    def test_pelve_separa_preparo_de_acessorio(self):
        acess, prep = self._interpretar(
            "CABECA PARA O GANTRY", "DECUBITO DORSAL", "ProStep", "TRAVESSEIRO",
            "MÃOS NO TÓRAX", "BEXIGA CHEIA", "RETO VAZIO")
        self.assertEqual(prep, {"PARA O GANTRY": "Cabeça", "DECÚBITO": "Dorsal",
                                "BRAÇOS": "Sobre Tórax", "BEXIGA": "Cheia",
                                "RETO": "Vazio"})
        # Só o que é acessório de verdade sobra na caixa.
        self.assertEqual(acess, "ProStep\nTRAVESSEIRO")

    def test_acento_e_abreviacao_nao_atrapalham(self):
        _a, prep = self._interpretar("CABEÇA P/ GANTRY", "DECÚBITO DORSAL",
                                     "BRAÇO DIR ELEVADO")
        self.assertEqual(prep["PARA O GANTRY"], "Cabeça")
        self.assertEqual(prep["BRAÇOS"], "Direito elevado")

    def test_sobra_da_linha_continua_sendo_acessorio(self):
        # "DECUBITO VENTRAL NO TRAVESSEIRO" diz o decúbito E um acessório.
        acess, prep = self._interpretar("DECUBITO VENTRAL NO TRAVESSEIRO")
        self.assertEqual(prep["DECÚBITO"], "Ventral")
        self.assertEqual(acess, "TRAVESSEIRO")

    def test_sobra_sai_com_o_acento_original(self):
        # O casamento é sem acento, mas o corte é feito no texto como escrito.
        acess, _p = self._interpretar("DECUBITO DORSAL NO COLCHÃO")
        self.assertEqual(acess, "COLCHÃO")

    def test_linha_desconhecida_nunca_some(self):
        # A nota é digitada à mão: setup novo aparece antes de o app aprendê-lo,
        # e perder a linha seria perder a instrução de como deitar o paciente.
        acess, prep = self._interpretar("APARELHO NOVO XYZ", "BASE   (  B  )")
        self.assertEqual(prep, {})
        self.assertEqual(acess, "APARELHO NOVO XYZ\nBASE   (  B  )")

    def test_medida_da_rampa_nao_vira_posicao_de_braco(self):
        # "ÂNGULO DO BRACO -20" é medida do acessório, não onde o braço está.
        acess, prep = self._interpretar("RAMPA", "ÂNGULO DO BRACO -20",
                                        "ALTURA DO BRACO 4")
        self.assertNotIn("BRAÇOS", prep)
        self.assertEqual(acess.splitlines(),
                         ["RAMPA", "ÂNGULO DO BRACO -20", "ALTURA DO BRACO 4"])

    def test_jejum_sai_com_as_horas(self):
        # É a hora que muda o que se diz ao paciente.
        _a, prep = self._interpretar("D = 4       ( JEJUM DE 4 HORAS)")
        self.assertEqual(prep["JEJUM"], "4h")
        _a, prep = self._interpretar("JEJUM DE 6H")
        self.assertEqual(prep["JEJUM"], "6h")
        # Sem hora, a coluna fica vazia em vez de receber um valor chutado — a
        # linha continua visível nos acessórios.
        _a, prep = self._interpretar("PACIENTE EM JEJUM")
        self.assertNotIn("JEJUM", prep)
        _a, prep = self._interpretar("D = 4")
        self.assertNotIn("JEJUM", prep)

    def test_preparo_usa_o_vocabulario_do_relatorio(self):
        """As colunas saem na grafia da capa institucional, não na da nota."""
        _a, prep = self._interpretar("PES PARA O GANTRY",
                                     "DECUBITO LATERAL DIREITO",
                                     "BRACOS AO LONGO DO CORPO")
        self.assertEqual(prep["PARA O GANTRY"], "Pé")
        self.assertEqual(prep["DECÚBITO"], "Lateral Dir")
        self.assertEqual(prep["BRAÇOS"], "Ao lado corpo")
        for coluna, valor in prep.items():
            self.assertIn(valor, capa_pdf.OPCOES_PREPARO[coluna],
                          f"{valor!r} fora do vocabulário de {coluna}")

    def test_nao_se_aplica_vira_na(self):
        _a, prep = self._interpretar("BEXIGA NAO SE APLICA", "RETO NAO SE APLICA")
        self.assertEqual(prep["BEXIGA"], capa_pdf.VAZIO)
        self.assertEqual(prep["RETO"], capa_pdf.VAZIO)

    def test_nota_vazia_nao_quebra(self):
        self.assertEqual(capa_dados.interpretar_notas(""), ("", {}))
        self.assertEqual(capa_dados.interpretar_notas(None), ("", {}))

    def test_le_docx_de_verdade(self):
        """O .docx é lido na mão (zip + XML), sem dependência a mais."""
        import zipfile

        doc = ('<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
               "<w:p><w:r><w:t>CABECA PARA O GANTRY</w:t></w:r></w:p>"
               "<w:p><w:r><w:t>BEXIGA CHEIA</w:t></w:r></w:p>"
               "<w:p><w:r><w:t>M&#195;OS &amp; APOIO</w:t></w:r></w:p>"
               "</w:body></w:document>")
        caminho = os.path.join(tempfile.mkdtemp(), "nota.docx")
        with zipfile.ZipFile(caminho, "w") as z:
            z.writestr("word/document.xml", doc)
        texto = capa_dados.ler_nota(caminho)
        self.assertIn("CABECA PARA O GANTRY", texto)
        # Parágrafos viram linhas — sem isso o documento sairia numa linha só.
        self.assertEqual(len(capa_dados.interpretar_notas(texto)[1]), 2)
        self.assertIn("&", texto)          # entidade XML desescapada

    def test_arquivo_ilegivel_nao_derruba(self):
        caminho = os.path.join(tempfile.mkdtemp(), "quebrado.docx")
        with open(caminho, "wb") as fh:
            fh.write(b"isto nao e um docx")
        self.assertEqual(capa_dados.ler_nota(caminho), "")


class TestImagensPesadas(unittest.TestCase):
    """Foto de celular embutida crua fazia a capa passar de 100 MB."""

    def _foto(self, larg, alt):
        from PIL import Image
        buf = __import__("io").BytesIO()
        Image.new("RGB", (larg, alt), (120, 90, 60)).save(buf, format="JPEG")
        return buf.getvalue()

    def test_capa_com_fotos_de_celular_fica_leve(self):
        capa = capa_pdf.Capa(nome="TESTE")
        capa.fotos_posicionamento = [self._foto(4000, 3000) for _ in range(4)]
        pdf = capa_pdf.gerar(capa)
        self.assertTrue(pdf.startswith(b"%PDF"))
        # Sem a reamostragem isto passava de 100 MB e levava ~40 s.
        self.assertLess(len(pdf), 3_000_000, "capa grande demais para imprimir")

    def test_imagem_pequena_passa_intacta(self):
        # Reduzir a foto 3×4 do relatório não economizaria nada.
        pequena = self._foto(240, 239)
        self.assertIs(capa_pdf._reamostrar(pequena, 93.7, 83.1), pequena)


class TestPastaDosRelatorios(_ComRelatorios):
    """A pasta pode ser apontada na tela — é o que se faz quando nada é achado."""

    def tearDown(self):
        capa_dados.definir_pasta_dados("")
        super().tearDown()

    def test_escolha_da_tela_vence_a_variavel_de_ambiente(self):
        outra = tempfile.mkdtemp()
        capa_dados.definir_pasta_dados(outra)
        self.assertEqual(capa_dados.pasta_dados(), outra)
        # E "" devolve o controle para a variável de ambiente.
        capa_dados.definir_pasta_dados("")
        self.assertEqual(capa_dados.pasta_dados(), self.pasta)

    def test_lista_quais_relatorios_estao_la(self):
        # O de fotos não é escrito pelo setUp — a tela precisa saber disso.
        presentes = capa_dados.relatorios_presentes()
        self.assertIn(capa_dados.ARQ_CADASTRO, presentes)
        self.assertIn(capa_dados.ARQ_PRESCRICOES, presentes)
        self.assertNotIn(capa_dados.ARQ_FOTOS, presentes)

    def test_pasta_vazia_nao_acha_nada_e_nao_quebra(self):
        capa_dados.definir_pasta_dados(tempfile.mkdtemp())
        self.assertEqual(capa_dados.relatorios_presentes(), [])
        self.assertFalse(capa_dados.buscar("1111111AAA", "Antonio").achou)


class TestCantosArredondados(unittest.TestCase):
    def test_o_recorte_e_reposto_mesmo_com_erro(self):
        """Um erro dentro do bloco não pode deixar o recorte ligado.

        Se o ``restoreState`` não rodasse, tudo que fosse desenhado depois sairia
        aparado pelo retângulo daquela tabela — a folha seguinte viria em branco.
        """
        from reportlab.pdfgen import canvas as _canvas

        folha = capa_pdf._Folha(_canvas.Canvas(__import__("io").BytesIO()))
        profundidade = len(folha.c._codeStack)
        with self.assertRaises(ValueError):
            with folha.bloco(10, 10, 100, 100):
                raise ValueError("falha no meio do desenho")
        self.assertEqual(len(folha.c._codeStack), profundidade)

    def test_capa_com_cantos_arredondados_ainda_fecha(self):
        capa = capa_pdf.Capa(nome="TESTE", registro="1X")
        capa.blocos = [capa_pdf.Bloco(titulo="Plano", volumes=["Volume PTV"])]
        pdf = capa_pdf.gerar(capa)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("TESTE", _texto(pdf))


class TestProcuraAutomatica(unittest.TestCase):
    """Achar os relatórios sem ninguém precisar configurar nada.

    O caminho padrão (``capa/``) é uma convenção que quem recebe a exportação
    não é obrigado a conhecer — e uma capa vazia não explica que o problema era
    o nome da pasta.
    """

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self._env = os.environ.pop(capa_dados.PASTA_ENV, None)
        capa_dados.definir_pasta_dados("")
        self._app_dir = capa_dados._app_dir
        capa_dados._app_dir = lambda: self.base

    def tearDown(self):
        capa_dados._app_dir = self._app_dir
        capa_dados.definir_pasta_dados("")
        if self._env is not None:
            os.environ[capa_dados.PASTA_ENV] = self._env

    def _semear(self, *partes):
        pasta = os.path.join(self.base, *partes)
        os.makedirs(pasta, exist_ok=True)
        with open(os.path.join(pasta, capa_dados.ARQ_CADASTRO), "w",
                  encoding="utf-8-sig") as fh:
            fh.write(_CADASTRO)
        return pasta

    def test_acha_a_pasta_com_outro_nome(self):
        alvo = self._semear("TCs_Teste", "banco de dados")
        self.assertEqual(capa_dados.pasta_dados(), alvo)

    def test_capa_barra_e_preferida_a_procura(self):
        # A convenção continua valendo quando existe: é o caminho previsível.
        self._semear("outra pasta")
        alvo = self._semear("capa")
        self.assertEqual(capa_dados.pasta_dados(), alvo)

    def test_sem_relatorio_nenhum_devolve_o_padrao(self):
        self.assertEqual(capa_dados.pasta_dados(),
                         os.path.join(self.base, "capa"))

    def test_escolha_da_tela_dispensa_a_procura(self):
        self._semear("TCs_Teste", "banco de dados")
        escolhida = tempfile.mkdtemp()
        capa_dados.definir_pasta_dados(escolhida)
        self.assertEqual(capa_dados.pasta_dados(), escolhida)

    def test_nao_desce_em_pastas_grandes(self):
        # Varrer .venv/.git a cada abertura seria caro e nunca acharia nada.
        self._semear(".venv", "relatorios")
        self.assertEqual(capa_dados.pasta_dados(),
                         os.path.join(self.base, "capa"))

    def test_procura_uma_vez_por_sessao(self):
        alvo = self._semear("dados")
        self.assertEqual(capa_dados.pasta_dados(), alvo)
        chamadas = []
        original = capa_dados._procurar_relatorios
        capa_dados._procurar_relatorios = lambda: chamadas.append(1) or ""
        try:
            capa_dados.pasta_dados()
            self.assertEqual(chamadas, [], "procurou de novo em vez de usar o cache")
        finally:
            capa_dados._procurar_relatorios = original


class TestEscolhaDePrescricoes(_ComRelatorios):
    """O relatório traz o histórico inteiro; só três cabem na folha."""

    def test_marca_as_do_curso_do_cadastro(self):
        res = capa_dados.buscar("2222222BBB", "")
        opcoes = capa_pdf.opcoes_de(res)
        self.assertEqual(len(opcoes), 2)
        self.assertTrue(all(o.do_curso_atual and o.marcada for o in opcoes))

    def test_ordena_da_mais_recente_para_a_mais_antiga(self):
        res = capa_dados.buscar("2222222BBB", "")
        datas = [o.data for o in capa_pdf.opcoes_de(res)]
        self.assertEqual(datas, ["05/05/2026", "03/05/2026"])

    def test_curso_antigo_entra_na_lista_mas_desmarcado(self):
        """Reimprimir capa de curso encerrado é pedido real — some não pode."""
        res = capa_dados.buscar("2222222BBB", "")
        res.prescricoes.append(capa_dados.Prescricao(
            site="Pelve", descricao="RT ANTIGA", curso="C1 2019",
            data_aprovacao="02/04/2019", fracoes="5"))
        opcoes = capa_pdf.opcoes_de(res)
        antiga = opcoes[-1]                       # a mais velha vai para o fim
        self.assertEqual(antiga.curso, "C1 2019")
        self.assertFalse(antiga.do_curso_atual)
        self.assertFalse(antiga.marcada)

    def test_nao_marca_mais_do_que_cabe_na_folha(self):
        res = capa_dados.buscar("2222222BBB", "")
        base = res.prescricoes[0]
        for i in range(6):
            res.prescricoes.append(capa_dados.Prescricao(
                site="Pelve", descricao=f"EXTRA {i}", curso=base.curso,
                data_aprovacao="05/05/2026", fracoes="5"))
        opcoes = capa_pdf.opcoes_de(res)
        self.assertEqual(sum(1 for o in opcoes if o.marcada), capa_pdf.MAX_BLOCOS)

    def test_sempre_sobra_uma_marcada(self):
        # Curso do cadastro que não bate com prescrição nenhuma: a capa não pode
        # sair vazia sem ninguém ter decidido isso.
        res = capa_dados.buscar("2222222BBB", "")
        res.cadastro.curso = "CURSO QUE NAO EXISTE"
        opcoes = capa_pdf.opcoes_de(res)
        self.assertEqual(sum(1 for o in opcoes if o.marcada), 1)
        self.assertTrue(opcoes[0].marcada)        # a mais recente

    def test_rotulo_comeca_pela_data(self):
        res = capa_dados.buscar("2222222BBB", "")
        rotulo = capa_pdf.opcoes_de(res)[0].rotulo()
        self.assertTrue(rotulo.startswith("5/5/2026"), rotulo)
        self.assertIn("C1 MAIO 26", rotulo)
        self.assertIn("Mama, direita", rotulo)

    def test_data_do_cabecalho_vem_das_escolhidas(self):
        """Prescrição de outro curso, que nem entrou, não pode datar a capa."""
        res = capa_dados.buscar("2222222BBB", "")
        res.prescricoes.append(capa_dados.Prescricao(
            site="Pelve", descricao="FUTURA", curso="C9 2030",
            data_aprovacao="01/01/2030", fracoes="5"))
        capa = capa_pdf.de_resultado(res)
        self.assertEqual(capa.data_aprovacao, "5/5/2026")


class TestSetupsDePosicionamento(unittest.TestCase):
    """Um paciente pode ter mais de um jeito de ser deitado.

    O TC7 é tratado de fêmur E de tórax: no primeiro os braços vão sobre o
    tórax, no segundo não. São instruções de montagem diferentes, e fundi-las
    numa linha só mandaria montar errado metade das sessões.
    """

    def setUp(self):
        self.pasta = tempfile.mkdtemp(prefix="setups_")

    def _nota(self, nome, *linhas):
        import zipfile
        corpo = "".join(f"<w:p><w:r><w:t>{l}</w:t></w:r></w:p>" for l in linhas)
        caminho = os.path.join(self.pasta, nome)
        with zipfile.ZipFile(caminho, "w") as z:
            z.writestr("word/document.xml",
                       f'<?xml version="1.0"?><w:document xmlns:w="x">'
                       f"<w:body>{corpo}</w:body></w:document>")

    def _foto(self, nome):
        from PIL import Image
        Image.new("RGB", (40, 30), (10, 20, 30)).save(
            os.path.join(self.pasta, nome))

    def test_uma_nota_um_setup(self):
        self._nota("PELVE.docx", "CABECA PARA O GANTRY", "BEXIGA CHEIA")
        self._foto("qualquer.png")
        setups = capa_dados.setups_da_pasta(self.pasta)
        self.assertEqual(len(setups), 1)
        self.assertEqual(setups[0].nome, "PELVE")
        self.assertEqual(setups[0].preparo["BEXIGA"], "Cheia")
        self.assertEqual(len(setups[0].fotos), 1)

    def test_fotos_vao_para_o_setup_que_o_nome_indica(self):
        # É o caso real de um paciente tratado de fêmur e de tórax: o nome
        # do arquivo traz o do setup.
        self._nota("FEMUR.docx", "TRAVESSEIRO")
        self._nota("TORAX.docx", "RAMPA DE TORAX")
        self._foto("PACIENTE FEMUR FOTO.png")
        self._foto("PACIENTE FOTO TORAX.png")
        self._foto("PACIENTE FOTO TORAX 2.png")
        setups = {s.nome: s for s in capa_dados.setups_da_pasta(self.pasta)}
        self.assertEqual(len(setups["FEMUR"].fotos), 1)
        self.assertEqual(len(setups["TORAX"].fotos), 2)

    def test_foto_sem_pista_vai_para_o_primeiro(self):
        # Fotos numeradas ("PACIENTE 1/2") não dizem nada — quem distribui é a
        # pessoa, na tela. Adivinhar seria pior do que agrupar.
        self._nota("SNC RADIOCIRURGIA.docx", "MASCARA")
        self._nota("TORAX.docx", "RAMPA")
        self._foto("PACIENTE1.png")
        self._foto("PACIENTE2.png")
        setups = capa_dados.setups_da_pasta(self.pasta)
        self.assertEqual(len(setups[0].fotos), 2)
        self.assertEqual(len(setups[1].fotos), 0)

    def test_palavra_generica_nao_casa(self):
        # "FOTO" está em todo nome de arquivo; se contasse, casaria com tudo.
        self.assertEqual(capa_dados._tokens_do_setup("FOTO DE SETUP"), set())
        self.assertEqual(capa_dados._tokens_do_setup("MAMA VAC = LOCK"),
                         {"MAMA", "VAC", "LOCK"})

    def test_sem_nota_um_setup_com_tudo(self):
        self._foto("a.png")
        self._foto("b.png")
        setups = capa_dados.setups_da_pasta(self.pasta)
        self.assertEqual(len(setups), 1)
        self.assertEqual(setups[0].nome, "")
        self.assertEqual(len(setups[0].fotos), 2)

    def test_pasta_inexistente_nao_quebra(self):
        self.assertEqual(capa_dados.setups_da_pasta("/nao/existe"), [])
        self.assertEqual(capa_dados.setups_da_pasta(""), [])


class TestFolha2ComDoisSetups(unittest.TestCase):

    def _capa(self, n):
        capa = capa_pdf.Capa(nome="TESTE")
        capa.setups = [
            capa_dados.Setup(nome=f"SETUP{i}", acessorios=f"ACESSORIO {i}",
                             preparo={"BRAÇOS": "Sobre Tórax"} if i == 0 else {})
            for i in range(n)]
        return capa

    def test_setup_unico_mantem_os_atalhos(self):
        """``capa.acessorios``/``preparo`` continuam falando do primeiro setup."""
        capa = capa_pdf.Capa(nome="TESTE")
        capa.acessorios = "TRAVESSEIRO"
        capa.preparo = {"BEXIGA": "Cheia"}
        capa.fotos_posicionamento = [b"x"]
        self.assertEqual(capa.setups[0].acessorios, "TRAVESSEIRO")
        self.assertEqual(capa.setups[0].preparo["BEXIGA"], "Cheia")
        self.assertEqual(capa.acessorios, "TRAVESSEIRO")
        self.assertEqual(len(capa.fotos_posicionamento), 1)

    def test_os_dois_setups_saem_impressos(self):
        texto = _texto(capa_pdf.gerar(self._capa(2)))
        for esperado in ("SETUP0", "SETUP1", "ACESSORIO 0", "ACESSORIO 1"):
            self.assertIn(esperado, texto, f"não saiu impresso: {esperado!r}")

    def test_preparo_de_cada_setup_e_o_seu(self):
        """Fundir os dois numa linha mandaria montar errado metade das sessões."""
        capa = self._capa(2)
        texto = _texto(capa_pdf.gerar(capa))
        # O primeiro tem braços sobre o tórax; o segundo, não. A linha BRAÇOS
        # aparece porque vale para UM deles — some só quando não vale para
        # nenhum. E o "N/A" do que não se aplica deixou de ser impresso: eram
        # cinco linhas para dizer, em geral, uma coisa.
        self.assertIn("Sobre Tórax", texto)
        self.assertIn("BRAÇOS", texto)
        self.assertNotIn("JEJUM", texto, "linha sem valor em setup nenhum")

    def test_setup_alem_do_limite_nao_cabe_e_e_avisado(self):
        # O que passa de MAX_SETUPS é descartado por ``setups_impressos`` — a
        # tela avisa (ver ``posicionamento._avisar_setups``), a folha não mente.
        extra = capa_pdf.MAX_SETUPS
        capa = self._capa(extra + 1)
        self.assertEqual(len(capa.setups_impressos()), capa_pdf.MAX_SETUPS)
        texto = _texto(capa_pdf.gerar(capa))
        self.assertIn("SETUP0", texto)                  # o primeiro sai
        self.assertNotIn(f"SETUP{extra}", texto)        # o excedente, não

    def test_celula_de_preparo_nunca_sai_em_branco(self):
        """Em branco lê-se como "esqueceram de preencher".

        Espiona o desenho do quadro em vez de contar "N/A" no texto da folha: a
        legenda do Checklist ("N/A: não se aplica") e o cabeçalho da coluna N/A
        também dizem N/A, e a contagem passou a medir a coisa errada.
        """
        import io as _io

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as _canvas

        f = capa_pdf._Folha(_canvas.Canvas(_io.BytesIO(), pagesize=A4))
        valores = []
        original = capa_pdf._Folha.txt_centro

        def espiao(self, x0, x1, topo, texto, *a, **k):
            valores.append(str(texto))
            return original(self, x0, x1, topo, texto, *a, **k)

        capa_pdf._Folha.txt_centro = espiao
        try:
            # (x0, x1, y0, y_cab, y_itens, y1) — com um setup só não há
            # linha de nomes, então y_itens == y_cab.
            com_preparo = capa_dados.Setup(nome="X")
            com_preparo.preparo = {"BEXIGA": "Cheia", "JEJUM": "4h"}
            capa_pdf._preparo_p2(f, [com_preparo],
                                 330.0, 579.3, 500.0, 518.0, 518.0, 600.0)
        finally:
            capa_pdf._Folha.txt_centro = original
        self.assertEqual(len(valores), 2, "só as duas que se aplicam")
        self.assertTrue(all(v.strip() for v in valores), valores)
        self.assertNotIn(capa_pdf.VAZIO, valores)

    def test_sem_preparo_nenhum_o_quadro_nao_entra(self):
        """Saía a moldura com a divisória, a coluna de valores vazia e um
        "Sem preparo específico" no canto — meia faixa de quadro para dizer que
        não há o que dizer, no caso que é a MAIORIA."""
        capa = capa_pdf.Capa(nome="X", registro="1X")
        capa.setups = [capa_dados.Setup(nome="X")]
        texto = _texto(capa_pdf.gerar(capa))
        self.assertNotIn("PREPARO", texto)
        for col in capa_pdf.PREPARO_NA_CONTRACAPA:
            self.assertNotIn(col, texto, f"{col} não se aplica e saiu")

    def test_sem_preparo_os_acessorios_ocupam_a_faixa_inteira(self):
        """Sem o quadro ao lado, a lista de acessórios herda a largura dele —
        deixar o vão aberto só trocaria um retângulo vazio por outro."""
        chamadas = []
        original = capa_pdf._acessorios_p2

        def espiao(f, setups, x0, x1, *a, **k):
            chamadas.append((x0, x1))
            return original(f, setups, x0, x1, *a, **k)

        capa_pdf._acessorios_p2 = espiao
        try:
            sem = capa_dados.Setup(nome="X")
            com = capa_dados.Setup(nome="X")
            com.preparo = {"BEXIGA": "Cheia"}
            for setup in (sem, com):
                capa = capa_pdf.Capa(nome="X", registro="1X")
                capa.setups = [setup]
                capa_pdf.gerar(capa)
        finally:
            capa_pdf._acessorios_p2 = original
        (x0_sem, x1_sem), (x0_com, x1_com) = chamadas
        self.assertEqual(x0_sem, x0_com)                 # mesma borda esquerda
        self.assertGreater(x1_sem, x1_com + 100.0)       # herdou o quadro todo

    def test_decubito_nao_se_repete_na_contracapa(self):
        # A pág. 2 da Ficha Técnica já traz a coluna "Posicionamento" (decúbito
        # + para onde vai a cabeça), lida do DICOM, e as duas folhas andam
        # grampeadas. Duas versões da mesma verdade é uma a mais.
        self.assertIn("DECÚBITO", capa_pdf.COLUNAS_PREPARO)
        self.assertNotIn("DECÚBITO", capa_pdf.PREPARO_NA_CONTRACAPA)
        capa = capa_pdf.Capa(nome="TESTE")
        capa.setups = [capa_dados.Setup(nome="X", preparo={"DECÚBITO": "Ventral"})]
        texto = _texto(capa_pdf.gerar(capa))
        self.assertNotIn("DECÚBITO", texto)
        self.assertNotIn("Ventral", texto)

    def test_checklist_veio_para_a_contracapa(self):
        # Saiu da pág. 2 da Ficha Técnica e chegou aqui INTEIRO: itens, colunas
        # de marcação e legenda.
        texto = _texto(capa_pdf.gerar(capa_pdf.Capa(nome="TESTE")))
        self.assertIn("CHECKLIST PRÉ-TRATAMENTO", texto)
        for item in capa_pdf.CHECKLIST_ITENS:
            self.assertIn(item, texto, item)
        self.assertIn("conforme", texto)

    def test_exames_e_o_ultimo_bloco_antes_do_carimbo(self):
        # Com preparo de verdade: sem nenhum, o quadro PREPARO não entra (é o
        # caso da maioria) e não haveria o que ordenar.
        capa = capa_pdf.Capa(nome="TESTE")
        capa.setups = [capa_dados.Setup(nome="X", preparo={"BEXIGA": "Cheia"})]
        texto = _texto(capa_pdf.gerar(capa))
        ordem = ["ACESSÓRIOS", "PREPARO", "CHECKLIST PRÉ-TRATAMENTO",
                 "EXAMES COMPLEMENTARES?", "CARIMBO E ASSINATURA"]
        posicoes = [texto.find(bloco) for bloco in ordem]
        self.assertNotIn(-1, posicoes, f"bloco faltando: {ordem}")
        self.assertEqual(posicoes, sorted(posicoes), ordem)

    def test_exames_sai_unificado_numa_linha_so(self):
        texto = _texto(capa_pdf.gerar(capa_pdf.Capa(nome="TESTE")))
        for coluna in ("EXAMES COMPLEMENTARES?", "QUANTIDADE", "DEVOLVIDO POR",
                       "DATA", "ASSINATURA PACIENTE"):
            self.assertIn(coluna, texto, coluna)
