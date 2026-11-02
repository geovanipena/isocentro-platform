"""Páginas de conferência do 600CD: reconhecimento de RT Image, seleção dos
portais de setup, renderização do DRR e inclusão das páginas na ficha."""
import io
import unittest

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from isocentro.dicom import dicom_rt
from isocentro.papel import drr
from isocentro.papel import ficha_pdf


def _rt_image(label: str, gantry: float, rotulo_extra=None) -> Dataset:
    ds = Dataset()
    ds.Modality = "RTIMAGE"
    ds.RTImageLabel = label
    ds.GantryAngle = gantry
    ds.RTImagePosition = [-32.0, 32.0]
    ds.ImagePlanePixelSpacing = [1.0, 1.0]
    ds.Rows = ds.Columns = 64
    arr = (np.linspace(0, 4000, 64 * 64).reshape(64, 64)).astype("uint16")
    ds.PixelData = arr.tobytes()
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    return ds


class TestIdentificacaoRI(unittest.TestCase):
    def test_rtimage_vira_ri(self):
        self.assertEqual(dicom_rt.identificar(_rt_image("PORTAL 0-DRR", 0)), "RI")


def _plano(uid, setup_beams, treat_beams=()):
    from pydicom.sequence import Sequence
    ds = Dataset(); ds.SOPInstanceUID = uid
    beams = []
    for n in setup_beams:
        b = Dataset(); b.BeamNumber = n; b.TreatmentDeliveryType = "SETUP"
        beams.append(b)
    for n in treat_beams:
        b = Dataset(); b.BeamNumber = n; b.TreatmentDeliveryType = "TREATMENT"
        beams.append(b)
    ds.BeamSequence = Sequence(beams)
    return ds


def _ri_ref(label, gantry, plano_uid, beam):
    from pydicom.sequence import Sequence
    ds = _rt_image(label, gantry)
    ref = Dataset(); ref.ReferencedSOPInstanceUID = plano_uid
    ds.ReferencedRTPlanSequence = Sequence([ref])
    ds.ReferencedBeamNumber = beam
    return ds


def _plano_nomeado(uid, nomes: dict):
    """Plano cujos feixes de SETUP têm ``BeamName`` — ``{numero: nome}``."""
    from pydicom.sequence import Sequence
    ds = Dataset(); ds.SOPInstanceUID = uid
    beams = []
    for numero, nome in nomes.items():
        b = Dataset()
        b.BeamNumber = numero
        b.TreatmentDeliveryType = "SETUP"
        b.BeamName = nome
        beams.append(b)
    ds.BeamSequence = Sequence(beams)
    return ds


