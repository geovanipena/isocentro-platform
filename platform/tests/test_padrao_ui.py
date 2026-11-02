"""O padrão dos pop-ups e dos diálogos — o que não pode divergir de novo.

Antes havia ~75 sítios de pop-up montados um a um e 14 ``QDialog`` com o rodapé
escrito à mão. Três coisas divergiam, e as três custam a quem é interrompido no
meio do trabalho com o paciente na mesa: o verbo do botão, a ORDEM dos botões e
o que o Enter faz.

Estes testes guardam o padrão. Eles não conferem beleza: conferem que a mesma
pergunta continua com a mesma cara em toda tela.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QApplication, QLabel, QMessageBox,
                                 QPushButton)
    _APP = QApplication.instance() or QApplication([])
    from isocentro.interface import tratamento
    from isocentro.interface import ui
except Exception:  # noqa: BLE001 — sem Qt estes testes não se aplicam
    ui = None


def _destruir(w) -> None:
    from PySide6.QtCore import QEvent
    w.setParent(None)
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def _rodape(d) -> list:
    """Os rótulos da faixa de botões, na ordem em que aparecem na tela."""
    linha = d.layout().itemAt(d.layout().count() - 1)
    saida = []
    for i in range(linha.count()):
        w = linha.itemAt(i).widget()
        saida.append(w.text() if w is not None else "<vão>")
    return saida


@unittest.skipIf(ui is None, "ui indisponível (PyQt5?)")
class TestRodape(unittest.TestCase):
    """A ordem dos botões não é gosto — é ditada pelos ``QMessageBox``."""

    def test_confirmar_vem_ANTES_de_cancelar(self):
        """No Windows o Qt desenha ``[OK][Cancelar]`` e isso não se muda.

        Os pop-ups são 5× mais frequentes que os diálogos próprios, então é
        ELE que dita a ordem da casa. Antes, três diálogos faziam o contrário e
        quem acabara de clicar "Aplicar" à direita achava "Cancelar" ali.
        """
        d = ui.Dialogo("T")
        try:
            d.rodape("Aplicar")
            self.assertEqual(_rodape(d), ["<vão>", "Aplicar", "Cancelar"])
        finally:
            _destruir(d)

    def test_as_acoes_laterais_ficam_a_ESQUERDA_do_par(self):
        """"Todos", "Limpar", "Atualizar" são do trabalho, não do fechamento
        da tela — no meio do par, empurrariam o confirmar de lugar conforme a
        tela tivesse ou não ação lateral."""
        d = ui.Dialogo("T")
        try:
            d.rodape("Aplicar", extras=[("Todos", None), ("Limpar", None)])
            self.assertEqual(
                _rodape(d),
                ["Todos", "Limpar", "<vão>", "Aplicar", "Cancelar"])
        finally:
            _destruir(d)

    def test_Enter_confirma(self):
        """Aparecia em 3 dos 14 diálogos. Nos outros 11 o Enter não fazia
        nada, e quem digita a senha e aperta Enter conclui que travou."""
        d = ui.Dialogo("T")
        try:
            botoes = d.rodape("Entrar")
            self.assertTrue(botoes["Entrar"].isDefault())
            self.assertFalse(botoes["Cancelar"].isDefault())
        finally:
            _destruir(d)

    def test_acao_destrutiva_PERDE_o_Enter(self):
        """Botão destrutivo que responde ao Enter é o caminho mais curto para
        apagar o trabalho de alguém — a mão erra a tecla."""
        d = ui.Dialogo("T")
        try:
            botoes = d.rodape("Apagar tudo", perigo=True)
            self.assertFalse(botoes["Apagar tudo"].isDefault())
            self.assertTrue(botoes["Cancelar"].isDefault())
        finally:
            _destruir(d)

    def test_tela_de_leitura_nao_tem_solido_nem_Cancelar(self):
        """Sólido significa "o passo que não se desfaz"; numa tela que só
        mostra não há passo nenhum. E "Cancelar" ali sugere que algo estava
        sendo feito e foi desfeito — e nada estava."""
        d = ui.Dialogo("T")
        try:
            self.assertEqual(list(d.rodape()), ["Fechar"])
            self.assertEqual(_rodape(d), ["<vão>", "Fechar"])
        finally:
            _destruir(d)

    def test_o_rodape_entra_por_ULTIMO_mesmo_com_corpo_depois(self):
        """Quem herda monta o corpo em ``self.corpo``; o rodapé mora na raiz.
        Sem essa separação, um ``addWidget`` tardio caía DEPOIS dos botões."""
        d = ui.Dialogo("T")
        try:
            d.rodape("Ok")
            d.corpo.addWidget(QLabel("miolo que chegou tarde"))
            self.assertEqual(_rodape(d)[-1], "Cancelar")
        finally:
            _destruir(d)


@unittest.skipIf(ui is None, "ui indisponível (PyQt5?)")
class TestPopups(unittest.TestCase):
    """O verbo no botão, e o pai que centraliza."""

    def _espiar(self):
        """Troca ``exec_`` por um espião: modal de verdade trava a suíte."""
        vistos = {}
        orig = QMessageBox.exec

        def falso(self):
            vistos["msg"] = self
            vistos["botoes"] = [b.text() for b in self.buttons()]
            vistos["icone"] = self.icon()
            vistos["padrao"] = (self.defaultButton().text()
                                if self.defaultButton() else "")
            return 0

        QMessageBox.exec = falso
        # GUARDA E DEVOLVE. ``del QMessageBox.exec`` some com o método
        # ORIGINAL para o resto do processo — armadilha já paga neste projeto.
        self.addCleanup(setattr, QMessageBox, "exec", orig)
        return vistos

    def test_confirmar_exige_o_VERBO_e_nao_oferece_Sim_Nao(self):
        """"Trocar de paciente?" com [Sim][Não] obriga a reler o título para
        saber o que "Sim" faz — e o título de um modal que interrompe alguém é
        justamente o que não se lê."""
        vistos = self._espiar()
        ui.confirmar(None, "Trocar de paciente?", "Há fotos carregadas.",
                     acao="Descartar e trocar", recusa="Continuar com o atual")
        self.assertEqual(vistos["botoes"],
                         ["Descartar e trocar", "Continuar com o atual"])
        self.assertNotIn("Sim", vistos["botoes"])

    def test_confirmar_devolve_True_so_na_acao(self):
        vistos = self._espiar()
        ui.confirmar(None, "T", "t", acao="Seguir")
        self.assertEqual(vistos["padrao"], "Seguir")

    def test_perigo_tira_o_Enter_da_acao(self):
        vistos = self._espiar()
        ui.confirmar(None, "T", "t", acao="Apagar", recusa="Manter",
                     perigo=True)
        self.assertEqual(vistos["padrao"], "Manter")

    def test_o_icone_vem_da_FUNCAO_escolhida(self):
        """"Isto é um aviso" e "isto é uma falha" viram decisões tomadas na
        chamada, legíveis no grep — e não um argumento que se copia errado."""
        for fn, icone in ((ui.avisar, QMessageBox.Information),
                          (ui.alertar, QMessageBox.Warning),
                          (ui.falhar, QMessageBox.Critical)):
            with self.subTest(fn=fn.__name__):
                vistos = self._espiar()
                fn(None, "T", "t")
                self.assertEqual(vistos["icone"], icone)

    def test_detalhe_vai_no_segundo_paragrafo(self):
        """22 dos 24 pop-ups à mão já faziam assim: o título diz o assunto, o
        texto diz o que houve, o detalhe diz o caminho do arquivo. Amontoado no
        texto principal, a pergunta virava um parágrafo."""
        vistos = self._espiar()
        ui.avisar(None, "Pronto", "Ficha gerada.", "C:/casos/1X/ficha.pdf")
        self.assertEqual(vistos["msg"].text(), "Ficha gerada.")
        self.assertEqual(vistos["msg"].informativeText(),
                         "C:/casos/1X/ficha.pdf")

    def test_escolher_devolve_o_ROTULO_e_nao_o_indice(self):
        """``if escolha == "Abrir a pasta"`` diz o que aconteceu; ``== 1`` só
        diz onde o botão estava — e mexer na ordem trocaria de ação em
        silêncio."""
        vistos = self._espiar()
        ui.escolher(None, "Simulação cadastrada", "Pronto.",
                    ["Confeccionar a capa", "Abrir a pasta"])
        self.assertEqual(vistos["botoes"],
                         ["Confeccionar a capa", "Abrir a pasta", "Fechar"])
        self.assertEqual(vistos["padrao"], "Confeccionar a capa")

    def test_escolher_sem_clique_devolve_vazio(self):
        self._espiar()
        self.assertEqual(
            ui.escolher(None, "T", "t", ["A", "B"]), "")


@unittest.skipIf(ui is None, "ui indisponível (PyQt5?)")
class TestDialogosDoPrograma(unittest.TestCase):
    """Os diálogos de verdade seguem o padrão — não só a moldura.

    A moldura sozinha não garante nada: um diálogo que herde ``ui.Dialogo`` e
    continue montando o rodapé à mão volta ao ponto de partida. Este teste
    percorre os diálogos convertidos e confere o resultado NA TELA.
    """

    def _dialogos(self):
        from isocentro.interface import gui
        return [("DialogImagemDias", gui.DialogImagemDias(25)),
                ("DialogGerenciarNomes",
                 gui.DialogGerenciarNomes("médicos", ["A", "B"]))]

    def _leituras(self):
        """As telas de LEITURA da Ficha Virtual, convertidas em 25/08/2026.

        Ficaram de fora do padrão quando ele nasceu (são de 24/08) e o usuário
        percebeu na tela: "o botão Checklist e o Campos ao abrir não assumem o
        layout do app".
        """
        from isocentro.interface import checklist as ck
        from isocentro.papel import ficha_pdf
        return [
            ("_JanelaChecklist",
             tratamento._JanelaChecklist({}, ck.ITENS, ck.MARCAS, ck.LEGENDA)),
            ("_JanelaCampos",
             tratamento._JanelaCampos([("Plano", "sABD")],
                                      [{"fase": 1, "ssd": 98.4}],
                                      ficha_pdf.CAMPOS_LINHAS[:2], "de 20/08")),
            ("_JanelaTexto",
             tratamento._JanelaTexto("deitar de bruços", "Nota", "+2 fotos")),
        ]

    def test_as_telas_da_ficha_virtual_seguem_o_padrao(self):
        """Elas GRAVAM a cada clique (o checklist) ou só mostram (as outras):
        nenhuma tem o que confirmar, então o rodapé é o de leitura — saída
        única chamada "Fechar", sem sólido e sem "Cancelar"."""
        for nome, d in self._leituras():
            with self.subTest(dialogo=nome):
                try:
                    d.show()
                    self.assertIsInstance(d, ui.Dialogo)
                    self.assertEqual(_rodape(d), ["<vão>", "Fechar"])
                finally:
                    _destruir(d)

    def test_nenhuma_delas_sombreia_corpo_ou_rodape(self):
        """``self.corpo`` e ``self.rodape`` são o layout e o método do
        ``ui.Dialogo``. Um QLabel com um desses nomes os apaga da instância — e
        a janela abre sem botão e sem lugar para o próprio conteúdo. As três
        tinham um: ``rodape`` no checklist e ``corpo`` na nota."""
        for nome, d in self._leituras():
            with self.subTest(dialogo=nome):
                try:
                    self.assertTrue(callable(d.rodape), "rodape sombreado")
                    self.assertFalse(isinstance(d.corpo, QLabel),
                                     "corpo sombreado")
                finally:
                    _destruir(d)

    def test_todos_confirmam_a_esquerda_e_cancelam_a_direita(self):
        for nome, d in self._dialogos():
            with self.subTest(dialogo=nome):
                try:
                    d.show()
                    rot = _rodape(d)
                    self.assertEqual(rot[-1], "Cancelar", rot)
                    self.assertEqual(rot[-3], "<vão>", rot)
                finally:
                    _destruir(d)

    def test_todos_tem_UM_solido_e_ele_responde_ao_Enter(self):
        """Um sólido por tela — "o passo que não se desfaz". E o Enter cai
        nele: era o que faltava em 11 dos 14 diálogos."""
        for nome, d in self._dialogos():
            with self.subTest(dialogo=nome):
                try:
                    d.show()
                    padroes = [b.text() for b in d.findChildren(QPushButton)
                               if b.isDefault()]
                    self.assertEqual(len(padroes), 1, padroes)
                    self.assertIs(d.botao_confirmar.isDefault(), True)
                finally:
                    _destruir(d)

    def test_o_Enter_no_campo_de_nome_ADICIONA_sem_fechar(self):
        """Quem cadastra três médicos perdia a janela no primeiro.

        O Enter do campo era entregue ao botão DEFAULT do diálogo — o "Salvar"
        do rodapé —, então digitar um nome e apertar Enter acrescentava e
        fechava na mesma tecla. ``setAutoDefault(False)`` no "＋ Adicionar" não
        cobria isso: o problema estava do outro lado da faixa.
        """
        from PySide6.QtTest import QTest

        from isocentro.interface import gui
        d = gui.DialogGerenciarNomes("médicos", ["Ana Souza"])
        try:
            d.show()
            d.ed.setFocus()
            QTest.keyClicks(d.ed, "Bruno Lima")
            QTest.keyClick(d.ed, Qt.Key_Return)
            self.assertEqual(d.resultado(), ["Ana Souza", "Bruno Lima"])
            self.assertTrue(d.isVisible(), "a janela fechou no Enter do campo")
            # E o Enter FORA do campo continua salvando — é o padrão das 14.
            d.lst.setFocus()
            QTest.keyClick(d, Qt.Key_Return)
            self.assertFalse(d.isVisible())
        finally:
            _destruir(d)

    def test_nenhum_botao_do_rodape_tem_folha_CONGELADA(self):
        """``setStyleSheet(estilo.btn_*())`` congela as cores do momento em que
        o widget nasceu; ``estilo.pintar`` guarda a RECEITA e acompanha a troca
        dia↔noite. Eram 19 sítios congelados — a regra do CLAUDE.md valendo
        para o código novo, e não só no papel."""
        from isocentro.interface import estilo
        for nome, d in self._dialogos():
            with self.subTest(dialogo=nome):
                origem = estilo.modo()
                self.addCleanup(estilo.definir_modo, origem)
                try:
                    d.show()
                    antes = d.botao_confirmar.styleSheet()
                    # "dia"/"noite" são os nomes do módulo. Um nome inventado
                    # não levanta erro — ``_aplicar`` cai no padrão —, e o
                    # teste passaria a comparar a folha com ela mesma.
                    estilo.definir_modo("dia" if origem == "noite"
                                        else "noite")
                    self.assertNotEqual(
                        d.botao_confirmar.styleSheet(), antes,
                        "o botão não acompanhou a troca de modo")
                finally:
                    _destruir(d)


@unittest.skipIf(ui is None, "ui indisponível (PyQt5?)")
class TestAtalhos(unittest.TestCase):

    def test_o_atalho_vai_ESCRITO_no_tooltip(self):
        """Atalho que não aparece em lugar nenhum não é descoberto, e não ser
        descoberto é o mesmo que não existir."""
        b = QPushButton("Impressão")
        b.setToolTip("Gera o PDF da ficha.")
        alvo = QLabel()
        try:
            ui.atalho("Ctrl+P", alvo, lambda: None, botao=b)
            self.assertIn("Gera o PDF da ficha.", b.toolTip())
            self.assertIn("(Ctrl+P)", b.toolTip())
        finally:
            _destruir(alvo)

    def test_anunciar_duas_vezes_nao_repete_a_tecla(self):
        """``definir_ativo`` reescreve o tooltip a cada mudança de estado; sem
        a guarda o botão acabava com "(Ctrl+P) (Ctrl+P) (Ctrl+P)"."""
        b = QPushButton("x")
        ui.anunciar_atalho(b, "Ctrl+P")
        ui.anunciar_atalho(b, "Ctrl+P")
        self.assertEqual(b.toolTip().count("Ctrl+P"), 1)

    def test_a_janela_anuncia_os_atalhos_nos_botoes(self):
        """Um programa usado com o paciente na mesa tinha DOIS atalhos e
        nenhuma barra de menus. Se o atalho não está escrito no botão, ninguém
        o descobre — e não ser descoberto é o mesmo que não existir."""
        from isocentro.interface import gui
        j = gui.JanelaPrincipal(
            usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        try:
            for botao, tecla in ((j.btn_pasta, "Ctrl+O"),
                                 (j.btn_pdf, "Ctrl+P"),
                                 (j.btn_edicao, "Ctrl+E"),
                                 (j.btn_tratados, "Ctrl+H")):
                with self.subTest(tecla=tecla):
                    self.assertIn(f"({tecla})", botao.toolTip())
        finally:
            j.deleteLater()

    def test_nenhum_atalho_em_acao_DESTRUTIVA(self):
        """Atalho não pergunta, e a mão erra a tecla. "Limpar" é o único botão
        destrutivo da bancada e tem de continuar exigindo o clique."""
        from isocentro.interface import gui
        j = gui.JanelaPrincipal(
            usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        try:
            self.assertNotIn("Ctrl", j.btn_limpar.toolTip())
        finally:
            j.deleteLater()

    def test_o_atalho_principal_respeita_o_botao_APAGADO(self):
        """Botão aceso significa pronto — o atalho não pode ser a porta dos
        fundos de um passo que a tela está negando."""
        from isocentro.interface import gui
        j = gui.JanelaPrincipal(
            usuario={"usuario": "t", "nome": "T", "papel": "fisico"})
        try:
            chamou = []
            j._escolher_ficha = lambda: chamou.append("ficha")
            j._abrir_pasta = lambda: chamou.append("pasta")
            j.btn_pdf.setEnabled(False)     # bancada vazia: sólido é a pasta
            j._acao_principal()
            self.assertEqual(chamou, ["pasta"])
            j.btn_pdf.setEnabled(True)      # caso montado: sólido é a impressão
            j._acao_principal()
            self.assertEqual(chamou, ["pasta", "ficha"])
        finally:
            j.deleteLater()

    def test_o_atalho_nao_atravessa_modal(self):
        """``ApplicationShortcut`` continuaria disparando ação na janela de
        trás com um modal aberto — a definição de clique fantasma."""
        alvo = QLabel()
        try:
            atl = ui.atalho("Ctrl+P", alvo, lambda: None)
            self.assertEqual(atl.context(), Qt.WindowShortcut)
        finally:
            _destruir(alvo)


# Esvazia ``estilo._ouvintes`` entre um teste e o seguinte. Sem isto, a lista
# cresce durante o arquivo inteiro e cada repintura percorre tudo o que já se
# acumulou — ver ``tests/limpeza_de_tela.py`` para os números.
from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


if __name__ == "__main__":
    unittest.main()
