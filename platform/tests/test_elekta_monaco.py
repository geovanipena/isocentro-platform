"""Compatibilidade com os DICOM do Monaco (Elekta).

O Monaco exporta diferente do Eclipse/ARIA (Varian) em quatro pontos que
quebravam a ficha, todos observados nos casos de TCs_Teste/Elekta:

1. arquivo CRU — sem preâmbulo, sem "DICM" e sem o grupo 0002 (File Meta), o
   que impedia o pydicom de decodificar TC, RT Dose e RT Image;
2. um RT Dose por FEIXE além da soma do plano;
3. mesa e pontos de referência como ROIs (SUPPORT/MARKER), que entravam no DVH;
4. planos sem os Table Top Setup Displacements, com o TP0 só como ROI marcador.
"""
import io
import os
import sys
import unittest

import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ImplicitVRLittleEndian

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isocentro.adaptadores.dicom import leitura  # noqa: E402
from isocentro.dados import equipe  # noqa: E402
from isocentro.dicom import dicom_rt  # noqa: E402

_LISTAS = {"fisicos": equipe.FISICOS, "medicos": equipe.MEDICOS}
from isocentro.papel import ficha_pdf as fp  # noqa: E402


def _bytes_sem_file_meta() -> bytes:
    """Um dataset gravado CRU (implicit VR LE, sem preâmbulo/DICM), como o Monaco."""
    ds = Dataset()
    ds.PatientName = "TESTE^ELEKTA"
    ds.PatientID = "13816"
    ds.Modality = "CT"
    ds.Rows = 2
    ds.Columns = 2
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 1
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = (1000).to_bytes(2, "little") * 4
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=False, little_endian=True, implicit_vr=True)
    return buf.getvalue()


class TestArquivoSemFileMeta(unittest.TestCase):

    def test_pydicom_puro_nao_decodifica(self):
        """A raiz do problema: sem (0002,0010) o pydicom recusa os pixels."""
        ds = pydicom.dcmread(io.BytesIO(_bytes_sem_file_meta()), force=True)
        ds.file_meta = FileMetaDataset()          # como o arquivo cru chega
        with self.assertRaises(AttributeError):
            _ = ds.pixel_array

    def test_carregar_repoe_o_transfer_syntax(self):
        ds = leitura.carregar(_bytes_sem_file_meta(), stop_before_pixels=False)
        self.assertEqual(ds.file_meta.TransferSyntaxUID, ImplicitVRLittleEndian)
        self.assertEqual(ds.pixel_array.shape, (2, 2))   # decodifica de verdade

    def test_nao_mexe_em_arquivo_que_ja_tem_meta(self):
        buf = io.BytesIO()
        ds = pydicom.dcmread(io.BytesIO(_bytes_sem_file_meta()), force=True)
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
        ds.save_as(buf, enforce_file_format=False, little_endian=True, implicit_vr=False)
        lido = leitura.carregar(buf.getvalue())
        self.assertEqual(lido.file_meta.TransferSyntaxUID,
                         pydicom.uid.ExplicitVRLittleEndian)


def _fake_plano(uid: str) -> Dataset:
    ds = Dataset()
    ds.SOPInstanceUID = uid
    ds.RTPlanLabel = "01_A"
    ds.BeamSequence = Sequence([])
    return ds


def _fake_dose(uid_plano: str, soma: str) -> Dataset:
    ds = Dataset()
    ds.DoseSummationType = soma
    ref = Dataset(); ref.ReferencedSOPInstanceUID = uid_plano
    ds.ReferencedRTPlanSequence = Sequence([ref])
    return ds


