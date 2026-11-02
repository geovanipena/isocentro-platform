"""O ARCO do gantry na ficha — não só o ângulo em que ele começa.

Visto no caso 9000021ANA (gFEMUR_DIR, 20/08/2026): cinco arcos VMAT, e a linha
Gantry da ficha saiu "300 179 300 179 300". São cinco ângulos fixos para cinco
arcos que varrem meia volta cada — quem confere na sala lê "gantry 300" e
procura um campo parado que não existe.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dicom import dicom_rt  # noqa: E402
from isocentro.papel import ficha_pdf  # noqa: E402
from pydicom.dataset import Dataset  # noqa: E402


def _cp(gantry, sentido=None):
    cp = Dataset()
    cp.GantryAngle = gantry
    if sentido is not None:
        cp.GantryRotationDirection = sentido
    return cp


class TestArcoDoFeixe(unittest.TestCase):

    def test_arco_guarda_o_fim_e_o_sentido(self):
        arco = dicom_rt._arco_do_feixe([_cp(300.0, "CW"), _cp(179.0, "CW")])
        self.assertEqual(arco["gantry_fim"], 179.0)
        self.assertEqual(arco["gantry_sentido"], "CW")

    def test_campo_estatico_nao_tem_arco(self):
        """Sem sentido de rotação não há arco — e "gantry_fim" preenchido num
        campo parado faria a ficha anunciar uma varredura que não acontece."""
        arco = dicom_rt._arco_do_feixe([_cp(90.0, "NONE")])
        self.assertIsNone(arco["gantry_fim"])
        self.assertEqual(arco["gantry_sentido"], "")
        self.assertIsNone(dicom_rt._arco_do_feixe([_cp(90.0)])["gantry_fim"])

    def test_sem_control_point_nao_quebra(self):
        self.assertIsNone(dicom_rt._arco_do_feixe([])["gantry_fim"])

    def test_o_fim_e_o_ULTIMO_ponto_e_nao_o_maior_angulo(self):
        """Um arco que cruza o 0° tem 359 no meio do caminho; "300→359"
        descreveria uma volta que não houve."""
        arco = dicom_rt._arco_do_feixe(
            [_cp(300.0, "CW"), _cp(359.0, "CW"), _cp(179.0, "CW")])
        self.assertEqual(arco["gantry_fim"], 179.0)


class TestGantryTexto(unittest.TestCase):

    def test_arco_sai_com_a_seta_e_o_SENTIDO(self):
        """"300→179" sozinho é ambíguo: de 300 a 179 dá para ir pelos dois
        lados, e é o sentido que diz por onde o braço passa — horário cruza o
        0° (a frente do paciente), anti-horário cruza o 240°."""
        self.assertEqual(
            dicom_rt.gantry_texto({"gantry": 300.0, "gantry_fim": 179.0,
                                   "gantry_sentido": "CW"}), "300→179 h")
        self.assertEqual(
            dicom_rt.gantry_texto({"gantry": 179.0, "gantry_fim": 300.0,
                                   "gantry_sentido": "CC"}), "179→300 ah")
        # "CCW" é a mesma coisa que "CC", escrita por outro TPS.
        self.assertEqual(
            dicom_rt.gantry_texto({"gantry": 179.0, "gantry_fim": 300.0,
                                   "gantry_sentido": "CCW"}), "179→300 ah")

    def test_sentido_desconhecido_nao_vira_letra(self):
        """Sentido errado no papel é pior que sentido nenhum: quem confere iria
        procurar o braço passando pelo lado errado."""
        self.assertEqual(
            dicom_rt.gantry_texto({"gantry": 300.0, "gantry_fim": 179.0,
                                   "gantry_sentido": "?"}), "300→179")

    def test_campo_estatico_sai_so_com_o_angulo(self):
        self.assertEqual(
            dicom_rt.gantry_texto({"gantry": 90.0, "gantry_fim": None}), "90")

    def test_meio_grau_nao_some(self):
        """Mesa e colimador de 352,5° já custaram um arredondamento; o gantry
        de meio grau tem de sobreviver pelo mesmo motivo."""
        self.assertEqual(
            dicom_rt.gantry_texto({"gantry": 352.5, "gantry_fim": 7.5}),
            "352,5→7,5")

    def test_sem_gantry_nao_inventa(self):
        self.assertEqual(dicom_rt.gantry_texto({}), "")
        self.assertEqual(
            dicom_rt.gantry_texto({"gantry": None, "gantry_fim": 179.0}), "")


class TestGantryNaFichaImpressa(unittest.TestCase):
    """O que sai NO PAPEL — é ele que vai para a sala de tratamento."""

    @staticmethod
    def _texto(feixes):
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        tela = ficha_pdf.Tela(c, 842, 595)
        ficha_pdf._tabela_campos(tela, 40, feixes)
        c.showPage()
        c.save()
        try:
            from pypdf import PdfReader
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("pypdf ausente") from None
        return PdfReader(io.BytesIO(buf.getvalue())).pages[0].extract_text()

    def test_o_arco_INTEIRO_vai_para_o_papel(self):
        """Os dois ângulos E o sentido — em duas linhas dentro da célula desde
        que o texto de uma linha passou a invadir a coluna vizinha (ver
        ``test_o_arco_CABE_na_celula``). O que não pode é PERDER a letra: sem
        ela "300→179" é ambíguo, e quem confere procuraria o braço passando
        pelo lado errado."""
        txt = self._texto([{"gantry": 300.0, "gantry_fim": 179.0,
                            "gantry_sentido": "CW", "fase": 1}])
        self.assertIn("300→179", txt.replace(" ", ""))
        self.assertIn("h", txt)

    def test_campo_estatico_continua_como_era(self):
        """A mudança não pode mexer no 3D conformacional, que é a maioria das
        fichas: campo parado imprime um ângulo só, como sempre imprimiu."""
        txt = self._texto([{"gantry": 90.0, "fase": 1}]).replace(" ", "")
        self.assertIn("90", txt)
        self.assertNotIn("→", txt)

    def test_o_arco_CABE_na_celula(self):
        """"352,5→7,5 ah" precisa de 34,5pt onde a célula tem 31,4.

        O encolhimento de ``Tela.txt`` para no piso de 5,5pt e o recorte é da
        TABELA, não da célula: o excedente saía por cima da coluna ao lado, com
        o ângulo de um campo sobre o do outro — na folha que se confere contra
        o console. Daí a quebra em duas linhas (ângulos em cima, sentido
        embaixo).
        """
        from reportlab.pdfbase.pdfmetrics import stringWidth

        disp = (842 - 2 * 14 - 50) / ficha_pdf.N_CAMPOS - ficha_pdf._PAD_CELULA
        for feixe in ({"gantry": 352.5, "gantry_fim": 7.5,
                       "gantry_sentido": "CCW"},
                      {"gantry": 181.0, "gantry_fim": 179.0,
                       "gantry_sentido": "CCW"},
                      {"gantry": 300.0, "gantry_fim": 179.0,
                       "gantry_sentido": "CW"}):
            texto = ficha_pdf.valor_do_campo(feixe, "gantry", 0)
            angulos, _, sentido = texto.partition(" ")
            self.assertTrue(sentido, f"{texto} não tem sentido para quebrar")
            # Os ângulos encolhem sozinhos até caber; o piso não é atingido
            # porque o sufixo saiu da linha.
            larg = stringWidth(angulos, "Helvetica",
                               ficha_pdf._FONTE_VAL_TABELA)
            tam = (ficha_pdf._FONTE_VAL_TABELA if larg <= disp
                   else max(ficha_pdf._FONTE_VAL_TABELA * disp / larg,
                            ficha_pdf._FONTE_MIN))
            self.assertLessEqual(stringWidth(angulos, "Helvetica", tam),
                                 disp + 0.01, f"{angulos} invade a vizinha")
            self.assertLessEqual(
                stringWidth(sentido, "Helvetica",
                            ficha_pdf._FONTE_SENTIDO_ARCO),
                disp, f"{sentido} invade a vizinha")

    def test_fase_apagada_na_edicao_nao_imprime_a_palavra_None(self):
        """Apagar a célula Fase grava ``None`` NA CHAVE — e o default do
        ``get`` só cobre a chave ausente. ``str(None)`` fazia a palavra "None"
        sair impressa na ficha que vai para a sala."""
        txt = self._texto([{"gantry": 90.0, "fase": None}])
        self.assertNotIn("None", txt)
        # Chave AUSENTE continua valendo fase 1, como sempre valeu.
        self.assertIn("1", self._texto([{"gantry": 90.0}]))


if __name__ == "__main__":
    unittest.main()
