"""Dia ↔ noite: nenhuma tela pode ficar para trás na troca.

A folha de estilo do Qt é TEXTO, e o texto congela as cores do instante em que
o widget nasceu. Trocar a constante em ``estilo`` depois disso não repinta nada
— quem precisa acompanhar registra a receita (:func:`estilo.pintar`), não o
resultado.

O jeito de isso quebrar é sempre o mesmo e nunca dá erro: alguém escreve
``w.setStyleSheet(f"...{st.ACAO}...")``, funciona no modo em que testou, e a
tela fica no modo antigo para sempre. Estes testes varrem as telas montadas
procurando cor que não seja do modo em vigor.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ISOCENTRO_USERS_DIR", str(Path(__file__).parent))

try:
    from PySide6.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    _APP.setStyle("Fusion")
    from isocentro.papel import capa_pdf
    from isocentro.interface import estilo
    from isocentro.interface import gui
except Exception as exc:  # noqa: BLE001
    gui = None
    _MOTIVO = str(exc)

_HEX = re.compile(r"#[0-9a-fA-F]{6}")

# Cores que NÃO pertencem à paleta de propósito, e por quê:
_INTENCIONAIS = {
    "#000000",  # fundo do corte — a imagem é uma janela, não superfície do app
    "#1a1a1a",  # tinta sobre a tarja amarela, igual à da folha impressa
    "#10201a",  # texto escuro sobre a cor de um plano
    "#33b876", "#e0a63a", "#8ec5e6",   # cores categóricas de plano
    "#c084fc", "#ef7a85",
}


def _fora_do_modo(raiz, modo: str) -> list[tuple[str, str]]:
    """(classe, cor) de toda folha que não é do modo em vigor."""
    permitidas = {v.lower() for v in estilo.MODOS[modo].values()} | _INTENCIONAIS
    achados = []
    for w in [raiz] + raiz.findChildren(object):
        try:
            css = w.styleSheet()
        except Exception:  # noqa: BLE001 — nem todo filho é widget
            continue
        for cor in _HEX.findall(css or ""):
            if cor.lower() not in permitidas:
                achados.append((type(w).__name__, cor))
    return achados


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestTrocaDeModo(unittest.TestCase):

    def setUp(self):
        gui.aplicar_modo("noite")
        self.j = gui.JanelaPrincipal({"usuario": "dev", "papel": "admin"})
        # A Capa só monta os campos com um caso; sem isto metade da tela nem
        # existe e o teste passaria por não ter o que conferir.
        self.j.capa.carregar(capa_pdf.Capa(
            nome="AMOSTRA DE BELTRANA", registro="9000016BET",
            nascimento="14/07/1966", sexo="Feminino", convenio="Ipasgo",
            medico="THAIS", maquina="600CD"))
        for indice in (2, 0, 1):      # abre as três, para todas existirem
            self.j._ir_para_modo(indice)
        _APP.processEvents()

    def tearDown(self):
        self.j.close()
        self.j.deleteLater()
        _APP.processEvents()
        gui.aplicar_modo("noite")

    def _telas(self):
        return (("Capa", self.j.capa), ("Ficha Total", self.j.pag_total),
                ("Fichinha", self.j.fichinha), ("faixa de modo", self.j._barra_modo))

    def test_nenhuma_tela_fica_no_modo_antigo(self):
        """O sintoma: trocar o modo e uma aba continuar escura (ou clara).

        Acontece quando a folha foi escrita direto em vez de registrada — e não
        levanta erro nenhum, só fica errado na tela.
        """
        for destino in ("dia", "noite", "dia"):
            gui.aplicar_modo(destino)
            _APP.processEvents()
            for nome, tela in self._telas():
                fora = _fora_do_modo(tela, destino)
                self.assertEqual(
                    fora, [],
                    f"{nome} ficou no modo antigo ao trocar para {destino}: "
                    f"{sorted(set(fora))[:6]}")

    def test_widgets_refeitos_nao_empilham_registros(self):
        """O caso real: cartões refeitos A CADA TECLA digitada.

        ``posicionamento._repintar_valores`` recria os cartões de preparo a
        cada caractere nos acessórios, três pinturas por cartão. Sem varredura
        fora da troca de modo, uma sessão de trabalho normal empilharia dezenas
        de milhares de registros de widgets que já morreram.
        """
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QLabel, QWidget

        estilo._varrer()
        base = len(estilo._ouvintes)
        for _ in range(estilo._LIMITE_VARREDURA * 2):
            pai = QWidget()
            estilo.pintar(QLabel(pai), lambda: f"color:{estilo.ACAO};")
            pai.deleteLater()
            del pai
            _APP.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertLess(len(estilo._ouvintes),
                        base + estilo._LIMITE_VARREDURA + 50,
                        "a varredura periódica não está limpando os mortos")

    def test_o_registro_nao_cresce_sem_limite(self):
        """Ouvinte de widget morto tem de sair na primeira troca seguinte."""
        antes = len(estilo._ouvintes)
        for _ in range(3):
            gui.aplicar_modo("dia")
            gui.aplicar_modo("noite")
        self.assertLessEqual(len(estilo._ouvintes), antes,
                             "a lista de repintura só cresce")

    def test_widget_destruido_com_o_pai_sai_do_registro(self):
        """Referência forte ao widget não pode impedir o registro de se limpar.

        Ela é forte de propósito: com ``weakref`` o PyQt coletava o invólucro de
        todo campo criado em fábrica e a folha sumia junto. Quem marca a morte é
        o C++ ter ido embora — e quem o leva embora é o PAI, que é como todo
        widget pintado de verdade nasce (dentro de um layout).
        """
        from PySide6.QtWidgets import QLabel, QWidget

        pai = QWidget()
        for _ in range(3):
            estilo.pintar(QLabel(pai), lambda: f"color:{estilo.ACAO};")
        antes = len(estilo._ouvintes)
        pai.deleteLater()
        del pai
        # ``processEvents`` sozinho NÃO entrega o DeferredDelete — o pai
        # continuaria vivo e o teste passaria por não ter destruído nada.
        from PySide6.QtCore import QEvent
        _APP.sendPostedEvents(None, QEvent.DeferredDelete)
        _APP.processEvents()
        gui.aplicar_modo("dia")
        self.assertLessEqual(len(estilo._ouvintes), antes - 3)


@unittest.skipIf(gui is None, "gui indisponível (PySide6?)")
class TestPaleta(unittest.TestCase):

    def test_os_dois_modos_tem_as_mesmas_chaves(self):
        """Chave faltando num modo é ``AttributeError`` só ao trocar."""
        self.assertEqual(set(estilo.DIA), set(estilo.NOITE))

    def test_toda_cor_e_hexadecimal_valido(self):
        for modo, cores in estilo.MODOS.items():
            for nome, valor in cores.items():
                self.assertRegex(valor, r"^#[0-9A-Fa-f]{6}$", f"{modo}.{nome}")

    def test_o_texto_sobre_o_solido_inverte_com_o_modo(self):
        """No noturno o acento é claro: branco por cima dele fica ilegível."""
        self.assertEqual(estilo.DIA["SOBRE_ACAO"].lower(), "#ffffff")
        self.assertNotEqual(estilo.NOITE["SOBRE_ACAO"].lower(), "#ffffff")

    def test_a_paleta_do_sistema_segue_o_modo(self):
        from PySide6.QtGui import QPalette

        for modo in ("dia", "noite"):
            gui.aplicar_modo(modo)
            p = gui._paleta_dark()
            self.assertEqual(p.color(QPalette.Window).name().lower(),
                             estilo.MODOS[modo]["FUNDO_TELA"].lower())
        gui.aplicar_modo("noite")


# Esvazia ``estilo._ouvintes`` entre um teste e o seguinte. Sem isto, a lista
# cresce durante o arquivo inteiro e cada repintura percorre tudo o que já se
# acumulou — ver ``tests/limpeza_de_tela.py`` para os números.
from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


if __name__ == "__main__":
    unittest.main()