class TestDosePorFeixe(unittest.TestCase):
    """O Monaco exporta ``_Dose.dcm`` (PLAN) + ``_Dose_RxA_BmN.dcm`` (BEAM),
    todos apontando para o mesmo plano."""

    def test_prefere_a_dose_do_plano(self):
        p = _fake_plano("1.2.3")
        beams = [_fake_dose("1.2.3", "BEAM") for _ in range(3)]
        plano = _fake_dose("1.2.3", "PLAN")
        # A dose do plano chega DEPOIS das de feixe (ordem do disco).
        b = dicom_rt.agrupar_planos([p], [], beams + [plano], **_LISTAS)[0]
        self.assertIs(b["rd_ds"], plano)

    def test_sem_dose_de_plano_usa_a_que_houver(self):
        p = _fake_plano("1.2.3")
        beam = _fake_dose("1.2.3", "BEAM")
        b = dicom_rt.agrupar_planos([p], [], [beam], **_LISTAS)[0]
        self.assertIs(b["rd_ds"], beam)


def _fake_rs(estruturas, pontos=None):
    """RS mínimo a partir de [(num, nome, tipo, tem_contorno)].

    ``pontos``: {num: [(x, y, z), ...]} com o contorno real da ROI."""
    rs = Dataset()
    rois, contornos, obs = [], [], []
    for num, nome, tipo, tem in estruturas:
        r = Dataset(); r.ROINumber = num; r.ROIName = nome; rois.append(r)
        rc = Dataset(); rc.ReferencedROINumber = num
        itens = []
        if tem:
            c = Dataset()
            xyz = (pontos or {}).get(num)
            if xyz:
                c.ContourData = [v for p in xyz for v in p]
            itens.append(c)
        rc.ContourSequence = Sequence(itens)
        contornos.append(rc)
        o = Dataset(); o.ReferencedROINumber = num
        o.RTROIInterpretedType = tipo; obs.append(o)
    rs.StructureSetROISequence = Sequence(rois)
    rs.ROIContourSequence = Sequence(contornos)
    rs.RTROIObservationsSequence = Sequence(obs)
    return rs


class TestEstruturasDoMonaco(unittest.TestCase):

    def test_mesa_e_marcadores_ficam_fora_do_dvh(self):
        rs = _fake_rs([
            (1, "patient", "EXTERNAL", True),
            (2, "RETO", "ORGAN", True),
            (3, "Foam Core", "SUPPORT", True),      # mesa
            (4, "Carbon Fiber", "SUPPORT", True),   # mesa
            (5, "TP0", "MARKER", True),             # ponto de referência
            (6, "ISO TTO", "MARKER", True),
        ])
        self.assertEqual(fp._estruturas_para_dvh(rs), ["RETO"])

    def test_alvo_entra_mesmo_vindo_depois_dos_orgaos(self):
        # Ordem do Monaco: os PTVs vêm no fim; com limite 8 o alvo sumia.
        est = [(i, f"OAR{i}", "ORGAN", True) for i in range(1, 12)]
        est.append((99, "PTV 36.25Gy", "PTV", True))
        nomes = fp._estruturas_para_dvh(_fake_rs(est), limite=8)
        self.assertEqual(nomes[0], "PTV 36.25Gy")
        self.assertEqual(len(nomes), 8)


