"""Pasta com mais de um paciente não pode virar uma ficha só.

O defeito, medido em 31/08/2026 na pasta de teste do Elekta: a varredura é
RECURSIVA, e uma pasta-pai com sete pacientes produzia UMA ficha — nome e
registro do primeiro, planos de três pessoas diferentes — sem aviso nenhum na
tela. A única pista era "6 TC" na barra de status, que ninguém lê assim.

    A ficha saía em nome de: BALTA^ELDA GARCIA (13870)
      plano 1  RGH=13870  BALTA^ELDA GARCIA           ✓
      plano 2  RGH=13792  BERTOLI^ELEA ROCHA          ✗
      plano 3  RGH=13153  LEAO^ELISON L. VALENZUELA   ✗

Ficha é o que vai grampeado para a sala. O programa já filtrava por
``PatientID`` para não APAGAR o DICOM de quem nunca foi aberto
(``_excluir_arquivos_pasta``) — sabia do risco na hora de apagar e não sabia na
hora de carregar.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom  # noqa: E402
from pydicom.dataset import Dataset, FileMetaDataset  # noqa: E402
from pydicom.uid import ExplicitVRLittleEndian  # noqa: E402

from isocentro.interface import carregadores  # noqa: E402
from tests import fontes  # noqa: E402

# O QApplication nasce no IMPORT, como nos demais testes de tela desta suíte.
# Criá-lo dentro de um método de teste derrubava o processo inteiro (exit 127,
# sem mensagem): o Qt não aceita a aplicação sendo montada e desmontada no meio
# da execução, e o crash levava a suíte junto sem dizer por quê.
try:
    from PySide6.QtWidgets import QApplication

    _APP = QApplication.instance() or QApplication([])
    from isocentro.interface import gui
except Exception as exc:  # noqa: BLE001
    gui = None
    _MOTIVO = str(exc)


def _gravar(pasta: Path, nome_arq: str, registro: str, nome: str,
            modalidade: str = "CT") -> Path:
    """Um DICOM mínimo, só com o que a triagem por cabeçalho lê."""
    ds = Dataset()
    ds.PatientID = registro
    ds.PatientName = nome
    ds.Modality = modalidade
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.SOPClassUID = pydicom.uid.CTImageStorage
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    caminho = pasta / nome_arq
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    caminho.write_bytes(buf.getvalue())
    return caminho


class TestTriagemDePacientes(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="multipac_")
        self.pasta = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_acha_cada_paciente_da_pasta(self):
        """É o que permite perguntar de quem é a ficha antes de montá-la."""
        _gravar(self.pasta, "a1.dcm", "13870", "BALTA^ELDA GARCIA")
        _gravar(self.pasta, "a2.dcm", "13870", "BALTA^ELDA GARCIA")
        _gravar(self.pasta, "b1.dcm", "13792", "BERTOLI^ELEA ROCHA")

        achados = carregadores.pacientes_na_pasta(self.pasta)
        self.assertEqual(set(achados), {"13870", "13792"})
        self.assertEqual(achados["13870"][1], 2, "contou errado os arquivos")
        self.assertEqual(achados["13792"][1], 1)

    def test_o_nome_sai_como_se_fala(self):
        """O DICOM guarda ``FAMÍLIA^NOME``; a lista tem de mostrar o nome.

        A primeira versão exibia ``Balta^elda Garcia`` — o separador cru na
        cara de quem escolhe, e o sobrenome na frente. Quem procura na lista
        procura o nome que leu na requisição, não a forma de armazenamento.

        Formatar pelos COMPONENTES (``family_name``/``given_name``) e não por
        ``str()``: converter cedo perde a estrutura e não há como saber mais
        qual pedaço é o sobrenome.
        """
        _gravar(self.pasta, "a.dcm", "13870", "BALTA^ELDA GARCIA")
        _gravar(self.pasta, "b.dcm", "07964", "DOS SANTOS^LUZIA D ANDREA")

        achados = carregadores.pacientes_na_pasta(self.pasta)
        self.assertEqual(achados["13870"][0], "Elda Garcia Balta")
        # O conectivo fica minúsculo: "Luzia D Andrea Dos Santos" não é como
        # ninguém escreve (ver _CONECTIVOS em nomes.py).
        self.assertEqual(achados["07964"][0], "Luzia D Andrea dos Santos")

    def test_paciente_sem_nome_nao_inventa(self):
        """Campo sem fonte nasce vazio — a regra do CLAUDE.md vale aqui também.

        O diálogo mostra "(sem nome)" e o registro, que é o que casa com o
        sistema. Preencher com qualquer coisa seria pior que o branco.
        """
        _gravar(self.pasta, "x.dcm", "13870", "")
        self.assertEqual(carregadores.pacientes_na_pasta(self.pasta)["13870"][0],
                         "")

    def test_acha_em_subpasta(self):
        """A varredura é recursiva — é justamente daí que vem o problema.

        A pasta-pai de um serviço tem uma subpasta por paciente; apontar para
        ela é o gesto que produzia a ficha misturada.
        """
        (self.pasta / "PAC_A").mkdir()
        (self.pasta / "PAC_B").mkdir()
        _gravar(self.pasta / "PAC_A", "x.dcm", "111", "UM^PACIENTE")
        _gravar(self.pasta / "PAC_B", "y.dcm", "222", "OUTRO^PACIENTE")

        self.assertEqual(set(carregadores.pacientes_na_pasta(self.pasta)),
                         {"111", "222"})

    def test_pasta_de_um_paciente_so_devolve_um(self):
        """O caso NORMAL não pode ganhar pergunta nenhuma.

        Com um único paciente o programa segue direto para a carga — pôr um
        diálogo no caminho de todo dia para proteger o caso raro seria trocar
        um risco por um estorvo.
        """
        for i in range(4):
            _gravar(self.pasta, f"{i}.dcm", "13870", "BALTA^ELDA GARCIA")
        self.assertEqual(len(carregadores.pacientes_na_pasta(self.pasta)), 1)

    def test_pasta_vazia_nao_estoura(self):
        self.assertEqual(carregadores.pacientes_na_pasta(self.pasta), {})

    def test_arquivo_ilegivel_nao_derruba_a_triagem(self):
        """Um .dcm corrompido no meio não pode impedir de abrir o paciente."""
        _gravar(self.pasta, "bom.dcm", "13870", "BALTA^ELDA GARCIA")
        (self.pasta / "lixo.dcm").write_bytes(b"isto nao e DICOM")
        self.assertEqual(set(carregadores.pacientes_na_pasta(self.pasta)),
                         {"13870"})


class TestFiltroDoCarregador(unittest.TestCase):
    """O worker carrega SÓ quem se pediu — é o que dá dono à ficha."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="multipac_")
        self.pasta = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _e_do_paciente(self, registro, ds_registro):
        w = carregadores._CarregarTudo(str(self.pasta), None, registro=registro)
        ds = Dataset()
        if ds_registro is not None:
            ds.PatientID = ds_registro
        return w._e_do_paciente(ds)

    def test_sem_filtro_todo_mundo_passa(self):
        """Pasta de um paciente só: nada muda no caminho de todo dia."""
        self.assertTrue(self._e_do_paciente("", "13870"))
        self.assertTrue(self._e_do_paciente("", "99999"))

    def test_com_filtro_so_o_escolhido_passa(self):
        self.assertTrue(self._e_do_paciente("13870", "13870"))
        self.assertFalse(self._e_do_paciente("13870", "13792"))

    def test_o_registro_casa_sem_ligar_para_espaco_e_caixa(self):
        """``_norm_registro`` já existia para isto; o filtro usa o mesmo."""
        self.assertTrue(self._e_do_paciente("13870", " 13870 "))
        self.assertTrue(self._e_do_paciente("9000002cel", "9000002CEL"))

    def test_arquivo_sem_registro_passa(self):
        """Auxiliar de cabeçalho magro não pode sumir em silêncio.

        Há RT Image e protocolo de gating cujo cabeçalho de triagem não traz
        ``PatientID``. Recusá-los descartaria material legítimo, e o preço de
        deixá-los passar é pequeno: não trazem plano nem dose.
        """
        self.assertTrue(self._e_do_paciente("13870", None))
        self.assertTrue(self._e_do_paciente("13870", ""))


