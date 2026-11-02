"""Trocar de paciente não pode deixar NADA do anterior na tela.

Este arquivo existe porque o mesmo erro apareceu duas vezes em dois dias, por
caminhos diferentes:

* as fotos de posicionamento do paciente A ficavam na capa do B (o repor do
  posicionamento não perguntava de quem eram);
* a pasta de A continuava valendo ao montar a capa de B, e ``carregar_da_pasta``
  trazia as notas e as fotos dela.

Os dois foram corrigidos com testes específicos — e o segundo apareceu **depois**
do primeiro, no mesmo dia. Isso diz que o problema não é cada caso: é a forma da
tela. Ela vive muito, ``self._capa`` é reusado, e cada caminho novo que carrega
um paciente precisa lembrar de apagar o anterior. Teste específico só pega o
caminho em que alguém pensou.

Então aqui não se testa caminho: percorre-se **todo campo e todo widget de
texto** da tela, com valores marcados, e falha-se se qualquer coisa do primeiro
paciente sobreviver ao segundo. Um teste que não precisa que eu adivinhe onde
vai vazar da próxima vez.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io as _io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
for _var in ("ISOCENTRO_SIMULACOES", "ISOCENTRO_INVENTARIO_DIR", "ISOCENTRO_NOTAS_DIR",
             "ISOCENTRO_USERS_DIR", "ISOCENTRO_CORRECOES", "ISOCENTRO_ESPELHO",
             "ISOCENTRO_CONFIG"):
    os.environ.setdefault(_var, tempfile.mkdtemp(prefix="vazamento_"))

try:
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import (QApplication, QComboBox, QLineEdit,
                                 QPlainTextEdit, QTextEdit)
    _APP = QApplication.instance() or QApplication([])

    from isocentro.interface import capa as capa_tela
    # Entra na sondagem de propósito, ainda que não seja usado direto:
    # se o capa_dados não importar, é aqui que o teste tem de pular.
    from isocentro.banco import capa_dados  # noqa: F401
    from isocentro.papel import capa_pdf
    from PIL import Image
except Exception as exc:  # noqa: BLE001
    capa_tela = None
    _MOTIVO = str(exc)

# Marca que não existe em paciente nenhum: se aparecer na tela do segundo,
# veio do primeiro. Texto e não número, para casar em campo de qualquer tipo.
_MARCA = "ZZMARCADOANTERIORZZ"


def _capa_marcada() -> "capa_pdf.Capa":
    """Uma capa com a MARCA em todo campo de texto que ela tenha.

    Montada por reflexão: campo novo no ``Capa`` entra aqui sozinho, e é essa a
    graça — o teste não envelhece quando alguém acrescenta um dado à folha.
    """
    import dataclasses
    capa = capa_pdf.Capa()
    for campo in dataclasses.fields(capa):
        if campo.type is str or isinstance(getattr(capa, campo.name), str):
            setattr(capa, campo.name, _MARCA)
    capa.nome = f"PACIENTE UM {_MARCA}"
    capa.registro = "1111111AAA"
    return capa


def _textos_da_tela(tela) -> dict:
    """Todo texto visível da tela, por widget — sem lista de campos a manter."""
    # Widget destruído com ``deleteLater`` continua sendo FILHO até o evento ser
    # entregue, e ``processEvents`` não entrega ``DeferredDelete`` (armadilha já
    # paga, ver o CLAUDE.md). Sem esta linha, a aba de posicionamento que
    # acabou de ser removida ainda respondia com o texto do paciente anterior e
    # a sonda acusava um vazamento que já tinha sido corrigido.
    _APP.sendPostedEvents(None, QEvent.DeferredDelete)
    fora = {}
    for w in tela.findChildren(QLineEdit):
        fora[f"QLineEdit:{w.objectName() or id(w)}"] = w.text()
    for w in tela.findChildren(QComboBox):
        fora[f"QComboBox:{w.objectName() or id(w)}"] = w.currentText()
    for tipo in (QTextEdit, QPlainTextEdit):
        for w in tela.findChildren(tipo):
            fora[f"QTextEdit:{w.objectName() or id(w)}"] = w.toPlainText()
    return fora


@unittest.skipIf(capa_tela is None, "PySide6/Pillow indisponíveis")
class TestNadaDoAnterior(unittest.TestCase):

    def setUp(self):
        self.tela = capa_tela.PainelCapa()

    def tearDown(self):
        self.tela.deleteLater()

    def _arrastar_fotos(self, quantas: int = 2) -> None:
        pasta = tempfile.mkdtemp()
        caminhos = []
        for i in range(quantas):
            p = os.path.join(pasta, f"TORAX_{i}.jpg")
            Image.new("RGB", (900, 700), (30, 80, 140)).save(p)
            caminhos.append(p)
        self.tela.posicionamento._soltou_fotos(caminhos)

    def _fotos(self) -> int:
        return sum(len(s.fotos) for s in self.tela.posicionamento.setups())

    def test_nenhum_campo_guarda_texto_do_paciente_anterior(self):
        """Percorre TODO campo da tela — não uma lista que eu tenha escrito.

        É o ponto: quando alguém acrescentar um campo à capa daqui a um ano,
        este teste passa a cobri-lo sem ninguém lembrar de vir aqui.
        """
        self.tela.carregar(_capa_marcada())
        depois = capa_pdf.Capa(nome="PACIENTE DOIS", registro="2222222BBB")
        self.tela.carregar(depois)

        sujos = {k: v for k, v in _textos_da_tela(self.tela).items()
                 if _MARCA in (v or "")}
        self.assertEqual(sujos, {},
                         f"sobrou do paciente anterior: {sujos}")

    def test_o_posicionamento_nao_atravessa(self):
        """As fotos da TC do primeiro não podem sair na folha 2 do segundo."""
        self.tela.carregar(_capa_marcada())
        self._arrastar_fotos()
        self.assertEqual(self._fotos(), 2)
        self.tela.carregar(capa_pdf.Capa(nome="PACIENTE DOIS",
                                         registro="2222222BBB"))
        self.assertEqual(self._fotos(), 0)

    def test_a_pasta_do_anterior_nao_fica_valendo(self):
        """``carregar_da_pasta`` cai na pasta guardada quando não recebe uma;
        herdar a do anterior importava as notas e fotos DELE."""
        self.tela.definir_pasta(tempfile.mkdtemp())
        self.tela.carregar(_capa_marcada())
        self.tela.definir_pasta("")
        self.tela.carregar(capa_pdf.Capa(nome="PACIENTE DOIS",
                                         registro="2222222BBB"))
        self.assertEqual(self.tela.pasta_do_paciente(), "")

    def test_o_dono_do_posicionamento_muda_junto(self):
        """Quem carrega o segundo paciente passa a ser o dono — senão o
        posicionamento do primeiro seria "preservado" para ele."""
        self.tela.carregar(_capa_marcada())
        self._arrastar_fotos()
        self.assertTrue(self.tela.posicionamento_e_de("1111111AAA"))
        self.assertFalse(self.tela.posicionamento_e_de("2222222BBB"))

    def _escolher_na_busca(self, nome: str, registro: str) -> None:
        """O caminho de quem chega da tomografia: escolher na lista da busca."""
        class _Ref:
            def __init__(self, nome, registro):
                self.nome, self.registro = nome, registro
                self.nascimento = "01/01/1970"

            def casa(self, _termo):
                return True

            def rotulo(self):
                return self.nome

        self.tela.definir_pacientes([_Ref(nome, registro)])
        self.tela.busca.setText(nome[:6])
        self.tela.lista_pac.setCurrentRow(0)

    def test_escolher_na_busca_nao_herda_o_posicionamento_de_quem_estava(self):
        """O paciente que chegou pela BANCADA não passa por ``_escolher_paciente``,
        então ``self._escolhido`` era ``None`` e a troca não era detectada: o
        posicionamento dele era reassinado para quem foi escolhido na busca, e a
        nota (e as fotos) de A saíam na capa de B."""
        from isocentro.banco import capa_dados
        capa = _capa_marcada()
        capa.setups = [capa_dados.Setup(nome=f"TORAX {_MARCA}",
                                        acessorios=_MARCA,
                                        arquivo=f"SETUP_{_MARCA}.txt")]
        self.tela.carregar(capa)          # pela bancada: sem passar pela busca
        self.assertTrue(self.tela.posicionamento.setups())

        self._escolher_na_busca("PACIENTE DOIS", "2222222BBB")

        self.assertEqual(self.tela.posicionamento.setups(), [])
        sujos = {k: v for k, v in _textos_da_tela(self.tela).items()
                 if _MARCA in (v or "")}
        self.assertEqual(sujos, {}, f"sobrou do anterior: {sujos}")

    def test_com_FOTOS_a_troca_pela_busca_pergunta_antes(self):
        """Foto de tomografia não se refaz sem o paciente na sala — descartar
        cala a boca é o erro mais caro desta tela. E a pergunta tem de saber
        dizer de quem são as fotos, mesmo sem referência da busca."""
        perguntas = []
        self.tela._confirmar_troca = lambda de, para: (
            perguntas.append((de, para)) or False)
        self.tela.carregar(_capa_marcada())
        self._arrastar_fotos()

        self._escolher_na_busca("PACIENTE DOIS", "2222222BBB")

        self.assertEqual(len(perguntas), 1)
        self.assertIn(_MARCA, perguntas[0][0])      # de quem são as fotos
        self.assertEqual(perguntas[0][1], "PACIENTE DOIS")
        # Recusada, nada se perde: as fotos continuam onde estavam.
        self.assertEqual(self._fotos(), 2)
        self.assertTrue(self.tela.posicionamento_e_de("1111111AAA"))

    def test_limpar_nao_deixa_rastro(self):
        """O caminho de "Próximo paciente": a tela tem de voltar ao zero."""
        self.tela.carregar(_capa_marcada())
        self._arrastar_fotos()
        self.tela.limpar()
        sujos = {k: v for k, v in _textos_da_tela(self.tela).items()
                 if _MARCA in (v or "")}
        self.assertEqual(sujos, {}, f"sobrou depois de limpar: {sujos}")
        self.assertEqual(self._fotos(), 0)
        self.assertEqual(self.tela.pasta_do_paciente(), "")

    def test_a_foto_3x4_do_anterior_nao_fica(self):
        """A 3×4 é o que confere, na sala, que o paciente é o da folha —
        a última que pode atravessar."""
        com_foto = _capa_marcada()
        # JPEG DE VERDADE: assinatura falsa passa pela conferência do app mas o
        # Qt não a decodifica, e o teste "passaria" com a moldura sempre vazia —
        # provando nada.
        buf = _io.BytesIO()
        Image.new("RGB", (300, 400), (200, 170, 150)).save(buf, format="JPEG")
        com_foto.foto = buf.getvalue()
        self.tela.carregar(com_foto)
        self.assertTrue(self.tela.lbl_foto.tem_imagem())
        self.tela.carregar(capa_pdf.Capa(nome="PACIENTE DOIS",
                                         registro="2222222BBB"))
        self.assertFalse(self.tela.lbl_foto.tem_imagem())
        self.assertIsNone(self.tela.coletar().foto)


# Esvazia ``estilo._ouvintes`` entre um teste e o seguinte. Sem isto, a lista
# cresce durante o arquivo inteiro e cada repintura percorre tudo o que já se
# acumulou — ver ``tests/limpeza_de_tela.py`` para os números.
from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


if __name__ == "__main__":
    unittest.main()