class TestTP0SemDeslocamento(unittest.TestCase):
    """Planos do Monaco sem (300A,01D2/01D4/01D6): o TP0 vem como ROI MARKER."""

    def _rs_com_tp0(self, nome="TP0"):
        return _fake_rs(
            [(1, "CORPO", "EXTERNAL", True), (2, nome, "MARKER", True)],
            pontos={2: [(0.4, -26.5, -825.0)]})

    def test_le_o_marcador(self):
        c = dicom_rt.marcador_tp0(self._rs_com_tp0())
        self.assertEqual([round(v, 1) for v in c], [0.4, -26.5, -825.0])

    def test_aceita_sufixo_no_nome(self):
        c = dicom_rt.marcador_tp0(self._rs_com_tp0("TP0 SSD 100 cm"))
        self.assertIsNotNone(c)

    def test_deriva_o_deslocamento_e_fecha_a_volta(self):
        rp = {"iso_pos_mm": [11.3, -37.4, -835.0], "patient_position": "HFS",
              "desl_lat": None, "desl_long": None, "desl_vert": None,
              "maquina": "Synergy01"}
        self.assertTrue(dicom_rt.completar_deslocamentos(rp, self._rs_com_tp0()))
        volta = dicom_rt._tp0_coords(rp["iso_pos_mm"], rp["desl_lat"],
                                     rp["desl_long"], rp["desl_vert"], "HFS")
        self.assertEqual([round(v, 1) for v in volta], [0.4, -26.5, -825.0])

    def test_nao_sobrescreve_o_que_o_plano_traz(self):
        rp = {"iso_pos_mm": [11.3, -37.4, -835.0], "patient_position": "HFS",
              "desl_lat": 1.5, "desl_long": 3.5, "desl_vert": 2.5,
              "maquina": "Synergy01"}
        self.assertFalse(dicom_rt.completar_deslocamentos(rp, self._rs_com_tp0()))
        self.assertEqual((rp["desl_lat"], rp["desl_long"], rp["desl_vert"]),
                         (1.5, 3.5, 2.5))

    def test_sem_marcador_nao_inventa(self):
        rp = {"iso_pos_mm": [0, 0, 0], "patient_position": "HFS",
              "desl_lat": None, "desl_long": None, "desl_vert": None}
        rs = _fake_rs([(1, "CORPO", "EXTERNAL", True)])
        self.assertFalse(dicom_rt.completar_deslocamentos(rp, rs))
        self.assertIsNone(rp["desl_lat"])


def _fake_feixe(cunhas=None, fora=()):
    """Feixe com WedgeSequence e a posição delas no 1º ponto de controle.

    ``cunhas``: [(numero, wedge_id, angulo)]; ``fora``: números retirados."""
    beam = Dataset()
    seq = []
    for num, wid, ang in (cunhas or []):
        w = Dataset(); w.WedgeNumber = num
        if wid:
            w.WedgeID = wid
        if ang is not None:
            w.WedgeAngle = ang
        seq.append(w)
    beam.WedgeSequence = Sequence(seq)
    cp0 = Dataset()
    pos = []
    for num, *_ in (cunhas or []):
        p = Dataset(); p.ReferencedWedgeNumber = num
        p.WedgePosition = "OUT" if num in fora else "IN"
        pos.append(p)
    cp0.WedgePositionSequence = Sequence(pos)
    return beam, cp0


class TestFiltro(unittest.TestCase):
    """O Monaco usa cunha motorizada nos campos 3D (W15…W60)."""

    def test_sem_cunha(self):
        b, cp = _fake_feixe()
        self.assertEqual(dicom_rt._filtro_do_feixe(b, cp), "-")

    def test_cunha_no_campo_sai_pelo_id(self):
        b, cp = _fake_feixe([(1, "W60", "60")])
        self.assertEqual(dicom_rt._filtro_do_feixe(b, cp), "W60")

    def test_cunha_retirada_nao_conta(self):
        b, cp = _fake_feixe([(1, "W60", "60")], fora=(1,))
        self.assertEqual(dicom_rt._filtro_do_feixe(b, cp), "-")

    def test_sem_id_cai_no_angulo(self):
        b, cp = _fake_feixe([(1, "", "45")])
        self.assertEqual(dicom_rt._filtro_do_feixe(b, cp), "45°")

    def test_cunha_que_entra_depois_do_primeiro_segmento_conta(self):
        # Cunha MOTORIZADA: o campo tem um segmento aberto e outro com ela. Olhando
        # só o CP0, um campo entregue COM cunha saía com "-" na linha Filtro.
        b, cp0 = _fake_feixe([(1, "W60", "60")], fora=(1,))
        _, cp_in = _fake_feixe([(1, "W60", "60")])       # cunha DENTRO no 2º CP
        b.ControlPointSequence = Sequence([cp0, cp_in])
        self.assertEqual(dicom_rt._filtro_do_feixe(b, cp0), "W60")

    def test_cunha_out_em_todos_os_pontos_segue_retirada(self):
        b, cp0 = _fake_feixe([(1, "W60", "60")], fora=(1,))
        _, cp1 = _fake_feixe([(1, "W60", "60")], fora=(1,))
        b.ControlPointSequence = Sequence([cp0, cp1])
        self.assertEqual(dicom_rt._filtro_do_feixe(b, cp0), "-")