class TestNomeDoPortal(unittest.TestCase):
    """O nome do portal vem do PLANO, porque o da imagem vem cortado.

    ``RTImageLabel`` é VR ``SH`` — dezesseis caracteres, sufixo "-DRR" incluído.
    No TC15 o feixe ``PORTAL MAMA TG`` virou ``'PORTAL MAMA -DRR'`` e o
    ``PORTAL FSC 345`` virou ``'PORTAL FSC 3-DRR'``: a folha do 600CD mandava
    conferir um portal com um nome que não existe no console.
    """

    def test_nome_inteiro_vem_do_feixe(self):
        plano = _plano_nomeado("U1", {5: "PORTAL MAMA TG"})
        ri = _ri_ref("PORTAL MAMA -DRR", 311, "U1", 5)
        self.assertEqual(dicom_rt.rotulo_drr_setup(ri, [plano]),
                         "PORTAL MAMA TG")

    def test_numero_cortado_tambem_volta_inteiro(self):
        plano = _plano_nomeado("U1", {3: "PORTAL FSC 345"})
        ri = _ri_ref("PORTAL FSC 3-DRR", 345, "U1", 3)
        self.assertEqual(dicom_rt.rotulo_drr_setup(ri, [plano]),
                         "PORTAL FSC 345")

    def test_sem_os_planos_cai_no_rotulo_da_imagem(self):
        """Cortado é melhor que vazio — Histórico antigo e acervo sem plano."""
        ri = _ri_ref("PORTAL FSC 3-DRR", 345, "U1", 3)
        self.assertEqual(dicom_rt.rotulo_drr_setup(ri), "PORTAL FSC 3")

    def test_plano_de_outro_caso_nao_batiza_o_portal(self):
        """O feixe 3 de OUTRO plano tem outro nome — casar por número só."""
        plano = _plano_nomeado("U2", {3: "PORTAL PELVE"})
        ri = _ri_ref("PORTAL FSC 3-DRR", 345, "U1", 3)
        self.assertEqual(dicom_rt.rotulo_drr_setup(ri, [plano]), "PORTAL FSC 3")

    def test_feixe_sem_nome_cai_no_rotulo(self):
        plano = _plano("U1", setup_beams=[3])          # sem BeamName
        ri = _ri_ref("PORTAL FSC 3-DRR", 345, "U1", 3)
        self.assertEqual(dicom_rt.rotulo_drr_setup(ri, [plano]), "PORTAL FSC 3")

    def test_sem_o_uid_do_plano_so_feixe_de_SETUP_batiza_o_portal(self):
        """Número de feixe REINICIA a cada plano.

        Sem o UID no RT Image, o primeiro plano com aquele número vence — e um
        feixe de TRATAMENTO acabaria dando o nome ao portal. O portal passaria a
        se chamar como um campo que não é ele, na folha que se confere com o
        paciente na mesa.
        """
        from pydicom.sequence import Sequence
        tratamento = Dataset(); tratamento.SOPInstanceUID = "U1"
        b = Dataset()
        b.BeamNumber = 3
        b.TreatmentDeliveryType = "TREATMENT"
        b.BeamName = "3 G150"
        tratamento.BeamSequence = Sequence([b])
        ri = _rt_image("PORTAL FSC 3-DRR", 345)   # sem ReferencedRTPlanSequence
        ri.ReferencedBeamNumber = 3
        self.assertEqual(dicom_rt.rotulo_drr_setup(ri, [tratamento]),
                         "PORTAL FSC 3")

    def test_sem_o_uid_o_feixe_de_setup_ainda_vale(self):
        """A tolerância continua: acervo sem a referência do plano não pode
        perder o nome inteiro por causa dela."""
        plano = _plano_nomeado("U1", {3: "PORTAL FSC 345"})
        ri = _rt_image("PORTAL FSC 3-DRR", 345)
        ri.ReferencedBeamNumber = 3
        self.assertEqual(dicom_rt.rotulo_drr_setup(ri, [plano]),
                         "PORTAL FSC 345")

    def test_o_titulo_da_pagina_usa_o_nome_inteiro(self):
        plano = _plano_nomeado("U1", {5: "PORTAL MAMA TG"})
        ri = _ri_ref("PORTAL MAMA -DRR", 311, "U1", 5)
        self.assertEqual(ficha_pdf._titulo_drr(ri, "", [plano]),
                         "DRR - Portal MAMA TG")


class TestSelecaoPortais(unittest.TestCase):
    def test_seleciona_pelos_feixes_de_setup(self):
        # mama+FSC: portais são os RI que referenciam feixes SETUP (qualquer ângulo).
        plano = _plano("U1", setup_beams=[4, 5], treat_beams=[1, 2, 3])
        ris = [_ri_ref("PORTAL 0-DRR", 0, "U1", 4),
               _ri_ref("PORTAL MAMA-DRR", 311, "U1", 5),
               _ri_ref("2 G0-DRR", 0, "U1", 3)]   # feixe de tratamento → fora
        sel = dicom_rt.selecionar_drrs_setup(ris, [plano])
        self.assertEqual([d.RTImageLabel for d in sel],
                         ["PORTAL 0-DRR", "PORTAL MAMA-DRR"])

    def test_fallback_por_portal_sem_planos(self):
        imgs = [_rt_image("PORTAL 0-DRR", 0), _rt_image("PORTAL 90-DRR", 90),
                _rt_image("7 G45-DRR", 45)]
        sel = dicom_rt.selecionar_drrs_setup(imgs)
        self.assertEqual([d.RTImageLabel for d in sel],
                         ["PORTAL 0-DRR", "PORTAL 90-DRR"])

    def test_sem_portal_sem_planos_vazio(self):
        sel = dicom_rt.selecionar_drrs_setup([_rt_image("7 G45-DRR", 0)])
        self.assertEqual(sel, [])

    def test_rotulo_do_portal(self):
        self.assertEqual(dicom_rt.rotulo_drr_setup(_rt_image("PORTAL FSC 3-DRR", 0)),
                         "PORTAL FSC 3")