class TestATelaPergunta(unittest.TestCase):
    """Com mais de um paciente, o programa pergunta antes de montar a ficha."""

    def test_carregar_pasta_pergunta_e_filtra(self):
        fonte = fontes.texto("gui.py")
        corpo = fonte[fonte.index("    def _carregar_pasta(self"):]
        corpo = corpo[:corpo.index("\n    def ", 10)]

        self.assertIn("pacientes_na_pasta(pasta)", corpo,
                      "a pasta não é triada antes de carregar")
        self.assertIn("DialogEscolherPaciente", corpo,
                      "não pergunta de quem é a ficha")
        self.assertIn("registro=registro_alvo", corpo,
                      "pergunta mas não passa a escolha ao worker — a ficha "
                      "sairia misturada do mesmo jeito")

    def _carregar(self, pasta):
        """Chama ``_carregar_pasta`` de verdade, com o worker desligado.

        Devolve ``(quantas vezes perguntou, registro passado ao worker)``.

        Por comportamento, e não por texto: a primeira versão deste teste
        procurava a string ``len(achados) > 1`` no corpo do método, e ela
        aparece DUAS vezes ali (a segunda no ``historico.registrar``). Trocar
        o ``if`` por ``if False`` — ou seja, deixar de perguntar — não fazia o
        teste falhar.
        """
        from isocentro.interface import gui

        perguntou = []
        registrou = []

        class _DialogoFalso:
            def __init__(self, achados, pai=None):
                perguntou.append(achados)

            def exec(self):
                from PySide6.QtWidgets import QDialog
                return QDialog.Accepted

            def escolhido(self):
                return "13870"

        class _Qualquer:
            """Responde a tudo: ``sinal.connect(...)``, ``start()``, o que vier.

            O ``_carregar_pasta`` encadeia atributos (``ct_pronto.connect``),
            então devolver só uma função não basta — foi o que quebrou a
            primeira versão deste falso.
            """

            def __call__(self, *a, **k):
                return None

            def __getattr__(self, _nome):
                return _Qualquer()

        class _WorkerFalso(_Qualquer):
            def __init__(self, pasta, pai=None, registro=""):
                registrou.append(registro)

            def isRunning(self):
                return False

        guardados = (gui.DialogEscolherPaciente, gui._CarregarTudo)
        gui.DialogEscolherPaciente = _DialogoFalso
        gui._CarregarTudo = _WorkerFalso
        janela = gui.JanelaPrincipal(
            usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        try:
            janela._carregar_pasta(str(pasta))
        finally:
            # Devolver, nunca ``del``: o ``del`` sumiria com a ORIGINAL.
            gui.DialogEscolherPaciente, gui._CarregarTudo = guardados
            janela.deleteLater()
        return len(perguntou), (registrou[0] if registrou else None)

    def test_com_varios_pacientes_pergunta_e_passa_a_escolha(self):
        if gui is None:
            self.skipTest(f"Qt indisponível: {_MOTIVO}")
        with tempfile.TemporaryDirectory(prefix="multipac_") as tmp:
            pasta = Path(tmp)
            _gravar(pasta, "a.dcm", "13870", "BALTA^ELDA GARCIA")
            _gravar(pasta, "b.dcm", "13792", "BERTOLI^ELEA ROCHA")

            perguntas, registro = self._carregar(pasta)
            self.assertEqual(perguntas, 1, "não perguntou de quem é a ficha")
            self.assertEqual(registro, "13870",
                             "perguntou, mas o worker carregaria todo mundo")

    def test_com_um_paciente_nao_pergunta_nada(self):
        """O caminho de todo dia não pode ganhar um clique a mais.

        Pôr um diálogo na frente de toda abertura de pasta para proteger o
        caso raro trocaria um risco por um estorvo diário — e estorvo diário é
        o que faz gente procurar atalho.
        """
        if gui is None:
            self.skipTest(f"Qt indisponível: {_MOTIVO}")
        with tempfile.TemporaryDirectory(prefix="multipac_") as tmp:
            pasta = Path(tmp)
            for i in range(3):
                _gravar(pasta, f"{i}.dcm", "13870", "BALTA^ELDA GARCIA")

            perguntas, registro = self._carregar(pasta)
            self.assertEqual(perguntas, 0, "perguntou à toa")
            self.assertEqual(registro, "",
                             "sem ambiguidade o filtro fica vazio — carrega "
                             "tudo, como sempre")

    def test_o_dialogo_devolve_o_registro_escolhido(self):
        if gui is None:
            self.skipTest(f"Qt indisponível: {_MOTIVO}")
        achados = {"13870": ("BALTA^ELDA GARCIA", 179),
                   "13792": ("BERTOLI^ELEA ROCHA", 341)}
        d = gui.DialogEscolherPaciente(achados)
        try:
            # Ordenado por NOME: BALTA vem antes de BERTOLI.
            self.assertEqual(d.escolhido(), "13870")
            d.lista.setCurrentRow(1)
            self.assertEqual(d.escolhido(), "13792")
        finally:
            d.deleteLater()


# Esvazia ``estilo._ouvintes`` entre um teste e o seguinte — ver
# ``tests/limpeza_de_tela.py``.
from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


if __name__ == "__main__":
    unittest.main()