class TestLinhaFiltroNaFicha(unittest.TestCase):
    """Na Elekta a linha "Tabela" (tolerance table) dá lugar a "Filtro"."""

    _ELEKTA = {"fabricante": "Elekta Solutions AB"}
    _VARIAN = {"fabricante": "Varian Medical Systems"}

    def test_elekta_troca_tabela_por_filtro(self):
        linhas = fp.linhas_campos(self._ELEKTA)
        self.assertIn(("Filtro", "filtro"), linhas)
        self.assertNotIn(("Tabela", "tabela"), linhas)
        self.assertEqual(len(linhas), len(fp.CAMPOS_LINHAS))

    def test_varian_mantem_tabela(self):
        self.assertEqual(fp.linhas_campos(self._VARIAN), fp.CAMPOS_LINHAS)

    def test_ficha_antiga_sem_fabricante_mantem_tabela(self):
        self.assertEqual(fp.linhas_campos({}), fp.CAMPOS_LINHAS)

    def test_multi_plano_basta_um_da_elekta(self):
        # A tabela da pág. 2 é uma só: se um plano é do Monaco, a linha é Filtro.
        linhas = fp.linhas_campos([self._VARIAN, self._ELEKTA])
        self.assertIn(("Filtro", "filtro"), linhas)


def _plano_com_equipe(fabricante, revisor="", operador="", medico_registro=""):
    ds = Dataset()
    ds.Manufacturer = fabricante
    if revisor:
        ds.ReviewerName = revisor
    if operador:
        ds.OperatorsName = operador
    if medico_registro:
        ds.PhysiciansOfRecord = medico_registro
    ds.BeamSequence = Sequence([])
    return ds


class TestEquipeNoMonaco(unittest.TestCase):
    """Quem é quem troca de campo entre os dois TPS: no Monaco quem APROVA
    (ReviewerName) é o médico, e o físico é o usuário gravado no RT Struct."""

    def test_revisor_do_monaco_e_medico(self):
        rp = dicom_rt.parse_rtplan(
            _plano_com_equipe("Elekta Solutions AB", revisor="Fernando Rezende"),
            **_LISTAS)
        self.assertEqual(rp["medico"], "Fernando Batista Rezende")
        self.assertEqual(rp["fisico"], "")     # não é o físico

    def test_revisor_do_eclipse_segue_como_fisico(self):
        rp = dicom_rt.parse_rtplan(
            _plano_com_equipe("Varian Medical Systems",
                              revisor="Geovani Pires Pena",
                              medico_registro="Teixeira de Prado^Jean"),
            **_LISTAS)
        self.assertEqual(rp["medico"], "Jean Teixeira de Prado")
        self.assertEqual(rp["fisico"], "Geovani Pires Pena")

    def test_fisico_vem_do_login_no_rt_struct(self):
        rs = Dataset(); rs.OperatorsName = "adriano"
        rp = {"fisico": ""}
        self.assertTrue(dicom_rt.completar_equipe(rp, rs, **_LISTAS))
        self.assertEqual(rp["fisico"], "Adriano Henrique Dal Moro")

    def test_login_irreconhecivel_nao_vira_nome(self):
        rs = Dataset(); rs.OperatorsName = "test"
        rp = {"fisico": ""}
        self.assertFalse(dicom_rt.completar_equipe(rp, rs, **_LISTAS))
        self.assertEqual(rp["fisico"], "")

    def test_nao_sobrescreve_fisico_do_plano(self):
        rs = Dataset(); rs.OperatorsName = "adriano"
        rp = {"fisico": "Mario Sergio"}
        self.assertFalse(dicom_rt.completar_equipe(rp, rs, **_LISTAS))
        self.assertEqual(rp["fisico"], "Mario Sergio")