class TestRenderDRR(unittest.TestCase):
    def test_gera_png(self):
        png = drr.render_drr(_rt_image("PORTAL 0-DRR", 0))
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_isocentro_no_centro(self):
        g = dicom_rt.drr_geometria(_rt_image("PORTAL 0-DRR", 0))
        self.assertAlmostEqual(g["col_iso"], 32.0)
        self.assertAlmostEqual(g["lin_iso"], 32.0)


def _dados(maquina: str) -> dict:
    # 30 frações → mapa de frações em página própria (não cabe embaixo da tabela
    # de campos nem no layout lateral), para estes testes contarem as páginas de
    # DRR/portal sem essa interação.
    return {"pac_nome": "FULANO DE TAL", "pac_registro": "123BET",
            "pac_nascimento": "01/01/1970", "eq_medico": "Dr. X",
            "eq_fisico": "Fis. Y", "maquina": maquina, "gating": "",
            "fracionamento": "1x dia", "rx_fracoes": 30}


def _store() -> dict:
    return {"RP": {"num_fracoes": 30, "feixes": [{"gantry": 0, "um": 100}]}}


def _n_paginas(pdf: bytes) -> int:
    import pypdf
    return len(pypdf.PdfReader(io.BytesIO(pdf)).pages)


class TestPaginasNaFicha(unittest.TestCase):
    def test_600cd_com_portais_anexa_drr_e_portal(self):
        sel = dicom_rt.selecionar_drrs_setup(
            [_rt_image("PORTAL 0-DRR", 0), _rt_image("PORTAL 90-DRR", 90)])
        pdf = ficha_pdf.gerar_ficha(_dados("600CD"), _store(), {"drrs": sel})
        # ficha + frações + 2 DRR + portal = 5 (600CD não é elegível a SUS).
        self.assertEqual(_n_paginas(pdf), 5)

    def test_600cd_sem_portais_anexa_so_portal(self):
        pdf = ficha_pdf.gerar_ficha(_dados("600CD"), _store(), {"drrs": []})
        self.assertEqual(_n_paginas(pdf), 3)   # ficha + frações + portal

    def test_600cd_tres_portais_tres_paginas(self):
        sel = [_rt_image("PORTAL 0-DRR", 0), _rt_image("PORTAL MAMA-DRR", 311),
               _rt_image("PORTAL FSC 3-DRR", 345)]
        pdf = ficha_pdf.gerar_ficha(_dados("600CD"), _store(), {"drrs": sel})
        self.assertEqual(_n_paginas(pdf), 6)   # ficha + frações + 3 DRR + portal

    def test_drrs_png_prontos_nao_pareiam_com_datasets(self):
        # PNGs prontos têm prioridade e NÃO são pareados por índice com a lista de
        # datasets (evita imagem/título trocados se um render tiver falhado).
        png = drr.render_drr(_rt_image("PORTAL 0-DRR", 0))
        recursos = {"drrs": [_rt_image("PORTAL 0-DRR", 0),
                             _rt_image("PORTAL MAMA-DRR", 311)],  # 2 datasets
                    "drrs_png": [png], "drrs_titulos": ["PORTAL 0"]}  # só 1 PNG
        pdf = ficha_pdf.gerar_ficha(_dados("600CD"), _store(), recursos)
        # usa só o PNG pronto → ficha + frações + 1 DRR + portal = 4
        self.assertEqual(_n_paginas(pdf), 4)

    def test_6ex_nao_recebe_paginas(self):
        # 6EX é série C, mas as páginas de conferência são só do 600CD.
        sel = dicom_rt.selecionar_drrs_setup(
            [_rt_image("PORTAL 0-DRR", 0), _rt_image("PORTAL 90-DRR", 90)])
        pdf = ficha_pdf.gerar_ficha(_dados("6EX"), _store(), {"drrs": sel})
        self.assertEqual(_n_paginas(pdf), 2)   # só ficha + frações

    def test_truebeam_nao_recebe_paginas(self):
        sel = dicom_rt.selecionar_drrs_setup(
            [_rt_image("PORTAL 0-DRR", 0), _rt_image("PORTAL 90-DRR", 90)])
        pdf = ficha_pdf.gerar_ficha(_dados("TrueBeamSN1001"), _store(), {"drrs": sel})
        self.assertEqual(_n_paginas(pdf), 2)   # só ficha + frações


