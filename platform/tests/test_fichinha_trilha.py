"""Trilha da tela Fichinha: quando cada ÍCONE de linha pode estar aceso.

A promessa continua sendo "aceso significa pronto", mas na v8 ela mudou de
lugar: até a v7 a trilha era uma grade de quatro botões no cartão central, e
desde 23/09/2026 são três ícones que aparecem no hover da LINHA da Documentação
(``👁 Visualizar · ✏ Editar · 🖨 Imprimir``). O cartão, o campo de caminho e o
botão ⚡ não existem mais — quem os procurar aqui está lendo a suíte da v7.

O que mudou de REGRA, e não só de widget:

* **Visualizar e Editar acendem com a linha**, mesmo sem ficha montada: os dois
  montam o caso quando ele ainda não está montado (decisão do usuário em
  22/09/2026). Exigir a ficha pronta obrigaria a passar pela visualização para
  poder editar;
* **a Impressão continua esperando a Visualização** — a única regra da trilha
  que não se negocia — e agora espera a visualização DESTA linha: imprimir com
  o caso anterior montado sairia com o nome do paciente novo na tela e o
  documento do antigo na bandeja;
* **o campo do caminho saiu**, e com ele o ``×`` que fechava o caso. Quem faz
  isso agora é a janela, por ``limpar_caso()``.

Rodar:  python -m unittest discover -s tests -v
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
    from PySide6.QtWidgets import QApplication, QLabel
    _APP = QApplication.instance() or QApplication([])
    from isocentro.dominio import gatilho_registro as gr
    from isocentro.interface import fichinha
except Exception as exc:  # noqa: BLE001
    fichinha = None
    _MOTIVO = str(exc)


PASTA_DO_CASO = r"C:\casos\paciente"


def _preparada(pasta=PASTA_DO_CASO, **extra):
    """Uma linha de Documentação ``● PRONTA`` — a única que abre alguma coisa."""
    e = {"dono": "Leonardo Moraes", "paciente": "Fulano de Tal",
         "registro": "9000001", "data": "22/09", "titulo": "Documentação",
         "estado": "Open", "instancia": 7,
         "automacao": {"estado": gr.PRONTA, "avisos": [], "planos": ["P1"],
                       "desde": "", "pasta": pasta}}
    e.update(extra)
    return e


def _icones(lista, linha=0) -> dict:
    """Os botões de ação da linha ``linha``, pela chave da ação."""
    return lista.itemWidget(lista.item(linha))._botoes


def _acesos(lista, linha=0) -> set:
    return {k for k, b in _icones(lista, linha).items() if b.isEnabled()}


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class TestTrilha(unittest.TestCase):
    """Os três ícones da Documentação, na linha de um caso preparado."""

    def setUp(self):
        self.p = fichinha.PainelFichinha()
        self.p.definir_atividades([_preparada()])
        self.p.definir_caminho(PASTA_DO_CASO)
        # Selecionar a linha é o que põe ``_atualizar_trilha`` a reacendê-la a
        # cada mudança de estado — o mesmo caminho do cursor parado em cima
        # dela enquanto a ficha termina de montar.
        self.p.atividades.setCurrentRow(0)

    def _montada(self, com_previa=True):
        self.p.definir_estado(fichinha.PRONTA)
        self.p.definir_previa(com_previa)

    def test_a_linha_sozinha_ja_acende_visualizar_e_editar(self):
        """Antes da v8 os dois exigiam ficha montada, e montar era outro botão.

        Com o ⚡ fora da tela, exigir ficha pronta deixaria a linha sem nenhum
        gesto possível: não haveria por onde montar o caso.
        """
        self.assertEqual(_acesos(self.p.atividades),
                         {fichinha.VISUALIZAR, fichinha.EDITAR})

    def test_ficha_montada_sem_previa_nao_acende_a_impressao(self):
        """Multi-plano esperando agendamento: montado, mas não conferível.

        Acesa sem prévia, a Impressão mandaria para a bandeja um documento que
        o programa ainda não conseguiu fechar.
        """
        self._montada(com_previa=False)
        self.assertNotIn(fichinha.IMPRIMIR, _acesos(self.p.atividades))
        # Editar continua: é por ela que se resolve o que falta.
        self.assertIn(fichinha.EDITAR, _acesos(self.p.atividades))

    def test_impressao_so_depois_de_ver(self):
        self._montada()
        self.assertNotIn(fichinha.IMPRIMIR, _acesos(self.p.atividades))
        self.p.definir_estado(fichinha.VISTA)
        self.p.definir_previa(True)
        self.assertIn(fichinha.IMPRIMIR, _acesos(self.p.atividades))

    def test_editar_depois_de_ver_derruba_a_previa(self):
        """O PDF em disco é da versão anterior à edição."""
        self._montada()
        self.p.definir_estado(fichinha.VISTA)
        self.p.definir_previa(True)
        self.p.invalidar_visualizacao()
        self.assertFalse(self.p.previa_pronta())
        self.assertNotIn(fichinha.IMPRIMIR, _acesos(self.p.atividades))

    def test_a_carga_apaga_os_tres(self):
        """O clique dado durante a montagem ficaria na fila e trocaria o
        paciente assim que ela soltasse."""
        self._montada()
        self.p.definir_estado(fichinha.CARREGANDO)
        self.assertEqual(_acesos(self.p.atividades), set())

    def test_caso_novo_zera_a_previa(self):
        self._montada()
        self.p.definir_estado(fichinha.CARREGANDO)
        self.assertFalse(self.p.previa_pronta())

    def test_trabalho_em_curso_apaga_tudo(self):
        """Mesmo perigo da carga, por outra porta: gerar o PDF também trava a
        interface, e o clique acumulado dispararia uma segunda geração."""
        self._montada()
        self.p.definir_estado(fichinha.VISTA)
        self.p.bloquear(True)
        self.assertEqual(_acesos(self.p.atividades), set())
        self.assertFalse(self.p.atividades.isEnabled())
        self.p.bloquear(False)
        self.assertTrue(self.p.atividades.isEnabled())
        self.assertIn(fichinha.VISUALIZAR, _acesos(self.p.atividades))

    def test_linha_que_nao_esta_pronta_nao_oferece_nada(self):
        """O Qt deixa marcar qualquer linha; sem este filtro o «Visualizar»
        acenderia sobre uma Documentação que ainda não virou arquivo nenhum."""
        # LIBERADA não está mais aqui: desde 09/10/2026 ela nem entra no
        # quadro (ver ``test_fichinha_documentacao``).
        for estado in (gr.PREPARANDO, gr.INCOMPLETA):
            with self.subTest(estado=estado):
                e = _preparada()
                e["automacao"] = {"estado": estado, "desde": "",
                                  "pasta": PASTA_DO_CASO}
                self.p.definir_atividades([e])
                self.p.atividades.setCurrentRow(0)
                self.assertEqual(_acesos(self.p.atividades), set())

    def test_pronta_sem_pasta_tambem_nao(self):
        """Planos em pastas diferentes: abrir uma carregaria parte do curso, e
        a ficha sairia pela metade."""
        self.p.definir_atividades([_preparada(pasta="")])
        self.p.atividades.setCurrentRow(0)
        self.assertEqual(_acesos(self.p.atividades), set())


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class TestFecharOCaso(unittest.TestCase):
    """``limpar_caso()`` — herdeira do ``×`` que sumiu com o campo.

    A janela precisa de um jeito de dizer "este caso não está mais aqui": sem
    ele, a faixa do topo continuaria falando de um paciente que saiu da
    bancada, e a Capa (que fica em outra tela) arquivaria a simulação do
    próximo no nome do anterior.
    """

    def setUp(self):
        self.p = fichinha.PainelFichinha()
        self.p.definir_atividades([_preparada()])
        self.p.definir_caminho(PASTA_DO_CASO)
        self.p.atividades.setCurrentRow(0)
        self.pedidos = []
        self.p.fechar_caso.connect(self.pedidos.append)

    def test_fechar_desliga_a_trilha(self):
        self.p.definir_estado(fichinha.VISTA)
        self.p.definir_previa(True)
        self.p.limpar_caso()
        self.assertEqual(self.p.estado(), fichinha.INICIAL)
        self.assertEqual(self.p.caminho(), "")
        # Visualizar e Editar continuam acesos — a LINHA ainda está lá, e é
        # por ela que o caso renasce. O que não pode sobrar é a Impressão,
        # que apontaria para o PDF do caso que acabou de sair.
        self.assertEqual(_acesos(self.p.atividades),
                         {fichinha.VISUALIZAR, fichinha.EDITAR})

    def test_fechar_leva_de_onde_a_trilha_saiu(self):
        """Recusar tem de devolver o caso ao MESMO ponto, senão quem cancelou
        perde o Imprimir."""
        self.p.definir_estado(fichinha.VISTA)
        self.p.limpar_caso()
        self.assertEqual(self.pedidos, [fichinha.VISTA])

    def test_sem_ficha_montada_nao_pede_nada(self):
        """Sem caso na bancada não há o que fechar no resto do app."""
        self.p.limpar_caso()
        self.assertEqual(self.pedidos, [])

    def test_o_caso_de_volta_nao_ressuscita_a_previa(self):
        """Montar de novo é um clique; a prévia é do documento anterior."""
        self.p.definir_estado(fichinha.VISTA)
        self.p.definir_previa(True)
        self.p.limpar_caso()
        self.p.definir_caminho(PASTA_DO_CASO)
        self.assertFalse(self.p.previa_pronta())
        self.assertNotIn(fichinha.IMPRIMIR, _acesos(self.p.atividades))


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class TestAImpressaoEDaLinhaMontada(unittest.TestCase):
    """A Impressão só acende na linha DO caso que está montado.

    É o perigo que na v7 morava no campo de texto — digitar outra pasta por
    cima deixava a trilha descrevendo o caso anterior. Com cinco linhas na
    lista, ele voltou por outra porta: passar o cursor na linha do vizinho não
    pode oferecer a impressão do documento que está na tela.
    """

    def setUp(self):
        self.p = fichinha.PainelFichinha()
        self.p.definir_atividades([_preparada(),
                                   _preparada(pasta=r"C:\casos\outro",
                                              registro="9000002")])
        self.p.definir_caminho(PASTA_DO_CASO)
        self.p.definir_estado(fichinha.VISTA)
        self.p.definir_previa(True)

    def _acender(self, linha):
        self.p._hover_doc(self.p.atividades.item(linha))
        return _acesos(self.p.atividades, linha)

    def test_a_linha_do_caso_montado_imprime(self):
        self.assertIn(fichinha.IMPRIMIR, self._acender(0))

    def test_a_linha_do_vizinho_nao(self):
        self.assertNotIn(fichinha.IMPRIMIR, self._acender(1))
        # E continua oferecendo o que faz sentido: montar o caso dela.
        self.assertEqual(self._acender(1),
                         {fichinha.VISUALIZAR, fichinha.EDITAR})

    def test_mesma_pasta_escrita_de_outro_jeito_e_a_mesma(self):
        """Barra invertida e maiúscula não são "outro paciente"."""
        self.p.definir_atividades([_preparada(pasta="C:/casos/PACIENTE\\")])
        self.assertIn(fichinha.IMPRIMIR, self._acender(0))


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class TestOsPedidosDaDocumentacao(unittest.TestCase):
    """O que cada ícone emite — e o que ele faz quando o caso não está montado."""

    def setUp(self):
        self.p = fichinha.PainelFichinha()
        self.p.definir_atividades([_preparada()])
        self.p.atividades.setCurrentRow(0)
        self.abertas = []
        self.p.abrir_documentacao.connect(self.abertas.append)

    def _clicar(self, acao, linha=0):
        self.p._hover_doc(self.p.atividades.item(linha))
        _icones(self.p.atividades, linha)[acao].click()

    def test_visualizar_sem_caso_montado_pede_a_carga_com_o_destino(self):
        """Montar leva segundos e acontece noutra thread: o que fazer DEPOIS
        não dá para decidir aqui, então viaja junto no pedido."""
        self._clicar(fichinha.VISUALIZAR)
        self.assertEqual(len(self.abertas), 1)
        self.assertEqual(self.abertas[0]["apos"], fichinha.VISUALIZAR)
        self.assertEqual(self.abertas[0]["instancia"], 7)

    def test_editar_sem_caso_montado_pede_a_carga_com_o_destino(self):
        self._clicar(fichinha.EDITAR)
        self.assertEqual(self.abertas[0]["apos"], fichinha.EDITAR)

    def test_com_o_caso_ja_na_tela_o_icone_faz_so_o_seu_passo(self):
        """Remontar o que já está montado custaria os mesmos segundos de
        carga para chegar ao mesmo lugar."""
        vistas, edicoes = [], []
        self.p.pedir_visualizacao.connect(lambda: vistas.append(1))
        self.p.abrir_edicao.connect(lambda: edicoes.append(1))
        self.p.definir_caminho(PASTA_DO_CASO)
        self.p.definir_estado(fichinha.PRONTA)
        self.p.definir_previa(True)
        self._clicar(fichinha.VISUALIZAR)
        self._clicar(fichinha.EDITAR)
        self.assertEqual((len(vistas), len(edicoes)), (1, 1))
        self.assertEqual(self.abertas, [])

    def test_imprimir_pede_a_impressao(self):
        impressoes = []
        self.p.pedir_impressao.connect(lambda: impressoes.append(1))
        self.p.definir_caminho(PASTA_DO_CASO)
        self.p.definir_estado(fichinha.VISTA)
        self.p.definir_previa(True)
        self._clicar(fichinha.IMPRIMIR)
        self.assertEqual(len(impressoes), 1)

    def test_icone_apagado_nao_emite(self):
        """O atalho de teclado e o duplo clique chegam por dentro, sem passar
        pelo ``isEnabled`` do botão."""
        self.p._pedir_acao_doc(fichinha.IMPRIMIR, _preparada())
        self.assertEqual(self.abertas, [])


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class TestFichasRecentes(unittest.TestCase):
    """A lista "Suas últimas fichas" — agora um dos cinco cartões."""

    def setUp(self):
        self.p = fichinha.PainelFichinha()

    @staticmethod
    def _entradas(n, **extra):
        base = {"n_versoes": 2, "json_path": r"C:\casos\FICHA.json"}
        base.update(extra)
        return [{"em": f"2026-08-{10 + i:02d}T14:30:00",
                 "paciente": f"PACIENTE {i}", "registro": str(100 + i),
                 "versao": 1, "maquina": "TB1",
                 "pasta": rf"C:\casos\p{i}", **base} for i in range(n)]

    def test_vazio_convida_em_vez_de_sumir(self):
        """Escondê-la faria a tela mudar de forma, e ninguém a descobriria."""
        self.p.definir_recentes([])
        self.assertEqual(self.p.recentes.count(), 1)
        self.assertIn("Nenhuma ficha", self.p.recentes.item(0).text())
        # O convite não é uma ficha: não pode ser clicado.
        self.assertFalse(self.p.recentes.item(0).flags() & Qt.ItemIsEnabled)

    def test_uma_linha_por_entrada_com_os_dados_junto(self):
        self.p.definir_recentes(self._entradas(3), hoje=3)
        self.assertEqual(self.p.recentes.count(), 3)
        dados = self.p.recentes.item(0).data(Qt.UserRole)
        self.assertEqual(dados["registro"], "100")
        self.assertEqual(dados["pasta"], r"C:\casos\p0")

    def test_as_acoes_so_aparecem_sob_o_cursor(self):
        """A v8.0 tinha uma fileira de botões por bloco, e cinco blocos viraram
        cinco fileiras: a tela lia como painel de controle. O usuário recusou
        em 23/09/2026 — a ação passou a pertencer à linha."""
        self.p.definir_recentes(self._entradas(2))
        linha0 = self.p.recentes.itemWidget(self.p.recentes.item(0))
        linha1 = self.p.recentes.itemWidget(self.p.recentes.item(1))
        self.assertTrue(linha0.acoes.isHidden())
        self.p.b_recentes.linha_sob_o_cursor(self.p.recentes.item(0))
        self.assertFalse(linha0.acoes.isHidden())
        # E some da OUTRA linha: duas fileiras acesas ao mesmo tempo é o que
        # acontecia guardando "a última" em vez de percorrer a lista.
        self.assertTrue(linha1.acoes.isHidden())
        self.p.b_recentes.linha_sob_o_cursor(None)
        self.assertTrue(linha0.acoes.isHidden())

    def test_escolher_uma_ficha_nao_move_a_lista(self):
        """O que muda de tamanho arrasta a lista junto, debaixo do cursor que
        acabou de clicar — e o clique seguinte cai noutro paciente."""
        self.p.definir_recentes(self._entradas(3))
        self.p.resize(900, 800)
        self.p.show()
        self.p.repaint()
        topo = lambda: self.p.recentes.mapTo(          # noqa: E731
            self.p, self.p.recentes.rect().topLeft()).y()
        antes = topo()
        for passo in (0, 1, 2):
            self.p.recentes.setCurrentRow(passo)
            self.p.repaint()
            self.assertEqual(topo(), antes, f"linha {passo}")
        self.p.limpar_selecao_recente()
        self.p.repaint()
        self.assertEqual(topo(), antes)

    def test_a_faixa_de_acoes_nao_reflowa_a_linha(self):
        """O nome do paciente encolheria no instante em que a pessoa mira o
        ícone — e o alvo fugiria do cursor."""
        self.p.definir_recentes(self._entradas(2))
        self.p.resize(900, 800)
        self.p.show()
        self.p.repaint()
        linha = self.p.recentes.itemWidget(self.p.recentes.item(0))
        nome = linha.layout().itemAt(0).widget()
        antes = nome.width()
        self.p.b_recentes.linha_sob_o_cursor(self.p.recentes.item(0))
        self.p.repaint()
        self.assertEqual(nome.width(), antes)

    def test_cada_icone_pede_a_sua_acao(self):
        self.p.definir_recentes(self._entradas(2))
        pedidos = []
        self.p.acao_recente.connect(
            lambda a, e: pedidos.append((a, e["registro"])))
        icones = _icones(self.p.recentes, 1)
        for chave in (fichinha.CARREGAR, fichinha.VERSOES, fichinha.PDF,
                      fichinha.PASTA):
            icones[chave].click()
        self.assertEqual(pedidos, [(fichinha.CARREGAR, "101"),
                                   (fichinha.VERSOES, "101"),
                                   (fichinha.PDF, "101"),
                                   (fichinha.PASTA, "101")])

    def test_o_icone_age_sobre_a_LINHA_dele_e_nao_sobre_a_selecao(self):
        """É o que a ação de linha resolveu: não há mais "agir sobre quem?".

        Com a faixa embaixo do bloco, clicar sem conferir qual linha estava
        marcada agia sobre outro paciente.
        """
        self.p.definir_recentes(self._entradas(3))
        pedidos = []
        self.p.acao_recente.connect(lambda a, e: pedidos.append(e["registro"]))
        self.p.recentes.setCurrentRow(0)
        _icones(self.p.recentes, 2)[fichinha.CARREGAR].click()
        self.assertEqual(pedidos, ["102"])

    def test_as_acoes_sao_as_da_tela_de_historico_e_nada_mais(self):
        """Houve um "Refazer" aqui; ele saiu.

        Na pasta com ficha anterior ele abria a pergunta "reabrir ou elaborar
        nova?" — a mesma que o botão já respondia — e, com os DICOM apagados,
        virava o Carregar por um caminho mais longo.
        """
        self.p.definir_recentes(self._entradas(1))
        self.assertEqual(list(_icones(self.p.recentes, 0)),
                         [fichinha.CARREGAR, fichinha.VERSOES,
                          fichinha.PDF, fichinha.PASTA])

    def test_duplo_clique_carrega(self):
        """O mesmo gesto da tela de Histórico tem de fazer a mesma coisa."""
        self.p.definir_recentes(self._entradas(1))
        pedidos = []
        self.p.acao_recente.connect(lambda a, e: pedidos.append(a))
        self.p.recentes.setCurrentRow(0)
        self.p.recentes.itemDoubleClicked.emit(self.p.recentes.item(0))
        self.assertEqual(pedidos, [fichinha.CARREGAR])

    def test_ficha_fora_do_indice_so_oferece_o_que_da_para_fazer(self):
        """Índice limpo: o registro salvo e o PDF não existem para o app."""
        self.p.definir_recentes(self._entradas(1, n_versoes=0, json_path=""))
        # A pasta continua lá e ainda dá para abri-la; o resto depende do
        # registro salvo, que o índice não conhece mais.
        self.assertEqual(_acesos(self.p.recentes), {fichinha.PASTA})

    def test_versao_unica_nao_oferece_comparacao(self):
        """Comparar uma versão com ela mesma gastaria um clique para nada."""
        self.p.definir_recentes(self._entradas(1, n_versoes=1))
        acesos = _acesos(self.p.recentes)
        self.assertNotIn(fichinha.VERSOES, acesos)
        self.assertIn(fichinha.CARREGAR, acesos)

    def test_sem_pasta_anotada_o_indice_ainda_localiza_o_caso(self):
        """A ficha antiga não guardava a pasta; o ``json_path`` sabe onde é."""
        self.p.definir_recentes(self._entradas(1, pasta=""))
        acesos = _acesos(self.p.recentes)
        self.assertIn(fichinha.PASTA, acesos)
        self.assertIn(fichinha.CARREGAR, acesos)

    def test_icone_apagado_nao_emite(self):
        """O clique não chega, mas o duplo clique e os atalhos entram por
        dentro — e lá o ``isEnabled`` do botão não vale nada."""
        pedidos = []
        self.p.acao_recente.connect(lambda a, e: pedidos.append(a))
        self.p._pedir_acao(fichinha.VERSOES,
                           self._entradas(1, n_versoes=1)[0])
        self.assertEqual(pedidos, [])

    def test_convite_vazio_nao_emite_nada(self):
        self.p.definir_recentes([])
        pedidos = []
        self.p.acao_recente.connect(lambda a, e: pedidos.append(a))
        self.p.recentes.setCurrentRow(0)
        self.p._pedir_acao(fichinha.CARREGAR, self.p.ficha_escolhida())
        self.assertEqual(pedidos, [])

    def test_contador_do_dia(self):
        self.p.definir_recentes(self._entradas(2), hoje=0)
        self.assertFalse(self.p.lbl_hoje.isVisible())
        self.p.definir_recentes(self._entradas(2), hoje=1)
        self.assertEqual(self.p.lbl_hoje.text(), "1 ficha hoje")
        self.p.definir_recentes(self._entradas(2), hoje=7)
        self.assertEqual(self.p.lbl_hoje.text(), "7 fichas hoje")

    def test_recarregar_nao_acumula(self):
        self.p.definir_recentes(self._entradas(5))
        self.p.definir_recentes(self._entradas(2))
        self.assertEqual(self.p.recentes.count(), 2)

    def test_lista_apaga_durante_o_trabalho(self):
        """O clique dado no meio de uma carga trocaria o paciente depois."""
        self.p.definir_recentes(self._entradas(3))
        self.p.recentes.setCurrentRow(0)
        self.p.bloquear(True)
        self.assertFalse(self.p.recentes.isEnabled())
        self.p.bloquear(False)
        self.assertTrue(self.p.recentes.isEnabled())

    def test_nome_que_nao_cabe_termina_em_reticencias(self):
        """Cortado à força, o nome truncado lia-se como o nome inteiro.

        Num documento de identificação isso é o erro que não pode acontecer:
        "CLEUDIMAR NUNES DE MOURA BRITO" virava "…MOURA BRIT" sem marca nenhuma
        de que continuava.
        """
        comprido = "CLEUDIMAR NUNES DE MOURA BRITO DA CONCEICAO SOBRINHO"
        self.p.definir_recentes(self._entradas(1, paciente=comprido))
        self.p.resize(700, 800)
        self.p.show()
        self.p.repaint()
        linha = self.p.recentes.itemWidget(self.p.recentes.item(0))
        rotulo = linha.layout().itemAt(0).widget()
        self.assertLess(len(rotulo.text()), len(comprido))
        self.assertTrue(rotulo.text().endswith("…"), rotulo.text())
        # O nome inteiro continua a um passe de mouse de distância.
        self.assertIn(comprido, self.p.recentes.item(0).toolTip())

    def test_a_linha_nunca_passa_da_largura_visivel(self):
        """A data saía pela metade no canto direito.

        O palpite de tamanho do item vinha da largura NATURAL da linha, que
        inclui o nome inteiro antes de elidir. Maior que a área visível e com a
        barra horizontal desligada, o excedente era só cortado — e o que ficava
        de fora era a última coluna, não o nome.
        """
        self.p.definir_recentes(self._entradas(
            1, paciente="CLEUDIMAR NUNES DE MOURA BRITO DA CONCEICAO SOBRINHO"))
        self.p.resize(700, 800)
        self.p.show()
        self.p.repaint()
        linha = self.p.recentes.itemWidget(self.p.recentes.item(0))
        self.assertLessEqual(linha.width(), self.p.recentes.viewport().width())
        # E a última coluna termina dentro da área visível.
        ultima = linha.layout().itemAt(linha.layout().count() - 1).widget()
        self.assertLessEqual(
            ultima.mapTo(linha, ultima.rect().topRight()).x(), linha.width())

    def test_nome_que_cabe_fica_inteiro(self):
        self.p.definir_recentes(self._entradas(1, paciente="ANA LIMA"))
        self.p.resize(700, 800)
        self.p.show()
        self.p.repaint()
        linha = self.p.recentes.itemWidget(self.p.recentes.item(0))
        self.assertEqual(linha.layout().itemAt(0).widget().text(), "ANA LIMA")

    def test_quando_fala_em_vez_de_datar(self):
        import datetime

        hoje = datetime.datetime.now().replace(hour=14, minute=32)
        ontem = hoje - datetime.timedelta(days=1)
        self.assertEqual(fichinha._quando(hoje.isoformat()), "hoje 14:32")
        self.assertTrue(fichinha._quando(ontem.isoformat()).startswith("ontem"))
        self.assertEqual(fichinha._quando("1998-03-04T08:05:00"), "04/03/1998")
        self.assertEqual(fichinha._quando(""), "")   # evento sem carimbo


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class TestBarraDeModo(unittest.TestCase):

    def test_um_botao_por_modo_num_grupo_exclusivo_so(self):
        """A faixa monta um botão para CADA modo, e um só fica aceso.

        A lista era escrita à mão com os três modos de então, e a quarta tela
        (Ficha Virtual) quebrou o teste sem que nada estivesse errado. Comparar
        com ``MODOS`` prova o que interessa — que nenhum modo ficou de fora da
        faixa — e não cobra manutenção a cada tela nova.
        """
        escolhas = []
        faixa, botoes = fichinha.barra_de_modo(escolhas.append)
        self.assertEqual(sorted(botoes), sorted(fichinha.MODOS))
        # Escolher a Capa tem de APAGAR a Ficha Total, ainda que estejam em
        # cantos opostos da faixa.
        botoes[fichinha.MODO_CAPA].click()
        self.assertEqual(escolhas, [fichinha.MODO_CAPA])
        self.assertFalse(botoes[fichinha.MODO_TOTAL].isChecked())
        self.assertTrue(botoes[fichinha.MODO_CAPA].isChecked())

    def test_todas_as_abas_aparecem_na_faixa(self):
        """A Total voltou à faixa a pedido do usuário (09/10/2026): "pode
        deixar a aba Total mostrando"."""
        faixa, botoes = fichinha.barra_de_modo(lambda _i: None)
        faixa.show()
        self.addCleanup(faixa.hide)
        for modo in fichinha.MODOS:
            self.assertTrue(botoes[modo].isVisible(),
                            f"modo {modo} sumiu da faixa")

    def test_a_capa_up_e_a_primeira_da_faixa(self):
        """Pedido do usuário (09/10/2026): "deixar a aba capa-up primeiro,
        depois seguir normalmente". O programa continua abrindo na Fichinha,
        "mesmo que fique diferente" — ver o teste do modo inicial.
        """
        self.assertEqual(fichinha.ROTULOS_MODO[0],
                         (fichinha.MODO_CAPA, "Capa-Up"))
        self.assertEqual(fichinha.MODOS[1:],
                         (fichinha.MODO_FICHINHA, fichinha.MODO_TOTAL,
                          fichinha.MODO_QUALIDADE, fichinha.MODO_FICHA_VIRTUAL,
                          fichinha.MODO_AGENDA, fichinha.MODO_RADIOTERADADOS))

    def test_cada_funcao_ve_as_suas_abas(self):
        """Pedido do usuário (26/08/2026): o médico abre o programa para
        consultar o que já aconteceu, e três abas de montagem de documento no
        caminho são três lugares onde ele pode se perder.

        A Agenda entrou em 23/09/2026 e é informação de SERVIÇO, não decisão
        clínica — ao contrário da Qualidade, todas as funções a veem.
        """
        self.assertEqual(fichinha.modos_do_papel("fisico"), fichinha.MODOS)
        self.assertEqual(fichinha.modos_do_papel("admin"), fichinha.MODOS)
        self.assertEqual(fichinha.modos_do_papel("medico"),
                         (fichinha.MODO_FICHA_VIRTUAL, fichinha.MODO_AGENDA))
        self.assertEqual(fichinha.modos_do_papel("dosimetrista"),
                         (fichinha.MODO_CAPA, fichinha.MODO_FICHA_VIRTUAL,
                          fichinha.MODO_AGENDA))

    def test_funcao_de_fora_do_mapa_fica_com_o_PADRAO(self):
        """Técnico, enfermeiro, recepcionista — e a função que ainda não
        existe. Acesso de MENOS alguém reclama no mesmo dia; acesso de mais
        ninguém percebe."""
        for papel in ("tecnico", "enfermeiro", "recepcionista", "inventado"):
            with self.subTest(papel=papel):
                self.assertEqual(fichinha.modos_do_papel(papel),
                                 fichinha.MODOS_PADRAO)

    def test_sem_ninguem_identificado_a_faixa_fica_inteira(self):
        """Papel VAZIO não é uma função: é a janela aberta sem login. Esconder
        aba de quem o programa não sabe quem é seria esconder por engano."""
        self.assertEqual(fichinha.modos_do_papel(""), fichinha.MODOS)
        self.assertEqual(fichinha.modos_do_papel(None), fichinha.MODOS)

    def test_a_ordem_da_faixa_manda_no_recorte(self):
        """A ordem sai de ``ROTULOS_MODO``, nunca da tupla do mapa: escrita
        duas vezes, ela ficaria errada na segunda e a faixa leria diferente
        conforme quem entrou."""
        self.assertEqual(
            list(fichinha.modos_do_papel("dosimetrista")),
            [m for m in fichinha.MODOS
             if m in fichinha.modos_do_papel("dosimetrista")])

    def test_o_programa_abre_na_primeira_aba_que_a_funcao_ve(self):
        """Abrir numa aba que a função não enxerga deixaria a faixa sem botão
        aceso e o miolo mostrando uma tela que ninguém pode escolher de volta."""
        self.assertEqual(fichinha.modo_inicial("fisico"),
                         fichinha.MODO_FICHINHA)
        self.assertEqual(fichinha.modo_inicial("medico"),
                         fichinha.MODO_FICHA_VIRTUAL)
        self.assertEqual(fichinha.modo_inicial("dosimetrista"),
                         fichinha.MODO_CAPA)

    def test_a_faixa_do_medico_tem_dois_botoes_e_a_Virtual_esta_acesa(self):
        """Virtual e Agenda (23/09/2026) — as duas abas de CONSULTA. A que
        acende é a Virtual, porque é o modo inicial do médico."""
        _faixa, botoes = fichinha.barra_de_modo(lambda _i: None,
                                                papel="medico")
        self.assertEqual(list(botoes),
                         [fichinha.MODO_FICHA_VIRTUAL, fichinha.MODO_AGENDA])
        self.assertTrue(botoes[fichinha.MODO_FICHA_VIRTUAL].isChecked())
        self.assertFalse(botoes[fichinha.MODO_AGENDA].isChecked())

    def test_a_faixa_nasce_com_a_tela_inicial_marcada(self):
        _faixa, botoes = fichinha.barra_de_modo(lambda _i: None)
        marcados = [m for m, b in botoes.items() if b.isChecked()]
        self.assertEqual(marcados, [fichinha.MODO_INICIAL])

    def test_a_ordem_da_faixa_nao_e_a_da_pilha(self):
        """Reordenar a faixa não pode renumerar as telas.

        O número é a posição no ``QStackedWidget`` da janela; a faixa é só a
        ordem de leitura. Trocar um pelo outro faria a barra apontar uma tela e
        o miolo mostrar outra.
        """
        self.assertEqual((fichinha.MODO_TOTAL, fichinha.MODO_FICHINHA,
                          fichinha.MODO_CAPA, fichinha.MODO_FICHA_VIRTUAL),
                         (0, 1, 2, 3))
        # E a faixa NÃO os lê nessa ordem: a Capa-Up vem primeiro. É o par de
        # afirmações que dá sentido ao nome deste teste.
        self.assertNotEqual(fichinha.MODOS,
                            tuple(range(len(fichinha.ROTULOS_MODO))))

    def test_sem_rotulos_de_grupo(self):
        """Só os botões: "Modo"/"Documentos" eram texto que ninguém precisava."""
        faixa, _botoes = fichinha.barra_de_modo(lambda _i: None)
        self.assertEqual(faixa.findChildren(QLabel), [])


# Esvazia ``estilo._ouvintes`` entre um teste e o seguinte. Sem isto, a lista
# cresce durante o arquivo inteiro e cada repintura percorre tudo o que já se
# acumulou — ver ``tests/limpeza_de_tela.py`` para os números.
from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


if __name__ == "__main__":
    unittest.main()