class TestEquipePorMaquina(unittest.TestCase):
    """O Synergy é do SAT e tem equipe própria: a ficha dele oferece SÓ ela, e as
    demais máquinas (Clinica) oferecem só o resto. Ninguém aparece nas duas."""

    _SAT_MEDICOS = ("Camila Sampaio", "Fernando Batista Rezende")
    _SAT_FISICOS = ("Adriano Henrique Dal Moro", "Isabela Lacerda")
    _OUTRAS = ("TrueBeamSN1001", "TBuniverSN1002", "600CD", "6EX")

    def test_synergy_oferece_so_a_equipe_do_sat(self):
        self.assertEqual(equipe.equipe_da_maquina(equipe.MEDICOS, "Synergy01"),
                         list(self._SAT_MEDICOS))
        self.assertEqual(equipe.equipe_da_maquina(equipe.FISICOS, "Synergy01"),
                         list(self._SAT_FISICOS))

    def test_equipe_do_sat_nao_aparece_nas_outras_maquinas(self):
        for maq in self._OUTRAS:
            medicos = equipe.equipe_da_maquina(equipe.MEDICOS, maq)
            fisicos = equipe.equipe_da_maquina(equipe.FISICOS, maq)
            for nome in self._SAT_MEDICOS:
                self.assertNotIn(nome, medicos, maq)
            for nome in self._SAT_FISICOS:
                self.assertNotIn(nome, fisicos, maq)

    def test_equipe_da_clinica_some_no_synergy(self):
        self.assertNotIn("Geovani Pires Pena",
                         equipe.equipe_da_maquina(equipe.FISICOS, "Synergy01"))
        self.assertNotIn("Jean Teixeira de Prado",
                         equipe.equipe_da_maquina(equipe.MEDICOS, "Synergy01"))
        for maq in self._OUTRAS:
            self.assertIn("Geovani Pires Pena",
                          equipe.equipe_da_maquina(equipe.FISICOS, maq), maq)

    def test_as_duas_listas_somadas_dao_a_lista_inteira(self):
        for nomes in (equipe.MEDICOS, equipe.FISICOS):
            sat = equipe.equipe_da_maquina(nomes, "Synergy01")
            clinica = equipe.equipe_da_maquina(nomes, "TrueBeamSN1001")
            self.assertEqual(sorted(sat + clinica), sorted(nomes))

    def test_sem_maquina_oferece_a_lista_inteira(self):
        self.assertEqual(equipe.equipe_da_maquina(equipe.MEDICOS, ""),
                         list(equipe.MEDICOS))
        self.assertEqual(equipe.equipe_da_maquina(equipe.FISICOS, None),
                         list(equipe.FISICOS))

    def test_nome_apagado_no_cadastro_nao_volta_pelo_filtro(self):
        # Quem monta a lista é o cadastro (gui._cadastro_equipe), que já mescla a
        # canônica: um nome que falta aqui é um nome APAGADO em Configurações →
        # Equipe. Repor por conta própria fazia a 🗑 não surtir efeito nenhum.
        sem_camila = [n for n in equipe.MEDICOS if n != "Camila Sampaio"]
        self.assertEqual(equipe.equipe_da_maquina(sem_camila, "Synergy01"),
                         ["Fernando Batista Rezende"])

    def test_nome_acrescentado_pelo_usuario_aparece_no_synergy(self):
        # Nome que não está em nenhuma lista canônica foi cadastrado em
        # Configurações → Equipe: não há como saber de que unidade é, e escondê-lo
        # do Synergy significava nunca poder assinar uma ficha do SAT.
        novo = "Fulano de Tal Recem Cadastrado"
        nomes = list(equipe.MEDICOS) + [novo]
        self.assertIn(novo, equipe.equipe_da_maquina(nomes, "Synergy01"))
        self.assertIn(novo, equipe.equipe_da_maquina(nomes, "TrueBeamSN1001"))


