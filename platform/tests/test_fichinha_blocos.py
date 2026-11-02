"""Os cartões da Fichinha v8: a peça comum, as Datas e as Altas Prontas.

A tela passou de dois quadros para cinco em 23/09/2026, e os dois que existiam
tinham o mesmo desenho escrito duas vezes — com diferenças que ninguém pediu.
O ``_Bloco`` é esse desenho num lugar só, e o ``_Linha`` é a linha com as ações
escondidas até o cursor chegar.

Aqui ficam os blocos que nasceram na v8 e ainda não tinham suíte: o quadro de
**Datas Relevantes** e o de **Altas Prontas**, mais as duas peças que os cinco
compartilham.

Rodar:  python -m unittest tests.test_fichinha_blocos -v
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
    from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem
    _APP = QApplication.instance() or QApplication([])
    from isocentro.interface import fichinha
except Exception:  # noqa: BLE001
    fichinha = None

from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


def _linha(lista, i):
    return lista.itemWidget(lista.item(i))


def _acesos(lista, i=0) -> set:
    return {k for k, b in _linha(lista, i)._botoes.items() if b.isEnabled()}


def _alta(paciente="FULANO", unidade="CEL", pdf="X:/p/ALTA_1.pdf",
          pasta="X:/p", data="10/09"):
    return {"paciente": paciente, "unidade": unidade, "pdf": pdf,
            "pasta": pasta, "data": data, "registro": "9000001"}


def _evento(titulo="Reunião de serviço", data="2026-10-01",
            tipo=fichinha.TIPO_SERVICO if fichinha else "", nota=""):
    return {"titulo": titulo, "data": data, "tipo": tipo, "nota": nota,
            "id": titulo}


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class APecaComum(unittest.TestCase):
    """``_Bloco`` — o que os cinco cartões têm igual."""

    def setUp(self):
        self.b = fichinha._Bloco("Documentação disponível")

    def test_o_titulo_e_etiqueta_em_versal(self):
        """O teal grande e centrado da v8.0 pesava mais que os nomes dos
        pacientes: o título não é conteúdo, é a legenda do que está embaixo."""
        self.assertEqual(self.b.titulo.text(), "DOCUMENTAÇÃO DISPONÍVEL")

    def test_o_cracha_so_aparece_com_numero(self):
        """Crachá vazio visível é vão reservado, e esta tela não tem."""
        self.assertTrue(self.b.cracha.isHidden())
        self.b.definir_cracha("12")
        self.assertFalse(self.b.cracha.isHidden())
        self.b.definir_cracha("")
        self.assertTrue(self.b.cracha.isHidden())

    def test_o_rodape_some_quando_nao_ha_recado(self):
        self.b.definir_rodape("lido às 14:02")
        self.assertFalse(self.b.rodape.isHidden())
        self.b.definir_rodape("")
        self.assertTrue(self.b.rodape.isHidden())

    def test_a_lista_nasce_com_altura_de_varias_linhas(self):
        """Sem isto o bloco nascia como uma tira de uma linha e pulava de
        tamanho quando a primeira resposta do banco chegava — e as cinco
        chegam em momentos diferentes, então a tela dançava na abertura."""
        self.b.ajustar_altura()
        self.assertGreaterEqual(
            self.b.lista.minimumHeight(), fichinha._LINHAS_MINIMAS * 32)

    def test_a_lista_cheia_nao_passa_do_teto(self):
        """Sem teto, a mais cheia empurra as outras para fora do campo de
        visão, e rolar a página inteira vira o único jeito de ver a de baixo."""
        for _ in range(40):
            self.b.lista.addItem("linha")
        self.b.ajustar_altura()
        altura_de_dez = fichinha.MAX_RECENTES * (
            self.b.lista.sizeHintForRow(0) or 32) + 8
        self.assertLessEqual(self.b.lista.minimumHeight(), altura_de_dez)

    def test_o_hover_acende_uma_linha_e_apaga_as_outras(self):
        """Guardar "a última" em vez de percorrer a lista deixava ações acesas
        para sempre quando a lista era redesenhada com o cursor parado nela."""
        linhas = []
        for i in range(3):
            w = fichinha._Linha({"i": i})
            w.definir_acoes(fichinha._ACOES_DATAS, lambda *_a: None)
            w.fechar()
            item = QListWidgetItem()
            self.b.lista.addItem(item)
            self.b.lista.setItemWidget(item, w)
            linhas.append(w)
        self.b.linha_sob_o_cursor(self.b.lista.item(1))
        self.assertEqual([w.acoes.isHidden() for w in linhas],
                         [True, False, True])
        self.b.linha_sob_o_cursor(None)
        self.assertEqual([w.acoes.isHidden() for w in linhas],
                         [True, True, True])


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class ALinha(unittest.TestCase):
    """``_Linha`` — o corpo transparente ao mouse e os ícones que não são."""

    def test_nenhuma_parte_da_linha_e_transparente_ao_mouse(self):
        """Este teste afirmava o CONTRÁRIO até 07/10/2026 — o corpo
        transparente — e era o defeito: o Qt pula a subárvore inteira de um
        widget transparente ao procurar quem está sob o cursor, e os ícones
        nunca recebiam o clique ("todos os botões em documentação somente
        abrem a prévia"). O clique no texto chega à lista sem o atributo,
        porque o evento ignorado sobe ao pai. A prova pelo ``childAt`` está em
        ``test_fichinha_icones``."""
        w = fichinha._Linha({})
        w.definir_acoes(fichinha._ACOES_DATAS, lambda *_a: None)
        w.fechar()
        self.assertFalse(w.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertFalse(
            w.acoes.testAttribute(Qt.WA_TransparentForMouseEvents))

    def test_a_faixa_de_acoes_guarda_o_lugar_dela_escondida(self):
        """``setFixedWidth`` sozinho não bastava: o Qt tira do layout o widget
        escondido, e o nome do paciente ia de 123 px para 1 px no instante em
        que o cursor chegava — o reflow que a reserva existe para impedir."""
        w = fichinha._Linha({})
        w.definir_acoes(fichinha._ACOES_DATAS, lambda *_a: None)
        w.fechar()
        self.assertTrue(w.acoes.sizePolicy().retainSizeWhenHidden())

    def test_linha_sem_acao_nenhuma_nao_mostra_faixa_vazia(self):
        w = fichinha._Linha({})
        w.fechar()
        w.mostrar_acoes(True)
        self.assertTrue(w.acoes.isHidden())

    def test_a_dica_de_um_icone_troca_sem_mexer_nos_outros(self):
        """A Impressão vira liberação quando o caso veio da temporária, e
        apagada precisa dizer por quê — com ícone, o tooltip é o único canal."""
        w = fichinha._Linha({})
        w.definir_acoes(fichinha._ACOES_DOC, lambda *_a: None)
        w.fechar()
        w.definir_dica(fichinha.IMPRIMIR, "outra coisa")
        self.assertEqual(w._botoes[fichinha.IMPRIMIR].toolTip(), "outra coisa")
        self.assertEqual(w._botoes[fichinha.EDITAR].toolTip(),
                         fichinha._DICAS_DOC[fichinha.EDITAR])


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class DatasRelevantes(unittest.TestCase):
    """O quadro do serviço — eventos criados à mão, nada vem do banco."""

    def setUp(self):
        self.p = fichinha.PainelFichinha()

    def test_a_lista_sai_em_ordem_de_DATA(self):
        """Um quadro de datas lido de cima para baixo tem de responder "o que
        vem primeiro" — ordem de criação não responde nada."""
        self.p.definir_datas([_evento("terceiro", "2026-12-01"),
                              _evento("primeiro", "2026-10-01"),
                              _evento("segundo", "2026-11-01")])
        titulos = [self.p.datas.item(i).data(Qt.UserRole)["titulo"]
                   for i in range(self.p.datas.count())]
        self.assertEqual(titulos, ["primeiro", "segundo", "terceiro"])

    def test_evento_sem_data_vai_para_o_FIM_em_vez_de_sumir(self):
        """Campo sem fonte nasce vazio e a tela mostra — sumir esconderia um
        evento que alguém criou."""
        self.p.definir_datas([_evento("sem data", ""),
                              _evento("com data", "2026-10-01")])
        ultimo = self.p.datas.item(
            self.p.datas.count() - 1).data(Qt.UserRole)
        self.assertEqual(ultimo["titulo"], "sem data")

    def test_o_filtro_por_tipo_redesenha_sem_reler(self):
        self.p.definir_datas([_evento("do serviço", tipo=fichinha.TIPO_SERVICO),
                              _evento("pessoal", "2026-10-02",
                                      tipo=fichinha.TIPO_PESSOAL)])
        self.p._filtrar_datas(fichinha.TIPO_PESSOAL)
        self.assertEqual(self.p.datas.count(), 1)
        self.assertEqual(self.p.datas.item(0).data(Qt.UserRole)["titulo"],
                         "pessoal")
        # A lista inteira continua na memória: voltar a "Todas" não relê o
        # arquivo do serviço.
        self.p._filtrar_datas("")
        self.assertEqual(self.p.datas.count(), 2)

    def test_filtro_sem_nada_diz_QUAL_tipo_esta_vazio(self):
        """"Nenhum evento" seco faria a pessoa achar que o quadro inteiro está
        vazio, quando o que está vazio é o recorte que ela escolheu."""
        self.p.definir_datas([_evento(tipo=fichinha.TIPO_SERVICO)])
        self.p._filtrar_datas(fichinha.TIPO_COMEMORATIVA)
        self.assertEqual(self.p.datas.count(), 1)
        self.assertIn(fichinha.TIPO_COMEMORATIVA, self.p.datas.item(0).text())
        # E o convite não é um evento: não dá para clicar nele.
        self.assertFalse(self.p.datas.item(0).flags() & Qt.ItemIsEnabled)

    def test_quadro_vazio_convida_a_criar(self):
        self.p.definir_datas([])
        self.assertIn("Nova", self.p.datas.item(0).text())

    def test_cada_icone_pede_a_sua_acao_sobre_o_evento_da_linha(self):
        self.p.definir_datas([_evento("primeiro", "2026-10-01"),
                              _evento("segundo", "2026-11-01")])
        pedidos = []
        self.p.acao_data.connect(lambda a, ev: pedidos.append((a, ev["titulo"])))
        _linha(self.p.datas, 1)._botoes[fichinha.EDITAR_DATA].click()
        _linha(self.p.datas, 0)._botoes[fichinha.EXCLUIR_DATA].click()
        self.assertEqual(pedidos, [(fichinha.EDITAR_DATA, "segundo"),
                                   (fichinha.EXCLUIR_DATA, "primeiro")])

    def test_a_nota_do_evento_fica_no_tooltip(self):
        """A linha só cabe data, título e etiqueta; a nota é o resto."""
        self.p.definir_datas([_evento(nota="levar o relatório do mês")])
        self.assertEqual(self.p.datas.item(0).toolTip(),
                         "levar o relatório do mês")


@unittest.skipIf(fichinha is None, "PySide6 indisponível")
class AltasProntas(unittest.TestCase):
    """As altas a imprimir: seleção múltipla, chip por unidade, PDF em disco."""

    def setUp(self):
        self.p = fichinha.PainelFichinha()

    def test_sem_resposta_do_sistema_e_diferente_de_nada_pendente(self):
        """É a leitura errada mais cara deste bloco: "o servidor não respondeu"
        e "está tudo em dia" saem idênticos, e a segunda é a que a pessoa leva
        para casa."""
        self.p.definir_altas(None, recado="Não deu para perguntar.")
        self.assertIn("Não deu para perguntar", self.p.altas.item(0).text())
        self.p.definir_altas([])
        self.assertIn("Nenhuma alta pendente", self.p.altas.item(0).text())

    def test_o_recado_vai_para_a_lista_OU_para_o_rodape(self):
        """Repetido nos dois, lia como se fossem dois problemas."""
        self.p.definir_altas(None, recado="Sem resposta.")
        self.assertEqual(self.p.b_altas.rodape.text(), "")
        self.p.definir_altas([_alta()], recado="lido às 14:02")
        self.assertEqual(self.p.b_altas.rodape.text(), "lido às 14:02")

    def test_o_cracha_conta_quantas_folhas_vao_sair(self):
        self.p.definir_altas([_alta(), _alta("SICRANO"), _alta("BELTRANO")])
        self.assertEqual(self.p.b_altas.cracha.text(), "3")

    def test_um_chip_por_unidade_PRESENTE_com_a_contagem(self):
        """Chip que nunca tem nada é um alvo que ensina a não clicar."""
        self.p.definir_altas([_alta(unidade="CEL"), _alta(unidade="CEL"),
                              _alta(unidade="ANA")])
        self.assertEqual(sorted(self.p._chips_unidade), ["ANA", "CEL"])
        self.assertEqual(self.p._chips_unidade["CEL"].text(), "CEL  2")

    def test_o_chip_marca_a_unidade_inteira_e_desmarca_no_segundo_clique(self):
        """Sem desmarcar, o único jeito de desfazer seria clicar numa linha
        qualquer — e quem marcou doze por engano não adivinha esse gesto."""
        self.p.definir_altas([_alta("A", "CEL"), _alta("B", "CEL"),
                              _alta("C", "ANA")])
        self.p._chips_unidade["CEL"].click()
        self.assertEqual({e["paciente"] for e in self.p.altas_escolhidas()},
                         {"A", "B"})
        self.p._chips_unidade["CEL"].click()
        self.assertEqual(self.p.altas_escolhidas(), [])

    def test_o_chip_so_fica_marcado_com_a_unidade_INTEIRA_na_selecao(self):
        """É o que distingue "marquei o CEL" de "marquei dois pacientes que por
        acaso são do CEL"."""
        self.p.definir_altas([_alta("A", "CEL"), _alta("B", "CEL")])
        self.p.altas.item(0).setSelected(True)
        self.p._selecao_mudou()
        self.assertFalse(self.p._chips_unidade["CEL"].isChecked())
        self.p.altas.item(1).setSelected(True)
        self.p._selecao_mudou()
        self.assertTrue(self.p._chips_unidade["CEL"].isChecked())

    def test_sem_PDF_em_disco_o_icone_de_abrir_fica_apagado(self):
        """Aceso e sem arquivo, o clique só teria como avisar que não deu — e
        o aviso chegaria depois do clique."""
        self.p.definir_altas([_alta(pdf="")])
        self.assertEqual(_acesos(self.p.altas), {fichinha.PASTA_ALTA})

    def test_sem_pasta_o_icone_da_pasta_tambem(self):
        self.p.definir_altas([_alta(pasta="")])
        self.assertEqual(_acesos(self.p.altas), {fichinha.ABRIR_ALTA})

    def test_o_icone_age_sobre_a_SELECAO_quando_ha_uma(self):
        """É a única lista assim, e é o pedido: escolher vários pacientes e
        abrir todas as altas de uma vez."""
        self.p.definir_altas([_alta("A"), _alta("B"), _alta("C")])
        pedidos = []
        self.p.acao_alta.connect(
            lambda a, es: pedidos.append((a, [e["paciente"] for e in es])))
        self.p.altas.item(0).setSelected(True)
        self.p.altas.item(1).setSelected(True)
        _linha(self.p.altas, 0)._botoes[fichinha.ABRIR_ALTA].click()
        self.assertEqual(pedidos, [(fichinha.ABRIR_ALTA, ["A", "B"])])

    def test_clicar_fora_da_selecao_age_sobre_a_LINHA_clicada(self):
        """Senão o clique faria uma coisa invisível, longe de onde o cursor
        está."""
        self.p.definir_altas([_alta("A"), _alta("B"), _alta("C")])
        pedidos = []
        self.p.acao_alta.connect(
            lambda a, es: pedidos.append([e["paciente"] for e in es]))
        self.p.altas.item(0).setSelected(True)
        _linha(self.p.altas, 2)._botoes[fichinha.ABRIR_ALTA].click()
        self.assertEqual(pedidos, [["C"]])

    def test_a_lista_aceita_marcar_varias(self):
        self.p.definir_altas([_alta("A"), _alta("B")])
        self.assertEqual(self.p.altas.selectionMode(),
                         QListWidget.ExtendedSelection)

    def test_o_icone_do_cabecalho_so_existe_com_alguma_marcada(self):
        """Ele abre TODAS as marcadas de uma vez: sem seleção não há o que
        abrir, e um ícone parado no canto ensinaria a clicar em nada."""
        self.p.definir_altas([_alta("A")])
        self.assertTrue(self.p._btn_abrir_altas.isHidden())
        self.p.altas.item(0).setSelected(True)
        self.assertFalse(self.p._btn_abrir_altas.isHidden())
        self.assertTrue(self.p._btn_abrir_altas.isEnabled())

    def test_o_icone_do_cabecalho_apaga_se_nenhuma_marcada_tem_PDF(self):
        self.p.definir_altas([_alta("A", pdf="")])
        self.p.altas.item(0).setSelected(True)
        self.assertFalse(self.p._btn_abrir_altas.isEnabled())

    def test_recarregar_nao_acumula_chip_nem_linha(self):
        """Os chips são recriados a cada leitura: a lista de unidades muda com
        o serviço."""
        self.p.definir_altas([_alta("A", "CEL"), _alta("B", "ANA")])
        self.p.definir_altas([_alta("C", "BET")])
        self.assertEqual(self.p.altas.count(), 1)
        self.assertEqual(list(self.p._chips_unidade), ["BET"])


if __name__ == "__main__":
    unittest.main()