class TestFolhaDePortais(unittest.TestCase):
    """A folha mudou de MOLDURA em 25/08/2026; o que ela diz não mudou.

    O pedido do usuário foi "esse layout não combina com o restante da ficha,
    mantenha a essência". Estes testes são a ESSÊNCIA: se um deles cair, a
    folha perdeu algo que quem confere o portal na sala precisa ter no papel.
    """

    def _pagina_portal(self):
        import pypdf
        pdf = ficha_pdf.gerar_ficha(_dados("600CD"), _store(), {"drrs": []})
        return pypdf.PdfReader(io.BytesIO(pdf)).pages[-1]

    def test_sai_em_RETRATO(self):
        """Passou um dia em paisagem, alinhada com as págs. 1 a 3, e voltou.

        A paisagem combinava melhor com o maço, mas a altura que sobrava só
        dava para dez portais. Numa folha de conferência a quantidade de linhas
        é a FUNÇÃO; a orientação é a forma — e a função ganha.
        """
        cx = self._pagina_portal().mediabox
        self.assertGreater(float(cx.height), float(cx.width))

    def test_saem_QUINZE_portais(self):
        """Dez era número fixo herdado do papel antigo, e foi o que fez a
        versão em paisagem ser recusada. Vinte e um, que era o que o retrato
        comportava, o usuário aparou: "21 é muito, mas o espaço para observação
        precisa ser maior"."""
        # Por LINHA do texto, não por substring: cada nº de portal sai sozinho
        # numa linha. Com substring, o "16" de "Impresso em 16/09/2026"
        # reprovava a suíte todo dia 16 (foi o que parou o robô em 16/09/2026),
        # e o "1" achava-se em qualquer data — o laço não provava nada.
        linhas = [l.strip() for l in self._pagina_portal().extract_text().splitlines()]
        for n in range(1, 16):
            with self.subTest(linha=n):
                self.assertIn(str(n), linhas)
        self.assertNotIn("16", linhas)

    def test_o_teto_de_linhas_vale_por_mais_altura_que_haja(self):
        """Sem o teto, a folha voltaria a encher de linha em branco — foi de
        onde vieram os 21."""
        for disponivel in (500.0, 700.0, 2000.0):
            with self.subTest(disponivel=disponivel):
                self.assertEqual(ficha_pdf.portal_linhas(disponivel),
                                 ficha_pdf._PORTAL_LINHAS_MAX)

    def test_com_POUCA_altura_a_folha_entrega_menos_linhas(self):
        """O teto é TETO, não promessa: se um cabeçalho crescer, a folha corta
        linhas em vez de empurrar a última para fora da página."""
        n = ficha_pdf.portal_linhas(150.0)
        self.assertLess(n, ficha_pdf._PORTAL_LINHAS_MAX)
        self.assertGreaterEqual(150.0 / n, ficha_pdf._PORTAL_ALT_MIN)

    def test_a_sobra_da_folha_vai_para_a_FAIXA_e_nao_para_a_tabela(self):
        """Era o contrário: a tabela ficava com tudo e a faixa tinha altura
        cravada. Agora a tabela pede o seu (teto × altura alvo) e o que sobra é
        da figura, da legenda e das observações — que é o que o usuário pediu.
        """
        # A tabela pede o mesmo, haja o que houver de folha.
        self.assertEqual(
            ficha_pdf._portal_altura_tabela(),
            ficha_pdf._PORTAL_CAB
            + ficha_pdf._PORTAL_LINHAS_MAX * ficha_pdf._PORTAL_ALT_ALVO)
        # E sobra faixa de verdade: mais que o piso, numa A4 retrato.
        sobra = 842 - 24 - ficha_pdf._portal_altura_tabela() - 8 - 155
        self.assertGreater(sobra, ficha_pdf._PORTAL_FAIXA_MIN)

    def test_as_seis_direcoes_ISO_continuam_com_os_MESMOS_sinais(self):
        """É a convenção de sinal a que os diagramas se referem. Trocar um
        sinal aqui manda deslocar o paciente para o lado errado — e ninguém
        confere isso contra o papel antigo depois que a folha mudou."""
        self.assertEqual(
            ficha_pdf.PORTAL_ISO,
            (("+", "Direita"), ("-", "Esquerda"), ("-", "Cabeça"),
             ("+", "Pés"), ("+", "Anterior"), ("-", "Posterior")))
        texto = self._pagina_portal().extract_text()
        for _sinal, nome in ficha_pdf.PORTAL_ISO:
            self.assertIn(nome, texto)

    def test_as_colunas_de_preenchimento_continuam_todas(self):
        texto = self._pagina_portal().extract_text()
        for rotulo in ("Realizado", "Dia", "Técnicos", "Corrigido", "Médico",
                       "Correções ISO (cm)", "OBSERVAÇÕES", "Portal"):
            with self.subTest(rotulo=rotulo):
                self.assertIn(rotulo, texto)

    def test_toda_direcao_tem_forma_CURTA_para_o_cabecalho(self):
        """Uma direção sem abreviação cai no nome inteiro e derruba o corpo do
        cabeçalho INTEIRO — ele é um só para toda a linha de rótulos.

        Foi assim que a folha ficou com rótulos de 5,5 pt: "Esquerda" numa
        coluna de 28 pt. Com "Esq." o mesmo cabeçalho sobe para ~9 pt, o corpo
        das outras tabelas da ficha.
        """
        for _sinal, nome in ficha_pdf.PORTAL_ISO:
            with self.subTest(direcao=nome):
                curto = ficha_pdf.PORTAL_ISO_CURTO.get(nome, "")
                self.assertTrue(curto, f"{nome} sem forma curta")
                self.assertLessEqual(len(curto), len(nome))

    def test_o_nome_INTEIRO_continua_na_folha_pela_legenda(self):
        """A abreviação só é honesta porque a legenda está na MESMA folha,
        logo acima da tabela, e é ela a autoridade sobre a convenção."""
        texto = self._pagina_portal().extract_text()
        for _sinal, nome in ficha_pdf.PORTAL_ISO:
            with self.subTest(direcao=nome):
                self.assertIn(nome, texto)

    def test_o_campo_GANTRY_saiu_da_folha(self):
        """Tirado a pedido do usuário em 25/08/2026.

        Ele vinha do papel antigo e era o único dado de PLANO nesta folha — e
        um dado que a ficha já traz, com um ângulo por campo, na linha "Gantry"
        da pág. 2. Aqui era uma casa só para um tratamento que tem vários:
        escrever um ângulo nela obrigava a escolher qual, e a folha não diz
        qual. A altura foi para as observações.
        """
        self.assertNotIn("GANTRY", self._pagina_portal().extract_text())

    def test_a_folha_se_NOMEIA(self):
        """Com o cabeçalho da ficha, as páginas passaram a começar iguais — e
        esta é a que se solta do maço para ficar na sala por dias."""
        self.assertIn("CONFERÊNCIA DE PORTAIS",
                      self._pagina_portal().extract_text())

    def test_a_legenda_sai_da_MESMA_tupla_que_rotula_as_colunas(self):
        """Legenda e cabeçalho discordarem sobre um sinal manda deslocar o
        paciente para o lado errado — e duas listas discordam cedo ou tarde.

        Repare no LONGITUDINAL: o positivo é o SEGUNDO nome do par (Pés). Um
        "+" fixo na primeira coluna escreveria "+ Cabeça", invertendo a
        correção no papel.
        """
        self.assertEqual(
            ficha_pdf.portal_legenda(),
            [("Lateral", "+ Direita", "−  Esquerda"),
             ("Longitudinal", "+ Pés", "−  Cabeça"),
             ("Vertical", "+ Anterior", "−  Posterior")])
        texto = self._pagina_portal().extract_text()
        for eixo in ficha_pdf.PORTAL_EIXOS:
            with self.subTest(eixo=eixo):
                self.assertIn(eixo, texto)

    def test_sem_o_diagrama_a_folha_ainda_sai(self):
        """``table_serie_c.PNG`` pode faltar num pacote mal gerado. Melhor a
        folha sem o desenho — a legenda continua lá — do que ficha nenhuma."""
        original = ficha_pdf.TABLE_SERIE_C
        ficha_pdf.TABLE_SERIE_C = "nao_existe.png"
        try:
            pdf = ficha_pdf.gerar_ficha(_dados("600CD"), _store(), {"drrs": []})
            self.assertEqual(_n_paginas(pdf), 3)
        finally:
            # GUARDA E DEVOLVE — sem isto, o resto da suíte rodaria com a ficha
            # inteira sem a imagem da mesa, e ninguém saberia.
            ficha_pdf.TABLE_SERIE_C = original


if __name__ == "__main__":
    unittest.main()