class TestAprovacaoDoPlano(unittest.TestCase):
    """No Monaco o nome do médico é o ReviewerName, que só existe DEPOIS da
    aprovação: plano UNAPPROVED chega legitimamente sem médico."""

    def test_plano_aprovado_traz_o_medico(self):
        ds = _plano_com_equipe("Elekta Solutions AB", revisor="Camila Sampaio")
        ds.ApprovalStatus = "APPROVED"
        rp = dicom_rt.parse_rtplan(ds, **_LISTAS)
        self.assertEqual(rp["medico"], "Camila Sampaio")
        self.assertEqual(rp["aprovacao"], "APPROVED")

    def test_plano_nao_aprovado_vem_sem_medico_e_diz_por_que(self):
        # Sem aprovação o Monaco não grava ReviewerName: não há o que puxar, e o
        # status é o que permite explicar o campo vazio (ver
        # gui._avisar_medico_sem_aprovacao).
        ds = _plano_com_equipe("Elekta Solutions AB")
        ds.ApprovalStatus = "UNAPPROVED"
        rp = dicom_rt.parse_rtplan(ds, **_LISTAS)
        self.assertEqual(rp["medico"], "")
        self.assertEqual(rp["aprovacao"], "UNAPPROVED")


class TestUnidadeDaPessoa(unittest.TestCase):
    """A unidade é um dado da PESSOA (editável em Configurações → Equipe), não
    uma lista fechada no código: contratar alguém não pode exigir republicar o
    executável."""

    def test_padrao_de_fabrica(self):
        self.assertEqual(equipe.unidade_da_pessoa("Camila Sampaio"), "SAT")
        self.assertEqual(equipe.unidade_da_pessoa("Geovani Pires Pena"),
                         "Clinica")

    def test_desconhecido_nao_tem_unidade_e_aparece_em_todas(self):
        self.assertEqual(equipe.unidade_da_pessoa("Fulano Novo"), "")
        for maq in ("Synergy01", "TrueBeamSN1001"):
            self.assertIn("Fulano Novo",
                          equipe.equipe_da_maquina(["Fulano Novo"], maq), maq)

    def test_cadastro_vence_o_padrao_de_fabrica(self):
        unid = {"Jean Teixeira de Prado": "SAT"}
        self.assertEqual(
            equipe.unidade_da_pessoa("Jean Teixeira de Prado", unid), "SAT")
        self.assertIn("Jean Teixeira de Prado",
                      equipe.equipe_da_maquina(equipe.MEDICOS, "Synergy01",
                                                 unid))
        self.assertNotIn("Jean Teixeira de Prado",
                         equipe.equipe_da_maquina(equipe.MEDICOS,
                                                    "TrueBeamSN1001", unid))

    def test_cadastro_tambem_solta_alguem_do_sat(self):
        # Marcar "Todas" (unidade vazia) põe a pessoa em qualquer acelerador.
        unid = {"Camila Sampaio": ""}
        for maq in ("Synergy01", "TrueBeamSN1001", "600CD"):
            self.assertIn("Camila Sampaio",
                          equipe.equipe_da_maquina(equipe.MEDICOS, maq,
                                                     unid), maq)

    def test_maquina_desconhecida_oferece_a_lista_inteira(self):
        # Sem saber a unidade da máquina, esconder nome é o pior dos erros.
        self.assertEqual(
            equipe.equipe_da_maquina(equipe.MEDICOS, "Acelerador Novo"),
            list(equipe.MEDICOS))

    def test_outra_grafia_da_mesma_pessoa_herda_a_unidade(self):
        # O cadastro de cada serviço traz o nome completo; a lista canônica, a
        # forma curta. Sem herdar, o nome longo escaparia do filtro por unidade.
        longo = "Camila Sampaio de Oliveira"
        self.assertEqual(dicom_rt.mesma_pessoa(longo, equipe.MEDICOS),
                         "Camila Sampaio")
        self.assertEqual(equipe.unidade_da_pessoa(longo), "SAT")
        self.assertNotIn(longo, equipe.equipe_da_maquina([longo], "600CD"))

    def test_nao_confunde_quem_so_divide_o_primeiro_nome(self):
        # "Nathalia Ramalho Ogawa" (médica) e "Nathalia Bittencourt" (física) têm um
        # token em comum — não são a mesma pessoa.
        self.assertEqual(
            dicom_rt.mesma_pessoa("Nathalia Bittencourt", ["Nathalia Ramalho Ogawa"]), "")

    def test_um_token_so_nao_afirma_nada(self):
        # Um primeiro nome solto casa com meia lista; para unidade e para
        # deduplicar cadastro, isso engoliria gente de verdade.
        self.assertEqual(dicom_rt.mesma_pessoa("Camila", equipe.MEDICOS), "")
        self.assertEqual(equipe.unidade_da_pessoa("Camila"), "")

    def test_synergy_e_a_unica_maquina_do_sat(self):
        from isocentro.dominio import constantes
        sat = [m.chave for m in constantes.MAQUINAS if m.unidade == "SAT"]
        self.assertEqual(sat, ["Synergy01"])


