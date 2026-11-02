"""Os ícones das linhas da Fichinha RECEBEM o clique — e o hover os mostra.

O que quebrou no uso (07/10/2026): "todos os botões em documentação somente
abrem a prévia". A linha tinha ``WA_TransparentForMouseEvents`` para o clique
no texto chegar à lista, e o Qt, ao procurar o widget sob o cursor, pula a
subárvore INTEIRA de um widget transparente — os ícones inclusive. O clique no
ícone caía na lista e só selecionava; o duplo clique virava Visualizar. Nenhum
teste via isso porque todos chamavam ``botao.click()``, que não passa pela
procura do widget sob o cursor. Aqui a pergunta é a do Qt: ``childAt``.
"""
from __future__ import annotations

import unittest

try:
    from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem

    from isocentro.interface import fichinha
except ImportError:  # pragma: no cover — sem PyQt5 a suíte segue
    fichinha = None

from tests.limpeza_de_tela import load_tests  # noqa: F401


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class TestIconesDaLinha(unittest.TestCase):

    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.lista = QListWidget()
        self.lista.resize(600, 200)
        self.linha = fichinha._Linha({"paciente": "X"})
        self.linha.fechar()
        self.recebidos = []
        self.linha.definir_acoes(
            fichinha._ACOES_DOC,
            lambda chave, dados: self.recebidos.append(chave))
        item = QListWidgetItem()
        item.setSizeHint(self.linha.sizeHint())
        self.lista.addItem(item)
        self.lista.setItemWidget(item, self.linha)
        self.item = item
        self.lista.show()
        self.linha.mostrar_acoes(True)
        self.app.processEvents()

    def tearDown(self):
        self.lista.close()
        self.lista.deleteLater()

    def test_o_widget_sob_o_cursor_no_icone_e_o_proprio_icone(self):
        vp = self.lista.viewport()
        for chave, botao in self.linha._botoes.items():
            centro = botao.mapTo(vp, botao.rect().center())
            self.assertIs(vp.childAt(centro), botao,
                          f"o clique no ícone {chave} não chega a ele")

    def test_a_linha_nao_e_transparente_ao_mouse(self):
        from PySide6.QtCore import Qt
        self.assertFalse(self.linha.testAttribute(Qt.WA_TransparentForMouseEvents))

    def test_cursor_entrando_na_linha_avisa_a_lista(self):
        """Sem isto os ícones nunca apareciam: o hover da lista era mudo."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QEnterEvent
        entrou = []
        self.lista.itemEntered.connect(entrou.append)
        self.linha.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
        self.assertEqual(entrou, [self.item])


if __name__ == "__main__":
    unittest.main()
