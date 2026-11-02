"""Quadro de Documentação da Fichinha: o estado da preparação em cada linha.

A frente 2 da ficha temporária (11/09/2026). A dedução do estado é do
``gatilho_registro`` e se testa lá; aqui fica o que só a tela pode errar — o
aviso que some do tooltip, a coluna que deixa de ser coluna, e o que a linha
oferece antes de a liberação existir.

**O que a v8 mudou aqui** (23/09/2026): o clique na linha SELECIONA em vez de
disparar a carga, e o que abre o caso são os ícones que aparecem no hover
(``_pedir_acao_doc``). A liberação, que trocava o texto de um botão da trilha,
agora é o tooltip do ícone 🖨 — ícone não tem rótulo.

Rodar:  python -m unittest tests.test_fichinha_documentacao -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel, QListWidget
    _APP = QApplication.instance() or QApplication([])
    from isocentro.dominio import gatilho_registro as gr
    from isocentro.interface import fichinha
except Exception:  # noqa: BLE001
    fichinha = None

from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


PASTA_DO_CASO = "X:/tmp/9000001/C1"


def _entrada(automacao=None):
    return {"dono": "Leonardo Moraes", "paciente": "Fulano de Tal",
            "registro": "9000001", "data": "11/09", "titulo": "Documentação",
            "estado": "Open", "instancia": 7, "automacao": automacao}


def _pronta(pasta=PASTA_DO_CASO):
    return _entrada({"estado": gr.PRONTA, "avisos": [], "planos": ["P1"],
                     "desde": "", "pasta": pasta})


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class EstadoNaLinha(unittest.TestCase):

    def setUp(self):
        self.p = fichinha.PainelFichinha()

    def _estado(self, linha: int) -> QLabel:
        item = self.p.atividades.item(linha)
        return self.p.atividades.itemWidget(item).findChild(
            QLabel, "estado_automacao")

    def test_pronta_com_aviso_o_aviso_vem_primeiro_no_tooltip(self):
        """"Sem cadastro de simulação" muda o gesto do físico — ele vai montar
        o posicionamento à mão. Depois do nome do dono, ninguém chega a ler."""
        self.p.definir_atividades([_entrada({
            "estado": gr.PRONTA, "avisos": ["sem cadastro de simulação"],
            "planos": ["P1"], "desde": "2026-09-11T14:02:00"})])
        self.assertEqual(self._estado(0).text(), "● PRONTA")
        dica = self.p.atividades.item(0).toolTip()
        self.assertTrue(dica.startswith("⚠ sem cadastro de simulação"), dica)
        self.assertIn("11/09 14:02", dica)

    def test_incompleta_diz_o_motivo_de_cada_plano(self):
        """Sem o motivo, um plano travado por falha de C-MOVE pareceria só
        "ainda preparando" para sempre."""
        self.p.definir_atividades([_entrada({
            "estado": gr.INCOMPLETA, "desde": "2026-09-11T09:00:00",
            "motivos": ["P2: o DICOM chegou pela metade: 3 arquivo(s)"]})])
        self.assertEqual(self._estado(0).text(), "⚠ incompleta")
        self.assertIn("P2: o DICOM chegou pela metade",
                      self.p.atividades.item(0).toolTip())

    def test_coluna_do_estado_tem_a_mesma_largura_com_e_sem_estado(self):
        """Colada ao texto, a data andaria de lugar de uma linha para a outra,
        e a coluna de datas deixaria de ser coluna."""
        self.p.definir_atividades([
            _entrada({"estado": gr.PRONTA, "avisos": [], "planos": [],
                      "desde": ""}),
            _entrada(None),
            _entrada({"estado": gr.PREPARANDO, "desde": ""}),
        ])
        larguras = {self._estado(i).width() for i in range(3)}
        self.assertEqual(len(larguras), 1, larguras)
        self.assertEqual(self._estado(1).text(), "")
        # Sem estado conhecido, o tooltip é o de antes: nada de linha vazia
        # no topo anunciando um estado que não existe.
        self.assertTrue(self.p.atividades.item(1).toolTip().startswith(
            "Leonardo Moraes"))

    def test_caso_liberado_sai_do_quadro(self):
        """Pedido do usuário em 09/10/2026: "ficha liberada sai da
        documentação disponível". A linha ficava marcada "✓ liberada" até
        alguém concluir a atividade no ARIA, ocupando lugar de trabalho que
        já estava feito."""
        liberada = _entrada({"estado": gr.LIBERADA, "desde": ""})
        liberada["paciente"] = "Liberado"
        self.p.definir_atividades([_pronta(), liberada])
        pacientes = [self.p._entrada(self.p.atividades.item(i)).get("paciente")
                     for i in range(self.p.atividades.count())]
        self.assertEqual(pacientes, ["Fulano de Tal"])

    def test_todos_liberados_e_quadro_em_dia(self):
        """Sem nenhuma linha a fazer, o quadro diz isso — e não "não deu para
        perguntar", que é outra coisa."""
        self.p.definir_atividades([_entrada({"estado": gr.LIBERADA})])
        self.assertEqual(self.p.atividades.count(), 1)
        self.assertIn("Nenhuma documentação",
                      self.p.atividades.item(0).text())

    def test_liberado_que_voltou_a_pronta_reaparece(self):
        """Plano reaprovado depois da liberação: o registro devolve ``pronta``
        (ver ``gatilho_registro.estados_da_documentacao``), e a linha tem de
        estar no quadro — é ficha nova para conferir."""
        self.p.definir_atividades([_pronta()])
        self.assertEqual(self._estado(0).text(), "● PRONTA")

    def test_a_lista_escolhe_UMA_linha(self):
        """Na v7 o clique ABRIA o caso e a lista não tinha seleção nenhuma.

        Com a ação na linha, a seleção voltou a existir — é ela que o
        ``_atualizar_trilha`` usa para reacender os ícones quando a ficha muda
        de estado com o cursor parado em cima. Múltipla ela não pode ser: os
        três ícones agem sobre UM caso, e a lista ofereceria marcar cinco.
        """
        self.p.definir_atividades([_pronta(), _pronta()])
        self.assertEqual(self.p.atividades.selectionMode(),
                         QListWidget.SingleSelection)

    def test_o_responsavel_aparece_so_pelo_primeiro_nome(self):
        """Pedido do usuário em 23/09/2026: "nome completo do paciente, usar
        iniciais para o físico, ou somente o primeiro nome".

        O responsável ocupava a coluna maior com o nome inteiro MAIS as
        iniciais entre parênteses, e o que sobrava ao paciente dava
        "Joao Carlos de Ol…".
        """
        e = _entrada()
        e["dono"] = "Ana Fatima Albuquerque (AC)"
        self.p.definir_atividades([e])
        linha = self.p.atividades.itemWidget(self.p.atividades.item(0))
        self.assertEqual(linha.layout().itemAt(0).widget().text(), "Ana")
        # O nome inteiro continua a um passe de mouse de distância.
        self.assertIn("Ana Fatima Albuquerque (AC)",
                      self.p.atividades.item(0).toolTip())

    def test_o_paciente_leva_a_coluna_maior(self):
        """É o único dado da linha que precisa ser lido por inteiro: o
        responsável cabe em qualquer largura agora."""
        self.p.definir_atividades([_pronta()])
        lay = self.p.atividades.itemWidget(
            self.p.atividades.item(0)).layout()
        self.assertGreater(lay.stretch(1), lay.stretch(0))

    def test_atividade_sem_responsavel_diz_isso(self):
        """Em branco, a coluna leria como "é minha" para quem passa o olho."""
        e = _entrada()
        e["dono"] = ""
        self.p.definir_atividades([e])
        linha = self.p.atividades.itemWidget(self.p.atividades.item(0))
        self.assertEqual(linha.layout().itemAt(0).widget().text(),
                         "(sem responsável)")

    def test_liberada_nao_fica_no_quadro_nem_para_ser_liberada_de_novo(self):
        """Até 09/10/2026 a linha ficava "✓ liberada", com quem liberou e para
        onde no tooltip — a marca existia para o próximo físico não liberar de
        novo. Agora a linha SAI (pedido do usuário: "ficha liberada sai da
        documentação disponível"), o que protege do mesmo jeito: não há o que
        clicar. Quem liberou e para onde continuam no ``gatilho_registro`` e no
        histórico de uso."""
        self.p.definir_atividades([_entrada({
            "estado": gr.LIBERADA, "desde": "2026-09-11T20:10:00",
            "por": "Fulana Física", "pasta": "Y:/sim/FULANO_9000001/09-2026"})])
        self.assertIsNone(self.p._entrada(self.p.atividades.item(0)))


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class OQueAbreOCaso(unittest.TestCase):
    """Só o ``● PRONTA`` com pasta abre alguma coisa — e por um ÍCONE.

    Até a v7 quem abria era o clique na linha. Passou a ser o ícone porque a
    linha ganhou três destinos diferentes (ver, editar, imprimir) e um clique
    só não escolhe entre três.
    """

    def setUp(self):
        self.p = fichinha.PainelFichinha()
        self.pedidos = []
        self.p.abrir_documentacao.connect(self.pedidos.append)

    def _visualizar(self, automacao):
        self.p.definir_atividades([_entrada(automacao)])
        self.p._pedir_acao_doc(fichinha.VISUALIZAR, _entrada(automacao))

    def test_pronta_com_pasta_pede_para_abrir(self):
        self._visualizar({"estado": gr.PRONTA, "avisos": [], "planos": ["P1"],
                          "desde": "", "pasta": PASTA_DO_CASO})
        self.assertEqual(len(self.pedidos), 1)
        self.assertEqual(self.pedidos[0]["automacao"]["pasta"], PASTA_DO_CASO)
        self.assertEqual(self.pedidos[0]["instancia"], 7)

    def test_pronta_sem_pasta_nao_abre(self):
        """Planos em pastas diferentes: abrir uma carregaria parte do curso, e
        a ficha sairia pela metade."""
        self._visualizar({"estado": gr.PRONTA, "avisos": [], "planos": [],
                          "desde": "", "pasta": ""})
        self.assertEqual(self.pedidos, [])

    def test_preparando_incompleta_e_liberada_nao_abrem(self):
        for estado in (gr.PREPARANDO, gr.INCOMPLETA, gr.LIBERADA):
            self._visualizar({"estado": estado, "desde": "",
                              "pasta": PASTA_DO_CASO})
        self.assertEqual(self.pedidos, [])

    def test_durante_a_carga_nao_troca_o_paciente(self):
        """Ficaria na fila e trocaria o paciente assim que a carga soltasse."""
        self.p.definir_estado(fichinha.CARREGANDO)
        self._visualizar({"estado": gr.PRONTA, "avisos": [], "planos": [],
                          "desde": "", "pasta": PASTA_DO_CASO})
        self.assertEqual(self.pedidos, [])

    def test_o_clique_na_linha_apenas_ESCOLHE(self):
        """Na v7 ele disparava a carga na hora.

        Escolher e carregar viraram gestos diferentes porque a linha passou a
        ter três destinos: o clique que abrisse o caso sozinho escolheria um
        deles por conta própria.
        """
        self.p.definir_atividades([_pronta()])
        self.p.atividades.setCurrentRow(0)
        self.assertEqual(self.pedidos, [])
        self.assertIsNotNone(self.p.documentacao_escolhida())

    def test_linha_escolhida_que_nao_esta_pronta_nao_conta(self):
        """O Qt deixa marcar qualquer uma; sem o filtro, o «Visualizar»
        acenderia sobre uma Documentação que ainda não virou arquivo nenhum."""
        self.p.definir_atividades([_entrada({"estado": gr.PREPARANDO,
                                             "desde": ""})])
        self.p.atividades.setCurrentRow(0)
        self.assertIsNone(self.p.documentacao_escolhida())


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class LiberarEmVezDeImprimir(unittest.TestCase):
    """O ícone 🖨 quando o caso veio da pasta temporária.

    **O defeito que este bloco passou a guardar** (23/09/2026):
    ``definir_liberacao`` ainda escrevia em ``self.btn_imprimir``, que a v8
    apagou junto com a trilha de botões. Como ``gui.py`` chama
    ``definir_liberacao(None)`` em TODA carga de pasta, o app levantava
    ``AttributeError`` ao abrir qualquer caso — e a suíte quebrada desta tela
    era justamente o que escondia isso.
    """

    def setUp(self):
        self.p = fichinha.PainelFichinha()
        self.p.definir_atividades([_pronta()])
        self.p.definir_caminho(PASTA_DO_CASO)
        self.p.definir_estado(fichinha.VISTA)
        self.p.definir_previa(True)
        self.p.atividades.setCurrentRow(0)

    def _icone(self, chave=None):
        item = self.p.atividades.item(0)
        self.p._hover_doc(item)
        return self.p.atividades.itemWidget(item)._botoes[
            chave or fichinha.IMPRIMIR]

    def test_sem_liberacao_e_a_impressao_de_sempre(self):
        self.p.definir_liberacao(None)
        icone = self._icone()
        self.assertTrue(icone.isEnabled())
        self.assertEqual(icone.toolTip(), fichinha._DICAS_DOC[fichinha.IMPRIMIR])

    def test_quem_pode_ve_o_icone_aceso_dizendo_que_libera(self):
        self.p.definir_liberacao({"permitido": True})
        icone = self._icone()
        self.assertTrue(icone.isEnabled())
        self.assertIn("Liberar para impressão", icone.toolTip())

    def test_quem_nao_pode_ve_apagado_com_o_motivo(self):
        """Ícone aceso significa pronto: clicar só para ouvir "não é seu"
        seria o aceso que mente."""
        self.p.definir_liberacao({"permitido": False})
        icone = self._icone()
        self.assertFalse(icone.isEnabled())
        self.assertIn("físico", icone.toolTip())

    def test_quem_nao_pode_tambem_nao_emite_por_dentro(self):
        """O ícone apagado barra o clique; o atalho entra por outro caminho."""
        impressoes = []
        self.p.pedir_impressao.connect(lambda: impressoes.append(1))
        self.p.definir_liberacao({"permitido": False})
        self.p._pedir_acao_doc(fichinha.IMPRIMIR, _pronta())
        self.assertEqual(impressoes, [])

    def test_voltar_a_none_desfaz_a_dica(self):
        """A pasta aberta à mão depois de um caso da temporária não pode
        continuar anunciando liberação."""
        self.p.definir_liberacao({"permitido": True})
        self.p.definir_liberacao(None)
        self.assertEqual(self._icone().toolTip(),
                         fichinha._DICAS_DOC[fichinha.IMPRIMIR])

    def test_definir_liberacao_nao_quebra_sem_caso_na_tela(self):
        """É o caminho exato de ``gui.py``: toda carga de pasta começa por
        ``definir_liberacao(None)``, com a lista ainda vazia."""
        p = fichinha.PainelFichinha()
        p.definir_liberacao(None)
        p.definir_liberacao({"permitido": True})
        self.assertIsNotNone(p._liberacao)


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class QuemLibera(unittest.TestCase):

    def test_fisico_e_admin_liberam(self):
        self.assertTrue(fichinha.pode_liberar("fisico"))
        self.assertTrue(fichinha.pode_liberar("Admin "))

    def test_outras_funcoes_nao(self):
        """Papel desconhecido cai no "não": liberar é o passo que manda a
        ficha para a sala."""
        for papel in ("medico", "dosimetrista", "tecnico", "papel_novo"):
            self.assertFalse(fichinha.pode_liberar(papel), papel)


if __name__ == "__main__":
    unittest.main()