class TestUnificarGrafias(unittest.TestCase):
    """A mesma pessoa escrita de dois jeitos vira UMA entrada, com o nome mais
    completo — o combo mostrava as duas (a da lista canônica e a do cadastro)."""

    def test_fica_o_nome_mais_completo_venha_de_onde_vier(self):
        # Ora ganha o do cadastro, ora o da lista canônica: o critério é o nome,
        # não a origem.
        self.assertEqual(
            dicom_rt.unificar_grafias(["Ana Fatima Albuquerque",
                                       "Ana Fátima de Paula Brandao Albuquerque"]),
            ["Ana Fátima de Paula Brandao Albuquerque"])
        self.assertEqual(
            dicom_rt.unificar_grafias(["Lais Toscano Mayer João", "Lais Toscano Mayer"]),
            ["Lais Toscano Mayer João"])
        self.assertEqual(
            dicom_rt.unificar_grafias(["Lais Toscano Mayer", "Lais Toscano Mayer João"]),
            ["Lais Toscano Mayer João"])

    def test_nao_junta_pessoas_diferentes(self):
        nomes = ["Lais Toscano Mayer", "Nicole Mayer Arruda Falcao",
                 "Nathalia Ramalho Ogawa", "Nathalia Bittencourt"]
        self.assertEqual(dicom_rt.unificar_grafias(nomes), nomes)

    def test_unificar_a_lista_canonica_com_o_cadastro(self):
        # O caso real: juntar as duas listas mostrava a mesma médica duas vezes.
        cadastro = ["Ana Fátima de Paula Brandao Albuquerque", "Lais Toscano Mayer"]
        lista = dicom_rt.unificar_grafias(list(equipe.MEDICOS) + cadastro)
        self.assertEqual(len(lista), len(equipe.MEDICOS))
        self.assertEqual([n for n in lista if "Albuquerque" in n],
                         ["Ana Fátima de Paula Brandao Albuquerque"])
        self.assertEqual([n for n in lista if n.startswith("Lais")],
                         ["Lais Toscano Mayer João"])


class TestOrdemAlfabetica(unittest.TestCase):
    """As listas de equipe crescem por acréscimo (nome novo no fim); quem as lê
    tem de receber em ordem alfabética, com acento comparando como sem."""

    def test_listas_canonicas_estao_em_ordem(self):
        for nomes in (equipe.MEDICOS, equipe.FISICOS):
            self.assertEqual(list(nomes), dicom_rt.ordem_alfabetica(nomes))

    def test_acento_nao_joga_o_nome_para_o_fim(self):
        # Por code point, "Á" e "T" com til vêm depois de "Z".
        nomes = ["Zuleica Alves", "Thaís Franco Sartori", "Ávila Nunes"]
        self.assertEqual(dicom_rt.ordem_alfabetica(nomes),
                         ["Ávila Nunes", "Thaís Franco Sartori",
                          "Zuleica Alves"])

    def test_caixa_nao_conta(self):
        self.assertEqual(dicom_rt.ordem_alfabetica(["bruno", "Ana", "carlos"]),
                         ["Ana", "bruno", "carlos"])

    def test_nome_novo_entra_no_lugar_alfabetico(self):
        # Nome cadastrado depois (vem no fim do arquivo) não sai solto no fim.
        med = equipe.equipe_da_maquina(
            list(equipe.MEDICOS) + ["Alvaro Recem Chegado"], "600CD")
        self.assertEqual(med, dicom_rt.ordem_alfabetica(med))
        self.assertEqual(med[0], "Alvaro Recem Chegado")

    def test_lista_da_maquina_sai_ordenada(self):
        for maq in ("Synergy01", "TrueBeamSN1001", "600CD", ""):
            for nomes in (equipe.MEDICOS, equipe.FISICOS):
                fora_de_ordem = list(reversed(nomes))
                saida = equipe.equipe_da_maquina(fora_de_ordem, maq)
                self.assertEqual(saida, dicom_rt.ordem_alfabetica(saida), maq)


class TestMaquinaSynergy(unittest.TestCase):

    def test_cadastrada_com_a_mesa_do_truebeam(self):
        from isocentro.dominio import constantes
        m = constantes.identificar_maquina("Synergy01")
        self.assertIsNotNone(m)
        self.assertEqual(m.grupo_mesa, "TB")       # mesmo desenho do TrueBeam
        self.assertEqual(m.imagem, "CBCT")         # campo de setup do Monaco
        self.assertFalse(m.mesa_vert_invertida)

    def test_ficha_do_synergy_sai_com_o_logo_do_sat(self):
        self.assertEqual(os.path.basename(fp.logo_da_maquina("Synergy01")),
                         "logo_sat.png")
        self.assertTrue(os.path.exists(fp.logo_da_maquina("Synergy01")))

    def test_demais_maquinas_seguem_com_o_institucional(self):
        for maq in ("TrueBeamSN1001", "600CD", "6EX", "Maquina Desconhecida", ""):
            self.assertEqual(fp.logo_da_maquina(maq), fp.LOGO, maq)


class TestTemaDaFicha(unittest.TestCase):
    """As págs. 2 e 3 saem na cor da unidade que trata na máquina."""

    def test_synergy_usa_o_vermelho_do_sat(self):
        self.assertIs(fp.tema_da_maquina("Synergy01"), fp.TEMA_SAT)
        self.assertEqual(fp.TEMA_SAT.forte.hexval()[2:].upper(), "ED323E")

    def test_demais_maquinas_seguem_no_verde(self):
        for maq in ("TrueBeamSN1001", "600CD", "6EX", "Desconhecida", "", None):
            self.assertIs(fp.tema_da_maquina(maq), fp.TEMA_CLINICA, maq)

    def test_cor_do_1o_plano_e_do_1o_iso_seguem_a_marca(self):
        for tema in (fp.TEMA_SAT, fp.TEMA_CLINICA):
            self.assertIs(fp._cor_plano(0, tema), tema.forte)
            self.assertIs(fp._cor_iso([{"iso_index": 0}], 0, tema), tema.forte)

    def test_demais_planos_e_isos_nao_mudam_de_unidade(self):
        # Precisam ser distinguíveis ENTRE SI, não identificar a unidade.
        for i in (1, 2, 3, 4):
            self.assertIs(fp._cor_plano(i, fp.TEMA_SAT),
                          fp._cor_plano(i, fp.TEMA_CLINICA))
        self.assertIs(fp._cor_iso([{"iso_index": 1}], 0, fp.TEMA_SAT), fp.AZUL_ISO)

    def test_amarelo_de_atencao_e_o_mesmo_nas_duas(self):
        # Gating, mesa fora do zero e bólus são aviso, não marca.
        self.assertEqual(fp.AMARELO.hexval(), fp.AMARELO.hexval())
        self.assertNotIn(fp.AMARELO, (fp.TEMA_SAT.forte, fp.TEMA_SAT.clara))


if __name__ == "__main__":
    unittest.main()
